# Unyxed IDK Themes

A growing grab bag of rich, low-glare themes: Aubergine, Lagoon, Forest, Indigo Dusk, and the Clay, Mauve and Stone mid-tones.

Every theme ships for **Zed**, **Windows Terminal**, **Claude Code**, **opencode** and **Obsidian**
(via the AnuPpuccin theme), and works in **Antigravity CLI** through the terminal scheme,
all generated from one file: `palettes.json`.

| Family | Themes |
|---|---|
| Aubergine | Aubergine Dark, Aubergine Light |
| Lagoon | Lagoon Dark, Lagoon Light |
| Forest | Forest Dark, Forest Light |
| Indigo Dusk | Indigo Dusk Dark, Indigo Dusk Light |
| Mid Tones | Clay, Mauve, Stone |

## Syntax colors

Nine syntax hues, spread around the color wheel with matched lightness so tokens are easy to tell apart
but the theme stays calm: declaration keywords, control flow, imports and preprocessor, strings, functions,
numbers, types, properties and operators each get their own color. The build enforces a minimum CIELAB
difference (delta E 25) between them. It works in any language: grammars that emit only plain `keyword`
(for example Luau) simply show one keyword color.

## Install

**Zed** (once): command palette, `zed: install dev extension`, select this repo folder.
Pick a theme with Ctrl+K, Ctrl+T. To follow the system light/dark mode:

```json
"theme": { "mode": "system", "light": "<Light theme name>", "dark": "<Dark theme name>" }
```

**Windows Terminal and Obsidian** (PowerShell, from this folder):

```powershell
.\install.ps1 -Vault "D:\path\to\Vault"
```

- Windows Terminal: restart it, then Settings > Profiles > Defaults (or a profile) > Appearance > Color scheme.
- Claude Code: themes go to `~/.claude/themes/`; pick one with `/theme`. Use it together with the same
  scheme in Windows Terminal: Claude Code draws on the terminal's background.
- opencode: themes go to `~/.config/opencode/themes/`; pick one with `/theme`.
- Antigravity CLI: nothing to install. Keep `colorScheme` on `"terminal"` (the default, or `/config`)
  and it uses the Windows Terminal scheme.
- Obsidian: install the AnuPpuccin theme, then Settings > Appearance > CSS snippets, and enable **one**
  `unyxed-idk-theme-*.css` snippet. Leave AnuPpuccin's custom color fields in Style Settings empty, or they override the snippet.
  Any AnuPpuccin flavor works as the base; Mocha (dark) and Latte (light) are good defaults.

If PowerShell refuses to run the script: `powershell -ExecutionPolicy Bypass -File .\install.ps1 -Vault "..."`.

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
