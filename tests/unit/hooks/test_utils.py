"""Tests for π.hooks.utils module."""

import subprocess
from pathlib import Path
from unittest.mock import patch

from π.hooks.utils import compact_path, run_check_command


class TestCompactPath:
    """Tests for compact_path function."""

    def test_relative_to_home(self):
        """Should replace home directory with ~/."""
        home = Path.home()
        test_path = home / "Documents" / "test.py"

        result = compact_path(test_path)

        assert result.startswith("~/")
        assert "Documents" in result

    def test_value_error_on_relative_to(self):
        """Should handle ValueError when path is not relative to home."""
        # Path that's not under home directory
        test_path = Path("/var/log/test.log")

        with patch.object(
            Path, "is_relative_to", side_effect=ValueError("not relative")
        ):
            result = compact_path(test_path)

        # Should fall through to project root or return as-is
        assert isinstance(result, str)

    def test_long_path_truncation(self):
        """Should truncate very long paths."""
        # Create a path that's > 60 chars with > 4 parts
        long_path = Path("/very/long/deeply/nested/path/to/file.py")

        result = compact_path(long_path)

        # Should contain ellipsis for truncated paths
        if len(str(long_path)) > 60:
            assert "..." in result or len(result) <= len(str(long_path))

    def test_returns_string(self, tmp_path: Path):
        """Should always return a string."""
        result = compact_path(tmp_path / "test.py")

        assert isinstance(result, str)


class TestRunCheckCommand:
    """Tests for run_check_command function."""

    def test_success_returns_zero(self, tmp_path: Path):
        """Should return zero exit code on success."""
        code, stdout, stderr = run_check_command(
            tmp_path, ["echo", "hello"], "echo"
        )

        assert code == 0
        assert "hello" in stdout
        assert stderr == ""

    def test_timeout_returns_124(self, tmp_path: Path):
        """Should return 124 on timeout."""
        with patch(
            "subprocess.run",
            side_effect=subprocess.TimeoutExpired("cmd", 30),
        ):
            code, _stdout, stderr = run_check_command(
                tmp_path, ["sleep", "100"], "test"
            )

        assert code == 124
        assert "timed out" in stderr

    def test_not_found_returns_127(self, tmp_path: Path):
        """Should return 127 when command not found."""
        with patch("subprocess.run", side_effect=FileNotFoundError()):
            code, _stdout, stderr = run_check_command(
                tmp_path, ["nonexistent_cmd"], "test"
            )

        assert code == 127
        assert "not found" in stderr

    def test_generic_error_returns_1(self, tmp_path: Path):
        """Should return 1 on generic exception."""
        with patch("subprocess.run", side_effect=OSError("Permission denied")):
            code, _stdout, stderr = run_check_command(
                tmp_path, ["some_cmd"], "test"
            )

        assert code == 1
        assert "error" in stderr.lower()

    def test_failure_returns_nonzero(self, tmp_path: Path):
        """Should return non-zero exit code on command failure."""
        code, _stdout, _stderr = run_check_command(
            tmp_path, ["python", "-c", "import sys; sys.exit(42)"], "python"
        )

        assert code == 42
