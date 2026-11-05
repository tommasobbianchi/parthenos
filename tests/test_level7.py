"""S6 (Level-6 telemetry + predictive pre-fetch) behavior tests.

Covers spec §1 behaviors 1-6:
  1. heat_map(top_k) returns {project_id: [{node_id, floatation}, ...]} for
     project members only, sorted by floatation descending then node id
     ascending, truncated to top_k per project; empty dict with no members.
  2. sinking_trends(project_id, limit) returns [{node_id, floatation,
     last_recall}] for members with floatation < 1.0, sorted by floatation
     ascending then node id ascending, truncated to limit.
  3. health() returns {total_nodes, projects, avg_floatation, conflicting_nodes,
     hot_nodes} with deterministic aggregates.
  4. prefetch_candidates(threshold) returns ids with floatation >= threshold,
     sorted by floatation descending then id ascending.
  5. Read-only concurrency: Telemetry calls never block behind a node lock.
  6. Regression: interfaces import + signals_out shape unchanged.
"""

from __future__ import annotations

import threading

from parthenos.graph import GraphStore
from parthenos.interfaces import signals_out
from parthenos.node import MemoryNode
from parthenos.telemetry import Telemetry


def make_node(
    node_id: str,
    *,
    last_recall: float = 0.0,
    floatation: float = 1.0,
    project: object = None,
) -> MemoryNode:
    dims: dict = {}
    if project is not None:
        dims["project"] = project
    return MemoryNode(
        id=node_id,
        created_at=0.0,
        last_recall=last_recall,
        floatation=floatation,
        dims=dims,
    )


def build_store() -> tuple[GraphStore, Telemetry]:
    """A store with two projects, a multi-project node, and an orphan.

    Node / floatation / last_recall / project:
      a  0.9   1.0  "P"
      b  0.5   2.0  "P"
      c  0.5   3.0  "P"
      d  1.0   4.0  "P"       (sinking excludes: not < 1.0)
      m  0.7   5.0  ["P","Q"] (multi-project / conflicting)
      q  0.8   6.0  "Q"
      r  0.1   7.0  "Q"
      o  0.99  8.0  None      (orphan: no project dim)
    """
    store = GraphStore()
    store.add_node(make_node("a", last_recall=1.0, floatation=0.9, project="P"))
    store.add_node(make_node("b", last_recall=2.0, floatation=0.5, project="P"))
    store.add_node(make_node("c", last_recall=3.0, floatation=0.5, project="P"))
    store.add_node(make_node("d", last_recall=4.0, floatation=1.0, project="P"))
    store.add_node(make_node("m", last_recall=5.0, floatation=0.7, project=["P", "Q"]))
    store.add_node(make_node("q", last_recall=6.0, floatation=0.8, project="Q"))
    store.add_node(make_node("r", last_recall=7.0, floatation=0.1, project="Q"))
    store.add_node(make_node("o", last_recall=8.0, floatation=0.99))
    return store, Telemetry(store)


# Behavior 1 ---------------------------------------------------------------


def test_heat_map_sorted_desc_then_id_and_truncated():
    _store, telemetry = build_store()

    result = telemetry.heat_map(top_k=10)

    # only project members; orphan "o" excluded; multi-project "m" in both
    assert set(result) == {"P", "Q"}
    assert [entry["node_id"] for entry in result["P"]] == ["d", "a", "m", "b", "c"]
    assert [entry["floatation"] for entry in result["P"]] == [1.0, 0.9, 0.7, 0.5, 0.5]
    assert [entry["node_id"] for entry in result["Q"]] == ["q", "m", "r"]
    assert [entry["floatation"] for entry in result["Q"]] == [0.8, 0.7, 0.1]

    # each entry carries exactly {node_id, floatation}
    assert all(set(entry) == {"node_id", "floatation"} for entry in result["P"])

    # top_k truncation per project (descending order preserved)
    truncated = telemetry.heat_map(top_k=2)
    assert [entry["node_id"] for entry in truncated["P"]] == ["d", "a"]
    assert [entry["node_id"] for entry in truncated["Q"]] == ["q", "m"]


def test_heat_map_tie_break_node_id_ascending():
    store = GraphStore()
    # identical floatation within one project -> node id ascending
    store.add_node(make_node("z", floatation=0.5, project="P"))
    store.add_node(make_node("a", floatation=0.5, project="P"))
    store.add_node(make_node("m", floatation=0.5, project="P"))
    telemetry = Telemetry(store)

    result = telemetry.heat_map()

    assert [entry["node_id"] for entry in result["P"]] == ["a", "m", "z"]


def test_heat_map_empty_and_orphan_only():
    store = GraphStore()
    assert Telemetry(store).heat_map() == {}

    store.add_node(make_node("orphan", floatation=0.99))
    assert Telemetry(store).heat_map() == {}


def test_heat_map_nonpositive_top_k_empty():
    store = GraphStore()
    store.add_node(make_node("a", floatation=0.9, project="P"))
    telemetry = Telemetry(store)

    assert telemetry.heat_map(top_k=0) == {"P": []}
    assert telemetry.heat_map(top_k=-3) == {"P": []}


# Behavior 2 ---------------------------------------------------------------


def test_sinking_trends_sorted_asc_then_id_with_last_recall():
    _store, telemetry = build_store()

    result = telemetry.sinking_trends("P", limit=10)

    # only members with floatation < 1.0 (d at 1.0 excluded); most sunk first
    assert [entry["node_id"] for entry in result] == ["b", "c", "m", "a"]
    assert [entry["floatation"] for entry in result] == [0.5, 0.5, 0.7, 0.9]
    assert [entry["last_recall"] for entry in result] == [2.0, 3.0, 5.0, 1.0]
    assert all(set(entry) == {"node_id", "floatation", "last_recall"} for entry in result)


def test_sinking_trends_limit_and_unknown_project():
    _store, telemetry = build_store()

    limited = telemetry.sinking_trends("P", limit=2)
    assert [entry["node_id"] for entry in limited] == ["b", "c"]

    assert telemetry.sinking_trends("P", limit=0) == []
    assert telemetry.sinking_trends("P", limit=-1) == []
    assert telemetry.sinking_trends("Z", limit=10) == []


# Behavior 3 ---------------------------------------------------------------


def test_health_aggregates_deterministic():
    _store, telemetry = build_store()

    health = telemetry.health()

    assert set(health) == {
        "total_nodes",
        "projects",
        "avg_floatation",
        "conflicting_nodes",
        "hot_nodes",
    }
    assert health["total_nodes"] == 8
    assert health["projects"] == 2
    # (0.9+0.5+0.5+1.0+0.7+0.8+0.1+0.99)/8 == 0.68625
    assert health["avg_floatation"] == 0.68625
    assert health["conflicting_nodes"] == 1  # only "m" spans 2 projects
    assert health["hot_nodes"] == 4  # a(0.9), d(1.0), q(0.8), o(0.99)


def test_health_empty_store():
    telemetry = Telemetry(GraphStore())

    health = telemetry.health()

    assert health == {
        "total_nodes": 0,
        "projects": 0,
        "avg_floatation": 0.0,
        "conflicting_nodes": 0,
        "hot_nodes": 0,
    }


# Behavior 4 ---------------------------------------------------------------


def test_prefetch_candidates_sorted_and_threshold():
    _store, telemetry = build_store()

    # default threshold 0.8: a(0.9), d(1.0), q(0.8), o(0.99)
    assert telemetry.prefetch_candidates() == ["d", "o", "a", "q"]

    # stricter threshold excludes q(0.8) and a(0.9) -> d(1.0), o(0.99)
    assert telemetry.prefetch_candidates(threshold=0.95) == ["d", "o"]

    # no node above an impossible ceiling
    assert telemetry.prefetch_candidates(threshold=2.0) == []


# Behavior 5 ---------------------------------------------------------------


def test_telemetry_calls_do_not_block_on_node_lock():
    store, telemetry = build_store()

    node = store.get_node("a")
    assert node is not None

    results: dict[str, object] = {}

    def capture() -> None:
        results["heat_map"] = telemetry.heat_map()
        results["sinking"] = telemetry.sinking_trends("P")
        results["health"] = telemetry.health()
        results["prefetch"] = telemetry.prefetch_candidates()

    with node.lock:
        thread = threading.Thread(target=capture)
        thread.start()
        thread.join(timeout=2.0)
        assert not thread.is_alive(), "telemetry blocked behind a node lock"

    assert "heat_map" in results
    assert "sinking" in results
    assert "health" in results
    assert "prefetch" in results
    assert results["health"] == {
        "total_nodes": 8,
        "projects": 2,
        "avg_floatation": 0.68625,
        "conflicting_nodes": 1,
        "hot_nodes": 4,
    }


# Behavior 6 ---------------------------------------------------------------


def test_signals_out_shape_regression():
    signals = signals_out()

    assert set(signals) >= {"priorities", "views", "alerts"}
    assert signals["priorities"] == []
    assert signals["views"] == []
    assert signals["alerts"] == []
