import asyncio
from pathlib import Path
from typing import Callable

from claude_agent_sdk import (
    ClaudeAgentOptions,
    ClaudeSDKClient,
)
from claude_agent_sdk.types import (
    HookMatcher,
)

from π.hooks import check_bash_command, check_file_format, check_file_write
from π.utils import (
    create_workflow_dir,
    escape_csv_text,
    extract_message_content,
    generate_workflow_id,
)

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


class QueueMessage:
    def __init__(self, *, message_from: str, message: str):
        self.message_from = message_from
        self.message = message


class AgentQueue(asyncio.Queue[QueueMessage | None]):
    def __init__(self, name: str):
        self.name = name
        super().__init__()


def capture_conversation_to_csv(
    *,
    workflow_dir: Path,
) -> Callable[[QueueMessage, str], None]:
    """Create a function to write conversation messages to a CSV file."""
    # Write the header once when the function is first called
    csv_file = workflow_dir / "conversation.csv"
    with open(csv_file, "w", encoding="utf-8") as f:
        f.write("message_from,message_to,message\n")

    # Return a function that can be called to append messages to the CSV file
    def _write_message(msg: QueueMessage, message_to: str) -> None:
        with open(csv_file, "a", encoding="utf-8") as f:
            f.write(f"{msg.message_from},{message_to},{escape_csv_text(msg.message)}\n")

    return _write_message


def get_agent_options(
    *,
    system_prompt: str | None = None,
    model: str | None = None,
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
        allowed_tools=ALLOWED_TOOLS,
        permission_mode="acceptEdits",
        system_prompt=system_prompt,
        setting_sources=["project"],
        model=model,
        cwd=cwd,  # helps to find the project .claude dir
    )


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
    write_conversation: Callable[[QueueMessage, str], None] | None = None,
    outboxes: list[AgentQueue],
    client: ClaudeSDKClient,
    inbox: AgentQueue,
):
    while (msg_item := await inbox.get()) is not None:
        if not msg_item.message:
            continue

        if write_conversation:
            write_conversation(msg_item, inbox.name)
        else:
            print(f"[{msg_item.message_from} -> {inbox.name}]")
            print(f"> {msg_item.message}")

        msg_result = await query_agent(
            prompt=msg_item.message,
            name=inbox.name,
            client=client,
        )

        async with asyncio.TaskGroup() as task_group:
            queue_message = QueueMessage(
                message=msg_result or "",
                message_from=inbox.name,
            )
            for outbox in outboxes:
                task_group.create_task(outbox.put(queue_message))

    # Signal the end of the conversation
    for outbox in outboxes:
        outbox.put_nowait(None)


async def main():
    # Set up workflow directory for conversation logging
    workflow_id = generate_workflow_id()
    workflow_dir = create_workflow_dir(Path.cwd() / ".logs", workflow_id)
    write_conversation = capture_conversation_to_csv(workflow_dir=workflow_dir)

    # Create agent options for the tech lead and software engineer
    tech_lead_options = get_agent_options(
        system_prompt="You are the tech lead and you call the shots. Use the tools to follow the workflow.",
    )
    software_engineer_options = get_agent_options(
        system_prompt="You are the software engineer and you follow the instructions of the tech lead.",
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
                outboxes=[software_engineer_agent_queue],
                write_conversation=write_conversation,
                client=software_engineer_client,
                inbox=tech_lead_agent_queue,
            ),
            name=software_engineer_agent_queue.name,
        )
        task_group.create_task(
            agent(
                write_conversation=write_conversation,
                inbox=software_engineer_agent_queue,
                outboxes=[tech_lead_agent_queue],
                client=tech_lead_client,
            ),
            name=tech_lead_agent_queue.name,
        )
        # EXAMPLE: On how to add a third agent to the conversation
        # task_group.create_task(
        #     proxy_agent(
        #         inbox=proxy_agent_queue,
        #     ),
        #     name=proxy_agent_queue.name,
        # )

        mission = "What's the capital of France?"
        initial_message = QueueMessage(message_from="user", message=mission)

        # We prompt the software engineer to research the codebase first, so
        # so that any clarifying questions go to the tech lead.
        await software_engineer_agent_queue.put(initial_message)

        minutes = 10
        print(f"waiting for {minutes} minutes...")
        await asyncio.sleep(minutes * 60)

        print("Done")


if __name__ == "__main__":
    asyncio.run(main())
