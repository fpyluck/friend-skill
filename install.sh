#!/usr/bin/env bash
# 朋友 + 减法 skill installer (bash/zsh)
# Installs to ~/.claude/skills/{朋友,减法}/, ~/.codex/skills/{朋友,减法}/, ~/.shared/friend/

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
TIMESTAMP="$(date +%Y%m%d_%H%M%S)"

CLAUDE_FRIEND_DST="$HOME/.claude/skills/朋友/SKILL.md"
CODEX_FRIEND_DST="$HOME/.codex/skills/朋友/SKILL.md"
CLAUDE_SUBTRACT_DST="$HOME/.claude/skills/减法/SKILL.md"
CODEX_SUBTRACT_DST="$HOME/.codex/skills/减法/SKILL.md"
AGENTS_FILE="$HOME/.codex/AGENTS.md"
MAILBOX_DIR="$HOME/.shared/friend"

CLAUDE_FRIEND_SRC="$SCRIPT_DIR/claude/skills/朋友/SKILL.md"
CODEX_FRIEND_SRC="$SCRIPT_DIR/codex/skills/朋友/SKILL.md"
CLAUDE_SUBTRACT_SRC="$SCRIPT_DIR/claude/skills/减法/SKILL.md"
CODEX_SUBTRACT_SRC="$SCRIPT_DIR/codex/skills/减法/SKILL.md"
SNIPPET="$SCRIPT_DIR/codex/AGENTS.md.snippet"

backup_if_exists() {
  local path="$1"
  if [[ -f "$path" ]]; then
    local bak="${path}.bak.${TIMESTAMP}"
    cp -p "$path" "$bak"
    echo "  备份已存在文件 → $bak"
  fi
}

install_skill() {
  local src="$1" dst="$2" label="$3"
  echo "$label"
  if [[ ! -f "$src" ]]; then
    echo "  ✗ 源文件缺失：$src" >&2
    return 1
  fi
  mkdir -p "$(dirname "$dst")"
  backup_if_exists "$dst"
  cp -p "$src" "$dst"
  echo "  ✓ 已安装 → $dst"
}

install_skill "$CLAUDE_FRIEND_SRC"   "$CLAUDE_FRIEND_DST"   "[1/6] 安装 Claude 端朋友 skill"
install_skill "$CODEX_FRIEND_SRC"    "$CODEX_FRIEND_DST"    "[2/6] 安装 Codex 端朋友 skill"
install_skill "$CLAUDE_SUBTRACT_SRC" "$CLAUDE_SUBTRACT_DST" "[3/6] 安装 Claude 端减法 skill"
install_skill "$CODEX_SUBTRACT_SRC"  "$CODEX_SUBTRACT_DST"  "[4/6] 安装 Codex 端减法 skill"

echo "[5/6] 追加全局指针到 ~/.codex/AGENTS.md"
mkdir -p "$(dirname "$AGENTS_FILE")"
if [[ -f "$AGENTS_FILE" ]] && grep -q "朋友 skill" "$AGENTS_FILE" 2>/dev/null; then
  echo "  ✓ AGENTS.md 已包含朋友指针，跳过"
else
  if [[ -f "$SNIPPET" ]]; then
    [[ -f "$AGENTS_FILE" ]] && echo "" >> "$AGENTS_FILE"
    cat "$SNIPPET" >> "$AGENTS_FILE"
    echo "  ✓ 已追加"
  else
    echo "  ✗ snippet 文件缺失：$SNIPPET" >&2
  fi
fi

echo "[6/6] 创建邮箱目录 ~/.shared/friend/"
mkdir -p "$MAILBOX_DIR"
echo "  ✓ $MAILBOX_DIR"

echo ""
echo "安装完成。验证："
echo "  - 在 Claude Code 输入 /朋友 应见到此 skill"
echo "  - Claude/Codex 均已安装朋友和减法 skill"
echo "  - 在 Codex 启动时 ~/.codex/AGENTS.md 会被读取"
echo "  - 邮箱目录就绪：$MAILBOX_DIR"
