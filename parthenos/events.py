"""Event model. Levels communicate only through lightweight signals (scores/labels/alerts)."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

EVENT_KINDS = frozenset(
    {
        "ingest",        # raw utterance / tool result / task event -> ephemeral buffer
        "recall",        # node retrieved (raises floatation)
        "promote",       # ephemeral survivor promoted to persistent node
        "emotional_stimulus",  # fear/anger/etc -> near-instant retrieval
        "context_switch",       # topic jump (L3/L4 estimate cost)
        "neglect",       # time passed without recall
    }
)


@dataclass
class Event:
    kind: str
    payload: dict[str, Any] = field(default_factory=dict)
    ts: float = 0.0

    def __post_init__(self) -> None:
        if self.kind not in EVENT_KINDS:
            raise ValueError(f"unknown event kind: {self.kind}")

    @property
    def node_id(self) -> str | None:
        return self.payload.get("node_id")
