# Claim Assistant — Agentic AI Capstone Project

An agentic system that **researches and adjudicates fraud and billing-dispute claims**
on behalf of a human claim processor. It reads a submitted claim, determines which
regulatory/policy checks apply to its type, autonomously gathers evidence through
tools (transaction lookups, access-log checks, anomaly computation, policy retrieval),
and either renders a grounded **Approve / Deny** decision or reports **Inconclusive**
with a stated reason — always with a full, append-only audit trail.

Built with **LangGraph** (a ReAct Think→Act→Observe loop plus a Research/Decisioning
supervisor graph), **FastAPI**, **React**, **PostgreSQL**, and **Qdrant** for the
policy-corpus RAG. Human-in-the-loop escalation (`ask_human`) suspends a run and
resumes it — via Postgres-backed checkpointing — whenever the processor answers,
even after a restart.

The design rationale lives in [`specs/requirements.md`](specs/requirements.md) (the
*why*), [`specs/technical.md`](specs/technical.md) (stack choices + alternatives), and
[`docs/c4-architecture.md`](docs/c4-architecture.md) (C4 diagrams of the system as
built).

---

## Architecture

Three runnable units, three external services:

| Unit | Tech | Role |
|---|---|---|
| **Claims Application** | React 18 (Vite), `:5173` | Password gate, claim submission, claim list, claim detail (Checks / Account & Transaction / Audit Trail tabs), `ask_human` Q&A |
| **API & Agent Backend** | Python 3.11+, FastAPI, LangGraph, `:8000` | REST API, shared-password auth, in-process agent worker via `BackgroundTasks` |
| **Postgres** | Postgres 15 (Docker for local dev), `:5432` | `claims`, `check_ledger`, `audit_trail`, `episodic_facts`, `transactions`, `access_logs`, `account_profiles`, plus LangGraph checkpoint tables |
| LLM Provider *(external)* | OpenAI (default) or OpenRouter | Think-step reasoning + tool calls; OpenAI also supplies embeddings |
| Qdrant Cloud *(external)* | `claims-policy-corpus` collection | Vector store for the policy/regulation corpus (semantic long-term memory) |
| LangSmith *(external)* | — | Dev-time tracing of the Think/Act/Observe trajectory |

### How a claim is processed

1. **Init** — seed the check ledger with every check required for the claim type
   (looked up deterministically by `claim_type`, never LLM-inferred), load episodic
   facts for the entity.
2. **Think → Act → Observe loop** — the LLM proposes one tool call per turn; the graph
   executes it, maps the result onto check-ledger state (`PASS` / `FAIL` / `UNKNOWN` /
   `BLOCKED`), and writes an `audit_trail` row.
3. **Terminate** — the decision is *derived from the ledger*, never self-declared:
   - any check `FAIL` → **Deny** (short-circuits remaining checks)
   - all checks `PASS` → **Approve**
   - iteration cap (~12), 5 no-progress iterations, or the 3-question `ask_human`
     budget exhausted → **Inconclusive** with a reason

Claim processing runs on the **Research / Decisioning supervisor graph**
([`backend/agent/orchestrator.py`](backend/agent/orchestrator.py)): a Research
sub-agent (Grounding + Retrieval tools only) gathers evidence, then hands off
permanently to a Decisioning sub-agent (Computation tools + `ask_human`) that drives
the remaining checks. Iteration/no-progress/human-budget counters are global across the
whole run. ([`backend/agent/graph.py`](backend/agent/graph.py) holds the shared state /
check-ledger / finalize core it builds on — it used to also carry a standalone
single-agent `AGENT_MODE=legacy` loop, since removed.)

A separate **on-demand Recovery agent** (`POST /claims/{id}/recovery`) runs *after* a
decision exists, only for `approve` / `inconclusive` claims: one `search_network_policy`
retrieval + one structured-output LLM call judging card-network chargeback eligibility.
Its output is an advisory `audit_trail` note — deliberately LLM-judged rather than
code-computed.

### Claim taxonomy

| Claim type | Required checks |
|---|---|
| `billing_dispute` | `transaction_exists`, `duplicate_charge_check`, `policy_dispute_window`, `account_standing` |
| `fraud` | `account_red_flags`, `transaction_pattern_anomaly`, `system_access_log_check`, `policy_liability_rule` |

Full mapping (check → resolving tool → PASS/FAIL semantics) in
[`specs/technical.md`](specs/technical.md) §4.

---

## Project Structure

```
backend/
  main.py                     FastAPI app + routes
  auth.py                     shared-password gate + admin/processor/customer roles (X-Username)
  worker.py                   run_claim_agent / resume_claim_agent (BackgroundTasks); build_claim_graph()
  db.py                       pooled psycopg connection helper; loads .env.local
  agent/
    orchestrator.py           the claim-processing path — Research/Decisioning supervisor graph
    graph.py                  shared core: ClaimState, check-ledger derivation, finalize_node, caps
    recovery.py               on-demand card-network recovery agent
    llm.py                    OpenAI / OpenRouter / Ollama provider switch
    tools.py                  Grounding / Computation / Retrieval / ask_human / write_determination
    checks.py                 REQUIRED_CHECKS per claim type; deterministic compute_decision
    ledger.py                 sole writer of check_ledger / audit_trail / claims.decision
    episodic.py               cross-claim entity facts (keyed lookup)
  generate_synthetic_data.py  10 hand-authored scenarios → GPT-generated fixtures (accounts/transactions/access logs)
  setup_checkpointer.py       creates LangGraph's PostgresSaver tables
  eval_notebook.ipynb         Phase 9 — runs all 10 eval claims through the live orchestrator
  test_api.py                 pytest: auth, list endpoints, claim lifecycle
frontend/src/
  App.jsx, api.js             auth state + fetch wrapper (Bearer auth, 401 handling)
  components/                  PasswordGate, ClaimForm, ClaimList, ClaimDetail, TabStrip
scripts/
  start.sh / stop.sh          bring the full stack up / down
  run-all-tests.sh            8-section integration test (prereqs → DB → API → LLM → data → claim → eval → integrity)
  test.sh                     9-section smoke test
  test-browser.sh             Playwright end-to-end (login → submit → process → audit trail)
  ingest_policy_corpus.py     clause-boundary chunker → Qdrant
docs/
  c4-architecture.md          C4 diagrams (context / container / component / dynamic)
  context.md                  workspace snapshot + assistant-handoff notes
  files/*.md                  policy & regulation corpus (CCD, DBD, ZEL, ACH, FRD, NWR) + 00_CORPUS_INDEX.md
specs/
  requirements.md             functional requirements + design rationale
  technical.md                stack table (choice / alternatives / why) + claim taxonomy + multi-agent design
  tracker.md                  phase-by-phase implementation log
  eval_claims.md              the 10 predetermined eval claims (ground truth for eval_notebook.ipynb)
schema.sql                    application tables
docker-compose.yml            local Postgres 15
```

---

## Quick Start

### Prerequisites
- Python 3.11+
- Node.js (LTS)
- Docker Desktop (for local Postgres)
- API keys: OpenAI, Qdrant Cloud, LangSmith (see [Environment Variables](#environment-variables))

### 1. Configure environment
```bash
cp .env.example .env.local
# then edit .env.local and fill in real values (OPENAI_API_KEY, QDRANT_URL/API_KEY, LANGSMITH_API_KEY, …)
```

### 2. Start Postgres and apply the schema
```bash
docker compose up -d postgres

# application tables
docker compose exec -T postgres psql -U postgres -d claims_dev < schema.sql

# LangGraph checkpoint tables (idempotent — run once per fresh database)
cd backend && source .venv/bin/activate
python -m backend.setup_checkpointer
```
> `backend/.venv` is created automatically the first time you run `./scripts/start.sh`
> or any test script. To make it yourself: `python3 -m venv backend/.venv && backend/.venv/bin/pip install -r backend/requirements.txt`.

### 3. Ingest the policy corpus into Qdrant (one-time)
```bash
# from the repo root, with the backend venv active
source backend/.venv/bin/activate
python scripts/ingest_policy_corpus.py
```
Creates the `claims-policy-corpus` collection on first run and upserts ~118 clause
chunks (idempotent). The script loads `.env.local` itself.

### 4. Load synthetic fixture data
```bash
cd backend && source .venv/bin/activate

# preview generation for one account without writing to the DB
python -m backend.generate_synthetic_data --dry-run --accounts ACC-9001

# load all 10 eval accounts (accounts, transactions, access logs)
python -m backend.generate_synthetic_data
```

### 5. Run everything
```bash
./scripts/start.sh    # Postgres + FastAPI (:8000) + React dev server (:5173)
./scripts/stop.sh     # tear it all down
```

- **Frontend:** http://localhost:5173
- **Backend API:** http://localhost:8000
- **Auth:** send `Authorization: Bearer <AUTH_PASSWORD>` (value from `.env.local`) plus
  `X-Username: admin|processor|customer` (omit → `admin`). The three demo users share
  the one password; the username only selects a **role** (`backend/auth.py`):
  - `admin` — everything, including the Agent tab and the per-claim Context / Memory /
    Sub-agents tracing tabs
  - `processor` — every claim, but no Agent tab and no tracing tabs
  - `customer` — may only file claims and see the claims they filed
  The frontend password gate has one-click buttons for each.
- **Logs:** `backend/uvicorn.log`, `frontend/vite.log`

---

## API Endpoints

All `/claims*` and `/accounts*` routes require `Authorization: Bearer <AUTH_PASSWORD>`
(and honour `X-Username` for role — see Quick Start). `/agent/*` and the per-claim
`agent-context` / `memory` routes are **admin only**; `POST /claims/{id}/recovery` is
blocked for `customer`; a `customer` only sees claims where `filed_by` is their username.

| Method & path | Purpose |
|---|---|
| `GET /` | Health check (unauthenticated) |
| `GET /whoami` | Echo the caller's `{username, role}` (used by the frontend login) |
| `POST /claims` | Submit a claim (records `filed_by`); enqueues the agent run via `BackgroundTasks` |
| `GET /claims?limit=` | List claims with status/decision |
| `GET /claims/{id}` | Claim detail + check ledger |
| `GET /claims/{id}/context` | Account profile + disputed-transaction detail |
| `GET /claims/{id}/audit` | Full timestamped audit trail (agent vs human attributed) |
| `GET /claims/{id}/questions` | Pending `ask_human` question, if the run is paused |
| `POST /claims/{id}/answer` | Answer a pending question; resumes the run |
| `GET /claims/{id}/decision` | Final decision + evidentiary basis |
| `POST /claims/{id}/recovery` | Trigger the on-demand Recovery agent (`approve`/`inconclusive` only; not for `customer`) |
| `GET /claims/{id}/agent-context` | **admin** — the model's live message window + run counters (Context tab) |
| `GET /claims/{id}/memory` | **admin** — episodic facts for the claim's account (Memory tab) |
| `GET /agent/tools` | **admin** — static tool catalog (Agent tab) |
| `GET /agent/graph` | **admin** — compiled orchestrator graph, Mermaid + ASCII (Agent tab) |
| `GET /accounts` | List accounts |
| `GET /accounts/{id}/transactions` | Transactions for an account |

---

## Testing

All test scripts create/activate `backend/.venv`, ensure Postgres is up, and read
secrets from `.env.local`.

### Integration test — `./scripts/run-all-tests.sh`
Eight sections: prerequisites → start services → Python env → **1** DB connection →
**2** API endpoints & auth → **3** LLM & Qdrant → **4** synthetic-data dry run →
**5** fixture load → **6** single claim through the orchestrator → **7** eval suite
(first 3 claims) → **8** DB integrity. Prints a pass/fail summary and exits non-zero on
any failure.

### Smoke test — `./scripts/test.sh`
Nine sections, similar coverage, less strict summary — quickest way to confirm the
stack is wired up.

### Full evaluation (30 min) — 10 predetermined claims
```bash
cd backend && source .venv/bin/activate
jupyter nbconvert --to notebook --execute --inplace eval_notebook.ipynb
```
Runs every claim in [`specs/eval_claims.md`](specs/eval_claims.md) through the live
orchestrator (with a scripted `ask_human` auto-responder for #6/#7/#10). Expected:
10/10 match the predetermined outcomes (4 Approve, 5 Deny, 1 Inconclusive).

### Browser end-to-end — `./scripts/test-browser.sh`
Requires the stack already running (`./scripts/start.sh`) and Playwright
(`npm install -D @playwright/test`). Validates login → claim submission → live status
updates → audit-trail tab.

### Unit / integration (pytest)
```bash
cd backend && source .venv/bin/activate
pip install pytest
pytest test_api.py -v
```

---

## Environment Variables

Defined in `.env.example`; copy to `.env.local` (gitignored — never commit) and fill in.

| Variable | Notes |
|---|---|
| `LLM_PROVIDER` | `openai` (default), `openrouter`, or `ollama` — see [`backend/agent/llm.py`](backend/agent/llm.py) |
| `OPENAI_API_KEY` / `OPENAI_MODEL` | Required for the default provider; also used for embeddings regardless of `LLM_PROVIDER` |
| `OPENROUTER_API_KEY` / `OPENROUTER_MODEL` / `OPENROUTER_BASE_URL` | Only when `LLM_PROVIDER=openrouter` |
| `QDRANT_URL` / `QDRANT_API_KEY` / `QDRANT_COLLECTION` | Qdrant Cloud; collection defaults to `claims-policy-corpus` |
| `LANGSMITH_API_KEY` / `LANGSMITH_TRACING` / `LANGSMITH_ENDPOINT` / `LANGSMITH_PROJECT` | Tracing auto-instruments from these vars alone; no app code needed |
| `DATABASE_URL` | Local dev: `postgresql://postgres:password@localhost:5432/claims_dev` |
| `AUTH_PASSWORD` | Shared password for the API gate and the frontend login |

---

## Documentation

| Doc | What's in it |
|---|---|
| [`specs/requirements.md`](specs/requirements.md) | Functional requirements, the ReAct-vs-ToT rationale, decision/memory/audit model |
| [`specs/technical.md`](specs/technical.md) | Stack table (choice · alternatives considered · why), claim taxonomy, multi-agent + Recovery-agent design |
| [`specs/tracker.md`](specs/tracker.md) | Phase-by-phase implementation log (Phases 0–11) with the bugs found and fixed along the way |
| [`specs/eval_claims.md`](specs/eval_claims.md) | The 10 eval claims and their predetermined outcomes |
| [`docs/c4-architecture.md`](docs/c4-architecture.md) | C4 diagrams (Mermaid): system context, containers, components, claim lifecycle |
| [`docs/deployment.md`](docs/deployment.md) | Step-by-step guide + checklist for deploying to a single Linux server (Nginx + systemd/uvicorn + Postgres) |
| [`docs/files/00_CORPUS_INDEX.md`](docs/files/00_CORPUS_INDEX.md) | Policy-corpus map: documents, superseded pairs, near-duplicates, deliberate coverage gaps |

---

## Known Limitations

- **Auth is one shared password with fixed roles** — `admin` / `processor` / `customer`
  all authenticate with the same `AUTH_PASSWORD`; the `X-Username` header picks the role
  (`backend/auth.py`). There are no per-user secrets and no real identity provider, so
  the audit trail still can't distinguish two people using the same role.
- **RAG reranking is not implemented** — `search_policy` sorts the top-20 Qdrant
  candidates by raw cosine score and truncates to top-3; the LLM rerank described in
  `technical.md` was never wired up (`tracker.md` Phase 3).
- **Retrieval-only checks close on any hit** — `policy_dispute_window` /
  `policy_liability_rule` PASS on a retrieved, citable clause; there is no computation
  step comparing the clause's stated day-count window against the claim's filed date
  (deliberately deferred — see `technical.md` §4).
- **Background execution is in-process** (`BackgroundTasks`, no queue) — fine at
  capstone scale; `tracker.md` backlog notes when to split it out.
- **Test harness is not wired into CI** — the eval notebook and scripts are run
  manually.
