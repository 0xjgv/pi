import asyncio
from dataclasses import dataclass, field
from typing import Literal, TypeVar

from pydantic import BaseModel

T = TypeVar("T", bound=BaseModel)


class QueueMessage:
    def __init__(self, *, message_from: str, message: str):
        self.message_from = message_from
        self.message = message


class AgentQueue(asyncio.Queue[QueueMessage | None]):
    def __init__(self, name: str):
        self.name = name
        super().__init__()


@dataclass
class StageResult:
    """Captures the outcome of a stage execution."""

    stage: str
    status: Literal["complete", "questions", "error"]
    output_file: str | None = None
    questions: list[str] = field(default_factory=list)
    response: str | None = None
