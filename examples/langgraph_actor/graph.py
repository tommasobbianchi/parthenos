"""A3 — minimal LangGraph actor (orchestration placeholder).

A tiny stateful graph for the Parthenos orchestration backend (A3). One node
echoes a message and stamps a status; in-memory checkpoints. This is the
integration contract, not the full L4 policy engine — L4 stays in-house and
calls this service when it needs graph-state orchestration.
"""

from __future__ import annotations

from typing import Annotated, TypedDict

from langgraph.graph import END, START, StateGraph
from langgraph.graph.message import add_messages


class ActorState(TypedDict):
    messages: Annotated[list[str], add_messages]
    status: str


def orchestrate(state: ActorState) -> ActorState:
    """Pass-through node: mirror messages, stamp status."""
    return {"messages": state.get("messages", []), "status": "orchestrated"}


builder = StateGraph(ActorState)
builder.add_node("orchestrate", orchestrate)
builder.add_edge(START, "orchestrate")
builder.add_edge("orchestrate", END)

app = builder.compile()
