"""S1 (Level-1 core) behavior tests.

Covers spec §1 behaviors 1-6:
  1. ingest absorbs an event and returns a promoted MemoryNode (floatation == 1.0).
  2. recall raises floatation toward 1.0; neglect/time lowers it toward 0.0 (injectable clock).
  3. FoveaEngine.stimulate ripples with beta**h decay, bounded by radius.
  4. Per-node synchronization: concurrent stimulate on disjoint nodes never blocks.
  5. context_in / signals_out expose a stable return shape and never touch the graph.
  6. Events reject unknown kinds with ValueError.
"""

from __future__ import annotations

import threading

import pytest

from parthenos.buffer import EphemeralBuffer
from parthenos.events import EVENT_KINDS, Event
from parthenos.fovea import DEFAULT_RADIUS, DEFAULT_RIPPLE_BETA, FoveaEngine
from parthenos.interfaces import context_in, signals_out
from parthenos.node import MemoryNode, TypedEdge


class ManualClock:
    """Injectable clock: a callable returning a mutable float."""

    def __init__(self, t: float = 0.0) -> None:
        self.value = t

    def __call__(self) -> float:
        return self.value

    def advance(self, dt: float) -> None:
        self.value += dt


def make_chain(n: int = 6, floatation: float = 0.0) -> dict[str, MemoryNode]:
    """Build a directional chain n0 -> n1 -> ... -> n{n-1} of MemoryNodes."""
    nodes: dict[str, MemoryNode] = {}
    for i in range(n):
        nodes[f"n{i}"] = MemoryNode(
            id=f"n{i}", created_at=0.0, last_recall=0.0, floatation=floatation
        )
    for i in range(n - 1):
        nodes[f"n{i}"].edges.append(TypedEdge(target_id=f"n{i+1}", kind="assoc"))
    return nodes


# Behavior 1 ---------------------------------------------------------------


def test_ingest_promotes_node_with_floatation_one():
    clock = ManualClock(123.0)
    buf = EphemeralBuffer(clock=clock)
    event = Event(kind="ingest", payload={"node_id": "n0"})

    node = buf.ingest(event)

    assert isinstance(node, MemoryNode)
    assert node.id == "n0"
    assert node.created_at == 123.0
    assert node.last_recall == 123.0
    assert node.floatation == 1.0
    # the event landed in the ephemeral buffer
    assert event in buf.drain()
    # the promoted node is stored in the in-memory, id-keyed store
    assert buf.nodes["n0"] is node


# Behavior 2 ---------------------------------------------------------------


def test_recall_raises_and_neglect_lowers_floatation():
    clock = ManualClock(100.0)
    buf = EphemeralBuffer(clock=clock)
    node = buf.ingest(Event(kind="ingest", payload={"node_id": "a"}))
    assert node.floatation == 1.0

    clock.advance(10.0)  # 10 time units without recall
    lowered = buf.neglect(node)
    assert 0.0 < lowered < 1.0

    raised = buf.recall(node)
    assert raised == 1.0  # clamps at the ceiling
    assert node.last_recall == 110.0

    clock.advance(30.0)  # long absence -> sinks to the floor
    sunk = buf.neglect(node)
    assert sunk >= 0.0
    assert node.floatation == sunk
    assert node.floatation == 0.0


# Behavior 3 ---------------------------------------------------------------


def test_stimulate_ripples_with_beta_decay_and_respects_radius():
    nodes = make_chain(n=6, floatation=0.0)
    engine = FoveaEngine(beta=0.5, radius=3)

    deltas = engine.stimulate(nodes["n0"], intensity=1.0, graph=nodes)

    assert deltas == {"n0": 1.0, "n1": 0.5, "n2": 0.25, "n3": 0.125}
    assert "n4" not in deltas
    assert "n5" not in deltas
    assert nodes["n4"].floatation == 0.0
    assert nodes["n5"].floatation == 0.0


def test_stimulate_uses_default_beta_and_radius():
    nodes = make_chain(n=6, floatation=0.0)
    engine = FoveaEngine()
    assert engine.beta == DEFAULT_RIPPLE_BETA == 0.5
    assert engine.radius == DEFAULT_RADIUS == 3

    deltas = engine.stimulate(nodes["n0"], intensity=1.0, graph=nodes)
    assert "n3" in deltas
    assert "n4" not in deltas


# Behavior 4 ---------------------------------------------------------------


def test_concurrent_stimulate_on_disjoint_nodes_does_not_block():
    nodes = make_chain(n=8, floatation=0.0)
    engine = FoveaEngine(beta=0.5, radius=3)

    # Per-node synchronization: each node owns a distinct lock (never one shared lock).
    assert nodes["n0"].lock is not nodes["n6"].lock

    done = threading.Event()
    deltas: list[dict[str, float]] = []

    def worker() -> None:
        deltas.append(engine.stimulate(nodes["n6"], intensity=0.5, graph=nodes))
        done.set()

    # Hold n0's own lock to simulate an in-flight update on n0's neighborhood.
    # A whole-graph lock would make stimulate(n6) block behind it.
    with nodes["n0"].lock:
        thread = threading.Thread(target=worker)
        thread.start()
        thread.join(timeout=2.0)
        assert not thread.is_alive(), "stimulate(n6) blocked behind n0's lock"

    assert done.is_set()
    assert deltas and deltas[0] == {"n6": 0.5, "n7": 0.25}
    assert nodes["n6"].floatation == 0.5
    assert nodes["n0"].floatation == 0.0  # n0 untouched by n6's disjoint neighborhood


# Behavior 5 ---------------------------------------------------------------


def test_interface_return_shape_is_stable():
    context_in({"tokens": [1, 2, 3], "project": "parthenos", "emotion": "curious"})

    signals = signals_out()

    assert set(signals) >= {"priorities", "views", "alerts"}
    assert signals["priorities"] == []
    assert signals["views"] == []
    assert signals["alerts"] == []


# Behavior 6 ---------------------------------------------------------------


def test_event_rejects_unknown_kind():
    with pytest.raises(ValueError):
        Event(kind="not-a-real-kind", payload={})

    assert Event(kind="ingest").kind == "ingest"
    assert "ingest" in EVENT_KINDS
