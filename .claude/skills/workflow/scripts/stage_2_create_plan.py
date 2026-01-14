#!/usr/bin/env python3
"""Stage 2: Design - creates implementation plan with thorough research.

Usage: stage_2_create_plan.py 'objective' [--research-doc PATH] [--session-id ID]

Runs /2_create_plan command and outputs the result.
Look for:
- Plan document path (e.g., thoughts/shared/plans/YYYY-MM-DD-*.md)
- SESSION_ID line at end of output for resumption
"""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path

from base import ClaudeSession


async def run_design(
    *,
    objective: str,
    research_doc: str | None = None,
    session_id: str | None = None,
) -> tuple[str, str]:
    """Run design commands in isolated session."""
    session = ClaudeSession()

    context = f"{research_doc}\n\n{objective}" if research_doc else objective

    return await session.run_command(
        "/2_create_plan",
        context,
        session_id=session_id,
    )


def _parse_args() -> tuple[str, str | None, str | None]:
    """Parse command line arguments."""
    if len(sys.argv) < 2:
        print(__doc__, file=sys.stderr)
        sys.exit(1)

    objective = sys.argv[1]
    research_doc = None
    session_id = None

    if "--research-doc" in sys.argv:
        idx = sys.argv.index("--research-doc")
        if idx + 1 < len(sys.argv):
            research_doc = sys.argv[idx + 1]
        else:
            print("Error: --research-doc requires a path", file=sys.stderr)
            sys.exit(1)

    if "--session-id" in sys.argv:
        idx = sys.argv.index("--session-id")
        if idx + 1 < len(sys.argv):
            session_id = sys.argv[idx + 1]
        else:
            print("Error: --session-id requires a value", file=sys.stderr)
            sys.exit(1)

    return objective, research_doc, session_id


def _validate_research_doc(path: str) -> None:
    """Validate research document exists."""
    doc_path = Path(path)
    if not doc_path.exists():
        print(f"Error: research document not found: {path}", file=sys.stderr)
        sys.exit(1)
    if not doc_path.is_file():
        print(f"Error: not a file: {path}", file=sys.stderr)
        sys.exit(1)


def main() -> None:
    """Execute design stage from command line."""
    if "--help" in sys.argv or "-h" in sys.argv:
        print(__doc__, file=sys.stderr)
        sys.exit(0)

    objective, research_doc, session_id = _parse_args()

    if not objective.strip():
        print("Error: objective cannot be empty", file=sys.stderr)
        sys.exit(1)

    if research_doc:
        _validate_research_doc(research_doc)

    try:
        result, new_session_id = asyncio.run(
            run_design(
                objective=objective,
                research_doc=research_doc,
                session_id=session_id,
            )
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
