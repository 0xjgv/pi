"""Tests for π.support.permissions module."""

from unittest.mock import MagicMock, patch

import pytest
from claude_agent_sdk.types import PermissionResultAllow

from π.support.permissions import can_use_tool


def _make_question(
    question: str = "Test question?",
    header: str = "Test",
    options: list | None = None,
    multi_select: bool = False,
) -> dict:
    """Helper to create a question dict."""
    return {
        "question": question,
        "header": header,
        "options": options
        or [
            {"label": "Option A", "description": "First option"},
            {"label": "Option B", "description": "Second option"},
        ],
        "multiSelect": multi_select,
    }


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
    async def test_askuserquestion_returns_structured_output(self):
        """Should return questions and answers in updated_input."""
        question = _make_question("What is your goal?", "Goal")

        with (
            patch("π.support.permissions.asyncio.to_thread") as mock_thread,
            patch("π.support.permissions.console"),
            patch("π.support.permissions.speak"),
            patch("π.support.permissions.get_current_status", return_value=None),
        ):
            mock_thread.return_value = "1"  # Select first option

            result = await can_use_tool(
                tool_name="AskUserQuestion",
                tool_input={"questions": [question]},
                context=MagicMock(),
            )

        assert isinstance(result, PermissionResultAllow)
        assert result.updated_input["questions"] == [question]
        assert result.updated_input["answers"] == {"What is your goal?": "Option A"}

    @pytest.mark.asyncio
    async def test_askuserquestion_displays_question_and_options(self):
        """Should display question header, text, and options."""
        question = _make_question("Which database?", "Database")

        with (
            patch("π.support.permissions.asyncio.to_thread", return_value="1"),
            patch("π.support.permissions.console") as mock_console,
            patch("π.support.permissions.speak"),
            patch("π.support.permissions.get_current_status", return_value=None),
        ):
            await can_use_tool(
                tool_name="AskUserQuestion",
                tool_input={"questions": [question]},
                context=MagicMock(),
            )

        print_calls = str(mock_console.print.call_args_list)
        assert "Database" in print_calls
        assert "Which database?" in print_calls
        assert "Option A" in print_calls
        assert "Option B" in print_calls

    @pytest.mark.asyncio
    async def test_askuserquestion_plays_audio(self):
        """Should play audio notification."""
        with (
            patch("π.support.permissions.asyncio.to_thread", return_value="1"),
            patch("π.support.permissions.console"),
            patch("π.support.permissions.speak") as mock_speak,
            patch("π.support.permissions.get_current_status", return_value=None),
        ):
            await can_use_tool(
                tool_name="AskUserQuestion",
                tool_input={"questions": [_make_question()]},
                context=MagicMock(),
            )

        mock_speak.assert_called_once_with("questions")

    @pytest.mark.asyncio
    async def test_askuserquestion_suspends_spinner(self):
        """Should suspend and resume spinner during input."""
        mock_status = MagicMock()

        with (
            patch("π.support.permissions.asyncio.to_thread", return_value="1"),
            patch("π.support.permissions.console"),
            patch("π.support.permissions.speak"),
            patch("π.support.permissions.get_current_status", return_value=mock_status),
        ):
            await can_use_tool(
                tool_name="AskUserQuestion",
                tool_input={"questions": [_make_question()]},
                context=MagicMock(),
            )

        mock_status.stop.assert_called_once()
        mock_status.start.assert_called_once()

    @pytest.mark.asyncio
    async def test_askuserquestion_handles_no_spinner(self):
        """Should handle case when no spinner is active."""
        with (
            patch("π.support.permissions.asyncio.to_thread", return_value="1"),
            patch("π.support.permissions.console"),
            patch("π.support.permissions.speak"),
            patch("π.support.permissions.get_current_status", return_value=None),
        ):
            result = await can_use_tool(
                tool_name="AskUserQuestion",
                tool_input={"questions": [_make_question()]},
                context=MagicMock(),
            )

        assert isinstance(result, PermissionResultAllow)

    @pytest.mark.asyncio
    async def test_askuserquestion_empty_questions_fallback(self):
        """Should use fallback when no questions provided."""
        with (
            patch("π.support.permissions.asyncio.to_thread", return_value="answer"),
            patch("π.support.permissions.console") as mock_console,
            patch("π.support.permissions.speak"),
            patch("π.support.permissions.get_current_status", return_value=None),
        ):
            result = await can_use_tool(
                tool_name="AskUserQuestion",
                tool_input={"questions": []},
                context=MagicMock(),
            )

        assert result.updated_input["questions"] == []
        assert "" in result.updated_input["answers"]
        print_calls = str(mock_console.print.call_args_list)
        assert "Agent needs input" in print_calls

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

        log_call = str(mock_logger.debug.call_args_list[-1])
        assert "..." in log_call
        assert len(str(long_input)) > 100


class TestAskUserQuestionOptions:
    """Tests for option selection handling."""

    @pytest.mark.asyncio
    async def test_numeric_selection_maps_to_label(self):
        """Entering a number should return the option label."""
        question = _make_question("Pick one?", "Choice")

        with (
            patch("π.support.permissions.asyncio.to_thread", return_value="2"),
            patch("π.support.permissions.console"),
            patch("π.support.permissions.speak"),
            patch("π.support.permissions.get_current_status", return_value=None),
        ):
            result = await can_use_tool(
                tool_name="AskUserQuestion",
                tool_input={"questions": [question]},
                context=MagicMock(),
            )

        assert result.updated_input["answers"]["Pick one?"] == "Option B"

    @pytest.mark.asyncio
    async def test_text_input_used_directly(self):
        """Text input should be used as-is."""
        question = _make_question("What feature?", "Feature")

        with (
            patch("π.support.permissions.asyncio.to_thread", return_value="Auth"),
            patch("π.support.permissions.console"),
            patch("π.support.permissions.speak"),
            patch("π.support.permissions.get_current_status", return_value=None),
        ):
            result = await can_use_tool(
                tool_name="AskUserQuestion",
                tool_input={"questions": [question]},
                context=MagicMock(),
            )

        assert result.updated_input["answers"]["What feature?"] == "Auth"

    @pytest.mark.asyncio
    async def test_multi_select_comma_separated(self):
        """Multi-select should parse comma-separated numbers."""
        question = _make_question("Select features?", "Features", multi_select=True)

        with (
            patch("π.support.permissions.asyncio.to_thread", return_value="1, 2"),
            patch("π.support.permissions.console"),
            patch("π.support.permissions.speak"),
            patch("π.support.permissions.get_current_status", return_value=None),
        ):
            result = await can_use_tool(
                tool_name="AskUserQuestion",
                tool_input={"questions": [question]},
                context=MagicMock(),
            )

        answers = result.updated_input["answers"]
        assert answers["Select features?"] == "Option A, Option B"

    @pytest.mark.asyncio
    async def test_other_option_prompts_custom_input(self):
        """Selecting 'Other' should prompt for custom text."""
        question = _make_question("Pick one?", "Choice")

        with (
            patch("π.support.permissions.asyncio.to_thread") as mock_thread,
            patch("π.support.permissions.console"),
            patch("π.support.permissions.speak"),
            patch("π.support.permissions.get_current_status", return_value=None),
        ):
            # First call: select "Other" (option 3), second call: custom text
            mock_thread.side_effect = ["3", "Custom answer"]

            result = await can_use_tool(
                tool_name="AskUserQuestion",
                tool_input={"questions": [question]},
                context=MagicMock(),
            )

        assert result.updated_input["answers"]["Pick one?"] == "Custom answer"

    @pytest.mark.asyncio
    async def test_multiple_questions_all_answered(self):
        """Multiple questions should all be collected."""
        q1 = _make_question("First?", "Q1")
        q2 = _make_question("Second?", "Q2")

        with (
            patch("π.support.permissions.asyncio.to_thread") as mock_thread,
            patch("π.support.permissions.console"),
            patch("π.support.permissions.speak"),
            patch("π.support.permissions.get_current_status", return_value=None),
        ):
            mock_thread.side_effect = ["1", "2"]

            result = await can_use_tool(
                tool_name="AskUserQuestion",
                tool_input={"questions": [q1, q2]},
                context=MagicMock(),
            )

        assert result.updated_input["answers"]["First?"] == "Option A"
        assert result.updated_input["answers"]["Second?"] == "Option B"


class TestAskUserQuestionValidation:
    """Tests for input validation in AskUserQuestion."""

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
                tool_input={"questions": [_make_question("Test?", "Test")]},
                context=MagicMock(),
            )

        assert result.updated_input["answers"]["Test?"] == "[No response provided]"

    @pytest.mark.asyncio
    async def test_timeout_returns_placeholder(self):
        """Timeout should return placeholder response."""
        with (
            patch("π.support.permissions.wait_for") as mock_wait,
            patch("π.support.permissions.console"),
            patch("π.support.permissions.speak"),
            patch("π.support.permissions.get_current_status", return_value=None),
        ):
            mock_wait.side_effect = TimeoutError()

            result = await can_use_tool(
                tool_name="AskUserQuestion",
                tool_input={"questions": [_make_question("Test?", "Test")]},
                context=MagicMock(),
            )

        assert "[No response - timed out]" in result.updated_input["answers"]["Test?"]

    @pytest.mark.asyncio
    async def test_invalid_number_returns_placeholder(self):
        """Invalid number selection should return placeholder."""
        question = _make_question("Pick?", "Pick")

        with (
            patch("π.support.permissions.asyncio.to_thread", return_value="99"),
            patch("π.support.permissions.console"),
            patch("π.support.permissions.speak"),
            patch("π.support.permissions.get_current_status", return_value=None),
        ):
            result = await can_use_tool(
                tool_name="AskUserQuestion",
                tool_input={"questions": [question]},
                context=MagicMock(),
            )

        assert result.updated_input["answers"]["Pick?"] == "[Invalid selection]"
