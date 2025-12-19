from logging import Logger
from os import getenv

import dspy

# TODO: test different models in ReAct
# gemini-3-pro-preview
# gemini-3-flash-preview
THINKING_MODELS = {
    "low": "claude-haiku-4-5-20251001",
    "med": "claude-sonnet-4-5-20250929",
    "high": "claude-opus-4-5-20251101",
}


def configure_dspy(*, model: str = THINKING_MODELS["low"], logger: Logger) -> None:
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
