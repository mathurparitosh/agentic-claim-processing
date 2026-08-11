# Claim Assistant — Implementation Tracker

Companion to [requirements.md](requirements.md) and [technical.md](technical.md).
Work through phases in order — each one depends on the previous. Check items off as
you go.

## Legend

- `🌐 EXTERNAL` — happens outside this repo/VS Code: a web dashboard, an account
  signup, an SSH session on the Ubuntu server.
- `💻 LOCAL` — happens in this repo, in your terminal or VS Code.
- Unchecked `[ ]` = not started. Check to `[x]` when done.

---

## Phase 0 — Accounts & External Prerequisites

Do all of this first — nothing in Phase 1+ can run without these keys/services.

### OpenAI (LLM + embeddings + reranking)
- [x] 🌐 Sign up / log in at platform.openai.com
- [x] 🌐 Add a payment method under **Billing → Payment methods** (API calls fail without one) — confirm this is done
- [x] 🌐 Create an API key under **API keys → Create new secret key** — copy it immediately, it's shown once
  - ⚠️ Confirm `OPENAI_API_KEY` uses a valid OpenAI key (`sk-...` prefix) and `LANGSMITH_API_KEY` uses the LangSmith key prefix (`lsv2_pt_...`).
- [x] 🌐 Set a usage limit/budget alert under **Billing → Limits** (recommended, not required)

### Pinecone (semantic memory / policy corpus)
- [x] 🌐 Sign up at app.pinecone.io
- [x] 🌐 Create or select a project
- [x] 🌐 Create an index:
  - name: `claims-policy-corpus` (or your choice — record it, it goes in `.env`)
  - dimension: **1536** (must match `text-embedding-3-small`)
  - metric: **cosine**
  - type: Serverless, region close to your Ubuntu server
- [x] 🌐 Generate an API key under **API Keys**

### LangSmith (dev-time tracing)
- [x] 🌐 Sign up at smith.langchain.com
- [x] 🌐 Create a project, e.g. `claim-assistant`
- [x] 🌐 Generate an API key under **Settings → API Keys**

### Ubuntu deployment server
- [x] 🌐 Confirm SSH access: hostname/IP, SSH key or password, a sudo-capable user
- [x] 🌐 Decide: access via server IP, or point an existing domain at it (optional — not required to ship)

### Version control (recommended, not strictly required)
- [x] 🌐 Create a GitHub (or other git host) repo — makes it far easier to get code onto the Ubuntu server later
- [x] 💻 `git init` in this project directory
- [x] 💻 Add a `.gitignore` (`.env`, `__pycache__/`, `node_modules/`, `*.pyc`, etc.)

### Local dev tooling
- [x] 🌐 Install Docker Desktop (or Docker Engine) locally — for a local Postgres instance during development. This is a one-time installer download, no account required.
- [x] 🌐 Install Node.js (LTS) and Python 3.11+ locally if not already present

---

## Phase 1 — Project Scaffolding

- [x] 💻 Create `backend/` and `frontend/` folders
- [x] 💻 Python virtualenv in `backend/`; install: `fastapi uvicorn[standard] langgraph langgraph-checkpoint-postgres langchain-openai pinecone psycopg[binary] python-dotenv langsmith unstructured`
- [x] 💻 Scaffold React app in `frontend/` (Vite)
- [x] 💻 Validate frontend scaffold with `npm install` and `npm run build`
- [x] 💻 `docker-compose.yml` with a local Postgres service for dev (mirrors the prod Postgres engine)
- [x] 💻 `.env.example` / `.env.local` listing every required variable:
  - `OPENAI_API_KEY`
  - `PINECONE_API_KEY`, `PINECONE_INDEX`
  - `LANGSMITH_API_KEY`, `LANGSMITH_TRACING=true`, `LANGSMITH_ENDPOINT`, `LANGSMITH_PROJECT`
  - `DATABASE_URL`
  - `AUTH_PASSWORD` (shared-password gate)
- [x] 💻 Fill in remaining real values from Phase 0 (Pinecone, DB, auth password) — never commit `.env.local`

---

## Phase 2 — Data Layer (Postgres)

- [x] 💻 Write `schema.sql`: `claims`, `check_ledger`, `audit_trail`, `episodic_facts` tables (per technical.md's memory-to-store mapping)
- [x] 💻 Apply `schema.sql` to local dev Postgres (via `docker compose up` + `psql`)
- [x] 💻 Confirm LangGraph's `PostgresSaver.setup()` creates its own checkpointer tables against the same DB (`backend/setup_checkpointer.py`; verified `checkpoints`, `checkpoint_blobs`, `checkpoint_writes`, `checkpoint_migrations` created in `claims_dev`)
- [x] 💻 Small `db.py` connection helper shared by the API and agent code (now pooled via `psycopg_pool.ConnectionPool`; `db.open_pool()`/`db.close_pool()` wired into FastAPI startup/shutdown)

---

## Phase 3 — RAG Ingestion Pipeline

- [ ] 🌐/💻 Source or author sample policy & regulation documents (Word/PDF). **This is a content-authoring task, not code** — write/collect these in Word or Google Docs outside VS Code, then drop the files into a `policy_docs/` folder in the repo.
- [ ] 💻 Ingestion script: `unstructured` parse → custom clause-boundary chunker (per requirements.md §9) → embed via `text-embedding-3-small` → upsert to Pinecone
- [ ] 💻 Run ingestion once against the Pinecone index created in Phase 0
- [ ] 💻 Retrieval function: query → top **k=20** → GPT rerank → relevance-floor check → top **3** (or zero, per requirements.md §9)
- [ ] 💻 Manual smoke test: run one sample query, confirm sensible results + citations come back

---

## Phase 4 — Tools & Agent Core (LangGraph)

- [x] 💻 **Claim taxonomy defined** — `billing_dispute` / `fraud` claim types, 4 required checks each, each check mapped to the tool(s) that resolve it and its PASS/FAIL semantics documented. `backend/agent/checks.py` (`REQUIRED_CHECKS`, `compute_decision`); full writeup in technical.md §4.

- [x] 💻 **Tool functions implemented** (requirements.md §8) — `backend/agent/tools.py`:
  - Grounding: `lookup_transaction`, `lookup_account_profile`, `lookup_access_logs` (query the new fixture tables)
  - Computation: `check_duplicate_charge`, `check_transaction_anomaly`, `check_dispute_window` (pure date math)
  - Retrieval: `search_policy` — wired to the **real** Pinecone index (`claims-policy-corpus`), not stubbed. Top-k=20 → relevance-floor filter → top-3, per requirements.md §9. Since Phase 3 hasn't ingested any documents yet, the index has 0 vectors, so it currently — correctly — returns zero results rather than a fabricated match.
  - `ask_human` — suspends the run via LangGraph `interrupt()`; takes a `check_name` so the human's yes/no answer can close that specific check (requirements.md §6's "only tool- or human-verified facts may close a check").
  - `write_determination` — LLM-callable, but carries no decision payload; calling it only triggers the deterministic ledger-derived decision in `finalize_node`, never asserts an outcome itself.
  - **Fixed during review**: `search_policy` originally returned only the top-3 results to the caller, and the audit-trail log used that same trimmed value — so the full 20-candidate list + scores was never actually recorded, contradicting requirements.md §9 / technical.md §3 ("full retrieval detail ... logged to the audit trail, not just the top 3"). Fixed: the tool now returns the full candidate list, `graph.py`'s `act_observe_node` audit-logs it in full, and only strips `candidates` back out of the copy shown to the model (so the LLM's context doesn't balloon with clauses it already discarded). Verified via a re-run: `audit_trail.payload->'result'` now carries `filter` and the full `candidates` array for every `search_policy` call.

- [x] 💻 **Synthetic data generator** (technical.md's Synthetic Data row) — `backend/generate_synthetic_data.py`. GPT (`gpt-4.1`, JSON-object mode) generates `account_profile` / `transactions` / `access_logs` per hand-authored scenario narrative; an automated `expect`-block check (standing, amount/location anomaly, presence of a risk-flagged access-log entry near the disputed transaction) replaces manual eyeballing as the "review against intended outcome" step. One scenario defined so far: `ACC-9001`, `fraud`, disputed transaction `TXN-7001`.
- [x] 💻 **Fixture data loaded** into the new `transactions` / `access_logs` / `account_profiles` tables for `ACC-9001` (7 transactions, 3-4 access-log events incl. one risk-flagged, one account profile).

- [x] 💻 **LangGraph agent graph built** — `backend/agent/graph.py`. `init` (loads episodic facts, seeds the check ledger, auto-resolves `duplicate_charge_check` when not applicable to the claim's stated reason) → `think` (`ChatOpenAI(model="gpt-4.1")`, `tool_choice="required"` so every turn calls a tool) → `act_observe` (executes tool call(s), maps results to check-ledger updates per the rules in technical.md §4, writes `audit_trail`) → conditional routing back to `think` or to `finalize`. Termination matches requirements.md §5 exactly: any FAIL → deny (short-circuit), all PASS → approve, iteration ≥ 12 or 5 no-progress iterations or human-question budget (3) exhausted → inconclusive with a stated reason. `PostgresSaver` checkpointer wired in via `build_graph(checkpointer)`.
- [x] 💻 **Episodic memory read/write helpers** — `backend/agent/episodic.py` (`get_facts`, `upsert_fact`), keyed lookup against `episodic_facts` as designed in technical.md §2. Wired into `init_node` (read) and `act_observe_node` (write, after `account_standing`/`account_red_flags`-relevant grounding calls).

- [x] 💻 **Smoke test** — `backend/smoke_test_agent.py`, run against the hand-picked `ACC-9001` fraud claim, outside the API layer.
  - First run surfaced a real agent-reasoning bug: the model passed the claim's `filed_at` instead of the disputed transaction's `occurred_at` into `lookup_access_logs`, searched the wrong time window, found nothing, and the run incorrectly landed `deny`. Fixed by tightening the tool docstring and the system prompt to name `lookup_transaction` as the source of the real timestamp. Re-ran clean.
  - Final result: `inconclusive`, reason `policy_liability_rule` unresolved. `account_red_flags`, `transaction_pattern_anomaly`, and `system_access_log_check` all resolved correctly (PASS) from the synthetic data; `policy_liability_rule` is `BLOCKED` because Pinecone has 0 vectors — the correct, honest outcome pending Phase 3, not a bug (requirements.md §9's "no matching policy found is a valid outcome").
  - `ask_human` interrupt/resume verified in a separate standalone check: paused mid-graph, then resumed against a **freshly constructed** graph/checkpointer instance (simulating a process restart) and produced the correct resumed state — confirms the §13 resumability requirement holds end-to-end, decoupled from whether the LLM happens to choose `ask_human` on a given run.

**Not yet wired to the API**: `backend/worker.py` (used by `POST /claims`) still runs the Phase-1 placeholder, not this graph — that swap is Phase 5 work.

### Gaps found auditing against `Capstone Claim Project v2.drawio` (Phase 4 scope)

- **Retrieval tool scope is narrower than the diagram.** The diagram's Retrieval box (now) lists "claim/dispute history · policy search"; only policy search (`search_policy`) exists in code. "Claim/dispute history" is effectively covered by the Grounding tools instead (`lookup_transaction`/`lookup_account_profile` hit Postgres directly rather than a semantic-search retrieval path) — not treated as a gap, just a different tool category than the diagram implies.
- **Resolved: project domain is card-transaction billing/fraud disputes, not healthcare claims.** requirements.md, technical.md, and the drawio previously carried leftover healthcare-claims boilerplate (NPI, prior authorization, eligibility) alongside the actual banking-flavored content (ATM transactions, Check claims). Confirmed with the user and scrubbed: `requirements.md` §7/§8 and `technical.md` (Architecture Components, Memory-to-store mapping, §4) now say "account/cardholder" instead of "NPI/member", and the Retrieval/Grounding/Computation tool descriptions match what's actually built (claim/dispute history + policy search; transaction evidence + account/cardholder verification; date math + duplicate-charge detection + transaction-pattern anomaly scoring). Diagram boxes for Retrieval, Grounding, Computation, and the episodic-memory cylinder updated to match.
- **Termination note said "3 no-progress iterations"**, conflicting with requirements.md §5 / technical.md §4 / the actual code (5). Resolved with the user: **5 is correct**; the drawio note has been corrected to match.
- **Episodic-memory hydration is attributed to the Retrieval tool in the diagram** ("hydrate / write facts" edge from Retrieval to episodic memory); the implementation instead writes episodic facts from `act_observe_node` after any grounding tool call touching `account_standing`/`account_red_flags`. Functionally equivalent (episodic read/write both happen), just a different attribution of *which* tool triggers it — not treated as a gap, noted for accuracy.

---

## Phase 5 — Orchestrator & API (FastAPI)

- [x] 💻 Endpoint: `POST /claims` (implemented)
- [ ] 💻 Endpoints: `GET /claims/{id}`, `GET /claims/{id}/questions`, `POST /claims/{id}/answer`, `GET /claims/{id}/decision`
- [x] 💻 Wire claim submission to `BackgroundTasks` (implemented — currently runs the placeholder `worker.run_claim_agent`; swap in the real LangGraph agent once Phase 4 lands)
- [ ] 💻 Shared-password auth middleware on the API
- [ ] 💻 End-to-end local test via curl/HTTP: submit → poll status → answer a question if one comes up → see final decision

---

## Phase 6 — Frontend (React)

- [ ] 💻 Claim submission form
- [ ] 💻 Claim list / status view (polls the backend — per the `ask_human` channel decision)
- [ ] 💻 Question/answer UI for `ask_human`
- [ ] 💻 Decision view: Approve/Deny/Inconclusive + citations + check-ledger breakdown
- [ ] 💻 Password-gate screen
- [ ] 💻 End-to-end test in-browser against the local backend

---

## Phase 7 — Observability & Audit

- [ ] 💻 Wire LangSmith tracing using the Phase 0 credentials
- [ ] 💻 Confirm `audit_trail` rows are written for every tool call, retrieval detail, and final determination (requirements.md §11)
- [ ] 💻 Manual check: pull up one LangSmith trace and the corresponding `audit_trail` rows side by side — confirm they tell the same story

---

## Phase 8 — Evaluation (10 test claims)

- [ ] 💻 Design 10 claims spanning claim types + evidence-completeness levels, each with a predetermined expected outcome (requirements.md §12) — write these out (e.g. a markdown table) before generating synthetic evidence for them
- [ ] 💻 Generate synthetic evidence per claim (Phase 4 generator)
- [ ] 💻 Jupyter notebook: run all 10 through the agent, compare actual vs. expected decision + check trace
- [ ] 💻 Fix discrepancies; re-run until the eval set passes, or document known gaps

---

## Phase 9 — Deployment (your Ubuntu server)

- [ ] 🌐 SSH into the server
- [ ] 🌐 Install system packages: Python 3.11+, Node.js/npm, PostgreSQL server, Nginx, git
- [ ] 🌐 Create a Postgres DB + user on the server; apply `schema.sql`; note the connection string
- [ ] 🌐 Get the code onto the server (`git clone`, or `scp` if not using git)
- [ ] 🌐 Create the server-side `.env` with real production values (OpenAI/Pinecone/LangSmith keys, prod `DATABASE_URL`, `AUTH_PASSWORD`) — copied manually, never committed
- [ ] 🌐 `npm run build` the React app; point Nginx at the static output
- [ ] 🌐 Create a systemd unit for the FastAPI app (uvicorn) so it restarts on crash/reboot
- [ ] 🌐 Configure Nginx as a reverse proxy: static frontend + `/api` → FastAPI (uvicorn)
- [ ] 🌐 `ufw allow` only what's needed (80, 443, OpenSSH) — nothing else should be open to the internet
- [ ] 🌐 (Optional) Point a domain at the server + get a TLS cert via certbot; otherwise access over HTTP via the server's IP
- [ ] 🌐 Run the Pinecone ingestion script once against production (same index, or a separate prod index for dev/prod separation)
- [ ] 🌐 Smoke test the deployed URL end-to-end

---

## Phase 10 — Capstone Wrap-up

- [ ] 💻 Record/prepare a demo walkthrough referencing requirements.md and technical.md
- [ ] 💻 Confirm technical.md and the `.drawio` diagram still match what was actually built; update if implementation diverged
- [ ] 💻 Write up known limitations / follow-ups (e.g., multi-user auth, CI-based test harness, dedicated reranker)
