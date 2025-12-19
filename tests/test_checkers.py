"""Tests for π.hooks.checkers module."""

from pathlib import Path
from unittest.mock import MagicMock


class TestCheckPython:
    """Tests for Python checker."""

    def test_uses_uvx_when_available(self, mocker: MagicMock, tmp_path: Path):
        """Should prefer uvx over ruff when available."""
        from π.hooks.checkers import check_python

        # Mock shutil.which to return uvx
        mocker.patch(
            "shutil.which", side_effect=lambda x: "/usr/bin/uvx" if x == "uvx" else None
        )

        # Mock run_check_command
        mock_run = mocker.patch(
            "π.hooks.checkers.run_check_command", return_value=(0, "", "")
        )

        # Mock console to prevent output
        mocker.patch("π.hooks.checkers.console")

        py_file = tmp_path / "test.py"
        py_file.write_text("print('hello')")

        result = check_python(py_file, "Edit")

        assert result == 0
        mock_run.assert_called_once()
        cmd = mock_run.call_args[1]["cmd"]
        assert cmd[0] == "uvx"
        assert cmd[1] == "ruff"

    def test_uses_ruff_when_uvx_unavailable(self, mocker: MagicMock, tmp_path: Path):
        """Should fall back to ruff when uvx not available."""
        from π.hooks.checkers import check_python

        # Mock shutil.which to return ruff but not uvx
        mocker.patch(
            "shutil.which",
            side_effect=lambda x: "/usr/bin/ruff" if x == "ruff" else None,
        )
        mock_run = mocker.patch(
            "π.hooks.checkers.run_check_command", return_value=(0, "", "")
        )
        mocker.patch("π.hooks.checkers.console")

        py_file = tmp_path / "test.py"
        py_file.write_text("print('hello')")

        result = check_python(py_file, "Edit")

        assert result == 0
        cmd = mock_run.call_args[1]["cmd"]
        assert cmd[0] == "ruff"

    def test_returns_zero_when_ruff_not_found(self, mocker: MagicMock, tmp_path: Path):
        """Should return 0 with warning when ruff not installed."""
        from π.hooks.checkers import check_python

        mocker.patch("shutil.which", return_value=None)
        mock_console = mocker.patch("π.hooks.checkers.console")

        py_file = tmp_path / "test.py"
        py_file.write_text("print('hello')")

        result = check_python(py_file, "Edit")

        assert result == 0
        # Should print warning
        mock_console.print.assert_called()
        assert "not found" in str(mock_console.print.call_args)

    def test_returns_two_on_check_failure(self, mocker: MagicMock, tmp_path: Path):
        """Should return 2 when checks fail."""
        from π.hooks.checkers import check_python

        mocker.patch("shutil.which", return_value="/usr/bin/uvx")
        mocker.patch(
            "π.hooks.checkers.run_check_command",
            return_value=(1, "", "error: unused import"),
        )
        mocker.patch("π.hooks.checkers.console")

        py_file = tmp_path / "test.py"
        py_file.write_text("import os")

        result = check_python(py_file, "Edit")

        assert result == 2


class TestCheckTypescript:
    """Tests for TypeScript/JavaScript checker."""

    def test_returns_zero_when_no_package_json(self, mocker: MagicMock, tmp_path: Path):
        """Should return 0 when no package.json found."""
        from π.hooks.checkers import check_typescript

        mocker.patch("π.hooks.checkers.console")

        ts_file = tmp_path / "test.ts"
        ts_file.write_text("const x = 1;")

        result = check_typescript(ts_file, "Edit")

        assert result == 0

    def test_returns_zero_when_no_eslint_config(
        self, mocker: MagicMock, tmp_path: Path
    ):
        """Should return 0 when no ESLint config found."""
        from π.hooks.checkers import check_typescript

        mocker.patch("π.hooks.checkers.console")

        # Create package.json but no eslint config
        (tmp_path / "package.json").write_text('{"name": "test"}')
        ts_file = tmp_path / "test.ts"
        ts_file.write_text("const x = 1;")

        result = check_typescript(ts_file, "Edit")

        assert result == 0

    def test_runs_eslint_with_config(self, mocker: MagicMock, tmp_path: Path):
        """Should run eslint when config exists."""
        from π.hooks.checkers import check_typescript

        mock_run = mocker.patch(
            "π.hooks.checkers.run_check_command", return_value=(0, "", "")
        )
        mocker.patch("π.hooks.checkers.console")

        # Create package.json and eslint config
        (tmp_path / "package.json").write_text('{"name": "test"}')
        (tmp_path / "eslint.config.mjs").write_text("export default {};")
        ts_file = tmp_path / "test.ts"
        ts_file.write_text("const x = 1;")

        result = check_typescript(ts_file, "Edit")

        assert result == 0
        mock_run.assert_called_once()
        cmd = mock_run.call_args[1]["cmd"]
        assert "npx" in cmd
        assert "eslint" in cmd


class TestCheckRust:
    """Tests for Rust checker."""

    def test_returns_zero_when_no_cargo_toml(self, mocker: MagicMock, tmp_path: Path):
        """Should return 0 when no Cargo.toml found."""
        from π.hooks.checkers import check_rust

        mocker.patch("π.hooks.checkers.console")

        rs_file = tmp_path / "main.rs"
        rs_file.write_text("fn main() {}")

        result = check_rust(rs_file, "Edit")

        assert result == 0

    def test_runs_cargo_check(self, mocker: MagicMock, tmp_path: Path):
        """Should run cargo check when Cargo.toml exists."""
        from π.hooks.checkers import check_rust

        mock_run = mocker.patch(
            "π.hooks.checkers.run_check_command", return_value=(0, "", "")
        )
        mocker.patch("π.hooks.checkers.console")

        # Create Cargo.toml
        (tmp_path / "Cargo.toml").write_text('[package]\nname = "test"')
        src = tmp_path / "src"
        src.mkdir()
        rs_file = src / "main.rs"
        rs_file.write_text("fn main() {}")

        result = check_rust(rs_file, "Edit")

        assert result == 0
        mock_run.assert_called_once()
        cmd = mock_run.call_args[1]["cmd"]
        assert cmd == ["cargo", "check"]


class TestCheckGo:
    """Tests for Go checker."""

    def test_returns_zero_when_no_go_mod(self, mocker: MagicMock, tmp_path: Path):
        """Should return 0 when no go.mod found."""
        from π.hooks.checkers import check_go

        mocker.patch("π.hooks.checkers.console")

        go_file = tmp_path / "main.go"
        go_file.write_text("package main")

        result = check_go(go_file, "Edit")

        assert result == 0

    def test_uses_golangci_lint_when_available(self, mocker: MagicMock, tmp_path: Path):
        """Should prefer golangci-lint over go vet."""
        from π.hooks.checkers import check_go

        mocker.patch("shutil.which", return_value="/usr/bin/golangci-lint")
        mock_run = mocker.patch(
            "π.hooks.checkers.run_check_command", return_value=(0, "", "")
        )
        mocker.patch("π.hooks.checkers.console")

        # Create go.mod
        (tmp_path / "go.mod").write_text("module test")
        go_file = tmp_path / "main.go"
        go_file.write_text("package main")

        result = check_go(go_file, "Edit")

        assert result == 0
        mock_run.assert_called_once()
        cmd = mock_run.call_args[1]["cmd"]
        assert "golangci-lint" in cmd

    def test_uses_go_vet_when_golangci_lint_unavailable(
        self, mocker: MagicMock, tmp_path: Path
    ):
        """Should fall back to go vet."""
        from π.hooks.checkers import check_go

        mocker.patch("shutil.which", return_value=None)
        mock_run = mocker.patch(
            "π.hooks.checkers.run_check_command", return_value=(0, "", "")
        )
        mocker.patch("π.hooks.checkers.console")

        # Create go.mod
        (tmp_path / "go.mod").write_text("module test")
        go_file = tmp_path / "main.go"
        go_file.write_text("package main")

        result = check_go(go_file, "Edit")

        assert result == 0
        cmd = mock_run.call_args[1]["cmd"]
        assert cmd == ["go", "vet", "./..."]


class TestRunCheckCommand:
    """Tests for run_check_command utility."""

    def test_returns_exit_code_stdout_stderr(self, mocker: MagicMock, tmp_path: Path):
        """Should return tuple of exit code, stdout, stderr."""
        from π.hooks.utils import run_check_command

        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = "output"
        mock_result.stderr = ""
        mocker.patch("subprocess.run", return_value=mock_result)
        mocker.patch("π.hooks.utils.log_event")

        exit_code, stdout, stderr = run_check_command(
            cwd=tmp_path,
            cmd=["echo", "test"],
            name="test",
        )

        assert exit_code == 0
        assert stdout == "output"
        assert stderr == ""

    def test_handles_timeout(self, mocker: MagicMock, tmp_path: Path):
        """Should handle subprocess timeout."""
        import subprocess

        from π.hooks.utils import run_check_command

        mocker.patch("subprocess.run", side_effect=subprocess.TimeoutExpired("cmd", 30))
        mocker.patch("π.hooks.utils.log_event")

        exit_code, stdout, stderr = run_check_command(
            cwd=tmp_path,
            cmd=["sleep", "100"],
            name="test",
            timeout=1,
        )

        assert exit_code == 124
        assert "timed out" in stderr

    def test_handles_command_not_found(self, mocker: MagicMock, tmp_path: Path):
        """Should handle FileNotFoundError."""
        from π.hooks.utils import run_check_command

        mocker.patch("subprocess.run", side_effect=FileNotFoundError())
        mocker.patch("π.hooks.utils.log_event")

        exit_code, stdout, stderr = run_check_command(
            cwd=tmp_path,
            cmd=["nonexistent"],
            name="test",
        )

        assert exit_code == 127
        assert "not found" in stderr

    def test_logs_check_command(self, mocker: MagicMock, tmp_path: Path):
        """Should log the check command."""
        from π.hooks.utils import run_check_command

        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = ""
        mock_result.stderr = ""
        mocker.patch("subprocess.run", return_value=mock_result)
        mock_log = mocker.patch("π.hooks.utils.log_event")

        run_check_command(
            cwd=tmp_path,
            cmd=["ruff", "check", "test.py"],
            name="ruff",
            tool_name="Edit",
            file_path="/path/to/test.py",
        )

        mock_log.assert_called()
        call_args = mock_log.call_args_list[0]
        assert call_args[0][0] == "[CHECK_COMMAND]"
