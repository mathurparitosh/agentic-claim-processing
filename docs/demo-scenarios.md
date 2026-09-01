# Demo Scenarios

Ready-made claims for demoing the agent, with a focus on the **human-in-the-loop**
(`ask_human`) flow. Ground truth and rationale live in
[`../specs/eval_claims.md`](../specs/eval_claims.md); scenario definitions and the
synthetic evidence are in `backend/generate_synthetic_data.py`
(`SCENARIOS`). Prerequisite: fixtures loaded
(`python -m backend.generate_synthetic_data`) and the app running
(`./scripts/start.sh`).

---

## Human-in-the-loop demo (ACC-9006 / 9007 / 9010)

### Why these three aren't in the account dropdown

The claim form's account list is `GET /accounts`, which is literally
`SELECT account_id, member_name FROM account_profiles`. **ACC-9006, ACC-9007, and
ACC-9010 deliberately have no `account_profiles` row** — only `transactions` and
`access_logs`.

That missing row is the whole point: `lookup_account_profile` returns "not found", so
`account_standing` / `account_red_flags` (fraud) can't be resolved by any tool. The
run can't reach a decision on evidence alone, so the **Decisioning sub-agent calls
`ask_human`**, the run suspends (`status = awaiting_input`), and it resumes and
finishes once you answer (requirements.md §10, "Human-in-the-Loop").

If you loaded profile rows for these accounts they'd resolve on their own and never
demonstrate `ask_human` — so leave them out.

### Filing a claim for a profile-less account from the UI

1. **Account ID** field is a free-text input with autocomplete, not a locked
   dropdown. Type the account ID (e.g. `ACC-9006`) even though it isn't suggested.
2. Because it isn't a "known" account, the form automatically swaps the **Disputed
   transaction ID** dropdown for a free-text box. Type the transaction ref from the
   table below.
3. Pick the **claim type** and **reason** from the table, submit.
4. The claim goes `processing → awaiting_input`. The claim detail view shows
   **"The agent needs input"** with the question and the check it's trying to resolve.
5. Answer with the **Yes** / **No** buttons or the free-text box. The run resumes and
   finishes.

### The three scenarios

| Account | Claim type | Reason | Disputed txn | Answer when asked | Expected outcome |
|---|---|---|---|---|---|
| `ACC-9006` | Fraud | `not_recognized` | `TXN-6007` — $2,300, GiftCardHub Online, Boise ID (vs. a clean Raleigh NC history) | **yes** ("account in good standing") | **Approve** — the human answer closes `account_standing` PASS; the anomaly + risk-flagged login already made the other checks PASS. |
| `ACC-9007` | Billing dispute | `duplicate_charge` | `TXN-7107` — $47.25, exact duplicate of `TXN-7106` same merchant/time | **no** | **Deny** — the "no" closes `account_standing` FAIL, which short-circuits to Deny even though the duplicate and the policy checks would have passed. |
| `ACC-9010` | Fraud | `other` | `TXN-1007` — $1,650, ElectraGift Online, Bend OR (vs. a clean Boise ID history) | ambiguous every time, e.g. **"not sure, can't confirm either way"** | **Inconclusive** — the answer never resolves `account_red_flags` (stays UNKNOWN); after the 3-question human budget / no-progress cap the run is forced Inconclusive, reason naming `account_red_flags`. |

Notes:
- **First word matters.** The answer parser keys off the first word: `yes` / `confirmed`
  / `true` / `correct` → check PASS; `no` / `denied` / `false` / `negative` → FAIL;
  anything else → stays UNKNOWN (that's what makes ACC-9010 end Inconclusive).
- **Question budget is 3 per claim.** ACC-9010 will be asked up to three times before
  it gives up.
- The suspended run is checkpointed in Postgres — you can restart the backend while a
  claim is `awaiting_input` and still answer it afterward.

### What to watch in the Audit Trail tab

- `agent_think` rows tagged `research` then `decisioning` — the sub-agent handoff.
- a `tool_call` row for `ask_human` (only the Decisioning sub-agent has that tool).
- after you answer: a `human_answer` row (`source: human`), then more `agent_think` /
  `tool_call` rows, then `determination_written`.

### Same thing via API (no UI)

```bash
BASE=http://localhost:8000
AUTH="Authorization: Bearer $(grep '^AUTH_PASSWORD=' .env.local | cut -d= -f2)"

# 1. submit
CID=$(curl -s -X POST "$BASE/claims" -H "$AUTH" -H 'Content-Type: application/json' -d '{
  "claim_type": "fraud",
  "claim_payload": {"account_id":"ACC-9006","disputed_transaction_id":"TXN-6007",
                    "reason":"not_recognized","filed_at":"2026-07-25T09:00:00Z"}
}' | python3 -c 'import sys,json;print(json.load(sys.stdin)["claim_id"])')

# 2. poll until status == awaiting_input, then read the question
curl -s "$BASE/claims/$CID" -H "$AUTH" | python3 -m json.tool
curl -s "$BASE/claims/$CID/questions" -H "$AUTH" | python3 -m json.tool

# 3. answer -> run resumes
curl -s -X POST "$BASE/claims/$CID/answer" -H "$AUTH" -H 'Content-Type: application/json' \
  -d '{"answer":"yes"}'

# 4. poll until completed, read the decision
curl -s "$BASE/claims/$CID/decision" -H "$AUTH" | python3 -m json.tool
```

For ACC-9007 use `claim_type: billing_dispute`, `reason: duplicate_charge`,
`disputed_transaction_id: TXN-7107`, answer `"no"`. For ACC-9010 use
`reason: other`, `disputed_transaction_id: TXN-1007`, answer
`"not sure, can't confirm either way"` each time it asks.

---

## The other seven accounts (straight-through, no `ask_human`)

These have full `account_profiles` rows, so they appear in the dropdown and the
transaction picker works normally. They resolve on evidence alone.

| Account | Claim type | Reason | Disputed txn | Expected | Why |
|---|---|---|---|---|---|
| `ACC-9001` | Fraud | `unauthorized_transaction` | `TXN-7001` | **Approve** | outlier amount + location, risk-flagged login, standing `good`, policy clause found — all 4 checks PASS |
| `ACC-9002` | Billing dispute | `duplicate_charge` | `TXN-2007` | **Approve** | real near-duplicate pair found, standing `good`, policy clause found |
| `ACC-9003` | Fraud | `unauthorized_transaction` | `TXN-3007` | **Approve** | same shape as ACC-9001, different account/city/amount |
| `ACC-9004` | Fraud | `unauthorized_transaction` | `TXN-4007` | **Deny** | account `standing = suspended` → `account_red_flags` FAIL short-circuits |
| `ACC-9005` | Billing dispute | `duplicate_charge` | `TXN-5007` | **Deny** | no matching same-amount/same-merchant charge in the 24h window → `duplicate_charge_check` FAIL |
| `ACC-9008` | Billing dispute | `not_recognized` | `TXN-8099` | **Deny** | `disputed_transaction_id` matches no real transaction → `transaction_exists` FAIL |
| `ACC-9009` | Fraud | `unauthorized_transaction` | `TXN-9107` | **Deny** | ordinary transaction — typical amount, known location, no risk-flagged login → anomaly + access-log checks FAIL |

Coverage across all 10: 4 Approve (9001/2/3/6), 5 Deny (9004/5/7/8/9), 1 Inconclusive
(9010).

---

## Resetting between demos

Clear claims but keep the fixtures and policy corpus:

```bash
docker compose exec -T postgres psql -U postgres -d claims_dev -c 'DELETE FROM claims;'
```

`check_ledger` and `audit_trail` cascade automatically. See
[`data-model.md`](./data-model.md#cleanup-recipes) for a full clean slate (episodic
memory + LangGraph checkpoints).
