# Unyxed IDK Themes

A growing grab bag of rich, low-glare themes: Aubergine, Lagoon, Forest, Indigo Dusk, and the Clay, Mauve and Stone mid-tones.

Every theme ships for **Zed** and a long list of other apps, all generated from one file, `palettes.json`, so a color fixed there reaches every app on the next build:

- **Editors:** Zed, VS Code (also Cursor, Windsurf and the Antigravity editor), Neovim / LazyVim, Sublime Text
- **Terminals:** Windows Terminal, Ghostty, kitty, Alacritty, WezTerm
- **Command line:** Claude Code, opencode, Antigravity CLI (through the terminal scheme), bat, delta, fzf, PowerShell's typing colors
- **Browsers and web:** Chrome (also Edge and Brave), Firefox, Zen Browser, GitHub (Stylus), Discord (Vencord, Vesktop, BetterDiscord)
- **Notes:** Obsidian (via the AnuPpuccin theme)

| Family | Themes |
|---|---|
| Aubergine | Aubergine Dark, Aubergine Light |
| Lagoon | Lagoon Dark, Lagoon Light |
| Forest | Forest Dark, Forest Light |
| Indigo Dusk | Indigo Dusk Dark, Indigo Dusk Light |
| Mid Tones | Clay, Mauve, Stone |

`preview/index.html` shows every theme side by side (open it in a browser) with C++, TypeScript and Luau samples, next to Zed's Gruvbox for comparison.

## Syntax colors

Syntax highlighting follows the structure of Zed's built-in Gruvbox theme: seven hues (red, orange,
yellow, green, aqua, blue, purple) color the same kinds of tokens Gruvbox colors with them, so code
reads the way a mainstream theme reads. Keywords are red, functions and strings green, types and
constants yellow, numbers purple, operators aqua, attributes and namespaces blue; variables and
properties stay in the plain text color. The hues themselves are each theme's own calm colors,
and the build enforces a minimum CIELAB difference (delta E 25) between them and the text color.
It works in any language, including third-party grammars, because it only uses Zed's common
capture names.

A theme still being moved to this structure is marked "pending" in the preview.

## Install

Build first (`python tools/build.py`, needs Python 3.9+). Then, in PowerShell from this folder:

```powershell
.\install.ps1 -Vault "D:\path\to\Vault"
```

It installs every port whose app it finds on the PC (Windows Terminal, Claude Code, opencode, VS Code and
its forks, Neovim, Alacritty, WezTerm, bat, Discord clients, Obsidian) and skips the rest. Skip some with
`-Skip VSCode, Neovim`. If PowerShell refuses to run it:
`powershell -ExecutionPolicy Bypass -File .\install.ps1`.

Then pick a theme in each app:

| App | Files | Pick a theme |
|---|---|---|
| **Zed** | `themes/` | Once: command palette, `zed: install dev extension`, this folder. Then Ctrl+K Ctrl+T. |
| **Windows Terminal** | `ports/windows-terminal/` | Restart it, then Settings > Profiles > Defaults > Appearance > Color scheme. |
| **VS Code**, Cursor, Windsurf, Antigravity | `ports/vscode/unyxed-idk-theme.vsix` | install.ps1 installs it with each editor's command line; or Extensions view > `...` > Install from VSIX. Then Ctrl+K Ctrl+T. |
| **Neovim / LazyVim** | `colors/`, `lua/lualine/themes/` | install.ps1 copies them into your Neovim config. In LazyVim set `{ "LazyVim/LazyVim", opts = { colorscheme = "aubergine-dark" } }`. Or skip the copy and load this repo as a plugin: `{ dir = "D:/path/to/unyxed-idk-theme", lazy = false, priority = 1000 }`. |
| **Ghostty** | `ports/ghostty/` | Copy into `~/.config/ghostty/themes/`, then `theme = light:Aubergine Light,dark:Aubergine Dark`. |
| **kitty** | `ports/kitty/` | Copy into `~/.config/kitty/themes/`, then `kitten themes` (or `include themes/aubergine-dark.conf`). |
| **Alacritty** | `ports/alacritty/` | install.ps1 copies to `%APPDATA%\alacritty\themes\`. In `alacritty.toml`: `[general]` `import = ["~/AppData/Roaming/alacritty/themes/aubergine-dark.toml"]`. |
| **WezTerm** | `ports/wezterm/` | install.ps1 copies to `~/.config/wezterm/colors/`. In `.wezterm.lua`: `config.color_scheme = "Aubergine Dark"`. |
| **Claude Code** | `ports/claude-code/` | `/theme`. Use the same scheme in the terminal: Claude Code draws on the terminal's background. |
| **opencode** | `ports/opencode/` | `/theme`. |
| **Antigravity CLI** | (none) | Keep `colorScheme` on `"terminal"` (the default, or `/config`): it uses the terminal scheme. |
| **bat** | `ports/tmtheme/` | install.ps1 copies them and runs `bat cache --build`. Then `bat --theme="Aubergine Dark"`, or `--theme="Aubergine Dark"` in bat's config file. |
| **delta** | `ports/delta/` | Needs the bat themes above. In `~/.gitconfig`: `[include]` `path = D:/path/to/unyxed-idk-theme/ports/delta/unyxed-idk-theme.gitconfig`, then `[delta]` `features = aubergine-dark`. |
| **Sublime Text** | `ports/tmtheme/` | Copy into `Packages/User/`, then `"color_scheme": "Aubergine Dark.tmTheme"`. |
| **fzf** | `ports/fzf/` | In `$PROFILE`: `$env:UNYXED_THEME = "aubergine-dark"; . "D:\path\to\unyxed-idk-theme\ports\fzf\fzf.ps1"` (bash/zsh: `fzf.sh`). |
| **PowerShell** | `ports/powershell/` | In `$PROFILE`: `. "D:\path\to\unyxed-idk-theme\ports\powershell\aubergine-dark.ps1"`. Colors what you type (PSReadLine). |
| **Chrome**, Edge, Brave | `ports/chrome/<theme>/` | `chrome://extensions`, turn on Developer mode, Load unpacked, pick the theme's folder. |
| **Firefox** | `ports/firefox/` | See "Firefox" below. |
| **Zen Browser** | `ports/zen/<family>/` | `.\install.ps1 -ZenTheme aubergine` copies it into your Zen profiles. Then `about:config`, set `toolkit.legacyUserProfileCustomizations.stylesheets` to true, restart. Follows Zen's light/dark mode. |
| **GitHub** | `ports/github/` | Install the Stylus extension, then Stylus > Manage > Write new style, paste one `.user.css` file and save. Follows GitHub's light/dark setting. |
| **Discord** | `ports/discord/` | install.ps1 copies them for Vencord, Vesktop and BetterDiscord. Turn one on in Settings > Themes. Follows Discord's light/dark setting. |
| **Obsidian** | `ports/obsidian/` | Install AnuPpuccin, then Settings > Appearance > CSS snippets, enable **one** `unyxed-idk-theme-*.css`. Leave AnuPpuccin's custom color fields in Style Settings empty. |

Zed can follow the system light/dark mode:

```json
"theme": { "mode": "system", "light": "Aubergine Light", "dark": "Aubergine Dark" }
```

### Firefox

Release Firefox only keeps add-ons that Mozilla has signed, so a theme file from this repo needs one of:

- **Try it:** `about:debugging` > This Firefox > Load Temporary Add-on, pick `ports/firefox/<theme>.xpi`.
  It stays until Firefox restarts.
- **Keep it:** sign it once for free at addons.mozilla.org (Submit a New Add-on > "On your own"), upload
  the `.xpi`, and install the signed file Mozilla gives back. Nothing is published.
- Firefox Developer Edition, Nightly and ESR can set `xpinstall.signatures.required` to false in
  `about:config` and install the `.xpi` directly.

The `.vsix` and `.xpi` files are built by `python tools/build.py` and are not committed.

## Recommended terminal settings

Every terminal color in these themes is readable on its background (the build enforces at least
4.5:1 for all 16 ANSI colors and 3.5:1 for the dim ones). But a theme can only control those 16
colors. Programs that print 256-color or RGB values pick their own colors and can still land on
something unreadable. These settings are the safety net:

**Zed** (`settings.json`). The default is 45, which Zed documents as the floor for large text only:

```json
"terminal": { "minimum_contrast": 75 }
```

**Windows Terminal** (`settings.json`, under `profiles.defaults`):

```json
"adjustIndistinguishableColors": "always"
```

## Update after a change

```powershell
git pull
python tools/build.py
.\install.ps1 -Vault "D:\path\to\Vault"
```

Zed picks up the rebuilt files from the folder; if a change does not show, reinstall the dev extension.

## Maintaining

Agents (Claude Code, opencode, etc.) maintain this repo; see `AGENTS.md`. Short version:
edit `palettes.json`, run `python tools/build.py`, commit everything.
Requires Python 3.9+ (no packages).

## Before publishing to the Zed extension store

Set the real `repository` URL in `extension.toml`, add a LICENSE file and screenshots, bump `version`.
