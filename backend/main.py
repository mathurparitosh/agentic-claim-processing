import json
import os
from uuid import uuid4

from fastapi import APIRouter, BackgroundTasks, Depends, FastAPI, HTTPException, Security
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pydantic import BaseModel

from . import db
from . import worker

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

AUTH_PASSWORD = os.getenv("AUTH_PASSWORD")
_bearer_scheme = HTTPBearer()


def require_auth(credentials: HTTPAuthorizationCredentials = Security(_bearer_scheme)):
    """Shared-password gate (technical.md's Auth row). Send `Authorization: Bearer <AUTH_PASSWORD>`."""
    if not AUTH_PASSWORD or credentials.credentials != AUTH_PASSWORD:
        raise HTTPException(status_code=401, detail="invalid credentials")


@app.on_event("startup")
def startup_event():
    db.open_pool()
    db.test_connection()
    if not AUTH_PASSWORD:
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


@claims_router.post("/claims")
def create_claim(claim: ClaimIn, background_tasks: BackgroundTasks):
    """Persist a new claim and start the background agent run."""
    claim_id = str(uuid4())

    with db.get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO claims (id, claim_type, claim_payload, status)
                VALUES (%s, %s, %s, 'pending')
                """,
                (claim_id, claim.claim_type, json.dumps(claim.claim_payload)),
            )
    background_tasks.add_task(worker.run_claim_agent, claim_id)
    return {"claim_id": claim_id, "status": "pending"}


@claims_router.get("/claims")
def list_claims(limit: int = 50):
    """Most recently submitted claims first -- backs the frontend's claim list view
    (tracker.md Phase 6). Not in the original Phase 5 endpoint list; added because a
    list view has no other way to discover claims that exist server-side."""
    with db.get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT id, claim_type, status, decision, submitted_at, last_updated
                FROM claims ORDER BY submitted_at DESC LIMIT %s
                """,
                (limit,),
            )
            return cur.fetchall()


@claims_router.get("/claims/{claim_id}")
def get_claim(claim_id: str):
    with db.get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT id, claim_type, claim_payload, status, decision, decision_reason,
                       pending_question, submitted_at, last_updated
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


@claims_router.get("/claims/{claim_id}/questions")
def get_questions(claim_id: str):
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
def answer_claim(claim_id: str, body: AnswerIn, background_tasks: BackgroundTasks):
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

    background_tasks.add_task(worker.resume_claim_agent, claim_id, body.answer)
    return {"claim_id": claim_id, "status": "processing"}


@claims_router.get("/claims/{claim_id}/decision")
def get_decision(claim_id: str):
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


app.include_router(claims_router)
