#!/usr/bin/env python3
"""Build every output of this theme package from palettes.json.

Usage:
    python tools/build.py          # validate, then write all outputs
    python tools/build.py --fix    # nudge colors that miss contrast targets, save palettes.json, then build
    python tools/build.py --check  # validate only, write nothing (exit 1 on errors)

Outputs (all generated, never edit by hand):
    themes/<family>.json                      Zed theme families
    ports/windows-terminal/<package-id>.json  Windows Terminal fragment with every scheme
    ports/obsidian/<package-id>-<family>.css  AnuPpuccin snippets, one per family
    preview/index.html                        Static preview of every variant

Requires Python 3.9+, no third-party packages.
"""
import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PALETTES = ROOT / "palettes.json"
REFERENCE = ROOT / "reference" / "zed.json"
SCHEMA = "https://zed.dev/schema/themes/v0.2.0.json"

ROLES = ["bg", "panel", "tx", "cm", "kw", "st", "fn", "nu", "ty", "er", "green", "yellow", "blue", "sel"]
SYNTAX_ROLES = ["kw", "st", "fn", "nu", "ty"]
ANSI_ROLES = ["er", "green", "yellow", "blue", "nu", "fn"]
DEFAULT_RULES = {"text": 7.0, "comment": 4.2, "syntax": 4.5, "ansi": 4.5, "distinct": 12.0}

# Captures that intentionally render in the default text color (no theme key needed).
PLAIN_CAPTURES = {"none", "nested", "text.jsx"}


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


# ---------------------------------------------------------------- data
def load():
    data = json.loads(PALETTES.read_text(encoding="utf-8"))
    ref = json.loads(REFERENCE.read_text(encoding="utf-8"))
    return data, ref


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
def ansi(c, dark, tbg):
    tx = c["tx"]
    base = {
        "black": mix(c["bg"], tx, 0.25) if dark else tx,
        "red": c["er"], "green": c["green"], "yellow": c["yellow"],
        "blue": c["blue"], "magenta": c["nu"], "cyan": c["fn"],
        "white": mix(c["bg"], tx, 0.75) if dark else mix(c["bg"], tx, 0.3),
    }
    out = {}
    for name, col in base.items():
        out[name] = col
        if name == "black":
            out["bright_black"] = c["cm"]
        elif name == "white":
            out["bright_white"] = mix(tx, "#FFFFFF", 0.3) if dark else mix(c["bg"], "#FFFFFF", 0.5)
        else:
            out["bright_" + name] = mix(col, "#FFFFFF", 0.15) if dark else mix(col, "#000000", 0.12)
        out["dim_" + name] = mix(col, tbg, 0.35)
    return out


# ---------------------------------------------------------------- zed
def zed_syntax(c, opts):
    tx, bg, cm = c["tx"], c["bg"], c["cm"]
    kw, st, fn, nu, ty = c["kw"], c["st"], c["fn"], c["nu"], c["ty"]
    floor = 4.5
    punct = soft(tx, bg, 0.30, floor)
    op = soft(tx, bg, 0.22, floor)
    doc = mix(cm, tx, 0.2)
    it = {"font_style": "italic"}
    w = opts.get("emphasis_weight")
    strong = {"font_weight": w} if w else {}

    def s(color, **extra):
        d = {"color": color}
        d.update(extra)
        return d

    return {
        # comments
        "comment": s(cm, **it), "comment.doc": s(doc, **it), "string.doc": s(doc, **it),
        # keywords and friends
        "keyword": s(kw, **strong), "preproc": s(kw), "storageclass": s(kw), "import": s(kw),
        "selector": s(kw), "selector.pseudo": s(nu), "media": s(kw), "keyframes": s(kw),
        "supports": s(kw), "charset": s(kw),
        "variable.special": s(kw, **it), "variable.builtin": s(kw, **it),
        # types (includes type.builtin like `unsigned int`, classes, interfaces)
        "type": s(ty, **strong), "constructor": s(ty), "concept": s(ty), "enum": s(ty),
        "tag.component": s(ty), "lifetime": s(nu, **it),
        # functions
        "function": s(fn), "function.decorator": s(nu), "property.json_key": s(fn),
        # literals
        "string": s(st), "string.escape": s(nu), "string.regex": s(nu), "string.special": s(st),
        "string.special.symbol": s(nu), "text.literal": s(st),
        "number": s(nu), "boolean": s(nu), "constant": s(nu), "variant": s(nu),
        "attribute": s(nu), "label": s(nu),
        # plain identifiers stay in the text color on purpose
        "variable": s(tx), "variable.parameter": s(tx), "property": s(tx), "namespace": s(tx),
        "module": s(tx), "embedded": s(tx), "primary": s(tx), "text": s(tx),
        # punctuation and operators
        "operator": s(op), "punctuation": s(punct), "punctuation.special": s(kw),
        "punctuation.list_marker": s(kw), "punctuation.markup": s(kw), "punctuation.embedded": s(kw),
        # markup
        "tag": s(kw), "tag.doctype": s(cm), "title": s(kw, font_weight=700),
        "markup.heading": s(kw, font_weight=700), "markup.link": s(fn),
        "emphasis": s(tx, **it), "emphasis.strong": s(tx, font_weight=700),
        "strikethrough": s(cm), "link_text": s(fn), "link_uri": s(st),
        # diff and misc
        "diff.plus": s(c["green"]), "diff.minus": s(c["er"]), "diff.delta": s(c["yellow"]),
        "warning": s(c["yellow"]), "hint": s(cm), "predictive": s(cm, **it),
    }


def zed_theme(v):
    c, dark = v["colors"], is_dark(v)
    bg, panel, tx, cm = c["bg"], c["panel"], c["tx"], c["cm"]
    kw, st, fn, nu, er = c["kw"], c["st"], c["fn"], c["nu"], c["er"]
    green, yellow, blue, sel = c["green"], c["yellow"], c["blue"], c["sel"]

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
        "border": border, "border.variant": bvar, "border.focused": fn, "border.selected": kw,
        "border.transparent": "#00000000", "border.disabled": bdis,
        "elevated_surface.background": elev, "surface.background": panel, "background": panel,
        "element.background": el_bg, "element.hover": el_h, "element.active": el_a,
        "element.selected": sel, "element.disabled": bdis, "element.selection_background": alpha(kw, .25),
        "drop_target.background": alpha(kw, .2), "drop_target.border": kw,
        "ghost_element.background": "#00000000", "ghost_element.hover": el_h,
        "ghost_element.active": el_a, "ghost_element.selected": sel, "ghost_element.disabled": bdis,
        "text": tx, "text.muted": muted, "text.placeholder": cm, "text.disabled": dis, "text.accent": kw,
        "icon": icon, "icon.muted": cm, "icon.disabled": dis, "icon.placeholder": cm, "icon.accent": kw,
        "debugger.accent": er,
        "status_bar.background": panel, "title_bar.background": panel,
        "title_bar.inactive_background": panel, "toolbar.background": bg, "tab_bar.background": panel,
        "tab.inactive_background": panel, "tab.active_background": bg,
        "search.match_background": alpha(fn, .3), "search.active_match_background": alpha(st, .45),
        "panel.background": panel, "panel.focused_border": fn, "panel.indent_guide": bvar,
        "panel.indent_guide_hover": border, "panel.indent_guide_active": border,
        "panel.overlay_background": elev, "panel.overlay_hover": el_h,
        "pane.focused_border": bvar, "pane_group.border": border,
        "scrollbar_thumb.background": alpha(tx, .15),
        "scrollbar.thumb.background": alpha(tx, .15), "scrollbar.thumb.hover_background": alpha(tx, .3),
        "scrollbar.thumb.active_background": alpha(tx, .4), "scrollbar.thumb.border": "#00000000",
        "scrollbar.track.background": "#00000000", "scrollbar.track.border": bvar,
        "minimap.thumb.background": alpha(tx, .1), "minimap.thumb.hover_background": alpha(tx, .15),
        "minimap.thumb.active_background": alpha(tx, .2), "minimap.thumb.border": "#00000000",
        "editor.foreground": tx, "editor.code_lens.foreground": cm, "editor.background": bg,
        "editor.gutter.background": bg, "editor.subheader.background": panel,
        "editor.active_line.background": lift(bg, .05), "editor.highlighted_line.background": sel,
        "editor.debugger_active_line.background": alpha(yellow, .15),
        "editor.line_number": linenum, "editor.active_line_number": tx,
        "editor.hover_line_number": mix(linenum, tx, .5), "editor.invisible": linenum,
        "editor.wrap_guide": guide, "editor.active_wrap_guide": guide_a,
        "editor.indent_guide": guide, "editor.indent_guide_active": guide_a,
        "editor.document_highlight.read_background": alpha(fn, .15),
        "editor.document_highlight.write_background": alpha(kw, .2),
        "editor.document_highlight.bracket_background": alpha(kw, .2),
        "editor.diff_hunk.added.background": alpha(green, .18),
        "editor.diff_hunk.added.hollow_background": alpha(green, .08),
        "editor.diff_hunk.added.hollow_border": alpha(green, .5),
        "editor.diff_hunk.deleted.background": alpha(er, .18),
        "editor.diff_hunk.deleted.hollow_background": alpha(er, .08),
        "editor.diff_hunk.deleted.hollow_border": alpha(er, .5),
        "terminal.background": bg, "terminal.foreground": tx, "terminal.ansi.background": bg,
        "terminal.bright_foreground": mix(tx, "#FFFFFF", .3) if dark else mix(tx, "#000000", .3),
        "terminal.dim_foreground": cm,
        "link_text.hover": fn,
        "version_control.added": green, "version_control.deleted": er,
        "version_control.modified": yellow, "version_control.renamed": blue,
        "version_control.conflict": nu, "version_control.ignored": cm,
        "version_control.word_added": alpha(green, .25), "version_control.word_deleted": alpha(er, .25),
        "version_control.conflict_marker.ours": alpha(green, .12),
        "version_control.conflict_marker.theirs": alpha(blue, .12),
    }
    vim = {"normal": kw, "insert": green, "replace": er, "visual": nu, "visual_line": nu,
           "visual_block": nu, "helix_normal": kw, "helix_select": nu}
    for mode, col in vim.items():
        S[f"vim.{mode}.background"] = col
        S[f"vim.{mode}.foreground"] = on(col)
    S["vim.yank.background"] = alpha(st, .35)
    S["vim.helix_jump_label.foreground"] = kw
    for k, col in ansi(c, dark, bg).items():
        S["terminal.ansi." + k] = col

    def stat(name, col):
        S[name] = col
        S[name + ".background"] = mix(bg, col, .14)
        S[name + ".border"] = mix(bg, col, .38)
    for name, col in [("error", er), ("warning", yellow), ("success", green), ("info", fn),
                      ("hint", cm), ("created", green), ("modified", yellow), ("deleted", er),
                      ("conflict", nu), ("renamed", blue), ("ignored", cm), ("hidden", cm),
                      ("predictive", cm), ("unreachable", cm)]:
        stat(name, col)
    S["accents"] = [kw, st, fn, nu, c["ty"], blue, green]
    S["players"] = [{"cursor": p, "background": p, "selection": alpha(p, .25)}
                    for p in (kw, fn, st, nu, blue, green)]
    S["syntax"] = zed_syntax(c, v.get("options", {}))
    return {"name": v["name"], "appearance": v["appearance"], "style": S}


# ---------------------------------------------------------------- windows terminal
def wt_scheme(v):
    c, dark = v["colors"], is_dark(v)
    a = ansi(c, dark, c["bg"])
    wt = {"name": v["name"], "background": c["bg"], "foreground": c["tx"],
          "cursorColor": c["kw"], "selectionBackground": c["sel"]}
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
        "rosewater": mix(c["st"], tx, .35), "flamingo": mix(c["kw"], tx, .3), "pink": mix(c["kw"], c["nu"], .4),
        "mauve": c["kw"], "red": c["er"], "maroon": mix(c["er"], c["kw"], .5), "peach": c["st"],
        "yellow": c["yellow"], "green": c["green"], "teal": c["fn"], "sky": mix(c["fn"], c["blue"], .5),
        "sapphire": mix(c["blue"], c["fn"], .3), "blue": c["blue"], "lavender": c["nu"],
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


# ---------------------------------------------------------------- preview
def preview_html(pkg, data):
    cards = []
    for fam, v in variants(data):
        c = v["colors"]
        p = mix(c["tx"], c["bg"], .3)
        code = (
            f'<span style="color:{c["cm"]};font-style:italic">// default constructor is not available</span>\n'
            f'<span style="color:{c["kw"]}">class</span> <span style="color:{c["ty"]}">Shader</span> <span style="color:{p}">{{</span>\n'
            f'<span style="color:{c["kw"]}">public</span><span style="color:{p}">:</span>\n'
            f'    <span style="color:{c["ty"]}">unsigned int</span> id<span style="color:{p}">{{</span><span style="color:{c["nu"]}">0</span><span style="color:{p}">}};</span>\n'
            f'    <span style="color:{c["ty"]}">Shader</span><span style="color:{p}">()</span> = <span style="color:{c["kw"]}">delete</span><span style="color:{p}">;</span>\n'
            f'    <span style="color:{c["kw"]}">void</span> <span style="color:{c["fn"]}">use</span><span style="color:{p}">()</span> <span style="color:{c["kw"]}">const</span> <span style="color:{p}">{{</span> <span style="color:{c["fn"]}">glUseProgram</span><span style="color:{p}">(</span>id<span style="color:{p}">);</span> <span style="color:{p}">}}</span>\n'
            f'    <span style="color:{c["ty"]}">std</span>::<span style="color:{c["ty"]}">string</span> name = <span style="color:{c["st"]}">"shader\\n"</span><span style="color:{p}">;</span>\n'
            f'<span style="color:{p}">}};</span>'
        )
        cards.append(
            f'<section><h2>{v["name"]}</h2><div class="ed" style="background:{c["bg"]};color:{c["tx"]};border-color:{c["panel"]}">'
            f'<div class="bar" style="background:{c["panel"]};color:{c["cm"]}">shader.hpp</div><pre>{code}</pre></div></section>')
    return ("<!doctype html><meta charset=utf-8><title>" + pkg["name"] + " preview</title>"
            "<style>body{font-family:system-ui,sans-serif;background:#888;margin:24px}"
            "h2{font-size:14px;margin:18px 0 6px;color:#111}.ed{border-radius:8px;overflow:hidden;border:1px solid}"
            ".bar{padding:6px 12px;font-size:12px}pre{margin:0;padding:12px 16px;font:13px/1.7 ui-monospace,Consolas,monospace}</style>"
            "<h1 style='font-size:18px'>" + pkg["name"] + "</h1>" + "".join(cards))


# ---------------------------------------------------------------- validation
def validate(data, ref, themes):
    errors, warnings = [], []
    want = set(ref["color_keys"]) | set(ref["status_keys"])
    for fam, v in variants(data):
        c, name, r = v["colors"], v["name"], rules_for(data, v)
        missing = [k for k in ROLES if k not in c]
        if missing:
            errors.append(f"{name}: palette missing roles {missing}")
            continue
        bg = c["bg"]
        checks = [("tx", r["text"]), ("cm", r["comment"])] + [(k, r["syntax"]) for k in SYNTAX_ROLES + ["er"]]
        for k, target in checks:
            got = contrast(c[k], bg)
            if got + 1e-9 < target:
                errors.append(f"{name}: {k} {c[k]} is {got:.2f}:1 on bg, needs {target}")
        for k in ANSI_ROLES:
            got = contrast(c[k], bg)
            if got + 1e-9 < r["ansi"]:
                errors.append(f"{name}: terminal {k} {c[k]} is {got:.2f}:1 on bg, needs {r['ansi']}")
        pool = SYNTAX_ROLES + ["tx"]
        for i, a in enumerate(pool):
            for b in pool[i + 1:]:
                d = delta_e(c[a], c[b])
                if d < r["distinct"]:
                    warnings.append(f"{name}: {a} and {b} look similar (dE {d:.1f} < {r['distinct']})")
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
    keys = set(themes[0]["style"]["syntax"]) if themes else set()
    for cap in ref["captures"]:
        if cap.startswith("_") or cap in PLAIN_CAPTURES:
            continue
        parts = cap.split(".")
        if not any(".".join(parts[:i]) in keys for i in range(len(parts), 0, -1)):
            warnings.append(f"capture @{cap} has no theme key (renders as plain text)")
    return errors, warnings


def fix(data):
    changed = []
    for fam, v in variants(data):
        c, r = v["colors"], rules_for(data, v)
        # Blend toward black (light themes) or white (dark themes): keeps hue and saturation.
        anchor = "#FFFFFF" if is_dark(v) else "#000000"
        targets = [("tx", r["text"]), ("cm", r["comment"])] + [(k, r["syntax"]) for k in SYNTAX_ROLES + ["er"]]
        for k, target in targets:
            new = toward_contrast(c[k], c["bg"], target, anchor)
            if new != c[k]:
                changed.append(f"{v['name']}: {k} {c[k]} -> {new}")
                c[k] = new
        for k in ANSI_ROLES:
            new = toward_contrast(c[k], c["bg"], r["ansi"], anchor)
            if new != c[k]:
                changed.append(f"{v['name']}: {k} {c[k]} -> {new} (terminal)")
                c[k] = new
    return changed


# ---------------------------------------------------------------- main
def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--fix", action="store_true", help="adjust failing colors and save palettes.json")
    ap.add_argument("--check", action="store_true", help="validate only, write nothing")
    args = ap.parse_args()

    data, ref = load()
    pkg = data["package"]
    if args.fix:
        for line in fix(data):
            print("fixed", line)
        PALETTES.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")

    themes_by_family = {f["file"]: [zed_theme(v) for v in f["variants"]] for f in data["families"]}
    all_themes = [t for ts in themes_by_family.values() for t in ts]
    errors, warnings = validate(data, ref, all_themes)
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

    pv = ROOT / "preview"
    pv.mkdir(exist_ok=True)
    (pv / "index.html").write_text(preview_html(pkg, data), encoding="utf-8")

    n = len(all_themes)
    print(f"built {n} themes: Zed ({len(data['families'])} files), Windows Terminal ({n} schemes), "
          f"Obsidian ({snippets} snippets), preview")


if __name__ == "__main__":
    main()
