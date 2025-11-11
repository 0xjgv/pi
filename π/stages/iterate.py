#!/usr/bin/env python3
"""Iterate plan stage - external process wrapper."""

import asyncio
import sys
from pathlib import Path

from claude_agent_sdk import ClaudeAgentOptions
from π.agent import run_agent
from π.stages import StageResult, StageRunner
from π.utils import load_prompt


class IterateStage(StageRunner):
    """Iterate on plan stage."""

    def parse_args(self) -> None:
        """Parse: workflow_id user_query log_dir research_doc plan_doc previous_result"""
        if len(self.args) < 7:
            raise ValueError(
                f"Usage: {self.args[0]} <workflow_id> <user_query> <log_dir> <research_doc> <plan_doc> <previous_result>"
            )
        self.workflow_id = self.args[1]
        self.user_query = self.args[2]
        self.log_dir = Path(self.args[3])
        self.research_document = self.args[4]
        self.plan_document = self.args[5]
        self.previous_result = self.args[6]

    async def run_stage(self) -> StageResult:
        """Execute iteration stage."""
        # Load prompt template
        prompt_template, model = load_prompt("iterate_plan")
        prompt = prompt_template.format(
            research_document=self.research_document,
            plan_document=self.plan_document,
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
            log_file=self.log_dir / "iterate.log",
            prompt=f"{prompt}\n\n{self.previous_result}",
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
    stage = IterateStage(sys.argv)
    return await stage.execute()


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
