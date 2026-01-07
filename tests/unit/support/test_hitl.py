"""Tests for π.hitl module (Human-in-the-Loop)."""

from unittest.mock import MagicMock, patch

from π.support import ConsoleInputProvider, create_ask_user_question_tool


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

        with patch("π.support.hitl.Prompt.ask", return_value="user response"):
            provider.ask("What is your goal?")

        # Verify console.print was called with the question
        print_calls = mock_console.print.call_args_list
        assert any("What is your goal?" in str(call) for call in print_calls)

    def test_ask_returns_user_response(self):
        """Should return the user's response."""
        provider = ConsoleInputProvider(console=MagicMock())

        with patch("π.support.hitl.Prompt.ask", return_value="Add authentication"):
            result = provider.ask("What feature do you want?")

        assert result == "Add authentication"

    def test_ask_uses_rich_prompt(self):
        """Should use Rich Prompt for input."""
        provider = ConsoleInputProvider(console=MagicMock())

        with patch("π.support.hitl.Prompt.ask") as mock_ask:
            mock_ask.return_value = "response"
            provider.ask("Question?")

        mock_ask.assert_called_once()


class TestCreateAskUserQuestionTool:
    """Tests for create_ask_user_question_tool factory."""

    def test_returns_callable(self):
        """Should return a callable function."""
        mock_provider = MagicMock()

        tool = create_ask_user_question_tool(mock_provider)

        assert callable(tool)

    def test_tool_has_name(self):
        """Tool should have a name for DSPy."""
        mock_provider = MagicMock()

        tool = create_ask_user_question_tool(mock_provider)

        assert tool.__name__ == "ask_user_question"

    def test_tool_has_docstring(self):
        """Tool should have docstring for DSPy tool description."""
        mock_provider = MagicMock()

        tool = create_ask_user_question_tool(mock_provider)

        assert tool.__doc__ is not None
        assert "user" in tool.__doc__.lower() or "clarif" in tool.__doc__.lower()

    def test_tool_delegates_to_provider(self):
        """Tool should delegate to provider.ask()."""
        mock_provider = MagicMock()
        mock_provider.ask.return_value = "Human response"

        tool = create_ask_user_question_tool(mock_provider)
        result = tool("What is the scope?")

        mock_provider.ask.assert_called_once_with("What is the scope?")
        assert result == "Human response"

    def test_tool_passes_question_to_provider(self):
        """Tool should pass question unchanged to provider."""
        mock_provider = MagicMock()
        mock_provider.ask.return_value = "answer"

        tool = create_ask_user_question_tool(mock_provider)
        tool("Complex question with special chars: @#$%")

        mock_provider.ask.assert_called_with(
            "Complex question with special chars: @#$%"
        )


class TestHumanInputProviderProtocol:
    """Tests for HumanInputProvider protocol compliance."""

    def test_console_provider_implements_protocol(self):
        """ConsoleInputProvider should implement HumanInputProvider protocol."""
        provider = ConsoleInputProvider(console=MagicMock())

        # Protocol check - has ask method with correct signature
        assert hasattr(provider, "ask")
        assert callable(provider.ask)

        class CustomProvider:
            def ask(self, question: str) -> str:
                return f"Custom answer to: {question}"

        provider = CustomProvider()
        tool = create_ask_user_question_tool(provider)

        result = tool("Test question")

        assert result == "Custom answer to: Test question"


class TestConsoleInputProviderValidation:
    """Tests for ConsoleInputProvider validation (Phase 2 additions)."""

    def test_retries_on_empty_response(self):
        """Should retry when empty response and allow_empty=False."""
        mock_console = MagicMock()
        provider = ConsoleInputProvider(console=mock_console, allow_empty=False)

        with patch("π.support.hitl.Prompt.ask") as mock_ask:
            # First call empty, second call valid
            mock_ask.side_effect = ["", "valid response"]
            result = provider.ask("Question?")

        assert result == "valid response"
        assert mock_ask.call_count == 2

    def test_max_retries_returns_placeholder(self):
        """Should return placeholder after max retries."""
        mock_console = MagicMock()
        provider = ConsoleInputProvider(
            console=mock_console, allow_empty=False, max_retries=2
        )

        with patch("π.support.hitl.Prompt.ask", return_value=""):
            result = provider.ask("Question?")

        assert "[No response after retries]" in result

    def test_allow_empty_accepts_empty(self):
        """Should accept empty when allow_empty=True."""
        mock_console = MagicMock()
        provider = ConsoleInputProvider(console=mock_console, allow_empty=True)

        with patch("π.support.hitl.Prompt.ask", return_value=""):
            result = provider.ask("Question?")

        assert result == ""


class TestAgentInputProvider:
    """Tests for AgentInputProvider."""

    def test_ask_reads_context(self):
        """AgentInputProvider should read objective from context."""
        from π.support.hitl import AgentInputProvider
        from π.workflow.context import get_ctx

        # Setup context
        ctx = get_ctx()
        ctx.objective = "Test objective"
        ctx.current_stage = "research"

        mock_lm = MagicMock()

        with patch("dspy.Predict") as mock_predict:
            mock_predict.return_value.return_value.answer = "Test answer"
            provider = AgentInputProvider(lm=mock_lm)
            answer = provider.ask("What should I do?")

        assert answer == "Test answer"
        # Verify context was passed to the LM
        call_kwargs = mock_predict.return_value.call_args.kwargs
        assert "Test objective" in call_kwargs["context"]

    def test_answer_log_tracking(self):
        """AgentInputProvider should track question/answer pairs."""
        from π.support.hitl import AgentInputProvider

        mock_lm = MagicMock()

        with patch("dspy.Predict") as mock_predict:
            mock_predict.return_value.return_value.answer = "Answer 1"
            provider = AgentInputProvider(lm=mock_lm)
            provider.ask("Question 1")

            mock_predict.return_value.return_value.answer = "Answer 2"
            provider.ask("Question 2")

        assert len(provider.answers) == 2
        assert provider.answers[0] == ("Question 1", "Answer 1")
        assert provider.answers[1] == ("Question 2", "Answer 2")


class TestLazyProviderResolution:
    """Tests for lazy provider resolution in ask_user_question."""

    def test_uses_context_provider_when_set(self):
        """Tool should use provider from context when available."""
        from π.workflow.context import get_ctx

        mock_provider = MagicMock()
        mock_provider.ask.return_value = "context answer"

        ctx = get_ctx()
        ctx.input_provider = mock_provider

        tool = create_ask_user_question_tool()
        result = tool("test question")

        assert result == "context answer"
        mock_provider.ask.assert_called_once_with("test question")

        # Clean up
        ctx.input_provider = None

    def test_falls_back_to_default_provider(self):
        """Tool should fall back to default when context has no provider."""
        from π.workflow.context import get_ctx

        mock_default = MagicMock()
        mock_default.ask.return_value = "default answer"

        ctx = get_ctx()
        ctx.input_provider = None

        tool = create_ask_user_question_tool(default_provider=mock_default)
        result = tool("test question")

        assert result == "default answer"
