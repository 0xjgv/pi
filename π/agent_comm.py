import asyncio
import contextlib
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Literal

from claude_agent_sdk import ClaudeAgentOptions

from π.agent import run_agent

AgentMessage = tuple[str, str]
PromptBuilder = Callable[["AgentParticipant", AgentMessage, "ConversationState"], str]


class ConversationState:
    """In-memory transcript for a dual-agent exchange."""

    def __init__(self) -> None:
        self.history: list[AgentMessage] = []

    def append(self, speaker: str, content: str) -> None:
        self.history.append((speaker, content))

    def render(self) -> str:
        if not self.history:
            return ""
        return "\n".join(f"{speaker}: {content}" for speaker, content in self.history)

    def copy(self) -> list[AgentMessage]:
        return list(self.history)

    def __len__(self) -> int:
        return len(self.history)


@dataclass(slots=True)
class AgentParticipant:
    """Configuration for a single conversational agent."""

    name: str
    options: ClaudeAgentOptions
    prompt_builder: PromptBuilder | None = None
    log_file: Path | None = None
    verbose: bool = False

    def build_prompt(self, incoming: AgentMessage, state: ConversationState) -> str:
        builder = self.prompt_builder or _default_prompt_builder
        return builder(self, incoming, state)


@dataclass(slots=True)
class ConversationResult:
    """Final transcript for a conversation."""

    transcript: list[AgentMessage]

    def as_text(self) -> str:
        if not self.transcript:
            return ""
        return "\n".join(
            f"{speaker}: {content}" for speaker, content in self.transcript
        )


def _default_prompt_builder(
    participant: AgentParticipant,
    incoming: AgentMessage,
    state: ConversationState,
) -> str:
    sender, message = incoming
    transcript = state.render()
    if transcript:
        transcript_block = transcript
    else:
        transcript_block = f"{sender}: {message}"

    return (
        f"You are {participant.name}. Continue the dialogue below.\n\n"
        f"{transcript_block}\n\n"
        f"Most recent message from {sender}: {message}\n"
        f"Reply in the voice of {participant.name}:"
    )


async def _agent_worker(
    participant: AgentParticipant,
    *,
    inbox: asyncio.Queue[AgentMessage | None],
    state: ConversationState,
    transcript_queue: asyncio.Queue[AgentMessage],
    stop_event: asyncio.Event,
) -> None:
    while True:
        payload = await inbox.get()
        if payload is None:
            break
        if stop_event.is_set():
            continue

        prompt = participant.build_prompt(payload, state)

        try:
            reply_text = await run_agent(
                log_file=participant.log_file,
                options=participant.options,
                verbose=participant.verbose,
                prompt=prompt,
            )
        except asyncio.CancelledError:
            stop_event.set()
            raise
        except Exception:
            stop_event.set()
            raise

        await transcript_queue.put((participant.name, reply_text))


async def run_agent_conversation(
    *,
    first_responder: Literal["agent_a", "agent_b"] = "agent_b",
    per_turn_timeout: float | None = None,
    initial_sender: str | None = None,
    agent_a: AgentParticipant,
    agent_b: AgentParticipant,
    initial_message: str,
    turns: int = 4,
) -> ConversationResult:
    """Run a bounded asynchronous conversation between two agents.

    Args:
        agent_a: First agent participant.
        agent_b: Second agent participant.
        initial_message: Seed message inserted at the start of the exchange.
        turns: Number of run_agent calls (responses) to collect.
        first_responder: Which agent receives the initial message.
        initial_sender: Logical speaker for the initial message. Defaults to the
            opposing agent's name.
        per_turn_timeout: Optional timeout (seconds) per response.

    Returns:
        ConversationResult containing the full transcript (including initial
        message).

    Raises:
        ValueError: If configuration values are invalid.
        asyncio.TimeoutError: If per_turn_timeout expires before collecting all turns.
    """
    if turns < 1:
        raise ValueError("turns must be at least 1")
    if first_responder not in {"agent_a", "agent_b"}:
        raise ValueError("first_responder must be 'agent_a' or 'agent_b'")

    transcript_queue: asyncio.Queue[AgentMessage] = asyncio.Queue()
    stop_event = asyncio.Event()
    state = ConversationState()

    a_inbox: asyncio.Queue[AgentMessage | None] = asyncio.Queue()
    b_inbox: asyncio.Queue[AgentMessage | None] = asyncio.Queue()

    workers = [
        asyncio.create_task(
            _agent_worker(
                agent_a,
                transcript_queue=transcript_queue,
                stop_event=stop_event,
                inbox=a_inbox,
                state=state,
            ),
            name=f"{agent_a.name}-worker",
        ),
        asyncio.create_task(
            _agent_worker(
                agent_b,
                transcript_queue=transcript_queue,
                stop_event=stop_event,
                inbox=b_inbox,
                state=state,
            ),
            name=f"{agent_b.name}-worker",
        ),
    ]

    pending_response: asyncio.Task | None = None
    responses_collected = 0

    try:
        default_sender = agent_b.name if first_responder == "agent_a" else agent_a.name
        receiver_queue = a_inbox if first_responder == "agent_a" else b_inbox
        seeded_sender = initial_sender or default_sender

        receiver_queue.put_nowait((seeded_sender, initial_message))
        state.append(seeded_sender, initial_message)

        pending_response = asyncio.create_task(transcript_queue.get())

        while responses_collected < turns:
            wait_set: set[asyncio.Task] = {pending_response, *workers}
            done, _ = await asyncio.wait(
                wait_set,
                timeout=per_turn_timeout,
                return_when=asyncio.FIRST_COMPLETED,
            )

            if not done:
                raise asyncio.TimeoutError(
                    f"Timed out waiting for turn {responses_collected + 1}."
                )

            for worker in workers:
                if worker in done:
                    exc = worker.exception()
                    if exc is not None:
                        stop_event.set()
                        raise exc
                    stop_event.set()
                    raise RuntimeError(
                        f"Worker '{worker.get_name()}' exited unexpectedly."
                    )

            if pending_response in done:
                speaker, reply_text = pending_response.result()
                state.append(speaker, reply_text)
                responses_collected += 1

                if responses_collected >= turns:
                    pending_response = None
                    break

                if speaker == agent_a.name:
                    next_queue = b_inbox
                elif speaker == agent_b.name:
                    next_queue = a_inbox
                else:
                    stop_event.set()
                    raise RuntimeError(f"Unknown speaker '{speaker}' in transcript")

                next_queue.put_nowait((speaker, reply_text))
                pending_response = asyncio.create_task(transcript_queue.get())

        stop_event.set()

    except asyncio.TimeoutError as exc:
        stop_event.set()
        for worker in workers:
            worker.cancel()
        raise asyncio.TimeoutError(
            f"Timed out waiting for turn {responses_collected + 1}."
        ) from exc

    finally:
        stop_event.set()
        a_inbox.put_nowait(None)
        b_inbox.put_nowait(None)
        if pending_response is not None and not pending_response.done():
            pending_response.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await pending_response
        await asyncio.gather(*workers, return_exceptions=True)

    return ConversationResult(
        transcript=state.copy(),
    )
