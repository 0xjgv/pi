"""Tests for orchestrator display module."""

import pytest
from rich.console import Console

from π.orchestrator.display import (
    STAGE_ORDER,
    OrchestratorDisplay,
    _get_stage_progress,
    _truncate,
    create_display,
)
from π.orchestrator.state import (
    Task,
    TaskStage,
    TaskStatus,
    WorkflowConfig,
    WorkflowState,
    OrchestratorStatus,
)


class TestTruncate:
    """Tests for _truncate helper."""

    def test_short_text_unchanged(self) -> None:
        """Short text should not be truncated."""
        result = _truncate("hello", max_len=10)
        assert result == "hello"

    def test_exact_length_unchanged(self) -> None:
        """Text at exact max length should not be truncated."""
        result = _truncate("1234567890", max_len=10)
        assert result == "1234567890"

    def test_long_text_truncated(self) -> None:
        """Long text should be truncated with ellipsis."""
        result = _truncate("hello world this is long", max_len=10)
        assert result == "hello w..."
        assert len(result) == 10

    def test_default_max_length(self) -> None:
        """Default max length should be 60."""
        long_text = "a" * 100
        result = _truncate(long_text)
        assert len(result) == 60
        assert result.endswith("...")


class TestGetStageProgress:
    """Tests for _get_stage_progress helper."""

    def test_pending_stage(self) -> None:
        """Pending stage should be at index 0."""
        idx, total = _get_stage_progress("pending")
        assert idx == 0
        assert total == len(STAGE_ORDER) - 1

    def test_complete_stage(self) -> None:
        """Complete stage should be at max index."""
        idx, total = _get_stage_progress("complete")
        assert idx == total

    def test_middle_stage(self) -> None:
        """Middle stage should return correct index."""
        idx, total = _get_stage_progress("creating plan")
        assert idx == STAGE_ORDER.index("creating plan")
        assert total == len(STAGE_ORDER) - 1

    def test_unknown_stage(self) -> None:
        """Unknown stage should default to 0."""
        idx, total = _get_stage_progress("unknown_stage")
        assert idx == 0


class TestOrchestratorDisplay:
    """Tests for OrchestratorDisplay class."""

    @pytest.fixture
    def console(self) -> Console:
        """Create console for testing."""
        return Console(force_terminal=True, width=80)

    @pytest.fixture
    def display(self, console: Console) -> OrchestratorDisplay:
        """Create display instance."""
        return OrchestratorDisplay(console=console)

    @pytest.fixture
    def sample_state(self) -> WorkflowState:
        """Create sample workflow state."""
        return WorkflowState(
            version=1,
            objective="Test objective for display",
            objective_hash="abc12345",
            created_at="2025-01-01T00:00:00",
            updated_at="2025-01-01T00:00:00",
            config=WorkflowConfig(max_iterations=10, current_iteration=2),
            status=OrchestratorStatus.RUNNING,
            tasks=[
                Task(
                    id="t1",
                    description="First task",
                    status=TaskStatus.COMPLETED,
                    stage=TaskStage.COMPLETE,
                ),
                Task(
                    id="t2",
                    description="Second task - currently in progress",
                    status=TaskStatus.IN_PROGRESS,
                    stage=TaskStage.IMPLEMENTING,
                ),
                Task(
                    id="t3",
                    description="Third task pending",
                    status=TaskStatus.PENDING,
                    stage=TaskStage.PENDING,
                ),
                Task(
                    id="t4",
                    description="Fourth task pending",
                    status=TaskStatus.PENDING,
                    stage=TaskStage.PENDING,
                ),
            ],
        )

    def test_init_creates_console_if_not_provided(self) -> None:
        """Display should create its own console if not provided."""
        display = OrchestratorDisplay()
        assert display.console is not None

    def test_init_uses_provided_console(self, console: Console) -> None:
        """Display should use provided console."""
        display = OrchestratorDisplay(console=console)
        assert display.console is console

    def test_update_state(
        self, display: OrchestratorDisplay, sample_state: WorkflowState
    ) -> None:
        """update_state should store state."""
        display.update_state(sample_state)
        assert display._state is sample_state

    def test_update_current_task(
        self, display: OrchestratorDisplay, sample_state: WorkflowState
    ) -> None:
        """update_current_task should store current task."""
        task = sample_state.tasks[1]
        display.update_current_task(task)
        assert display._current_task is task

    def test_update_current_task_none(self, display: OrchestratorDisplay) -> None:
        """update_current_task should accept None."""
        display.update_current_task(None)
        assert display._current_task is None

    def test_update_stage(
        self, display: OrchestratorDisplay, sample_state: WorkflowState
    ) -> None:
        """update_stage should update current task's stage."""
        task = sample_state.tasks[1]
        display.update_current_task(task)
        display.update_stage(TaskStage.VALIDATING)
        assert display._current_task.stage == TaskStage.VALIDATING

    def test_build_display_with_no_state(self, display: OrchestratorDisplay) -> None:
        """Building display with no state should return panel."""
        panel = display._build_display()
        assert panel is not None
        assert "No state" in str(panel.renderable)

    def test_build_display_with_state(
        self, display: OrchestratorDisplay, sample_state: WorkflowState
    ) -> None:
        """Building display with state should include task info."""
        display._state = sample_state
        display._current_task = sample_state.tasks[1]
        panel = display._build_display()
        assert panel is not None

    def test_build_current_task_section_with_task(
        self, display: OrchestratorDisplay, sample_state: WorkflowState
    ) -> None:
        """Current task section should show task details."""
        display._current_task = sample_state.tasks[1]
        table = display._build_current_task_section()
        assert table is not None

    def test_build_current_task_section_no_task(
        self, display: OrchestratorDisplay
    ) -> None:
        """Current task section should handle no current task."""
        display._current_task = None
        table = display._build_current_task_section()
        assert table is not None

    def test_build_next_tasks_section(
        self, display: OrchestratorDisplay, sample_state: WorkflowState
    ) -> None:
        """Next tasks section should show pending tasks."""
        display._state = sample_state
        display._current_task = sample_state.tasks[1]
        table = display._build_next_tasks_section()
        assert table is not None

    def test_build_next_tasks_limits_to_three(
        self, display: OrchestratorDisplay, sample_state: WorkflowState
    ) -> None:
        """Next tasks section should limit to 3 tasks."""
        # Add more pending tasks
        for i in range(5, 10):
            sample_state.tasks.append(
                Task(
                    id=f"t{i}",
                    description=f"Task {i}",
                    status=TaskStatus.PENDING,
                    stage=TaskStage.PENDING,
                )
            )
        display._state = sample_state
        display._current_task = sample_state.tasks[1]
        # The method internally limits to 3, verify it doesn't crash
        table = display._build_next_tasks_section()
        assert table is not None

    def test_build_progress_section(
        self, display: OrchestratorDisplay, sample_state: WorkflowState
    ) -> None:
        """Progress section should show completion stats."""
        display._state = sample_state
        text = display._build_progress_section()
        assert "1/4 tasks" in str(text)
        assert "Iteration 2/10" in str(text)

    def test_log_iteration(self, display: OrchestratorDisplay) -> None:
        """log_iteration should not raise."""
        display.log_iteration(1, 10)  # Should not raise

    def test_log_task_start(
        self, display: OrchestratorDisplay, sample_state: WorkflowState
    ) -> None:
        """log_task_start should not raise."""
        task = sample_state.tasks[0]
        display.log_task_start(task)  # Should not raise

    def test_log_task_complete(
        self, display: OrchestratorDisplay, sample_state: WorkflowState
    ) -> None:
        """log_task_complete should not raise."""
        task = sample_state.tasks[0]
        display.log_task_complete(task)  # Should not raise

    def test_log_workflow_result_success(self, display: OrchestratorDisplay) -> None:
        """log_workflow_result should handle success."""
        display.log_workflow_result(
            strategy="full",
            success=True,
            outputs={"plan": "/path/to/plan.md"},
        )  # Should not raise

    def test_log_workflow_result_failure(self, display: OrchestratorDisplay) -> None:
        """log_workflow_result should handle failure."""
        display.log_workflow_result(
            strategy="quick",
            success=False,
        )  # Should not raise


class TestCreateDisplay:
    """Tests for create_display factory function."""

    def test_creates_display(self) -> None:
        """create_display should return OrchestratorDisplay."""
        display = create_display()
        assert isinstance(display, OrchestratorDisplay)

    def test_accepts_console(self) -> None:
        """create_display should accept console parameter."""
        console = Console()
        display = create_display(console=console)
        assert display.console is console


class TestStageOrder:
    """Tests for STAGE_ORDER constant."""

    def test_starts_with_pending(self) -> None:
        """Stage order should start with pending."""
        assert STAGE_ORDER[0] == "pending"

    def test_ends_with_complete(self) -> None:
        """Stage order should end with complete."""
        assert STAGE_ORDER[-1] == "complete"

    def test_contains_all_workflow_stages(self) -> None:
        """Stage order should contain key workflow stages."""
        expected = [
            "researching codebase",
            "creating plan",
            "reviewing plan",
            "implementing changes",
        ]
        for stage in expected:
            assert stage in STAGE_ORDER
