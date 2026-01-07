#!/usr/bin/env bash
# Git post-commit hook for documentation sync
# Accumulates file changes and triggers sync agent when threshold reached
#
# NOTE: We run accumulate-only first, then the threshold check. This is
# intentional - if this commit pushes us past the threshold, we want to
# trigger the sync immediately rather than waiting for the next commit.

set -euo pipefail

# Accumulate file count from this commit
python -m π.doc_sync --accumulate-only 2>/dev/null || true

# Check if threshold reached and trigger sync
python -m π.doc_sync 2>/dev/null || true
