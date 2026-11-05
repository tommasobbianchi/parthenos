"""Memory node model (Level 1 seed, Level 2 dims).

Dimensions are a *living vocabulary*, not a rigid schema: `dims` is a free-form
dict that Level 2 can rename/merge/split at runtime. Level 1 only needs the
floatation lifecycle (sink/rise).
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from threading import Lock
from typing import Any

Clock = Callable[[], float]

DEFAULT_RECALL_STRENGTH = 0.5
DEFAULT_NEGLECT_RATE = 0.05


@dataclass
class TypedEdge:
    """Edge with a living type label; added in Level 2.

    Temporal fields (valid_at/invalid_at) mirror the bi-temporal model of
    substrate graphs like Zep Graphiti; both are optional and default to None
    (always-valid edge).
    """

    target_id: str
    kind: str
    weight: float = 1.0
    valid_at: float | None = None
    invalid_at: float | None = None


@dataclass
class MemoryNode:
    """A single memory. Sinks on neglect, rises on recall/stimulus."""

    id: str
    created_at: float
    last_recall: float
    floatation: float = 1.0
    dims: dict[str, Any] = field(default_factory=dict)
    edges: list[TypedEdge] = field(default_factory=list)
    # Per-node lock: foveal updates synchronize at node granularity, never
    # across the whole graph. Not part of the data model (init=False).
    lock: Lock = field(default_factory=Lock, init=False, repr=False, compare=False)
    # Private decision trace: one {event, ts, delta} entry per recall/neglect/
    # stimulus event since creation. Populated by recall/neglect (below) and by
    # FoveaEngine.stimulate. Not part of the data model (init=False).
    _trace: list[dict[str, Any]] = field(
        default_factory=list, init=False, repr=False, compare=False
    )

    def recall(self, now: float, strength: float = DEFAULT_RECALL_STRENGTH) -> float:
        """Raise floatation toward the 1.0 ceiling and refresh `last_recall`."""
        with self.lock:
            before = self.floatation
            self.floatation = min(1.0, self.floatation + strength)
            self.last_recall = now
            self._trace.append(
                {"event": "recall", "ts": now, "delta": self.floatation - before}
            )
            return self.floatation

    def neglect(self, now: float, rate: float = DEFAULT_NEGLECT_RATE) -> float:
        """Lower floatation toward 0.0 in proportion to time since last recall."""
        with self.lock:
            before = self.floatation
            elapsed = max(0.0, now - self.last_recall)
            self.floatation = max(0.0, self.floatation - rate * elapsed)
            self._trace.append(
                {"event": "neglect", "ts": now, "delta": self.floatation - before}
            )
            return self.floatation
