"""Tests for π.agent module."""

from pathlib import Path

from π.agent import AVAILABLE_TOOLS, get_agent_options


class TestAvailableTools:
    """Tests for AVAILABLE_TOOLS constant."""

    def test_includes_core_tools(self):
        """Should include essential tools."""
        assert "Bash" in AVAILABLE_TOOLS
        assert "Read" in AVAILABLE_TOOLS
        assert "Write" in AVAILABLE_TOOLS
        assert "Edit" in AVAILABLE_TOOLS
        assert "Grep" in AVAILABLE_TOOLS
        assert "Glob" in AVAILABLE_TOOLS

    def test_all_tools_are_strings(self):
        """All tools should be string identifiers."""
        for tool in AVAILABLE_TOOLS:
            assert isinstance(tool, str)
            assert len(tool) > 0


class TestGetAgentOptions:
    """Tests for get_agent_options factory function."""

    def test_returns_claude_agent_options(self):
        """Should return a ClaudeAgentOptions instance."""
        from claude_agent_sdk import ClaudeAgentOptions

        result = get_agent_options()

        assert isinstance(result, ClaudeAgentOptions)

    def test_sets_permission_mode_to_accept_edits(self):
        """Should use acceptEdits permission mode."""
        result = get_agent_options()

        assert result.permission_mode == "acceptEdits"

    def test_includes_all_available_tools(self):
        """Should include all available tools."""
        result = get_agent_options()

        assert result.allowed_tools == AVAILABLE_TOOLS

    def test_configures_hooks(self):
        """Should configure PreToolUse and PostToolUse hooks."""
        result = get_agent_options()

        assert "PreToolUse" in result.hooks
        assert "PostToolUse" in result.hooks

    def test_pre_tool_use_matches_bash(self):
        """PreToolUse hook should match Bash tool."""
        result = get_agent_options()

        pre_hooks = result.hooks["PreToolUse"]
        assert len(pre_hooks) == 1
        assert pre_hooks[0].matcher == "Bash"

    def test_post_tool_use_matches_write_edit(self):
        """PostToolUse hook should match Write and Edit tools."""
        result = get_agent_options()

        post_hooks = result.hooks["PostToolUse"]
        assert len(post_hooks) == 1
        assert "Write" in post_hooks[0].matcher
        assert "Edit" in post_hooks[0].matcher

    def test_uses_provided_cwd(self, tmp_path: Path):
        """Should use the provided cwd."""
        result = get_agent_options(cwd=tmp_path)

        assert result.cwd == tmp_path

    def test_defaults_to_current_cwd(self):
        """Should default to Path.cwd() when no cwd provided."""
        result = get_agent_options()

        assert result.cwd == Path.cwd()

    def test_uses_provided_system_prompt(self):
        """Should use the provided system prompt."""
        result = get_agent_options(system_prompt="Custom prompt")

        assert result.system_prompt == "Custom prompt"

    def test_setting_sources_includes_project(self):
        """Should include 'project' in setting sources."""
        result = get_agent_options()

        assert "project" in result.setting_sources
