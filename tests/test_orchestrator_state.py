"""Tests for π.orchestrator.state module."""

import json

from π.orchestrator.state import (
    OrchestratorStatus,
    Task,
    TaskStatus,
    TaskStrategy,
    WorkflowState,
    compute_objective_hash,
    create_state,
    get_state_path,
    load_or_create_state,
    load_state,
    load_state_by_hash,
    save_state,
)
from π.support.directory import get_state_dir


class TestComputeObjectiveHash:
    """Tests for compute_objective_hash function."""

    def test_returns_8_char_hash(self):
        """Should return 8-character hex hash."""
        result = compute_objective_hash("test objective")
        assert len(result) == 8
        assert all(c in "0123456789abcdef" for c in result)

    def test_same_input_same_hash(self):
        """Should return same hash for same input."""
        hash1 = compute_objective_hash("test")
        hash2 = compute_objective_hash("test")
        assert hash1 == hash2

    def test_different_input_different_hash(self):
        """Should return different hash for different input."""
        hash1 = compute_objective_hash("test1")
        hash2 = compute_objective_hash("test2")
        assert hash1 != hash2


class TestTask:
    """Tests for Task dataclass."""

    def test_default_status_is_pending(self):
        """Should default to pending status."""
        task = Task(id="t1", description="Test task")
        assert task.status == TaskStatus.PENDING

    def test_to_dict_includes_all_fields(self):
        """Should serialize all fields to dict."""
        task = Task(
            id="t1",
            description="Test task",
            status=TaskStatus.COMPLETED,
            parent_id="t0",
            strategy=TaskStrategy.FULL_WORKFLOW,
            outputs={"research": "/path/to/doc.md"},
            validation_retries=2,
            last_validation_failure="Test failed",
            started_at="2026-01-01T10:00:00",
            completed_at="2026-01-01T12:00:00",
        )
        d = task.to_dict()

        assert d["id"] == "t1"
        assert d["description"] == "Test task"
        assert d["status"] == "completed"
        assert d["parent_id"] == "t0"
        assert d["strategy"] == "full_workflow"
        assert d["outputs"] == {"research": "/path/to/doc.md"}
        assert d["validation_retries"] == 2
        assert d["last_validation_failure"] == "Test failed"

    def test_from_dict_creates_task(self):
        """Should deserialize dict to Task."""
        data = {
            "id": "t1",
            "description": "Test task",
            "status": "in_progress",
            "parent_id": None,
            "strategy": "quick_change",
            "outputs": {},
        }
        task = Task.from_dict(data)

        assert task.id == "t1"
        assert task.description == "Test task"
        assert task.status == TaskStatus.IN_PROGRESS
        assert task.strategy == TaskStrategy.QUICK_CHANGE

    def test_from_dict_handles_missing_optional_fields(self):
        """Should handle missing optional fields."""
        data = {
            "id": "t1",
            "description": "Test task",
            "status": "pending",
        }
        task = Task.from_dict(data)

        assert task.parent_id is None
        assert task.strategy is None
        assert task.outputs == {}
        assert task.validation_retries == 0


class TestWorkflowState:
    """Tests for WorkflowState dataclass."""

    def test_has_pending_tasks_true(self):
        """Should return True when pending tasks exist."""
        state = create_state("Test objective")
        state.tasks = [Task(id="t1", description="Test", status=TaskStatus.PENDING)]
        assert state.has_pending_tasks() is True

    def test_has_pending_tasks_false(self):
        """Should return False when no pending tasks."""
        state = create_state("Test objective")
        state.tasks = [Task(id="t1", description="Test", status=TaskStatus.COMPLETED)]
        assert state.has_pending_tasks() is False

    def test_has_pending_tasks_includes_in_progress(self):
        """Should return True when tasks are in progress."""
        state = create_state("Test objective")
        state.tasks = [Task(id="t1", description="Test", status=TaskStatus.IN_PROGRESS)]
        assert state.has_pending_tasks() is True

    def test_all_complete_true(self):
        """Should return True when all tasks completed."""
        state = create_state("Test objective")
        state.tasks = [
            Task(id="t1", description="Test 1", status=TaskStatus.COMPLETED),
            Task(id="t2", description="Test 2", status=TaskStatus.COMPLETED),
        ]
        assert state.all_complete() is True

    def test_all_complete_false(self):
        """Should return False when some tasks pending."""
        state = create_state("Test objective")
        state.tasks = [
            Task(id="t1", description="Test 1", status=TaskStatus.COMPLETED),
            Task(id="t2", description="Test 2", status=TaskStatus.PENDING),
        ]
        assert state.all_complete() is False

    def test_all_complete_false_when_empty(self):
        """Should return False when no tasks."""
        state = create_state("Test objective")
        assert state.all_complete() is False

    def test_increment_iteration(self):
        """Should increment iteration count."""
        state = create_state("Test objective")
        assert state.config.current_iteration == 0
        state.increment_iteration()
        assert state.config.current_iteration == 1

    def test_halt_sets_status_and_reason(self):
        """Should set halted status and reason."""
        state = create_state("Test objective")
        state.halt(reason="Test failure")
        assert state.status == OrchestratorStatus.HALTED
        assert state.halt_reason == "Test failure"

    def test_to_dict_round_trip(self):
        """Should serialize and deserialize correctly."""
        state = create_state("Test objective")
        state.tasks = [Task(id="t1", description="Test", status=TaskStatus.PENDING)]

        d = state.to_dict()
        restored = WorkflowState.from_dict(d)

        assert restored.objective == state.objective
        assert restored.objective_hash == state.objective_hash
        assert restored.status == state.status
        assert len(restored.tasks) == 1
        assert restored.tasks[0].id == "t1"


class TestCreateState:
    """Tests for create_state function."""

    def test_creates_running_state(self):
        """Should create state with running status."""
        state = create_state("Test objective")
        assert state.status == OrchestratorStatus.RUNNING

    def test_sets_objective_and_hash(self):
        """Should set objective and compute hash."""
        state = create_state("Test objective")
        assert state.objective == "Test objective"
        assert state.objective_hash == compute_objective_hash("Test objective")

    def test_creates_empty_tasks_list(self):
        """Should create empty tasks list."""
        state = create_state("Test objective")
        assert state.tasks == []

    def test_sets_timestamps(self):
        """Should set created_at and updated_at."""
        state = create_state("Test objective")
        assert state.created_at is not None
        assert state.updated_at is not None


class TestGetStateDir:
    """Tests for get_state_dir function."""

    def test_creates_state_directory(self, tmp_path):
        """Should create .π/state/ directory."""
        state_dir = get_state_dir(tmp_path)
        assert state_dir == tmp_path / ".π" / "state"
        assert state_dir.is_dir()

    def test_is_idempotent(self, tmp_path):
        """Should be safe to call multiple times."""
        dir1 = get_state_dir(tmp_path)
        dir2 = get_state_dir(tmp_path)
        assert dir1 == dir2

    def test_creates_gitignore(self, tmp_path):
        """Should add .π/ to gitignore."""
        get_state_dir(tmp_path)
        gitignore = tmp_path / ".gitignore"
        assert gitignore.exists()
        assert ".π/" in gitignore.read_text()


class TestSaveAndLoadState:
    """Tests for save_state and load_state functions."""

    def test_save_creates_file(self, tmp_path):
        """Should create state file."""
        state = create_state("Test objective")
        save_state(state, tmp_path)

        state_path = get_state_path(state.objective, tmp_path)
        assert state_path.exists()

    def test_load_returns_saved_state(self, tmp_path):
        """Should load previously saved state."""
        state = create_state("Test objective")
        state.tasks = [Task(id="t1", description="Test", status=TaskStatus.PENDING)]
        save_state(state, tmp_path)

        loaded = load_state("Test objective", tmp_path)
        assert loaded is not None
        assert loaded.objective == "Test objective"
        assert len(loaded.tasks) == 1

    def test_load_returns_none_for_missing(self, tmp_path):
        """Should return None when state file doesn't exist."""
        loaded = load_state("Nonexistent objective", tmp_path)
        assert loaded is None

    def test_load_state_by_hash(self, tmp_path):
        """Should load state by hash."""
        state = create_state("Test objective")
        save_state(state, tmp_path)

        loaded = load_state_by_hash(state.objective_hash, tmp_path)
        assert loaded is not None
        assert loaded.objective == "Test objective"

    def test_save_updates_updated_at(self, tmp_path):
        """Should update updated_at on save."""
        state = create_state("Test objective")
        original_updated = state.updated_at
        save_state(state, tmp_path)
        assert state.updated_at != original_updated


class TestLoadOrCreateState:
    """Tests for load_or_create_state function."""

    def test_creates_new_state_when_missing(self, tmp_path):
        """Should create new state when file doesn't exist."""
        state = load_or_create_state("New objective", tmp_path)
        assert state.objective == "New objective"
        assert state.status == OrchestratorStatus.RUNNING

        # Should also save it
        loaded = load_state("New objective", tmp_path)
        assert loaded is not None

    def test_loads_existing_state(self, tmp_path):
        """Should load existing state when file exists."""
        # Create and save a state
        original = create_state("Existing objective")
        original.tasks = [Task(id="t1", description="Test", status=TaskStatus.COMPLETED)]
        save_state(original, tmp_path)

        # Load it
        loaded = load_or_create_state("Existing objective", tmp_path)
        assert len(loaded.tasks) == 1
        assert loaded.tasks[0].status == TaskStatus.COMPLETED


class TestStateFileFormat:
    """Tests for state file JSON format."""

    def test_file_is_valid_json(self, tmp_path):
        """Should write valid JSON."""
        state = create_state("Test objective")
        save_state(state, tmp_path)

        state_path = get_state_path(state.objective, tmp_path)
        with state_path.open() as f:
            data = json.load(f)

        assert data["objective"] == "Test objective"
        assert data["version"] == 1

    def test_file_is_pretty_printed(self, tmp_path):
        """Should format JSON with indentation."""
        state = create_state("Test objective")
        save_state(state, tmp_path)

        state_path = get_state_path(state.objective, tmp_path)
        content = state_path.read_text()

        # Check for indentation (pretty print)
        assert "\n  " in content
