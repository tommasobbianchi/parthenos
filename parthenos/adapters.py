"""Level 8: substrate integration behind the stable interface.

The metacognitive layer orchestrates substrate libraries (Zep, Cognee, Mem0)
via their public APIs without rewriting them. Adapters normalize those APIs to a
single internal protocol, so swapping a substrate never touches L3/L4 or the LLM
interface.

Real substrates are external services; this module defines the protocol and
adapters over duck-typed backends (tests use a fake backend). Wiring real
services is a deployment concern, not a code concern of the layer.
"""

from __future__ import annotations

from typing import Any, Protocol


class SubstrateBackend(Protocol):
    """The minimal surface an external memory substrate must expose."""

    def add(self, node_id: str, payload: dict[str, Any]) -> None: ...
    def get(self, node_id: str) -> dict[str, Any] | None: ...
    def link(self, src_id: str, tgt_id: str, kind: str) -> None: ...
    def search(self, query: str, k: int) -> list[dict[str, Any]]: ...


class SubstrateError(RuntimeError):
    """Raised when a substrate backend is unreachable or rejects an operation."""


class SubstrateAdapter:
    """Base adapter: normalizes a backend to the internal protocol."""

    backend: SubstrateBackend

    def __init__(self, backend: SubstrateBackend) -> None:
        self.backend = backend

    def store_memory(self, node) -> dict[str, Any]:
        """Normalize a MemoryNode into backend-addable payload; call backend.add."""
        node_id = node.id
        payload: dict[str, Any] = {
            "id": node.id,
            "floatation": node.floatation,
            "dims": node.dims,
        }
        try:
            self.backend.add(node_id, payload)
        except Exception as exc:
            raise SubstrateError(str(exc)) from exc
        return {"node_id": node_id, "payload": payload}

    def retrieve(self, query: str, k: int = 5) -> list[dict[str, Any]]:
        """Search the backend; return normalized [{node_id, score}] sorted desc."""
        records = [
            {"node_id": rec["node_id"], "score": rec.get("score", 0.0)}
            for rec in self.backend.search(query, k)
        ]
        records.sort(key=lambda rec: (-rec["score"], rec["node_id"]))
        return records

    def link_nodes(self, src_id: str, tgt_id: str, kind: str = "assoc") -> None:
        """Create a typed link in the backend."""
        try:
            self.backend.link(src_id, tgt_id, kind)
        except Exception as exc:
            raise SubstrateError(str(exc)) from exc


class Mem0Adapter(SubstrateAdapter):
    """Adapter for Mem0-style fact stores."""


class ZepAdapter(SubstrateAdapter):
    """Adapter for Zep/Graphiti-style temporal graph services."""


class CogneeAdapter(SubstrateAdapter):
    """Adapter for Cognee-style graph-vector memory engines."""
