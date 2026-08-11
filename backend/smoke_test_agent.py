"""Phase 4 smoke test: run the LangGraph agent against one hand-picked claim end-to-end,
outside the API layer (tracker.md Phase 4). Prints the final decision, check ledger, and
audit trail so the run can be inspected by hand.

    python -m backend.smoke_test_agent
"""
import json
from uuid import uuid4

from dotenv import load_dotenv

load_dotenv(".env.local")

from langgraph.checkpoint.postgres import PostgresSaver  # noqa: E402
from langgraph.types import Command  # noqa: E402

from . import db  # noqa: E402
from .agent.graph import build_graph, initial_state  # noqa: E402
from .generate_synthetic_data import SCENARIOS  # noqa: E402

SCENARIO = SCENARIOS[0]


def insert_claim(claim_id: str, claim_type: str, claim_payload: dict):
    with db.get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "INSERT INTO claims (id, claim_type, claim_payload, status) VALUES (%s, %s, %s, 'pending')",
                (claim_id, claim_type, json.dumps(claim_payload)),
            )


def print_claim_result(claim_id: str):
    with db.get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT status, decision, decision_reason FROM claims WHERE id = %s", (claim_id,))
            claim_row = cur.fetchone()
            cur.execute(
                "SELECT check_name, check_status, detail FROM check_ledger WHERE claim_id = %s ORDER BY check_name",
                (claim_id,),
            )
            checks = cur.fetchall()
            cur.execute(
                "SELECT event_type, event_subtype, source, created_at FROM audit_trail WHERE claim_id = %s ORDER BY created_at",
                (claim_id,),
            )
            audit_rows = cur.fetchall()

    print("\n=== Claim result ===")
    print(f"status={claim_row['status']} decision={claim_row['decision']!r}")
    print(f"reason: {claim_row['decision_reason']}")

    print("\n=== Check ledger ===")
    for c in checks:
        print(f"  {c['check_name']}: {c['check_status']}  detail={c['detail']}")

    print(f"\n=== Audit trail ({len(audit_rows)} rows) ===")
    for a in audit_rows:
        print(f"  [{a['created_at']}] {a['event_type']}/{a['event_subtype']} via {a['source']}")


def main():
    db.open_pool()

    claim_id = str(uuid4())
    claim_type = SCENARIO["claim_type"]
    claim_payload = SCENARIO["claim_payload"]
    insert_claim(claim_id, claim_type, claim_payload)
    print(f"Claim {claim_id} ({claim_type}) inserted: {claim_payload}")

    with PostgresSaver.from_conn_string(db.DATABASE_URL) as checkpointer:
        graph = build_graph(checkpointer)
        config = {"configurable": {"thread_id": claim_id}}

        result = graph.invoke(initial_state(claim_id, claim_type, claim_payload), config=config)

        # If the agent called ask_human, the graph pauses here with an interrupt payload
        # instead of a normal end state. Auto-answer "yes" for the smoke test so the run
        # can complete unattended; a real run would surface this via the questions/answer
        # API endpoints (Phase 5) instead.
        while "__interrupt__" in result:
            interrupt_info = result["__interrupt__"][0]
            print(f"\n[ask_human] {interrupt_info.value}")
            print("[ask_human] auto-answering 'yes' for smoke test purposes")
            result = graph.invoke(Command(resume="yes"), config=config)

    print_claim_result(claim_id)
    db.close_pool()


if __name__ == "__main__":
    main()
