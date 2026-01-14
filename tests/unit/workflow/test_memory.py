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


class TestCleanupChromaStore:
    """Tests for ChromaDB store cleanup function."""

    def test_returns_false_when_path_not_exists(self, tmp_path):
        """Should return False if chroma path doesn't exist."""
        from π.workflow.memory import cleanup_chroma_store

        nonexistent = tmp_path / "nonexistent"
        result = cleanup_chroma_store(chroma_path=str(nonexistent))
        assert result is False

    def test_returns_false_when_store_is_fresh(self, tmp_path):
        """Should return False if store is newer than retention period."""
        from π.workflow.memory import cleanup_chroma_store

        chroma_dir = tmp_path / "chroma"
        chroma_dir.mkdir()
        (chroma_dir / "test.db").touch()

        # Fresh store should not be archived
        result = cleanup_chroma_store(chroma_path=str(chroma_dir), retention_days=30)
        assert result is False
        assert chroma_dir.exists()  # Still exists

    def test_archives_old_store(self, tmp_path):
        """Should archive store older than retention period."""
        import os
        from datetime import datetime, timedelta

        from π.workflow.memory import cleanup_chroma_store

        # Create chroma directory structure
        chroma_dir = tmp_path / "chroma"
        chroma_dir.mkdir()
        test_file = chroma_dir / "test.db"
        test_file.touch()

        # Set modification time to 40 days ago
        old_time = datetime.now() - timedelta(days=40)
        old_timestamp = old_time.timestamp()
        os.utime(chroma_dir, (old_timestamp, old_timestamp))

        # Should archive the old store
        result = cleanup_chroma_store(chroma_path=str(chroma_dir), retention_days=30)
        assert result is True
        assert not chroma_dir.exists()  # Original moved
        # Archived directory should exist
        archived_dirs = list((tmp_path / "archived").glob("*/chroma"))
        assert len(archived_dirs) == 1

    def test_uses_default_retention_from_constants(self, tmp_path):
        """Should use RETENTION.memory_store_days as default."""
        from π.workflow.memory import cleanup_chroma_store

        chroma_dir = tmp_path / "chroma"
        chroma_dir.mkdir()

        # With default retention (30 days), fresh store should not be archived
        result = cleanup_chroma_store(chroma_path=str(chroma_dir))
        assert result is False
