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

    def test_rejects_path_containing_both_dirs(self, tmp_path: Path) -> None:
        """Should reject path containing both research and plans directories."""
        # Create a contrived path that contains both directory patterns
        weird_dir = tmp_path / "thoughts/shared/research/subdir/thoughts/shared/plans"
        weird_dir.mkdir(parents=True)
        doc = weird_dir / "2026-01-05-test.md"
        doc.write_text("# Test")

        with pytest.raises(ValidationError) as exc_info:
            ResearchDocPath(path=str(doc))
        error_msg = _get_validation_error_message(exc_info)
        assert "plan document when research expected" in error_msg

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

    def test_rejects_wrong_extension(self, tmp_path: Path) -> None:
        """Should reject non-markdown files."""
        plans_dir = tmp_path / "thoughts/shared/plans"
        plans_dir.mkdir(parents=True)
        doc = plans_dir / "2026-01-05-test.txt"
        doc.write_text("Test")

        with pytest.raises(ValidationError) as exc_info:
            PlanDocPath(path=str(doc))
        error_msg = _get_validation_error_message(exc_info)
        assert "must be markdown" in error_msg

    def test_rejects_nonexistent_file(self) -> None:
        """Should reject nonexistent files."""
        with pytest.raises(ValidationError) as exc_info:
            PlanDocPath(path="thoughts/shared/plans/2026-01-05-nonexistent.md")
        error_msg = _get_validation_error_message(exc_info)
        assert "does not exist" in error_msg


class TestResultModels:
    """Tests for result model structures."""

    def test_research_result_with_needs_implementation(self, tmp_path: Path) -> None:
        """ResearchResult should hold needs_implementation and multi-doc fields."""
        research_dir = tmp_path / "thoughts/shared/research"
        research_dir.mkdir(parents=True)
        doc = research_dir / "2026-01-05-test.md"
        doc.write_text("# Test")

        research_doc = ResearchDocPath(path=str(doc))
        result = ResearchResult(
            research_docs=[research_doc],
            summaries=["Test summary"],
            needs_implementation=False,
            reason="Already exists",
        )

        assert result.needs_implementation is False
        assert result.reason == "Already exists"
        assert len(result.research_docs) == 1
        assert len(result.summaries) == 1

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


class TestDatePrefixValidation:
    """Parametrized tests for date prefix validation."""

    @pytest.mark.parametrize(
        "filename,should_pass",
        [
            ("2026-01-05-test.md", True),
            ("2025-12-31-test.md", True),
            ("2026-01-01-minimum.md", True),
            ("2026-1-5-test.md", False),  # missing zero padding
            ("26-01-05-test.md", False),  # 2-digit year
            ("no-date-test.md", False),  # no date at all
            ("test-2026-01-05.md", False),  # date not at start
        ],
    )
    def test_research_doc_date_formats(
        self, tmp_path: Path, filename: str, should_pass: bool
    ) -> None:
        """Test various date format edge cases for research docs."""
        research_dir = tmp_path / "thoughts/shared/research"
        research_dir.mkdir(parents=True)
        doc = research_dir / filename
        doc.write_text("# Test")

        if should_pass:
            result = ResearchDocPath(path=str(doc))
            assert result.path is not None
        else:
            with pytest.raises(ValidationError):
                ResearchDocPath(path=str(doc))
