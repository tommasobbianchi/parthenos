"""Level 5: versioned serialization + timeline snapshots.

Append-only timeline of versioned graph snapshots for restore and comparison.
Snapshots are immutable deep copies of graph state (nodes, dims, edges,
floatation). Per-node concurrency already exists in the model; snapshots are
read-only with respect to the live graph (no locks, benign race).

Serialization format: JSON, deterministic key ordering, sets as sorted lists.
"""

from __future__ import annotations

import copy
import json
import time
from pathlib import Path
from typing import Any

from parthenos.graph import GraphStore
from parthenos.node import Clock, MemoryNode, TypedEdge


def _canonicalize(value: Any) -> Any:
    """Return a deterministic, JSON-safe form of a dim value.

    Sets and frozensets become sorted lists; dicts are sorted by key and their
    values canonicalized recursively; lists and tuples keep their order (elements
    canonicalized). Scalars pass through unchanged.
    """
    if isinstance(value, (set, frozenset)):
        return sorted(value)
    if isinstance(value, dict):
        return {key: _canonicalize(value[key]) for key in sorted(value)}
    if isinstance(value, (list, tuple)):
        return [_canonicalize(item) for item in value]
    return value


class Snapshotter:
    """Builds serializable snapshots of a GraphStore."""

    def __init__(self, store: GraphStore, clock: Clock | None = None) -> None:
        self._store = store
        self._version = 0
        self._clock = clock if clock is not None else time.time

    def snapshot(self) -> dict:
        """Return a deterministic, JSON-serializable deep copy of the graph state."""
        version = self._version
        self._version += 1
        return self._build(version)

    def _build(self, version: int) -> dict:
        nodes = [
            {
                "id": node.id,
                "created_at": node.created_at,
                "last_recall": node.last_recall,
                "floatation": node.floatation,
                "dims": _canonicalize(node.dims),
            }
            for _, node in sorted(self._store._nodes.items(), key=lambda item: item[0])
        ]
        edges = [
            {
                "src": src,
                "tgt": tgt,
                "kind": edge.kind,
                "weight": edge.weight,
                "valid_at": edge.valid_at,
                "invalid_at": edge.invalid_at,
            }
            for (src, tgt), edge in sorted(
                self._store._edges.items(), key=lambda item: item[0]
            )
        ]
        return {
            "version": version,
            "taken_at": self._clock(),
            "nodes": nodes,
            "edges": edges,
        }

    def save_snapshot(self, path: str | Path) -> None:
        """Write the current snapshot state to `path` as sorted-key JSON."""
        snapshot = self._build(self._version)
        with open(path, "w", encoding="utf-8") as file:
            json.dump(snapshot, file, sort_keys=True)

    def load_snapshot(self, path: str | Path) -> dict:
        """Read a snapshot dict previously written by save_snapshot."""
        with open(path, encoding="utf-8") as file:
            return json.load(file)

    def restore(self, snapshot: dict) -> None:
        """Replace the store's contents with `snapshot` (nodes + edges)."""
        store = self._store
        store._nodes.clear()
        store._edges.clear()
        for node_data in snapshot["nodes"]:
            node = MemoryNode(
                id=node_data["id"],
                created_at=node_data["created_at"],
                last_recall=node_data["last_recall"],
                floatation=node_data["floatation"],
                dims=copy.deepcopy(node_data["dims"]),
            )
            store._nodes[node.id] = node
        for edge_data in snapshot["edges"]:
            edge = TypedEdge(
                target_id=edge_data["tgt"],
                kind=edge_data["kind"],
                weight=edge_data["weight"],
                valid_at=edge_data.get("valid_at"),
                invalid_at=edge_data.get("invalid_at"),
            )
            store._edges[(edge_data["src"], edge_data["tgt"])] = edge


def _node_modified(older: dict, newer: dict) -> bool:
    """True when an id-preserving field (floatation/dims/last_recall) changed."""
    return (
        older["floatation"] != newer["floatation"]
        or older["dims"] != newer["dims"]
        or older["last_recall"] != newer["last_recall"]
    )


class Timeline:
    """Append-only versioned snapshot log."""

    def __init__(self) -> None:
        self._entries: list[dict] = []

    def push(self, snapshot: dict) -> None:
        """Append `snapshot` (must contain "version" and "taken_at")."""
        self._entries.append(
            {
                "version": snapshot["version"],
                "taken_at": snapshot["taken_at"],
                "snapshot": copy.deepcopy(snapshot),
            }
        )

    def restore(self, version: int) -> dict:
        """Return the snapshot with the given version; raise KeyError if absent."""
        for entry in self._entries:
            if entry["version"] == version:
                return copy.deepcopy(entry["snapshot"])
        raise KeyError(version)

    def diff(self, older_version: int, newer_version: int) -> dict:
        """Compare two stored snapshots, returning added/removed/modified sets.

        Nodes are keyed by id (modified when floatation/dims/last_recall differ);
        edges are keyed by (src, tgt) (a changed weight/kind shows up as the old
        edge removed and the new edge added). Deterministic ordering throughout.
        """
        older = self.restore(older_version)
        newer = self.restore(newer_version)

        older_nodes = {n["id"]: n for n in older["nodes"]}
        newer_nodes = {n["id"]: n for n in newer["nodes"]}

        common_ids = older_nodes.keys() & newer_nodes.keys()

        added_nodes = [newer_nodes[nid] for nid in newer_nodes if nid not in older_nodes]
        removed_nodes = [older_nodes[nid] for nid in older_nodes if nid not in newer_nodes]
        modified_nodes = [
            newer_nodes[nid]
            for nid in common_ids
            if _node_modified(older_nodes[nid], newer_nodes[nid])
        ]

        older_edges = {(e["src"], e["tgt"]): e for e in older["edges"]}
        newer_edges = {(e["src"], e["tgt"]): e for e in newer["edges"]}

        added_edges = [
            newer_edges[key]
            for key in newer_edges
            if key not in older_edges or older_edges[key] != newer_edges[key]
        ]
        removed_edges = [
            older_edges[key]
            for key in older_edges
            if key not in newer_edges or older_edges[key] != newer_edges[key]
        ]

        def by_id(node: dict) -> str:
            return node["id"]

        def by_endpoints(edge: dict) -> tuple[str, str]:
            return (edge["src"], edge["tgt"])

        return {
            "added_nodes": sorted(added_nodes, key=by_id),
            "removed_nodes": sorted(removed_nodes, key=by_id),
            "modified_nodes": sorted(modified_nodes, key=by_id),
            "added_edges": sorted(added_edges, key=by_endpoints),
            "removed_edges": sorted(removed_edges, key=by_endpoints),
        }
