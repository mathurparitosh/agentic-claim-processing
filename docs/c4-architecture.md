# Claim Assistant — C4 Architecture

Companion to [`specs/requirements.md`](../specs/requirements.md) and
[`specs/technical.md`](../specs/technical.md). Those documents carry the *why* behind
each choice (alternatives considered, tradeoffs); this document is the *map* —
[C4 model](https://c4model.com/) diagrams of the system at increasing zoom, kept in
sync with the code rather than the plan. Diagrams render as
[Mermaid](https://mermaid.js.org/) — GitHub, most IDEs (incl. VS Code with a Mermaid
extension), and any Mermaid-aware Markdown viewer render them inline.

Reflects the system as of 2026-08-17 (Qdrant as the vector store, OpenAI/OpenRouter as
switchable LLM providers — see `specs/tracker.md` Phase 3 and the LLM-provider note in
Phase 5 for how it got here — plus Phase 7's refactor: `backend/agent/orchestrator.py`'s
Research/Decisioning supervisor graph is now the default claim-processing path
(`AGENT_MODE=orchestrator`), the on-demand Recovery agent
(`backend/agent/recovery.py`, `POST /claims/{id}/recovery`) was added, and LangSmith
tracing (Level 1/2) is now actually configured and live, not just a planned
dependency).

---

## Level 1 — System Context

Who uses Claim Assistant, and what external systems does it depend on.

```mermaid
C4Context
  title System Context — Claim Assistant

  Person(processor, "Claim Processor", "Human user. Submits claims, answers agent questions, reviews decisions.")

  System(claimAssistant, "Claim Assistant", "Researches and adjudicates billing-dispute / fraud claims: gathers evidence via tools, reasons in a ReAct loop, and reaches a deterministic Approve / Deny / Inconclusive decision with a full audit trail.")

  System_Ext(llmProvider, "LLM Provider", "OpenAI (default) or OpenRouter. Reasoning for the agent's Think step; OpenAI also supplies embeddings.")
  System_Ext(qdrant, "Qdrant Cloud", "Vector store for the policy & regulation corpus (semantic long-term memory).")
  System_Ext(langsmith, "LangSmith", "Dev-time tracing of the agent's Think/Act/Observe trajectory. Configured and live (LANGSMITH_TRACING=true in .env.local).")

  Rel(processor, claimAssistant, "Submits claims, answers ask_human questions, reviews decisions", "HTTPS")
  Rel(claimAssistant, llmProvider, "Chat completions (tool calling) + embeddings", "HTTPS/API")
  Rel(claimAssistant, qdrant, "Semantic search over policy clauses", "HTTPS/API")
  Rel(claimAssistant, langsmith, "Trace export", "HTTPS/API")
```

**Notes**

- There is exactly one human role (`Claim Processor`) — no separate admin/reviewer
  role exists; auth is a single shared password (`technical.md`'s Auth row), not
  per-user accounts.
- `LLM Provider` is drawn as one external system because the app only ever talks to
  one at a time — `LLM_PROVIDER` in `.env.local` picks OpenAI or OpenRouter
  (`backend/agent/llm.py`); embeddings (`text-embedding-3-small`) always go to OpenAI
  regardless of that switch, since Qdrant's collection dimension/relevance-floor
  calibration is pinned to that specific model.
- LangSmith is shown as a dev-time observability dependency (`technical.md`'s
  Observability row) — distinct from the `audit_trail` table, which is the permanent
  system-of-record audit log. It's now configured (`.env.local`'s
  `LANGSMITH_TRACING`/`LANGSMITH_API_KEY`/`LANGSMITH_ENDPOINT`/`LANGSMITH_PROJECT`,
  loaded by `backend/db.py`'s `load_dotenv()` before any LLM calls run) and tracing is
  live — LangChain/LangSmith auto-instrument from those env vars alone, no application
  code required.
- The Recovery agent's network-chargeback-recovery question ("can the bank recover
  funds from the card network for an already-decided claim") is a materially different
  question from claim adjudication, but is left out of this System Context diagram to
  keep it coarse-grained — see Level 2/3 for where it enters (`backend/agent/recovery.py`,
  `POST /claims/{id}/recovery`).

---

## Level 2 — Containers

The deployable/runnable units inside Claim Assistant, and how they talk to each other.

```mermaid
C4Container
  title Container diagram — Claim Assistant

  Person(processor, "Claim Processor")

  System_Boundary(app, "Claim Assistant") {
    Container(spa, "Claims Application", "React 18 (Vite)", "Password gate, claim submission form (account/transaction autocomplete), claim list, claim detail (Checks / Account & Transaction / Audit Trail tabs)")
    Container(api, "API & Agent Backend", "Python 3.12, FastAPI, LangGraph", "REST API, shared-password auth gate, background ReAct agent worker")
    ContainerDb(pg, "Postgres", "Postgres 15 (Docker for local dev)", "claims, check_ledger, audit_trail, episodic_facts, account_profiles, transactions, access_logs, LangGraph checkpoint tables")
  }

  System_Ext(llmProvider, "LLM Provider", "OpenAI or OpenRouter")
  System_Ext(qdrant, "Qdrant Cloud", "claims-policy-corpus collection")
  System_Ext(langsmith, "LangSmith")

  Rel(processor, spa, "Uses in browser", "HTTPS")
  Rel(spa, api, "Calls REST API", "JSON/HTTPS, Authorization: Bearer <password>")
  Rel(api, pg, "Reads/writes", "SQL (psycopg, pooled)")
  Rel(api, llmProvider, "Think-step reasoning + tool calls; policy-search embeddings", "HTTPS/API")
  Rel(api, qdrant, "search_policy vector queries", "HTTPS/API")
  Rel(api, langsmith, "Traces (configured, live)", "HTTPS/API")
```

**Notes**

- Local dev: Vite serves the SPA on `:5173`, uvicorn serves the API on `:8000`,
  `CORSMiddleware` in `backend/main.py` bridges the cross-origin gap
  (`scripts/start.sh` brings all three up together). Production (`specs/tracker.md`
  Phase 10, not yet done): Nginx serves the built SPA and reverse-proxies `/api` to
  uvicorn same-origin, so CORS stops mattering.
- "API & Agent Backend" is one container, not two, because the background agent
  worker (`backend/worker.py`) runs in-process via FastAPI `BackgroundTasks` — no
  separate worker process or task queue (`technical.md`'s Background Execution row:
  Celery/RQ was rejected as unjustified at this scale).
- Postgres is also LangGraph's checkpoint store (`PostgresSaver`), not just the
  application database — that's what lets a claim paused on `ask_human` survive a
  backend restart and resume correctly hours or days later.
- The on-demand Recovery agent (`POST /claims/{id}/recovery`, Phase 7) lives in this
  same "API & Agent Backend" container — it's a single retrieval call + one
  `with_structured_output` LLM call that runs synchronously in the request/response
  cycle, not via `BackgroundTasks`, since it's a few seconds of work rather than a
  multi-minute agent loop.

---

## Level 3 — Components (API & Agent Backend)

The backend container is where nearly all the interesting behavior lives. This is a
zoom into its internal modules.

```mermaid
C4Component
  title Component diagram — API & Agent Backend

  Container_Boundary(api, "API & Agent Backend") {
    Component(routes, "API Routes", "backend/main.py", "HTTP endpoints; require_auth gate on every /claims* and /accounts* route")
    Component(worker, "Worker", "backend/worker.py", "run_claim_agent / resume_claim_agent — _build_graph() picks build_orchestrator_graph (default) or graph.py's build_graph (AGENT_MODE=legacy), drives it via BackgroundTasks, handles __interrupt__")
    Component(orchestratorC, "Orchestrator Graph", "backend/agent/orchestrator.py", "Default claim-processing path (AGENT_MODE=orchestrator): one supervisor StateGraph, think_research/think_decisioning sub-nodes (own narrower toolsets) sharing one act_observe node + checkpointer")
    Component(graphC, "Agent Graph (legacy)", "backend/agent/graph.py", "Fallback path (AGENT_MODE=legacy), unmodified: single-agent ReAct StateGraph init -> think -> act_observe -> (loop | finalize). Also the source of the shared business-rule helpers orchestrator.py imports (see note below)")
    Component(recoveryC, "Recovery Agent", "backend/agent/recovery.py", "assess_recovery(claim_id) — on-demand, not part of either graph above: one search_network_policy retrieval call + one with_structured_output LLM call, not a multi-turn ReAct loop")
    Component(llmC, "LLM Provider Switch", "backend/agent/llm.py", "_build_base_model() shared by build_agent_model(tools) (tool-calling, used by graphC/orchestratorC) and build_structured_model(schema) (with_structured_output, used by recoveryC), both per LLM_PROVIDER")
    Component(toolsC, "Tools", "backend/agent/tools.py", "Grounding, Computation, Retrieval (search_policy), ask_human, write_determination — plus search_network_policy, reachable only from recoveryC, never from orchestratorC/graphC")
    Component(checksC, "Checks & Decision Rule", "backend/agent/checks.py", "REQUIRED_CHECKS per claim type; deterministic compute_decision")
    Component(ledgerC, "Ledger", "backend/agent/ledger.py", "Sole writer of check_ledger / audit_trail / claims.decision")
    Component(episodicC, "Episodic Memory", "backend/agent/episodic.py", "Cross-claim entity facts, keyed lookup")
    Component(dbC, "DB Pool", "backend/db.py", "psycopg_pool ConnectionPool, dict-row cursors")
  }

  ContainerDb(pg, "Postgres")
  System_Ext(llmProvider, "LLM Provider")
  System_Ext(qdrant, "Qdrant Cloud")

  Rel(routes, dbC, "Direct SQL for simple reads/writes (claims, context, audit)", "SQL")
  Rel(routes, worker, "Starts/resumes a run", "BackgroundTasks")
  Rel(routes, ledgerC, "Logs claim_submitted / human_answer (source: human)", "call")
  Rel(routes, recoveryC, "POST /claims/{id}/recovery -> assess_recovery(claim_id), synchronous (not BackgroundTasks)", "call")

  Rel(worker, orchestratorC, "build_orchestrator_graph(checkpointer).invoke(...) — default", "call")
  Rel(worker, graphC, "build_graph(checkpointer).invoke(...) — AGENT_MODE=legacy fallback", "call")
  Rel(worker, dbC, "Reads claim row, flips status", "SQL")

  Rel(orchestratorC, graphC, "imports _derive_check_updates / _format_checks / ClaimState / finalize_node / iteration caps — shared, unmodified", "import")
  Rel(orchestratorC, llmC, "MODEL_RESEARCH/MODEL_DECISIONING = build_agent_model(...)", "call")
  Rel(orchestratorC, toolsC, "Research sub-agent: Grounding+Retrieval tools only; Decisioning sub-agent: Computation + ask_human + write_determination", "call")
  Rel(orchestratorC, ledgerC, "update_check / log_audit (source: agent, sub_agent: research|decisioning)", "call")
  Rel(orchestratorC, episodicC, "get_facts (init) / upsert_fact (after grounding calls)", "call")

  Rel(graphC, llmC, "MODEL = build_agent_model(TOOLS)", "call")
  Rel(llmC, llmProvider, "Chat completions (tool_choice=required) / structured-output calls", "HTTPS")
  Rel(graphC, toolsC, "Invokes exactly one tool per turn", "call")
  Rel(graphC, checksC, "Required-checks list, termination/decision rule", "call")
  Rel(graphC, ledgerC, "update_check / log_audit (source: agent) / finalize_decision", "call")
  Rel(graphC, episodicC, "get_facts (init) / upsert_fact (after grounding calls)", "call")

  Rel(recoveryC, toolsC, "search_network_policy (hardcoded network_recovery filter)", "call")
  Rel(recoveryC, llmC, "build_structured_model(RecoveryAssessment)", "call")
  Rel(recoveryC, ledgerC, "log_audit(recovery_assessment, source: agent)", "call")
  Rel(recoveryC, dbC, "Reads claims + check_ledger rows directly", "SQL")

  Rel(toolsC, qdrant, "search_policy / search_network_policy: query_points", "HTTPS")
  Rel(toolsC, llmProvider, "search_policy / search_network_policy: embeddings.create (text-embedding-3-small)", "HTTPS")
  Rel(toolsC, dbC, "Grounding/computation reads (transactions, access_logs, account_profiles)", "SQL")

  Rel(ledgerC, dbC, "SQL", "SQL")
  Rel(episodicC, dbC, "SQL", "SQL")
  Rel(dbC, pg, "SQL")
```

**Notes**

- **`ledger.py` is the single write path** for `check_ledger`, `audit_trail`, and
  `claims.decision` — `graph.py` and `orchestrator.py` (agent-sourced events),
  `recovery.py` (`recovery_assessment` events), and `main.py` (the two human-sourced
  events, `claim_submitted` and `human_answer`) all call into it rather than writing
  SQL directly, which is what makes every audit row's `source: "agent"|"human"`
  attribution reliable (`specs/requirements.md` §11).
- **`checks.py` is the only place the core Approve/Deny/Inconclusive decision is
  computed**, and it's shared, not duplicated: the LLM never asserts a decision —
  `write_determination` is a tool with no decision payload; calling it only triggers
  `finalize_node` (defined once, in `graph.py`), which calls `ledger.finalize_decision`,
  which calls `checks.compute_decision` on the check ledger's actual PASS/FAIL/BLOCKED
  state (`specs/requirements.md` §6). `orchestrator.py` imports `finalize_node`
  directly rather than reimplementing it — along with `_derive_check_updates`,
  `_format_checks`, `ClaimState`, and the iteration caps — specifically so the
  check-ledger/decision rules can never drift between the legacy and orchestrator
  paths. The Recovery agent's `eligible` judgment is a deliberate, scoped exception to
  this pattern: it's an LLM-judged, advisory output, not a run through `checks.py`
  (`specs/technical.md` §5).
- **`tools.py` talks to three different stores**: Postgres directly (grounding/
  computation tools), Qdrant (semantic search — `search_policy` for the main
  claim-processing loop, `search_network_policy` exclusively for `recoveryC`), and the
  LLM provider (embeddings for that search — always OpenAI, independent of
  `LLM_PROVIDER`).
- **`orchestrator.py` vs `graph.py`**: `orchestrator.py` is new code for the
  supervisor's `act_observe_node` and its two think-nodes (they needed
  sub_agent-tagging/role-switching logic the legacy loop doesn't have), so there's
  deliberate duplication of the tool-execution loop *shape* between the two files —
  but the business rules inside it (check derivation, formatting, decision
  finalization, iteration caps) are imported, not copied.
- **`recovery.py` is a one-shot judgment, not a ReAct loop**: one retrieval call
  (`search_network_policy`) feeds one `with_structured_output` call
  (`RecoveryAssessment` schema) — no tool-calling turns, no checkpointing, no
  `ask_human`. It runs synchronously inside the `POST /claims/{id}/recovery` request.
- Endpoints not shown individually above (they all route through `routes` →
  `dbC`/`worker`/`ledgerC`/`recoveryC`): `POST /claims`, `GET /claims`,
  `GET /claims/{id}`, `GET /claims/{id}/context`, `GET /claims/{id}/audit`,
  `GET /claims/{id}/questions`, `POST /claims/{id}/answer`, `GET /claims/{id}/decision`,
  `POST /claims/{id}/recovery`, `GET /accounts`, `GET /accounts/{id}/transactions`.

### Frontend components (Claims Application), for completeness

```mermaid
C4Component
  title Component diagram — Claims Application (React)

  Container_Boundary(spa, "Claims Application") {
    Component(app, "App", "App.jsx", "Auth state, selected-claim state, layout")
    Component(gate, "PasswordGate", "PasswordGate.jsx", "Shared-password login; stores in sessionStorage")
    Component(form, "ClaimForm", "ClaimForm.jsx", "Account autocomplete (datalist) + transaction dropdown, claim submission")
    Component(list, "ClaimList", "ClaimList.jsx", "Polls GET /claims every 3s, status/decision badges")
    Component(detail, "ClaimDetail", "ClaimDetail.jsx", "Checks / Account & Transaction / Audit Trail tabs; ask_human Q&A")
    Component(api, "api.js", "api.js", "fetch wrapper, Bearer auth injection, 401 handling")
  }

  Container(backend, "API & Agent Backend")

  Rel(app, gate, "Renders when unauthenticated")
  Rel(app, form, "Renders in sidebar")
  Rel(app, list, "Renders in sidebar")
  Rel(app, detail, "Renders in main pane")
  Rel(form, api, "listAccounts / listAccountTransactions / submitClaim")
  Rel(list, api, "listClaims (poll)")
  Rel(detail, api, "getClaim / getContext / getAudit (poll) / answerQuestion")
  Rel(api, backend, "JSON/HTTPS", "Bearer <password>")
```

---

## Level 4 — Dynamic view: a claim's lifecycle

Not a C4 "Code" diagram (there's no class hierarchy complex enough to warrant one) —
instead, the runtime sequence that the container/component diagrams above don't show:
how a claim moves through the system, including the `ask_human` pause/resume that
motivates several of the architectural choices above (Postgres-backed checkpointing,
background-task execution, polling-based `ask_human` channel).

```mermaid
sequenceDiagram
    actor P as Claim Processor
    participant SPA as Claims Application
    participant API as API Routes
    participant W as Worker
    participant G as Agent Graph
    participant T as Tools
    participant PG as Postgres
    participant L as LLM Provider
    participant Q as Qdrant

    P->>SPA: Fill claim form, submit
    SPA->>API: POST /claims
    API->>PG: INSERT claims (status=pending)
    API->>PG: log_audit(claim_submitted, source=human)
    API-->>SPA: 202 claim_id
    API->>W: BackgroundTasks: run_claim_agent(claim_id)

    W->>PG: status=processing
    W->>G: graph.invoke(initial_state)
    loop Think / Act / Observe (until decided or capped)
        G->>L: Think: propose one tool call
        G->>T: Act: execute tool
        alt Grounding / Computation
            T->>PG: SQL lookup
        else Retrieval (search_policy)
            T->>L: embed query
            T->>Q: vector search (claim_type filter)
        else ask_human
            T-->>G: interrupt() — pause, serialize state
        end
        G->>PG: Observe: update_check + log_audit(source=agent)
    end

    alt Agent called write_determination
        G->>PG: finalize_decision (checks -> Approve/Deny/Inconclusive)
        Note over W: graph.invoke() returns with no __interrupt__ - already finalized
    else Agent called ask_human
        W->>PG: status=awaiting_input, pending_question
    end

    P->>SPA: Poll for status / questions
    SPA->>API: GET /claims/{id}, GET /claims/{id}/questions
    API->>PG: SELECT
    API-->>SPA: status, pending_question, checks, audit

    opt awaiting_input
        P->>SPA: Answer question
        SPA->>API: POST /claims/{id}/answer
        API->>PG: log_audit(human_answer, source=human)
        API->>W: BackgroundTasks: resume_claim_agent(claim_id, answer)
        W->>G: graph.invoke(Command(resume=answer))
        Note over G: Rehydrated from PostgresSaver checkpoint —<br/>works even after a backend restart
        G->>PG: ...continues the Think/Act/Observe loop...
    end
```

**Since Phase 7**, `G` ("Agent Graph") in the loop above is `orchestratorC` by default
(`AGENT_MODE=orchestrator`), not `graphC` — but the externally-visible sequence shape is
unchanged: `graph.invoke`/`Command(resume=...)`, one shared `act_observe`, the same
pause/resume/checkpoint mechanics. What changes internally is that "Think" now covers
two distinct roles sharing this same loop shape — a Research turn (Grounding + Retrieval
tools only) followed by a Decisioning turn (Computation + `ask_human` +
`write_determination`) — with a supervisor deciding after each `act_observe` round which
role goes next (research-owned checks resolved, or its iteration budget exhausted, hands
off to Decisioning permanently). `ask_human` is only ever proposed during a Decisioning
turn, since Research has no access to that tool.

### Recovery agent — separate, on-demand sequence

A materially different interaction shape from the loop above: synchronous, one-shot, no
pause/resume, no checkpointing. Triggered only after a claim already has a decision.

```mermaid
sequenceDiagram
    actor P as Claim Processor
    participant SPA as Claims Application
    participant API as API Routes
    participant R as Recovery Agent
    participant PG as Postgres
    participant Q as Qdrant
    participant L as LLM Provider

    P->>SPA: Click "Check Recovery Eligibility"
    SPA->>API: POST /claims/{id}/recovery
    API->>PG: SELECT decision FROM claims
    alt decision not in (approve, inconclusive)
        API-->>SPA: 409
    else eligible to check
        API->>R: assess_recovery(claim_id)
        R->>PG: SELECT claim + check_ledger rows
        R->>Q: search_network_policy (network_recovery filter)
        R->>L: with_structured_output(RecoveryAssessment)
        R->>PG: log_audit(recovery_assessment, source=agent)
        R-->>API: assessment result
        API-->>SPA: 200 assessment result
    end
    SPA->>SPA: Switch to Audit Trail tab, show new entry
```

---

## Scope & maintenance

This document is the structural map; it deliberately does **not** repeat the
decision rationale already in `specs/technical.md` (tech-choice table with
alternatives considered) or the requirement-level "why" in `specs/requirements.md`.
When either changes in a way that moves a box or an arrow — a new container, a
component split apart, a dependency swapped (as Pinecone → Qdrant was) — update the
relevant diagram(s) here too, the same way `specs/tracker.md` is kept current against
the actual implementation.
