"""Multi-agent orchestrator: Research + Decisioning sub-agents, one supervisor
conditional edge routing between them inside a single LangGraph graph
(specs/technical.md §5, resolved 2026-08-17: one graph with two think-nodes, not two
separate subgraphs).

This is the only claim-processing path (backend/worker.py). It imports the shared
business-rule helpers (_derive_check_updates, _format_checks, ClaimState,
finalize_node, the iteration caps) from graph.py -- which is now just that shared core;
the standalone single-agent Think/Act/Observe loop that used to live there and run
under AGENT_MODE=legacy has been removed -- so the check-ledger/decision rules stay
defined in exactly one place.

Determinism/boundedness per requirements.md §13: the final Approve/Deny/Inconclusive
outcome is computed by compute_decision(check_ledger) in finalize_node, never asserted
by either sub-agent; iteration/no-progress/human-question counters are global across
both sub-agents, not reset per sub-agent.

Routing is a simple two-phase pattern, not a dynamic per-turn handoff: Research always
runs first, and the supervisor moves to Decisioning -- permanently, it never routes
back -- as soon as either (a) no research-owned check is still UNKNOWN, or (b)
RESEARCH_ITERATION_CAP research rounds have passed, whichever comes first. (b) exists
because a research check can be legitimately unresolvable by any research tool -- e.g.
account_standing stays UNKNOWN forever if lookup_account_profile can't find a profile
at all, there's no tool result that ever changes that. Without a cap, the supervisor
would keep re-invoking Research on that claim forever, since Research has no
ask_human to escalate with -- only Decisioning does. (Caught by the orchestrator's own
smoke test, backend/smoke_test_orchestrator.py: a claim against a hidden account
profile looped in Research until the global no-progress cap killed the whole run
inconclusive, without Decisioning -- and therefore ask_human -- ever getting a turn.)
"""
import json
from typing import Literal

from langchain_core.messages import SystemMessage, ToolMessage
from langgraph.graph import END, START, StateGraph

from . import episodic, ledger
from .graph import (
    MAX_ITERATIONS,
    NO_PROGRESS_LIMIT,
    ClaimState,
    _derive_check_updates,
    _format_checks,
    finalize_node,
)
from .llm import active_model_name, active_provider, build_agent_model
from .tools import (
    HUMAN_QUESTION_BUDGET,
    ask_human,
    check_duplicate_charge,
    check_transaction_anomaly,
    lookup_access_logs,
    lookup_account_profile,
    lookup_transaction,
    search_policy,
    write_determination,
)

RESEARCH_TOOLS = [lookup_transaction, lookup_account_profile, lookup_access_logs, search_policy]
DECISIONING_TOOLS = [check_duplicate_charge, check_transaction_anomaly, ask_human, write_determination]
ALL_TOOLS_BY_NAME = {t.name: t for t in RESEARCH_TOOLS + DECISIONING_TOOLS}

# Which sub-agent owns resolving each check, per specs/technical.md §4's tool-category
# mapping -- Grounding/Retrieval checks go to Research, Computation checks go to
# Decisioning. transaction_pattern_anomaly is "Grounding + Computation" in the taxonomy
# table but resolves purely through check_transaction_anomaly (a Computation tool that
# queries the DB itself, no separate grounding lookup required first), so it's
# Decisioning-owned here.
RESEARCH_CHECKS = {
    "transaction_exists",
    "account_standing",
    "policy_dispute_window",
    "account_red_flags",
    "system_access_log_check",
    "policy_liability_rule",
}
DECISIONING_CHECKS = {"duplicate_charge_check", "transaction_pattern_anomaly"}

# Buffer added on top of a claim's actual research-owned check count (3 for
# billing_dispute, 4 for fraud) to get the research-phase iteration budget -- covers a
# prerequisite lookup that doesn't itself resolve a check (e.g. lookup_transaction
# before lookup_access_logs) plus one retry. Deliberately tight, not generous: the
# NO_PROGRESS_LIMIT=5 no-progress cap is global/shared (route_after_act checks it
# *before* the research-vs-decisioning handoff below), so a loose research budget
# would burn most or all of that shared budget before Decisioning -- and therefore
# ask_human -- ever gets a turn. See the module docstring for the stuck-check scenario
# this guards against.
RESEARCH_ITERATION_BUFFER = 2

MODEL_RESEARCH = build_agent_model(RESEARCH_TOOLS)
MODEL_DECISIONING = build_agent_model(DECISIONING_TOOLS)


class OrchestratorState(ClaimState):
    active_agent: str  # "research" | "decisioning" -- which sub-agent owns the pending
    # tool call(s), so act_observe_node can tag audit_trail entries with it.


RESEARCH_PROMPT_HEADER = (
    "You are the Claim Assistant's Research sub-agent, one role inside a larger "
    "orchestrator. Your only job is gathering evidence with Grounding and Retrieval "
    "tools -- you never judge, compute, or decide anything, and you have no "
    "computation tools, ask_human, or write_determination available. Call exactly one "
    "round of tool(s) per turn, targeting a still-UNKNOWN check this role can resolve: "
    f"{', '.join(sorted(RESEARCH_CHECKS))}. Look up the disputed transaction first "
    "(lookup_transaction) so you have its real occurred_at timestamp -- other tools "
    "that take a transaction timestamp expect that value, not the claim's "
    "filed_at/submission date. Once none of your checks are UNKNOWN anymore, the "
    "orchestrator hands off to the Decisioning sub-agent automatically -- you don't "
    "need to signal this yourself, just keep making progress each turn."
)

DECISIONING_PROMPT_HEADER = (
    "You are the Claim Assistant's Decisioning sub-agent, one role inside a larger "
    "orchestrator. The Research sub-agent has already gathered what evidence it could "
    "-- your job is computation (check_duplicate_charge, check_transaction_anomaly), "
    "last-resort human escalation (ask_human) for any check that's still "
    "UNKNOWN/BLOCKED and can't be resolved by any tool, and deciding when to stop. You "
    "never decide Approve/Deny/Inconclusive yourself -- that outcome is computed "
    "deterministically from the check ledger once you call write_determination. Call "
    "exactly one round of tool(s) per turn. Once every check is resolved -- or you "
    "cannot resolve the remaining ones with the tools/human input available -- call "
    "write_determination."
)


def _build_system_prompt(header: str, claim_type: str, claim_payload: dict, checks: dict, known_facts: dict) -> str:
    parts = [
        header,
        "",
        f"Claim type: {claim_type}",
        f"Claim payload: {json.dumps(claim_payload)}",
        "",
        "Required checks for this claim type and their current status:",
        _format_checks(checks),
    ]
    if known_facts:
        parts += ["", f"Known facts from prior claims about this account: {json.dumps(known_facts)}"]
    return "\n".join(parts)


def init_node(state: OrchestratorState) -> dict:
    claim_id, claim_type, payload = state["claim_id"], state["claim_type"], state["claim_payload"]
    checks = ledger.init_checks(claim_id, claim_type)

    # Deterministic pre-resolution: duplicate_charge_check only applies when the claim's
    # own stated reason is 'duplicate_charge' -- submitted data, not agent inference,
    # preserving determinism (requirements.md §6). Mirrors graph.py's init_node exactly.
    if claim_type == "billing_dispute" and payload.get("reason") != "duplicate_charge":
        detail = {"note": "not applicable: claim reason is not duplicate_charge"}
        checks["duplicate_charge_check"] = {"status": "PASS", "detail": detail}
        ledger.update_check(claim_id, "duplicate_charge_check", "PASS", detail)

    account_id = payload.get("account_id")
    known_facts = episodic.get_facts(account_id, "account") if account_id else {}

    ledger.log_audit(
        claim_id,
        "run_started",
        {
            "claim_type": claim_type,
            "claim_payload": payload,
            "agent_mode": "orchestrator",
            "model": active_model_name(),
            "provider": active_provider(),
        },
        "agent",
    )

    return {
        "checks": checks,
        "messages": [SystemMessage(content=_build_system_prompt(RESEARCH_PROMPT_HEADER, claim_type, payload, checks, known_facts))],
        "iteration": 0,
        "iterations_without_progress": 0,
        "questions_asked": 0,
        "decision_requested": False,
        "decision": None,
        "decision_reason": None,
        "active_agent": "research",
    }


def _log_think(claim_id: str, sub_agent: str, iteration: int, response, role_switch: bool = False) -> None:
    """One audit row per LLM reasoning turn -- records which sub-agent is active, the
    model/provider that produced it, and the tool(s) it proposed for this turn."""
    ledger.log_audit(
        claim_id,
        "agent_think",
        {
            "sub_agent": sub_agent,
            "model": active_model_name(),
            "provider": active_provider(),
            "iteration": iteration,
            "role_switch": role_switch,
            "proposed_tools": [tc["name"] for tc in getattr(response, "tool_calls", []) or []],
        },
        "agent",
        event_subtype=sub_agent,
    )


def think_research_node(state: OrchestratorState) -> dict:
    iteration = state["iteration"] + 1
    response = MODEL_RESEARCH.invoke(state["messages"])
    _log_think(state["claim_id"], "research", iteration, response)
    return {"messages": [response], "iteration": iteration, "active_agent": "research"}


def think_decisioning_node(state: OrchestratorState) -> dict:
    iteration = state["iteration"] + 1
    new_messages = []
    invoke_messages = state["messages"]
    role_switch = state.get("active_agent") != "decisioning"
    if role_switch:
        # First entry into Decisioning this run -- inject an explicit role-switch
        # reminder so the model knows its persona/toolset changed; each act_observe
        # round afterward keeps it anchored with the updated check ledger, same as the
        # legacy single agent's reminder pattern.
        reminder = SystemMessage(
            content=DECISIONING_PROMPT_HEADER + "\n\nCurrent check ledger:\n" + _format_checks(state["checks"])
        )
        invoke_messages = invoke_messages + [reminder]
        new_messages.append(reminder)
    response = MODEL_DECISIONING.invoke(invoke_messages)
    new_messages.append(response)
    _log_think(state["claim_id"], "decisioning", iteration, response, role_switch=role_switch)
    return {"messages": new_messages, "iteration": iteration, "active_agent": "decisioning"}


def act_observe_node(state: OrchestratorState) -> dict:
    claim_id, claim_type = state["claim_id"], state["claim_type"]
    active_agent = state["active_agent"]
    last_ai_message = state["messages"][-1]
    checks = {name: dict(c) for name, c in state["checks"].items()}
    questions_asked = state["questions_asked"]
    decision_requested = state["decision_requested"]
    progressed = False
    tool_messages = []

    for call in last_ai_message.tool_calls:
        name, args, tool_call_id = call["name"], call["args"], call["id"]

        if name == "write_determination":
            decision_requested = True
            ledger.log_audit(
                claim_id,
                "tool_call",
                {"tool": name, "args": args, "sub_agent": active_agent},
                "agent",
                event_subtype="write_determination",
            )
            tool_messages.append(ToolMessage(content="Determination requested; ledger will be finalized.", tool_call_id=tool_call_id))
            continue

        if name == "ask_human" and questions_asked >= HUMAN_QUESTION_BUDGET:
            result = {"skipped": True, "reason": "human question budget exhausted"}
            ledger.log_audit(
                claim_id,
                "tool_call",
                {"tool": name, "args": args, "result": result, "sub_agent": active_agent},
                "agent",
                event_subtype=name,
            )
            tool_messages.append(ToolMessage(content=json.dumps(result), tool_call_id=tool_call_id))
            continue
        if name not in ALL_TOOLS_BY_NAME:
            # A weak model (seen with local Ollama models) can hallucinate a tool name.
            result = {"error": "unknown_tool", "detail": f"{name!r} is not an available tool"}
            ledger.log_audit(
                claim_id,
                "tool_call",
                {"tool": name, "args": args, "result": result, "sub_agent": active_agent},
                "agent",
                event_subtype=name,
            )
            tool_messages.append(ToolMessage(content=json.dumps(result), tool_call_id=tool_call_id))
            continue

        if name == "ask_human":
            questions_asked += 1
            result = ALL_TOOLS_BY_NAME[name].invoke(args)  # raises a GraphInterrupt here, pausing the run
        else:
            try:
                result = ALL_TOOLS_BY_NAME[name].invoke(args)
            except Exception as exc:
                # Weak models sometimes emit a tool call with missing/invalid args
                # (e.g. search_policy with no query). Feed the error back to the model
                # as a normal tool result instead of crashing the whole run.
                result = {"error": "tool_execution_failed", "detail": str(exc)[:500]}

        # Derive the check-ledger updates first so the audit row can name which checks
        # this tool call moved and to what -- the single most useful thing to see in the
        # collapsed audit view.
        updates = _derive_check_updates(claim_type, name, args, result, checks)

        # Same audit-trail-gets-full-result / model-gets-trimmed-result split as
        # graph.py's act_observe_node, plus the sub_agent tag.
        ledger.log_audit(
            claim_id,
            "tool_call",
            {
                "tool": name,
                "args": args,
                "result": result,
                "sub_agent": active_agent,
                "checks_updated": [{"check": cn, "status": st} for cn, st, _ in updates],
            },
            "agent",
            event_subtype=name,
        )
        llm_facing_result = {k: v for k, v in result.items() if k != "candidates"} if name == "search_policy" else result
        tool_messages.append(ToolMessage(content=json.dumps(llm_facing_result), tool_call_id=tool_call_id))

        for check_name, status, detail in updates:
            if checks[check_name]["status"] != status:
                progressed = True
            checks[check_name] = {"status": status, "detail": detail}
            ledger.update_check(claim_id, check_name, status, detail)

            account_id = args.get("account_id")
            if account_id and check_name in ("account_standing", "account_red_flags"):
                episodic.upsert_fact(account_id, "account", check_name, {"status": status, "detail": detail}, claim_id, source=name)

    reminder = SystemMessage(content="Updated check ledger:\n" + _format_checks(checks))

    return {
        "messages": tool_messages + [reminder],
        "checks": checks,
        "questions_asked": questions_asked,
        "decision_requested": decision_requested,
        "iterations_without_progress": 0 if progressed else state["iterations_without_progress"] + 1,
    }


def route_after_act(state: OrchestratorState) -> Literal["think_research", "think_decisioning", "finalize"]:
    if state["decision_requested"]:
        return "finalize"
    if any(c["status"] == "FAIL" for c in state["checks"].values()):
        return "finalize"
    if all(c["status"] == "PASS" for c in state["checks"].values()):
        return "finalize"
    if state["iteration"] >= MAX_ITERATIONS:
        return "finalize"
    if state["iterations_without_progress"] >= NO_PROGRESS_LIMIT:
        return "finalize"

    # Once Decisioning has taken a turn, never route back to Research (see module
    # docstring). Otherwise stay in Research until either nothing left for it to
    # resolve, or its iteration budget runs out (the stuck-check fallback).
    if state["active_agent"] != "decisioning":
        research_checks_in_claim = [c for c in state["checks"] if c in RESEARCH_CHECKS]
        research_open = any(state["checks"][c]["status"] == "UNKNOWN" for c in research_checks_in_claim)
        research_cap = len(research_checks_in_claim) + RESEARCH_ITERATION_BUFFER
        if research_open and state["iteration"] < research_cap:
            return "think_research"
    return "think_decisioning"


def build_orchestrator_graph(checkpointer):
    workflow = StateGraph(OrchestratorState)
    workflow.add_node("init", init_node)
    workflow.add_node("think_research", think_research_node)
    workflow.add_node("think_decisioning", think_decisioning_node)
    workflow.add_node("act_observe", act_observe_node)
    workflow.add_node("finalize", finalize_node)

    workflow.add_edge(START, "init")
    workflow.add_edge("init", "think_research")
    workflow.add_edge("think_research", "act_observe")
    workflow.add_edge("think_decisioning", "act_observe")
    workflow.add_conditional_edges(
        "act_observe",
        route_after_act,
        {"think_research": "think_research", "think_decisioning": "think_decisioning", "finalize": "finalize"},
    )
    workflow.add_edge("finalize", END)

    return workflow.compile(checkpointer=checkpointer)
