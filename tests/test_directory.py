"""Tests for π.directory module."""

from π.directory import get_logs_dir


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
