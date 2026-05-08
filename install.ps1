# 朋友 skill installer (PowerShell 5.1+)
# Installs to ~/.claude/skills/朋友/, ~/.codex/skills/朋友/, ~/.shared/friend/

$ErrorActionPreference = 'Stop'

$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$Timestamp = Get-Date -Format 'yyyyMMdd_HHmmss'

$ClaudeDst = Join-Path $HOME '.claude\skills\朋友\SKILL.md'
$CodexDst  = Join-Path $HOME '.codex\skills\朋友\SKILL.md'
$AgentsFile = Join-Path $HOME '.codex\AGENTS.md'
$MailboxDir = Join-Path $HOME '.shared\friend'

$ClaudeSrc = Join-Path $ScriptDir 'claude\skills\朋友\SKILL.md'
$CodexSrc  = Join-Path $ScriptDir 'codex\skills\朋友\SKILL.md'
$Snippet   = Join-Path $ScriptDir 'codex\AGENTS.md.snippet'

function Backup-IfExists {
  param([string]$Path)
  if (Test-Path -LiteralPath $Path) {
    $bak = "$Path.bak.$Timestamp"
    Copy-Item -LiteralPath $Path -Destination $bak -Force
    Write-Host "  备份已存在文件 → $bak"
  }
}

function Install-Skill {
  param([string]$Src, [string]$Dst, [string]$Label)
  Write-Host $Label
  if (-not (Test-Path -LiteralPath $Src)) {
    Write-Error "  ✗ 源文件缺失：$Src"
    return
  }
  $dir = Split-Path -Parent $Dst
  New-Item -ItemType Directory -Force -Path $dir | Out-Null
  Backup-IfExists -Path $Dst
  Copy-Item -LiteralPath $Src -Destination $Dst -Force
  Write-Host "  ✓ 已安装 → $Dst"
}

Install-Skill -Src $ClaudeSrc -Dst $ClaudeDst -Label '[1/4] 安装 Claude 端 skill'
Install-Skill -Src $CodexSrc  -Dst $CodexDst  -Label '[2/4] 安装 Codex 端 skill'

Write-Host '[3/4] 追加全局指针到 ~/.codex/AGENTS.md'
New-Item -ItemType Directory -Force -Path (Split-Path -Parent $AgentsFile) | Out-Null
$alreadyHas = $false
if (Test-Path -LiteralPath $AgentsFile) {
  $content = [System.IO.File]::ReadAllText($AgentsFile, [System.Text.Encoding]::UTF8)
  if ($content -match '朋友 skill') { $alreadyHas = $true }
}
if ($alreadyHas) {
  Write-Host '  ✓ AGENTS.md 已包含朋友指针，跳过'
} else {
  if (Test-Path -LiteralPath $Snippet) {
    $snippetText = [System.IO.File]::ReadAllText($Snippet, [System.Text.Encoding]::UTF8)
    $existing = if (Test-Path -LiteralPath $AgentsFile) {
      [System.IO.File]::ReadAllText($AgentsFile, [System.Text.Encoding]::UTF8)
    } else { '' }
    $combined = if ($existing) { "$existing`n$snippetText" } else { $snippetText }
    [System.IO.File]::WriteAllText($AgentsFile, $combined, [System.Text.UTF8Encoding]::new($false))
    Write-Host '  ✓ 已追加'
  } else {
    Write-Error "  ✗ snippet 文件缺失：$Snippet"
  }
}

Write-Host '[4/4] 创建邮箱目录 ~/.shared/friend/'
New-Item -ItemType Directory -Force -Path $MailboxDir | Out-Null
Write-Host "  ✓ $MailboxDir"

Write-Host ''
Write-Host '安装完成。验证：'
Write-Host '  - 在 Claude Code 输入 /朋友 应见到此 skill'
Write-Host '  - 在 Codex 启动时 ~/.codex/AGENTS.md 会被读取'
Write-Host "  - 邮箱目录就绪：$MailboxDir"
