from time import sleep
from . import db


def run_claim_agent(claim_id: str):
    """Placeholder background worker that marks a claim as processing and writes an audit row.

    Replace this with the LangGraph run wiring later.
    """
    import json

    with db.get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "UPDATE claims SET status = %s, last_updated = now() WHERE id = %s",
                ("processing", claim_id),
            )
            cur.execute(
                "INSERT INTO audit_trail (claim_id, event_type, payload, source) VALUES (%s, %s, %s, %s)",
                (claim_id, "agent_started", json.dumps({"note": "agent run started"}), "worker"),
            )
    # simulate work (short sleep)
    sleep(0.5)
    with db.get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "UPDATE claims SET status = %s, decision = %s, decision_reason = %s, last_updated = now() WHERE id = %s",
                ("completed", "inconclusive", "placeholder-run", claim_id),
            )
            cur.execute(
                "INSERT INTO audit_trail (claim_id, event_type, payload, source) VALUES (%s, %s, %s, %s)",
                (claim_id, "agent_finished", json.dumps({"note": "agent run finished (placeholder)"}), "worker"),
            )
