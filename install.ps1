<#
.SYNOPSIS
  Installs this package's Windows Terminal schemes and Obsidian (AnuPpuccin) snippets.

.DESCRIPTION
  - Windows Terminal: copies ports/windows-terminal/*.json into
    %LOCALAPPDATA%\Microsoft\Windows Terminal\Fragments\<package-id>\
    Restart Windows Terminal, then pick a scheme in Settings > Profiles > Appearance.
  - Obsidian: copies ports/obsidian/*.css into <vault>\.obsidian\snippets\ for every
    vault passed with -Vault. Then enable ONE snippet in Settings > Appearance > CSS snippets.

  Zed is not handled here: install the repo folder once with "zed: install dev extension".
  Re-run this script after every build to update the copies.

.EXAMPLE
  .\install.ps1
  .\install.ps1 -Vault "D:\Notes\VaultA", "D:\Notes\VaultB"
  .\install.ps1 -Vault "D:\Notes\VaultA" -SkipTerminal
#>
param(
    [string[]]$Vault = @(),
    [switch]$SkipTerminal
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
