"""Shared pytest fixtures for π test suite."""

import logging
from pathlib import Path
from typing import Generator
from unittest.mock import MagicMock

import pytest


@pytest.fixture
def clean_logging() -> Generator[None, None, None]:
    """Reset logging state before and after tests."""
    # Store original state
    original_handlers = logging.root.handlers[:]
    original_level = logging.root.level
    pi_logger = logging.getLogger("π")
    original_pi_level = pi_logger.level
    original_pi_handlers = pi_logger.handlers[:]

    # Clean state for test
    for handler in logging.root.handlers[:]:
        logging.root.removeHandler(handler)
    logging.root.setLevel(logging.WARNING)

    yield

    # Restore original state
    for handler in logging.root.handlers[:]:
        logging.root.removeHandler(handler)
    for handler in original_handlers:
        logging.root.addHandler(handler)
    logging.root.setLevel(original_level)

    pi_logger.handlers = original_pi_handlers
    pi_logger.setLevel(original_pi_level)


@pytest.fixture
def clean_registry() -> Generator[None, None, None]:
    """Reset the checker registry before and after tests."""
    from π.hooks.registry import _registry

    # Store original state
    original_registry = _registry.copy()

    yield

    # Restore original state
    _registry.clear()
    _registry.update(original_registry)


@pytest.fixture
def mock_console(mocker: MagicMock) -> MagicMock:
    """Mock the Rich console to prevent output during tests."""
    return mocker.patch("π.hooks.utils.console")


@pytest.fixture
def temp_project(tmp_path: Path) -> Path:
    """Create a temporary project structure with common files."""
    # Create pyproject.toml
    (tmp_path / "pyproject.toml").write_text('[project]\nname = "test"\n')

    # Create source directory
    src = tmp_path / "src"
    src.mkdir()
    (src / "__init__.py").touch()

    return tmp_path


@pytest.fixture
def temp_command_dir(tmp_path: Path) -> Path:
    """Create a temporary command directory with sample commands."""
    cmd_dir = tmp_path / ".claude" / "commands"
    cmd_dir.mkdir(parents=True)

    # Create numbered command files
    (cmd_dir / "1_research_codebase.md").write_text(
        "# Research\nResearch the codebase."
    )
    (cmd_dir / "2_create_plan.md").write_text("# Plan\nCreate a plan.")
    (cmd_dir / "3_implement_plan.md").write_text("# Implement\nImplement the plan.")

    return cmd_dir
