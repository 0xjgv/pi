"""DSPy callbacks for ReAct iteration logging.

Provides visibility into agent thought/action/observation cycles.
"""

from __future__ import annotations

import logging
import os
import time
from typing import Any

from dspy.utils.callback import BaseCallback

from π.utils import truncate

logger = logging.getLogger(__name__)

# LM debug logging configuration
LM_PROMPT_TRUNCATE = 2000  # Max chars for prompt logging
LM_RESPONSE_TRUNCATE = 1000  # Max chars for response logging


def lm_debug_enabled() -> bool:
    """Check if verbose LM debug logging is enabled at runtime."""
    return os.getenv("PI_LM_DEBUG", "").lower() in ("1", "true", "yes")


def _summarize_inputs(inputs: dict[str, Any]) -> str:
    """Summarize inputs for logging (truncate long values)."""
    parts = []
    for k, v in inputs.items():
        parts.append(f"{k}={truncate(str(v))!r}")
    return ", ".join(parts)


class ReActLoggingCallback(BaseCallback):
    """Callback to log ReAct thought/action/observation cycles.

    Intercepts DSPy module execution to provide visibility into
    intermediate reasoning steps for debugging agent decisions.
    """

    def __init__(self) -> None:
        self._start_times: dict[str, float] = {}
        self._iteration_counts: dict[str, int] = {}
        self._lm_start_times: dict[str, float] = {}  # Track LM call timing

    def on_module_start(
        self,
        call_id: str,
        instance: Any,
        inputs: dict[str, Any],
    ) -> None:
        """Log when a ReAct module or iteration starts."""
        self._start_times[call_id] = time.perf_counter()
        module_name = type(instance).__name__

        if module_name == "ReAct":
            logger.info("ReAct START: %s", _summarize_inputs(inputs))
        elif module_name == "Predict":
            # Track iteration count for this ReAct execution
            parent_id = call_id.rsplit(".", 1)[0] if "." in call_id else call_id
            self._iteration_counts[parent_id] = (
                self._iteration_counts.get(parent_id, 0) + 1
            )
            iteration = self._iteration_counts[parent_id]
            logger.debug("ReAct iteration %d starting", iteration)

    def on_module_end(
        self,
        call_id: str,
        outputs: dict[str, Any] | None,
        exception: Exception | None,
    ) -> None:
        """Log ReAct iteration details after completion."""
        duration = time.perf_counter() - self._start_times.pop(call_id, 0)

        if exception:
            logger.error("ReAct FAILED (%.2fs): %s", duration, exception)
            return

        if not outputs:
            return

        # Log based on output type
        if self._is_thought_output(outputs):
            self._log_thought(outputs, duration)
        elif self._is_action_output(outputs):
            self._log_action(outputs, duration)
        elif self._is_final_output(outputs):
            self._log_completion(outputs, duration, call_id)

    def on_lm_start(
        self,
        call_id: str,
        instance: Any,
        inputs: dict[str, Any],
    ) -> None:
        """Log when an LM call starts (captures raw prompt)."""
        self._lm_start_times[call_id] = time.perf_counter()

        # Defensive model attribute access - try multiple locations
        model = (
            getattr(instance, "model", None)
            or getattr(instance, "model_name", None)
            or getattr(getattr(instance, "kwargs", {}), "model", None)
            or "unknown"
        )
        logger.debug("LM CALL START [%s]: model=%s", call_id[:8], model)

        # Verbose prompt logging when PI_LM_DEBUG=1
        if lm_debug_enabled():
            messages = inputs.get("messages", [])
            prompt_str = str(messages)
            total_len = len(prompt_str)
            prompt_str = truncate(
                prompt_str,
                LM_PROMPT_TRUNCATE,
                f"... [truncated, {total_len} total chars]",
            )
            logger.debug("LM PROMPT [%s]: %s", call_id[:8], prompt_str)

    def on_lm_end(
        self,
        call_id: str,
        outputs: dict[str, Any] | None,
        exception: Exception | None,
    ) -> None:
        """Log LM call completion with timing, tokens, and response."""
        start_time = self._lm_start_times.pop(call_id, None)
        latency_ms = int((time.perf_counter() - start_time) * 1000) if start_time else 0
        cid = call_id[:8]

        if exception:
            logger.error(
                "LM CALL FAILED [%s]: %s (latency=%dms)", cid, exception, latency_ms
            )
            return

        if not outputs:
            logger.debug("LM CALL END [%s]: no outputs (latency=%dms)", cid, latency_ms)
            return

        # Defensive fallback: check multiple possible locations for usage data
        response = outputs.get("response", {})
        response_usage = response.get("usage") if isinstance(response, dict) else None
        usage = outputs.get("usage") or response_usage or {}
        if not usage:
            logger.debug(
                "LM COMPLETE [%s]: latency=%dms, tokens=unavailable", cid, latency_ms
            )
        else:
            in_tok = usage.get("prompt_tokens", 0)
            out_tok = usage.get("completion_tokens", 0)
            cached = usage.get("cache_read_input_tokens", 0)
            tokens_str = f"tokens={{in={in_tok}, out={out_tok}, cached={cached}}}"
            logger.debug(
                "LM COMPLETE [%s]: latency=%dms, %s", cid, latency_ms, tokens_str
            )

        # Verbose response logging when PI_LM_DEBUG=1
        if lm_debug_enabled():
            response_str = str(outputs.get("response", outputs))
            total_len = len(response_str)
            response_str = truncate(
                response_str,
                LM_RESPONSE_TRUNCATE,
                f"... [truncated, {total_len} total chars]",
            )
            logger.debug("LM RESPONSE [%s]: %s", cid, response_str)

    def _is_thought_output(self, outputs: dict[str, Any]) -> bool:
        """Check if outputs contain a thought/reasoning step."""
        return any(k.startswith("Thought") or k == "next_thought" for k in outputs)

    def _is_action_output(self, outputs: dict[str, Any]) -> bool:
        """Check if outputs contain an action step."""
        return any(
            k in ("next_tool_name", "next_tool_args", "tool_name") for k in outputs
        )

    def _is_final_output(self, outputs: dict[str, Any]) -> bool:
        """Check if outputs are the final result."""
        return "trajectory" in outputs or any(
            k in ("research_doc_paths", "plan_doc_path", "status") for k in outputs
        )

    def _log_thought(self, outputs: dict[str, Any], duration: float) -> None:
        """Log a reasoning step."""
        thought = (
            outputs.get("next_thought")
            or outputs.get("Thought_1")
            or outputs.get("rationale", "")
        )
        if thought:
            logger.info("ReAct THOUGHT (%.2fs): %s", duration, truncate(thought, 500))

    def _log_action(self, outputs: dict[str, Any], duration: float) -> None:
        """Log an action step."""
        tool_name = outputs.get("next_tool_name") or outputs.get("tool_name", "unknown")
        tool_args = outputs.get("next_tool_args") or outputs.get("tool_args", {})
        logger.info(
            "ReAct ACTION (%.2fs): %s(%s)",
            duration,
            tool_name,
            truncate(str(tool_args), 200),
        )

        # Log observation if present
        if observation := outputs.get("observation"):
            logger.info("ReAct OBSERVATION: %s", truncate(str(observation), 500))

    def _log_completion(
        self, outputs: dict[str, Any], duration: float, call_id: str
    ) -> None:
        """Log final trajectory summary."""
        # Get iteration count
        parent_id = call_id.rsplit(".", 1)[0] if "." in call_id else call_id
        iterations = self._iteration_counts.pop(parent_id, 0)

        if trajectory := outputs.get("trajectory"):
            iterations = len([k for k in trajectory if str(k).startswith("thought_")])

        logger.info("ReAct COMPLETE (%.2fs): %d iterations", duration, iterations)


# Module-level instance for easy registration
react_logging_callback = ReActLoggingCallback()
