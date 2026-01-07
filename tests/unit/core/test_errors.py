"""Tests for π.errors module."""

import pytest

from π.core import AgentExecutionError


class TestAgentExecutionError:
    """Tests for AgentExecutionError exception."""

    def test_inherits_from_exception(self):
        """Should be a subclass of Exception."""
        assert issubclass(AgentExecutionError, Exception)

    def test_can_be_raised_and_caught(self):
        """Should be raisable and catchable."""
        with pytest.raises(AgentExecutionError) as exc_info:
            raise AgentExecutionError("Test error message")

        assert "Test error message" in str(exc_info.value)

    def test_can_wrap_other_exceptions(self):
        """Should support exception chaining."""
        original = ValueError("Original error")

        with pytest.raises(AgentExecutionError) as exc_info:
            raise AgentExecutionError("Wrapped") from original

        assert exc_info.value.__cause__ is original
