"""Level 6: aggregated telemetry + predictive pre-fetch.

Telemetry aggregates the graph into health indicators, heat maps, and sinking
trends per project; predictive pre-fetching surfaces hot-cache candidates above a
confidence threshold. All read-only snapshots: no locks, deterministic ordering.
"""

from __future__ import annotations

from parthenos.graph import GraphStore, Missing
from parthenos.node import MemoryNode


class Telemetry:
    """Read-only observer producing aggregates. Never mutates."""

    def __init__(self, store: GraphStore) -> None:
        self._store = store

    @staticmethod
    def _projects(node: MemoryNode) -> list[str]:
        """Return the project ids a node belongs to (string or list in dims)."""
        value = node.dims.get("project", Missing)
        if value is Missing:
            return []
        if isinstance(value, str):
            return [value]
        return list(value)

    def _members(self) -> dict[str, list[tuple[str, MemoryNode]]]:
        """Group project-member nodes by project id, lock-free."""
        groups: dict[str, list[tuple[str, MemoryNode]]] = {}
        for node_id, node in self._store._nodes.items():
            for project in self._projects(node):
                groups.setdefault(project, []).append((node_id, node))
        return groups

    def heat_map(self, top_k: int = 10) -> dict[str, list[dict]]:
        """Return {project_id: [{node_id, floatation} ...]} sorted by floatation
        descending then node id ascending, truncated to `top_k` per project.
        Only project members appear. Empty dict when no members."""
        result: dict[str, list[dict]] = {}
        groups = self._members()
        for project in sorted(groups):
            members = groups[project]
            ordered = sorted(members, key=lambda item: (-item[1].floatation, item[0]))
            entries = [] if top_k <= 0 else ordered[:top_k]
            result[project] = [
                {"node_id": node_id, "floatation": node.floatation}
                for node_id, node in entries
            ]
        return result

    def sinking_trends(self, project_id: str, limit: int = 10) -> list[dict]:
        """Return [{node_id, floatation, last_recall}] for project members with
        floatation < 1.0, sorted by floatation ascending (most sunk first), then
        node id ascending, truncated to `limit`."""
        members = self._members().get(project_id, [])
        sunk = [(node_id, node) for node_id, node in members if node.floatation < 1.0]
        ordered = sorted(sunk, key=lambda item: (item[1].floatation, item[0]))
        entries = [] if limit <= 0 else ordered[:limit]
        return [
            {
                "node_id": node_id,
                "floatation": node.floatation,
                "last_recall": node.last_recall,
            }
            for node_id, node in entries
        ]

    def health(self) -> dict:
        """Return overall indicators:
        {"total_nodes": int, "projects": int, "avg_floatation": float,
         "conflicting_nodes": int, "hot_nodes": int}
        avg_floatation over all nodes (0.0 when no nodes); conflicting_nodes =
        count of nodes belonging to 2+ projects; hot_nodes = count with
        floatation >= 0.8. Deterministic."""
        nodes = list(self._store._nodes.values())
        total = len(nodes)
        floatation_sum = 0.0
        hot = 0
        projects: set[str] = set()
        conflicting = 0
        for node in nodes:
            floatation_sum += node.floatation
            if node.floatation >= 0.8:
                hot += 1
            project_set = set(self._projects(node))
            projects.update(project_set)
            if len(project_set) >= 2:
                conflicting += 1
        avg = round(floatation_sum / total, 6) if total else 0.0
        return {
            "total_nodes": total,
            "projects": len(projects),
            "avg_floatation": avg,
            "conflicting_nodes": conflicting,
            "hot_nodes": hot,
        }

    def prefetch_candidates(self, threshold: float = 0.8) -> list[str]:
        """Return node ids with floatation >= threshold, sorted by floatation
        descending then id ascending. Predictive hot-cache candidates."""
        hot = [
            (node_id, node)
            for node_id, node in self._store._nodes.items()
            if node.floatation >= threshold
        ]
        ordered = sorted(hot, key=lambda item: (-item[1].floatation, item[0]))
        return [node_id for node_id, _node in ordered]
