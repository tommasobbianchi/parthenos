# Existing Solutions — Study & Reuse Matrix

> Status: v1.0 (2026-11-04). Produced by the orchestrator (research lane) after the explorer
> subagent failed to spawn twice ("no user query found in messages" / "no model fallback
> chain for explorer"). Sources: official repos/docs + web searches, URLs inline.
> Verdicts are for Parthenos: a 4-level metacognitive layer the orchestrates substrates,
> never rewrites them.

## 1. Matrix

| # | Solution | One-liner | Deploy mode | Maturity | Key API concepts | License | Verdict |
|---|---|---|---|---|---|---|---|
| 1 | **Mem0** (mem0ai) | Drop-in memory layer for agents: extract conversational facts into a vector store with auto-linking | Python SDK + self-hosted server (Docker: API, Postgres+pgvector, Neo4j) + cloud | Active; Python SDK v2.2.1 (Sep 2026) | `add/search/get/update/delete` memories; graph memory; `Memory` class; framework-agnostic | Apache-2.0 (OSS core; self-hosted no usage-based billing) | **fact-extraction** substrate |
| 2 | **Zep/Graphiti** | Bi-temporal knowledge graph: facts + edges with valid_from/valid_to, entity resolution | Zep: memory-layer service. Graphiti: open-source Python framework (you supply graph DB + LLM + embedder) | Graphiti ~31.3k stars (Sep 2026); active | Temporal Context Graph; `Graphiti` class, `add_episode`, `search`; Neo4j backend | Apache-2.0 | **graph substrate** (L2 temporal edges) |
| 3 | **Letta** (f.k.a. MemGPT) | OS-style virtual memory paging: move data between core memory (RAM) and external memory (disk) | Full agent runtime (Python framework) | Active (github.com/letta-ai/letta) | Memory blocks in context window; recall memory saved to disk; agent loop + tool execution | Apache-2.0 | **peer/L1 reference** (buffer semantics) |
| 4 | **Cognee** | Graph-vector hybrid memory engine with data pipelines; entity consolidation, self-reweighting | Python library; self-hosted (Docker), on-prem, or cloud | Active | `cognee.add/search`; graph+vector+relational triple store; memify pipeline | Apache-2.0 (OSS) | **graph substrate** candidate |
| 5 | **RMR** (Re-consolidative Metacognitive Retrieval) | Metacognitive consolidation: accumulate reusable meta-reasoning skills across instances (beyond episodic meta-reasoning) | Paper (arXiv 2604.17399; ACL 2026) | No public code found | "Perceive-Judge-Consolidate" style cycles; skill accumulation | — | **conceptual** (L4 inspiration) |
| 6 | **MeLA** | Metacognitive LLM-driven architecture for Automatic Heuristic Design via prompt evolution (refine guiding prompt from feedback) | Paper (arXiv 2507.20541; cited 6) | No standalone code found | Metacognition prompt; prompt evolution loop | — | **conceptual** (L4/param calibration inspiration) |
| 7 | **MetaCogAgent** | Multi-agent LLM framework with self-aware task delegation: each agent judges answer-vs-delegate | Paper (arXiv 2605.17292; 2026) | No standalone code found | Self-awareness module; task-capability alignment | — | **conceptual** (delegation patterns) |
| 8 | **MetaKGRAG** | Metacognitive KG-RAG: path-aware Perceive-Evaluate-Adjust closed loop over graph exploration | Paper (arXiv 2508.09460; cited 3) | No standalone code found | Perceive/Evaluate/Adjust cycle; path-level deficiency self-assessment | — | **conceptual** (L4 supervise L3 retrieval) |
| 9 | **MAGMA** | Multi-graph agentic memory: each memory represented across orthogonal semantic/temporal/causal/entity graphs; retrieval = policy-guided traversal | Paper (arXiv 2601.03236; cited 71) + GitHub FredJiang0324/MAGMA | Code repo exists (paper-driven) | Multi-graph views; policy-guided traversal | — (check repo) | **peer component** (multi-view precedent for L3 lenses) |
| 10 | **AssoMem** | Associative memory graph for scalable memory QA: relevance + importance + temporal alignment via RITRanker | Paper (arXiv 2510.10397) + GitHub facebookresearch/AssoMem | Code repo exists (Meta/FAIR) | Associative graph; multi-signal retrieval (relevance/importance/temporal) | — (check repo) | **peer component** (multi-signal ranking for L2/L3) |

## 2. Reuse opportunities specific to Parthenos

- **Bi-temporal edges (Zep Graphiti)** → implement L2 typed edges with valid-until semantics; also
  gives us entity-resolution to cheaply detect consolidation candidates.
- **Self-reweighting / consolidation (Cognee, RMR)** → L4 consolidation + pruning design can borrow
  the "entity description fragmentation + consolidation" approach Cognee documents.
- **Multi-signal ranking (AssoMem)** → our L2/L3 weight compositing (semantic × emotional × recency
  × project) maps directly onto their relevance/importance/temporal triplet; copy the adaptive
  mutual re-ranking idea.
- **Multi-graph views (MAGMA)** → precedent for L3 lenses: orthogonal graphs over the same nodes,
  retrieval as traversal. We do overlapping *views* (no physical moves) — same spirit.
- **Prompt/parameter evolution (MeLA)** → precedent for lucid-dreaming calibration: evolve the
  layer's own parameters from traces, not the LLM weights.
- **Per-node concurrency / timelines / telemetry**: none of the surveyed solutions advertise
  ready-made per-node locking, versioned snapshot timelines, or health telemetry — build these
  ourselves (S5/S6).

## 3. Stack recommendation (updated)

Keep the brief's default, confirmed by today's evidence:

- **Graph substrate (L2)**: Zep Graphiti (Apache-2.0, active, bi-temporal) — with Cognee as the
  alternative if we want one library that also does ingestion pipelines (Graphiti is more of a
  framework; you supply DB/LLM/embedder).
- **Fact extraction (L1→L2 promotion)**: Mem0 (Python SDK v2.2.1) — conversational fact
  extraction + auto-linking, self-hosted Docker stack available.
- **Orchestrator**: Parthenos itself (pure-Python core, S1) on top, via the stable interface.
- **Conceptual borrows**: RMR/MetaKGRAG → L4 supervision loops; MAGMA → L3 lens view model;
  AssoMem → multi-signal weight compositing; MeLA → lucid dreaming.

> Note for S8: adapters must wrap Zep/Cognee/Mem0 behind the stable interface
> (`parthenos/interfaces.py`) so a substrate swap never touches L3/L4.

## 4. Integration mapping (post-S8, against the implemented code)

How each solution maps onto the concrete Parthenos modules now in the repo:

| Solution | Maps to | Concrete wiring |
|---|---|---|
| **Mem0** (v2 SDK) | L1→L2 promotion (`parthenos/buffer.py`) + `adapters.Mem0Adapter` | Feed utterances to Mem0 `add` (extracts conversational facts into the vector store); promote results into `MemoryNode`s; candidate retrieval via `search` normalized by the adapter. Backends: Qdrant, Valkey, Neo4j; self-hosted Docker stack (API + Postgres/pgvector + Neo4j). |
| **Zep Graphiti** (graphiti-core 0.7.8) | L2 graph substrate (`parthenos/graph.py` temporal edges) + `adapters.ZepAdapter` | Graphiti is a **library, not a service**: you supply the graph DB (Neo4j), an LLM, and an embedder. Its bi-temporal edge model (edges carry valid_at/invalid_at + created/expired timestamps) is the exact temporal metadata our L2 `TypedEdge` should carry in real deployment. Add episodes via `add_episode`, query via `search`. |
| **Cognee** | L2/L4 alternative substrate + L4 consolidation support | E→C→L pipeline: `cognee.add()` ingests, `cognee.search()` queries graph+vector+relational. Built-in entity consolidation is a candidate engine behind our L4 `propose_consolidation`. |
| **Letta** (MemGPT) | L1 buffer semantics reference | Memory blocks = conceptual model for `EphemeralBuffer` promotion/eviction policy. |
| **RMR / MetaKGRAG** | L4 supervision loops conceptual borrow | Perceive-Evaluate-Adjust style cycles inspire `Supervision`/`Reorganizer` orchestration. |
| **MAGMA** | L3 lens model precedent | Orthogonal graphs over same nodes, retrieval as traversal → our `Lens.view` overlapping views. |
| **AssoMem** | L2/L3 weight compositing | Relevance × importance × temporal multi-signal ranking → our floatation × membership × emotional override compositing. |
| **MeLA** | L7 lucid dreaming precedent | Prompt/parameter evolution over traces → `Calibrator` proposal rules. |

**Reference topology (recommended):** local Parthenos orchestrator (modules in `parthenos/`) ↔ adapters (`adapters.py`) → Graphiti+Neo4j for the temporal graph substrate and Mem0 for conversational fact extraction; Cognee as a drop-in substrate alternative. Everything behind the stable `interfaces.py` contract, so swapping a substrate never touches L3/L4 or the LLM.

## 5. License & deployment snapshot

| Solution | License | Deploy mode | Version/signal |
|---|---|---|---|
| Mem0 | Apache-2.0 | Self-hosted server (Docker) or cloud; no usage-based billing self-hosted | Python SDK v2.2.1 (Sep 2026) |
| Zep Graphiti | Apache-2.0 | Library only (needs Neo4j + LLM + embedder) | graphiti-core 0.7.8 (PyPI); ~31.3k★ |
| Cognee | Apache-2.0 | Python library; Docker self-host / on-prem / cloud | active |
| Letta | Apache-2.0 | Full agent runtime (Python) | active |
| RMR / MeLA / MetaCogAgent / MetaKGRAG / MAGMA / AssoMem | — (papers; MAGMA & AssoMem have code repos) | conceptual / reference | cited above |

## 6. Sources

- Mem0: github.com/mem0ai/mem0 · mem0.ai · self-host Docker guide (mem0.ai/library/integrations/self-host-mem0-docker)
- Graphiti: github.com/getzep/graphiti (31.3k★) · getzep.com/platform/graphiti · arXiv 2501.13956 (Zep)
- Letta: github.com/letta-ai/letta · letta.com/blog/memory-blocks
- Cognee: github.com/topoteretes/cognee · docs.cognee.ai · cognee.ai
- RMR: arXiv 2604.17399 (Metacognitive Consolidation, ACL 2026)
- MeLA: arXiv 2507.20541
- MetaCogAgent: arXiv 2605.17292
- MetaKGRAG: arXiv 2508.09460
- MAGMA: arXiv 2601.03236 · github.com/FredJiang0324/MAGMA
- AssoMem: arXiv 2510.10397 · github.com/facebookresearch/AssoMem
- API specifics (2026-11-04 re-check): Mem0 `add`/`search` docs (docs.mem0.ai/core-concepts/memory-operations/add); Graphiti bi-temporal edges — valid_at/invalid_at (+ created/expired) per getzep.com/blog/beyond-static-knowledge-graphs and graphiti-core 0.7.8 (PyPI); Cognee E→C→L `cognee.add()`/`cognee.search()` (docs.cognee.ai/python-api).
