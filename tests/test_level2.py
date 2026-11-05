"""S2 (Level-2 graph + vocabulary) behavior tests.

Covers spec §1 behaviors 1-6:
  1. GraphStore.add_node/get_node round-trips; re-registering replaces.
  2. GraphStore.add_edge raises KeyError for absent endpoints; edges are
     visible via neighbors(kind=None) and carry weight; remove_edge is a
     truthy-returning removal.
  3. GraphStore.set_dim/get_dim persist any-named dims; unset dims read back
     as the Missing sentinel (so None stays a real value).
  4. DimensionVocabulary rename/merge/split propagate atomically and never
     change floatation (behavior-independent).
  5. set_dim on disjoint nodes does not block (per-node locks, no whole-graph lock).
  6. Regression: interfaces import + signals_out shape unchanged (L1 surface).
"""

from __future__ import annotations

import threading

import pytest

from parthenos.graph import GraphStore, Missing
from parthenos.interfaces import context_in, signals_out
from parthenos.node import MemoryNode
from parthenos.vocab import DimensionVocabulary


def make_node(node_id: str, *, dims: dict | None = None, floatation: float = 1.0) -> MemoryNode:
    return MemoryNode(
        id=node_id,
        created_at=0.0,
        last_recall=0.0,
        floatation=floatation,
        dims=dict(dims) if dims else {},
    )


# Behavior 1 ---------------------------------------------------------------


def test_add_get_node_round_trip_and_replacement():
    store = GraphStore()
    first = make_node("n0", dims={"mood": "calm"})
    assert store.add_node(first) is first
    assert store.get_node("n0") is first
    assert store.get_node("ghost") is None

    # Re-registering an id replaces the stored node.
    second = make_node("n0", dims={"mood": "excited"})
    store.add_node(second)
    assert store.get_node("n0") is second
    assert store.get_node("n0") is not first


# Behavior 2 ---------------------------------------------------------------


def test_add_edge_endpoints_neighbors_remove():
    store = GraphStore()
    store.add_node(make_node("n0"))
    store.add_node(make_node("n1"))
    store.add_node(make_node("n2"))

    with pytest.raises(KeyError):
        store.add_edge("n0", "ghost", "assoc")
    with pytest.raises(KeyError):
        store.add_edge("ghost", "n1", "assoc")

    e1 = store.add_edge("n0", "n1", "assoc", weight=0.7)
    e2 = store.add_edge("n0", "n2", "links", weight=0.3)

    assert e1.target_id == "n1"
    assert e1.kind == "assoc"
    assert e1.weight == 0.7

    assert store.neighbors("n0") == [e1, e2]
    assert store.neighbors("n0", kind="assoc") == [e1]
    assert store.neighbors("n0", kind="links") == [e2]
    assert store.neighbors("n0", kind="nope") == []
    assert store.neighbors("n1") == []

    assert store.remove_edge("n0", "n1") is True
    assert store.remove_edge("n0", "n1") is False
    assert store.neighbors("n0") == [e2]


# Behavior 3 ---------------------------------------------------------------


def test_dim_persistence_any_name_none_and_missing_sentinel():
    store = GraphStore()
    store.add_node(make_node("n"))

    store.set_dim("n", "sentiment", "curious")
    assert store.get_dim("n", "sentiment") == "curious"

    # Any name is legal (living vocabulary).
    store.set_dim("n", "x-arbitrary/tag", 42)
    assert store.get_dim("n", "x-arbitrary/tag") == 42

    # None is a real value, distinct from the Missing sentinel.
    store.set_dim("n", "emoji", None)
    assert store.get_dim("n", "emoji") is None

    # A never-set dim reads back as Missing, not None.
    assert store.get_dim("n", "never-set") is Missing
    assert store.get_dim("n", "never-set") is not None


# Behavior 4 ---------------------------------------------------------------


def test_vocab_rename_moves_values_and_unions_existing():
    store = GraphStore()
    store.add_node(make_node("n0", dims={"mood": "calm", "emotion": "peaceful"}))
    store.add_node(make_node("n1", dims={"mood": "excited"}))
    store.add_node(make_node("n2", dims={}))

    vocab = DimensionVocabulary(store)
    vocab.register("mood")
    vocab.register("emotion")

    vocab.rename("mood", "emotion")

    assert store.get_dim("n0", "mood") is Missing
    assert store.get_dim("n1", "mood") is Missing
    # Rename to an existing name unions both.
    assert store.get_dim("n0", "emotion") == {"calm", "peaceful"}
    assert store.get_dim("n1", "emotion") == "excited"
    assert store.get_dim("n2", "emotion") is Missing

    # 'mood' is no longer a known dimension.
    with pytest.raises(KeyError):
        vocab.rename("mood", "whatever")


def test_vocab_merge_unions_values():
    store = GraphStore()
    store.add_node(make_node("n0", dims={"a": "x", "b": "y"}))
    store.add_node(make_node("n1", dims={"a": "z"}))
    store.add_node(make_node("n2", dims={}))

    vocab = DimensionVocabulary(store)
    vocab.merge("a", "b", "c")

    assert store.get_dim("n0", "a") is Missing
    assert store.get_dim("n0", "b") is Missing
    assert store.get_dim("n0", "c") == {"x", "y"}
    assert store.get_dim("n1", "a") is Missing
    assert store.get_dim("n1", "c") == "z"
    assert store.get_dim("n2", "c") is Missing


def test_vocab_split_default_and_custom():
    store = GraphStore()
    store.add_node(make_node("n0", dims={"full": "Hello World"}))

    vocab = DimensionVocabulary(store)
    # Default splitter value -> (value, None): 'a' gets the value, 'b' stays absent.
    vocab.split("full", "first", "second")

    assert store.get_dim("n0", "full") is Missing
    assert store.get_dim("n0", "first") == "Hello World"
    assert store.get_dim("n0", "second") is Missing

    # A custom splitter is honored.
    store2 = GraphStore()
    store2.add_node(make_node("m", dims={"name": "Jane Doe"}))
    vocab2 = DimensionVocabulary(store2)
    vocab2.split("name", "first", "last", splitter=lambda v: tuple(v.split(" ", 1)))

    assert store2.get_dim("m", "name") is Missing
    assert store2.get_dim("m", "first") == "Jane"
    assert store2.get_dim("m", "last") == "Doe"


def test_vocab_ops_do_not_change_floatation():
    store = GraphStore()
    nodes = {
        "n0": store.add_node(make_node("n0", dims={"mood": "calm"}, floatation=0.7)),
        "n1": store.add_node(make_node("n1", dims={"mood": "excited"}, floatation=0.3)),
        "n2": store.add_node(make_node("n2", dims={}, floatation=0.9)),
    }
    nodes["n0"].last_recall = 11.0
    nodes["n1"].last_recall = 22.0
    nodes["n2"].last_recall = 33.0

    before_float = {nid: node.floatation for nid, node in nodes.items()}
    before_recall = {nid: node.last_recall for nid, node in nodes.items()}

    vocab = DimensionVocabulary(store)
    vocab.register("mood")
    vocab.rename("mood", "emotion")
    vocab.merge("emotion", "nope", "merged")
    vocab.split("emotion", "x", "y")

    for nid, node in nodes.items():
        assert node.floatation == before_float[nid]  # bit-identical: never touched
        assert node.last_recall == before_recall[nid]


# Behavior 5 ---------------------------------------------------------------


def test_set_dim_on_disjoint_nodes_does_not_block():
    store = GraphStore()
    a = store.add_node(make_node("a"))
    b = store.add_node(make_node("b"))

    # Per-node locks: a and b own distinct locks.
    assert a.lock is not b.lock

    done = threading.Event()

    def worker() -> None:
        store.set_dim("b", "tag", "written")
        done.set()

    # Hold a's own lock to simulate an in-flight update on node a.
    # A whole-graph lock would make set_dim(b) block behind it.
    with a.lock:
        thread = threading.Thread(target=worker)
        thread.start()
        thread.join(timeout=2.0)
        assert not thread.is_alive(), "set_dim(b) blocked behind a's lock"

    assert done.is_set()
    assert store.get_dim("b", "tag") == "written"
    assert store.get_dim("a", "tag") is Missing


# Behavior 6 ---------------------------------------------------------------


def test_interface_import_and_shape_regression():
    context_in({"tokens": [1, 2, 3], "project": "parthenos", "emotion": "curious"})
    signals = signals_out()

    assert set(signals) >= {"priorities", "views", "alerts"}
    assert signals["priorities"] == []
    assert signals["views"] == []
    assert signals["alerts"] == []


def test_edge_temporal_fields_default_and_override():
    store = GraphStore()
    store.add_node(make_node("n0"))
    store.add_node(make_node("n1"))
    store.add_node(make_node("n2"))

    plain = store.add_edge("n0", "n1", "assoc")
    assert plain.valid_at is None
    assert plain.invalid_at is None

    timed = store.add_edge("n0", "n2", "tmp", weight=0.5, valid_at=10.0, invalid_at=20.0)
    assert timed.valid_at == 10.0
    assert timed.invalid_at == 20.0
