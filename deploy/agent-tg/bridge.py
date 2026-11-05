#!/usr/bin/env python3
"""Parthenos agent ↔ Athena Telegram bridge.

Reuses Athena's existing Telegram channel (single poller owns getUpdates),
so this bridge does NOT call Telegram's API for inbound. Instead it watches
Athena's append-only `inbox.ndjson` (written by `inbox-poll.py` every 30s)
and handles messages prefixed with `/agent`:

  /agent <prompt>  -> Hermes agent (with Athena grounding + durable memory)
                      -> reply in the same Telegram chat
                      -> back-route a tell event into Athena's project-status
                         inbox (athena tell Parthenos ...)

Everything else is left to Athena's normal pipeline (tmux injection).

Outbound uses Athena's `_tg.send_message` (sendMessage is safe to call
concurrently with the poller — it only writes the chat, never reads updates).
"""
from __future__ import annotations

import importlib.util
import os
import pathlib
import subprocess
import time

REPO = pathlib.Path(__file__).resolve().parent.parent.parent
ATHENA = pathlib.Path.home() / "projects" / "athena"
COMM_TG_SCRIPTS = ATHENA / "modules" / "comm-tg" / "scripts"
INBOX_NDJSON = ATHENA / "modules" / "comm-tg" / "data" / "inbox.ndjson"
AGENT_LOOP = REPO / "bin" / "agent-loop.py"
ATHENA_BIN = pathlib.Path.home() / ".local" / "bin" / "athena"

POLL_SECONDS = 5.0


def _ensure_paths() -> None:
    """systemd user services get a minimal PATH; make ~/.local/bin visible."""
    local_bin = str(pathlib.Path.home() / ".local" / "bin")
    current = os.environ.get("PATH", "")
    if local_bin not in current.split(os.pathsep):
        os.environ["PATH"] = local_bin + os.pathsep + current


def _load_module(name: str, path: pathlib.Path):
    spec = importlib.util.spec_from_file_location(name, str(path))
    mod = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(mod)
    return mod


def is_agent_command(text: str) -> bool:
    stripped = text.strip()
    return stripped.lower().startswith("/agent ") or stripped.lower() == "/agent"


def strip_agent_prefix(text: str) -> str:
    stripped = text.strip()
    return stripped[len("/agent"):].strip()


class Bridge:
    def __init__(self) -> None:
        _ensure_paths()
        self._tg = _load_module("_tg", COMM_TG_SCRIPTS / "_tg.py")
        self._agent_loop = _load_module("agent_loop", AGENT_LOOP)
        self._offset = INBOX_NDJSON.stat().st_size if INBOX_NDJSON.exists() else 0

    # -- inbound -------------------------------------------------------------

    def _new_records(self) -> list[dict]:
        import json

        if not INBOX_NDJSON.exists():
            return []
        with INBOX_NDJSON.open(encoding="utf-8") as fh:
            fh.seek(self._offset)
            lines = fh.readlines()
            self._offset = fh.tell()
        out: list[dict] = []
        for line in lines:
            line = line.strip()
            if not line:
                continue
            try:
                out.append(json.loads(line))
            except json.JSONDecodeError:
                continue
        return out

    # -- outbound -----------------------------------------------------------

    def _reply(self, text: str, reply_to_message_id: int | None) -> None:
        # parse_mode=None: agent text may contain <>& that HTML mode would choke on.
        self._tg.send_message(text, reply_to_message_id=reply_to_message_id,
                              parse_mode=None)

    def _ack_eyes(self, msg_id: int) -> None:
        self._tg.set_message_reaction(int(msg_id), emoji="👀")

    def _backroute(self, summary: str) -> None:
        try:
            subprocess.run(
                [str(ATHENA_BIN), "tell", "Parthenos", summary],
                capture_output=True, text=True, check=False, timeout=20,
            )
        except (OSError, subprocess.TimeoutExpired):
            pass

    # -- one message --------------------------------------------------------

    def handle_record(self, rec: dict) -> None:
        text = (rec.get("text") or "").strip()
        if not is_agent_command(text):
            return
        msg_id = rec.get("msg_id")
        if msg_id is not None:
            self._ack_eyes(msg_id)
        prompt = strip_agent_prefix(text)
        grounding = self._agent_loop.fetch_athena_grounding()
        rc, answer = self._agent_loop.run_prompt(prompt, grounding, return_text=True)
        if rc != 0:
            return
        answer = (answer or "").strip()
        if answer:
            if len(answer) > 3600:
                answer = answer[:3600] + "\n…(troncato)"
            self._reply(answer, reply_to_message_id=msg_id)
        self._backroute(f"telegram /agent handled msg {msg_id}: {prompt[:120]}")

    # -- loop ---------------------------------------------------------------

    def run_forever(self) -> None:
        print("agent-tg bridge watching", INBOX_NDJSON, flush=True)
        while True:
            for rec in self._new_records():
                try:
                    self.handle_record(rec)
                except Exception as exc:  # noqa: BLE001
                    print("handle_record error:", type(exc).__name__, exc, flush=True)
            time.sleep(POLL_SECONDS)


if __name__ == "__main__":
    Bridge().run_forever()
