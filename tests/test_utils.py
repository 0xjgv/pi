"""Tests for π.utils module."""

import logging
from pathlib import Path

from π.utils import (
    create_workflow_dir,
    generate_workflow_id,
    setup_logging,
)


def test_generate_workflow_id_is_uuid():
    """Workflow IDs should be valid UUIDs."""
    workflow_id = generate_workflow_id()
    assert len(workflow_id) == 36
    assert workflow_id.count("-") == 4


def test_generate_workflow_id_is_unique():
    """Each call should produce a unique ID."""
    ids = [generate_workflow_id() for _ in range(100)]
    assert len(set(ids)) == 100


def test_create_workflow_dir(tmp_path: Path):
    """Should create nested directory structure."""
    workflow_id = "test-workflow-123"
    result = create_workflow_dir(tmp_path, workflow_id)

    assert result == tmp_path / workflow_id
    assert result.exists()
    assert result.is_dir()


def test_setup_logging_verbose():
    """Verbose mode should set DEBUG level."""
    # Reset logging before test
    for handler in logging.root.handlers[:]:
        logging.root.removeHandler(handler)
    logging.root.setLevel(logging.WARNING)

    setup_logging(verbose=True)
    # basicConfig sets the level on the root logger
    assert logging.getLogger().level == logging.DEBUG


def test_setup_logging_default():
    """Default mode should set INFO level."""
    # Reset logging before test
    for handler in logging.root.handlers[:]:
        logging.root.removeHandler(handler)
    logging.root.setLevel(logging.WARNING)

    setup_logging(verbose=False)
    # Check root logger since basicConfig sets it there
    assert logging.getLogger().level == logging.INFO
