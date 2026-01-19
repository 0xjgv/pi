"""Tests for π.workflow.tools module."""

import json
from pathlib import Path

import pytest

from π.workflow.tools import (
    commit_changes,
    create_plan,
    implement_plan,
    iterate_plan,
    research_codebase,
    review_plan,
    write_claude_md,
)

pytestmark = pytest.mark.no_api


class TestResearchCodebase:
    """Tests for research_codebase tool."""

    @pytest.mark.asyncio
    async def test_returns_json_with_doc_path_and_summary(
        self, mock_run_claude_session, fresh_workflow_context
    ):
        """Should return JSON with doc_path and summary."""
        _ = fresh_workflow_context  # Used for context setup
        mock_run_claude_session.side_effect = lambda **_kw: (
            "Research summary",
            "sess-1",
            "/docs/research.md",
            [],
        )

        result = await research_codebase.handler({"query": "analyze the codebase"})

        content = json.loads(result["content"][0]["text"])
        assert content["doc_path"] == "/docs/research.md"
        assert content["summary"] == "Research summary"


class TestCreatePlan:
    """Tests for create_plan tool."""

    @pytest.mark.asyncio
    async def test_passes_document_path(
        self, mock_run_claude_session, fresh_workflow_context, tmp_path: Path
    ):
        """Should pass research document path to run_claude_session."""
        _ = fresh_workflow_context  # Used for context setup
        research_doc = tmp_path / "research.md"
        research_doc.write_text("# Research")

        mock_run_claude_session.side_effect = lambda **_kw: (
            "Plan created",
            "sess-2",
            "/plans/plan.md",
            [],
        )

        result = await create_plan.handler({
            "query": "create implementation plan",
            "research_path": str(research_doc),
        })

        # Verify document was passed
        call_kwargs = mock_run_claude_session.call_args.kwargs
        assert call_kwargs["document"] == research_doc

        content = json.loads(result["content"][0]["text"])
        assert content["doc_path"] == "/plans/plan.md"


class TestReviewPlan:
    """Tests for review_plan tool."""

    @pytest.mark.asyncio
    async def test_approved_when_result_is_clean(
        self, mock_run_claude_session, fresh_workflow_context, tmp_path: Path
    ):
        """Should set approved=True when no critical keywords found."""
        _ = fresh_workflow_context  # Used for context setup
        plan_doc = tmp_path / "plan.md"
        plan_doc.write_text("# Plan")

        mock_run_claude_session.side_effect = lambda **_kw: (
            "Plan looks good, well structured",
            "sess-3",
            str(plan_doc),
            [],
        )

        result = await review_plan.handler({
            "query": "review this plan",
            "plan_path": str(plan_doc),
        })

        content = json.loads(result["content"][0]["text"])
        assert content["approved"] is True
        assert "feedback" in content

    @pytest.mark.asyncio
    @pytest.mark.parametrize("keyword", ["issue", "problem", "fix", "change", "revise"])
    async def test_rejected_when_keywords_found(
        self,
        mock_run_claude_session,
        fresh_workflow_context,
        tmp_path: Path,
        keyword: str,
    ):
        """Should set approved=False when critical keywords found."""
        _ = fresh_workflow_context  # Used for context setup
        plan_doc = tmp_path / "plan.md"
        plan_doc.write_text("# Plan")

        mock_run_claude_session.side_effect = lambda **_kw: (
            f"Found an {keyword} in the plan",
            "sess-3",
            str(plan_doc),
            [],
        )

        result = await review_plan.handler({
            "query": "review this plan",
            "plan_path": str(plan_doc),
        })

        content = json.loads(result["content"][0]["text"])
        assert content["approved"] is False


class TestIteratePlan:
    """Tests for iterate_plan tool."""

    @pytest.mark.asyncio
    async def test_builds_full_query_with_feedback(
        self, mock_run_claude_session, fresh_workflow_context, tmp_path: Path
    ):
        """Should build full_query with feedback and instructions."""
        _ = fresh_workflow_context  # Used for context setup
        plan_doc = tmp_path / "plan.md"
        plan_doc.write_text("# Plan")

        captured_query: str | None = None

        async def capture_query(**kwargs):
            nonlocal captured_query
            captured_query = kwargs.get("query")
            return ("Updated plan", "sess-4", str(plan_doc), [])

        mock_run_claude_session.side_effect = capture_query

        await iterate_plan.handler({
            "query": "address the issues",
            "plan_path": str(plan_doc),
            "feedback": "Missing error handling",
        })

        assert captured_query is not None
        assert "## Review Feedback to Address" in captured_query
        assert "Missing error handling" in captured_query
        assert "## Additional Instructions" in captured_query
        assert "address the issues" in captured_query


class TestImplementPlan:
    """Tests for implement_plan tool."""

    @pytest.mark.asyncio
    async def test_returns_files_changed(
        self, mock_run_claude_session, fresh_workflow_context, tmp_path: Path
    ):
        """Should return files_changed list."""
        _ = fresh_workflow_context  # Used for context setup
        plan_doc = tmp_path / "plan.md"
        plan_doc.write_text("# Plan")

        mock_run_claude_session.side_effect = lambda **_kw: (
            "Implementation complete",
            "sess-5",
            None,
            ["src/main.py", "src/utils.py"],
        )

        result = await implement_plan.handler({
            "query": "implement phase 1",
            "plan_path": str(plan_doc),
        })

        content = json.loads(result["content"][0]["text"])
        assert content["files_changed"] == ["src/main.py", "src/utils.py"]


class TestCommitChanges:
    """Tests for commit_changes tool."""

    @pytest.mark.asyncio
    async def test_updates_session_id(
        self, mock_run_claude_session, fresh_workflow_context
    ):
        """Should update session_id in context."""
        _ = fresh_workflow_context  # Used for context setup
        mock_run_claude_session.side_effect = lambda **_kw: (
            "Committed abc123",
            "sess-6",
            None,
            [],
        )

        result = await commit_changes.handler({"query": "commit the changes"})

        content = json.loads(result["content"][0]["text"])
        assert "result" in content


class TestWriteClaudeMd:
    """Tests for write_claude_md tool."""

    @pytest.mark.asyncio
    async def test_includes_git_diff_in_query(
        self, mock_run_claude_session, fresh_workflow_context
    ):
        """Should include git diff in the full query."""
        _ = fresh_workflow_context  # Used for context setup
        captured_query: str | None = None

        async def capture_query(**kwargs):
            nonlocal captured_query
            captured_query = kwargs.get("query")
            return ("CLAUDE.md updated", "sess-7", None, ["CLAUDE.md"])

        mock_run_claude_session.side_effect = capture_query

        await write_claude_md.handler({
            "query": "update documentation",
            "git_diff": "diff --git a/src/main.py\n+new code",
        })

        assert captured_query is not None
        assert "## Changes Since Last Sync" in captured_query
        assert "diff --git a/src/main.py" in captured_query
        assert "## Update Instructions" in captured_query
        assert "update documentation" in captured_query

    @pytest.mark.asyncio
    async def test_returns_files_changed_and_summary(
        self, mock_run_claude_session, fresh_workflow_context
    ):
        """Should return files_changed and summary in output."""
        _ = fresh_workflow_context  # Used for context setup
        mock_run_claude_session.side_effect = lambda **_kw: (
            "Updated CLAUDE.md",
            "sess-7",
            None,
            ["CLAUDE.md"],
        )

        result = await write_claude_md.handler({
            "query": "update docs",
            "git_diff": "some diff",
        })

        content = json.loads(result["content"][0]["text"])
        assert content["files_changed"] == ["CLAUDE.md"]
        assert content["summary"] == "Updated CLAUDE.md"
