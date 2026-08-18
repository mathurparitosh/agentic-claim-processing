"""Phase 7 smoke test: run each synthetic scenario through both the legacy single-agent
graph and the new orchestrator graph, and compare outcomes (tracker.md Phase 7 -- "same
claims, same expected outcomes as the legacy agent" after the refactor).

    python -m backend.smoke_test_orchestrator
"""
import json
from uuid import uuid4

from dotenv import load_dotenv

load_dotenv(".env.local")

from langgraph.checkpoint.postgres import PostgresSaver  # noqa: E402
from langgraph.types import Command  # noqa: E402

from . import db  # noqa: E402
from .agent.graph import build_graph as build_legacy_graph  # noqa: E402
from .agent.graph import initial_state  # noqa: E402
from .agent.orchestrator import build_orchestrator_graph  # noqa: E402
from .generate_synthetic_data import SCENARIOS  # noqa: E402


def insert_claim(claim_id: str, claim_type: str, claim_payload: dict):
    with db.get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "INSERT INTO claims (id, claim_type, claim_payload, status) VALUES (%s, %s, %s, 'pending')",
                (claim_id, claim_type, json.dumps(claim_payload)),
            )


def fetch_result(claim_id: str) -> dict:
    with db.get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT status, decision, decision_reason FROM claims WHERE id = %s", (claim_id,))
            claim_row = cur.fetchone()
            cur.execute(
                "SELECT check_name, check_status FROM check_ledger WHERE claim_id = %s ORDER BY check_name",
                (claim_id,),
            )
            checks = {c["check_name"]: c["check_status"] for c in cur.fetchall()}
    return {"decision": claim_row["decision"], "reason": claim_row["decision_reason"], "checks": checks}


def run_scenario(build_graph_fn, claim_type: str, claim_payload: dict) -> dict:
    claim_id = str(uuid4())
    insert_claim(claim_id, claim_type, claim_payload)

    with PostgresSaver.from_conn_string(db.DATABASE_URL) as checkpointer:
        graph = build_graph_fn(checkpointer)
        config = {"configurable": {"thread_id": claim_id}}
        result = graph.invoke(initial_state(claim_id, claim_type, claim_payload), config=config)

        while "__interrupt__" in result:
            interrupt_info = result["__interrupt__"][0]
            print(f"    [ask_human] {interrupt_info.value['question']!r} -- auto-answering 'yes'")
            result = graph.invoke(Command(resume="yes"), config=config)

    return fetch_result(claim_id)


def main():
    db.open_pool()

    all_match = True
    for scenario in SCENARIOS:
        claim_type, claim_payload = scenario["claim_type"], scenario["claim_payload"]
        print(f"\n=== {scenario['account_id']} ({claim_type}) ===")

        print("  legacy:")
        legacy = run_scenario(build_legacy_graph, claim_type, claim_payload)
        print(f"    decision={legacy['decision']!r} reason={legacy['reason']!r}")
        print(f"    checks={legacy['checks']}")

        print("  orchestrator:")
        orchestrator = run_scenario(build_orchestrator_graph, claim_type, claim_payload)
        print(f"    decision={orchestrator['decision']!r} reason={orchestrator['reason']!r}")
        print(f"    checks={orchestrator['checks']}")

        match = legacy["decision"] == orchestrator["decision"] and legacy["checks"] == orchestrator["checks"]
        print(f"  MATCH: {match}")
        all_match = all_match and match

    print(f"\n=== Overall: {'ALL MATCH' if all_match else 'MISMATCH FOUND'} ===")
    db.close_pool()


if __name__ == "__main__":
    main()
