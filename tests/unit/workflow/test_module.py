"""Tests for DSPy workflow module signatures."""

from __future__ import annotations

import dspy

from π.workflow.module import DesignSignature, ExecuteSignature, ResearchSignature


class TestResearchSignature:
    """Tests for ResearchSignature."""

    def test_inherits_from_dspy_signature(self) -> None:
        """ResearchSignature is a DSPy Signature."""
        assert issubclass(ResearchSignature, dspy.Signature)

    def test_has_objective_input(self) -> None:
        """ResearchSignature has objective input field."""
        fields = ResearchSignature.model_fields
        assert "objective" in fields

    def test_has_stage_output(self) -> None:
        """ResearchSignature has stage output field."""
        fields = ResearchSignature.model_fields
        assert "stage" in fields

    def test_has_research_summaries_output(self) -> None:
        """ResearchSignature has research_summaries output field."""
        fields = ResearchSignature.model_fields
        assert "research_summaries" in fields

    def test_has_research_doc_paths_output(self) -> None:
        """ResearchSignature has research_doc_paths output field."""
        fields = ResearchSignature.model_fields
        assert "research_doc_paths" in fields

    def test_has_needs_implementation_output(self) -> None:
        """ResearchSignature has needs_implementation output field."""
        fields = ResearchSignature.model_fields
        assert "needs_implementation" in fields

    def test_has_task_status_output(self) -> None:
        """ResearchSignature has task_status output field."""
        fields = ResearchSignature.model_fields
        assert "task_status" in fields

    def test_has_five_output_fields(self) -> None:
        """ResearchSignature has exactly 5 output fields."""
        output_fields = [
            "stage",
            "research_summaries",
            "research_doc_paths",
            "needs_implementation",
            "task_status",
        ]
        fields = ResearchSignature.model_fields
        for field in output_fields:
            assert field in fields


class TestDesignSignature:
    """Tests for DesignSignature."""

    def test_inherits_from_dspy_signature(self) -> None:
        """DesignSignature is a DSPy Signature."""
        assert issubclass(DesignSignature, dspy.Signature)

    def test_has_objective_input(self) -> None:
        """DesignSignature has objective input field."""
        fields = DesignSignature.model_fields
        assert "objective" in fields

    def test_has_research_doc_paths_input(self) -> None:
        """DesignSignature has research_doc_paths input field."""
        fields = DesignSignature.model_fields
        assert "research_doc_paths" in fields

    def test_has_research_summaries_input(self) -> None:
        """DesignSignature has research_summaries input field."""
        fields = DesignSignature.model_fields
        assert "research_summaries" in fields

    def test_has_three_inputs(self) -> None:
        """DesignSignature has 3 input fields."""
        input_fields = ["objective", "research_doc_paths", "research_summaries"]
        fields = DesignSignature.model_fields
        for field in input_fields:
            assert field in fields

    def test_has_stage_output(self) -> None:
        """DesignSignature has stage output field."""
        fields = DesignSignature.model_fields
        assert "stage" in fields

    def test_has_plan_doc_path_output(self) -> None:
        """DesignSignature has plan_doc_path output field."""
        fields = DesignSignature.model_fields
        assert "plan_doc_path" in fields

    def test_has_plan_summary_output(self) -> None:
        """DesignSignature has plan_summary output field."""
        fields = DesignSignature.model_fields
        assert "plan_summary" in fields


class TestExecuteSignature:
    """Tests for ExecuteSignature."""

    def test_inherits_from_dspy_signature(self) -> None:
        """ExecuteSignature is a DSPy Signature."""
        assert issubclass(ExecuteSignature, dspy.Signature)

    def test_has_plan_doc_path_input(self) -> None:
        """ExecuteSignature has plan_doc_path input field."""
        fields = ExecuteSignature.model_fields
        assert "plan_doc_path" in fields

    def test_has_objective_input(self) -> None:
        """ExecuteSignature has objective input field."""
        fields = ExecuteSignature.model_fields
        assert "objective" in fields

    def test_has_two_inputs(self) -> None:
        """ExecuteSignature has 2 input fields."""
        input_fields = ["plan_doc_path", "objective"]
        fields = ExecuteSignature.model_fields
        for field in input_fields:
            assert field in fields

    def test_has_stage_output(self) -> None:
        """ExecuteSignature has stage output field."""
        fields = ExecuteSignature.model_fields
        assert "stage" in fields

    def test_has_status_output(self) -> None:
        """ExecuteSignature has status output field."""
        fields = ExecuteSignature.model_fields
        assert "status" in fields

    def test_has_files_changed_output(self) -> None:
        """ExecuteSignature has files_changed output field."""
        fields = ExecuteSignature.model_fields
        assert "files_changed" in fields

    def test_has_commit_hash_output(self) -> None:
        """ExecuteSignature has commit_hash output field."""
        fields = ExecuteSignature.model_fields
        assert "commit_hash" in fields

    def test_has_four_outputs(self) -> None:
        """ExecuteSignature has 4 output fields."""
        output_fields = ["stage", "status", "files_changed", "commit_hash"]
        fields = ExecuteSignature.model_fields
        for field in output_fields:
            assert field in fields
