"""Tests for π.hooks.registry module."""

from pathlib import Path

from π.hooks.registry import (
    LanguageChecker,
    _registry,
    get_checker,
    language_checker,
)


class TestLanguageChecker:
    """Tests for LanguageChecker dataclass."""

    def test_stores_func_and_metadata(self):
        """Should store function, scope, and project markers."""

        def dummy_checker(_path: Path, _tool_name: str | None = None) -> int:
            return 0

        checker = LanguageChecker(
            func=dummy_checker,
            scope="project",
            project_markers=["Cargo.toml"],
        )

        assert checker.func is dummy_checker
        assert checker.scope == "project"
        assert checker.project_markers == ["Cargo.toml"]


class TestLanguageCheckerDecorator:
    """Tests for language_checker decorator."""

    def test_registers_single_extension(self, clean_registry: None):
        """Should register function for single extension."""

        @language_checker([".test"])
        def test_checker(_path: Path, _tool_name: str | None = None) -> int:
            return 0

        assert ".test" in _registry
        assert _registry[".test"].func is test_checker

    def test_registers_multiple_extensions(self, clean_registry: None):
        """Should register function for multiple extensions."""

        @language_checker([".a", ".b", ".c"])
        def multi_checker(_path: Path, _tool_name: str | None = None) -> int:
            return 0

        assert ".a" in _registry
        assert ".b" in _registry
        assert ".c" in _registry
        assert _registry[".a"].func is multi_checker

    def test_normalizes_extensions_to_lowercase(self, clean_registry: None):
        """Should normalize extensions to lowercase."""

        @language_checker([".PY", ".Py", ".pY"])
        def py_checker(_path: Path, _tool_name: str | None = None) -> int:
            return 0

        assert ".py" in _registry
        # All should map to same checker
        assert _registry[".py"].func is py_checker

    def test_default_scope_is_file(self, clean_registry: None):
        """Default scope should be 'file'."""

        @language_checker([".xyz"])
        def _file_checker(_path: Path, _tool_name: str | None = None) -> int:
            return 0

        assert _registry[".xyz"].scope == "file"

    def test_custom_scope_and_markers(self, clean_registry: None):
        """Should store custom scope and project markers."""

        @language_checker([".rs"], scope="project", project_markers=["Cargo.toml"])
        def _rust_checker(_path: Path, _tool_name: str | None = None) -> int:
            return 0

        assert _registry[".rs"].scope == "project"
        assert _registry[".rs"].project_markers == ["Cargo.toml"]

    def test_returns_original_function(self, clean_registry: None):
        """Decorator should return the original function unchanged."""

        @language_checker([".fn"])
        def original_func(_path: Path, _tool_name: str | None = None) -> int:
            return 42

        # Function should still work normally
        assert original_func(Path("/test"), None) == 42


class TestGetChecker:
    """Tests for get_checker function."""

    def test_returns_checker_for_registered_extension(self, clean_registry: None):
        """Should return checker for registered extension."""

        @language_checker([".reg"])
        def registered_checker(_path: Path, _tool_name: str | None = None) -> int:
            return 0

        result = get_checker(".reg")

        assert result is not None
        assert result.func is registered_checker

    def test_returns_none_for_unregistered_extension(self, clean_registry: None):
        """Should return None for unregistered extension."""
        result = get_checker(".unknown")

        assert result is None

    def test_normalizes_query_to_lowercase(self, clean_registry: None):
        """Should find checker regardless of query case."""

        @language_checker([".mix"])
        def _mix_checker(_path: Path, _tool_name: str | None = None) -> int:
            return 0

        assert get_checker(".MIX") is not None
        assert get_checker(".Mix") is not None
        assert get_checker(".mix") is not None
