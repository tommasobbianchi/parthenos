"""Lucid-dream nightly calibration — report flow (S9.2).

Runs the Calibrator over a GraphStore (loaded from an S5 JSON snapshot when
available) and produces a calibration report JSON. The layer proposes parameter
deltas; it never applies them. Application at a quiet checkpoint stays the
caller's job (bin/parthenos-dream + systemd timer).
"""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path

from parthenos.dream import Calibrator
from parthenos.graph import GraphStore
from parthenos.node import Clock
from parthenos.serialize import Snapshotter


def load_store_from_snapshot(path: str | Path) -> GraphStore:
    """Rebuild a GraphStore from an S5 snapshot JSON file.

    Raises FileNotFoundError when the file is absent.
    """
    path = Path(path)
    if not path.is_file():
        raise FileNotFoundError(path)
    snapshot = json.loads(path.read_text(encoding="utf-8"))
    store = GraphStore()
    Snapshotter(store).restore(snapshot)
    return store


def run_report(store: GraphStore, now: Clock | float | None = None) -> dict:
    """Compute the calibration report for a store.

    ``now`` may be a callable (clock), a float epoch, or None (real time).
    Returns deterministic content: generated_at (ISO), total_nodes, stats, and
    proposals (empty when the store has no nodes).
    """
    calibrator = Calibrator(store)
    stats = calibrator.collect_stats()
    proposals = calibrator.propose_calibration()
    return {
        "generated_at": _iso_now(now),
        "total_nodes": stats["total_nodes"],
        "stats": stats,
        "proposals": proposals,
    }


def write_report(report: dict, path: str | Path) -> None:
    """Write the report as JSON (sorted keys, 2-space indent)."""
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    Path(path).write_text(json.dumps(report, indent=2, sort_keys=True), encoding="utf-8")


def _iso_now(now: Clock | float | None) -> str:
    if now is None:
        ts = __import__("time").time()
    elif callable(now):
        ts = now()
    else:
        ts = float(now)
    return datetime.fromtimestamp(ts, tz=UTC).isoformat()
