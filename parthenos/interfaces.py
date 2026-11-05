"""Stable LLM interface: context in, signals and priorities out.

The LLM is an interchangeable leaf — swapping it never touches the graph or
supervision logic. This module is the only surface the cloud LLM talks to.
"""

from __future__ import annotations

from typing import Any

_context: dict[str, Any] | None = None


def context_in(ctx: dict[str, Any]) -> None:
    """Consume LLM context: tokens, embeddings, task/project id, emotional tags."""
    global _context
    _context = dict(ctx)


def signals_out() -> dict[str, Any]:
    """Emit priorities/views/alerts for the LLM to consume."""
    return {
        "priorities": [],
        "views": [],
        "alerts": [],
    }
