"""Tests for memory client configuration and fallback."""

from unittest.mock import patch

import pytest

from π.workflow.memory import NoOpMemoryClient, get_memory_client


class TestNoOpMemoryClient:
    """Tests for the fallback memory client."""

    def test_add_returns_skipped_status(self):
        client = NoOpMemoryClient("test reason")
        result = client.add("test message", user_id="test")
        assert result == {"id": None, "status": "skipped"}

    def test_search_returns_empty_results(self):
        client = NoOpMemoryClient()
        result = client.search("query", user_id="test")
        assert result == {"results": []}

    def test_get_all_returns_empty_results(self):
        client = NoOpMemoryClient()
        result = client.get_all(user_id="test")
        assert result == {"results": []}


class TestGetMemoryClient:
    """Tests for memory client factory function."""

    @pytest.fixture(autouse=True)
    def clear_cache(self):
        """Clear LRU cache before each test."""
        get_memory_client.cache_clear()
        yield
        get_memory_client.cache_clear()

    def test_returns_noop_on_import_error(self):
        with (
            patch(
                "π.workflow.memory._get_hosted_client",
                side_effect=ImportError("test"),
            ),
            patch(
                "π.workflow.memory._get_self_hosted_client",
                side_effect=ImportError("test"),
            ),
            patch.dict("os.environ", {"MEM0_API_KEY": ""}, clear=False),
        ):
            client = get_memory_client()
            assert isinstance(client, NoOpMemoryClient)

    def test_returns_noop_on_initialization_error(self):
        with (
            patch(
                "π.workflow.memory._get_self_hosted_client",
                side_effect=RuntimeError("config error"),
            ),
            patch.dict("os.environ", {"MEM0_API_KEY": ""}, clear=False),
        ):
            client = get_memory_client()
            assert isinstance(client, NoOpMemoryClient)

    def test_tries_hosted_when_api_key_set(self):
        with (
            patch(
                "π.workflow.memory._get_hosted_client",
                side_effect=RuntimeError("hosted error"),
            ),
            patch.dict("os.environ", {"MEM0_API_KEY": "test-key"}, clear=False),
        ):
            client = get_memory_client()
            # Should return NoOp because hosted client failed
            assert isinstance(client, NoOpMemoryClient)
