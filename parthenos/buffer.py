"""Level 1: raw memory, context window, ephemeral buffer.

Maximum floatation, no structure yet. Events land in the ephemeral buffer;
survivors are promoted to persistent nodes.
"""

from __future__ import annotations

from parthenos.events import Event
from parthenos.node import (
    DEFAULT_NEGLECT_RATE,
    DEFAULT_RECALL_STRENGTH,
    Clock,
    MemoryNode,
)


class EphemeralBuffer:
    """Bounded buffer of raw events. Promotes survivors into the persistent store."""

    def __init__(self, capacity: int = 1024, clock: Clock | None = None) -> None:
        self.capacity = capacity
        self._clock = clock if clock is not None else __import__("time").time
        self._events: list[Event] = []
        self.nodes: dict[str, MemoryNode] = {}

    def ingest(self, event: Event) -> MemoryNode:
        """Absorb a raw event. Returns the promoted node (or raises on overflow policy)."""
        self._events.append(event)
        return self.promote(event)

    def promote(self, event: Event) -> MemoryNode:
        """Promote an event into an in-memory MemoryNode (S1 stand-in for persistence)."""
        node_id = event.node_id or self._next_id()
        now = self._clock()
        node = MemoryNode(id=node_id, created_at=now, last_recall=now, floatation=1.0)
        self.nodes[node_id] = node
        return node

    def recall(self, node: MemoryNode, strength: float = DEFAULT_RECALL_STRENGTH) -> float:
        """Raise `node`'s floatation using the buffer's injectable clock."""
        return node.recall(self._clock(), strength=strength)

    def neglect(self, node: MemoryNode, rate: float = DEFAULT_NEGLECT_RATE) -> float:
        """Lower `node`'s floatation using the buffer's injectable clock."""
        return node.neglect(self._clock(), rate=rate)

    def drain(self) -> list[Event]:
        """Return buffered events (used by the periodic sweeper)."""
        return self._events

    def _next_id(self) -> str:
        return f"node-{len(self._events)}"
