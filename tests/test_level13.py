"""Agent runtime slice — Athena awareness grounding tests (window1).

Covers the pure formatting + fetching helpers used by bin/agent-loop.py to
inject Athena awareness into Hermes prompts.
"""

from __future__ import annotations

import importlib.util
import pathlib

_spec = importlib.util.spec_from_file_location(
    "agent_loop", pathlib.Path(__file__).resolve().parent.parent / "bin" / "agent-loop.py"
)
al = importlib.util.module_from_spec(_spec)
assert _spec.loader is not None
_spec.loader.exec_module(al)


def test_format_grounding_full():
    data = {
        "now": "2026-11-05T05:31:12+01:00",
        "when": {"now": "2026-11-05T05:31:12+01:00", "tz": "CET",
                 "weekday": "thursday", "daypart": "early-morning"},
        "where": {"host": "nativedev", "host_role": "server",
                  "project_cwd": "~/projects/Parthenos",
                  "tailscale_peers_up_count": 11,
                  "tailscale_peers_down_count": 21,
                  "daniel_reachable": False},
        "social": {"presence": "unknown", "sleep": "awake"},
    }
    out = al.format_grounding(data)
    assert "now=2026-11-05T05:31:12+01:00" in out
    assert "tz=CET" in out
    assert "weekday=thursday" in out
    assert "host=nativedev" in out
    assert "ts_up=11/down=21" in out
    assert "daniel=False" in out
    assert "sleep=awake" in out


def test_format_grounding_sparse():
    assert al.format_grounding({}) == ""
    out = al.format_grounding({"now": "x", "where": {"host": "h"}})
    assert "host=h" in out


def test_grounding_block_shape():
    block = al.make_grounding_block("grounding-text")
    assert "grounding-text" in block
    assert block.startswith("[context]")
    assert block.endswith("[/context]")
