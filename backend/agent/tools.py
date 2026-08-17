"""Tool layer (requirements.md §8): Retrieval, Grounding, Computation, ask_human,
write_determination.

Grounding/Computation tools read the synthetic fixture tables (`transactions`,
`access_logs`, `account_profiles`) -- see specs/technical.md §4. Retrieval queries the
real Qdrant collection (`scripts/ingest_policy_corpus.py`, Phase 3).
"""
import os
from datetime import date, datetime
from decimal import Decimal

from langchain_core.tools import tool
from langgraph.types import interrupt
from openai import OpenAI
from qdrant_client import QdrantClient, models

from .. import db

_openai_client = None
_qdrant_client = None

HUMAN_QUESTION_BUDGET = 3
# Calibrated against the real policy corpus (scripts/ingest_policy_corpus.py) with
# text-embedding-3-small cosine scores: genuinely relevant clauses land ~0.55-0.68,
# off-topic queries ~0.06-0.08. The original 0.75 predates any real data in the
# index (Pinecone was always empty) and silently discarded every correct match.
RELEVANCE_FLOOR = 0.5


def _jsonable(value):
    """Make psycopg row values (Decimal/datetime) JSON-serializable for tool output."""
    if isinstance(value, Decimal):
        return float(value)
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    if isinstance(value, dict):
        return {k: _jsonable(v) for k, v in value.items()}
    if isinstance(value, list):
        return [_jsonable(v) for v in value]
    return value


def _openai() -> OpenAI:
    global _openai_client
    if _openai_client is None:
        _openai_client = OpenAI()
    return _openai_client


def _qdrant() -> QdrantClient:
    global _qdrant_client
    if _qdrant_client is None:
        _qdrant_client = QdrantClient(
            url=os.getenv("QDRANT_URL"), api_key=os.getenv("QDRANT_API_KEY")
        )
    return _qdrant_client


# ---- Grounding -------------------------------------------------------------


@tool
def lookup_transaction(account_id: str, transaction_ref: str) -> dict:
    """Grounding tool. Look up one specific transaction on an account by its reference id.
    Returns whether it was found and, if so, its amount/merchant/location/channel/status/occurred_at."""
    with db.get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT transaction_ref, occurred_at, amount, merchant, location, channel, status
                FROM transactions WHERE account_id = %s AND transaction_ref = %s
                """,
                (account_id, transaction_ref),
            )
            row = cur.fetchone()
    if not row:
        return {"found": False}
    return {"found": True, "transaction": _jsonable(dict(row))}


@tool
def lookup_account_profile(account_id: str) -> dict:
    """Grounding tool. Look up an account's standing, fraud red flags, and dispute history count."""
    with db.get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT account_id, member_name, standing, fraud_red_flags, dispute_history_count
                FROM account_profiles WHERE account_id = %s
                """,
                (account_id,),
            )
            row = cur.fetchone()
    if not row:
        return {"found": False}
    return {"found": True, "profile": _jsonable(dict(row))}


@tool
def lookup_access_logs(account_id: str, near_timestamp: str | None = None, window_hours: int = 24) -> dict:
    """Grounding tool. Look up system/login/device access-log events for an account. If
    near_timestamp (ISO 8601) is given, restrict to events within window_hours of it;
    otherwise return the most recent events. near_timestamp should be the disputed
    transaction's own occurred_at (from lookup_transaction) -- NOT the claim's filed_at
    or submission date -- since the goal is to check for suspicious access around the
    transaction itself."""
    with db.get_connection() as conn:
        with conn.cursor() as cur:
            if near_timestamp:
                cur.execute(
                    """
                    SELECT occurred_at, event_type, device_id, ip_address, location, risk_flag
                    FROM access_logs
                    WHERE account_id = %s
                      AND occurred_at BETWEEN %s::timestamptz - (%s || ' hours')::interval
                                           AND %s::timestamptz + (%s || ' hours')::interval
                    ORDER BY occurred_at
                    """,
                    (account_id, near_timestamp, window_hours, near_timestamp, window_hours),
                )
            else:
                cur.execute(
                    """
                    SELECT occurred_at, event_type, device_id, ip_address, location, risk_flag
                    FROM access_logs WHERE account_id = %s ORDER BY occurred_at DESC LIMIT 20
                    """,
                    (account_id,),
                )
            rows = [_jsonable(dict(r)) for r in cur.fetchall()]
    return {"logs": rows, "risk_flag_count": sum(1 for r in rows if r["risk_flag"])}


# ---- Computation ------------------------------------------------------------


@tool
def check_duplicate_charge(account_id: str, transaction_ref: str, window_hours: int = 24) -> dict:
    """Computation tool. Check whether the given transaction was charged again (same
    amount + merchant) on the same account within window_hours. Use for billing disputes
    where the customer claims a duplicate charge."""
    with db.get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT occurred_at, amount, merchant FROM transactions WHERE account_id = %s AND transaction_ref = %s",
                (account_id, transaction_ref),
            )
            base = cur.fetchone()
            if not base:
                return {"error": "transaction_not_found"}
            cur.execute(
                """
                SELECT transaction_ref, occurred_at, amount, merchant
                FROM transactions
                WHERE account_id = %s AND transaction_ref != %s AND amount = %s AND merchant = %s
                  AND occurred_at BETWEEN %s::timestamptz - (%s || ' hours')::interval
                                       AND %s::timestamptz + (%s || ' hours')::interval
                """,
                (
                    account_id,
                    transaction_ref,
                    base["amount"],
                    base["merchant"],
                    base["occurred_at"],
                    window_hours,
                    base["occurred_at"],
                    window_hours,
                ),
            )
            matches = [_jsonable(dict(r)) for r in cur.fetchall()]
    return {"duplicate_found": len(matches) > 0, "matches": matches}


@tool
def check_transaction_anomaly(account_id: str, transaction_ref: str) -> dict:
    """Computation tool. Compare one transaction against the account's own transaction
    history (average amount, common locations) to flag amount or location anomalies."""
    with db.get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT amount, location, merchant FROM transactions WHERE account_id = %s AND transaction_ref = %s",
                (account_id, transaction_ref),
            )
            target = cur.fetchone()
            if not target:
                return {"error": "transaction_not_found"}
            cur.execute(
                "SELECT amount, location FROM transactions WHERE account_id = %s AND transaction_ref != %s",
                (account_id, transaction_ref),
            )
            history = cur.fetchall()

    if not history:
        return {"anomalous": None, "reason": "no_history_to_compare"}

    amounts = [float(r["amount"]) for r in history]
    avg_amount = sum(amounts) / len(amounts)
    known_locations = {r["location"] for r in history if r["location"]}

    reasons = []
    target_amount = float(target["amount"])
    if avg_amount > 0 and target_amount > avg_amount * 3:
        reasons.append(f"amount {target_amount} is >3x the account's average ({avg_amount:.2f})")
    if target["location"] and known_locations and target["location"] not in known_locations:
        reasons.append(f"location '{target['location']}' not seen before on this account")

    return {"anomalous": bool(reasons), "reasons": reasons, "average_amount": round(avg_amount, 2)}


# ---- Retrieval ---------------------------------------------------------------


@tool
def search_policy(query: str, claim_type: str) -> dict:
    """Retrieval tool. Semantic search over the company policy/regulation corpus for the
    text governing this claim type. Returns up to 3 relevant clauses with citations, or
    zero results if nothing clears the relevance floor -- 'no matching policy found' is a
    valid, honest outcome, not an error."""
    embedding = _openai().embeddings.create(model="text-embedding-3-small", input=query).data[0].embedding
    raw = _qdrant().query_points(
        collection_name=os.getenv("QDRANT_COLLECTION", "claims-policy-corpus"),
        query=embedding,
        limit=20,
        query_filter=models.Filter(
            must=[models.FieldCondition(key="claim_type", match=models.MatchValue(value=claim_type))]
        ),
        with_payload=True,
    )

    candidates = [
        {
            "id": str(p.id),
            "score": p.score,
            "text": (p.payload or {}).get("text"),
            "citation": (p.payload or {}).get("citation"),
        }
        for p in raw.points
    ]
    top = sorted((c for c in candidates if c["score"] >= RELEVANCE_FLOOR), key=lambda c: -c["score"])[:3]

    # requirements.md §9 / technical.md §3: full retrieval detail (all candidates and
    # scores, not just the top 3 used) must reach the audit trail. `candidates` is
    # stripped back out before this result is shown to the model (see graph.py) so the
    # LLM's context only sees the top 3 -- the full list is for the audit record only.
    return {
        "query": query,
        "filter": {"claim_type": claim_type},
        "results": top,
        "candidate_count": len(candidates),
        "candidates": candidates,
    }


# ---- Human-in-the-loop --------------------------------------------------------


@tool
def ask_human(question: str, check_name: str) -> dict:
    """Ask the human claim processor a yes/no clarifying question when no tool can supply
    a fact needed to resolve check_name. Suspends the run until the processor answers
    (possibly hours/days later); use only as a last resort, and phrase the question so a
    yes/no answer resolves it."""
    answer = interrupt({"question": question, "check_name": check_name})
    return {"answer": answer, "check_name": check_name}


# ---- Terminal write -----------------------------------------------------------


@tool
def write_determination(rationale: str) -> str:
    """Call this once every required check has a verified outcome (or you've exhausted
    the tools/human input available to resolve the remaining ones). Provide a short
    rationale summarizing the check ledger. The actual Approve/Deny/Inconclusive outcome
    is computed deterministically from the check ledger, not from this rationale."""
    return "determination_requested"


TOOLS = [
    lookup_transaction,
    lookup_account_profile,
    lookup_access_logs,
    check_duplicate_charge,
    check_transaction_anomaly,
    search_policy,
    ask_human,
    write_determination,
]
