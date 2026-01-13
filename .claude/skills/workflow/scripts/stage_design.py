#!/usr/bin/env python3
"""Stage 2: Design - creates implementation plan in isolated SDK session.

Usage: stage_design.py 'objective' [--research-doc PATH]

Runs /2_create_plan command and outputs the result.
Look for the plan document path in the output.
"""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path

# Add script directory to path for base import
sys.path.insert(0, str(Path(__file__).parent))

from base import ClaudeSession


async def run_design(*, objective: str, research_doc: str | None = None) -> str:
    """Run design commands in isolated session."""
    session = ClaudeSession()

    context = f"Objective: {objective}"
    if research_doc:
        context += f"\n\nResearch document: {research_doc}"

    return await session.run_command("/2_create_plan", context)


def _parse_args() -> tuple[str, str | None]:
    """Parse command line arguments."""
    if len(sys.argv) < 2:
        print(
            "Usage: stage_design.py 'objective' [--research-doc PATH]",
            file=sys.stderr,
        )
        sys.exit(1)

    objective = sys.argv[1]
    research_doc = None

    if "--research-doc" in sys.argv:
        idx = sys.argv.index("--research-doc")
        if idx + 1 < len(sys.argv):
            research_doc = sys.argv[idx + 1]
        else:
            print("Error: --research-doc requires a path", file=sys.stderr)
            sys.exit(1)

    return objective, research_doc


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

    objective, research_doc = _parse_args()

    if not objective.strip():
        print("Error: objective cannot be empty", file=sys.stderr)
        sys.exit(1)

    if research_doc:
        _validate_research_doc(research_doc)

    try:
        result = asyncio.run(run_design(objective=objective, research_doc=research_doc))
        print(result)
    except KeyboardInterrupt:
        print("\nInterrupted", file=sys.stderr)
        sys.exit(130)
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
