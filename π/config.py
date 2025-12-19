from enum import StrEnum
from logging import Logger
from os import getenv

import dspy


# TODO: test different models in ReAct
class GeminiModel(StrEnum):
    Flash = "gemini-3-flash-preview"
    Pro = "gemini-3-pro-preview"


class ClaudeModel(StrEnum):
    Haiku = "claude-haiku-4-5-20251001"
    Sonnet = "claude-sonnet-4-5-20250929"
    Opus = "claude-opus-4-5-20251101"


class OpenAIModel(StrEnum):
    GPT52Codex = "gpt-5.2-codex"


class ThinkingModel(StrEnum):
    Low = ClaudeModel.Haiku
    Med = ClaudeModel.Sonnet
    High = ClaudeModel.Opus


class Provider(StrEnum):
    Claude = "claude"
    Gemini = "gemini"
    OpenAI = "openai"


# Provider → Tier → Model mapping
PROVIDER_MODELS: dict[Provider, dict[str, str]] = {
    Provider.Claude: {
        "low": ClaudeModel.Haiku,
        "med": ClaudeModel.Sonnet,
        "high": ClaudeModel.Opus,
    },
    Provider.Gemini: {
        "low": GeminiModel.Flash,
        "med": GeminiModel.Flash,  # Only 2 Gemini tiers available
        "high": GeminiModel.Pro,
    },
    Provider.OpenAI: {
        "med": OpenAIModel.GPT52Codex,
    },
}

# For backwards compatibility with tests expecting DEFAULT_MODELS
DEFAULT_MODELS = PROVIDER_MODELS[Provider.Claude]


def get_model(*, provider: Provider, tier: str) -> str:
    """Resolve provider and tier to a model identifier.

    Args:
        provider: The AI provider (claude, gemini)
        tier: The thinking tier (low, med, high)

    Returns:
        Model identifier string for DSPy

    Raises:
        KeyError: If provider or tier is invalid
    """
    return PROVIDER_MODELS[provider][tier]


def configure_dspy(*, model: str, logger: Logger) -> None:
    """Configure DSPy with the specified model."""
    try:
        lm = dspy.LM(
            api_base=getenv("CLIPROXY_API_BASE", "http://localhost:8317"),
            api_key=getenv("CLIPROXY_API_KEY"),
            model=model,
        )
        dspy.configure(lm=lm)
    except Exception as e:
        logger.warning("DSPy LM not configured: %s", e, exc_info=True)
