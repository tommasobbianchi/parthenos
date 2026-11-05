"""Level 3: contextual partitioning — project lenses.

A lens does not move memories; it builds an overlapping view over the graph,
highlighting nodes relevant to an active project and attenuating the rest.
Cross-project links stay visible at reduced weight. Priority management lives
here: a strong emotional stimulus raises a node's weight regardless of project.

Views are read-only snapshots; recomputation across projects is embarrassingly
parallel (the GPU parallelization hook in the design doc applies to this).
"""

from __future__ import annotations

from parthenos.graph import GraphStore

DEFAULT_ATTENUATION = 0.1
DEFAULT_EMOTIONAL_POWER = 2.0


class Lens:
    """Per-project view builder over a GraphStore."""

    def __init__(self, store: GraphStore, project_id: str) -> None:
        self._store = store
        self.project_id = project_id
        self._membership: dict[str, float] = {}  # node_id -> membership strength
        self._emotional: dict[str, float] = {}  # node_id -> override power
        self._attenuation = DEFAULT_ATTENUATION

    def set_project_membership(self, node_id: str, strength: float = 1.0) -> None:
        """Mark `node_id` as belonging to this project with `strength`."""
        self._membership[node_id] = strength

    def set_emotional_override(self, node_id: str, power: float = DEFAULT_EMOTIONAL_POWER) -> None:
        """Raise a node's weight regardless of project (fear/anger stimulus)."""
        self._emotional[node_id] = power

    def set_cross_project_attenuation(self, factor: float) -> None:
        """Attenuation applied to links that cross project boundaries."""
        self._attenuation = factor

    def view(self) -> dict[str, float]:
        """Return {node_id: effective_weight} for the current graph state.

        Read-only snapshot: members carry their membership strength, non-members
        linked to a member stay visible at ``edge.weight * attenuation``, and any
        emotional override wins outright. No locks are acquired; every node with a
        nonzero weight is included.
        """
        members = self._membership
        attenuation = self._attenuation
        result: dict[str, float] = {}

        # 1. Members: weight is the membership strength (1.0 by default).
        for node_id, strength in members.items():
            result[node_id] = strength

        # 2. Cross-project visibility: a non-member linked (either direction) to a
        #    member stays visible at the linking edge's weight times attenuation.
        edges = self._store._edges
        for node_id in self._store._nodes:
            if node_id in members:
                continue
            best = 0.0
            for edge in self._store.neighbors(node_id):
                if edge.target_id in members and edge.weight > best:
                    best = edge.weight
            for (src_id, tgt_id), edge in edges.items():
                if tgt_id == node_id and src_id in members and edge.weight > best:
                    best = edge.weight
            if best > 0.0:
                result[node_id] = best * attenuation

        # 3. Emotional override: lifts a node regardless of membership or edges.
        for node_id, power in self._emotional.items():
            result[node_id] = power

        return result
