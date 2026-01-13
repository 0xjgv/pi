#!/usr/bin/env python3
"""Stage 1: Research - runs in isolated SDK session."""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path

# Add script directory to path for base import
sys.path.insert(0, str(Path(__file__).parent))

from base import ClaudeSession  # noqa: E402


async def run_research(objective: str) -> str:
    """Run research command in isolated session."""
    session = ClaudeSession()
    return await session.run_command("/1_research_codebase", objective)


def main() -> None:
    if len(sys.argv) < 2:
        print("Usage: stage_research.py 'objective'", file=sys.stderr)
        sys.exit(1)

    objective = sys.argv[1]
    result = asyncio.run(run_research(objective))
    print(result)


if __name__ == "__main__":
    main()
