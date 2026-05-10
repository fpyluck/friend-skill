# friend-skill installer (PowerShell)
# Idempotent; backs up existing files; updates AGENTS.md via managed block.

[CmdletBinding()]
param()

$ErrorActionPreference = 'Stop'
$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$Timestamp = Get-Date -Format 'yyyyMMdd_HHmmss'

$ClaudeSkills = Join-Path $HOME '.claude/skills'
$CodexSkills  = Join-Path $HOME '.codex/skills'
$ClaudeFriend = Join-Path $ClaudeSkills 'friend'
$ClaudeHandoff = Join-Path $ClaudeSkills 'handoff'
$ClaudeHelper = Join-Path $ClaudeSkills 'helper'
$CodexFriend  = Join-Path $CodexSkills 'friend'
$CodexHandoff = Join-Path $CodexSkills 'handoff'
$CodexHelper  = Join-Path $CodexSkills 'helper'
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

function Install-Tree {
    param([string]$SrcDir, [string]$DstDir)
    if (-not (Test-Path $SrcDir)) {
        Write-Error "source dir missing: $SrcDir"
    }
    $srcRoot = (Resolve-Path $SrcDir).Path.TrimEnd('\', '/')
    Get-ChildItem -Path $SrcDir -File -Recurse |
        Where-Object { $_.FullName -notmatch '[\\/]+__pycache__[\\/]' -and $_.Name -notlike '*.pyc' } |
        ForEach-Object {
            $rel = $_.FullName.Substring($srcRoot.Length).TrimStart('\', '/')
            Install-File $_.FullName (Join-Path $DstDir $rel)
        }
}

Write-Host '[1/5] Install Claude-side skills'
Install-Tree (Join-Path $ScriptDir 'claude/skills/friend')  $ClaudeFriend
Install-Tree (Join-Path $ScriptDir 'claude/skills/handoff') $ClaudeHandoff
Install-Tree (Join-Path $ScriptDir 'claude/skills/helper')  $ClaudeHelper

Write-Host '[2/5] Install Codex-side skills'
Install-Tree (Join-Path $ScriptDir 'codex/skills/friend')  $CodexFriend
Install-Tree (Join-Path $ScriptDir 'codex/skills/handoff') $CodexHandoff
Install-Tree (Join-Path $ScriptDir 'codex/skills/helper')  $CodexHelper

Write-Host '[3/5] Install shared friend runtime'
if (-not (Test-Path $Mailbox)) {
    New-Item -ItemType Directory -Path $Mailbox -Force | Out-Null
}
Install-Tree (Join-Path $ScriptDir 'shared/friend') $Mailbox

Write-Host '[4/5] Update ~/.codex/AGENTS.md (managed block, idempotent)'
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

Write-Host '[5/5] Verify'
$check = @(
    (Join-Path $ClaudeFriend 'SKILL.md'),
    (Join-Path $ClaudeHandoff 'SKILL.md'),
    (Join-Path $ClaudeHelper 'SKILL.md'),
    (Join-Path $CodexFriend  'SKILL.md'),
    (Join-Path $CodexHandoff 'SKILL.md'),
    (Join-Path $CodexHelper 'SKILL.md'),
    (Join-Path $Mailbox      'friend_gate.py'),
    (Join-Path $Mailbox      'friend_mailbox_bridge.py'),
    (Join-Path $Mailbox      'friend_queue.py'),
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

'@ | Write-Host
