"""Stage execution infrastructure for external workflow processes."""

import json
import sys
from abc import ABC, abstractmethod
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any


@dataclass
class StageResult:
    """Structured result from a stage execution."""

    status: str  # "success" or "error"
    result: str  # Last message from agent
    document: str | None  # Path to generated document (if applicable)
    stats: dict[str, Any]  # Tool usage statistics
    error: str | None = None  # Error message if status="error"

    def to_json(self) -> str:
        """Serialize to JSON string."""
        return json.dumps(asdict(self), indent=2)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "StageResult":
        """Deserialize from dictionary."""
        return cls(**data)


class StageRunner(ABC):
    """Base class for all workflow stage scripts."""

    def __init__(self, args: list[str]):
        """Initialize with command-line arguments."""
        self.args = args
        self.workflow_id: str = ""
        self.user_query: str = ""
        self.log_dir: Path = Path()
        self.thoughts_dir: Path = Path()
        self.previous_result: str = ""

    @abstractmethod
    def parse_args(self) -> None:
        """Parse command-line arguments specific to this stage."""
        pass

    @abstractmethod
    async def run_stage(self) -> StageResult:
        """Execute the stage logic and return structured result."""
        pass

    def output_result(self, result: StageResult) -> None:
        """Output result as JSON to stdout."""
        print(result.to_json())

    def output_stats(self, stats_summary: str) -> None:
        """Output stats to stderr for progress reporting."""
        print(stats_summary, file=sys.stderr)

    async def execute(self) -> int:
        """Main execution flow. Returns exit code."""
        try:
            self.parse_args()
            result = await self.run_stage()
            self.output_result(result)
            return 0 if result.status == "success" else 1
        except Exception as e:
            error_result = StageResult(
                status="error",
                result="",
                document=None,
                stats={},
                error=str(e)
            )
            self.output_result(error_result)
            return 1
