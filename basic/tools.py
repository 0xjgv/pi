"""MCP tools for π workflow using Claude Agent SDK.

This module defines MCP tools that expose workflow commands (research, plan,
implement, etc.) as callable tools via the Claude Agent SDK's native MCP support.

Tools handle all context management. Bridge is pure execution.

Tool naming convention: mcp__workflow__{tool_name}
"""

from __future__ import annotations

from pathlib import Path

from claude_agent_sdk import create_sdk_mcp_server, tool

from basic.bridge import COMMAND_DOC_TYPE, run_claude_session
from basic.context import get_workflow_ctx
from π.core.enums import Command

# --- Tool Definitions ---


@tool(
    name="research_codebase",
    description="Research the codebase and document findings. Use this to explore "
    "and understand code structure, patterns, and implementations.",
    input_schema={"query": str},
)
async def research_codebase(args: dict) -> dict:
    """Research the codebase based on a query."""
    ctx = get_workflow_ctx()
    cmd = Command.RESEARCH_CODEBASE

    result, session_id, doc_path = await run_claude_session(
        tool_command=cmd,
        query=args["query"],
        session_id=ctx.session_ids.get(cmd),
        objective=ctx.objective,
    )

    # Update context
    ctx.session_ids[cmd] = session_id
    if doc_path and (doc_type := COMMAND_DOC_TYPE.get(cmd)):
        ctx.doc_paths[doc_type] = doc_path

    return {
        "content": [
            {
                "type": "text",
                "text": f"<doc_path>{doc_path}</doc_path>\n<result>{result}</result>",
            }
        ]
    }


@tool(
    name="create_plan",
    description="Create a detailed implementation plan based on a research document. "
    "Requires path to research document produced by research_codebase.",
    input_schema={"query": str, "research_path": str},
)
async def create_plan(args: dict) -> dict:
    """Create a plan based on a research document."""
    ctx = get_workflow_ctx()
    cmd = Command.CREATE_PLAN

    result, session_id, doc_path = await run_claude_session(
        tool_command=cmd,
        query=args["query"],
        session_id=ctx.session_ids.get(cmd),
        objective=ctx.objective,
        document=Path(args["research_path"]),
    )

    # Update context
    ctx.session_ids[cmd] = session_id
    if doc_path and (doc_type := COMMAND_DOC_TYPE.get(cmd)):
        ctx.doc_paths[doc_type] = doc_path

    return {
        "content": [
            {
                "type": "text",
                "text": f"<doc_path>{doc_path}</doc_path>\n<result>{result}</result>",
            }
        ]
    }


@tool(
    name="review_plan",
    description="Review and critique an existing plan document. "
    "Identifies issues, gaps, and areas for improvement.",
    input_schema={"query": str, "plan_path": str},
)
async def review_plan(args: dict) -> dict:
    """Review a plan document."""
    ctx = get_workflow_ctx()
    cmd = Command.REVIEW_PLAN

    result, session_id, doc_path = await run_claude_session(
        tool_command=cmd,
        query=args["query"],
        session_id=ctx.session_ids.get(cmd),
        objective=ctx.objective,
        document=Path(args["plan_path"]),
    )

    # Update context
    ctx.session_ids[cmd] = session_id
    if doc_path and (doc_type := COMMAND_DOC_TYPE.get(cmd)):
        ctx.doc_paths[doc_type] = doc_path

    return {
        "content": [
            {
                "type": "text",
                "text": f"<doc_path>{doc_path}</doc_path>\n<result>{result}</result>",
            }
        ]
    }


@tool(
    name="iterate_plan",
    description="Iterate on a plan based on review feedback. "
    "Updates the plan document to address identified issues.",
    input_schema={"query": str, "plan_path": str, "feedback": str},
)
async def iterate_plan(args: dict) -> dict:
    """Iterate on a plan based on feedback."""
    ctx = get_workflow_ctx()
    cmd = Command.ITERATE_PLAN

    full_query = (
        f"## Review Feedback to Address\n{args['feedback']}\n\n"
        f"## Additional Instructions\n{args['query']}"
    )

    result, session_id, doc_path = await run_claude_session(
        tool_command=cmd,
        query=full_query,
        session_id=ctx.session_ids.get(cmd),
        objective=ctx.objective,
        document=Path(args["plan_path"]),
    )

    # Update context
    ctx.session_ids[cmd] = session_id
    if doc_path and (doc_type := COMMAND_DOC_TYPE.get(cmd)):
        ctx.doc_paths[doc_type] = doc_path

    return {
        "content": [
            {
                "type": "text",
                "text": f"<doc_path>{doc_path}</doc_path>\n<result>{result}</result>",
            }
        ]
    }


@tool(
    name="implement_plan",
    description="Implement a plan by executing all phases. "
    "Makes actual code changes according to the plan document.",
    input_schema={"query": str, "plan_path": str},
)
async def implement_plan(args: dict) -> dict:
    """Implement a plan by executing all phases."""
    ctx = get_workflow_ctx()
    cmd = Command.IMPLEMENT_PLAN

    result, session_id, _ = await run_claude_session(
        tool_command=cmd,
        query=args["query"],
        session_id=ctx.session_ids.get(cmd),
        objective=ctx.objective,
        document=Path(args["plan_path"]),
    )

    # Update context
    ctx.session_ids[cmd] = session_id

    return {"content": [{"type": "text", "text": f"<result>{result}</result>"}]}


@tool(
    name="commit_changes",
    description="Commit the changes made during implementation. "
    "Creates a git commit with appropriate message.",
    input_schema={"query": str},
)
async def commit_changes(args: dict) -> dict:
    """Commit changes with context."""
    ctx = get_workflow_ctx()
    cmd = Command.COMMIT

    result, session_id, _ = await run_claude_session(
        tool_command=cmd,
        query=args["query"],
        session_id=ctx.session_ids.get(cmd),
        objective=ctx.objective,
    )

    # Update context
    ctx.session_ids[cmd] = session_id

    return {"content": [{"type": "text", "text": f"<result>{result}</result>"}]}


@tool(
    name="write_claude_md",
    description="Update CLAUDE.md documentation based on codebase changes. "
    "Keeps project documentation in sync with code.",
    input_schema={"query": str, "git_diff": str},
)
async def write_claude_md(args: dict) -> dict:
    """Update CLAUDE.md based on changes."""
    ctx = get_workflow_ctx()
    cmd = Command.WRITE_CLAUDE_MD

    full_query = (
        f"Based on the following recent codebase changes, update CLAUDE.md:\n\n"
        f"## Changes Since Last Sync\n{args['git_diff']}\n\n"
        f"## Update Instructions\n{args['query']}"
    )

    result, session_id, _ = await run_claude_session(
        tool_command=cmd,
        query=full_query,
        session_id=ctx.session_ids.get(cmd),
        objective=ctx.objective,
    )

    # Update context
    ctx.session_ids[cmd] = session_id

    return {"content": [{"type": "text", "text": f"<result>{result}</result>"}]}


# --- MCP Server ---

workflow_server = create_sdk_mcp_server(
    name="workflow",
    version="1.0.0",
    tools=[
        research_codebase,
        create_plan,
        review_plan,
        iterate_plan,
        implement_plan,
        commit_changes,
        write_claude_md,
    ],
)

# Tool names for allowed_tools configuration
WORKFLOW_TOOLS = [
    "mcp__workflow__research_codebase",
    "mcp__workflow__create_plan",
    "mcp__workflow__review_plan",
    "mcp__workflow__iterate_plan",
    "mcp__workflow__implement_plan",
    "mcp__workflow__commit_changes",
    "mcp__workflow__write_claude_md",
]
