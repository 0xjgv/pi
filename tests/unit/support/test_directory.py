"""Tests for π.utils module (directory functions)."""

from π.config import get_logs_dir
from π.utils import get_project_root


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
