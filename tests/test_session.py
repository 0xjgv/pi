"""Tests for π.session module."""

from pathlib import Path

import pytest

from π.session import Command, WorkflowSession, build_command_map


class TestCommand:
    """Tests for Command enum."""

    def test_command_values(self):
        """Command enum should have expected string values."""
        assert Command.RESEARCH_CODEBASE == "research_codebase"
        assert Command.CREATE_PLAN == "create_plan"
        assert Command.IMPLEMENT_PLAN == "implement_plan"

    def test_command_is_str_enum(self):
        """Command should be usable as a string."""
        assert str(Command.RESEARCH_CODEBASE) == "research_codebase"
        assert f"{Command.CREATE_PLAN}" == "create_plan"


class TestBuildCommandMap:
    """Tests for build_command_map function."""

    def test_builds_from_numbered_files(self, temp_command_dir: Path):
        """Should build command map from numbered markdown files."""
        result = build_command_map(command_dir=temp_command_dir)

        assert Command.RESEARCH_CODEBASE in result
        assert Command.CREATE_PLAN in result
        assert Command.IMPLEMENT_PLAN in result
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
        (cmd_dir / "5_unknown_command.md").write_text("# Unknown")

        result = build_command_map(command_dir=cmd_dir)
        assert result == {}

    def test_handles_malformed_files_gracefully(self, tmp_path: Path):
        """Should handle edge cases in file naming."""
        cmd_dir = tmp_path / "commands"
        cmd_dir.mkdir()

        # File with just a number (no underscore separator)
        (cmd_dir / "1.md").write_text("# Just number")

        result = build_command_map(command_dir=cmd_dir)
        # Should not crash, just skip
        assert result == {}


class TestWorkflowSession:
    """Tests for WorkflowSession class."""

    def test_initialization_creates_empty_dicts(self):
        """Session should initialize with empty values for all commands."""
        session = WorkflowSession()

        for cmd in Command:
            assert session.get_session_id(cmd) == ""
            assert session.get_doc_path(cmd) == ""

    def test_get_set_session_id(self):
        """Should store and retrieve session IDs."""
        session = WorkflowSession()
        session.set_session_id(Command.RESEARCH_CODEBASE, "abc123")

        assert session.get_session_id(Command.RESEARCH_CODEBASE) == "abc123"
        assert session.get_session_id(Command.CREATE_PLAN) == ""

    def test_get_set_doc_path(self):
        """Should store and retrieve document paths."""
        session = WorkflowSession()
        session.set_doc_path(Command.CREATE_PLAN, "/path/to/research.md")

        assert session.get_doc_path(Command.CREATE_PLAN) == "/path/to/research.md"
        assert session.get_doc_path(Command.IMPLEMENT_PLAN) == ""

    def test_should_resume_with_matching_id(self):
        """Should return True when session ID matches."""
        session = WorkflowSession()
        session.set_session_id(Command.RESEARCH_CODEBASE, "session-xyz")

        assert session.should_resume(Command.RESEARCH_CODEBASE, "session-xyz") is True

    def test_should_resume_with_non_matching_id(self):
        """Should return False when session ID doesn't match."""
        session = WorkflowSession()
        session.set_session_id(Command.RESEARCH_CODEBASE, "session-xyz")

        assert session.should_resume(Command.RESEARCH_CODEBASE, "different-id") is False

    def test_should_resume_with_none(self):
        """Should return False when session ID is None."""
        session = WorkflowSession()
        session.set_session_id(Command.RESEARCH_CODEBASE, "session-xyz")

        assert session.should_resume(Command.RESEARCH_CODEBASE, None) is False

    def test_should_resume_with_empty_string(self):
        """Should return False when session ID is empty string."""
        session = WorkflowSession()
        session.set_session_id(Command.RESEARCH_CODEBASE, "session-xyz")

        assert session.should_resume(Command.RESEARCH_CODEBASE, "") is False

    def test_should_resume_when_no_stored_session(self):
        """Should return False when no session ID was stored."""
        session = WorkflowSession()

        assert session.should_resume(Command.RESEARCH_CODEBASE, "any-id") is False

    def test_validate_plan_doc_accepts_different_path(self):
        """Should accept a plan path different from research doc."""
        session = WorkflowSession()
        session.set_doc_path(Command.CREATE_PLAN, "/path/to/research.md")

        # Should not raise
        session.validate_plan_doc("/path/to/plan.md")

    def test_validate_plan_doc_rejects_research_doc(self):
        """Should reject when plan path matches research document."""
        session = WorkflowSession()
        session.set_doc_path(Command.CREATE_PLAN, "/path/to/research.md")

        with pytest.raises(ValueError) as exc_info:
            session.validate_plan_doc("/path/to/research.md")

        assert "implement_plan requires the PLAN document" in str(exc_info.value)
        assert "/path/to/research.md" in str(exc_info.value)

    def test_validate_plan_doc_allows_when_no_research_stored(self):
        """Should allow any path when no research doc was stored."""
        session = WorkflowSession()

        # Should not raise even with same paths
        session.validate_plan_doc("/any/path.md")

    def test_multiple_sessions_independent(self):
        """Different command sessions should be independent."""
        session = WorkflowSession()
        session.set_session_id(Command.RESEARCH_CODEBASE, "research-123")
        session.set_session_id(Command.CREATE_PLAN, "plan-456")
        session.set_session_id(Command.IMPLEMENT_PLAN, "impl-789")

        assert session.get_session_id(Command.RESEARCH_CODEBASE) == "research-123"
        assert session.get_session_id(Command.CREATE_PLAN) == "plan-456"
        assert session.get_session_id(Command.IMPLEMENT_PLAN) == "impl-789"
