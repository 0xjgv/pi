#!/usr/bin/env python3
"""Stage 1: Research - runs in isolated SDK session.

Usage: stage_research.py 'objective'

Runs /1_research_codebase command and outputs the result.
Look for the research document path in the output.
"""

from __future__ import annotations

import asyncio
import sys

from base import ClaudeSession


async def run_research(*, objective: str) -> str:
    """Run research command in isolated session."""
    session = ClaudeSession()
    return await session.run_command("/1_research_codebase", objective)


def main() -> None:
    """Execute research stage from command line."""
    if "--help" in sys.argv or "-h" in sys.argv:
        print(__doc__, file=sys.stderr)
        sys.exit(0)

    if len(sys.argv) < 2:
        print("Usage: stage_research.py 'objective'", file=sys.stderr)
        sys.exit(1)

    objective = sys.argv[1]
    if not objective.strip():
        print("Error: objective cannot be empty", file=sys.stderr)
        sys.exit(1)

    try:
        result = asyncio.run(run_research(objective=objective))
        print(result)
    except KeyboardInterrupt:
        print("\nInterrupted", file=sys.stderr)
        sys.exit(130)
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
