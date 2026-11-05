"""S9.2 — lucid-dream CLI report path tests.

Exercises the nightly calibration report flow: loading a serialized snapshot
(S5 format) into a GraphStore, running Calibrator, and writing/reading a JSON
report. Only the module logic is tested; the bin/ wrapper is thin.
"""

from __future__ import annotations

import json

import pytest

from parthenos.dream_cli import load_store_from_snapshot, run_report, write_report
from parthenos.graph import GraphStore
from parthenos.serialize import Snapshotter


def _sample_store() -> GraphStore:
    store = GraphStore()
    from parthenos.node import MemoryNode

    for nid, fl in (("a", 0.2), ("b", 0.9), ("c", 0.5)):
        node = MemoryNode(
            id=nid,
            created_at=0.0,
            last_recall=1.0,
            floatation=fl,
            dims={"project": ["P"], "label": "x"} if nid != "c" else {"label": "x"},
        )
        store.add_node(node)
    return store


def test_run_report_shape():
    report = run_report(_sample_store(), now=1_700_000_000.0)
    assert set(report) >= {"generated_at", "stats", "proposals", "total_nodes"}
    assert report["total_nodes"] == 3
    assert report["stats"]["avg_floatation"] > 0.0
    assert isinstance(report["proposals"], list)


def test_run_report_empty_store():
    report = run_report(GraphStore(), now=1_700_000_000.0)
    assert report["total_nodes"] == 0
    assert report["stats"]["avg_floatation"] == 0.0
    assert report["proposals"] == []


def test_snapshot_round_trip_load(tmp_path):
    snap_path = tmp_path / "store.snapshot.json"
    snap = Snapshotter(_sample_store(), clock=lambda: 123.0).snapshot()
    snap_path.write_text(json.dumps(snap))

    store = load_store_from_snapshot(snap_path)
    report = run_report(store)
    assert report["total_nodes"] == 3


def test_load_missing_snapshot_raises(tmp_path):
    with pytest.raises(FileNotFoundError):
        load_store_from_snapshot(tmp_path / "missing.json")


def test_write_report_round_trip(tmp_path):
    out = tmp_path / "dream-report.json"
    write_report(run_report(_sample_store()), out)
    data = json.loads(out.read_text())
    assert data["total_nodes"] == 3
    assert "proposals" in data
