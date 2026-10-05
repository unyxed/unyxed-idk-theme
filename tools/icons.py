"""File and folder icon themes for coding, colored from palettes.json.

Called by build.py; run on its own with `python tools/icons.py` to rebuild only the icons.

Sources (shared by both theme repos, never edited per theme):
    tools/icons/catppuccin.json    the icon shapes: Catppuccin Icons (MIT, see tools/icons/LICENSE),
                                   in Iconify JSON form, drawn with Catppuccin Macchiato colors
    tools/icons/associations.json  which icon each file extension, file name, folder name and
                                   VS Code language id gets (edit this to add file types)

Every Catppuccin color is mapped to one of our palette roles (COLOR_ROLES), so each variant gets
the same shapes in its own colors: C and C++ in blue, shaders in purple, CMake in red, green and
blue, and so on. Folders are outlined in the theme's accent with a colored badge.

Outputs (all generated, never edit by hand):
    icons/<theme>/<icon>.svg        one set of SVGs per variant
    icon_themes/<package-id>.json   Zed icon theme family (one icon theme per variant)
    ports/vscode-icons/             VS Code icon theme extension (package.json, themes/<theme>.json);
                                    install.ps1 adds the SVGs from icons/ when it installs it
    preview/icons.html              icon preview for the owner (agents: do not read it)
"""
import json
import re
import shutil
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import build as B  # noqa: E402  (shared color helpers)

ROOT = B.ROOT
SRC = Path(__file__).resolve().parent / "icons"
ZED_SCHEMA = "https://zed.dev/schema/icon_themes/v0.3.0.json"

# Catppuccin Macchiato color -> our palette role. "folder" is the folder outline.
COLOR_ROLES = {
    "#cad3f5": "tx", "#fff": "tx", "#8087a2": "cm",
    "#ed8796": "red", "#ee99a0": "red",
    "#f5a97f": "orange",
    "#eed49f": "yellow", "#df8e1d": "yellow",
    "#a6da95": "green",
    "#8bd5ca": "aqua", "#91d7e3": "aqua", "#7dc4e4": "aqua",
    "#8aadf4": "blue", "#b7bdf8": "blue", "#3700ff": "blue",
    "#c6a0f6": "purple",
    "#f5bde6": "accent", "#f4dbd6": "accent", "#f0c6c6": "accent",
}
FOLDER_ROLE = "accent"  # outline of every folder icon: the theme's identity color
FILE_ROLE = "cm"        # the plain file icon, for files nothing else matches: quiet
ICON_FLOOR = 3.0        # WCAG non-text contrast for every icon color, on bg and on panel

# Outline of a named folder (closed / open), leaving the bottom-right corner for a badge.
BADGE_OUTLINE = {
    False: "M4.5 4.5H12A1.5 1.5 0 0 1 13.5 6v.5m-7.5 7H2A1.5 1.5 0 0 1 .5 12V3.5a1 1 0 0 1 1-1h5a1 1 0 0 1 1 1v1",
    True: "m1.875 8l.686-2.743a1 1 0 0 1 .97-.757h10.938a1 1 0 0 1 .97 1.243l-.315 1.26M6 13.5H2.004A1.5 1.5 0 0 1 "
          ".5 12V3.5a1 1 0 0 1 1-1h5a1 1 0 0 1 1 1v1",
}
# Doc-like files that are often written in capitals (README.md, LICENSE ...): Zed matches names exactly.
UPPER_ICONS = {"readme", "license", "changelog", "contributing", "code-of-conduct", "humans", "todo",
               "security", "codeowners", "release"}
# Icons shown in the preview, in order.
PREVIEW = ["c", "c-header", "cpp", "cpp-header", "cuda", "shader", "cmake", "makefile", "meson", "ninja",
           "assembly", "binary", "lib", "exe", "rust", "zig", "odin", "go", "python", "lua", "luau", "typescript",
           "javascript", "csharp", "java", "kotlin", "swift", "haskell", "html", "css", "json", "yaml", "toml",
           "markdown", "config", "env", "git", "docker", "bash", "powershell", "lock", "log", "image", "font",
           "readme", "license", "file", "folder", "folder-open", "folder-src", "folder-include", "folder-lib",
           "folder-tests", "folder-dist", "folder-docs", "folder-scripts", "folder-config", "folder-assets",
           "folder-badge-shader", "folder-badge-cmake", "folder-github", "folder-vscode"]


def load_sources():
    pack = json.loads((SRC / "catppuccin.json").read_text(encoding="utf-8"))
    assoc = json.loads((SRC / "associations.json").read_text(encoding="utf-8"))
    bodies = {k: v["body"] for k, v in pack["icons"].items()}
    for k, v in pack.get("aliases", {}).items():
        bodies[k] = bodies[v["parent"]]
    return bodies, assoc


def file_name(icon):
    """associations.json value -> SVG file stem ('folder+shader' -> 'folder-badge-shader')."""
    return "folder-badge-" + icon[7:] if icon.startswith("folder+") else icon


def is_folder(name):
    return name.startswith(("folder", "root"))


def badge_body(outline_open, glyph):
    """A folder outline plus another icon shrunk into its bottom-right corner."""
    glyph = re.sub(r'stroke-width="([\d.]+)"', lambda m: f'stroke-width="{float(m.group(1)) * 2:g}"', glyph)
    return (f'<path fill="none" stroke="#cad3f5" stroke-linecap="round" stroke-linejoin="round" '
            f'd="{BADGE_OUTLINE[outline_open]}"/>'
            f'<g stroke-width="2" transform="translate(7.5 7.5) scale(.5)">{glyph}</g>')


def needed_icons(bodies, assoc):
    """Every SVG the themes reference: name -> (template body, is folder)."""
    used = {"file", "folder", "folder-open", "root", "root-open"}
    for sect in ("file_extensions", "file_names", "language_ids", "folder_names"):
        used.update(assoc[sect].values())
    out = {}
    for icon in sorted(used):
        if icon.startswith("folder+"):
            glyph = bodies[icon[7:]]
            out[file_name(icon)] = badge_body(False, glyph)
            out[file_name(icon) + "-open"] = badge_body(True, glyph)
        elif icon.startswith("folder-") and icon not in ("folder-open",):
            out[icon] = bodies[icon]
            out[icon + "-open"] = bodies.get(icon + "-open", bodies[icon])
        else:
            out[icon] = bodies[icon]
    return out


def role_colors(v):
    """Role -> color for one variant, each nudged (same hue) to ICON_FLOOR on bg and panel."""
    c, dark = v["colors"], B.is_dark(v)
    out = {}
    for role in set(COLOR_ROLES.values()) | {FOLDER_ROLE, FILE_ROLE}:
        col = c[role]
        for surface in ("bg", "panel"):
            col = B.readable(col, c[surface], ICON_FLOOR, dark)
        out[role] = col
    return out


def paint(name, body, roles):
    folder = is_folder(name)

    def swap(m):
        role = COLOR_ROLES.get(m.group(0).lower())
        if role is None:
            raise ValueError(f"icon {name}: color {m.group(0)} has no role in COLOR_ROLES")
        if folder and role == "tx":
            role = FOLDER_ROLE
        if name == "file":
            role = FILE_ROLE
        return roles[role]
    body = re.sub(r"#[0-9a-fA-F]{6}\b|#[0-9a-fA-F]{3}\b", swap, body)
    return f'<svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 16 16">{body}</svg>\n'


def zed_names(names, docs=None):
    """Zed matches file and folder names exactly, so add the usual capitalised spellings."""
    out = {}
    for k, icon in names.items():
        out.setdefault(k, icon)
        if k.islower() and not k.startswith(".") and k[0].isalpha():
            out.setdefault(k[0].upper() + k[1:], icon)
            if docs is not None and icon in docs:
                stem, dot, ext = k.partition(".")
                out.setdefault(stem.upper() + dot + ext, icon)
    return dict(sorted(out.items()))


def zed_icon_theme(v, assoc, svgs):
    s = B.slug(v["name"])
    path = lambda n: f"./icons/{s}/{n}.svg"  # noqa: E731
    files = {n: {"path": path(n)} for n in sorted(svgs) if not is_folder(n)}
    files["default"] = {"path": path("file")}
    folders = {}
    for k, icon in zed_names(assoc["folder_names"]).items():
        n = file_name(icon)
        folders[k] = {"collapsed": path(n), "expanded": path(n + "-open")}
    return {
        "name": f"{v['name']} Icons",
        "appearance": v["appearance"],
        "directory_icons": {"collapsed": path("folder"), "expanded": path("folder-open")},
        "named_directory_icons": folders,
        "file_stems": zed_names(assoc["file_names"], UPPER_ICONS),
        "file_suffixes": dict(assoc["file_extensions"]),
        "file_icons": files,
    }


def vscode_icon_theme(v, assoc, svgs):
    s = B.slug(v["name"])
    lower = lambda d: {k.lower(): file_name(i) for k, i in sorted(d.items(), reverse=True)}  # noqa: E731
    folders = lower(assoc["folder_names"])
    return {
        "iconDefinitions": {n: {"iconPath": f"../icons/{s}/{n}.svg"} for n in sorted(svgs)},
        "file": "file", "folder": "folder", "folderExpanded": "folder-open",
        "rootFolder": "root", "rootFolderExpanded": "root-open",
        "fileExtensions": dict(sorted(lower(assoc["file_extensions"]).items())),
        "fileNames": dict(sorted(lower(assoc["file_names"]).items())),
        "folderNames": dict(sorted(folders.items())),
        "folderNamesExpanded": {k: i + "-open" for k, i in sorted(folders.items())},
        "languageIds": dict(sorted(lower(assoc["language_ids"]).items())),
        "hidesExplorerArrows": False,
    }


def package_version():
    m = re.search(r'^version\s*=\s*"([^"]+)"', (ROOT / "extension.toml").read_text(encoding="utf-8"), re.M)
    return m.group(1) if m else "0.0.0"


def vscode_package(pkg, vs):
    name = pkg["name"].replace(" Themes", "") + " Icons"
    return {
        "name": f"{pkg['id'].replace('-theme', '')}-icons",
        "displayName": name,
        "description": f"File and folder icons for coding, in the colors of {pkg['name']}.",
        "publisher": pkg["author"],
        "version": package_version(),
        "license": "MIT",
        "engines": {"vscode": "^1.60.0"},
        "categories": ["Themes"],
        "contributes": {"iconThemes": [
            {"id": B.slug(v["name"]) + "-icons", "label": f"{v['name']} Icons",
             "path": f"./themes/{B.slug(v['name'])}.json"} for v in vs]},
    }


def preview_html(pkg, vs, painted):
    cards = []
    for v in vs:
        c, s = v["colors"], B.slug(v["name"])
        cells = "".join(f'<figure title="{n}">{painted[s][n]}<figcaption>{n.replace("folder-badge-", "folder+")}'
                        f"</figcaption></figure>" for n in PREVIEW if n in painted[s])
        cards.append(f'<section><h3>{v["name"]}</h3><div class=pan style="background:{c["panel"]};color:{c["cm"]}">'
                     f"{cells}</div></section>")
    return ("<!doctype html><meta charset=utf-8><meta name=viewport content='width=device-width,initial-scale=1'>"
            f"<title>{pkg['name']} icons</title><style>body{{font-family:system-ui,sans-serif;background:#7a7a7a;"
            "margin:20px;color:#111}h1{font-size:18px}h3{font-size:13px;margin:0 0 5px}"
            ".grid{display:grid;gap:14px;grid-template-columns:repeat(auto-fill,minmax(min(100%,560px),1fr))}"
            ".pan{border-radius:8px;padding:10px;display:grid;gap:6px 4px;"
            "grid-template-columns:repeat(auto-fill,minmax(64px,1fr))}"
            "figure{margin:0;text-align:center}figure svg{width:32px;height:32px;display:block;margin:0 auto 2px}"
            "figcaption{font-size:10px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}</style>"
            f"<h1>{pkg['name']}: icons (shown at 2x, on each theme's panel color)</h1><div class=grid>"
            + "".join(cards) + "</div>\n")


def validate(data):
    """Errors: missing icons, unmapped colors, or icon colors below ICON_FLOOR."""
    errors = []
    bodies, assoc = load_sources()
    for sect, d in assoc.items():
        if sect.startswith("$"):
            continue
        for k, icon in d.items():
            base = icon[7:] if icon.startswith("folder+") else icon
            if base not in bodies:
                errors.append(f"icons: associations.json {sect}[{k!r}] -> unknown icon {icon!r}")
    for name, body in needed_icons(bodies, assoc).items() if not errors else ():
        for col in re.findall(r"#[0-9a-fA-F]{6}\b|#[0-9a-fA-F]{3}\b", body):
            if col.lower() not in COLOR_ROLES:
                errors.append(f"icons: {name} uses {col}, which has no role in COLOR_ROLES")
    for _, v in B.variants(data):
        for role, col in role_colors(v).items():
            for surface in ("bg", "panel"):
                r = B.contrast(col, v["colors"][surface])
                if r < ICON_FLOOR:
                    errors.append(f"icons: {v['name']} {role} {col} is {r:.2f}:1 on {surface} (< {ICON_FLOOR})")
    return errors


def build(data):
    """Write every icon output. Returns a one-line summary."""
    pkg = data["package"]
    bodies, assoc = load_sources()
    svgs = needed_icons(bodies, assoc)
    vs = [v for _, v in B.variants(data)]

    icons_dir = ROOT / "icons"
    if icons_dir.exists():
        shutil.rmtree(icons_dir)
    painted = {}
    for v in vs:
        s, roles = B.slug(v["name"]), role_colors(v)
        d = icons_dir / s
        d.mkdir(parents=True)
        painted[s] = {}
        for name, body in svgs.items():
            painted[s][name] = svg = paint(name, body, roles)
            (d / f"{name}.svg").write_text(svg, encoding="utf-8", newline="\n")

    zed_dir = ROOT / "icon_themes"
    zed_dir.mkdir(exist_ok=True)
    for old in zed_dir.glob("*.json"):
        old.unlink()
    family = {"$schema": ZED_SCHEMA, "name": pkg["name"].replace(" Themes", "") + " Icons",
              "author": pkg["author"], "themes": [zed_icon_theme(v, assoc, svgs) for v in vs]}
    (zed_dir / f"{pkg['id']}.json").write_text(json.dumps(family, indent=1) + "\n", encoding="utf-8", newline="\n")

    vsc = ROOT / "ports" / "vscode-icons"
    if (vsc / "themes").exists():
        shutil.rmtree(vsc / "themes")
    (vsc / "themes").mkdir(parents=True)
    for v in vs:
        (vsc / "themes" / f"{B.slug(v['name'])}.json").write_text(
            json.dumps(vscode_icon_theme(v, assoc, svgs), indent=1) + "\n", encoding="utf-8", newline="\n")
    (vsc / "package.json").write_text(json.dumps(vscode_package(pkg, vs), indent=2) + "\n",
                                      encoding="utf-8", newline="\n")
    shutil.copyfile(SRC / "LICENSE", vsc / "LICENSE")

    (ROOT / "preview").mkdir(exist_ok=True)
    (ROOT / "preview" / "icons.html").write_text(preview_html(pkg, vs, painted), encoding="utf-8", newline="\n")
    n_map = sum(len(assoc[k]) for k in ("file_extensions", "file_names", "folder_names"))
    return (f"icons: {len(svgs)} icons x {len(vs)} themes, {n_map} file and folder associations "
            f"(Zed icon themes, VS Code icon themes, preview/icons.html)")


def main():
    data = json.loads(B.PALETTES.read_text(encoding="utf-8"))
    errors = validate(data)
    for e in errors:
        print("ERROR:", e)
    if errors:
        sys.exit(1)
    print(build(data))


if __name__ == "__main__":
    main()
