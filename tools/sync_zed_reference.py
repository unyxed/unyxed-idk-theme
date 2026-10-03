#!/usr/bin/env python3
"""Refresh reference/zed.json from Zed's source code.

Zed adds theme keys and grammar captures over time. This sparse-clones the Zed repo
(only the files needed) and records:
  - every theme color key and status key Zed accepts (crates/settings_content/src/theme.rs)
  - every highlight capture name used by Zed's built-in grammars (**/highlights.scm)

Then run `python tools/build.py`: it fails if any theme is missing a new key, and
warns about captures with no matching syntax key.

Usage:  python tools/sync_zed_reference.py      (needs git and network access)
"""
import datetime
import json
import re
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "reference" / "zed.json"


def run(*cmd, cwd=None):
    subprocess.run(cmd, cwd=cwd, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


def main():
    with tempfile.TemporaryDirectory() as tmp:
        repo = Path(tmp) / "zed"
        print("cloning zed (sparse)...")
        run("git", "clone", "--depth", "1", "--filter=blob:none", "--sparse",
            "https://github.com/zed-industries/zed.git", str(repo))
        run("git", "sparse-checkout", "set", "--no-cone", "**/highlights.scm",
            "crates/settings_content/src/theme.rs", cwd=repo)
        sha = subprocess.run(["git", "rev-parse", "--short", "HEAD"], cwd=repo,
                             capture_output=True, text=True, check=True).stdout.strip()
        src = (repo / "crates/settings_content/src/theme.rs").read_text(encoding="utf-8")

        def keys(struct):
            m = re.search(r"pub struct " + struct + r"\s*\{(.*?)\n\}", src, re.S)
            if not m:
                sys.exit(f"could not find {struct}; Zed's layout changed, update this script")
            return re.findall(r'#\[serde\(rename = "([^"]+)"', m.group(1))

        caps = set()
        for f in repo.rglob("highlights.scm"):
            if "test-extension" in f.parts:
                continue
            caps.update(re.findall(r"@([a-zA-Z][a-zA-Z0-9_.-]*)", f.read_text(encoding="utf-8")))

    old = json.loads(OUT.read_text(encoding="utf-8")) if OUT.exists() else {}
    new = {"zed_commit": sha, "synced": datetime.date.today().isoformat(),
           "color_keys": keys("ThemeColorsContent"), "status_keys": keys("StatusColorsContent"),
           "captures": sorted(caps)}
    for field in ("color_keys", "status_keys", "captures"):
        added = sorted(set(new[field]) - set(old.get(field, [])))
        removed = sorted(set(old.get(field, [])) - set(new[field]))
        if added:
            print(f"{field} added: {added}")
        if removed:
            print(f"{field} removed: {removed}")
    OUT.parent.mkdir(exist_ok=True)
    OUT.write_text(json.dumps(new, indent=1) + "\n", encoding="utf-8")
    print(f"reference updated to zed@{sha}")


if __name__ == "__main__":
    main()
