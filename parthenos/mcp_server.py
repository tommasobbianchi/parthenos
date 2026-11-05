"""Actor wiring A1 — Parthenos exposed as an MCP server (loopback).

Implements a minimal, dependency-free MCP-over-HTTP subset (Streamable HTTP
shape, JSON-RPC 2.0): `initialize`, `tools/list`, `tools/call`. Backbone for
the actor pipeline (R4): actors (Hermes, LangGraph, …) reach Parthenos
uniformly through this endpoint.

Production default: http://127.0.0.1:8765/mcp (loopback only — no auth on
purpose this iteration; bind loopback, expose over Tailscale only).

Tools exposed:
  - emit_memory(kind, payload) -> ingest an Event; returns the promoted node id
  - recall(query, k)          -> nodes whose dim string values contain `query`
                                (case-insensitive), sorted by floatation desc
  - plan_priority(project_id) -> lens view weights for a project, sorted desc
"""

from __future__ import annotations

import json
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any

from parthenos import __version__
from parthenos.buffer import EphemeralBuffer
from parthenos.events import EVENT_KINDS, Event
from parthenos.graph import GraphStore
from parthenos.lens import Lens
from parthenos.serialize import Snapshotter

SERVER_NAME = "parthenos"
PROTOCOL_VERSION = "2024-11-05"

TOOLS: list[dict[str, Any]] = [
    {
        "name": "emit_memory",
        "description": "Ingest a memory event; returns the promoted node id.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "kind": {"type": "string", "enum": ["ingest", "recall"]},
                "payload": {"type": "object"},
            },
            "required": ["kind"],
        },
    },
    {
        "name": "recall",
        "description": "Search nodes by substring over dim values; sorted by floatation desc.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "query": {"type": "string"},
                "k": {"type": "integer", "minimum": 1, "maximum": 100},
            },
            "required": ["query"],
        },
    },
    {
        "name": "plan_priority",
        "description": "Return a project lens view sorted by weight desc.",
        "inputSchema": {
            "type": "object",
            "properties": {"project_id": {"type": "string"}},
            "required": ["project_id"],
        },
    },
]


class _JsonRpcError(Exception):
    """JSON-RPC error raised by handlers and normalized by the dispatcher."""

    def __init__(self, code: int, message: str) -> None:
        super().__init__(message)
        self.code = code
        self.message = message


class McpServer:
    """Minimal MCP-over-HTTP server (JSON-RPC 2.0 subset)."""

    def __init__(
        self,
        store: GraphStore,
        host: str = "127.0.0.1",
        port: int = 8765,
        snapshot_path: str | None = None,
        snapshot_interval: float = 60.0,
    ) -> None:
        self._store = store
        self._host = host
        self._port = port
        self._httpd: ThreadingHTTPServer | None = None
        self._buffer = EphemeralBuffer()
        self._id_lock = threading.Lock()
        self._id_counter = 0
        self._snapshot_path = snapshot_path
        self._snapshot_interval = snapshot_interval
        self._dirty = False
        self._saver_stop = threading.Event()
        self._saver: threading.Thread | None = None
        self._load_snapshot_if_any()

    # -- persistence ---------------------------------------------------------

    def _load_snapshot_if_any(self) -> None:
        """Restore the store contents from the snapshot file when it exists."""
        if not self._snapshot_path:
            return
        from pathlib import Path

        path = Path(self._snapshot_path)
        if not path.is_file():
            return
        snapshot = json.loads(path.read_text(encoding="utf-8"))
        Snapshotter(self._store).restore(snapshot)

    def _save_snapshot(self) -> None:
        """Write the current graph state to the snapshot path (no-op if none)."""
        if not self._snapshot_path:
            return
        from pathlib import Path

        path = Path(self._snapshot_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        Snapshotter(self._store).save_snapshot(path)
        self._dirty = False

    def _mark_dirty(self) -> None:
        self._dirty = True

    def _run_saver(self) -> None:
        while not self._saver_stop.wait(self._snapshot_interval):
            if self._dirty:
                self._save_snapshot()

    def _start_saver(self) -> None:
        if self._snapshot_path and self._snapshot_interval > 0:
            self._saver = threading.Thread(target=self._run_saver, daemon=True)
            self._saver.start()

    # -- JSON-RPC dispatch --------------------------------------------------

    def handle_request(self, body: dict[str, Any]) -> dict[str, Any]:
        """Dispatch one JSON-RPC request; returns the response dict."""
        if not isinstance(body, dict):
            return self._error(None, -32600, "Invalid Request")
        if body.get("jsonrpc") != "2.0":
            return self._error(body.get("id"), -32600, "Invalid Request")
        req_id = body.get("id")
        method = body.get("method")
        if not isinstance(method, str) or not method:
            return self._error(req_id, -32600, "Invalid Request")
        params = body.get("params", {})
        if not isinstance(params, dict):
            params = {}
        try:
            if method == "initialize":
                result = self._handle_initialize(params)
            elif method == "tools/list":
                result = self._handle_tools_list()
            elif method == "tools/call":
                result = self._handle_tools_call(params)
            else:
                return self._error(req_id, -32601, "Method not found")
        except _JsonRpcError as exc:
            return self._error(req_id, exc.code, exc.message)
        return {"jsonrpc": "2.0", "id": req_id, "result": result}

    def _error(self, req_id: Any, code: int, message: str) -> dict[str, Any]:
        return {
            "jsonrpc": "2.0",
            "id": req_id,
            "error": {"code": code, "message": message},
        }

    def _handle_initialize(self, params: dict[str, Any]) -> dict[str, Any]:
        return {
            "protocolVersion": PROTOCOL_VERSION,
            "capabilities": {"tools": {}},
            "serverInfo": {"name": SERVER_NAME, "version": __version__},
        }

    def _handle_tools_list(self) -> dict[str, Any]:
        return {"tools": TOOLS}

    def _handle_tools_call(self, params: dict[str, Any]) -> dict[str, Any]:
        if not isinstance(params, dict):
            raise _JsonRpcError(-32602, "Invalid params")
        name = params.get("name")
        if not isinstance(name, str) or not name:
            raise _JsonRpcError(-32602, "Invalid params: missing tool name")
        arguments = params.get("arguments")
        if arguments is None:
            arguments = {}
        if not isinstance(arguments, dict):
            raise _JsonRpcError(-32602, "Invalid params: arguments must be an object")
        if name == "emit_memory":
            return self._tool_emit_memory(arguments)
        if name == "recall":
            return self._tool_recall(arguments)
        if name == "plan_priority":
            return self._tool_plan_priority(arguments)
        raise _JsonRpcError(-32601, f"Unknown tool: {name}")

    def _tool_emit_memory(self, args: dict[str, Any]) -> dict[str, Any]:
        kind = args.get("kind")
        if not isinstance(kind, str) or not kind:
            raise _JsonRpcError(-32602, "Missing required parameter: kind")
        if kind not in EVENT_KINDS:
            raise _JsonRpcError(-32602, f"Invalid event kind: {kind}")
        payload = args.get("payload")
        if payload is None:
            payload = {}
        if not isinstance(payload, dict):
            raise _JsonRpcError(-32602, "Invalid params: payload must be an object")
        payload = dict(payload)
        node_id = payload.pop("node_id", None)
        if not node_id:
            node_id = self._generate_node_id()
        event = Event(kind=kind, payload=dict(payload, node_id=node_id))
        node = self._buffer.ingest(event)
        node.dims.update(payload)
        self._store.add_node(node)
        self._mark_dirty()
        return {"content": [{"type": "text", "text": node.id}]}

    def _tool_recall(self, args: dict[str, Any]) -> dict[str, Any]:
        query = args.get("query")
        if not isinstance(query, str) or not query:
            raise _JsonRpcError(-32602, "Missing required parameter: query")
        k = args.get("k")
        k = 10 if k is None else int(k)
        needle = query.lower()
        matches: list[tuple[str, float]] = []
        for node_id, node in self._store._nodes.items():
            if any(needle in value.lower() for value in self._dim_strings(node)):
                matches.append((node_id, node.floatation))
        matches.sort(key=lambda pair: (-pair[1], pair[0]))
        text = "\n".join(f"{nid}:{fl}" for nid, fl in matches[:k])
        return {"content": [{"type": "text", "text": text}]}

    def _tool_plan_priority(self, args: dict[str, Any]) -> dict[str, Any]:
        project_id = args.get("project_id")
        if not isinstance(project_id, str) or not project_id:
            raise _JsonRpcError(-32602, "Missing required parameter: project_id")
        lens = Lens(self._store, project_id)
        for node_id, node in self._store._nodes.items():
            if project_id in self._projects(node):
                weight = self._project_weight(node, project_id)
                lens.set_project_membership(node_id, weight)
        view = lens.view()
        items = sorted(view.items(), key=lambda pair: (-pair[1], pair[0]))
        text = "\n".join(f"{nid}:{weight}" for nid, weight in items)
        return {"content": [{"type": "text", "text": text}]}

    # -- helpers ------------------------------------------------------------

    def _generate_node_id(self) -> str:
        with self._id_lock:
            node_id = f"node-{self._id_counter}"
            self._id_counter += 1
            return node_id

    @staticmethod
    def _dim_strings(node: Any) -> list[str]:
        strings: list[str] = []
        for value in node.dims.values():
            if isinstance(value, str):
                strings.append(value)
            elif isinstance(value, (list, tuple, set, frozenset)):
                strings.extend(str(item) for item in value)
            else:
                strings.append(str(value))
        return strings

    @staticmethod
    def _projects(node: Any) -> set[str]:
        value = node.dims.get("project")
        if value is None:
            return set()
        if isinstance(value, str):
            return {value}
        if isinstance(value, (list, tuple, set, frozenset)):
            return {str(item) for item in value}
        return {str(value)}

    @staticmethod
    def _project_weight(node: Any, project: str) -> float:
        registry = node.dims.get("project_weight")
        if isinstance(registry, dict):
            return registry.get(project, 1.0)
        return 1.0

    # -- HTTP lifecycle -----------------------------------------------------

    def start(self) -> None:
        """Start the HTTP server in the calling thread (blocks)."""
        handler = self._make_handler()
        self._httpd = ThreadingHTTPServer((self._host, self._port), handler)
        self._start_saver()
        self._httpd.serve_forever()

    def stop(self) -> None:
        self._saver_stop.set()
        if self._dirty:
            self._save_snapshot()
        if self._httpd is not None:
            self._httpd.shutdown()
            self._httpd.server_close()
            self._httpd = None

    def _make_handler(self) -> type[BaseHTTPRequestHandler]:
        server = self

        class Handler(BaseHTTPRequestHandler):
            def do_POST(self) -> None:
                if self.path != "/mcp":
                    self.send_error(404)
                    return
                length = int(self.headers.get("Content-Length", 0))
                raw = self.rfile.read(length)
                try:
                    body = json.loads(raw)
                except (json.JSONDecodeError, UnicodeDecodeError):
                    self.send_response(400)
                    self.end_headers()
                    return
                response = server.handle_request(body)
                payload = json.dumps(response).encode("utf-8")
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(payload)))
                self.end_headers()
                self.wfile.write(payload)

            def log_message(self, *args: Any) -> None:  # quiet
                pass

        return Handler
