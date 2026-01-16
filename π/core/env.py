"""Environment variable validation."""


def validate_required_env() -> None:
    """Validate required environment variables at startup.

    Note: ClaudeCodeLM uses claude_agent_sdk auth automatically.
    No explicit API key configuration required.
    """
