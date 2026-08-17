# Claim Assistant — C4 Architecture

Companion to [`specs/requirements.md`](../specs/requirements.md) and
[`specs/technical.md`](../specs/technical.md). Those documents carry the *why* behind
each choice (alternatives considered, tradeoffs); this document is the *map* —
[C4 model](https://c4model.com/) diagrams of the system at increasing zoom, kept in
sync with the code rather than the plan. Diagrams render as
[Mermaid](https://mermaid.js.org/) — GitHub, most IDEs (incl. VS Code with a Mermaid
extension), and any Mermaid-aware Markdown viewer render them inline.

Reflects the system as of 2026-08-16 (Qdrant as the vector store, OpenAI/OpenRouter as
switchable LLM providers — see `specs/tracker.md` Phase 3 and the LLM-provider note in
Phase 5 for how it got here).

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
  System_Ext(langsmith, "LangSmith", "Dev-time tracing of the agent's Think/Act/Observe trajectory. Not wired up yet (Phase 7).")

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
- LangSmith is shown because it's a confirmed architectural dependency
  (`technical.md`'s Observability row) even though it isn't wired into the code yet —
  Phase 7 in `specs/tracker.md` is still open.

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
  Rel(api, langsmith, "Traces (not yet wired up)", "HTTPS/API")
```

**Notes**

- Local dev: Vite serves the SPA on `:5173`, uvicorn serves the API on `:8000`,
  `CORSMiddleware` in `backend/main.py` bridges the cross-origin gap
  (`scripts/start.sh` brings all three up together). Production (`specs/tracker.md`
  Phase 9, not yet done): Nginx serves the built SPA and reverse-proxies `/api` to
  uvicorn same-origin, so CORS stops mattering.
- "API & Agent Backend" is one container, not two, because the background agent
  worker (`backend/worker.py`) runs in-process via FastAPI `BackgroundTasks` — no
  separate worker process or task queue (`technical.md`'s Background Execution row:
  Celery/RQ was rejected as unjustified at this scale).
- Postgres is also LangGraph's checkpoint store (`PostgresSaver`), not just the
  application database — that's what lets a claim paused on `ask_human` survive a
  backend restart and resume correctly hours or days later.

---

## Level 3 — Components (API & Agent Backend)

The backend container is where nearly all the interesting behavior lives. This is a
zoom into its internal modules.

```mermaid
C4Component
  title Component diagram — API & Agent Backend

  Container_Boundary(api, "API & Agent Backend") {
    Component(routes, "API Routes", "backend/main.py", "HTTP endpoints; require_auth gate on every /claims* and /accounts* route")
    Component(worker, "Worker", "backend/worker.py", "run_claim_agent / resume_claim_agent — drives the graph via BackgroundTasks, handles __interrupt__")
    Component(graphC, "Agent Graph", "backend/agent/graph.py", "LangGraph ReAct StateGraph: init -> think -> act_observe -> (loop | finalize)")
    Component(llmC, "LLM Provider Switch", "backend/agent/llm.py", "Builds the bound ChatOpenAI model per LLM_PROVIDER")
    Component(toolsC, "Tools", "backend/agent/tools.py", "Grounding, Computation, Retrieval (search_policy), ask_human, write_determination")
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

  Rel(worker, graphC, "graph.invoke(...) / graph.invoke(Command(resume=...))", "call")
  Rel(worker, dbC, "Reads claim row, flips status", "SQL")

  Rel(graphC, llmC, "MODEL = build_agent_model(TOOLS)", "call")
  Rel(llmC, llmProvider, "Chat completions (tool_choice=required)", "HTTPS")
  Rel(graphC, toolsC, "Invokes exactly one tool per turn", "call")
  Rel(graphC, checksC, "Required-checks list, termination/decision rule", "call")
  Rel(graphC, ledgerC, "update_check / log_audit (source: agent) / finalize_decision", "call")
  Rel(graphC, episodicC, "get_facts (init) / upsert_fact (after grounding calls)", "call")

  Rel(toolsC, qdrant, "search_policy: query_points", "HTTPS")
  Rel(toolsC, llmProvider, "search_policy: embeddings.create (text-embedding-3-small)", "HTTPS")
  Rel(toolsC, dbC, "Grounding/computation reads (transactions, access_logs, account_profiles)", "SQL")

  Rel(ledgerC, dbC, "SQL", "SQL")
  Rel(episodicC, dbC, "SQL", "SQL")
  Rel(dbC, pg, "SQL")
```

**Notes**

- **`ledger.py` is the single write path** for `check_ledger`, `audit_trail`, and
  `claims.decision` — both `graph.py` (agent-sourced events) and `main.py` (the two
  human-sourced events, `claim_submitted` and `human_answer`) call into it rather than
  writing SQL directly, which is what makes every audit row's `source: "agent"|"human"`
  attribution reliable (`specs/requirements.md` §11).
- **`checks.py` is the only place a decision is computed.** The LLM never asserts
  Approve/Deny/Inconclusive — `write_determination` is a tool with no decision payload;
  calling it only triggers `finalize_node`, which calls `ledger.finalize_decision`,
  which calls `checks.compute_decision` on the check ledger's actual PASS/FAIL/BLOCKED
  state (`specs/requirements.md` §6).
- **`tools.py` talks to three different stores**: Postgres directly (grounding/
  computation tools), Qdrant (semantic search), and the LLM provider (embeddings for
  that search — always OpenAI, independent of `LLM_PROVIDER`).
- Endpoints not shown individually above (they all route through `routes` →
  `dbC`/`worker`/`ledgerC`): `POST /claims`, `GET /claims`, `GET /claims/{id}`,
  `GET /claims/{id}/context`, `GET /claims/{id}/audit`, `GET /claims/{id}/questions`,
  `POST /claims/{id}/answer`, `GET /claims/{id}/decision`, `GET /accounts`,
  `GET /accounts/{id}/transactions`.

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

---

## Scope & maintenance

This document is the structural map; it deliberately does **not** repeat the
decision rationale already in `specs/technical.md` (tech-choice table with
alternatives considered) or the requirement-level "why" in `specs/requirements.md`.
When either changes in a way that moves a box or an arrow — a new container, a
component split apart, a dependency swapped (as Pinecone → Qdrant was) — update the
relevant diagram(s) here too, the same way `specs/tracker.md` is kept current against
the actual implementation.
