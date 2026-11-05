#!/usr/bin/env python3
"""Athena kit — minimal standalone context block (vendored).

Used when Parthenos is cloned without a full Athena installation. Produces the
same compact [Athena context] block the receiver serves to the extension's
popup injector. Falls back gracefully (time/host/tailscale) if Athena's richer
`athena` CLI is absent.
"""
import argparse
import json
import os
import socket
import subprocess
import sys
from datetime import datetime

def _tailscale():
    try:
        p = subprocess.run(["tailscale", "status", "--json"],
                           capture_output=True, text=True, check=False, timeout=10)
        if p.returncode == 0 and p.stdout.strip():
            peers = json.loads(p.stdout).get("Peer", {})
            up = [x for x in peers.values() if x.get("Online")]
            return len(up), len(peers) - len(up)
    except Exception:
        pass
    return None, None

def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--block", action="store_true")
    ap.add_argument("--segments", action="store_true")
    args = ap.parse_args()

    now = datetime.now().astimezone()
    segs = [
        f"now={now.isoformat(timespec='seconds')}",
        f"tz={now.tzname()}",
        now.strftime("%A").lower(),
    ]
    segs.append(f"host={socket.gethostname()}")
    cwd = os.getcwd()
    segs.append(f"cwd={cwd}")
    up, down = _tailscale()
    if up is not None:
        segs.append(f"tailnet {up}up/{down}down")

    if args.segments:
        print("\n".join(segs))
        return 0
    print("[Athena context]\n" + "\n".join(segs) + "\n[/Athena context]")
    return 0

if __name__ == "__main__":
    sys.exit(main())
