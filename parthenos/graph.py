"""Level 2: associative graph store.

Every surviving memory receives dimensional metadata (semantic labels, emotional
valence, last-recall timestamp, task/project links) and typed edges. The sink/rise
mechanism stays behavior-driven (L1 floatation dynamics); categories are labels,
not drivers. Per-node locks from L1 are reused — never a whole-graph lock.
"""

from __future__ import annotations

from parthenos.node import Clock, MemoryNode, TypedEdge


class _Missing:
    """Sentinel for an absent dimensional attribute.

    Distinct from ``None`` so that ``None`` can be stored as a real value.
    """

    __slots__ = ()

    def __repr__(self) -> str:  # pragma: no cover - debugging aid
        return "Missing"


Missing = _Missing()


class GraphStore:
    """In-memory associative graph (S2 stand-in; persistence lands in S5)."""

    def __init__(self, clock: Clock | None = None) -> None:
        self._clock = clock if clock is not None else __import__("time").time
        self._nodes: dict[str, MemoryNode] = {}
        self._edges: dict[tuple[str, str], TypedEdge] = {}

    def add_node(self, node: MemoryNode) -> MemoryNode:
        """Register a node. Re-registering replaces the stored node."""
        self._nodes[node.id] = node
        return node

    def get_node(self, node_id: str) -> MemoryNode | None:
        """Return the stored node for ``node_id``, or ``None`` if absent."""
        return self._nodes.get(node_id)

    def _require_node(self, node_id: str) -> MemoryNode:
        node = self._nodes.get(node_id)
        if node is None:
            raise KeyError(node_id)
        return node

    def add_edge(
        self,
        src_id: str,
        tgt_id: str,
        kind: str,
        weight: float = 1.0,
        valid_at: float | None = None,
        invalid_at: float | None = None,
    ) -> TypedEdge:
        """Add a typed edge. Raises KeyError if either endpoint is absent."""
        self._require_node(src_id)
        self._require_node(tgt_id)
        edge = TypedEdge(
            target_id=tgt_id,
            kind=kind,
            weight=weight,
            valid_at=valid_at,
            invalid_at=invalid_at,
        )
        self._edges[(src_id, tgt_id)] = edge
        return edge

    def remove_edge(self, src_id: str, tgt_id: str) -> bool:
        """Remove an edge; returns True if it existed."""
        return self._edges.pop((src_id, tgt_id), None) is not None

    def neighbors(self, node_id: str, kind: str | None = None) -> list[TypedEdge]:
        """Outgoing edges of ``node_id``, optionally filtered by ``kind``."""
        result: list[TypedEdge] = []
        for (src_id, _tgt_id), edge in self._edges.items():
            if src_id == node_id and (kind is None or edge.kind == kind):
                result.append(edge)
        return result

    def set_dim(self, node_id: str, dim: str, value: object) -> None:
        """Set a dimensional attribute on a node (living vocabulary — any key)."""
        node = self._require_node(node_id)
        with node.lock:
            node.dims[dim] = value

    def get_dim(self, node_id: str, dim: str) -> object:
        """Return a dimensional attribute (Missing sentinel when absent)."""
        node = self._require_node(node_id)
        with node.lock:
            return node.dims.get(dim, Missing)
