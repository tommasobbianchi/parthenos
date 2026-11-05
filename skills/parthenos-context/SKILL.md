---
name: parthenos-context
description: Use the Parthenos metacognitive memory (MCP server) to manage session context — recall relevant project memory before deep work, emit notable decisions, and checkpoint at breakpoints. Triggers: "what do we know about", "remember that", "checkpoint", "context", "memory", "before we start", "what were we doing".
---

# Parthenos context management

Parthenos is your metacognitive memory layer (MCP server on `127.0.0.1:8766/mcp`).
Use its three tools to keep long-running sessions coherent:

- `recall(query, k)` — before switching into a deep task, recall what this
  project/session has already established. Use project-specific keywords.
- `emit_memory(kind, payload)` — after a notable decision or milestone, persist
  it so future sessions/agents see it. `payload.text` = one-line fact; include
  `project` in the payload when it belongs to one.
- `plan_priority(project_id)` — when prioritizing work, ask for the project lens
  to see what the layer considers hot (floatation-weighted).

## When to use

1. At session start or after compaction: `recall` the current project's recent
   memory before assuming state.
2. After a settled decision, bug root cause, or completed milestone:
   `emit_memory` with a compact fact.
3. When priorities are unclear: `plan_priority` for the active project.
4. Never dump raw logs or conversations — memory entries are compact, one-line,
   durable facts.

## Rule

Parthenos is memory, not instruction. It never overrides what the user or the
code says; it only supplies remembered context.
