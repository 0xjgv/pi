import logging
from enum import StrEnum
from functools import lru_cache
from os import getenv

import dspy

logger = logging.getLogger(__name__)


class AntigravityModel(StrEnum):
    """Antigravity models (Gemini-Claude hybrids)."""

    GeminiFlash = "gemini-3-flash-preview"
    GeminiPro = "gemini-3-pro-preview"
    ClaudeSonnet = "gemini-claude-sonnet-4-5"
    ClaudeSonnetThinking = "gemini-claude-sonnet-4-5-thinking"
    ClaudeOpusThinking = "gemini-claude-opus-4-5-thinking"


class ClaudeModel(StrEnum):
    """Anthropic Claude models."""

    Haiku = "claude-haiku-4-5-20251001"
    Sonnet = "claude-sonnet-4-5-20250929"
    Opus = "claude-opus-4-5-20251101"


class OpenAIModel(StrEnum):
    """OpenAI models."""

    GPT52 = "gpt-5.2"
    GPT52Codex = "gpt-5.2-codex"


class Provider(StrEnum):
    Claude = "claude"
    Antigravity = "antigravity"
    OpenAI = "openai"


# Provider → Tier → Model mapping
PROVIDER_MODELS: dict[Provider, dict[str, str]] = {
    Provider.Claude: {
        "low": ClaudeModel.Haiku,
        "med": ClaudeModel.Sonnet,
        "high": ClaudeModel.Opus,
    },
    Provider.Antigravity: {
        "low": AntigravityModel.GeminiFlash,
        "med": AntigravityModel.ClaudeSonnetThinking,
        "high": AntigravityModel.GeminiPro,
    },
    Provider.OpenAI: {
        "low": OpenAIModel.GPT52,
        "med": OpenAIModel.GPT52,
        "high": OpenAIModel.GPT52Codex,
    },
}

# For backwards compatibility
DEFAULT_MODELS = PROVIDER_MODELS[Provider.Claude]


def get_model(*, provider: Provider, tier: str) -> str:
    """Resolve provider and tier to a model identifier.

    Args:
        provider: The AI provider (claude, antigravity, openai)
        tier: The thinking tier (low, med, high)

    Returns:
        Model identifier string for DSPy

    Raises:
        KeyError: If provider or tier is invalid
    """
    return PROVIDER_MODELS[provider][tier]


@lru_cache(maxsize=6)
def get_lm(provider: Provider, tier: str) -> dspy.LM:
    """Get cached LM instance for provider/tier combination.

    Args:
        provider: AI provider (claude, antigravity, openai)
        tier: Model tier (low, med, high)

    Returns:
        Configured dspy.LM instance
    """
    base_url = getenv("CLIPROXY_API_BASE", "http://localhost:8317")
    raw_model = get_model(provider=provider, tier=tier)
    logger.debug(f"Resolving LM: {provider}/{tier} → {raw_model}")

    # HACK: LiteLLM auto-routes gemini-* models to Vertex AI, which requires
    # Google Cloud auth. We bypass this by prefixing with "openai/" to force
    # the OpenAI-compatible code path through our proxy instead.
    #
    # Different providers also expect different endpoint paths:
    # - Anthropic: {base}/v1/messages (LiteLLM appends /v1/messages)
    # - OpenAI:    {base}/v1/chat/completions (LiteLLM appends /chat/completions)
    if raw_model.startswith("gemini"):
        model = f"openai/{raw_model}"
        api_base = f"{base_url}/v1"
        logger.debug(f"Gemini hack: {raw_model} → {model}, base: {api_base}")
    else:
        model = raw_model
        api_base = base_url

    logger.debug(f"LM config: model={model}, api_base={api_base}")
    return dspy.LM(
        api_key=getenv("CLIPROXY_API_KEY"),
        api_base=api_base,
        model=model,
    )
