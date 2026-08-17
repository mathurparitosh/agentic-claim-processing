"""The ReAct (Think -> Act -> Observe) agent graph (requirements.md §5).

Think is an LLM call proposing tool call(s). Act (execute the tool) and Observe (fold
the result into the check ledger) are combined into one graph node -- Observe here is
deterministic bookkeeping derived from a tool result, not a second reasoning step, so it
doesn't need its own LLM call. Termination is computed from check-ledger state, never
self-declared by the model (requirements.md §6).
"""
import json
from typing import Annotated, Literal, TypedDict

from langchain_core.messages import SystemMessage, ToolMessage
from langgraph.graph import END, START, StateGraph
from langgraph.graph.message import add_messages

from . import episodic, ledger
from .checks import REQUIRED_CHECKS
from .llm import build_agent_model
from .tools import HUMAN_QUESTION_BUDGET, TOOLS

MAX_ITERATIONS = 12
NO_PROGRESS_LIMIT = 5

TOOLS_BY_NAME = {t.name: t for t in TOOLS}
# Provider/model switchable via .env.local's LLM_PROVIDER -- see agent/llm.py. Also
# sidesteps a real LangGraph interrupt hazard: if a turn's tool_calls included e.g.
# lookup_transaction *and* ask_human, resuming after the ask_human pause re-runs the
# whole node from the top, re-executing lookup_transaction's DB writes and producing a
# duplicate audit_trail row. With exactly one tool call per turn, ask_human (when
# chosen) has no side effects ahead of it in the same node call, so resume is safe.
MODEL = build_agent_model(TOOLS)


class ClaimState(TypedDict):
    claim_id: str
    claim_type: str
    claim_payload: dict
    messages: Annotated[list, add_messages]
    checks: dict
    iteration: int
    iterations_without_progress: int
    questions_asked: int
    decision_requested: bool
    decision: str | None
    decision_reason: str | None


SYSTEM_PROMPT_HEADER = (
    "You are the Claim Assistant research agent. You gather evidence about a submitted "
    "claim using tools; every tool call you make is recorded and used to resolve the "
    "claim's required checks. You never decide Approve/Deny/Inconclusive yourself -- "
    "that outcome is computed deterministically from the check ledger once you call "
    "write_determination. Call exactly one round of tool(s) per turn, targeting an "
    "UNKNOWN or BLOCKED check. Look up the disputed transaction first (lookup_transaction) "
    "so you have its real occurred_at timestamp -- other tools that take a transaction "
    "timestamp expect that value, not the claim's filed_at/submission date. Once every "
    "check is resolved -- or you cannot resolve the remaining ones with the tools/human "
    "input available -- call write_determination."
)


def _format_checks(checks: dict) -> str:
    lines = []
    for name, c in checks.items():
        suffix = f" ({json.dumps(c['detail'])})" if c["detail"] else ""
        lines.append(f"  - {name}: {c['status']}{suffix}")
    return "\n".join(lines)


def _build_system_prompt(claim_type: str, claim_payload: dict, checks: dict, known_facts: dict) -> str:
    parts = [
        SYSTEM_PROMPT_HEADER,
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


def init_node(state: ClaimState) -> dict:
    claim_id, claim_type, payload = state["claim_id"], state["claim_type"], state["claim_payload"]
    checks = ledger.init_checks(claim_id, claim_type)

    # Deterministic pre-resolution: duplicate_charge_check only applies when the claim's
    # own stated reason is 'duplicate_charge' -- that's submitted data, not agent
    # inference, so resolving it here (rather than spending a tool call) preserves
    # determinism (requirements.md §6).
    if claim_type == "billing_dispute" and payload.get("reason") != "duplicate_charge":
        detail = {"note": "not applicable: claim reason is not duplicate_charge"}
        checks["duplicate_charge_check"] = {"status": "PASS", "detail": detail}
        ledger.update_check(claim_id, "duplicate_charge_check", "PASS", detail)

    account_id = payload.get("account_id")
    known_facts = episodic.get_facts(account_id, "account") if account_id else {}

    ledger.log_audit(claim_id, "run_started", {"claim_type": claim_type, "claim_payload": payload}, "agent")

    return {
        "checks": checks,
        "messages": [SystemMessage(content=_build_system_prompt(claim_type, payload, checks, known_facts))],
        "iteration": 0,
        "iterations_without_progress": 0,
        "questions_asked": 0,
        "decision_requested": False,
        "decision": None,
        "decision_reason": None,
    }


def think_node(state: ClaimState) -> dict:
    response = MODEL.invoke(state["messages"])
    return {"messages": [response], "iteration": state["iteration"] + 1}


def _derive_check_updates(claim_type: str, tool_name: str, args: dict, result: dict, checks: dict) -> list[tuple[str, str, dict]]:
    """Business rules mapping a tool result to check-ledger updates. See specs/technical.md
    §4 for the PASS/FAIL semantics documented per check."""
    updates: list[tuple[str, str, dict]] = []

    if tool_name == "lookup_transaction" and "transaction_exists" in checks:
        updates.append(("transaction_exists", "PASS" if result.get("found") else "FAIL", result))

    elif tool_name == "lookup_account_profile":
        profile = result.get("profile") if result.get("found") else None
        standing = profile["standing"] if profile else None
        status = "UNKNOWN" if standing is None else ("PASS" if standing == "good" else "FAIL")
        if "account_standing" in checks:
            updates.append(("account_standing", status, result))
        if "account_red_flags" in checks:
            updates.append(("account_red_flags", status, result))

    elif tool_name == "check_duplicate_charge" and "duplicate_charge_check" in checks and "error" not in result:
        updates.append(("duplicate_charge_check", "PASS" if result.get("duplicate_found") else "FAIL", result))

    elif tool_name == "check_transaction_anomaly" and "transaction_pattern_anomaly" in checks:
        anomalous = result.get("anomalous")
        if anomalous is not None:
            updates.append(("transaction_pattern_anomaly", "PASS" if anomalous else "FAIL", result))

    elif tool_name == "lookup_access_logs" and "system_access_log_check" in checks:
        status = "PASS" if result.get("risk_flag_count", 0) > 0 else "FAIL"
        updates.append(("system_access_log_check", status, result))

    elif tool_name == "search_policy":
        target = "policy_dispute_window" if claim_type == "billing_dispute" else "policy_liability_rule"
        if target in checks:
            if not result.get("results"):
                updates.append((target, "BLOCKED", {"note": "no matching policy found", "query": result.get("query")}))
            else:
                # No computation step applies the retrieved clause's actual text (e.g. its
                # stated filing-window day count) -- a retrieved, citable governing policy
                # is treated as satisfying this check (documented simplification,
                # specs/technical.md §4). This is deliberately the *only* way either
                # retrieval-only check can PASS: an earlier version let the model supply a
                # filing-window day count itself via a separate tool, and it did -- with a
                # number from its own training knowledge, never having called search_policy
                # at all. Retrieval-only checks must only close via an actual retrieval hit.
                updates.append((target, "PASS", {"citations": result.get("results")}))

    elif tool_name == "ask_human":
        check_name = args.get("check_name")
        if check_name in checks:
            answer = (result.get("answer") or "").strip().lower()
            if answer.startswith(("yes", "confirmed", "true")):
                updates.append((check_name, "PASS", {"human_answer": result.get("answer")}))
            elif answer.startswith(("no", "denied", "false")):
                updates.append((check_name, "FAIL", {"human_answer": result.get("answer")}))
            else:
                updates.append((check_name, "UNKNOWN", {"human_answer": result.get("answer"), "note": "answer not clearly yes/no"}))

    return updates


def act_observe_node(state: ClaimState) -> dict:
    claim_id, claim_type = state["claim_id"], state["claim_type"]
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
            ledger.log_audit(claim_id, "tool_call", {"tool": name, "args": args}, "agent", event_subtype="write_determination")
            tool_messages.append(ToolMessage(content="Determination requested; ledger will be finalized.", tool_call_id=tool_call_id))
            continue

        if name == "ask_human" and questions_asked >= HUMAN_QUESTION_BUDGET:
            result = {"skipped": True, "reason": "human question budget exhausted"}
            ledger.log_audit(claim_id, "tool_call", {"tool": name, "args": args, "result": result}, "agent")
            tool_messages.append(ToolMessage(content=json.dumps(result), tool_call_id=tool_call_id))
            continue
        if name == "ask_human":
            questions_asked += 1

        result = TOOLS_BY_NAME[name].invoke(args)  # ask_human raises a GraphInterrupt here, pausing the run

        # Audit trail gets the full result (e.g. search_policy's ~20 raw candidates +
        # scores, requirements.md §9); the model only sees the trimmed version so its
        # context doesn't balloon with candidates it already discarded.
        ledger.log_audit(claim_id, "tool_call", {"tool": name, "args": args, "result": result}, "agent")
        llm_facing_result = {k: v for k, v in result.items() if k != "candidates"} if name == "search_policy" else result
        tool_messages.append(ToolMessage(content=json.dumps(llm_facing_result), tool_call_id=tool_call_id))

        for check_name, status, detail in _derive_check_updates(claim_type, name, args, result, checks):
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


def finalize_node(state: ClaimState) -> dict:
    forced_reason = None
    if not state["decision_requested"]:
        if state["iteration"] >= MAX_ITERATIONS:
            forced_reason = f"Inconclusive: hit the {MAX_ITERATIONS}-iteration cap before all checks resolved."
        elif state["iterations_without_progress"] >= NO_PROGRESS_LIMIT:
            forced_reason = f"Inconclusive: {NO_PROGRESS_LIMIT} iterations without measurable progress on remaining checks."

    decision, reason = ledger.finalize_decision(state["claim_id"], state["checks"], forced_reason=forced_reason)
    return {"decision": decision, "decision_reason": reason}


def route_after_act(state: ClaimState) -> Literal["think", "finalize"]:
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
    return "think"


def build_graph(checkpointer):
    workflow = StateGraph(ClaimState)
    workflow.add_node("init", init_node)
    workflow.add_node("think", think_node)
    workflow.add_node("act_observe", act_observe_node)
    workflow.add_node("finalize", finalize_node)

    workflow.add_edge(START, "init")
    workflow.add_edge("init", "think")
    workflow.add_edge("think", "act_observe")
    workflow.add_conditional_edges("act_observe", route_after_act, {"think": "think", "finalize": "finalize"})
    workflow.add_edge("finalize", END)

    return workflow.compile(checkpointer=checkpointer)


def initial_state(claim_id: str, claim_type: str, claim_payload: dict) -> dict:
    if claim_type not in REQUIRED_CHECKS:
        raise ValueError(f"Unknown claim_type: {claim_type!r}")
    return {"claim_id": claim_id, "claim_type": claim_type, "claim_payload": claim_payload}
