# Friend (朋友) Skill — Windows PowerShell Details

The main SKILL.md shows bash + GNU tool examples. This file covers the PowerShell equivalents, `session_id`/`thread_id` extraction, and tee patterns. Use this file when your shell is Windows PowerShell (not Git Bash or WSL — those use the main SKILL.md directly).

## Round 1: Initiating consultation (PowerShell)

```powershell
$prompt = @'
[FRIEND_CONSULT round=1]
<prompt content — paste from the template in SKILL.md>
'@

$prompt | codex exec --skip-git-repo-check -C "<task_dir>" --json --sandbox workspace-write `
  -o "$env:TEMP\friend_reply_roundN.txt" - |
  Out-File "$env:TEMP\friend_events_roundN.jsonl" -Encoding utf8

# Read the reply
Get-Content "$env:TEMP\friend_reply_roundN.txt"

# Extract session_id (new codex CLI uses thread_id; older uses session_id — test empirically)
$sessionId = (Get-Content "$env:TEMP\friend_events_roundN.jsonl" |
  ForEach-Object { try { $_ | ConvertFrom-Json -EA Stop } catch { $null } } |
  Where-Object { $_ -and ($_.session_id -or $_.thread_id) } |
  Select-Object -First 1 |
  ForEach-Object { if ($_.session_id) { $_.session_id } else { $_.thread_id } })
```

## Bash: extracting session_id / thread_id (one-liner)

```bash
SESSION_ID=$(grep -oE '"(session_id|thread_id)":"[^"]*"' "$TMP/friend_events_round1.jsonl" | head -1 | cut -d'"' -f4)
```

## Multi-round continuation (PowerShell)

```powershell
$prompt | codex exec resume $sessionId --skip-git-repo-check --json --sandbox workspace-write `
  -o "$env:TEMP\friend_reply_roundN.txt" -
```

Note: `codex exec resume` does not accept `-C`; cwd is locked to the original session.

## Capturing both events.jsonl and the reply (bash tee pattern)

```bash
codex exec --skip-git-repo-check -C "<task_dir>" --json --sandbox workspace-write \
  -o "<TMP>/friend_reply_round<N>.txt" \
  - <<'EOF' | tee "<TMP>/friend_events_round<N>.jsonl" >/dev/null
[FRIEND_CONSULT round=1]
...
EOF
```

`tee ... >/dev/null` writes stdout to file while discarding terminal output (avoids Windows console encoding issues).
