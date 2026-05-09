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

Installs the friend (朋友) skill into Claude Code and Codex local skill dirs,
plus a shared mailbox bridge under ~/.shared/friend/.

Idempotent: existing files backed up to <path>.bak.<timestamp>.
EOF
      exit 0 ;;
  esac
done

CLAUDE_FRIEND="$HOME/.claude/skills/朋友"
CODEX_FRIEND="$HOME/.codex/skills/朋友"
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

echo "[1/5] Install Claude-side 朋友 skill"
install_file "$SCRIPT_DIR/claude/skills/朋友/SKILL.md"          "$CLAUDE_FRIEND/SKILL.md"
install_file "$SCRIPT_DIR/claude/skills/朋友/POWERSHELL_TIPS.md" "$CLAUDE_FRIEND/POWERSHELL_TIPS.md"
install_file "$SCRIPT_DIR/claude/skills/朋友/scripts/friend_mailbox_claude.py" \
             "$CLAUDE_FRIEND/scripts/friend_mailbox_claude.py"
install_file "$SCRIPT_DIR/claude/skills/朋友/scripts/surface_friend_pending.sh" \
             "$CLAUDE_FRIEND/scripts/surface_friend_pending.sh"
chmod +x "$CLAUDE_FRIEND/scripts/friend_mailbox_claude.py" \
         "$CLAUDE_FRIEND/scripts/surface_friend_pending.sh"

echo "[2/5] Install Codex-side 朋友 skill"
install_file "$SCRIPT_DIR/codex/skills/朋友/SKILL.md" "$CODEX_FRIEND/SKILL.md"

echo "[3/5] Install mailbox bridge + queue"
mkdir -p "$MAILBOX"
install_file "$SCRIPT_DIR/scripts/friend_mailbox_bridge.py" "$MAILBOX/friend_mailbox_bridge.py"
install_file "$SCRIPT_DIR/scripts/friend_queue.py"          "$MAILBOX/friend_queue.py"
chmod +x "$MAILBOX/friend_mailbox_bridge.py" "$MAILBOX/friend_queue.py"

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
for f in "$CLAUDE_FRIEND/SKILL.md" "$CODEX_FRIEND/SKILL.md" \
         "$MAILBOX/friend_mailbox_bridge.py" "$AGENTS"; do
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
