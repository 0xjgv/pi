#!/usr/bin/env python3
"""Stage 3: Review - reviews plan for completeness and accuracy.

Usage: stage_3_review_plan.py --plan-doc PATH [--session-id ID]

Runs /3_review_plan command and outputs the result.
Look for:
- Review findings (blocking, high-priority, optional)
- SESSION_ID line at end of output for resumption
"""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path

from base import ClaudeSession


async def run_review_plan(
    *,
    plan_doc: str,
    session_id: str | None = None,
) -> tuple[str, str]:
    """Run review plan command in isolated session."""
    session = ClaudeSession()
    context = plan_doc
    return await session.run_command(
        "/3_review_plan",
        context,
        session_id=session_id,
    )


def _parse_args() -> tuple[str, str | None]:
    """Parse command line arguments."""
    plan_doc = None
    session_id = None

    if "--plan-doc" in sys.argv:
        idx = sys.argv.index("--plan-doc")
        if idx + 1 < len(sys.argv):
            plan_doc = sys.argv[idx + 1]
        else:
            print("Error: --plan-doc requires a path", file=sys.stderr)
            sys.exit(1)

    if "--session-id" in sys.argv:
        idx = sys.argv.index("--session-id")
        if idx + 1 < len(sys.argv):
            session_id = sys.argv[idx + 1]
        else:
            print("Error: --session-id requires a value", file=sys.stderr)
            sys.exit(1)

    if not plan_doc:
        print("Error: --plan-doc is required", file=sys.stderr)
        sys.exit(1)

    return plan_doc, session_id


def _validate_plan_doc(path: str) -> None:
    """Validate plan document exists."""
    doc_path = Path(path)
    if not doc_path.exists():
        print(f"Error: plan document not found: {path}", file=sys.stderr)
        sys.exit(1)
    if not doc_path.is_file():
        print(f"Error: not a file: {path}", file=sys.stderr)
        sys.exit(1)


def main() -> None:
    """Execute review plan stage from command line."""
    if "--help" in sys.argv or "-h" in sys.argv:
        print(__doc__, file=sys.stderr)
        sys.exit(0)

    plan_doc, session_id = _parse_args()
    _validate_plan_doc(plan_doc)

    try:
        result, new_session_id = asyncio.run(
            run_review_plan(
                plan_doc=plan_doc,
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
