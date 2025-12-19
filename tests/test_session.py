"""Tests for π.session module."""

import logging
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

    def test_builds_from_numbered_files(self, temp_command_dir: Path):
        """Should build command map from numbered markdown files."""
        result = build_command_map(command_dir=temp_command_dir)

        assert Command.CLARIFY in result
        assert Command.RESEARCH_CODEBASE in result
        assert Command.CREATE_PLAN in result
        assert Command.IMPLEMENT_PLAN in result
        assert result[Command.CLARIFY] == "/0_clarify"
        assert result[Command.RESEARCH_CODEBASE] == "/1_research_codebase"
        assert result[Command.CREATE_PLAN] == "/2_create_plan"
        assert result[Command.IMPLEMENT_PLAN] == "/3_implement_plan"

    def test_returns_empty_when_dir_missing(self, tmp_path: Path):
        """Should return empty dict if command directory doesn't exist."""
        nonexistent = tmp_path / "nonexistent"
        result = build_command_map(command_dir=nonexistent)

        assert result == {}

    def test_skips_non_matching_files(self, tmp_path: Path):
        """Should skip files that don't match the numbered pattern."""
        cmd_dir = tmp_path / "commands"
        cmd_dir.mkdir()

        # Create files that don't match pattern
        (cmd_dir / "readme.md").write_text("# Readme")
        (cmd_dir / "notes.txt").write_text("notes")
        (cmd_dir / "a_invalid.md").write_text("invalid")

        result = build_command_map(command_dir=cmd_dir)
        assert result == {}

    def test_skips_unknown_commands(self, tmp_path: Path):
        """Should skip files with unknown command names."""
        cmd_dir = tmp_path / "commands"
        cmd_dir.mkdir()

        # Create a numbered file with unknown command
        (cmd_dir / "99_unknown_command.md").write_text("# Unknown")

        result = build_command_map(command_dir=cmd_dir)
        assert result == {}

    def test_handles_malformed_files_gracefully(self, tmp_path: Path):
        """Should handle edge cases in file naming."""
        cmd_dir = tmp_path / "commands"
        cmd_dir.mkdir()

        # File with just a number (no underscore separator)
        (cmd_dir / "1.md").write_text("# Just number")
        # File with empty name after number
        (cmd_dir / "0_.md").write_text("# Empty name")

        result = build_command_map(command_dir=cmd_dir)
        # Should not crash, just skip
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

    def test_should_resume_when_no_stored_session(self):
        """Should return False when no session ID was stored."""
        session = WorkflowSession()

        assert session.should_resume(Command.RESEARCH_CODEBASE, "any-id") is False

    def test_validate_plan_doc_raises_when_same_as_research(self):
        """Should raise ValueError if plan path equals research doc."""
        session = WorkflowSession()
        session.set_doc_path(Command.CREATE_PLAN, "/path/to/research.md")

        with pytest.raises(ValueError) as exc_info:
            session.validate_plan_doc("/path/to/research.md")

        assert "implement_plan requires the PLAN document" in str(exc_info.value)
        assert "/path/to/research.md" in str(exc_info.value)

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

    def test_multiple_sessions_independent(self):
        """Different command sessions should be independent."""
        session = WorkflowSession()
        session.set_session_id(Command.CLARIFY, "clarify-000")
        session.set_session_id(Command.RESEARCH_CODEBASE, "research-123")
        session.set_session_id(Command.CREATE_PLAN, "plan-456")
        session.set_session_id(Command.IMPLEMENT_PLAN, "impl-789")

        assert session.get_session_id(Command.CLARIFY) == "clarify-000"
        assert session.get_session_id(Command.RESEARCH_CODEBASE) == "research-123"
        assert session.get_session_id(Command.CREATE_PLAN) == "plan-456"
        assert session.get_session_id(Command.IMPLEMENT_PLAN) == "impl-789"

    def test_log_session_state_logs_all_data(self, caplog: pytest.LogCaptureFixture):
        """Should log all session state at debug level."""
        session = WorkflowSession()
        session.set_session_id(Command.CLARIFY, "test-id")
        session.set_doc_path(Command.CREATE_PLAN, "/test/path.md")

        with caplog.at_level(logging.DEBUG):
            session.log_session_state()

        assert "WorkflowSession state" in caplog.text
        assert "test-id" in caplog.text
        assert "/test/path.md" in caplog.text
