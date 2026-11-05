"""Foveal update engine: local updates, ripples fade with distance.

When a node is stimulated, only it and its direct neighbors get full updates;
impact at hop h decays by ripple_beta**h. This keeps per-event cost at tens of
light operations even at ~400k nodes (avg degree 10–20).
"""

from __future__ import annotations

from collections import deque

from parthenos.node import Clock, MemoryNode

DEFAULT_RIPPLE_BETA = 0.5
DEFAULT_RADIUS = 3


class FoveaEngine:
    """Stimulates a node and returns the floatation deltas it caused.

    Synchronization is per-node: each ``MemoryNode`` carries its own lock and
    ``stimulate`` acquires only the locks of the nodes it touches, in sorted id
    order to avoid lock-order deadlocks. Two calls on disjoint neighborhoods
    therefore proceed concurrently; there is never a whole-graph lock.
    """

    def __init__(
        self,
        beta: float = DEFAULT_RIPPLE_BETA,
        radius: int = DEFAULT_RADIUS,
        clock: Clock | None = None,
    ) -> None:
        self.beta = beta
        self.radius = radius
        self._clock = clock if clock is not None else __import__("time").time

    def stimulate(
        self,
        node: MemoryNode,
        intensity: float = 1.0,
        *,
        graph: dict[str, MemoryNode] | None = None,
    ) -> dict[str, float]:
        """Raises `node` (and neighbors, decaying) and returns {node_id: delta_floatation}."""
        if graph is None:
            graph = {}

        # BFS from the stimulated node following node.edges into the graph.
        visited: set[str] = set()
        frontier: deque[tuple[MemoryNode, int]] = deque([(node, 0)])
        touched: list[tuple[MemoryNode, int]] = []
        while frontier:
            current, hop = frontier.popleft()
            if current.id in visited:
                continue
            visited.add(current.id)
            touched.append((current, hop))
            if hop >= self.radius:
                continue
            for edge in current.edges:
                neighbor = graph.get(edge.target_id)
                if neighbor is not None and neighbor.id not in visited:
                    frontier.append((neighbor, hop + 1))

        deltas: dict[str, float] = {}
        now = self._clock()
        # Apply in deterministic id order to avoid lock-order deadlocks.
        for current, hop in sorted(touched, key=lambda item: item[0].id):
            impact = intensity * (self.beta ** hop)
            with current.lock:
                new_floatation = min(1.0, max(0.0, current.floatation + impact))
                delta = new_floatation - current.floatation
                current.floatation = new_floatation
                current._trace.append({"event": "stimulus", "ts": now, "delta": delta})
            if delta != 0.0:
                deltas[current.id] = delta
        return deltas
