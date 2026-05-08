# 朋友 (friend) — Claude Code × Codex 双向协作 Skill

> 让 **Claude Code** 和 **Codex CLI** 在重要任务上互相协商、互为审稿人，搞不定就找人类终审。

[English summary](#english-summary) at the bottom.

---

## 简介

"朋友"是一个跨 Agent 协作 skill，同时安装到 **Claude Code** 和 **Codex CLI** 两端。当任务进入需要决策的阶段（制定执行性计划、上下文压力大、复杂歧义、高风险信号词、破坏性操作），双方会自动用统一协议互相协商；最多 5 轮内达成一致就执行，无法达成就升级给用户裁决。

**核心理念**：
- 单方面决策容易出错——两个不同模型互相牵制更稳健
- 协议化 + 三态决议（AGREE / REFINE / OBJECT）避免漫无边际的讨论
- 用户始终是终审

## 它解决什么

- **静默幻觉**：让另一方核验具体路径、函数名、命令前必须附来源（"我读了 X 第 Y 行"）
- **上下文腐败**：5 轮上限 + 上下文压力强制触发，避免长会话退化
- **过度自信**：复杂任务双方背靠背给意见，分歧自然显现
- **破坏性误操作**：删除/迁移/生产部署前强制协商
- **跨工具链盲区**：跨仓库 / 权限边界不清 / 修改全局配置时强制协商

## 工作原理

```
┌────────────────┐                         ┌────────────────┐
│  Claude Code   │ ─── codex exec ──────►  │   Codex CLI    │
│   (forward)    │                         │                │
│                │ ◄─── file mailbox ───── │                │
│                │      用户做邮差          │                │
└────────────────┘                         └────────────────┘
```

- **正向（Claude → Codex）**：通过 `codex exec` 命令直接发起协商，session 续接多轮
- **反向（Codex → Claude）**：通过本地文件邮箱 `~/.shared/friend/codex_to_claude.md` 与 `claude_to_codex.md`，用户转告路径
  - *为什么不直接用 `claude -p`？* 实测在多种 API 网关下普通POST 路径会返回空响应或 cloudflare 400。文件邮箱完全本地，零 API 依赖

## 前提条件

| 组件 | 要求 | 验证 |
|---|---|---|
| Claude Code CLI | 已安装并登录 | `claude --version` |
| Codex CLI | 已安装并登录 | `codex --version` |
| Shell | bash / zsh（首选）；PowerShell 5.1+ 可用 | `bash --version` |
| API 接入 | 主进程能用即可（反向链路走文件邮箱） | 试跑任意小任务 |

## 安装

### 方式 A：脚本安装（推荐）

bash / zsh：

```bash
git clone https://github.com/fpyluck/friend-skill.git
cd friend-skill
bash install.sh
```

PowerShell：

```powershell
git clone https://github.com/fpyluck/friend-skill.git
cd friend-skill
powershell -ExecutionPolicy Bypass -File install.ps1
```

脚本会做的事：
1. 复制 `claude/skills/朋友/SKILL.md` → `~/.claude/skills/朋友/SKILL.md`
2. 复制 `codex/skills/朋友/SKILL.md` → `~/.codex/skills/朋友/SKILL.md`
3. 在 `~/.codex/AGENTS.md` 末尾追加全局指针段落（如不存在则创建）
4. 创建邮箱目录 `~/.shared/friend/`
5. 不会覆盖已存在的同名 skill；遇冲突会备份为 `SKILL.md.bak.<timestamp>`

### 方式 B：手动安装

```bash
# Claude 端
mkdir -p ~/.claude/skills/朋友
cp claude/skills/朋友/SKILL.md ~/.claude/skills/朋友/

# Codex 端
mkdir -p ~/.codex/skills/朋友
cp codex/skills/朋友/SKILL.md ~/.codex/skills/朋友/

# 全局指针（追加到 ~/.codex/AGENTS.md）
cat codex/AGENTS.md.snippet >> ~/.codex/AGENTS.md

# 邮箱目录
mkdir -p ~/.shared/friend
```

### 验证安装

在 Claude Code 会话里输入 `/朋友` 应能看到 skill；在 Codex 启动时 `~/.codex/AGENTS.md` 会被读取。

## 使用

### 自动触发

不需要你做任何事——skill 会在以下场景自动启动协商：

**强制触发**（不询问）：
- 制定**执行性计划**（实施方案 / 架构决策 / 批量改动）
- 工作中**上下文压力大**（已读了大量文件、跑了大量工具）
- 任务**复杂或歧义**（多种合理路径、跨多子系统）
- 用户使用"重要 / 关键 / 小心 / 别搞砸"等**高风险信号词**
- **破坏性 / 不可逆操作**（删除、迁移、生产部署）
- 跨仓库 / 跨工具链 / 权限边界不清 / 修改全局配置

**询问用户**：
- 难判任务（"这个要不要叫上 codex？"）

**简单任务默认不触发**（单文件改动、明确修复）——避免打断流程。

### 手动触发

向 Claude Code 或 Codex 任意一方说：
- `/朋友`
- "问问 codex / 问问 claude"
- "和朋友商量一下"
- "叫上朋友"

### 反向链路（Codex → Claude）实操

当 Codex 想问 Claude 意见时，会按文件邮箱协议工作。你（用户）只需在两端转告：

```
Codex 那边：
> 你（Codex）："朋友消息已写入 ~/.shared/friend/codex_to_claude.md。请转告 Claude 读这份文件。"

你切到 Claude Code 那边，说：
> 你："读 ~/.shared/friend/codex_to_claude.md"

Claude 那边：
> Claude 自动按防递归规则回复，写入 ~/.shared/friend/claude_to_codex.md。
> Claude："回复已写入 ~/.shared/friend/claude_to_codex.md，请转告 Codex 读取。"

你切回 Codex，说：
> 你："读 ~/.shared/friend/claude_to_codex.md"
```

多轮就在这两份文件来回覆盖。

## 协议参考

### 标记

| 标记 | 用途 | 是否需多轮 |
|---|---|---|
| `[FRIEND_CONSULT round=N]` | 双向协商，求决议 | 是（最多 5 轮） |
| `[NOTIFY]` | 单向通知（skill / hook / 偏好变更） | 否（接收方仅 ACK） |

标记**必须出现在消息第一个非空行**。这是协商身份标记，避免文件内容偶然包含触发误判。

### 三态决议

- **AGREE**：同意当前方案，可执行
- **REFINE**：方向对，需具体修改
- **OBJECT**：方案不对，提替代

不允许造新词。信息不足时用 `REFINE: 需要先向用户确认 X/Y/Z`。

### 首次项目交接卡（round=1 必填）

涉及本地工程时，第一次发起咨询必须附结构化交接信息：

```text
## 项目交接（首次必填）
- 项目根目录: <绝对路径>
- 执行环境: <Windows PowerShell / WSL bash / Docker compose / devcontainer / remote / N/A>
- 项目类型: <语言 + 框架>
- 虚拟环境: <绝对路径 / conda env 名 / 容器服务名 / N/A>
- 激活命令: <优先不依赖激活态；确需 activate 时写一行；不需要则 N/A>
- 主要工具调用:
  - test: <一行命令或 N/A>
  - build: <一行命令或 N/A>
  - run: <一行命令或 N/A>
  - lint: <一行命令或 N/A>
- 关键约定/限制: <2-3 条；没有写 N/A>
- 相关文件指针: <按需 @ 引用或绝对路径列表；没有写 N/A>
```

**关键规则**：
- 路径写**绝对路径**
- 命令写**一行可执行字符串**（不是描述）
- 优先写**不依赖激活态**的命令（解释器绝对路径 / `uv run` / `docker compose exec`），避免无状态 shell 陷阱
- 不复制 README 全文，只列文件指针让对方按需读
- 不写密钥 / token / 凭证 / `.env` 原文
- 新开无历史会话即使逻辑上是后续协商，也按 round=1 重发完整交接卡（判断标准是"对方有没有上下文"）

### 抗幻觉原则

回复中提及具体路径、函数名、命令、行号或工具结果时，**必须附来源**（读了哪个文件、跑了什么命令）；未核实就明说"未核实"。

## 故障排查

### `claude -p` 反向调用失败（HTTP 200 空响应或 cloudflare 400）

**症状**：Codex 调 `claude -p` 报 `API Error: API returned an empty or malformed response (HTTP 200)` 或 `cloudflare 400`。

**原因**：本机使用的 API 网关通常只兼容 Claude Code 主进程的 streaming endpoint，所以 `claude -p` 这种非交互单次调用打不通。

**解决**：本 skill 已默认走文件邮箱反向链路，**不依赖 `claude -p`**。如未来你的网关修复了，可在 `~/.codex/skills/朋友/SKILL.md` 取消 `claude -p` 备选段的禁用。

**自检**：
```bash
# 检查继承 env
env | grep ANTHROPIC_BASE_URL
# 探针看路径是否兼容
curl -X POST -H "Content-Type: application/json" \
  -H "anthropic-version: 2023-06-01" \
  $ANTHROPIC_BASE_URL/v1/messages
# 200 + 空 body 或 400 cloudflare → 网关不兼容
```

### Codex 找不到 `codex exec resume`

**症状**：报错 `error: unrecognized subcommand 'resume'`。

**原因**：旧版 Codex CLI 不支持 `exec resume`。

**解决**：升级到 Codex CLI ≥ 0.128，或在协商时不用 session 续接，每轮新开 `codex exec` 在 prompt 里粘贴上一轮要点。

### 文件邮箱路径在 PowerShell 找不到

**症状**：PowerShell 下 `~/.shared/friend/...` 找不到文件。

**原因**：PowerShell 不展开 `~`，应该用 `$HOME`。

**解决**：手动改成 `$HOME/.shared/friend/...` 或 `Join-Path $HOME '.shared/friend'`。Skill 文件已注明 shell 假设，agent 应自行处理。

### 中文乱码

**症状**：Codex 用 PowerShell 写邮箱文件出现乱码。

**原因**：PowerShell 默认编码不是 UTF-8。

**解决**：用 `[System.IO.File]::WriteAllText($path, $content, [System.Text.UTF8Encoding]::new($false))` 强制 UTF-8 无 BOM。

### 用户忘了转告路径

**症状**：Codex 写完邮箱后挂着等回复，但用户没告诉 Claude 去读。

**解决**：协议要求 Codex 在写完后**主动告诉用户**："请转告 Claude 读 `~/.shared/friend/codex_to_claude.md`"。如未提示，可以让 Codex 重发。

## 已知限制

1. **反向链路依赖人**：用户做邮差，不能完全自动化。如果想自动，需要写文件监听 hook（本 skill 暂不实现）
2. **单机 / 单用户**：邮箱路径假设单用户；多人协作或远程开发场景需自定义路径
3. **API 网关兼容性**：`claude -p` 反向链路当前默认禁用；不同网关行为不一
4. **不是 LLM 路由**：朋友 skill 只是协议，**不调度任务到不同模型**——双方都是当前会话内的本机 agent
5. **强制触发可能误判**：模型对"上下文压力大"的判断是软启发，可能误触发或漏触发；用户可手动 `/朋友` 补救

## 自定义

### 调整最大轮数

编辑两边 `SKILL.md` 中的 "最多 5 轮" → 你的目标值。

### 调整触发条件

编辑 `## 触发判定` 章节。建议：减项不加项，避免提示词过强。

### 改邮箱路径

编辑两边 `SKILL.md` 中所有 `~/.shared/friend/` 引用。注意保持双方一致。

### 添加 hooks 自动转告

把"读 `~/.shared/friend/codex_to_claude.md`"自动注入用户消息。这会让反向链路无需人邮差，但实现复杂（需要 Claude Code 的 `Stop` 或 `UserPromptSubmit` hook 监听邮箱文件 mtime）。本 skill v1 不实现，留作未来扩展。

## 开发故事

这个 skill 是**通过它自己的协议自我迭代出来的**。整个开发过程中：
- v0：手写两份 SKILL.md
- v0.1：用 `[FRIEND_CONSULT round=1]` 让 Codex 评审 v0
- v0.2：Codex REFINE 直接动手改文件（指出 `codex-wrapper` 不存在、应该用 `codex exec`）
- v0.3：又一轮协商加入"互通同步机制"
- v0.4：再一轮加入"首次项目交接卡"
- v0.5：联网搜程序员真实抱怨（venv 陷阱、context rot、AGENTS.md 太长反而有害），减法 + 加 3 条原则
- v0.6：诊断并修复反向链路 gateway bug，改用文件邮箱
- v1.0：泛用性审查，硬编码全部占位符化

每一轮都是用 `[FRIEND_CONSULT]` 协议本身完成的——这是它最好的实战测试。

## 项目结构

```
friend-skill/
├── README.md                          # 本文件
├── LICENSE                            # MIT
├── install.sh                         # bash 安装脚本
├── install.ps1                        # PowerShell 安装脚本
├── claude/
│   └── skills/朋友/SKILL.md           # 复制到 ~/.claude/skills/朋友/
├── codex/
│   ├── skills/朋友/SKILL.md           # 复制到 ~/.codex/skills/朋友/
│   └── AGENTS.md.snippet              # 追加到 ~/.codex/AGENTS.md
└── shared/
    └── friend/.gitkeep                # 创建 ~/.shared/friend/ 目录占位
```

## 贡献

欢迎 issue / PR。请保持改动**最小可用**——参考 ETH Zurich 2026.02 研究：详细 AGENTS.md 反而降低 agent 成功率 3% 并增加 20% 成本。SKILL.md 软上限 250 行。

## License

MIT — 见 [LICENSE](LICENSE)。

---

## English Summary

**friend (朋友)** is a bidirectional collaboration skill installed on both **Claude Code** and **Codex CLI**. When tasks enter decision phases (executable plans, context pressure, ambiguity, high-risk signals, destructive operations), the two agents automatically negotiate via a unified protocol with three-state verdicts (AGREE / REFINE / OBJECT), up to 5 rounds, escalating to the human user if no consensus.

The forward channel uses `codex exec`. The reverse channel uses a local file mailbox (`~/.shared/friend/`) with the user as postman, because `claude -p` is unreliable through common API gateways. Zero cloud-API dependency for the reverse path.

See Chinese sections above for installation, usage, protocol, and troubleshooting.
