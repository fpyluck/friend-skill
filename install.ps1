# friend-skill installer (PowerShell)
# Installs the friend (朋友) and handoff (交班) skills.
# Idempotent; backs up existing files; updates AGENTS.md via managed block.

[CmdletBinding()]
param()

$ErrorActionPreference = 'Stop'
$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$Timestamp = Get-Date -Format 'yyyyMMdd_HHmmss'

$ClaudeFriend  = Join-Path $HOME '.claude/skills/朋友'
$CodexFriend   = Join-Path $HOME '.codex/skills/朋友'
$ClaudeHandoff = Join-Path $HOME '.claude/skills/handoff'
$CodexHandoff  = Join-Path $HOME '.codex/skills/handoff'
$Mailbox = Join-Path $HOME '.shared/friend'
$Agents  = Join-Path $HOME '.codex/AGENTS.md'

function Backup-IfExists {
    param([string]$Path)
    if (Test-Path $Path) {
        $bak = "$Path.bak.$Timestamp"
        Copy-Item $Path $bak
        Write-Host "  backup: $Path -> $bak"
    }
}

function Install-File {
    param([string]$Src, [string]$Dst)
    if (-not (Test-Path $Src)) {
        Write-Error "source missing: $Src"
    }
    $dstDir = Split-Path -Parent $Dst
    if (-not (Test-Path $dstDir)) {
        New-Item -ItemType Directory -Path $dstDir -Force | Out-Null
    }
    Backup-IfExists $Dst
    Copy-Item $Src $Dst -Force
    Write-Host "  ✓ $Dst"
}

Write-Host '[1/7] Install Claude-side 朋友 skill'
Install-File (Join-Path $ScriptDir 'claude/skills/朋友/SKILL.md')              (Join-Path $ClaudeFriend 'SKILL.md')
Install-File (Join-Path $ScriptDir 'claude/skills/朋友/POWERSHELL_TIPS.md')    (Join-Path $ClaudeFriend 'POWERSHELL_TIPS.md')
Install-File (Join-Path $ScriptDir 'claude/skills/朋友/scripts/friend_mailbox_claude.py') `
             (Join-Path $ClaudeFriend 'scripts/friend_mailbox_claude.py')
Install-File (Join-Path $ScriptDir 'claude/skills/朋友/scripts/surface_friend_pending.sh') `
             (Join-Path $ClaudeFriend 'scripts/surface_friend_pending.sh')
Install-File (Join-Path $ScriptDir 'claude/skills/朋友/scripts/start_friend_session.sh') `
             (Join-Path $ClaudeFriend 'scripts/start_friend_session.sh')

Write-Host '[2/7] Install Codex-side 朋友 skill'
Install-File (Join-Path $ScriptDir 'codex/skills/朋友/SKILL.md') (Join-Path $CodexFriend 'SKILL.md')

Write-Host '[3/7] Install Claude-side handoff skill'
Install-File (Join-Path $ScriptDir 'claude/skills/handoff/SKILL.md') (Join-Path $ClaudeHandoff 'SKILL.md')

Write-Host '[4/7] Install Codex-side handoff skill'
Install-File (Join-Path $ScriptDir 'codex/skills/handoff/SKILL.md')                   (Join-Path $CodexHandoff 'SKILL.md')
Install-File (Join-Path $ScriptDir 'codex/skills/handoff/agents/openai.yaml')         (Join-Path $CodexHandoff 'agents/openai.yaml')
Install-File (Join-Path $ScriptDir 'codex/skills/handoff/assets/handoff-template.md') (Join-Path $CodexHandoff 'assets/handoff-template.md')
Install-File (Join-Path $ScriptDir 'codex/skills/handoff/scripts/new_handoff.py')     (Join-Path $CodexHandoff 'scripts/new_handoff.py')

Write-Host '[5/7] Install mailbox bridge + queue'
if (-not (Test-Path $Mailbox)) {
    New-Item -ItemType Directory -Path $Mailbox -Force | Out-Null
}
Install-File (Join-Path $ScriptDir 'shared/friend/friend_mailbox_bridge.py') (Join-Path $Mailbox 'friend_mailbox_bridge.py')
Install-File (Join-Path $ScriptDir 'shared/friend/friend_queue.py')          (Join-Path $Mailbox 'friend_queue.py')

Write-Host '[6/7] Update ~/.codex/AGENTS.md (managed block, idempotent)'
$agentsDir = Split-Path -Parent $Agents
if (-not (Test-Path $agentsDir)) {
    New-Item -ItemType Directory -Path $agentsDir -Force | Out-Null
}
$snippetFile = Join-Path $ScriptDir 'codex/AGENTS.md.snippet'
if (-not (Test-Path $snippetFile)) {
    Write-Error "snippet missing: $snippetFile"
}
$snippet = Get-Content $snippetFile -Raw -Encoding utf8
$beginMark = '<!-- BEGIN friend-skill'
$endMark   = '<!-- END friend-skill -->'

if (-not (Test-Path $Agents)) {
    Set-Content -Path $Agents -Value $snippet -Encoding utf8
    Write-Host "  ✓ created $Agents with managed block"
} else {
    $existing = Get-Content $Agents -Raw -Encoding utf8
    if ($existing -match [regex]::Escape($beginMark) -and $existing -match [regex]::Escape($endMark)) {
        Backup-IfExists $Agents
        $pattern = '(?s)' + [regex]::Escape($beginMark) + '.*?' + [regex]::Escape($endMark)
        $updated = [regex]::Replace($existing, $pattern, { param($m) $snippet.TrimEnd() })
        Set-Content -Path $Agents -Value $updated -Encoding utf8
        Write-Host "  ✓ replaced managed block in $Agents"
    } else {
        Backup-IfExists $Agents
        Add-Content -Path $Agents -Value ("`n" + $snippet) -Encoding utf8
        Write-Host "  ✓ appended managed block to $Agents"
        Write-Host "  note: legacy entries (if any) left in place; remove manually if duplicated."
    }
}

Write-Host '[7/7] Verify'
$check = @(
    (Join-Path $ClaudeFriend  'SKILL.md'),
    (Join-Path $CodexFriend   'SKILL.md'),
    (Join-Path $ClaudeHandoff 'SKILL.md'),
    (Join-Path $CodexHandoff  'SKILL.md'),
    (Join-Path $Mailbox       'friend_mailbox_bridge.py'),
    $Agents
)
foreach ($f in $check) {
    if (Test-Path $f) { Write-Host "  ✓ $f" } else { Write-Host "  ✗ missing $f" }
}

@'

Done.

Next steps:
  - Bridge default mode is manual (no claude -p call). Start it:
      python ~/.shared/friend/friend_mailbox_bridge.py --watch --mailbox ~/.shared/friend
  - Auto-dispatch (requires working claude -p):
      python ~/.shared/friend/friend_mailbox_bridge.py --watch --transport claude_cli
  - Diagnose claude -p:
      python ~/.shared/friend/friend_mailbox_bridge.py --probe --transport claude_cli
  - Create a new handoff (Codex side):
      python ~/.codex/skills/handoff/scripts/new_handoff.py --project-key <slug> --title "<title>"

'@ | Write-Host
