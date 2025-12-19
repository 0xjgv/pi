"""Tests for π.hooks.logging module."""

import json
from datetime import datetime
from pathlib import Path

from π.hooks.logging import _truncate_value, log_event


class TestTruncateValue:
    """Tests for _truncate_value helper."""

    def test_truncates_long_strings(self):
        """Should truncate strings longer than max_len."""
        long_string = "a" * 300
        result = _truncate_value(long_string, max_len=100)

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

        assert len(result["key"]) == 53  # 50 + "..."

    def test_truncates_nested_list_values(self):
        """Should truncate string values inside lists."""
        data = ["a" * 300, "b" * 300]
        result = _truncate_value(data, max_len=50)

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
        data = {
            "level1": {
                "level2": {
                    "value": "a" * 300
                }
            }
        }
        result = _truncate_value(data, max_len=50)

        assert len(result["level1"]["level2"]["value"]) == 53


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
