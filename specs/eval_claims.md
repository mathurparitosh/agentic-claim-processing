# Phase 9 — Evaluation Claim Set (10 claims)

Companion to [tracker.md](tracker.md) Phase 9. Written out **before** generating synthetic
evidence, per that phase's first checkbox — this table is the predetermined
ground truth; `backend/eval_notebook.ipynb` runs each claim through the live orchestrator
graph and diffs actual vs. expected. Scenario definitions (narrative + `expect` blocks
used to mechanically validate LLM-generated evidence before it's loaded) live in
`backend/generate_synthetic_data.py`'s `SCENARIOS` list, same generator used since Phase 4.

Ten claims were chosen to span both claim types, several `reason` values, and four
evidence-completeness levels: **complete/clean** (the check-owning fact is unambiguous
and favorable), **complete/unfounded** (unambiguous but unfavorable — the claim itself
doesn't hold up), **incomplete** (a required fact has no tool path to resolution, forcing
`ask_human`), and **irresolvable** (incomplete *and* the human's answer doesn't clearly
resolve it either, so no path to a resolved check exists at all).

| # | Account | Claim type | Reason | Evidence completeness | Expected decision | Resolving mechanism |
|---|---------|-----------|--------|------------------------|--------------------|----------------------|
| 1 | ACC-9001 | fraud | unauthorized_transaction | Complete / clean | **Approve** | Outlier amount+location, risk-flagged access log near the transaction, standing `good`, `search_policy` finds a governing `fraud` clause. All 4 checks PASS. |
| 2 | ACC-9002 | billing_dispute | duplicate_charge | Complete / clean | **Approve** | `check_duplicate_charge` finds the real near-duplicate pair, standing `good`, `search_policy` finds a governing `billing_dispute` clause. All 4 checks PASS. |
| 3 | ACC-9003 | fraud | unauthorized_transaction | Complete / clean | **Approve** | Same shape as #1 (independent scenario, different account/city/amount) — confirms #1 isn't a lucky one-off. |
| 4 | ACC-9004 | fraud | unauthorized_transaction | Complete / unfounded (bad standing) | **Deny** | Account `standing = suspended` → `account_red_flags` FAILs immediately (any FAIL short-circuits to Deny regardless of the other 3 checks). |
| 5 | ACC-9005 | billing_dispute | duplicate_charge | Complete / unfounded (no actual duplicate) | **Deny** | Member believes they were charged twice; generated data deliberately contains no matching same-amount/same-merchant transaction within the 24h window → `check_duplicate_charge` finds nothing → `duplicate_charge_check` FAILs. |
| 6 | ACC-9006 | fraud | not_recognized | Incomplete, human-resolved favorably | **Approve** | Account has no `account_profiles` row at all (deliberately not loaded) → `account_standing`/`account_red_flags` have no tool path to resolution (`UNKNOWN`, not `FAIL`) → agent must `ask_human`. Harness answers **"yes"** (account in good standing) → PASS. Transaction is a clean anomaly + risk-flagged access log like #1, so the other 3 checks resolve to PASS on their own → Approve once the human answer lands. |
| 7 | ACC-9007 | billing_dispute | duplicate_charge | Incomplete, human-resolved unfavorably | **Deny** | Same missing-profile setup as #6, but for a billing_dispute: real duplicate exists (`duplicate_charge_check` would PASS) and policy match exists, but harness answers the `account_standing` question **"no"** → FAILs → Deny, overriding the two checks that would otherwise have passed. |
| 8 | ACC-9008 | billing_dispute | not_recognized | Incomplete / invalid claim | **Deny** | The claim's `disputed_transaction_id` doesn't correspond to any real transaction on the account (a data-entry-error / phantom-transaction scenario) → `lookup_transaction` returns `found: False` → `transaction_exists` FAILs immediately. |
| 9 | ACC-9009 | fraud | unauthorized_transaction | Complete / unfounded (no anomaly) | **Deny** | Disputed transaction is ordinary — typical amount, a known location, no risk-flagged access log nearby. `transaction_pattern_anomaly` and `system_access_log_check` both FAIL (member's fraud claim doesn't hold up against the evidence). |
| 10 | ACC-9010 | billing_dispute→fraud* | other | Irresolvable | **Inconclusive** | Same missing-profile setup as #6/#7, but the harness answers every `ask_human` question ambiguously ("not sure, can't confirm either way") — not clearly yes/no, so `account_red_flags` stays `UNKNOWN` even after the human answers. Budget/no-progress caps are eventually hit with one check permanently unresolved → forced Inconclusive, reason names `account_red_flags`. |

\* #10 is `claim_type: fraud` (not billing_dispute) — the "other" reason is valid for
either claim type in `ClaimForm.jsx`'s dropdown; picked fraud here so the unresolvable
check is `account_red_flags` (fraud's account-profile-derived check), exercising the
same missing-profile mechanism as #6/#7 rather than inventing a third.

**Coverage achieved**: 6 fraud (#1,3,4,6,9,10) / 4 billing_dispute (#2,5,7,8). Decisions:
4 Approve (#1,2,3,6), 5 Deny (#4,5,7,8,9), 1 Inconclusive (#10) — deliberately Deny-heavy
versus the first 3 Phase 4-era scenarios (all Approve), since those were the only ones
that existed before this phase and an eval set that's all-Approve doesn't exercise the
decision rule's FAIL/short-circuit or Inconclusive paths at all.

**Human-in-the-loop answer script** (used only by `eval_notebook.ipynb`'s auto-responder
for scenarios #6/#7/#10 — #1-5,8,9 never trigger `ask_human` since their `account_profiles`
row is loaded normally): #6 → `"yes"`, #7 → `"no"`, #10 → `"not sure, can't confirm either
way"` (repeated on every ask, to genuinely exhaust the budget rather than resolve on a later
try).
