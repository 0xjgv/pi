"""Integration tests for workflow execution."""

from pathlib import Path
from unittest.mock import patch

import pytest

from π.workflow import run_workflow


@pytest.fixture
def mock_cwd(tmp_path):
    """Create temporary working directory with required structure."""
    (tmp_path / "thoughts").mkdir()
    (tmp_path / ".logs").mkdir()
    return tmp_path


@pytest.fixture
def sample_prompt():
    """Sample workflow prompt."""
    return "Research the authentication system and create an implementation plan"


@pytest.mark.asyncio
async def test_workflow_basic_execution(mock_cwd, sample_prompt):
    """Test basic workflow execution through all stages."""

    # Mock run_stage to return successful results
    from π.stages import StageResult

    def mock_run_stage(stage_name, args, cwd, retry=True):
        """Mock stage execution."""
        result = StageResult(
            status="success",
            result=f"Mock result from {stage_name}",
            document=str(mock_cwd / "thoughts" / f"{stage_name}.md") if stage_name in ["research", "plan"] else None,
            stats={"total_tools": 10, "errors": 0, "tool_counts": {"Read": 5}}
        )
        # Create mock document files
        if result.document:
            Path(result.document).touch()
        return (0, result)

    with patch("π.workflow.run_stage", side_effect=mock_run_stage):
        result = await run_workflow(prompt=sample_prompt, cwd=mock_cwd)

        # Verify workflow completed
        assert result is not None
        assert "validate" in result.lower() or "Mock result" in result


@pytest.mark.asyncio
async def test_workflow_handles_stage_failure(mock_cwd, sample_prompt):
    """Test workflow stops on stage failure."""

    def mock_run_stage_with_failure(stage_name, args, cwd, retry=True):
        """Mock stage that fails on plan stage."""
        from π.stages import StageResult

        if stage_name == "plan":
            # Simulate failure
            return (1, None)

        result = StageResult(
            status="success",
            result=f"Mock result from {stage_name}",
            document=str(mock_cwd / "thoughts" / f"{stage_name}.md") if stage_name == "research" else None,
            stats={"total_tools": 10, "errors": 0, "tool_counts": {"Read": 5}}
        )
        if result.document:
            Path(result.document).touch()
        return (0, result)

    with patch("π.workflow.run_stage", side_effect=mock_run_stage_with_failure):
        result = await run_workflow(prompt=sample_prompt, cwd=mock_cwd)

        # Verify workflow stopped
        assert result is None


@pytest.mark.asyncio
async def test_workflow_creates_directories(mock_cwd, sample_prompt):
    """Test workflow creates thoughts and log directories."""

    from π.stages import StageResult

    def mock_run_stage(stage_name, args, cwd, retry=True):
        result = StageResult(
            status="success",
            result="Mock result",
            document=None,
            stats={"total_tools": 1, "errors": 0, "tool_counts": {}}
        )
        return (0, result)

    with patch("π.workflow.run_stage", side_effect=mock_run_stage):
        await run_workflow(prompt=sample_prompt, cwd=mock_cwd)

        # Verify directories exist
        assert (mock_cwd / "thoughts").exists()
        assert (mock_cwd / ".logs").exists()

        # Verify workflow-specific directories were created
        thoughts_dirs = list((mock_cwd / "thoughts").iterdir())
        log_dirs = list((mock_cwd / ".logs").iterdir())

        assert len(thoughts_dirs) > 0
        assert len(log_dirs) > 0


@pytest.mark.asyncio
async def test_workflow_passes_data_between_stages(mock_cwd, sample_prompt):
    """Test data flows correctly between stages."""

    from π.stages import StageResult

    stage_calls = []

    def mock_run_stage(stage_name, args, cwd, retry=True):
        """Track stage calls and arguments."""
        stage_calls.append({
            "stage": stage_name,
            "args": args
        })

        result = StageResult(
            status="success",
            result=f"Result from {stage_name}",
            document=str(mock_cwd / "thoughts" / f"{stage_name}.md") if stage_name in ["research", "plan"] else None,
            stats={"total_tools": 1, "errors": 0, "tool_counts": {}}
        )
        if result.document:
            Path(result.document).touch()
        return (0, result)

    with patch("π.workflow.run_stage", side_effect=mock_run_stage):
        await run_workflow(prompt=sample_prompt, cwd=mock_cwd)

        # Verify stages were called in order
        expected_stages = ["research", "plan", "review", "iterate", "implement", "commit", "validate"]
        actual_stages = [call["stage"] for call in stage_calls]
        assert actual_stages == expected_stages

        # Verify plan stage received research result
        plan_call = stage_calls[1]  # Second call is plan
        assert "Result from research" in plan_call["args"][-1]
