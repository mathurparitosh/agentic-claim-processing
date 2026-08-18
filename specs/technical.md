# Claim Assistant — Technical Stack

## 1. Confirmed Stack

| Layer                | Choice                                                            | Alternatives Considered                                                                                                                                                                                                                                                                                                                                                                                                                                                              | Why I Picked This                                                                                                                                                                                                                                                                                                                                                                                                                   |
| -------------------- | ----------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Frontend             | **React**                                                         | None evaluated                                                                                                                                                                                                                                                                                                                                                                                                                                                                       | Claims Application UI used by the Claim Processor: submit claims, view/answer agent questions, review decisions.                                                                                                                                                                                                                                                                                                                    |
| Agents / backend     | **Python**                                                        | None evaluated                                                                                                                                                                                                                                                                                                                                                                                                                                                                       | Implements the ReAct loop, orchestrator, and tool layer.                                                                                                                                                                                                                                                                                                                                                                            |
| LLM                  | **GPT API** ([platform.openai.com](https://platform.openai.com/)), switchable to **OpenRouter** | None evaluated for the default. OpenRouter added 2026-08-16 as a switchable alternate provider (`LLM_PROVIDER` in `.env.local`, `backend/agent/llm.py`) -- lets the agent run against `openrouter/free` (or any OpenRouter model) instead of paying for OpenAI calls; not the default since OpenRouter's free tier is rate-limited (50 req/day with no credit purchase, 20 req/min) and its per-model tool-calling reliability isn't guaranteed the way OpenAI's is. | Powers the Think step of the reasoning loop (proposes actions); the harness executes them.                                                                                                                                                                                                                                                                                                                                          |
| Retrieval / RAG      | **Qdrant**                                                        | Pinecone — used through Phase 4/5, migrated away from in Phase 3's real ingestion pass; no functional gap found, switched at the user's request.                                                                                                                                                                                                                                                                                                                                   | Vector store for the policy & regulation semantic memory corpus.                                                                                                                                                                                                                                                                                                                                                                    |
| Orchestration        | **LangGraph**                                                     | None evaluated  (typical alternatives here would be a heavier durable-workflow engine like Temporal).                                                                                                                                                                                                                                                                                                                                                                                | Drives the ReAct (Think/Act/Observe) loop and the Adjudication Orchestrator; its checkpointing can back the "survive pauses, resume on `ask_human` response" requirement.                                                                                                                                                                                                                                                           |
| Checkpointer         | **LangGraph `PostgresSaver`**                                     | In-memory checkpointer (`MemorySaver`) — rejected, doesn't survive a process restart, which breaks the "resume hours/days later" requirement. `SqliteSaver` — rejected once the Database decision moved to Postgres, to avoid running two DB technologies for no benefit.                                                                                                                                                                                                            | Persists graph state so a paused run (waiting on `ask_human`) can be rehydrated later. Backed by the same Postgres instance as the rest of the app.                                                                                                                                                                                                                                                                                 |
| Database             | **Postgres**                                                      | SQLite (interim, migrate later) — reconsidered and rejected: deployment already requires a cloud VM, and most hosts (Fly.io, Railway, etc.) attach managed Postgres about as easily as a persistent volume for SQLite, so provisioning Postgres from the start costs about the same as SQLite + a later migration, without ever hitting SQLite's write-concurrency ceiling (`database is locked` under concurrent Check Ledger writes) or needing WAL-mode/busy-timeout workarounds. | Claims DB / Check Ledger / Audit Trail, from the start. Proper row-level locking and MVCC handle concurrent writes from the Orchestrator + multiple in-flight agent runs cleanly — no interim data store, no migration step later.                                                                                                                                                                                                  |
| API layer            | **FastAPI**                                                       | None evaluated in this session (Flask and Django REST are the usual alternatives; FastAPI's native async support and auto-generated OpenAPI docs are why it's typically preferred alongside an async LangGraph backend).                                                                                                                                                                                                                                                             | Sits between the React frontend and the LangGraph backend; exposes claim submission, status, and `ask_human` question/answer endpoints.                                                                                                                                                                                                                                                                                             |
| Background execution | **FastAPI `BackgroundTasks`**                                     | A task queue (Celery/RQ) — rejected, adds a broker (Redis/etc.) and worker process not justified at capstone/single-VM scale. Running the agent loop synchronously in the request handler — rejected, blocks the HTTP response for the full multi-minute claim run and is incompatible with the polling-based `ask_human` design, which assumes the run is already progressing independently of any single request.                                                                  | Runs the LangGraph agent loop for a submitted claim without blocking the FastAPI request that started it, so the frontend can immediately start polling for status/questions while the run executes. No new infra beyond what's already in the stack.                                                                                                                                                                               |
| Embeddings           | **OpenAI `text-embedding-3-small`**                               | `text-embedding-3-large` — deferred; higher quality/cost, only worth it if retrieval quality is measurably lacking.                                                                                                                                                                                                                                                                                                                                                                  | Same vendor as the LLM — one API key, one billing relationship, no extra integration. Must stay identical between ingestion and query time.                                                                                                                                                                                                                                                                                         |
| Reranker             | **LLM-based rerank (GPT)**                                        | Cohere Rerank — rejected, adds a new vendor/API key/cost just for this one step. Local cross-encoder — rejected, adds model-serving infra to build and maintain.                                                                                                                                                                                                                                                                                                                     | Prompt GPT to score/reorder the top-20 Qdrant candidates down to top-3. No new API key/vendor; at k=20 the extra latency/cost per query is negligible. Revisit a dedicated reranker only if rerank quality becomes a bottleneck.                                                                                                                                                                                                  |
| Document ingestion   | **`unstructured`** + custom clause chunker                        | A simpler custom parser keyed off consistent clause numbering — rejected since source docs aren't finalized and may not have consistent structure. A PDF-specific heavy-parsing approach — rejected for the same reason (format not locked in).                                                                                                                                                                                                                                      | Source policy docs aren't finalized (mix of Word/PDF, structure unknown), so `unstructured` handles parsing/table-extraction across formats, feeding a custom chunker that splits on clause boundaries per requirements.md §9 rather than fixed size.                                                                                                                                                                               |
| Observability        | **LangSmith**                                                     | LangFuse — rejected, open-source alternative but adds self-hosting overhead not justified for a capstone. Custom structured logging straight into the Audit Trail — rejected as the primary dev tool since it would conflate a compliance-facing store with a dev-debugging concern.                                                                                                                                                                                                 | Native LangGraph tracing for development/debugging (step-by-step Think/Act/Observe visibility, latency, token cost). Distinct from the Audit Trail: LangSmith is a dev-facing tool, the Audit Trail (Postgres) remains the compliance system of record — don't conflate the two. Traces will include the full claim trajectory; fine on this project's synthetic data, but revisit before ever pointing this at real customer data. |
| `ask_human` channel  | **Polling**                                                       | WebSockets — rejected, connection-management complexity (reconnects, scaling) not justified by a human-paced workflow. SSE — rejected as an unnecessary middle ground when polling is simple enough and sufficient.                                                                                                                                                                                                                                                                  | React polls a FastAPI status endpoint for pending questions/answers. Simplest to build, no connection-management overhead; fine when sub-second latency isn't needed.                                                                                                                                                                                                                                                               |
| Synthetic data       | **LLM-generated**                                                 | Hand-authored fixtures — rejected; more deterministic/auditable but more manual effort to produce. Script-generated (Faker/random) — rejected; more volume/variety but harder to hand-verify a claim's evidence matches its intended expected outcome.                                                                                                                                                                                                                               | GPT generates the simulated transaction history, system logs, and account red-flag records for the 10 test claims. Review each generated record against its claim's intended expected outcome so the synthetic evidence doesn't accidentally contradict the test's expected decision.                                                                                                                                               |
| Test harness         | **Notebook-based**                                                | pytest + fixtures — rejected; more rigorous and CI-ready, but more ceremony than needed for a capstone eval/demo. Custom eval script — rejected; a viable middle ground, but a notebook is better suited to interactive trace inspection for the writeup.                                                                                                                                                                                                                            | The 10-claim evaluation set (requirements.md §12) is run and inspected in a Jupyter notebook — each claim's agent trace and decision reviewed interactively. Fits a capstone demo/writeup; not wired into CI.                                                                                                                                                                                                                       |
| Deployment           | **Self-managed Ubuntu VM** (existing server)                      | Local only — rejected; no reachable URL for a demo. A managed PaaS (Fly.io/Railway) — not needed; a suitable Ubuntu server is already available.                                                                                                                                                                                                                                                                                                                                     | FastAPI backend (via systemd + uvicorn), the built React static files (served via Nginx), and Postgres all run on the existing Ubuntu VM, reachable over the server's IP (or a domain if one is pointed at it). Setup is manual (SSH, package installs, systemd unit, Nginx reverse-proxy config) rather than a PaaS's managed build/deploy pipeline — see tracker.md Phase 10 for the concrete steps.                               |
| Auth                 | **Shared-password gate**                                          | None / single-user — rejected once the app is reachable at a public VM URL, it needs some gate. Basic user accounts — rejected; more build effort than justified for a capstone that isn't about auth.                                                                                                                                                                                                                                                                               | One shared password/API key protects the FastAPI endpoints on the public demo VM — keeps the URL from being wide open, without building real per-user accounts. Note: this means the Audit Trail can't attribute an action to a specific processor if more than one person ever uses it — acceptable for a single-user capstone demo, but not a substitute for real per-user auth if this became multi-user.                        |
| Secrets management   | **`.env` + `python-dotenv`**                                      | Cloud secrets manager — rejected; more production-realistic and slightly safer, but adds setup not justified at capstone/single-VM scale.                                                                                                                                                                                                                                                                                                                                            | OpenAI/Qdrant/LangSmith keys live in a gitignored `.env`, loaded via `python-dotenv`; the same file is copied (never committed) onto the deploy VM.                                                                                                                                                                                                                                                                               |

## 2. Architecture Components

Derived from `specs/Capstone Claim Project v2.drawio`.

- **Claims Application (Frontend, React)** — entry point for the Claim Processor;
  reads/writes the Claims DB.
- **Claims DB** — system of record for claim data and final determinations. Postgres.
- **Adjudication Orchestrator** — runs the agent loop for a claim via FastAPI
  `BackgroundTasks`, so it starts/resumes without blocking the request that
  triggered it, and must survive pauses (e.g., while waiting on `ask_human`).
  LangGraph's `PostgresSaver` checkpointer persists graph state between steps so a
  run can be rehydrated after a pause.
- **ReAct Agent** — the Think/Act/Observe loop, implemented as a LangGraph graph.
  LLM proposes the next action; the graph/harness is responsible for actually
  executing it (tool call, human question, or write).
- **Check Ledger** — persistent store of per-check state (PASS / FAIL / UNKNOWN /
  BLOCKED) for the claim currently being processed; the source of truth the
  Approve/Deny/Inconclusive decision is derived from. Postgres.
- **Audit Trail** — append-only log of every agent step, tool call, retrieval detail,
  and final determination + basis. Postgres.
- **Tool Layer**
  - Retrieval tools (claim/dispute history, policy search)
  - Grounding tools (transaction evidence, account/cardholder verification, document
    extraction with citations)
  - Computation tools (date math, duplicate-charge detection, transaction-pattern
    anomaly scoring)
  - `ask_human` (suspends the run; last-resort retrieval)
  - `write_determination` (single irreversible write of the final decision)
- **Long-Term Memory**
  - Semantic — policy/regulation corpus, versioned, stored in Qdrant as embeddings.
  - Episodic — entity facts (keyed by account/cardholder), provenance-tagged, so
    previously verified facts can be reused across claims. Stored as a Postgres table
    (`episodic_facts` or similar), keyed by entity ID, each row carrying the fact, its
    source (claim/tool that established it), and a timestamp — a keyed-lookup access
    pattern, not similarity search, so it belongs in Postgres rather than Qdrant.

### Memory-to-store mapping

requirements.md §7 defines short-term vs. long-term memory conceptually; this maps
each to an actual store in this stack:

| Memory type | What it holds | Backing store |
|---|---|---|
| Short-term — agent state | Raw Think/Act/Observe trajectory (messages, tool calls) for the in-progress claim; enables resume after `ask_human` | LangGraph `PostgresSaver` checkpointer |
| Short-term — check state | Structured PASS/FAIL/UNKNOWN/BLOCKED per required check; what the final decision is derived from | Check Ledger (Postgres table) |
| Long-term — semantic | Policy/regulation corpus, versioned | Qdrant (vector store, similarity search) |
| Long-term — episodic | Entity facts keyed by account/cardholder, provenance-tagged | `episodic_facts` (Postgres table, keyed lookup) |

All four now live in this stack — no memory type from requirements.md §7 is
unassigned.

## 3. Retrieval Pipeline (RAG)

- Source documents: policy/regulation Word/PDF files, chunked by policy clause
  (not fixed-size), preserving parent-child structure between a policy and its
  sub-clauses; tables/decision trees converted to markdown and kept as a single,
  unsplit chunk.
- Embedding + similarity search via Qdrant.
- Query flow: retrieve top **k ≈ 20** → rerank → apply a relevance-floor threshold →
  return top **3** (zero results is a valid outcome below the floor).
- Retrieval calls (query, filters, full candidate list, scores) are logged to the
  audit trail for later audit review, not just the final top-3 used.

## 4. Claim Taxonomy (Phase 4)

requirements.md §4 says the checks that apply are "determined only after reading the
claim" but doesn't enumerate claim types or checks. This section is that enumeration —
the concrete mapping the LangGraph agent, synthetic-data fixtures, and (later) the
Phase 9 eval set are all built against. Two claim types, matching requirements.md §1's
"billing dispute or fraud claims" framing.

Each check is deterministically required for its claim type (looked up by
`claim_type`, not LLM-inferred) — the check *ledger* is initialized with all required
checks at UNKNOWN when a run starts. What the ReAct loop actually reasons about is
*which tool to call next* to resolve each still-UNKNOWN/BLOCKED check, not which
checks apply in the first place. This keeps "classification" auditable/deterministic
rather than a model judgment call, consistent with requirements.md §13's
determinism-of-decisioning requirement.

### `billing_dispute`

| Check | Tool category | Resolves by |
|---|---|---|
| `transaction_exists` | Grounding | Disputed transaction is found in the account's transaction history |
| `duplicate_charge_check` | Computation | Same amount/merchant charged twice within a short window (only decisive when dispute reason is `duplicate_charge`) |
| `policy_dispute_window` | Retrieval | Retrieve the applicable dispute-filing-window policy; a retrieved, citable policy satisfies the check (see note below — a real day-count comparison against the claim's filed date is deferred) |
| `account_standing` | Grounding | Account is not already flagged for dispute-process abuse |

### `fraud`

| Check | Tool category | Resolves by |
|---|---|---|
| `account_red_flags` | Grounding | Existing fraud/red-flag signals already on the account |
| `transaction_pattern_anomaly` | Grounding + Computation | Disputed transaction checked against the account's history for velocity/amount/location anomalies |
| `system_access_log_check` | Grounding | Suspicious login/device activity in the access logs around the transaction time |
| `policy_liability_rule` | Retrieval | Retrieve the applicable fraud-liability regulation/policy to ground the decision |

### Synthetic data fixture tables (Postgres)

Backing the Grounding tools above — synthetic, not real customer data (requirements.md
§3):

- `transactions` — per-account transaction history (amount, merchant, location,
  channel, status, timestamp).
- `access_logs` — per-account system/login/device event history.
- `account_profiles` — per-account standing, existing fraud red-flags, dispute
  history count.

### Retrieval tool status

Wired to a real Qdrant collection (`claims-policy-corpus`) end-to-end rather than
stubbed. **Vector store migrated from Pinecone to Qdrant** (see tracker.md Phase 3) —
embeddings still come from OpenAI `text-embedding-3-small` (1536-dim, cosine); only the
store/query client changed (`backend/agent/tools.py`'s `_qdrant()`). Phase 3 ingestion
(`scripts/ingest_policy_corpus.py`) is a clause-boundary chunker over
`docs/files/*.md` — one chunk per `###`/`####` heading (a single numbered policy
provision, e.g. `FRD-2.1`), not naive paragraph splitting — producing 101 chunks tagged
with `claim_type` (`billing_dispute`/`fraud`) for `search_policy`'s filter. Both
retrieval-only checks close **only** via `search_policy`'s own result: BLOCKED if it
returns zero candidates, PASS (with the retrieved clause as citation) if it returns
any.

`RELEVANCE_FLOOR` (in `tools.py`) was originally set to `0.75` before there was ever
real data behind it (Pinecone stayed empty through Phase 3-5). Once Qdrant was
populated, real cosine scores from `text-embedding-3-small` showed genuinely relevant
clauses landing ~0.55-0.68 and off-topic queries ~0.06-0.08 — `0.75` was silently
discarding every correct match. Recalibrated to `0.5`.

Neither retrieval-only check has a computation step that applies the retrieved
clause's actual text (e.g. extracting its stated day-count window and comparing
against the claim's filed date) — that's deferred pending tagging policy chunks with
structured metadata (e.g. a `window_days` field) to compute against. **This is
deliberate, not an oversight**: an earlier version gave the model a separate tool that
took a `window_days` argument directly from the model, intending the model to use the
number from a retrieved clause — instead the model supplied a plausible-sounding day
count from its own training knowledge without ever calling `search_policy` first,
closing `policy_dispute_window` on an ungrounded guess. Found via the Phase 5
end-to-end test (a `billing_dispute` claim resolved `policy_dispute_window` to PASS
with `window_days: 60` despite the vector store having 0 vectors at the time). Removed
that tool; a check able to close only through an actual retrieval hit can't be
bypassed this way.

## 5. Multi-Agent Orchestration (Research / Decisioning) + On-Demand Recovery Agent

**Built 2026-08-17** (tracker.md Phase 7 has the full implementation/verification
writeup). Two independent structures, not three peer agents sharing one loop:

1. An **orchestrator graph** that replaces the single agent's Think/Act/Observe loop
   as the default claim-processing path. `backend/agent/graph.py` (today's single
   agent) stays in the codebase as a selectable fallback via a new env var, mirroring
   the existing `LLM_PROVIDER` switch pattern (§1) — the orchestrator becomes the
   default, the legacy single agent isn't deleted.
2. A separate, **on-demand Recovery agent**, triggered per claim after a decision
   already exists — not part of the orchestrator graph's run at all.

**Motivation**: primarily to demonstrate a multi-agent orchestration pattern for the
capstone, not a fix for an observed limitation in the current single-agent loop.

### Orchestrator graph: Research + Decisioning sub-agents

- **Research agent** — owns Grounding + Retrieval tools only (`lookup_transaction`,
  `lookup_account_profile`, `lookup_access_logs`, `search_policy`). Gathers evidence
  and updates the check ledger for evidence-type checks (`transaction_exists`,
  `account_standing`, `account_red_flags`, `system_access_log_check`,
  `policy_dispute_window`, `policy_liability_rule`, per §4's taxonomy). Makes no
  approve/deny judgment of any kind.
- **Decisioning agent** — owns Computation tools (`check_duplicate_charge`,
  `check_transaction_anomaly`) + `ask_human`, plus the orchestration judgment of which
  still-UNKNOWN/BLOCKED check to pursue next (hand back to Research for more evidence,
  call a computation tool, or escalate to `ask_human`) — the same judgment the single
  agent's Think step already exercises today, just scoped to a narrower toolset behind
  a distinct LLM call. **The final Approve/Deny/Inconclusive outcome is unchanged**:
  still computed by `compute_decision(check_ledger)` in code once every check is
  resolved or a termination condition is hit (any FAIL → deny short-circuit, iteration
  ≥ 12, 5 no-progress iterations, or the 3-question human budget — same rules as today,
  requirements.md §5). Neither sub-agent, nor the orchestrator itself, ever asserts the
  outcome directly — this is what keeps requirements.md §13's "Determinism of
  decisioning" intact across the refactor.
- The orchestrator routes to Research first, and hands off to Decisioning
  permanently (never back) once either (a) no research-owned check is still UNKNOWN,
  or (b) Research's iteration budget runs out — **not** purely (a) alone. (b) exists
  because a research check can be legitimately unresolvable by any research tool (e.g.
  `account_standing` stays UNKNOWN forever if `lookup_account_profile` can't find a
  profile at all — that never becomes BLOCKED, just permanently UNKNOWN). Found via
  `backend/smoke_test_orchestrator.py` during implementation: a claim against a hidden
  account profile looped in Research for the whole run and hit the *global*
  no-progress cap before Decisioning — and therefore `ask_human`, which only
  Decisioning owns — ever got a turn, landing `inconclusive` instead of correctly
  escalating to a human. Research's iteration budget is
  `len(research-owned checks in this claim) + 2`, deliberately tight rather than
  generous: `NO_PROGRESS_LIMIT` is checked *before* the phase-handoff decision and is
  shared across both sub-agents, so a loose research budget burns most of that shared
  allowance before Decisioning ever runs.
- Iteration/no-progress/human-budget counters are tracked **globally across the whole
  orchestrator run** (both sub-agents share one counter each), not reset per
  sub-agent — a sub-agent boundary must not become a loophole around the Boundedness
  requirement (§13).
- Audit trail: every sub-agent's tool call is logged exactly as today
  (`act_observe_node`'s pattern), plus which sub-agent (`research`/`decisioning`) made
  the call — extends the existing `source: agent/human` audit field, doesn't replace
  it, so a reviewer can tell which role was active for any given step.
- Checkpointing: same `PostgresSaver` mechanism — an orchestrator run must survive the
  same pause/resume-after-`ask_human` requirement as today (§13's Resumability),
  regardless of which sub-agent triggered the interrupt.

### Recovery agent (on-demand, not part of the orchestrator run)

- **Purpose**: after a claim reaches `approve` or `inconclusive`, determine whether the
  case is eligible for card-network recovery (charging back the merchant's acquiring
  bank via Visa/Mastercard/ATM network rules) and, if eligible, assemble the supporting
  document package. Not automatic — the Claim Processor triggers it per claim from the
  UI (a new action, e.g. a "Check Recovery Eligibility" button on the claim detail
  screen). Not all cases are eligible.
- **Trigger condition — resolved 2026-08-17: `decision IN ('approve', 'inconclusive')`**,
  gated in code (the action is hidden/disabled otherwise), not left to the Recovery
  agent's own judgment. `deny` is excluded — the bank held the cardholder liable, no
  credit was issued, so there's nothing to recover from the merchant.
  `inconclusive` *is* included alongside `approve` — plausible operational rationale:
  an inconclusive claim can already carry a provisional credit (Reg E-style rules
  commonly require crediting the cardholder within a set number of days of a dispute,
  before investigation concludes), so recovery can be a live question even before a
  final determination exists. Keeping this a code gate rather than agent judgment stays
  consistent with the same principle behind the eligibility-logic exception itself
  (§5 above): reserve LLM judgment for what's genuinely interpretive (which reason code
  applies), not for a fact already sitting in the `claims` table.
- **Rule source**: a new synthetic network-rules corpus, authored the same way as the
  existing 5-rail policy corpus (`docs/files/*.md` — ACH/CCD/DBD/ZEL/FRD), covering
  simplified Visa/Mastercard/ATM chargeback reason codes and filing windows. Ingested
  into Qdrant via a new/extended ingestion pass, retrieved through a new tool (e.g.
  `search_network_policy`), parallel to `search_policy`. Tentative default: reuse the
  existing collection with a new `claim_type` tag (e.g. `network_recovery`) rather than
  a separate collection, consistent with Phase 3's single-collection-filtered-by-tag
  pattern — reconsider only if there's an actual reason to split.
- **Eligibility logic — the deliberate exception**: unlike every other check in this
  system, recovery eligibility is **LLM-judged, not code-computed from a deterministic
  rule**. The agent retrieves the applicable network policy and weighs it against the
  claim's facts (claim type, dispute reason, decision, evidence already in the check
  ledger) the way a human recovery analyst would, rather than closing on a fixed rule
  match. This is a conscious, scoped departure from this project's usual grounding
  philosophy — the Phase 5 `check_dispute_window` bug fix (§4 above) is the canonical
  example of *why* that philosophy exists elsewhere in this app — justified here
  because:
  - The output is advisory (an audit-trail note), not a system-of-record outcome —
    nothing else in the app reads or depends on it.
  - It sits outside requirements.md §13's actual scope: "Determinism of decisioning" is
    specifically about the Approve/Deny/Inconclusive outcome, which recovery
    eligibility is not.
  - Not all cases are eligible, and eligibility genuinely depends on network-rule
    interpretation that's a closer fit for LLM judgment than a fixed rule table
    (reason-code selection has real edge-case interpretation, unlike e.g. a fixed
    dispute-window day count).
- **Output**: no new table, no new API surface beyond the one trigger endpoint, no new
  UI tab for now. The eligibility determination (eligible/not-eligible + reasoning) and
  the assembled package contents (evidence list, applicable reason code, filing
  deadline, narrative) are written as a single `audit_trail` entry (`event_type:
  recovery_assessment`, `source: agent`) via the existing `ledger.log_audit` helper —
  visible in the claim's existing Audit Trail tab with no frontend display changes
  needed, just the one trigger action. A dedicated table/tab is a natural later step if
  this gets used for real, not built now.
- Not tied to the orchestrator's checkpointed run — a short-lived, single-purpose agent
  invoked by a new endpoint (e.g. `POST /claims/{id}/recovery`), via `BackgroundTasks`
  consistent with the rest of the app.

### Open implementation questions (resolve before writing code)

- ~~Exact LangGraph node structure for the orchestrator~~ **Resolved 2026-08-17: one
  supervisor node, with conditional routing to Research/Decisioning sub-nodes, inside
  a single graph** — not two separate subgraphs. Concretely: `think_research` and
  `think_decisioning` are two distinct nodes (each its own LLM call, bound to its own
  narrower toolset per the split above), with a `supervisor` node/conditional edge
  deciding which one runs next based on check-ledger state (any evidence-type check
  still UNKNOWN/BLOCKED → route to Research; otherwise → Decisioning). `act_observe`
  stays a single shared node executing whichever tool call either sub-node produced —
  it doesn't need to know which sub-agent it's serving, since tool execution and
  audit-trail/check-ledger update logic is identical either way (just tagged with
  which sub-agent originated the call, per the audit-trail bullet above). This keeps
  one checkpointed graph (so `PostgresSaver`/resumability/global iteration counters all
  work exactly as they do today, no cross-graph handoff to keep in sync) rather than
  the added complexity of invoking/resuming two separate compiled graphs.
- ~~Whether Recovery eligibility should be restricted to `decision == approve` only, or
  also considered for other outcomes~~ **Resolved 2026-08-17: `approve` and
  `inconclusive`, excluding `deny`** — see the Recovery agent's trigger-condition
  bullet above.
- `Capstone Claim Project v2.drawio` will fall out of sync with this once built (same
  situation as the Phase 4 gap-audit notes) — update it alongside implementation this
  time, not deferred to wrap-up.

## 6. Open / To-Be-Decided

All previously open items now have a decision (§1, §4, §5). Nothing outstanding at this
time — revisit this section as implementation surfaces new gaps.
