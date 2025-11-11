#!/usr/bin/env python3
"""Research codebase stage - external process wrapper."""

import asyncio
import sys
from pathlib import Path

from claude_agent_sdk import ClaudeAgentOptions
from π.agent import run_agent
from π.stages import StageResult, StageRunner
from π.utils import find_file_starting_with, load_prompt


class ResearchStage(StageRunner):
    """Research codebase stage."""

    def parse_args(self) -> None:
        """Parse: workflow_id user_query log_dir thoughts_dir"""
        if len(self.args) < 5:
            raise ValueError(
                f"Usage: {self.args[0]} <workflow_id> <user_query> <log_dir> <thoughts_dir>"
            )
        self.workflow_id = self.args[1]
        self.user_query = self.args[2]
        self.log_dir = Path(self.args[3])
        self.thoughts_dir = Path(self.args[4])

    async def run_stage(self) -> StageResult:
        """Execute research stage."""
        # Load prompt template
        prompt_template, model = load_prompt("research_codebase")
        prompt = prompt_template.format(
            workflow_id=self.workflow_id,
            user_query=self.user_query,
        )

        # Configure options
        options = ClaudeAgentOptions(
            permission_mode="acceptEdits",
            setting_sources=["project"],
            model=model,
            cwd=Path.cwd()
        )

        # Run agent
        result, stats = await run_agent(
            options=options,
            log_file=self.log_dir / "research.log",
            prompt=prompt,
            verbose=False
        )

        # Find generated document
        try:
            document = find_file_starting_with(
                base_dir=self.thoughts_dir,
                start_text="research"
            )
            document_path = str(document)
        except FileNotFoundError:
            document_path = None

        # Output stats to stderr
        self.output_stats(f"📊 {stats.get_summary()}")

        # Return structured result
        return StageResult(
            status="success",
            result=result,
            document=document_path,
            stats={
                "total_tools": stats.total_tools,
                "errors": stats.errors,
                "tool_counts": stats.tool_counts
            }
        )


async def main() -> int:
    """Entry point."""
    stage = ResearchStage(sys.argv)
    return await stage.execute()


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
