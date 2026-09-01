# Safety & Intervention Plan — Claim Assistant

How this capstone agent reduces risk, how we measure whether the controls are
holding, and when a human must decide instead of the agent. Companion to
[`../specs/requirements.md`](../specs/requirements.md) (§5, §6, §10–§13),
[`../specs/technical.md`](../specs/technical.md), and the Phase 9 eval harness
([`../backend/eval_notebook.ipynb`](../backend/eval_notebook.ipynb),
[`../specs/eval_claims.md`](../specs/eval_claims.md)). Module references are to
*Module 6 — Evaluation, Guardrails, Logging & Observability*.

**Thesis.** The design puts the *decision* on deterministic rails
(`compute_decision()` over a check ledger — the model cannot assert an outcome) and
the *reasoning* on disk (an append-only audit trail). Guardrails constrain each step
of the loop, evaluation proves the constraints hold across a representative claim
set, and human intervention is the designed fallback for the cases the guardrails
deliberately refuse to resolve alone. The goal is **resilience, not perfect
prevention**: every run either produces an evidence-backed decision or fails safe to
*Inconclusive* with a named reason and a full trace.

---

## 1. What the agent does, and what can go wrong

**What it does.** Claim Assistant adjudicates `billing_dispute` and `fraud` claims
for a human claim processor. On submission it classifies the claim, then runs a
bounded ReAct (Think → Act → Observe) loop with two sub-agents — **Research** gathers
evidence via read-only lookup / retrieval / computation tools; **Decisioning** runs
the computation checks, asks the human if needed, and requests the terminal write.
Each required check (4 per claim type) is moved to `PASS` / `FAIL` / `UNKNOWN` /
`BLOCKED` in a **check ledger**, and the Approve / Deny / Inconclusive outcome is
computed from that ledger by fixed rules — never emitted as free-form model text.
There is exactly one irreversible action (`write_determination`). A separate,
advisory Recovery assessment can run *after* a decision exists.

**Risk register.**

| # | Risk | Where it bites | Current exposure |
|---|------|----------------|------------------|
| R1 | **Ungrounded decision** — model concludes Approve/Deny without evidence to support it | Reasoning layer (Module 6 "cognitive" risk) | *Low by construction* — outcome is derived from the ledger, and only a tool result or human answer can close a check. The model's own inference can only choose the next action. |
| R2 | **Wrong-policy grounding** — RAG returns a lexically similar clause from the wrong claim type; decision cited to the wrong rule | `search_policy` → `policy_*` checks | *Low* — Qdrant query hard-filters on `claim_type`; a wrong-type clause cannot be retrieved. |
| R3 | **Retrieval poisoning / stale policy** — a bad or outdated chunk in the corpus propagates to every claim that retrieves it | Policy corpus (Qdrant), Module 6 Layer 2 | *Open* — no corpus versioning or ingest-time validation yet. |
| R4 | **Bad tool arguments / tool failure** — a weak model emits a malformed tool call; an unhandled exception crashes the run and strands the claim in `processing` | Act step | *Mitigated* — unknown-tool guard + `try/except` around every tool call return a structured error to the model instead of a crash. (This was a real bug, found with a local model, now fixed.) |
| R5 | **Non-termination / cost runaway** — loop never converges and burns tokens | Runtime, Module 6 Layer 4 | *Low* — `MAX_ITERATIONS = 12`, `NO_PROGRESS_LIMIT = 5`, per-phase research cap, `HUMAN_QUESTION_BUDGET = 3`; all runs terminate. |
| R6 | **Silent context loss** — a fact established early (e.g. the governing regulation) is evicted by summarization before the decision | Short-term memory | *Mitigated* — the check ledger and episodic facts hold verified findings outside the message window; the ledger, not the transcript, drives the decision. |
| R7 | **Rubber-stamp human input** — processor answers `ask_human` without real review; the first-word answer parser over-trusts a casual "yes" | HITL path (Module 6 §3) | *Partial* — an ambiguous answer keeps the check `UNKNOWN` (→ Inconclusive) rather than guessing, but a confident wrong "yes" still closes the check. |
| R8 | **Premature irreversible write** — `write_determination` fires before the ledger supports a terminal outcome | Terminal action | *Low* — the tool's output is advisory; the real outcome is recomputed from the ledger regardless of what the model says. |
| R9 | **Unauthorised access / PII exposure** — claims carry account and transaction detail; audit payloads store full retrieval traces | API + audit store | *Partial* — shared-password bearer auth on all claim routes; no field-level redaction or row-level access control. |
| R10 | **Provider variance** — switching LLM provider (OpenAI / OpenRouter / Ollama) changes tool-calling reliability and determinism | Model layer | *Known* — weak local models do not honour `tool_choice="required"`; treated as a provider-quality gate, not a silent config switch. |

---

## 2. Guardrails

Organised by junction of the ReAct loop, per Module 6's "a gate at every transition"
framing. **Bold = implemented in the current codebase.** *Italic = planned.*

**Input gate**
- **All claim routes sit behind a bearer-token dependency (`require_auth`); requests are validated against a Pydantic model (`ClaimIn`) and rejected if malformed.**
- **`claim_type` drives `REQUIRED_CHECKS`; only `fraud` and `billing_dispute` have a defined check set, so nothing else has an adjudication path.** Claim `reason` comes from a fixed UI dropdown, not free text.
- *Prompt-injection screening on the free-text fields that do reach the model — the `ask_human` answer and any future free-text reason.*

**Planning / role gate**
- **Two sub-agents with disjoint tool sets.** Research holds only read-only lookups + `search_policy`. Only Decisioning holds `ask_human` and `write_determination` — the two safety-relevant tools are unreachable during evidence gathering.
- **`tool_choice="required"` and `parallel_tool_calls=False`** — exactly one tool call per turn, and every turn must act, so no turn silently stalls.
- **The Research → Decisioning handoff injects an explicit role-switch `SystemMessage` and is one-way** — the supervisor never routes back, so the phases can't thrash.

**Source-verification gate**
- **`search_policy` hard-filters Qdrant by `claim_type`** — a wrong-claim-type clause cannot be retrieved (mitigates R2).
- **Retrieve top 20 → apply a relevance floor of 0.5 → return top 3. If nothing clears the floor, return zero results.** "No matching policy found" is an honest `BLOCKED`, never a forced low-confidence match.
- **The full retrieval trace — query, filter, all ~20 candidates and their scores — is written to the audit trail**, so the retrieval step itself is reviewable (requirements §9).

**Tool-execution gate**
- **Every tool is read-only except the single terminal write, `write_determination`**, which is isolated as the last action and whose return value is advisory only.
- **Unknown-tool guard + `try/except` on every tool call** → a structured `{"error": …}` is fed back to the model; the run continues and can still end Inconclusive rather than 500 (mitigates R4).

**Output / decision-integrity gate**
- **The outcome is `compute_decision()` over the check ledger**: any `FAIL` → *deny* (short-circuits), any `UNKNOWN`/`BLOCKED` → *inconclusive*, all `PASS` → *approve*.
- **Only a tool result or a human answer may move a check to `PASS`/`FAIL`.** Model inference can only select the next action. This is the core guardrail — it makes "Approve" impossible to assert without an external, checkable fact (mitigates R1, R8).

**Runtime monitoring & boundedness**
- **Hard caps guarantee termination:** `MAX_ITERATIONS = 12`, `NO_PROGRESS_LIMIT = 5` (both force Inconclusive), per-phase research cap = *(research checks in this claim)* + 2, `HUMAN_QUESTION_BUDGET = 3`.
- **Every step emits an append-only `audit_trail` row** — `run_started`, `agent_think`, `tool_call`, `human_answer`, `determination_written`, `recovery_assessment` — tagged `source = agent` or `human`, and recording the model and provider used.
- **Run state is checkpointed to Postgres after every super-step (`PostgresSaver`)** — a claim paused on `ask_human` resumes from its checkpoint even across a backend restart, rather than being re-run (requirements §13).
- *LangSmith tracing (`LANGCHAIN_TRACING_V2`) for latency, token, and step-level observability in a deployed setting (Module 6 §5).*

**Escalation rules** — see §4.

**Recovery agent** — **gated in code to `decision IN ('approve','inconclusive')`**; retrieval-grounded structured output; explicitly advisory — one audit row, no system-of-record write.

---

## 3. Evaluation metrics

The Phase 9 harness (`eval_notebook.ipynb`) already runs 10 predetermined claims
through the live orchestrator and diffs actual vs. expected outcome *and* full
check-ledger detail. The set spans both claim types and four evidence-completeness
levels (clean / unfounded / incomplete / irresolvable): 4 Approve, 5 Deny, 1
Inconclusive — deliberately Deny-heavy so the FAIL / short-circuit / Inconclusive
paths are actually exercised.

| Metric | Definition | Target | How measured |
|--------|------------|--------|--------------|
| **Decision accuracy** | Exact match of `decision` vs. predetermined expected | 10/10 now; ≥ 95% on an expanded stratified set | `eval_notebook.ipynb` (asserts 10/10) |
| **Path / trace correctness** | Right outcome reached via the right checks resolving the right way | 100% on the seed set | Notebook diffs each check's `status` **and** `detail`, not just the outcome — catches "right answer, wrong reasoning" |
| **Groundedness** | Share of closed checks whose `detail` traces to a tool result or human answer | 100% (by construction; monitored as a regression) | Inspect `check_ledger.detail` provenance |
| **Citation coverage** | Share of Approve/Deny decisions carrying a policy citation | ≥ 90% (remainder legitimately `BLOCKED`) | `policy_*` check detail |
| **Retrieval quality** | precision@3 of `search_policy` vs. a labelled query→clause set; empty-result rate; wrong-claim-type rate | wrong-type = 0 (enforced); empty-rate tracked for drift | Offline retrieval eval over labelled queries |
| **Safety / short-circuit correctness** | Every seeded FAIL scenario Denies; no seeded Deny scenario Approves | 100% — asymmetric: a wrong Approve is worse than a wrong Deny | Seed-set assertions |
| **Escalation rate** | Fraction of runs that call `ask_human` | No hard target; alert on drift up (tool-coverage gap) or an implausibly low rate | Count `tool_call` / `ask_human` audit rows |
| **Fallback success** | Of forced-Inconclusive runs, fraction that terminated cleanly with a reason naming the unresolved check | 100% | Notebook checks the forced-Inconclusive reason string |
| **Termination** | Runs finishing within the iteration cap | 100%; zero non-terminating runs | Iteration count in final state |
| **Latency & cost** | p50 / p95 wall-clock and token spend per claim, per provider | Regression gate on provider swap | LangSmith / run timing |
| **Robustness** | Malformed-tool-call injection → run continues, ends Inconclusive, never 500 | 100% | Fault-injection test (regression for R4) |
| **Recovery calibration** | LLM-judged eligible/not-eligible vs. a human-labelled set; over-eligibility rate | over-eligibility ≤ 5% (advisory output) | Offline labelled comparison |

---

## 4. When a human must decide instead of the agent

Two mechanisms: **(a) in-run `ask_human`** — automatic today; **(b) risk-tiered
routing** — proposed, following Module 6's control-room model (auto-pass below a
threshold, human review above it — a *router*, not a blocking *gate*).

| Trigger | Signal in the system | Action | Status |
|---------|----------------------|--------|--------|
| A required fact has no tool path (e.g. missing `account_profiles` row) | Check stays `UNKNOWN` after available tools are tried | Decisioning calls `ask_human`; run suspends (`awaiting_input`), resumes on answer | **Implemented** |
| Human-question budget exhausted, a check still open | `questions_asked ≥ 3` | Stop, force Inconclusive, surface the reason | **Implemented** |
| Iteration or no-progress cap hit | `iteration ≥ 12` or `iterations_without_progress ≥ 5` | Force Inconclusive; do **not** write a decision | **Implemented** |
| Retrieval returns nothing for a check that needs a citation | `policy_*` check → `BLOCKED` | Contributes to Inconclusive — never Approve on an uncited rule | **Implemented** |
| `ask_human` answer doesn't cleanly parse | First word not yes/no/confirmed/denied/… | Check stays `UNKNOWN` → Inconclusive rather than a guess | **Implemented** (partial — see R7) |
| Approve above a policy-defined dollar threshold | Claim amount vs. threshold from policy | Route to async human confirmation *before* the terminal write | *Proposed* — needs a claim-amount field + a policy threshold |
| Low model confidence / self-contradiction, or a weak/local provider | Explicit confidence signal (not yet emitted) | Route to human rather than let the loop guess | *Proposed* |
| Policy-sensitive claim type or flagged account | Account / type on a review list | Mandatory human review regardless of ledger state | *Proposed* |

**Design stance (Module 6 §3).** Prefer a **router over a gate** — the common
claim flows straight through; only the high-impact or low-confidence tail blocks.
Present the review as a **decision card**, not a log dump: the current "The agent
needs input" view already shows the specific question and the check it is trying to
resolve, with yes / no controls — the reviewer can act on it without reading the
transcript. Recurring `ask_human` triggers for the *same* missing data are a signal
to fix tool coverage upstream, not to keep routing to a human (Module 6 §3, the
feedback trap).

---

## 5. How guardrails, evaluation, and human intervention combine

They operate on one shared substrate — the **check ledger** and the **audit
trail** — at three different times:

- **Before / during each step, guardrails constrain what the agent *can* do:**
  disjoint tool sets, read-only tools, one tool per turn, a bounded loop, and an
  outcome that is computed from the ledger rather than spoken by the model. This is
  *defense in depth* — no single control is load-bearing. A perfect model with a
  poisoned corpus would still be caught by the `claim_type` filter and the relevance
  floor; a broken tool call is caught by the execution guard; a model that "decides"
  Approve is overruled by `compute_decision()`.
- **Between deploys, evaluation proves the constraints are actually holding:** the
  10-claim harness checks not just outcomes but the *path* — which checks resolved
  and how — and asserts the fail-safe behaviours (short-circuit on FAIL, clean
  forced-Inconclusive). It is the *continuous feedback engine* from Module 6 §5: a
  production failure becomes a new seed claim, the cause is fixed, and the eval
  proves the fix before the next deploy.
- **At the edge of the agent's competence, human intervention is the designed
  fallback** — not an afterthought bolted on. The guardrails are written so that a
  claim the agent *cannot* ground either pauses for a human (`ask_human`) or
  terminates as an explained Inconclusive. The human is never the throughput
  bottleneck for the common case, because the common case never reaches them.

Net effect: **the system fails safe.** Every run ends in one of three states — an
evidence-backed Approve/Deny, a human-answered resolution, or an Inconclusive that
names exactly which check it could not close — and all three are fully
reconstructable from the audit trail alone.

---

## 6. Trade-offs considered

- **Autonomy vs. reliability.** Chose a **deterministic decision core** over an
  LLM-judged one. The model cannot assert an outcome. Cost: genuinely novel claims
  that don't fit the check taxonomy land Inconclusive instead of getting a
  best-effort call. Benefit: a hard floor on wrong Approves, and every decision is
  auditable.
- **Autonomy vs. oversight.** `ask_human` is a *last resort* with a budget of 3.
  More questions → fewer Inconclusives but more processor load and more rubber-stamp
  risk; fewer → faster but more unresolved claims. Three is the compromise.
- **Efficiency vs. safety.** `parallel_tool_calls=False`, one tool per turn, and a
  12-iteration cap make a run slower and chattier than a free-running agent, but
  keep every run bounded, linear, and cheap to audit. Same reason ReAct was chosen
  over Tree-of-Thought: a single trajectory maps directly onto the audit trail; a
  branching search does not (requirements §5).
- **Coverage vs. simplicity.** Two sub-agents, not five. Enough to separate "gather
  evidence" from "decide, escalate, and write" — a split that matters because the
  two halves have different, safety-relevant tool access. More agents would add
  coordination surface and token cost without a matching safety gain.
- **Groundedness vs. availability.** The relevance floor returns *zero* rather than
  a weak match, producing more `BLOCKED` checks and more Inconclusives — but no
  decision is ever cited to a marginal clause.
- **Deployability vs. determinism.** Supporting local models (Ollama) widens where
  the system can run, but weak models don't honour `tool_choice="required"`.
  Mitigated by the tool-error guard and surfaced as a provider-quality eval gate
  rather than a silent switch.

---

## 7. How this plan supports a safer real-world deployment

The architecture already provides the properties a real deployment needs:

- **Traceability** — every decision is reconstructable from the append-only audit
  trail alone, with no reliance on model memory; retrieval is logged in full, not
  just the part that was used.
- **Resumability** — a claim waiting on a human survives process restarts
  (checkpointed run state), so human latency never corrupts a run.
- **Boundedness** — iteration and question caps guarantee termination; there is no
  unbounded-cost failure mode.
- **Fail-safe default** — the terminal states are an evidence-backed decision or an
  Inconclusive that names the unresolved check; the system does not guess under
  uncertainty.
- **Small blast radius** — every tool is read-only except one isolated,
  evidence-gated write.
- **Provider portability with a gate** — the LLM provider can be swapped, and an
  eval run is the gate for accepting a new one.

**Gaps to close before a production deployment:** prompt-injection screening on
free-text inputs (R1-adjacent); risk-tiered dollar-threshold routing (§4); an
explicit model-confidence signal; policy-corpus versioning and ingest-time
validation (R3); audit-log tamper protection (Module 6 Layer 5); and rate / load
limiting on the API. The plan's contribution is that the **decision is already on
deterministic rails and the trace is already on disk** — the remaining work is
adding gates at the edges, not re-establishing trust in the core.

---

### Module 6 concepts this plan applies

Defense in depth across layers · a gate/router at every junction of the agentic loop
· resilience over perfect prevention · router-not-gate for high-impact review ·
reviewer interface as a decision card, not a form · fix recurring errors upstream
instead of re-routing them · knowledge ≠ decision-making (the model researches; the
rules decide) · bound the loop, not the human · continuous-feedback evaluation
(production failure → seed case → fix → prove).
