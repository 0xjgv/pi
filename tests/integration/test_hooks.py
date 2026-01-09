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

    @pytest.mark.asyncio
    async def test_check_file_format_ignores_non_edit_write(self):
        """check_file_format should only run for Edit/Write tools."""
        from π.hooks import check_file_format

        input_data = cast(
            "HookInput",
            {
                "tool_name": "Bash",
                "tool_input": {"command": "ls"},
            },
        )
        context = HookContext(signal=None)

        result = await check_file_format(input_data, None, context)

        assert result == {}

    @pytest.mark.asyncio
    async def test_check_file_format_ignores_missing_file_path(self):
        """check_file_format should return empty when no file_path."""
        from π.hooks import check_file_format

        input_data = cast(
            "HookInput",
            {
                "tool_name": "Edit",
                "tool_input": {},
            },
        )
        context = HookContext(signal=None)

        result = await check_file_format(input_data, None, context)

        assert result == {}

    @pytest.mark.asyncio
    async def test_check_file_format_ignores_nonexistent_file(self, tmp_path: Path):
        """check_file_format should return empty when file doesn't exist."""
        from π.hooks import check_file_format

        input_data = cast(
            "HookInput",
            {
                "tool_name": "Write",
                "tool_input": {"file_path": str(tmp_path / "nonexistent.py")},
            },
        )
        context = HookContext(signal=None)

        result = await check_file_format(input_data, None, context)

        assert result == {}

    @pytest.mark.asyncio
    async def test_check_file_format_ignores_unknown_extension(self, tmp_path: Path):
        """check_file_format should return empty for unknown file types."""
        from π.hooks import check_file_format

        unknown_file = tmp_path / "test.xyz"
        unknown_file.write_text("content")

        input_data = cast(
            "HookInput",
            {
                "tool_name": "Edit",
                "tool_input": {"file_path": str(unknown_file)},
            },
        )
        context = HookContext(signal=None)

        result = await check_file_format(input_data, None, context)

        assert result == {}

    @pytest.mark.asyncio
    async def test_check_file_format_runs_checker_on_python(self, tmp_path: Path):
        """check_file_format should run checker for Python files."""
        from unittest.mock import MagicMock, patch

        from π.hooks import check_file_format
        from π.hooks.registry import LanguageChecker

        python_file = tmp_path / "test.py"
        python_file.write_text("print('hello')\n")

        input_data = cast(
            "HookInput",
            {
                "tool_name": "Edit",
                "tool_input": {"file_path": str(python_file)},
            },
        )
        context = HookContext(signal=None)

        # Mock get_checker to return a mock checker that succeeds
        mock_checker = LanguageChecker(
            func=MagicMock(return_value=0), scope="file", project_markers=[]
        )
        with patch("π.hooks.linting.get_checker", return_value=mock_checker):
            result = await check_file_format(input_data, None, context)

        assert result == {}

    @pytest.mark.asyncio
    async def test_check_file_format_blocks_on_failure(self, tmp_path: Path):
        """check_file_format should block when checker returns exit code 2."""
        from unittest.mock import MagicMock, patch

        from π.hooks import check_file_format
        from π.hooks.registry import LanguageChecker

        python_file = tmp_path / "test.py"
        python_file.write_text("print('hello')\n")

        input_data = cast(
            "HookInput",
            {
                "tool_name": "Edit",
                "tool_input": {"file_path": str(python_file)},
            },
        )
        context = HookContext(signal=None)

        # Mock get_checker to return a mock checker that fails
        mock_checker = LanguageChecker(
            func=MagicMock(return_value=2), scope="file", project_markers=[]
        )
        with patch("π.hooks.linting.get_checker", return_value=mock_checker):
            result = await check_file_format(input_data, None, context)

        assert result.get("decision") == "block"
        assert "Code quality checks failed" in result.get("reason", "")
