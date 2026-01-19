"""MCP tools for π workflow using Claude Agent SDK.

This module defines MCP tools that expose workflow commands (research, plan,
implement, etc.) as callable tools via the Claude Agent SDK's native MCP support.

Tools return JSON with fields that map to WorkflowOutput schema:
- research_codebase → doc_path, summary
- create_plan → doc_path
- review_plan → doc_path, approved
- iterate_plan → doc_path
- implement_plan → files_changed
- commit_changes → commit_hash

Tool naming convention: mcp__workflow__{tool_name}
"""

from __future__ import annotations

import json
from pathlib import Path

from claude_agent_sdk import create_sdk_mcp_server, tool

from basic.bridge import (
    COMMAND_DOC_TYPE,
    run_claude_session,
)
from basic.context import get_workflow_ctx
from π.core.enums import Command

# --- Tool Definitions ---


@tool(
    name="research_codebase",
    description="Research the codebase and document findings. Use this to explore "
    "and understand code structure, patterns, and implementations. "
    "Returns JSON with doc_path and summary for WorkflowOutput.",
    input_schema={"query": str},
)
async def research_codebase(args: dict) -> dict:
    """Research the codebase based on a query."""
    cmd = Command.RESEARCH_CODEBASE
    ctx = get_workflow_ctx()

    result, session_id, doc_path, _ = await run_claude_session(
        session_id=ctx.session_ids.get(cmd),
        observer=ctx.observer,
        query=args["query"],
        tool_command=cmd,
    )

    # Update context
    ctx.session_ids[cmd] = session_id
    if doc_path and (doc_type := COMMAND_DOC_TYPE.get(cmd)):
        ctx.doc_paths[doc_type] = doc_path

    # Return JSON for structured output compatibility
    output = {"doc_path": doc_path, "summary": result}
    return {"content": [{"type": "text", "text": json.dumps(output, indent=2)}]}


@tool(
    name="create_plan",
    description="Create a detailed implementation plan based on a research document. "
    "Requires path to research document produced by research_codebase. "
    "Returns JSON with doc_path for WorkflowOutput.",
    input_schema={"query": str, "research_path": str},
)
async def create_plan(args: dict) -> dict:
    """Create a plan based on a research document."""
    cmd = Command.CREATE_PLAN
    ctx = get_workflow_ctx()

    result, session_id, doc_path, _ = await run_claude_session(
        document=Path(args["research_path"]),
        session_id=ctx.session_ids.get(cmd),
        query=args["query"],
        tool_command=cmd,
        observer=ctx.observer,
    )

    # Update context
    ctx.session_ids[cmd] = session_id
    if doc_path and (doc_type := COMMAND_DOC_TYPE.get(cmd)):
        ctx.doc_paths[doc_type] = doc_path

    # Return JSON for structured output compatibility
    output = {"doc_path": doc_path, "result": result}
    return {"content": [{"type": "text", "text": json.dumps(output, indent=2)}]}


@tool(
    name="review_plan",
    description="Review and critique an existing plan document. "
    "Identifies issues, gaps, and areas for improvement. "
    "Returns JSON with approved boolean for WorkflowOutput.",
    input_schema={"query": str, "plan_path": str},
)
async def review_plan(args: dict) -> dict:
    """Review a plan document."""
    cmd = Command.REVIEW_PLAN
    ctx = get_workflow_ctx()

    result, session_id, doc_path, _ = await run_claude_session(
        session_id=ctx.session_ids.get(cmd),
        document=Path(args["plan_path"]),
        observer=ctx.observer,
        query=args["query"],
        tool_command=cmd,
    )

    # Update context
    ctx.session_ids[cmd] = session_id
    if doc_path and (doc_type := COMMAND_DOC_TYPE.get(cmd)):
        ctx.doc_paths[doc_type] = doc_path

    # Determine approval from result (heuristic: no critical issues found)
    result_lower = result.lower()
    approved = not any(
        word in result_lower for word in ["issue", "problem", "fix", "change", "revise"]
    )

    # Return JSON for structured output compatibility
    output = {"doc_path": doc_path, "approved": approved, "feedback": result}
    return {"content": [{"type": "text", "text": json.dumps(output, indent=2)}]}


@tool(
    name="iterate_plan",
    description="Iterate on a plan based on review feedback. "
    "Updates the plan document to address identified issues. "
    "Returns JSON with updated doc_path for WorkflowOutput.",
    input_schema={"query": str, "plan_path": str, "feedback": str},
)
async def iterate_plan(args: dict) -> dict:
    """Iterate on a plan based on feedback."""
    cmd = Command.ITERATE_PLAN
    ctx = get_workflow_ctx()

    full_query = (
        f"## Review Feedback to Address\n{args['feedback']}\n\n"
        f"## Additional Instructions\n{args['query']}"
    )

    result, session_id, doc_path, _ = await run_claude_session(
        session_id=ctx.session_ids.get(cmd),
        document=Path(args["plan_path"]),
        observer=ctx.observer,
        tool_command=cmd,
        query=full_query,
    )

    # Update context
    ctx.session_ids[cmd] = session_id
    if doc_path and (doc_type := COMMAND_DOC_TYPE.get(cmd)):
        ctx.doc_paths[doc_type] = doc_path

    # Return JSON for structured output compatibility
    output = {"doc_path": doc_path, "result": result}
    return {"content": [{"type": "text", "text": json.dumps(output, indent=2)}]}


@tool(
    name="implement_plan",
    description="Implement a plan by executing all phases. "
    "Makes actual code changes according to the plan document. "
    "Returns JSON with files_changed list for WorkflowOutput.",
    input_schema={"query": str, "plan_path": str},
)
async def implement_plan(args: dict) -> dict:
    """Implement a plan by executing all phases."""
    cmd = Command.IMPLEMENT_PLAN
    ctx = get_workflow_ctx()

    result, session_id, _, files_changed = await run_claude_session(
        session_id=ctx.session_ids.get(cmd),
        document=Path(args["plan_path"]),
        observer=ctx.observer,
        query=args["query"],
        tool_command=cmd,
    )

    # Update context
    ctx.session_ids[cmd] = session_id

    # Return JSON for structured output compatibility
    output = {"files_changed": files_changed, "result": result}
    return {"content": [{"type": "text", "text": json.dumps(output, indent=2)}]}


@tool(
    name="commit_changes",
    description="Commit the changes made during implementation. "
    "Creates a git commit with appropriate message. "
    "Returns JSON with commit_hash for WorkflowOutput.",
    input_schema={"query": str},
)
async def commit_changes(args: dict) -> dict:
    """Commit changes with context."""
    ctx = get_workflow_ctx()
    cmd = Command.COMMIT

    result, session_id, _, _ = await run_claude_session(
        session_id=ctx.session_ids.get(cmd),
        observer=ctx.observer,
        query=args["query"],
        tool_command=cmd,
    )

    # Update context
    ctx.session_ids[cmd] = session_id

    output = {"result": result}
    return {"content": [{"type": "text", "text": json.dumps(output, indent=2)}]}


@tool(
    name="write_claude_md",
    description="Update CLAUDE.md documentation based on codebase changes. "
    "Keeps project documentation in sync with code.",
    input_schema={"query": str, "git_diff": str},
)
async def write_claude_md(args: dict) -> dict:
    """Update CLAUDE.md based on changes."""
    cmd = Command.WRITE_CLAUDE_MD
    ctx = get_workflow_ctx()

    full_query = (
        f"Based on the following recent codebase changes, update CLAUDE.md:\n\n"
        f"## Changes Since Last Sync\n{args['git_diff']}\n\n"
        f"## Update Instructions\n{args['query']}"
    )

    result, session_id, _, files_changed = await run_claude_session(
        session_id=ctx.session_ids.get(cmd),
        observer=ctx.observer,
        tool_command=cmd,
        query=full_query,
    )

    # Update context
    ctx.session_ids[cmd] = session_id

    # Return JSON for structured output compatibility
    output = {"files_changed": files_changed, "summary": result}
    return {"content": [{"type": "text", "text": json.dumps(output, indent=2)}]}


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
