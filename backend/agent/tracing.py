"""Read-only views of the agent's internals, for the frontend's agent-tracing tabs
(tracker.md Phase 12).

Nothing here mutates a claim, the check ledger, or the audit trail. These functions
only *read* -- the LangGraph checkpoint (`get_state`), `episodic_facts`, and the
compiled graph / tool objects. The Sub-agents view is derived on the frontend from the
existing `/claims/{id}/audit` data, so there's no function for it here.
"""
import json
from functools import lru_cache

from langchain_core.messages import AIMessage, HumanMessage, SystemMessage, ToolMessage
from langgraph.checkpoint.postgres import PostgresSaver

from .. import db
from ..worker import build_claim_graph
from .checks import REQUIRED_CHECKS
from .graph import MAX_ITERATIONS, NO_PROGRESS_LIMIT
from .llm import active_model_name, active_provider
from .orchestrator import (
    DECISIONING_CHECKS,
    DECISIONING_TOOLS,
    RESEARCH_CHECKS,
    RESEARCH_TOOLS,
)
from .tools import TOOL_CATEGORY, TOOL_RESOLVES_CHECKS, TOOLS, search_network_policy

_ROLE_BY_TYPE = {
    SystemMessage: "system",
    HumanMessage: "human",
    AIMessage: "ai",
    ToolMessage: "tool",
}

NODE_PROSE = {
    "init": "Seeds the check ledger, loads episodic facts for the account, auto-resolves "
    "duplicate_charge_check when the claim reason isn't 'duplicate_charge', logs run_started.",
    "think_research": "Research sub-agent LLM turn -- Grounding + Retrieval tools only. One "
    "tool call per turn, targeting a still-UNKNOWN research-owned check.",
    "think_decisioning": "Decisioning sub-agent LLM turn -- Computation tools + ask_human + "
    "write_determination. Injects a role-switch reminder on first entry.",
    "act_observe": "Executes the proposed tool call, maps the result onto check-ledger updates "
    "(_derive_check_updates), writes the audit row, upserts episodic facts after account lookups.",
    "finalize": "Deterministic close -- compute_decision(check_ledger) -> Approve/Deny/"
    "Inconclusive, or a forced Inconclusive on the iteration / no-progress caps.",
}


def _serialize_message(m) -> dict:
    role = _ROLE_BY_TYPE.get(type(m)) or getattr(m, "type", "unknown")
    content = m.content if isinstance(m.content, str) else json.dumps(m.content)
    out = {"role": role, "content": content}
    tool_calls = getattr(m, "tool_calls", None)
    if tool_calls:
        out["tool_calls"] = [
            {"name": tc.get("name"), "args": tc.get("args"), "id": tc.get("id")} for tc in tool_calls
        ]
    if isinstance(m, ToolMessage):
        out["tool_call_id"] = m.tool_call_id
        out["name"] = getattr(m, "name", None)
    return out


def get_agent_context(claim_id: str) -> dict | None:
    """The message window the model is actually working from right now -- reconstructed
    from the LangGraph checkpoint keyed by thread_id == claim_id -- plus the run's
    counters and which node runs next. Returns None if the claim doesn't exist."""
    with db.get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT claim_type, status FROM claims WHERE id = %s", (claim_id,))
            row = cur.fetchone()
    if not row:
        return None

    # Same per-call checkpointer pattern worker.py uses; read-only get_state here.
    with PostgresSaver.from_conn_string(db.DATABASE_URL) as checkpointer:
        snapshot = build_claim_graph(checkpointer).get_state({"configurable": {"thread_id": claim_id}})

    values = snapshot.values or {}
    messages = [_serialize_message(m) for m in values.get("messages", [])]
    approx_tokens = sum(len(m["content"] or "") for m in messages) // 4

    return {
        "claim_type": row["claim_type"],
        "claim_status": row["status"],
        "pending": not messages,
        "messages": messages,
        "message_count": len(messages),
        "approx_tokens": approx_tokens,
        "active_agent": values.get("active_agent"),
        "decision_requested": values.get("decision_requested"),
        "next_nodes": list(snapshot.next) if snapshot.next else [],
        "counters": {
            "iteration": values.get("iteration"),
            "iterations_without_progress": values.get("iterations_without_progress"),
            "questions_asked": values.get("questions_asked"),
            "max_iterations": MAX_ITERATIONS,
            "no_progress_limit": NO_PROGRESS_LIMIT,
        },
        "model": active_model_name(),
        "provider": active_provider(),
    }


def get_agent_memory(claim_id: str) -> dict | None:
    """Episodic facts for this claim's account -- the cross-claim memory the run reads
    at init and writes back after account lookups. Each fact is tagged with whether the
    most recent write came from this claim or an earlier one. Returns None if the claim
    doesn't exist."""
    with db.get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT claim_payload FROM claims WHERE id = %s", (claim_id,))
            row = cur.fetchone()
            if not row:
                return None
            account_id = (row["claim_payload"] or {}).get("account_id")
            facts = []
            if account_id:
                cur.execute(
                    """
                    SELECT fact_key, fact_value, provenance, updated_at
                    FROM episodic_facts
                    WHERE entity_id = %s AND entity_type = 'account'
                    ORDER BY fact_key
                    """,
                    (account_id,),
                )
                for f in cur.fetchall():
                    prov = f["provenance"] or {}
                    facts.append(
                        {
                            "fact_key": f["fact_key"],
                            "fact_value": f["fact_value"],
                            "source_tool": prov.get("source"),
                            "origin_claim_id": prov.get("claim_id"),
                            "written_by_this_claim": prov.get("claim_id") == claim_id,
                            "updated_at": f["updated_at"].isoformat() if f["updated_at"] else None,
                        }
                    )
    return {"account_id": account_id, "entity_type": "account", "facts": facts}


def _tool_params(tool) -> list[dict]:
    schema = {}
    args_schema = getattr(tool, "args_schema", None)
    if args_schema is not None:
        try:
            schema = args_schema.model_json_schema()
        except AttributeError:
            schema = args_schema if isinstance(args_schema, dict) else {}
    required = set(schema.get("required", []))
    return [
        {"name": name, "type": spec.get("type", "any"), "required": name in required}
        for name, spec in (schema.get("properties") or {}).items()
    ]


@lru_cache(maxsize=1)
def tool_catalog() -> dict:
    """The static tool catalog: every tool, its category, params, which sub-agent owns
    it in the orchestrator, and which check(s) its result can move."""
    research = {t.name for t in RESEARCH_TOOLS}
    decisioning = {t.name for t in DECISIONING_TOOLS}

    entries = []
    for tool in [*TOOLS, search_network_policy]:
        owner = "research" if tool.name in research else "decisioning" if tool.name in decisioning else "recovery"
        entries.append(
            {
                "name": tool.name,
                "category": TOOL_CATEGORY.get(tool.name, "Other"),
                "description": (tool.description or "").strip().splitlines()[0],
                "params": _tool_params(tool),
                "owner": owner,
                "resolves_checks": TOOL_RESOLVES_CHECKS.get(tool.name, []),
            }
        )

    return {
        "tools": entries,
        "owners": {
            "research": {"tools": sorted(research), "checks": sorted(RESEARCH_CHECKS)},
            "decisioning": {"tools": sorted(decisioning), "checks": sorted(DECISIONING_CHECKS)},
        },
        "required_checks": REQUIRED_CHECKS,
    }


@lru_cache(maxsize=1)
def graph_view() -> dict:
    """The compiled orchestrator graph as Mermaid (primary) + ASCII (fallback), with a
    one-line description per node."""
    g = build_claim_graph().get_graph()
    try:
        ascii_art = g.draw_ascii()
    except Exception as exc:  # grandalf not installed, etc. -- mermaid still renders.
        ascii_art = f"(ASCII rendering unavailable: {exc})"
    return {"mermaid": g.draw_mermaid(), "ascii": ascii_art, "nodes": NODE_PROSE}
