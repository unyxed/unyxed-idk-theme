# AGENTS.md: Unyxed IDK Themes

Instructions for any coding agent (Claude Code, opencode, Codex, etc.) working in this repo.

## Context

- The owner uses these themes daily and relies on agents to design and maintain them. They are not a
  theme designer. Everything must work out of the box: no missing UI colors, no syntax bugs.
- This repo produces one Zed theme extension plus ports for Windows Terminal and Obsidian (AnuPpuccin).
- Sibling repo: `unyxed-cocoa-theme`. Both repos use the **same** `tools/`, `install.ps1` and `reference/`.
  If you change any of those here, make the identical change there.

## Golden rules

1. `palettes.json` is the only source of truth. Never hand-edit `themes/`, `ports/` or `preview/`:
   they are regenerated and your edits will be lost.
2. After any change run `python tools/build.py`. It must finish with no errors. Treat warnings as
   bugs to fix unless you can explain them to the owner.
3. Never lower the contrast rules to get a build through. Fix the colors (`--fix` or by hand).
4. Commit the source and the generated output together. CI fails if generated files are stale.
5. When a change affects how a theme looks, tell the owner what changed and why, in plain words.

## Layout

```
palettes.json            source of truth: package info, rules, families, variants, colors
tools/build.py           generator and validator (no dependencies)
tools/sync_zed_reference.py  refreshes reference/zed.json from Zed's source
reference/zed.json       snapshot of Zed's theme keys and grammar captures (with Zed commit)
themes/*.json            GENERATED Zed theme families
ports/windows-terminal/  GENERATED Windows Terminal fragment (all schemes)
ports/obsidian/          GENERATED AnuPpuccin CSS snippets
preview/index.html       GENERATED visual preview
install.ps1              copies ports into Windows Terminal and Obsidian vaults
extension.toml           Zed extension manifest
```

## Commands

```
python tools/build.py              # validate and write all outputs
python tools/build.py --fix        # nudge colors that miss contrast targets, save palettes.json, build
python tools/build.py --check      # validate only
python tools/sync_zed_reference.py # update reference/zed.json from Zed main (needs git + network)
```

## Palette roles

Each variant has these 14 colors. Everything else (about 190 Zed keys, 20 terminal colors,
26 AnuPpuccin colors) is derived from them in `tools/build.py`.

| Role | Used for |
|---|---|
| `bg` | editor background, terminal background |
| `panel` | sidebar, tabs, status bar, title bar (darker than `bg` in dark themes: gives depth) |
| `tx` | main text, variables, properties, parameters, namespaces |
| `cm` | comments (italic), muted UI text |
| `kw` | keywords, tags, markdown headings, cursor, primary accent |
| `st` | strings |
| `fn` | functions, methods, JSON keys |
| `nu` | numbers, constants, booleans, attributes, escapes |
| `ty` | types: built-in (`unsigned int`, `string`), classes, constructors, JSX components |
| `er` | errors, deletions, terminal red |
| `green`, `yellow`, `blue` | git/diff/status colors and terminal ANSI colors |
| `sel` | selected rows and highlighted lines |

## Design rules (the owner's preferences)

- Five syntax hues only: `kw`, `st`, `fn`, `nu`, `ty`. Plain identifiers stay in `tx`. Built-in types
  must use `ty`, never `tx` and never `kw` (this was a real bug once: `unsigned int` looked like a variable).
- The five hues must be clearly distinct from each other and from `tx` (the build warns below the
  `distinct` rule, measured as CIELAB delta E).
- Comments are italic and quiet but readable.
- No pure white or pure black backgrounds. The owner is sensitive to glare and to low-contrast text.
- Backgrounds carry real color and depth. Avoid: cold blue-gray or flat gray (Nord-like, feels
  lifeless), yellow-brown (Gruvbox-like), neon or high-saturation accents (distracting).
- Mid-tone themes (Clay, Mauve, Stone) have `appearance: light` on a darker background. They need
  dark, crisp ink. Stone uses stricter per-variant rules (text 11, syntax 7, comment 5) because the
  owner found softer ink hard to read; prefer that recipe for new mid-tones.
- Naming: pairs are `<Family> Dark` / `<Family> Light`; standalone themes use a plain name. Names must be
  unique across both repos (Zed, Windows Terminal and Obsidian all key on the name).

## Adding a theme

1. Add a family (or a variant to a family) in `palettes.json` with all 14 roles.
   `file` is the family's file slug. For a new dark theme, also design its light partner unless the
   owner asks for a standalone theme.
2. Run `python tools/build.py --fix`, then `python tools/build.py`. Fix any warnings.
3. Open `preview/index.html` and check the new theme next to the existing ones.
4. Update the theme table in `README.md`, bump `version` in `extension.toml` (minor version for new
   themes, patch for color tweaks), commit.

## Changing a color

Edit the role in `palettes.json`, build, check the preview, commit with a message saying what and why
(for example "Stone: darker strings, they blended with text").

## Keeping up with Zed

Zed adds theme keys and grammar captures over time. Missing keys silently fall back to Zed's stock
colors, which looks like a bug to the owner. Every few months, or when the owner reports an odd color:

1. `python tools/sync_zed_reference.py` (prints added and removed keys and captures).
2. `python tools/build.py`. Errors list theme keys the generator does not set yet: add them in
   `zed_theme()` in `tools/build.py`, derived from the palette roles. Warnings list grammar captures with
   no syntax key: map them in `zed_syntax()`.
3. Apply the same `tools/` change in the sibling repo, rebuild both, commit both.

How Zed resolves syntax colors: a capture like `@type.builtin` uses the longest theme key that matches
on dot boundaries (`type.builtin`, then `type`). Captures from third-party language extensions
(Luau, GLSL, etc.) are not in the reference but use the same common names.

## Ports

- **Windows Terminal**: one fragment file with every scheme, installed to
  `%LOCALAPPDATA%\Microsoft\Windows Terminal\Fragments\unyxed-idk-theme\`. Fragment schemes must define every
  color in the table (the generator does). Terminal background is `bg`.
- **Obsidian**: snippets set AnuPpuccin's `--ctp-custom-*` variables (RGB triples) on `.theme-dark` /
  `.theme-light`, which every AnuPpuccin flavor reads before its own colors. One snippet per family, or
  one per variant when a family has several variants of the same appearance (they would collide).
  The owner enables one snippet at a time.
- Run `install.ps1` after building to copy ports into place.

## Before you finish a task

- [ ] `python tools/build.py` passes with no errors and no warnings
- [ ] preview checked for anything that changed visually
- [ ] README theme table and `extension.toml` version updated if themes were added
- [ ] shared files mirrored to `unyxed-cocoa-theme` if `tools/`, `install.ps1` or `reference/` changed
- [ ] source and generated files committed together
