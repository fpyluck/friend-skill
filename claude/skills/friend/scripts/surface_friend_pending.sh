#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
HELPER="${SCRIPT_DIR}/friend_mailbox_claude.py"

surface_path="$(python3 "$HELPER" surface --timeout "${1:-0}" --poll-interval 0.5)"
printf '%s\n' "$surface_path"
if [[ "$surface_path" == *.md && -f "$surface_path" ]]; then
  printf '\n--- pending request surfaced for ClaudeCode ---\n'
  sed -n '1,220p' "$surface_path"
fi
