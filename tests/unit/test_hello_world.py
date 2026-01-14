"""Tests for hello_world function."""

from π.hello_world import hello_world


class TestHelloWorld:
    """Tests for hello_world function."""

    def test_returns_string(self):
        """Should return a string type."""
        result = hello_world()
        assert isinstance(result, str)

    def test_returns_expected_greeting(self):
        """Should return 'Hello, World!' exactly."""
        result = hello_world()
        assert result == "Hello, World!"

    def test_greeting_not_empty(self):
        """Should return a non-empty string."""
        result = hello_world()
        assert len(result) > 0

    def test_contains_hello(self):
        """Should contain the word 'Hello'."""
        result = hello_world()
        assert "Hello" in result

    def test_contains_world(self):
        """Should contain the word 'World'."""
        result = hello_world()
        assert "World" in result


class TestHelloWorldEdgeCases:
    """Edge case tests for hello_world function."""

    def test_idempotent_calls(self):
        """Multiple calls should return identical results."""
        first = hello_world()
        second = hello_world()
        assert first == second

    def test_never_returns_none(self):
        """Should never return None."""
        result = hello_world()
        assert result is not None
