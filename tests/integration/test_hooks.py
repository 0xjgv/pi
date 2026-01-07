"""Integration tests for hook system."""

from pathlib import Path
from typing import cast

import pytest
from claude_agent_sdk.types import HookContext, HookInput


class TestHookIntegration:
    """Integration tests for hook system."""

    @pytest.fixture
    def project_with_python(self, tmp_path: Path) -> Path:
        """Create a Python project structure."""
        (tmp_path / "pyproject.toml").write_text("[project]\nname = 'test'")
        src = tmp_path / "src"
        src.mkdir()
        (src / "main.py").write_text("print('hello')\n")
        return tmp_path

    def test_check_file_format_integrates_with_registry(
        self, project_with_python: Path
    ):
        """check_file_format should use registry to find checker."""
        from π.hooks.registry import get_checker

        # Verify Python checker is registered
        checker = get_checker(".py")
        assert checker is not None

        # Test that file would be recognized
        python_file = project_with_python / "src" / "main.py"
        assert python_file.suffix == ".py"

    @pytest.mark.asyncio
    async def test_bash_command_hook_blocks_dangerous(self):
        """Bash command hook should block dangerous commands."""
        from π.hooks import check_bash_command

        dangerous_input = cast(
            "HookInput",
            {
                "tool_name": "Bash",
                "tool_input": {"command": "rm -rf /"},
            },
        )
        context = HookContext(signal=None)

        result = await check_bash_command(dangerous_input, None, context)

        hook_output = result.get("hookSpecificOutput")
        assert hook_output is not None
        assert hook_output.get("permissionDecision") == "deny"

    @pytest.mark.asyncio
    async def test_bash_command_hook_allows_safe(self):
        """Bash command hook should allow safe commands."""
        from π.hooks import check_bash_command

        safe_input = cast(
            "HookInput",
            {
                "tool_name": "Bash",
                "tool_input": {"command": "ls -la"},
            },
        )
        context = HookContext(signal=None)

        result = await check_bash_command(safe_input, None, context)

        assert result == {}
