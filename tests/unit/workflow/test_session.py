"""Tests for π.workflow.bridge module (Command, ExecutionContext)."""

from pathlib import Path

import pytest

from π.workflow import (
    Command,
    ExecutionContext,
    build_command_map,
)


class TestCommand:
    """Tests for Command enum."""

    def test_has_all_workflow_stages(self):
        """Should define all workflow stages."""
        assert Command.CLARIFY == "clarify"
        assert Command.RESEARCH_CODEBASE == "research_codebase"
        assert Command.CREATE_PLAN == "create_plan"
        assert Command.ITERATE_PLAN == "iterate_plan"

    def test_is_string_enum(self):
        """Command values should be usable as strings."""
        assert str(Command.CLARIFY) == "clarify"
        assert f"{Command.RESEARCH_CODEBASE}" == "research_codebase"


class TestBuildCommandMap:
    """Tests for build_command_map function."""

    def test_returns_empty_when_dir_not_exists(self, tmp_path: Path):
        """Should return empty dict if command directory doesn't exist."""
        result = build_command_map(command_dir=tmp_path / "nonexistent")
        assert result == {}

    def test_parses_numbered_command_files(self, tmp_path: Path):
        """Should parse files like 0_clarify.md -> Command.CLARIFY."""
        (tmp_path / "0_clarify.md").write_text("# Clarify")
        (tmp_path / "1_research_codebase.md").write_text("# Research")

        result = build_command_map(command_dir=tmp_path)

        assert Command.CLARIFY in result
        assert result[Command.CLARIFY] == "/0_clarify"
        assert Command.RESEARCH_CODEBASE in result
        assert result[Command.RESEARCH_CODEBASE] == "/1_research_codebase"

    def test_ignores_malformed_files(self, tmp_path: Path):
        """Should skip files that don't match pattern."""
        (tmp_path / "invalid.md").write_text("# Invalid")
        (tmp_path / "0_.md").write_text("# Empty name")
        (tmp_path / "0_clarify.md").write_text("# Valid")

        result = build_command_map(command_dir=tmp_path)

        assert len(result) == 1
        assert Command.CLARIFY in result

    def test_ignores_unknown_commands(self, tmp_path: Path):
        """Should skip files with unknown command names."""
        (tmp_path / "99_unknown_command.md").write_text("# Unknown")

        result = build_command_map(command_dir=tmp_path)

        assert result == {}


class TestExecutionContext:
    """Tests for ExecutionContext dataclass."""

    def test_initial_state_has_empty_session_ids(self):
        """New context should have empty session_ids dict."""
        ctx = ExecutionContext()

        assert ctx.session_ids == {}

    def test_initial_state_has_empty_doc_paths(self):
        """New context should have empty doc_paths dict."""
        ctx = ExecutionContext()

        assert ctx.doc_paths == {}

    def test_set_and_get_session_id(self):
        """Should store and retrieve session IDs via dict."""
        ctx = ExecutionContext()

        ctx.session_ids[Command.RESEARCH_CODEBASE] = "session-123"

        assert ctx.session_ids.get(Command.RESEARCH_CODEBASE) == "session-123"
        assert ctx.session_ids.get(Command.CLARIFY) is None  # not set

    def test_set_and_get_doc_path(self):
        """Should store and retrieve doc paths via dict."""
        ctx = ExecutionContext()

        ctx.doc_paths[Command.CREATE_PLAN] = "/path/to/research.md"

        assert ctx.doc_paths.get(Command.CREATE_PLAN) == "/path/to/research.md"

    def test_validate_plan_doc_raises_when_same_as_research(self):
        """Should raise ValueError if plan path equals research doc."""
        ctx = ExecutionContext()
        ctx.doc_paths[Command.CREATE_PLAN] = "/path/to/research.md"

        with pytest.raises(ValueError) as exc_info:
            ctx.validate_plan_doc("/path/to/research.md")

        assert "implement_plan requires the PLAN document" in str(exc_info.value)

    def test_validate_plan_doc_allows_different_paths(self):
        """Should not raise when plan path differs from research doc."""
        ctx = ExecutionContext()
        ctx.doc_paths[Command.CREATE_PLAN] = "/path/to/research.md"

        # Should not raise
        ctx.validate_plan_doc("/path/to/plan.md")

    def test_validate_plan_doc_allows_when_no_research_doc(self):
        """Should not raise when no research doc is set."""
        ctx = ExecutionContext()

        # Should not raise
        ctx.validate_plan_doc("/path/to/plan.md")

    def test_log_session_state_logs_all_data(self, caplog: pytest.LogCaptureFixture):
        """Should log all context state at debug level."""
        import logging

        ctx = ExecutionContext()
        ctx.session_ids[Command.CLARIFY] = "test-id"
        ctx.doc_paths[Command.CREATE_PLAN] = "/test/path.md"

        with caplog.at_level(logging.DEBUG, logger="π.workflow.bridge"):
            ctx.log_session_state()

        assert "ExecutionContext state" in caplog.text
        assert "test-id" in caplog.text
        assert "/test/path.md" in caplog.text
