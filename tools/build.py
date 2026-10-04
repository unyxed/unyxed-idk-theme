#!/usr/bin/env python3
"""Build every output of this theme package from palettes.json.

Usage:
    python tools/build.py          # validate, then write all outputs
    python tools/build.py --fix    # nudge colors that miss contrast targets, save palettes.json, then build
    python tools/build.py --check  # validate only, write nothing (exit 1 on errors)
    python tools/build.py --check -v  # also print the worst-case terminal contrast per theme

Outputs (all generated, never edit by hand):
    themes/<family>.json                      Zed theme families
    ports/windows-terminal/<package-id>.json  Windows Terminal fragment with every scheme
    ports/obsidian/<package-id>-<family>.css  AnuPpuccin snippets, one per family
    ports/claude-code/<theme>.json            Claude Code custom themes (~/.claude/themes)
    ports/opencode/<theme>.json               opencode themes (~/.config/opencode/themes)

Requires Python 3.9+, no third-party packages.
"""
import argparse
import json
import math
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PALETTES = ROOT / "palettes.json"
REFERENCE = ROOT / "reference" / "zed.json"
GRUVBOX = ROOT / "reference" / "gruvbox.json"
SCHEMA = "https://zed.dev/schema/themes/v0.2.0.json"

HUES = ["red", "orange", "yellow", "green", "aqua", "blue", "purple"]
ROLES = ["bg", "panel", "tx", "cm", "sel", "accent"] + HUES
DEFAULT_RULES = {"text": 7.0, "comment": 4.2, "syntax": 4.5,
                 "distinct": 25.0, "chroma": 45.0, "spread": 20.0,
                 # terminal: programs draw ordinary text with any ANSI slot (see AGENTS.md)
                 "ansi": 4.5, "ansi_dim": 3.5, "ansi_sep": 12.0}
ANSI_NAMES = ["black", "red", "green", "yellow", "blue", "magenta", "cyan", "white"]

# Zed's Gruvbox syntax structure: which keys share a hue. Copied from reference/gruvbox.json,
# and the build checks it still matches that file. "text" = the plain editor text color.
GROUPS = {
    "red": ["keyword", "preproc", "function.builtin"],
    "green": ["function", "string", "title"],
    "yellow": ["type", "constant", "selector"],
    "blue": ["attribute", "constructor", "namespace", "label", "variant", "variable.special",
             "text.literal", "emphasis", "emphasis.strong", "punctuation.markup", "selector.pseudo"],
    "purple": ["number", "boolean", "link_uri", "string.special"],
    "aqua": ["operator", "tag", "embedded", "link_text", "string.special.symbol"],
    "orange": ["enum", "string.regex"],
    "text": ["variable", "variable.parameter", "property", "primary", "punctuation.list_marker"],
}
# Captures Zed's grammars emit that Gruvbox has no key for (or whose prefix lands in the wrong
# group). Each goes to the nearest Gruvbox group by meaning.
EXTRA = {
    "red": ["storageclass", "import", "type.qualifier", "media", "keyframes", "supports", "charset"],
    "blue": ["module", "variable.builtin", "function.decorator", "function.method.constructor", "lifetime"],
    "yellow": ["concept", "diff.delta"],
    "green": ["markup.heading"],
    "purple": ["markup.link.url", "type.unit"],
    "text": ["text", "function.kwargs"],
    "comment": ["strikethrough"],
}
BOLD = {"title", "emphasis.strong", "markup.heading"}
ITALIC = {"link_text"}
# Captures that intentionally render in the default text color (no theme key needed).
PLAIN_CAPTURES = {"none", "nested"}


# ---------------------------------------------------------------- color math
def h2r(h):
    h = h.lstrip("#")
    return tuple(int(h[i:i + 2], 16) for i in (0, 2, 4))


def r2h(rgb):
    return "#%02X%02X%02X" % tuple(max(0, min(255, round(x))) for x in rgb)


def mix(a, b, t):
    A, B = h2r(a), h2r(b)
    return r2h([A[i] * (1 - t) + B[i] * t for i in range(3)])


def alpha(c, a):
    return c[:7] + "%02X" % round(a * 255)


def lum(h):
    def f(c):
        c /= 255
        return c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4
    r, g, b = (f(x) for x in h2r(h))
    return 0.2126 * r + 0.7152 * g + 0.0722 * b


def contrast(a, b):
    la, lb = lum(a), lum(b)
    return (max(la, lb) + 0.05) / (min(la, lb) + 0.05)


def lab(h):
    def f(c):
        c /= 255
        return c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4
    r, g, b = (f(x) for x in h2r(h))
    x = (r * 0.4124 + g * 0.3576 + b * 0.1805) / 0.95047
    y = r * 0.2126 + g * 0.7152 + b * 0.0722
    z = (r * 0.0193 + g * 0.1192 + b * 0.9505) / 1.08883

    def g_(t):
        return t ** (1 / 3) if t > 0.008856 else 7.787 * t + 16 / 116
    fx, fy, fz = g_(x), g_(y), g_(z)
    return 116 * fy - 16, 500 * (fx - fy), 200 * (fy - fz)


def lab_hex(L, a, b):
    """CIELAB to hex, or None when the color is outside sRGB."""
    fy = (L + 16) / 116
    fx, fz = fy + a / 500, fy - b / 200

    def finv(t):
        return t ** 3 if t ** 3 > 0.008856 else (t - 16 / 116) / 7.787
    X, Y, Z = finv(fx) * 0.95047, finv(fy), finv(fz) * 1.08883
    rgb = (3.2404542 * X - 1.5371385 * Y - 0.4985314 * Z,
           -0.9692660 * X + 1.8760108 * Y + 0.0415560 * Z,
           0.0556434 * X - 0.2040259 * Y + 1.0572252 * Z)
    if any(v < -0.001 or v > 1.001 for v in rgb):
        return None
    rgb = [min(max(v, 0), 1) for v in rgb]
    return r2h([255 * (12.92 * v if v <= 0.0031308 else 1.055 * v ** (1 / 2.4) - 0.055) for v in rgb])


def chroma(h):
    _, a, b = lab(h)
    return math.hypot(a, b)


def delta_e(a, b):
    A, B = lab(a), lab(b)
    return sum((A[i] - B[i]) ** 2 for i in range(3)) ** 0.5


def toward_contrast(color, bg, target, anchor):
    """Move color toward anchor in 1% steps until it reaches target contrast on bg."""
    start, t, out = color, 0.0, color
    while contrast(out, bg) < target and t < 1:
        t += 0.01
        out = mix(start, anchor, t)
    if contrast(out, bg) < target:  # anchor not extreme enough: use black/white
        far = "#000000" if lum(bg) > 0.18 else "#FFFFFF"
        t, out = 0.0, color
        while contrast(out, bg) < target and t < 1:
            t += 0.01
            out = mix(start, far, t)
    return out


def soft(c, bg, ratio, minimum):
    """Blend c toward bg by ratio, but never below `minimum` contrast."""
    while ratio > 0 and contrast(mix(c, bg, ratio), bg) < minimum:
        ratio -= 0.02
    return mix(c, bg, max(ratio, 0))


def sharpness(c):
    """Gruvbox-style separation numbers for a palette: avg chroma, L* range, closest pair."""
    ls = [lab(c[k])[0] for k in HUES]
    pool = HUES + ["tx"]
    pairs = sorted((delta_e(c[a], c[b]), a, b) for i, a in enumerate(pool) for b in pool[i + 1:])
    return {"chroma": sum(chroma(c[k]) for k in HUES) / len(HUES), "lmin": min(ls), "lmax": max(ls),
            "spread": max(ls) - min(ls), "closest": pairs[0]}


# ---------------------------------------------------------------- data
def load():
    data = json.loads(PALETTES.read_text(encoding="utf-8"))
    ref = json.loads(REFERENCE.read_text(encoding="utf-8"))
    gruv = json.loads(GRUVBOX.read_text(encoding="utf-8"))
    return data, ref, gruv


def rules_for(data, variant):
    r = dict(DEFAULT_RULES)
    r.update(data.get("rules", {}).get(variant["appearance"], {}))
    r.update(variant.get("rules", {}))
    return r


def variants(data):
    for fam in data["families"]:
        for v in fam["variants"]:
            yield fam, v


def is_dark(v):
    return v["appearance"] == "dark"


# ---------------------------------------------------------------- terminal colors
def ansi_greys(c, dark, r):
    """The four grey slots, placed on the line bg -> tx -> (white on dark, black on light).

    Programs print ordinary text with these, so every one must clear the `ansi` contrast floor,
    stay `ansi_sep` delta E away from the foreground and from its own bright/normal partner, and
    keep the natural order: the slot nearest the background is `black` (darkest grey on dark
    themes, lightest on light ones), `bright_white` is the most emphasised (furthest from bg)."""
    bg, tx, floor, sep = c["bg"], c["tx"], r["ansi"], r["ansi_sep"]
    far = "#FFFFFF" if dark else "#000000"
    # line[0] = bg, line[200] = tx, line[400] = white/black: ordered from the background outward
    line = [mix(bg, tx, i / 200) for i in range(201)] + [mix(tx, far, i / 200) for i in range(1, 201)]
    low = next(i for i in range(201) if contrast(line[i], bg) >= floor)  # first readable step

    def away(i, *cols):
        return all(delta_e(line[i], x) >= sep for x in cols)

    def pick(indices, *cols):
        return next((i for i in indices if away(i, *cols)), None)

    black = low
    # white sits between black and the foreground (as close to the foreground as allowed) and
    # bright_white beyond the foreground, if the gamut leaves room. Squeezed mid-tones put white
    # beyond the foreground too rather than reuse black's grey. Otherwise (no room beyond the
    # foreground) bright_white is the closest step below it and white the next one down.
    not_black = [i for i in range(200, low - 1, -1) if delta_e(line[i], line[black]) >= sep / 2]
    white = pick(not_black, tx)
    bw = pick(range(201, 401), tx)
    if bw is not None and white is None:
        white = bw
        bw = pick(range(white + 1, 401), tx, line[white])
    if bw is None:
        bw = pick(range(199, low - 1, -1), tx)
        if bw is None:
            return {k: tx for k in ("black", "bright_black", "white", "bright_white")}  # validator reports it
        white = pick([i for i in range(bw - 1, low - 1, -1) if delta_e(line[i], line[black]) >= sep / 2],
                     tx, line[bw])
        if white is None:
            white = pick(range(bw - 1, low - 1, -1), tx, line[bw])
    # bright_black: the comment color, pushed toward the text only as far as floor and separation need
    def fits(x):
        return (x is not None and floor <= contrast(x, bg) < contrast(tx, bg)
                and all(delta_e(x, y) >= sep for y in (line[black], tx)))
    bblack = next((x for x in (mix(c["cm"], tx, i / 100) for i in range(101)) if fits(x)), None)
    if bblack is None:
        # Too little lightness between the floor and the text (low-contrast mid-tones): keep the
        # comment hue and add the least chroma that makes it distinct from both neighbours.
        L0, L1 = lab(tx)[0], lab(line[black])[0]
        _, a, b = lab(c["cm"])
        hue, c0 = math.atan2(b, a), math.hypot(a, b)
        grid = ((abs(C - c0), abs(L - (L0 + L1) / 2), lab_hex(L, C * math.cos(hue), C * math.sin(hue)))
                for C in range(0, 41) for L in [L0 + (L1 - L0) * i / 40 for i in range(41)])
        bblack = next((x for _, _, x in sorted(grid, key=lambda g: g[:2]) if fits(x)), tx)
    return {"black": line[black], "bright_black": bblack,
            "white": line[white] if white is not None else tx, "bright_white": line[bw]}


def ansi(c, dark, r):
    """All 24 ANSI slots (normal, bright_, dim_). Feeds Zed's terminal.ansi.* and Windows Terminal."""
    bg, floor = c["bg"], r["ansi"]
    anchor = "#FFFFFF" if dark else "#000000"
    greys = ansi_greys(c, dark, r)
    hues = {"red": c["red"], "green": c["green"], "yellow": c["yellow"],
            "blue": c["blue"], "magenta": c["purple"], "cyan": c["aqua"]}
    out = {}
    for name in ANSI_NAMES:
        if name in hues:  # unchanged unless below the floor; then the smallest step that passes
            col = toward_contrast(hues[name], bg, floor, anchor)
            bright = toward_contrast(mix(col, "#FFFFFF", 0.15) if dark else mix(col, "#000000", 0.12),
                                     bg, floor, anchor)
        else:
            col, bright = greys[name], greys["bright_" + name]
        out[name], out["bright_" + name] = col, bright
        # faint by design, never invisible: blend toward bg only as far as the dim floor allows
        out["dim_" + name] = soft(col, bg, 0.35, r["ansi_dim"])
    return out


# ---------------------------------------------------------------- zed
def zed_syntax(c, rules):
    tx, bg, cm = c["tx"], c["bg"], c["cm"]
    floor = rules["syntax"]
    color = {h: c[h] for h in HUES}
    color["text"] = tx
    color["comment"] = cm
    # muted helpers: doc comments and escapes are a lighter muted tone (closer to text than comments)
    doc = mix(cm, tx, 0.3)

    def s(col, key=None, **extra):
        d = {"color": col}
        if key in BOLD:
            d["font_weight"] = 700
        if key in ITALIC:
            d["font_style"] = "italic"
        d.update(extra)
        return d

    out = {}
    for group, keys in list(GROUPS.items()) + list(EXTRA.items()):
        for k in keys:
            out[k] = s(color[group], k)
    out.update({
        # comments stay italic (the owner's choice; Gruvbox has upright comments)
        "comment": s(cm, font_style="italic"), "comment.doc": s(doc, font_style="italic"),
        "string.escape": s(doc),
        # punctuation: dimmed text, brackets dimmer, delimiters/special slightly brighter
        "punctuation": s(soft(tx, bg, 0.16, floor)),
        "punctuation.bracket": s(soft(tx, bg, 0.34, floor)),
        "punctuation.delimiter": s(soft(tx, bg, 0.07, floor)),
        "punctuation.special": s(soft(tx, bg, 0.07, floor)),
        # editor hints and diff
        "hint": s(mix(cm, c["aqua"], 0.25)), "predictive": s(mix(cm, bg, 0.2), font_style="italic"),
        "diff.plus": s(c["green"]), "diff.minus": s(c["red"]),
    })
    return out


def zed_theme(v):
    c, dark = v["colors"], is_dark(v)
    bg, panel, tx, cm, sel, acc = c["bg"], c["panel"], c["tx"], c["cm"], c["sel"], c["accent"]
    red, orange, yellow, green = c["red"], c["orange"], c["yellow"], c["green"]
    aqua, blue, purple = c["aqua"], c["blue"], c["purple"]

    def lift(base, t):
        return mix(base, tx, t)
    border, bvar, bdis = lift(panel, .14), lift(panel, .08), lift(panel, .06)
    elev = lift(bg, .05) if dark else mix(bg, "#FFFFFF", .35)
    el_bg, el_h, el_a = lift(bg, .06), lift(bg, .10), lift(bg, .14)
    muted, dis, icon = mix(tx, bg, .35), mix(tx, bg, .6), mix(tx, bg, .2)
    linenum = mix(cm, bg, .2)
    guide, guide_a = lift(bg, .08), lift(bg, .20)

    def on(color):  # readable label color on top of `color`
        return bg if contrast(bg, color) >= contrast(tx, color) else tx

    S = {
        "border": border, "border.variant": bvar, "border.focused": acc, "border.selected": acc,
        "border.transparent": "#00000000", "border.disabled": bdis,
        "elevated_surface.background": elev, "surface.background": panel, "background": panel,
        "element.background": el_bg, "element.hover": el_h, "element.active": el_a,
        "element.selected": sel, "element.disabled": bdis, "element.selection_background": alpha(acc, .25),
        "drop_target.background": alpha(acc, .2), "drop_target.border": acc,
        "ghost_element.background": "#00000000", "ghost_element.hover": el_h,
        "ghost_element.active": el_a, "ghost_element.selected": sel, "ghost_element.disabled": bdis,
        "text": tx, "text.muted": muted, "text.placeholder": cm, "text.disabled": dis, "text.accent": acc,
        "icon": icon, "icon.muted": cm, "icon.disabled": dis, "icon.placeholder": cm, "icon.accent": acc,
        "debugger.accent": red,
        "status_bar.background": panel, "title_bar.background": panel,
        "title_bar.inactive_background": panel, "toolbar.background": bg, "tab_bar.background": panel,
        "tab.inactive_background": panel, "tab.active_background": bg,
        "search.match_background": alpha(blue, .3), "search.active_match_background": alpha(orange, .45),
        "panel.background": panel, "panel.focused_border": acc, "panel.indent_guide": bvar,
        "panel.indent_guide_hover": border, "panel.indent_guide_active": border,
        "panel.overlay_background": elev, "panel.overlay_hover": el_h,
        "pane.focused_border": bvar, "pane_group.border": border,
        "scrollbar_thumb.background": alpha(tx, .15),
        "scrollbar.thumb.background": alpha(tx, .15), "scrollbar.thumb.hover_background": alpha(tx, .3),
        "scrollbar.thumb.active_background": alpha(acc, .6), "scrollbar.thumb.border": "#00000000",
        "scrollbar.track.background": "#00000000", "scrollbar.track.border": bvar,
        "minimap.thumb.background": alpha(tx, .1), "minimap.thumb.hover_background": alpha(tx, .15),
        "minimap.thumb.active_background": alpha(acc, .3), "minimap.thumb.border": "#00000000",
        "editor.foreground": tx, "editor.code_lens.foreground": cm, "editor.background": bg,
        "editor.gutter.background": bg, "editor.subheader.background": panel,
        "editor.active_line.background": lift(bg, .05), "editor.highlighted_line.background": sel,
        "editor.debugger_active_line.background": alpha(yellow, .15),
        "editor.line_number": linenum, "editor.active_line_number": tx,
        "editor.hover_line_number": mix(linenum, tx, .5), "editor.invisible": linenum,
        "editor.wrap_guide": guide, "editor.active_wrap_guide": guide_a,
        "editor.indent_guide": guide, "editor.indent_guide_active": guide_a,
        "editor.document_highlight.read_background": alpha(blue, .15),
        "editor.document_highlight.write_background": alpha(acc, .2),
        "editor.document_highlight.bracket_background": alpha(acc, .2),
        "editor.diff_hunk.added.background": alpha(green, .18),
        "editor.diff_hunk.added.hollow_background": alpha(green, .08),
        "editor.diff_hunk.added.hollow_border": alpha(green, .5),
        "editor.diff_hunk.deleted.background": alpha(red, .18),
        "editor.diff_hunk.deleted.hollow_background": alpha(red, .08),
        "editor.diff_hunk.deleted.hollow_border": alpha(red, .5),
        "terminal.background": bg, "terminal.foreground": tx, "terminal.ansi.background": bg,
        "terminal.bright_foreground": mix(tx, "#FFFFFF", .3) if dark else mix(tx, "#000000", .3),
        "terminal.dim_foreground": cm,
        "link_text.hover": blue,
        "version_control.added": green, "version_control.deleted": red,
        "version_control.modified": yellow, "version_control.renamed": blue,
        "version_control.conflict": orange, "version_control.ignored": cm,
        "version_control.word_added": alpha(green, .25), "version_control.word_deleted": alpha(red, .25),
        "version_control.conflict_marker.ours": alpha(green, .12),
        "version_control.conflict_marker.theirs": alpha(blue, .12),
    }
    vim = {"normal": acc, "insert": green, "replace": red, "visual": purple, "visual_line": purple,
           "visual_block": purple, "helix_normal": acc, "helix_select": purple}
    for mode, col in vim.items():
        S[f"vim.{mode}.background"] = col
        S[f"vim.{mode}.foreground"] = on(col)
    S["vim.yank.background"] = alpha(yellow, .35)
    S["vim.helix_jump_label.foreground"] = acc
    for k, col in ansi(c, dark, v["_rules"]).items():
        S["terminal.ansi." + k] = col

    def stat(name, col):
        S[name] = col
        S[name + ".background"] = mix(bg, col, .14)
        S[name + ".border"] = mix(bg, col, .38)
    for name, col in [("error", red), ("warning", yellow), ("success", green), ("info", blue),
                      ("hint", cm), ("created", green), ("modified", yellow), ("deleted", red),
                      ("conflict", orange), ("renamed", blue), ("ignored", cm), ("hidden", cm),
                      ("predictive", cm), ("unreachable", cm)]:
        stat(name, col)
    S["accents"] = [acc, yellow, aqua, purple, green, blue, orange]
    S["players"] = [{"cursor": p, "background": p, "selection": alpha(p, .25)}
                    for p in (acc, blue, orange, purple, aqua, red, yellow, green)]
    S["syntax"] = zed_syntax(c, v["_rules"])
    return {"name": v["name"], "appearance": v["appearance"], "style": S}


# ---------------------------------------------------------------- windows terminal
def wt_scheme(v):
    c, dark = v["colors"], is_dark(v)
    a = ansi(c, dark, v["_rules"])
    wt = {"name": v["name"], "background": c["bg"], "foreground": c["tx"],
          "cursorColor": c["accent"], "selectionBackground": c["sel"]}
    names = {"black": "black", "red": "red", "green": "green", "yellow": "yellow",
             "blue": "blue", "magenta": "purple", "cyan": "cyan", "white": "white"}
    for src, dst in names.items():
        wt[dst] = a[src]
        wt["bright" + dst[0].upper() + dst[1:]] = a["bright_" + src]
    return wt


# ---------------------------------------------------------------- obsidian (AnuPpuccin)
def ctp_palette(v):
    c = v["colors"]
    bg, tx = c["bg"], c["tx"]
    dark = is_dark(v)
    crust = mix(c["panel"], "#000000", .12) if dark else mix(c["panel"], tx, .06)
    return {
        "rosewater": mix(c["orange"], tx, .45), "flamingo": c["accent"],
        "pink": mix(c["purple"], c["red"], .35), "mauve": c["purple"], "red": c["red"],
        "maroon": mix(c["red"], c["accent"], .5), "peach": c["orange"],
        "yellow": c["yellow"], "green": c["green"], "teal": c["aqua"], "sky": mix(c["aqua"], c["blue"], .5),
        "sapphire": mix(c["blue"], c["aqua"], .3), "blue": c["blue"], "lavender": mix(c["blue"], c["purple"], .5),
        "text": tx, "subtext1": mix(tx, bg, .15), "subtext0": mix(tx, bg, .28),
        "overlay2": mix(bg, tx, .62), "overlay1": mix(bg, tx, .52), "overlay0": c["cm"],
        "surface2": mix(bg, tx, .24), "surface1": mix(bg, tx, .16), "surface0": mix(bg, tx, .09),
        "base": bg, "mantle": c["panel"], "crust": crust,
    }


def slug(text):
    return "".join(ch if ch.isalnum() else "-" for ch in text.lower()).strip("-")


def obsidian_units(fam):
    """One snippet per family, unless two variants share an appearance (they would
    overwrite each other), in which case one snippet per variant."""
    apps = [v["appearance"] for v in fam["variants"]]
    if len(apps) == len(set(apps)):
        return [(fam["file"], fam["name"], fam["variants"])]
    return [(slug(v["name"]), v["name"], [v]) for v in fam["variants"]]


def obsidian_css(pkg, title, vs):
    lines = [f"/* {pkg['name']} - {title}, for the AnuPpuccin Obsidian theme.",
             f"   Generated by tools/build.py from palettes.json. Do not edit by hand.",
             "   Enable one snippet at a time in Settings > Appearance > CSS snippets. */", ""]
    for v in vs:
        sel = ".theme-dark" if is_dark(v) else ".theme-light"
        lines.append(f"/* {v['name']} */")
        lines.append(sel + " {")
        for k, col in ctp_palette(v).items():
            lines.append(f"  --ctp-custom-{k}: {', '.join(str(x) for x in h2r(col))};")
        lines.append("}")
        lines.append("")
    return "\n".join(lines)


# ---------------------------------------------------------------- claude code
# Custom theme files for ~/.claude/themes/<slug>.json. Claude Code draws on the terminal's own
# background, so these assume the matching Windows Terminal scheme (terminal bg = `bg`).
def readable(col, bg, floor, dark):
    """col, nudged away from bg (same hue) until it reaches `floor` contrast."""
    return toward_contrast(col, bg, floor, "#FFFFFF" if dark else "#000000")


def tint(bg, col, t, fg, floor):
    """bg tinted toward col by up to t, backing off until fg keeps `floor` contrast on it."""
    while t > 0 and contrast(fg, mix(bg, col, t)) < floor:
        t -= 0.01
    return mix(bg, col, max(t, 0))


def claude_code_theme(v):
    c, dark, r = v["colors"], is_dark(v), v["_rules"]
    bg, tx, cm, acc = c["bg"], c["tx"], c["cm"], c["accent"]
    floor, faint = r["ansi"], r["ansi_dim"]
    shimmer = lambda col: mix(col, tx, 0.35)
    pink = mix(c["purple"], c["red"], 0.4)
    indigo = mix(c["blue"], c["purple"], 0.5)
    o = {
        # text and accents
        "claude": acc, "claudeShimmer": shimmer(acc), "text": tx, "inverseText": bg,
        "inactive": readable(cm, bg, faint, dark), "inactiveShimmer": shimmer(cm),
        "subtle": soft(tx, bg, 0.55, faint), "suggestion": c["blue"],
        "permission": c["blue"], "permissionShimmer": shimmer(c["blue"]), "remember": c["purple"],
        # status
        "success": c["green"], "error": c["red"], "warning": c["yellow"], "warningShimmer": shimmer(c["yellow"]),
        "merged": c["purple"],
        # input box and modes
        "promptBorder": mix(bg, tx, 0.35), "promptBorderShimmer": mix(bg, tx, 0.6),
        "planMode": c["aqua"], "autoAccept": c["purple"], "bashBorder": c["orange"], "ide": c["blue"],
        "fastMode": c["orange"], "fastModeShimmer": shimmer(c["orange"]), "effortUltra": c["purple"],
        # diffs: tinted backgrounds, text stays readable on them (checked)
        "diffAdded": tint(bg, c["green"], 0.2, tx, floor), "diffRemoved": tint(bg, c["red"], 0.2, tx, floor),
        "diffAddedDimmed": tint(bg, c["green"], 0.09, tx, floor), "diffRemovedDimmed": tint(bg, c["red"], 0.09, tx, floor),
        "diffAddedWord": tint(bg, c["green"], 0.36, tx, floor), "diffRemovedWord": tint(bg, c["red"], 0.36, tx, floor),
        # transcript backgrounds
        "userMessageBackground": mix(bg, tx, 0.07), "userMessageBackgroundHover": mix(bg, tx, 0.12),
        "bashMessageBackgroundColor": tint(bg, c["orange"], 0.1, tx, floor),
        "memoryBackgroundColor": tint(bg, c["purple"], 0.1, tx, floor),
        "selectionBg": c["sel"],
        # usage meter and labels
        "rate_limit_fill": acc, "rate_limit_empty": mix(bg, tx, 0.2),
        "briefLabelYou": c["blue"], "briefLabelClaude": acc,
    }
    for name, col in [("red", c["red"]), ("blue", c["blue"]), ("green", c["green"]), ("yellow", c["yellow"]),
                      ("purple", c["purple"]), ("orange", c["orange"]), ("pink", pink), ("cyan", c["aqua"])]:
        o[f"{name}_FOR_SUBAGENTS_ONLY"] = readable(col, bg, floor, dark)
    for name, col in [("red", c["red"]), ("orange", c["orange"]), ("yellow", c["yellow"]), ("green", c["green"]),
                      ("blue", c["blue"]), ("indigo", indigo), ("violet", c["purple"])]:
        o[f"rainbow_{name}"] = readable(col, bg, floor, dark)
        o[f"rainbow_{name}_shimmer"] = shimmer(col)
    return {"name": v["name"], "base": "dark" if dark else "light", "overrides": o}


# Tokens drawn as text on the terminal background, and the background tokens text sits on.
CC_TEXT = ["claude", "text", "suggestion", "permission", "remember", "success", "error", "warning", "merged",
           "planMode", "autoAccept", "ide", "fastMode", "effortUltra", "briefLabelYou", "briefLabelClaude"]
CC_FAINT = ["inactive", "subtle"]
CC_TEXT_BG = ["diffAdded", "diffRemoved", "diffAddedDimmed", "diffRemovedDimmed", "diffAddedWord",
              "diffRemovedWord", "userMessageBackground", "userMessageBackgroundHover",
              "bashMessageBackgroundColor", "memoryBackgroundColor", "selectionBg"]


# ---------------------------------------------------------------- opencode
# Theme files for ~/.config/opencode/themes/<slug>.json. opencode paints its own background.
def opencode_theme(v):
    c, dark, r = v["colors"], is_dark(v), v["_rules"]
    bg, panel, tx, cm, acc = c["bg"], c["panel"], c["tx"], c["cm"], c["accent"]
    floor, faint = r["ansi"], r["ansi_dim"]
    on_acc = bg if contrast(bg, acc) >= contrast(tx, acc) else tx

    def ink(col, minimum=floor):  # readable on both the editor background and the side panel
        return readable(readable(col, bg, minimum, dark), panel, minimum, dark)
    added, removed = tint(bg, c["green"], 0.14, tx, floor), tint(bg, c["red"], 0.14, tx, floor)
    added_ln, removed_ln = tint(bg, c["green"], 0.22, tx, floor), tint(bg, c["red"], 0.22, tx, floor)
    line_num = readable(readable(cm, added_ln, faint, dark), removed_ln, faint, dark)
    t = {
        "primary": ink(acc), "secondary": ink(c["blue"]), "accent": ink(c["purple"]),
        "error": ink(c["red"]), "warning": ink(c["yellow"]), "success": ink(c["green"]), "info": ink(c["aqua"]),
        "text": tx, "textMuted": ink(cm, faint), "selectedListItemText": on_acc,
        "background": bg, "backgroundPanel": panel, "backgroundElement": mix(bg, tx, 0.06),
        "backgroundMenu": panel,
        "border": mix(panel, tx, 0.14), "borderActive": acc, "borderSubtle": mix(panel, tx, 0.08),
        "diffAdded": c["green"], "diffRemoved": c["red"], "diffContext": cm, "diffHunkHeader": c["blue"],
        "diffHighlightAdded": c["green"], "diffHighlightRemoved": c["red"],
        "diffAddedBg": added, "diffRemovedBg": removed, "diffContextBg": panel, "diffLineNumber": line_num,
        "diffAddedLineNumberBg": added_ln, "diffRemovedLineNumberBg": removed_ln,
        # markdown follows the Gruvbox syntax groups used in Zed (title green, links purple/aqua,
        # literal code and emphasis blue, list markers plain text)
        "markdownText": tx, "markdownHeading": c["green"], "markdownLink": c["purple"],
        "markdownLinkText": c["aqua"], "markdownCode": c["blue"], "markdownBlockQuote": cm,
        "markdownEmph": c["blue"], "markdownStrong": c["blue"], "markdownHorizontalRule": cm,
        "markdownListItem": tx, "markdownListEnumeration": tx, "markdownImage": c["purple"],
        "markdownImageText": c["aqua"], "markdownCodeBlock": tx,
        "syntaxComment": cm, "syntaxKeyword": c["red"], "syntaxFunction": c["green"], "syntaxVariable": tx,
        "syntaxString": c["green"], "syntaxNumber": c["purple"], "syntaxType": c["yellow"],
        "syntaxOperator": c["aqua"], "syntaxPunctuation": soft(tx, bg, 0.16, r["syntax"]),
    }
    return {"$schema": "https://opencode.ai/theme.json", "theme": t}


OC_TEXT_BG = ["background", "backgroundPanel", "backgroundElement", "backgroundMenu", "diffAddedBg",
              "diffRemovedBg", "diffContextBg", "diffAddedLineNumberBg", "diffRemovedLineNumberBg"]


def port_check(v):
    """Readability of the Claude Code and opencode ports (same floors as the terminal)."""
    c, r, name = v["colors"], v["_rules"], v["name"]
    probs = []

    def need(fg, bgc, floor, what):
        got = contrast(fg, bgc)
        if got + 1e-9 < floor:
            probs.append(f"{name}: {what} is {got:.2f}:1, needs {floor}")
    cc = claude_code_theme(v)["overrides"]
    for k in CC_TEXT + [k for k in cc if k.endswith("_FOR_SUBAGENTS_ONLY")]:
        need(cc[k], c["bg"], r["ansi"], f"claude-code {k} on the terminal background")
    for k in CC_FAINT:
        need(cc[k], c["bg"], r["ansi_dim"], f"claude-code {k} on the terminal background")
    for k in CC_TEXT_BG:
        need(c["tx"], cc[k], r["ansi"], f"claude-code text on {k}")
    for k in ("claude", "success", "error", "warning", "permission"):
        need(cc["inverseText"], cc[k], r["ansi"], f"claude-code inverseText on {k}")
    oc = opencode_theme(v)["theme"]
    for k in OC_TEXT_BG:
        need(oc["text"], oc[k], r["ansi"], f"opencode text on {k}")
    for k in ("background", "backgroundPanel", "backgroundElement", "backgroundMenu"):
        need(oc["textMuted"], oc[k], r["ansi_dim"], f"opencode textMuted on {k}")
    for k in ("diffAddedLineNumberBg", "diffRemovedLineNumberBg"):
        need(oc["diffLineNumber"], oc[k], r["ansi_dim"], f"opencode diffLineNumber on {k}")
    need(oc["selectedListItemText"], oc["primary"], r["ansi"], "opencode selectedListItemText on primary")
    for k in ("primary", "secondary", "accent", "error", "warning", "success", "info"):
        for b in ("background", "backgroundPanel"):
            need(oc[k], oc[b], r["ansi"], f"opencode {k} on {b}")
    return probs


# ---------------------------------------------------------------- validation
def resolve_key(syntax, cap):
    parts = cap.split(".")
    for i in range(len(parts), 0, -1):
        k = ".".join(parts[:i])
        if k in syntax:
            return k
    return None


def group_of_keys():
    out = {}
    for group, keys in list(GROUPS.items()) + list(EXTRA.items()):
        for k in keys:
            out[k] = group
    return out


def over(bg, rgba):
    """Opaque color of a #RRGGBBAA overlay drawn on bg."""
    return mix(bg, rgba[:7], int(rgba[7:9], 16) / 255 if len(rgba) == 9 else 1)


def terminal_check(v, style):
    """Terminal readability (see AGENTS.md). Returns (problems, worst-case row for the -v table)."""
    c, r, name, bg, dark = v["colors"], v["_rules"], v["name"], v["colors"]["bg"], is_dark(v)
    wt = wt_scheme(v)
    probs = []
    slot = {k[len("terminal.ansi."):]: col for k, col in style.items()
            if k.startswith("terminal.ansi.") and k != "terminal.ansi.background"}
    text_slots = {k: col for k, col in slot.items() if not k.startswith("dim_")}
    text_slots.update({"wt." + k: col for k, col in wt.items()
                       if k not in ("name", "background", "foreground", "cursorColor", "selectionBackground")})
    dim_slots = {k: col for k, col in slot.items() if k.startswith("dim_")}
    dim_slots["dim_foreground"] = style["terminal.dim_foreground"]
    fg_slots = {"foreground": style["terminal.foreground"], "bright_foreground": style["terminal.bright_foreground"],
                "wt.foreground": wt["foreground"]}
    sel_text = {"zed selection": contrast(c["tx"], over(bg, style["players"][0]["selection"])),
                "wt selectionBackground": contrast(wt["foreground"], wt["selectionBackground"])}

    def worst(slots, floor, label):
        k, col = min(slots.items(), key=lambda kv: contrast(kv[1], bg))
        got = contrast(col, bg)
        for kk, cc in slots.items():
            if contrast(cc, bg) + 1e-9 < floor:
                probs.append(f"{name}: terminal {kk} {cc} is {contrast(cc, bg):.2f}:1 on bg, needs {floor} ({label})")
        return k, got
    w_text = worst(text_slots, r["ansi"], "programs print text with it")
    w_dim = worst(dim_slots, r["ansi_dim"], "faint, never invisible")
    w_fg = worst(fg_slots, r["text"], "terminal text")
    for what, got in sel_text.items():
        if got + 1e-9 < r["ansi"]:
            probs.append(f"{name}: text on {what} is {got:.2f}:1, needs {r['ansi']}")
    # greys stay meaningful: partners apart, all apart from the foreground, natural order
    fg = c["tx"]
    pairs = [("black", "bright_black"), ("white", "bright_white")] + \
            [(g, "fg") for g in ("black", "bright_black", "white", "bright_white")]
    seps = []
    for a, b in pairs:
        d = delta_e(slot[a], fg if b == "fg" else slot[b])
        seps.append(d)
        if d + 1e-9 < r["ansi_sep"]:
            probs.append(f"{name}: terminal {a} and {b} look alike (dE {d:.1f} < {r['ansi_sep']})")
    greys = ("black", "bright_black", "white", "bright_white")
    L = {g: lab(slot[g])[0] for g in greys}
    sign = 1 if dark else -1  # "brighter" means further from the background
    if any(sign * (L["black"] - L[g]) > 0.5 for g in greys):
        probs.append(f"{name}: terminal black is not the grey closest to the background")
    if any(sign * (L[g] - L["bright_white"]) > 0.5 for g in greys):
        probs.append(f"{name}: terminal bright_white is not the most emphasised grey")
    if contrast(slot["bright_black"], bg) >= contrast(fg, bg):
        probs.append(f"{name}: terminal bright_black is not quieter than the foreground")
    row = (name, w_text, w_dim, w_fg, min(sel_text.values()), min(seps))
    return probs, row


def terminal_table(rows):
    out = [f"{'theme':20s} {'worst text slot':26s} {'worst dim slot':24s} {'worst fg':22s} {'on sel':>6s} {'grey dE':>7s}"]
    for name, (tk, tv), (dk, dv), (fk, fv), sel, sep in rows:
        out.append(f"{name:20s} {tk:18s}{tv:6.2f}:1 {dk:16s}{dv:6.2f}:1 {fk:14s}{fv:6.2f}:1 {sel:6.2f} {sep:7.1f}")
    return "\n".join(out)


def validate(data, ref, gruv, themes, rows=None):
    errors, warnings = [], []
    for (_, v), t in zip(variants(data), themes):
        probs, row = terminal_check(v, t["style"])
        errors.extend(probs)
        errors.extend(port_check(v))
        if rows is not None:
            rows.append(row)
    want = set(ref["color_keys"]) | set(ref["status_keys"])
    pending = []
    for fam, v in variants(data):
        c, name, r = v["colors"], v["name"], v["_rules"]
        missing = [k for k in ROLES if k not in c]
        if missing:
            errors.append(f"{name}: palette missing roles {missing}")
            continue
        unknown = sorted(set(c) - set(ROLES))
        if unknown:
            errors.append(f"{name}: palette has unknown roles {unknown}")
        problems = []
        bg = c["bg"]
        checks = [("tx", r["text"]), ("cm", r["comment"]), ("accent", r["syntax"])] + [(k, r["syntax"]) for k in HUES]
        for k, target in checks:
            got = contrast(c[k], bg)
            if got + 1e-9 < target:
                problems.append(f"{name}: {k} {c[k]} is {got:.2f}:1 on bg, needs {target}")
        # Gruvbox-style sharpness: hues far apart, saturated enough, spread in lightness
        pool = HUES + ["tx"]
        for i, a in enumerate(pool):
            for b in pool[i + 1:]:
                d = delta_e(c[a], c[b])
                if d < r["distinct"]:
                    problems.append(f"{name}: {a} and {b} look too similar (dE {d:.1f} < {r['distinct']})")
        sh = sharpness(c)
        if sh["chroma"] + 1e-9 < r["chroma"]:
            problems.append(f"{name}: hues too dull (avg chroma {sh['chroma']:.1f} < {r['chroma']})")
        if sh["spread"] + 1e-9 < r["spread"]:
            problems.append(f"{name}: hues too flat (L* spread {sh['spread']:.1f} < {r['spread']})")
        if v.get("pending"):
            pending.append(f"{name} ({len(problems)} issue(s))")
        else:
            errors.extend(problems)
    if pending:
        warnings.append("not yet migrated to the Gruvbox structure, sharpness not enforced: " + ", ".join(pending))
    names = [v["name"] for _, v in variants(data)]
    dupes = {n for n in names if names.count(n) > 1}
    if dupes:
        errors.append(f"duplicate variant names: {sorted(dupes)}")
    for t in themes:
        style = t["style"]
        absent = sorted(want - set(style))
        if absent:
            errors.append(f"{t['name']}: missing Zed keys {absent}")
        unknown = sorted(set(style) - want - {"syntax", "players", "accents"})
        if unknown:
            warnings.append(f"{t['name']}: keys Zed does not know {unknown}")
        for k, col in style.items():
            if isinstance(col, str) and k != "syntax" and not (col.startswith("#") and len(col) in (7, 9)):
                errors.append(f"{t['name']}: bad color {k}={col}")
        for label in ("normal", "insert", "replace", "visual"):
            got = contrast(style[f"vim.{label}.foreground"], style[f"vim.{label}.background"])
            if got < 4.5:
                warnings.append(f"{t['name']}: vim {label} label contrast {got:.1f}")
    # Structure: the GROUPS table must still match Zed's Gruvbox, and our themes must have every key it has.
    groups = group_of_keys()
    for gt in gruv["themes"]:
        if gt["name"] not in ("Gruvbox Dark", "Gruvbox Light"):
            continue
        gsyn = gt["style"]["syntax"]
        for group, keys in GROUPS.items():
            base = gsyn[keys[0]]["color"]
            for k in keys[1:]:
                if delta_e(gsyn[k]["color"][:7], base[:7]) > 2:
                    errors.append(f"GROUPS: {k} is not in the same group as {keys[0]} in {gt['name']}")
        for k in gsyn:
            if themes and k not in themes[0]["style"]["syntax"]:
                errors.append(f"syntax key {k} from {gt['name']} is missing from our themes")
    # Every grammar capture must land on a key that belongs to a known group.
    keys = set(themes[0]["style"]["syntax"]) if themes else set()
    unresolved, ungrouped = [], set()
    for cap in ref["captures"]:
        if cap.startswith("_") or cap in PLAIN_CAPTURES:
            continue
        k = resolve_key(keys, cap)
        if k is None:
            unresolved.append(cap)
        elif k not in groups and k.split(".")[0] not in ("comment", "punctuation", "string", "hint",
                                                          "predictive", "diff"):
            ungrouped.add(k)
    if unresolved:
        errors.append(f"captures with no theme key (would render as plain text): {sorted(unresolved)}")
    if ungrouped:
        errors.append(f"syntax keys outside the Gruvbox groups: {sorted(ungrouped)}")
    return errors, warnings


def fix(data):
    changed = []
    for fam, v in variants(data):
        c, r = v["colors"], rules_for(data, v)
        # Blend toward black (light themes) or white (dark themes): keeps hue and saturation.
        anchor = "#FFFFFF" if is_dark(v) else "#000000"
        targets = [("tx", r["text"]), ("cm", r["comment"]), ("accent", r["syntax"])] + [(k, r["syntax"]) for k in HUES]
        for k, target in targets:
            new = toward_contrast(c[k], c["bg"], target, anchor)
            if new != c[k]:
                changed.append(f"{v['name']}: {k} {c[k]} -> {new}")
                c[k] = new
    return changed


# ---------------------------------------------------------------- main
def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--fix", action="store_true", help="adjust failing colors and save palettes.json")
    ap.add_argument("--check", action="store_true", help="validate only, write nothing")
    ap.add_argument("-v", "--verbose", action="store_true", help="print the per-theme terminal contrast table")
    args = ap.parse_args()

    data, ref, gruv = load()
    pkg = data["package"]
    if args.fix:
        for line in fix(data):
            print("fixed", line)
        PALETTES.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
    for _, v in variants(data):
        v["_rules"] = rules_for(data, v)

    themes_by_family = {f["file"]: [zed_theme(v) for v in f["variants"]] for f in data["families"]}
    all_themes = [t for ts in themes_by_family.values() for t in ts]
    rows = []
    errors, warnings = validate(data, ref, gruv, all_themes, rows)
    if args.verbose:
        print(terminal_table(rows) + "\n")
    for w in warnings:
        print("warning:", w)
    for e in errors:
        print("ERROR:", e)
    if errors:
        print(f"\n{len(errors)} error(s). Nothing written. Try: python tools/build.py --fix")
        sys.exit(1)
    if args.check:
        print("check passed")
        return

    out_themes = ROOT / "themes"
    out_themes.mkdir(exist_ok=True)
    for old in out_themes.glob("*.json"):
        old.unlink()
    for fam in data["families"]:
        doc = {"$schema": SCHEMA, "name": fam["name"], "author": pkg["author"], "themes": themes_by_family[fam["file"]]}
        (out_themes / f"{fam['file']}.json").write_text(json.dumps(doc, indent=2) + "\n", encoding="utf-8")

    wt_dir = ROOT / "ports" / "windows-terminal"
    wt_dir.mkdir(parents=True, exist_ok=True)
    wt = {"$help": "Windows Terminal fragment. Install with install.ps1.",
          "schemes": [wt_scheme(v) for _, v in variants(data)]}
    (wt_dir / f"{pkg['id']}.json").write_text(json.dumps(wt, indent=2) + "\n", encoding="utf-8")

    ob_dir = ROOT / "ports" / "obsidian"
    ob_dir.mkdir(parents=True, exist_ok=True)
    for old in ob_dir.glob("*.css"):
        old.unlink()
    snippets = 0
    for fam in data["families"]:
        for name, title, vs in obsidian_units(fam):
            (ob_dir / f"{pkg['id']}-{name}.css").write_text(obsidian_css(pkg, title, vs) + "\n", encoding="utf-8")
            snippets += 1

    for port, gen in (("claude-code", claude_code_theme), ("opencode", opencode_theme)):
        d = ROOT / "ports" / port
        d.mkdir(parents=True, exist_ok=True)
        for old in d.glob("*.json"):
            old.unlink()
        for _, v in variants(data):
            (d / f"{slug(v['name'])}.json").write_text(json.dumps(gen(v), indent=2) + "\n", encoding="utf-8")

    n = len(all_themes)
    print(f"built {n} themes: Zed ({len(data['families'])} files), Windows Terminal ({n} schemes), "
          f"Obsidian ({snippets} snippets), Claude Code ({n}), opencode ({n})")


if __name__ == "__main__":
    main()
