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

    from π.core.enums import Provider, Tier
    from π.core.models import PROVIDER_MODELS

    api_base = os.getenv("CLIPROXY_API_BASE", "http://localhost:8317")
    api_key = os.getenv("CLIPROXY_API_KEY", "")
    model = PROVIDER_MODELS[Provider.Claude][Tier.MED]

    config = {
        "llm": {
            "provider": "openai",
            "config": {
                "model": model,
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


def cleanup_chroma_store(
    *,
    chroma_path: str | None = None,
    retention_days: int | None = None,
) -> bool:
    """Archive ChromaDB store if older than retention period.

    Moves entire chroma directory to .π/memory/archived/{timestamp}/
    when store age exceeds retention_days.

    Args:
        chroma_path: Path to chroma store. Defaults to .π/memory/chroma.
        retention_days: Days before archiving. Defaults to RETENTION.memory_store_days.

    Returns:
        True if archived, False otherwise.
    """
    import shutil
    from datetime import datetime, timedelta
    from pathlib import Path

    from π.core.constants import RETENTION

    path = Path(chroma_path) if chroma_path else Path(".π/memory/chroma")
    days = retention_days if retention_days is not None else RETENTION.memory_store_days

    if not path.exists():
        return False

    # Check modification time of store
    mtime = datetime.fromtimestamp(path.stat().st_mtime)
    if datetime.now() - mtime < timedelta(days=days):
        return False

    # Archive to timestamped directory
    archive_dir = path.parent / "archived" / mtime.strftime("%Y-%m-%d")
    archive_dir.mkdir(parents=True, exist_ok=True)
    shutil.move(str(path), str(archive_dir / "chroma"))

    logger.info("Archived ChromaDB store to %s", archive_dir)
    return True
