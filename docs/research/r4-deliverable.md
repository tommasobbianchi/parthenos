# R4 — Final Deliverable: Shortlist & Integration Sketch (Parthenos/Athena)

> Research date: 2026-11-04. Synthesizes R1 (validated matrix), R2 (role classification), R3 (interop/feasibility) — see same directory. No new claims beyond R1–R3; where a fact is not already sourced there it is marked. Target host: nativedev (<nativedev-tailscale-ip>, Tailscale).

---

## 1. Executive summary

The survey (R1–R3) found that **three open-source agents are directly wire-ready as pipeline actors on nativedev**: **Hermes Agent** (execute + memory + communicate + identity; MCP client+server, CLI, ACP; small footprint), **LangGraph** (orchestration/plan backend; `langgraph dev` server), and **OpenHands** (on-demand coding execute actor; HTTP/SDK/ACP, but heavy). **Khoj** (memory substrate, REST/MCP) and **CrewAI** (wrapped role-based planner) are viable but need an S8 adapter and a license sign-off (Khoj AGPL). The **protocol backbone is MCP**: Parthenos should expose itself as an MCP server on a loopback port so every actor reaches it uniformly; **A2A** (v1.0) is reserved as the future L4→actor fan-out protocol; **ACP** matters only for IDE-hosted agents. **Stays in-house** by design: perceive/ambient sensing, identity/tonal adaptation, and L4 supervision. Recommended first-wire order: Parthenos-as-MCP-server → Hermes → LangGraph → OpenHands (on-demand), then evaluate Khoj/CrewAI post-license-decision.

---

## 2. Shortlist matrix (decision-ready)

| Actor | Role fit (R2) | Interface (R3) | License | Footprint @ nativedev | Wiring verdict |
|---|---|---|---|---|---|
| **Hermes Agent** | Execute, Memory, Communicate, Identity | MCP client+server, CLI/TUI, ACP, `hermes proxy`, `mcp_servers` config | MIT | small (source install; $5-VPS-class) | ✅ **direct** |
| **OpenHands** | Execute (coding), Supervise(partial) | HTTP agent-server + SDK + ACP; `X-Session-API-Key` | MIT (+enterprise dir) | heavy (K8s pod+PVC per conversation) → on-demand | ✅ **direct** (on-demand only) |
| **LangGraph / LangChain** | Orchestrate, Plan, Memory(checkpoints) | `langgraph dev` (loopback 2024), SDK, Agent Server; MCP adapter | MIT | small–moderate (`dev` in-memory; `up`+PG) | ✅ **direct** |
| **Khoj** | Memory, Perceive(doc), Communicate, Execute | HTTP/REST + web (42110) + MCP | AGPL-3.0 | moderate (4–8 GB) | ⚠️ **adapter needed** (AGPL sign-off) |
| **CrewAI** | Plan, Orchestrate(subordinate), Execute | Python lib + `crewai run` CLI | MIT | trivial (process) | ⚠️ **adapter needed** (wrap; disable telemetry) |
| ~~AutoGPT~~ | Execute/Platform | UI/SDK/MCP | MIT + **Polyform Shield** | Docker | ❌ **not now** (licensing + beta) |
| ~~OpenClaw~~ | full agent platform | CLI/Gateway/apps | MIT | Docker/npm | ❌ **not now** (security posture) |
| **MCP** (protocol) | backbone: Execute+Memory | stdio + Streamable HTTP; JSON-RPC 2.0 | open standard | — | backbone (build Parthenos as MCP server) |
| **A2A** (protocol) | L4 fan-out | AgentCard + task lifecycle (v1.0) | open standard | — | reserved (in-house L4 → actors) |
| **ACP** (protocol) | IDE-hosted agents only | Zed's Agent Client Protocol | open standard | — | only for editor hosting |

---

## 3. Integration sketch — reference pipeline on nativedev

```text
                         ┌──────────────────────────────────────────────┐
                         │              ATHENA (awareness shell)        │
                         │  CLI contract `athena` — never acts itself    │
                         │  sense/efferent modules (in-house)            │
                         └───────────────▲──────────────────┬───────────┘
                                         │ athena CLI       │ awareness state
                         ┌───────────────┴──────────────────▼───────────┐
                         │        PARTHENOS (metacognitive layer)       │
                         │  parthenos/ modules · L4 supervision (in-house│
                         │  S8 adapters.py · memory · plan · identity    │
                         │  ── EXPOSED AS AN MCP SERVER ──              │
                         │  http://127.0.0.1:8766/mcp  (loopback)       │
                         └───────┬─────────────────┬──────────────┬─────┘
                                 │                 │              │
            MCP (client)         │  MCP (client)   │ HTTP/SDK     │ MCP/REST (adapter)
                                 ▼                 ▼              ▼
    ┌──────────────────┐  ┌──────────────┐  ┌─────────────┐  ┌──────────────┐
    │ HERMES Agent     │  │ LANGGRAPH    │  │ OPENHANDS   │  │ KHOJ (opt)  │
    │ MCP+ACP+CLI,    │  │ langgraph dev │  │ server+SDK  │  │ memory substr │
    │ small resident   │  │ orchestration │  │ on-demand   │  │ + CrewAI (opt)│
    └──────────────────┘  └──────────────┘  └─────────────┘  └──────────────┘
         ▲        ▲              ▲               ▲
         │        │              │               │
    A2A (reserved, L4 fan-out)   │               │
         │                        │               │
    ┌──────────────────────────────────────────────────────────────┐
    │  PROTOCOL BACKBONE (all loopback → Tailscale <nativedev-tailscale-ip>) │
    │  MCP: Parthenos-as-server; actors as MCP clients              │
    │  A2A: v1.0, reserved for L4→actor fan-out (in-house build)    │
    │  ACP: only for IDE-hosted agents (Hermes/OpenHands)           │
    └──────────────────────────────────────────────────────────────┘
```

**Arrow/interface map (from R3):**
- **Athena ↔ Parthenos**: `athena` CLI contract (awareness state, sense streams) — in-house modules.
- **Parthenos → Hermes**: MCP client (`mcp_servers` → `url: http://127.0.0.1:8766/mcp`) **or** direct `hermes` CLI/HTTP. Parthenos = MCP `host/client`, Hermes = actor. *(Alternatively Hermes' `hermes mcp serve` makes Hermes the server; pick one owner per direction.)*
- **Parthenos → LangGraph**: Agent Server over HTTP (Python `Client(apiUrl="http://localhost:2024")`) — orchestration/plan backend.
- **Parthenos → OpenHands**: HTTP agent-server + SDK on demand (`X-Session-API-Key`), heavy → spawn per task, teardown after.
- **Parthenos → Khoj / CrewAI**: **S8 adapter** in `adapters.py` (MCP/REST for Khoj; wrap `crewai run` for CrewAI); Khoj behind AGPL decision.
- **Parthenos as MCP server**: expose `parthenos/` capabilities (memory read/write, plan, event emit) on `127.0.0.1:8766/mcp` — the uniform interop point.

*Note:* the L1–L4 layer numbering follows Parthenos' own `parthenos/` module layout; only **L4 supervision is pinned here** (in-house, per R2) — lower-layer numbering is not asserted.

---

## 4. Recommendations & next steps

**Wire first (order):**
1. **Parthenos as an MCP server** on `127.0.0.1:8766/mcp` (backbone) — smallest change, unlocks everything.
2. **Hermes Agent** — direct MCP client; wire memory/skills loop as an execute+memory actor.
3. **LangGraph** — run `langgraph dev`/`up` as orchestration backend behind L4.
4. **OpenHands** — on-demand execute stub via HTTP/SDK, spawned per task.

**Must change before going live (R3 security list):**
- Hermes: enable command-approval; whitelist MCP tools; vet skills-hub installs; tokens stay 0600.
- OpenHands: sandbox + load a command-policy (`PreToolUse`) hook; keep agent-server off the public tailnet (loopback/Tailscale only).
- LangGraph: keep loopback bind; add app-level auth on the server.
- Khoj: leave Operator mode OFF (`KHOJ_OPERATOR_ENABLED` unset), lock `/server/admin`; CrewAI: disable telemetry.

**Open decisions:**
- **Khoj AGPL sign-off** — if Parthenos must stay permissive-only, drop Khoj and use Hermes' memory + LangGraph checkpoints as the substrate instead.
- **Build an A2A endpoint?** — recommended only when L4 actually needs to fan out to multiple remote actors (cross-domain auth not yet standardized; plan for task-level auth).
- **ACP** — adopt only if an IDE must host Hermes/OpenHands; not needed for pipeline actors.

**Stays in-house (by design, R2 gaps):** perceive/ambient sensing (Athena), identity/tonal adaptation (Hermes' Honcho is user-memory, not tonal), and L4 supervision (Parthenos core).

> **Bottom line:** ship Parthenos-as-MCP-server + Hermes + LangGraph (all direct, small) as the v1 actor set; add OpenHands on-demand; revisit Khoj/CrewAI only after the tuplePL/telemetry decisions; keep perceive/identity/L4 in-house.
