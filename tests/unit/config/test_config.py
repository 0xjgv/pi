"""Tests for π.config module."""

from pathlib import Path
from unittest.mock import patch

from π.config import (
    COMMAND_MAP,
    ORCHESTRATOR_TOOLS,
    STAGE_AGENT_TOOLS,
    build_command_map,
    get_orchestrator_options,
    get_stage_agent_options,
)
from π.core.enums import Command


class TestToolConfiguration:
    """Tests for tool configuration constants."""

    def test_orchestrator_tools_has_read_only(self):
        """Orchestrator should have read-only tools."""
        assert "Glob" in ORCHESTRATOR_TOOLS
        assert "Grep" in ORCHESTRATOR_TOOLS
        assert "Read" in ORCHESTRATOR_TOOLS
        # Should NOT have write tools
        assert "Write" not in ORCHESTRATOR_TOOLS
        assert "Edit" not in ORCHESTRATOR_TOOLS

    def test_stage_agent_tools_has_write_tools(self):
        """Stage agents should have write tools."""
        assert "Write" in STAGE_AGENT_TOOLS
        assert "Edit" in STAGE_AGENT_TOOLS
        assert "Bash" in STAGE_AGENT_TOOLS

    def test_stage_agent_tools_excludes_ask_user_question(self):
        """Stage agents should NOT have AskUserQuestion."""
        assert "AskUserQuestion" not in STAGE_AGENT_TOOLS


class TestCommandMap:
    """Tests for COMMAND_MAP configuration."""

    def test_has_research_command(self):
        """Should have research_codebase command."""
        assert Command.RESEARCH_CODEBASE in COMMAND_MAP

    def test_has_plan_command(self):
        """Should have create_plan command."""
        assert Command.CREATE_PLAN in COMMAND_MAP

    def test_commands_are_slash_commands(self):
        """All commands should be slash commands."""
        for cmd, slash_cmd in COMMAND_MAP.items():
            assert slash_cmd.startswith("/"), f"{cmd} command doesn't start with /"

    def test_build_command_map_handles_missing_dir(self, tmp_path: Path):
        """Should return empty map for missing command directory."""
        result = build_command_map(command_dir=tmp_path / "nonexistent")
        assert result == {}


class TestGetOrchestratorOptions:
    """Tests for get_orchestrator_options function."""

    def test_returns_claude_agent_options(self):
        """Should return ClaudeAgentOptions instance."""
        with patch("π.config.get_project_root") as mock_root:
            mock_root.return_value = Path("/test")
            options = get_orchestrator_options()

        assert options is not None
        assert options.allowed_tools == ORCHESTRATOR_TOOLS

    def test_accepts_system_prompt(self):
        """Should accept custom system prompt."""
        with patch("π.config.get_project_root") as mock_root:
            mock_root.return_value = Path("/test")
            options = get_orchestrator_options(system_prompt="Test prompt")

        assert options.system_prompt == "Test prompt"


class TestGetStageAgentOptions:
    """Tests for get_stage_agent_options function."""

    def test_returns_claude_agent_options(self):
        """Should return ClaudeAgentOptions instance."""
        with patch("π.config.get_project_root") as mock_root:
            mock_root.return_value = Path("/test")
            options = get_stage_agent_options()

        assert options is not None
        assert options.allowed_tools == STAGE_AGENT_TOOLS

    def test_uses_project_setting_sources(self):
        """Should use project settings only."""
        with patch("π.config.get_project_root") as mock_root:
            mock_root.return_value = Path("/test")
            options = get_stage_agent_options()

        assert options.setting_sources == ["project"]
