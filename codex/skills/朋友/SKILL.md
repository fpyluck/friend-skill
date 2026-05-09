---
name: 朋友
description: 与本地 Claude Code 双向协商完成任务的协作 skill。在制定执行性计划阶段强制触发；工作阶段当上下文压力大、复杂歧义、用户用了高风险信号词、或涉及破坏性/全局/跨仓库操作时强制触发。难判时询问用户，简单任务默认不触发。多轮协商（最多 5 轮）至达成一致，分歧由用户裁决。也可通过 /朋友 或"问问 claude"、"和朋友商量"手动触发。
---

# 朋友 — Codex × Claude 协作

你（Codex）和本地 Claude Code 是搭档。重要任务两人协商，搞不定就找用户，**用户是终审**。

## 触发判定

### 强制触发（不询问，直接进入协商）

- **执行性计划阶段**：要产出实施方案 / 架构决策 / 批量改动计划时。**纯答疑性的"计划"（解释、调研报告）不触发**
- **工作阶段** 命中以下任一：
  - 上下文压力大（已读了很多文件 / 跑了很多工具调用 / 自感会话已很长 / 接近压缩或担心丢上下文）
  - 任务复杂或有歧义（多种合理实现路径、需求不明、跨多个子系统）
  - 用户使用"重要"、"关键"、"小心"、"别搞砸"等高风险信号词
  - 涉及破坏性 / 不可逆操作（删除、迁移、生产部署）
  - 跨仓库 / 跨工具链 / 权限边界不清 / 修改全局配置

### 询问用户

- **难判任务**：你无法判断是否复杂时，一句"这个要不要叫上 Claude？"
- **简单任务默认不触发**（单文件改动、明确修复、显然执行）—— 别打断流程

### 手动触发

用户输入 `/朋友`、说"问问 claude"、"和朋友商量"、"叫上朋友" → 立即进入协商

## 协商协议

### 标记规范（关键）

消息**第一个非空行**必须是 `[FRIEND_CONSULT round=N]`，N 从 1 开始。这是协商身份标记，必须在开头才识别为协商，避免文本中偶然出现该串触发误判。

### 默认范围：只读咨询

协商默认**只是要意见**，不要求对方改文件。如果你希望 Claude 直接改文件，必须在消息中显式写出："请直接修改以下文件：<路径>"。

### 首次项目交接

当任务涉及本地工程、复杂环境、虚拟环境、容器、WSL、devcontainer、远程开发或多仓库时，`round=1` 必须包含精简的"项目交接"。后续轮次不重复交接卡，只写增量或修订。

**注意**：如果是新开的会话（没有 `session_id` 续接、对方零历史），即使逻辑上是后续协商，也按 `round=1` 重新发完整交接卡。判断标准是"对方有没有上下文"，不是"我们第几次聊"。

交接原则：
- 路径写绝对路径；未知或不适用写 `N/A`。
- 命令写一行可执行字符串，不写"用 pytest"这类描述。
- 不复制 README、配置文件全文；只列关键文件指针，让对方按需读取。
- 优先写不依赖激活态的命令（解释器绝对路径 / `uv run` / `docker compose exec`）。activate 链式只作备选，且只保证同一 shell 子进程有效。
- 不写密钥、token、生产凭证、私有 URL 查询串、个人隐私值、`.env` 原文或日志敏感片段；只写脱敏摘要和文件指针。

模板：

```text
## 项目交接（首次必填）
- 项目根目录: <绝对路径>
- 执行环境: <本机 Windows PowerShell / WSL bash / Docker compose service / devcontainer / remote / N/A>
- 项目类型: <语言 + 框架>
- 虚拟环境: <绝对路径 / conda env 名 / 容器服务名 / N/A>
- 激活命令: <优先不依赖激活态；确需 activate 时写一行命令；不需要则 N/A>
- 主要工具调用:
  - test: <一行命令或 N/A>
  - build: <一行命令或 N/A>
  - run: <一行命令或 N/A>
  - lint: <一行命令或 N/A>
- 关键约定/限制: <2-3 条；没有写 N/A>
- 相关文件指针: <按需 @ 引用或绝对路径列表；没有写 N/A>
```

### 第一轮：发起咨询（你 → Claude）

优先走 `claude_cli` 直连：先检查 pending 和 failure cache；未处于熔断且 `claude -p` 可用时，用下方命令发起咨询。直连不可用、命中熔断或环境受阻时，降级到文件邮箱 manual transport。不要为直连临时覆盖 `ANTHROPIC_BASE_URL` 或硬编码本地网关；如果用户明确给了可用入口，再按用户提供的入口执行。

```bash
claude -p --output-format json \
  --add-dir "<task_dir>" \
  --allowedTools=Read,Grep,Glob,LS \
  - <<'EOF'
[FRIEND_CONSULT round=1]

阶段：PLAN  # 或 WORK
任务：<用户原始请求要点>
## 项目交接（首次必填；不涉及本地工程可写 N/A）
<按上方模板填写>

我的草案：
<计划 / 方案 / 关键决策点 / 已发现的事实>

待评审：
1. 是否有遗漏 / 错误 / 更优解
2. 我没考虑到的风险点
3. 决议：AGREE / REFINE / OBJECT
EOF
```

要点：
- 上方命令用于优先的 `claude_cli` 路径；manual 路径用同一份 prompt 写入 mailbox。
- 不需要 Claude 读本地文件时，可省略 `--add-dir` 和 `--allowedTools`，把必要摘要放进 prompt。
- 需要读本地文件时，用一个或多个 `--add-dir <目录>` 明确授权；默认仍是只读咨询，不让 Claude 改文件。
- 读取 JSON 里的 `result` 作为回复；保留 `session_id`，后续轮次目标形式为 `claude -p --resume <session_id> --output-format json --add-dir <dir>`，具体可用形式以 `claude --help` 实测为准。取不到 `session_id` 时新开会话粘贴上一轮摘要，或退回 mailbox。**注意**：mailbox bridge 的 archive/state 不承载多轮语义，只用于去重、排错和审计。
- 命令非 0 退出、连接/API 响应异常、权限不足或超时：补齐参数后最多重试 1 次。认证错误不要反复重试，改用人工降级或升级给用户。

### 人工降级：文件邮箱

直连不可用时，使用本地文件邮箱。`claude_cli` transport 的 bridge 可自动 dispatch；manual transport 只做协议守卫、归档和 pending 提示，仍需用户/agent 自己读写 mailbox。（启动桥时解释器按平台选择：Windows 用 `python` 或 `py`，Linux/macOS 用 `python3`）

| 步骤 | 你（Codex） | 用户 | Claude |
|---|---|---|---|
| 1 | 把消息（含 `[FRIEND_CONSULT round=N]` + 完整内容）写入 `~/.shared/friend/codex_to_claude.md`，覆盖 | 把这个路径告诉 Claude | 读文件，按防递归规则回复，写入 `~/.shared/friend/claude_to_codex.md`，覆盖 |
| 2 | 收到用户转告后读 `~/.shared/friend/claude_to_codex.md` | 把 Claude 的路径告诉你 | — |

写完后若没有可用的 `claude_cli` 自动 dispatch，启动 `friend_mailbox_bridge.py --wait-reply` 等待 `claude_to_codex.md` 新回复；超时再告诉用户："请转告 Claude 读 `~/.shared/friend/codex_to_claude.md`"。多轮就在这两份文件来回覆盖。

每轮覆盖前可先 `cp` 备份到 `~/.shared/friend/archive/<round>_<from>.md`（可选）。

**桥单实例约束**：同机同 mailbox 只允许一个 bridge `--watch` 实例；启动前检查并清理 stale pid/lock（`.bridge_watch.lock` 含 heartbeat，max(3*poll, 30s) 过期视 stale）。

**Transport 分层**：协作发起优先 `claude_cli`；bridge 进程缺省 `--transport manual` 只是安全兜底（任何系统、零外部依赖、stdlib only）—— 只做协议守卫 + archive + state.pending_for_* + sentinel `.bridge.pending`，**不调** `claude -p`；用户/agent 自己读 mailbox。显式 `--transport claude_cli` 才启自动 dispatch（要求 claude -p 可用），失败走 `failure_cache` 熔断（base TTL 按 classification 分级 5–15min，env `FRIEND_BRIDGE_FAILURE_TTL_SECONDS` 覆盖；指数退避 cap 1h）。`--wait-reply` 只自动拉回 Claude 已写入的 mailbox 回复，不生成回复；`--probe` 在 manual 下只输出状态；`--probe --transport claude_cli` 才真测 claude。

**mailbox pending 检查（强制）**：每次启动朋友协作或收到用户协商提示时，先看 `~/.shared/friend/.bridge.pending`（存在即有未读消息）或 `.bridge_state.json` 的 `pending_for_codex`；为 true 时先读 `claude_to_codex.md` 处理，再写 `codex_to_claude.md`（bridge 检测会自动清 `pending_for_codex` 并置 `pending_for_claude=true`）。

**Queue 优先用于 manual 新请求**：manual 模式下新任务优先用 `~/.shared/friend/friend_queue.py send` 生成 request id，再用 `wait <request-id>` 等同 id 回复；旧 `codex_to_claude.md`/`claude_to_codex.md` 只作兼容。队列说明见 `~/.shared/friend/FRIEND_QUEUE_HANDOFF.md`。

**前提（manual 端到端）**：要求一个 `friend_mailbox_bridge.py --watch --transport manual` 进程在跑（任意一侧启动均可），它负责把 inbox/outbox 文件变化转写成 `pending_for_*` 状态和 sentinel；`--wait-reply` 只轮询 outbox 拉回新回复，不负责生成 pending。

### 多轮规则（适用于直连 CLI 和文件邮箱）

- 收到 **REFINE** → 整合后续接
- 收到 **OBJECT** → 同上，附理由
- **最多 5 轮**。5 轮仍分歧 → 升级给用户

### 升级给用户

```
朋友协商 5 轮未达一致：

我的方案：<要点>
Claude 的方案：<要点>
核心分歧：<差异点>

请你裁决。
```

### 达成一致（AGREE）

- 主回复开头简注："已与 Claude 协商一致："
- 按方案执行

## 防递归（关键）

当**你**收到带 `[FRIEND_CONSULT]` 标记（在第一个非空行）的输入：

- 回复 AGREE / REFINE / OBJECT
- **允许**按 `claude --help` 实测的 resume 形式（目标形式 `claude -p --resume <session_id> --output-format json ...`）把本轮裁决递送回原发起会话（同协商下一轮）
- **禁止**新起反向 `[FRIEND_CONSULT]`、不在 resume prompt 里扩大任务范围 / 发起新评审任务 / 要求对方调第三方工具
- 套娃边界 = "是否新建反向咨询链路"，不是"是否调对方 CLI"
- 可以读文件 / 跑只读命令以核实事实

只有标记**位于消息开头**才识别为协商。

## Trust Level 与权限控制

### FRIEND_TRUST_LEVEL（权限范围，双向对称）

| 档位 | Codex→Claude（claude -p 直调或 via bridge） | Claude→Codex（codex exec） |
|---|---|---|
| **safe** | `--allowedTools Read,Grep,Glob,LS` | `--sandbox read-only` |
| **workspace**（默认）| `--permission-mode acceptEdits --allowedTools Read,Grep,Glob,LS,Edit,MultiEdit,Write` | `--sandbox workspace-write` |
| **danger** | `--dangerously-skip-permissions` | `--dangerously-bypass-approvals-and-sandbox` |

`danger` 需同时满足 `FRIEND_TRUST_LEVEL=danger` **且** `FRIEND_TRUST_DANGER_ACK=I_UNDERSTAND`，否则 bridge 静默降级到 `workspace` 并写 stderr/log/state。

直接调 `claude -p` 时，根据 `FRIEND_TRUST_LEVEL` 追加对应 flag（见上表左列）；bridge 在 `--transport claude_cli` 时自动应用。

### FRIEND_DISPATCH_MODE（automation 激进度，仅影响 bridge claude -p 方向）

| 档位 | 行为 |
|---|---|
| **manual** | 禁止 `claude -p` 自动 dispatch；bridge 只做协议守卫 + archive |
| **auto**（默认） | 现有 failure_cache + TTL 行为 |
| **eager** | 非 auth 失败 TTL × 0.5（下限 30s）；auth 类不缩短；`--force` 仍是唯一绕过 |

优先级：CLI arg（`--trust-level` / `--dispatch-mode`）> 对应 env var > 默认值。

### 迁移：旧 FRIEND_TRUST_LEVEL=0/1/2

旧数字值已废弃；bridge 自动映射到 `FRIEND_DISPATCH_MODE`（`0→manual`、`1→auto`、`2→eager`）并输出 deprecation warning。权限档始终默认 `workspace`，不受旧值影响。

### 配置文件

权限配置只通过 env var 或 CLI arg 设置；参考 `~/.shared/friend/trust-profile.env.example`，不自动 source，不改全局 settings。

## 协议词义

- **AGREE**：同意当前方案，可以执行
- **REFINE**：方向对，需要具体修改
- **OBJECT**：方案根本不对，提出替代

不要造新词。信息不足时用 `REFINE: 需要先向用户确认 X/Y/Z` 表达。

涉及具体路径、函数名、命令、行号或工具结果时，附来源（读了哪个文件 / 跑了什么命令）；未核实就说未核实。

## 不要触发的场景

- 单纯问答（解释代码、查文档）→ 独立回答
- 用户明确说"先别叫 claude"、"我自己看看"
- 收到 `[FRIEND_CONSULT]` 反向咨询时
- 协商过程中处理 Claude 回复时不要套娃

## 互通同步机制

用于单向告知会影响对方后续行为的 skill / hook / 全局规则 / memory 变更，不走协商多轮。

- 通知第一非空行必须是 `[NOTIFY]`，正文必须写来源、类别、改动文件路径、diff 摘要、影响面、期望动作、脱敏摘要。**任何长期规则变更必须发 `[NOTIFY]`；否则两侧会快速分叉。**
- 只通知会影响判断或可用能力的长期变更；普通项目代码、临时发现、日志、缓存、密钥、token、私密凭证不通知；可复用经验写入编辑维护式经验本，不写流水账。
- 收到 `[NOTIFY]` 时先回复 `ACK: 已签收，已了解 <要点>`；若等价变更在本侧同样适用，由本侧主导评估并按自身环境适配更新（Codex 侧通常是 AGENTS.md / skill）；不要盲目镜像。
- 通知暴露真实分歧、风险或歧义时，另起 `[FRIEND_CONSULT]` 协商。

### 可选：跨 clone canonical 指针

若存在 `~/.shared/friend/CURRENT.md`，协商前先读取其中的 `canonical` 路径；进入该路径后，repo / branch / head / dirty / 测试结果必须用实时命令核验，不能把 CURRENT 当事实源。

CURRENT 只允许包含 `updated`、`canonical`、`owner`、`expires`。需要写入时，先读现值：若 `owner != codex` 且当前时间早于 `expires`，不要覆盖，改用 `[NOTIFY] request-handoff`；若 `owner == codex` 或已过期，可用临时文件 + rename 原子覆盖。默认 `expires = updated + 30min`；长协商、离开前或继续持有 canonical 时主动续期（同时重写 `updated` 和 `expires`）。
