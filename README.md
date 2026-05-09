# 朋友 — Claude × Codex 双向协商

> 一个 AI 做计划，另一个 AI 审它——重大决策不单人拍板。

## 为什么需要它

AI agent 在独立执行复杂任务时容易陷入局部最优：上下文压力大时会漏掉细节，复杂架构决策时会走错方向，高风险操作时没有第二道防线。

`朋友` 给 Claude Code 和 Codex 装了一套对等协商协议。计划阶段、高风险操作、复杂歧义——一方把草案发给另一方，收到结构化的 AGREE / REFINE / OBJECT 回复，最多 5 轮达成一致，否则交给你裁决。

富哥专用技能，双倍token，双倍效率，双倍快乐。

尽管Claude Code 和 Codex是朋友，但是从不同端激活，可能有不同的效果哦！就像我们一样，项目由不同的leader主导，风格会略有不同~

## 协商长什么样

```
[用户] 迁移线上数据库
  ↓
发起方起草方案 A ──[FRIEND_CONSULT round=1]──→ 朋友
                    朋友: REFINE: 方案 A 有竞态窗口
  ↓
发起方修订为方案 B ──[FRIEND_CONSULT round=2]──→ 朋友
                    朋友: AGREE: 安全，可以执行
  ↓
执行
```

## 触发时机

**自动触发（不用管）**
- 制定执行计划 / 架构决策
- 上下文压力大（会话很长、快要压缩）
- 用了"重要"、"关键"、"别搞砸"等高风险词
- 破坏性操作（删除、迁移、生产部署）
- 跨仓库 / 修改全局配置

**手动触发**：`/朋友` 或说"问问 codex"、"叫上朋友"

**不触发**：单文件小修复、明确执行的简单任务——别打断流程

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

建议两端都装。只装一端时，只能保证已安装的一端遵循协议；另一端需要用户手动转述并要求按协议回复。

## 协商协议

三种决议，不造新词：

| 决议 | 含义 |
|------|------|
| `AGREE` | 同意当前方案，可以执行 |
| `REFINE` | 方向对，需要具体修改 |
| `OBJECT` | 有根本问题，提出替代方案 |

通信走直连 CLI（`claude -p` / `codex exec`），失败时降级到 `~/.shared/friend/` 文件邮箱（`codex_to_claude.md` ↔ `claude_to_codex.md`），由你做一次转发。

## 仓库结构

```
friend-skill/
├── claude/SKILL.md    →  ~/.claude/skills/朋友/SKILL.md
└── codex/SKILL.md     →  ~/.codex/skills/朋友/SKILL.md
```

---

*这个 skill 是用它自己的协议迭代出来的。*

