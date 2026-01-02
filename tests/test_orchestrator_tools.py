"""Tests for π.orchestrator.tools module."""

from unittest.mock import patch

from π.orchestrator.state import (
    Task,
    TaskStatus,
    create_state,
)
from π.orchestrator.tools import (
    ValidationResult,
    WorkflowResult,
    add_task,
    format_status_display,
    get_next_task,
    get_state_summary,
    increment_validation_retry,
    mark_blocked,
    mark_complete,
    mark_in_progress,
    should_retry_validation,
    validate_implementation,
)


class TestGetNextTask:
    """Tests for get_next_task function."""

    def test_returns_first_pending_task(self):
        """Should return first pending task."""
        state = create_state("Test")
        state.tasks = [
            Task(id="t1", description="Task 1", status=TaskStatus.PENDING),
            Task(id="t2", description="Task 2", status=TaskStatus.PENDING),
        ]

        task = get_next_task(state)
        assert task is not None
        assert task.id == "t1"

    def test_returns_none_when_no_pending(self):
        """Should return None when no pending tasks."""
        state = create_state("Test")
        state.tasks = [
            Task(id="t1", description="Task 1", status=TaskStatus.COMPLETED),
        ]

        task = get_next_task(state)
        assert task is None

    def test_returns_none_when_empty(self):
        """Should return None when no tasks."""
        state = create_state("Test")
        task = get_next_task(state)
        assert task is None

    def test_prioritizes_subtasks(self):
        """Should return incomplete subtasks before parent."""
        state = create_state("Test")
        state.tasks = [
            Task(id="t1", description="Parent", status=TaskStatus.PENDING),
            Task(id="t2", description="Subtask", status=TaskStatus.PENDING, parent_id="t1"),
        ]

        task = get_next_task(state)
        assert task is not None
        assert task.id == "t2"

    def test_skips_completed_subtasks(self):
        """Should skip completed subtasks."""
        state = create_state("Test")
        state.tasks = [
            Task(id="t1", description="Parent", status=TaskStatus.PENDING),
            Task(id="t2", description="Subtask", status=TaskStatus.COMPLETED, parent_id="t1"),
        ]

        task = get_next_task(state)
        assert task is not None
        assert task.id == "t1"


class TestAddTask:
    """Tests for add_task function."""

    def test_adds_task_with_generated_id(self, tmp_path):
        """Should add task with sequential ID."""
        state = create_state("Test")

        task_id = add_task(state, "New task", root=tmp_path)

        assert task_id == "t1"
        assert len(state.tasks) == 1
        assert state.tasks[0].description == "New task"

    def test_adds_subtask_with_parent(self, tmp_path):
        """Should add subtask with parent_id."""
        state = create_state("Test")
        add_task(state, "Parent", root=tmp_path)

        task_id = add_task(state, "Child", parent_id="t1", root=tmp_path)

        assert task_id == "t2"
        assert state.tasks[1].parent_id == "t1"

    def test_increments_id_correctly(self, tmp_path):
        """Should increment ID based on task count."""
        state = create_state("Test")
        add_task(state, "Task 1", root=tmp_path)
        add_task(state, "Task 2", root=tmp_path)
        task_id = add_task(state, "Task 3", root=tmp_path)

        assert task_id == "t3"


class TestMarkInProgress:
    """Tests for mark_in_progress function."""

    def test_sets_status_to_in_progress(self, tmp_path):
        """Should set task status to in_progress."""
        state = create_state("Test")
        state.tasks = [Task(id="t1", description="Test", status=TaskStatus.PENDING)]

        mark_in_progress(state, "t1", root=tmp_path)

        assert state.tasks[0].status == TaskStatus.IN_PROGRESS

    def test_sets_started_at_timestamp(self, tmp_path):
        """Should set started_at timestamp."""
        state = create_state("Test")
        state.tasks = [Task(id="t1", description="Test", status=TaskStatus.PENDING)]

        mark_in_progress(state, "t1", root=tmp_path)

        assert state.tasks[0].started_at is not None

    def test_raises_for_missing_task(self, tmp_path):
        """Should raise ValueError for missing task."""
        state = create_state("Test")

        try:
            mark_in_progress(state, "t99", root=tmp_path)
            assert False, "Should have raised"
        except ValueError as e:
            assert "t99" in str(e)


class TestMarkComplete:
    """Tests for mark_complete function."""

    def test_sets_status_to_completed(self, tmp_path):
        """Should set task status to completed."""
        state = create_state("Test")
        state.tasks = [Task(id="t1", description="Test", status=TaskStatus.IN_PROGRESS)]

        mark_complete(state, "t1", root=tmp_path)

        assert state.tasks[0].status == TaskStatus.COMPLETED

    def test_sets_outputs(self, tmp_path):
        """Should set task outputs."""
        state = create_state("Test")
        state.tasks = [Task(id="t1", description="Test", status=TaskStatus.IN_PROGRESS)]

        mark_complete(state, "t1", outputs={"plan": "/path/to/plan.md"}, root=tmp_path)

        assert state.tasks[0].outputs == {"plan": "/path/to/plan.md"}

    def test_sets_completed_at_timestamp(self, tmp_path):
        """Should set completed_at timestamp."""
        state = create_state("Test")
        state.tasks = [Task(id="t1", description="Test", status=TaskStatus.IN_PROGRESS)]

        mark_complete(state, "t1", root=tmp_path)

        assert state.tasks[0].completed_at is not None


class TestMarkBlocked:
    """Tests for mark_blocked function."""

    def test_sets_status_to_blocked(self, tmp_path):
        """Should set task status to blocked."""
        state = create_state("Test")
        state.tasks = [Task(id="t1", description="Test", status=TaskStatus.IN_PROGRESS)]

        mark_blocked(state, "t1", reason="Test failure", root=tmp_path)

        assert state.tasks[0].status == TaskStatus.BLOCKED

    def test_sets_failure_reason(self, tmp_path):
        """Should set last_validation_failure."""
        state = create_state("Test")
        state.tasks = [Task(id="t1", description="Test", status=TaskStatus.IN_PROGRESS)]

        mark_blocked(state, "t1", reason="Test failure", root=tmp_path)

        assert state.tasks[0].last_validation_failure == "Test failure"


class TestIncrementValidationRetry:
    """Tests for increment_validation_retry function."""

    def test_increments_retry_count(self, tmp_path):
        """Should increment validation_retries."""
        state = create_state("Test")
        state.tasks = [Task(id="t1", description="Test", status=TaskStatus.IN_PROGRESS)]

        count = increment_validation_retry(
            state, "t1", failure_message="Failed", root=tmp_path
        )

        assert count == 1
        assert state.tasks[0].validation_retries == 1

    def test_accumulates_retries(self, tmp_path):
        """Should accumulate retry count."""
        state = create_state("Test")
        state.tasks = [Task(id="t1", description="Test", status=TaskStatus.IN_PROGRESS)]

        increment_validation_retry(state, "t1", failure_message="Fail 1", root=tmp_path)
        count = increment_validation_retry(state, "t1", failure_message="Fail 2", root=tmp_path)

        assert count == 2

    def test_updates_failure_message(self, tmp_path):
        """Should update last_validation_failure."""
        state = create_state("Test")
        state.tasks = [Task(id="t1", description="Test", status=TaskStatus.IN_PROGRESS)]

        increment_validation_retry(state, "t1", failure_message="Latest failure", root=tmp_path)

        assert state.tasks[0].last_validation_failure == "Latest failure"


class TestShouldRetryValidation:
    """Tests for should_retry_validation function."""

    def test_returns_true_when_retries_available(self):
        """Should return True when retries < max."""
        task = Task(id="t1", description="Test", validation_retries=1)
        assert should_retry_validation(task) is True

    def test_returns_false_when_max_retries(self):
        """Should return False when retries >= max."""
        task = Task(id="t1", description="Test", validation_retries=3)
        assert should_retry_validation(task) is False


class TestValidateImplementation:
    """Tests for validate_implementation function."""

    def test_passes_when_all_checks_succeed(self, mock_subprocess_success):
        """Should return passed=True when all checks pass."""
        task = Task(id="t1", description="Test")

        result = validate_implementation(task)

        assert result.passed is True
        assert len(result.failures) == 0

    def test_fails_when_check_fails(self, mock_subprocess_failure):
        """Should return passed=False with failures when check fails."""
        task = Task(id="t1", description="Test")

        result = validate_implementation(task)

        assert result.passed is False
        assert len(result.failures) > 0

    def test_handles_make_not_found(self, tmp_path):
        """Should handle FileNotFoundError gracefully."""
        task = Task(id="t1", description="Test")

        with patch("subprocess.run", side_effect=FileNotFoundError):
            result = validate_implementation(task, project_root=tmp_path)

        # Should still return a result (not raise)
        assert isinstance(result, ValidationResult)


class TestGetStateSummary:
    """Tests for get_state_summary function."""

    def test_includes_objective(self):
        """Should include objective in summary."""
        state = create_state("Test objective")
        summary = get_state_summary(state)
        assert "Test objective" in summary

    def test_includes_iteration_count(self):
        """Should include iteration count."""
        state = create_state("Test")
        state.config.current_iteration = 5
        state.config.max_iterations = 50
        summary = get_state_summary(state)
        assert "5/50" in summary

    def test_includes_task_counts(self):
        """Should include task status counts."""
        state = create_state("Test")
        state.tasks = [
            Task(id="t1", description="Done", status=TaskStatus.COMPLETED),
            Task(id="t2", description="Pending", status=TaskStatus.PENDING),
        ]
        summary = get_state_summary(state)
        assert "Completed (1)" in summary
        assert "Pending (1)" in summary


class TestFormatStatusDisplay:
    """Tests for format_status_display function."""

    def test_includes_objective(self):
        """Should include objective."""
        state = create_state("Test objective")
        display = format_status_display(state)
        assert "Test objective" in display

    def test_includes_hash(self):
        """Should include objective hash."""
        state = create_state("Test objective")
        display = format_status_display(state)
        assert state.objective_hash in display

    def test_includes_task_tree(self):
        """Should include tasks with status indicators."""
        state = create_state("Test")
        state.tasks = [
            Task(id="t1", description="Completed task", status=TaskStatus.COMPLETED),
            Task(id="t2", description="Pending task", status=TaskStatus.PENDING),
        ]
        display = format_status_display(state)
        assert "t1" in display
        assert "t2" in display
        assert "Completed task" in display
        assert "Pending task" in display

    def test_shows_halt_reason(self):
        """Should show halt reason when halted."""
        state = create_state("Test")
        state.halt(reason="Test failure reason")
        display = format_status_display(state)
        assert "Test failure reason" in display


class TestWorkflowResult:
    """Tests for WorkflowResult dataclass."""

    def test_success_result(self):
        """Should create successful result."""
        result = WorkflowResult(
            success=True,
            outputs={"plan": "/path"},
        )
        assert result.success is True
        assert result.error is None

    def test_failure_result(self):
        """Should create failure result."""
        result = WorkflowResult(
            success=False,
            outputs={},
            error="Test error",
        )
        assert result.success is False
        assert result.error == "Test error"


class TestValidationResult:
    """Tests for ValidationResult dataclass."""

    def test_passed_result(self):
        """Should create passed result."""
        result = ValidationResult(passed=True, failures=[])
        assert result.passed is True

    def test_failed_result(self):
        """Should create failed result with messages."""
        result = ValidationResult(
            passed=False,
            failures=["Test failed", "Lint failed"],
        )
        assert result.passed is False
        assert len(result.failures) == 2
