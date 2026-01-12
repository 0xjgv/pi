"""Staged workflow orchestrator with early-exit capability."""

from __future__ import annotations

import logging
import time
from typing import TYPE_CHECKING

import dspy

from π.support.aitl import AgentQuestionAnswerer
from π.workflow.checkpoint import (
    CheckpointManager,
    CheckpointState,
    WorkflowStage,
)
from π.workflow.context import get_ctx
from π.workflow.staged import (
    stage_design,
    stage_execute,
    stage_research,
)
from π.workflow.types import DesignResult, ExecuteResult, ResearchResult

if TYPE_CHECKING:
    from collections.abc import Callable

logger = logging.getLogger(__name__)

# Retry configuration
BASE_RETRY_DELAY = 1.0  # seconds


def _run_with_retry[T: (ResearchResult, DesignResult, ExecuteResult)](
    *,
    stage_fn: Callable[[], T],
    stage: WorkflowStage,
    checkpoint: CheckpointManager,
    objective: str,
) -> T:
    """Execute a stage function with retry logic.

    Uses exponential backoff between attempts (1s, 2s, 4s) and clears
    session IDs at the start of each retry to avoid resuming invalid sessions.

    Args:
        stage_fn: Zero-arg callable that executes the stage.
        stage: The workflow stage being executed.
        checkpoint: CheckpointManager for tracking attempts.
        objective: The workflow objective.

    Returns:
        Stage result on success.

    Raises:
        Exception: Re-raises last exception if all retries exhausted.
    """
    attempt = checkpoint.get_attempt_count(stage)
    last_error: Exception | None = None
    ctx = get_ctx()

    while attempt < checkpoint.max_retries:
        attempt += 1
        logger.info(
            "Stage %s attempt %d/%d", stage.value, attempt, checkpoint.max_retries
        )

        # Clear session IDs at retry start to avoid resuming invalid sessions
        # (Claude SDK session IDs are ephemeral and invalid across CLI restarts)
        if attempt > 1:
            ctx.session_ids.clear()
            logger.debug("Cleared session IDs for retry")

        try:
            result = stage_fn()
            checkpoint.save_stage_result(
                objective=objective,
                stage=stage,
                result=result,
                attempt_count=attempt,
            )
            return result

        except ValueError as e:
            # User input errors - log and retry
            last_error = e
            logger.warning(
                "Stage %s attempt %d failed (ValueError): %s",
                stage.value,
                attempt,
                e,
            )

        except Exception as e:
            # Transient failures - log type and retry
            last_error = e
            logger.warning(
                "Stage %s attempt %d failed (%s): %s",
                stage.value,
                attempt,
                type(e).__name__,
                e,
            )

        # Exponential backoff before next attempt
        if attempt < checkpoint.max_retries:
            delay = BASE_RETRY_DELAY * (2 ** (attempt - 1))  # 1s, 2s, 4s
            logger.info("Retrying in %.1fs...", delay)
            time.sleep(delay)

    # All retries exhausted - re-raise with context
    msg = f"Stage {stage.value} failed after {checkpoint.max_retries} attempts"
    logger.error("%s: %s", msg, last_error)
    raise type(last_error)(f"{msg}: {last_error}") from last_error


class StagedWorkflow(dspy.Module):
    """Three-stage workflow with early-exit after research.

    Stages:
        1. Research (triage gate) - can exit if needs_implementation=False
        2. Design (plan + review + iterate)
        3. Execute (implement + commit)
    """

    def __init__(
        self,
        lm: dspy.LM,
        *,
        checkpoint: CheckpointManager | None = None,
    ) -> None:
        super().__init__()
        self.lm = lm
        self.checkpoint = checkpoint or CheckpointManager()

    def forward(
        self,
        objective: str,
        *,
        resume_state: CheckpointState | None = None,
    ) -> dspy.Prediction:
        """Execute the workflow with checkpoint support.

        Args:
            objective: The workflow objective.
            resume_state: Optional checkpoint state to resume from.

        Returns:
            dspy.Prediction with workflow results.
        """
        # Configure explicit agent-based question answering
        ctx = get_ctx()
        ctx.input_provider = AgentQuestionAnswerer()

        # Determine starting point
        if resume_state:
            research = resume_state.research_result
            design = resume_state.design_result
            start_stage = self.checkpoint.get_resume_stage()
            logger.info("Resuming from checkpoint: next_stage=%s", start_stage)
        else:
            research = None
            design = None
            start_stage = WorkflowStage.RESEARCH

        # Stage 1: Research (triage gate)
        if start_stage == WorkflowStage.RESEARCH:
            logger.info("=== STAGE 1/3: RESEARCH ===")
            try:
                research = _run_with_retry(
                    stage_fn=lambda: stage_research(objective=objective, lm=self.lm),
                    stage=WorkflowStage.RESEARCH,
                    checkpoint=self.checkpoint,
                    objective=objective,
                )
            except Exception as e:
                logger.error("Research failed: %s", e)
                return dspy.Prediction(status="failed", reason=str(e))

        # Ensure research is not None at this point
        assert research is not None, "Research result required"

        # Helper to get research paths as list
        research_paths = [doc.path for doc in research.research_docs]

        # Early exit if already complete
        if not research.needs_implementation:
            logger.info("Early exit: %s", research.reason)
            self.checkpoint.clear()  # No further work needed
            return dspy.Prediction(
                research_doc_paths=research_paths,
                status="already_complete",
                reason=research.reason,
            )

        # Stage 2: Design (plan + review + iterate)
        # Run design if: starting at or before DESIGN stage AND no design result yet
        stages = list(WorkflowStage)
        start_idx = stages.index(start_stage)
        design_idx = stages.index(WorkflowStage.DESIGN)

        if start_idx <= design_idx and design is None:
            logger.info("=== STAGE 2/3: DESIGN ===")
            try:
                design = _run_with_retry(
                    stage_fn=lambda: stage_design(
                        research=research,
                        objective=objective,
                        lm=self.lm,
                    ),
                    stage=WorkflowStage.DESIGN,
                    checkpoint=self.checkpoint,
                    objective=objective,
                )
            except Exception as e:
                logger.error("Design failed: %s", e)
                return dspy.Prediction(
                    research_doc_paths=research_paths,
                    status="failed",
                    reason=str(e),
                )

        # Ensure design is not None at this point
        assert design is not None, "Design result required"

        # Stage 3: Execute (implement + commit)
        logger.info("=== STAGE 3/3: EXECUTE ===")
        try:
            execute = _run_with_retry(
                stage_fn=lambda: stage_execute(
                    plan_doc=design.plan_doc,
                    objective=objective,
                    lm=self.lm,
                ),
                stage=WorkflowStage.EXECUTE,
                checkpoint=self.checkpoint,
                objective=objective,
            )
        except Exception as e:
            logger.error("Execute failed: %s", e)
            return dspy.Prediction(
                research_doc_paths=research_paths,
                plan_doc_path=design.plan_doc.path,
                status="failed",
                reason=str(e),
            )

        # Workflow complete - clear checkpoint
        self.checkpoint.clear()

        return dspy.Prediction(
            research_doc_paths=research_paths,
            files_changed=execute.files_changed,
            plan_doc_path=design.plan_doc.path,
            commit_hash=execute.commit_hash,
            status=execute.status,
        )
