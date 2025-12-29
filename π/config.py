"""π configuration - providers, stages, and agent options."""

import logging
from enum import StrEnum
from functools import lru_cache
from os import getenv
from pathlib import Path

import dspy
from claude_agent_sdk import ClaudeAgentOptions, HookMatcher

from π.hooks import check_bash_command, check_file_format
from π.support import can_use_tool

logger = logging.getLogger(__name__)


class Provider(StrEnum):
    Claude = "claude"
    Antigravity = "antigravity"
    OpenAI = "openai"


class Stage(StrEnum):
    """Workflow stages."""

    CLARIFY = "clarify"
    RESEARCH = "research"
    PLAN = "plan"
    REVIEW_PLAN = "review_plan"
    ITERATE_PLAN = "iterate_plan"


# Provider → Tier → Model mapping
PROVIDER_MODELS: dict[Provider, dict[str, str]] = {
    Provider.Claude: {
        "low": "claude-haiku-4-5-20251001",
        "med": "claude-sonnet-4-5-20250929",
        "high": "claude-opus-4-5-20251101",
    },
    Provider.Antigravity: {
        "low": "gemini-3-flash-preview",
        "med": "gemini-claude-sonnet-4-5-thinking",
        "high": "gemini-3-pro-preview",
    },
    Provider.OpenAI: {
        "low": "gpt-5.2",
        "med": "gpt-5.2",
        "high": "gpt-5.2-codex",
    },
}

# For backwards compatibility
DEFAULT_MODELS = PROVIDER_MODELS[Provider.Claude]

# Stage → Model tier mapping (only active stages)
STAGE_TIERS: dict[Stage, str] = {
    Stage.RESEARCH: "high",
    Stage.PLAN: "high",
    Stage.REVIEW_PLAN: "high",
    Stage.ITERATE_PLAN: "high",
}

# Maximum ReAct iterations (same for all stages)
MAX_ITERS = 3


@lru_cache(maxsize=6)
def get_lm(provider: Provider, tier: str) -> dspy.LM:
    """Get cached LM instance for provider/tier combination.

    Args:
        provider: AI provider (claude, antigravity, openai)
        tier: Model tier (low, med, high)

    Returns:
        Configured dspy.LM instance

    Raises:
        KeyError: If provider or tier is invalid
    """
    base_url = getenv("CLIPROXY_API_BASE", "http://localhost:8317")
    raw_model = PROVIDER_MODELS[provider][tier]
    logger.debug("Resolving LM: %s/%s → %s", provider, tier, raw_model)

    # HACK: LiteLLM auto-routes gemini-* models to Vertex AI, which requires
    # Google Cloud auth. We bypass this by prefixing with "openai/" to force
    # the OpenAI-compatible code path through our proxy instead.
    if raw_model.startswith("gemini"):
        model = f"openai/{raw_model}"
        api_base = f"{base_url}/v1"
        logger.debug("Gemini hack: %s → %s, base: %s", raw_model, model, api_base)
    else:
        model = raw_model
        api_base = base_url

    logger.debug("LM config: model=%s, api_base=%s", model, api_base)
    return dspy.LM(
        api_key=getenv("CLIPROXY_API_KEY"),
        api_base=api_base,
        model=model,
    )


# https://code.claude.com/docs/en/settings#tools-available-to-claude
AVAILABLE_TOOLS = [
    "AskUserQuestion",
    "Bash",
    "BashOutput",
    "Edit",
    "ExitPlanMode",
    "Glob",
    "Grep",
    "KillShell",
    "NotebookEdit",
    "Read",
    "Skill",
    "SlashCommand",
    "Task",
    "TodoWrite",
    "WebFetch",
    "WebSearch",
    "Write",
]


def get_agent_options(
    *,
    system_prompt: str | None = None,
    cwd: Path = Path.cwd(),
) -> ClaudeAgentOptions:
    """Get Claude agent options with hooks and permissions configured."""
    return ClaudeAgentOptions(
        hooks={
            "PostToolUse": [
                HookMatcher(matcher="Write|Edit", hooks=[check_file_format]),
            ],
            "PreToolUse": [
                HookMatcher(matcher="Bash", hooks=[check_bash_command]),
            ],
        },
        permission_mode="acceptEdits",
        allowed_tools=AVAILABLE_TOOLS,
        system_prompt=system_prompt,
        setting_sources=["project"],
        can_use_tool=can_use_tool,
        cwd=cwd,
    )


__all__ = [
    "AVAILABLE_TOOLS",
    "DEFAULT_MODELS",
    "MAX_ITERS",
    "PROVIDER_MODELS",
    "Provider",
    "STAGE_TIERS",
    "Stage",
    "get_agent_options",
    "get_lm",
]
