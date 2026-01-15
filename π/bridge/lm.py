"""Direct Claude Code LM for DSPy - no HTTP required."""

import asyncio
from typing import Any

from claude_agent_sdk import ClaudeAgentOptions, query
from dspy.clients.base_lm import BaseLM
from litellm.types.utils import Choices, Message, ModelResponse

SUPPORTED_MODELS = [
    "claude-haiku-4-5-20251001",
    "claude-sonnet-4-5-20250929",
    "claude-opus-4-5-20251101",
]
DEFAULT_MODEL = "claude-opus-4-5-20251101"


class ClaudeCodeLM(BaseLM):
    """DSPy LM that calls Claude Code directly via SDK."""

    _shared_loop: asyncio.AbstractEventLoop | None = None

    def __init__(self, model: str = DEFAULT_MODEL, **kwargs: Any) -> None:
        super().__init__(model=model, model_type="chat", **kwargs)
        if model not in SUPPORTED_MODELS:
            model = DEFAULT_MODEL
        self._model = model
        self._options = ClaudeAgentOptions(model=model)

    @classmethod
    def _get_event_loop(cls) -> asyncio.AbstractEventLoop:
        """Get or create a shared event loop."""
        if cls._shared_loop is not None and not cls._shared_loop.is_closed():
            return cls._shared_loop
        cls._shared_loop = asyncio.new_event_loop()
        asyncio.set_event_loop(cls._shared_loop)
        return cls._shared_loop

    def forward(
        self,
        prompt: str | None = None,
        messages: list[dict[str, Any]] | None = None,
    ) -> ModelResponse:
        """Sync completion via Claude Code SDK."""
        formatted = self._format_messages(messages) if messages else prompt or ""
        # We could intercept the messages that dspy here
        loop = self._get_event_loop()
        response_text = loop.run_until_complete(self._query(formatted))
        # We could also intercept the response text here
        return ModelResponse(
            id=f"claude-code-{id(self)}",
            model=self._model,
            choices=[
                Choices(
                    message=Message(content=response_text, role="assistant"),
                    finish_reason="stop",
                    index=0,
                )
            ],
        )

    def _format_messages(self, messages: list[dict[str, Any]]) -> str:
        """Format messages with XML tags for role delineation."""
        parts = []
        for msg in messages:
            role = msg.get("role", "user")
            content = msg.get("content", "")
            if role == "system":
                parts.append(f"<system>\n{content}\n</system>")
            elif role == "user":
                parts.append(f"<user>\n{content}\n</user>")
            elif role == "assistant":
                parts.append(f"<assistant>\n{content}\n</assistant>")
        return "\n\n".join(parts)

    async def _query(self, prompt: str) -> str:
        """Async query to Claude Code."""
        response_text = ""
        async for message in query(prompt=prompt, options=self._options):
            if hasattr(message, "content"):
                for block in message.content:
                    if hasattr(block, "text"):
                        response_text += block.text
        return response_text
