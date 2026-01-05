"""Tests for workflow type system."""

from pathlib import Path

import pytest
from pydantic import ValidationError

from π.workflow.types import (
    DesignResult,
    ExecuteResult,
    PlanDocPath,
    ResearchDocPath,
    ResearchResult,
)


def _get_validation_error_message(
    exc_info: pytest.ExceptionInfo[ValidationError],
) -> str:
    """Extract the original error message from Pydantic ValidationError.

    Pydantic wraps ValueError from field_validators into ValidationError.
    The original message is in exc_info.value.errors()[0]['ctx']['error'].
    """
    errors = exc_info.value.errors()
    if errors and "ctx" in errors[0] and "error" in errors[0]["ctx"]:
        return str(errors[0]["ctx"]["error"])
    # Fallback to string representation
    return str(exc_info.value)


class TestResearchDocPath:
    """Tests for ResearchDocPath validation."""

    def test_valid_research_path(self, tmp_path: Path) -> None:
        """Valid research path should pass validation."""
        # Create valid research doc
        research_dir = tmp_path / "thoughts/shared/research"
        research_dir.mkdir(parents=True)
        doc = research_dir / "2026-01-05-test.md"
        doc.write_text("# Test")

        result = ResearchDocPath(path=str(doc))
        assert result.doc_type == "research"
        assert doc.name in result.path

    def test_rejects_plan_directory(self, tmp_path: Path) -> None:
        """Should reject paths in plans directory."""
        plans_dir = tmp_path / "thoughts/shared/plans"
        plans_dir.mkdir(parents=True)
        doc = plans_dir / "2026-01-05-test.md"
        doc.write_text("# Test")

        with pytest.raises(ValidationError) as exc_info:
            ResearchDocPath(path=str(doc))
        error_msg = _get_validation_error_message(exc_info)
        assert "must be in thoughts/shared/research" in error_msg

    def test_rejects_nonexistent_file(self) -> None:
        """Should reject nonexistent files."""
        with pytest.raises(ValidationError) as exc_info:
            ResearchDocPath(path="thoughts/shared/research/nonexistent.md")
        error_msg = _get_validation_error_message(exc_info)
        assert "does not exist" in error_msg

    def test_rejects_wrong_extension(self, tmp_path: Path) -> None:
        """Should reject non-markdown files."""
        research_dir = tmp_path / "thoughts/shared/research"
        research_dir.mkdir(parents=True)
        doc = research_dir / "2026-01-05-test.txt"
        doc.write_text("Test")

        with pytest.raises(ValidationError) as exc_info:
            ResearchDocPath(path=str(doc))
        error_msg = _get_validation_error_message(exc_info)
        assert "must be markdown" in error_msg

    def test_rejects_missing_date_prefix(self, tmp_path: Path) -> None:
        """Should reject files without date prefix."""
        research_dir = tmp_path / "thoughts/shared/research"
        research_dir.mkdir(parents=True)
        doc = research_dir / "no-date-test.md"
        doc.write_text("# Test")

        with pytest.raises(ValidationError) as exc_info:
            ResearchDocPath(path=str(doc))
        error_msg = _get_validation_error_message(exc_info)
        assert "must start with YYYY-MM-DD" in error_msg


class TestPlanDocPath:
    """Tests for PlanDocPath validation."""

    def test_valid_plan_path(self, tmp_path: Path) -> None:
        """Valid plan path should pass validation."""
        plans_dir = tmp_path / "thoughts/shared/plans"
        plans_dir.mkdir(parents=True)
        doc = plans_dir / "2026-01-05-test.md"
        doc.write_text("# Test")

        result = PlanDocPath(path=str(doc))
        assert result.doc_type == "plan"

    def test_rejects_research_directory(self, tmp_path: Path) -> None:
        """Should reject paths in research directory."""
        research_dir = tmp_path / "thoughts/shared/research"
        research_dir.mkdir(parents=True)
        doc = research_dir / "2026-01-05-test.md"
        doc.write_text("# Test")

        with pytest.raises(ValidationError) as exc_info:
            PlanDocPath(path=str(doc))
        error_msg = _get_validation_error_message(exc_info)
        assert "must be in thoughts/shared/plans" in error_msg

    def test_rejects_missing_date_prefix(self, tmp_path: Path) -> None:
        """Should reject files without date prefix."""
        plans_dir = tmp_path / "thoughts/shared/plans"
        plans_dir.mkdir(parents=True)
        doc = plans_dir / "no-date-test.md"
        doc.write_text("# Test")

        with pytest.raises(ValidationError) as exc_info:
            PlanDocPath(path=str(doc))
        error_msg = _get_validation_error_message(exc_info)
        assert "must start with YYYY-MM-DD" in error_msg


class TestResultModels:
    """Tests for result model structures."""

    def test_research_result_with_needs_implementation(self, tmp_path: Path) -> None:
        """ResearchResult should hold needs_implementation flag."""
        research_dir = tmp_path / "thoughts/shared/research"
        research_dir.mkdir(parents=True)
        doc = research_dir / "2026-01-05-test.md"
        doc.write_text("# Test")

        research_doc = ResearchDocPath(path=str(doc))
        result = ResearchResult(
            research_doc=research_doc,
            summary="Test summary",
            needs_implementation=False,
            reason="Already exists",
        )

        assert result.needs_implementation is False
        assert result.reason == "Already exists"

    def test_execute_result_defaults(self) -> None:
        """ExecuteResult should have correct defaults."""
        result = ExecuteResult(status="success")
        assert result.files_changed == []
        assert result.commit_hash is None

    def test_design_result_defaults(self, tmp_path: Path) -> None:
        """DesignResult should have correct defaults."""
        plans_dir = tmp_path / "thoughts/shared/plans"
        plans_dir.mkdir(parents=True)
        doc = plans_dir / "2026-01-05-test.md"
        doc.write_text("# Test")

        plan_doc = PlanDocPath(path=str(doc))
        result = DesignResult(
            plan_doc=plan_doc,
            summary="Test summary",
        )

        assert result.estimated_changes == 0
