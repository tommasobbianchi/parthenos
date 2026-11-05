# Research: Personal Agents on GitHub as Pipeline Actors

> Status: epic plan v0.1 (2026-11-04). Owner: orchestrator. Tracked in bd epic
> (label `research,parthenos,athena,personal-agents`). This document is the plan
> and the evolving deliverable container; bd issues reference it.

## 0. Context (Athena analysis, 2026-11-04)

Athena (`~/projects/athena`) is the personal-assistance shell for Tommaso.
It holds awareness (presence, sleep, tone, spatial/temporal grounding, intentions,
project status, sense streams) and exposes it through a stable `athena` CLI that
verticals call. It never acts itself.

Research question: **which open-source personal agents / agent-toolkits on GitHub
can act as actors in our pipeline** (Athena awareness shell + Parthenos
metacognitive layer + verticals)? "Actor" = a tool/agent with a stable interface
(CLI, MCP, ACP, SDK, HTTP) that can play a pipeline role, not a monolith to adopt.

## 1. Actor taxonomy (working draft)

| Role | Pipeline slot | Examples to screen |
|---|---|---|
| Perceive / senses | input, ambient | vision/wearables wrappers, HA sensors, TG inbox |
| Memory | substrate | Letta, Mem0, Zep, Cognee (already covered in S0) |
| Plan / cognition | L4-adjacent | task managers, planners, Eisenhower sorters |
| Execute / tool | verticals | opencode, claude-code forks, agy (Antigravity CLI), deepseek-tui, OpenHands |
| Communicate / efferent | output | Telegram bots, TTS, notify, relay daemons |
| Supervise / orchestrate | L4 | multi-agent frameworks; MCP/ACP hosts |
| Identity / personalization | cross | profile/tonal adapters |

## 2. Phases (bd children under the epic)

- **R1 — Landscape survey**: enumerate OSS personal-agent projects/toolkits on
  GitHub (2026): name, repo, maturity (stars/release), license, interface
  (CLI/MCP/ACP/SDK/HTTP), deploy mode (self-hosted, service, library).
- **R2 — Actor role classification**: map each candidate onto the taxonomy above;
  mark which can plug into Athena + Parthenos as actors; identify gaps
  (roles with no good OSS actor).
- **R3 — Interop & feasibility**: MCP/ACP/CLI contract details, self-hosted
  footprint, cost, security boundaries, Tailscale constraints; shortlist that
  can be wired into the reference pipeline without rewriting.
- **R4 — Deliverable + recommendations**: final report in this file; a shortlist
  matrix; integration sketch showing which actors replace/extend our S8 adapters
  and which become Athena modules.

## 3. Method

- Sources: GitHub search/repos, official docs, context7 for library APIs.
- Evidence: every claim carries repo URL + date; maturity from stars/release dates.
- Deliverable discipline: same as S0 — matrix + verdicts, no hype.

## 4. Constraints

- Only tools that can run self-hosted on nativedev/Tailscale are eligible for
  "actor in our pipeline" status; cloud-only services are noted but not shortlisted.
- License must be permissive/OSI for core actors (MIT/Apache/BSD), or clearly
  separable service components.
- Interop hooks: prefer MCP/ACP/CLI over SDK-only; SDK-only acceptable when thin.

## 5. Initial sweep (R1 draft, 2026-11-04)

First-pass landscape (web, Nov 2026). Each row = candidate actor; verify + deepen
in R1 before any verdict.

| Candidate | Role fit | Interface | License | Notes |
|---|---|---|---|---|
| OpenHands (OpenHands/openhands) | execute/tool (coding agents) | CLI, API, self-hosted canvas | MIT (verify) | Always-on engineering agents; agent canvas control center |
| AutoGPT (significant-gravitas) | personal automation, autonomous loop | CLI/GUI | MIT (verify) | Most-starred agent repo; self-hosted always-on |
| Hermes Agent (NousResearch/hermes-agent) | execute/tool + memory + skill learning | CLI, installers, messaging-platform integrations | MIT | Self-improving loop (creates skills from experience) — the 2026 breakout OSS personal agent (~200k★); positioned as the OpenClaw alternative; built-in learning loop parallels our L4/lucid-dreaming concepts |
| CrewAI | orchestrate (role-based crews) | Python SDK | MIT (verify) | Roles = ready-made actor model for pipeline roles |
| LangGraph (LangChain) | orchestrate/plan (state graphs) | Python SDK | MIT | Production default in 2026; ~40.6k★ |
| Khoj (khoj-ai/khoj) | memory + personal assistant shell | HTTP API, apps | AGPL-3.0 | Self-hosted second brain, one-user personal AI; note AGPL |
| OpenClaw | full personal agent platform | ? | ? | Appears in 2026 OSS lists (~280k★ per one source) — **verify**; we abandoned a prior `~/projects/openclaw` fork over security issues |
| MCP / ACP / A2A / ANP | interop layer (all roles) | protocol | open standards | MCP=model↔tool, ACP=client↔agent, A2A/ANP=agent↔agent; R3 hinges on these |

Open questions for R1/R3: which of these expose MCP/ACP servers vs SDK-only;
self-hosted resource footprint on nativedev; AGPL implications for Khoj actor use;
OpenClaw identity/trust (verify security posture before any integration); Hermes
Agent's external surface (does it expose MCP/ACP or only its CLI/installer? its
skill-learning loop vs our own L4/dream calibration — overlap or complement).

### R1 verification (Mercury 3 sweep, 2026-11-04)

Full validated matrix + per-candidate detail + protocol layer: see
`r1-sweep-mercury3.md` (same directory). Verified verdicts:

| Candidate | License | Verdict |
|---|---|---|
| Hermes Agent | MIT | ✅ good fit (MCP+ACP+CLI+HTTP, small footprint, native memory/skills loop) |
| OpenHands | MIT | ✅ good fit (SDK/HTTP/ACP) |
| LangGraph/LangChain | MIT | ✅ good fit (orchestration SDK/server) |
| AutoGPT | MIT + Polyform Shield | ⚠️ needs verification (licensing, beta platform) |
| CrewAI | MIT | ⚠️ needs verification (needs own service wrapper) |
| Khoj | AGPL-3.0 | ⚠️ needs verification (AGPL, cloud sunset) |
| OpenClaw | MIT | ⚠️ needs verification (security: sandbox off by default, CVE-2026-25253, Moltbook breach) |

Protocol layer: **MCP** = near-universal actor interface; **ACP** (Zed) only for
editor-hosted agents; **A2A** (v1.0, Linux Foundation) = agent-to-agent, none of the
candidates expose it by default; **ANP** least mature. IBM's older ACP is deprecated
(absorbed into A2A) — do not target it.

### R2 verification (Mercury 3 sweep, 2026-11-04)

Full candidate→roles matrix + plug-in mapping + gap list: see
`r2-classification.md` (same directory). Headline verdicts:
- **Direct-fit actors:** Execute → Hermes (MCP/CLI/HTTP) + OpenHands (SDK/HTTP/ACP);
  Orchestrate/Plan → LangGraph (SDK/server) + A2A as L4 fan-out protocol.
- **Adapter needed:** Khoj + Hermes memory as memory substrates; CrewAI as wrapped
  planner/execute actor; gateway inbound/outbound as Athena sense/efferent modules.
- **Not now:** AutoGPT (Polyform Shield + beta); OpenClaw (security); CrewAI as a
  supervisor (L4 stays in-house by design).
- **Gaps:** ambient/wearable Perceive actor; dedicated Identity/tonal adapter (Hermes'
  Honcho is user-memory, not tonal adaptation) — both stay in-house. Khoj AGPL is a
  license decision point for permissive-only pipeline.

### R4 verification (Mercury 3 sweep, 2026-11-04) — epic deliverable

Final report + decision-ready shortlist + integration sketch: see `r4-deliverable.md`
(same directory). v1 actor set: **Parthenos-as-MCP-server** (loopback `127.0.0.1:8766/mcp`)
+ **Hermes** (direct) + **LangGraph** (direct) + **OpenHands** (on-demand). Adapter-dependent:
Khoj (AGPL sign-off) + CrewAI. Reserved: A2A for L4 fan-out; ACP only IDE-hosted. In-house:
perceive/ambient, identity/tonal, L4 supervision.

> Note (implemented 2026-11-04): on nativedev the MCP endpoint runs on **127.0.0.1:8766**
> because 8765 is occupied by the unrelated `aipmo` service. Port is configurable via
> `bin/parthenos-mcp --port`.

### R3 verification (Mercury 3 sweep, 2026-11-04)

Full interface contracts + nativedev footprint + security must-changes + protocol wire
facts: see `r3-interop.md` (same directory). Wiring verdicts:
- **Direct (wire-ready on nativedev, loopback + Tailscale only):** Hermes Agent (MCP
  client+server, CLI, ACP — small footprint), LangGraph (`langgraph dev`, loopback 2024),
  OpenHands (HTTP agent-server + SDK, but heavy → on-demand execute).
- **Adapter needed:** Khoj (REST/MCP, ~4–8 GB, AGPL sign-off required), CrewAI
  (`crewai run`, disable telemetry, wrap behind S8 adapter).
- **Protocol backbone:** Parthenos should expose itself as an **MCP server** on a loopback
  port (e.g. `127.0.0.1:8766/mcp`); **A2A** v1.0 is the future L4→actor fan-out (AgentCard
  + task lifecycle; cross-domain auth not yet standardized); **ACP** only for IDE-hosted
  agents. Security: sandbox/approvals on by default before any actor goes live.
