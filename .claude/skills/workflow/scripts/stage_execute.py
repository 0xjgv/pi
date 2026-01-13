#!/usr/bin/env python3
"""Stage 3: Execute - runs implement→commit in isolated SDK session."""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path

# Add script directory to path for base import
sys.path.insert(0, str(Path(__file__).parent))

from base import ClaudeSession  # noqa: E402


async def run_execute(objective: str, plan_doc: str) -> str:
    """Run execute commands in isolated session."""
    session = ClaudeSession()

    context = f"Objective: {objective}\n\nPlan document: {plan_doc}"

    return await session.run_command("/5_implement_plan", context)


def main() -> None:
    if len(sys.argv) < 2:
        print("Usage: stage_execute.py 'objective' --plan-doc PATH")
        sys.exit(1)

    objective = sys.argv[1]
    plan_doc = None

    if "--plan-doc" in sys.argv:
        idx = sys.argv.index("--plan-doc")
        if idx + 1 < len(sys.argv):
            plan_doc = sys.argv[idx + 1]

    if not plan_doc:
        print("Error: --plan-doc is required")
        sys.exit(1)

    result = asyncio.run(run_execute(objective, plan_doc))
    print(result)


if __name__ == "__main__":
    main()
