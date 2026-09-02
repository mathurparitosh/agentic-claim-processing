import json
import os
from uuid import uuid4

from fastapi import APIRouter, BackgroundTasks, Depends, FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from . import db
from . import worker
from .agent import ledger, recovery, tracing
from .agent.checks import storage_claim_type, storage_reason
from .auth import Identity, require_admin, require_auth

app = FastAPI()

# Local dev only: Vite serves the frontend from a different origin (localhost:5173) than
# the API (localhost:8000). Phase 9 deployment serves both same-origin via Nginx, so this
# won't matter in prod, but the browser needs it for local development (tracker.md Phase 6).
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
def startup_event():
    db.open_pool()
    db.test_connection()
    if not os.getenv("AUTH_PASSWORD"):
        raise RuntimeError("AUTH_PASSWORD is not set in .env.local")


@app.on_event("shutdown")
def shutdown_event():
    db.close_pool()


class ClaimIn(BaseModel):
    claim_type: str
    claim_payload: dict


class AnswerIn(BaseModel):
    answer: str


@app.get("/")
def read_root():
    return {"message": "Claim assistant backend is running."}


claims_router = APIRouter(dependencies=[Depends(require_auth)])


def require_claim_access(claim_id: str, identity: Identity = Depends(require_auth)) -> str:
    """Per-claim visibility gate. admin/processor see every claim; a customer only sees
    claims they filed. Returns 404 (not 403) on someone else's claim so its existence
    isn't leaked. Add as `_: str = Depends(require_claim_access)` on any /claims/{id}/* route."""
    if not identity.is_customer:
        return claim_id
    with db.get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT filed_by FROM claims WHERE id = %s", (claim_id,))
            row = cur.fetchone()
    if not row or row["filed_by"] != identity.username:
        raise HTTPException(status_code=404, detail="claim not found")
    return claim_id


@app.get("/whoami")
def whoami(identity: Identity = Depends(require_auth)):
    """Echo the caller's resolved role -- the frontend uses this to confirm login and
    decide which controls/tabs to show."""
    return {"username": identity.username, "role": identity.role}


@claims_router.post("/claims")
def create_claim(claim: ClaimIn, background_tasks: BackgroundTasks, identity: Identity = Depends(require_auth)):
    """Persist a new claim and start the background agent run. `filed_by` records the
    submitting user so a customer can be shown only their own claims."""
    claim_id = str(uuid4())
    claim_type = storage_claim_type(claim.claim_type)
    claim_payload = dict(claim.claim_payload)
    if "reason" in claim_payload:
        claim_payload["reason"] = storage_reason(claim_payload["reason"])

    with db.get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO claims (id, claim_type, claim_payload, status, filed_by)
                VALUES (%s, %s, %s, 'pending', %s)
                """,
                (claim_id, claim_type, json.dumps(claim_payload), identity.username),
            )
    ledger.log_audit(
        claim_id,
        "claim_submitted",
        {"claim_type": claim_type, "claim_payload": claim_payload, "filed_by": identity.username},
        "human",
    )
    background_tasks.add_task(worker.run_claim_agent, claim_id)
    return {"claim_id": claim_id, "status": "pending"}


@claims_router.get("/claims")
def list_claims(limit: int = 50, identity: Identity = Depends(require_auth)):
    """Most recently submitted claims first -- backs the frontend's claim list view
    (tracker.md Phase 6). A customer only sees claims they filed; admin/processor see all."""
    where = "WHERE filed_by = %s" if identity.is_customer else ""
    params = ([identity.username] if identity.is_customer else []) + [limit]
    with db.get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                f"""
                  SELECT c.id, c.claim_type, c.status, c.decision, c.submitted_at, c.last_updated, c.filed_by,
                      c.claim_payload ->> 'reason' AS reason,
                      c.claim_payload ->> 'account_id' AS account_id,
                      a.member_name,
                      t.merchant,
                      t.amount
                  FROM claims c
                  LEFT JOIN account_profiles a ON a.account_id = c.claim_payload ->> 'account_id'
                  LEFT JOIN transactions t
                    ON t.account_id = c.claim_payload ->> 'account_id'
                   AND t.transaction_ref = c.claim_payload ->> 'disputed_transaction_id'
                  {where} ORDER BY c.submitted_at DESC LIMIT %s
                """,
                params,
            )
            return cur.fetchall()


@claims_router.get("/accounts")
def list_accounts():
    """Sample accounts available in the synthetic fixture data -- backs the claim
    form's account-ID autocomplete so the filer picks a real account instead of
    typing one blind."""
    with db.get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT account_id, member_name FROM account_profiles ORDER BY account_id"
            )
            return cur.fetchall()


@claims_router.get("/accounts/{account_id}/transactions")
def list_account_transactions(account_id: str):
    """Transactions for one account -- backs the claim form's disputed-transaction
    dropdown, populated once an account is picked."""
    with db.get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT transaction_ref, occurred_at, amount, merchant, location, channel, status
                FROM transactions WHERE account_id = %s ORDER BY occurred_at
                """,
                (account_id,),
            )
            return cur.fetchall()


@claims_router.get("/claims/{claim_id}")
def get_claim(claim_id: str, _: str = Depends(require_claim_access)):
    with db.get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT id, claim_type, claim_payload, status, decision, decision_reason,
                       pending_question, submitted_at, last_updated, filed_by
                FROM claims WHERE id = %s
                """,
                (claim_id,),
            )
            claim = cur.fetchone()
            if not claim:
                raise HTTPException(status_code=404, detail="claim not found")

            cur.execute(
                "SELECT check_name, check_status, detail, updated_at FROM check_ledger WHERE claim_id = %s ORDER BY check_name",
                (claim_id,),
            )
            checks = cur.fetchall()

    return {**claim, "checks": checks}


@claims_router.get("/claims/{claim_id}/context")
def get_context(claim_id: str, _: str = Depends(require_claim_access)):
    """Account profile + disputed transaction detail for the claim's own account_id /
    disputed_transaction_id (claim_payload), for the frontend's Account & Transaction
    tab (requirements.md §11). Read-only lookup against the same fixture tables the
    Grounding tools query -- this is a display convenience, not a tool call, so it
    doesn't touch the check ledger or audit trail."""
    with db.get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT claim_payload FROM claims WHERE id = %s", (claim_id,))
            row = cur.fetchone()
            if not row:
                raise HTTPException(status_code=404, detail="claim not found")

            account_id = row["claim_payload"].get("account_id")
            transaction_ref = row["claim_payload"].get("disputed_transaction_id")

            account = None
            if account_id:
                cur.execute(
                    """
                    SELECT account_id, member_name, opened_at, standing, fraud_red_flags, dispute_history_count
                    FROM account_profiles WHERE account_id = %s
                    """,
                    (account_id,),
                )
                account = cur.fetchone()

            transaction = None
            if account_id and transaction_ref:
                cur.execute(
                    """
                    SELECT transaction_ref, occurred_at, amount, merchant, location, channel, status
                    FROM transactions WHERE account_id = %s AND transaction_ref = %s
                    """,
                    (account_id, transaction_ref),
                )
                transaction = cur.fetchone()

    return {"account": account, "transaction": transaction}


@claims_router.get("/claims/{claim_id}/audit")
def get_audit(claim_id: str, _: str = Depends(require_claim_access)):
    """Full audit trail timeline for the claim (requirements.md §11), oldest first --
    every tool call, retrieval detail, and human action, each tagged with who performed
    it (`source`: 'agent' or 'human') and when."""
    with db.get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT id FROM claims WHERE id = %s", (claim_id,))
            if not cur.fetchone():
                raise HTTPException(status_code=404, detail="claim not found")

            cur.execute(
                """
                SELECT event_type, event_subtype, payload, source, created_at
                FROM audit_trail WHERE claim_id = %s ORDER BY created_at ASC
                """,
                (claim_id,),
            )
            entries = cur.fetchall()

    return {"entries": entries}


@claims_router.get("/agent/tools", dependencies=[Depends(require_admin)])
def agent_tools():
    """Static tool catalog for the frontend's Agent tab (tracker.md Phase 12): every
    tool, its category, params, owning sub-agent, and the check(s) its result resolves.
    Admin only."""
    return tracing.tool_catalog()


@claims_router.get("/agent/graph", dependencies=[Depends(require_admin)])
def agent_graph():
    """The compiled orchestrator graph as Mermaid + ASCII, with per-node prose, for the
    Agent tab's Graph view. Admin only."""
    return tracing.graph_view()


@claims_router.get("/claims/{claim_id}/agent-context", dependencies=[Depends(require_admin)])
def agent_context(claim_id: str):
    """The message window the model is working from right now, reconstructed from the
    LangGraph checkpoint (thread_id == claim_id), plus the run's counters and next node
    -- backs the claim detail view's Context tab. Admin only; read-only."""
    result = tracing.get_agent_context(claim_id)
    if result is None:
        raise HTTPException(status_code=404, detail="claim not found")
    return result


@claims_router.get("/claims/{claim_id}/memory", dependencies=[Depends(require_admin)])
def agent_memory(claim_id: str):
    """Episodic facts for this claim's account -- the cross-claim memory the run reads
    at init and writes back after account lookups. Backs the Memory tab. Admin only."""
    result = tracing.get_agent_memory(claim_id)
    if result is None:
        raise HTTPException(status_code=404, detail="claim not found")
    return result


@claims_router.get("/claims/{claim_id}/questions")
def get_questions(claim_id: str, _: str = Depends(require_claim_access)):
    with db.get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT status, pending_question FROM claims WHERE id = %s", (claim_id,))
            row = cur.fetchone()

    if not row:
        raise HTTPException(status_code=404, detail="claim not found")
    if row["status"] != "awaiting_input" or not row["pending_question"]:
        return {"pending": False}
    return {"pending": True, "question": row["pending_question"]}


@claims_router.post("/claims/{claim_id}/answer")
def answer_claim(claim_id: str, body: AnswerIn, background_tasks: BackgroundTasks, _: str = Depends(require_claim_access)):
    with db.get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT status FROM claims WHERE id = %s", (claim_id,))
            row = cur.fetchone()
            if not row:
                raise HTTPException(status_code=404, detail="claim not found")
            if row["status"] != "awaiting_input":
                raise HTTPException(status_code=409, detail=f"claim is not awaiting input (status={row['status']})")

            cur.execute(
                "UPDATE claims SET status = 'processing', pending_question = NULL, last_updated = now() WHERE id = %s",
                (claim_id,),
            )

    ledger.log_audit(claim_id, "human_answer", {"answer": body.answer}, "human")
    background_tasks.add_task(worker.resume_claim_agent, claim_id, body.answer)
    return {"claim_id": claim_id, "status": "processing"}


@claims_router.get("/claims/{claim_id}/decision")
def get_decision(claim_id: str, _: str = Depends(require_claim_access)):
    with db.get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT status, decision, decision_reason FROM claims WHERE id = %s", (claim_id,))
            row = cur.fetchone()
            if not row:
                raise HTTPException(status_code=404, detail="claim not found")

            cur.execute(
                "SELECT check_name, check_status, detail FROM check_ledger WHERE claim_id = %s ORDER BY check_name",
                (claim_id,),
            )
            checks = cur.fetchall()

    return {
        "status": row["status"],
        "decision": row["decision"],
        "decision_reason": row["decision_reason"],
        "checks": checks,
    }


RECOVERY_ELIGIBLE_DECISIONS = {"approve", "inconclusive"}


@claims_router.post("/claims/{claim_id}/recovery")
def check_recovery_eligibility(claim_id: str, identity: Identity = Depends(require_auth)):
    """On-demand Recovery agent trigger (specs/technical.md §5, tracker.md Phase 7).
    An internal bank operation -- not customer-facing (403 for customers). Gated in code
    to decision IN ('approve', 'inconclusive') -- a 'deny'd claim never had a credit
    issued, so there's nothing to recover from the merchant (NWR-1.1). Runs synchronously:
    a single retrieval call + one structured-output LLM call, not a multi-minute agent
    loop, so there's no need for the BackgroundTasks/polling pattern the main claim run uses."""
    if identity.is_customer:
        raise HTTPException(status_code=403, detail="recovery assessment is not available to customers")
    with db.get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT decision FROM claims WHERE id = %s", (claim_id,))
            row = cur.fetchone()
            if not row:
                raise HTTPException(status_code=404, detail="claim not found")
            if row["decision"] not in RECOVERY_ELIGIBLE_DECISIONS:
                raise HTTPException(
                    status_code=409,
                    detail=f"claim decision {row['decision']!r} is not recovery-eligible (must be approve or inconclusive)",
                )

    return recovery.assess_recovery(claim_id)


app.include_router(claims_router)
