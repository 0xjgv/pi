#!/usr/bin/env python3
"""Stage 3: Execute - implements plan in isolated SDK session.

Usage: stage_execute.py 'objective' --plan-doc PATH

Runs /5_implement_plan command and outputs the result.
Look for files changed and commit hash in the output.
"""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path

from base import ClaudeSession


async def run_execute(*, objective: str, plan_doc: str) -> str:
    """Run execute commands in isolated session."""
    session = ClaudeSession()
    context = f"Objective: {objective}\n\nPlan document: {plan_doc}"
    return await session.run_command("/5_implement_plan", context)


def _parse_args() -> tuple[str, str]:
    """Parse command line arguments."""
    if len(sys.argv) < 2:
        print("Usage: stage_execute.py 'objective' --plan-doc PATH", file=sys.stderr)
        sys.exit(1)

    objective = sys.argv[1]
    plan_doc = None

    if "--plan-doc" in sys.argv:
        idx = sys.argv.index("--plan-doc")
        if idx + 1 < len(sys.argv):
            plan_doc = sys.argv[idx + 1]
        else:
            print("Error: --plan-doc requires a path", file=sys.stderr)
            sys.exit(1)

    if not plan_doc:
        print("Error: --plan-doc is required", file=sys.stderr)
        sys.exit(1)

    return objective, plan_doc


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
    """Execute implementation stage from command line."""
    if "--help" in sys.argv or "-h" in sys.argv:
        print(__doc__, file=sys.stderr)
        sys.exit(0)

    objective, plan_doc = _parse_args()

    if not objective.strip():
        print("Error: objective cannot be empty", file=sys.stderr)
        sys.exit(1)

    _validate_plan_doc(plan_doc)

    try:
        result = asyncio.run(run_execute(objective=objective, plan_doc=plan_doc))
        print(result)
    except KeyboardInterrupt:
        print("\nInterrupted", file=sys.stderr)
        sys.exit(130)
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
