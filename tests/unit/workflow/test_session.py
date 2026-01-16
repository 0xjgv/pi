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
        assert Command.RESEARCH_CODEBASE == "research_codebase"
        assert Command.CREATE_PLAN == "create_plan"
        assert Command.REVIEW_PLAN == "review_plan"
        assert Command.IMPLEMENT_PLAN == "implement_plan"
        assert Command.COMMIT == "commit"

    def test_is_string_enum(self):
        """Command values should be usable as strings."""
        assert str(Command.RESEARCH_CODEBASE) == "research_codebase"
        assert f"{Command.CREATE_PLAN}" == "create_plan"


class TestBuildCommandMap:
    """Tests for build_command_map function."""

    def test_returns_empty_when_dir_not_exists(self, tmp_path: Path):
        """Should return empty dict if command directory doesn't exist."""
        result = build_command_map(command_dir=tmp_path / "nonexistent")
        assert result == {}

    def test_parses_numbered_command_files(self, tmp_path: Path):
        """Should parse numbered command files to Command enum."""
        (tmp_path / "1_research_codebase.md").write_text("# Research")
        (tmp_path / "2_create_plan.md").write_text("# Create Plan")

        result = build_command_map(command_dir=tmp_path)

        assert Command.RESEARCH_CODEBASE in result
        assert result[Command.RESEARCH_CODEBASE] == "/1_research_codebase"
        assert Command.CREATE_PLAN in result
        assert result[Command.CREATE_PLAN] == "/2_create_plan"

    def test_ignores_malformed_files(self, tmp_path: Path):
        """Should skip files that don't match pattern."""
        (tmp_path / "invalid.md").write_text("# Invalid")
        (tmp_path / "0_.md").write_text("# Empty name")
        (tmp_path / "1_research_codebase.md").write_text("# Valid")

        result = build_command_map(command_dir=tmp_path)

        assert len(result) == 1
        assert Command.RESEARCH_CODEBASE in result

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

    def test_set_and_get_session_id(self):
        """Should store and retrieve session IDs via dict."""
        ctx = ExecutionContext()

        ctx.session_ids[Command.RESEARCH_CODEBASE] = "session-123"

        assert ctx.session_ids.get(Command.RESEARCH_CODEBASE) == "session-123"
        assert ctx.session_ids.get(Command.CREATE_PLAN) is None  # not set

    def test_get_or_validate_plan_path_auto_selects_from_context(self, tmp_path):
        """Should auto-select most recent plan when no path provided."""
        import os

        # Create plan directory structure
        plans_dir = tmp_path / "thoughts/shared/plans"
        plans_dir.mkdir(parents=True)

        # Create two plans with different mtimes
        old_plan = plans_dir / "2024-01-01-old-plan.md"
        new_plan = plans_dir / "2024-01-02-new-plan.md"
        old_plan.write_text("old")
        new_plan.write_text("new")

        # Set explicit mtimes to ensure deterministic selection
        os.utime(old_plan, (1000000, 1000000))  # older mtime
        os.utime(new_plan, (2000000, 2000000))  # newer mtime

        ctx = ExecutionContext()
        ctx.extracted_paths[Command.CREATE_PLAN] = {str(old_plan), str(new_plan)}

        result = ctx.get_or_validate_plan_path()
        assert result == str(new_plan.resolve())

    def test_get_or_validate_plan_path_validates_provided_path(self, tmp_path):
        """Should validate and return provided path."""
        plans_dir = tmp_path / "thoughts/shared/plans"
        plans_dir.mkdir(parents=True)
        plan = plans_dir / "2024-01-01-test-plan.md"
        plan.write_text("plan content")

        ctx = ExecutionContext()
        result = ctx.get_or_validate_plan_path(str(plan))
        assert result == str(plan.resolve())

    def test_get_or_validate_plan_path_raises_when_no_plan(self):
        """Should raise ValueError when no plan in context and none provided."""
        ctx = ExecutionContext()

        with pytest.raises(ValueError) as exc_info:
            ctx.get_or_validate_plan_path()

        assert "No plan document available" in str(exc_info.value)

    def test_get_or_validate_plan_path_raises_for_invalid_path(self):
        """Should raise ValueError for path not in plans directory."""
        ctx = ExecutionContext()

        with pytest.raises(ValueError) as exc_info:
            ctx.get_or_validate_plan_path("/nonexistent/path.md")

        # PlanDocPath validates directory first
        assert "must be in thoughts/shared/plans" in str(exc_info.value)

    def test_log_session_state_logs_all_data(self, caplog: pytest.LogCaptureFixture):
        """Should log all context state at debug level."""
        import logging

        ctx = ExecutionContext()
        ctx.extracted_paths[Command.RESEARCH_CODEBASE] = {"/test/path.md"}
        ctx.session_ids[Command.RESEARCH_CODEBASE] = "test-id"

        with caplog.at_level(logging.DEBUG, logger="π.workflow.context"):
            ctx.log_session_state()

        assert "ExecutionContext state" in caplog.text
        assert "test-id" in caplog.text
        assert "/test/path.md" in caplog.text
