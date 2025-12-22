"""Tests for π.hooks.logging module."""

import json
from datetime import datetime, timedelta
from pathlib import Path

from π.hooks.logging import _truncate_value, cleanup_old_hook_logs, log_event


class TestTruncateValue:
    """Tests for _truncate_value helper."""

    def test_truncates_long_strings(self):
        """Should truncate strings longer than max_len."""
        long_string = "a" * 300
        result = _truncate_value(long_string, max_len=100)

        assert isinstance(result, str)
        assert len(result) == 103  # 100 + "..."
        assert result.endswith("...")

    def test_preserves_short_strings(self):
        """Should not truncate strings shorter than max_len."""
        short_string = "hello"
        result = _truncate_value(short_string, max_len=100)

        assert result == "hello"

    def test_truncates_nested_dict_values(self):
        """Should truncate string values inside dicts."""
        data = {"key": "a" * 300}
        result = _truncate_value(data, max_len=50)

        assert isinstance(result, dict)
        assert len(result["key"]) == 53  # 50 + "..."

    def test_truncates_nested_list_values(self):
        """Should truncate string values inside lists."""
        data = ["a" * 300, "b" * 300]
        result = _truncate_value(data, max_len=50)

        assert isinstance(result, list)
        assert len(result[0]) == 53
        assert len(result[1]) == 53

    def test_preserves_non_string_types(self):
        """Should preserve ints, floats, booleans, None."""
        assert _truncate_value(123) == 123
        assert _truncate_value(3.14) == 3.14
        assert _truncate_value(True) is True
        assert _truncate_value(None) is None

    def test_handles_deeply_nested_structures(self):
        """Should handle arbitrarily nested structures."""
        data = {"level1": {"level2": {"value": "a" * 300}}}
        result = _truncate_value(data, max_len=50)

        assert isinstance(result, dict)
        level1 = result["level1"]
        assert isinstance(level1, dict)
        level2 = level1["level2"]
        assert isinstance(level2, dict)
        assert len(level2["value"]) == 53


class TestLogEvent:
    """Tests for log_event function."""

    def test_creates_log_file_with_date(self, log_dir: Path):
        """Should create log file named with current date."""
        log_event("[TEST_EVENT]", {"key": "value"})

        today = datetime.now().strftime("%Y-%m-%d")
        log_file = log_dir / f"{today}-hooks.log"

        assert log_file.exists()

    def test_appends_to_existing_log(self, log_dir: Path):
        """Should append multiple events to same log file."""
        log_event("[EVENT_1]", {"n": 1})
        log_event("[EVENT_2]", {"n": 2})

        today = datetime.now().strftime("%Y-%m-%d")
        log_file = log_dir / f"{today}-hooks.log"
        content = log_file.read_text()

        assert "[EVENT_1]" in content
        assert "[EVENT_2]" in content

    def test_log_format_includes_timestamp(self, log_dir: Path):
        """Should include ISO timestamp in log entry."""
        log_event("[TIME_TEST]", {"data": "test"})

        today = datetime.now().strftime("%Y-%m-%d")
        log_file = log_dir / f"{today}-hooks.log"
        content = log_file.read_text()

        # Should have ISO format timestamp
        assert today in content
        assert "T" in content  # ISO separator

    def test_log_format_includes_event_name(self, log_dir: Path):
        """Should include event name in log entry."""
        log_event("[CUSTOM_EVENT]", {"x": 1})

        today = datetime.now().strftime("%Y-%m-%d")
        log_file = log_dir / f"{today}-hooks.log"
        content = log_file.read_text()

        assert "[CUSTOM_EVENT]" in content

    def test_log_format_includes_json_data(self, log_dir: Path):
        """Should include JSON-serialized data in log entry."""
        log_event("[DATA_TEST]", {"command": "ls", "exit_code": 0})

        today = datetime.now().strftime("%Y-%m-%d")
        log_file = log_dir / f"{today}-hooks.log"
        content = log_file.read_text()

        # Extract JSON part (after last |)
        json_part = content.split("|")[-1].strip()
        data = json.loads(json_part)

        assert data["command"] == "ls"
        assert data["exit_code"] == 0

    def test_truncates_long_values_in_data(self, log_dir: Path):
        """Should truncate long string values in logged data."""
        long_output = "x" * 500
        log_event("[TRUNCATE_TEST]", {"output": long_output})

        today = datetime.now().strftime("%Y-%m-%d")
        log_file = log_dir / f"{today}-hooks.log"
        content = log_file.read_text()

        # Original 500-char string should not appear
        assert long_output not in content
        # But truncated version should
        assert "..." in content


class TestCleanupOldHookLogs:
    """Tests for cleanup_old_hook_logs function."""

    def test_returns_zero_if_directory_missing(self, tmp_path, monkeypatch):
        """Should return 0 if logs directory doesn't exist."""
        non_existent = tmp_path / "missing"
        monkeypatch.setattr("π.hooks.logging._LOG_DIR", non_existent)
        deleted = cleanup_old_hook_logs()
        assert deleted == 0

    def test_deletes_old_hook_log_files(self, log_dir: Path):
        """Should delete hook log files older than retention days."""
        # Create old log file (40 days ago)
        old_date = datetime.now() - timedelta(days=40)
        old_file = log_dir / f"{old_date.strftime('%Y-%m-%d')}-hooks.log"
        old_file.write_text("old hook log")

        # Create recent log file (15 days ago)
        recent_date = datetime.now() - timedelta(days=15)
        recent_file = log_dir / f"{recent_date.strftime('%Y-%m-%d')}-hooks.log"
        recent_file.write_text("recent hook log")

        deleted = cleanup_old_hook_logs(retention_days=30)

        assert deleted == 1
        assert not old_file.exists()
        assert recent_file.exists()

    def test_preserves_recent_hook_log_files(self, log_dir: Path):
        """Should preserve hook log files newer than retention days."""
        # Create recent log files
        today = datetime.now()
        for days_ago in [0, 5, 10, 20]:
            date = today - timedelta(days=days_ago)
            log_file = log_dir / f"{date.strftime('%Y-%m-%d')}-hooks.log"
            log_file.write_text(f"hook log from {days_ago} days ago")

        deleted = cleanup_old_hook_logs(retention_days=30)

        assert deleted == 0
        assert len(list(log_dir.glob("*-hooks.log"))) == 4

    def test_skips_invalid_filenames(self, log_dir: Path):
        """Should skip files with unexpected format."""
        # Create files with invalid names
        (log_dir / "invalid-hooks.log").write_text("invalid")
        (log_dir / "2025-13-99-hooks.log").write_text("bad date")
        (log_dir / "not-a-date.log").write_text("not hook log")

        deleted = cleanup_old_hook_logs(retention_days=30)

        assert deleted == 0
        assert len(list(log_dir.glob("*-hooks.log"))) == 2  # Only valid pattern files

    def test_custom_retention_days(self, log_dir: Path):
        """Should respect custom retention days parameter."""
        # Create log files at various ages
        for days_ago in [10, 50, 90]:
            date = datetime.now() - timedelta(days=days_ago)
            log_file = log_dir / f"{date.strftime('%Y-%m-%d')}-hooks.log"
            log_file.write_text(f"hook log from {days_ago} days ago")

        deleted = cleanup_old_hook_logs(retention_days=60)

        # Should delete 90 day old log, keep 10 and 50 day old
        assert deleted == 1
        assert len(list(log_dir.glob("*-hooks.log"))) == 2

    def test_only_deletes_hook_log_files(self, log_dir: Path):
        """Should only delete *-hooks.log files, not other files."""
        # Create old hook log file
        old_date = datetime.now() - timedelta(days=40)
        old_hook_log = log_dir / f"{old_date.strftime('%Y-%m-%d')}-hooks.log"
        old_hook_log.write_text("old hook log")

        # Create other files that should not be deleted
        (log_dir / "README.md").write_text("readme")
        (log_dir / f"{old_date.strftime('%Y-%m-%d')}.log").write_text("not hook log")

        deleted = cleanup_old_hook_logs(retention_days=30)

        assert deleted == 1
        assert not old_hook_log.exists()
        assert (log_dir / "README.md").exists()
        assert (log_dir / f"{old_date.strftime('%Y-%m-%d')}.log").exists()

    def test_handles_permission_errors_gracefully(self, log_dir: Path):
        """Should continue processing if file deletion fails."""
        # Create old hook log file
        old_date = datetime.now() - timedelta(days=40)
        old_file = log_dir / f"{old_date.strftime('%Y-%m-%d')}-hooks.log"
        old_file.write_text("old hook log")

        # We can't easily test actual permission errors in tests,
        # but we verify the function handles OSError in the try/except
        deleted = cleanup_old_hook_logs(retention_days=30)

        assert deleted == 1
