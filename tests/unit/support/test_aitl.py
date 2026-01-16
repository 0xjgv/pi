"""Tests for π.support.aitl module (Question Answering)."""

import json
import logging
from unittest.mock import MagicMock, patch

import pytest

from π.support import AgentQuestionAnswerer, create_ask_questions_tool
from π.support.aitl import Answer, Question, _normalize_questions


class TestQuestionAnswerModels:
    """Tests for Question and Answer Pydantic models."""

    def test_question_defaults(self):
        """Question should have sensible defaults."""
        q = Question(text="What is X?")
        assert q.text == "What is X?"
        assert q.response_type == "brief"
        assert q.context is None

    def test_question_with_all_fields(self):
        """Question should accept all fields."""
        q = Question(
            text="How does Y work?",
            response_type="detailed",
            context="Looking at auth module",
        )
        assert q.response_type == "detailed"
        assert q.context == "Looking at auth module"

    def test_answer_defaults(self):
        """Answer should have sensible defaults."""
        a = Answer(content="Yes, it exists")
        assert a.content == "Yes, it exists"
        assert a.evidence is None
        assert a.confidence == "MEDIUM"

    def test_answer_with_all_fields(self):
        """Answer should accept all fields."""
        a = Answer(
            content="Found at config.py",
            evidence="π/config.py:42",
            confidence="HIGH",
        )
        assert a.evidence == "π/config.py:42"
        assert a.confidence == "HIGH"


class TestNormalizeQuestions:
    """Tests for question normalization helper."""

    def test_normalize_question_objects(self):
        """Should pass through Question objects unchanged."""
        questions = [Question(text="Q1"), Question(text="Q2")]
        result = _normalize_questions(questions)
        assert result == questions

    def test_normalize_string_list(self):
        """Should convert list[str] to list[Question]."""
        result = _normalize_questions(["Q1", "Q2"])
        assert len(result) == 2
        assert result[0].text == "Q1"
        assert result[0].response_type == "brief"  # default

    def test_normalize_dict_list(self):
        """Should convert list[dict] to list[Question]."""
        result = _normalize_questions([
            {"text": "Q1", "response_type": "detailed"},
            {"text": "Q2"},
        ])
        assert len(result) == 2
        assert result[0].response_type == "detailed"
        assert result[1].response_type == "brief"  # default

    def test_normalize_empty_list(self):
        """Should handle empty list."""
        result = _normalize_questions([])
        assert result == []


class TestJSONParsing:
    """Tests for JSON answer parsing."""

    def test_parse_json_answers_from_code_fence(self):
        """Parser should extract answers from JSON code fence."""
        answerer = AgentQuestionAnswerer()
        result = """Here are my answers:

```json
{
  "answers": [
    {
      "content": "Yes, CI exists",
      "evidence": ".github/workflows/test.yml:1",
      "confidence": "HIGH"
    },
    {"content": "No logo found", "evidence": null, "confidence": "HIGH"}
  ]
}
```
"""
        answers = answerer._parse_json_answers(result, 2)
        assert answers is not None
        assert len(answers) == 2
        assert "Yes, CI exists" in answers[0]
        assert "HIGH" in answers[0]
        assert "No logo found" in answers[1]

    def test_parse_json_answers_pads_missing(self):
        """Parser should pad if JSON has fewer answers than expected."""
        answerer = AgentQuestionAnswerer()
        result = '```json\n{"answers": [{"content": "Only one"}]}\n```'
        answers = answerer._parse_json_answers(result, 3)
        assert len(answers) == 3
        assert "(no answer)" in answers[2]

    def test_parse_json_answers_returns_none_on_invalid(self):
        """Parser should return None for invalid JSON."""
        answerer = AgentQuestionAnswerer()
        result = "This is not JSON at all"
        answers = answerer._parse_json_answers(result, 2)
        assert answers is None


class TestDelimiterParsing:
    """Tests for delimiter-based answer parsing."""

    def test_parse_delimiter_answers(self):
        """Parser should extract answers between delimiters."""
        answerer = AgentQuestionAnswerer()
        result = """
=== ANSWER 1 ===
Yes, the project has CI/CD.
Found at .github/workflows/test.yml

=== ANSWER 2 ===
No logo found in the repository.
"""
        answers = answerer._parse_delimiter_answers(result, 2)
        assert answers is not None
        assert len(answers) == 2
        assert "Yes, the project has CI/CD" in answers[0]
        assert "No logo found" in answers[1]

    def test_parse_delimiter_handles_multiline(self):
        """Parser should capture multi-line content between delimiters."""
        answerer = AgentQuestionAnswerer()
        result = """
=== ANSWER 1 ===
Line 1
Line 2
Line 3
"""
        answers = answerer._parse_delimiter_answers(result, 1)
        assert "Line 1" in answers[0]
        assert "Line 2" in answers[0]
        assert "Line 3" in answers[0]


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

    def test_tool_delegates_to_answerer_with_question_objects(self):
        """Tool should delegate to answerer.ask() with Question objects."""
        mock_answerer = MagicMock()
        mock_answerer.ask.return_value = ["Answer 1", "Answer 2"]

        tool = create_ask_questions_tool(mock_answerer)
        questions = [
            Question(text="What is the scope?"),
            Question(text="What are the constraints?"),
        ]
        result = tool(questions)

        mock_answerer.ask.assert_called_once()
        call_args = mock_answerer.ask.call_args[0][0]
        assert len(call_args) == 2
        assert call_args[0].text == "What is the scope?"
        assert result == ["Answer 1", "Answer 2"]

    def test_tool_normalizes_string_input(self):
        """Tool should normalize list[str] to list[Question]."""
        mock_answerer = MagicMock()
        mock_answerer.ask.return_value = ["answer"]

        tool = create_ask_questions_tool(mock_answerer)
        tool(["Complex question with special chars: @#$%"])

        mock_answerer.ask.assert_called_once()
        call_args = mock_answerer.ask.call_args[0][0]
        assert isinstance(call_args[0], Question)
        assert call_args[0].text == "Complex question with special chars: @#$%"


class TestQuestionAnswererProtocol:
    """Tests for QuestionAnswerer protocol compliance."""

    def test_custom_answerer_works_with_tool(self):
        """Custom answerers implementing protocol should work with tool."""

        class CustomAnswerer:
            def ask(self, questions: list[Question]) -> list[str]:
                return [f"Custom answer to: {q.text}" for q in questions]

        answerer = CustomAnswerer()
        tool = create_ask_questions_tool(answerer)

        result = tool([
            Question(text="Test question 1"),
            Question(text="Test question 2"),
        ])

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
            answerer.ask([Question(text="Question 1"), Question(text="Question 2")])

            mock_exec.return_value = ["Answer 3"]
            answerer.ask([Question(text="Question 3")])

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
        """Parser should handle numbered answer formats (legacy)."""
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
        result = tool([Question(text="test question")])

        assert result == ["context answer"]
        mock_answerer.ask.assert_called_once()

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
        result = tool([Question(text="test question")])

        assert result == ["default answer"]


class TestAITLJSONLogging:
    """Tests for AITL JSON line logging."""

    def test_ask_emits_json_line(self, caplog: pytest.LogCaptureFixture) -> None:
        """ask() emits a JSON line with full Q&A content."""
        answerer = AgentQuestionAnswerer()
        # Long question to verify no truncation
        questions = [
            Question(text="What is X?" * 50),
            Question(text="Where is Y?"),
        ]

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
        # Questions are now dicts with text field
        assert data["questions"][0]["text"] == "What is X?" * 50
        assert data["answers"] == ["Answer 1", "Answer 2"]
        assert data["duration_ms"] >= 0
        assert "batch_id" in data
        assert len(data["batch_id"]) == 8
        assert "timestamp" in data

    def test_json_line_handles_unicode(self, caplog: pytest.LogCaptureFixture) -> None:
        """JSON line handles unicode content correctly."""
        answerer = AgentQuestionAnswerer()
        questions = [Question(text="What is π?"), Question(text="日本語の質問")]

        with patch.object(answerer, "_execute_agent") as mock_exec:
            mock_exec.return_value = ["Pi is a constant", "Japanese answer"]
            with caplog.at_level(logging.INFO, logger="π.support.aitl"):
                answerer.ask(questions)

        json_lines = [r for r in caplog.records if "AITL_JSON:" in r.message]
        json_str = json_lines[0].message.split("AITL_JSON: ", 1)[1]
        data = json.loads(json_str)

        assert "π" in data["questions"][0]["text"]
        assert "日本語" in data["questions"][1]["text"]

    def test_json_line_no_truncation(self, caplog: pytest.LogCaptureFixture) -> None:
        """JSON line contains full untruncated Q&A content."""
        answerer = AgentQuestionAnswerer()
        # Create content longer than old truncation limits
        long_question = "Q" * 200
        long_answer = "A" * 400

        with patch.object(answerer, "_execute_agent") as mock_exec:
            mock_exec.return_value = [long_answer]
            with caplog.at_level(logging.INFO, logger="π.support.aitl"):
                answerer.ask([Question(text=long_question)])

        json_lines = [r for r in caplog.records if "AITL_JSON:" in r.message]
        json_str = json_lines[0].message.split("AITL_JSON: ", 1)[1]
        data = json.loads(json_str)

        # Verify no truncation occurred
        assert data["questions"][0]["text"] == long_question
        assert len(data["questions"][0]["text"]) == 200
        assert data["answers"][0] == long_answer
        assert len(data["answers"][0]) == 400
