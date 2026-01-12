"""DSPy callbacks for ReAct iteration logging.

Provides visibility into agent thought/action/observation cycles.
"""

from __future__ import annotations

import logging
import time
from typing import Any

from dspy.utils.callback import BaseCallback

logger = logging.getLogger(__name__)


def _summarize_inputs(inputs: dict[str, Any]) -> str:
    """Summarize inputs for logging (truncate long values)."""
    parts = []
    for k, v in inputs.items():
        val_str = str(v)
        if len(val_str) > 100:
            val_str = val_str[:100] + "..."
        parts.append(f"{k}={val_str!r}")
    return ", ".join(parts)


class ReActLoggingCallback(BaseCallback):
    """Callback to log ReAct thought/action/observation cycles.

    Intercepts DSPy module execution to provide visibility into
    intermediate reasoning steps for debugging agent decisions.
    """

    def __init__(self) -> None:
        self._start_times: dict[str, float] = {}
        self._iteration_counts: dict[str, int] = {}

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
            thought_preview = thought[:500] + "..." if len(thought) > 500 else thought
            logger.info("ReAct THOUGHT (%.2fs): %s", duration, thought_preview)

    def _log_action(self, outputs: dict[str, Any], duration: float) -> None:
        """Log an action step."""
        tool_name = outputs.get("next_tool_name") or outputs.get("tool_name", "unknown")
        tool_args = outputs.get("next_tool_args") or outputs.get("tool_args", {})
        args_str = str(tool_args)[:200]
        logger.info("ReAct ACTION (%.2fs): %s(%s)", duration, tool_name, args_str)

        # Log observation if present
        if observation := outputs.get("observation"):
            obs_preview = (
                str(observation)[:500] + "..."
                if len(str(observation)) > 500
                else str(observation)
            )
            logger.info("ReAct OBSERVATION: %s", obs_preview)

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
