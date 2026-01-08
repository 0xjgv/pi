"""Tests for ObjectiveLoop."""

from pathlib import Path
from unittest.mock import MagicMock, patch

from π.workflow.loop import (
    LoopState,
    LoopStatus,
    Task,
    TaskStatus,
    _objective_hash,
    _state_path,
    _task_from_dict,
    _task_to_dict,
    archive_state,
    load_state,
    save_state,
)


class TestTaskSerialization:
    """Tests for task serialization."""

    def test_task_to_dict(self) -> None:
        task = Task(
            id="task_001",
            description="Test task",
            dependencies=["task_000"],
            priority=2,
            status=TaskStatus.COMPLETED,
            result="Success",
            commit_hash="abc123",
        )
        result = _task_to_dict(task)
        assert result["id"] == "task_001"
        assert result["status"] == "completed"
        assert result["commit_hash"] == "abc123"

    def test_task_from_dict(self) -> None:
        data = {
            "id": "task_002",
            "description": "Another task",
            "dependencies": [],
            "priority": 1,
            "status": "pending",
        }
        task = _task_from_dict(data)
        assert task.id == "task_002"
        assert task.status == TaskStatus.PENDING

    def test_task_roundtrip(self) -> None:
        """Test serialization and deserialization preserve all fields."""
        original = Task(
            id="task_003",
            description="Roundtrip task",
            dependencies=["dep1", "dep2"],
            priority=3,
            status=TaskStatus.IN_PROGRESS,
            result="partial",
            error="some error",
            plan_doc_path="/path/to/plan.md",
            research_doc_path="/path/to/research.md",
            commit_hash="def456",
        )
        data = _task_to_dict(original)
        restored = _task_from_dict(data)

        assert restored.id == original.id
        assert restored.description == original.description
        assert restored.dependencies == original.dependencies
        assert restored.priority == original.priority
        assert restored.status == original.status
        assert restored.result == original.result
        assert restored.error == original.error
        assert restored.plan_doc_path == original.plan_doc_path
        assert restored.research_doc_path == original.research_doc_path
        assert restored.commit_hash == original.commit_hash


class TestStatePersistence:
    """Tests for state save/load."""

    def test_save_load_roundtrip(self, tmp_path: Path) -> None:
        state = LoopState(
            objective="Test objective",
            tasks=[
                Task(id="t1", description="Task 1", status=TaskStatus.COMPLETED),
                Task(id="t2", description="Task 2", status=TaskStatus.PENDING),
            ],
            completed_task_ids={"t1"},
            iteration=3,
        )

        path = tmp_path / "state.json"
        save_state(state, path)

        loaded = load_state(path)
        assert loaded.objective == state.objective
        assert loaded.iteration == 3
        assert len(loaded.tasks) == 2
        assert "t1" in loaded.completed_task_ids

    def test_atomic_write(self, tmp_path: Path) -> None:
        """Verify atomic write doesn't leave temp files."""
        state = LoopState(objective="Test")
        path = tmp_path / "state.json"

        save_state(state, path)

        assert path.exists()
        assert not path.with_suffix(".tmp").exists()

    def test_state_status_preserved(self, tmp_path: Path) -> None:
        """Verify loop status is preserved."""
        state = LoopState(
            objective="Test",
            status=LoopStatus.FAILED,
            iteration=10,
            max_iterations=50,
        )
        path = tmp_path / "state.json"

        save_state(state, path)
        loaded = load_state(path)

        assert loaded.status == LoopStatus.FAILED
        assert loaded.max_iterations == 50


class TestObjectiveHash:
    """Tests for objective hashing."""

    def test_hash_stability(self) -> None:
        """Same objective produces same hash."""
        h1 = _objective_hash("build a calculator")
        h2 = _objective_hash("build a calculator")
        assert h1 == h2

    def test_hash_uniqueness(self) -> None:
        """Different objectives produce different hashes."""
        h1 = _objective_hash("build a calculator")
        h2 = _objective_hash("build a todo app")
        assert h1 != h2

    def test_hash_length(self) -> None:
        """Hash is 12 characters."""
        h = _objective_hash("any objective")
        assert len(h) == 12


class TestLoopState:
    """Tests for LoopState dataclass."""

    def test_default_values(self) -> None:
        """Test default values are set correctly."""
        state = LoopState(objective="test")
        assert state.tasks == []
        assert state.completed_task_ids == set()
        assert state.iteration == 0
        assert state.max_iterations == 50
        assert state.status == LoopStatus.RUNNING

    def test_mutable_defaults_isolation(self) -> None:
        """Test that mutable defaults are not shared between instances."""
        state1 = LoopState(objective="test1")
        state2 = LoopState(objective="test2")

        state1.tasks.append(Task(id="t1", description="Task 1"))
        state1.completed_task_ids.add("t1")

        assert len(state2.tasks) == 0
        assert len(state2.completed_task_ids) == 0


class TestTask:
    """Tests for Task dataclass."""

    def test_default_values(self) -> None:
        """Test default values are set correctly."""
        task = Task(id="t1", description="Test task")
        assert task.dependencies == []
        assert task.priority == 1
        assert task.status == TaskStatus.PENDING
        assert task.result is None
        assert task.error is None
        assert task.plan_doc_path is None
        assert task.research_doc_path is None
        assert task.commit_hash is None


class TestStateTimestamps:
    """Tests for state timestamp fields."""

    def test_first_save_sets_created_and_updated(self, tmp_path: Path) -> None:
        """First save sets both created_at and updated_at."""
        import json

        state = LoopState(objective="Test")
        path = tmp_path / "state.json"

        save_state(state, path)

        data = json.loads(path.read_text())
        assert "created_at" in data
        assert "updated_at" in data
        assert data["created_at"] == data["updated_at"]
        # Verify ISO 8601 format with timezone
        assert data["created_at"].endswith("+00:00")

    def test_subsequent_save_preserves_created_updates_updated(
        self, tmp_path: Path
    ) -> None:
        """Subsequent saves preserve created_at but update updated_at."""
        import json
        import time

        state = LoopState(objective="Test")
        path = tmp_path / "state.json"

        save_state(state, path)
        first_data = json.loads(path.read_text())
        original_created = first_data["created_at"]

        time.sleep(0.01)  # Ensure time difference
        state.iteration = 1
        save_state(state, path)

        second_data = json.loads(path.read_text())
        assert second_data["created_at"] == original_created
        assert second_data["updated_at"] >= original_created

    def test_timestamps_are_utc_iso8601(self, tmp_path: Path) -> None:
        """Verify timestamps are UTC in ISO 8601 format."""
        import json
        from datetime import datetime

        state = LoopState(objective="Test")
        path = tmp_path / "state.json"

        save_state(state, path)

        data = json.loads(path.read_text())
        # Should parse without error and have UTC timezone
        parsed = datetime.fromisoformat(data["created_at"])
        assert parsed.tzinfo is not None
        assert parsed.utcoffset().total_seconds() == 0


class TestStatePath:
    """Tests for _state_path() function."""

    def test_creates_checkpoint_directory(self, tmp_path: Path) -> None:
        """Should create checkpoint directory if it doesn't exist."""
        checkpoint_dir = tmp_path / "nonexistent" / "checkpoint"
        assert not checkpoint_dir.exists()

        result = _state_path("test objective", checkpoint_dir)

        assert checkpoint_dir.exists()
        assert result.parent == checkpoint_dir

    def test_uses_objective_hash_as_filename(self, tmp_path: Path) -> None:
        """Should use objective hash for filename."""
        result = _state_path("test objective", tmp_path)

        expected_hash = _objective_hash("test objective")
        assert result.name == f"{expected_hash}.json"


class TestArchiveState:
    """Tests for archive_state() function."""

    def test_moves_state_to_archive_directory(self, tmp_path: Path) -> None:
        """Should move state file to archive subdirectory."""
        state_file = tmp_path / "test-state.json"
        state_file.write_text('{"objective": "test"}')

        archive_state(state_file, tmp_path)

        assert not state_file.exists()
        assert (tmp_path / "archive" / "test-state.json").exists()

    def test_creates_archive_directory_if_missing(self, tmp_path: Path) -> None:
        """Should create archive directory if it doesn't exist."""
        state_file = tmp_path / "state.json"
        state_file.write_text("{}")

        archive_dir = tmp_path / "archive"
        assert not archive_dir.exists()

        archive_state(state_file, tmp_path)

        assert archive_dir.exists()


class TestObjectiveLoopHelpers:
    """Tests for ObjectiveLoop helper methods."""

    def test_should_continue_returns_false_when_not_running(self) -> None:
        """Should return False when status is not RUNNING."""
        from π.workflow.loop import ObjectiveLoop

        with patch("π.workflow.loop.get_lm"):
            loop = ObjectiveLoop()

        state = LoopState(objective="test", status=LoopStatus.COMPLETED)
        assert loop._should_continue(state) is False

        state = LoopState(objective="test", status=LoopStatus.FAILED)
        assert loop._should_continue(state) is False

    def test_should_continue_returns_false_at_max_iterations(self) -> None:
        """Should return False and set FAILED when max iterations reached."""
        from π.workflow.loop import ObjectiveLoop

        with patch("π.workflow.loop.get_lm"):
            loop = ObjectiveLoop()

        state = LoopState(objective="test", iteration=50, max_iterations=50)
        result = loop._should_continue(state)

        assert result is False
        assert state.status == LoopStatus.FAILED

    def test_should_continue_returns_true_when_running(self) -> None:
        """Should return True when running and under max iterations."""
        from π.workflow.loop import ObjectiveLoop

        with patch("π.workflow.loop.get_lm"):
            loop = ObjectiveLoop()

        state = LoopState(objective="test", iteration=5, max_iterations=50)
        assert loop._should_continue(state) is True

    def test_should_redecompose_when_all_tasks_done_but_running(self) -> None:
        """Should return True when all tasks done but loop still running."""
        from π.workflow.loop import ObjectiveLoop

        with patch("π.workflow.loop.get_lm"):
            loop = ObjectiveLoop()

        state = LoopState(
            objective="test",
            tasks=[
                Task(id="t1", description="Task 1", status=TaskStatus.COMPLETED),
                Task(id="t2", description="Task 2", status=TaskStatus.FAILED),
            ],
            status=LoopStatus.RUNNING,
        )
        assert loop._should_redecompose(state) is True

    def test_should_redecompose_returns_false_when_pending_tasks(self) -> None:
        """Should return False when there are pending tasks."""
        from π.workflow.loop import ObjectiveLoop

        with patch("π.workflow.loop.get_lm"):
            loop = ObjectiveLoop()

        state = LoopState(
            objective="test",
            tasks=[
                Task(id="t1", description="Task 1", status=TaskStatus.COMPLETED),
                Task(id="t2", description="Task 2", status=TaskStatus.PENDING),
            ],
            status=LoopStatus.RUNNING,
        )
        assert loop._should_redecompose(state) is False

    def test_handle_no_tasks_completes_when_no_pending(self) -> None:
        """Should set COMPLETED status when no pending tasks remain."""
        from π.workflow.loop import ObjectiveLoop

        with patch("π.workflow.loop.get_lm"):
            loop = ObjectiveLoop()

        state = LoopState(
            objective="test",
            tasks=[
                Task(id="t1", description="Task 1", status=TaskStatus.COMPLETED),
            ],
            status=LoopStatus.RUNNING,
        )
        result = loop._handle_no_tasks(state)

        assert result.status == LoopStatus.COMPLETED

    def test_get_codebase_context_returns_git_info(self) -> None:
        """Should return git status and recent commits."""
        from π.workflow.loop import ObjectiveLoop

        with patch("π.workflow.loop.get_lm"):
            loop = ObjectiveLoop()

        with patch("π.workflow.loop.subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(stdout="M file.py\nabc123 commit")

            result = loop._get_codebase_context()

            assert "M file.py" in result or "Git status" in result

    def test_get_codebase_context_handles_error(self) -> None:
        """Should return fallback message when git fails."""
        from π.workflow.loop import ObjectiveLoop

        with patch("π.workflow.loop.get_lm"):
            loop = ObjectiveLoop()

        with patch("π.workflow.loop.subprocess.run", side_effect=Exception("git err")):
            result = loop._get_codebase_context()

            assert "unable to get git context" in result
