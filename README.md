# 四合技能套件：朋友 × 兄弟们 × 帮手 × 交班
# Four-Skill Suite: Friend × Xiongdimen × Helper × Handoff

> Claude Code、Codex、Gemini 三端协作 — 协商、对齐、分工、交接，一套走到底。

---

## 一句话定位

| 技能 | 触发词 | 作用 |
|---|---|---|
| `朋友` | `朋友` / `/friend` | Claude ↔ Codex 双端实时协商，关键时刻第二视角 |
| `兄弟们` | `兄弟们` / `/xiongdimen` | Claude × Codex × Gemini 三方对齐，Gemini 补产品/UX/多模态视角 |
| `帮手` | `帮手` / `/helper` | 协商结束后的文件不重叠分工执行 |
| `交班` | `交班` / `/handoff` | 写出下一个 agent 5 分钟内能接手的持久化工程状态 |

四个技能是一条链：**朋友/兄弟们** 做决策，**帮手** 做执行，**交班** 做记录。

---

## What's New in v3.0 — 2026-05-19

这是一次全新重写，核心变化是加入 **Gemini** 作为第三端，以及 **兄弟们 (xiongdimen)** 技能的正式发布。

### 三端技能体系

- **Gemini 加入**：`兄弟们` 技能现在覆盖三个 CLI（Claude Code + Codex + Gemini），提供完整的三方对齐能力。
- **`xiongdimen` 独立发布**：Claude 侧、Codex 侧、Gemini 侧各有对应的 SKILL.md，角色清晰分工：
  - Claude：歧义检查、备选方案、用户侧叙事、风险梳理
  - Codex：实现契约、后端/API 形态、仓库侧风险、验证边界
  - Gemini：广度、前端/UX、多模态/产品评审（叶子审阅者，返回结论后停止）
- **`gemini_leaf.py` 统一分发**：Claude 和 Codex 两端都打包了同一个 Gemini 运行器脚本。

### 四技能完整套件

- `朋友` (friend)：双端协商，最多 5 轮，三态裁决（AGREE / REFINE / OBJECT）
- `兄弟们` (xiongdimen)：**新** 三方对齐，`朋友` transport + Gemini 叶子查询
- `帮手` (helper)：**经 `[SPLIT: YES]` 授权后**的文件不重叠分工执行
- `交班` (handoff)：工程持久化，9 节标准模板，支持 agent 切换和上下文重置恢复

### 其他改进

- `friend_discovery.py` 加入共享运行时，mailbox 路径自动发现更可靠
- `POWERSHELL_TIPS.md` 同步更新 — Windows PowerShell 用户的专属参考
- 协议标记规范化：`[FRIEND_CONSULT round=N]` 必须在第一个非空行
- `[XIONGDIMEN_GEMINI_QUERY]` 替代废弃的 `[XIONGDIMEN_FRONTEND_QUERY]`

---

## 它解决什么

单个 agent 最容易出问题的地方，通常不是"不会写代码"，而是：

- 长任务后上下文开始漂移，却还在自信推进。
- 方案有多条合理路径，但模型只沿着第一条路走到底。
- 删除、迁移、发布、全局配置这类操作影响很大，却缺少第二视角。
- 跨仓库、跨 CLI、跨系统环境时，某一端对另一端的真实约束不了解。
- 产品/UX/多模态判断不是单一 agent 的强项，需要独立广度视角。
- 会话切换或上下文重置时，工程状态散落在记忆里，接手方不知从哪读起。

`朋友` 和 `兄弟们` 让关键节点有第二或第三视角。`帮手` 让多 agent 并行执行不踩脚。`交班` 让切换不断线。

---

## 文件树

```
friend-skill/
├── claude/skills/
│   ├── friend/
│   │   ├── SKILL.md                        # Claude 侧协商规则
│   │   ├── POWERSHELL_TIPS.md              # PowerShell 专用说明
│   │   └── scripts/
│   │       ├── friend_mailbox_claude.py    # Claude 侧 mailbox 工具
│   │       ├── start_friend_session.sh     # 会话启动辅助
│   │       └── surface_friend_pending.sh   # 挂起任务浮出工具
│   ├── xiongdimen/
│   │   ├── SKILL.md                        # Claude 侧三方对齐规则
│   │   └── scripts/
│   │       └── gemini_leaf.py              # Gemini 叶子运行器
│   ├── helper/
│   │   └── SKILL.md                        # Claude 侧执行分工规则
│   └── handoff/
│       ├── SKILL.md                        # Claude 侧交班规则
│       └── agents/
│           └── openai.yaml                 # OpenAI-compatible agent 配置
├── codex/
│   ├── AGENTS.md.snippet                   # 写入 ~/.codex/AGENTS.md 的托管块
│   └── skills/
│       ├── friend/
│       │   └── SKILL.md                    # Codex 侧协商规则
│       ├── xiongdimen/
│       │   ├── SKILL.md                    # Codex 侧三方对齐规则
│       │   └── scripts/
│       │       └── gemini_leaf.py          # Gemini 叶子运行器
│       ├── helper/
│       │   └── SKILL.md                    # Codex 侧执行分工规则
│       └── handoff/
│           ├── SKILL.md                    # Codex 侧交班规则
│           ├── scripts/
│           │   └── new_handoff.py          # 交班骨架生成器
│           └── assets/
│               └── handoff-template.md     # 规范模板（9 节）
├── gemini/skills/
│   └── xiongdimen/
│       └── SKILL.md                        # Gemini 叶子审阅规则
├── shared/friend/                          # 共享运行时（三端共用）
│   ├── friend_discovery.py                 # mailbox 路径自动发现
│   ├── friend_gate.py                      # 权限把关与格式验证
│   ├── friend_mailbox_bridge.py            # 自动/手动消息桥
│   ├── friend_queue.py                     # 队列（mailbox overwrite-safe fallback）
│   ├── trust-profile.env.example           # 信任级别配置示例
│   └── tests/
│       └── test_friend_gate.py
├── install.sh                              # bash/zsh/WSL 一键安装
├── install.ps1                             # PowerShell 一键安装
└── LICENSE
```

---

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

安装器是幂等的 — 重复运行只会更新文件，旧文件自动备份。

---

## 技能使用说明

### 朋友 (friend) — Claude ↔ Codex 双端协商

**何时触发**（自动，无需用户操作）

- 制定实现计划、架构决策、批量变更计划
- 上下文压力大、任务复杂或有歧义
- 用户说了"重要/关键/小心"等高风险词
- 破坏性/不可逆操作（删除、迁移、发布、全局配置）
- Bug 排查陷入瓶颈，反复尝试没有新信号

**手动触发**

在 Claude 或 Codex 中输入：`朋友`、`/friend`、`问问 codex/claude`、`和朋友商量`

**协商流程**

```
[FRIEND_CONSULT round=1]   ← 第一个非空行必须是这行
Phase: PLAN | WORK
Task: <一句话描述>

My draft: <方案>
Review points:
1. 有什么漏洞或更好的方案？
2. 有没有没考虑到的风险？
3. Decision: AGREE / REFINE / OBJECT
```

- 最多 5 轮，达成 `AGREE` 后执行
- 未达成共识 → 升级给用户裁决
- 协商结束后给用户一段简洁的 Owner Note

---

### 兄弟们 (xiongdimen) — Claude × Codex × Gemini 三方对齐

**何时使用**

- 需要 Gemini 的产品/UX/多模态/广度视角时
- 功能级设计、前后端对齐、meta-skill 设计
- 比 `朋友` 更重，不要用于单 agent 能处理的任务

**触发**（仅手动）

输入：`兄弟们`、`/xiongdimen`、`xiongdimen`

**流程**

1. 通过 `朋友` transport 向 Claude/Codex 发送 `[FRIEND_CONSULT round=1] Mode: xiongdimen`
2. 向 Gemini 发送 `[XIONGDIMEN_GEMINI_QUERY]`（通过 `gemini_leaf.py`）
3. 综合三方意见，出具 `[XIONGDIMEN_BRIEF]`

**Gemini 查询格式**

```text
[XIONGDIMEN_GEMINI_QUERY]
Task: <一句话>
Focus: frontend | product | multimodal | meta-skill | other
Context: <只给 Gemini 需要的内容>
Known constraints: <后端/API/用户约束，或 N/A>
```

Gemini 返回格式：`Status / Key observations / Interface needs / Risks / Open questions`

---

### 帮手 (helper) — 协商后分工执行

**前提**：必须先有 `[FRIEND_BRIEF]` 或 `[XIONGDIMEN_BRIEF]` 且 `[SPLIT: YES]`，否则说 `No split-ready brief found — 先走 朋友`。

**触发**（仅手动，且需 `[SPLIT: YES]` 授权）

输入：`帮手`、`/helper`、`helper`

**Work Card 格式**

```text
[HELPER_WORK_CARD]
source: FRIEND_BRIEF | XIONGDIMEN_BRIEF
goal: <一句话>
mode: file-disjoint
claude: <Claude 负责的路径/任务>
codex: <Codex 负责的路径/任务>
integrator: Claude | Codex
validate: <验证命令，或 N/A>
stop-if: <重叠、共享配置、验证变更、阻塞条件>
```

- 各 agent 只在自己的路径/任务内工作
- 执行完成后发送 `[HELPER_COMPLETE]`，integrator 汇总验证

---

### 交班 (handoff) — 工程持久化

**触发**

输入：`交班`、`/handoff`、`handoff`，或说"接力"、"帮我写个交班"

**用途**

- Agent 切换前保存工程状态
- 上下文重置后从同一状态继续
- 同一 agent 的自交班（self-handoff）

**默认路径**：`~/.shared/friend/handoffs/<project-key>.md`

**骨架生成器**（Codex 侧）

```bash
python3 ~/.codex/skills/handoff/scripts/new_handoff.py \
  --project-key my-project \
  --title "My Project" \
  --agent codex \
  --target-agent claude
```

**标准模板（9 节）**

| 节 | 内容 |
|---|---|
| `current_objective` | 背景、目标、当前停止点 |
| `environment_commands` | 路径、shell、虚拟环境、运行/测试/构建命令 |
| `file_map` | ≤5 个重要路径及用途 |
| `open_issues` | 阻塞项、未解决问题、风险假设 |
| `decisions_and_changes` | ≤5 条最近决策（含原因） |
| `error_ledger` | 重大错误、根因、修复、预防 |
| `next_actions` | 有序、可测试的下一步 |
| `agent_notes` | 继续方注意事项、同伴审阅要点 |
| `owner_review` | 用户标注：`[TODO]` / `[DONE]` / `[USER-ACTION]` |

---

## 四技能协作示意

```
用户输入一个复杂任务
        │
        ▼
  [朋友] 双端协商
  Claude ↔ Codex
        │
   (需要产品/UX视角?)
        ├── YES → [兄弟们] 三方对齐
        │         Claude × Codex × Gemini
        │
   AGREE → 执行策略选择
        │
        ├── 单端执行 → Claude 或 Codex 直接做
        ├── 分工执行 → [帮手] file-disjoint 分工
        │
   执行完成 / 上下文压力 / 角色切换
        │
        ▼
  [交班] 写持久化工程状态
  供下一个 agent 接手
```

---

## 信任级别配置

三端共用 `FRIEND_TRUST_LEVEL` 环境变量：

| 级别 | Claude → Codex | Codex → Claude | 说明 |
|---|---|---|---|
| `safe` | `--sandbox read-only` | `--allowedTools Read,Grep,Glob,LS` | 只读建议 |
| `workspace` (默认) | `--sandbox workspace-write` | `--permission-mode acceptEdits` + Read/Write tools | 可写工作区 |
| `danger` | `--dangerously-bypass-approvals-and-sandbox` | `--dangerously-skip-permissions` | 危险模式，需 `FRIEND_TRUST_DANGER_ACK=I_UNDERSTAND` |

配置参考：`shared/friend/trust-profile.env.example`

---

## 常见问题

**Q: 朋友和兄弟们什么时候用哪个？**
A: 多数情况用 `朋友`。只有当 Gemini 的产品/UX/多模态视角对当前任务有实质帮助时，才用 `兄弟们`。

**Q: `[SPLIT: YES]` 自动触发帮手吗？**
A: 不会。`[SPLIT: YES]` 是授权标记，仍需用户或主 agent 显式调用 `帮手`。

**Q: Gemini 不可用怎么办？**
A: 记录 `Gemini: BLOCKED (<reason>)` 并继续，不阻塞流程。

**Q: 协商陷入循环怎么办？**
A: `朋友` 最多 5 轮；如果讨论不再产生新信息，优先重新检查问题框架，而不是继续打磨方案。5 轮后自动升级给用户裁决。

**Q: 在 Windows PowerShell 中有什么特别注意的？**
A: 参见 `claude/skills/friend/POWERSHELL_TIPS.md`，里面有 PowerShell 专用的 here-string 格式和 session_id 提取方法。

---

## 反馈与贡献

Issues: https://github.com/fpyluck/friend-skill/issues

---

MIT License © 2026 fpyluck and contributors
