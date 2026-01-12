"""Unit tests for checkpoint management."""

from __future__ import annotations

import json
from typing import TYPE_CHECKING

import pytest

if TYPE_CHECKING:
    from pathlib import Path

from π.workflow.checkpoint import (
    CheckpointManager,
    CheckpointState,
    WorkflowStage,
)
from π.workflow.types import (
    ResearchDocPath,
    ResearchResult,
)


class TestCheckpointManager:
    """Tests for CheckpointManager class."""

    @pytest.fixture
    def checkpoint_dir(self, tmp_path: Path) -> Path:
        """Create a temporary checkpoint directory with required structure."""
        pi_dir = tmp_path / ".π"
        pi_dir.mkdir()
        # Also create research/plans dirs in same temp root
        (tmp_path / "thoughts" / "shared" / "research").mkdir(parents=True)
        (tmp_path / "thoughts" / "shared" / "plans").mkdir(parents=True)
        return tmp_path

    @pytest.fixture
    def manager(
        self, checkpoint_dir: Path, monkeypatch: pytest.MonkeyPatch
    ) -> CheckpointManager:
        """Create a CheckpointManager with temp directory."""
        monkeypatch.setattr(
            "π.workflow.checkpoint.get_project_root",
            lambda: checkpoint_dir,
        )
        return CheckpointManager()

    @pytest.fixture
    def sample_research_result(self, checkpoint_dir: Path) -> ResearchResult:
        """Create a sample ResearchResult for testing.

        Uses checkpoint_dir (not tmp_path) so paths match the manager's root.
        Creates the doc file in the correct structure for path validators.
        """
        # Create a fake research doc in the checkpoint_dir structure
        research_dir = checkpoint_dir / "thoughts" / "shared" / "research"
        doc_path = research_dir / "2026-01-12-test.md"
        doc_path.write_text("# Test Research")

        return ResearchResult(
            research_docs=[ResearchDocPath(path=str(doc_path))],
            needs_implementation=True,
            summaries=["Test summary"],
            reason=None,
        )

    def test_has_checkpoint_false_initially(self, manager: CheckpointManager) -> None:
        """CheckpointManager reports no checkpoint when file doesn't exist."""
        assert not manager.has_checkpoint()

    def test_save_and_load_checkpoint(
        self,
        manager: CheckpointManager,
        sample_research_result: ResearchResult,
    ) -> None:
        """Checkpoint can be saved and loaded."""
        manager.save_stage_result(
            objective="test objective",
            stage=WorkflowStage.RESEARCH,
            result=sample_research_result,
        )

        assert manager.has_checkpoint()

        loaded = manager.load()
        assert loaded is not None
        assert loaded.objective == "test objective"
        assert loaded.last_completed_stage == WorkflowStage.RESEARCH
        assert loaded.research_result is not None
        assert loaded.research_result.needs_implementation is True

    def test_clear_removes_checkpoint(
        self,
        manager: CheckpointManager,
        sample_research_result: ResearchResult,
    ) -> None:
        """clear() removes the checkpoint file."""
        manager.save_stage_result(
            objective="test",
            stage=WorkflowStage.RESEARCH,
            result=sample_research_result,
        )
        assert manager.has_checkpoint()

        manager.clear()
        assert not manager.has_checkpoint()

    def test_get_resume_stage_after_research(
        self,
        manager: CheckpointManager,
        sample_research_result: ResearchResult,
    ) -> None:
        """Resume stage is DESIGN after research completes."""
        manager.save_stage_result(
            objective="test",
            stage=WorkflowStage.RESEARCH,
            result=sample_research_result,
        )

        assert manager.get_resume_stage() == WorkflowStage.DESIGN

    def test_get_resume_stage_no_checkpoint(self, manager: CheckpointManager) -> None:
        """Resume stage is RESEARCH when no checkpoint exists."""
        assert manager.get_resume_stage() == WorkflowStage.RESEARCH

    def test_attempt_count_tracking(
        self,
        manager: CheckpointManager,
        sample_research_result: ResearchResult,
    ) -> None:
        """Attempt count is tracked per stage."""
        assert manager.get_attempt_count(WorkflowStage.RESEARCH) == 0

        manager.save_stage_result(
            objective="test",
            stage=WorkflowStage.RESEARCH,
            result=sample_research_result,
            attempt_count=2,
        )

        assert manager.get_attempt_count(WorkflowStage.RESEARCH) == 2

    def test_load_corrupted_file_returns_none(
        self,
        manager: CheckpointManager,
        checkpoint_dir: Path,
    ) -> None:
        """Loading corrupted checkpoint file returns None."""
        checkpoint_file = checkpoint_dir / ".π" / "checkpoint.json"
        checkpoint_file.parent.mkdir(parents=True, exist_ok=True)
        checkpoint_file.write_text("not valid json {{{")

        assert manager.load() is None

    def test_load_missing_paths_clears_checkpoint(
        self,
        manager: CheckpointManager,
        checkpoint_dir: Path,
    ) -> None:
        """Loading checkpoint with missing paths clears it and returns None."""
        # Create checkpoint referencing non-existent file
        checkpoint_file = checkpoint_dir / ".π" / "checkpoint.json"
        checkpoint_file.write_text(
            json.dumps({
                "objective": "test",
                "created_at": "2026-01-12T00:00:00+00:00",
                "updated_at": "2026-01-12T00:00:00+00:00",
                "last_completed_stage": "research",
                "stages": {
                    "research": {
                        "stage": "research",
                        "completed_at": "2026-01-12T00:00:00+00:00",
                        "attempt_count": 1,
                        "result": {
                            "research_docs": [
                                {
                                    "path": "/nonexistent/path.md",
                                    "doc_type": "research",
                                }
                            ],
                            "needs_implementation": True,
                            "summaries": ["test"],
                            "reason": None,
                        },
                    }
                },
            })
        )

        result = manager.load()
        assert result is None
        assert not manager.has_checkpoint()  # Should be cleared

    def test_objective_mismatch_raises_error(
        self,
        manager: CheckpointManager,
        sample_research_result: ResearchResult,
    ) -> None:
        """save_stage_result raises ValueError if objective doesn't match."""
        manager.save_stage_result(
            objective="original objective",
            stage=WorkflowStage.RESEARCH,
            result=sample_research_result,
        )

        with pytest.raises(ValueError, match="Objective mismatch"):
            manager.save_stage_result(
                objective="different objective",
                stage=WorkflowStage.DESIGN,
                result=sample_research_result,  # Not valid but ok for this test
            )

    def test_is_stale_returns_false_for_recent(
        self,
        manager: CheckpointManager,
        sample_research_result: ResearchResult,
    ) -> None:
        """is_stale returns False for recently updated checkpoints."""
        manager.save_stage_result(
            objective="test",
            stage=WorkflowStage.RESEARCH,
            result=sample_research_result,
        )

        state = manager.load()
        assert state is not None
        assert not state.is_stale(max_age_hours=24)


class TestCheckpointStateValidatePaths:
    """Tests for CheckpointState.validate_paths()."""

    def test_returns_empty_for_valid_paths(self, tmp_path: Path) -> None:
        """validate_paths returns empty list when all paths exist."""
        # Create research doc
        research_dir = tmp_path / "thoughts" / "shared" / "research"
        research_dir.mkdir(parents=True)
        doc_path = research_dir / "2026-01-12-test.md"
        doc_path.write_text("# Test")

        data = {
            "stages": {
                "research": {
                    "result": {
                        "research_docs": [{"path": str(doc_path)}],
                    }
                }
            }
        }

        missing = CheckpointState.validate_paths(data)
        assert missing == []

    def test_returns_missing_paths(self) -> None:
        """validate_paths returns list of non-existent paths."""
        data = {
            "stages": {
                "research": {
                    "result": {
                        "research_docs": [{"path": "/does/not/exist.md"}],
                    }
                },
                "design": {
                    "result": {
                        "plan_doc": {"path": "/also/missing.md"},
                    },
                },
            }
        }

        missing = CheckpointState.validate_paths(data)
        assert "/does/not/exist.md" in missing
        assert "/also/missing.md" in missing


class TestWorkflowStage:
    """Tests for WorkflowStage enum."""

    def test_stage_order(self) -> None:
        """Stages are ordered correctly."""
        stages = list(WorkflowStage)
        assert stages == [
            WorkflowStage.RESEARCH,
            WorkflowStage.DESIGN,
            WorkflowStage.EXECUTE,
        ]
