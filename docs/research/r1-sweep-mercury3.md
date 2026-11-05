# R1 Landscape Sweep — Open-Source Personal Agents / Agent Toolkits (validated)

> Research date: 2026-11-04. Purpose: candidates for **actors** in the Parthenos pipeline (stable interface: CLI / MCP / ACP / SDK / HTTP). All claims carry inline source URLs. Star counts are live GitHub figures at research time and move fast.

---

## Candidate matrix (snapshot)

| # | Candidate | Repo | License | Stars | Latest release (date) | Interface | Deploy mode | Verdict (actor) |
|---|-----------|------|---------|-------|------------------------|-----------|-------------|------------------|
| 1 | **OpenHands** | github.com/OpenHands/OpenHands | MIT (+ enterprise/ source-available) | ~83k–88k | v1.9.0 (2026-08-03) | CLI, SDK, HTTP agent-server, ACP, GUI | Self-hosted (Docker/K8s) + cloud | ✅ good fit |
| 2 | **AutoGPT** | github.com/Significant-Gravitas/AutoGPT | MIT core; **Polyform Shield** for `autogpt_platform/` | ~188k | autogpt-platform-beta-v0.11.0 (2026-11-04) | Platform UI, Python SDK, headless, MCP | Self-hosted (Docker) or cloud | ⚠️ needs verification |
| 3 | **CrewAI** | github.com/crewAIInc/crewAI | MIT | ~60k | v1.15.34 (2026-11-01) | Python library, CLI (`crewai run`), MCP tools | Library (pip) + cloud AMP | ⚠️ needs verification |
| 4 | **LangGraph / LangChain** | github.com/langchain-ai/langgraph | MIT | ~44k (LangChain ~149k) | langgraph 1.2.19 (2026-10-30) | Python/JS SDK, `langgraph` CLI, server (HTTP), MCP | Library + deployable server | ✅ good fit (orchestration) |
| 5 | **Khoj** | github.com/khoj-ai/khoj | AGPL-3.0 | ~38k | 2.0.0-beta.28 (2026-03-26) | App/web, Obsidian/Emacs/WhatsApp clients, MCP | Self-hosted service (Docker/pip); cloud sunset | ⚠️ needs verification |
| 6 | **OpenClaw** | github.com/openclaw/openclaw | MIT | ~353k–374k (verify) | v2026.10.x (2026-10) | CLI, Gateway, Web Control UI, native apps, channels | Self-hosted gateway (npm/Docker) | ⚠️ needs verification (security) |
| 7 | **Hermes Agent** | github.com/NousResearch/hermes-agent | MIT | ~260k | v0.22.7 (2026-11-03) | CLI/TUI, Desktop, web dashboard, **ACP server**, **MCP**, gateway, OpenAI proxy | Self-hosted (small footprint) + cloud | ✅ good fit |

---

## Per-candidate detail

### 1. OpenHands
- **One-line:** Open-source AI-driven software-development agent (autonomous coding agent) with CLI, SDK, and server.
- **Repo:** https://github.com/OpenHands/OpenHands — **License:** MIT; `enterprise/` dir is source-available, paid beyond 1 month (https://github.com/OpenHands/OpenHands/blob/main/LICENSE).
- **Maturity:** ~83k stars (RepositoryStats, 2026-08: 83,209; https://repositorystats.com/openhands/openhands); latest release v1.9.0 2026-08-03 (ibid). Very active (~7.9k commits, 128 releases).
- **Interface:** CLI, Python SDK (`software-agent-sdk`), agent-server HTTP API, frontend (Agent Canvas); repo contains `examples/acp-docker/` → ACP support (https://github.com/openhands/OpenHands).
- **Deploy:** self-hosted Docker/Helm(K8s) or OpenHands Cloud; runs as a service.
- **Caveats:** agent has full filesystem/network access unless sandboxed; enterprise features gated; server is a heavy Docker footprint.
- **Verdict:** ✅ good fit — stable SDK + HTTP agent-server is a clean actor boundary.

### 2. AutoGPT
- **One-line:** Platform for building/deploying/managing continuous autonomous agents (visual builder + classic agent).
- **Repo:** https://github.com/Significant-Gravitas/AutoGPT — **License:** MIT for classic/Forge/agbenchmark/GUI; **Polyform Shield** for `autogpt_platform/` (in-development platform) (http://github.com/significant-gravitas/autogpt).
- **Maturity:** ~188k stars (GitGenius 2026-11-02: 187,878); frequent releases, latest autogpt-platform-beta-v0.11.0 2026-11-04 (https://newreleases.io/project/github/Significant-Gravitas/AutoGPT/release/autogpt-platform-beta-v0.11.0); platform still **beta**.
- **Interface:** Platform UI, Python SDK, headless execution API; MCP server/tool support.
- **Deploy:** self-hosted via Docker Compose, or AutoGPT Cloud (closed beta waitlist).
- **Caveats:** Polyform Shield is non-OSI + restricts commercial use → review for a commercial pipeline; 41 CVEs reported (releasealert.dev); platform API unstable (beta).
- **Verdict:** ⚠️ needs verification — UI/platform-centric, licensing friction, not primarily an embeddable SDK actor.

### 3. CrewAI
- **One-line:** Python framework for orchestrating role-playing multi-agent crews/teams.
- **Repo:** https://github.com/crewAIInc/crewAI — **License:** MIT.
- **Maturity:** ~60k stars (GitGenius 2026-11-02: 60,394); very active, latest v1.15.34 2026-11-01 (https://github.com/crewAIInc/crewAI/releases/tag/1.15.34).
- **Interface:** Python library/API, CLI (`crewai run`), MCP tools (agents can call MCP servers), CrewAI AMP cloud platform.
- **Deploy:** library dependency (pip) or CrewAI Cloud/AMP; self-hostable as code.
- **Caveats:** framework not a long-running service — you host your own Crew process; telemetry on by default; PyPI dependency chain (LiteLLM) is broad.
- **Verdict:** ⚠️ needs verification — good as an orchestration library, but "actor" requires you to wrap it in your own service; memory model is crew-internal.

### 4. LangGraph / LangChain
- **One-line:** Low-level framework for building stateful, long-running, graph-based agents (LangChain = higher-level ecosystem).
- **Repo:** https://github.com/langchain-ai/langgraph — **License:** MIT (API: MIT).
- **Maturity:** ~44k stars (API, 2026-11-03: 44,350); latest langgraph 1.2.19 2026-10-30; weekly releases; ~294 contributors (https://repositoryradar.dev/repo/langchain-ai/langgraph).
- **Interface:** Python & JS/TS SDK; `langgraph` CLI (dev server); LangGraph Platform HTTP server (RemoteGraph); MCP server support; checkpoints/persistence.
- **Deploy:** library; deployable as a service via LangGraph Platform (self-hosted or cloud).
- **Caveats:** SDK is code, not an agent binary — you build the agent; adds an orchestration dependency rather than an out-of-box actor.
- **Verdict:** ✅ good fit — the most robust *orchestration* actor/SDK if Parthenos wants graph-state control; not a turnkey assistant.

### 5. Khoj
- **One-line:** Self-hostable personal AI "second brain": RAG over your docs + web, custom agents, automations.
- **Repo:** https://github.com/khoj-ai/khoj — **License:** AGPL-3.0 (copyleft, network-use clause).
- **Maturity:** ~38k stars (API 2026-11-02: 37,946); latest release 2.0.0-beta.28 (2026-03-26); active commits.
- **Interface:** web app, desktop/phone, Obsidian/Emacs, WhatsApp; MCP integration; REST API.
- **Deploy:** self-hosted service (Docker compose / `pip install khoj[local]`); **Khoj Cloud sunset 2026-04-15** → self-host is now the only path (https://www.promptquorum.com/power-local-llm/khoj-ai-second-brain-review).
- **Caveats:** AGPL (must open-source modifications if offered as network service); beta API churn between 2.0.x releases; heavier server (RAG index).
- **Verdict:** ⚠️ needs verification — strong personal-assistant actor but AGPL + beta API; fits if Parthenos can commit to AGPL or self-host.

### 6. OpenClaw
- **One-line:** Self-hosted personal AI assistant gateway that connects 20+ messaging channels to an agent (multi-agent routing, skills).
- **Repo:** https://github.com/openclaw/openclaw — **License:** MIT.
- **Maturity:** stars reported ~353k (GitHub search 2026-10) to ~374k; created 2025-11-24 with ~30–52k commits — **anomalously fast growth; treat star count as unverified**. Actively maintained 2026 (release notes through v2026.10.x: https://docs.openclaw.ai/releases).
- **Interface:** CLI (`openclaw`), Gateway process, Web Control UI, macOS/iOS/Android native apps, channel plugins (Discord/Telegram/Slack/WhatsApp/iMessage/etc), plugin SDK.
- **Deploy:** self-hosted gateway (npm/Docker) on your hardware; run as personal single-operator or team.
- **Caveats (security/trust):** ⚠️ **significant.** Sandboxing and exec-approval **off by default**; agent runs shell commands on host as your user (https://clawdocs.org/security/overview). Incidents: **one-click RCE CVE-2026-25253** patched early 2026; **Moltbook breach exposed ~1.5M agent API tokens**; hundreds of malicious skills found on ClawHub (https://clawdocs.org/security/overview). 647 public advisories (docs.openclaw.ai/start/why-openclaw). Trust model is single-operator, not multi-tenant; treat inbound messages as untrusted input.
- **Verdict:** ⚠️ needs verification — powerful personal actor but current security posture (default-unsandboxed, breach history) makes it risky as an untrusted pipeline actor without hardening.

### 7. Hermes Agent (extra attention)
- **One-line:** Self-improving AI agent from Nous Research with an explicit memory + skill-learning loop.
- **Repo:** https://github.com/NousResearch/hermes-agent — **License:** MIT (API: MIT).
- **Maturity:** **~260k stars** (API 2026-11-04: 260,415; created 2025-07-22 — very rapid growth, verify); latest release **v0.22.7** 2026-11-03 (API: https://api.github.com/repos/NousResearch/hermes-agent/releases/latest); ~582 commits/release-window.
- **Version/interface:** v0.22.7 (stable line; v0.23.0 upcoming). Interfaces: **CLI + TUI** (`hermes` / `hermes --tui`), native **Desktop app**, web dashboard, **messaging gateway** (Telegram/Discord/Slack/WhatsApp/Signal/Teams/iMessage/Matrix/Email), **an ACP server for IDEs** (VS Code / Zed / JetBrains), **MCP** (`hermes mcp serve`, `mcp_servers` config), and an **OpenAI-compatible proxy** (`hermes proxy`) (https://github.com/NousResearch/hermes-agent/blob/main/skills/autonomous-ai-agents/hermes-agent/SKILL.md).
- **Memory + skill-learning loop (confirmed):** closed learning loop — agent-curated memory with periodic nudges, autonomous skill creation after complex tasks, skills self-improve during use, FTS5 cross-session recall with LLM summarization, Honcho dialectic user modeling; `/learn` turns sources into skills; `skill_manage` tool lets the agent create/update/delete its own skills; write-approval gates (https://hermes-agent.nousresearch.com/docs/user-guide/features/skills).
- **Self-hosted footprint:** small — "run it on a $5 VPS"; 6 terminal backends (local, Docker, SSH, Daytona, Modal, Vercel Sandbox); serverless persistence option; config in `~/.hermes/config.yaml` (https://github.com/nousresearch/hermes-agent).
- **Caveats:** very young/fast-growing (52k+ open issues in API feed — triage load); beta-grade releases; crowdsourced skill hub (agentskills.io) is an untrusted-code vector — vet skills; imports from OpenClaw can bring secrets.
- **Verdict:** ✅ good fit — the candidate with the *most native fit* for Parthenos (memory + skills meta-loop, MCP + ACP + CLI/HTTP, tiny footprint). Needs verification pins for source/version provenance given age and star velocity.

---

## Interop protocol layer (one paragraph each)

**MCP — Model Context Protocol** (Anthropic, Nov 2024; now under the Agentic AI Foundation / Linux Foundation, Dec 2025). Solves: a *standard interface between an AI agent/host and external tools, data, resources* (JSON-RPC 2.0; servers expose resources/prompts/tools), so agents don't reinvent tool-calling per vendor. Of the candidates, **MCP is the near-universal actor interface**: AutoGPT, CrewAI, LangGraph, Khoj, Hermes (`hermes mcp serve`/`mcp_servers`), and OpenClaw (plugins) all integrate MCP; OpenHands also consumes MCP tools. MCP alone does not cover agent-to-agent delegation or client/editor coupling. (Sources: https://www.infoworld.com/article/4007686/a-developers-guide-to-ai-protocols-mcp-a2a-and-acp.html; https://a2a-protocol.org/dev/topics/a2a-and-mcp.)

**ACP — Agent Client Protocol** (Zed Industries, Aug 2025, with JetBrains). Solves: *standardizing communication between a client (code editor/IDE) and an agent* — analogous to LSP — so any ACP agent works in any ACP editor, for local and remote/IDE-hosted scenarios; JSON representations reuse MCP (https://agentclientprotocol.com/). ⚠️ **Naming ambiguity:** IBM's earlier **Agent Communication Protocol (ACP)** (Mar 2025, BeAI) is **deprecated and absorbed into A2A** — do not build on it (https://crystl.dev/blog/agent-communication-protocols). Which candidates expose ACP (Zed's): **Hermes** ships an ACP server for IDEs; **OpenHands** ships ACP examples (docker). Most others do not (they are MCP-first).
**A2A — Agent2Agent Protocol** (Google, Apr 2025; now v1.0 under Linux Foundation). Solves: *agent-to-agent delegation and collaboration across boundaries* — task lifecycle, discovery via AgentCard (`/.well-known/agent-card.json`), streaming/callback for long-running tasks; the "another agent" layer (https://a2a-protocol.org; https://crystl.dev/blog/agent-communication-protocols). None of the seven candidates *expose an A2A server* by default (they are MCP-first); A2A is the emerging peer-to-peer layer above them.
**ANP — Agent Network Protocol**. Solves: *decentralized agent identity, capability discovery and selective/context-aware sharing* over HTTP(S), with fine-grained control over what an agent exposes to other agents; younger/less standardized than MCP/A2A, circulated in W3C agent-protocol discussions and not yet a shipping interface on these candidates (Sources: https://lists.w3.org/Archives/Public/public-agentprotocol/2025Aug/att-0012/Agent_Protocol_Comparison_MCP__A2A__and_ANP.pdf; https://agentsurface.dev/docs/protocols/comparison).

### Bottom line for Parthenos
- The cleanest **actor interface** across the field is **MCP** (wide, stable, and everything here speaks it); **ACP** only matters for editor-hosted agents (Hermes, OpenHands).
- **Good-fit actors (stable interface, embeddable):** Hermes Agent (MCP+ACP+CLI+HTTP, small footprint, native memory/skills loop), OpenHands (SDK/HTTP/ACP), LangGraph (SDK/server for orchestration).
- **Needs verification:** OpenClaw (security posture), AutoGPT & Khoj (licensing/beta), CrewAI (needs your own service wrapper).
- **Protocol-only:** MCP/A2A/ACP/ANP are layers, not actors.
