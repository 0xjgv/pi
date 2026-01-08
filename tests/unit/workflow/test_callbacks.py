"""Tests for DSPy logging callbacks."""

from π.workflow.callbacks import LoggingCallback, _truncate


class TestTruncate:
    def test_short_text_unchanged(self):
        assert _truncate("short") == "short"

    def test_long_text_truncated(self):
        long_text = "x" * 3000
        result = _truncate(long_text)
        assert len(result) == 2003  # 2000 + "..."
        assert result.endswith("...")

    def test_exact_limit_unchanged(self):
        text = "x" * 2000
        assert _truncate(text) == text


class TestLoggingCallback:
    def test_on_lm_start_with_messages(self, caplog):
        callback = LoggingCallback()
        inputs = {"messages": [{"role": "user", "content": "test prompt"}]}

        with caplog.at_level("DEBUG"):
            callback.on_lm_start(call_id="call-1", instance=None, inputs=inputs)

        assert "LM prompt: test prompt" in caplog.text

    def test_on_lm_start_with_prompt(self, caplog):
        callback = LoggingCallback()
        inputs = {"prompt": "direct prompt text"}

        with caplog.at_level("DEBUG"):
            callback.on_lm_start(call_id="call-1", instance=None, inputs=inputs)

        assert "LM prompt: direct prompt text" in caplog.text

    def test_on_lm_start_fallback(self, caplog):
        callback = LoggingCallback()
        inputs = {"other": "data"}

        with caplog.at_level("DEBUG"):
            callback.on_lm_start(call_id="call-1", instance=None, inputs=inputs)

        assert "LM inputs:" in caplog.text

    def test_on_lm_end_logs_response(self, caplog):
        callback = LoggingCallback()
        outputs = {"response": "test response"}

        with caplog.at_level("DEBUG"):
            callback.on_lm_end(call_id="call-1", outputs=outputs, exception=None)

        assert "LM response:" in caplog.text

    def test_on_lm_end_logs_exception(self, caplog):
        callback = LoggingCallback()
        err = ValueError("test error")

        with caplog.at_level("WARNING"):
            callback.on_lm_end(call_id="call-1", outputs={}, exception=err)

        assert "LM error: test error" in caplog.text

    def test_on_lm_end_empty_outputs(self, caplog):
        callback = LoggingCallback()

        with caplog.at_level("DEBUG"):
            callback.on_lm_end(call_id="call-1", outputs={}, exception=None)

        # Empty outputs should not log
        assert "LM response:" not in caplog.text

    def test_on_tool_start(self, caplog):
        callback = LoggingCallback()

        class MockTool:
            name = "test_tool"

        with caplog.at_level("DEBUG"):
            callback.on_tool_start(
                call_id="call-1", instance=MockTool(), inputs={"arg": "value"}
            )

        assert "DSPy tool start: test_tool" in caplog.text
        assert "arg" in caplog.text

    def test_on_tool_end(self, caplog):
        callback = LoggingCallback()

        with caplog.at_level("DEBUG"):
            callback.on_tool_end(
                call_id="call-1", outputs={"result": "done"}, exception=None
            )

        assert "DSPy tool end:" in caplog.text

    def test_on_tool_end_with_error(self, caplog):
        callback = LoggingCallback()
        err = RuntimeError("tool failed")

        with caplog.at_level("WARNING"):
            callback.on_tool_end(call_id="call-1", outputs={}, exception=err)

        assert "DSPy tool error: tool failed" in caplog.text
