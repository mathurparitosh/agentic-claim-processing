"""On-demand Recovery agent (specs/technical.md §5) -- not part of the orchestrator's
checkpointed claim-processing run. Triggered per claim, after a decision exists, by
POST /claims/{id}/recovery (backend/main.py), which also enforces the
decision IN ('approve', 'inconclusive') eligibility gate in code before calling this.

Unlike every other check in this app, recovery eligibility is LLM-judged rather than a
deterministic check-ledger closure -- a deliberate, scoped exception (see technical.md
§5 for the full justification: the output is advisory, not the core Approve/Deny/
Inconclusive decision requirements.md §13 governs). The result is a single audit_trail
entry (event_type: recovery_assessment), not a new table or system-of-record outcome.
"""
import json

from pydantic import BaseModel, Field

from .. import db
from . import ledger
from .llm import build_structured_model
from .tools import search_network_policy


class RecoveryAssessment(BaseModel):
    eligible: bool = Field(description="Whether this claim is eligible for card-network recovery")
    reasoning: str = Field(description="Why eligible or not, grounded in the retrieved network policy -- never the model's own training knowledge of card network rules")
    network: str | None = Field(default=None, description="Visa, Mastercard, or the specific ATM network -- set only if eligible")
    reason_code: str | None = Field(default=None, description="The applicable chargeback reason code, per the retrieved policy -- set only if eligible")
    filing_deadline: str | None = Field(default=None, description="The filing deadline, computed from the retrieved policy's stated window and the transaction's occurred_at date -- set only if eligible")
    evidence_summary: list[str] = Field(default_factory=list, description="Evidence from the claim's check ledger supporting the filing -- set only if eligible")
    narrative: str | None = Field(default=None, description="Draft narrative for the recovery filing package -- set only if eligible")


RECOVERY_PROMPT = """You are a card-network recovery analyst. A claim has already been decided by the claims agent; your only job is to judge whether the issuing bank can pursue recovery from the merchant's acquiring bank via Visa/Mastercard/ATM network rules, and if so, to prepare the filing package.

Claim type: {claim_type}
Claim decision: {decision} ({decision_reason})
Claim payload: {claim_payload}

Check ledger (evidence gathered while adjudicating this claim):
{checks}

Applicable network policy retrieved for this claim:
{policy}

Judge eligibility strictly against the retrieved policy and the claim's actual facts above. If nothing was retrieved, or nothing retrieved actually covers this claim's situation, you must find it not eligible -- do not reason from your own training knowledge about card network rules. If eligible, select the specific network and reason code the retrieved policy supports, state the filing deadline it specifies (computed from the transaction's occurred_at date, not the claim's filed_at date), summarize the supporting evidence from the check ledger, and draft a short filing narrative."""


def _format_checks(checks: list[dict]) -> str:
    lines = [f"  - {c['check_name']}: {c['check_status']}" + (f" ({json.dumps(c['detail'])})" if c.get("detail") else "") for c in checks]
    return "\n".join(lines) or "  (no checks recorded)"


def assess_recovery(claim_id: str) -> dict:
    with db.get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT claim_type, claim_payload, decision, decision_reason FROM claims WHERE id = %s",
                (claim_id,),
            )
            claim = cur.fetchone()
            cur.execute(
                "SELECT check_name, check_status, detail FROM check_ledger WHERE claim_id = %s ORDER BY check_name",
                (claim_id,),
            )
            checks = cur.fetchall()

    query = (
        f"chargeback reason code and filing window for a {claim['claim_type']} claim, "
        f"dispute reason: {claim['claim_payload'].get('reason', 'unspecified')}"
    )
    policy_result = search_network_policy.invoke({"query": query})

    prompt = RECOVERY_PROMPT.format(
        claim_type=claim["claim_type"],
        decision=claim["decision"],
        decision_reason=claim["decision_reason"],
        claim_payload=json.dumps(claim["claim_payload"]),
        checks=_format_checks(checks),
        policy=json.dumps(policy_result.get("results", [])),
    )

    assessment = build_structured_model(RecoveryAssessment).invoke(prompt)

    payload = {
        "claim_type": claim["claim_type"],
        "decision": claim["decision"],
        "query": query,
        "retrieved_policy": policy_result,
        "assessment": assessment.model_dump(),
    }
    ledger.log_audit(claim_id, "recovery_assessment", payload, "agent")
    return payload
