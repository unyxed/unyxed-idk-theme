<#
.SYNOPSIS
  Copies this package's generated ports into the apps installed on this PC.

.DESCRIPTION
  Run it after every build. Each port is only installed when its app is found, so it is safe to
  run on any machine. Browser themes, GitHub and Discord's Vencord Quick CSS need one click in the
  app itself: see README.md.

  - Windows Terminal: ports/windows-terminal/*.json into
    %LOCALAPPDATA%\Microsoft\Windows Terminal\Fragments\<package-id>\  (restart Terminal)
  - Claude Code: ports/claude-code/*.json into ~\.claude\themes\  (pick one with /theme)
  - opencode: ports/opencode/*.json into ~\.config\opencode\themes\  (pick one with /theme)
  - VS Code, VS Code Insiders, Cursor, VSCodium, Windsurf, Antigravity: installs
    ports/vscode/<package-id>.vsix with each editor's command-line tool that is on PATH (pick a
    theme with Ctrl+K Ctrl+T)
  - VS Code icon themes: packs ports/vscode-icons plus the icons/ folder into a .vsix and installs it
    the same way (pick one in "Preferences: File Icon Theme"). Zed gets the icon themes with the
    extension itself.
  - Neovim / LazyVim: colors/*.lua and lua/lualine/themes/*.lua into %LOCALAPPDATA%\nvim\
  - Alacritty: ports/alacritty/*.toml into %APPDATA%\alacritty\themes\
  - WezTerm: ports/wezterm/*.toml into ~\.config\wezterm\colors\
  - bat (and delta, which uses bat's themes): ports/tmtheme/*.tmTheme into bat's themes folder,
    then rebuilds bat's cache
  - Discord: ports/discord/*.theme.css into the Vencord, Vesktop and BetterDiscord themes folders
  - Zen Browser: only with -ZenTheme <name>, copies ports/zen/<name>/userChrome.css and
    userContent.css into every Zen profile's chrome folder (existing files are kept as .bak)
  - Obsidian: ports/obsidian/*.css into <vault>\.obsidian\snippets\ for every -Vault
  - Antigravity CLI has no theme files: keep its colorScheme on "terminal" and it uses the
    Windows Terminal scheme.

  Zed is not handled here: install the repo folder once with "zed: install dev extension".

.EXAMPLE
  .\install.ps1
  .\install.ps1 -Vault "D:\Notes\VaultA", "D:\Notes\VaultB"
  .\install.ps1 -ZenTheme cocoa-rose
  .\install.ps1 -Skip VSCode, Neovim
  .\install.ps1 -SkipIcons
#>
param(
    [string[]]$Vault = @(),
    [string]$ZenTheme = "",
    # any of: Terminal, ClaudeCode, Opencode, VSCode, Icons, Neovim, Alacritty, WezTerm, Bat, Discord
    [string[]]$Skip = @(),
    # older switches, still accepted
    [switch]$SkipTerminal,
    [switch]$SkipClaudeCode,
    [switch]$SkipOpencode,
    [switch]$SkipIcons
)

$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $MyInvocation.MyCommand.Path
$pkg = (Get-Content (Join-Path $root "palettes.json") -Raw | ConvertFrom-Json).package
if ($SkipTerminal) { $Skip += "Terminal" }
if ($SkipClaudeCode) { $Skip += "ClaudeCode" }
if ($SkipOpencode) { $Skip += "Opencode" }
if ($SkipIcons) { $Skip += "Icons" }
$cfg = if ($env:XDG_CONFIG_HOME) { $env:XDG_CONFIG_HOME } else { Join-Path $HOME ".config" }
$appData = if ($env:APPDATA) { $env:APPDATA } else { $cfg }
$localAppData = if ($env:LOCALAPPDATA) { $env:LOCALAPPDATA } else { $cfg }

function Want($name) { return -not ($Skip -contains $name) }
function Has($command) { return [bool](Get-Command $command -ErrorAction SilentlyContinue) }

# Copies files matching $pattern from ports into $dest. Returns $false when there is nothing to copy.
function Copy-Port($pattern, $dest, $label) {
    $src = Join-Path $root $pattern
    if (-not (Test-Path $src)) { return $false }
    New-Item -ItemType Directory -Force -Path $dest | Out-Null
    Copy-Item $src $dest -Force
    Write-Host "$($label): copied to $dest"
    return $true
}

if (Want "Terminal") {
    $dest = Join-Path $localAppData "Microsoft\Windows Terminal\Fragments\$($pkg.id)"
    if (Copy-Port "ports\windows-terminal\*.json" $dest "Windows Terminal") {
        Write-Host "  restart Windows Terminal, then pick a scheme in Settings > Profiles > Appearance"
    }
}
if (Want "ClaudeCode") {
    Copy-Port "ports\claude-code\*.json" (Join-Path $HOME ".claude\themes") "Claude Code (choose one with /theme)" | Out-Null
}
if (Want "Opencode") {
    Copy-Port "ports\opencode\*.json" (Join-Path $cfg "opencode\themes") "opencode (choose one with /theme)" | Out-Null
}

if (Want "VSCode") {
    $vsix = Join-Path $root "ports\vscode\$($pkg.id).vsix"
    if (-not (Test-Path $vsix)) {
        Write-Warning "VS Code: $vsix is missing. Run 'python tools/build.py' first."
    } else {
        $found = $false
        foreach ($cli in "code", "code-insiders", "cursor", "codium", "windsurf", "antigravity") {
            if (Has $cli) {
                & $cli --install-extension $vsix --force | Out-Null
                Write-Host "$($cli): extension installed (pick a theme with Ctrl+K Ctrl+T)"
                $found = $true
            }
        }
        if (-not $found) { Write-Host "VS Code: no editor command found on PATH, skipped" }
    }
}

if (Want "Icons") {
    $ext = Join-Path $root "ports\vscode-icons"
    $clis = @("code", "code-insiders", "cursor", "codium", "windsurf", "antigravity") | Where-Object { Get-Command $_ -ErrorAction SilentlyContinue }
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

if (Want "Neovim") {
    $nvim = Join-Path $localAppData "nvim"
    if ((Test-Path $nvim) -or (Has "nvim")) {
        Copy-Port "colors\*.lua" (Join-Path $nvim "colors") "Neovim colorschemes" | Out-Null
        Copy-Port "lua\lualine\themes\*.lua" (Join-Path $nvim "lua\lualine\themes") "Neovim lualine themes" | Out-Null
    }
}

if ((Want "Alacritty") -and ((Has "alacritty") -or (Test-Path (Join-Path $appData "alacritty")))) {
    Copy-Port "ports\alacritty\*.toml" (Join-Path $appData "alacritty\themes") "Alacritty" | Out-Null
}
if ((Want "WezTerm") -and ((Has "wezterm") -or (Test-Path (Join-Path $cfg "wezterm")))) {
    Copy-Port "ports\wezterm\*.toml" (Join-Path $cfg "wezterm\colors") "WezTerm" | Out-Null
}

if ((Want "Bat") -and (Has "bat")) {
    $batThemes = Join-Path (& bat --config-dir) "themes"
    if (Copy-Port "ports\tmtheme\*.tmTheme" $batThemes "bat") {
        & bat cache --build | Out-Null
        Write-Host "  bat cache rebuilt; delta uses the same themes"
    }
}

if (Want "Discord") {
    foreach ($client in "Vencord", "vesktop", "BetterDiscord") {
        $dir = Join-Path $appData $client
        if (Test-Path $dir) {
            Copy-Port "ports\discord\*.theme.css" (Join-Path $dir "themes") "Discord ($client)" | Out-Null
        }
    }
}

if ($ZenTheme) {
    $src = Join-Path $root "ports\zen\$ZenTheme"
    $profiles = Join-Path $appData "zen\Profiles"
    if (-not (Test-Path $src)) {
        Write-Warning "Zen: no theme '$ZenTheme'. Choose one of: $((Get-ChildItem (Join-Path $root 'ports\zen') -Directory).Name -join ', ')"
    } elseif (-not (Test-Path $profiles)) {
        Write-Warning "Zen: no profiles found in $profiles"
    } else {
        foreach ($p in Get-ChildItem $profiles -Directory) {
            $chrome = Join-Path $p.FullName "chrome"
            New-Item -ItemType Directory -Force -Path $chrome | Out-Null
            foreach ($f in "userChrome.css", "userContent.css") {
                $dest = Join-Path $chrome $f
                if ((Test-Path $dest) -and -not (Test-Path "$dest.bak")) { Copy-Item $dest "$dest.bak" }
                Copy-Item (Join-Path $src $f) $dest -Force
            }
            Write-Host "Zen: $ZenTheme installed in $chrome"
        }
        Write-Host "  enable toolkit.legacyUserProfileCustomizations.stylesheets in about:config, then restart Zen"
    }
}

foreach ($v in $Vault) {
    if (-not (Test-Path (Join-Path $v ".obsidian"))) {
        Write-Warning "Skipping '$v': no .obsidian folder found, is this a vault?"
        continue
    }
    Copy-Port "ports\obsidian\*.css" (Join-Path $v ".obsidian\snippets") "Obsidian" | Out-Null
}
if ($Vault.Count -eq 0) {
    Write-Host "Obsidian: no -Vault given, skipped. Example: .\install.ps1 -Vault 'D:\Notes\MyVault'"
}
