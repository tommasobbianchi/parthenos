#!/usr/bin/env python3
"""Athena — browser presence receiver (loopback :8008).

Receives structured presence events from the Athena Bridge Chrome extension and
appends them to modules/llm-context/data/browser-events.ndjson (same ndjson
conventions as capture.py). Single-local-writer; loopback only.

Expected payload (POST /llm-context, JSON):
  {
    "client": "claude-web" | "gemini" | "chatgpt" | "browser",
    "domain": "claude.ai",
    "conv_title": "..." | null,
    "window_active": true|false,
    "tab_count": int | null,
    "ts": ISO | null
  }
"""
from __future__ import annotations

import json
import os
import sys
from datetime import UTC, datetime
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
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

HOST = "0.0.0.0"  # tailnet + loopback; single-operator home net, Tailscale-only exposure recommended
PORT = 8008

ALLOWED_CLIENTS = {"claude-web", "gemini", "chatgpt", "browser"}


def iso_now() -> str:
    return datetime.now(UTC).isoformat(timespec="seconds")


def append_event(payload: dict) -> dict:
    rec = {
        "ts": iso_now(),
        "kind": "browser_presence",
        "source": "chrome-extension",
        **{k: payload.get(k) for k in ("client", "domain", "conv_title",
                                       "window_active", "tab_count")},
    }
    DATA.mkdir(parents=True, exist_ok=True)
    with EVENTS.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(rec, ensure_ascii=False) + "\n")
    return rec


class Handler(BaseHTTPRequestHandler):
    def do_GET(self) -> None:
        # Serve the live Athena context block for the extension popup injector.
        if self.path == "/llm-context/block":
            import subprocess

            try:
                p = subprocess.run(
                    [str(ROOT / "modules" / "llm-context" / "inject.py"), "--block"],
                    capture_output=True, text=True, check=False, timeout=20,
                )
                block = p.stdout if p.returncode == 0 else ""
            except Exception:  # noqa: BLE001
                block = ""
            body = json.dumps({"block": block}).encode()
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
            return
        self.send_error(404)

    def do_POST(self) -> None:
        if self.path != "/llm-context":
            self.send_error(404)
            return
        length = int(self.headers.get("Content-Length", 0))
        if length > 64 * 1024:
            self.send_response(413)
            self.end_headers()
            return
        try:
            payload = json.loads(self.rfile.read(length))
        except (json.JSONDecodeError, UnicodeDecodeError):
            self.send_response(400)
            self.end_headers()
            return
        client = payload.get("client", "browser")
        if client not in ALLOWED_CLIENTS:
            self.send_response(400)
            self.end_headers()
            return
        append_event(payload)
        body = json.dumps({"ok": True}).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, *args) -> None:  # quiet
        pass


def main() -> int:
    httpd = ThreadingHTTPServer((HOST, PORT), Handler)
    print(f"athena browser receiver on http://{HOST}:{PORT}/llm-context "
          f"-> {EVENTS}", flush=True)
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        pass
    return 0


if __name__ == "__main__":
    sys.exit(main())
