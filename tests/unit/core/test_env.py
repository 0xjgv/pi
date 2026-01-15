"""Tests for environment validation module."""

from π.core.env import validate_required_env


class TestValidateRequiredEnv:
    """Tests for validate_required_env function."""

    def test_passes_without_env_vars(self) -> None:
        """No error when no env vars are set (ClaudeCodeLM uses SDK auth)."""
        validate_required_env()  # Should not raise
