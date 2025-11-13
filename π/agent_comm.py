# conversation_queue_async.py
import asyncio
from pathlib import Path

from claude_agent_sdk import ClaudeAgentOptions, ClaudeSDKClient
from claude_agent_sdk.types import (
    AssistantMessage,
    HookMatcher,
    Message,
    ResultMessage,
    SystemMessage,
    TextBlock,
    UserMessage,
)

from π.hooks import check_bash_command, check_file_format

CWD = Path.cwd().parent
DEFAULT_MODEL = "sonnet"


def get_agent_options(
    *,
    system_prompt: str | None = None,
    fork_session: bool = False,
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
        permission_mode="acceptEdits",
        system_prompt=system_prompt,
        setting_sources=["project"],
        fork_session=fork_session,
        model=model,
        cwd=cwd,
    )


def extract_message_content(msg: Message | ResultMessage) -> str | None:
    if isinstance(msg, ResultMessage):
        return msg.result
    if isinstance(msg, SystemMessage):
        return None
    if isinstance(msg, (UserMessage, AssistantMessage)):
        content = msg.content
        if isinstance(content, str):
            return content
        if isinstance(content, list):
            # Extract text from TextBlock items
            texts = []
            for block in content:
                if isinstance(block, TextBlock):
                    texts.append(block.text)
            return "\n".join(texts) if texts else None
    return None


async def run_agent(
    *,
    options: ClaudeAgentOptions,
    prompt: str,
    name: str,
) -> str | None:
    async with ClaudeSDKClient(options=options) as client:
        result = await query_agent(client=client, prompt=prompt, name=name)
        return result


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


async def main():
    teacher_inbox, student_inbox = asyncio.Queue(), asyncio.Queue()

    # HERE: we want to start the async context for the teacher & student agents
    # the student agent should start a new session for each conversation
    # we want to figure out how to delegate the tasks of starting a new session to the teacher agent (later)
    # the teacher maintains the content of the conversation
    # the student learns though starts over when the lesson ends and things change.
    # the teacher keeps track of the previous lessons (history) and can use it to help guide the student.

    teacher_options = get_agent_options(system_prompt="You are the teacher")
    student_options = get_agent_options(
        system_prompt="You are the student",
        fork_session=True,  # start a new session for the student
    )

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
