#!/usr/bin/env python3
"""Stage 6: Commit - creates git commits.

Usage: stage_6_commit.py [message] [--session-id ID]

Runs /6_commit command and outputs the result.
Look for:
- Commit hash
- Files committed
- SESSION_ID line at end of output for resumption
"""

from __future__ import annotations

import asyncio
import sys

from base import ClaudeSession


async def run_commit(
    *,
    message: str | None = None,
    session_id: str | None = None,
) -> tuple[str, str]:
    """Run commit command in isolated session."""
    session = ClaudeSession()
    context = f"Commit hint: {message}" if message else ""
    return await session.run_command(
        "/6_commit",
        context,
        session_id=session_id,
    )


def _parse_args() -> tuple[str | None, str | None]:
    """Parse command line arguments."""
    message = None
    session_id = None

    # First positional arg (if not a flag) is the message
    args = [a for a in sys.argv[1:] if not a.startswith("-")]
    if args:
        message = args[0]

    if "--session-id" in sys.argv:
        idx = sys.argv.index("--session-id")
        if idx + 1 < len(sys.argv):
            session_id = sys.argv[idx + 1]
        else:
            print("Error: --session-id requires a value", file=sys.stderr)
            sys.exit(1)

    return message, session_id


def main() -> None:
    """Execute commit stage from command line."""
    if "--help" in sys.argv or "-h" in sys.argv:
        print(__doc__, file=sys.stderr)
        sys.exit(0)

    message, session_id = _parse_args()

    try:
        result, new_session_id = asyncio.run(
            run_commit(
                message=message,
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
