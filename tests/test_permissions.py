"""Tests for π.support.permissions module."""

from unittest.mock import MagicMock, patch

import pytest
from claude_agent_sdk.types import PermissionResultAllow

from π.support.permissions import can_use_tool


class TestCanUseTool:
    """Tests for can_use_tool permission callback."""

    @pytest.mark.asyncio
    async def test_allows_non_askuserquestion_tools(self):
        """Should allow other tools without special handling."""
        result = await can_use_tool(
            tool_name="Bash",
            tool_input={"command": "ls"},
            context=MagicMock(),
        )

        assert isinstance(result, PermissionResultAllow)
        assert result.updated_input is None

    @pytest.mark.asyncio
    async def test_askuserquestion_returns_updated_input(self):
        """Should return user's response in updated_input."""
        with (
            patch("π.support.permissions.asyncio.to_thread") as mock_thread,
            patch("π.support.permissions.console"),
            patch("π.support.permissions.speak"),
            patch("π.support.permissions.get_current_status", return_value=None),
        ):
            mock_thread.return_value = "user response"

            result = await can_use_tool(
                tool_name="AskUserQuestion",
                tool_input={"question": "What is your goal?"},
                context=MagicMock(),
            )

        assert isinstance(result, PermissionResultAllow)
        assert result.updated_input == {
            "question": "What is your goal?",
            "answer": "user response",
        }

    @pytest.mark.asyncio
    async def test_askuserquestion_displays_question(self):
        """Should display the question to console."""
        with (
            patch("π.support.permissions.asyncio.to_thread", return_value="answer"),
            patch("π.support.permissions.console") as mock_console,
            patch("π.support.permissions.speak"),
            patch("π.support.permissions.get_current_status", return_value=None),
        ):
            await can_use_tool(
                tool_name="AskUserQuestion",
                tool_input={"question": "What feature?"},
                context=MagicMock(),
            )

        # Verify question was printed
        print_calls = str(mock_console.print.call_args_list)
        assert "What feature?" in print_calls

    @pytest.mark.asyncio
    async def test_askuserquestion_plays_audio(self):
        """Should play audio notification."""
        with (
            patch("π.support.permissions.asyncio.to_thread", return_value="answer"),
            patch("π.support.permissions.console"),
            patch("π.support.permissions.speak") as mock_speak,
            patch("π.support.permissions.get_current_status", return_value=None),
        ):
            await can_use_tool(
                tool_name="AskUserQuestion",
                tool_input={"question": "Test?"},
                context=MagicMock(),
            )

        mock_speak.assert_called_once_with("questions")

    @pytest.mark.asyncio
    async def test_askuserquestion_suspends_spinner(self):
        """Should suspend and resume spinner during input."""
        mock_status = MagicMock()

        with (
            patch("π.support.permissions.asyncio.to_thread", return_value="answer"),
            patch("π.support.permissions.console"),
            patch("π.support.permissions.speak"),
            patch("π.support.permissions.get_current_status", return_value=mock_status),
        ):
            await can_use_tool(
                tool_name="AskUserQuestion",
                tool_input={"question": "Test?"},
                context=MagicMock(),
            )

        mock_status.stop.assert_called_once()
        mock_status.start.assert_called_once()

    @pytest.mark.asyncio
    async def test_askuserquestion_handles_no_spinner(self):
        """Should handle case when no spinner is active."""
        with (
            patch("π.support.permissions.asyncio.to_thread", return_value="answer"),
            patch("π.support.permissions.console"),
            patch("π.support.permissions.speak"),
            patch("π.support.permissions.get_current_status", return_value=None),
        ):
            # Should not raise
            result = await can_use_tool(
                tool_name="AskUserQuestion",
                tool_input={"question": "Test?"},
                context=MagicMock(),
            )

        assert isinstance(result, PermissionResultAllow)

    @pytest.mark.asyncio
    async def test_askuserquestion_default_question(self):
        """Should use default question when none provided."""
        with (
            patch("π.support.permissions.asyncio.to_thread", return_value="answer"),
            patch("π.support.permissions.console"),
            patch("π.support.permissions.speak"),
            patch("π.support.permissions.get_current_status", return_value=None),
        ):
            result = await can_use_tool(
                tool_name="AskUserQuestion",
                tool_input={},  # No question
                context=MagicMock(),
            )

        assert result.updated_input["question"] == "Agent needs input:"

    @pytest.mark.asyncio
    async def test_truncates_long_input_in_logs(self):
        """Should truncate long tool inputs in debug logs (at 100 chars)."""
        long_input = {"data": "x" * 200}

        with patch("π.support.permissions.logger") as mock_logger:
            await can_use_tool(
                tool_name="Bash",
                tool_input=long_input,
                context=MagicMock(),
            )

        # Verify truncation in log call - actual code uses [:100] + "..."
        log_call = str(mock_logger.debug.call_args_list[-1])
        assert "..." in log_call
        # Verify truncation happened (str(long_input) > 100 chars)
        assert len(str(long_input)) > 100


class TestCanUseToolValidation:
    """Tests for input validation in can_use_tool (Phase 2 additions)."""

    @pytest.mark.asyncio
    async def test_empty_response_replaced(self):
        """Empty user response should be replaced with placeholder."""
        with (
            patch("π.support.permissions.wait_for") as mock_wait,
            patch("π.support.permissions.console"),
            patch("π.support.permissions.speak"),
            patch("π.support.permissions.get_current_status", return_value=None),
        ):
            mock_wait.return_value = "   "  # Whitespace only

            result = await can_use_tool(
                tool_name="AskUserQuestion",
                tool_input={"question": "Test?"},
                context=MagicMock(),
            )

        assert result.updated_input["answer"] == "[No response provided]"

    @pytest.mark.asyncio
    async def test_timeout_returns_placeholder(self):
        """Timeout should return placeholder response."""
        with (
            patch("π.support.permissions.wait_for") as mock_wait,
            patch("π.support.permissions.console"),
            patch("π.support.permissions.speak"),
            patch("π.support.permissions.get_current_status", return_value=None),
        ):
            # Use builtin TimeoutError (not deprecated asyncio.TimeoutError)
            mock_wait.side_effect = TimeoutError()

            result = await can_use_tool(
                tool_name="AskUserQuestion",
                tool_input={"question": "Test?"},
                context=MagicMock(),
            )

        assert "[No response - timed out]" in result.updated_input["answer"]

    @pytest.mark.asyncio
    async def test_empty_question_replaced(self):
        """Empty question should be replaced with default."""
        with (
            patch("π.support.permissions.wait_for") as mock_wait,
            patch("π.support.permissions.console"),
            patch("π.support.permissions.speak"),
            patch("π.support.permissions.get_current_status", return_value=None),
        ):
            mock_wait.return_value = "answer"

            result = await can_use_tool(
                tool_name="AskUserQuestion",
                tool_input={"question": "   "},  # Whitespace only
                context=MagicMock(),
            )

        assert result.updated_input["question"] == "Agent needs input:"
