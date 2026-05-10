# 朋友 (friend)：Claude Code × Codex 双端协作 Skill

> 让 Claude Code 和 Codex 在重要任务上互相校准：一个提出方案，另一个审稿、挑错、补盲区。能达成一致就执行，达不成一致就交给用户裁决。

`朋友` 不是把两个 agent 绑成一个更吵的声音。它是一套本地协作协议，让 Claude Code 和 Codex 保留各自的判断、工具链和工作习惯，在真正值得停下来确认的时刻互相问一句：这个方案稳吗？

## What's new

### v2.2 — 2026-05-10

- **Slug 重命名**：`朋友/` 目录全部改为 `friend/`（`claude/skills/friend`、`codex/skills/friend`）；不再发布旧的 `朋友` 目录。
- **helper skill 加入发行版**：新增 `helper` skill（Claude + Codex 双端），负责协商后的分工执行（work card 格式，外部 CLI helper 参考资料）。
- **共享运行时扩展**：新增 `friend_gate.py`（权限把关与格式验证），新增 gate 测试套件（12 个测试）；安装器一并同步 `friend_gate.py`、`tests/`、`trust-profile.env.example`。
- **Debug 修复**：`start_friend_session.sh`、`new_handoff.py` 不再硬编码路径；`AGENTS.md.snippet` 路径修正为 `~/.codex/skills/friend/SKILL.md`；所有脚本 LF 标准化。

### v2.1 — 2026-05-10

- **handoff (交班) skill 加入发行版**：两侧都新增了 `handoff` skill。`朋友` 负责实时协商和消息传递；`handoff` 负责把当前工程状态打包成下一个 agent（或同一个 agent 重置上下文后）能直接接手的持久文档。两个 skill 互相感知，协商中产生的决策建议写进 `decisions_and_changes`，未解决分歧写进 `open_issues`。
  - Codex 侧附带 `new_handoff.py`（骨架生成器）和 `handoff-template.md`（规范模板）。
  - 触发词：`交班`、`handoff`、`接力`、`轮流继续同一工程`，或直接说 `/handoff`。
- **朋友 skill 改为英文**：SKILL.md 全面改写为英文，结构更紧凑；POWERSHELL_TIPS.md 同步更新为英文。协商协议本身（标记格式、决议词、触发判定逻辑）保持不变。

### v2.0

- Transport 分两层：`--transport manual`（默认，stdlib only，无 `claude -p`）和 `--transport claude_cli`（可选，带 failure cache 熔断）。
- Pending check 绑定 inbox SHA256，不再被无关 outbox 写入错误清零。
- Queue 接口（`friend_queue.py`）作为 manual 模式下的首选发起方式。

## 它解决什么

单个 agent 最容易出问题的地方，通常不是"不会写代码"，而是：

- 长任务后上下文开始漂移，却还在自信推进。
- 方案有多条合理路径，但模型只沿着第一条路走到底。
- 删除、迁移、发布、全局配置这类操作影响很大，却缺少第二视角。
- 跨仓库、跨 CLI、跨系统环境时，某一端对另一端的真实约束不了解。
- 说到了路径、命令、函数、行号，却没有说明依据来自哪里。
- 会话切换或上下文重置时，工程状态散落在记忆里，接手方不知从哪读起。

`朋友` 的处理方式很朴素：关键时刻，让另一个 agent 做一次独立评审。`handoff` 的处理方式同样朴素：切换前，把工程状态写成一份接手方 5 分钟内能读完的文档。

## 核心能力

- **双端安装**：同一套协议分别安装到 Claude Code 和 Codex；两侧设计上对称但不机械镜像。
- **自动触发**：执行性计划、复杂歧义、上下文压力、高风险信号、破坏性操作会触发协商。
- **手动召唤**：对任意一端说 `/朋友`、`问问 claude`、`问问 codex`、`和朋友商量`。
- **三态决议**：只允许 `AGREE`、`REFINE`、`OBJECT`，避免讨论失控。
- **最多 5 轮**：协商不能无限拉扯，分歧解决不了就升级给用户。
- **防递归**：收到朋友咨询的一方按裁决回推（同 thread 续接），但不新建反向咨询链路。
- **handoff 持久化**：`/handoff`（`交班`）把工程当前状态写成结构化 Markdown，供下一个 agent 或同一 agent 重启后直接接手；与 `朋友` 协议互通。
- **跨平台 manual 通道**：bridge 默认 `--transport manual`，**任何系统**（Linux / macOS / Windows / WSL）零外部依赖跑通。
- **可选 claude_cli 加速**：显式 `--transport claude_cli` 启用自动 dispatch，配合 failure cache 熔断。
- **来源约束**：提到具体路径、命令、函数、行号时，要说明读了哪个文件或跑了什么命令。
- **stdlib only**：`bridge` 和 helper 都只用 Python 标准库；不引入第三方包，不修改用户 shell / PATH / proxy / settings。

## 30 秒安装

### bash / zsh / WSL

```bash
git clone https://github.com/fpyluck/friend-skill.git
cd friend-skill
bash install.sh
```

### PowerShell

```powershell
git clone https://github.com/fpyluck/friend-skill.git
cd friend-skill
powershell -ExecutionPolicy Bypass -File install.ps1
```

安装脚本会做这些事：

1. 安装 Claude 端 `朋友` skill 到 `~/.claude/skills/朋友/`（含 `SKILL.md`、`POWERSHELL_TIPS.md`、`scripts/friend_mailbox_claude.py`）
2. 安装 Codex 端 `朋友` skill 到 `~/.codex/skills/朋友/SKILL.md`
3. 安装 Claude 端 `handoff` skill 到 `~/.claude/skills/handoff/SKILL.md`
4. 安装 Codex 端 `handoff` skill 到 `~/.codex/skills/handoff/`（含 `SKILL.md`、`agents/openai.yaml`、`assets/handoff-template.md`、`scripts/new_handoff.py`）
5. 创建 `~/.shared/friend/` 本地邮箱目录
6. 安装邮箱桥脚本到 `~/.shared/friend/friend_mailbox_bridge.py`
7. 通过 managed block 幂等更新 `~/.codex/AGENTS.md`（重复运行不会重复追加）

已存在的同名文件先备份为 `<path>.bak.<timestamp>`。

## Transport 分层（v2 关键设计）

朋友 skill 的双向通信不强依赖 `claude -p` 直连——后者在第三方网关 / 公司代理 / 受限网络下经常失败。

### `--transport manual`（默认；任何系统）

bridge 不调 `claude -p`，只做：
- 协议守卫：首行必须是 `[FRIEND_CONSULT round=N]` / `[NOTIFY]`（inbox）或 `AGREE:` / `REFINE:` / `OBJECT:` / `ACK:`（outbox）
- 完整归档（`--no-archive-prompts` 切元数据归档）
- 状态机：`pending_for_claude` / `pending_for_codex` 双向标志
- Sentinel `~/.shared/friend/.bridge.pending`（任一 pending 时存在的 JSON）

manual 端到端工作流：

**前提**：本机要有一个 `friend_mailbox_bridge.py --watch --transport manual` 进程在跑，它负责把 inbox/outbox 文件变化转写成 `pending_for_*` 状态和 sentinel。

启动 watcher（任一侧）：
```bash
python3 ~/.shared/friend/friend_mailbox_bridge.py --watch --mailbox ~/.shared/friend
```

会话内一次往返：
1. Codex 写 `~/.shared/friend/codex_to_claude.md` → manual watcher 检测 → 设 `pending_for_claude=true`
2. Codex 启动 `bridge --wait-reply --mailbox <path>` 阻塞等回复
3. ClaudeCode 用 `friend_mailbox_claude.py watch --print-inbox` 检测 pending → 推理 → `helper write --reply-file <reply>`
4. manual watcher 检测 outbox 新 hash → 返回回复给 Codex（清 `pending_for_codex`）

### `--transport claude_cli`（可选；要求 `claude -p` 可用）

启用自动 dispatch：bridge 直接调 `claude -p`。失败时按 classification（timeout / proxy / auth / malformed / unknown）写 `failure_cache`，TTL 内跳过重试，指数退避 cap 1h。

诊断当前机器的 `claude -p` 是否可用：

```bash
python3 ~/.shared/friend/friend_mailbox_bridge.py --probe --transport claude_cli
```

输出 `ok` 或 `failed:<classification>`。

## 协商协议

第一行必须是：

```text
[FRIEND_CONSULT round=N]
```

`N` 从 1 开始。回复只能用三种决议：

```text
AGREE:  同意，可以执行
REFINE: 方向对，但需要修改
OBJECT: 方案不对，给出替代方案
```

规则：

- 最多 5 轮，达不成一致升级给用户裁决。
- 收到 `[FRIEND_CONSULT]` 的一方可用 `--resume` 推回原会话（同协商下一轮），但不新起反向 `[FRIEND_CONSULT]`，避免套娃。
- 涉及具体路径、命令、行号时附来源（读了哪个文件、跑了什么命令）。

## 治理底线

任何长期规则变更（skill / hook / 全局配置 / memory）必须用 `[NOTIFY]` 通知对方，正文必含：来源、类别、改动文件路径、diff 摘要、影响面、期望动作、脱敏摘要。

## 文件结构

```text
friend-skill/
├── README.md
├── LICENSE
├── install.sh
├── install.ps1
├── claude/
│   └── skills/
│       ├── 朋友/                          → 安装到 ~/.claude/skills/朋友/
│       │   ├── SKILL.md
│       │   ├── POWERSHELL_TIPS.md
│       │   └── scripts/
│       │       ├── friend_mailbox_claude.py
│       │       ├── surface_friend_pending.sh
│       │       └── start_friend_session.sh
│       └── handoff/                       → 安装到 ~/.claude/skills/handoff/
│           └── SKILL.md
├── codex/
│   ├── skills/
│   │   ├── 朋友/                          → 安装到 ~/.codex/skills/朋友/
│   │   │   └── SKILL.md
│   │   └── handoff/                       → 安装到 ~/.codex/skills/handoff/
│   │       ├── SKILL.md
│   │       ├── agents/
│   │       │   └── openai.yaml
│   │       ├── assets/
│   │       │   └── handoff-template.md
│   │       └── scripts/
│   │           └── new_handoff.py
│   └── AGENTS.md.snippet
└── shared/
    └── friend/                            → 安装到 ~/.shared/friend/
        ├── friend_mailbox_bridge.py
        ├── friend_queue.py
        └── trust-profile.env.example
```

## 故障排查

### `claude -p` 在某些机器返回 HTTP 200 + empty/malformed

第三方网关常见问题，bridge 修不了。两条路：
1. 默认 manual transport 已经能跑通端到端协作，不依赖 `claude -p`
2. 如要诊断网关：`python3 friend_mailbox_bridge.py --probe --transport claude_cli`

### 启动 bridge 报"another watcher live"

同 mailbox 已有一个 watcher 在跑（heartbeat 还活）。`--watch` 第二次启动会 exit 0，避免重启循环。如需强制：先 `ps -ef | grep friend_mailbox_bridge` 确认无活进程，再删 `~/.shared/friend/.bridge_watch.lock`。

### Windows 的 `python3` 是 Microsoft Store 占位

git bash 在 Windows 上 `python3` 通常是 Store stub。改用 `python` 或 `py`。

### WSL 下 `~/.shared/friend` 解析到 WSL home

WSL 下的 `~` 是 `/home/<user>`，与 Windows-side mailbox 不通。启动 bridge / helper 时显式传 `--mailbox /mnt/c/Users/<user>/.shared/friend`。

helper `friend_mailbox_claude.py` 自动按以下顺序探测：`FRIEND_MAILBOX` env → 当前 `.claude` 目录的 sibling `.shared/friend` → `~/.shared/friend`。

## 设计原则

- **人类终审**：两个 agent 都只是协作方，最终裁决权在用户。
- **只在值得时打断**：协作要减少风险，而不是制造流程负担。
- **证据优先**：具体事实要能回到文件、命令或工具输出。
- **本地优先**：通信文件、桥脚本和协商记录都在本机；不上传任何外部服务。
- **跨平台默认**：manual transport 在任何 Python 3 环境跑通；自动化是增益，不是前提。
- **差异共存**：Claude Code 和 Codex 可以互相学习，但不需要长得一样。

## 贡献

欢迎 issue 和 PR。

## License

MIT, 见 [LICENSE](LICENSE).

## English Summary

**friend** is a bidirectional collaboration skill for Claude Code and Codex. Same protocol, two transports:

- **Manual transport (default)**: stdlib-only file mailbox under `~/.shared/friend/`. The bridge guards protocol markers, archives messages, tracks `pending_for_*` flags, and writes a sentinel — but does **not** invoke `claude -p`. Works on any system.
- **`claude_cli` transport (opt-in)**: invokes `claude -p` for auto-dispatch with classified failure cache (timeout / proxy / auth / malformed / unknown), exponential backoff capped at 1h.

**handoff** is the persistence layer alongside friend: `朋友` handles live consultation and transport; `handoff` writes the compact project state the continuing agent needs after a break, context reset, or role switch. Say `交班` or `/handoff` to trigger it.

Three verdicts (`AGREE`, `REFINE`, `OBJECT`), up to 5 rounds, then human escalation. Anti-recursion: replies may use thread/session resume, but a new `[FRIEND_CONSULT]` reverse chain is forbidden. Long-term rule changes must use `[NOTIFY]` with a strict required-fields template. Stdlib-only Python; no third-party packages, no global env / proxy / shell mutations.
