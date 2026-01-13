"""Stage-level checkpointing with retry capability.

Provides persistence for workflow stage results, enabling resume after
interruption and automatic retry of failed stages.
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import StrEnum
from pathlib import Path
from typing import Any

from pydantic import BaseModel

from π.support.directory import get_project_root
from π.workflow.types import DesignResult, ExecuteResult, ResearchResult

logger = logging.getLogger(__name__)

CHECKPOINT_FILE = ".π/checkpoint.json"
DEFAULT_MAX_RETRIES = 3


class WorkflowStage(StrEnum):
    """Workflow stages for checkpoint tracking."""

    RESEARCH = "research"
    DESIGN = "design"
    EXECUTE = "execute"


class StageCheckpoint(BaseModel):
    """Checkpoint data for a single stage."""

    stage: WorkflowStage
    completed_at: str
    attempt_count: int = 1
    result: dict[str, Any]  # Serialized stage result


class CheckpointState(BaseModel):
    """Complete checkpoint state for a workflow run."""

    objective: str
    created_at: str
    updated_at: str
    last_completed_stage: WorkflowStage | None = None
    stages: dict[WorkflowStage, StageCheckpoint] = {}

    # Stage results (populated when loaded)
    research_result: ResearchResult | None = None
    design_result: DesignResult | None = None
    execute_result: ExecuteResult | None = None

    @classmethod
    def validate_paths(cls, data: dict[str, Any]) -> list[str]:
        """Check if all referenced document paths exist before full deserialization.

        Args:
            data: Raw checkpoint data dict.

        Returns:
            List of missing paths (empty if all valid).
        """
        missing: list[str] = []
        stages = data.get("stages", {})

        for stage_data in stages.values():
            result = stage_data.get("result", {})
            # Check research docs
            for doc in result.get("research_docs", []):
                path = doc.get("path") if isinstance(doc, dict) else None
                if path and not Path(path).exists():
                    missing.append(path)
            # Check plan doc
            plan_doc = result.get("plan_doc")
            if plan_doc:
                path = plan_doc.get("path") if isinstance(plan_doc, dict) else None
                if path and not Path(path).exists():
                    missing.append(path)

        return missing

    def is_stale(self, *, max_age_hours: int = 24) -> bool:
        """Check if checkpoint is older than max_age_hours.

        Args:
            max_age_hours: Maximum age in hours before considered stale.

        Returns:
            True if checkpoint is stale.
        """
        updated = datetime.fromisoformat(self.updated_at)
        age = datetime.now(UTC) - updated
        return age.total_seconds() > max_age_hours * 3600


@dataclass
class CheckpointManager:
    """Manages checkpoint persistence and stage retry logic.

    Follows the DocSyncState pattern from π/doc_sync/core.py.
    """

    max_retries: int = DEFAULT_MAX_RETRIES
    _state: CheckpointState | None = field(default=None, repr=False)

    @property
    def checkpoint_path(self) -> Path:
        """Get the checkpoint file path."""
        return get_project_root() / CHECKPOINT_FILE

    def load(self) -> CheckpointState | None:
        """Load checkpoint state from file.

        Uses validate_paths() to check path existence before full deserialization,
        avoiding ValidationError from Pydantic path validators on missing files.

        Returns:
            CheckpointState if file exists and is valid, None otherwise.
        """
        if not self.checkpoint_path.exists():
            return None

        try:
            data = json.loads(self.checkpoint_path.read_text())

            # Check paths exist before running validators
            missing = CheckpointState.validate_paths(data)
            if missing:
                logger.warning(
                    "Checkpoint references missing paths, clearing: %s", missing
                )
                self.clear()
                return None

            state = CheckpointState.model_validate(data)

            # Restore typed result objects from serialized data
            if WorkflowStage.RESEARCH in state.stages:
                state.research_result = ResearchResult.model_validate(
                    state.stages[WorkflowStage.RESEARCH].result
                )
            if WorkflowStage.DESIGN in state.stages:
                state.design_result = DesignResult.model_validate(
                    state.stages[WorkflowStage.DESIGN].result
                )
            if WorkflowStage.EXECUTE in state.stages:
                state.execute_result = ExecuteResult.model_validate(
                    state.stages[WorkflowStage.EXECUTE].result
                )

            self._state = state
            logger.info("Loaded checkpoint: last_stage=%s", state.last_completed_stage)
            return state

        except (json.JSONDecodeError, ValueError) as e:
            logger.warning("Failed to load checkpoint: %s", e)
            return None

    def save(self, state: CheckpointState) -> None:
        """Persist checkpoint state to file atomically.

        Uses write-to-temp-then-rename pattern to prevent corruption.
        """
        state.updated_at = datetime.now(UTC).isoformat()
        self.checkpoint_path.parent.mkdir(parents=True, exist_ok=True)

        # Atomic write: temp file then rename
        temp_path = self.checkpoint_path.with_suffix(".tmp")
        temp_path.write_text(json.dumps(state.model_dump(mode="json"), indent=2))
        temp_path.rename(self.checkpoint_path)

        self._state = state
        logger.info("Saved checkpoint: last_stage=%s", state.last_completed_stage)

    def clear(self) -> None:
        """Delete checkpoint file."""
        if self.checkpoint_path.exists():
            self.checkpoint_path.unlink()
            logger.info("Cleared checkpoint")
        self._state = None

    def has_checkpoint(self) -> bool:
        """Check if a checkpoint file exists."""
        return self.checkpoint_path.exists()

    def get_resume_stage(self) -> WorkflowStage | None:
        """Get the next stage to execute after resume.

        Returns:
            Next stage after last completed, or None if workflow is complete.
        """
        state = self._state or self.load()
        if state is None or state.last_completed_stage is None:
            return WorkflowStage.RESEARCH

        stages = list(WorkflowStage)
        current_idx = stages.index(state.last_completed_stage)

        if current_idx >= len(stages) - 1:
            return None  # Workflow complete

        return stages[current_idx + 1]

    def save_stage_result(
        self,
        *,
        objective: str,
        stage: WorkflowStage,
        result: ResearchResult | DesignResult | ExecuteResult,
        attempt_count: int = 1,
    ) -> None:
        """Save a stage result to checkpoint.

        Args:
            objective: The workflow objective.
            stage: The completed stage.
            result: The stage result (Pydantic model).
            attempt_count: Number of attempts for this stage.

        Raises:
            ValueError: If existing checkpoint has different objective.
        """
        now = datetime.now(UTC).isoformat()

        # Load existing or create new state
        state = (
            self._state
            or self.load()
            or CheckpointState(
                objective=objective,
                created_at=now,
                updated_at=now,
            )
        )

        # Validate objective consistency
        if state.objective != objective:
            msg = (
                f"Objective mismatch: checkpoint has '{state.objective}', "
                f"but current is '{objective}'. Clear checkpoint first."
            )
            raise ValueError(msg)

        # Update state with new stage result
        state.stages[stage] = StageCheckpoint(
            stage=stage,
            completed_at=now,
            attempt_count=attempt_count,
            result=result.model_dump(mode="json"),
        )
        state.last_completed_stage = stage

        # Store typed result via attribute mapping
        result_attrs = {
            WorkflowStage.RESEARCH: "research_result",
            WorkflowStage.DESIGN: "design_result",
            WorkflowStage.EXECUTE: "execute_result",
        }
        setattr(state, result_attrs[stage], result)

        self.save(state)

    def get_attempt_count(self, stage: WorkflowStage) -> int:
        """Get the current attempt count for a stage."""
        state = self._state or self.load()
        if state is None or stage not in state.stages:
            return 0
        return state.stages[stage].attempt_count
