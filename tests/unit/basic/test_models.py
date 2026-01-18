"""Tests for basic.models structured output.

These tests verify that the WorkflowOutput model correctly:
1. Validates required fields (research_doc_path, status, summary)
2. Handles optional fields for conditional workflow paths
3. Enforces field types (can't hallucinate invalid values)
"""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from basic.models import WorkflowOutput


class TestWorkflowOutput:
    """Tests for WorkflowOutput structured output model."""

    def test_minimal_valid_output(self) -> None:
        """Test that minimal required fields are enforced."""
        output = WorkflowOutput(
            research_doc_path="/path/to/research.md",
            research_summary="Found relevant patterns",
            needs_implementation=False,
            status="no_changes_needed",
            summary="Research complete, no implementation required",
        )
        assert output.research_doc_path == "/path/to/research.md"
        assert output.needs_implementation is False
        assert output.status == "no_changes_needed"
        # Optional fields default to None/empty
        assert output.plan_doc_path is None
        assert output.commit_hash is None
        assert output.files_changed == []

    def test_full_workflow_output(self) -> None:
        """Test output with all optional fields filled."""
        output = WorkflowOutput(
            research_doc_path="/path/to/research.md",
            research_summary="Found issues to fix",
            needs_implementation=True,
            plan_doc_path="/path/to/plan.md",
            review_approved=True,
            review_iteration_count=2,
            files_changed=["src/main.py", "tests/test_main.py"],
            commit_hash="abc1234",
            status="complete",
            summary="Implemented and committed changes",
        )
        assert output.needs_implementation is True
        assert output.plan_doc_path == "/path/to/plan.md"
        assert output.review_approved is True
        assert output.review_iteration_count == 2
        assert len(output.files_changed) == 2
        assert output.commit_hash == "abc1234"
        assert output.status == "complete"

    def test_missing_required_field_raises(self) -> None:
        """Test that missing required fields raise ValidationError."""
        with pytest.raises(ValidationError) as exc_info:
            WorkflowOutput(
                # Missing: research_doc_path, research_summary, needs_implementation
                status="complete",
                summary="Done",
            )
        errors = exc_info.value.errors()
        missing_fields = {e["loc"][0] for e in errors}
        assert "research_doc_path" in missing_fields
        assert "research_summary" in missing_fields
        assert "needs_implementation" in missing_fields

    def test_invalid_status_raises(self) -> None:
        """Test that invalid status literal raises ValidationError."""
        with pytest.raises(ValidationError) as exc_info:
            WorkflowOutput(
                research_doc_path="/path/to/research.md",
                research_summary="Summary",
                needs_implementation=False,
                status="invalid_status",  # type: ignore[arg-type]
                summary="Done",
            )
        errors = exc_info.value.errors()
        assert any("status" in str(e) for e in errors)

    def test_json_schema_generation(self) -> None:
        """Test that model generates valid JSON schema for SDK."""
        schema = WorkflowOutput.model_json_schema()

        # Required fields must be in schema
        assert "research_doc_path" in schema["properties"]
        assert "status" in schema["properties"]
        assert "summary" in schema["properties"]

        # Status should have enum constraint
        status_schema = schema["properties"]["status"]
        assert (
            "enum" in status_schema
            or "const" in status_schema
            or "anyOf" in status_schema
        )

    def test_conditional_path_no_implementation(self) -> None:
        """Test early exit path when no implementation needed."""
        output = WorkflowOutput(
            research_doc_path="/research.md",
            research_summary="Already implemented",
            needs_implementation=False,
            status="no_changes_needed",
            summary="No work needed",
        )
        # Plan/review/execute fields should be None/empty
        assert output.plan_doc_path is None
        assert output.review_approved is None
        assert output.files_changed == []
        assert output.commit_hash is None

    def test_conditional_path_no_commit(self) -> None:
        """Test path where implementation made no changes."""
        output = WorkflowOutput(
            research_doc_path="/research.md",
            research_summary="Minor issue",
            needs_implementation=True,
            plan_doc_path="/plan.md",
            review_approved=True,
            files_changed=[],  # No files changed
            status="complete",
            summary="Reviewed but no changes needed",
        )
        # commit_hash should be None when no files changed
        assert output.commit_hash is None
        assert output.files_changed == []


class TestForcingFunction:
    """Tests demonstrating the 'forcing function' behavior.

    The orchestrator cannot hallucinate values for these fields because
    they must come from actual tool execution:
    - research_doc_path: Must be a real file from research_codebase
    - plan_doc_path: Must be a real file from create_plan
    - commit_hash: Must be a real git hash from commit_changes
    """

    def test_model_validates_types(self) -> None:
        """Test that model enforces correct types."""
        # Can't use wrong types
        with pytest.raises(ValidationError):
            WorkflowOutput(
                research_doc_path=123,  # type: ignore[arg-type]
                research_summary="Summary",
                needs_implementation="yes",  # type: ignore[arg-type]
                status="complete",
                summary="Done",
            )

    def test_files_changed_must_be_list(self) -> None:
        """Test that files_changed must be a list of strings."""
        with pytest.raises(ValidationError):
            WorkflowOutput(
                research_doc_path="/research.md",
                research_summary="Summary",
                needs_implementation=True,
                files_changed="not a list",  # type: ignore[arg-type]
                status="complete",
                summary="Done",
            )

    def test_model_from_json(self) -> None:
        """Test deserializing from JSON (as SDK would provide)."""
        json_data = {
            "research_doc_path": "/path/to/research.md",
            "research_summary": "Found patterns",
            "needs_implementation": True,
            "plan_doc_path": "/path/to/plan.md",
            "review_approved": True,
            "review_iteration_count": 1,
            "files_changed": ["src/file.py"],
            "commit_hash": "abc1234",
            "status": "complete",
            "summary": "Done",
        }
        output = WorkflowOutput.model_validate(json_data)
        assert output.research_doc_path == "/path/to/research.md"
        assert output.commit_hash == "abc1234"
        assert output.files_changed == ["src/file.py"]
