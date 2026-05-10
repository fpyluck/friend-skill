#!/usr/bin/env bash
# friend-skill installer (bash/zsh; cross-platform: Linux, macOS, WSL)
# Idempotent: re-runnable; backs up existing files; updates AGENTS.md via managed block.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
TIMESTAMP="$(date +%Y%m%d_%H%M%S)"

for arg in "$@"; do
  case "$arg" in
    -h|--help)
      cat <<EOF
Usage: bash install.sh

Installs friend, handoff, and helper skills into Claude Code and Codex local
skill dirs, plus the shared friend runtime under ~/.shared/friend/.

Idempotent: existing files backed up to <path>.bak.<timestamp>.
EOF
      exit 0 ;;
  esac
done

CLAUDE_SKILLS="$HOME/.claude/skills"
CODEX_SKILLS="$HOME/.codex/skills"
CLAUDE_FRIEND="$CLAUDE_SKILLS/friend"
CLAUDE_HANDOFF="$CLAUDE_SKILLS/handoff"
CLAUDE_HELPER="$CLAUDE_SKILLS/helper"
CODEX_FRIEND="$CODEX_SKILLS/friend"
CODEX_HANDOFF="$CODEX_SKILLS/handoff"
CODEX_HELPER="$CODEX_SKILLS/helper"
MAILBOX="$HOME/.shared/friend"
AGENTS="$HOME/.codex/AGENTS.md"

backup_if_exists() {
  local path="$1"
  if [ -f "$path" ]; then
    cp -p "$path" "${path}.bak.${TIMESTAMP}"
    echo "  backup: $path -> ${path}.bak.${TIMESTAMP}"
  fi
}

install_file() {
  local src="$1" dst="$2"
  if [ ! -f "$src" ]; then
    echo "  ✗ source missing: $src" >&2
    return 1
  fi
  mkdir -p "$(dirname "$dst")"
  backup_if_exists "$dst"
  cp -p "$src" "$dst"
  echo "  ✓ $dst"
}

install_tree() {
  local src_dir="$1" dst_dir="$2"
  if [ ! -d "$src_dir" ]; then
    echo "  ✗ source dir missing: $src_dir" >&2
    return 1
  fi
  while IFS= read -r -d '' src; do
    local rel="${src#$src_dir/}"
    install_file "$src" "$dst_dir/$rel"
  done < <(find "$src_dir" -type f ! -path '*/__pycache__/*' ! -name '*.pyc' -print0 | sort -z)
}

echo "[1/5] Install Claude-side skills"
install_tree "$SCRIPT_DIR/claude/skills/friend" "$CLAUDE_FRIEND"
install_tree "$SCRIPT_DIR/claude/skills/handoff" "$CLAUDE_HANDOFF"
install_tree "$SCRIPT_DIR/claude/skills/helper" "$CLAUDE_HELPER"
chmod +x "$CLAUDE_FRIEND/scripts/friend_mailbox_claude.py" \
         "$CLAUDE_FRIEND/scripts/surface_friend_pending.sh" \
         "$CLAUDE_FRIEND/scripts/start_friend_session.sh"

echo "[2/5] Install Codex-side skills"
install_tree "$SCRIPT_DIR/codex/skills/friend" "$CODEX_FRIEND"
install_tree "$SCRIPT_DIR/codex/skills/handoff" "$CODEX_HANDOFF"
install_tree "$SCRIPT_DIR/codex/skills/helper" "$CODEX_HELPER"
chmod +x "$CODEX_HANDOFF/scripts/new_handoff.py"

echo "[3/5] Install shared friend runtime"
mkdir -p "$MAILBOX"
install_tree "$SCRIPT_DIR/shared/friend" "$MAILBOX"
chmod +x "$MAILBOX/friend_gate.py" "$MAILBOX/friend_mailbox_bridge.py" "$MAILBOX/friend_queue.py"

echo "[4/5] Update ~/.codex/AGENTS.md (managed block, idempotent)"
mkdir -p "$(dirname "$AGENTS")"
SNIPPET_FILE="$SCRIPT_DIR/codex/AGENTS.md.snippet"
if [ ! -f "$SNIPPET_FILE" ]; then
  echo "  ✗ snippet missing: $SNIPPET_FILE" >&2
  exit 1
fi
SNIPPET_CONTENT="$(cat "$SNIPPET_FILE")"
BEGIN_MARK="<!-- BEGIN friend-skill"
END_MARK="<!-- END friend-skill -->"

if [ ! -f "$AGENTS" ]; then
  printf '%s\n' "$SNIPPET_CONTENT" > "$AGENTS"
  echo "  ✓ created $AGENTS with managed block"
elif grep -qF "$BEGIN_MARK" "$AGENTS" && grep -qF "$END_MARK" "$AGENTS"; then
  backup_if_exists "$AGENTS"
  awk -v snippet="$SNIPPET_CONTENT" '
    BEGIN { inside = 0 }
    /<!-- BEGIN friend-skill/ { inside = 1; print snippet; next }
    /<!-- END friend-skill -->/ { inside = 0; next }
    !inside { print }
  ' "$AGENTS" > "${AGENTS}.tmp.$$" && mv "${AGENTS}.tmp.$$" "$AGENTS"
  echo "  ✓ replaced managed block in $AGENTS"
else
  backup_if_exists "$AGENTS"
  printf '\n%s\n' "$SNIPPET_CONTENT" >> "$AGENTS"
  echo "  ✓ appended managed block to $AGENTS"
  echo "  note: existing file did not have managed-block markers; legacy entries (if any) were left in place. Remove them manually if duplicated."
fi

echo "[5/5] Verify"
for f in "$CLAUDE_FRIEND/SKILL.md" "$CLAUDE_HANDOFF/SKILL.md" "$CLAUDE_HELPER/SKILL.md" \
         "$CODEX_FRIEND/SKILL.md" "$CODEX_HANDOFF/SKILL.md" "$CODEX_HELPER/SKILL.md" \
         "$MAILBOX/friend_gate.py" "$MAILBOX/friend_mailbox_bridge.py" "$MAILBOX/friend_queue.py" "$AGENTS"; do
  [ -f "$f" ] && echo "  ✓ $f" || echo "  ✗ missing $f"
done

cat <<EOF

Done.

Next steps:
  - Bridge default mode is manual (no claude -p call). Start it (any system):
      python3 ~/.shared/friend/friend_mailbox_bridge.py --watch --mailbox ~/.shared/friend
    (Windows git bash: replace python3 with python or py)
  - To enable auto-dispatch (requires working claude -p):
      python3 ~/.shared/friend/friend_mailbox_bridge.py --watch --transport claude_cli --mailbox ~/.shared/friend
  - Diagnose claude -p:
      python3 ~/.shared/friend/friend_mailbox_bridge.py --probe --transport claude_cli
EOF
