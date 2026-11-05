"""A4 — OpenHands on-demand execute actor: driver + resource measurement.

Runs the local agent-server in Docker with hard resource caps (OOM protection on
nativedev), creates a conversation with a trivial coding task on DeepSeek,
polls to completion, samples container memory/CPU during the run, then cleans up.

Usage:
  python deploy/openhands/a4_driver.py [--image ghcr.io/openhands/agent-server:latest-python]

Env: DEEPSEEK_API_KEY (required).
"""

from __future__ import annotations

import argparse
import json
import subprocess
import time
import urllib.request

CONTAINER = "openhands-a4"
SERVER_PORT = 8000
BASE = f"http://127.0.0.1:{SERVER_PORT}"

# Hard caps — the OOM-protection core (nativedev has 62 GB; give it plenty but
# bounded, and never let it balloon).
MEM_LIMIT = "6g"
MEM_SWAP = "6g"
CPUS = "4"
PIDS_LIMIT = "512"

TASK = (
    "Compute all prime numbers up to 20000 and write them one per line to "
    "/workspace/primes.txt. Also create /workspace/hello.txt containing exactly "
    'the line "hello from openhands". Report the count of primes found.'
)

WORKSPACE_HOST = "~/projects/Parthenos/deploy/openhands/workspace"

TOOLS = [{"name": "terminal"}, {"name": "file_editor"}]


def _req(method: str, path: str, body: dict | None = None, timeout: int = 30) -> dict:
    req = urllib.request.Request(BASE + path, method=method)
    if body is not None:
        req.add_header("Content-Type", "application/json")
        payload = json.dumps(body).encode()
    else:
        payload = None
    with urllib.request.urlopen(req, payload, timeout=timeout) as resp:
        return json.loads(resp.read())


def _run(cmd: list[str]) -> str:
    return subprocess.run(
        cmd, capture_output=True, text=True, check=False, timeout=60
    ).stdout


def container_up() -> bool:
    out = _run(["docker", "inspect", "-f", "{{.State.Running}}", CONTAINER])
    return out.strip() == "true"


def start_container(image: str) -> None:
    if container_up():
        print("container already running")
        return
    print(f"starting container {CONTAINER} (mem={MEM_LIMIT} cpus={CPUS} pids={PIDS_LIMIT})")
    _run([
        "docker", "run", "-d", "--name", CONTAINER,
        "--network", "host",  # uvicorn binds loopback inside the image; host net keeps 127.0.0.1:8000 reachable
        "--memory", MEM_LIMIT, "--memory-swap", MEM_SWAP,
        "--cpus", CPUS, "--pids-limit", PIDS_LIMIT,
        "-v", f"{WORKSPACE_HOST}:/workspace",
        image,
    ])
    for _ in range(30):
        if container_up():
            return
        time.sleep(1)
    raise RuntimeError("container did not start")


def wait_ready(timeout: int = 60) -> None:
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            _req("GET", "/openapi.json", timeout=5)
            return
        except (OSError, TimeoutError):
            time.sleep(2)
    raise RuntimeError("agent-server not ready")


def docker_stats_sample() -> dict:
    out = _run([
        "docker", "stats", "--no-stream", "--format",
        "{{.MemUsage}}|{{.MemPerc}}|{{.CPUPerc}}|{{.PIDs}}", CONTAINER,
    ]).strip()
    if not out:
        return {}
    mem_usage, mem_pct, cpu_pct, pids = [p.strip() for p in out.split("|")]
    return {"mem": mem_usage, "mem_pct": mem_pct, "cpu_pct": cpu_pct, "pids": pids}


def parse_mem_bytes(mem_str: str) -> float:
    """Docker '1.23GiB / 6GiB' -> usage bytes."""
    part = mem_str.split(" / ")[0]
    val = float(part.replace("GiB", "").replace("MiB", "").replace("KiB", ""))
    if "GiB" in part:
        return val * 1024**3
    if "MiB" in part:
        return val * 1024**2
    return val * 1024


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--image", default="ghcr.io/openhands/agent-server:latest-python")
    args = ap.parse_args()

    key = __import__("os").environ.get("DEEPSEEK_API_KEY", "")
    if not key:
        print("DEEPSEEK_API_KEY not set")
        return 2

    start_container(args.image)
    wait_ready()
    baseline = docker_stats_sample()
    print("baseline (ready, idle):", baseline)

    print("creating conversation (DeepSeek via OpenAI-compatible mapping)")
    conv = _req("POST", "/api/conversations", {
        "agent": {
            "llm": {
                "model": "openai/deepseek-flash",
                "api_key": key,
                "base_url": "https://api.deepseek.com/v1",
            },
            "tools": TOOLS,
        },
        "workspace": {"working_dir": "/workspace"},
        "initial_message": {"content": [{"text": TASK}]},
    })
    conv_id = conv.get("id")
    if not conv_id:
        print("create conversation failed:", json.dumps(conv)[:500])
        return 1
    print("conversation:", conv_id)

    # Conversations auto-start on creation; only explicitly run when parked.
    initial_status = conv.get("execution_status") or "running"
    if initial_status in {"created", "stopped"}:
        _req("POST", f"/api/conversations/{conv_id}/run", {})

    peak_bytes = 0.0
    samples = 0
    status = "unknown"
    deadline = time.time() + 240
    while time.time() < deadline:
        info = _req("GET", f"/api/conversations/{conv_id}")
        status = info.get("execution_status", "")
        s = docker_stats_sample()
        if s:
            samples += 1
            try:
                peak_bytes = max(peak_bytes, parse_mem_bytes(s["mem"]))
            except ValueError:
                pass
            if samples % 10 == 0:
                print(f"  [{samples}] status={status} {s}")
        if status in {"finished", "error"}:
            break
        time.sleep(1)

    print(f"\n=== RESULT status={status} samples={samples} "
          f"peak_mem={peak_bytes/1024**3:.2f} GiB ===")

    # Verify the task actually ran: tool events + any hello.txt evidence.
    try:
        ev = _req("GET", f"/api/conversations/{conv_id}/events/search?limit=100")
        items = ev.get("items", [])
        tools = sorted({
            e.get("tool_name") for e in items if e.get("kind") == "ActionEvent"
        })
        hello_hits = [
            e.get("content") or e.get("message") or ""
            for e in items
            if "hello" in str(e).lower()
        ]
        print("tools used:", tools)
        print("hello hits:", len(hello_hits))
        for h in hello_hits[:5]:
            print("  -", str(h)[:160])
        print("event count:", len(items))
    except (OSError, TimeoutError):
        print("event fetch unavailable")

    print("cleaning up")
    try:
        _req("DELETE", f"/api/conversations/{conv_id}")
    except (OSError, TimeoutError):
        print("delete conversation failed")
    _run(["docker", "stop", CONTAINER])
    _run(["docker", "rm", CONTAINER])

    # Host-side artifact verification (workspace was volume-mounted).
    from pathlib import Path

    hello = Path(WORKSPACE_HOST) / "hello.txt"
    primes = Path(WORKSPACE_HOST) / "primes.txt"
    hello_ok = hello.is_file() and hello.read_text().strip() == "hello from openhands"
    prime_lines = len(primes.read_text().splitlines()) if primes.is_file() else 0
    print(f"artifact hello.txt ok={hello_ok}; primes.txt lines={prime_lines}")

    ok = status == "finished" and hello_ok and prime_lines > 1000
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
