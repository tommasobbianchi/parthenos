"""Agent runtime slice — persistence (snapshot save/load on McpServer) tests.

Covers the durability hooks: optional snapshot path wired into McpServer;
loading an existing snapshot at construction; saving after mutations; and the
round-trip guarantee (emit via MCP → snapshot → new server sees the memory).
"""

from __future__ import annotations

import json

from parthenos.graph import GraphStore
from parthenos.mcp_server import McpServer

EMIT = {
    "jsonrpc": "2.0",
    "id": 1,
    "method": "tools/call",
    "params": {
        "name": "emit_memory",
        "arguments": {"kind": "ingest", "payload": {"text": "durable memory"}},
    },
}


def test_emit_marks_dirty_and_save_writes_file(tmp_path):
    server = McpServer(GraphStore(), snapshot_path=str(tmp_path / "g.json"))
    assert server._dirty is False
    server.handle_request(EMIT)
    assert server._dirty is True
    server._save_snapshot()
    data = json.loads((tmp_path / "g.json").read_text())
    assert data["nodes"], "snapshot should contain the emitted node"


def test_construction_loads_existing_snapshot(tmp_path):
    snap = tmp_path / "g.json"
    first = McpServer(GraphStore(), snapshot_path=str(snap))
    first.handle_request(EMIT)
    first._save_snapshot()

    second = McpServer(GraphStore(), snapshot_path=str(snap))
    assert second._store.get_node  # store exists
    # the emitted node is present after reload
    nodes = second._store._nodes
    assert any("durable" in str(n.dims) for n in nodes.values())


def test_round_trip_emit_persist_reload(tmp_path):
    snap = tmp_path / "g.json"
    server = McpServer(GraphStore(), snapshot_path=str(snap))
    server.handle_request(EMIT)
    server._save_snapshot()

    fresh = McpServer(GraphStore(), snapshot_path=str(snap))
    hits = fresh.handle_request({
        "jsonrpc": "2.0",
        "id": 2,
        "method": "tools/call",
        "params": {"name": "recall", "arguments": {"query": "durable", "k": 10}},
    })
    text = hits["result"]["content"][0]["text"]
    assert "node-" in text
