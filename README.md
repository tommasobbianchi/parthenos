# Parthenos

A **metacognitive memory layer** for LLM agents — a four-level associative memory
with foveal (local) updates, a living dimensional vocabulary, and a supervisor
that proposes, never imposes.

Built as the memory brain of a personal agent: it sits atop any interchangeable
LLM through a stable interface (`context in, signals out`), and orchestrates
substrate services (Mem0, Zep Graphiti, LangGraph) without rewriting them.

## The four levels

| Level | What it is |
|---|---|
| L1 | Raw memory / context window / ephemeral buffer — maximum floatation, no structure |
| L2 | Associative graph + dimensional metadata (semantic, emotional, temporal, project). Dims are a *living vocabulary*: rename/merge/split at runtime; sink/rise is behavior-driven |
| L3 | Contextual partitioning — per-project lenses: overlapping views, cross-project links attenuated, emotional override |
| L4 | Metacognitive supervision — watches movement (sinking, collisions, context jumps), proposes reorganizations, explains decisions |

Levels communicate only through lightweight signals (scores/labels/alerts); the
LLM is an interchangeable leaf.

## Scalability

Foveal updates: a stimulus updates a node and its direct neighborhood, with
`-` decay at distance. Prototype target: ~400k nodes, average degree 15 →
measured **7,304 events/s, p99 0.16 ms**, ~46 nodes touched (see
`tests/test_benchmark.py`).

## Repository layout

```
parthenos/     core layers (L1–L4, serialization, telemetry, adapters, MCP server)
bin/           launchers: parthenos-mcp, parthenos-dream, agent-loop
deploy/        substrate deployments (Mem0 compose + live smoke, OpenHands driver, TG bridge)
examples/      LangGraph orchestration example
docs/          architecture + research notes
systemd/       user units for supervised deployment
tests/         pytest suite (run: python3 -m pytest -q)
```

## Quick start (core)

```bash
python3 -m pytest -q            # full suite
pytest -m benchmark tests/test_benchmark.py   # scale benchmark
./bin/parthenos-mcp --store data/graph.snapshot.json   # durable MCP server
```

## License

GPL-3.0. See [LICENSE](LICENSE).
