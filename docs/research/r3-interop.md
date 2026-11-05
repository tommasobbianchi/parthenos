# R3 — Interop & Feasibility (shortlist wiring for Parthenos/Athena)

> Research date: 2026-11-04. Inputs: R1 matrix (`r1-sweep-mercury3.md`), R2 classification (`r2-classification.md`), epic plan (`personal-agents-actors.md`). Target host: **nativedev** (<nativedev-tailscale-ip>, always-on, Tailscale). Every endpoint/flag below was verified against official docs/repos; where a specific flag could not be verified it is marked **unverified** rather than guessed.

---

## 1. Hermes Agent (execute · memory · communicate · identity — R2 ✅)

**Contract — entry points (official docs):**
- CLI/TUI: `hermes` (classic) / `hermes --tui`; `hermes gateway run` (messaging); `hermes proxy` (OpenAI-compatible local endpoint); `hermes mcp …`; `hermes skills`; `hermes import-agent`; `hermes cron`. Config in `~/.hermes/config.yaml`; data/state in `~/.hermes/` (`~/.local/bin/hermes` launcher) — https://hermes-agent.nousresearch.com/docs/getting-started/installation.
- **MCP client** (`mcp_servers` in config): stdio (`command`/`args`/`env`) or HTTP (`url`/`headers`), SSE, OAuth 2.1/PKCE/DCR, mTLS (`client_cert`/`client_key`). Tools registered as `mcp_<server>_<tool>`; per-server `tools.include/exclude` filtering. Tokens cached at `~/.hermes/mcp-tokens/<server>.json` (mode 0600). `hermes mcp serve` exposes Hermes *as* an MCP server (an actor endpoint) — https://hermes-agent.nousresearch.com/docs/user-guide/features/mcp.
- ACP server for IDEs (VS Code/Zed/JetBrains) — R1 source (SKILL.md).

Minimal wiring snippet:
```yaml
# ~/.hermes/config.yaml
mcp_servers:
  parthenos:
    url: "http://127.0.0.1:8766/mcp"      # our Parthenos MCP endpoint
    headers: { Authorization: "Bearer <token>" }
    tools: { include: [emit_memory, recall, plan] }
```
```bash
hermes chat                      # run, target model via `hermes model`
```

**Footprint:** source installer → `~/.hermes/hermes-agent/` (Python 3.14 + pinned Node/Chromium); small enough for a $5-VPS-class box enR1). No D required for core; Docker image exists (`/opt/hermes/`).

**Security:** stdio env is filtered (no blind env passthrough); MCP tool filtering = config-level exposure control; `memory.write_approval` / skill guard gates exist; MCP tokens 0600; OAuth `iss` checks (RFC 9207). **Change before use:** enable command-approval, restrict toolset/whitelist MCP tools, vet skills-hub installs (agentskills.io is untrusted-code surface). No known Hermes CVE found in R1 (mark: none observed, not a clean bill).

**Wiring verdict:** ✅ **direct** — MCP + CLI/HTTP + ACP, small footprint.

---

## 2. OpenHands (execute — R2 ✅)

**Contract — entry points (official docs):**
- Cloud/serve API (`https://app.all-hands.dev/api/v1/…` or self-hosted): auth header `X-Session-API-Key: <OH_API_KEY>`; `POST /api/v1/app-conversations/stream-start` (creates conversation+sandbox), `GET …/app-conversations/search`, `DELETE …/app-conversations/{id}`, sandbox endpoints `…/sandboxes` (start/pause/delete), agent bash `POST {agent}/api/bash/execute_bash_command` — https://docs.openhands.dev/cookbook/start-sandbox, /archive-sandbox.
- SDK: Python `software-agent-sdk` (agent-server HTTP); ACP examples in repo.
- Security hooks: plugin system with `PreToolUse` hooks (`hooks.json`, `.claude-plugin/` format) → deterministic command blacklist/whitelist — https://docs.openhands.dev/cookbook/command-blacklist.

Minimal wiring snippet:
```python
import requests
H={"X-Session-API-Key":"<OH_API_KEY>"}
r=requests.post("http://127.0.0.1:8000/api/v1/app-conversations/stream-start",
                headers=H, json={"llm_model":"claude-sonnet-4-5","agent_kind":"openhands"})
conv=r.json()["id"]          # then POST messages, poll, DELETE when done
```
**Footprint:** heavy — one sandbox/conversation = pod+service+PVC in Kubernetes (or Docker); not a $5-VPS actor; self-host via Docker/Helm. Cloud option exists.

**Security:** per-conversation sandbox (isolated runtime); agent has full filesystem inside the sandbox; hooks give deterministic policy backstop; **don't** expose agent-server to the public tailnet — keep on loopback/Tailscale. **Change before use:** enable sandboxing + load a command-policy hook; restrict the agent-server to trusted interfaces.

**Wiring verdict:** ✅ **direct** (SDK/HTTP/ACP), but footprint-heavy → run as an on-demand execute actor, not an always-on resident.

---

## 3. LangGraph / LangChain (orchestrate · plan — R2 ✅)

**Contract — entry points (official docs):**
- CLI: `langgraph dev` (no Docker, `pip install "langgraph-cli[inmem]"`, binds `127.0.0.1:2024` by default, hot-reload, DAP debugger); `langgraph up` (Docker stack; needs LangSmith API key for dev, license for prod; uses ports 8123/5432/6379); `langgraph build`/`dockerfile`/`deploy` — https://docs.langchain.com/langgraph-platform/langgraph-cli, /local-server.
- Server exposes runs/threads/assistants API (Agent Server). JS: `npx @langchain/langgraph-cli dev`. MCP adapter available (langchain-mcp).
```bash
pip install "langgraph-cli[inmem]"
langgraph dev --port 2024 --host 127.0.0.1   # API at http://127.0.0.1:2024
# client: Client(apiUrl="http://localhost:2024"); client.runs.stream(...)
```
**Footprint:** `dev` = in-memory, tiny; `up` = Docker (Postgres checkpoints, ~1–2 GB+). Fits nativedev comfortably; bind loopback, expose over Tailscale only.

**Security:** framework-level — you own node code and checkpoint store; no embedded sandbox. State/persistence in your control (Postgres/SQLite). No known LangGraph CVE surfaced in R1 (CVEs 14 reported on releasealert for the repo). **Change before use:** auth on the server (its default dev bind is loopback-only — good), restrict to trusted callers.

**Wiring verdict:** ✅ **direct** (SDK + server) — the orchestration/plan substrate behind L4.

---

## 4. Khoj (memory substrate — R2 ⚠️/needs-verification)

**Contract — entry points (official docs):**
- Self-host: docker compose stack — server ports **42110**, plus pgvector Postgres + SearxNG (web search) + Terrarium (Python code sandbox). Admin/Django panel at `/server/admin`. `docker-compose up` from `khoj-ai/khoj` repo; or `pip install 'khoj[local]'` + `khoj --anonymous-mode` (single-user) — https://docs.khoj.dev/get-started/setup; https://selfhost.directory/project/khoj.md.
- REST/HTTP API + web UI on 42110; MCP integration listed in R1.
```bash
cd ~/.khoj && wget https://raw.githubusercontent.com/khoj-ai/khoj/master/docker-compose.yml
# set KHOJ_DJANGO_SECRET_KEY / ADMIN_PASSWORD / LLM keys
docker-compose up -d   # UI+API at http://localhost:42110
```
**Footprint:** 4 GB RAM min (cloud LLMs), 8 GB recommended, 2 vCPU, 2–10 GB disk; local models need 8–16 GB + GPU — https://railway.com/deploy/khoj. Comfortable on nativedev. Default binds localhost; remote access opt-in.

**Security:** server ingests your indexed docs (privacy boundary = your host). **⚠️ Operator mode** (`KHOJ_OPERATOR_ENABLED`) mounts `/var/run/docker.sock` for a computer container — leave OFF. AGPL-3.0 (network-use copyleft). Multi-user needs magic-link/Google auth.

**Wiring verdict:** ⚠️ **adapter needed** — REST/MCP wrap behind an S8-style adapter; AGPL must be signed off before committing.

---

## 5. CrewAI (wrapped planner — R2 ⚠️/needs-verification)

**Contract — entry points (official docs/R1):**
- Python library; CLI `crewai run` (project runner); agents call MCP tools. No long-running service — you host your own Crew process.
```python
from crewai import Agent, Task, Crew
crew = Crew(agents=[...], tasks=[...])
result = crew.kickoff()
```
**Footprint:** pip dependency (LiteLLM chain); process-resident; trivial disk, modest RAM per LLM call.

**Security:** library, not sandbox — runs as your user; telemetry on by default (disable for privacy); **you** own the execution boundary. No known CrewAI CVE surfaced in R1 (CVEs 6 reported on releasealert for the repo).

**Wiring verdict:** ⚠️ **adapter needed** — wrap `crewai run`/library behind an S8 adapter; good as a subordinate role-based planner, not a supervisor.

---

## 6. Protocol layer — wiring facts

**MCP (Model Context Protocol)** — client/host ↔ tool/data server. Roles: **host = client** (Hermes, our adapters), **server = capability** (Parthenos can expose itself as an MCP server). Transports: **stdio** (local subprocess) and **Streamable HTTP** (remote; SSE is legacy). Messages JSON-RPC 2.0 (`initialize`, `tools/list`, `tools/call`, resource/prompt). **Not standardized:** no built-in auth (OAuth/CIMD/DCR is an emerging layer; bearer tokens are convention), no native delta-streaming. MCP is now under the Agentic AI Foundation / Linux Foundation (Dec 2025) — sources: https://hermes-agent.nousresearch.com/docs/user-guide/features/mcp (transport/auth detail), https://www.infoworld.com/article/4007686/a-developers-guide-to-ai-protocols-mcp-a2a-and-acp.html.

**A2A (Agent2Agent)** — agent ↔ agent delegation. v1.0 under Linux Foundation. Key mechanics: **AgentCard** discovery at `/.well-known/agent-card.json` (v1.0 adds verifiable/signed cards over JWTs); **task lifecycle** states created → working → needing-input → completed/failed; streaming + callback delivery; enterprise patterns (multi-tenancy, security per task). **Not standardized:** cross-domain authorization/trust brokerage for tasks is still an open problem, and no surveyed candidate exposes an A2A server by default — we'd build the A2A side in-house for L4 → actor fan-out — source: https://a2a-protocol.org (v1.0.0 topics), https://crystl.dev/blog/agent-communication-protocols.

**ACP (Agent Client Protocol, Zed)** — editor/IDE ↔ agent hosting; JSON largely reuses MCP; only Hermes (+ OpenHands examples) expose it among our shortlist. IBM's older ACP is dead (absorbed into A2A). We use ACP only where an IDE must host an agent, not for pipeline actors — source: https://agentclientprotocol.com/.

---

## 7. Tailscale / nativedev wiring notes
- nativedev is the canonical host; every actor service should bind **loopback** and be reached via Tailscale IP `<nativedev-tailscale-ip>` on a mapped port, never published to the public internet.
- Hermes OAuth callbacks for remote MCPs use loopback redirect (`redirect_port`); over SSH/Tailscale use `hermes mcp login` with port-forward, or set `oauth.redirect_uri` to a Tailscale Funnel URL (proxied callback) — https://hermes-agent.nousresearch.com/docs/user-guide/features/mcp.
- LangGraph `dev` default bind is already loopback (`127.0.0.1:2024`); Khoj defaults to localhost; OpenHands agent-server should be loopback/Tailscale-only.
- Expose `parthenos` itself as an MCP server on a loopback port (e.g. `http://127.0.0.1:8766/mcp`) so all actors that speak MCP can reach it uniformly.

---

## 8. Wiring verdict summary

| Actor | Contract | Auth | Footprint (nativedev) | Verdict |
|---|---|---|---|---|
| Hermes Agent | MCP client+server, CLI, ACP, `hermes proxy` | per-MCP OAuth/token; 0600 token files | small (source install / $5-VPS class) | ✅ direct |
| OpenHands | HTTP agent-server + SDK + ACP | `X-Session-API-Key` / Bearer | heavy (K8s pod+PVC per conv) | ✅ direct, on-demand |
| LangGraph | `langgraph dev`/`up` + SDK (Agent Server) | loopback default; your own app auth | small–moderate (`dev` in-memory; `up` Docker+PG) | ✅ direct |
| Khoj | HTTP/REST + web (42110) + MCP | admin/Django + API tokens | moderate (4–8 GB) | ⚠️ adapter (AGPL) |
| CrewAI | Python lib + `crewai run` CLI + MCP | none (your process) | trivial (process) | ⚠️ adapter |
| MCP | stdio + Streamable HTTP; JSON-RPC 2.0 | external (OAuth/token convention) | — | backbone; build Parthenos as an MCP server |
| A2A | AgentCard + task lifecycle (v1.0) | not yet standardized across domains | — | in-house L4 fan-out |
| ACP | editor↔agent (Zed) | — | — | only for IDE hosting |

**Bottom line:** Hermes (direct, small, MCP+ACP), LangGraph (direct, orchestration), and OpenHands (direct, on-demand execute) are wire-ready on nativedev; Khoj and CrewAI need S8 adapters + licensing sign-off; MCP is the backbone (Parthenos should expose itself as an MCP server), A2A is the future L4 fan-out protocol, and ACP is relevant only for IDE-hosted agents.
