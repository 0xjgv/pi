"""Checkpoint integration for queue-based workflow."""

from π.core.enums import WorkflowStage
from π.workflow.checkpoint import CheckpointManager
from π.workflow.types import (
    DesignResult,
    ExecuteResult,
    PlanDocPath,
    ResearchDocPath,
    ResearchResult,
)

from .models import DesignOutput, ExecuteOutput, ResearchOutput


def research_to_checkpoint(output: ResearchOutput) -> ResearchResult:
    """Convert queue ResearchOutput to checkpoint ResearchResult."""
    return ResearchResult(
        research_docs=[ResearchDocPath(path=p) for p in output.research_docs],
        needs_implementation=output.needs_implementation,
        summaries=output.summaries,
        reason=output.reason,
    )


def design_to_checkpoint(output: DesignOutput) -> DesignResult:
    """Convert queue DesignOutput to checkpoint DesignResult."""
    return DesignResult(
        plan_doc=PlanDocPath(path=output.plan_path),
        estimated_changes=output.estimated_changes,
        summary=output.summary,
    )


def execute_to_checkpoint(output: ExecuteOutput) -> ExecuteResult:
    """Convert queue ExecuteOutput to checkpoint ExecuteResult."""
    return ExecuteResult(
        files_changed=output.files_changed,
        status=output.status,
        commit_hash=output.commit_hash,
    )


def save_queue_checkpoint(
    checkpoint: CheckpointManager,
    objective: str,
    stage: WorkflowStage,
    output: ResearchOutput | DesignOutput | ExecuteOutput,
) -> None:
    """Save queue output to checkpoint system."""
    converters = {
        WorkflowStage.RESEARCH: research_to_checkpoint,
        WorkflowStage.DESIGN: design_to_checkpoint,
        WorkflowStage.EXECUTE: execute_to_checkpoint,
    }

    converter = converters[stage]
    result = converter(output)  # type: ignore[arg-type]
    checkpoint.save_stage_result(
        objective=objective,
        stage=stage,
        result=result,
    )
