"""Documentation sync workflow stage.

Evaluates codebase changes and updates CLAUDE.md when warranted.
"""

from π.doc_sync.core import (
    DEFAULT_FILES_THRESHOLD,
    DocSyncResult,
    DocSyncSignature,
    DocSyncState,
    stage_doc_sync,
)

__all__ = [
    "DEFAULT_FILES_THRESHOLD",
    "DocSyncResult",
    "DocSyncSignature",
    "DocSyncState",
    "stage_doc_sync",
]
