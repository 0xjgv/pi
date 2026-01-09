#!/usr/bin/env bash
# Install documentation sync git hook
# Usage: ./.claude/hack/install-doc-sync-hook.sh

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
HOOK_SOURCE="${SCRIPT_DIR}/doc-sync-hook.sh"
HOOK_TARGET=".git/hooks/post-commit"

# Ensure hook source exists
if [[ ! -f "$HOOK_SOURCE" ]]; then
    echo "Error: Hook source not found: $HOOK_SOURCE"
    exit 1
fi

# Create hooks directory if needed
mkdir -p .git/hooks

# Check for existing hook
if [[ -f "$HOOK_TARGET" ]]; then
    # Append to existing hook if not already present
    if ! grep -q "doc-sync" "$HOOK_TARGET"; then
        echo "" >> "$HOOK_TARGET"
        echo "# Documentation sync hook" >> "$HOOK_TARGET"
        tail -n +2 "$HOOK_SOURCE" >> "$HOOK_TARGET"
        echo "Documentation sync appended to existing post-commit hook"
    else
        echo "Documentation sync hook already installed"
    fi
else
    # Create new hook
    cp "$HOOK_SOURCE" "$HOOK_TARGET"
    chmod +x "$HOOK_TARGET"
    echo "Documentation sync hook installed"
fi
