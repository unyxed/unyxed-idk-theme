<#
.SYNOPSIS
  Installs this package's Windows Terminal schemes, Claude Code and opencode themes, and
  Obsidian (AnuPpuccin) snippets.

.DESCRIPTION
  - Windows Terminal: copies ports/windows-terminal/*.json into
    %LOCALAPPDATA%\Microsoft\Windows Terminal\Fragments\<package-id>\
    Restart Windows Terminal, then pick a scheme in Settings > Profiles > Appearance.
  - Obsidian: copies ports/obsidian/*.css into <vault>\.obsidian\snippets\ for every
    vault passed with -Vault. Then enable ONE snippet in Settings > Appearance > CSS snippets.
  - Claude Code: copies ports/claude-code/*.json into ~\.claude\themes\. Pick one with /theme.
    Use it with the matching Windows Terminal scheme: Claude Code draws on the terminal background.
  - opencode: copies ports/opencode/*.json into ~\.config\opencode\themes\. Pick one with /theme.
  - Antigravity CLI has no theme files: keep its colorScheme on "terminal" and it uses the
    Windows Terminal (or Zed terminal) scheme.

  Zed is not handled here: install the repo folder once with "zed: install dev extension".
  Re-run this script after every build to update the copies.

.EXAMPLE
  .\install.ps1
  .\install.ps1 -Vault "D:\Notes\VaultA", "D:\Notes\VaultB"
  .\install.ps1 -Vault "D:\Notes\VaultA" -SkipTerminal
  .\install.ps1 -SkipClaudeCode -SkipOpencode
#>
param(
    [string[]]$Vault = @(),
    [switch]$SkipTerminal,
    [switch]$SkipClaudeCode,
    [switch]$SkipOpencode
)

$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $MyInvocation.MyCommand.Path
$pkg = (Get-Content (Join-Path $root "palettes.json") -Raw | ConvertFrom-Json).package

if (-not $SkipTerminal) {
    $dest = Join-Path $env:LOCALAPPDATA "Microsoft\Windows Terminal\Fragments\$($pkg.id)"
    New-Item -ItemType Directory -Force -Path $dest | Out-Null
    Copy-Item (Join-Path $root "ports\windows-terminal\*.json") $dest -Force
    Write-Host "Windows Terminal: schemes installed to $dest (restart Terminal to load them)"
}

function Copy-Themes($port, $dest, $label) {
    $src = Join-Path $root "ports\$port\*.json"
    if (-not (Test-Path $src)) { return }
    New-Item -ItemType Directory -Force -Path $dest | Out-Null
    Copy-Item $src $dest -Force
    Write-Host "$($label): themes copied to $dest (choose one with /theme)"
}
if (-not $SkipClaudeCode) {
    Copy-Themes "claude-code" (Join-Path $HOME ".claude\themes") "Claude Code"
}
if (-not $SkipOpencode) {
    $cfg = if ($env:XDG_CONFIG_HOME) { $env:XDG_CONFIG_HOME } else { Join-Path $HOME ".config" }
    Copy-Themes "opencode" (Join-Path $cfg "opencode\themes") "opencode"
}

foreach ($v in $Vault) {
    if (-not (Test-Path (Join-Path $v ".obsidian"))) {
        Write-Warning "Skipping '$v': no .obsidian folder found, is this a vault?"
        continue
    }
    $snip = Join-Path $v ".obsidian\snippets"
    New-Item -ItemType Directory -Force -Path $snip | Out-Null
    Copy-Item (Join-Path $root "ports\obsidian\*.css") $snip -Force
    Write-Host "Obsidian: snippets copied to $snip"
}

if ($Vault.Count -eq 0) {
    Write-Host "Obsidian: no -Vault given, skipped. Example: .\install.ps1 -Vault 'D:\Notes\MyVault'"
}
