from pathlib import Path
from typing import Any

from claude_agent_sdk import ClaudeAgentOptions, ClaudeSDKClient
from claude_agent_sdk.types import (
    AssistantMessage,
    Message,
    ResultMessage,
    SystemMessage,
    TextBlock,
    ThinkingBlock,
    ToolResultBlock,
    ToolUseBlock,
    UserMessage,
)

from π.utils import write_to_log


class AgentStats:
    """Track tool usage statistics for an agent run."""

    def __init__(self):
        self.tool_counts: dict[str, int] = {}
        self.total_tools = 0
        self.errors = 0

    def record_tool(self, tool_name: str):
        self.tool_counts[tool_name] = self.tool_counts.get(tool_name, 0) + 1
        self.total_tools += 1

    def record_error(self):
        self.errors += 1

    def get_summary(self) -> str:
        if not self.total_tools:
            return "No tools used"
        top_tools = sorted(self.tool_counts.items(), key=lambda x: x[1], reverse=True)[
            :3
        ]
        tools_str = ", ".join(f"{name}({count})" for name, count in top_tools)
        error_str = f", {self.errors} errors" if self.errors else ""
        return f"{self.total_tools} tools executed: {tools_str}{error_str}"


def handle_message(
    msg: Message,
    log_file: Path | None = None,
    verbose: bool = True,
    stats: AgentStats | None = None,
) -> None | str:
    instance_label = type(msg).__name__
    message_parts: list[str] = []
    cli_output: list[str] = []  # Simplified output for CLI

    if isinstance(msg, AssistantMessage):
        for block in msg.content:
            if isinstance(block, TextBlock):
                message_parts.append(block.text)
                # Only show assistant text in verbose mode
            elif isinstance(block, ThinkingBlock):
                message_parts.append(block.thinking)
                # Don't show thinking in CLI unless verbose
            elif isinstance(block, ToolUseBlock):
                tool_info = f"Tool: {block.name}"
                if block.input:
                    # Show relevant input parameters
                    params = ", ".join(
                        f"{k}={str(v)[:50]}" for k, v in list(block.input.items())[:2]
                    )
                    tool_info += f" ({params})"
                message_parts.append(tool_info)
                # Track tool usage in stats
                if stats:
                    stats.record_tool(block.name)
                # Don't show individual tools in simplified mode
            elif isinstance(block, ToolResultBlock):
                result_info = f"Result for tool {block.tool_use_id}"
                if block.is_error:
                    result_info += " [ERROR]"
                    if stats:
                        stats.record_error()
                message_parts.append(result_info)
                # Only show errors in simplified mode
                if block.is_error and block.content:
                    error_content = str(block.content)[:200]
                    cli_output.append(f"  ❌ Error: {error_content}")
            else:
                message_parts.append(repr(block))
    elif isinstance(msg, ResultMessage):
        if msg.result:
            message_parts.append(msg.result)
        else:
            metadata = (
                f"subtype={msg.subtype}, duration_ms={msg.duration_ms}, "
                f"turns={msg.num_turns}, is_error={msg.is_error}"
            )
            message_parts.append(metadata)
    elif isinstance(msg, UserMessage):
        content = msg.content
        if isinstance(content, str):
            message_parts.append(content)
            # Don't show subagent prompts in simplified mode
        else:
            blocks = content if isinstance(content, (list, tuple)) else [content]
            for block in blocks:
                if isinstance(block, TextBlock):
                    message_parts.append(block.text)
                elif isinstance(block, ThinkingBlock):
                    message_parts.append(block.thinking)
                elif isinstance(block, str):
                    message_parts.append(block)
                else:
                    message_parts.append(repr(block))
    elif isinstance(msg, SystemMessage):
        message_parts.append(f"subtype={msg.subtype}, data={msg.data}")
    else:
        message_parts.append(repr(msg))

    message_body = "\n".join(part for part in message_parts if part).strip()
    if not message_body:
        message_body = ""

    # Full logging to file
    compound_message = f"[{instance_label}] {message_body or '(no content)'}"
    if log_file:
        write_to_log(log_file, compound_message)

    # Simplified CLI output (only show errors by default)
    if not verbose and cli_output:
        for line in cli_output:
            print(line)
    elif verbose:
        print(compound_message)

    return message_body


async def run_agent(
    *,
    log_file: Path | None = None,
    options: ClaudeAgentOptions,
    verbose: bool = True,
    prompt: str,
) -> tuple[str, AgentStats]:
    """Run agent and return the last message along with stats."""
    if log_file:
        write_to_log(log_file, f"[Prompt] {prompt}\n{'=' * 80}\n")

    stats = AgentStats()
    last_message = ""
    async with ClaudeSDKClient(options=options) as client:
        await client.query(prompt=prompt)

        async for msg in client.receive_response():
            result = handle_message(msg, log_file, verbose=verbose, stats=stats)
            if result:
                last_message = result

    return last_message, stats


async def get_server_info(*, options: ClaudeAgentOptions) -> dict[str, Any] | None:
    async with ClaudeSDKClient(options=options) as client:
        info = await client.get_server_info()
        return info
