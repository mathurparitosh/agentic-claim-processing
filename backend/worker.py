"""Background worker: drives the LangGraph agent for a claim (Phase 4 agent core).

Runs via FastAPI BackgroundTasks so POST /claims and POST /claims/{id}/answer return
immediately while the agent runs independently (technical.md's Background Execution row).
"""
import json
import os

from langgraph.checkpoint.postgres import PostgresSaver
from langgraph.types import Command

from . import db
from .agent.graph import build_graph as build_legacy_graph
from .agent.graph import initial_state
from .agent.orchestrator import build_orchestrator_graph


def _build_graph(checkpointer):
    """AGENT_MODE picks which claim-processing graph runs -- 'orchestrator' (default,
    Research/Decisioning sub-agents, specs/technical.md §5) or 'legacy' (the original
    single-agent ReAct loop in agent/graph.py, kept as a fallback, not deleted)."""
    mode = os.getenv("AGENT_MODE", "orchestrator").lower()
    if mode == "orchestrator":
        return build_orchestrator_graph(checkpointer)
    if mode == "legacy":
        return build_legacy_graph(checkpointer)
    raise RuntimeError(f"Unknown AGENT_MODE: {mode!r} (expected 'orchestrator' or 'legacy')")


def _handle_graph_result(claim_id: str, result: dict):
    """After a graph.invoke() call, the run either paused on ask_human (result carries
    __interrupt__) or reached finalize_node, which already wrote the decision itself
    (backend/agent/ledger.py) -- nothing left to do here in that case."""
    if "__interrupt__" in result:
        interrupt_payload = result["__interrupt__"][0].value
        with db.get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    UPDATE claims SET status = 'awaiting_input', pending_question = %s, last_updated = now()
                    WHERE id = %s
                    """,
                    (json.dumps(interrupt_payload), claim_id),
                )


def run_claim_agent(claim_id: str):
    """Start a fresh agent run for a newly submitted claim."""
    with db.get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT claim_type, claim_payload FROM claims WHERE id = %s", (claim_id,))
            row = cur.fetchone()
            if not row:
                return
            cur.execute("UPDATE claims SET status = 'processing', last_updated = now() WHERE id = %s", (claim_id,))

    with PostgresSaver.from_conn_string(db.DATABASE_URL) as checkpointer:
        graph = _build_graph(checkpointer)
        config = {"configurable": {"thread_id": claim_id}}
        result = graph.invoke(initial_state(claim_id, row["claim_type"], row["claim_payload"]), config=config)

    _handle_graph_result(claim_id, result)


def resume_claim_agent(claim_id: str, answer: str):
    """Resume a claim paused on ask_human with the processor's answer. The claim's
    status/pending_question are already updated to 'processing'/NULL by the API
    endpoint before this background task runs (backend/main.py)."""
    with PostgresSaver.from_conn_string(db.DATABASE_URL) as checkpointer:
        graph = _build_graph(checkpointer)
        config = {"configurable": {"thread_id": claim_id}}
        result = graph.invoke(Command(resume=answer), config=config)

    _handle_graph_result(claim_id, result)
