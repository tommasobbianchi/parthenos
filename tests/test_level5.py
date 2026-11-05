"""S4b (Level-4 reorganization-proposal primitives) behavior tests.

Covers spec §1 behaviors 1-5:
  1. propose_consolidation() returns deterministic, maximal groups of >=2 nodes born
     separately (distinct created_at), in the same project, sharing >= min_shared
     non-empty dim values.
  2. propose_pruning() buckets nodes into archive/delete by floatation + age
     thresholds (delete wins over archive; deterministic ordering).
  3. estimate_context_switch_cost() returns a deterministic cost in [0, 1].
  4. Read-only + no-lock concurrency: Reorganizer calls never block on a node lock.
  5. Regression: interfaces import + signals_out shape unchanged.
"""

from __future__ import annotations

import threading

import pytest

from parthenos.graph import GraphStore
from parthenos.interfaces import context_in, signals_out
from parthenos.node import MemoryNode
from parthenos.reorganize import Reorganizer


class ManualClock:
    """Injectable clock: a callable returning a mutable float."""

    def __init__(self, t: float = 0.0) -> None:
        self.value = t

    def __call__(self) -> float:
        return self.value

    def advance(self, dt: float) -> None:
        self.value += dt


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


def test_propose_consolidation_maximal_group_and_reason():
    store = GraphStore()
    for node in (
        make_node("a1", created_at=1.0, dims={"project": ["A"], "topic": "neural", "mood": "calm"}),
        make_node("a2", created_at=2.0, dims={"project": ["A"], "topic": "neural", "mood": "calm"}),
        make_node(
            "a3",
            created_at=3.0,
            dims={"project": ["A"], "topic": "neural", "mood": "calm", "extra": "x"},
        ),
        make_node("b1", created_at=4.0, dims={"project": ["A"], "topic": "gravity"}),
        make_node("b2", created_at=5.0, dims={"project": ["B"], "topic": "neural", "mood": "calm"}),
        make_node("solo", created_at=6.0, dims={"project": ["A"], "topic": "neural"}),
    ):
        store.add_node(node)

    proposals = Reorganizer(store).propose_consolidation(min_shared=2)

    assert proposals == [{"node_ids": ["a1", "a2", "a3"], "reason": "shared dims: mood,topic"}]


def test_propose_consolidation_respects_min_shared_threshold():
    store = GraphStore()
    store.add_node(make_node("a1", created_at=1.0, dims={"project": ["A"], "topic": "neural"}))
    store.add_node(make_node("a2", created_at=2.0, dims={"project": ["A"], "topic": "neural"}))

    rz = Reorganizer(store)

    # Only one shared dim: fails the default min_shared=2 floor.
    assert rz.propose_consolidation(min_shared=2) == []
    # At min_shared=1 the single shared dim qualifies.
    assert rz.propose_consolidation(min_shared=1) == [
        {"node_ids": ["a1", "a2"], "reason": "shared dims: topic"}
    ]


def test_propose_consolidation_requires_distinct_created_at():
    store = GraphStore()
    store.add_node(
        make_node("a1", created_at=5.0, dims={"project": ["A"], "topic": "neural", "mood": "calm"})
    )
    store.add_node(
        make_node("a2", created_at=5.0, dims={"project": ["A"], "topic": "neural", "mood": "calm"})
    )

    # Same creation timestamp: born together, not "born separately".
    assert Reorganizer(store).propose_consolidation(min_shared=2) == []


# Behavior 2 ---------------------------------------------------------------


def test_propose_pruning_archive_delete_and_delete_wins():
    store = GraphStore()
    for node in (
        make_node("fresh", last_recall=95.0, floatation=0.5),   # age 5  -> nowhere
        make_node("archive_only", last_recall=80.0, floatation=0.6),  # age 20 -> archive
        make_node("delete_me", last_recall=70.0, floatation=0.1),     # age 30 -> delete
        make_node("healthy", last_recall=50.0, floatation=1.0),       # high float -> nowhere
    ):
        store.add_node(node)

    proposal = Reorganizer(store).propose_pruning(0.7, 10.0, clock=lambda: 100.0)

    # delete_me also meets the archive condition, but delete wins.
    assert proposal == {"archive": ["archive_only"], "delete": ["delete_me"]}


def test_propose_pruning_default_clock_is_real_time():
    store = GraphStore()
    store.add_node(make_node("old", last_recall=0.0, floatation=0.5))

    proposal = Reorganizer(store).propose_pruning(1.0, 1.0)

    assert proposal == {"archive": ["old"], "delete": []}


# Behavior 3 ---------------------------------------------------------------


def test_estimate_context_switch_cost_bounds_and_determinism():
    store = GraphStore()
    for node in (
        make_node("x1", dims={"project": ["A"]}),
        make_node("x2", dims={"project": ["A"]}),
        make_node("x3", dims={"project": ["A", "B"]}),
        make_node("y1", dims={"project": ["B"]}),
        make_node("y2", dims={"project": ["C"]}),
    ):
        store.add_node(node)

    rz = Reorganizer(store)

    # shared = {x3}; unique = {x1, x2, x3, y1} -> 1 - 1/4 = 0.75
    assert rz.estimate_context_switch_cost("A", "B") == pytest.approx(0.75)
    # identical project: share all members -> 0.0
    assert rz.estimate_context_switch_cost("A", "A") == pytest.approx(0.0)
    # disjoint membership -> 1.0
    assert rz.estimate_context_switch_cost("A", "C") == pytest.approx(1.0)


# Behavior 4 ---------------------------------------------------------------


def test_reorganizer_is_read_only_and_never_blocks():
    store = GraphStore()
    for node in (
        make_node(
            "a1", created_at=1.0, last_recall=0.0, floatation=0.5,
            dims={"project": ["A"], "topic": "neural"},
        ),
        make_node(
            "a2", created_at=2.0, last_recall=0.0, floatation=0.5,
            dims={"project": ["A"], "topic": "neural"},
        ),
        make_node("b1", created_at=3.0, last_recall=0.0, floatation=1.0, dims={"project": ["B"]}),
    ):
        store.add_node(node)

    rz = Reorganizer(store)
    results: dict[str, object] = {}

    def run_all() -> None:
        results["consolidation"] = rz.propose_consolidation(min_shared=1)
        results["pruning"] = rz.propose_pruning(1.0, 1.0, clock=lambda: 100.0)
        results["cost"] = rz.estimate_context_switch_cost("A", "B")

    # Hold a node's own lock to simulate an in-flight update. Reorganizer takes no
    # locks, so none of its calls may block behind it.
    node = store.get_node("a1")
    assert node is not None
    with node.lock:
        thread = threading.Thread(target=run_all)
        thread.start()
        thread.join(timeout=2.0)
        assert not thread.is_alive(), "Reorganizer blocked behind a node lock"

    assert set(results) == {"consolidation", "pruning", "cost"}


# Behavior 5 ---------------------------------------------------------------


def test_interface_import_and_shape_regression():
    context_in({"tokens": [1, 2, 3], "project": "parthenos", "emotion": "curious"})

    signals = signals_out()

    assert set(signals) >= {"priorities", "views", "alerts"}
    assert signals["priorities"] == []
    assert signals["views"] == []
    assert signals["alerts"] == []
