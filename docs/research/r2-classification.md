# R2 — Actor Role Classification (Parthenos/Athena personal-agents epic)

> Research date: 2026-11-04. Inputs: `r1-sweep-mercury3.md` (validated matrix + protocol layer) and `personal-agents-actors.md` §1 taxonomy / §5 R1 verification. This file maps each candidate onto the pipeline actor taxonomy and pins plug-in points for Athena (awareness shell) + Parthenos (metacognitive layer, S8 adapters). Every factual claim carries its source URL (reused from R1 where applicable). Roles per §1 taxonomy: **Perceive · Memory · Plan · Execute · Communicate · Supervise · Identity**.

---

## 1. Candidate → roles matrix

| Candidate | Roles it best fits | One-line justification |
|---|---|---|
| **Hermes Agent** | **Memory** · **Execute/tool** · **Communicate/efferent** · **Identity/personalization** · (Plan, partial) | Native memory+skill learning loop (FTS5 cross-session recall, Honcho dialectic user modeling, `/learn`, `skill_manage`), 40+ tools + MCP + 6 terminal backends (execute), multi-platform messaging gateway + TTS outbound (communicate), profiles + user model (identity); small self-hosted footprint (sources: https://github.com/NousResearch/hermes-agent; https://hermes-agent.nousresearch.com/docs/user-guide/features/skills). |
| **OpenHands** | **Execute/tool** · **Supervise/orchestrate** (partial) | AI-driven software-dev agent with a clean SDK + HTTP agent-server + ACP boundary (execute); Agent Canvas + automation server can schedule/orchestrate agents (supervise partial) (source: https://github.com/OpenHands/OpenHands). |
| **AutoGPT** | **Execute/tool** · **Supervise/orchestrate** (platform) · **Plan** (autonomous loop) | Platform for building/deploying/managing continuous agents — an actor *factory* rather than a single actor; beta + Polyform Shield friction (source: https://github.com/Significant-Gravitas/AutoGPT). |
| **CrewAI** | **Supervise/orchestrate** · **Plan** · **Execute** | Role-based crews + flows are a ready-made role model (supervise/plan); agents call tools inside a crew (execute); needs your own service wrapper (source: https://github.com/crewAIInc/crewAI). |
| **LangGraph / LangChain** | **Supervise/orchestrate** · **Plan** · **Memory** (checkpoints) | Graph-state orchestration + durable checkpoints (memory substrate), the most robust orchestration SDK/server; you build the agent (source: https://github.com/langchain-ai/langgraph). |
| **Khoj** | **Memory** · **Perceive** (doc ingest) · **Communicate** · **Execute** | Self-hosted RAG "second brain" over your docs/web (memory + perceive), email/WhatsApp automations (communicate/execute); AGPL (source: https://github.com/khoj-ai/khoj). |
| **OpenClaw** | **Perceive** (channels in) · **Communicate** (channels out) · **Execute** · **Identity/personalization** · **Supervise** (multi-agent routing) | Full personal-agent gateway across 20+ channels (perceive/communicate), host-level tool execution (execute), SOUL.md persona + memory (identity), multi-agent routing (supervise); ⚠️ security posture (sandbox off by default, CVE-2026-25253, Moltbook breach) (sources: https://github.com/openclaw/openclaw; https://clawdocs.org/security/overview). |
| **MCP (protocol)** | **Execute/tool** + **Memory** (resources) | Near-universal actor interface: standardizes agent↔tool/data connection (JSON-RPC 2.0); the interop backbone (source: https://www.infoworld.com/article/4007686/a-developers-guide-to-ai-protocols-mcp-a2a-and-acp.html). |
| **ACP (protocol)** | **Execute/tool** (client↔agent) | Zed's Agent Client Protocol standardizes editor/IDE↔agent hosting (only Hermes + OpenHands expose it; IBM's older ACP is dead → absorbed into A2A) (sources: https://agentclientprotocol.com/; https://crystl.dev/blog/agent-communication-protocols). |
| **A2A (protocol)** | **Supervise/orchestrate** (agent↔agent) | v1.0 under Linux Foundation: task delegation + AgentCard discovery; the L4 → actor fan-out protocol; no surveyed candidate exposes an A2A server by default (source: https://a2a-protocol.org; https://crystl.dev/blog/agent-communication-protocols). |
| **ANP (protocol)** | **Identity** (decentralized discovery) | Capability/identity discovery over HTTP with selective sharing; least mature, W3C-discussed, not shipping on these candidates (source: https://agentsurface.dev/docs/protocols/comparison). |

---

## 2. Plug-in mapping for Athena + Parthenos

Attachment marks: **direct** = works today via existing interface · **adapter needed** = wrap behind an S8-style adapter / Athena module · **not now** = excluded or needs hardening.

| Role | Candidate (if any) | Where it attaches | Mark |
|---|---|---|---|
| **Perceive / senses** | Khoj (doc ingest) — no ambient/wearable OSS actor | Parthenos `parthenos/` — feed ingested docs as a source to memory; Athena stays the owner of raw sense streams | adapter needed |
| | Hermes / OpenClaw gateways (chat/message inbound) | Athena — new sense module subscribing to gateway inbound (awareness of user messages) | adapter needed |
| **Memory (substrate)** | Khoj | Parthenos memory module behind `adapters.py` — alternative substrate, REST/MCP interface | adapter needed (AGPL: decide before commit) |
| | Hermes memory/skills (FTS5 + Honcho) | Parthenos — expose via `hermes mcp serve` / API; memory retrieval + skill store as substrate | adapter needed |
| | LangGraph checkpoints | Parthenos — durable graph-state/checkpoint store | direct (SDK) |
| **Plan / cognition (L4-adjacent)** | LangGraph | Parthenos `parthenos/` — graph/state executor for planning pipelines | direct (SDK/server) |
| | CrewAI (flows/planning) | Parthenos — wrap a Crew process as a planning actor | adapter needed |
| | Hermes (skills/planner) | Parthenos — use skill system as procedural planning | adapter needed |
| **Execute / tool (verticals)** | Hermes Agent | Parthenos `adapters.py` — as an execute actor via MCP/CLI/HTTP | direct |
| | OpenHands | Parthenos `adapters.py` — as a coding/execute actor via SDK/HTTP(+ACP) | direct |
| | AutoGPT | not now — Polyform Shield + beta platform; revisit if platform stabilizes | not now |
| | CrewAI | Parthenos `adapters.py` — wrapped crew process as execute actor | adapter needed |
| **Communicate / efferent** | Hermes gateway / OpenClaw channels | Athena — outbound efferent module (TTS/notify/Telegram-style delivery) | adapter needed |
| | Khoj (email/WhatsApp automations) | Athena — scheduled outbound delivery | adapter needed |
| **Supervise / orchestrate (L4)** | A2A (protocol) — **no actor adopted** | Parthenos L4 → fan-out to execute actors over A2A | direct (protocol) |
| | LangGraph (if graph control ever wanted) | Parthenos — optional orchestration backend under L4 | direct (SDK) |
| | CrewAI | not now — L4 supervision stays in-house by design; CrewAI at most a subordinate planner | not now |
| **Identity / personalization (cross)** | Hermes (Honcho user modeling, profiles) | Cross-cutting → Parthenos identity/profile store, consumed by Athena | adapter needed |
| | OpenClaw (SOUL.md persona) | not now — security posture; persona file is a useful pattern to borrow, not to adopt | not now |

---

## 3. Gap list (no good OSS actor among surveyed)

1. **Perceive — wearable/ambient input actor.** None of the surveyed candidates ingest ambient sensors (position, physiological, spatial/temporal context) — their "perception" is chat/doc inbound. Athena remains the in-house sense owner; an external OSS wearable/sensor wrapper would be novel net-new, not a surveyed candidate.
2. **Identity/tonal personalization actor.** Only partial coverage: Hermes' Honcho user modeling is user-*memory*, not a dedicated tonal/voice/identity adapter. No surveyed OSS actor ships a ready tonal-personalization interface → build in-house vs borrow Hermes' Honcho.
3. **Dedicated supervise/orchestrate actor.** Deliberately unfilled — L4 supervision stays in-house by design (& personal-agents-actors.md §1). A2A is the protocol bridge to subordinate actors, not an actor itself. CrewAI is the closest role-based candidate but is rejected as a supervisor (kept only as subordinate planner, adapter needed).
4. **AGPL-constrained memory substrate** (Khoj) — a license gap, not a capability gap: if Parthenos stays permissive-only, Khoj is out unless we commit to AGPL. (source: https://github.com/khoj-ai/khoj — AGPL-3.0)

**Bottom line:** the surveyed set gives strong, direct-fit actors for **Execute** (Hermes, OpenHands) and **Orchestrate/Plan** (LangGraph, A2A protocol); Hermes uniquely covers **Memory + Skills + Communicate + Identity**. The two genuine gaps are **Perceive/ambient sensing** and **dedicated Identity/tonal adaptation** — both stay in-house (Athena / Parthenos) for now, with A2A as the L4 interop backbone.
