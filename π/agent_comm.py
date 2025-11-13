# conversation_queue_async.py
import asyncio
from pathlib import Path
from typing import Any

from claude_agent_sdk import (
    ClaudeAgentOptions,
    ClaudeSDKClient,
    create_sdk_mcp_server,
    tool,
)
from claude_agent_sdk.types import (
    AssistantMessage,
    HookMatcher,
    Message,
    ResultMessage,
    SystemMessage,
    TextBlock,
    ThinkingBlock,
    ToolResultBlock,
    UserMessage,
)

from π.hooks import check_bash_command, check_file_format

CWD = Path.cwd().parent
DEFAULT_MODEL = "sonnet"


def get_agent_options(
    *,
    continue_conversation: bool = False,
    system_prompt: str | None = None,
    model: str = DEFAULT_MODEL,
    cwd: Path = CWD,
) -> ClaudeAgentOptions:
    return ClaudeAgentOptions(
        hooks={
            "PostToolUse": [
                HookMatcher(matcher="Write|MultiEdit|Edit", hooks=[check_file_format])
            ],
            "PreToolUse": [
                HookMatcher(matcher="Bash", hooks=[check_bash_command]),
            ],
        },
        continue_conversation=continue_conversation,
        permission_mode="acceptEdits",
        system_prompt=system_prompt,
        setting_sources=["project"],
        model=model,
        cwd=cwd,
    )


def extract_message_content(msg: Message | ResultMessage) -> str | None:
    if isinstance(msg, SystemMessage):
        print(f"SYSTEM MESSAGE: {msg.data}")
    if isinstance(msg, ResultMessage):
        return msg.result
    if isinstance(msg, SystemMessage):
        return None
    if isinstance(msg, (UserMessage, AssistantMessage)):
        content = msg.content
        if isinstance(content, str):
            return content
        if isinstance(content, list):
            texts = []
            for block in content:
                if isinstance(block, TextBlock):
                    texts.append(block.text)
                elif isinstance(block, ThinkingBlock):
                    texts.append(block.thinking)
                elif isinstance(block, ToolResultBlock):
                    texts.append(block.content)
            return "\n".join(texts) if texts else None
    return None


async def query_agent(
    *,
    client: ClaudeSDKClient,
    prompt: str,
    name: str,
) -> str | None:
    messages: list[str] = []
    await client.query(prompt=prompt)
    async for msg in client.receive_response():
        print(f"[{name}] MESSAGE:", msg.__class__.__name__)
        content = extract_message_content(msg)
        if content is not None:
            messages.append(content)

    return messages[-1] if len(messages) > 0 else None


async def agent(
    *,
    client: ClaudeSDKClient,
    outbox: asyncio.Queue,
    inbox: asyncio.Queue,
    name: str,
):
    while (message := await inbox.get()) is not None:
        print(f"[{name}] received: {message[-700:] if message else ''}")
        msg_result = await query_agent(client=client, prompt=message, name=name)
        # print(f"[{name}] responds: {msg_result[-700:] if msg_result else ''}")
        await outbox.put(msg_result)

    # Signal the end of the conversation
    outbox.put_nowait(None)


class NamedQueue(asyncio.Queue[Any]):
    def __init__(self, name: str):
        self.name: str = name
        super().__init__()


async def main():
    teacher_inbox, student_inbox = NamedQueue("teacher"), NamedQueue("student")

    teacher_options = get_agent_options(
        system_prompt="You are the teacher, use mcp tools to communicate with the student."
    )
    student_options = get_agent_options(
        system_prompt="You are the student, use mcp tools to communicate with the teacher."
    )

    queue_map = {
        teacher_inbox.name: teacher_inbox,
        student_inbox.name: student_inbox,
    }
    available_agents = list(queue_map.keys())

    @tool(
        "send_message",
        "Send a message to an agent",
        {
            "type": "object",
            "properties": {
                "to": {"type": "string", "enum": available_agents},
                "message": {"type": "string"},
            },
            "required": ["to", "message"],
        },
    )
    async def send_message(args: dict[str, str]) -> dict[str, Any]:
        print(f"[send_message] called {available_agents}")
        print(f"[send_message] called with args: {args}")
        to_agent = args["to"]
        inbox = queue_map[to_agent]
        await inbox.put(args["message"])
        return {
            "content": [
                {
                    "type": "text",
                    "text": f"Message sent to {to_agent}",
                }
            ]
        }

    tools = [send_message]
    mcp_server_name = "agents_comm"
    mcp_server = create_sdk_mcp_server(
        name=mcp_server_name,
        version="1.0.0",
        tools=tools,
    )

    allowed_mcp_servers = [f"mcp__{mcp_server_name}__{tool.name}" for tool in tools]

    teacher_options.mcp_servers = {mcp_server_name: mcp_server}
    teacher_options.allowed_tools = allowed_mcp_servers

    student_options.mcp_servers = {mcp_server_name: mcp_server}
    student_options.allowed_tools = allowed_mcp_servers

    async with (
        ClaudeSDKClient(options=teacher_options) as teacher_client,
        ClaudeSDKClient(options=student_options) as student_client,
    ):
        tasks = [
            asyncio.create_task(
                agent(
                    client=teacher_client,
                    outbox=student_inbox,
                    inbox=teacher_inbox,
                    name="teacher",
                )
            ),
            asyncio.create_task(
                agent(
                    client=student_client,
                    outbox=teacher_inbox,
                    inbox=student_inbox,
                    name="student",
                )
            ),
        ]

        await teacher_inbox.put(
            "ask the student to complete the word one character at a time: 'apple'"
        )
        # wait for the student to respond
        minutes = 7
        print(f"waiting for {minutes} minutes...")
        await asyncio.sleep(minutes * 60)

        await asyncio.gather(
            teacher_inbox.put(None),
            student_inbox.put(None),
        )
        await asyncio.gather(*tasks)


if __name__ == "__main__":
    asyncio.run(main())
