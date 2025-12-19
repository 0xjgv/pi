"""Tests for π.session module."""

from pathlib import Path

import pytest

from π.session import (
    Command,
    WorkflowSession,
    build_command_map,
)


class TestCommand:
    """Tests for Command enum."""

    def test_has_all_workflow_stages(self):
        """Should define all workflow stages."""
        assert Command.CLARIFY == "clarify"
        assert Command.RESEARCH_CODEBASE == "research_codebase"
        assert Command.CREATE_PLAN == "create_plan"
        assert Command.IMPLEMENT_PLAN == "implement_plan"

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


class TestWorkflowSession:
    """Tests for WorkflowSession dataclass."""

    def test_initial_state_has_empty_session_ids(self):
        """New session should have empty session IDs for all commands."""
        session = WorkflowSession()

        for cmd in Command:
            assert session.get_session_id(cmd) == ""

    def test_initial_state_has_empty_doc_paths(self):
        """New session should have empty doc paths for all commands."""
        session = WorkflowSession()

        for cmd in Command:
            assert session.get_doc_path(cmd) == ""

    def test_set_and_get_session_id(self):
        """Should store and retrieve session IDs."""
        session = WorkflowSession()

        session.set_session_id(Command.RESEARCH_CODEBASE, "session-123")

        assert session.get_session_id(Command.RESEARCH_CODEBASE) == "session-123"
        assert session.get_session_id(Command.CLARIFY) == ""  # unchanged

    def test_set_and_get_doc_path(self):
        """Should store and retrieve doc paths."""
        session = WorkflowSession()

        session.set_doc_path(Command.CREATE_PLAN, "/path/to/research.md")

        assert session.get_doc_path(Command.CREATE_PLAN) == "/path/to/research.md"

    def test_should_resume_returns_false_when_no_session_id(self):
        """Should return False when no session_id provided."""
        session = WorkflowSession()

        assert session.should_resume(Command.CLARIFY, None) is False
        assert session.should_resume(Command.CLARIFY, "") is False

    def test_should_resume_returns_false_when_ids_dont_match(self):
        """Should return False when session IDs don't match."""
        session = WorkflowSession()
        session.set_session_id(Command.CLARIFY, "session-123")

        assert session.should_resume(Command.CLARIFY, "different-id") is False

    def test_should_resume_returns_true_when_ids_match(self):
        """Should return True when session IDs match."""
        session = WorkflowSession()
        session.set_session_id(Command.CLARIFY, "session-123")

        assert session.should_resume(Command.CLARIFY, "session-123") is True

    def test_validate_plan_doc_raises_when_same_as_research(self):
        """Should raise ValueError if plan path equals research doc."""
        session = WorkflowSession()
        session.set_doc_path(Command.CREATE_PLAN, "/path/to/research.md")

        with pytest.raises(ValueError) as exc_info:
            session.validate_plan_doc("/path/to/research.md")

        assert "implement_plan requires the PLAN document" in str(exc_info.value)

    def test_validate_plan_doc_allows_different_paths(self):
        """Should not raise when plan path differs from research doc."""
        session = WorkflowSession()
        session.set_doc_path(Command.CREATE_PLAN, "/path/to/research.md")

        # Should not raise
        session.validate_plan_doc("/path/to/plan.md")

    def test_validate_plan_doc_allows_when_no_research_doc(self):
        """Should not raise when no research doc is set."""
        session = WorkflowSession()

        # Should not raise
        session.validate_plan_doc("/path/to/plan.md")

    def test_log_session_state_logs_all_data(self, caplog: pytest.LogCaptureFixture):
        """Should log all session state at debug level."""
        import logging

        session = WorkflowSession()
        session.set_session_id(Command.CLARIFY, "test-id")
        session.set_doc_path(Command.CREATE_PLAN, "/test/path.md")

        with caplog.at_level(logging.DEBUG):
            session.log_session_state()

        assert "WorkflowSession state" in caplog.text
        assert "test-id" in caplog.text
        assert "/test/path.md" in caplog.text
