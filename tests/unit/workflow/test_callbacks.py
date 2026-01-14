"""Tests for ReActLoggingCallback LM logging methods."""

import logging
import time
from unittest.mock import Mock

import pytest

from π.workflow.callbacks import ReActLoggingCallback


class TestLMLogging:
    """Tests for on_lm_start and on_lm_end callbacks."""

    def test_on_lm_start_logs_model(self, caplog: pytest.LogCaptureFixture) -> None:
        """on_lm_start logs model name at DEBUG level."""
        callback = ReActLoggingCallback()
        mock_instance = Mock()
        mock_instance.model = "claude-sonnet-4-5"

        with caplog.at_level(logging.DEBUG, logger="π.workflow.callbacks"):
            callback.on_lm_start(
                call_id="test-123",
                instance=mock_instance,
                inputs={"messages": [{"role": "user", "content": "hello"}]},
            )

        assert "LM CALL START [test-123]" in caplog.text
        assert "claude-sonnet-4-5" in caplog.text

    def test_on_lm_start_fallback_model_name(
        self, caplog: pytest.LogCaptureFixture
    ) -> None:
        """on_lm_start falls back to model_name when model attr missing."""
        callback = ReActLoggingCallback()

        # Test model_name fallback
        mock_instance = Mock(spec=[])
        mock_instance.model_name = "fallback-model"

        with caplog.at_level(logging.DEBUG, logger="π.workflow.callbacks"):
            callback.on_lm_start(
                call_id="test-fallback",
                instance=mock_instance,
                inputs={"messages": []},
            )

        assert "fallback-model" in caplog.text

    def test_on_lm_start_unknown_model(self, caplog: pytest.LogCaptureFixture) -> None:
        """on_lm_start logs 'unknown' when no model attribute exists."""
        callback = ReActLoggingCallback()

        # No model attributes at all
        mock_instance = Mock(spec=[])

        with caplog.at_level(logging.DEBUG, logger="π.workflow.callbacks"):
            callback.on_lm_start(
                call_id="test-unknown",
                instance=mock_instance,
                inputs={"messages": []},
            )

        assert "unknown" in caplog.text

    def test_on_lm_end_logs_latency_and_tokens(
        self, caplog: pytest.LogCaptureFixture
    ) -> None:
        """on_lm_end logs latency and token usage."""
        callback = ReActLoggingCallback()
        callback._lm_start_times["test-456"] = time.perf_counter() - 0.5  # 500ms ago

        with caplog.at_level(logging.DEBUG, logger="π.workflow.callbacks"):
            callback.on_lm_end(
                call_id="test-456",
                outputs={
                    "usage": {
                        "prompt_tokens": 100,
                        "completion_tokens": 50,
                        "cache_read_input_tokens": 30,
                    },
                    "response": "test response",
                },
                exception=None,
            )

        assert "LM COMPLETE [test-456]" in caplog.text
        assert "latency=" in caplog.text
        assert "in=100" in caplog.text
        assert "out=50" in caplog.text

    def test_on_lm_end_usage_fallback_from_response(
        self, caplog: pytest.LogCaptureFixture
    ) -> None:
        """on_lm_end extracts usage from response.usage when top-level missing."""
        callback = ReActLoggingCallback()
        callback._lm_start_times["test-nested"] = time.perf_counter()

        with caplog.at_level(logging.DEBUG, logger="π.workflow.callbacks"):
            callback.on_lm_end(
                call_id="test-nested",
                outputs={
                    "response": {
                        "usage": {"prompt_tokens": 200, "completion_tokens": 100},
                    },
                },
                exception=None,
            )

        assert "in=200" in caplog.text
        assert "out=100" in caplog.text

    def test_on_lm_end_no_usage_data(self, caplog: pytest.LogCaptureFixture) -> None:
        """on_lm_end handles missing usage data gracefully."""
        callback = ReActLoggingCallback()
        callback._lm_start_times["test-no-usage"] = time.perf_counter()

        with caplog.at_level(logging.DEBUG, logger="π.workflow.callbacks"):
            callback.on_lm_end(
                call_id="test-no-usage",
                outputs={"response": "some text"},
                exception=None,
            )

        assert "tokens=unavailable" in caplog.text

    def test_on_lm_end_no_outputs(self, caplog: pytest.LogCaptureFixture) -> None:
        """on_lm_end handles None outputs gracefully."""
        callback = ReActLoggingCallback()
        callback._lm_start_times["test-no-out"] = time.perf_counter()

        with caplog.at_level(logging.DEBUG, logger="π.workflow.callbacks"):
            callback.on_lm_end(
                call_id="test-no-out",
                outputs=None,
                exception=None,
            )

        assert "LM CALL END [test-no-]" in caplog.text
        assert "no outputs" in caplog.text

    def test_on_lm_end_logs_exception(self, caplog: pytest.LogCaptureFixture) -> None:
        """on_lm_end logs errors at ERROR level."""
        callback = ReActLoggingCallback()
        callback._lm_start_times["test-789"] = time.perf_counter()

        with caplog.at_level(logging.DEBUG, logger="π.workflow.callbacks"):
            callback.on_lm_end(
                call_id="test-789",
                outputs=None,
                exception=ValueError("API error"),
            )

        assert "LM CALL FAILED [test-789]" in caplog.text
        assert "API error" in caplog.text

    def test_on_lm_start_verbose_mode(
        self, caplog: pytest.LogCaptureFixture, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """on_lm_start logs full prompt when PI_LM_DEBUG=1."""
        # Function-based check means we can just set the env var
        monkeypatch.setenv("PI_LM_DEBUG", "1")

        callback = ReActLoggingCallback()
        mock_instance = Mock()
        mock_instance.model = "test-model"

        with caplog.at_level(logging.DEBUG, logger="π.workflow.callbacks"):
            callback.on_lm_start(
                call_id="verbose-test",
                instance=mock_instance,
                inputs={"messages": [{"role": "user", "content": "test prompt"}]},
            )

        assert "LM PROMPT [verbose-]" in caplog.text
        assert "test prompt" in caplog.text

    def test_on_lm_end_verbose_mode(
        self, caplog: pytest.LogCaptureFixture, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """on_lm_end logs full response when PI_LM_DEBUG=1."""
        monkeypatch.setenv("PI_LM_DEBUG", "1")

        callback = ReActLoggingCallback()
        callback._lm_start_times["verbose-resp"] = time.perf_counter()

        with caplog.at_level(logging.DEBUG, logger="π.workflow.callbacks"):
            callback.on_lm_end(
                call_id="verbose-resp",
                outputs={"response": "detailed response content"},
                exception=None,
            )

        assert "LM RESPONSE [verbose-]" in caplog.text
        assert "detailed response content" in caplog.text

    def test_verbose_mode_disabled_by_default(
        self, caplog: pytest.LogCaptureFixture, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """on_lm_start does not log prompt when PI_LM_DEBUG not set."""
        monkeypatch.delenv("PI_LM_DEBUG", raising=False)

        callback = ReActLoggingCallback()
        mock_instance = Mock()
        mock_instance.model = "test-model"

        with caplog.at_level(logging.DEBUG, logger="π.workflow.callbacks"):
            callback.on_lm_start(
                call_id="no-verbose",
                instance=mock_instance,
                inputs={"messages": [{"role": "user", "content": "secret prompt"}]},
            )

        assert "LM PROMPT" not in caplog.text
        assert "secret prompt" not in caplog.text


class TestStageDetection:
    """Tests for stage detection methods."""

    def test_is_final_output_with_stage_research(self) -> None:
        """Detects research stage from stage field."""
        callback = ReActLoggingCallback()
        assert callback._is_final_output({"stage": "research", "other": "value"})

    def test_is_final_output_with_stage_design(self) -> None:
        """Detects design stage from stage field."""
        callback = ReActLoggingCallback()
        assert callback._is_final_output({"stage": "design"})

    def test_is_final_output_with_stage_execute(self) -> None:
        """Detects execute stage from stage field."""
        callback = ReActLoggingCallback()
        assert callback._is_final_output({"stage": "execute"})

    def test_is_final_output_with_trajectory(self) -> None:
        """Detects final output from trajectory key (backwards compat)."""
        callback = ReActLoggingCallback()
        assert callback._is_final_output({"trajectory": {"thought_1": "..."}})

    def test_is_final_output_rejects_intermediate(self) -> None:
        """Does not detect intermediate outputs as final."""
        callback = ReActLoggingCallback()
        assert not callback._is_final_output({"next_thought": "reasoning"})
        assert not callback._is_final_output({"next_tool_name": "Read"})
        assert not callback._is_final_output({"unknown_key": "value"})

    def test_is_thought_output(self) -> None:
        """Detects thought outputs correctly."""
        callback = ReActLoggingCallback()
        assert callback._is_thought_output({"Thought_1": "reasoning"})
        assert callback._is_thought_output({"next_thought": "more reasoning"})
        assert not callback._is_thought_output({"stage": "research"})

    def test_is_action_output(self) -> None:
        """Detects action outputs correctly."""
        callback = ReActLoggingCallback()
        assert callback._is_action_output({"next_tool_name": "Read"})
        assert callback._is_action_output({"next_tool_args": {}})
        assert callback._is_action_output({"tool_name": "Write"})
        assert not callback._is_action_output({"stage": "research"})
