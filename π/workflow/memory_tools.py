"""DSPy-compatible memory tools for storing and retrieving learnings.

These tools enable ReAct agents to persist lessons learned, blockers,
and insights across workflow iterations.
"""

from __future__ import annotations

import logging
import subprocess
from functools import lru_cache
from typing import TYPE_CHECKING

from π.workflow.memory import get_memory_client

if TYPE_CHECKING:
    from mem0 import Memory, MemoryClient

logger = logging.getLogger(__name__)


@lru_cache(maxsize=1)
def _get_repo_id() -> str:
    """Get repo name as user_id for memory isolation per codebase."""
    try:
        result = subprocess.run(
            ["git", "rev-parse", "--show-toplevel"],
            capture_output=True,
            text=True,
            timeout=5,
            check=True,
        )
        repo_path = result.stdout.strip()
        return repo_path.split("/")[-1]
    except Exception:
        return "default_repo"


class MemoryTools:
    """Tools for storing and retrieving learnings across workflow iterations.

    Purpose: Remember lessons learned, blockers encountered, and insights gained.
    NOT for: Storing research docs or plan files (those go in thoughts/shared/).

    Memory types:
    - lesson_learned: What worked or didn't work during implementation
    - blocker: Obstacles encountered and how they were resolved
    - insight: Strategic observations about the codebase or approach
    - decision: Key architectural or design decisions with rationale
    - caveat: Things to watch out for or keep in mind
    """

    def __init__(self, memory: Memory | MemoryClient) -> None:
        self.memory = memory
        self.user_id = _get_repo_id()

    def store_memory(self, content: str, memory_type: str = "insight") -> str:
        """Store a learning or insight for future reference.

        Use this to persist lessons learned, blockers, or important decisions
        that should inform future work in this codebase.

        Args:
            content: What to remember. Be specific and include context.
            memory_type: One of: lesson_learned, blocker, insight, decision, caveat.

        Returns:
            Confirmation message.

        Example:
            store_memory(
                "The auth module requires httpOnly cookies - localStorage won't work",
                "caveat"
            )
        """
        try:
            formatted = f"[{memory_type}] {content}"
            self.memory.add(formatted, user_id=self.user_id)
            logger.debug("Stored memory: %s", content[:100])
            return f"Stored: {content[:100]}..."
        except Exception as e:
            logger.error("Failed to store memory: %s", e)
            return f"Error storing memory: {e}"

    def search_memories(self, query: str, limit: int = 5) -> str:
        """Search memories for relevant learnings before making decisions.

        Use this before starting work to recall past lessons and blockers.

        Args:
            query: What you're looking for (e.g., "authentication issues").
            limit: Maximum results to return.

        Returns:
            Formatted list of relevant memories.

        Example:
            search_memories("database migration problems")
        """
        try:
            results = self.memory.search(query, user_id=self.user_id, limit=limit)

            if not results or not results.get("results"):
                return "No relevant memories found."

            formatted = ["Relevant memories:"]
            for i, item in enumerate(results["results"], 1):
                content = item.get("memory", "")
                formatted.append(f"{i}. {content}")

            return "\n".join(formatted)
        except Exception as e:
            logger.error("Failed to search memories: %s", e)
            return f"Error searching memories: {e}"

    def get_all_memories(self, limit: int = 10) -> str:
        """Get all memories for this codebase.

        Args:
            limit: Maximum memories to return.

        Returns:
            Formatted list of all memories.
        """
        try:
            results = self.memory.get_all(user_id=self.user_id)

            if not results or not results.get("results"):
                return "No memories stored yet."

            memories = results["results"][-limit:]
            formatted = [f"Memories ({len(memories)}):"]
            for i, item in enumerate(memories, 1):
                content = item.get("memory", "")
                formatted.append(f"{i}. {content}")

            return "\n".join(formatted)
        except Exception as e:
            logger.error("Failed to get memories: %s", e)
            return f"Error retrieving memories: {e}"


# Module-level instance for DSPy tool registration
_memory_tools: MemoryTools | None = None


def get_memory_tools() -> MemoryTools:
    """Get or create the MemoryTools instance."""
    global _memory_tools  # noqa: PLW0603
    if _memory_tools is None:
        _memory_tools = MemoryTools(get_memory_client())
    return _memory_tools


# DSPy-compatible tool functions (delegate to class methods)
def store_memory(content: str, memory_type: str = "insight") -> str:
    """Store a learning or insight for future reference."""
    return get_memory_tools().store_memory(content, memory_type)


def search_memories(query: str, limit: int = 5) -> str:
    """Search memories for relevant learnings."""
    return get_memory_tools().search_memories(query, limit)


def get_all_memories(limit: int = 10) -> str:
    """Get all memories for this codebase."""
    return get_memory_tools().get_all_memories(limit)
