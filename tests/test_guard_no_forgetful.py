"""GUARD: Parthenos runtime code must never call the Forgetful MCP server.

Forgetful is the curated global memory (checkpoint protocol only — invoked by
the agent session, never by Parthenos code). Writing every event/loop to
Forgetful would flood it (observed: 20+ leaked per-session MCP processes and a
4MB WAL). This test asserts the runtime tree contains no Forgetful client
references, so a future "helpful" integration fails the suite loudly.
"""

from __future__ import annotations

import pathlib

ROOT = pathlib.Path(__file__).resolve().parent.parent
SCAN_DIRS = ("parthenos", "bin", "deploy")
FORBIDDEN = (
    "forgetful-ai",
    "forgetful_ai",
    "Forgetful",
    "create_memory",
    "execute_forgetful_tool",
    "query_memory",
)
IGNORED = {".git", "__pycache__", "node_modules", ".venv", "workspace"}


def _iter_files():
    for d in SCAN_DIRS:
        base = ROOT / d
        if not base.exists():
            continue
        for p in base.rglob("*"):
            if not p.is_file() or p.name.startswith("."):
                continue
            if any(part in IGNORED for part in p.parts):
                continue
            if p.suffix in {".py", ".sh", ".js", ".ts", ".jsonc", ".md", ".service", ".timer"}:
                yield p


def test_no_forgetful_client_in_runtime_tree():
    hits = []
    for f in _iter_files():
        try:
            text = f.read_text(encoding="utf-8", errors="ignore")
        except OSError:
            continue
        for token in FORBIDDEN:
            if token.lower() in text.lower():
                hits.append((str(f.relative_to(ROOT)), token))
    assert not hits, "Forbidden Forgetful references in Parthenos runtime:\n" + \
        "\n".join(f"  {path}: {tok}" for path, tok in hits)
