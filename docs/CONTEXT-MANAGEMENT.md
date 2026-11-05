# Context management: wiring Parthenos into LLM sessions

Parthenos acts as a metacognitive memory layer for Claude Code and OpenCode
sessions over MCP. This file documents how to register it and how agents are
directed to use it.

## MCP registration (one-time, per machine)

Both clients point at the single loopback server (`127.0.0.1:8766/mcp`).
Use a remote/HTTP entry — never a per-session local spawn (that caused a
process leak across sessions; see `docs/research/r1-sweep-mercury3.md`).

**OpenCode** (`~/.config/opencode/opencode.jsonc`):

```jsonc
"mcp": {
  "parthenos": {
    "type": "remote",
    "url": "http://127.0.0.1:8766/mcp",
    "enabled": true
  }
}
```

**Claude Code** (`~/.claude.json` → `mcpServers`):

```json
"parthenos": { "type": "http", "url": "http://127.0.0.1:8766/mcp" }
```

Claude loads MCP servers at session start; OpenCode picks them up for new
sessions (and sometimes live).

## Tools exposed

| Tool | Purpose |
|---|---|
| `recall(query, k)` | search memories by dim-value substring; sorted by floatation |
| `emit_memory(kind, payload)` | persist a one-line durable fact (use `project` key in payload) |
| `plan_priority(project_id)` | project lens view, weight-descending |

## Policy layer (skill / directive)

Agents are told **when** to use the tools — not just that they exist:

- **Claude Code**: skill `skills/parthenos-context/SKILL.md` (copy to
  `~/.claude/skills/parthenos-context/SKILL.md`).
- **OpenCode**: directive in `~/.config/opencode/AGENTS.md`.

Policy summary: recall before deep work; emit after settled decisions/root
causes/milestones; use `plan_priority` when ordering; never dump raw logs —
memory entries are compact facts; Parthenos is memory, never instruction.
