"""Staged workflow orchestrator with early-exit capability."""

from __future__ import annotations

import logging

import dspy

from π.config import Provider, Tier, get_lm
from π.workflow.staged import (
    stage_design,
    stage_execute,
    stage_research,
)

logger = logging.getLogger(__name__)


class StagedWorkflow(dspy.Module):
    """Three-stage workflow with early-exit after research.

    Stages:
        1. Research (triage gate) - can exit if needs_implementation=False
        2. Design (plan + review + iterate)
        3. Execute (implement + commit)
    """

    def __init__(self, lm: dspy.LM | None = None) -> None:
        """Initialize workflow with optional LM.

        Args:
            lm: DSPy language model. Defaults to Claude HIGH tier.
        """
        super().__init__()
        self.lm = lm

    def forward(self, objective: str) -> dspy.Prediction:
        """Execute staged workflow with early-exit capability.

        Args:
            objective: The objective to accomplish.

        Returns:
            dspy.Prediction with status and document paths.
        """
        # Get LM (from init or default)
        lm = self.lm or get_lm(Provider.Claude, Tier.HIGH)

        # Stage 1: Research (triage gate)
        logger.info("=== STAGE 1/3: RESEARCH ===")
        try:
            research = stage_research(objective=objective, lm=lm)
        except ValueError as e:
            logger.error("Research failed: %s", e)
            return dspy.Prediction(
                status="failed",
                reason=str(e),
            )

        # Early exit if already complete
        if not research.needs_implementation:
            logger.info("Early exit: %s", research.reason)
            return dspy.Prediction(
                research_doc_path=research.research_doc.path,
                status="already_complete",
                reason=research.reason,
            )

        # Stage 2: Design (plan + review + iterate)
        logger.info("=== STAGE 2/3: DESIGN ===")
        try:
            design = stage_design(
                research_doc=research.research_doc,
                objective=objective,
                lm=lm,
            )
        except ValueError as e:
            logger.error("Design failed: %s", e)
            return dspy.Prediction(
                status="failed",
                reason=str(e),
                research_doc_path=research.research_doc.path,
            )

        # Stage 3: Execute (implement + commit)
        logger.info("=== STAGE 3/3: EXECUTE ===")
        try:
            execute = stage_execute(
                plan_doc=design.plan_doc,
                objective=objective,
                lm=lm,
            )
        except ValueError as e:
            logger.error("Execute failed: %s", e)
            return dspy.Prediction(
                status="failed",
                reason=str(e),
                research_doc_path=research.research_doc.path,
                plan_doc_path=design.plan_doc.path,
            )

        return dspy.Prediction(
            status=execute.status,
            research_doc_path=research.research_doc.path,
            plan_doc_path=design.plan_doc.path,
            files_changed=execute.files_changed,
            commit_hash=execute.commit_hash,
        )
