#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
HELPER="${SCRIPT_DIR}/friend_mailbox_claude.py"
PROMPT="/mnt/c/Users/83233/.shared/friend/CLAUDE_FRIEND_SESSION_PROMPT.md"

if [[ -f "$PROMPT" ]]; then
  cat "$PROMPT"
  printf '\n--- current mailbox status ---\n'
fi

python3 "$HELPER" status
printf '\n--- pending inbox (if any) ---\n'
python3 "$HELPER" watch --print-inbox --timeout 1 --poll-interval 0.25 || true
