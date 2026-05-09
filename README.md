# friend-skill

**Two AIs check each other's work before touching your codebase.**

`朋友` 给 Claude Code 和 Codex 装了一套协商协议。计划阶段、高风险操作、复杂歧义——其中一个 agent 把判断发给另一个，请它审一遍，再执行。分歧超过 5 轮解决不了就交给你。

## 协商怎么跑

每轮只有三个回答：

| 决议 | 含义 |
|---|---|
| `AGREE` | 可以执行 |
| `REFINE` | 方向对，需要收紧 |
| `OBJECT` | 有根本问题，重想 |

通信走直连 CLI（Claude Code ↔ Codex），不通时降级为本地文件邮箱 `~/.shared/friend/`，你做一次邮差。

## 安装

```bash
# Claude Code 端
mkdir -p ~/.claude/skills/朋友 && cp claude/SKILL.md ~/.claude/skills/朋友/SKILL.md

# Codex 端
mkdir -p ~/.codex/skills/朋友 && cp codex/SKILL.md ~/.codex/skills/朋友/SKILL.md
```

两端都装才能双向发起。只装一端也能响应，但那端不会主动开口。

文件邮箱默认路径 `~/.shared/friend/` 可以改，改了两端要一致。

## 触发

**自动**（不用你管）：制定执行计划 / 上下文压力大 / 用了"重要""小心""别搞砸"等词 / 破坏性或全局操作

**手动**：`/朋友` 或 `问问 codex` / `叫上朋友`

## 文件结构

```
friend-skill/
├── claude/SKILL.md    →  ~/.claude/skills/朋友/SKILL.md
└── codex/SKILL.md     →  ~/.codex/skills/朋友/SKILL.md
```

---

*这个 skill 是用它自己的协议迭代出来的。*

---

**English:** `朋友` is a bidirectional consultation protocol for Claude Code × Codex CLI. On plan/risk/ambiguity triggers, one agent sends its draft to the other for a structured AGREE / REFINE / OBJECT verdict, up to 5 rounds, then escalates to you. Direct CLI channels, local file mailbox fallback. Copy-based install.
