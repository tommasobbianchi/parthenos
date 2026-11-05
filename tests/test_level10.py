"""Level 10 (A1) — MCP-over-HTTP backbone behavior tests.

Covers spec §1 behaviors 1-8:
  1. handle_request returns JSON-RPC 2.0 envelopes and echoes the request id
     (null, 0, int, string) on both success and error.
  2. initialize -> protocolVersion/capabilities/serverInfo.
  3. tools/list -> exactly the three TOOLS with their schemas.
  4. tools/call -> emit_memory ingests into the store; recall and plan_priority
     return sorted "<id>:<value>" text lines.
  5. Errors: unknown method / unknown tool -> -32601, missing params -> -32602,
     malformed JSON over HTTP -> 400.
  6. Non-JSON-RPC bodies (missing jsonrpc) -> -32600.
  7. Concurrency: parallel handle_request calls on disjoint nodes don't block.
  8. Regression: import + signals_out shape unchanged (full suite stays green).
"""

from __future__ import annotations

import http.client
import json
import threading
import time

import parthenos
from parthenos.graph import GraphStore
from parthenos.interfaces import signals_out
from parthenos.mcp_server import TOOLS, McpServer
from parthenos.node import MemoryNode


def make_node(
    node_id: str, *, dims: dict | None = None, floatation: float = 1.0
) -> MemoryNode:
    return MemoryNode(
        id=node_id,
        created_at=0.0,
        last_recall=0.0,
        floatation=floatation,
        dims=dict(dims) if dims else {},
    )


def _start_server(store: GraphStore) -> tuple[McpServer, threading.Thread, int]:
    server = McpServer(store, host="127.0.0.1", port=0)
    thread = threading.Thread(target=server.start, daemon=True)
    thread.start()
    deadline = time.time() + 5.0
    while server._httpd is None and time.time() < deadline:
        time.sleep(0.01)
    assert server._httpd is not None, "server did not start"
    port = server._httpd.server_address[1]
    return server, thread, port


def _post(port: int, path: str, body: bytes) -> tuple[int, bytes]:
    conn = http.client.HTTPConnection("127.0.0.1", port, timeout=5.0)
    conn.request("POST", path, body=body, headers={"Content-Type": "application/json"})
    resp = conn.getresponse()
    data = resp.read()
    status = resp.status
    conn.close()
    return status, data


# Behavior 1 ------------------------------------------------------------------


def test_success_envelope_echoes_id():
    server = McpServer(GraphStore())
    for req_id in (None, 0, 3, "req-9"):
        resp = server.handle_request(
            {"jsonrpc": "2.0", "id": req_id, "method": "tools/list"}
        )
        assert resp["jsonrpc"] == "2.0"
        assert resp["id"] == req_id
        assert "result" in resp and "error" not in resp
        assert resp["result"]["tools"] == TOOLS


def test_error_envelope_echoes_id_unknown_method():
    server = McpServer(GraphStore())
    resp = server.handle_request(
        {"jsonrpc": "2.0", "id": 42, "method": "no_such_method"}
    )
    assert resp["jsonrpc"] == "2.0"
    assert resp["id"] == 42
    assert "result" not in resp
    assert resp["error"]["code"] == -32601
    assert isinstance(resp["error"]["message"], str)


# Behavior 2 ------------------------------------------------------------------


def test_initialize_result_shape():
    server = McpServer(GraphStore())
    resp = server.handle_request(
        {"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {}}
    )
    result = resp["result"]
    assert result["protocolVersion"] == "2024-11-05"
    assert result["capabilities"] == {"tools": {}}
    assert result["serverInfo"] == {
        "name": "parthenos",
        "version": parthenos.__version__,
    }


# Behavior 3 ------------------------------------------------------------------


def test_tools_list_exactly_three_tools():
    server = McpServer(GraphStore())
    resp = server.handle_request({"jsonrpc": "2.0", "id": "t", "method": "tools/list"})
    tools = resp["result"]["tools"]
    assert len(tools) == 3
    assert [tool["name"] for tool in tools] == ["emit_memory", "recall", "plan_priority"]
    for tool in tools:
        assert tool["inputSchema"]["type"] == "object"


# Behavior 4 ------------------------------------------------------------------


def test_emit_memory_ingests_node_with_payload_dims():
    store = GraphStore()
    server = McpServer(store)
    resp = server.handle_request(
        {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "tools/call",
            "params": {
                "name": "emit_memory",
                "arguments": {
                    "kind": "ingest",
                    "payload": {"text": "hello", "valence": "positive"},
                },
            },
        }
    )
    content = resp["result"]["content"]
    assert len(content) == 1 and content[0]["type"] == "text"
    node_id = content[0]["text"]
    assert isinstance(node_id, str) and node_id
    node = store.get_node(node_id)
    assert node is not None
    assert node.dims == {"text": "hello", "valence": "positive"}


def test_recall_sorted_case_insensitive_top_k():
    store = GraphStore()
    for nid, fl, label in [
        ("n1", 0.2, "Apple"),
        ("n2", 0.8, "apricot"),
        ("n3", 0.8, "grape"),
        ("n4", 0.5, "pineapple"),
    ]:
        store.add_node(make_node(nid, dims={"label": label}, floatation=fl))
    server = McpServer(store)

    resp = server.handle_request(
        {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "tools/call",
            "params": {"name": "recall", "arguments": {"query": "AP", "k": 10}},
        }
    )
    text = resp["result"]["content"][0]["text"]
    assert text.splitlines() == ["n2:0.8", "n3:0.8", "n4:0.5", "n1:0.2"]

    resp = server.handle_request(
        {
            "jsonrpc": "2.0",
            "id": 2,
            "method": "tools/call",
            "params": {"name": "recall", "arguments": {"query": "ap", "k": 2}},
        }
    )
    text = resp["result"]["content"][0]["text"]
    assert text.splitlines() == ["n2:0.8", "n3:0.8"]


def test_plan_priority_sorted_by_weight_desc_then_id():
    store = GraphStore()
    store.add_node(
        make_node("p1", dims={"project": "proj", "project_weight": {"proj": 0.5}})
    )
    store.add_node(
        make_node("p2", dims={"project": "proj", "project_weight": {"proj": 2.0}})
    )
    store.add_node(make_node("p3", dims={"project": ["proj", "other"]}))
    store.add_node(make_node("p4", dims={"project": "other"}))
    server = McpServer(store)

    resp = server.handle_request(
        {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "tools/call",
            "params": {"name": "plan_priority", "arguments": {"project_id": "proj"}},
        }
    )
    text = resp["result"]["content"][0]["text"]
    assert text.splitlines() == ["p2:2.0", "p3:1.0", "p1:0.5"]


# Behavior 5 ------------------------------------------------------------------


def test_tools_call_unknown_tool_32601():
    server = McpServer(GraphStore())
    resp = server.handle_request(
        {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "tools/call",
            "params": {"name": "no_such_tool", "arguments": {}},
        }
    )
    assert resp["error"]["code"] == -32601


def test_missing_required_params_32602():
    server = McpServer(GraphStore())

    # tools/call without a tool name
    resp = server.handle_request(
        {"jsonrpc": "2.0", "id": 1, "method": "tools/call", "params": {}}
    )
    assert resp["error"]["code"] == -32602

    # recall without the required query
    resp = server.handle_request(
        {
            "jsonrpc": "2.0",
            "id": 2,
            "method": "tools/call",
            "params": {"name": "recall", "arguments": {}},
        }
    )
    assert resp["error"]["code"] == -32602

    # plan_priority without the required project_id
    resp = server.handle_request(
        {
            "jsonrpc": "2.0",
            "id": 3,
            "method": "tools/call",
            "params": {"name": "plan_priority", "arguments": {}},
        }
    )
    assert resp["error"]["code"] == -32602


def test_malformed_json_http_400():
    server, thread, port = _start_server(GraphStore())
    try:
        status, _ = _post(port, "/mcp", b"{this is not json")
        assert status == 400
    finally:
        server.stop()
        thread.join(timeout=5.0)


def test_http_initialize_round_trip():
    server, thread, port = _start_server(GraphStore())
    try:
        status, data = _post(
            port,
            "/mcp",
            b'{"jsonrpc":"2.0","id":1,"method":"initialize","params":{}}',
        )
        assert status == 200
        resp = json.loads(data)
        assert resp["jsonrpc"] == "2.0" and resp["id"] == 1
        assert resp["result"]["protocolVersion"] == "2024-11-05"
    finally:
        server.stop()
        thread.join(timeout=5.0)


# Behavior 6 ------------------------------------------------------------------


def test_missing_jsonrpc_field_32600():
    server = McpServer(GraphStore())
    resp = server.handle_request({"id": 1, "method": "tools/list"})
    assert resp["jsonrpc"] == "2.0"
    assert resp["id"] == 1
    assert resp["error"]["code"] == -32600
    assert isinstance(resp["error"]["message"], str)


# Behavior 7 ------------------------------------------------------------------


def test_concurrent_handle_request_disjoint_nodes():
    store = GraphStore()
    server = McpServer(store)
    results: dict[str, str] = {}
    barrier = threading.Barrier(2)

    def emit(key: str, text: str) -> None:
        barrier.wait()
        resp = server.handle_request(
            {
                "jsonrpc": "2.0",
                "id": key,
                "method": "tools/call",
                "params": {
                    "name": "emit_memory",
                    "arguments": {"kind": "ingest", "payload": {"text": text}},
                },
            }
        )
        results[key] = resp["result"]["content"][0]["text"]

    t1 = threading.Thread(target=emit, args=("req-1", "hello-one"))
    t2 = threading.Thread(target=emit, args=("req-2", "hello-two"))
    t1.start()
    t2.start()
    t1.join(timeout=5.0)
    t2.join(timeout=5.0)

    assert not t1.is_alive() and not t2.is_alive()
    assert set(results) == {"req-1", "req-2"}
    id1, id2 = results["req-1"], results["req-2"]
    assert id1 != id2
    assert store.get_node(id1) is not None
    assert store.get_node(id2) is not None


# Behavior 8 ------------------------------------------------------------------


def test_regression_import_and_signals_shape():
    assert parthenos.__version__ == "0.1.0"
    signals = signals_out()
    assert set(signals) >= {"priorities", "views", "alerts"}
