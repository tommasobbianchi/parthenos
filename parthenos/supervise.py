"""Level 4: metacognitive supervision (S4a — observation primitives).

Supervision does not touch data: it observes movement and proposes, never
imposes. This slice implements the observation primitives:
  - explainability: why was a node raised (decision trace)
  - conflict detection: two projects claiming the same node with different weights
  - behavioral anomaly detection: user terms from one project used in another
  - unexpected bridge discovery: cross-project links surfaced by the layer

All functions are read-only with respect to the graph (no locks, snapshots only).
"""

from __future__ import annotations

from parthenos.graph import GraphStore
from parthenos.node import MemoryNode


class Supervision:
    """Read-only observer over a GraphStore. Holds no mutable graph state."""

    def __init__(self, store: GraphStore) -> None:
        self._store = store

    # -- snapshot helpers (no locks; read node.dims directly) --------------

    @staticmethod
    def _projects(node: MemoryNode) -> set[str]:
        """Return the set of project ids a node belongs to (from dims["project"])."""
        value = node.dims.get("project")
        if value is None:
            return set()
        if isinstance(value, str):
            return {value}
        if isinstance(value, (list, tuple, set, frozenset)):
            return {str(item) for item in value}
        return {value}

    @staticmethod
    def _project_weight(node: MemoryNode, project: str) -> float:
        """Read the per-project weight registry (dims["project_weight"]), else 1.0."""
        registry = node.dims.get("project_weight")
        if isinstance(registry, dict):
            return registry.get(project, 1.0)
        return 1.0

    @staticmethod
    def _dim_strings(node: MemoryNode) -> list[str]:
        """Flatten every dim value on a node to a list of string tokens."""
        strings: list[str] = []
        for value in node.dims.values():
            if isinstance(value, str):
                strings.append(value)
            elif isinstance(value, (list, tuple, set, frozenset)):
                strings.extend(str(item) for item in value)
            else:
                strings.append(str(value))
        return strings

    # -- observation primitives -------------------------------------------

    def explain(self, node_id: str) -> list[dict]:
        """Return the decision trace for a node's current weight: a chronologically
        ordered list of {event, ts, delta} contributions. Empty if node unknown."""
        node = self._store.get_node(node_id)
        if node is None:
            return []
        return [dict(entry) for entry in node._trace]

    def detect_conflicts(self, project_a: str, project_b: str) -> list[dict]:
        """Return [{node_id, weight_a, weight_b}] for nodes claimed by both projects at
        different strengths. Empty when weights are equal or there is no overlap."""
        conflicts: list[dict] = []
        for node_id, node in self._store._nodes.items():
            projects = self._projects(node)
            if project_a in projects and project_b in projects:
                weight_a = self._project_weight(node, project_a)
                weight_b = self._project_weight(node, project_b)
                if weight_a != weight_b:
                    conflicts.append(
                        {"node_id": node_id, "weight_a": weight_a, "weight_b": weight_b}
                    )
        conflicts.sort(key=lambda item: item["node_id"])
        return conflicts

    def detect_anomalies(self, terms: list[str], active_project: str) -> list[dict]:
        """Return [{term, node_ids}] where a term (case-insensitive substring over any
        string dim value) matches nodes whose project dim does not include
        `active_project` — i.e. vocabulary from another project leaking in."""
        anomalies: list[dict] = []
        for term in terms:
            needle = term.lower()
            node_ids: list[str] = []
            for node_id, node in self._store._nodes.items():
                if active_project in self._projects(node):
                    continue
                if any(needle in token.lower() for token in self._dim_strings(node)):
                    node_ids.append(node_id)
            if node_ids:
                node_ids.sort()
                anomalies.append({"term": term, "node_ids": node_ids})
        return anomalies

    def discover_bridges(self) -> list[tuple[str, str, str]]:
        """Return [(src_id, tgt_id, kind)] for edges whose endpoints belong to different
        projects (per their project dim). Cross-project links surfaced by the layer."""
        nodes = self._store._nodes
        bridges: list[tuple[str, str, str]] = []
        for (src_id, tgt_id), edge in self._store._edges.items():
            src = nodes.get(src_id)
            tgt = nodes.get(tgt_id)
            if src is None or tgt is None:
                continue
            src_projects = self._projects(src)
            tgt_projects = self._projects(tgt)
            if src_projects and tgt_projects and src_projects != tgt_projects:
                bridges.append((src_id, tgt_id, edge.kind))
        bridges.sort(key=lambda item: (item[0], item[1]))
        return bridges
