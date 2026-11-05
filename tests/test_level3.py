"""S3 (Level-3 lens) behavior tests.

Covers spec §1 behaviors 1-6:
  1. Membership: members carry strength weight (1.0 default); non-members linked to a
     member are attenuated by DEFAULT_ATTENUATION; isolated non-members are absent.
  2. Cross-project visibility: a member->non-member edge keeps the non-member visible at
     edge.weight * attenuation; changing attenuation changes the visible weight.
  3. Emotional override: set_emotional_override lifts a node to `power` regardless of
     membership/edges (default power 2.0), above members.
  4. Vocabulary-independence: dimension rename/merge/split never change the view.
  5. Read-only + parallel recompute: view() takes no locks and concurrent lens computes
     never block each other.
  6. Regression: interfaces import + signals_out shape unchanged.
"""

from __future__ import annotations

import threading

import pytest

from parthenos.graph import GraphStore
from parthenos.interfaces import context_in, signals_out
from parthenos.lens import DEFAULT_ATTENUATION, DEFAULT_EMOTIONAL_POWER, Lens
from parthenos.node import MemoryNode
from parthenos.vocab import DimensionVocabulary


def make_node(node_id: str, *, dims: dict | None = None) -> MemoryNode:
    return MemoryNode(
        id=node_id,
        created_at=0.0,
        last_recall=0.0,
        floatation=1.0,
        dims=dict(dims) if dims else {},
    )


# Behavior 1 ---------------------------------------------------------------


def test_membership_strength_and_nonmember_attenuation():
    store = GraphStore()
    store.add_node(make_node("member"))
    store.add_node(make_node("linked"))
    store.add_node(make_node("isolated"))
    store.add_edge("member", "linked", "assoc", weight=1.0)

    lens = Lens(store, "proj")
    lens.set_project_membership("member")  # default strength 1.0
    lens.set_project_membership("weak", 0.6)

    view = lens.view()

    assert view["member"] == pytest.approx(1.0)
    assert view["weak"] == pytest.approx(0.6)
    # linked non-member: visible at edge.weight * attenuation (1.0 * 0.1)
    assert view["linked"] == pytest.approx(1.0 * DEFAULT_ATTENUATION)
    # isolated non-member is absent from the view
    assert "isolated" not in view


# Behavior 2 ---------------------------------------------------------------


def test_cross_project_edge_weight_times_attenuation():
    store = GraphStore()
    store.add_node(make_node("m"))
    store.add_node(make_node("x"))
    store.add_edge("m", "x", "links", weight=0.8)

    lens = Lens(store, "proj")
    lens.set_project_membership("m")

    assert lens.view()["x"] == pytest.approx(0.8 * DEFAULT_ATTENUATION)

    lens.set_cross_project_attenuation(0.5)
    assert lens.view()["x"] == pytest.approx(0.8 * 0.5)


def test_cross_project_visibility_incoming_edge():
    store = GraphStore()
    store.add_node(make_node("m"))
    store.add_node(make_node("x"))
    store.add_edge("x", "m", "cites", weight=0.6)  # non-member -> member

    lens = Lens(store, "proj")
    lens.set_project_membership("m")

    assert lens.view()["x"] == pytest.approx(0.6 * DEFAULT_ATTENUATION)


# Behavior 3 ---------------------------------------------------------------


def test_emotional_override_lifts_regardless_of_membership():
    store = GraphStore()
    store.add_node(make_node("member"))
    store.add_node(make_node("nonmember"))  # isolated: no edges, no membership
    store.add_node(make_node("isolated"))

    lens = Lens(store, "proj")
    lens.set_project_membership("member")
    lens.set_emotional_override("nonmember", 2.0)

    view = lens.view()

    assert view["member"] == pytest.approx(1.0)
    assert view["nonmember"] == pytest.approx(2.0)  # above members
    assert "isolated" not in view


def test_emotional_override_default_power():
    store = GraphStore()
    store.add_node(make_node("n"))

    lens = Lens(store, "proj")
    lens.set_emotional_override("n")  # default power

    assert lens.view()["n"] == pytest.approx(DEFAULT_EMOTIONAL_POWER)


def test_emotional_override_beats_membership():
    store = GraphStore()
    store.add_node(make_node("m"))

    lens = Lens(store, "proj")
    lens.set_project_membership("m", 0.7)
    lens.set_emotional_override("m", 3.0)

    assert lens.view()["m"] == pytest.approx(3.0)


# Behavior 4 ---------------------------------------------------------------


def test_vocab_ops_do_not_change_view():
    store = GraphStore()
    store.add_node(make_node("m", dims={"mood": "calm"}))
    store.add_node(make_node("x", dims={"mood": "excited"}))
    store.add_edge("m", "x", "assoc", weight=0.9)

    lens = Lens(store, "proj")
    lens.set_project_membership("m")
    lens.set_emotional_override("x", 5.0)

    before = lens.view()

    vocab = DimensionVocabulary(store)
    vocab.register("mood")
    vocab.rename("mood", "emotion")
    vocab.merge("emotion", "nope", "merged")
    vocab.split("emotion", "a", "b")

    after = lens.view()

    # Views derive from behavior + membership, never category names: bit-identical.
    assert after == before


# Behavior 5 ---------------------------------------------------------------


def test_view_is_lock_free_and_parallel():
    store = GraphStore()
    for nid in ("a0", "a1", "b0", "b1", "shared"):
        store.add_node(make_node(nid))
    store.add_edge("a0", "a1", "assoc", weight=1.0)
    store.add_edge("a0", "shared", "links", weight=0.5)
    store.add_edge("b0", "b1", "assoc", weight=1.0)
    store.add_edge("b0", "shared", "links", weight=0.5)

    lens_a = Lens(store, "A")
    lens_b = Lens(store, "B")
    lens_a.set_project_membership("a0")
    lens_b.set_project_membership("b0")

    results: dict[str, dict[str, float]] = {}

    def compute(lens: Lens, key: str) -> None:
        results[key] = lens.view()

    threads = [
        threading.Thread(target=compute, args=(lens_a, "a")),
        threading.Thread(target=compute, args=(lens_b, "b")),
    ]

    # Hold a node's own lock to simulate an in-flight update. view() reads a snapshot
    # and takes no locks, so neither lens may block behind it.
    node = store.get_node("shared")
    assert node is not None
    with node.lock:
        for t in threads:
            t.start()
        for t in threads:
            t.join(timeout=2.0)

    assert all(not t.is_alive() for t in threads)
    assert set(results) == {"a", "b"}
    assert results["a"]["a0"] == pytest.approx(1.0)
    assert results["b"]["b0"] == pytest.approx(1.0)


# Behavior 6 ---------------------------------------------------------------


def test_interface_import_and_shape_regression():
    context_in({"tokens": [1, 2, 3], "project": "parthenos", "emotion": "curious"})

    signals = signals_out()

    assert set(signals) >= {"priorities", "views", "alerts"}
    assert signals["priorities"] == []
    assert signals["views"] == []
    assert signals["alerts"] == []
