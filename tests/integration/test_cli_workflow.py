"""Integration tests for complete CLI workflows."""

from collections.abc import Generator
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from claude_agent_sdk.types import ResultMessage

from π.cli import main


class TestFullWorkflowIntegration:
    """Integration tests for complete CLI workflows."""

    @pytest.fixture(autouse=True)
    def isolate_logging(self, tmp_path: Path) -> Generator[None]:
        """Redirect logging to temporary directory."""
        mock_logs_dir = tmp_path / ".π" / "logs"
        mock_logs_dir.mkdir(parents=True)
        with patch("π.cli.main.get_logs_dir", return_value=mock_logs_dir):
            yield

    @pytest.fixture
    def mock_claude_responses(self) -> Generator[AsyncMock]:
        """Set up complete mock for Claude SDK."""
        with patch("π.workflow.bridge.ClaudeSDKClient") as mock_client_class:
            # Create async mock client
            mock_client = AsyncMock()
            mock_client_class.return_value.__aenter__.return_value = mock_client
            mock_client_class.return_value.__aexit__.return_value = None

            # Mock result message
            result_msg = MagicMock(spec=ResultMessage)
            result_msg.result = "Integration test completed"
            result_msg.session_id = "int-test-session"
            result_msg.num_turns = 2
            result_msg.duration_ms = 500
            result_msg.duration_api_ms = 400
            result_msg.total_cost_usd = 0.01
            result_msg.usage = {}

            # Set up async iterator
            async def response_iterator():
                yield result_msg

            mock_client.receive_response.return_value = response_iterator()

            yield mock_client

    @pytest.fixture
    def mock_staged_workflow(self) -> Generator[MagicMock]:
        """Mock StagedWorkflow for integration tests."""
        with patch("π.cli.main.StagedWorkflow") as mock:
            mock_instance = MagicMock()
            mock_instance.return_value = MagicMock(
                status="success",
                research_doc_path="/research.md",
                plan_doc_path="/plan.md",
                files_changed=["test.py"],
                commit_hash="abc1234",
            )
            mock.return_value = mock_instance
            yield mock

    def test_cli_initializes_and_runs(
        self,
        capsys: pytest.CaptureFixture[str],
        mock_staged_workflow: MagicMock,
        mock_claude_responses: AsyncMock,
    ):
        """CLI should initialize workflow and run successfully."""
        main(["test objective"])
        captured = capsys.readouterr()

        assert "π Workflow" in captured.out

    def test_agent_options_flow_to_workflow(
        self,
        capsys: pytest.CaptureFixture[str],
        mock_staged_workflow: MagicMock,
        mock_claude_responses: AsyncMock,
    ):
        """Agent options should be correctly configured."""
        with patch("π.workflow.bridge._get_agent_options") as mock_opts:
            from claude_agent_sdk import ClaudeAgentOptions

            mock_opts.return_value = ClaudeAgentOptions(
                permission_mode="acceptEdits",
                allowed_tools=["Bash", "Read"],
            )

            main(["test"])
            captured = capsys.readouterr()

            assert "π Workflow" in captured.out

    def test_error_handling_propagates(
        self,
        mock_staged_workflow: MagicMock,
    ):
        """Errors should be handled gracefully."""
        mock_staged_workflow.return_value.side_effect = Exception("Workflow error")

        with pytest.raises(Exception, match="Workflow error"):
            main(["test"])
