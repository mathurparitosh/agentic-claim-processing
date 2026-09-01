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

### Qdrant (semantic memory / policy corpus)
**Superseded Pinecone here — see Phase 3.** Original Pinecone setup (sign up, create a
`claims-policy-corpus` index, generate an API key) is no longer part of the live stack.
- [x] 🌐 Sign up / create a cluster at Qdrant Cloud
- [x] 🌐 Generate an API key
- [x] 🌐 Record the cluster URL — goes in `.env` as `QDRANT_URL`/`QDRANT_API_KEY`; collection (`claims-policy-corpus`, 1536-dim/cosine to match `text-embedding-3-small`) is created automatically by `scripts/ingest_policy_corpus.py` on first run, not manually

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
  - `QDRANT_URL`, `QDRANT_API_KEY`, `QDRANT_COLLECTION`
  - `LANGSMITH_API_KEY`, `LANGSMITH_TRACING=true`, `LANGSMITH_ENDPOINT`, `LANGSMITH_PROJECT`
  - `DATABASE_URL`
  - `AUTH_PASSWORD` (shared-password gate)
- [x] 💻 Fill in remaining real values from Phase 0 (Qdrant, DB, auth password) — never commit `.env.local`

---

## Phase 2 — Data Layer (Postgres)

- [x] 💻 Write `schema.sql`: `claims`, `check_ledger`, `audit_trail`, `episodic_facts` tables (per technical.md's memory-to-store mapping)
- [x] 💻 Apply `schema.sql` to local dev Postgres (via `docker compose up` + `psql`)
- [x] 💻 Confirm LangGraph's `PostgresSaver.setup()` creates its own checkpointer tables against the same DB (`backend/setup_checkpointer.py`; verified `checkpoints`, `checkpoint_blobs`, `checkpoint_writes`, `checkpoint_migrations` created in `claims_dev`)
- [x] 💻 Small `db.py` connection helper shared by the API and agent code (now pooled via `psycopg_pool.ConnectionPool`; `db.open_pool()`/`db.close_pool()` wired into FastAPI startup/shutdown)

---

## Phase 3 — RAG Ingestion Pipeline

- [x] 🌐/💻 Source or author sample policy & regulation documents. `docs/files/*.md` — 5 rail-specific policies (ACH, CCD/credit card, DBD/debit card, ZEL/P2P, FRD/fraud) plus a corpus index describing the intended chunk structure, 101 numbered provisions total. Markdown rather than the originally-planned Word/PDF, and already present in the repo before this phase — not authored as part of checking this off.
- [x] 💻 **Vector store migrated from Pinecone to Qdrant** (2026-08-16, at the user's request). Embeddings unchanged (`text-embedding-3-small`, 1536-dim, cosine) — only the store/query client swapped, so this was a low-risk change, not a reranker/embedding-model redesign. `backend/agent/tools.py`: `_pinecone_index_client()` → `_qdrant()`; `search_policy` now calls `QdrantClient.query_points(..., query_filter=Filter(claim_type=...))` instead of `index.query(...)`. `pinecone` dropped from `backend/requirements.txt`, `qdrant-client` added. `PINECONE_API_KEY`/`PINECONE_INDEX` removed from `.env.example`/`.env.local`; `QDRANT_URL`/`QDRANT_API_KEY`/`QDRANT_COLLECTION` added. requirements.md/technical.md's Pinecone references updated to Qdrant (technical.md's Phase 4/5 status notes below keep "Pinecone" where they're narrating what was actually true at that past point in time).
- [x] 💻 Ingestion script: `scripts/ingest_policy_corpus.py`. Real clause-boundary chunker (requirements.md §9) — one chunk per `###`/`####` markdown heading (each is a single numbered provision, e.g. `FRD-2.1`), not the naive paragraph-split placeholder from an earlier throwaway script (`upload_markdown_to_qdrant.py`, now deleted). Parses the fixed-order `**Effective:**`/`**Applies to:**`/`**Cross-references:**`/`**Regulatory basis:**` lines under each heading into payload metadata and strips them from the embedded text; prepends the section heading path to the clause body instead (`docs/files/00_CORPUS_INDEX.md`'s own stated guidance — heading-path text retrieves better than the bare clause). Each chunk tagged `claim_type: billing_dispute` (ACH/CCD/DBD/ZEL) or `fraud` (FRD) for `search_policy`'s filter. Point IDs are `uuid5(doc_id:citation)`, so re-running is idempotent (upsert, not duplicate).
- [x] 💻 Run ingestion once against the Qdrant collection (`claims-policy-corpus`, created automatically on first run). 101 parsed clauses (81 `billing_dispute` + 20 `fraud`) — matches the corpus index's stated "Active provisions: 101" exactly (105 total minus 4 superseded versions, correctly excluded by the chunker).
- [x] 💻 Retrieval function: query → top **k=20** → relevance-floor check → top **3** (or zero, per requirements.md §9). **Gap carried over from the original Pinecone implementation, not introduced by this migration**: `search_policy` has never actually called GPT to rerank the top-20 — despite technical.md's Reranker row describing "prompt GPT to score/reorder the top-20 candidates," the code has only ever sorted by raw cosine score and truncated to top-3. Not fixed here (out of scope for a vector-store swap); flagged for whoever picks this up next.
- [x] 💻 Manual smoke test: `search_policy.invoke(...)` run directly against live Qdrant for both claim types — e.g. "How long does a customer have to dispute an unauthorized ACH debit?" (`billing_dispute`) correctly top-matched `ACH-2.1` (score 0.684, "Consumer Unauthorized Debit Window"); "when must fraud claims be escalated to human review" (`fraud`) correctly top-matched `FRD-6.1` ("Mandatory Human Review"). Full agent smoke test (`python -m backend.smoke_test_agent`, same `ACC-9001` fraud scenario as Phase 4/5) re-run end-to-end: `policy_liability_rule` now resolves **PASS** citing real clauses (`FRD-4.2` account-takeover indicators, `FRD-2.4` automated-determination exclusions, `FRD-5.1` referral triggers) instead of the old BLOCKED-on-empty-index result — overall decision `approve`, all 4 checks PASS.

**Bug found and fixed during this migration: `RELEVANCE_FLOOR` was miscalibrated.** It was set to `0.75` back when the tool was first built, with no real data ever behind it to check the number against (Pinecone stayed empty through Phases 4 and 5). Once Qdrant had real embeddings, cosine scores from `text-embedding-3-small` showed genuinely relevant clauses landing ~0.55-0.68 and off-topic queries ~0.06-0.08 — `0.75` was silently discarding every correct match and would have made retrieval permanently return zero results even with a fully populated, correct index. Recalibrated to `0.5` (comfortable margin above the noise floor, below the relevant-match range) in `backend/agent/tools.py`.

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

### LLM provider made switchable: OpenAI ⇄ OpenRouter (2026-08-16)

At the user's request, the agent's Think-step model (`backend/agent/graph.py`) is no longer hardcoded to OpenAI. New module `backend/agent/llm.py` builds the model from `.env.local`'s `LLM_PROVIDER` (`openai`, the default, or `openrouter`), so switching providers is a one-line env change, no code edit or redeploy. `OPENAI_API_KEY`/`OPENAI_MODEL` and `OPENROUTER_API_KEY`/`OPENROUTER_MODEL`/`OPENROUTER_BASE_URL` all now live in `.env.local`/`.env.example` rather than any value being fixed in code. Scope: only the agent's reasoning LLM is switchable — `search_policy`'s embeddings stay pinned to OpenAI's `text-embedding-3-small` regardless of `LLM_PROVIDER` (switching that would break dimension/score compatibility with the already-ingested Qdrant collection), and `backend/generate_synthetic_data.py` (an offline dev tool, not part of the live agent) stays OpenAI-only.

Verified both paths against the real, running app rather than assumed:
- **`LLM_PROVIDER=openai`** (default): re-ran a claim end-to-end through the actual API after the refactor — same correct `approve` outcome as before, confirming the extraction into `llm.py` didn't change behavior.
- **`LLM_PROVIDER=openrouter`**, `OPENROUTER_MODEL=openrouter/free` (OpenRouter's own auto-router, restricted to free tool-calling-capable models — matches the working sample the user provided): first probed a single tool-calling request directly (confirms `tool_choice="required"` — which the whole agent design depends on, requirements.md §5 step 2 — is actually honored by whatever free model OpenRouter routes to, since this isn't documented/guaranteed across all providers). It correctly called `lookup_transaction` with the right args. Then ran a full claim end-to-end over real HTTP (`ACC-9002` duplicate-charge scenario): the agent correctly called `lookup_transaction`, `lookup_account_profile`, `check_duplicate_charge` (correctly resolving `duplicate_charge_check` PASS against the real TXN-2006/TXN-2007 duplicate), and `search_policy` (resolving `policy_dispute_window` PASS via Qdrant) — landing on the correct `approve` decision matching what `gpt-5.6-luna` would have produced. Confirms the whole tool-calling ReAct loop works unmodified with OpenRouter as the provider.

**Known limitation, not fixed**: OpenRouter's free tier is rate-limited (50 requests/day with no credit ever purchased on the account, 20 requests/minute) — a single claim run makes 5-8 LLM calls, so this is easy to exhaust well before running a full 10-claim Phase 9 evaluation set on it. Fine for occasional/demo use or as a zero-cost fallback; not a substitute for the OpenAI path if running the full eval suite. Left as `LLM_PROVIDER=openai` after testing (matches `.env.example`'s documented default) — the user can flip it back anytime.

---

## Phase 6 — Frontend (React)

- [x] 💻 **API surface extended for the frontend** — `backend/main.py`: added `GET /claims` (list, most-recent-first; not in the original Phase 5 endpoint list, added because the list view had no other way to discover claims that exist server-side) and `CORSMiddleware` (`localhost:5173` → `localhost:8000` for local dev; Phase 10's Nginx setup serves both same-origin in prod, so this is dev-only).
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

- [x] 💻 **Account/Transaction + Audit Trail tabs** (2026-08-16, requirements.md §11). Claim detail view split into three tabs (`frontend/src/components/ClaimDetail.jsx`): Checks (previous default view, unchanged), **Account & Transaction**, and **Audit Trail**.
  - Two new read-only endpoints in `backend/main.py`: `GET /claims/{id}/context` (looks up the account profile + disputed transaction from `claim_payload`'s `account_id`/`disputed_transaction_id` against the same `account_profiles`/`transactions` fixture tables the Grounding tools query — a display convenience, not a tool call, so it doesn't touch the check ledger) and `GET /claims/{id}/audit` (full `audit_trail` timeline for the claim, oldest first).
  - **Gap found and fixed while building this**: every `audit_trail` row ever written had `source = 'agent'` — including the claim's own submission and the human's answer to an `ask_human` question, both genuinely human-performed actions with no distinct audit row of their own (the human's answer text only showed up buried inside the *next* agent tool-call's payload). Requirements.md §11 now explicitly requires agent/human attribution on every entry, so this needed fixing, not just displaying: `backend/main.py`'s `create_claim` now logs a `claim_submitted` / `source: "human"` entry, and `answer_claim` now logs a `human_answer` / `source: "human"` entry, both via the existing `backend/agent/ledger.py:log_audit`. Verified over HTTP with a fresh claim: the timeline correctly opens with `human | claim_submitted` before `agent | run_started`.
  - Frontend polls `GET /claims/{id}/audit` alongside `GET /claims/{id}` on the same 2s cycle while the claim is active, so the Audit Trail tab updates live as the agent runs; `GET /claims/{id}/context` is fetched once per claim selection since account/transaction data doesn't change mid-run. Each audit row shows timestamp, event type, and an Agent/Human source pill, with the full JSON payload expandable on click (same interaction pattern as the existing check-ledger rows).
  - Verified over HTTP end-to-end (backend restarted, curl against both new endpoints) against a fresh `ACC-9001`/`TXN-7001` claim: `/context` returned the real account profile (Dana Ruiz, standing `good`) and transaction ($1,450.00, TechBuy Electronics, Phoenix AZ); `/audit` returned all 7 entries correctly ordered and sourced, ending in `agent | determination_written`. Browser-level verification not yet re-run (no Playwright driver currently set up in this session — see the note above).

- [x] 💻 **Two more synthetic accounts** (2026-08-16) — `ACC-9002` (Marcus Webb, `billing_dispute`, a same-merchant/same-amount duplicate charge — TXN-2006/TXN-2007, ~90 min apart, exercises `check_duplicate_charge`) and `ACC-9003` (Priya Nandakumar, `fraud`, same anomaly shape as `ACC-9001` but a different city/amount/merchant so the sample set isn't repetitive). Added as two more entries in `backend/generate_synthetic_data.py`'s `SCENARIOS` list — same LLM-generate-then-review pipeline as `ACC-9001`, not hand-written SQL. Added a `--accounts` filter flag to the script's CLI so a subset of scenarios can be (re)generated without touching the others' already-loaded data (running the full script unfiltered would have regenerated `ACC-9001` too, since the model has no seed/temperature control and each call samples fresh — see the Phase 5 LLM-swap notes above). First narrative draft asked for "6-10 transactions" per account (copied from `ACC-9001`'s wording) and generated 9 for `ACC-9002` on a dry run; tightened to "EXACTLY 7 transactions" and regenerated before loading, so all three accounts now have exactly 7 each.
- [x] 💻 **Account-ID autocomplete + transaction dropdown on the claim form** — `frontend/src/components/ClaimForm.jsx`. Two new endpoints in `backend/main.py`: `GET /accounts` (id + member name, all fixture accounts) and `GET /accounts/{id}/transactions` (that account's transactions). Account ID is now an `<input list>` bound to a `<datalist>` of real accounts (native browser autocomplete, no new dependency); once the typed value matches a known account, the disputed-transaction field switches from free text to a `<select>` populated from that account's real transactions (labeled `TXN-2007 — $54.18 Green Valley Grocers (Denver, CO)`), defaulting to the first one. Typing an account ID that isn't in the fixture data falls back to the original free-text transaction input, so submitting a claim against a not-yet-loaded account still works. Verified over HTTP: `GET /accounts` returns all 3 accounts; `GET /accounts/ACC-9002/transactions` returns its 7 transactions including the TXN-2006/TXN-2007 duplicate pair.

- [x] 💻 **Claims-list landing + in-app tab strip** (2026-08-17). New requirement from the user, changed the previous single-page sidebar+pane layout. Clarified: "new tab" means an **in-portal tab** (a tab strip inside the app, like an IDE/browser-tabs-within-a-page), not a real new browser tab — the user stays on the same browser tab throughout:
  1. On login, the first screen is the claims list (not today's combined form+list sidebar). Clicking a claim opens it as a new in-app tab alongside any others already open.
  2. A new **"Start Claim"** button (on the claims-list screen) opens a new in-app tab containing what today's left pane shows — the account/transaction/claim-type submission form (`ClaimForm`) — instead of that form living permanently in a sidebar.

  Current state this changes: `frontend/src/App.jsx` holds one `useState`-driven view — `app-sidebar` stacks `ClaimForm` + `ClaimList`, `app-main` shows `ClaimDetail` for whichever claim is `selectedClaimId`. No tab concept exists today (no browser tabs *or* in-app tabs) — this is a single always-visible sidebar+pane layout.

  Planned approach:
  - No routing library needed (no real navigation/URL/new-browser-tab involved — dropping the earlier `react-router-dom`/`sessionStorage` plan from this item, that was based on a misreading of "new tab"). All state stays client-side in-memory for the page's lifetime, same as today.
  - `App.jsx` gains a `tabs` array + `activeTabId` in state. Each tab is `{ id, kind: 'list' | 'detail' | 'new-claim', claimId? }`. A `list`-kind tab is created on login and is the landing view; treat it as unclosable (always at least the list tab available), matching "first screen after login is the claims list."
  - New `TabStrip` component renders one header per open tab (label + close `×`), clicking a header sets `activeTabId`; only the active tab's content is shown (others stay mounted but hidden, so in-flight polling on a `processing`/`awaiting_input` claim detail tab keeps running in the background rather than resetting when the user tabs away and back).
  - Clicking a claim row in `ClaimList` (which stays on the `list` tab): if a `detail` tab for that `claimId` is already open, just activate it (no duplicate tabs); otherwise open a new `detail` tab and activate it.
  - Clicking **"Start Claim"**: opens a new `new-claim` tab (renders `ClaimForm`) and activates it. Multiple `new-claim` tabs can coexist (starting more than one claim at once is fine) — no dedupe needed here, unlike claim-detail tabs.
  - **Open decision, defaulted for planning purposes, confirm before building**: on successful submit, the `new-claim` tab that submitted it converts in place into that claim's `detail` tab (closest to today's `handleSubmitted` behavior of immediately showing the new claim) rather than opening yet another tab or auto-closing back to the list.
  - `ClaimList`'s existing 3s poll (`GET /claims`) needs no changes — a claim submitted from a `new-claim` tab shows up in the list tab's next poll cycle same as today.
  - Layout/CSS (`frontend/src/index.css`): replace the current `app-sidebar` + `app-main` split with a full-width tab strip + full-width active-tab content area, since `ClaimDetail`/`ClaimForm` are no longer sharing horizontal space with a permanent sidebar.
  - Out of scope unless requested: persisting open tabs across a full page reload (a browser refresh will reset to just the `list` tab, same as losing any other in-memory SPA state today) and reflecting the active tab in the URL/browser history/back-button.
  - Re-run (or extend) the Phase 6 Playwright end-to-end flow to cover: login → land on claims list tab → click a claim → new in-app tab opens with that claim's detail, list tab still present → click a second claim → another in-app tab opens; clicking the first claim's tab again re-activates it rather than duplicating → click "Start Claim" → new in-app tab opens with the form → submit → confirm that tab converts to the new claim's detail and the list tab's poll picks up the new claim.

  **Built as planned above**, with the open decision resolved as recommended (submit converts the `new-claim` tab into that claim's `detail` tab in place). Implementation:
  - `frontend/src/components/TabStrip.jsx` (new) — renders tab headers (`Claims` / `New Claim` / `Claim <id prefix>`) with a close `×` on every tab except the permanent `list` tab.
  - `frontend/src/App.jsx` rewritten — `tabs` array (`{id, kind: 'list'|'detail'|'new-claim', claimId?}`) + `activeTabId` replace the old `selectedClaimId` state. `openClaimTab` dedupes against an already-open `detail` tab for that `claimId` rather than opening a second one; `openNewClaimTab` does not dedupe (multiple `New Claim` tabs can be open at once); `closeTab` falls back to the previous tab in the strip (or the list tab) when the active tab is closed, and is a no-op on the `list` tab (permanent, no close button rendered for it). Every tab's content stays mounted and is hidden with `display: none` rather than unmounted when inactive, so an in-flight `detail` tab keeps polling `GET /claims/{id}` / `GET /claims/{id}/audit` in the background while another tab is focused.
  - `frontend/src/components/ClaimList.jsx` — added the `Start Claim` button (`onStartClaim` prop) next to the "Claims" heading; the existing `selected` row highlight now keys off `openClaimIds` (claims that currently have an open `detail` tab) instead of a single `selectedClaimId`.
  - `frontend/src/index.css` — replaced `.app-sidebar`/`.app-main` with `.tab-strip`/`.tab-panel`; `ClaimForm`/`ClaimList` are no longer confined to a 340px column so both got a `max-width` for readability now that they render full-page.
  - `ClaimForm.jsx` and `ClaimDetail.jsx` needed no changes — both were already driven purely by props (`onSubmitted(claimId)` / `claimId`), so they slot into the new per-tab wrapper unchanged.
  - **Verified in a real browser**, not just `npm run build`: no project run-skill existed yet, so used `scripts/start.sh` (already in the repo — starts local Postgres via docker compose, then `uvicorn`/`vite dev`) plus a one-off Playwright driver in the scratchpad (same pattern as the original Phase 6 browser test; `chromium-cli` still isn't available in this environment). Drove the real app end-to-end:
    1. Logged in with the real `AUTH_PASSWORD` → landed directly on the `Claims` tab; confirmed the old `.app-sidebar` is gone and `.start-claim-btn` is present.
    2. Clicked "Start Claim" → a `New Claim` tab opened showing `ClaimForm`, `Claims` tab stayed open.
    3. Filled and submitted a real fraud claim (`ACC-9001`/`TXN-7001`) → the same tab converted in place to `Claim 97912f46` showing `ClaimDetail` (`Checks`/`Account & Transaction`/`Audit Trail` sub-tabs all rendered).
    4. Switched back to the `Claims` tab → the new claim appeared in the list (poll picked it up with no manual refresh).
    5. Clicked a claim row → its `detail` tab opened/activated, `Claims` tab remained open alongside it.
    6. Clicked back to `Claims` then re-clicked the same row → tab count stayed the same (2), confirming no duplicate tab was opened.
    7. Closed the active `detail` tab via its `×` → correctly fell back to the `Claims` tab.
    8. Zero browser console errors across the whole run.
  - Test claim (`97912f46-...`) created during this run cleaned up from the dev DB afterward (`DELETE FROM claims WHERE id = ...`; `check_ledger`/`audit_trail` rows cascade-deleted with it).

  **Follow-up tweak (2026-08-17, same day)**: moved the `Start Claim` button out of `ClaimList` and into `App.jsx`'s header, directly to the left of `Log out` (new `.app-header-actions` wrapper div so `justify-content: space-between` still keeps the title left / actions right) — it's a global action, not specific to the `Claims` tab's content, and clicking it now works from any tab, not just while `Claims` is active. `ClaimList` no longer takes an `onStartClaim` prop. Also changed `.claim-list` from `max-width: 640px` to `width: 100%` so claim rows fill the tab panel's full width instead of stopping short. Verified visually via the same Playwright setup: header renders `Start Claim` immediately left of `Log out`, and `.claim-list`'s rendered width now matches the tab panel's content width (only the panel's own padding accounts for the gap to the edge). No console errors.

  **Follow-up: per-claim summary pane (2026-08-17, same day)**. Each `Claim` tab's detail view now has a left-hand summary pane showing basic info at a glance — Account (ID + name), Transaction (reference, merchant, amount), and Dispute type — without needing to switch to the existing "Account & Transaction" tab (which stays as-is for the full detail: standing, opened date, dispute history count, fraud red flags, transaction location/channel/status). `frontend/src/components/ClaimDetail.jsx`: new `SummaryPane` subcomponent, sourced from data already being fetched — `context` (`GET /claims/{id}/context`, same call `ContextPanel` uses) for account/transaction, and `claim.claim_payload.reason` (the value chosen in `ClaimForm`'s `Reason` dropdown — `unauthorized_transaction`/`not_recognized`/`duplicate_charge`/`other`) for dispute type, which the API already returns on `GET /claims/{id}` but nothing previously surfaced in the UI. The claim-detail render now wraps in a `.claim-detail-layout` flex row: `SummaryPane` (fixed 220px) + the existing `.claim-detail` column (flexible). `frontend/src/index.css` adds `.claim-detail-layout`/`.claim-summary-pane`/`.summary-section`/`.summary-value`. No backend changes needed — both data sources were already in the API response, just not displayed. Verified in a real browser: opened a real `billing_dispute` claim, summary pane correctly showed `ACC-9001` / `Dana Ruiz` / `TXN-1004` / `Walgreens Pharmacy` / `$58.45` / `Unauthorized Transaction`, matching the claim's actual data; no console errors.

---

## Phase 7 — Multi-Agent Orchestration (Research / Decisioning) + On-Demand Recovery Agent

Built 2026-08-17. Architecture design in `technical.md` §5. Two independent pieces of
work, not three peer agents in one loop: the orchestrator graph is a refactor of the
default claim-processing path (Research + Decisioning sub-agents); the Recovery agent
is new, separate, on-demand functionality triggered per claim after a decision already
exists.

### Orchestrator graph (Research + Decisioning sub-agents)

- [x] 💻 Design the LangGraph node structure for the orchestrator — **one supervisor
  node routing between two sub-nodes** (`think_research` / `think_decisioning`, each
  its own LLM call bound to its own narrower toolset) inside a single graph, sharing
  one `act_observe` node and one checkpointer — not two separate subgraphs.
- [x] 💻 Built as `backend/agent/orchestrator.py` (new file). `backend/agent/graph.py`
  (the legacy single agent) is **completely unmodified** — `orchestrator.py` imports
  its shared, unmodified business-rule helpers (`_derive_check_updates`,
  `_format_checks`, `ClaimState`, `finalize_node`, the iteration caps) rather than
  duplicating them, so the check-ledger/decision rules can never drift between the two
  paths. `act_observe_node` and the two think-nodes are new code in `orchestrator.py`
  (couldn't be shared as-is — they needed the sub_agent-tagging/role-switching logic
  below), so there is some deliberate duplication of the tool-execution loop shape
  between the two files; the actual business rules inside it are shared via import.
- [x] 💻 Split the existing tool bindings: Research agent gets Grounding + Retrieval
  tools only (`lookup_transaction`, `lookup_account_profile`, `lookup_access_logs`,
  `search_policy`); Decisioning agent gets Computation tools
  (`check_duplicate_charge`, `check_transaction_anomaly`) + `ask_human` +
  `write_determination`.
- [x] 💻 Global iteration/no-progress/human-question counters shared across both
  sub-agents (not reset per sub-agent) — same termination rules as today
  (requirements.md §5), enforced across the two-role loop instead of one.
- [x] 💻 Final decision stays computed by the existing `compute_decision(check_ledger)`
  — `orchestrator.py` imports and reuses `graph.py`'s `finalize_node` directly,
  unchanged. Never asserted by either sub-agent (requirements.md §13's determinism
  requirement).
- [x] 💻 Audit trail: every `tool_call` entry now carries a `sub_agent`
  (`"research"`/`"decisioning"`) field alongside the existing `source: agent/human`
  field.
- [x] 💻 New env var `AGENT_MODE=orchestrator|legacy` (`.env.example`/`.env.local`,
  mirrors `LLM_PROVIDER`'s switch pattern) — orchestrator is the new default;
  `backend/worker.py`'s `_build_graph()` picks between `build_orchestrator_graph` and
  `graph.py`'s unmodified `build_graph` (the legacy path, kept as a fallback, not
  deleted).
- [x] 💻 New comparison smoke test, `backend/smoke_test_orchestrator.py` — runs every
  scenario in `backend/generate_synthetic_data.py` (`ACC-9001` fraud, `ACC-9002`
  billing_dispute/duplicate_charge, `ACC-9003` fraud) through **both** the legacy graph
  and the orchestrator graph and diffs decision + full check ledger. All three matched
  exactly after the bug fix below.

  **Bug found and fixed via this smoke test**: the first routing design handed off from
  Research to Decisioning only once every research-owned check left `UNKNOWN`
  (`PASS`/`FAIL`/`BLOCKED`) — but `account_standing` (and `account_red_flags`) can stay
  `UNKNOWN` forever with no research tool able to change that (`lookup_account_profile`
  returning "not found" never produces `BLOCKED`, just `UNKNOWN`). Tested against a
  claim with a deliberately hidden account profile: the orchestrator looped in Research
  for the full run and hit the *global* no-progress cap before Decisioning — and
  therefore `ask_human`, which only Decisioning owns — ever got a turn. Landed
  `inconclusive` instead of correctly escalating to a human, a real behavior regression
  vs. the legacy single agent (which has `ask_human` available immediately, no
  structural phase to get stuck in).

  Fixed in `orchestrator.py`'s `route_after_act`: Research now also hands off once its
  iteration budget runs out, not only once nothing is left `UNKNOWN`. The budget is
  `len(research-owned checks in this claim) + RESEARCH_ITERATION_BUFFER` (buffer = 2)
  — deliberately tight rather than generous, since `NO_PROGRESS_LIMIT` (5) is checked
  *before* the phase-handoff decision and is shared across both sub-agents; a loose
  budget burns most of that shared allowance in Research before Decisioning ever runs.
  Re-tested the same hidden-account-profile claim after the fix: Research handed off
  after 5 rounds, Decisioning correctly called `ask_human`
  (`"Is account ACC-9002 in good standing...?"`), the run paused, and resuming with
  `"yes"` (via a **freshly constructed** checkpointer/graph instance, simulating a
  process restart — same resumability check as the original Phase 4 test) completed
  correctly: `account_standing: PASS (human_answer: "yes")`, overall `approve`. Re-ran
  the 3-scenario comparison after the fix too — still all-match, the fix didn't
  perturb the claims that resolve cleanly through Research alone.

### Recovery agent (new, on-demand, not part of the orchestrator run)

- [x] 💻 New synthetic network-rules corpus: `docs/files/NWR_Network_Recovery.md` (13
  provisions — Visa/Mastercard/ATM reason codes, filing windows, evidence/package
  requirements, exclusions), same clause-heading format as the existing 5-rail corpus
  so the existing chunker parses it unmodified.
- [x] 💻 Ingested into the existing Qdrant collection (`claims-policy-corpus`) tagged
  `claim_type: network_recovery` — `scripts/ingest_policy_corpus.py`'s
  `CLAIM_TYPE_BY_DOC_ID` gained one entry (`"NWR": "network_recovery"`), no other
  ingestion-script changes needed. Re-running the script is idempotent (existing
  `uuid5`-keyed upsert), so this added exactly the 13 new `network_recovery` chunks
  without touching the 101 already-ingested `billing_dispute`/`fraud` ones. Corpus now
  114 chunks total.
- [x] 💻 New retrieval tool `search_network_policy` (`backend/agent/tools.py`) —
  parallel to `search_policy` but hardcoded to the `network_recovery` filter (no
  `claim_type` parameter needed, unlike `search_policy`, since there's only one such
  corpus). Deliberately **not** added to the orchestrator's `TOOLS`/`RESEARCH_TOOLS`/
  `DECISIONING_TOOLS` — it's exclusively for the Recovery agent's own direct use, never
  reachable from the main claim-processing loop.
- [x] 💻 New Recovery agent, `backend/agent/recovery.py` (`assess_recovery(claim_id)`)
  — **eligibility is LLM-judged, not a deterministic check-ledger closure**, per the
  deliberate, scoped exception in technical.md §5. Implemented as a single retrieval
  call + one `with_structured_output` LLM call (Pydantic `RecoveryAssessment` schema:
  `eligible`, `reasoning`, `network`, `reason_code`, `filing_deadline`,
  `evidence_summary`, `narrative`) — not a multi-turn tool-calling loop, since the task
  is a one-shot judgment, not an evidence-gathering process. `backend/agent/llm.py`
  refactored (`_build_base_model()` extracted, shared by `build_agent_model` and the
  new `build_structured_model`) rather than duplicating the provider-selection
  boilerplate. Verified live: `with_structured_output` works correctly against
  `gpt-5.6-luna` over the Responses API (`use_responses_api=True`) — this was the one
  genuinely uncertain integration point going in, confirmed rather than assumed.
- [x] 💻 New endpoint `POST /claims/{claim_id}/recovery` (`backend/main.py`) —
  code-gated to `decision IN ('approve', 'inconclusive')` (409 otherwise, matching the
  existing `answer_claim` pattern), 404 on an unknown claim id. Runs **synchronously**
  (not via `BackgroundTasks`) — a single retrieval + one LLM call is a few seconds,
  not a multi-minute loop, so there's no need for the polling pattern the main claim
  run uses; the response carries the full result directly. Writes one `audit_trail`
  entry (`event_type: recovery_assessment`) via the existing `ledger.log_audit` — no
  new table, no new read endpoint.
- [x] 💻 Frontend: `frontend/src/components/ClaimDetail.jsx` gained a "Check Recovery
  Eligibility" button inside the existing decision box, rendered only when
  `claim.decision` is `approve` or `inconclusive` (a `deny`'d claim never shows the
  button at all, not just a disabled one — mirrors the endpoint's gate). On click:
  calls the new endpoint, refetches the audit trail, and switches to the Audit Trail
  sub-tab so the result is immediately visible (same expand-to-see-full-JSON
  interaction as every other audit row — no new display component needed).
  `frontend/src/api.js` gained `checkRecoveryEligibility(claimId)`.
- [x] 💻 **Verified end-to-end in a real browser** (Playwright, same pattern as prior
  phases): submitted a real `billing_dispute`/`duplicate_charge` claim against
  `ACC-9002`'s known `TXN-2006`/`TXN-2007` duplicate pair, waited for it to resolve via
  the orchestrator (`Approved`), clicked "Check Recovery Eligibility," confirmed the
  view switched to Audit Trail and a `recovery_assessment` entry appeared showing a
  correctly-grounded result (network `Mastercard`, reason code `4834`, citing the
  actual retrieved `NWR-3.2`/`NWR-3.3` provisions, not a hallucinated answer). Zero
  console errors. Also verified over direct HTTP: 409 on a `deny`'d claim, 404 on an
  unknown claim id, 401 with no auth header.
- [x] 💻 Diagram (`Capstone Claim Project v2.drawio`) update — done. The single
  `agent` cell ("ReAct Agent (LangGraph)") is now a dashed boundary box
  ("Orchestrator Graph (LangGraph supervisor)") containing two child boxes,
  "Research Sub-Agent (Grounding + Retrieval tools)" and "Decisioning Sub-Agent
  (Computation + ask_human + write_determination)", with a small routing edge
  between them labeled "hand off once research-owned checks resolved or budget
  exhausted". Existing THINK/ACT/OBSERVE/ledger/audit/observability edges (e5-e9,
  e15) were left targeting the boundary cell (kept the id `agent`) rather than
  repointed to a specific sub-node — a documentation diagram, not a literal render,
  and the boundary-as-target reads cleanly. Added a new, visually separate "Recovery
  Agent (on-demand)" box (not inside the orchestrator boundary), with edges to
  `m_semantic` (labeled `search_network_policy (network_recovery filter)`), to
  `audit` (labeled `log_audit(recovery_assessment)`), and a dashed edge from
  `frontend` labeled "Check Recovery Eligibility → POST /claims/{id}/recovery
  (synchronous, not BackgroundTasks)" — not routed through the `orchestrator` box
  since the endpoint runs synchronously. `t_retrieval` and `m_semantic` updated
  Pinecone → Qdrant; `t_retrieval`'s "k=20→GPT rerank→top3" corrected to "k=20 →
  relevance floor (0.5) → top-3" (there was never a reranker — this was wrong before
  Phase 7 too, just never fixed). `observability` label dropped "Not wired up yet"
  now that LangSmith tracing is live. Canvas bumped from 850x1100 to 1250x950 to fit
  the new boundary/sub-nodes and Recovery Agent row without overlapping existing
  shapes. Verified with `python3 -c "import xml.etree.ElementTree as ET;
  ET.parse('specs/Capstone Claim Project v2.drawio')"` — parses clean.
- [x] 💻 `docs/c4-architecture.md` is now stale too (found while implementing, not
  previously flagged): its Level 3 component diagram and sequence diagram both
  described `graph.py`'s single-agent node structure (`init -> think -> act_observe
  -> ...`) as *the* agent architecture, which is no longer accurate now that the
  orchestrator is the default (`AGENT_MODE=orchestrator`). Fixed — see the `Diagram`
  entry below, which covers both docs.

### Diagram

- [x] 💻 `Capstone Claim Project v2.drawio` will fall out of sync with this once
  built (same situation as the Phase 4 gap-audit notes) — update it alongside
  implementation this time, not deferred to Phase 11 wrap-up. Updated (see the
  detailed bullet above); `docs/c4-architecture.md` updated alongside it in the same
  pass since it had drifted for the same underlying reason. Level 1/2 System
  Context/Container diagrams: dropped LangSmith's "not wired up yet (Phase 8)"
  framing (`.env.local` now has real `LANGSMITH_TRACING`/`LANGSMITH_API_KEY`/
  `LANGSMITH_ENDPOINT`/`LANGSMITH_PROJECT`, loaded via `backend/db.py`'s
  `load_dotenv()` before any LLM calls — auto-instrumented, no app code needed);
  added a Level-2 note on the Recovery agent's synchronous (non-BackgroundTasks)
  execution inside the same "API & Agent Backend" container. Level 3 gained
  `orchestratorC` (`backend/agent/orchestrator.py`) and `recoveryC`
  (`backend/agent/recovery.py`) components plus `search_network_policy` on
  `toolsC`; `graphC` relabeled "Agent Graph (legacy)" with its fallback role noted;
  `worker`'s description updated for `_build_graph()`'s
  `build_orchestrator_graph`/`build_graph` choice; `llmC` updated for
  `build_structured_model` (the `_build_base_model()` refactor); notes section
  expanded to explain that `orchestrator.py` imports `graph.py`'s
  `_derive_check_updates`/`_format_checks`/`ClaimState`/`finalize_node`/iteration
  caps rather than duplicating them (the important architectural fact — business
  rules are shared, only the tool-execution loop *shape* is duplicated), and that
  Recovery's `eligible` judgment is a deliberate, scoped exception to "`checks.py` is
  the only place a decision is computed" (LLM-judged, advisory, not a
  `compute_decision` run). Added `POST /claims/{id}/recovery` to the
  "endpoints not shown individually" list. Level 4: left the Think/Act/Observe
  sequence diagram's shape as-is (still accurate at this zoom — same
  `graph.invoke`/`Command(resume=...)`/checkpointing mechanics either way) and added
  a prose note clarifying "Think" now covers Research and Decisioning turns sharing
  that loop, plus a new short sequence diagram for the Recovery agent's separate
  synchronous one-shot flow (`POST /claims/{id}/recovery` → one retrieval + one
  structured LLM call → one `audit_trail` write → response, including the 409 gate).
  Top-of-file date bumped to 2026-08-17 with a one-line summary of what changed.

---

## Phase 8 — Observability & Audit

- [x] 💻 **Wire LangSmith tracing using the Phase 0 credentials** (2026-08-17). No
  application code needed — `LANGSMITH_TRACING=true`, `LANGSMITH_API_KEY`,
  `LANGSMITH_ENDPOINT` (`https://api.smith.langchain.com`), and
  `LANGSMITH_PROJECT=claim-assistant` were already present in `.env.local` from Phase 1,
  loaded via `backend/db.py`'s `load_dotenv()` (which every entrypoint imports before any
  LLM call runs). LangChain/LangGraph auto-instrument tracing purely from those env vars.
  Verified live, not just assumed: `langsmith.Client().read_project(project_name="claim-assistant")`
  round-tripped successfully against the real API using the configured key, confirming
  both the credentials are valid and the project exists — actual trace volume will
  accumulate as the agent runs (Phase 9's eval runs below exercise this).
- [ ] 💻 Confirm `audit_trail` rows are written for every tool call, retrieval detail, and final determination (requirements.md §11)
- [ ] 💻 Manual check: pull up one LangSmith trace and the corresponding `audit_trail` rows side by side — confirm they tell the same story

---

## Phase 9 — Evaluation (10 test claims)

Built 2026-08-17.

- [x] 💻 **Design 10 claims spanning claim types + evidence-completeness levels, each
  with a predetermined expected outcome** — [`specs/eval_claims.md`](eval_claims.md),
  written before any of the 7 new scenarios' evidence was generated. Reused the 3
  Phase-4-era scenarios (`ACC-9001`/9002/9003, all clean-Approve) and added 7 more
  (`ACC-9004`-`9010`) specifically to exercise paths the original 3 never touched: a
  `FAIL`-short-circuit Deny from bad account standing (#4), a Deny from an *unfounded*
  duplicate-charge claim where no actual duplicate exists (#5), Approve/Deny reached
  only via `ask_human` because the account's `account_profiles` row is deliberately
  never loaded (#6 human answers "yes", #7 human answers "no"), a Deny from a disputed
  transaction id that doesn't exist on the account at all (#8), a Deny from a fraud
  claim where the transaction turns out *not* to be anomalous (#9), and an Inconclusive
  where the one unresolvable check stays `UNKNOWN` even after the human is asked,
  because their answer is genuinely ambiguous (#10). Final mix: 6 fraud / 4
  billing_dispute, 4 Approve / 5 Deny / 1 Inconclusive.

- [x] 💻 **Generate synthetic evidence per claim** — `backend/generate_synthetic_data.py`.
  Extended `SCENARIOS` with the 7 new entries above (narratives + `expect` blocks per
  the existing Phase-4 pattern) and extended `review_scenario`'s automated-review
  vocabulary with four new expectation keys these scenarios needed:
  `access_logs.no_risk_flag`, `disputed_transaction.location_in_history`,
  `disputed_transaction.amount_not_over_avg_multiple` (asserts the disputed amount
  stays under N× the account's own average, i.e. "this genuinely isn't anomalous"),
  and `no_duplicate_for_disputed` (asserts no other transaction shares amount+merchant
  within 24h of the disputed one, i.e. "the member's duplicate claim is mistaken").
  Added a `load_account_profile: False` scenario flag (`load_scenario` skips the
  `account_profiles` INSERT, and issues a `DELETE` instead so re-running is still
  idempotent) for #6/#7/#10's missing-profile design. Also added a 3-attempt retry
  loop around generate-then-review in `main()`, since generation is stochastic — one
  scenario (#7) needed 2 retries before its generated data matched the `expect` block,
  the rest passed first try. All 7 generated and loaded cleanly; verified against the
  DB directly (`account_profiles` correctly has no row for `ACC-9006`/9007/9010, all 10
  accounts have exactly 7 transactions).

  **Bug found and fixed while writing scenario #7's data**: its
  `disputed_transaction_ref` (used internally by the generator to identify "the
  disputed transaction" in the generated JSON) was set to `TXN-7007`, but the
  narrative and `claim_payload.disputed_transaction_id` both said `TXN-7107` — a
  copy-paste mismatch from adjusting the account's transaction-ref range to avoid
  colliding with `ACC-9001`'s `TXN-7001`. Caught immediately by the automated review
  ("disputed transaction not found in generated transactions") on the first dry run,
  before anything was loaded; fixed by correcting `disputed_transaction_ref` to match.

- [x] 💻 **Jupyter notebook: run all 10 through the agent, compare actual vs. expected
  decision + check trace** — `backend/eval_notebook.ipynb`. Same run pattern as
  `backend/smoke_test_orchestrator.py` (`insert_claim` → `build_orchestrator_graph`
  (the current `AGENT_MODE=orchestrator` default) → `graph.invoke` → resume through any
  `ask_human` interrupts → read back `claims.decision` + full `check_ledger`), extended
  with a per-scenario `HUMAN_ANSWERS` auto-responder (`"yes"`/`"no"`/an intentionally
  ambiguous string, matching `specs/eval_claims.md`'s answer script) instead of always
  answering `"yes"`, and a final cleanup cell that deletes the 10 claims it created
  (`check_ledger`/`audit_trail` cascade with them) so re-running doesn't accumulate
  rows in the dev DB. `jupyter`/`nbformat`/`ipykernel`/`pandas` added to
  `backend/requirements.txt` (dev/eval-only, not needed to run the app) since none were
  previously installed. Executed for real via
  `jupyter nbconvert --to notebook --execute --inplace backend/eval_notebook.ipynb`
  against the live dev Postgres + Qdrant + `gpt-5.6-luna` — not just eyeballed in the
  UI. Result: **10/10 claims matched their predetermined expected decision** on the
  first fully-passing run (~100s wall-clock for all 10, reasoning-model latency
  included).

- [x] 💻 **Fix discrepancies; re-run until the eval set passes** — one real
  discrepancy was found and fixed (not just scenario-authoring mistakes, an actual
  agent-code bug):

  **Bug found and fixed: `ask_human` answer parsing matched on a raw string prefix,
  not a word boundary.** `backend/agent/graph.py`'s `_derive_check_updates` decided
  PASS/FAIL/UNKNOWN for a human's free-text answer via
  `answer.startswith(("no", "denied", "false"))` — which also matches any answer
  merely *beginning with the letters "no"*, such as "not sure", "nothing on file", or
  "november". Scenario #10 was deliberately designed to test the Inconclusive path
  with an ambiguous human answer ("not sure, can't confirm either way") and instead
  landed **Deny**, because `"not sure...".startswith("no")` is `True` in Python. This
  isn't just a test-harness quirk: `ClaimDetail.jsx`'s `ask_human` UI has a free-text
  fallback alongside its Yes/No buttons (Phase 6), so a real claim processor typing an
  honestly uncertain answer would have hit the exact same misclassification in
  production. Fixed in `backend/agent/graph.py` (the single shared
  `_derive_check_updates`, imported unchanged by `orchestrator.py` too, so both agent
  paths got the fix at once): now matches on the answer's first whitespace-delimited
  word (punctuation-stripped) against the yes/no synonym sets, rather than a prefix of
  the whole string. Re-ran scenario #10 alone first to confirm the fix (correctly
  landed Inconclusive, `account_red_flags` left `UNKNOWN` after two ambiguous answers
  exhausted meaningful progress), then re-ran all 10 together — 10/10 matched, no
  regressions in the other 9 (none of which depend on this code path except #6/#7,
  whose clean "yes"/"no" answers were never affected by the bug).

  No other discrepancies found — every other scenario matched its expected outcome
  on the first real run, so no known gaps to document here.

---

## Phase 10 — Deployment (your Ubuntu server)

> Full step-by-step guide + checklist: [`docs/deployment.md`](../docs/deployment.md)
> (Nginx serving `frontend/dist` + `/api/` proxy → systemd/uvicorn `backend.main:app`
> (1 worker) + local Postgres; Qdrant Cloud and OpenAI stay external). The bullets
> below are the original outline; `docs/deployment.md` expands each one.

- [ ] 🌐 SSH into the server
- [ ] 🌐 Install system packages: Python 3.11+, Node.js/npm, PostgreSQL server, Nginx, git
- [ ] 🌐 Create a Postgres DB + user on the server; apply `schema.sql`; note the connection string
- [ ] 🌐 Get the code onto the server (`git clone`, or `scp` if not using git)
- [ ] 🌐 Create the server-side `.env` with real production values (OpenAI/Qdrant/LangSmith keys, prod `DATABASE_URL`, `AUTH_PASSWORD`) — copied manually, never committed
- [ ] 🌐 `npm run build` the React app; point Nginx at the static output
- [ ] 🌐 Create a systemd unit for the FastAPI app (uvicorn) so it restarts on crash/reboot
- [ ] 🌐 Configure Nginx as a reverse proxy: static frontend + `/api` → FastAPI (uvicorn)
- [ ] 🌐 `ufw allow` only what's needed (80, 443, OpenSSH) — nothing else should be open to the internet
- [ ] 🌐 (Optional) Point a domain at the server + get a TLS cert via certbot; otherwise access over HTTP via the server's IP
- [ ] 🌐 Run `scripts/ingest_policy_corpus.py` once against production (same Qdrant collection, or a separate prod collection for dev/prod separation)
- [ ] 🌐 Smoke test the deployed URL end-to-end

---

## Phase 11 — Capstone Wrap-up

- [ ] 💻 Record/prepare a demo walkthrough referencing requirements.md and technical.md
- [ ] 💻 Confirm technical.md and the `.drawio` diagram still match what was actually built; update if implementation diverged
- [ ] 💻 Write up known limitations / follow-ups (e.g., multi-user auth, CI-based test harness, dedicated reranker)

---

## Phase 12 — Agent-tracing UI (`traceing` branch)

Built 2026-08-31 on branch `traceing` (isolated so it can be dropped wholesale if
needed). Goal: surface the agent's internals the way the "Agent with Subagent
LangGraph" teaching project does — inspect Context / Memory / Tools / Graph /
Sub-agents in tabs — adapted to this app's many-concurrent-claims shape (the reference
has one agent / one conversation; here each inspector view is scoped to one claim run,
`thread_id = claim_id`).

### Phase 0 — Remove `AGENT_MODE=legacy`

- [x] 💻 The standalone single-agent Think/Act/Observe graph in `backend/agent/graph.py`
  (`build_graph`, `init_node`/`think_node`/`act_observe_node`/`route_after_act`, the
  all-8-tools `MODEL` binding, `SYSTEM_PROMPT_HEADER`, `_build_system_prompt`) was
  removed. `graph.py` is now just the shared core `orchestrator.py` builds on:
  `ClaimState`, `_derive_check_updates`, `_format_checks`, `finalize_node`,
  `MAX_ITERATIONS`/`NO_PROGRESS_LIMIT`, `initial_state`. Kept the filename so
  `orchestrator.py`'s `from .graph import (...)` and `worker.py`'s
  `from .agent.graph import initial_state` are unchanged.
- [x] 💻 `backend/worker.py`: `_build_graph()`'s `AGENT_MODE` switch replaced by
  `build_claim_graph(checkpointer=None)` — always the orchestrator graph; the
  `checkpointer=None` path is what the new Graph endpoint compiles for
  `.get_graph().draw_mermaid()`.
- [x] 💻 `AGENT_MODE` removed from `.env.example`. `backend/smoke_test_agent.py` deleted;
  `backend/smoke_test_orchestrator.py` no longer diffs against legacy (just runs each
  scenario through the orchestrator). Docs synced: `README.md`, `docs/c4-architecture.md`
  (Level 3 component diagram + notes), `specs/technical.md` §5.

### Phase A — Backend read-only endpoints

- [x] 💻 `GET /claims/{id}/agent-context` — the model's message window from the
  checkpointer (`build_claim_graph(cp).get_state(...)`), plus iteration / no-progress /
  questions-asked counters, `active_agent`, next node, model/provider, token estimate.
- [x] 💻 `GET /claims/{id}/memory` — `episodic_facts` for the claim's account, each
  tagged written-by-this-claim vs carried in from an earlier one, with the originating
  claim id.
- [x] 💻 `GET /agent/tools` — static tool catalog: category, params, owning sub-agent,
  checks-resolved (new `TOOL_CATEGORY` / `TOOL_RESOLVES_CHECKS` maps in `tools.py`).
- [x] 💻 `GET /agent/graph` — compiled orchestrator graph: `draw_mermaid()` +
  `draw_ascii()` (needs `grandalf`, added to requirements) + per-node prose. Both
  static views memoized. New module `backend/agent/tracing.py` holds all four.
- [x] 💻 Verified via `TestClient` against the dev DB: 200 with data, 401 without auth,
  404 for an unknown claim; shapes match what the frontend components consume.

### Phase B — Portal "Agent" tab (Tools + Graph)

- [x] 💻 New closable, deduped portal tab (`App.jsx` / `TabStrip.jsx`), opened from an
  "Agent" header button. `AgentPanel.jsx` (lazy-loaded so `mermaid` stays out of the
  initial bundle) with a Tools view (per-sub-agent ownership cards + tools grouped by
  category) and a Graph view (`mermaid` render, `ASCII` toggle + auto-fallback, node
  prose). `frontend/package.json` gains `mermaid@11`.

### Phase C — Per-claim inspector tabs

- [x] 💻 `ClaimDetail.jsx` sub-tab row 3 → 6: **Checks · Context · Memory · Account &
  Transaction · Audit Trail · Sub-agents**. Context = the message window + run
  counters; Memory = episodic facts with per-claim provenance; Sub-agents = a
  Research/Decisioning breakdown (turns, iteration range, tools used, handoff point)
  derived client-side from the `/audit` data already polled. `api.js` gains
  `getAgentContext` / `getAgentMemory` / `getToolCatalog` / `getAgentGraph`.

### Phase D — Live feel

- [x] 💻 `getAgentContext` + `getAgentMemory` folded into `ClaimDetail`'s existing 2s
  poll (both degrade to `null` on a transient error rather than red-bannering the
  view); Sub-agents re-derives each cycle. Context tab tracks a running claim live.

### Verification

- [x] 💻 **Real browser** (Playwright driving Chrome for Testing against the running
  `scripts/start.sh` stack): login → Agent tab opens → Tools view lists tools grouped
  by category with per-sub-agent ownership cards → Graph view renders the Mermaid
  diagram (`__start__ → init → think_research → act_observe → …`) and the ASCII toggle
  works → open a completed claim → the 6 sub-tabs are present → Context shows the live
  header (`messages 36 · ≈ tokens 8,802 · iteration 9/12 · active decisioning · next
  done · model …`) with expandable message rows → Memory shows the account's episodic
  fact tagged "written by this claim" → Sub-agents shows Research (turns 5, iters 1–5)
  vs Decisioning · active (turns 4, iters 6–9) → Agent tab closes cleanly. Zero app
  console errors (the pre-existing `favicon.ico` 404 aside).

*(Phase E — SSE streaming from `worker.run_claim_agent` — explicitly out of scope.)*

---

## Unassigned — Backlog

Not scheduled into any phase above; revisit if/when the trigger condition below
actually shows up.

- [ ] 💻 **Split the background worker out of the API container** (raised 2026-08-17,
  discussing "API & Agent Backend is one container" in `docs/c4-architecture.md`
  Level 2, in the context of adding more APIs to this backend going forward). Current
  design: `backend/worker.py` runs the claim-processing agent in-process via FastAPI
  `BackgroundTasks` — no separate worker process or task queue
  (`technical.md`'s Background Execution row already rejected Celery/RQ as
  unjustified at this scale).
  **Don't split preemptively just because more endpoints get added** — the risk
  `BackgroundTasks` actually creates is long-running/blocking work sharing the same
  process and event loop as request handling; new endpoints that are fast/CRUD-style
  won't contend with the claim-processing worker for resources. Revisit only once one
  of these actually shows up: (1) claim volume high enough that in-process agent runs
  start starving request latency, (2) needing to scale worker replicas independently
  from API replicas, or (3) wanting a worker crash/restart to not affect API uptime.
  At that point, pull `worker.py`'s `run_claim_agent`/`resume_claim_agent` behind a
  real queue (Celery/RQ, or similar) as a second process/container — until then, this
  stays a documented tradeoff, not a task.
