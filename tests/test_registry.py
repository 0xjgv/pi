"""Tests for π.hooks.registry module."""

from pathlib import Path
from typing import Generator

import pytest

from π.hooks.registry import LanguageChecker, _registry, get_checker, language_checker


@pytest.fixture
def isolated_registry() -> Generator[dict, None, None]:
    """Provide an isolated registry for testing, restoring original after."""
    original = _registry.copy()
    _registry.clear()
    yield _registry
    _registry.clear()
    _registry.update(original)


class TestLanguageChecker:
    """Tests for LanguageChecker dataclass."""

    def test_checker_attributes(self):
        """LanguageChecker should store all attributes."""

        def dummy_func(path: Path, tool_name: str | None = None) -> int:
            return 0

        checker = LanguageChecker(
            func=dummy_func,
            scope="project",
            project_markers=["Cargo.toml"],
        )

        assert checker.func is dummy_func
        assert checker.scope == "project"
        assert checker.project_markers == ["Cargo.toml"]


class TestLanguageCheckerDecorator:
    """Tests for language_checker decorator."""

    def test_registers_single_extension(self, isolated_registry: dict):
        """Should register checker for a single extension."""

        @language_checker([".test"])
        def check_test(path: Path, tool_name: str | None = None) -> int:
            return 0

        assert ".test" in isolated_registry
        assert isolated_registry[".test"].func is check_test

    def test_registers_multiple_extensions(self, isolated_registry: dict):
        """Should register checker for multiple extensions."""

        @language_checker([".ts", ".tsx", ".js", ".jsx"])
        def check_js(path: Path, tool_name: str | None = None) -> int:
            return 0

        assert ".ts" in isolated_registry
        assert ".tsx" in isolated_registry
        assert ".js" in isolated_registry
        assert ".jsx" in isolated_registry

        # All should point to same function
        assert isolated_registry[".ts"].func is check_js
        assert isolated_registry[".jsx"].func is check_js

    def test_normalizes_extension_case(self, isolated_registry: dict):
        """Should normalize extensions to lowercase."""

        @language_checker([".PY", ".PyX"])
        def check_python(path: Path, tool_name: str | None = None) -> int:
            return 0

        assert ".py" in isolated_registry
        assert ".pyx" in isolated_registry
        assert ".PY" not in isolated_registry

    def test_default_scope_is_file(self, isolated_registry: dict):
        """Default scope should be 'file'."""

        @language_checker([".test"])
        def check_test(path: Path, tool_name: str | None = None) -> int:
            return 0

        assert isolated_registry[".test"].scope == "file"

    def test_project_scope(self, isolated_registry: dict):
        """Should support project scope with markers."""

        @language_checker([".rs"], scope="project", project_markers=["Cargo.toml"])
        def check_rust(path: Path, tool_name: str | None = None) -> int:
            return 0

        checker = isolated_registry[".rs"]
        assert checker.scope == "project"
        assert checker.project_markers == ["Cargo.toml"]

    def test_returns_original_function(self, isolated_registry: dict):
        """Decorator should return the original function unchanged."""

        def check_test(path: Path, tool_name: str | None = None) -> int:
            return 42

        decorated = language_checker([".test"])(check_test)

        assert decorated is check_test
        assert decorated(Path("/test"), None) == 42

    def test_empty_project_markers_default(self, isolated_registry: dict):
        """Project markers should default to empty list."""

        @language_checker([".test"])
        def check_test(path: Path, tool_name: str | None = None) -> int:
            return 0

        assert isolated_registry[".test"].project_markers == []


class TestGetChecker:
    """Tests for get_checker function."""

    def test_returns_registered_checker(self, isolated_registry: dict):
        """Should return checker for registered extension."""

        @language_checker([".test"])
        def check_test(path: Path, tool_name: str | None = None) -> int:
            return 0

        result = get_checker(".test")

        assert result is not None
        assert result.func is check_test

    def test_returns_none_for_unknown_extension(self, isolated_registry: dict):
        """Should return None for unregistered extension."""
        result = get_checker(".unknown")
        assert result is None

    def test_normalizes_lookup_case(self, isolated_registry: dict):
        """Should normalize extension case during lookup."""

        @language_checker([".py"])
        def check_python(path: Path, tool_name: str | None = None) -> int:
            return 0

        assert get_checker(".PY") is not None
        assert get_checker(".Py") is not None
        assert get_checker(".py") is not None

    def test_requires_dot_prefix(self, isolated_registry: dict):
        """Extension lookup should include the dot."""

        @language_checker([".py"])
        def check_python(path: Path, tool_name: str | None = None) -> int:
            return 0

        assert get_checker("py") is None
        assert get_checker(".py") is not None


class TestRegistryIntegration:
    """Integration tests verifying real checkers are registered."""

    def test_python_checker_registered(self):
        """Python checker should be registered for .py and .pyx."""
        # Importing checkers registers them
        from π.hooks import checkers as _  # noqa: F401

        py_checker = get_checker(".py")
        pyx_checker = get_checker(".pyx")

        assert py_checker is not None
        assert pyx_checker is not None
        assert py_checker.func is pyx_checker.func

    def test_typescript_checker_registered(self):
        """TypeScript/JS checker should be registered."""
        from π.hooks import checkers as _  # noqa: F401

        assert get_checker(".ts") is not None
        assert get_checker(".tsx") is not None
        assert get_checker(".js") is not None
        assert get_checker(".jsx") is not None

    def test_rust_checker_registered(self):
        """Rust checker should be registered with project scope."""
        from π.hooks import checkers as _  # noqa: F401

        checker = get_checker(".rs")
        assert checker is not None
        assert checker.scope == "project"
        assert "Cargo.toml" in checker.project_markers

    def test_go_checker_registered(self):
        """Go checker should be registered with project scope."""
        from π.hooks import checkers as _  # noqa: F401

        checker = get_checker(".go")
        assert checker is not None
        assert checker.scope == "project"
        assert "go.mod" in checker.project_markers
