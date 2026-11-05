"""Level 7: lucid dreaming — nightly self-calibration.

A lightweight, incremental self-calibration process that runs while LLM weights
stay frozen. It reorganizes the layer's own parameters (sinking thresholds,
dimension weights, priority rules) based on observed behavior.

In the spirit of Level 4, this module *proposes* calibration deltas — it never
imposes them. Application happens at a quiet checkpoint by the caller.

All reads are lock-free and the module never mutates the graph or module
constants during proposal generation.
"""

from __future__ import annotations

from parthenos.fovea import DEFAULT_RIPPLE_BETA
from parthenos.graph import GraphStore, Missing
from parthenos.node import (
    DEFAULT_NEGLECT_RATE,
    DEFAULT_RECALL_STRENGTH,
    MemoryNode,
)


class Calibrator:
    """Proposes parameter calibration from observed behavior. Never mutates."""

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

    def collect_stats(self) -> dict:
        """Return deterministic aggregates over the store:
        {"total_nodes": int, "avg_floatation": float,
         "per_project_sink_ratio": {project_id: float},
         "hot_ratio": float, "recall_frequency": float}
        recall_frequency = fraction of nodes with last_recall strictly newer than
        created_at (i.e. recalled at least once). avg_floatation over all nodes
        (0.0 when none); hot_ratio = fraction with floatation >= 0.8.
        Deterministic key order."""
        nodes = list(self._store._nodes.values())
        total = len(nodes)

        floatation_sum = 0.0
        hot = 0
        recalled = 0
        for node in nodes:
            floatation_sum += node.floatation
            if node.floatation >= 0.8:
                hot += 1
            if node.last_recall > node.created_at:
                recalled += 1

        groups = self._members()
        sink_ratio: dict[str, float] = {}
        for project in sorted(groups):
            members = groups[project]
            sunk = sum(1 for _node_id, node in members if node.floatation < 1.0)
            sink_ratio[project] = round(sunk / max(1, len(members)), 6)

        return {
            "total_nodes": total,
            "avg_floatation": round(floatation_sum / total, 6) if total else 0.0,
            "per_project_sink_ratio": sink_ratio,
            "hot_ratio": round(hot / max(1, total), 6),
            "recall_frequency": round(recalled / max(1, total), 6),
        }

    def propose_calibration(self) -> list[dict]:
        """Return an ordered (deterministic) list of proposal dicts, each:
        {"parameter": str, "current": float, "proposed": float, "rationale": str}.
        Rules (deterministic from collect_stats):
          - if avg_floatation < 0.5: propose lowering DEFAULT_NEGLECT_RATE
            (current 0.05) by 20% (proposed = round(current * 0.8, 6))
          - if hot_ratio > 0.6: propose raising DEFAULT_RECALL_STRENGTH
            (current 0.5) by 10% (proposed = round(current * 1.1, 6))
          - if any per-project sink ratio > 0.7: propose lowering
            DEFAULT_RIPPLE_BETA (current 0.5) by 10%
            (proposed = round(current * 0.9, 6))
        Empty list when the store has no nodes."""
        stats = self.collect_stats()
        if stats["total_nodes"] == 0:
            return []

        proposals: list[dict] = []
        if stats["avg_floatation"] < 0.5:
            proposals.append(
                {
                    "parameter": "DEFAULT_NEGLECT_RATE",
                    "current": DEFAULT_NEGLECT_RATE,
                    "proposed": round(DEFAULT_NEGLECT_RATE * 0.8, 6),
                    "rationale": "avg_floatation < 0.5",
                }
            )
        if stats["hot_ratio"] > 0.6:
            proposals.append(
                {
                    "parameter": "DEFAULT_RECALL_STRENGTH",
                    "current": DEFAULT_RECALL_STRENGTH,
                    "proposed": round(DEFAULT_RECALL_STRENGTH * 1.1, 6),
                    "rationale": "hot_ratio > 0.6",
                }
            )
        if any(ratio > 0.7 for ratio in stats["per_project_sink_ratio"].values()):
            proposals.append(
                {
                    "parameter": "DEFAULT_RIPPLE_BETA",
                    "current": DEFAULT_RIPPLE_BETA,
                    "proposed": round(DEFAULT_RIPPLE_BETA * 0.9, 6),
                    "rationale": "sink ratio > 0.7",
                }
            )

        proposals.sort(key=lambda proposal: proposal["parameter"])
        return proposals
