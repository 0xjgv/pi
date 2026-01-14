#!/usr/bin/env python3
"""Stage 4: Iterate - refines plan based on feedback.

Usage: stage_4_iterate_plan.py --plan-doc PATH [--feedback "text"] [--session-id ID]

Runs /4_iterate_plan command and outputs the result.
Look for:
- Updated plan confirmation
- SESSION_ID line at end of output for resumption
"""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path

from base import ClaudeSession


async def run_iterate_plan(
    *,
    plan_doc: str,
    feedback: str | None = None,
    session_id: str | None = None,
) -> tuple[str, str]:
    """Run iterate plan command in isolated session."""
    session = ClaudeSession()

    context = f"{plan_doc}\n\n{feedback}" if feedback else plan_doc

    return await session.run_command(
        "/4_iterate_plan",
        context,
        session_id=session_id,
    )


def _parse_args() -> tuple[str, str | None, str | None]:
    """Parse command line arguments."""
    plan_doc = None
    feedback = None
    session_id = None

    if "--plan-doc" in sys.argv:
        idx = sys.argv.index("--plan-doc")
        if idx + 1 < len(sys.argv):
            plan_doc = sys.argv[idx + 1]
        else:
            print("Error: --plan-doc requires a path", file=sys.stderr)
            sys.exit(1)

    if "--feedback" in sys.argv:
        idx = sys.argv.index("--feedback")
        if idx + 1 < len(sys.argv):
            feedback = sys.argv[idx + 1]
        else:
            print("Error: --feedback requires a value", file=sys.stderr)
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

    return plan_doc, feedback, session_id


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
    """Execute iterate plan stage from command line."""
    if "--help" in sys.argv or "-h" in sys.argv:
        print(__doc__, file=sys.stderr)
        sys.exit(0)

    plan_doc, feedback, session_id = _parse_args()
    _validate_plan_doc(plan_doc)

    try:
        result, new_session_id = asyncio.run(
            run_iterate_plan(
                plan_doc=plan_doc,
                feedback=feedback,
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
