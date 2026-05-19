# friend-skill installer (PowerShell)
# Installs: friend, xiongdimen, helper, handoff for Claude Code and Codex;
#           xiongdimen for Gemini; shared friend runtime.
# Idempotent; backs up existing files; updates AGENTS.md via managed block.

[CmdletBinding()]
param()

$ErrorActionPreference = 'Stop'
$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$Timestamp = Get-Date -Format 'yyyyMMdd_HHmmss'

$ClaudeSkills  = Join-Path $HOME '.claude/skills'
$CodexSkills   = Join-Path $HOME '.codex/skills'
$GeminiSkills  = Join-Path $HOME '.gemini/skills'
$Mailbox       = Join-Path $HOME '.shared/friend'
$Agents        = Join-Path $HOME '.codex/AGENTS.md'

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
    Write-Host "  v $Dst"
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

Write-Host '[1/6] Install Claude-side skills'
Install-Tree (Join-Path $ScriptDir 'claude/skills/friend')     (Join-Path $ClaudeSkills 'friend')
Install-Tree (Join-Path $ScriptDir 'claude/skills/xiongdimen') (Join-Path $ClaudeSkills 'xiongdimen')
Install-Tree (Join-Path $ScriptDir 'claude/skills/helper')     (Join-Path $ClaudeSkills 'helper')
Install-Tree (Join-Path $ScriptDir 'claude/skills/handoff')    (Join-Path $ClaudeSkills 'handoff')

Write-Host '[2/6] Install Codex-side skills'
Install-Tree (Join-Path $ScriptDir 'codex/skills/friend')     (Join-Path $CodexSkills 'friend')
Install-Tree (Join-Path $ScriptDir 'codex/skills/xiongdimen') (Join-Path $CodexSkills 'xiongdimen')
Install-Tree (Join-Path $ScriptDir 'codex/skills/helper')     (Join-Path $CodexSkills 'helper')
Install-Tree (Join-Path $ScriptDir 'codex/skills/handoff')    (Join-Path $CodexSkills 'handoff')

Write-Host '[3/6] Install Gemini-side skills'
Install-Tree (Join-Path $ScriptDir 'gemini/skills/xiongdimen') (Join-Path $GeminiSkills 'xiongdimen')

Write-Host '[4/6] Install shared friend runtime'
if (-not (Test-Path $Mailbox)) {
    New-Item -ItemType Directory -Path $Mailbox -Force | Out-Null
}
Install-Tree (Join-Path $ScriptDir 'shared/friend') $Mailbox

Write-Host '[5/6] Update ~/.codex/AGENTS.md (managed block, idempotent)'
$agentsDir = Split-Path -Parent $Agents
if (-not (Test-Path $agentsDir)) {
    New-Item -ItemType Directory -Path $agentsDir -Force | Out-Null
}
$snippetFile = Join-Path $ScriptDir 'codex/AGENTS.md.snippet'
if (-not (Test-Path $snippetFile)) {
    Write-Error "snippet missing: $snippetFile"
}
$snippet   = Get-Content $snippetFile -Raw -Encoding utf8
$beginMark = '<!-- BEGIN friend-skill'
$endMark   = '<!-- END friend-skill -->'

if (-not (Test-Path $Agents)) {
    Set-Content -Path $Agents -Value $snippet -Encoding utf8
    Write-Host "  v created $Agents with managed block"
} else {
    $existing = Get-Content $Agents -Raw -Encoding utf8
    if ($existing -match [regex]::Escape($beginMark) -and $existing -match [regex]::Escape($endMark)) {
        Backup-IfExists $Agents
        $pattern = '(?s)' + [regex]::Escape($beginMark) + '.*?' + [regex]::Escape($endMark)
        $updated = [regex]::Replace($existing, $pattern, { param($m) $snippet.TrimEnd() })
        Set-Content -Path $Agents -Value $updated -Encoding utf8
        Write-Host "  v replaced managed block in $Agents"
    } elseif ($existing -match '(?m)^## 朋友 skill — 与 Claude Code 协商$') {
        Backup-IfExists $Agents
        $pattern = '(?ms)^## 朋友 skill — 与 Claude Code 协商.*?(?=^## |\z)'
        $updated = [regex]::Replace($existing, $pattern, { param($m) $snippet.TrimEnd() + "`n" }, 1)
        Set-Content -Path $Agents -Value $updated -Encoding utf8
        Write-Host "  v replaced legacy friend section in $Agents"
    } else {
        Backup-IfExists $Agents
        Add-Content -Path $Agents -Value ("`n" + $snippet) -Encoding utf8
        Write-Host "  v appended managed block to $Agents"
        Write-Host "  note: legacy entries (if any) left in place; remove manually if duplicated."
    }
}

Write-Host '[6/6] Verify'
$check = @(
    (Join-Path $ClaudeSkills  'friend/SKILL.md'),
    (Join-Path $ClaudeSkills  'xiongdimen/SKILL.md'),
    (Join-Path $ClaudeSkills  'helper/SKILL.md'),
    (Join-Path $ClaudeSkills  'handoff/SKILL.md'),
    (Join-Path $CodexSkills   'friend/SKILL.md'),
    (Join-Path $CodexSkills   'xiongdimen/SKILL.md'),
    (Join-Path $CodexSkills   'helper/SKILL.md'),
    (Join-Path $CodexSkills   'handoff/SKILL.md'),
    (Join-Path $GeminiSkills  'xiongdimen/SKILL.md'),
    (Join-Path $Mailbox       'friend_discovery.py'),
    (Join-Path $Mailbox       'friend_gate.py'),
    (Join-Path $Mailbox       'friend_mailbox_bridge.py'),
    (Join-Path $Mailbox       'friend_queue.py'),
    $Agents
)
foreach ($f in $check) {
    if (Test-Path $f) { Write-Host "  v $f" } else { Write-Host "  x missing $f" }
}

@'

Done. Four skills installed: friend / xiongdimen / helper / handoff

Next steps:
  - Bridge default mode is manual (no claude -p call). Start it:
      python ~/.shared/friend/friend_mailbox_bridge.py --watch
  - Auto-dispatch (requires working claude -p):
      python ~/.shared/friend/friend_mailbox_bridge.py --watch --transport claude_cli
  - Gemini runner requires Gemini CLI in PATH:
      npm install -g @google/gemini-cli
  - Diagnose claude -p:
      python ~/.shared/friend/friend_mailbox_bridge.py --probe --transport claude_cli

'@ | Write-Host
