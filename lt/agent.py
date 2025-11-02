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
    UserMessage,
)

from lt.utils import write_to_log


def handle_message(msg: Message, log_file: Path | None = None) -> None | str:
    instance_label = type(msg).__name__
    message_parts: list[str] = []

    if isinstance(msg, AssistantMessage):
        for block in msg.content:
            if isinstance(block, TextBlock):
                message_parts.append(block.text)
            elif isinstance(block, ThinkingBlock):
                message_parts.append(block.thinking)
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

    compound_message = f"[{instance_label}] {message_body or '(no content)'}"
    print(compound_message)
    if log_file:
        write_to_log(log_file, compound_message)
    return message_body


async def run_agent(
    *,
    log_file: Path | None = None,
    options: ClaudeAgentOptions,
    prompt: str,
) -> str:
    if log_file:
        write_to_log(log_file, f"[Prompt] {prompt}\n{'=' * 80}\n")

    last_message = ""
    async with ClaudeSDKClient(options=options) as client:
        await client.query(prompt=prompt)

        async for msg in client.receive_response():
            result = handle_message(msg, log_file)
            if result:
                last_message = result

    return last_message


async def get_server_info(*, options: ClaudeAgentOptions) -> dict[str, Any] | None:
    async with ClaudeSDKClient(options=options) as client:
        info = await client.get_server_info()
        return info
