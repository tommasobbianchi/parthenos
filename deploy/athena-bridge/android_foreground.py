#!/usr/bin/env python3
"""Athena — Android foreground-app sense (native Gemini/Claude apps).

Polls the Pixel over adb (Tailscale), reads the foreground package from
`dumpsys window`, and appends a presence event to the standard
llm-context/browser-events.ndjson stream (kind: android_foreground).

Only structural info: package name + alias. No content.

Relies on wireless debugging being enabled and `adb` already authorized:
  adb pair <ts-ip>:<port> <code>   # once
  adb connect <ts-ip>:5555
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from datetime import UTC, datetime
from pathlib import Path


def _module_dir(root: Path) -> Path:
    """llm-context module dir in a real Athena tree or the vendored kit."""
    m = root / "modules" / "llm-context"
    return m if m.is_dir() else root / "llm-context"


def _resolve_root() -> Path:
    env = os.environ.get("ATHENA_ROOT")
    if env:
        return Path(env)
    here = Path(__file__).resolve()
    # real Athena tree: <ath>/modules/llm-context/<file>
    if len(here.parents) > 3:
        p = here.parents[3]
        if (p / "modules" / "llm-context" / "inject.py").exists():
            return p
    # vendored kit in a Parthenos clone
    for anc in here.parents:
        kit = anc / "athena_kit"
        if (kit / "llm-context" / "inject.py").exists():
            return kit
    return Path.home() / "projects" / "athena"


ROOT = _resolve_root()
DATA = _module_dir(ROOT) / "data"
EVENTS = DATA / "browser-events.ndjson"

PACKAGE_ALIASES = {
    "com.anthropic.claude": "claude-app",
    "com.google.android.apps.bard": "gemini-app",
    "com.google.android.apps.googleapp": "google-app",
    "com.google.android.apps.nexuslauncher": "launcher",
    "com.android.systemui": "systemui",
}

DEFAULT_SERIAL = "100.120.88.98:5555"  # pixel-9a over Tailscale


def iso_now() -> str:
    return datetime.now(UTC).isoformat(timespec="seconds")


def foreground_package(serial: str) -> str | None:
    cmd = ["adb", "-s", serial, "shell", "dumpsys", "window"]
    try:
        p = subprocess.run(cmd, capture_output=True, text=True, check=False,
                           timeout=20)
    except (OSError, subprocess.TimeoutExpired):
        return None
    if p.returncode != 0:
        return None
    for line in p.stdout.splitlines():
        if "mFocusedApp" in line and "ActivityRecord{" in line:
            # ActivityRecord{... u0 com.pkg/.Activity t2}
            part = line.split("ActivityRecord{", 1)[1].split(" ", 1)[1]
            pkg = part.split("/", 1)[0]
            return pkg
        if "mCurrentFocus" in line and "Window{" in line:
            # Window{... u0 pkg/.Activity}
            part = line.split("Window{", 1)[1]
            # blob: Window{hash u0 <pkg>/<activity> ...}
            fields = part.split(" ", 2)
            if len(fields) >= 3:
                candidate = fields[2]
                if "/" in candidate:
                    return candidate.split("/", 1)[0]
    return None


def note(serial: str) -> dict | None:
    pkg = foreground_package(serial)
    if pkg is None:
        return None
    alias = PACKAGE_ALIASES.get(pkg)
    if alias is None:
        return None  # only known surfaces
    rec = {
        "ts": iso_now(),
        "kind": "android_foreground",
        "source": "adb-sense",
        "client": alias,
        "domain": "android",
        "conv_title": None,
        "window_active": True,
        "tab_count": None,
        "package": pkg,
    }
    DATA.mkdir(parents=True, exist_ok=True)
    with EVENTS.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(rec, ensure_ascii=False) + "\n")
    return rec


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--serial", default=DEFAULT_SERIAL)
    args = ap.parse_args()
    rec = note(args.serial)
    if rec:
        print(json.dumps(rec, ensure_ascii=False))
    else:
        print('{"ok": false, "reason": "no known foreground or adb unreachable"}')
    return 0


if __name__ == "__main__":
    sys.exit(main())
