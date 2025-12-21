"""Tests for π.hitl module (Human-in-the-Loop)."""

from unittest.mock import MagicMock, patch

import pytest

from π.hitl import ConsoleInputProvider, create_ask_human_tool


class TestConsoleInputProvider:
    """Tests for ConsoleInputProvider."""

    def test_creates_with_default_console(self):
        """Should create with default Rich console."""
        provider = ConsoleInputProvider()

        assert provider.console is not None

    def test_accepts_custom_console(self):
        """Should accept custom console instance."""
        mock_console = MagicMock()

        provider = ConsoleInputProvider(console=mock_console)

        assert provider.console is mock_console

    def test_ask_displays_question(self):
        """Should display the question to console."""
        mock_console = MagicMock()
        provider = ConsoleInputProvider(console=mock_console)

        with patch("π.hitl.Prompt.ask", return_value="user response"):
            provider.ask("What is your goal?")

        # Verify console.print was called with the question
        print_calls = mock_console.print.call_args_list
        assert any("What is your goal?" in str(call) for call in print_calls)

    def test_ask_returns_user_response(self):
        """Should return the user's response."""
        provider = ConsoleInputProvider(console=MagicMock())

        with patch("π.hitl.Prompt.ask", return_value="Add authentication"):
            result = provider.ask("What feature do you want?")

        assert result == "Add authentication"

    def test_ask_uses_rich_prompt(self):
        """Should use Rich Prompt for input."""
        provider = ConsoleInputProvider(console=MagicMock())

        with patch("π.hitl.Prompt.ask") as mock_ask:
            mock_ask.return_value = "response"
            provider.ask("Question?")

        mock_ask.assert_called_once()


class TestCreateAskHumanTool:
    """Tests for create_ask_human_tool factory."""

    def test_returns_callable(self):
        """Should return a callable function."""
        mock_provider = MagicMock()

        tool = create_ask_human_tool(mock_provider)

        assert callable(tool)

    def test_tool_has_name(self):
        """Tool should have a name for DSPy."""
        mock_provider = MagicMock()

        tool = create_ask_human_tool(mock_provider)

        assert tool.__name__ == "ask_human"

    def test_tool_has_docstring(self):
        """Tool should have docstring for DSPy tool description."""
        mock_provider = MagicMock()

        tool = create_ask_human_tool(mock_provider)

        assert tool.__doc__ is not None
        assert "human" in tool.__doc__.lower() or "clarif" in tool.__doc__.lower()

    def test_tool_delegates_to_provider(self):
        """Tool should delegate to provider.ask()."""
        mock_provider = MagicMock()
        mock_provider.ask.return_value = "Human response"

        tool = create_ask_human_tool(mock_provider)
        result = tool("What is the scope?")

        mock_provider.ask.assert_called_once_with("What is the scope?")
        assert result == "Human response"

    def test_tool_passes_question_to_provider(self):
        """Tool should pass question unchanged to provider."""
        mock_provider = MagicMock()
        mock_provider.ask.return_value = "answer"

        tool = create_ask_human_tool(mock_provider)
        tool("Complex question with special chars: @#$%")

        mock_provider.ask.assert_called_with("Complex question with special chars: @#$%")


class TestHumanInputProviderProtocol:
    """Tests for HumanInputProvider protocol compliance."""

    def test_console_provider_implements_protocol(self):
        """ConsoleInputProvider should implement HumanInputProvider protocol."""
        from π.hitl import HumanInputProvider

        provider = ConsoleInputProvider(console=MagicMock())

        # Protocol check - has ask method with correct signature
        assert hasattr(provider, "ask")
        assert callable(provider.ask)

    def test_mock_provider_works_with_factory(self):
        """Any object with ask() method should work."""

        class CustomProvider:
            def ask(self, question: str) -> str:
                return f"Custom answer to: {question}"

        provider = CustomProvider()
        tool = create_ask_human_tool(provider)

        result = tool("Test question")

        assert result == "Custom answer to: Test question"
