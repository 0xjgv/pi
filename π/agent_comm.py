# conversation_queue_async.py
import asyncio
from itertools import cycle
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
    TextBlock,
    UserMessage,
)

from π.hooks import check_bash_command, check_file_format


def get_agent_options(
    *,
    mcp_servers: dict[str, Any] = {},
    system_prompt: str | None = None,
    allowed_tools: list[str] = [],
    cwd: Path = Path.cwd(),
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
        permission_mode="acceptEdits",
        system_prompt=system_prompt,
        allowed_tools=allowed_tools,
        setting_sources=["project"],
        mcp_servers=mcp_servers,
        cwd=cwd,  # helps to find the project .claude dir
    )


def extract_message_content(msg: Message | ResultMessage) -> str | None:
    # if isinstance(msg, SystemMessage):
    #     # print(f"SYSTEM MESSAGE: {msg.data}")
    #     ...
    if isinstance(msg, ResultMessage):
        return msg.result
    if isinstance(msg, (UserMessage, AssistantMessage)):
        content = msg.content
        if isinstance(content, str):
            return content
        if isinstance(content, list):
            texts = []
            for block in content:
                if isinstance(block, TextBlock):
                    texts.append(block.text)
            return "\n".join(texts) if len(texts) > 0 else None
        return None
    return None


async def query_agent(
    *,
    client: ClaudeSDKClient,
    prompt: str,
    name: str,
) -> str | None:
    await client.query(prompt=prompt)

    last_instance_label = None
    messages: list[str] = []

    async for msg in client.receive_response():
        instance_label = type(msg).__name__

        if last_instance_label is None or last_instance_label != instance_label:
            print(f"[{name}] MESSAGE:", instance_label)
            last_instance_label = instance_label

        content = extract_message_content(msg)
        if content is not None and content.strip() != "":
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
        print(f"[{name}] RECEIVED MESSAGE: {message if message else ''}")
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
    # Create a cycle of workflow steps
    workflow = ("research", "plan", "review", "implement", "commit", "validate")
    workflow_iter = cycle(workflow)

    # Create an MCP server tools for the workflow
    @tool("get_step", "Get the current step of the workflow", {})
    async def get_step(_: Any) -> dict[str, Any]:
        current_step = next(workflow_iter)
        return {"content": [{"type": "text", "text": f"Workflow step: {current_step}"}]}

    # Create an MCP server tools for the agents
    mcp_server_name = "workflow"
    tools = [get_step]
    mcp_server = create_sdk_mcp_server(
        name=mcp_server_name,
        version="0.1.0",
        tools=tools,
    )
    allowed_mcp_server_tools = [
        f"mcp__{mcp_server_name}__{tool.name}" for tool in tools
    ]

    # Extra prompt for the agents to know the available tools
    available_tools = f"## Available tools: {', '.join(allowed_mcp_server_tools)}"

    # Create agent options for the lead and engineer
    lead_options = get_agent_options(
        system_prompt=f"You are the tech lead and you call the shots. Use the tools to follow the workflow. \n{available_tools}",
        mcp_servers={mcp_server_name: mcp_server},
        allowed_tools=allowed_mcp_server_tools,
    )
    engineer_options = get_agent_options(
        system_prompt=f"You are the engineer and you follow the instructions of the tech lead. \n{available_tools}",
        mcp_servers={mcp_server_name: mcp_server},
        allowed_tools=allowed_mcp_server_tools,
    )

    # Create named queues for the agents to communicate with each other
    lead_agent, engineer_agent = NamedQueue("lead"), NamedQueue("engineer")

    async with (
        ClaudeSDKClient(options=engineer_options) as engineer_client,
        ClaudeSDKClient(options=lead_options) as lead_client,
    ):
        tasks = [
            asyncio.create_task(
                agent(
                    outbox=engineer_agent,
                    client=lead_client,
                    inbox=lead_agent,
                    name="lead",
                ),
                name="lead",
            ),
            asyncio.create_task(
                agent(
                    client=engineer_client,
                    inbox=engineer_agent,
                    outbox=lead_agent,
                    name="engineer",
                ),
                name="engineer",
            ),
        ]

        mission = (
            "How would you refactor the codebase to improve the production readiness?"
        )
        await engineer_agent.put(f"/research_codebase {mission}")

        minutes = 7
        print(f"waiting for {minutes} minutes...")
        await asyncio.sleep(minutes * 60)

        await asyncio.gather(
            engineer_agent.put(None),
            lead_agent.put(None),
        )
        await asyncio.gather(*tasks)


if __name__ == "__main__":
    asyncio.run(main())
