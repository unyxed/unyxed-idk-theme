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
python tools/build.py --check -v   # validate and print each theme's worst-case terminal contrast
python tools/sync_zed_reference.py # update reference/zed.json from Zed main (needs git + network)
```

## Palette roles

Each variant has these 18 colors. Everything else (about 190 Zed keys, 20 terminal colors,
26 AnuPpuccin colors) is derived from them in `tools/build.py`.

| Role | Used for |
|---|---|
| `bg` | editor background, terminal background |
| `panel` | sidebar, tabs, status bar, title bar (darker than `bg` in dark themes: gives depth) |
| `tx` | main text, variables, parameters, namespaces |
| `cm` | comments (italic), muted UI text |
| `kw` | declaration/storage keywords (`class`, `const`, `public`, `local`, `interface`), `variable.special` (`this`), tags, markdown headings, cursor, primary accent |
| `ct` | control-flow keywords (`if`, `for`, `return`, `try`, `await`) |
| `im` | import and preprocessor keywords (`import`, `from`, `#include`, `#define`) |
| `st` | strings |
| `fn` | functions, methods, JSON keys |
| `nu` | numbers, constants, booleans, attributes, escapes |
| `ty` | types: built-in (`unsigned int`, `string`), classes, constructors, JSX components |
| `pr` | properties and members (`obj.size`, struct fields, object keys) |
| `op` | operators (`=`, `&&`, `->`) and word operators (`in`, `not`) |
| `er` | errors, deletions, terminal red |
| `green`, `yellow`, `blue` | git/diff/status colors and terminal ANSI colors |
| `sel` | selected rows and highlighted lines |

## Design rules (the owner's preferences)

- **Language-agnostic by design.** The themes must look right in every language out of the box, like
  mainstream themes do. Never tune colors or add syntax keys for one language (the owner's own C++,
  TypeScript and Luau are only preview samples, not targets). Design on Zed's shared capture names
  (`keyword`, `keyword.control`, `type.builtin`, `property`, ...), and make sure every split has a sane
  fallback: a grammar that emits only plain `keyword`, `function`, `type` or `property` must still look
  complete, and third-party extensions (Luau, GLSL, Odin, ...) must resolve through the longest-prefix
  rule without needing their own entries. Any new role or mapping must be justified by captures that
  several grammars in `reference/zed.json` use.
- Nine syntax hues: `kw`, `ct`, `im`, `st`, `fn`, `nu`, `ty`, `pr`, `op`. Plain identifiers stay in `tx`.
  Built-in types must use `ty`, never `tx` and never `kw` (this was a real bug once: `unsigned int`
  looked like a variable). The goal is Gruvbox-style separation: hues spread around the color wheel with
  matched lightness and chroma per theme, so tokens are told apart at a glance and still look cohesive.
  Do not fix a weak pair by raising saturation: move hue or lightness, and keep colors calm, never neon.
- The nine hues and `tx` must be clearly distinct from each other: the build **errors** below the
  `distinct` rule (default CIELAB delta E 25; every variant currently holds 25 or more, closest pairs 25-28).
  The same hue slots are used in every theme where possible (`ct` pink, `im` green, `pr` olive,
  `op` blue/steel, `kw` coral); keep each theme's own `kw/st/fn/nu/ty` identity (`ty` is yellow or green in a few).
  The mid-tones (Clay, Mauve, Stone) are gamut-limited and use looser slots; keep them at 25 anyway.
- Keyword split: `keyword` and `keyword.declaration` -> `kw`; `keyword.control` -> `ct`; `keyword.import`,
  `keyword.preproc`, `preproc`, `import` -> `im`; `keyword.operator` and `operator` -> `op`; `property`,
  `variable.other.member` -> `pr`. Grammars that emit only plain `keyword` (Luau) show every keyword in `kw`:
  that is expected, a theme cannot split by token text.
- Comments are italic and quiet but readable.
- No pure white or pure black backgrounds. The owner is sensitive to glare and to low-contrast text.
- Backgrounds carry real color and depth. Avoid: cold blue-gray or flat gray (Nord-like, feels
  lifeless), yellow-brown (Gruvbox-like), neon or high-saturation accents (distracting).
- Mid-tone themes (Clay, Mauve, Stone) have `appearance: light` on a darker background. They need
  dark, crisp ink. Stone uses stricter per-variant rules (text 11, syntax 7, comment 5) because the
  owner found softer ink hard to read; prefer that recipe for new mid-tones. Stone no longer has a
  `distinct` exception: it meets the global 25.
- Naming: pairs are `<Family> Dark` / `<Family> Light`; standalone themes use a plain name. Names must be
  unique across both repos (Zed, Windows Terminal and Obsidian all key on the name).

## Adding a theme

1. Add a family (or a variant to a family) in `palettes.json` with all 18 roles.
   `file` is the family's file slug. For a new dark theme, also design its light partner unless the
   owner asks for a standalone theme.
2. Run `python tools/build.py --fix`, then `python tools/build.py`. Fix any warnings and errors.
   `--fix` only repairs contrast; if `distinct` fails, move hues or lightness by hand (keep each role's
   usual hue slot, see the design rules).
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

## Terminal readability

Programs (CLI agents, `ls`, `git`, compilers, test runners) draw ordinary text with **any** of the
16 ANSI colors, including black, white and their bright and dim forms. A slot that sits close to
the background turns that text invisible. This happened once: light themes had `white` at 1.8:1 and
`bright_white` at 1.1:1, dark themes had `black` at 2.0:1, and an agent's output vanished. So the
terminal slots are text colors, not decoration, and the build checks them as such.

`ansi()` in `tools/build.py` builds every slot once; Zed's `terminal.*` keys and the Windows
Terminal schemes both come from it. Rules (build **errors**, contrast measured on `bg`):

| What | Minimum |
|---|---|
| every normal and `bright_` slot (black, red, green, yellow, blue, magenta, cyan, white), in Zed and Windows Terminal | 4.5:1 (`ansi`) |
| every `dim_` slot and `terminal.dim_foreground` | 3.5:1 (`ansi_dim`): faint by design, never invisible |
| `terminal.foreground`, `terminal.bright_foreground` | the `text` rule (7:1, Stone 11:1) |
| foreground text on the selection (Zed's player selection over `bg`, Windows Terminal's `selectionBackground`) | 4.5:1 |
| `black`/`bright_black`, `white`/`bright_white`, and each of those four vs the foreground | delta E 12 (`ansi_sep`) |

- **Greys keep their meaning.** They sit on the line from `bg` to `tx` and beyond. `black` is the
  readable grey closest to the background (darkest on dark themes, lightest on light ones);
  `bright_white` is the most emphasised (furthest from the background). On light themes it goes
  past the foreground when there is room; on dark themes, and on Stone, there is no room, so it
  sits 12 dE inside the foreground. `bright_black` is the comment color pushed just far enough to
  be readable, the usual "secondary text" grey, always quieter than the foreground. The low-contrast
  mid-tones (Clay, Mauve) have too little lightness between the 4.5:1 floor and their text, so
  their `bright_black` keeps the comment hue with a little more chroma, and their `white` sits
  past the foreground. The build also checks the order.
- **Hue slots** are the palette hues. They only move if they miss 4.5:1, and then by the smallest
  step that passes (darker on light themes, lighter on dark ones, same hue).
- **Dim slots** are the normal slots blended toward `bg`, but never past 3.5:1.
- Do not lower these rules to get a build through. If a new theme fails, adjust `tx`, `cm` or the
  background. `python tools/build.py --check -v` shows where each theme is tightest.
- Themes only control the 16 ANSI colors. Programs that print 256-color or RGB values bypass them;
  the README's recommended terminal settings (Zed `minimum_contrast`, Windows Terminal
  `adjustIndistinguishableColors`) are the safety net for those.

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
- [ ] `python tools/build.py --check -v`: no terminal slot is near its floor by accident
- [ ] preview checked for anything that changed visually
- [ ] README theme table and `extension.toml` version updated if themes were added
- [ ] shared files mirrored to `unyxed-cocoa-theme` if `tools/`, `install.ps1` or `reference/` changed
- [ ] source and generated files committed together
