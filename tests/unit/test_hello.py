"""Tests for hello module."""


class TestHello:
    """Tests for hello functionality."""

    def test_returns_string(self):
        """Should return a string."""
        result = "hello"
        assert isinstance(result, str)
