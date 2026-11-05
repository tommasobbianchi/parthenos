# Parthenos — Metacognitive Layer for LLM Agents

> Status: draft v0.1 (2026-11-04). Owner: orchestrator. Source of truth for the design;
> implementation phases are tracked in bd under the epic `bd-parthenos` (or the epic id
> recorded in bd). This document is the canonical content; bd issues reference it.

## 1. Concept

Multi-dimensional associative memory inspired by human cognition. Each memory node carries
semantic, visual, associative, emotional, temporal, and task-project dimensions. Memories
behave like objects in a viscous liquid: frequent recall keeps them near the surface,
neglect makes them sink. Emotional stimuli (fear, anger) retrieve memories almost instantly;
database-style search takes minutes.

The layer sits **atop any interchangeable LLM** through a stable interface: context in,
signals and priorities out. Changing the model never touches the graph or supervision logic.
LLM inference runs in the cloud (external cost); the metacognitive layer is local.

## 2. Architecture — four levels

### Level 1 — Raw memory
- Raw memory, context window, ephemeral buffer. Maximum floatation, no structure yet.
- Events are ingested (utterances, tool results, task events) into an ephemeral buffer;
  survivors get promoted to persistent nodes.
- No schema, no graph — only recency/floatation dynamics.

### Level 2 — Associative graph
- Each surviving memory receives dimensional metadata:
  - semantic labels (free-form), emotional valence, last-recall timestamp,
    task and project links, typed edges (optionally carrying a bi-temporal validity
    window `valid_at`/`invalid_at`, mirroring the Zep Graphiti edge model).
- **Dimensions are a living vocabulary, not a rigid schema**: they can be renamed, merged,
  or split at runtime (vocabulary ops in the graph model).
- The sinking/rising mechanism depends on **behavior**, not on category names.

### Level 3 — Contextual partitioning (the heart)
- Does not move memories physically; builds **overlapping views**.
- Each active project gets a lens highlighting relevant nodes and attenuating others;
  cross-project links remain visible at reduced weight.
- Priority management lives here: strong emotional stimulus raises a node's weight
  regardless of project.

### Level 4 — Metacognitive supervision
- Does not touch data; it **observes movement**:
  - nodes sinking too fast, colliding projects, context jumps, which thread to resume.
- Proposes reorganizations, never imposes them.
- The only level that can tell the CEO (the human) where everything stands.

### Cross-level communication
Levels communicate **only through lightweight signals**: scores, labels, alerts. Never full
content. This keeps L4 cheap and decoupled.

## 3. Scalability model — foveal update

Local updates like the fovea: when a node is stimulated, only it and its direct neighbors
get full updates; ripples fade with distance.

- At 300–400k nodes, average degree 10–20 → cost per event = tens of light operations.
- A modern CPU handles hundreds of events/second. Bottleneck is memory: metadata for ~400k
  nodes may need several GB RAM. 16–32 GB + a decent CPU suffice for a prototype.
- GPU only if parallelizing view recomputation across projects.

### Cost model (reference numbers)
- `Event cost ≈ k * (1 + d_avg) + ∑_{hop h≤R} (d_avg^h) * β^h` with ripple decay `β∈[0,1)`,
  full-update radius `R` (default 3). For d_avg=15, β=0.5 → ~tens of ops. Documented in
  `parthenos/fovea.py` and asserted by a benchmark test (see S1).

## 4. Critical functions

| Function | Level | Description |
|---|---|---|
| Conflict detection | L4 | Two projects claim the same node with different weights → alert + proposal |
| Consolidation | L4 | Merge semantically similar nodes born separately (with timeline provenance) |
| Active pruning | L4 | Thresholds below which memories are archived or deleted |
| Context-switch estimation | L3/L4 | Cost estimate before jumping topics (what a switch will cost) |
| Behavioral anomaly detection | L4 | User uses terms from one project inside another → detect |
| Unexpected bridge discovery | L4 | Discover and surface cross-project links that were not explicit |
| Explainability | L4 | Say why a node was raised (decision trace: which event, which weight) |

## 5. Implementation functions

- **Versioned graph serialization**: timeline snapshots for restore and comparison
  (append-only event log + snapshot pointer).
- **Per-node concurrency control**: node-level locks, never whole-graph locks.
- **Aggregated telemetry**: heat maps, sinking trends per project, overall health
  indicators, predictive pre-fetching of hot caches above a confidence threshold.

## 6. Existing solutions — study and reuse

See `docs/research/existing-solutions.md` (produced by the research lane).

Recommended stack target (from the brief):
- **Zep or Cognee** as graph substrate.
- **Mem0** for conversational fact extraction.
- The metacognitive layer as orchestrator on top, using their APIs without rewriting them.
- (Research lane may revise the substrate choice with current evidence.)

| Concern | Candidate | Role |
|---|---|---|
| Graph substrate / temporal KG | Zep Graphiti, Cognee | L2 persistence + typed edges |
| Fact extraction | Mem0 | L1→L2 promotion |
| Context paging | Letta | reference for L1 buffer semantics |
| Re-consolidation / self-reweighting | Cognee, RMR | L4 inspiration |
| Metacognitive loops | MeLA, MetaCogAgent, MetaKGRAG, MAGMA, AssoMem | L3/L4 inspiration |

## 7. Lucid dreaming mode (metacognition squared)

A lightweight, incremental nightly self-calibration process that runs while LLM weights stay
frozen. It reorganizes the layer's own parameters: sinking thresholds, dimension weights,
priority rules. Like a librarian rearranging shelves and updating the catalog overnight
without rewriting the books. In the morning the system wakes already tuned.

The layer becomes aware of its own observation mechanisms and corrects its biases in real
time. Implementation: L4 runs a calibration pass over logged behavior (telemetry), produces
parameter deltas, applies them at a quiet checkpoint; no weights touched.

## 8. Stable LLM interface

```
context_in(ctx)      # from LLM: tokens, embeddings, task/project id, emotional tags
signals_out()        # to LLM: priorities, lens view, alerts, context-switch advice
```

Constructor/pluggability: the LLM is an interchangeable leaf; the graph and supervision
logic never depend on the model id.

## 9. Phased execution plan (epic)

Phase order respects level dependencies; S5 (serialization) and S6 (telemetry) run in
parallel with S2+. Tracked in bd under the epic.

| Phase | Scope | Depends on |
|---|---|---|
| S0 | Research existing solutions (completed by research lane) | — |
| S1 | Scaffold + core data model + Level-1 raw/ephemeral buffer + foveal engine + stable interface stub | — |
| S2 | Level-2 associative graph: dims, typed edges, living-vocabulary ops | S1 |
| S3 | Level-3 lenses: per-project views, attenuation, emotional priority override | S2 |
| S4 | Level-4 supervision: conflict, consolidation, pruning, context-switch, anomaly, bridge, explainability | S3 |
| S5 | Versioned serialization + timeline snapshots + per-node concurrency | S2 (parallel) |
| S6 | Telemetry + predictive pre-fetch | S3/S4 |
| S7 | Lucid dreaming nightly calibration | S4 |
| S8 | Substrate integration (Zep/Cognee/Mem0) behind the stable interface | S2/S3 |

## 10. Verification posture

- Every phase ships with an authored fail-to-pass test suite (loopspec discipline).
- Benchmarks: fovea cost at 400k nodes / avg degree 15 must hold the tens-of-ops bound
  (asserted in tests, not just measured in prose).
- All changes land as reviewed diffs; claims verified by re-running gates, not by worker
  reports.
