"""LLM model configuration and factory functions."""

import logging
from functools import lru_cache
from os import getenv

import dspy

from π.core.enums import Provider, Stage, Tier

logger = logging.getLogger(__name__)

# Provider → Tier → Model mapping
PROVIDER_MODELS: dict[Provider, dict[Tier, str]] = {
    Provider.Claude: {
        Tier.LOW: "claude-haiku-4-5-20251001",
        Tier.MED: "claude-sonnet-4-5-20250929",
        Tier.HIGH: "claude-opus-4-5-20251101",
    },
    Provider.Antigravity: {
        Tier.LOW: "gemini-3-flash-preview",
        Tier.MED: "gemini-claude-sonnet-4-5-thinking",
        Tier.HIGH: "gemini-3-pro-preview",
        Tier.ULTRA: "gemini-claude-opus-4-5-thinking",
    },
}

# For backwards compatibility
DEFAULT_MODELS = PROVIDER_MODELS[Provider.Claude]

# Stage → Model tier mapping (only active stages)
STAGE_TIERS: dict[Stage, Tier] = {
    Stage.RESEARCH_CODEBASE: Tier.HIGH,
    Stage.PLAN: Tier.HIGH,
    Stage.REVIEW_PLAN: Tier.HIGH,
    Stage.ITERATE_PLAN: Tier.HIGH,
    Stage.IMPLEMENT_PLAN: Tier.HIGH,
    Stage.COMMIT: Tier.LOW,
}

# Maximum ReAct iterations (same for all stages)
MAX_ITERS = 5


@lru_cache(maxsize=6)
def get_lm(provider: Provider, tier: Tier) -> dspy.LM:
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
