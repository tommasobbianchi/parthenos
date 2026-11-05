"""Level 4: metacognitive supervision (S4b — reorganization proposals).

Supervision proposes, never imposes. This slice implements the reorganizing
proposals:
  - consolidation: merging semantically similar nodes born separately
  - active pruning: thresholds below which memories are archived or deleted
  - context-switch estimation: cost before jumping topics

All functions are read-only with respect to the graph; they return *proposals*
(dicts/lists of ids), never mutate. Deterministic by construction.
"""

from __future__ import annotations

import time
from collections.abc import Callable, Hashable

from parthenos.graph import GraphStore
from parthenos.node import MemoryNode


def _freeze(value: object) -> Hashable:
    """Return a hashable, equality-preserving stand-in for a dim value."""
    if isinstance(value, list):
        return tuple(value)
    if isinstance(value, (set, frozenset)):
        return frozenset(value)
    if isinstance(value, dict):
        return frozenset(value.items())
    return value  # type: ignore[return-value]


class Reorganizer:
    """Proposal generator. Never mutates the graph."""

    def __init__(self, store: GraphStore) -> None:
        self._store = store

    # -- helpers (no locks; read node fields directly) ----------------------

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
        return {str(value)}

    @staticmethod
    def _is_nonempty(value: object) -> bool:
        """True when a dim value is neither None nor an empty collection."""
        if value is None:
            return False
        if isinstance(value, str):
            return value != ""
        if isinstance(value, (list, tuple, set, frozenset, dict)):
            return len(value) > 0
        return True

    def _nonempty_items(self, node: MemoryNode) -> frozenset[tuple[str, Hashable]]:
        """Non-empty dims as (key, frozen_value) pairs, excluding the project dim."""
        return frozenset(
            (key, _freeze(value))
            for key, value in node.dims.items()
            if key != "project" and self._is_nonempty(value)
        )

    # -- proposal primitives -------------------------------------------------

    @staticmethod
    def _collect_project_groups(
        member_ids: list[str],
        items: dict[str, frozenset[tuple[str, Hashable]]],
        min_shared: int,
        groups: dict[frozenset[str], list[str]],
    ) -> None:
        """Record every itemset-defined node-set (size >= 2, shared dims >=
        min_shared) for one project into ``groups``, keyed by node-set."""
        universe = sorted(
            {item for it in items.values() for item in it},
            key=lambda kv: (kv[0], repr(kv[1])),
        )

        def dfs(prefix: frozenset[tuple[str, Hashable]], start: int) -> None:
            support = frozenset(nid for nid in member_ids if prefix <= items[nid])
            if len(support) < 2:
                return
            if len(prefix) >= min_shared:
                shared: set[tuple[str, Hashable]] | None = None
                for nid in support:
                    node_items = items[nid]
                    shared = set(node_items) if shared is None else shared & node_items
                assert shared is not None
                groups[frozenset(support)] = sorted(key for key, _ in shared)
            for i in range(start, len(universe)):
                item = universe[i]
                if item in prefix:
                    continue
                dfs(prefix | {item}, i + 1)

        dfs(frozenset(), 0)

    def propose_consolidation(self, min_shared: int = 2) -> list[dict]:
        """Return [{node_ids, reason}] proposals: groups of >=2 nodes born separately
        (distinct created_at) in the same project that share `min_shared` or more
        non-empty dim values. Sorted deterministically; empty when none."""
        groups: dict[frozenset[str], list[str]] = {}

        by_project: dict[str, list[str]] = {}
        for nid in sorted(self._store._nodes):
            for project in self._projects(self._store._nodes[nid]):
                by_project.setdefault(project, []).append(nid)

        for member_ids in by_project.values():
            member_ids.sort()
            items = {
                nid: self._nonempty_items(self._store._nodes[nid]) for nid in member_ids
            }
            self._collect_project_groups(member_ids, items, min_shared, groups)

        valid: list[tuple[frozenset[str], list[str]]] = []
        for node_set, keys in groups.items():
            if len(node_set) < 2:
                continue
            created_values = {self._store._nodes[nid].created_at for nid in node_set}
            if len(created_values) != len(node_set):
                continue  # not born separately
            valid.append((node_set, keys))

        maximal = [
            (ns, keys) for ns, keys in valid if not any(ns < other for other, _ in valid)
        ]
        maximal.sort(key=lambda pair: sorted(pair[0]))

        return [
            {"node_ids": sorted(node_set), "reason": "shared dims: " + ",".join(keys)}
            for node_set, keys in maximal
        ]

    def propose_pruning(
        self, floatation_floor: float, min_age: float, clock: Callable[[], float] | None = None
    ) -> dict[str, list[str]]:
        """Return {"archive": [ids], "delete": [ids]}:
          - archive: node.floatation < floatation_floor AND age > min_age
          - delete:   node.floatation < floatation_floor / 2 AND age > 2 * min_age
        Deterministic id ordering; a node appears in at most one bucket."""
        if clock is None:
            clock = time.time
        now = clock()

        archive: list[str] = []
        delete: list[str] = []
        for nid in sorted(self._store._nodes):
            node = self._store._nodes[nid]
            age = now - node.last_recall
            if node.floatation < floatation_floor / 2 and age > 2 * min_age:
                delete.append(nid)
            elif node.floatation < floatation_floor and age > min_age:
                archive.append(nid)
        return {"archive": archive, "delete": delete}

    def estimate_context_switch_cost(self, project_a: str, project_b: str) -> float:
        """Return a cost in [0, 1]: 0.0 when the projects share all members (cheap
        switch), 1.0 when they share none (expensive). Deterministic formula:
        cost = 1 - (shared_members / max(1, unique_members))."""
        members_a: set[str] = set()
        members_b: set[str] = set()
        for nid, node in self._store._nodes.items():
            projects = self._projects(node)
            if project_a in projects:
                members_a.add(nid)
            if project_b in projects:
                members_b.add(nid)

        shared = members_a & members_b
        unique = members_a | members_b
        return 1.0 - len(shared) / max(1, len(unique))
