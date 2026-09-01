"""Check ledger / audit trail / claim-finalization persistence.

These are the only functions that write to `check_ledger`, `audit_trail`, and the
decision columns on `claims` -- keeps the append-only / traceability guarantees
(requirements.md §11) in one place.
"""
import json

from .. import db
from .checks import REQUIRED_CHECKS, compute_decision


def init_checks(claim_id: str, claim_type: str) -> dict:
    required = REQUIRED_CHECKS[claim_type]
    with db.get_connection() as conn:
        with conn.cursor() as cur:
            for name in required:
                cur.execute(
                    """
                    INSERT INTO check_ledger (claim_id, check_name, check_status, detail)
                    VALUES (%s, %s, 'UNKNOWN', NULL)
                    ON CONFLICT (claim_id, check_name) DO NOTHING
                    """,
                    (claim_id, name),
                )
    return {name: {"status": "UNKNOWN", "detail": None} for name in required}


def update_check(claim_id: str, check_name: str, status: str, detail):
    with db.get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                UPDATE check_ledger SET check_status = %s, detail = %s, updated_at = now()
                WHERE claim_id = %s AND check_name = %s
                """,
                (status, json.dumps(detail) if detail is not None else None, claim_id, check_name),
            )


def log_audit(claim_id: str, event_type: str, payload: dict, source: str, event_subtype: str | None = None):
    with db.get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO audit_trail (claim_id, event_type, event_subtype, payload, source)
                VALUES (%s, %s, %s, %s, %s)
                """,
                (claim_id, event_type, event_subtype, json.dumps(payload), source),
            )


def finalize_decision(claim_id: str, checks: dict, forced_reason: str | None = None) -> tuple[str, str]:
    decision, reason = compute_decision(checks)
    if forced_reason:
        reason = forced_reason

    with db.get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                UPDATE claims SET status = 'completed', decision = %s, decision_reason = %s, last_updated = now()
                WHERE id = %s
                """,
                (decision, reason, claim_id),
            )

    log_audit(
        claim_id,
        "determination_written",
        {
            "decision": decision,
            "reason": reason,
            "checks": checks,
            "forced": forced_reason is not None,
        },
        "agent",
        event_subtype=decision,
    )
    return decision, reason
