"""Tests for π.workflow.context module."""

from π.core.enums import Command, DocType
from π.workflow.context import WorkflowContext, get_workflow_ctx, reset_workflow_ctx


class TestWorkflowContext:
    """Tests for WorkflowContext dataclass."""

    def test_default_values(self):
        """Should have empty defaults."""
        ctx = WorkflowContext()
        assert ctx.session_ids == {}
        assert ctx.doc_paths == {}
        assert ctx.objective is None
        assert ctx.observer is None

    def test_can_store_session_ids(self):
        """Should store session IDs by command."""
        ctx = WorkflowContext()
        ctx.session_ids[Command.RESEARCH_CODEBASE] = "session-123"
        assert ctx.session_ids[Command.RESEARCH_CODEBASE] == "session-123"

    def test_can_store_doc_paths(self):
        """Should store document paths by doc type."""
        ctx = WorkflowContext()
        ctx.doc_paths[DocType.RESEARCH] = "/path/to/research.md"
        assert ctx.doc_paths[DocType.RESEARCH] == "/path/to/research.md"


class TestGetWorkflowCtx:
    """Tests for get_workflow_ctx function."""

    def test_returns_context(self):
        """Should return a WorkflowContext."""
        reset_workflow_ctx()
        ctx = get_workflow_ctx()
        assert isinstance(ctx, WorkflowContext)

    def test_returns_same_instance(self):
        """Should return same instance on repeated calls."""
        reset_workflow_ctx()
        ctx1 = get_workflow_ctx()
        ctx2 = get_workflow_ctx()
        assert ctx1 is ctx2


class TestResetWorkflowCtx:
    """Tests for reset_workflow_ctx function."""

    def test_creates_fresh_context(self):
        """Should create a fresh context after reset."""
        ctx1 = get_workflow_ctx()
        ctx1.objective = "test"
        reset_workflow_ctx()
        ctx2 = get_workflow_ctx()
        assert ctx2.objective is None
        assert ctx1 is not ctx2
