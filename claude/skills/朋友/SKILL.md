---
name: 朋友
description: 与本地 Codex 双向协商完成任务的协作 skill。在制定执行性计划阶段强制触发；工作阶段当上下文压力大、复杂歧义、用户用了高风险信号词、或涉及破坏性/全局/跨仓库操作时强制触发。难判时询问用户，简单任务默认不触发。多轮协商（最多 5 轮）至达成一致，分歧由用户裁决。也可通过 /朋友 或"问问 codex"、"和朋友商量"手动触发。
---

# 朋友 — Claude × Codex 协作

你（Claude）和本地 Codex 是搭档。重要任务两人协商，搞不定就找用户，**用户是终审**。

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

- **难判任务**：你无法判断是否复杂时，一句"这个要不要叫上 codex？"
- **简单任务默认不触发**（单文件改动、明确修复、显然执行）—— 别打断流程

### 手动触发

用户输入 `/朋友`、说"问问 codex"、"和朋友商量"、"叫上朋友" → 立即进入协商

## 协商协议

### 标记规范（关键）

消息**第一个非空行**必须是 `[FRIEND_CONSULT round=N]`，其中 N 从 1 开始。这是协商身份标记，必须在开头才识别为协商，避免文本中偶然出现该串触发误判。

### 默认范围：只读咨询

协商默认**只是要意见**，不要求对方改文件。如果你希望 Codex 直接改文件，必须在消息中显式写出："请直接修改以下文件：<路径>"，否则 Codex 应只给建议。

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

### 第一轮：发起咨询（你 → Codex）

下面示例为 bash + GNU 工具；PowerShell 用 `@'...'@` heredoc + `$HOME` 替 `~`。`<TMP>` 是本机可写临时目录（例如 `~/.codex/tmp` / `$TMPDIR` / `%TEMP%`），`<N>` 是当前轮次。

```bash
codex exec --skip-git-repo-check -C "<task_dir>" --json \
  -o "<TMP>/friend_reply_round<N>.txt" \
  - <<'EOF'
[FRIEND_CONSULT round=1]

阶段：PLAN  # 或 WORK
任务：<用户原始请求要点>
## 项目交接（首次必填；不涉及本地工程可写 N/A）
- 项目根目录: <绝对路径或 N/A>
- 执行环境: <本机 Windows PowerShell / WSL bash / Docker compose service / devcontainer / remote / N/A>
- 项目类型: <语言 + 框架或 N/A>
- 虚拟环境: <绝对路径 / conda env 名 / 容器服务名 / N/A>
- 激活命令: <优先不依赖激活态；确需 activate 时写一行命令；不需要则 N/A>
- 主要工具调用:
  - test: <一行命令或 N/A>
  - build: <一行命令或 N/A>
  - run: <一行命令或 N/A>
  - lint: <一行命令或 N/A>
- 关键约定/限制: <2-3 条；没有写 N/A>
- 相关文件指针: <按需 @ 引用或绝对路径列表；没有写 N/A>

我的草案：
<计划 / 方案 / 关键决策点 / 已发现的事实>

待评审：
1. 是否有遗漏 / 错误 / 更优解
2. 我没考虑到的风险点
3. 决议：AGREE / REFINE / OBJECT

回复格式严格：
- AGREE: <一句话理由>
- REFINE: <具体修改建议，可分多条>
- OBJECT: <反对原因 + 替代方案>
EOF
```

要点：
- `--skip-git-repo-check`：协商不限定 git 仓库
- `-C <task_dir>`：传当前任务目录（让 Codex 用 @ 引用本地文件）
- `--json`：输出 JSONL 事件流，含 session_id（在 stdout 里），从中解析
- `-o <file>`：把最终 agent 消息写入文件，便于读取（避免 stdout 编码乱）
- `- <<'EOF'`：从 stdin 读 prompt，HEREDOC 保护特殊字符
- 超时建议 7200000，前台执行；CLI 报错、空响应或超时：重试 1 次，仍失败就升级给用户，不继续硬猜。

读取回复：`Read <TMP>/friend_reply_round<N>.txt`。

### 多轮协商

从 `--json` stdout 里抓 `session_id`（事件 `session_configured` 或类似），然后：

```bash
codex exec resume <session_id> --skip-git-repo-check --json \
  -o "<TMP>/friend_reply_round<N>.txt" \
  - <<'EOF'
[FRIEND_CONSULT round=2]
根据你的建议修订如下：<修订版>
仍维持的部分：<未采纳的点 + 理由>
请再判：AGREE / REFINE / OBJECT
EOF
```

注意：`codex exec resume` **不接受 `-C` 标志**（cwd 由原会话锁定）。如果 `session_id` 抓取失败，用 `codex exec resume --last ...` 拿最近一次会话；或退化为新开 `codex exec` 并在 prompt 里粘贴上一轮要点。**`codex resume` 的可用形式以 `codex --help` 实测为准。**

- 收到 **REFINE** → 整合后续接发新一轮
- 收到 **OBJECT** → 同上，附你坚持/接受的理由
- **最多 5 轮**。5 轮仍分歧 → 升级给用户

### 升级给用户

```
朋友协商 5 轮未达一致：

我的方案：<要点>
Codex 的方案：<要点>
核心分歧：<差异点>

请你裁决。
```

### 达成一致（AGREE）

- 主回复开头简注："已与 Codex 协商一致："
- 按方案执行

## 防递归（关键）

当**你**收到带 `[FRIEND_CONSULT]` 标记（在第一个非空行）的输入，即 Codex 反向咨询你：

- **直接回复 AGREE / REFINE / OBJECT，不要再调用 codex exec**
- 可以读文件 / 跑只读命令以核实事实，但**禁止**反向调用 codex CLI
- 否则会陷入死循环

只有标记**位于消息开头**才识别为协商，避免文件内容偶然包含该串触发误判。

## 反向链路：文件邮箱

由于本机 Codex 调 `claude -p` 受网关/token 限制不通，反向消息走文件邮箱。当用户告诉你"读 `~/.shared/friend/codex_to_claude.md`"或类似话：

1. 读 `~/.shared/friend/codex_to_claude.md`
2. 第一非空行若为 `[FRIEND_CONSULT round=N]`，按防递归直接回复（AGREE/REFINE/OBJECT），写入 `~/.shared/friend/claude_to_codex.md`（覆盖）
3. 告诉用户："回复已写入 `~/.shared/friend/claude_to_codex.md`，请转告 Codex 读取"

多轮在同两份文件来回覆盖即可。

## 协议词义

- **AGREE**：同意当前方案，可以执行
- **REFINE**：方向对，需要具体修改
- **OBJECT**：方案根本不对，提出替代

不要造新词。信息不足时用 `REFINE: 需要先向用户确认 X/Y/Z` 表达。

涉及具体路径、函数名、命令、行号或工具结果时，附来源（读了哪个文件 / 跑了什么命令）；未核实就说未核实。

## 不要触发的场景

- 单纯问答（解释代码、查文档）→ 独立回答
- 用户明确说"先别叫 codex"、"我自己看看"
- 收到 `[FRIEND_CONSULT]` 反向咨询时（见防递归）
- 已在协商过程中处理 Codex 回复，不要套娃

## 互通同步机制

用于单向告知会影响对方后续行为的 skill / hook / 全局规则 / memory 变更，不走协商多轮。

- 通知第一非空行必须是 `[NOTIFY]`，正文写来源、类别、变更、路径、影响、期望动作、脱敏摘要。
- 只通知会影响判断或可用能力的长期变更；普通项目代码、临时发现、日志、缓存、密钥、token、私密凭证不通知。
- 收到 `[NOTIFY]` 时只回复 `ACK: 已签收，已了解 <要点>`；默认不镜像安装、不改文件。
- 通知暴露真实分歧、风险或歧义时，另起 `[FRIEND_CONSULT]` 协商。
