"""Queue-based workflow orchestrator."""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any, Literal

from π.core.enums import WorkflowStage

from .checkpoint import save_queue_checkpoint
from .models import (
    CreatePlanOutput,
    DesignOutput,
    ExecuteOutput,
    ImplementOutput,
    IteratePlanOutput,
    ResearchOutput,
    ReviewPlanOutput,
)
from .queue import (
    StageQueue,
    create_design_queue,
    create_execute_queue,
    create_research_queue,
)

if TYPE_CHECKING:
    from π.workflow.checkpoint import CheckpointManager

    from .models import CommitOutput

logger = logging.getLogger(__name__)


@dataclass
class WorkflowResult:
    """Final result from workflow execution."""

    research: ResearchOutput
    design: DesignOutput | None = None
    execute: ExecuteOutput | None = None
    status: Literal["complete", "no_implementation", "failed"] = "complete"


@dataclass
class QueueOrchestrator:
    """Manages stage queues and orchestrates workflow execution.

    Pattern:
        orchestrator.send(stage, message) -> typed response
        orchestrator.evaluate(response) -> next action
    """

    objective: str
    max_design_iterations: int = 3
    checkpoint: CheckpointManager | None = field(default=None)

    # Stage queues (lazy initialized)
    _research_queue: StageQueue[ResearchOutput] | None = field(default=None)
    _design_queues: dict[str, StageQueue[Any]] = field(default_factory=dict)
    _execute_queues: dict[str, StageQueue[Any]] = field(default_factory=dict)

    # Stage results (accumulated)
    _research_result: ResearchOutput | None = field(default=None)
    _design_result: DesignOutput | None = field(default=None)

    def _save_checkpoint(
        self,
        stage: WorkflowStage,
        output: ResearchOutput | DesignOutput | ExecuteOutput,
    ) -> None:
        """Save stage result to checkpoint if checkpoint manager is configured."""
        if self.checkpoint is not None:
            save_queue_checkpoint(self.checkpoint, self.objective, stage, output)

    @property
    def research_queue(self) -> StageQueue[ResearchOutput]:
        """Get or create research queue."""
        if self._research_queue is None:
            self._research_queue = create_research_queue()
        return self._research_queue

    def design_queue(
        self, sub_stage: Literal["create", "review", "iterate"]
    ) -> StageQueue[Any]:
        """Get or create design sub-stage queue."""
        if sub_stage not in self._design_queues:
            self._design_queues[sub_stage] = create_design_queue(sub_stage)
        return self._design_queues[sub_stage]

    def execute_queue(
        self, sub_stage: Literal["implement", "commit"]
    ) -> StageQueue[Any]:
        """Get or create execute sub-stage queue."""
        if sub_stage not in self._execute_queues:
            self._execute_queues[sub_stage] = create_execute_queue(sub_stage)
        return self._execute_queues[sub_stage]

    async def run(self) -> WorkflowResult:
        """Execute the full workflow."""
        # =================================================================
        # Stage 1: Research
        # =================================================================
        logger.info("Starting research stage")
        research = await self._run_research()
        self._save_checkpoint(WorkflowStage.RESEARCH, research)

        if not research.needs_implementation:
            logger.info("No implementation needed: %s", research.reason)
            if self.checkpoint is not None:
                self.checkpoint.clear()
            return WorkflowResult(
                research=research,
                status="no_implementation",
            )

        # =================================================================
        # Stage 2: Design
        # =================================================================
        logger.info("Starting design stage")
        design = await self._run_design(research)
        self._save_checkpoint(WorkflowStage.DESIGN, design)

        # =================================================================
        # Stage 3: Execute
        # =================================================================
        logger.info("Starting execute stage")
        execute = await self._run_execute(design)
        self._save_checkpoint(WorkflowStage.EXECUTE, execute)

        if self.checkpoint is not None:
            self.checkpoint.clear()

        return WorkflowResult(
            research=research,
            design=design,
            execute=execute,
            status="complete" if execute.status == "success" else "failed",
        )

    async def _run_research(self) -> ResearchOutput:
        """Execute research stage via queue."""
        message = f"/1_research_codebase {self.objective}"
        return await self.research_queue.send(message)

    async def _run_design(self, research: ResearchOutput) -> DesignOutput:
        """Execute design stage with create->review->iterate loop."""
        # Step 1: Create plan
        research_docs_str = (
            ", ".join(research.research_docs) if research.research_docs else "none"
        )
        context = f"""
Objective: {self.objective}
Research findings: {", ".join(research.summaries)}
Research docs: {research_docs_str}
"""
        create_result: CreatePlanOutput = await self.design_queue("create").send(
            f"/2_create_plan {context}"
        )
        plan_path = create_result.plan_path
        summary = create_result.summary
        iterations = 0

        # Step 2-3: Review -> Iterate loop
        for _i in range(self.max_design_iterations):
            review_result: ReviewPlanOutput = await self.design_queue("review").send(
                f"/3_review_plan {plan_path}"
            )

            if review_result.approved:
                logger.info("Plan approved after %d iterations", iterations)
                break

            logger.info(
                "Review found issues (severity=%s): %s",
                review_result.severity,
                review_result.issues,
            )

            # Iterate to address issues
            issues_str = "\n".join(f"- {issue}" for issue in review_result.issues)
            iterate_result: IteratePlanOutput = await self.design_queue("iterate").send(
                f"/4_iterate_plan {plan_path}\nIssues to address:\n{issues_str}"
            )

            plan_path = iterate_result.plan_path
            summary = iterate_result.summary
            iterations += 1

        return DesignOutput(
            plan_path=plan_path,
            summary=summary,
            iterations=iterations,
        )

    async def _run_execute(self, design: DesignOutput) -> ExecuteOutput:
        """Execute implementation stage."""
        # Step 1: Implement
        implement_result: ImplementOutput = await self.execute_queue("implement").send(
            f"/5_implement_plan {design.plan_path}"
        )

        if implement_result.status == "failed":
            return ExecuteOutput(
                files_changed=implement_result.files_changed,
                status="failed",
            )

        # Step 2: Commit (if changes made)
        if implement_result.files_changed:
            files_str = ", ".join(implement_result.files_changed)
            commit_result: CommitOutput = await self.execute_queue("commit").send(
                f"/6_commit\nFiles changed: {files_str}"
            )

            return ExecuteOutput(
                files_changed=implement_result.files_changed,
                status=implement_result.status,
                commit_hash=commit_result.commit_hash,
            )

        return ExecuteOutput(
            files_changed=[],
            status=implement_result.status,
        )
