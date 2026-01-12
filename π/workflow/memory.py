"""Mem0 client configuration for semantic memory layer.

Provides memory persistence for lessons learned, blockers, and insights
across workflow iterations.
"""

from __future__ import annotations

import logging
import os
from functools import lru_cache
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from mem0 import Memory, MemoryClient

logger = logging.getLogger(__name__)


class NoOpMemoryClient:
    """Fallback client when memory service is unavailable.

    Returns empty results instead of raising errors, allowing workflows
    to continue without memory functionality.
    """

    def __init__(self, reason: str = "Memory service unavailable") -> None:
        self._reason = reason
        logger.warning("Using NoOpMemoryClient: %s", reason)

    def add(self, *_args: Any, **_kwargs: Any) -> dict[str, Any]:
        """No-op add that logs but doesn't store."""
        logger.debug("NoOp: add() called but memory unavailable")
        return {"id": None, "status": "skipped"}

    def search(self, *_args: Any, **_kwargs: Any) -> dict[str, list[Any]]:
        """Return empty results."""
        return {"results": []}

    def get_all(self, *_args: Any, **_kwargs: Any) -> dict[str, list[Any]]:
        """Return empty results."""
        return {"results": []}


@lru_cache(maxsize=1)
def get_memory_client() -> Memory | MemoryClient | NoOpMemoryClient:
    """Get configured Mem0 client with fallback on failure.

    Mode selection based on environment:
    - If MEM0_API_KEY is set: Use Mem0 Platform (hosted)
    - Otherwise: Use self-hosted with cliproxy + ChromaDB
    - On any error: Return NoOpMemoryClient for graceful degradation
    """
    mem0_api_key = os.getenv("MEM0_API_KEY")

    try:
        if mem0_api_key:
            return _get_hosted_client(mem0_api_key)
        return _get_self_hosted_client()
    except ImportError as e:
        return NoOpMemoryClient(f"mem0 not installed: {e}")
    except Exception as e:
        return NoOpMemoryClient(f"Initialization failed: {e}")


def _get_hosted_client(api_key: str) -> MemoryClient:
    """Get Mem0 Platform (hosted) client."""
    from mem0 import MemoryClient

    logger.debug("Initializing Mem0 Platform client (hosted)")
    return MemoryClient(api_key=api_key)


def _get_self_hosted_client() -> Memory:
    """Get self-hosted Mem0 client using cliproxy + ChromaDB."""
    from mem0 import Memory

    api_base = os.getenv("CLIPROXY_API_BASE", "http://localhost:8317")
    api_key = os.getenv("CLIPROXY_API_KEY", "")

    config = {
        "llm": {
            "provider": "openai",
            "config": {
                "model": "claude-sonnet-4-20250514",
                "openai_base_url": api_base,
                "api_key": api_key,
            },
        },
        "embedder": {
            "provider": "openai",
            "config": {
                "model": "text-embedding-3-small",
                "openai_base_url": api_base,
                "api_key": api_key,
            },
        },
        "vector_store": {
            "provider": "chroma",
            "config": {
                "collection_name": "pi_memories",
                "path": ".π/memory/chroma",
            },
        },
    }

    logger.debug("Initializing Mem0 client (self-hosted) with api_base=%s", api_base)
    return Memory.from_config(config)
