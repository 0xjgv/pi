"""Environment variable validation."""

from __future__ import annotations

import os
import sys


def validate_required_env() -> None:
    """Validate required environment variables at startup.

    Required:
        CLIPROXY_API_KEY: API key for LM proxy

    Optional (with defaults):
        CLIPROXY_API_BASE: LM proxy base URL (default: localhost:8317)
        MEM0_API_KEY: Mem0 hosted API (falls back to self-hosted)

    Exits with code 1 if required variables are missing.
    """
    missing: list[str] = []

    if not os.getenv("CLIPROXY_API_KEY"):
        missing.append("CLIPROXY_API_KEY")

    if missing:
        print(
            f"Error: Missing required environment variables: {', '.join(missing)}",
            file=sys.stderr,
        )
        print(
            "Set them in .env or export them before running π",
            file=sys.stderr,
        )
        sys.exit(1)
