"""Shared claim-graph core: state shape, check-ledger derivation rules, the finalize
node, and the iteration caps.

This module used to also hold a standalone single-agent ReAct graph (`build_graph`, an
`init`/`think`/`act_observe`/`finalize` loop) that ran when `AGENT_MODE=legacy`. That
mode was removed -- `backend/agent/orchestrator.py`'s Research/Decisioning supervisor
graph is now the only claim-processing path. What remains here is the part
`orchestrator.py` imports and builds on:

  - `ClaimState`            -- the base TypedDict `OrchestratorState` extends
  - `_derive_check_updates` -- the tool-result -> check-ledger business rules
  - `_format_checks`        -- ledger rendering for system prompts / reminders
  - `finalize_node`         -- the deterministic Approve/Deny/Inconclusive close
  - `MAX_ITERATIONS` / `NO_PROGRESS_LIMIT` -- global termination caps
  - `initial_state`         -- the graph's entry payload

Keeping these here (rather than in `orchestrator.py`) preserves the guarantee that the
check-ledger and decision rules live in one place and cannot drift. Termination is
computed from check-ledger state, never self-declared by the model (requirements.md §6).
"""
import json
from typing import Annotated, TypedDict

from langgraph.graph.message import add_messages

from . import ledger
from .checks import REQUIRED_CHECKS

MAX_ITERATIONS = 12
NO_PROGRESS_LIMIT = 5


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


def _format_checks(checks: dict) -> str:
    lines = []
    for name, c in checks.items():
        suffix = f" ({json.dumps(c['detail'])})" if c["detail"] else ""
        lines.append(f"  - {name}: {c['status']}{suffix}")
    return "\n".join(lines)


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
            # Match on the first *word*, not a raw string prefix -- a naive
            # answer.startswith("no") also matches "not sure", "nothing on file",
            # "november" etc., which are free-text answers a human processor could
            # plausibly type (ClaimDetail.jsx's Yes/No buttons have a free-text
            # fallback) and are not a "no". Found via a Phase 9 eval scenario whose
            # deliberately-ambiguous answer ("not sure, can't confirm either way")
            # was silently resolving to FAIL instead of the intended UNKNOWN.
            first_word = answer.split(None, 1)[0].rstrip(",.!;:") if answer.split() else ""
            if first_word in ("yes", "confirmed", "true", "correct", "affirmative"):
                updates.append((check_name, "PASS", {"human_answer": result.get("answer")}))
            elif first_word in ("no", "denied", "false", "negative"):
                updates.append((check_name, "FAIL", {"human_answer": result.get("answer")}))
            else:
                updates.append((check_name, "UNKNOWN", {"human_answer": result.get("answer"), "note": "answer not clearly yes/no"}))

    return updates


def finalize_node(state: ClaimState) -> dict:
    forced_reason = None
    if not state["decision_requested"]:
        if state["iteration"] >= MAX_ITERATIONS:
            forced_reason = f"Inconclusive: hit the {MAX_ITERATIONS}-iteration cap before all checks resolved."
        elif state["iterations_without_progress"] >= NO_PROGRESS_LIMIT:
            forced_reason = f"Inconclusive: {NO_PROGRESS_LIMIT} iterations without measurable progress on remaining checks."

    decision, reason = ledger.finalize_decision(state["claim_id"], state["checks"], forced_reason=forced_reason)
    return {"decision": decision, "decision_reason": reason}


def initial_state(claim_id: str, claim_type: str, claim_payload: dict) -> dict:
    if claim_type not in REQUIRED_CHECKS:
        raise ValueError(f"Unknown claim_type: {claim_type!r}")
    return {"claim_id": claim_id, "claim_type": claim_type, "claim_payload": claim_payload}
