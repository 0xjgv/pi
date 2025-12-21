"""Tests for π.router (ObjectiveRouter DSPy Module)."""

from collections.abc import Generator
from unittest.mock import MagicMock, patch

import pytest

from π.config import Provider
from π.router import ExecutionMode, ObjectiveRouter, classify_objective


class TestExecutionMode:
    """Tests for ExecutionMode enum."""

    def test_simple_value(self):
        """SIMPLE should have value 'simple'."""
        assert ExecutionMode.SIMPLE == "simple"
        assert ExecutionMode.SIMPLE.value == "simple"

    def test_workflow_value(self):
        """WORKFLOW should have value 'workflow'."""
        assert ExecutionMode.WORKFLOW == "workflow"
        assert ExecutionMode.WORKFLOW.value == "workflow"

    def test_str_enum_behavior(self):
        """Should behave as StrEnum for string comparisons."""
        assert ExecutionMode("simple") == ExecutionMode.SIMPLE
        assert ExecutionMode("workflow") == ExecutionMode.WORKFLOW


class TestObjectiveRouterSignature:
    """Tests for ObjectiveRouter signature definition."""

    def test_is_dspy_signature(self):
        """Should be a DSPy Signature subclass."""
        import dspy

        assert issubclass(ObjectiveRouter, dspy.Signature)

    def test_has_docstring(self):
        """Should have a descriptive docstring."""
        assert ObjectiveRouter.__doc__ is not None
        assert "simple" in ObjectiveRouter.__doc__.lower()
        assert "workflow" in ObjectiveRouter.__doc__.lower()


class TestClassifyObjective:
    """Tests for classify_objective function."""

    @pytest.fixture
    def mock_dspy(self) -> Generator[MagicMock, None, None]:
        """Mock dspy module."""
        with patch("π.router.dspy") as mock:
            yield mock

    @pytest.fixture
    def mock_config(self) -> Generator[MagicMock, None, None]:
        """Mock config functions."""
        with (
            patch("π.router.get_model") as mock_get_model,
            patch("π.router.configure_dspy") as mock_configure,
        ):
            mock_get_model.return_value = "claude-haiku-4-5-20251001"
            yield {"get_model": mock_get_model, "configure_dspy": mock_configure}

    def test_uses_low_tier_model(self, mock_dspy: MagicMock, mock_config: dict):
        """Router should always use low-tier model for fast classification."""
        mock_dspy.ChainOfThought.return_value.return_value = MagicMock(
            mode="simple", reasoning="Quick task"
        )
        logger = MagicMock()

        classify_objective("test", provider=Provider.Claude, logger=logger)

        mock_config["get_model"].assert_called_once_with(
            provider=Provider.Claude, tier="low"
        )

    def test_returns_simple_mode(self, mock_dspy: MagicMock, mock_config: dict):
        """Should return SIMPLE when router classifies as simple."""
        mock_dspy.ChainOfThought.return_value.return_value = MagicMock(
            mode="simple", reasoning="Single file change"
        )
        logger = MagicMock()

        result = classify_objective(
            "Fix typo in README", provider=Provider.Claude, logger=logger
        )

        assert result == ExecutionMode.SIMPLE

    def test_returns_workflow_mode(self, mock_dspy: MagicMock, mock_config: dict):
        """Should return WORKFLOW when router classifies as workflow."""
        mock_dspy.ChainOfThought.return_value.return_value = MagicMock(
            mode="workflow", reasoning="Multi-file implementation"
        )
        logger = MagicMock()

        result = classify_objective(
            "Implement OAuth2 authentication",
            provider=Provider.Claude,
            logger=logger,
        )

        assert result == ExecutionMode.WORKFLOW

    def test_uses_chain_of_thought(self, mock_dspy: MagicMock, mock_config: dict):
        """Should use dspy.ChainOfThought for reasoning."""
        mock_dspy.ChainOfThought.return_value.return_value = MagicMock(
            mode="simple", reasoning="test"
        )
        logger = MagicMock()

        classify_objective("test", provider=Provider.Claude, logger=logger)

        mock_dspy.ChainOfThought.assert_called_once_with(ObjectiveRouter)

    def test_passes_objective_to_router(self, mock_dspy: MagicMock, mock_config: dict):
        """Should pass objective to the router."""
        mock_router = MagicMock()
        mock_router.return_value = MagicMock(mode="simple", reasoning="test")
        mock_dspy.ChainOfThought.return_value = mock_router
        logger = MagicMock()

        classify_objective(
            "Implement feature X", provider=Provider.Claude, logger=logger
        )

        mock_router.assert_called_once_with(objective="Implement feature X")

    def test_logs_router_decision(self, mock_dspy: MagicMock, mock_config: dict):
        """Should log the router's decision and reasoning."""
        mock_dspy.ChainOfThought.return_value.return_value = MagicMock(
            mode="workflow", reasoning="Complex multi-step implementation task"
        )
        logger = MagicMock()

        classify_objective("test", provider=Provider.Claude, logger=logger)

        logger.debug.assert_called()

    def test_respects_provider_parameter(self, mock_dspy: MagicMock, mock_config: dict):
        """Should use specified provider for model selection."""
        mock_dspy.ChainOfThought.return_value.return_value = MagicMock(
            mode="simple", reasoning="test"
        )
        logger = MagicMock()

        classify_objective("test", provider=Provider.Antigravity, logger=logger)

        mock_config["get_model"].assert_called_once_with(
            provider=Provider.Antigravity, tier="low"
        )
