"""S7 (Level-7 lucid dreaming / nightly self-calibration) behavior tests.

Covers spec §1 behaviors 1-6:
  1. collect_stats() returns deterministic aggregates: total_nodes, avg_floatation,
     per_project_sink_ratio, hot_ratio, recall_frequency.
  2. propose_calibration() returns ordered deterministic proposal dicts per the
     stub docstring rules (neglect / recall / ripple), empty when no nodes.
  3. Determinism: identical store -> identical outputs across repeated calls.
  4. Non-mutation: collect_stats/propose_calibration never touch the store,
     node state, or module constants.
  5. Read-only concurrency: proposal generation completes while a node lock is
     held elsewhere (no locks taken).
  6. Regression: signals_out shape unchanged.
"""

from __future__ import annotations

import threading

from parthenos.dream import Calibrator
from parthenos.fovea import DEFAULT_RIPPLE_BETA
from parthenos.graph import GraphStore
from parthenos.interfaces import signals_out
from parthenos.node import (
    DEFAULT_NEGLECT_RATE,
    DEFAULT_RECALL_STRENGTH,
    MemoryNode,
)
from parthenos.serialize import Snapshotter


def make_node(
    node_id: str,
    *,
    created_at: float = 0.0,
    last_recall: float = 0.0,
    floatation: float = 1.0,
    project: object = None,
) -> MemoryNode:
    dims: dict = {}
    if project is not None:
        dims["project"] = project
    return MemoryNode(
        id=node_id,
        created_at=created_at,
        last_recall=last_recall,
        floatation=floatation,
        dims=dims,
    )


def build_store() -> tuple[GraphStore, Calibrator]:
    """A store with two projects, a multi-project node, and an orphan.

    Node / floatation / last_recall / project:
      a  0.9   1.0  "P"
      b  0.5   2.0  "P"
      c  0.5   3.0  "P"
      d  1.0   4.0  "P"       (not sinking: not < 1.0)
      m  0.7   5.0  ["P","Q"] (multi-project)
      q  0.8   6.0  "Q"
      r  0.1   7.0  "Q"
      o  0.99  0.0  None      (orphan; last_recall == created_at -> not recalled)
    """
    store = GraphStore()
    store.add_node(make_node("a", last_recall=1.0, floatation=0.9, project="P"))
    store.add_node(make_node("b", last_recall=2.0, floatation=0.5, project="P"))
    store.add_node(make_node("c", last_recall=3.0, floatation=0.5, project="P"))
    store.add_node(make_node("d", last_recall=4.0, floatation=1.0, project="P"))
    store.add_node(make_node("m", last_recall=5.0, floatation=0.7, project=["P", "Q"]))
    store.add_node(make_node("q", last_recall=6.0, floatation=0.8, project="Q"))
    store.add_node(make_node("r", last_recall=7.0, floatation=0.1, project="Q"))
    store.add_node(make_node("o", last_recall=0.0, floatation=0.99))
    return store, Calibrator(store)


# Behavior 1 ---------------------------------------------------------------


def test_collect_stats_aggregates():
    _store, calibrator = build_store()

    stats = calibrator.collect_stats()

    assert set(stats) == {
        "total_nodes",
        "avg_floatation",
        "per_project_sink_ratio",
        "hot_ratio",
        "recall_frequency",
    }
    assert stats["total_nodes"] == 8
    # (0.9+0.5+0.5+1.0+0.7+0.8+0.1+0.99)/8 == 0.68625
    assert stats["avg_floatation"] == 0.68625
    # P: a,b,c,m sink (4/5); Q: m,q,r sink (3/3)
    assert stats["per_project_sink_ratio"] == {"P": 0.8, "Q": 1.0}
    # a(0.9), d(1.0), q(0.8), o(0.99) -> 4/8
    assert stats["hot_ratio"] == 0.5
    # every node except o has last_recall > created_at -> 7/8
    assert stats["recall_frequency"] == 0.875


def test_collect_stats_empty_store():
    calibrator = Calibrator(GraphStore())

    assert calibrator.collect_stats() == {
        "total_nodes": 0,
        "avg_floatation": 0.0,
        "per_project_sink_ratio": {},
        "hot_ratio": 0.0,
        "recall_frequency": 0.0,
    }


def test_collect_stats_recall_frequency_and_project_sink_edges():
    store = GraphStore()
    # recalled: last_recall strictly greater than created_at
    store.add_node(make_node("x", created_at=5.0, last_recall=5.0, floatation=0.2, project="A"))
    store.add_node(make_node("y", created_at=0.0, last_recall=1.0, floatation=0.5, project="A"))
    calibrator = Calibrator(store)

    stats = calibrator.collect_stats()

    assert stats["recall_frequency"] == 0.5  # only y
    assert stats["per_project_sink_ratio"] == {"A": 1.0}


# Behavior 2 ---------------------------------------------------------------


def test_propose_calibration_all_rules_trigger():
    store = GraphStore()
    # avg_floatation = 6.4/13 = 0.4923... < 0.5 -> neglect
    # hot_ratio = 8/13 > 0.6 -> recall
    # P and Q sink ratio 1.0 > 0.7 -> ripple
    for i in range(8):
        store.add_node(make_node(f"hot{i}", floatation=0.8, project="P"))
    for i in range(5):
        store.add_node(make_node(f"cold{i}", floatation=0.0, project="Q"))
    calibrator = Calibrator(store)

    proposals = calibrator.propose_calibration()

    assert proposals == [
        {
            "parameter": "DEFAULT_NEGLECT_RATE",
            "current": DEFAULT_NEGLECT_RATE,
            "proposed": round(DEFAULT_NEGLECT_RATE * 0.8, 6),
            "rationale": "avg_floatation < 0.5",
        },
        {
            "parameter": "DEFAULT_RECALL_STRENGTH",
            "current": DEFAULT_RECALL_STRENGTH,
            "proposed": round(DEFAULT_RECALL_STRENGTH * 1.1, 6),
            "rationale": "hot_ratio > 0.6",
        },
        {
            "parameter": "DEFAULT_RIPPLE_BETA",
            "current": DEFAULT_RIPPLE_BETA,
            "proposed": round(DEFAULT_RIPPLE_BETA * 0.9, 6),
            "rationale": "sink ratio > 0.7",
        },
    ]


def test_propose_calibration_empty_store():
    assert Calibrator(GraphStore()).propose_calibration() == []


def test_propose_calibration_no_rules_trigger():
    store = GraphStore()
    # avg >= 0.5, hot_ratio <= 0.6, no project members (sink ratio empty)
    store.add_node(make_node("a", floatation=0.6))
    calibrator = Calibrator(store)

    assert calibrator.propose_calibration() == []


# Behavior 3 ---------------------------------------------------------------


def test_determinism_identical_outputs():
    _store, calibrator = build_store()

    stats1 = calibrator.collect_stats()
    stats2 = calibrator.collect_stats()
    proposals1 = calibrator.propose_calibration()
    proposals2 = calibrator.propose_calibration()

    assert stats1 == stats2
    assert proposals1 == proposals2
    # deterministic project key order
    assert list(stats1["per_project_sink_ratio"]) == ["P", "Q"]


# Behavior 4 ---------------------------------------------------------------


def test_no_mutation_of_store_or_constants():
    store, calibrator = build_store()

    snapshotter = Snapshotter(store, clock=lambda: 123.0)
    before = snapshotter.snapshot()

    const_before = (
        DEFAULT_NEGLECT_RATE,
        DEFAULT_RECALL_STRENGTH,
        DEFAULT_RIPPLE_BETA,
    )

    calibrator.collect_stats()
    calibrator.propose_calibration()

    after = snapshotter.snapshot()

    # only version/taken_at may differ across snapshot calls; content is stable
    assert after["nodes"] == before["nodes"]
    assert after["edges"] == before["edges"]

    assert (
        DEFAULT_NEGLECT_RATE,
        DEFAULT_RECALL_STRENGTH,
        DEFAULT_RIPPLE_BETA,
    ) == const_before


# Behavior 5 ---------------------------------------------------------------


def test_calibration_does_not_block_on_node_lock():
    store, calibrator = build_store()

    node = store.get_node("a")
    assert node is not None

    results: dict[str, object] = {}

    def capture() -> None:
        results["stats"] = calibrator.collect_stats()
        results["proposals"] = calibrator.propose_calibration()

    with node.lock:
        thread = threading.Thread(target=capture)
        thread.start()
        thread.join(timeout=2.0)
        assert not thread.is_alive(), "calibrator blocked behind a node lock"

    assert "stats" in results
    assert "proposals" in results


# Behavior 6 ---------------------------------------------------------------


def test_signals_out_shape_regression():
    signals = signals_out()

    assert set(signals) >= {"priorities", "views", "alerts"}
    assert signals["priorities"] == []
    assert signals["views"] == []
    assert signals["alerts"] == []
