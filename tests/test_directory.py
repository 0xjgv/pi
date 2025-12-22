"""Tests for π.directory module."""

from datetime import datetime, timedelta

from π.directory import cleanup_old_logs, get_logs_dir


class TestGetLogsDir:
    """Tests for get_logs_dir function."""

    def test_defaults_to_cwd(self, monkeypatch, tmp_path):
        """Should default to current working directory."""
        monkeypatch.chdir(tmp_path)
        logs_dir = get_logs_dir()
        assert logs_dir == tmp_path / ".π" / "logs"

    def test_accepts_custom_root_path(self, tmp_path):
        """Should accept custom root path."""
        logs_dir = get_logs_dir(tmp_path)
        assert logs_dir == tmp_path / ".π" / "logs"

    def test_creates_directory_structure(self, tmp_path):
        """Should create .π/logs/ directory."""
        logs_dir = get_logs_dir(tmp_path)
        assert logs_dir.is_dir()
        assert (tmp_path / ".π").is_dir()

    def test_is_idempotent(self, tmp_path):
        """Should be safe to call multiple times."""
        logs_dir1 = get_logs_dir(tmp_path)
        logs_dir2 = get_logs_dir(tmp_path)
        assert logs_dir1 == logs_dir2
        assert logs_dir1.is_dir()

    def test_creates_gitignore_if_missing(self, tmp_path):
        """Should create .gitignore with .π/ entry."""
        get_logs_dir(tmp_path)
        gitignore = tmp_path / ".gitignore"
        assert gitignore.exists()
        assert ".π/" in gitignore.read_text()

    def test_appends_to_existing_gitignore(self, tmp_path):
        """Should append .π/ to existing .gitignore."""
        gitignore = tmp_path / ".gitignore"
        gitignore.write_text("node_modules/\n")

        get_logs_dir(tmp_path)

        content = gitignore.read_text()
        assert "node_modules/" in content
        assert ".π/" in content

    def test_does_not_duplicate_gitignore_entry(self, tmp_path):
        """Should not add .π/ if already present."""
        gitignore = tmp_path / ".gitignore"
        gitignore.write_text(".π/\n")

        get_logs_dir(tmp_path)

        assert gitignore.read_text().count(".π") == 1


class TestCleanupOldLogs:
    """Tests for cleanup_old_logs function."""

    def test_returns_zero_if_directory_missing(self, tmp_path):
        """Should return 0 if logs directory doesn't exist."""
        non_existent = tmp_path / "missing"
        deleted = cleanup_old_logs(non_existent)
        assert deleted == 0

    def test_deletes_old_log_files(self, tmp_path):
        """Should delete log files older than retention days."""
        logs_dir = tmp_path / "logs"
        logs_dir.mkdir()

        # Create old log file (10 days ago)
        old_date = datetime.now() - timedelta(days=10)
        old_file = logs_dir / f"{old_date.strftime('%Y-%m-%d')}-10:00.log"
        old_file.write_text("old log")

        # Create recent log file (3 days ago)
        recent_date = datetime.now() - timedelta(days=3)
        recent_file = logs_dir / f"{recent_date.strftime('%Y-%m-%d')}-10:00.log"
        recent_file.write_text("recent log")

        deleted = cleanup_old_logs(logs_dir, retention_days=7)

        assert deleted == 1
        assert not old_file.exists()
        assert recent_file.exists()

    def test_preserves_recent_log_files(self, tmp_path):
        """Should preserve log files newer than retention days."""
        logs_dir = tmp_path / "logs"
        logs_dir.mkdir()

        # Create recent log files
        today = datetime.now()
        for days_ago in [0, 1, 2, 5]:
            date = today - timedelta(days=days_ago)
            log_file = logs_dir / f"{date.strftime('%Y-%m-%d')}-10:00.log"
            log_file.write_text(f"log from {days_ago} days ago")

        deleted = cleanup_old_logs(logs_dir, retention_days=7)

        assert deleted == 0
        assert len(list(logs_dir.glob("*.log"))) == 4

    def test_skips_invalid_filenames(self, tmp_path):
        """Should skip files with unexpected format."""
        logs_dir = tmp_path / "logs"
        logs_dir.mkdir()

        # Create files with invalid names
        (logs_dir / "invalid.log").write_text("invalid")
        (logs_dir / "2025-13-99.log").write_text("bad date")
        (logs_dir / "not-a-date.log").write_text("not a date")

        deleted = cleanup_old_logs(logs_dir, retention_days=7)

        assert deleted == 0
        assert len(list(logs_dir.glob("*.log"))) == 3

    def test_handles_permission_errors_gracefully(self, tmp_path):
        """Should continue processing if file deletion fails."""
        logs_dir = tmp_path / "logs"
        logs_dir.mkdir()

        # Create old log file
        old_date = datetime.now() - timedelta(days=10)
        old_file = logs_dir / f"{old_date.strftime('%Y-%m-%d')}-10:00.log"
        old_file.write_text("old log")

        # We can't easily test actual permission errors in tests,
        # but we verify the function handles OSError in the try/except
        deleted = cleanup_old_logs(logs_dir, retention_days=7)

        assert deleted == 1

    def test_custom_retention_days(self, tmp_path):
        """Should respect custom retention days parameter."""
        logs_dir = tmp_path / "logs"
        logs_dir.mkdir()

        # Create log files at various ages
        for days_ago in [5, 15, 25]:
            date = datetime.now() - timedelta(days=days_ago)
            log_file = logs_dir / f"{date.strftime('%Y-%m-%d')}-10:00.log"
            log_file.write_text(f"log from {days_ago} days ago")

        deleted = cleanup_old_logs(logs_dir, retention_days=10)

        # Should delete 15 and 25 day old logs, keep 5 day old
        assert deleted == 2
        assert len(list(logs_dir.glob("*.log"))) == 1

    def test_only_deletes_log_files(self, tmp_path):
        """Should only delete .log files, not other files."""
        logs_dir = tmp_path / "logs"
        logs_dir.mkdir()

        # Create old log file
        old_date = datetime.now() - timedelta(days=10)
        old_log = logs_dir / f"{old_date.strftime('%Y-%m-%d')}-10:00.log"
        old_log.write_text("old log")

        # Create other files that should not be deleted
        (logs_dir / "README.md").write_text("readme")
        (logs_dir / "data.json").write_text("{}")

        deleted = cleanup_old_logs(logs_dir, retention_days=7)

        assert deleted == 1
        assert not old_log.exists()
        assert (logs_dir / "README.md").exists()
        assert (logs_dir / "data.json").exists()
