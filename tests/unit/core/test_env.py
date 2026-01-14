"""Tests for environment validation module."""

from __future__ import annotations

from unittest.mock import patch

import pytest

from π.core.env import validate_required_env


class TestValidateRequiredEnv:
    """Tests for validate_required_env function."""

    @patch.dict("os.environ", {"CLIPROXY_API_KEY": "test-key"}, clear=True)
    def test_passes_when_required_vars_present(self) -> None:
        """No error when CLIPROXY_API_KEY is set."""
        # Should not raise or exit
        validate_required_env()

    @patch.dict("os.environ", {}, clear=True)
    def test_exits_when_api_key_missing(self) -> None:
        """Exits with code 1 when CLIPROXY_API_KEY is missing."""
        with pytest.raises(SystemExit) as exc_info:
            validate_required_env()
        assert exc_info.value.code == 1

    @patch.dict("os.environ", {"CLIPROXY_API_KEY": ""}, clear=True)
    def test_exits_when_api_key_empty(self) -> None:
        """Exits with code 1 when CLIPROXY_API_KEY is empty string."""
        with pytest.raises(SystemExit) as exc_info:
            validate_required_env()
        assert exc_info.value.code == 1

    @patch.dict(
        "os.environ",
        {"CLIPROXY_API_KEY": "test-key", "CLIPROXY_API_BASE": "http://example.com"},
        clear=True,
    )
    def test_optional_vars_not_required(self) -> None:
        """Optional vars like CLIPROXY_API_BASE don't affect validation."""
        # Should not raise
        validate_required_env()

    @patch.dict("os.environ", {"CLIPROXY_API_KEY": "test-key"}, clear=True)
    def test_mem0_api_key_is_optional(self) -> None:
        """MEM0_API_KEY is optional and doesn't cause exit."""
        # Should not raise even without MEM0_API_KEY
        validate_required_env()
