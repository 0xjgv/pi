#!/usr/bin/env python3
"""Implement plan stage - external process wrapper."""

import asyncio
import sys
from pathlib import Path

from claude_agent_sdk import ClaudeAgentOptions
from π.agent import run_agent
from π.stages import StageResult, StageRunner
from π.utils import load_prompt


class ImplementStage(StageRunner):
    """Implement plan stage."""

    def parse_args(self) -> None:
        """Parse: workflow_id log_dir plan_doc previous_result"""
        if len(self.args) < 5:
            raise ValueError(
                f"Usage: {self.args[0]} <workflow_id> <log_dir> <plan_doc> <previous_result>"
            )
        self.workflow_id = self.args[1]
        self.log_dir = Path(self.args[2])
        self.plan_document = self.args[3]
        self.previous_result = self.args[4]

    async def run_stage(self) -> StageResult:
        """Execute implementation stage."""
        # Load prompt template
        prompt_template, model = load_prompt("implement_plan")

        # Configure options
        options = ClaudeAgentOptions(
            permission_mode="acceptEdits",
            setting_sources=["project"],
            model=model,
            cwd=Path.cwd()
        )

        # Run agent - implement_plan prompt expects plan path
        result, stats = await run_agent(
            options=options,
            log_file=self.log_dir / "implement.log",
            prompt=f"{prompt_template}\n\nPlan: {self.plan_document}\n\n{self.previous_result}",
            verbose=False
        )

        # Output stats to stderr
        self.output_stats(f"📊 {stats.get_summary()}")

        # Return structured result
        return StageResult(
            status="success",
            result=result,
            document=None,
            stats={
                "total_tools": stats.total_tools,
                "errors": stats.errors,
                "tool_counts": stats.tool_counts
            }
        )


async def main() -> int:
    """Entry point."""
    stage = ImplementStage(sys.argv)
    return await stage.execute()


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
