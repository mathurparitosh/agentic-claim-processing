"""Synthetic research-source data generator (tracker.md Phase 4).

GPT generates transaction/access-log/account-profile records for a hand-picked claim
scenario. Each generated record is checked against the scenario's `expect` block before
loading -- per technical.md's Synthetic Data row, generated evidence must not
accidentally contradict the claim's intended expected outcome.

Usage:
    python -m backend.generate_synthetic_data          # generate + review + load all scenarios
    python -m backend.generate_synthetic_data --dry-run  # generate + review only, no DB writes
"""
import argparse
import json
import sys
from datetime import datetime

from dotenv import load_dotenv

load_dotenv(".env.local")

from openai import OpenAI  # noqa: E402

from . import db  # noqa: E402

MODEL = "gpt-5.6-luna"

RESPONSE_SCHEMA_DESCRIPTION = """
Return a JSON object with exactly these keys:

{
  "account_profile": {
    "member_name": string,
    "opened_at": ISO 8601 date,
    "standing": "good" | "flagged" | "suspended",
    "fraud_red_flags": array of short strings (empty array if none),
    "dispute_history_count": integer
  },
  "transactions": [
    {
      "transaction_ref": string (e.g. "TXN-1001"),
      "occurred_at": ISO 8601 timestamp,
      "amount": number,
      "merchant": string,
      "location": string (city, state),
      "channel": "card_present" | "online" | "atm" | "check",
      "status": "posted" | "pending" | "reversed"
    },
    ...
  ],
  "access_logs": [
    {
      "occurred_at": ISO 8601 timestamp,
      "event_type": "login" | "password_reset" | "device_change" | "failed_login",
      "device_id": string,
      "ip_address": string,
      "location": string (city, state),
      "risk_flag": boolean
    },
    ...
  ]
}

One transaction's transaction_ref MUST equal the scenario's disputed_transaction_ref.
Output raw JSON only, no markdown fences.
"""


# ---- Hand-picked scenarios ----------------------------------------------------
#
# Scenario 1 is the Phase 4 smoke-test claim: a `fraud` claim designed so the three
# tool-resolvable checks (account_red_flags, transaction_pattern_anomaly,
# system_access_log_check) clearly PASS. The fourth check, policy_liability_rule, is
# retrieval-only and Pinecone has 0 vectors until Phase 3 ingests policy docs -- so the
# run is expected to end Inconclusive on that one check, not Approve. That is the
# correct, honest behavior per requirements.md §9 ("no matching policy found" is a valid
# outcome), not a bug in the agent.

SCENARIOS = [
    {
        "account_id": "ACC-9001",
        "claim_type": "fraud",
        "disputed_transaction_ref": "TXN-7001",
        "narrative": (
            "Member Dana Ruiz reports a transaction she does not recognize. The account has "
            "a clean history: 6-10 unremarkable transactions over the past 3 months, all "
            "under $120, all in Austin, TX, all card_present at familiar merchants (grocery, "
            "gas, pharmacy). The disputed transaction TXN-7001 is an outlier: $1,450, an "
            "online electronics merchant, and NOT in Austin (use a different city/state). It "
            "occurred at 2026-07-15T02:14:00Z. Also include an access_logs entry within 2 "
            "hours before that timestamp showing a login from a device_id and ip_address "
            "never seen in the member's normal pattern, in the same unfamiliar city as the "
            "disputed transaction, with risk_flag true. Account standing is 'good' with no "
            "fraud_red_flags and dispute_history_count 0 -- this member has no history of "
            "abusing the dispute process."
        ),
        "expect": {
            "account_profile.standing": "good",
            "disputed_transaction.amount_over": 500,
            "disputed_transaction.location_differs_from_history": True,
            "access_logs.has_risk_flag_near_transaction": True,
        },
        "claim_payload": {
            "account_id": "ACC-9001",
            "disputed_transaction_id": "TXN-7001",
            "reason": "unauthorized_transaction",
            "filed_at": "2026-07-20T09:00:00Z",
        },
    },
    {
        "account_id": "ACC-9002",
        "claim_type": "billing_dispute",
        "disputed_transaction_ref": "TXN-2007",
        "narrative": (
            "Member Marcus Webb has an everyday spending pattern. Generate EXACTLY 7 "
            "transactions total (transaction_ref TXN-2001 through TXN-2007), over the past "
            "2 months, all under $80, all card_present in Denver, CO -- groceries, coffee "
            "shops, a gym membership, gas. The last two (TXN-2006 and TXN-2007) are "
            "near-duplicates: same merchant, same amount (around $54), posted within a few "
            "hours of each other on the same day, both card_present in Denver. TXN-2007 is "
            "the later, disputed one -- the member believes he was charged twice by "
            "mistake. Account standing is 'good', no fraud_red_flags, dispute_history_count "
            "1 (one prior unrelated dispute, already resolved)."
        ),
        "expect": {
            "account_profile.standing": "good",
        },
        "claim_payload": {
            "account_id": "ACC-9002",
            "disputed_transaction_id": "TXN-2007",
            "reason": "duplicate_charge",
            "filed_at": "2026-07-25T10:00:00Z",
        },
    },
    {
        "account_id": "ACC-9003",
        "claim_type": "fraud",
        "disputed_transaction_ref": "TXN-3007",
        "narrative": (
            "Member Priya Nandakumar reports a transaction she does not recognize. Generate "
            "EXACTLY 7 transactions total (transaction_ref TXN-3001 through TXN-3006, plus "
            "the disputed TXN-3007). The first 6 are a clean, unremarkable history over the "
            "past 3 months, all under $150, all in Seattle, WA, all card_present at familiar "
            "merchants (grocery, pharmacy, restaurants, transit). TXN-3007 is an outlier: "
            "$2,100, an online electronics or gift-card merchant, and NOT in Seattle (use a "
            "different city/state than Seattle and than Austin/Phoenix/Denver). It occurred "
            "at 2026-07-22T03:40:00Z. Also include an access_logs entry within 2 hours "
            "before that timestamp showing a login from a device_id and ip_address never "
            "seen in the member's normal pattern, in the same unfamiliar city as the "
            "disputed transaction, with risk_flag true. Account standing is 'good' with no "
            "fraud_red_flags and dispute_history_count 0."
        ),
        "expect": {
            "account_profile.standing": "good",
            "disputed_transaction.amount_over": 500,
            "disputed_transaction.location_differs_from_history": True,
            "access_logs.has_risk_flag_near_transaction": True,
        },
        "claim_payload": {
            "account_id": "ACC-9003",
            "disputed_transaction_id": "TXN-3007",
            "reason": "unauthorized_transaction",
            "filed_at": "2026-07-26T09:00:00Z",
        },
    },

    # ---- Phase 9 eval-set additions (specs/eval_claims.md) ----------------------
    # ACC-9001/9002/9003 above are all clean-Approve; these 7 fill out the eval set's
    # Deny/Approve-via-human/Deny-via-human/Inconclusive coverage. See
    # specs/eval_claims.md for the full predetermined-outcome table and rationale.

    {
        "account_id": "ACC-9004",
        "claim_type": "fraud",
        "disputed_transaction_ref": "TXN-4007",
        "narrative": (
            "Member Carlos Reyes reports a transaction he does not recognize. Generate "
            "EXACTLY 6 clean history transactions (TXN-4001 through TXN-4006) over the past "
            "3 months, all under $130, all in Miami, FL, all card_present at familiar "
            "merchants, plus the disputed TXN-4007: $1,800, an online electronics merchant, "
            "NOT in Miami (use a different city/state than any other account already used in "
            "this data set). It occurred at 2026-07-18T04:05:00Z. Include an access_logs "
            "entry within 2 hours before that timestamp showing a login from an unfamiliar "
            "device_id/ip_address in the same unfamiliar city, risk_flag true. IMPORTANT: "
            "account standing must be 'suspended' (not 'good') with fraud_red_flags "
            "including at least one entry like 'flagged for prior fraud investigation' and "
            "dispute_history_count 2 -- this account is already under scrutiny, independent "
            "of whether this specific transaction turns out to be real fraud."
        ),
        "expect": {
            "account_profile.standing": "suspended",
            "disputed_transaction.amount_over": 500,
            "disputed_transaction.location_differs_from_history": True,
            "access_logs.has_risk_flag_near_transaction": True,
        },
        "claim_payload": {
            "account_id": "ACC-9004",
            "disputed_transaction_id": "TXN-4007",
            "reason": "unauthorized_transaction",
            "filed_at": "2026-07-19T09:00:00Z",
        },
    },
    {
        "account_id": "ACC-9005",
        "claim_type": "billing_dispute",
        "disputed_transaction_ref": "TXN-5007",
        "narrative": (
            "Member Angela Fitch has an everyday spending pattern. Generate EXACTLY 7 "
            "transactions total (TXN-5001 through TXN-5007), over the past 2 months, all "
            "under $90, all card_present in Portland, OR -- groceries, coffee shops, a "
            "pharmacy, gas. TXN-5007 is the last one, dated 2026-07-24, and is the one the "
            "member disputes, believing she was charged twice for it. IMPORTANT: this is a "
            "mistaken belief -- make sure NO other transaction in the whole list shares both "
            "the same amount AND the same merchant as TXN-5007 within 24 hours of it (vary "
            "the amounts and merchants of the other transactions enough that none accidentally "
            "collides). Account standing is 'good', no fraud_red_flags, dispute_history_count 0."
        ),
        "expect": {
            "account_profile.standing": "good",
            "no_duplicate_for_disputed": True,
        },
        "claim_payload": {
            "account_id": "ACC-9005",
            "disputed_transaction_id": "TXN-5007",
            "reason": "duplicate_charge",
            "filed_at": "2026-07-25T10:00:00Z",
        },
    },
    {
        "account_id": "ACC-9006",
        "claim_type": "fraud",
        "disputed_transaction_ref": "TXN-6007",
        "narrative": (
            "Member Farah Osei reports a transaction she does not recognize. Generate "
            "EXACTLY 6 clean history transactions (TXN-6001 through TXN-6006) over the past "
            "3 months, all under $140, all in Raleigh, NC, all card_present at familiar "
            "merchants, plus the disputed TXN-6007: $2,300, an online gift-card merchant, NOT "
            "in Raleigh (use a city/state not already used elsewhere in this data set). It "
            "occurred at 2026-07-21T03:10:00Z. Include an access_logs entry within 2 hours "
            "before that timestamp showing a login from an unfamiliar device_id/ip_address in "
            "the same unfamiliar city, risk_flag true. Account standing 'good', no "
            "fraud_red_flags, dispute_history_count 0 (this account_profile will NOT actually "
            "be loaded into the system for this scenario -- generate it anyway per the schema)."
        ),
        "expect": {
            "account_profile.standing": "good",
            "disputed_transaction.amount_over": 500,
            "disputed_transaction.location_differs_from_history": True,
            "access_logs.has_risk_flag_near_transaction": True,
        },
        "load_account_profile": False,
        "claim_payload": {
            "account_id": "ACC-9006",
            "disputed_transaction_id": "TXN-6007",
            "reason": "not_recognized",
            "filed_at": "2026-07-22T09:00:00Z",
        },
        "human_answer": "yes",
    },
    {
        "account_id": "ACC-9007",
        "claim_type": "billing_dispute",
        "disputed_transaction_ref": "TXN-7107",
        "narrative": (
            "Member Ben Okafor has an everyday spending pattern. Generate EXACTLY 7 "
            "transactions total (TXN-7101 through TXN-7107 -- use this 71xx range, not 7001, "
            "to avoid colliding with the existing ACC-9001 scenario's TXN-7001), over the "
            "past 2 months, all under $85, all card_present in Nashville, TN. The last two "
            "(TXN-7106 and TXN-7107) are near-duplicates: same merchant, same amount (around "
            "$47), posted within a few hours of each other on the same day, both card_present "
            "in Nashville. TXN-7107 is the later, disputed one -- the member believes he was "
            "charged twice by mistake, and in this scenario he's right, it IS a genuine "
            "duplicate. Account standing 'good', no fraud_red_flags, dispute_history_count 0 "
            "(this account_profile will NOT actually be loaded into the system for this "
            "scenario -- generate it anyway per the schema)."
        ),
        "expect": {
            "account_profile.standing": "good",
        },
        "load_account_profile": False,
        "claim_payload": {
            "account_id": "ACC-9007",
            "disputed_transaction_id": "TXN-7107",
            "reason": "duplicate_charge",
            "filed_at": "2026-07-27T10:00:00Z",
        },
        "human_answer": "no",
    },
    {
        "account_id": "ACC-9008",
        "claim_type": "billing_dispute",
        "disputed_transaction_ref": "TXN-8007",
        "narrative": (
            "Member Sylvia Marchetti has an everyday spending pattern. Generate EXACTLY 7 "
            "transactions total (TXN-8001 through TXN-8007), over the past 2 months, all "
            "under $95, all card_present in Salt Lake City, UT -- groceries, gas, a gym "
            "membership, coffee shops. All ordinary, no duplicates, no anomalies. Account "
            "standing 'good', no fraud_red_flags, dispute_history_count 0."
        ),
        "expect": {
            "account_profile.standing": "good",
        },
        "claim_payload": {
            "account_id": "ACC-9008",
            # Deliberately does NOT match any of TXN-8001..TXN-8007 -- the member is
            # disputing a transaction reference that doesn't actually exist on the
            # account (data-entry error / phantom transaction), not one of the real ones.
            "disputed_transaction_id": "TXN-8099",
            "reason": "not_recognized",
            "filed_at": "2026-07-28T09:00:00Z",
        },
    },
    {
        "account_id": "ACC-9009",
        "claim_type": "fraud",
        "disputed_transaction_ref": "TXN-9107",
        "narrative": (
            "Member Owen Delacroix reports a transaction he claims he does not recognize, "
            "but it will turn out the claim doesn't hold up against the evidence. Generate "
            "EXACTLY 7 transactions total (TXN-9101 through TXN-9107 -- use this 91xx range "
            "to avoid colliding with ACC-9001's TXN-7001-style refs), over the past 3 "
            "months, all card_present in Cleveland, OH, at familiar merchants (grocery, gas, "
            "pharmacy, restaurants), amounts between $20 and $95. TXN-9107, the disputed one, "
            "must be ORDINARY and NOT anomalous: amount also between $20 and $95 (well under "
            "3x the average of the others), same city (Cleveland, OH), same "
            "card_present channel, at a familiar-type merchant. Do NOT include any "
            "access_logs entries with risk_flag true anywhere in the data -- all access_logs "
            "activity should look completely routine. Account standing 'good', no "
            "fraud_red_flags, dispute_history_count 0."
        ),
        "expect": {
            "account_profile.standing": "good",
            "disputed_transaction.amount_not_over_avg_multiple": 3,
            "disputed_transaction.location_in_history": True,
            "access_logs.no_risk_flag": True,
        },
        "claim_payload": {
            "account_id": "ACC-9009",
            "disputed_transaction_id": "TXN-9107",
            "reason": "unauthorized_transaction",
            "filed_at": "2026-07-29T09:00:00Z",
        },
    },
    {
        "account_id": "ACC-9010",
        "claim_type": "fraud",
        "disputed_transaction_ref": "TXN-1007",
        "narrative": (
            "Member Junko Watanabe reports a transaction she does not recognize. Generate "
            "EXACTLY 6 clean history transactions (TXN-1001 through TXN-1006 -- use this 10xx "
            "range to avoid colliding with other accounts in this data set) over the past 3 "
            "months, all under $110, all in Boise, ID, all card_present at familiar "
            "merchants, plus the disputed TXN-1007: $1,650, an online electronics or "
            "gift-card merchant, NOT in Boise (use a city/state not already used elsewhere in "
            "this data set). It occurred at 2026-07-23T02:50:00Z. Include an access_logs "
            "entry within 2 hours before that timestamp showing a login from an unfamiliar "
            "device_id/ip_address in the same unfamiliar city, risk_flag true. Account "
            "standing 'good', no fraud_red_flags, dispute_history_count 0 (this "
            "account_profile will NOT actually be loaded into the system for this scenario "
            "-- generate it anyway per the schema)."
        ),
        "expect": {
            "account_profile.standing": "good",
            "disputed_transaction.amount_over": 500,
            "disputed_transaction.location_differs_from_history": True,
            "access_logs.has_risk_flag_near_transaction": True,
        },
        "load_account_profile": False,
        "claim_payload": {
            "account_id": "ACC-9010",
            "disputed_transaction_id": "TXN-1007",
            "reason": "other",
            "filed_at": "2026-07-24T09:00:00Z",
        },
        "human_answer": "not sure, can't confirm either way",
    },
]


def generate_scenario(scenario: dict) -> dict:
    client = OpenAI()
    prompt = (
        f"Generate synthetic banking research-source data for one claim scenario.\n\n"
        f"Scenario narrative:\n{scenario['narrative']}\n\n"
        f"Disputed transaction reference: {scenario['disputed_transaction_ref']}\n\n"
        f"{RESPONSE_SCHEMA_DESCRIPTION}"
    )
    resp = client.chat.completions.create(
        model=MODEL,
        # No `temperature`: gpt-5.6-luna is a reasoning model and rejects any non-default
        # value outright (was 0.4, for variety across generated scenarios -- no longer
        # controllable with this model).
        response_format={"type": "json_object"},
        messages=[
            {"role": "system", "content": "You generate realistic synthetic test data for a claims-processing capstone project. Never use real people or real account data."},
            {"role": "user", "content": prompt},
        ],
    )
    return json.loads(resp.choices[0].message.content)


def review_scenario(scenario: dict, data: dict) -> list[str]:
    """Automated review against `expect` -- the human-review step tracker.md calls for,
    made mechanical since expectations are structured. Returns a list of problems (empty
    if the generated data matches the scenario's intent)."""
    problems = []
    expect = scenario["expect"]

    profile = data.get("account_profile", {})
    if expect.get("account_profile.standing") and profile.get("standing") != expect["account_profile.standing"]:
        problems.append(f"account_profile.standing = {profile.get('standing')!r}, expected {expect['account_profile.standing']!r}")

    txns = {t["transaction_ref"]: t for t in data.get("transactions", [])}
    disputed = txns.get(scenario["disputed_transaction_ref"])
    if not disputed:
        problems.append(f"disputed transaction {scenario['disputed_transaction_ref']!r} not found in generated transactions")
        return problems

    others = [t for t in txns.values() if t["transaction_ref"] != scenario["disputed_transaction_ref"]]

    if "disputed_transaction.amount_over" in expect:
        if not (disputed["amount"] > expect["disputed_transaction.amount_over"]):
            problems.append(f"disputed transaction amount {disputed['amount']} not > {expect['disputed_transaction.amount_over']}")

    if expect.get("disputed_transaction.location_differs_from_history"):
        history_locations = {t["location"] for t in others}
        if disputed["location"] in history_locations:
            problems.append(f"disputed transaction location {disputed['location']!r} matches an existing history location; expected it to differ")

    if expect.get("access_logs.has_risk_flag_near_transaction"):
        if not any(log.get("risk_flag") for log in data.get("access_logs", [])):
            problems.append("no access_logs entry has risk_flag = true")

    if expect.get("access_logs.no_risk_flag"):
        if any(log.get("risk_flag") for log in data.get("access_logs", [])):
            problems.append("expected no access_logs entry with risk_flag = true, but at least one was generated")

    if expect.get("disputed_transaction.location_in_history"):
        history_locations = {t["location"] for t in others}
        if disputed["location"] not in history_locations:
            problems.append(f"disputed transaction location {disputed['location']!r} not found among history locations; expected it to match")

    if "disputed_transaction.amount_not_over_avg_multiple" in expect:
        other_amounts = [float(t["amount"]) for t in others]
        if other_amounts:
            avg = sum(other_amounts) / len(other_amounts)
            multiple = expect["disputed_transaction.amount_not_over_avg_multiple"]
            if avg > 0 and float(disputed["amount"]) > avg * multiple:
                problems.append(f"disputed transaction amount {disputed['amount']} is > {multiple}x the history average ({avg:.2f}); expected it to look ordinary")

    if expect.get("no_duplicate_for_disputed"):
        window_seconds = 24 * 3600
        disputed_ts = _parse_ts(disputed["occurred_at"])
        for t in others:
            if t["merchant"] == disputed["merchant"] and float(t["amount"]) == float(disputed["amount"]):
                if abs((_parse_ts(t["occurred_at"]) - disputed_ts).total_seconds()) <= window_seconds:
                    problems.append(f"expected no duplicate of {disputed['transaction_ref']}, but {t['transaction_ref']} matches amount+merchant within 24h")

    if len(others) < 3:
        problems.append(f"only {len(others)} non-disputed transactions generated; want a few for pattern comparison")

    return problems


def _parse_ts(value: str) -> datetime:
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def load_scenario(scenario: dict, data: dict):
    account_id = scenario["account_id"]
    profile = data["account_profile"]
    # Phase 9 eval scenarios (#6/#7/#10, specs/eval_claims.md) deliberately leave no
    # account_profiles row so lookup_account_profile returns found=False and the
    # standing-derived check has no tool path to resolution, forcing ask_human.
    load_profile = scenario.get("load_account_profile", True)
    with db.get_connection() as conn:
        with conn.cursor() as cur:
            if load_profile:
                cur.execute(
                    """
                    INSERT INTO account_profiles (account_id, member_name, opened_at, standing, fraud_red_flags, dispute_history_count, raw)
                    VALUES (%s, %s, %s, %s, %s, %s, %s)
                    ON CONFLICT (account_id) DO UPDATE SET
                        member_name = EXCLUDED.member_name, opened_at = EXCLUDED.opened_at,
                        standing = EXCLUDED.standing, fraud_red_flags = EXCLUDED.fraud_red_flags,
                        dispute_history_count = EXCLUDED.dispute_history_count, raw = EXCLUDED.raw
                    """,
                    (
                        account_id,
                        profile["member_name"],
                        profile["opened_at"],
                        profile["standing"],
                        json.dumps(profile["fraud_red_flags"]),
                        profile["dispute_history_count"],
                        json.dumps(profile),
                    ),
                )
            else:
                cur.execute("DELETE FROM account_profiles WHERE account_id = %s", (account_id,))

            for t in data["transactions"]:
                cur.execute(
                    """
                    INSERT INTO transactions (account_id, transaction_ref, occurred_at, amount, merchant, location, channel, status, raw)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                    ON CONFLICT (account_id, transaction_ref) DO UPDATE SET
                        occurred_at = EXCLUDED.occurred_at, amount = EXCLUDED.amount, merchant = EXCLUDED.merchant,
                        location = EXCLUDED.location, channel = EXCLUDED.channel, status = EXCLUDED.status, raw = EXCLUDED.raw
                    """,
                    (
                        account_id, t["transaction_ref"], t["occurred_at"], t["amount"],
                        t["merchant"], t["location"], t["channel"], t["status"], json.dumps(t),
                    ),
                )

            # access_logs has no natural unique key to ON CONFLICT against; clear this
            # account's rows first so re-running a scenario (e.g. while iterating on Phase
            # 9 eval mismatches) replaces rather than duplicates them.
            cur.execute("DELETE FROM access_logs WHERE account_id = %s", (account_id,))
            for log in data["access_logs"]:
                cur.execute(
                    """
                    INSERT INTO access_logs (account_id, occurred_at, event_type, device_id, ip_address, location, risk_flag, raw)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                    """,
                    (
                        account_id, log["occurred_at"], log["event_type"], log.get("device_id"),
                        log.get("ip_address"), log.get("location"), log.get("risk_flag", False), json.dumps(log),
                    ),
                )


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true", help="generate + review only, skip DB writes")
    parser.add_argument(
        "--accounts", help="comma-separated account_ids to (re)generate; default is all scenarios"
    )
    args = parser.parse_args()

    scenarios = SCENARIOS
    if args.accounts:
        wanted = set(args.accounts.split(","))
        scenarios = [s for s in SCENARIOS if s["account_id"] in wanted]

    if not args.dry_run:
        db.open_pool()

    exit_code = 0
    max_attempts = 3
    for scenario in scenarios:
        print(f"--- Generating scenario: {scenario['account_id']} / {scenario['claim_type']} ---")
        data = None
        problems = []
        for attempt in range(1, max_attempts + 1):
            data = generate_scenario(scenario)
            problems = review_scenario(scenario, data)
            if not problems:
                break
            print(f"  attempt {attempt}/{max_attempts} failed review: {problems}")

        print(json.dumps(data, indent=2))

        if problems:
            exit_code = 1
            print(f"\nREVIEW FAILED for {scenario['account_id']} after {max_attempts} attempts:")
            for p in problems:
                print(f"  - {p}")
            continue

        print(f"\nReview OK for {scenario['account_id']}.")
        if not args.dry_run:
            load_scenario(scenario, data)
            print(f"Loaded fixtures for {scenario['account_id']}.")

    if not args.dry_run:
        db.close_pool()

    sys.exit(exit_code)


if __name__ == "__main__":
    main()
