"""S5 (Level-5 serialization + timeline snapshots) behavior tests.

Covers spec §1 behaviors 1-7:
  1. snapshot() returns a deterministic, JSON-serializable dict with version,
     taken_at, nodes (id/created_at/last_recall/floatation/dims), edges
     (src/tgt/kind/weight); version increments; set dims serialize as sorted lists;
     locks/private trace excluded.
  2. save_snapshot / load_snapshot round-trip equality; sorted JSON keys.
  3. restore() replaces store contents (fresh snapshot equals restored; old gone).
  4. Timeline push/restore by version; KeyError on unknown; deep-copy immutability.
  5. Timeline.diff node/edge sets in deterministic order; empty for identical.
  6. Read-only concurrency: snapshot() takes no locks, never blocks.
  7. Regression: interfaces import + signals_out shape unchanged.
"""

from __future__ import annotations

import json
import threading

import pytest

from parthenos.graph import GraphStore
from parthenos.interfaces import context_in, signals_out
from parthenos.node import MemoryNode, TypedEdge
from parthenos.serialize import Snapshotter, Timeline


class ManualClock:
    """Injectable clock: a callable returning a mutable float."""

    def __init__(self, t: float = 0.0) -> None:
        self.value = t

    def __call__(self) -> float:
        return self.value


def make_node(
    node_id: str,
    *,
    created_at: float = 0.0,
    last_recall: float = 0.0,
    floatation: float = 1.0,
    dims: dict | None = None,
) -> MemoryNode:
    return MemoryNode(
        id=node_id,
        created_at=created_at,
        last_recall=last_recall,
        floatation=floatation,
        dims=dict(dims) if dims else {},
    )


# Behavior 1 ---------------------------------------------------------------


def test_snapshot_structure_deterministic_and_version_increment():
    clock = ManualClock(42.0)
    store = GraphStore()
    store.add_node(
        make_node(
            "n1",
            created_at=1.0,
            last_recall=2.0,
            floatation=0.5,
            dims={"mood": "calm", "tags": {"b", "a", "c"}, "project": ["A"]},
        )
    )
    store.add_node(make_node("n2", created_at=3.0, last_recall=4.0, floatation=1.0))
    store.add_edge("n1", "n2", "assoc", weight=0.7)

    snapshots = Snapshotter(store, clock=clock)
    snap0 = snapshots.snapshot()
    snap1 = snapshots.snapshot()

    assert list(snap0) == ["version", "taken_at", "nodes", "edges"]
    assert snap0["version"] == 0
    assert snap1["version"] == 1
    assert snap0["taken_at"] == 42.0

    # nodes sorted by id, carrying exactly the five documented fields
    assert [n["id"] for n in snap0["nodes"]] == ["n1", "n2"]
    n1 = snap0["nodes"][0]
    assert set(n1) == {"id", "created_at", "last_recall", "floatation", "dims"}
    assert n1["created_at"] == 1.0
    assert n1["last_recall"] == 2.0
    assert n1["floatation"] == 0.5
    # set-valued dim -> sorted list; scalar and list dims preserved
    assert n1["dims"] == {"mood": "calm", "project": ["A"], "tags": ["a", "b", "c"]}
    # locks, private trace, and L1 edges are excluded
    assert "lock" not in n1 and "_trace" not in n1 and "edges" not in n1

    # edges carry src/tgt/kind/weight + bi-temporal window (S0 alignment)
    assert snap0["edges"] == [
        {
            "src": "n1",
            "tgt": "n2",
            "kind": "assoc",
            "weight": 0.7,
            "valid_at": None,
            "invalid_at": None,
        }
    ]

    # deterministic: same state -> identical nodes/edges across calls
    assert snap0["nodes"] == snap1["nodes"]
    assert snap0["edges"] == snap1["edges"]

    # JSON-serializable
    json.dumps(snap0)


# Behavior 2 ---------------------------------------------------------------


def test_save_load_round_trip_and_sorted_keys(tmp_path):
    clock = ManualClock(100.0)
    store = GraphStore()
    store.add_node(make_node("a", dims={"tags": {"x", "y"}}))
    store.add_node(make_node("b"))
    store.add_edge("a", "b", "assoc", weight=0.5)

    snapshots = Snapshotter(store, clock=clock)
    path = tmp_path / "snap.json"
    snapshots.save_snapshot(path)

    raw = path.read_text()
    parsed = json.loads(raw)
    # top-level keys written in sorted order
    assert list(parsed) == ["edges", "nodes", "taken_at", "version"]
    # deterministic: file content is exactly the sorted-key dump
    assert raw == json.dumps(parsed, sort_keys=True)

    loaded = snapshots.load_snapshot(path)
    assert loaded == snapshots.snapshot()


# Behavior 3 ---------------------------------------------------------------


def test_restore_replaces_store_contents():
    clock = ManualClock(100.0)
    store = GraphStore()
    store.add_node(make_node("a", created_at=1.0, dims={"mood": "calm"}))
    store.add_node(make_node("b", created_at=2.0, floatation=0.5))
    store.add_edge("a", "b", "assoc", weight=0.5)

    snapshots = Snapshotter(store, clock=clock)
    snap = snapshots.snapshot()

    # mutate the store: drop a, add c, add a new edge
    store._nodes.pop("a")
    store.add_node(make_node("c", created_at=3.0, floatation=0.9))
    store.add_edge("b", "c", "links", weight=0.2)

    snapshots.restore(snap)

    fresh = snapshots.snapshot()
    assert fresh["nodes"] == snap["nodes"]
    assert fresh["edges"] == snap["edges"]
    # old content gone; restored content present
    assert store.get_node("c") is None
    assert store.get_node("a") is not None


# Behavior 4 ---------------------------------------------------------------


def test_timeline_push_restore_keyerror_and_immutability():
    clock = ManualClock(100.0)
    store = GraphStore()
    store.add_node(make_node("n", floatation=0.5, dims={"mood": "calm"}))

    snapshots = Snapshotter(store, clock=clock)
    timeline = Timeline()

    s0 = snapshots.snapshot()
    timeline.push(s0)

    # mutate the live store after push
    node = store.get_node("n")
    assert node is not None
    node.floatation = 0.1
    node.dims["mood"] = "excited"

    s1 = snapshots.snapshot()
    timeline.push(s1)

    assert timeline.restore(0) == s0
    assert timeline.restore(1) == s1
    assert timeline.restore(0)["version"] == 0
    assert timeline.restore(0)["taken_at"] == 100.0
    # earlier pushed snapshot is immutable against later store mutation
    assert timeline.restore(0)["nodes"][0]["floatation"] == 0.5
    assert timeline.restore(0)["nodes"][0]["dims"]["mood"] == "calm"

    # restore returns a deep copy
    mutated = timeline.restore(0)
    mutated["nodes"][0]["floatation"] = 999.0
    assert timeline.restore(0)["nodes"][0]["floatation"] == 0.5

    with pytest.raises(KeyError):
        timeline.restore(99)


# Behavior 5 ---------------------------------------------------------------


def test_timeline_diff_nodes_and_edges():
    clock = ManualClock(100.0)
    store = GraphStore()
    store.add_node(make_node("a", created_at=1.0, last_recall=1.0, dims={"mood": "calm"}))
    store.add_node(make_node("b", created_at=2.0, last_recall=2.0, floatation=0.5))
    store.add_node(make_node("gone", created_at=3.0, last_recall=3.0, floatation=0.8))
    store.add_edge("a", "b", "assoc", weight=1.0)
    store.add_edge("gone", "b", "links", weight=0.5)

    snapshots = Snapshotter(store, clock=clock)
    timeline = Timeline()
    timeline.push(snapshots.snapshot())  # version 0

    # mutate: modify b, remove 'gone', add c, change edge weight, add an edge
    b = store.get_node("b")
    assert b is not None
    b.floatation = 0.9
    b.last_recall = 20.0
    store._nodes.pop("gone")
    store.add_node(make_node("c", created_at=4.0, last_recall=4.0, floatation=0.7))
    store._edges.pop(("gone", "b"))
    store._edges[("a", "b")] = TypedEdge(target_id="b", kind="assoc", weight=0.3)
    store.add_edge("c", "a", "cites", weight=0.9)

    timeline.push(snapshots.snapshot())  # version 1

    d = timeline.diff(0, 1)

    assert [n["id"] for n in d["added_nodes"]] == ["c"]
    assert [n["id"] for n in d["removed_nodes"]] == ["gone"]
    assert [n["id"] for n in d["modified_nodes"]] == ["b"]
    modified_b = d["modified_nodes"][0]
    assert modified_b["floatation"] == 0.9
    assert modified_b["last_recall"] == 20.0

    assert [(e["src"], e["tgt"]) for e in d["added_edges"]] == [("a", "b"), ("c", "a")]
    assert [(e["src"], e["tgt"]) for e in d["removed_edges"]] == [
        ("a", "b"),
        ("gone", "b"),
    ]


def test_timeline_diff_identical_snapshots_empty():
    clock = ManualClock(100.0)
    store = GraphStore()
    store.add_node(make_node("a"))
    store.add_edge("a", "a", "self", weight=1.0)

    snapshots = Snapshotter(store, clock=clock)
    timeline = Timeline()
    timeline.push(snapshots.snapshot())  # version 0
    timeline.push(snapshots.snapshot())  # version 1

    assert timeline.diff(0, 1) == {
        "added_nodes": [],
        "removed_nodes": [],
        "modified_nodes": [],
        "added_edges": [],
        "removed_edges": [],
    }


# Behavior 6 ---------------------------------------------------------------


def test_snapshot_does_not_block_on_node_lock():
    store = GraphStore()
    for nid in ("a", "b"):
        store.add_node(make_node(nid))
    store.add_edge("a", "b", "assoc", weight=1.0)

    snapshots = Snapshotter(store)
    result: dict[str, dict] = {}

    def capture() -> None:
        result["snap"] = snapshots.snapshot()

    node = store.get_node("a")
    assert node is not None
    with node.lock:
        thread = threading.Thread(target=capture)
        thread.start()
        thread.join(timeout=2.0)
        assert not thread.is_alive(), "snapshot blocked behind a node lock"

    assert "snap" in result
    assert [n["id"] for n in result["snap"]["nodes"]] == ["a", "b"]


# Behavior 7 ---------------------------------------------------------------


def test_interface_import_and_shape_regression():
    context_in({"tokens": [1, 2, 3], "project": "parthenos", "emotion": "curious"})

    signals = signals_out()

    assert set(signals) >= {"priorities", "views", "alerts"}
    assert signals["priorities"] == []
    assert signals["views"] == []
    assert signals["alerts"] == []


# S0 alignment: bi-temporal edge fields (valid_at/invalid_at) -----------------


def test_snapshot_edges_carry_temporal_fields():
    store = GraphStore()
    store.add_node(make_node("a"))
    store.add_node(make_node("b"))
    store.add_edge("a", "b", "tmp", weight=0.5, valid_at=10.0, invalid_at=20.0)

    snap = Snapshotter(store, clock=lambda: 0.0).snapshot()
    edge = snap["edges"][0]
    assert edge["valid_at"] == 10.0
    assert edge["invalid_at"] == 20.0


def test_timeline_diff_detects_temporal_change():
    store = GraphStore()
    store.add_node(make_node("a"))
    store.add_node(make_node("b"))
    store.add_edge("a", "b", "tmp", weight=0.5)

    snapshots = Snapshotter(store, clock=lambda: 0.0)
    timeline = Timeline()
    timeline.push(snapshots.snapshot())  # version 0

    # Move the validity window -> edge content changes.
    store.add_edge("a", "b", "tmp", weight=0.5, valid_at=5.0, invalid_at=15.0)
    timeline.push(snapshots.snapshot())  # version 1

    diff = timeline.diff(0, 1)
    assert diff["added_edges"] == [
        {"src": "a", "tgt": "b", "kind": "tmp", "weight": 0.5, "valid_at": 5.0, "invalid_at": 15.0}
    ]
    assert diff["removed_edges"] == [
        {"src": "a", "tgt": "b", "kind": "tmp", "weight": 0.5, "valid_at": None, "invalid_at": None}
    ]
