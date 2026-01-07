"""Tests for π.hooks.checkers module."""

from pathlib import Path
from unittest.mock import patch

from π.hooks.checkers import check_go, check_python, check_rust, check_typescript


class TestCheckPython:
    """Tests for check_python function."""

    def test_runs_ruff_via_uvx(self, python_file: Path):
        """Should run ruff via uvx when available."""
        with (
            patch("shutil.which", return_value="/usr/bin/uvx"),
            patch("π.hooks.checkers.run_check_command") as mock_run,
        ):
            mock_run.return_value = (0, "All checks passed", "")
            result = check_python(python_file, tool_name="Edit")

        mock_run.assert_called_once()
        cmd = mock_run.call_args.kwargs["cmd"]
        assert "uvx" in cmd
        assert "ruff" in cmd
        assert result == 0

    def test_falls_back_to_ruff_directly(self, python_file: Path):
        """Should use ruff directly when uvx not available."""

        def which_side_effect(cmd: str) -> str | None:
            return "/usr/bin/ruff" if cmd == "ruff" else None

        with (
            patch("shutil.which", side_effect=which_side_effect),
            patch("π.hooks.checkers.run_check_command") as mock_run,
        ):
            mock_run.return_value = (0, "Success", "")
            result = check_python(python_file, tool_name="Write")

        cmd = mock_run.call_args.kwargs["cmd"]
        assert cmd[0] == "ruff"
        assert result == 0

    def test_returns_zero_when_ruff_not_found(self, python_file: Path):
        """Should return 0 (pass) when ruff is not available."""
        with patch("shutil.which", return_value=None):
            result = check_python(python_file)

        assert result == 0

    def test_returns_zero_on_success(self, python_file: Path):
        """Should return 0 when ruff passes."""
        with (
            patch("shutil.which", return_value="/usr/bin/uvx"),
            patch("π.hooks.checkers.run_check_command") as mock_run,
        ):
            mock_run.return_value = (0, "All checks passed", "")
            result = check_python(python_file)

        assert result == 0

    def test_returns_two_on_failure(self, python_file: Path):
        """Should return 2 when ruff fails."""
        with (
            patch("shutil.which", return_value="/usr/bin/uvx"),
            patch("π.hooks.checkers.run_check_command") as mock_run,
        ):
            mock_run.return_value = (1, "", "Error: lint failed")
            result = check_python(python_file)

        assert result == 2


class TestCheckTypescript:
    """Tests for check_typescript function."""

    def test_returns_zero_when_no_package_json(self, tmp_path: Path):
        """Should return 0 when no package.json found."""
        ts_file = tmp_path / "test.ts"
        ts_file.write_text("const x = 1;")

        result = check_typescript(ts_file)

        assert result == 0

    def test_returns_zero_when_no_eslint_config(self, typescript_project: Path):
        """Should return 0 when no ESLint config found."""
        # Remove eslint config
        (typescript_project / "eslint.config.js").unlink()
        ts_file = typescript_project / "src" / "index.ts"

        result = check_typescript(ts_file)

        assert result == 0

    def test_runs_eslint_when_configured(self, typescript_project: Path):
        """Should run ESLint when properly configured."""
        ts_file = typescript_project / "src" / "index.ts"

        with patch("π.hooks.checkers.run_check_command") as mock_run:
            mock_run.return_value = (0, "All checks passed", "")
            result = check_typescript(ts_file)

        mock_run.assert_called_once()
        cmd = mock_run.call_args.kwargs["cmd"]
        assert "npx" in cmd
        assert "eslint" in cmd
        assert result == 0

    def test_returns_two_on_lint_failure(self, typescript_project: Path):
        """Should return 2 when ESLint fails."""
        ts_file = typescript_project / "src" / "index.ts"

        with patch("π.hooks.checkers.run_check_command") as mock_run:
            mock_run.return_value = (1, "", "Linting errors found")
            result = check_typescript(ts_file)

        assert result == 2


class TestCheckRust:
    """Tests for check_rust function."""

    def test_returns_zero_when_no_cargo_toml(self, tmp_path: Path):
        """Should return 0 when no Cargo.toml found."""
        rs_file = tmp_path / "main.rs"
        rs_file.write_text("fn main() {}")

        result = check_rust(rs_file)

        assert result == 0

    def test_runs_cargo_check(self, tmp_path: Path):
        """Should run cargo check when Cargo.toml exists."""
        (tmp_path / "Cargo.toml").write_text('[package]\nname = "test"')
        rs_file = tmp_path / "src" / "main.rs"
        rs_file.parent.mkdir()
        rs_file.write_text("fn main() {}")

        with patch("π.hooks.checkers.run_check_command") as mock_run:
            mock_run.return_value = (0, "Checking complete", "")
            result = check_rust(rs_file)

        mock_run.assert_called_once()
        cmd = mock_run.call_args.kwargs["cmd"]
        assert "cargo" in cmd
        assert "check" in cmd
        assert result == 0

    def test_returns_two_on_cargo_failure(self, tmp_path: Path):
        """Should return 2 when cargo check fails."""
        (tmp_path / "Cargo.toml").write_text('[package]\nname = "test"')
        rs_file = tmp_path / "src" / "main.rs"
        rs_file.parent.mkdir()
        rs_file.write_text("fn main() {}")

        with patch("π.hooks.checkers.run_check_command") as mock_run:
            mock_run.return_value = (1, "", "Compilation error")
            result = check_rust(rs_file)

        assert result == 2


class TestCheckGo:
    """Tests for check_go function."""

    def test_returns_zero_when_no_go_mod(self, tmp_path: Path):
        """Should return 0 when no go.mod found."""
        go_file = tmp_path / "main.go"
        go_file.write_text("package main")

        result = check_go(go_file)

        assert result == 0

    def test_prefers_golangci_lint(self, tmp_path: Path):
        """Should use golangci-lint when available."""
        (tmp_path / "go.mod").write_text("module test")
        go_file = tmp_path / "main.go"
        go_file.write_text("package main")

        with (
            patch("shutil.which", return_value="/usr/bin/golangci-lint"),
            patch("π.hooks.checkers.run_check_command") as mock_run,
        ):
            mock_run.return_value = (0, "All checks passed", "")
            result = check_go(go_file)

        cmd = mock_run.call_args.kwargs["cmd"]
        assert "golangci-lint" in cmd
        assert result == 0

    def test_falls_back_to_go_vet(self, tmp_path: Path):
        """Should fall back to go vet when golangci-lint not available."""
        (tmp_path / "go.mod").write_text("module test")
        go_file = tmp_path / "main.go"
        go_file.write_text("package main")

        with (
            patch("shutil.which", return_value=None),
            patch("π.hooks.checkers.run_check_command") as mock_run,
        ):
            mock_run.return_value = (0, "No issues found", "")
            result = check_go(go_file)

        cmd = mock_run.call_args.kwargs["cmd"]
        assert "go" in cmd
        assert "vet" in cmd
        assert result == 0

    def test_returns_two_on_lint_failure(self, tmp_path: Path):
        """Should return 2 when linting fails."""
        (tmp_path / "go.mod").write_text("module test")
        go_file = tmp_path / "main.go"
        go_file.write_text("package main")

        with (
            patch("shutil.which", return_value=None),
            patch("π.hooks.checkers.run_check_command") as mock_run,
        ):
            mock_run.return_value = (1, "", "Vet errors found")
            result = check_go(go_file)

        assert result == 2
