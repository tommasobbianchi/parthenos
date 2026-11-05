"""Agent-Telegram bridge — pure routing helpers tests (slice 2)."""

from __future__ import annotations

import importlib.util
import pathlib

_spec = importlib.util.spec_from_file_location(
    "agent_tg_bridge",
    pathlib.Path(__file__).resolve().parent.parent / "deploy" / "agent-tg" / "bridge.py",
)
bridge = importlib.util.module_from_spec(_spec)
assert _spec.loader is not None
_spec.loader.exec_module(bridge)


def test_is_agent_command():
    assert bridge.is_agent_command("/agent saluta")
    assert bridge.is_agent_command("/Agent ciao")  # case-insensitive
    assert bridge.is_agent_command("  /agent x")
    assert not bridge.is_agent_command("/agentx")
    assert not bridge.is_agent_command("ciao /agent")
    assert not bridge.is_agent_command("Athena, che ore sono?")


def test_strip_agent_prefix():
    assert bridge.strip_agent_prefix("/agent saluta") == "saluta"
    assert bridge.strip_agent_prefix("/Agent ciao bello") == "ciao bello"
    assert bridge.strip_agent_prefix("  /agent x  ") == "x"
