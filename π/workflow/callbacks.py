"""DSPy callbacks for logging LM interactions."""

import logging
from typing import Any

from dspy.utils.callback import BaseCallback

logger = logging.getLogger(__name__)

# Truncation limit for prompts/responses
_TRUNCATE_LIMIT = 2000


def _truncate(text: str, limit: int = _TRUNCATE_LIMIT) -> str:
    """Truncate text with ellipsis if exceeding limit."""
    if len(text) <= limit:
        return text
    return text[:limit] + "..."


class LoggingCallback(BaseCallback):
    """Callback that logs DSPy LM interactions.

    Logs prompts at on_lm_start and responses at on_lm_end.
    All logging is at DEBUG level to avoid noise in normal operation.
    """

    def on_lm_start(self, **kwargs: Any) -> None:
        """Log LM prompt before execution."""
        inputs = kwargs.get("inputs", {})
        # inputs contains 'messages' or 'prompt' depending on adapter
        if "messages" in inputs:
            # Chat format - log last user message (the actual prompt)
            messages = inputs["messages"]
            if messages:
                last_msg = messages[-1]
                content = last_msg.get("content", str(last_msg))
                logger.debug("LM prompt: %s", _truncate(str(content)))
        elif "prompt" in inputs:
            # Text format
            logger.debug("LM prompt: %s", _truncate(str(inputs["prompt"])))
        else:
            # Fallback - log entire inputs
            logger.debug("LM inputs: %s", _truncate(str(inputs)))

    def on_lm_end(self, **kwargs: Any) -> None:
        """Log LM response after execution."""
        exception = kwargs.get("exception")
        if exception:
            logger.warning("LM error: %s", exception)
            return

        outputs = kwargs.get("outputs", {})
        if outputs:
            logger.debug("LM response: %s", _truncate(str(outputs)))

    def on_tool_start(self, **kwargs: Any) -> None:
        """Log tool invocation."""
        instance = kwargs.get("instance")
        inputs = kwargs.get("inputs", {})
        fallback = type(instance).__name__ if instance else "unknown"
        tool_name = getattr(instance, "name", fallback)
        logger.debug("DSPy tool start: %s | args=%s", tool_name, _truncate(str(inputs)))

    def on_tool_end(self, **kwargs: Any) -> None:
        """Log tool completion."""
        exception = kwargs.get("exception")
        outputs = kwargs.get("outputs", {})
        if exception:
            logger.warning("DSPy tool error: %s", exception)
        else:
            logger.debug("DSPy tool end: %s", _truncate(str(outputs)))
