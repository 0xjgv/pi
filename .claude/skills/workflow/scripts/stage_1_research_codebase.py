#!/usr/bin/env python3
"""Stage 1: Research - documents codebase in isolated SDK session.

Usage: stage_1_research_codebase.py 'query' [--session-id ID]

Runs /1_research_codebase command and outputs the result.
Look for:
- Research document path (e.g., thoughts/shared/research/YYYY-MM-DD-*.md)
- SESSION_ID line at end of output for resumption
"""

from __future__ import annotations

import asyncio
import sys

from base import ClaudeSession


async def run_research(
    *,
    objective: str,
    session_id: str | None = None,
) -> tuple[str, str]:
    """Run research command in isolated session."""
    session = ClaudeSession()
    return await session.run_command(
        "/1_research_codebase",
        objective,
        session_id=session_id,
    )


def _parse_args() -> tuple[str, str | None]:
    """Parse command line arguments."""
    if len(sys.argv) < 2:
        print(
            "Usage: stage_1_research_codebase.py 'query' [--session-id ID]",
            file=sys.stderr,
        )
        sys.exit(1)

    objective = sys.argv[1]
    session_id = None

    if "--session-id" in sys.argv:
        idx = sys.argv.index("--session-id")
        if idx + 1 < len(sys.argv):
            session_id = sys.argv[idx + 1]
        else:
            print("Error: --session-id requires a value", file=sys.stderr)
            sys.exit(1)

    return objective, session_id


def main() -> None:
    """Execute research stage from command line."""
    if "--help" in sys.argv or "-h" in sys.argv:
        print(__doc__, file=sys.stderr)
        sys.exit(0)

    objective, session_id = _parse_args()

    if not objective.strip():
        print("Error: objective cannot be empty", file=sys.stderr)
        sys.exit(1)

    try:
        result, new_session_id = asyncio.run(
            run_research(objective=objective, session_id=session_id)
        )
        print(result)
        print("\n---")
        print(f"SESSION_ID: {new_session_id}")
    except KeyboardInterrupt:
        print("\nInterrupted", file=sys.stderr)
        sys.exit(130)
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
