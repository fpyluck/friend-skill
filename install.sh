#!/usr/bin/env bash
# friend-skill installer (bash/zsh; cross-platform: Linux, macOS, WSL)
# Installs: friend, xiongdimen, helper, handoff for Claude Code and Codex;
#           xiongdimen for Gemini; shared friend runtime.
# Idempotent: re-runnable; backs up existing files; updates AGENTS.md via managed block.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
TIMESTAMP="$(date +%Y%m%d_%H%M%S)"

for arg in "$@"; do
  case "$arg" in
    -h|--help)
      cat <<EOF
Usage: bash install.sh

Installs friend, xiongdimen, helper, and handoff skills into Claude Code, Codex,
and Gemini local skill dirs, plus the shared friend runtime under the resolved
install home. On WSL, the installer prefers the Windows profile unless
FRIEND_INSTALL_HOME is set.

Idempotent: existing files backed up to <path>.bak.<timestamp>.
EOF
      exit 0 ;;
  esac
done

# Determine install home: FRIEND_INSTALL_HOME > WSL Windows profile > $HOME.
INSTALL_HOME="${FRIEND_INSTALL_HOME:-}"
IS_WSL=false
if [ -z "$INSTALL_HOME" ] && [ -f /proc/version ] && grep -qiE 'microsoft|wsl' /proc/version 2>/dev/null; then
  IS_WSL=true
  if command -v cmd.exe >/dev/null 2>&1 && command -v wslpath >/dev/null 2>&1; then
    WIN_PROFILE="$(cmd.exe /c 'echo %USERPROFILE%' 2>/dev/null | tr -d '\r\n')"
    if [ -n "$WIN_PROFILE" ] && [ "$WIN_PROFILE" != "%USERPROFILE%" ]; then
      WSL_HOME="$(wslpath -u "$WIN_PROFILE" 2>/dev/null || true)"
      if [ -n "$WSL_HOME" ]; then
        INSTALL_HOME="$WSL_HOME"
        echo "  WSL: aligning to Windows profile $INSTALL_HOME (override with FRIEND_INSTALL_HOME)"
      fi
    fi
  fi
fi
INSTALL_HOME="${INSTALL_HOME:-$HOME}"

CLAUDE_SKILLS="$INSTALL_HOME/.claude/skills"
CODEX_SKILLS="$INSTALL_HOME/.codex/skills"
GEMINI_SKILLS="$INSTALL_HOME/.gemini/skills"
MAILBOX="$INSTALL_HOME/.shared/friend"
AGENTS="$INSTALL_HOME/.codex/AGENTS.md"

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

echo "[1/6] Install Claude-side skills"
install_tree "$SCRIPT_DIR/claude/skills/friend"     "$CLAUDE_SKILLS/friend"
install_tree "$SCRIPT_DIR/claude/skills/xiongdimen" "$CLAUDE_SKILLS/xiongdimen"
install_tree "$SCRIPT_DIR/claude/skills/helper"     "$CLAUDE_SKILLS/helper"
install_tree "$SCRIPT_DIR/claude/skills/handoff"    "$CLAUDE_SKILLS/handoff"
chmod +x "$CLAUDE_SKILLS/friend/scripts/friend_mailbox_claude.py" \
         "$CLAUDE_SKILLS/friend/scripts/surface_friend_pending.sh" \
         "$CLAUDE_SKILLS/friend/scripts/start_friend_session.sh" \
         "$CLAUDE_SKILLS/xiongdimen/scripts/gemini_leaf.py"

echo "[2/6] Install Codex-side skills"
install_tree "$SCRIPT_DIR/codex/skills/friend"     "$CODEX_SKILLS/friend"
install_tree "$SCRIPT_DIR/codex/skills/xiongdimen" "$CODEX_SKILLS/xiongdimen"
install_tree "$SCRIPT_DIR/codex/skills/helper"     "$CODEX_SKILLS/helper"
install_tree "$SCRIPT_DIR/codex/skills/handoff"    "$CODEX_SKILLS/handoff"
chmod +x "$CODEX_SKILLS/handoff/scripts/new_handoff.py" \
         "$CODEX_SKILLS/xiongdimen/scripts/gemini_leaf.py"

echo "[3/6] Install Gemini-side skills"
install_tree "$SCRIPT_DIR/gemini/skills/xiongdimen" "$GEMINI_SKILLS/xiongdimen"

echo "[4/6] Install shared friend runtime"
mkdir -p "$MAILBOX"
install_tree "$SCRIPT_DIR/shared/friend" "$MAILBOX"
chmod +x "$MAILBOX/friend_discovery.py" \
         "$MAILBOX/friend_gate.py" \
         "$MAILBOX/friend_mailbox_bridge.py" \
         "$MAILBOX/friend_queue.py"

if [ "$IS_WSL" = "true" ] && [ "$INSTALL_HOME" != "$HOME" ]; then
  WSL_LINK="$HOME/.shared/friend"
  if [ -L "$WSL_LINK" ]; then
    echo "  symlink already exists: $WSL_LINK -> $(readlink "$WSL_LINK")"
  elif [ -d "$WSL_LINK" ] && [ -n "$(ls -A "$WSL_LINK" 2>/dev/null)" ]; then
    echo "  ! non-empty WSL mailbox at $WSL_LINK - skipping symlink to avoid data loss."
    echo "    Syncing runtime launchers there so discovery can choose the active mailbox."
    install_tree "$SCRIPT_DIR/shared/friend" "$WSL_LINK"
    chmod +x "$WSL_LINK/friend_discovery.py" "$WSL_LINK/friend_gate.py" \
             "$WSL_LINK/friend_mailbox_bridge.py" "$WSL_LINK/friend_queue.py"
  else
    [ -d "$WSL_LINK" ] && rmdir "$WSL_LINK"
    mkdir -p "$(dirname "$WSL_LINK")"
    ln -s "$MAILBOX" "$WSL_LINK"
    echo "  ✓ symlink $WSL_LINK -> $MAILBOX"
  fi
fi

echo "[5/6] Update $INSTALL_HOME/.codex/AGENTS.md (managed block, idempotent)"
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
elif grep -qF "## 朋友 skill — 与 Claude Code 协商" "$AGENTS"; then
  backup_if_exists "$AGENTS"
  awk -v snippet="$SNIPPET_CONTENT" '
    BEGIN { inside = 0; replaced = 0 }
    $0 == "## 朋友 skill — 与 Claude Code 协商" && !replaced {
      print snippet
      inside = 1
      replaced = 1
      next
    }
    inside && /^## / {
      inside = 0
      print
      next
    }
    !inside { print }
  ' "$AGENTS" > "${AGENTS}.tmp.$$" && mv "${AGENTS}.tmp.$$" "$AGENTS"
  echo "  ✓ replaced legacy friend section in $AGENTS"
else
  backup_if_exists "$AGENTS"
  printf '\n%s\n' "$SNIPPET_CONTENT" >> "$AGENTS"
  echo "  ✓ appended managed block to $AGENTS"
  echo "  note: existing file did not have managed-block markers; legacy entries (if any) were left in place. Remove them manually if duplicated."
fi

echo "[6/6] Verify"
for f in \
  "$CLAUDE_SKILLS/friend/SKILL.md" \
  "$CLAUDE_SKILLS/xiongdimen/SKILL.md" \
  "$CLAUDE_SKILLS/helper/SKILL.md" \
  "$CLAUDE_SKILLS/handoff/SKILL.md" \
  "$CODEX_SKILLS/friend/SKILL.md" \
  "$CODEX_SKILLS/xiongdimen/SKILL.md" \
  "$CODEX_SKILLS/helper/SKILL.md" \
  "$CODEX_SKILLS/handoff/SKILL.md" \
  "$GEMINI_SKILLS/xiongdimen/SKILL.md" \
  "$MAILBOX/friend_discovery.py" \
  "$MAILBOX/friend_gate.py" \
  "$MAILBOX/friend_mailbox_bridge.py" \
  "$MAILBOX/friend_queue.py" \
  "$AGENTS"; do
  [ -f "$f" ] && echo "  ✓ $f" || echo "  ✗ missing $f"
done

cat <<EOF

Done. Four skills installed: friend / xiongdimen / helper / handoff

Next steps:
  - Bridge default mode is manual (no claude -p call). Start it (any system):
      python3 "$MAILBOX/friend_mailbox_bridge.py" --watch
    (Windows git bash: replace python3 with python or py)
  - To enable auto-dispatch (requires working claude -p):
      python3 "$MAILBOX/friend_mailbox_bridge.py" --watch --transport claude_cli
  - Gemini runner requires Gemini CLI in PATH:
      npm install -g @google/gemini-cli
  - Diagnose claude -p:
      python3 "$MAILBOX/friend_mailbox_bridge.py" --probe --transport claude_cli
EOF
