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

from π.hooks import check_bash_command, check_file_format, check_file_write


class AgentQueue(asyncio.Queue[Any]):
    def __init__(self, name: str):
        self.name: str = name
        super().__init__()


ALLOWED_TOOLS = [
    "Task",
    "Bash",
    "Glob",
    "Grep",
    "ExitPlanMode",
    "Read",
    "Edit",
    "Write",
    "NotebookEdit",
    "WebFetch",
    "TodoWrite",
    "WebSearch",
    "BashOutput",
    "KillShell",
    "Skill",
    "SlashCommand",
]


def get_agent_options(
    *,
    extra_allowed_tools: list[str] = [],
    mcp_servers: dict[str, Any] = {},
    system_prompt: str | None = None,
    cwd: Path = Path.cwd(),
) -> ClaudeAgentOptions:
    return ClaudeAgentOptions(
        hooks={
            "PostToolUse": [
                HookMatcher(matcher="Write|MultiEdit|Edit", hooks=[check_file_format]),
                HookMatcher(
                    matcher="Write", hooks=[check_file_write]
                ),  # Build the function that checks if the file has been written (research & plan document)
            ],
            "PreToolUse": [
                HookMatcher(matcher="Bash", hooks=[check_bash_command]),
            ],
        },
        allowed_tools=[*ALLOWED_TOOLS, *extra_allowed_tools],
        permission_mode="acceptEdits",
        system_prompt=system_prompt,
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
    outbox: AgentQueue,
    inbox: AgentQueue,
):
    while (message := await inbox.get()) is not None:
        print(f"[{inbox.name}] RECEIVED MESSAGE: {message if message else ''}")
        msg_result = await query_agent(client=client, prompt=message, name=inbox.name)
        # print(f"[{inbox.name}] responds: {msg_result[-700:] if msg_result else ''}")
        await outbox.put(msg_result)

    # Signal the end of the conversation
    outbox.put_nowait(None)


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

    # Create agent options for the tech lead and software engineer
    tech_lead_options = get_agent_options(
        system_prompt=f"You are the tech lead and you call the shots. Use the tools to follow the workflow. \n{available_tools}",
        extra_allowed_tools=allowed_mcp_server_tools,
        mcp_servers={mcp_server_name: mcp_server},
    )
    software_engineer_options = get_agent_options(
        system_prompt=f"You are the software engineer and you follow the instructions of the tech lead. \n{available_tools}",
        extra_allowed_tools=allowed_mcp_server_tools,
        mcp_servers={mcp_server_name: mcp_server},
    )

    # Create named queues for the agents to communicate with each other
    software_engineer_agent_queue, tech_lead_agent_queue = (
        AgentQueue("software_engineer"),
        AgentQueue("tech_lead"),
    )

    async with (
        ClaudeSDKClient(options=software_engineer_options) as software_engineer_client,
        ClaudeSDKClient(options=tech_lead_options) as tech_lead_client,
        asyncio.TaskGroup() as task_group,
    ):
        task_group.create_task(
            agent(
                outbox=software_engineer_agent_queue,
                client=software_engineer_client,
                inbox=tech_lead_agent_queue,
            ),
            name=software_engineer_agent_queue.name,
        )
        task_group.create_task(
            agent(
                inbox=software_engineer_agent_queue,
                outbox=tech_lead_agent_queue,
                client=tech_lead_client,
            ),
            name=tech_lead_agent_queue.name,
        )

        mission = "How would you implement a similar approach to ../linus in the way it handles the different workflow steps?"
        # We prompt the software engineer to research the codebase first, so
        # so that any clarifying questions go to the tech lead.
        await software_engineer_agent_queue.put(f"/research_codebase {mission}")

        minutes = 10
        print(f"waiting for {minutes} minutes...")
        await asyncio.sleep(minutes * 60)

        print("Done")


if __name__ == "__main__":
    asyncio.run(main())
