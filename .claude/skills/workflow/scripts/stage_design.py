#!/usr/bin/env python3
"""Stage 2: Design - runs create→review→iterate in isolated SDK session."""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path

# Add script directory to path for base import
sys.path.insert(0, str(Path(__file__).parent))

from base import ClaudeSession  # noqa: E402


async def run_design(objective: str, research_doc: str | None = None) -> str:
    """Run design commands in isolated session."""
    session = ClaudeSession()

    context = f"Objective: {objective}"
    if research_doc:
        context += f"\n\nResearch document: {research_doc}"

    return await session.run_command("/2_create_plan", context)


def main() -> None:
    if len(sys.argv) < 2:
        print("Usage: stage_design.py 'objective' [--research-doc PATH]")
        sys.exit(1)

    objective = sys.argv[1]
    research_doc = None

    if "--research-doc" in sys.argv:
        idx = sys.argv.index("--research-doc")
        if idx + 1 < len(sys.argv):
            research_doc = sys.argv[idx + 1]

    result = asyncio.run(run_design(objective, research_doc))
    print(result)


if __name__ == "__main__":
    main()
