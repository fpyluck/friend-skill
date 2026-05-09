# 朋友

两个 AI，互相审对方的方案。

你用 Claude Code 或 Codex 做复杂任务时，它们会犯一种病：越干越笃定，直到把自己绕进去。上下文压力大时漏细节，架构决策时走偏，高风险操作时没有第二道防线。

`朋友` 的解法很简单：让另一个 AI 拦住它，问一句"你确定吗？"

---

## 富哥专用技能

这不是省 token 的工具。它的美德恰恰相反。

双倍 token，双倍效率，双倍快乐。

---

## 它长这样

```
你：帮我迁移线上数据库
  ↓
Claude 起草方案 A
  └─[FRIEND_CONSULT round=1]─→ Codex
                                REFINE: 方案 A 有竞态窗口，建议加事务锁
  ↓
Claude 修订为方案 B
  └─[FRIEND_CONSULT round=2]─→ Codex
                                AGREE: 这个可以，执行吧
  ↓
执行
```

三种回答，不造新词：

| 决议 | 意思 |
|------|------|
| `AGREE` | 没问题，执行 |
| `REFINE` | 方向对，但要改 |
| `OBJECT` | 根本错了，重想 |

最多五轮。五轮没谈拢，交给你拍板。

---

## 两端激活，两种风格

Claude Code 发起的协商和 Codex 发起的协商，不是同一种体验。

Claude 主导时更像有人在追问意图、边界和风险；Codex 主导时更像有人盯着文件、命令、测试和可执行性。

就像同一个项目，换个 leader 来主导，决策风格、关注点、措辞都会不一样。两端都装，你能感受到两种视角在你的任务里博弈。只装一端，也能用，但少了那层张力。

---

## 何时触发

**自动**（不用管）

- 制定执行计划 / 架构决策
- 会话很长、快要压缩、上下文压力大
- 用了"重要"、"关键"、"别搞砸"
- 删除、迁移、生产部署等破坏性操作
- 跨仓库 / 修改全局配置

**手动**：`/朋友`，或说"问问 Claude"、"问问 Codex"、"叫上朋友"

**不触发**：单文件小修复、显然能执行的简单任务——别为了协商而协商。

---

## 安装

**Bash / macOS / Linux**

```bash
# Claude Code 端
mkdir -p ~/.claude/skills/朋友
curl -sL https://raw.githubusercontent.com/fpyluck/friend-skill/main/claude/SKILL.md \
  > ~/.claude/skills/朋友/SKILL.md

# Codex 端
mkdir -p ~/.codex/skills/朋友
curl -sL https://raw.githubusercontent.com/fpyluck/friend-skill/main/codex/SKILL.md \
  > ~/.codex/skills/朋友/SKILL.md
```

**Windows PowerShell**

```powershell
# Claude Code 端
New-Item -ItemType Directory -Force "$HOME\.claude\skills\朋友" | Out-Null
Invoke-WebRequest -Uri "https://raw.githubusercontent.com/fpyluck/friend-skill/main/claude/SKILL.md" `
  -OutFile "$HOME\.claude\skills\朋友\SKILL.md"

# Codex 端
New-Item -ItemType Directory -Force "$HOME\.codex\skills\朋友" | Out-Null
Invoke-WebRequest -Uri "https://raw.githubusercontent.com/fpyluck/friend-skill/main/codex/SKILL.md" `
  -OutFile "$HOME\.codex\skills\朋友\SKILL.md"
```

---

## 通信

Claude 找 Codex 走 `codex exec`；Codex 找 Claude 走 `claude -p --output-format json`。连不上时降级到本地文件邮箱 `~/.shared/friend/`（`codex_to_claude.md` ↔ `claude_to_codex.md`），你做一次转发。

---

*这个 skill 是用它自己的协议迭代出来的。*

