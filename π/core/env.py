"""Environment variable validation."""

from __future__ import annotations


def validate_required_env() -> None:
    """Validate required environment variables at startup.

    Note: ClaudeCodeLM uses claude_agent_sdk auth automatically.
    No explicit API key configuration required.
    """
