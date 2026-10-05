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
  - VS Code icon theme: packs ports/vscode-icons plus the icons/ folder into a .vsix and installs it
    with every editor CLI it finds (code, code-insiders, cursor, codium, windsurf). Then pick one in
    "Preferences: File Icon Theme". Zed gets the icon themes with the extension itself.
  - Antigravity CLI has no theme files: keep its colorScheme on "terminal" and it uses the
    Windows Terminal (or Zed terminal) scheme.

  Zed is not handled here: install the repo folder once with "zed: install dev extension".
  Re-run this script after every build to update the copies.

.EXAMPLE
  .\install.ps1
  .\install.ps1 -Vault "D:\Notes\VaultA", "D:\Notes\VaultB"
  .\install.ps1 -Vault "D:\Notes\VaultA" -SkipTerminal
  .\install.ps1 -SkipClaudeCode -SkipOpencode -SkipIcons
#>
param(
    [string[]]$Vault = @(),
    [switch]$SkipTerminal,
    [switch]$SkipClaudeCode,
    [switch]$SkipOpencode,
    [switch]$SkipIcons
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

if (-not $SkipIcons) {
    $ext = Join-Path $root "ports\vscode-icons"
    $clis = @("code", "code-insiders", "cursor", "codium", "windsurf") | Where-Object { Get-Command $_ -ErrorAction SilentlyContinue }
    if (-not (Test-Path (Join-Path $ext "package.json"))) {
        Write-Warning "VS Code icons: ports\vscode-icons not found, run python tools/build.py first"
    } elseif (-not $clis) {
        Write-Host "VS Code icons: no code/cursor/codium command found, skipped"
    } else {
        $manifest = Get-Content (Join-Path $ext "package.json") -Raw | ConvertFrom-Json
        $stage = Join-Path ([System.IO.Path]::GetTempPath()) "$($manifest.name)-vsix"
        if (Test-Path $stage) { Remove-Item $stage -Recurse -Force }
        $inner = Join-Path $stage "extension"
        New-Item -ItemType Directory -Force -Path $inner | Out-Null
        Copy-Item (Join-Path $ext "*") $inner -Recurse -Force
        Copy-Item (Join-Path $root "icons") $inner -Recurse -Force
        $id = "$($manifest.publisher).$($manifest.name)"
        Set-Content -LiteralPath (Join-Path $stage "[Content_Types].xml") -Encoding UTF8 -Value @'
<?xml version="1.0" encoding="utf-8"?>
<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types"><Default Extension=".json" ContentType="application/json"/><Default Extension=".svg" ContentType="image/svg+xml"/><Default Extension=".vsixmanifest" ContentType="text/xml"/><Default Extension="" ContentType="application/octet-stream"/></Types>
'@
        Set-Content -LiteralPath (Join-Path $stage "extension.vsixmanifest") -Encoding UTF8 -Value @"
<?xml version="1.0" encoding="utf-8"?>
<PackageManifest Version="2.0.0" xmlns="http://schemas.microsoft.com/developer/vsx-schema/2011">
  <Metadata>
    <Identity Language="en-US" Id="$($manifest.name)" Version="$($manifest.version)" Publisher="$($manifest.publisher)"/>
    <DisplayName>$($manifest.displayName)</DisplayName>
    <Description xml:space="preserve">$($manifest.description)</Description>
    <Categories>Themes</Categories>
    <Properties><Property Id="Microsoft.VisualStudio.Code.Engine" Value="$($manifest.engines.vscode)"/></Properties>
  </Metadata>
  <Installation><InstallationTarget Id="Microsoft.VisualStudio.Code"/></Installation>
  <Dependencies/>
  <Assets><Asset Type="Microsoft.VisualStudio.Code.Manifest" Path="extension/package.json" Addressable="true"/></Assets>
</PackageManifest>
"@
        $vsix = Join-Path ([System.IO.Path]::GetTempPath()) "$($manifest.name)-$($manifest.version).vsix"
        if (Test-Path $vsix) { Remove-Item $vsix -Force }
        Add-Type -AssemblyName System.IO.Compression.FileSystem
        [System.IO.Compression.ZipFile]::CreateFromDirectory($stage, $vsix)
        foreach ($cli in $clis) {
            & $cli --install-extension $vsix --force | Out-Null
            Write-Host "VS Code icons: $id installed with $cli (pick one in 'Preferences: File Icon Theme')"
        }
        Remove-Item $stage -Recurse -Force
    }
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
