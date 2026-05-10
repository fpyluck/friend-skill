#!/usr/bin/env bash
# friend-skill installer (bash/zsh; cross-platform: Linux, macOS, WSL)
# Installs the friend (朋友) and handoff (交班) skills.
# Idempotent: re-runnable; backs up existing files; updates AGENTS.md via managed block.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
TIMESTAMP="$(date +%Y%m%d_%H%M%S)"

for arg in "$@"; do
  case "$arg" in
    -h|--help)
      cat <<EOF
Usage: bash install.sh

Installs the friend (朋友) and handoff (交班) skills into Claude Code and Codex
local skill dirs, plus a shared mailbox bridge under ~/.shared/friend/.

Idempotent: existing files backed up to <path>.bak.<timestamp>.
EOF
      exit 0 ;;
  esac
done

CLAUDE_FRIEND="$HOME/.claude/skills/朋友"
CODEX_FRIEND="$HOME/.codex/skills/朋友"
CLAUDE_HANDOFF="$HOME/.claude/skills/handoff"
CODEX_HANDOFF="$HOME/.codex/skills/handoff"
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

echo "[1/7] Install Claude-side 朋友 skill"
install_file "$SCRIPT_DIR/claude/skills/朋友/SKILL.md"          "$CLAUDE_FRIEND/SKILL.md"
install_file "$SCRIPT_DIR/claude/skills/朋友/POWERSHELL_TIPS.md" "$CLAUDE_FRIEND/POWERSHELL_TIPS.md"
install_file "$SCRIPT_DIR/claude/skills/朋友/scripts/friend_mailbox_claude.py" \
             "$CLAUDE_FRIEND/scripts/friend_mailbox_claude.py"
install_file "$SCRIPT_DIR/claude/skills/朋友/scripts/surface_friend_pending.sh" \
             "$CLAUDE_FRIEND/scripts/surface_friend_pending.sh"
install_file "$SCRIPT_DIR/claude/skills/朋友/scripts/start_friend_session.sh" \
             "$CLAUDE_FRIEND/scripts/start_friend_session.sh"
chmod +x "$CLAUDE_FRIEND/scripts/friend_mailbox_claude.py" \
         "$CLAUDE_FRIEND/scripts/surface_friend_pending.sh" \
         "$CLAUDE_FRIEND/scripts/start_friend_session.sh"

echo "[2/7] Install Codex-side 朋友 skill"
install_file "$SCRIPT_DIR/codex/skills/朋友/SKILL.md" "$CODEX_FRIEND/SKILL.md"

echo "[3/7] Install Claude-side handoff skill"
install_file "$SCRIPT_DIR/claude/skills/handoff/SKILL.md" "$CLAUDE_HANDOFF/SKILL.md"

echo "[4/7] Install Codex-side handoff skill"
install_file "$SCRIPT_DIR/codex/skills/handoff/SKILL.md"                          "$CODEX_HANDOFF/SKILL.md"
install_file "$SCRIPT_DIR/codex/skills/handoff/agents/openai.yaml"                "$CODEX_HANDOFF/agents/openai.yaml"
install_file "$SCRIPT_DIR/codex/skills/handoff/assets/handoff-template.md"        "$CODEX_HANDOFF/assets/handoff-template.md"
install_file "$SCRIPT_DIR/codex/skills/handoff/scripts/new_handoff.py"            "$CODEX_HANDOFF/scripts/new_handoff.py"
chmod +x "$CODEX_HANDOFF/scripts/new_handoff.py"

echo "[5/7] Install mailbox bridge + queue"
mkdir -p "$MAILBOX"
install_file "$SCRIPT_DIR/shared/friend/friend_mailbox_bridge.py" "$MAILBOX/friend_mailbox_bridge.py"
install_file "$SCRIPT_DIR/shared/friend/friend_queue.py"          "$MAILBOX/friend_queue.py"
chmod +x "$MAILBOX/friend_mailbox_bridge.py" "$MAILBOX/friend_queue.py"

echo "[6/7] Update ~/.codex/AGENTS.md (managed block, idempotent)"
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

echo "[7/7] Verify"
for f in "$CLAUDE_FRIEND/SKILL.md" "$CODEX_FRIEND/SKILL.md" \
         "$CLAUDE_HANDOFF/SKILL.md" "$CODEX_HANDOFF/SKILL.md" \
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
  - Create a new handoff (Codex side):
      python3 ~/.codex/skills/handoff/scripts/new_handoff.py --project-key <slug> --title "<title>"
EOF
