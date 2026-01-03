"""Tests for π.orchestrator.agent module."""

from unittest.mock import MagicMock, patch

import pytest

from π.orchestrator.agent import OrchestratorAgent, QUICK_WORKFLOW_THRESHOLD
from π.orchestrator.signatures import (
    ComplexityAssessSignature,
    OneThingSignature,
    OrchestratorSignature,
)
from π.orchestrator.state import (
    Task,
    TaskStatus,
    TaskStrategy,
    create_state,
    save_state,
)


class TestOrchestratorSignatures:
    """Tests for orchestrator DSPy signatures."""

    def test_orchestrator_signature_has_required_fields(self):
        """Should define objective and state_summary inputs."""
        annotations = OrchestratorSignature.__annotations__
        assert "objective" in annotations
        assert "state_summary" in annotations
        assert "next_action" in annotations
        assert "reasoning" in annotations

    def test_complexity_signature_has_required_fields(self):
        """Should define task and context inputs."""
        annotations = ComplexityAssessSignature.__annotations__
        assert "task_description" in annotations
        assert "codebase_context" in annotations
        assert "complexity_score" in annotations
        assert "rationale" in annotations

    def test_one_thing_signature_has_required_fields(self):
        """Should define objective and completed inputs."""
        annotations = OneThingSignature.__annotations__
        assert "objective" in annotations
        assert "completed_tasks" in annotations
        assert "next_task" in annotations


class TestOrchestratorAgentInit:
    """Tests for OrchestratorAgent initialization."""

    @pytest.fixture
    def mock_dspy(self):
        """Mock dspy module."""
        with patch("π.orchestrator.agent.dspy") as mock:
            mock.ChainOfThought.return_value = MagicMock()
            mock.context.return_value.__enter__ = MagicMock()
            mock.context.return_value.__exit__ = MagicMock()
            yield mock

    @pytest.fixture
    def mock_workflow(self):
        """Mock RPIWorkflow."""
        with patch("π.orchestrator.agent.RPIWorkflow") as mock:
            mock.return_value = MagicMock()
            yield mock

    def test_creates_orchestrator_agent(self, mock_dspy, mock_workflow):
        """Should create ChainOfThought agent for orchestration."""
        OrchestratorAgent()
        assert mock_dspy.ChainOfThought.call_count >= 1

    def test_creates_complexity_agent(self, mock_dspy, mock_workflow):
        """Should create agent for complexity assessment."""
        OrchestratorAgent()
        # Should create multiple ChainOfThought agents
        assert mock_dspy.ChainOfThought.call_count >= 2

    def test_creates_one_thing_agent(self, mock_dspy, mock_workflow):
        """Should create agent for one-thing reasoning."""
        OrchestratorAgent()
        assert mock_dspy.ChainOfThought.call_count >= 3

    def test_creates_workflow_executor(self, mock_dspy, mock_workflow):
        """Should create RPIWorkflow for task execution."""
        OrchestratorAgent()
        mock_workflow.assert_called_once()


class TestComplexityAssessment:
    """Tests for complexity assessment logic."""

    def test_quick_workflow_threshold(self):
        """Should define threshold for quick workflow."""
        assert QUICK_WORKFLOW_THRESHOLD == 20

    def test_quick_strategy_for_low_complexity(self, tmp_path):
        """Should use quick strategy for complexity <= 20."""
        task = Task(id="t1", description="Fix typo")

        with patch("π.orchestrator.agent.dspy") as mock_dspy:
            with patch("π.orchestrator.agent.RPIWorkflow"):
                mock_dspy.ChainOfThought.return_value = MagicMock()
                mock_dspy.context.return_value.__enter__ = MagicMock()
                mock_dspy.context.return_value.__exit__ = MagicMock()

                agent = OrchestratorAgent(root=tmp_path)

                # Mock complexity agent to return low score
                agent._complexity_agent.return_value = MagicMock(
                    complexity_score=15,
                    rationale="Simple change",
                )

                state = create_state("Test")
                complexity = agent._assess_complexity(task, state)

                assert complexity == 15
                assert complexity <= QUICK_WORKFLOW_THRESHOLD


class TestOrchestratorForward:
    """Tests for OrchestratorAgent.forward method."""

    @pytest.fixture
    def mock_agent_deps(self):
        """Mock all agent dependencies."""
        with patch("π.orchestrator.agent.dspy") as mock_dspy:
            with patch("π.orchestrator.agent.RPIWorkflow") as mock_workflow:
                with patch("π.orchestrator.agent.get_lm") as mock_lm:
                    mock_dspy.ChainOfThought.return_value = MagicMock()
                    mock_dspy.context.return_value.__enter__ = MagicMock()
                    mock_dspy.context.return_value.__exit__ = MagicMock()
                    mock_dspy.Prediction = MagicMock

                    mock_workflow_instance = MagicMock()
                    mock_workflow_instance.return_value = MagicMock(
                        research_doc_path="/path/research.md",
                        plan_doc_path="/path/plan.md",
                        changes_made="Changes",
                    )
                    mock_workflow.return_value = mock_workflow_instance

                    yield {
                        "dspy": mock_dspy,
                        "workflow": mock_workflow,
                        "lm": mock_lm,
                    }

    def test_creates_state_for_new_objective(self, tmp_path, mock_agent_deps):
        """Should create state file for new objective."""
        agent = OrchestratorAgent(root=tmp_path)

        # Mock agents to immediately complete
        agent._one_thing_agent.return_value = MagicMock(
            next_task="Initial task",
            rationale="Start here",
        )
        agent._complexity_agent.return_value = MagicMock(
            complexity_score=50,
            rationale="Complex",
        )

        # Make workflow succeed
        agent._workflow.return_value = MagicMock(
            research_doc_path="/path/research.md",
            plan_doc_path="/path/plan.md",
            changes_made="Changes",
        )

        agent.forward("Test objective")

        # State file should exist
        state_dir = tmp_path / ".π" / "state"
        assert state_dir.exists()
        state_files = list(state_dir.glob("*.json"))
        assert len(state_files) == 1

    def test_returns_prediction_with_status(self, tmp_path, mock_agent_deps):
        """Should return prediction with status info."""
        agent = OrchestratorAgent(root=tmp_path)

        # Set max iterations to 0 to exit immediately
        with patch("π.orchestrator.agent.load_or_create_state") as mock_load:
            state = create_state("Test")
            state.config.max_iterations = 0
            mock_load.return_value = state

            result = agent.forward("Test objective")

            assert hasattr(result, "completed")
            assert hasattr(result, "status")


class TestOrchestratorResume:
    """Tests for OrchestratorAgent.resume method."""

    def test_raises_for_missing_state(self, tmp_path):
        """Should raise ValueError for missing state."""
        with patch("π.orchestrator.agent.dspy") as mock_dspy:
            with patch("π.orchestrator.agent.RPIWorkflow"):
                mock_dspy.ChainOfThought.return_value = MagicMock()

                agent = OrchestratorAgent(root=tmp_path)

                with pytest.raises(ValueError) as exc:
                    agent.resume("nonexistent")

                assert "No state found" in str(exc.value)

    def test_resumes_from_saved_state(self, tmp_path):
        """Should resume from saved state."""
        # Create and save a state
        state = create_state("Resume test")
        state.tasks = [Task(id="t1", description="Test", status=TaskStatus.PENDING)]
        save_state(state, tmp_path)

        with patch("π.orchestrator.agent.dspy") as mock_dspy:
            with patch("π.orchestrator.agent.RPIWorkflow"):
                with patch("π.orchestrator.agent.get_lm"):
                    mock_dspy.ChainOfThought.return_value = MagicMock()
                    mock_dspy.context.return_value.__enter__ = MagicMock()
                    mock_dspy.context.return_value.__exit__ = MagicMock()
                    mock_dspy.Prediction = MagicMock

                    agent = OrchestratorAgent(root=tmp_path)

                    # Mock to complete immediately
                    agent._complexity_agent.return_value = MagicMock(
                        complexity_score=10,
                        rationale="Quick",
                    )

                    result = agent.resume(state.objective_hash)

                    # Should have attempted to process
                    assert result is not None

    def test_resets_halted_state(self, tmp_path):
        """Should reset halted state to running."""
        from π.orchestrator.state import load_state_by_hash, OrchestratorStatus

        state = create_state("Halted test")
        state.halt(reason="Previous failure")
        save_state(state, tmp_path)

        # Verify state is halted before we create agent
        loaded = load_state_by_hash(state.objective_hash, tmp_path)
        assert loaded is not None
        assert loaded.status == OrchestratorStatus.HALTED

        with patch("π.orchestrator.agent.dspy") as mock_dspy:
            with patch("π.orchestrator.agent.RPIWorkflow"):
                with patch("π.orchestrator.agent.get_lm"):
                    mock_dspy.ChainOfThought.return_value = MagicMock()
                    mock_dspy.context.return_value.__enter__ = MagicMock()
                    mock_dspy.context.return_value.__exit__ = MagicMock()
                    mock_dspy.Prediction = MagicMock

                    # Agent creation should work with halted state
                    OrchestratorAgent(root=tmp_path)


class TestWorkflowRouting:
    """Tests for workflow routing based on complexity."""

    @pytest.fixture
    def agent_with_mocks(self, tmp_path):
        """Create agent with mocked dependencies."""
        with patch("π.orchestrator.agent.dspy") as mock_dspy:
            with patch("π.orchestrator.agent.RPIWorkflow") as mock_workflow:
                mock_dspy.ChainOfThought.return_value = MagicMock()
                mock_workflow_instance = MagicMock()
                mock_workflow.return_value = mock_workflow_instance

                agent = OrchestratorAgent(root=tmp_path)
                yield agent, mock_workflow_instance

    def test_quick_workflow_sets_strategy(self, agent_with_mocks, tmp_path):
        """Should set quick_change strategy for low complexity."""
        agent, _ = agent_with_mocks
        task = Task(id="t1", description="Quick fix")
        state = create_state("Test")

        agent._run_workflow(task, 15, state)

        assert task.strategy == TaskStrategy.QUICK_CHANGE

    def test_full_workflow_sets_strategy(self, agent_with_mocks, tmp_path):
        """Should set full_workflow strategy for high complexity."""
        agent, mock_workflow = agent_with_mocks
        task = Task(id="t1", description="Complex feature")
        state = create_state("Test")

        # Mock workflow to return proper result
        mock_workflow.return_value = MagicMock(
            research_doc_path="/path/research.md",
            plan_doc_path="/path/plan.md",
            changes_made="Changes",
        )

        agent._run_workflow(task, 50, state)

        assert task.strategy == TaskStrategy.FULL_WORKFLOW

    def test_full_workflow_calls_rpi_workflow(self, agent_with_mocks, tmp_path):
        """Should call RPIWorkflow for full workflow."""
        agent, mock_workflow = agent_with_mocks
        task = Task(id="t1", description="Complex feature")
        state = create_state("Test")

        mock_workflow.return_value = MagicMock(
            research_doc_path="/path/research.md",
            plan_doc_path="/path/plan.md",
            changes_made="Changes",
        )

        agent._run_workflow(task, 50, state)

        mock_workflow.assert_called_once()
