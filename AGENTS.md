# AGENTS.md: Unyxed IDK Themes

Instructions for any coding agent (Claude Code, opencode, Codex, etc.) working in this repo.

## Context

- The owner uses these themes daily and relies on agents to design and maintain them. They are not a
  theme designer. Everything must work out of the box: no missing UI colors, no syntax bugs.
- This repo produces one Zed theme extension plus ports for Windows Terminal, Claude Code, opencode
  and Obsidian (AnuPpuccin). Antigravity CLI is covered by the terminal schemes (see Ports).
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
reference/gruvbox.json   Zed's stock Gruvbox theme: the syntax structure our themes follow
themes/*.json            GENERATED Zed theme families
ports/windows-terminal/  GENERATED Windows Terminal fragment (all schemes)
ports/obsidian/          GENERATED AnuPpuccin CSS snippets
ports/claude-code/       GENERATED Claude Code custom themes, one per variant
ports/opencode/          GENERATED opencode themes, one per variant
preview/index.html       GENERATED visual preview for the owner (agents: do not read it, see below)
install.ps1              copies ports into Windows Terminal, Claude Code, opencode and Obsidian vaults
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

Each variant has these 13 colors. Everything else (about 190 Zed keys, 24 terminal colors,
26 AnuPpuccin colors) is derived from them in `tools/build.py`. The build errors on a missing or
unknown role.

| Role | Used for |
|---|---|
| `bg` | editor background, terminal background |
| `panel` | sidebar, tabs, status bar, title bar (darker than `bg` in dark themes: gives depth) |
| `tx` | main text, variables, parameters, properties |
| `cm` | comments (italic), muted UI text, ignored/hidden files |
| `sel` | selected rows and highlighted lines, terminal selection |
| `accent` | cursor, focused borders, accent text and icons, the first player color (UI only, never syntax) |
| `red` | keywords (all of them: declaration, control flow, storage, import), preprocessor, built-in functions; errors, deletions, terminal red |
| `orange` | enums, regular expressions; merge conflicts |
| `yellow` | types, constants, CSS selectors; warnings, modified files, terminal yellow |
| `green` | functions, strings, titles and markdown headings; success, added files, terminal green |
| `aqua` | operators, tags, embedded code, link text, symbols; terminal cyan |
| `blue` | attributes, constructors, namespaces and modules, labels, `this`/`self`, decorators, markup; info, renamed files, terminal blue |
| `purple` | numbers, booleans, special strings, URLs; terminal magenta |

The syntax side follows Zed's own Gruvbox theme key for key: `GROUPS` in `tools/build.py` says which
syntax keys share a hue, copied from `reference/gruvbox.json`, and the build errors if that table stops
matching the reference or if our themes lack any syntax key Gruvbox has. Captures Zed's grammars emit
that Gruvbox has no key for are placed in `EXTRA`, in the group closest in meaning.

## Design rules (the owner's preferences)

- **Language-agnostic by design.** The themes must look right in every language out of the box, like
  mainstream themes do. Never tune colors or add syntax keys for one language (the owner's own C++,
  TypeScript and Luau are only examples, not targets). Design on Zed's shared capture names
  (`keyword`, `type`, `function`, `property`, ...) so third-party extensions (Luau, GLSL, Odin, ...)
  resolve through the longest-prefix rule without needing their own entries. Any new mapping must be
  justified by captures that several grammars in `reference/zed.json` use.
- **Gruvbox structure, our colors.** Seven hues (`red`, `orange`, `yellow`, `green`, `aqua`, `blue`,
  `purple`) play the same parts as in Gruvbox, so tokens are grouped the way a mainstream theme groups
  them. Plain identifiers, parameters and properties stay in `tx`. Built-in types must land on `yellow`
  (`type`), never on `tx` or `red` (this was a real bug once: `unsigned int` looked like a variable).
  Every keyword is `red`: the split into control-flow, import and declaration colors was dropped.
  Functions and strings share `green`, as in Gruvbox.
- The seven hues and `tx` must be clearly distinct, saturated enough and spread in lightness. The build
  **errors** below these rules (see "Build rules" below): `distinct` (CIELAB delta E 25 between any two),
  `chroma` (average hue chroma) and `spread` (L* range of the hues). Do not fix a weak pair by raising
  saturation: move hue or lightness, and keep colors calm, never neon.
- `accent` is the theme's identity color (rose, coral, wine ...). It drives the UI, not syntax, so it may
  sit close to `red`; it still needs the `syntax` contrast on `bg`.
- Comments are italic and quiet but readable (Gruvbox's are upright; that is a deliberate difference).
- No pure white or pure black backgrounds. The owner is sensitive to glare and to low-contrast text.
- Backgrounds carry real color and depth: aubergine, teal, forest, indigo and the muted mid-tones. Avoid
  cold blue-gray or flat gray (Nord-like, feels lifeless), yellow-brown (Gruvbox's own backgrounds), and
  neon or high-saturation accents (distracting).
- Mid-tone themes (Clay, Mauve, Stone) have `appearance: light` on a darker background. They need
  dark, crisp ink. Stone uses stricter per-variant rules (text 11, syntax 7, comment 5; chroma and
  spread are lowered to fit that ink) because the owner found softer ink hard to read; prefer that
  recipe for new mid-tones.
- Naming: pairs are `<Family> Dark` / `<Family> Light`; standalone themes use a plain name. Names must be
  unique across both repos (Zed, Windows Terminal and Obsidian all key on the name).

## Build rules

Contrast is measured on `bg`. Defaults live in `DEFAULT_RULES` in `tools/build.py`; `palettes.json`
overrides them per appearance under `rules` (currently: syntax 4.8 on light themes, chroma 50 on dark
and 45 on light), and a variant can override them with its own `rules` object (currently only Stone, see the design rules).

| Rule | Default | Checks |
|---|---|---|
| `text` | 7.0 | `tx` contrast |
| `comment` | 4.2 | `cm` contrast |
| `syntax` | 4.5 | `accent` and each hue's contrast |
| `distinct` | 25 | delta E between any two of the seven hues and `tx` |
| `chroma` | 45 | average chroma of the seven hues |
| `spread` | 20 | L* range of the seven hues |
| `ansi`, `ansi_dim`, `ansi_sep` | 4.5, 3.5, 12 | terminal colors (see "Terminal readability") |

**Pending themes.** A variant with `"pending": true` still has its colors from before the Gruvbox
structure. The build checks its terminal colors and Zed keys as usual but only warns about its text,
hue and sharpness rules, and the preview shows it faded. Check `palettes.json` for which variants (if
any) still carry the flag. Migrating one means redesigning its seven hues until the build passes
without the flag, then removing `pending`. Do not add `pending` to hide a failing new theme.

## The preview

`python tools/build.py` regenerates `preview/index.html` on every run: every theme side by side with
C++, TypeScript and Luau samples, next to Zed's Gruvbox. It is for the owner to open in a browser.
Agents must not read it: it is about 400 KB of generated HTML and costs a lot of tokens, and the build's
validators already check everything it shows. Commit it with the other generated files.

## Adding a theme

1. Add a family (or a variant to a family) in `palettes.json` with all 13 roles.
   `file` is the family's file slug. For a new dark theme, also design its light partner unless the
   owner asks for a standalone theme.
2. Run `python tools/build.py --fix`, then `python tools/build.py`. Fix any warnings and errors.
   `--fix` only repairs contrast; if `distinct`, `chroma` or `spread` fails, move hues or lightness by
   hand (keep each hue recognisably red, orange, yellow ..., see the design rules).
3. Tell the owner to open `preview/index.html` in a browser to compare the new theme with the others
   and Zed's Gruvbox.
4. Update the theme table in `README.md`, bump `version` in `extension.toml` (minor version for new
   themes, patch for color tweaks), commit.

## Changing a color

Edit the role in `palettes.json`, build, commit with a message saying what and why
(for example "Stone: darker green, strings blended with text").

## Keeping up with Zed

Zed adds theme keys and grammar captures over time. Missing keys silently fall back to Zed's stock
colors, which looks like a bug to the owner. Every few months, or when the owner reports an odd color:

1. `python tools/sync_zed_reference.py` (prints added and removed keys and captures).
2. `python tools/build.py`. Errors list theme keys the generator does not set yet: add them in
   `zed_theme()` in `tools/build.py`, derived from the palette roles. Errors also list grammar captures
   with no syntax key, or whose key falls outside the Gruvbox groups: add them to `EXTRA` in the group
   closest in meaning. If Zed changes its Gruvbox theme, refresh `reference/gruvbox.json` and update
   `GROUPS` until the build agrees with it.
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
  past the foreground when there is room; on dark themes, and on Stone, there is no room, so it sits 12 dE inside
  the foreground. `bright_black` is the comment color pushed just far enough to be readable, the
  usual "secondary text" grey, always quieter than the foreground. A low-contrast theme (the Clay
  and Mauve mid-tones) with too little lightness between the 4.5:1 floor and its text falls back to the comment hue with a little
  more chroma for `bright_black`, and puts `white` past the foreground. The build also checks the order.
- **Hue slots** are the palette hues (`purple` is magenta, `aqua` is cyan). They only move if they miss 4.5:1, and then by the smallest
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
- **Claude Code**: one `<theme-slug>.json` per variant for `~/.claude/themes/` (`name`, `base`
  dark/light, `overrides` of Claude Code's color tokens; reference:
  https://code.claude.com/docs/en/terminal-config#create-a-custom-theme). Claude Code draws on the
  terminal's own background and has no background token, so these themes assume the matching
  Windows Terminal scheme (terminal background = `bg`). The accent is `claude`; status, mode and
  subagent colors use the seven hues; diff and message backgrounds are tints of `bg`.
- **opencode**: one `<theme-slug>.json` per variant for `~/.config/opencode/themes/` (schema
  https://opencode.ai/theme.json). opencode paints its own backgrounds (`bg`, `panel`). Its syntax and
  markdown keys follow the same Gruvbox groups as Zed (keyword red, function/string green, type
  yellow, number purple, operator aqua, headings green, inline code blue).
- **Antigravity CLI** (`agy`) has no custom theme files, only built-in schemes. Leave its
  `colorScheme` on `"terminal"` (the default): it then draws with the terminal's 16 ANSI colors,
  which our Windows Terminal and Zed terminal schemes already provide and the terminal rules keep
  readable.
- **Port readability** (build **errors**, same floors as the terminal): Claude Code text and accent
  tokens 4.5:1 on `bg`, `inactive`/`subtle` 3.5:1, `text` 4.5:1 on every tinted background (diffs,
  message backgrounds, selection), `inverseText` 4.5:1 on the colors it sits on; opencode `text`
  4.5:1 on every background, `textMuted` and diff line numbers 3.5:1, status/accent colors 4.5:1 on
  both `background` and `backgroundPanel`. Tinted backgrounds back off (`tint()`) and ink colors are
  nudged (`readable()`, same hue) only as far as these need, so a port can differ by a hair from
  the palette on a light theme whose panel is darker than its background.
- Run `install.ps1` after building to copy ports into place.

## Before you finish a task

- [ ] `python tools/build.py` passes with no errors and no warnings (the pending-themes warning is expected only while a variant carries `pending`)
- [ ] `python tools/build.py --check -v`: no terminal slot is near its floor by accident
- [ ] README theme table and `extension.toml` version updated if themes were added
- [ ] shared files mirrored to `unyxed-cocoa-theme` if `tools/`, `install.ps1` or `reference/` changed
- [ ] source and generated files committed together
