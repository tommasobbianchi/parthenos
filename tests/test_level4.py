"""S4a (Level-4 supervision observation primitives) behavior tests.

Covers spec §1 behaviors 1-6:
  1. explain() returns a deterministic, stable, chronological trace for a known
     node and [] for an unknown node.
  2. detect_conflicts() surfaces nodes claimed by two projects at different weights.
  3. detect_anomalies() finds terms (case-insensitive substring) on foreign nodes.
  4. discover_bridges() surfaces cross-project edges, deterministically sorted.
  5. Read-only concurrency: supervision calls never block on a node's lock.
  6. Regression: interfaces import + signals_out shape unchanged (L1-L3 surface).
"""

from __future__ import annotations

import threading

import pytest

from parthenos.fovea import FoveaEngine
from parthenos.graph import GraphStore
from parthenos.interfaces import context_in, signals_out
from parthenos.node import MemoryNode
from parthenos.supervise import Supervision


class ManualClock:
    """Injectable clock: a callable returning a mutable float."""

    def __init__(self, t: float = 0.0) -> None:
        self.value = t

    def __call__(self) -> float:
        return self.value

    def advance(self, dt: float) -> None:
        self.value += dt


def make_node(
    node_id: str, *, dims: dict | None = None, floatation: float = 1.0
) -> MemoryNode:
    return MemoryNode(
        id=node_id,
        created_at=0.0,
        last_recall=0.0,
        floatation=floatation,
        dims=dict(dims) if dims else {},
    )


# Behavior 1 ---------------------------------------------------------------


def test_explain_returns_chronological_trace_and_empty_for_unknown():
    store = GraphStore()
    clock = ManualClock(0.0)
    node = make_node("n")
    store.add_node(node)

    clock.advance(10.0)
    node.neglect(clock(), rate=0.05)  # 1.0 -> 0.5, delta -0.5
    clock.advance(1.0)
    node.recall(clock(), strength=0.2)  # 0.5 -> 0.7, delta +0.2
    clock.advance(2.0)
    node.recall(clock(), strength=0.5)  # 0.7 -> 1.0, delta +0.3

    sup = Supervision(store)
    trace = sup.explain("n")

    assert [e["event"] for e in trace] == ["neglect", "recall", "recall"]
    assert [e["ts"] for e in trace] == [10.0, 11.0, 13.0]
    assert [e["delta"] for e in trace] == pytest.approx([-0.5, 0.2, 0.3])

    # Unknown node -> empty.
    assert sup.explain("ghost") == []

    # Stable across calls: the returned trace is a copy, not the live record.
    first = sup.explain("n")
    first[0]["delta"] = 999.0
    second = sup.explain("n")
    assert second[0]["delta"] == pytest.approx(-0.5)


def test_explain_records_stimulus_events():
    store = GraphStore()
    clock = ManualClock(50.0)
    node = make_node("n0", floatation=0.0)
    store.add_node(node)

    engine = FoveaEngine(beta=0.5, radius=0, clock=clock)
    engine.stimulate(node, intensity=1.0, graph={"n0": node})

    sup = Supervision(store)
    assert sup.explain("n0") == [{"event": "stimulus", "ts": 50.0, "delta": 1.0}]


# Behavior 2 ---------------------------------------------------------------


def test_detect_conflicts_different_weights_only():
    store = GraphStore()
    store.add_node(
        make_node(
            "diff", dims={"project": ["A", "B"], "project_weight": {"A": 0.8, "B": 1.2}}
        )
    )
    store.add_node(make_node("same_default", dims={"project": ["A", "B"]}))
    store.add_node(
        make_node(
            "same_explicit",
            dims={"project": ["A", "B"], "project_weight": {"A": 0.5, "B": 0.5}},
        )
    )
    store.add_node(make_node("only_a", dims={"project": ["A"]}))
    store.add_node(make_node("no_project", dims={}))

    conflicts = Supervision(store).detect_conflicts("A", "B")

    assert conflicts == [{"node_id": "diff", "weight_a": 0.8, "weight_b": 1.2}]


def test_detect_conflicts_empty_when_no_conflict():
    store = GraphStore()
    store.add_node(make_node("x", dims={"project": ["A"]}))
    store.add_node(make_node("y", dims={"project": ["B"]}))

    assert Supervision(store).detect_conflicts("A", "B") == []


# Behavior 3 ---------------------------------------------------------------


def test_detect_anomalies_foreign_nodes_case_insensitive_substring():
    store = GraphStore()
    store.add_node(make_node("in_a", dims={"project": ["A"], "topic": "Neural Networks"}))
    store.add_node(make_node("in_b", dims={"project": ["B"], "topic": "neural nets are cool"}))
    store.add_node(make_node("in_b2", dims={"project": ["B"], "tag": "NEURAL"}))
    store.add_node(make_node("unlabeled", dims={"topic": "neural"}))

    anomalies = Supervision(store).detect_anomalies(["neural"], "A")

    assert anomalies == [{"term": "neural", "node_ids": ["in_b", "in_b2", "unlabeled"]}]


def test_detect_anomalies_empty_when_no_match():
    store = GraphStore()
    store.add_node(make_node("in_a", dims={"project": ["A"], "topic": "gravity"}))

    assert Supervision(store).detect_anomalies(["quantum"], "A") == []


# Behavior 4 ---------------------------------------------------------------


def test_discover_bridges_cross_project_edges_sorted():
    store = GraphStore()
    store.add_node(make_node("a1", dims={"project": ["A"]}))
    store.add_node(make_node("a2", dims={"project": ["A"]}))
    store.add_node(make_node("b1", dims={"project": ["B"]}))
    store.add_node(make_node("b2", dims={"project": ["B"]}))
    store.add_node(make_node("noproj", dims={}))

    store.add_edge("a1", "b1", "links")
    store.add_edge("b2", "a2", "cites")
    store.add_edge("a1", "a2", "assoc")  # same project: not a bridge
    store.add_edge("a1", "noproj", "assoc")  # one endpoint project-less: not a bridge

    bridges = Supervision(store).discover_bridges()

    assert bridges == [("a1", "b1", "links"), ("b2", "a2", "cites")]


def test_discover_bridges_empty_within_single_project():
    store = GraphStore()
    store.add_node(make_node("a1", dims={"project": ["A"]}))
    store.add_node(make_node("a2", dims={"project": ["A"]}))
    store.add_edge("a1", "a2", "assoc")

    assert Supervision(store).discover_bridges() == []


# Behavior 5 ---------------------------------------------------------------


def test_supervision_is_read_only_and_never_blocks():
    store = GraphStore()
    nodes = {
        "n": make_node("n", dims={"project": ["A"], "topic": "neural nets"}),
        "m": make_node("m", dims={"project": ["B"], "topic": "neural"}),
    }
    for nd in nodes.values():
        store.add_node(nd)
    store.add_edge("n", "m", "links")
    nodes["n"].recall(1.0, strength=0.0)  # prime a trace for explain()

    sup = Supervision(store)
    results: dict[str, object] = {}

    def run_all() -> None:
        results["explain"] = sup.explain("n")
        results["conflicts"] = sup.detect_conflicts("A", "B")
        results["anomalies"] = sup.detect_anomalies(["neural"], "A")
        results["bridges"] = sup.discover_bridges()

    # Hold n's own lock to simulate an in-flight update. Supervision takes no locks,
    # so none of its calls may block behind it.
    node = store.get_node("n")
    assert node is not None
    with node.lock:
        thread = threading.Thread(target=run_all)
        thread.start()
        thread.join(timeout=2.0)
        assert not thread.is_alive(), "supervision blocked behind a node lock"

    assert set(results) == {"explain", "conflicts", "anomalies", "bridges"}


# Behavior 6 ---------------------------------------------------------------


def test_interface_import_and_shape_regression():
    context_in({"tokens": [1, 2, 3], "project": "parthenos", "emotion": "curious"})

    signals = signals_out()

    assert set(signals) >= {"priorities", "views", "alerts"}
    assert signals["priorities"] == []
    assert signals["views"] == []
    assert signals["alerts"] == []
