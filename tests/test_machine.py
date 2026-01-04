"""Tests for unified state machine."""

import tempfile
from pathlib import Path

from π.machine.state import (
    Checkpoint,
    MachineConfig,
    MachineStatus,
    Task,
    TaskPriority,
    TaskResult,
    TaskStatus,
    WorkflowState,
    get_state_path,
    list_machines,
    load_state,
    save_state,
    state_to_yaml,
    yaml_to_state,
)


class TestTask:
    """Tests for Task dataclass."""

    def test_create_task(self) -> None:
        """Test basic task creation."""
        task = Task(id="test-1", description="Test task")
        assert task.id == "test-1"
        assert task.description == "Test task"
        assert task.status == TaskStatus.PENDING
        assert task.priority == TaskPriority.NORMAL
        assert task.depends_on == []

    def test_task_with_dependencies(self) -> None:
        """Test task with dependencies."""
        task = Task(
            id="impl-auth",
            description="Implement authentication",
            priority=TaskPriority.HIGH,
            depends_on=["research-auth", "plan-auth"],
        )
        assert task.depends_on == ["research-auth", "plan-auth"]
        assert task.priority == TaskPriority.HIGH

    def test_task_is_actionable(self) -> None:
        """Test is_actionable property."""
        task = Task(id="t1", description="Test")
        assert task.is_actionable is True

        task.status = TaskStatus.IN_PROGRESS
        assert task.is_actionable is False

        task.status = TaskStatus.COMPLETED
        assert task.is_actionable is False

    def test_task_is_terminal(self) -> None:
        """Test is_terminal property."""
        task = Task(id="t1", description="Test")
        assert task.is_terminal is False

        task.status = TaskStatus.COMPLETED
        assert task.is_terminal is True

        task.status = TaskStatus.FAILED
        assert task.is_terminal is True

        task.status = TaskStatus.SKIPPED
        assert task.is_terminal is True

        task.status = TaskStatus.BLOCKED
        assert task.is_terminal is False

    def test_task_to_dict(self) -> None:
        """Test task serialization."""
        task = Task(
            id="test-1",
            description="Test task",
            priority=TaskPriority.HIGH,
            notes="Some notes",
        )
        data = task.to_dict()

        assert data["id"] == "test-1"
        assert data["description"] == "Test task"
        assert data["status"] == "pending"
        assert data["priority"] == "high"
        assert data["notes"] == "Some notes"
        # Default values should be omitted
        assert "depends_on" not in data
        assert "strategy" not in data

    def test_task_from_dict(self) -> None:
        """Test task deserialization."""
        data = {
            "id": "impl-1",
            "description": "Implement feature",
            "status": "in_progress",
            "priority": "critical",
            "depends_on": ["research-1"],
            "created_at": "2024-01-01T00:00:00Z",
        }
        task = Task.from_dict(data)

        assert task.id == "impl-1"
        assert task.status == TaskStatus.IN_PROGRESS
        assert task.priority == TaskPriority.CRITICAL
        assert task.depends_on == ["research-1"]

    def test_task_with_result(self) -> None:
        """Test task with execution result."""
        result = TaskResult(
            success=True,
            output="Implementation complete",
            artifacts=["src/auth.py"],
            duration_seconds=45.5,
        )
        task = Task(id="t1", description="Test", result=result)

        data = task.to_dict()
        assert data["result"]["success"] is True
        assert data["result"]["artifacts"] == ["src/auth.py"]

        restored = Task.from_dict(data)
        assert restored.result is not None
        assert restored.result.success is True


class TestWorkflowState:
    """Tests for WorkflowState."""

    def test_create_state(self) -> None:
        """Test basic state creation."""
        state = WorkflowState(id="feature-auth")
        assert state.id == "feature-auth"
        assert state.status == MachineStatus.IDLE
        assert state.tasks == []

    def test_state_with_objective(self) -> None:
        """Test state with objective and config."""
        config = MachineConfig(max_iterations=100, complexity_threshold=30)
        state = WorkflowState(
            id="test-machine",
            objective="Build authentication system",
            issue_url="https://github.com/org/repo/issues/42",
            config=config,
        )

        assert state.objective == "Build authentication system"
        assert state.issue_url == "https://github.com/org/repo/issues/42"
        assert state.config.max_iterations == 100

    def test_get_task(self) -> None:
        """Test task lookup by ID."""
        state = WorkflowState(id="test")
        state.tasks = [
            Task(id="t1", description="Task 1"),
            Task(id="t2", description="Task 2"),
        ]

        assert state.get_task("t1") is not None
        assert state.get_task("t1").description == "Task 1"
        assert state.get_task("nonexistent") is None

    def test_get_next_task_simple(self) -> None:
        """Test getting next task without dependencies."""
        state = WorkflowState(id="test")
        state.tasks = [
            Task(id="t1", description="Task 1", priority=TaskPriority.NORMAL),
            Task(id="t2", description="Task 2", priority=TaskPriority.HIGH),
        ]

        # Higher priority first
        next_task = state.get_next_task()
        assert next_task is not None
        assert next_task.id == "t2"

    def test_get_next_task_with_dependencies(self) -> None:
        """Test task ordering respects dependencies."""
        state = WorkflowState(id="test")
        state.tasks = [
            Task(id="t1", description="First", priority=TaskPriority.LOW),
            Task(
                id="t2",
                description="Second",
                priority=TaskPriority.HIGH,
                depends_on=["t1"],
            ),
        ]

        # t2 has higher priority but depends on t1
        next_task = state.get_next_task()
        assert next_task is not None
        assert next_task.id == "t1"

        # Complete t1
        state.tasks[0].status = TaskStatus.COMPLETED

        # Now t2 should be next
        next_task = state.get_next_task()
        assert next_task is not None
        assert next_task.id == "t2"

    def test_get_next_task_priority_ordering(self) -> None:
        """Test priority ordering."""
        state = WorkflowState(id="test")
        state.tasks = [
            Task(id="t1", description="Low", priority=TaskPriority.LOW),
            Task(id="t2", description="Critical", priority=TaskPriority.CRITICAL),
            Task(id="t3", description="Normal", priority=TaskPriority.NORMAL),
        ]

        # Should get critical first
        task = state.get_next_task()
        assert task is not None
        assert task.id == "t2"

    def test_has_pending_work(self) -> None:
        """Test pending work detection."""
        state = WorkflowState(id="test")
        assert state.has_pending_work() is False

        state.tasks = [Task(id="t1", description="Test")]
        assert state.has_pending_work() is True

        state.tasks[0].status = TaskStatus.COMPLETED
        assert state.has_pending_work() is False

    def test_is_complete(self) -> None:
        """Test completion detection."""
        state = WorkflowState(id="test")
        assert state.is_complete() is False

        state.tasks = [
            Task(id="t1", description="Task 1"),
            Task(id="t2", description="Task 2"),
        ]
        assert state.is_complete() is False

        state.tasks[0].status = TaskStatus.COMPLETED
        assert state.is_complete() is False

        state.tasks[1].status = TaskStatus.COMPLETED
        assert state.is_complete() is True

    def test_get_progress(self) -> None:
        """Test progress calculation."""
        state = WorkflowState(id="test")
        state.tasks = [
            Task(id="t1", description="T1", status=TaskStatus.COMPLETED),
            Task(id="t2", description="T2", status=TaskStatus.PENDING),
            Task(id="t3", description="T3", status=TaskStatus.FAILED),
            Task(id="t4", description="T4", status=TaskStatus.BLOCKED),
        ]

        progress = state.get_progress()
        assert progress["total"] == 4
        assert progress["completed"] == 1
        assert progress["pending"] == 1
        assert progress["failed"] == 1
        assert progress["blocked"] == 1
        assert progress["percent"] == 25.0


class TestYAMLSerialization:
    """Tests for YAML serialization."""

    def test_state_to_yaml(self) -> None:
        """Test state serialization to YAML."""
        state = WorkflowState(
            id="test-machine",
            objective="Test objective",
        )
        state.tasks = [
            Task(id="t1", description="First task", notes="Important note"),
        ]

        yaml_content = state_to_yaml(state)

        # Should have header
        assert "Human Editable" in yaml_content
        # Should have state content
        assert "id: test-machine" in yaml_content
        assert "objective: Test objective" in yaml_content
        assert "Important note" in yaml_content

    def test_yaml_to_state(self) -> None:
        """Test state deserialization from YAML."""
        yaml_content = """
id: restored-machine
objective: Restored objective
status: paused
tasks:
  - id: task-1
    description: Test task
    status: pending
    priority: high
    created_at: "2024-01-01T00:00:00Z"
config:
  max_iterations: 100
created_at: "2024-01-01T00:00:00Z"
updated_at: "2024-01-01T00:00:00Z"
"""
        state = yaml_to_state(yaml_content)

        assert state.id == "restored-machine"
        assert state.objective == "Restored objective"
        assert state.status == MachineStatus.PAUSED
        assert len(state.tasks) == 1
        assert state.tasks[0].priority == TaskPriority.HIGH
        assert state.config.max_iterations == 100

    def test_roundtrip(self) -> None:
        """Test YAML roundtrip preserves data."""
        original = WorkflowState(
            id="roundtrip-test",
            objective="Test roundtrip",
            status=MachineStatus.RUNNING,
        )
        original.tasks = [
            Task(
                id="t1",
                description="Task with notes",
                priority=TaskPriority.CRITICAL,
                notes="Multi\nline\nnotes",
                depends_on=["other-task"],
            ),
        ]
        original.config = MachineConfig(max_iterations=75)

        yaml_content = state_to_yaml(original)
        restored = yaml_to_state(yaml_content)

        assert restored.id == original.id
        assert restored.objective == original.objective
        assert restored.status == original.status
        assert len(restored.tasks) == 1
        assert restored.tasks[0].notes == "Multi\nline\nnotes"
        assert restored.tasks[0].depends_on == ["other-task"]
        assert restored.config.max_iterations == 75


class TestFilePersistence:
    """Tests for file-based persistence."""

    def test_save_and_load(self) -> None:
        """Test saving and loading state."""
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)

            state = WorkflowState(
                id="persist-test",
                objective="Test persistence",
            )
            state.tasks = [Task(id="t1", description="Saved task")]

            save_state(state, root)

            # Verify file exists
            state_path = get_state_path("persist-test", root)
            assert state_path.exists()

            # Load it back
            loaded = load_state("persist-test", root)
            assert loaded is not None
            assert loaded.id == "persist-test"
            assert loaded.objective == "Test persistence"
            assert len(loaded.tasks) == 1

    def test_load_nonexistent(self) -> None:
        """Test loading non-existent state returns None."""
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            loaded = load_state("nonexistent", root)
            assert loaded is None

    def test_list_machines(self) -> None:
        """Test listing all machines."""
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)

            # Create several machines
            for i in range(3):
                state = WorkflowState(id=f"machine-{i}", objective=f"Objective {i}")
                save_state(state, root)

            machines = list_machines(root)
            assert len(machines) == 3

            # Should be sorted by updated_at
            ids = [m.id for m in machines]
            assert "machine-0" in ids
            assert "machine-1" in ids
            assert "machine-2" in ids

    def test_state_path_sanitization(self) -> None:
        """Test machine ID sanitization for filesystem."""
        # IDs with special characters should be sanitized
        path = get_state_path("feature/auth#123")
        assert "/" not in path.name
        assert "#" not in path.name


class TestCheckpoint:
    """Tests for checkpoint functionality."""

    def test_checkpoint_creation(self) -> None:
        """Test creating a checkpoint."""
        cp = Checkpoint(
            id="cp-1",
            timestamp="2024-01-01T00:00:00Z",
            machine_status=MachineStatus.RUNNING,
            current_task_id="t1",
            completed_task_ids=["t0"],
            notes="Before risky operation",
        )

        assert cp.id == "cp-1"
        assert cp.completed_task_ids == ["t0"]

    def test_checkpoint_serialization(self) -> None:
        """Test checkpoint roundtrip."""
        cp = Checkpoint(
            id="cp-test",
            timestamp="2024-01-01T00:00:00Z",
            machine_status=MachineStatus.PAUSED,
            current_task_id=None,
            completed_task_ids=["t1", "t2"],
        )

        data = cp.to_dict()
        restored = Checkpoint.from_dict(data)

        assert restored.id == cp.id
        assert restored.machine_status == MachineStatus.PAUSED
        assert restored.completed_task_ids == ["t1", "t2"]


class TestMachineConfig:
    """Tests for machine configuration."""

    def test_default_config(self) -> None:
        """Test default configuration values."""
        config = MachineConfig()

        assert config.max_iterations == 50
        assert config.max_task_retries == 3
        assert config.complexity_threshold == 20
        assert config.auto_checkpoint is True
        assert config.pause_on_failure is True
        assert config.validate_changes is True

    def test_custom_config(self) -> None:
        """Test custom configuration."""
        config = MachineConfig(
            max_iterations=100,
            complexity_threshold=30,
            validate_changes=False,
        )

        assert config.max_iterations == 100
        assert config.complexity_threshold == 30
        assert config.validate_changes is False

    def test_config_serialization(self) -> None:
        """Test config roundtrip."""
        config = MachineConfig(max_iterations=75, pause_on_failure=False)

        data = config.to_dict()
        restored = MachineConfig.from_dict(data)

        assert restored.max_iterations == 75
        assert restored.pause_on_failure is False


class TestTaskResult:
    """Tests for TaskResult."""

    def test_success_result(self) -> None:
        """Test successful result."""
        result = TaskResult(
            success=True,
            output="Implementation complete",
            artifacts=["src/auth.py", "tests/test_auth.py"],
            duration_seconds=123.45,
        )

        assert result.success is True
        assert len(result.artifacts) == 2
        assert result.error is None

    def test_failure_result(self) -> None:
        """Test failure result."""
        result = TaskResult(
            success=False,
            output="",
            error="Validation failed: tests failing",
        )

        assert result.success is False
        assert result.error is not None

    def test_result_serialization(self) -> None:
        """Test result roundtrip."""
        result = TaskResult(
            success=True,
            output="Done",
            artifacts=["file.py"],
            duration_seconds=10.5,
        )

        data = result.to_dict()
        restored = TaskResult.from_dict(data)

        assert restored.success == result.success
        assert restored.artifacts == result.artifacts
        assert restored.duration_seconds == result.duration_seconds
