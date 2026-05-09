# 朋友 skill — Windows PowerShell 详细命令

主 SKILL.md 是 bash + GNU 工具示例。本文件给 PowerShell 用户提供等价命令、`session_id`/`thread_id` 兼容提取、`tee` 写法等。适用：Windows + PowerShell（不是 git bash 或 WSL）。bash 环境直接看主 SKILL.md。

## 第一轮：发起咨询（PowerShell 版）

```powershell
$prompt = @'
[FRIEND_CONSULT round=1]
<prompt 内容（原样粘贴主 SKILL.md 模板里的内容）>
'@

$prompt | codex exec --skip-git-repo-check -C "<task_dir>" --json `
  -o "$env:TEMP\friend_reply_roundN.txt" - |
  Out-File "$env:TEMP\friend_events_roundN.jsonl" -Encoding utf8

# 读取回复
Get-Content "$env:TEMP\friend_reply_roundN.txt"

# 提取 session_id（codex 新版字段名为 thread_id；老版为 session_id，按实测取）
$sessionId = (Get-Content "$env:TEMP\friend_events_roundN.jsonl" |
  ForEach-Object { try { $_ | ConvertFrom-Json -EA Stop } catch { $null } } |
  Where-Object { $_ -and ($_.session_id -or $_.thread_id) } |
  Select-Object -First 1 |
  ForEach-Object { if ($_.session_id) { $_.session_id } else { $_.thread_id } })
```

## bash 版的 session_id / thread_id 提取一行命令

```bash
SESSION_ID=$(grep -oE '"(session_id|thread_id)":"[^"]*"' "$TMP/friend_events_round1.jsonl" | head -1 | cut -d'"' -f4)
```

## 多轮续接（PowerShell）

```powershell
$prompt | codex exec resume $sessionId --skip-git-repo-check --json `
  -o "$env:TEMP\friend_reply_roundN.txt" -
```

注意：`codex exec resume` 不接受 `-C` 标志，cwd 由原会话锁定。

## 同时捕获 events.jsonl 和回复（bash tee 写法）

主 SKILL.md 简化的写法用 `> events.jsonl 2>&1`。如果你想更接近"管道流式"地观察 events，用：

```bash
codex exec --skip-git-repo-check -C "<task_dir>" --json \
  -o "<TMP>/friend_reply_round<N>.txt" \
  - <<'EOF' | tee "<TMP>/friend_events_round<N>.jsonl" >/dev/null
[FRIEND_CONSULT round=1]
...
EOF
```

`tee ... >/dev/null` 把 stdout 同时写文件 + 丢弃终端（避免 Windows console 编码乱）。
