"""Tests for π.support.hitl module (Question Answering)."""

import json
import logging
from unittest.mock import MagicMock, patch

import pytest

from π.support import AgentQuestionAnswerer, create_ask_questions_tool


class TestCreateAskQuestionsTool:
    """Tests for create_ask_questions_tool factory."""

    def test_returns_callable(self):
        """Should return a callable function."""
        mock_answerer = MagicMock()

        tool = create_ask_questions_tool(mock_answerer)

        assert callable(tool)

    def test_tool_has_name(self):
        """Tool should have a name for DSPy."""
        mock_answerer = MagicMock()

        tool = create_ask_questions_tool(mock_answerer)

        assert tool.__name__ == "ask_questions"

    def test_tool_has_docstring(self):
        """Tool should have docstring for DSPy tool description."""
        mock_answerer = MagicMock()

        tool = create_ask_questions_tool(mock_answerer)

        assert tool.__doc__ is not None
        assert "question" in tool.__doc__.lower()

    def test_tool_delegates_to_answerer(self):
        """Tool should delegate to answerer.ask()."""
        mock_answerer = MagicMock()
        mock_answerer.ask.return_value = ["Answer 1", "Answer 2"]

        tool = create_ask_questions_tool(mock_answerer)
        result = tool(["What is the scope?", "What are the constraints?"])

        mock_answerer.ask.assert_called_once_with([
            "What is the scope?",
            "What are the constraints?",
        ])
        assert result == ["Answer 1", "Answer 2"]

    def test_tool_passes_questions_to_answerer(self):
        """Tool should pass questions unchanged to answerer."""
        mock_answerer = MagicMock()
        mock_answerer.ask.return_value = ["answer"]

        tool = create_ask_questions_tool(mock_answerer)
        tool(["Complex question with special chars: @#$%"])

        mock_answerer.ask.assert_called_with([
            "Complex question with special chars: @#$%"
        ])


class TestQuestionAnswererProtocol:
    """Tests for QuestionAnswerer protocol compliance."""

    def test_custom_answerer_works_with_tool(self):
        """Custom answerers implementing protocol should work with tool."""

        class CustomAnswerer:
            def ask(self, questions: list[str]) -> list[str]:
                return [f"Custom answer to: {q}" for q in questions]

        answerer = CustomAnswerer()
        tool = create_ask_questions_tool(answerer)

        result = tool(["Test question 1", "Test question 2"])

        assert result == [
            "Custom answer to: Test question 1",
            "Custom answer to: Test question 2",
        ]


class TestAgentQuestionAnswerer:
    """Tests for AgentQuestionAnswerer."""

    def test_answer_log_tracking(self):
        """AgentQuestionAnswerer should track question/answer batches."""
        answerer = AgentQuestionAnswerer()

        with patch.object(answerer, "_execute_agent") as mock_exec:
            mock_exec.return_value = ["Answer 1", "Answer 2"]
            answerer.ask(["Question 1", "Question 2"])

            mock_exec.return_value = ["Answer 3"]
            answerer.ask(["Question 3"])

        assert len(answerer.answers) == 2
        expected_first = (["Question 1", "Question 2"], ["Answer 1", "Answer 2"])
        assert answerer.answers[0] == expected_first
        assert answerer.answers[1] == (["Question 3"], ["Answer 3"])

    def test_uses_read_only_tools(self):
        """Agent options should only include read-only tools."""
        answerer = AgentQuestionAnswerer()
        options = answerer._get_agent_options()

        assert "Read" in options.allowed_tools
        assert "Glob" in options.allowed_tools
        assert "Grep" in options.allowed_tools

    def test_parse_answers_handles_numbered_format(self):
        """Parser should handle numbered answer formats."""
        answerer = AgentQuestionAnswerer()

        # Test dot-separated numbering
        result = answerer._parse_answers("1. First\n2. Second", 2)
        assert result == ["First", "Second"]

        # Test parenthesis-separated numbering
        result = answerer._parse_answers("1) First\n2) Second", 2)
        assert result == ["First", "Second"]

    def test_parse_answers_pads_missing(self):
        """Parser should pad if fewer answers than expected."""
        answerer = AgentQuestionAnswerer()

        result = answerer._parse_answers("1. Only one", 3)
        assert len(result) == 3
        assert result[0] == "Only one"
        assert result[1] == "(no answer)"
        assert result[2] == "(no answer)"

    def test_parse_answers_truncates_extra(self):
        """Parser should truncate if more answers than expected."""
        answerer = AgentQuestionAnswerer()

        result = answerer._parse_answers("1. One\n2. Two\n3. Three", 2)
        assert len(result) == 2
        assert result == ["One", "Two"]


class TestLazyAnswererResolution:
    """Tests for lazy answerer resolution in ask_questions."""

    def test_uses_context_answerer_when_set(self):
        """Tool should use answerer from context when available."""
        from π.workflow.context import get_ctx

        mock_answerer = MagicMock()
        mock_answerer.ask.return_value = ["context answer"]

        ctx = get_ctx()
        ctx.input_provider = mock_answerer

        tool = create_ask_questions_tool()
        result = tool(["test question"])

        assert result == ["context answer"]
        mock_answerer.ask.assert_called_once_with(["test question"])

        # Clean up
        ctx.input_provider = None

    def test_falls_back_to_default_answerer(self):
        """Tool should fall back to default when context has no answerer."""
        from π.workflow.context import get_ctx

        mock_default = MagicMock()
        mock_default.ask.return_value = ["default answer"]

        ctx = get_ctx()
        ctx.input_provider = None

        tool = create_ask_questions_tool(default_answerer=mock_default)
        result = tool(["test question"])

        assert result == ["default answer"]


class TestAITLJSONLogging:
    """Tests for AITL JSON line logging."""

    def test_ask_emits_json_line(self, caplog: pytest.LogCaptureFixture) -> None:
        """ask() emits a JSON line with full Q&A content."""
        answerer = AgentQuestionAnswerer()
        # Long question to verify no truncation
        questions = ["What is X?" * 50, "Where is Y?"]

        with patch.object(answerer, "_execute_agent") as mock_exec:
            mock_exec.return_value = ["Answer 1", "Answer 2"]
            with caplog.at_level(logging.INFO, logger="π.support.aitl"):
                answerer.ask(questions)

        # Find the JSON line
        json_lines = [r for r in caplog.records if "AITL_JSON:" in r.message]
        assert len(json_lines) == 1

        # Parse and validate
        json_str = json_lines[0].message.split("AITL_JSON: ", 1)[1]
        data = json.loads(json_str)

        assert data["count"] == 2
        assert data["questions"] == questions  # Full, untruncated
        assert data["answers"] == ["Answer 1", "Answer 2"]
        assert data["duration_ms"] >= 0
        assert "batch_id" in data
        assert len(data["batch_id"]) == 8
        assert "timestamp" in data

    def test_json_line_handles_unicode(self, caplog: pytest.LogCaptureFixture) -> None:
        """JSON line handles unicode content correctly."""
        answerer = AgentQuestionAnswerer()
        questions = ["What is π?", "日本語の質問"]

        with patch.object(answerer, "_execute_agent") as mock_exec:
            mock_exec.return_value = ["Pi is a constant", "Japanese answer"]
            with caplog.at_level(logging.INFO, logger="π.support.aitl"):
                answerer.ask(questions)

        json_lines = [r for r in caplog.records if "AITL_JSON:" in r.message]
        json_str = json_lines[0].message.split("AITL_JSON: ", 1)[1]
        data = json.loads(json_str)

        assert "π" in data["questions"][0]
        assert "日本語" in data["questions"][1]

    def test_json_line_no_truncation(self, caplog: pytest.LogCaptureFixture) -> None:
        """JSON line contains full untruncated Q&A content."""
        answerer = AgentQuestionAnswerer()
        # Create content longer than old truncation limits (100 chars Q, 200 chars A)
        long_question = "Q" * 200
        long_answer = "A" * 400

        with patch.object(answerer, "_execute_agent") as mock_exec:
            mock_exec.return_value = [long_answer]
            with caplog.at_level(logging.INFO, logger="π.support.aitl"):
                answerer.ask([long_question])

        json_lines = [r for r in caplog.records if "AITL_JSON:" in r.message]
        json_str = json_lines[0].message.split("AITL_JSON: ", 1)[1]
        data = json.loads(json_str)

        # Verify no truncation occurred
        assert data["questions"][0] == long_question
        assert len(data["questions"][0]) == 200
        assert data["answers"][0] == long_answer
        assert len(data["answers"][0]) == 400
