"""Tests for documentation sync module."""

import sys

import pytest

from π.doc_sync.core import DEFAULT_FILES_THRESHOLD, DocSyncState


class TestDocSyncState:
    """Tests for DocSyncState."""

    def test_load_missing_file_returns_defaults(self, tmp_path, monkeypatch):
        """Loading from missing file returns default state."""
        monkeypatch.setattr("π.doc_sync.core.get_project_root", lambda: tmp_path)
        state = DocSyncState.load()
        assert state.last_sync_commit is None
        assert state.files_changed_since_sync == 0

    def test_save_and_reload(self, tmp_path, monkeypatch):
        """State persists correctly through save/load cycle."""
        monkeypatch.setattr("π.doc_sync.core.get_project_root", lambda: tmp_path)
        state = DocSyncState(
            last_sync_commit="abc123",
            files_changed_since_sync=5,
        )
        state.save()

        reloaded = DocSyncState.load()
        assert reloaded.last_sync_commit == "abc123"
        assert reloaded.files_changed_since_sync == 5

    def test_should_trigger_below_threshold(self):
        """should_trigger returns False below threshold."""
        state = DocSyncState(files_changed_since_sync=5)
        assert not state.should_trigger()

    def test_should_trigger_at_threshold(self):
        """should_trigger returns True at threshold."""
        state = DocSyncState(files_changed_since_sync=DEFAULT_FILES_THRESHOLD)
        assert state.should_trigger()

    def test_mark_synced_resets_counter(self, tmp_path, monkeypatch):
        """mark_synced resets files counter and saves."""
        monkeypatch.setattr("π.doc_sync.core.get_project_root", lambda: tmp_path)
        state = DocSyncState(files_changed_since_sync=15)
        state.mark_synced("def456")

        assert state.files_changed_since_sync == 0
        assert state.last_sync_commit == "def456"
        assert state.last_sync_timestamp is not None


class TestDocSyncCLI:
    """Tests for CLI entry point."""

    def test_help_output(self, capsys):
        """--help displays usage information."""
        from π.doc_sync.__main__ import main

        with pytest.raises(SystemExit) as exc_info:
            sys.argv = ["doc_sync", "--help"]
            main()

        assert exc_info.value.code == 0
        captured = capsys.readouterr()
        assert "Documentation sync agent" in captured.out
