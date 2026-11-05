#!/usr/bin/env python3
"""Parthenos agent driver — the thin glue loop.

Wires the running components together:
  - Hermes (LLM + skills) is the agent front-end; it is configured with an MCP
    client pointing at the Parthenos server, so it can read/write agent memory.
  - Parthenos MCP server = durable metacognitive memory (snapshot-persisted).
  - LangGraph = optional orchestration backend (health-checked, not yet invoked).

Commands:
  agent-loop.py --check          health-check all services (exit 0 if all up)
  agent-loop.py --prompt "..."   run one prompt through Hermes
  agent-loop.py --chat            interactive REPL

Env: DEEPSEEK_API_KEY (used by Hermes), PATH must include ~/.local/bin.
"""
from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
import urllib.request

MCP_URL = "http://127.0.0.1:8766/mcp"
LANGGRAPH_URL = "http://127.0.0.1:2024/ok"


def _mcp_ok(timeout: float = 5.0) -> bool:
    body = json.dumps({"jsonrpc": "2.0", "id": 1, "method": "initialize",
                       "params": {}}).encode()
    req = urllib.request.Request(MCP_URL, data=body, method="POST", headers={
        "Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return resp.status == 200


def _langgraph_ok(timeout: float = 5.0) -> bool:
    with urllib.request.urlopen(LANGGRAPH_URL, timeout=timeout) as resp:
        data = json.loads(resp.read())
        return bool(data.get("ok"))


def format_grounding(data: dict) -> str:
    """Compact, deterministic Athena grounding string from `athena now --fast --json`."""
    when = data.get("when") or {}
    where = data.get("where") or {}
    parts: list[str] = []

    if when.get("now"):
        parts.append(f"now={when['now']}")
    if when.get("tz"):
        parts.append(f"tz={when['tz']}")
    if when.get("weekday"):
        parts.append(f"weekday={when['weekday']}")
    if when.get("daypart"):
        parts.append(f"daypart={when['daypart']}")

    if where.get("host"):
        parts.append(f"host={where['host']}")
    if where.get("host_role"):
        parts.append(str(where["host_role"]))
    if where.get("project_cwd"):
        parts.append(f"cwd={where['project_cwd']}")
    if where.get("tailscale_peers_up_count") is not None:
        parts.append(f"ts_up={where['tailscale_peers_up_count']}/"
                     f"down={where.get('tailscale_peers_down_count')}")
    if where.get("daniel_reachable") is not None:
        parts.append(f"daniel={where['daniel_reachable']}")

    social = data.get("social")
    if isinstance(social, dict):
        for key in ("presence", "sleep", "tone"):
            val = social.get(key)
            if val in (None, "", {}, []):
                continue
            parts.append(f"{key}={val}" if not isinstance(val, (dict, list))
                         else f"{key}=" + ",".join(str(v) for v in val))
    return "; ".join(parts)


def fetch_athena_grounding(timeout: float = 15.0) -> str | None:
    """Return current Athena grounding, or None when Athena is unavailable."""
    hermes_bin = shutil.which("athena")
    if not hermes_bin:
        return None
    try:
        proc = subprocess.run(
            [hermes_bin, "now", "--fast", "--json"],
            capture_output=True, text=True, check=False, timeout=timeout,
        )
    except subprocess.TimeoutExpired:
        return None
    if proc.returncode != 0:
        return None
    try:
        data = json.loads(proc.stdout)
    except json.JSONDecodeError:
        return None
    return format_grounding(data)


def make_grounding_block(grounding: str) -> str:
    return f"[context]\n{grounding}\n[/context]"


def check() -> int:
    hermes = shutil.which("hermes")
    results = {
        "hermes_bin": bool(hermes),
        "athena_bin": bool(shutil.which("athena")),
        "mcp_parthenos": _mcp_ok(),
        "langgraph": _langgraph_ok(),
    }
    print(json.dumps(results, indent=2))
    return 0 if all(results.values()) else 1


def run_prompt(prompt: str, grounding: str | None = None,
               return_text: bool = False):
    hermes = shutil.which("hermes")
    if not hermes:
        if return_text:
            return 2, ""
        print("hermes binary not on PATH", file=sys.stderr)
        return 2
    full = prompt
    if grounding:
        full = f"{make_grounding_block(grounding)}\n{prompt}"
    proc = subprocess.run([hermes, "-z", full], capture_output=True, text=True, check=False)
    if return_text:
        return proc.returncode, proc.stdout
    sys.stdout.write(proc.stdout)
    if proc.stderr:
        sys.stderr.write(proc.stderr)
    return proc.returncode


def repl(with_grounding: bool = True) -> int:
    print("parthenos agent REPL (Ctrl-D to exit)")
    while True:
        try:
            prompt = input("> ")
        except EOFError:
            print()
            return 0
        if not prompt.strip():
            continue
        if prompt.strip().lower() in {"/check", "health"}:
            check()
            continue
        grounding = fetch_athena_grounding() if with_grounding else None
        run_prompt(prompt, grounding)


def main() -> int:
    ap = argparse.ArgumentParser(description="Parthenos agent driver")
    g = ap.add_mutually_exclusive_group(required=True)
    g.add_argument("--check", action="store_true", help="health-check services")
    g.add_argument("--prompt", help="run one prompt through Hermes")
    g.add_argument("--chat", action="store_true", help="interactive REPL")
    ap.add_argument("--no-grounding", action="store_true",
                    help="skip Athena awareness injection")
    args = ap.parse_args()
    if args.check:
        return check()
    if args.prompt:
        grounding = None if args.no_grounding else fetch_athena_grounding()
        return run_prompt(args.prompt, grounding)
    return repl(with_grounding=not args.no_grounding)


if __name__ == "__main__":
    raise SystemExit(main())
