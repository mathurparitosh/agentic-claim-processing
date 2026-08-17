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

    if len(others) < 3:
        problems.append(f"only {len(others)} non-disputed transactions generated; want a few for pattern comparison")

    return problems


def load_scenario(scenario: dict, data: dict):
    account_id = scenario["account_id"]
    profile = data["account_profile"]
    with db.get_connection() as conn:
        with conn.cursor() as cur:
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
    for scenario in scenarios:
        print(f"--- Generating scenario: {scenario['account_id']} / {scenario['claim_type']} ---")
        data = generate_scenario(scenario)
        print(json.dumps(data, indent=2))

        problems = review_scenario(scenario, data)
        if problems:
            exit_code = 1
            print(f"\nREVIEW FAILED for {scenario['account_id']}:")
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
