# friend-skill

**A two-agent consultation protocol for Claude Code and Codex.**

让 Claude Code 和 Codex 先互相过一遍脑子，最后仍由用户拍板。

## 这是什么

`朋友` 是一个双向协商 skill：当任务进入计划阶段、风险变高、上下文复杂，或用户手动喊 `/朋友` 时，一端 agent 会把当前判断发给另一端 agent，请它审一下计划、风险和遗漏。

优先走直连 CLI：

```bash
claude -p --output-format json   # Codex → Claude
codex exec --skip-git-repo-check # Claude → Codex
```

如果直连不可用，就降级为文件邮箱：双方通过共享 Markdown 文件交换意见，用户做一次邮差。

默认文件邮箱路径是：

```text
~/.shared/friend/
```

这个路径可以改，但 Claude Code 端和 Codex 端必须保持一致。

## 安装

这是复制式安装，不是包管理器。把对应的 `SKILL.md` 放到各自 agent 的 skills 目录即可。

**Claude Code 端：**

```bash
mkdir -p ~/.claude/skills/朋友 && cp claude/SKILL.md ~/.claude/skills/朋友/SKILL.md
```

**Codex 端：**

```bash
mkdir -p ~/.codex/skills/朋友 && cp codex/SKILL.md ~/.codex/skills/朋友/SKILL.md
```

两端都装才能双向协商。只装一端也能用，但另一端不会主动发起协商。

## 触发方式

**自动触发：**

- 制定执行计划、做架构决策时
- 任务复杂、歧义大、上下文压力高时
- 用户说了"重要""关键""小心"等高风险词时
- 涉及破坏性操作、全局配置、跨仓库改动时

**手动触发：**

```text
/朋友
```

也可以说：`问问 codex` / `和朋友商量` / `叫上朋友`

## 工作方式

一端把当前任务、计划和风险点发给另一端，对方只做三件事：

- `AGREE`：计划可执行
- `REFINE`：方向对，但需要收紧或补充
- `OBJECT`：存在关键问题，需要重想

最多 5 轮协商。仍有分歧时升级给用户裁决。

## 项目结构

```
friend-skill/
├── README.md
├── LICENSE
├── claude/
│   └── SKILL.md    # 复制到 ~/.claude/skills/朋友/SKILL.md
└── codex/
    └── SKILL.md    # 复制到 ~/.codex/skills/朋友/SKILL.md
```

## 适合谁

适合经常让 AI 改代码、做架构判断、处理高风险操作的程序员。

它不是让两个 agent 无限聊天，而是给关键决策加一个冷静的搭档。

---

## English Summary

**friend (朋友)** is a bidirectional consultation protocol installed on both **Claude Code** and **Codex CLI**. When tasks enter decision phases — executable plans, high context pressure, ambiguity, high-risk signals, or destructive operations — the two agents negotiate via a three-state verdict system (AGREE / REFINE / OBJECT), up to 5 rounds, escalating to the human user if they can't agree.

Forward channel: `codex exec`. Reverse channel: `claude -p` (direct), with local file mailbox as fallback. Copy-based install, no package manager required.
