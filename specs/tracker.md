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
  - Computation: `check_duplicate_charge`, `check_transaction_anomaly` (pure date math; a third tool, `check_dispute_window`, was added here and then removed during Phase 5 — see the Phase 5 bug writeup below)
  - Retrieval: `search_policy` — wired to the **real** Pinecone index (`claims-policy-corpus`), not stubbed. Top-k=20 → relevance-floor filter → top-3, per requirements.md §9. Since Phase 3 hasn't ingested any documents yet, the index has 0 vectors, so it currently — correctly — returns zero results rather than a fabricated match.
  - `ask_human` — suspends the run via LangGraph `interrupt()`; takes a `check_name` so the human's yes/no answer can close that specific check (requirements.md §6's "only tool- or human-verified facts may close a check").
  - `write_determination` — LLM-callable, but carries no decision payload; calling it only triggers the deterministic ledger-derived decision in `finalize_node`, never asserts an outcome itself.
  - **Fixed during review**: `search_policy` originally returned only the top-3 results to the caller, and the audit-trail log used that same trimmed value — so the full 20-candidate list + scores was never actually recorded, contradicting requirements.md §9 / technical.md §3 ("full retrieval detail ... logged to the audit trail, not just the top 3"). Fixed: the tool now returns the full candidate list, `graph.py`'s `act_observe_node` audit-logs it in full, and only strips `candidates` back out of the copy shown to the model (so the LLM's context doesn't balloon with clauses it already discarded). Verified via a re-run: `audit_trail.payload->'result'` now carries `filter` and the full `candidates` array for every `search_policy` call.

- [x] 💻 **Synthetic data generator** (technical.md's Synthetic Data row) — `backend/generate_synthetic_data.py`. GPT (originally `gpt-4.1`, swapped to `gpt-5.6-luna` in Phase 5 — see below; JSON-object mode) generates `account_profile` / `transactions` / `access_logs` per hand-authored scenario narrative; an automated `expect`-block check (standing, amount/location anomaly, presence of a risk-flagged access-log entry near the disputed transaction) replaces manual eyeballing as the "review against intended outcome" step. One scenario defined so far: `ACC-9001`, `fraud`, disputed transaction `TXN-7001`.
- [x] 💻 **Fixture data loaded** into the new `transactions` / `access_logs` / `account_profiles` tables for `ACC-9001` (7 transactions, 3-4 access-log events incl. one risk-flagged, one account profile).

- [x] 💻 **LangGraph agent graph built** — `backend/agent/graph.py`. `init` (loads episodic facts, seeds the check ledger, auto-resolves `duplicate_charge_check` when not applicable to the claim's stated reason) → `think` (originally `ChatOpenAI(model="gpt-4.1")`, swapped to `gpt-5.6-luna` in Phase 5 — see below; `tool_choice="required"` so every turn calls a tool) → `act_observe` (executes tool call(s), maps results to check-ledger updates per the rules in technical.md §4, writes `audit_trail`) → conditional routing back to `think` or to `finalize`. Termination matches requirements.md §5 exactly: any FAIL → deny (short-circuit), all PASS → approve, iteration ≥ 12 or 5 no-progress iterations or human-question budget (3) exhausted → inconclusive with a stated reason. `PostgresSaver` checkpointer wired in via `build_graph(checkpointer)`.
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

- [x] 💻 **Real agent wired into the API** — `backend/worker.py` no longer runs the Phase-1 placeholder. `run_claim_agent(claim_id)` fetches `claim_type`/`claim_payload` from Postgres, sets `status='processing'`, and drives `backend/agent/graph.py`'s compiled graph (`thread_id = claim_id`, `PostgresSaver` checkpointer) via `graph.invoke(...)`. A new `resume_claim_agent(claim_id, answer)` resumes a paused run via `graph.invoke(Command(resume=answer), config=...)`. Either call may return with `__interrupt__` (agent called `ask_human`) instead of a finished run; `_handle_graph_result` catches that and sets `status='awaiting_input'` + `pending_question` — otherwise `finalize_node` already wrote the decision itself, nothing left to do.
- [x] 💻 **Endpoints implemented** — `backend/main.py`:
  - `GET /claims/{id}` — claim row + full check-ledger detail
  - `GET /claims/{id}/questions` — `{"pending": false}` normally, `{"pending": true, "question": {...}}` while `status='awaiting_input'` (the `ask_human` tool's `{question, check_name}` payload)
  - `POST /claims/{id}/answer` — validates the claim is actually `awaiting_input` (409 otherwise), flips it back to `processing`, clears `pending_question`, and hands off to `worker.resume_claim_agent` via `BackgroundTasks` so the HTTP response returns immediately
  - `GET /claims/{id}/decision` — status/decision/decision_reason + full check ledger
- [x] 💻 **Shared-password auth middleware** — `backend/main.py`, `HTTPBearer` + a `require_auth` dependency checking `Authorization: Bearer <AUTH_PASSWORD>`, applied via an `APIRouter(dependencies=[Depends(require_auth)])` wrapping every `/claims*` route. `/` (health check) stays open. Verified: no header → 401, wrong password → 401, correct password → 200. Startup now also fails fast with `RuntimeError` if `AUTH_PASSWORD` isn't set, matching `db.py`'s existing pattern for `DATABASE_URL`.
- [x] 💻 **New DB column**: `claims.pending_question JSONB`, added to `schema.sql` and applied to the local dev DB via `ALTER TABLE` (existing `CREATE TABLE IF NOT EXISTS` doesn't retrofit columns onto an already-created table).
- [x] 💻 **End-to-end curl/HTTP test** — full server run via `uvicorn`, exercised with `curl` (auth header pulled from `.env.local` into a shell variable, never printed):
  1. Re-ran the Phase 4 `ACC-9001` fraud claim through `POST /claims` for real over HTTP: polled `GET /claims/{id}` through `pending → processing → completed`, then `GET /claims/{id}/decision` — reproduced the exact same result as the Phase 4 direct-graph smoke test (`inconclusive` / `policy_liability_rule` unresolved; the other 3 checks PASS).
  2. Built a second scenario specifically to exercise the `ask_human` → `/answer` path over real HTTP (a `billing_dispute` claim against an account with a transaction but no `account_profiles` row, so `account_standing` has no tool path to resolution): the agent correctly asked *"Is the account in good standing...?"* targeting `check_name: account_standing`, `GET /claims/{id}/questions` surfaced it, `POST /claims/{id}/answer` with `{"answer": "yes"}` resumed the run in the background, and it completed with `account_standing: PASS (human_answer: "yes")` and an overall `approve` decision. Confirms the API-level resume path works end-to-end, not just the graph-level mechanism proven in Phase 4.
  3. Confirmed unauthenticated and wrong-password requests both get `401`.

### Bug found and fixed during the end-to-end test: ungrounded `policy_dispute_window`

The `ask_human` test run above (step 2) also resolved `policy_dispute_window` to **PASS** with `window_days: 60` — surprising, since Pinecone has 0 vectors. The audit trail showed why: the model called `check_dispute_window(filed_at, transaction_occurred_at, window_days=60)` directly, **never calling `search_policy` at all**, supplying `60` from its own training knowledge (a plausible real-world dispute-window number) rather than a retrieved citation. That's exactly the failure mode requirements.md §9's grounding requirement exists to prevent — a policy-derived check closed on the model's prior knowledge, not a checkable fact.

Root cause: `check_dispute_window` took `window_days` as a free LLM-supplied argument with no link back to an actual retrieval result, so nothing stopped the model from inventing one instead of retrieving it (or honestly leaving the check BLOCKED when retrieval comes back empty).

Fix: removed `check_dispute_window` from the tool layer entirely (`backend/agent/tools.py`). `policy_dispute_window` now closes exactly like `policy_liability_rule` already did — BLOCKED if `search_policy` returns zero candidates, PASS (citing the retrieved clause) if it returns any — so a retrieval-only check can now *only* close via an actual retrieval hit. `backend/agent/graph.py`'s `_derive_check_updates` and `specs/technical.md` §4 updated to match. Re-verified over HTTP with a fresh claim: `policy_dispute_window` now correctly resolves `BLOCKED` (not a fabricated PASS) while Pinecone remains empty.

Deferred, not fixed: a real day-count comparison against the retrieved clause's actual stated window is future Phase 3 work (needs ingestion to tag policy chunks with structured metadata like `window_days` to compute against) — documented in technical.md §4 rather than built now.

Also fixed alongside this: `backend/agent/graph.py`'s model binding now sets `parallel_tool_calls=False`. Requirements.md §5 step 2 already specifies one action per Act step; enforcing it in code also closes a real LangGraph hazard where, if a turn's tool calls included e.g. a DB-writing tool *and* `ask_human` together, resuming after the pause would re-run the whole node from the top and re-execute the earlier tool's side effects (duplicate `audit_trail` rows). With exactly one tool call per turn, `ask_human` (when chosen) has no side effects ahead of it to duplicate.

### LLM swapped: `gpt-4.1` → `gpt-5.6-luna`

At the user's request, both `backend/agent/graph.py` (agent's Think step) and `backend/generate_synthetic_data.py` (synthetic data generation) now call `gpt-5.6-luna` instead of `gpt-4.1`. Verified live against the OpenAI API (`client.models.list()`) rather than assumed — the account has `gpt-5.6-luna`, `gpt-5.6-sol`, and `gpt-5.6-terra`; no `-pro` variant exists for the 5.6 tier (unlike 5.5/5.4/5.2/5, which do have `-pro` variants).

Two real integration issues surfaced getting it working, both fixed:

1. **Function tools + reasoning aren't supported together on `/v1/chat/completions`.** `gpt-5.6-luna` is a reasoning model; binding tools via the default Chat Completions endpoint errors with `"Function tools with reasoning_effort are not supported... use /v1/responses or set reasoning_effort to 'none'"`. Setting `reasoning_effort="none"` would work but defeats the point of using a reasoning model. Fixed by setting `use_responses_api=True` on `ChatOpenAI`, which routes through `/v1/responses` and keeps reasoning intact while still supporting tool calls. Re-ran the full smoke test and the HTTP `ask_human`/`/answer` end-to-end test (fresh account, no profile row) against the swapped model — same correct behavior as `gpt-4.1`: the previously-fixed `policy_dispute_window` grounding bug stayed fixed (resolved `BLOCKED`, not a fabricated pass), interrupt/resume through the real API worked, decisions matched expectations. Took noticeably more tool-call iterations and wall-clock time per call than `gpt-4.1` (visible reasoning latency), still well within the 12-iteration cap.
2. **Reasoning models reject any non-default `temperature`.** Both the agent (`temperature=0`, for deterministic decisioning) and the data generator (`temperature=0.4`, for variety across generated scenarios) previously set an explicit temperature. `gpt-5.6-luna` returns `400 Unsupported value: 'temperature' does not support ... Only the default (1) value is supported` on raw API calls — confirmed on both `/v1/chat/completions` and `/v1/responses` directly. Oddly, `langchain_openai`'s `ChatOpenAI` was **silently dropping** `temperature=0` rather than raising when `use_responses_api=True`, which would have been misleading left in the code. Removed the `temperature` argument from both call sites with a comment explaining why; determinism of the *decision* itself is unaffected since that's still computed from the check ledger in code (requirements.md §6), never sampled from the model.

---

## Phase 6 — Frontend (React)

- [x] 💻 **API surface extended for the frontend** — `backend/main.py`: added `GET /claims` (list, most-recent-first; not in the original Phase 5 endpoint list, added because the list view had no other way to discover claims that exist server-side) and `CORSMiddleware` (`localhost:5173` → `localhost:8000` for local dev; Phase 9's Nginx setup serves both same-origin in prod, so this is dev-only).
- [x] 💻 **Password-gate screen** — `frontend/src/components/PasswordGate.jsx`. Stores the password in `sessionStorage` (cleared on tab close, not a long-lived local credential); `frontend/src/api.js`'s `request()` wrapper attaches it as `Authorization: Bearer <password>` on every call and clears it + surfaces a re-auth prompt on any `401`.
- [x] 💻 **Claim submission form** — `frontend/src/components/ClaimForm.jsx`. Claim type (fraud/billing_dispute), account ID, disputed transaction ID, reason (dropdown covering `duplicate_charge` so that check's real computation path is reachable from the UI, not just "not applicable"), filed-at timestamp.
- [x] 💻 **Claim list / status view** — `frontend/src/components/ClaimList.jsx`. Polls `GET /claims` every 3s independently of whichever claim is selected; status/decision badges with a pulse indicator while a claim is still in-flight (`pending`/`processing`/`awaiting_input`).
- [x] 💻 **Question/answer UI for `ask_human`** — `frontend/src/components/ClaimDetail.jsx`. When `status === 'awaiting_input'`, shows the pending question + which check it resolves, with Yes/No buttons plus a free-text fallback wired to `POST /claims/{id}/answer`.
- [x] 💻 **Decision view** — same component: Approve/Deny/Inconclusive banner with the reason, plus an expandable check-ledger list (click a check to see its full detail JSON, including citations from `search_policy` when present).
- [x] 💻 **End-to-end browser test** — no project skill existed yet for launching this app, so set up a one-off Playwright driver (isolated npm project under the scratchpad, not added to `frontend/package.json`) since `chromium-cli` wasn't available in this environment. Started the real `uvicorn` + `vite dev` servers and drove headless Chromium against `localhost:5173`:
  1. Password gate accepted the real `AUTH_PASSWORD` from `.env.local`.
  2. Submitted a `fraud` claim for `ACC-9001`/`TXN-7001` through the form; it appeared in the claim list and the status badge progressed `pending → processing`.
  3. This run, the agent (now on `gpt-5.6-luna`, see below) hit `policy_liability_rule` BLOCKED (empty Pinecone) and — correctly, per requirements.md §5/§10's "last resort" design — escalated to `ask_human` rather than giving up immediately. The question box rendered correctly (question text + which check it resolves); clicked "Yes".
  4. Run resumed and completed: decision box showed **"Approved — All required checks passed"**; expanded all 4 check rows and confirmed each renders its full detail JSON, including `policy_liability_rule` closing on `{"human_answer": "yes"}` — the human-verified-fact closure path (requirements.md §6) working correctly through the actual UI, not just the API.
  5. Confirmed the claim list's independent poll cycle self-corrected the sidebar's status badge to "Completed" a few seconds after the detail panel already showed it — proves list and detail poll independently rather than one silently depending on the other.
  6. Zero browser console errors across the whole run (`console --errors` equivalent checked after every step).
  
  Test claim data cleaned up from the dev DB afterward. No project skill was captured for this (per the `run` skill's guidance, only worth doing if it "just worked" without setup — this needed installing Playwright + downloading Chromium from scratch, so a `/run-skill-generator` pass would be worthwhile before the next frontend change needs the same verification).

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
