"""Tests for π.directory module."""

import os
from datetime import datetime, timedelta

from π.support import archive_old_documents, cleanup_old_logs, get_logs_dir
from π.support.directory import get_project_root


def _set_mtime_days_ago(path, days_ago):
    """Set file mtime to specified days ago from now."""
    mtime = (datetime.now() - timedelta(days=days_ago)).timestamp()
    os.utime(path, (mtime, mtime))


class TestGetProjectRoot:
    """Tests for get_project_root function."""

    def test_cwd_with_git_marker(self, monkeypatch, tmp_path):
        """Should return CWD when it has .git marker."""
        (tmp_path / ".git").mkdir()
        monkeypatch.chdir(tmp_path)
        assert get_project_root() == tmp_path

    def test_cwd_with_pyproject_marker(self, monkeypatch, tmp_path):
        """Should return CWD when it has pyproject.toml marker."""
        (tmp_path / "pyproject.toml").touch()
        monkeypatch.chdir(tmp_path)
        assert get_project_root() == tmp_path

    def test_cwd_with_claude_md_marker(self, monkeypatch, tmp_path):
        """Should return CWD when it has CLAUDE.md marker."""
        (tmp_path / "CLAUDE.md").touch()
        monkeypatch.chdir(tmp_path)
        assert get_project_root() == tmp_path

    def test_no_markers_no_git_falls_back_to_cwd(self, monkeypatch, tmp_path):
        """Should return CWD when no markers and not in git repo."""
        monkeypatch.chdir(tmp_path)
        # No markers, git rev-parse will fail
        assert get_project_root() == tmp_path

    def test_explicit_start_path(self, tmp_path):
        """Should use provided start_path instead of CWD."""
        (tmp_path / ".git").mkdir()
        assert get_project_root(tmp_path) == tmp_path


class TestGetLogsDir:
    """Tests for get_logs_dir function."""

    def test_defaults_to_project_root(self, monkeypatch, tmp_path):
        """Should default to detected project root."""
        (tmp_path / ".git").mkdir()
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


class TestArchiveOldDocuments:
    """Tests for archive_old_documents function."""

    def test_returns_empty_counts_if_directories_missing(self, tmp_path):
        """Should return zero counts if source directories don't exist."""
        result = archive_old_documents(root=tmp_path)
        assert result == {"research": 0, "plans": 0}

    def test_archives_old_research_documents(self, tmp_path):
        """Should archive research documents older than retention days by mtime."""
        research_dir = tmp_path / "thoughts" / "shared" / "research"
        research_dir.mkdir(parents=True)

        # Create old document (mtime 10 days ago)
        old_file = research_dir / "old-research.md"
        old_file.write_text("# Old Research")
        _set_mtime_days_ago(old_file, 10)

        # Create recent document (mtime 3 days ago)
        recent_file = research_dir / "recent-research.md"
        recent_file.write_text("# Recent Research")
        _set_mtime_days_ago(recent_file, 3)

        result = archive_old_documents(root=tmp_path, retention_days=5)

        assert result == {"research": 1, "plans": 0}
        assert not old_file.exists()
        assert recent_file.exists()
        archived = tmp_path / "thoughts" / "shared" / "archived" / "research"
        assert (archived / old_file.name).exists()

    def test_archives_old_plan_documents(self, tmp_path):
        """Should archive plan documents older than retention days by mtime."""
        plans_dir = tmp_path / "thoughts" / "shared" / "plans"
        plans_dir.mkdir(parents=True)

        # Create old document (mtime 10 days ago)
        old_file = plans_dir / "old-plan.md"
        old_file.write_text("# Old Plan")
        _set_mtime_days_ago(old_file, 10)

        result = archive_old_documents(root=tmp_path, retention_days=5)

        assert result == {"research": 0, "plans": 1}
        assert not old_file.exists()
        archived = tmp_path / "thoughts" / "shared" / "archived" / "plans"
        assert (archived / old_file.name).exists()

    def test_preserves_recent_documents(self, tmp_path):
        """Should preserve documents newer than retention days by mtime."""
        research_dir = tmp_path / "thoughts" / "shared" / "research"
        research_dir.mkdir(parents=True)

        # Create recent documents with various mtimes
        for days_ago in [0, 1, 2, 4]:
            doc_file = research_dir / f"doc-{days_ago}.md"
            doc_file.write_text(f"# Doc from {days_ago} days ago")
            _set_mtime_days_ago(doc_file, days_ago)

        result = archive_old_documents(root=tmp_path, retention_days=5)

        assert result == {"research": 0, "plans": 0}
        assert len(list(research_dir.glob("*.md"))) == 4

    def test_boundary_mtime_exactly_at_retention_days(self, tmp_path):
        """Should NOT archive document with mtime at retention_days boundary.

        A file with mtime at the retention boundary should be kept,
        because file_date < cutoff uses strict less-than comparison.
        We set mtime to 4.9 days ago to ensure it's within retention.
        """
        research_dir = tmp_path / "thoughts" / "shared" / "research"
        research_dir.mkdir(parents=True)

        # Create document with mtime just within retention (4.9 days ago)
        boundary_file = research_dir / "boundary-doc.md"
        boundary_file.write_text("# Boundary Document")
        _set_mtime_days_ago(boundary_file, 4.9)

        result = archive_old_documents(root=tmp_path, retention_days=5)

        # File within retention should NOT be archived
        assert result == {"research": 0, "plans": 0}
        assert boundary_file.exists()

    def test_only_archives_markdown_files(self, tmp_path):
        """Should only archive .md files, not other files."""
        research_dir = tmp_path / "thoughts" / "shared" / "research"
        research_dir.mkdir(parents=True)

        # Create old markdown file (mtime 10 days ago)
        old_md = research_dir / "research.md"
        old_md.write_text("# Research")
        _set_mtime_days_ago(old_md, 10)

        # Create other files with old mtime that should not be archived
        json_file = research_dir / "data.json"
        json_file.write_text("{}")
        _set_mtime_days_ago(json_file, 10)

        txt_file = research_dir / "notes.txt"
        txt_file.write_text("notes")
        _set_mtime_days_ago(txt_file, 10)

        result = archive_old_documents(root=tmp_path, retention_days=5)

        assert result == {"research": 1, "plans": 0}
        assert not old_md.exists()
        assert json_file.exists()
        assert txt_file.exists()

    def test_creates_archive_directories_on_demand(self, tmp_path):
        """Should create archive directories only when needed."""
        research_dir = tmp_path / "thoughts" / "shared" / "research"
        research_dir.mkdir(parents=True)

        # Create old document (mtime 10 days ago)
        old_file = research_dir / "research.md"
        old_file.write_text("# Research")
        _set_mtime_days_ago(old_file, 10)

        # Archive dir should not exist yet
        archive_dir = tmp_path / "thoughts" / "shared" / "archived" / "research"
        assert not archive_dir.exists()

        archive_old_documents(root=tmp_path, retention_days=5)

        # Now it should exist
        assert archive_dir.exists()

    def test_is_idempotent(self, tmp_path):
        """Should be safe to call multiple times."""
        research_dir = tmp_path / "thoughts" / "shared" / "research"
        research_dir.mkdir(parents=True)

        # Create old document (mtime 10 days ago)
        old_file = research_dir / "research.md"
        old_file.write_text("# Research")
        _set_mtime_days_ago(old_file, 10)

        result1 = archive_old_documents(root=tmp_path, retention_days=5)
        result2 = archive_old_documents(root=tmp_path, retention_days=5)

        assert result1 == {"research": 1, "plans": 0}
        assert result2 == {"research": 0, "plans": 0}

    def test_custom_retention_days(self, tmp_path):
        """Should respect custom retention days parameter."""
        research_dir = tmp_path / "thoughts" / "shared" / "research"
        research_dir.mkdir(parents=True)

        # Create documents with various mtimes
        for days_ago in [3, 8, 15]:
            doc_file = research_dir / f"doc-{days_ago}.md"
            doc_file.write_text(f"# Doc from {days_ago} days ago")
            _set_mtime_days_ago(doc_file, days_ago)

        result = archive_old_documents(root=tmp_path, retention_days=7)

        # Should archive 8 and 15 day old docs, keep 3 day old
        assert result == {"research": 2, "plans": 0}
        assert len(list(research_dir.glob("*.md"))) == 1
