"""S8 (Level-8 substrate adapters) behavior tests.

Covers spec §1 behaviors 1-6:
  1. SubstrateAdapter.store_memory normalizes a MemoryNode to
     {"node_id", "payload": {"id", "floatation", "dims"}}, calls backend.add,
     returns the normalized dict, and wraps backend errors in SubstrateError.
  2. SubstrateAdapter.retrieve calls backend.search(query, k), returns
     [{node_id, score}] sorted by score desc (tie-break node_id asc), missing
     scores default to 0.0.
  3. SubstrateAdapter.link_nodes calls backend.link(...); backend rejections
     surface as SubstrateError.
  4. The three concrete adapters (Mem0Adapter, ZepAdapter, CogneeAdapter) inherit
     identical normalization behavior.
  5. Error normalization: RuntimeError/KeyError propagate as SubstrateError with
     the original message preserved and the original exception as the cause.
  6. Stable-interface regression: parthenos.interfaces still imports and
     signals_out() keeps its shape.
"""

from __future__ import annotations

import pytest

from parthenos.adapters import (
    CogneeAdapter,
    Mem0Adapter,
    SubstrateAdapter,
    SubstrateError,
    ZepAdapter,
)
from parthenos.interfaces import signals_out
from parthenos.node import MemoryNode


class FakeBackend:
    """Duck-typed in-memory substrate backend (no real substrate SDK)."""

    def __init__(self) -> None:
        self.added: list[tuple[str, dict]] = []
        self.linked: list[tuple[str, str, str]] = []
        self.get_calls: int = 0
        self.results: list[dict] = []
        self.last_search: tuple[str, int] | None = None
        self.add_error: Exception | None = None
        self.link_error: Exception | None = None

    def add(self, node_id: str, payload: dict) -> None:
        if self.add_error is not None:
            raise self.add_error
        self.added.append((node_id, payload))

    def get(self, node_id: str) -> dict | None:
        self.get_calls += 1
        return None

    def link(self, src_id: str, tgt_id: str, kind: str) -> None:
        if self.link_error is not None:
            raise self.link_error
        self.linked.append((src_id, tgt_id, kind))

    def search(self, query: str, k: int) -> list[dict]:
        self.last_search = (query, k)
        return list(self.results)


def make_node(node_id: str = "n1", floatation: float = 0.7) -> MemoryNode:
    return MemoryNode(
        id=node_id,
        created_at=0.0,
        last_recall=0.0,
        floatation=floatation,
        dims={"project": "P", "tag": "x"},
    )


# Behavior 1 ---------------------------------------------------------------


def test_store_memory_normalizes_and_calls_add():
    backend = FakeBackend()
    adapter = SubstrateAdapter(backend)
    node = make_node()

    result = adapter.store_memory(node)

    payload = {"id": "n1", "floatation": 0.7, "dims": {"project": "P", "tag": "x"}}
    assert result == {"node_id": "n1", "payload": payload}
    assert backend.added == [("n1", payload)]
    assert backend.get_calls == 0  # store_memory never touches backend.get


def test_store_memory_wraps_backend_error():
    backend = FakeBackend()
    backend.add_error = RuntimeError("backend down")
    adapter = SubstrateAdapter(backend)

    with pytest.raises(SubstrateError) as exc_info:
        adapter.store_memory(make_node())

    assert str(exc_info.value) == "backend down"
    assert isinstance(exc_info.value.__cause__, RuntimeError)


# Behavior 2 ---------------------------------------------------------------


def test_retrieve_sorts_desc_and_defaults_missing_score():
    backend = FakeBackend()
    backend.results = [
        {"node_id": "a", "score": 0.5},
        {"node_id": "b", "score": 0.9},
        {"node_id": "c"},  # missing score -> 0.0
        {"node_id": "d", "score": 0.9},
    ]
    adapter = SubstrateAdapter(backend)

    result = adapter.retrieve("what is parthenos?")

    assert backend.last_search == ("what is parthenos?", 5)  # default k=5
    assert result == [
        {"node_id": "b", "score": 0.9},
        {"node_id": "d", "score": 0.9},
        {"node_id": "a", "score": 0.5},
        {"node_id": "c", "score": 0.0},
    ]


def test_retrieve_passes_k_to_backend():
    backend = FakeBackend()
    backend.results = []
    adapter = SubstrateAdapter(backend)

    adapter.retrieve("q", k=3)

    assert backend.last_search == ("q", 3)


# Behavior 3 ---------------------------------------------------------------


def test_link_nodes_calls_backend_link():
    backend = FakeBackend()
    adapter = SubstrateAdapter(backend)

    adapter.link_nodes("a", "b")
    adapter.link_nodes("b", "c", kind="cites")

    assert backend.linked == [("a", "b", "assoc"), ("b", "c", "cites")]


def test_link_nodes_wraps_backend_error():
    backend = FakeBackend()
    backend.link_error = KeyError("missing")
    adapter = SubstrateAdapter(backend)

    with pytest.raises(SubstrateError) as exc_info:
        adapter.link_nodes("a", "b")

    assert str(exc_info.value) == "'missing'"
    assert isinstance(exc_info.value.__cause__, KeyError)


# Behavior 4 ---------------------------------------------------------------


def test_three_adapters_share_identical_behavior():
    node = make_node()
    outputs: list[tuple] = []
    for adapter_cls in (Mem0Adapter, ZepAdapter, CogneeAdapter):
        backend = FakeBackend()
        backend.results = [{"node_id": "x", "score": 0.3}]
        adapter = adapter_cls(backend)
        stored = adapter.store_memory(node)
        retrieved = adapter.retrieve("q")
        adapter.link_nodes("n1", "x")
        outputs.append(
            (stored, retrieved, tuple(backend.added), tuple(backend.linked))
        )

    assert outputs[0] == outputs[1] == outputs[2]
    assert outputs[0][0] == {
        "node_id": "n1",
        "payload": {"id": "n1", "floatation": 0.7, "dims": {"project": "P", "tag": "x"}},
    }
    assert outputs[0][1] == [{"node_id": "x", "score": 0.3}]
    assert outputs[0][3] == (("n1", "x", "assoc"),)


# Behavior 5 ---------------------------------------------------------------


def test_error_normalization_preserves_message_and_cause():
    backend = FakeBackend()
    backend.add_error = RuntimeError("unreachable service")
    adapter = SubstrateAdapter(backend)

    with pytest.raises(SubstrateError) as exc_info:
        adapter.store_memory(make_node())
    assert str(exc_info.value) == "unreachable service"
    assert exc_info.value.__cause__ is backend.add_error

    backend2 = FakeBackend()
    backend2.link_error = KeyError("src")
    adapter2 = SubstrateAdapter(backend2)

    with pytest.raises(SubstrateError) as exc_info2:
        adapter2.link_nodes("src", "tgt")
    assert str(exc_info2.value) == "'src'"
    assert exc_info2.value.__cause__ is backend2.link_error


# Behavior 6 ---------------------------------------------------------------


def test_stable_interface_imports_and_signals_shape():
    signals = signals_out()

    assert set(signals) >= {"priorities", "views", "alerts"}
    assert signals["priorities"] == []
    assert signals["views"] == []
    assert signals["alerts"] == []
