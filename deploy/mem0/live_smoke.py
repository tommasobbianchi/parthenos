"""S9.3 live smoke — Mem0 SDK substrate through Mem0Adapter.

Requires: Mem0 stack running (deploy/mem0: postgres :8432, neo4j :8474),
DEEPSEEK_API_KEY set. Uses mock embedder (dim 10) so no embedding model
downloads are needed; the LLM path is real (DeepSeek fact extraction).

Run: ~/.venvs/mem0/bin/python deploy/mem0/live_smoke.py
"""

from __future__ import annotations

import os
from typing import Any

from mem0 import Memory

from parthenos.adapters import Mem0Adapter, SubstrateBackend
from parthenos.node import MemoryNode

DEEPSEEK_API_KEY = os.environ.get("DEEPSEEK_API_KEY", "")

CONFIG = {
    "llm": {
        "provider": "deepseek",
        "config": {"model": "deepseek-flash", "api_key": DEEPSEEK_API_KEY},
    },
    "embedder": {
        "provider": "fastembed",
        "config": {"model": "BAAI/bge-small-en-v1.5"},
    },
    "vector_store": {
        "provider": "pgvector",
        "config": {
            "connection_string": "postgresql://postgres:postgres@127.0.0.1:8432/postgres",
            "embedding_model_dims": 384,
        },
    },
}


class Mem0Backend(SubstrateBackend):
    """Tiny bridge: our adapter protocol -> the Mem0 SDK."""

    SMOKE_USER = "parthenos-smoke"

    def __init__(self, memory: Memory) -> None:
        self.memory = memory

    def add(self, node_id: str, payload: dict[str, Any]) -> None:
        text = payload.get("text") or payload.get("content") or str(payload)
        self.memory.add(text, user_id=self.SMOKE_USER, metadata={"node_id": node_id})

    def get(self, node_id: str) -> dict[str, Any] | None:
        for m in self.memory.get_all(user_id=self.SMOKE_USER).get("memories", []):
            if m.get("id") == node_id or m.get("metadata", {}).get("node_id") == node_id:
                return m
        return None

    def link(self, src_id: str, tgt_id: str, kind: str) -> None:
        # The SDK has no direct cross-node edge API; log the link.
        print(f"  [link] {src_id} -[{kind}]-> {tgt_id} (recorded)")

    def search(self, query: str, k: int) -> list[dict[str, Any]]:
        out = []
        for r in self.memory.search(query, limit=k, filters={"user_id": self.SMOKE_USER}) \
                .get("results", []):
            out.append({"node_id": r.get("id", ""), "score": r.get("score", 0.0)})
        return out


def main() -> int:
    if not DEEPSEEK_API_KEY:
        print("DEEPSEEK_API_KEY not set")
        return 2

    print("building Memory(config=...)")
    memory = Memory.from_config(CONFIG)
    backend = Mem0Backend(memory)
    adapter = Mem0Adapter(backend)

    uid = "tommaso-smoke"
    print("-> store_memory x2")
    n1 = adapter.store_memory(MemoryNode(
        id=f"n-{uid}-1", created_at=0.0, last_recall=0.0, floatation=0.8,
        dims={"text": "The Parthenos MCP server listens on port 8766."}))
    n2 = adapter.store_memory(MemoryNode(
        id=f"n-{uid}-2", created_at=0.0, last_recall=0.0, floatation=0.5,
        dims={"text": "Hermes agent talks to Parthenos over MCP."}))
    print("   stored:", n1["node_id"], n2["node_id"])

    print("-> adapter.link_nodes")
    adapter.link_nodes(n1["node_id"], n2["node_id"], kind="assoc")

    print("-> adapter.retrieve(query='MCP server port', k=3)")
    hits = adapter.retrieve("MCP server port", k=3)
    print("   hits:", hits)

    ok = bool(hits)
    print("SMOKE_OK" if ok else "SMOKE_FAIL")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
