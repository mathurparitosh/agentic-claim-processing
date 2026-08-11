from fastapi import FastAPI, BackgroundTasks
from pydantic import BaseModel
from uuid import uuid4

from .db import test_connection, get_connection
from . import worker

app = FastAPI()


@app.on_event("startup")
def startup_event():
    test_connection()


class ClaimIn(BaseModel):
    claim_type: str
    claim_payload: dict


@app.get("/")
def read_root():
    return {"message": "Claim assistant backend is running."}


@app.post("/claims")
def create_claim(claim: ClaimIn, background_tasks: BackgroundTasks):
    """Persist a new claim and start the background agent run."""
    claim_id = str(uuid4())
    import json

    # insert into claims
    conn = get_connection()
    with conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO claims (id, claim_type, claim_payload, status)
                VALUES (%s, %s, %s, %s)
                """,
                (claim_id, claim.claim_type, json.dumps(claim.claim_payload), 'pending'),
            )
    background_tasks.add_task(worker.run_claim_agent, claim_id)
    return {"claim_id": claim_id, "status": "pending"}
