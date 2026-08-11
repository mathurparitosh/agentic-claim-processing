# Project Context — Claim Assistant

Date: 2026-08-10

Purpose: single-file snapshot of current workspace state and instructions for switching between assistants (Claude / GitHub Copilot) during the project.

---

## Summary of actions completed so far

- Docker Desktop installed; Docker daemon verified running.
- `backend/` scaffold created with `backend/main.py`, `backend/requirements.txt` and a Python virtualenv at `backend/.venv` installed (using Python 3.12).
- `frontend/` scaffold created (Vite + React). `npm install` and `npm run build` verified.
- `.env.example` created; `.env.local` exists (contains live keys — DO NOT COMMIT). `DATABASE_URL` added and redacted in this file.
- `docker-compose.yml` added with a local Postgres service (image: `postgres:15`).
- `schema.sql` created and applied to local Postgres `claims_dev` database; tables created: `claims`, `check_ledger`, `audit_trail`, `episodic_facts`.
- `backend/db.py` helper created and validated against the local Postgres instance (uses `psycopg` with `row_factory=dict_row`).
- `specs/tracker.md` updated to reflect completed scaffolding and schema steps.

## Files created or modified (high-level)

- `.env.example`
- `.env.local` (contains secrets; redacted in repo and gitignored)
- `docker-compose.yml`
- `backend/main.py`
- `backend/requirements.txt`
- `backend/.venv/` (local virtual environment)
- `backend/db.py`
- `frontend/package.json`, `frontend/vite.config.js`, `frontend/index.html`, `frontend/src/main.jsx`, `frontend/dist/` (build output)
- `schema.sql`
- `specs/tracker.md` (progress updated)
- `docs/context.md` (this file)


## Important notes about secrets and environment

- `OPENAI_API_KEY`, `PINECONE_API_KEY`, and `LANGSMITH_API_KEY` should never be committed. Keep `.env.local` gitignored. If you share this repo or switch assistants, redact or remove `.env.local` contents before sharing.
- The `DATABASE_URL` used for local dev: `postgresql://postgres:password@localhost:5432/claims_dev` (set in `.env.local`).

## How to reproduce the local dev environment (quick commands)

# Start local Postgres (docker compose)
```
cd /path/to/agentic-claim-processing
docker compose up -d postgres
```

# Activate backend venv and run the FastAPI app
```
cd backend
source .venv/bin/activate
uvicorn backend.main:app --reload --port 8000
```

# Serve or preview frontend (built files available in `frontend/dist`)
```
cd frontend
npm run dev   # for dev
npm run build # already run; preview with `npm run preview` or serve static files
```

# Apply schema (if needed)
```
docker exec -i $(docker compose ps -q postgres) psql -U postgres -d claims_dev -f /workspace/schema.sql
```


## Switching between assistants (Claude ↔ GitHub Copilot)

When you switch between Claude and GitHub Copilot during this project, follow these handoff steps to keep work consistent and safe:

- Provide this file (`docs/context.md`) to the new assistant as the first read; it contains the current state and key commands.
- Redact secrets first: remove or replace lines in `.env.local` that contain API keys before sharing the file contents (replace values with `REDACTED`).
- Describe the intended next action explicitly (e.g., "Continue wiring FastAPI endpoints for claim submission and background tasks") and point to the relevant files (`backend/main.py`, `backend/db.py`, `specs/tracker.md`).
- If you want the assistant to run commands or modify files, give permission to do so and note whether they should commit changes.
- If switching back to GitHub Copilot, mention where Claude left off (file + line or PR/commit) and include any short notes Claude generated.

Suggested short prompts to hand off:
- To Claude: "Here's the repo state (see docs/context.md). Please implement `POST /claims` and wire BackgroundTasks to start the LangGraph run; avoid touching `.env.local` and ask before creating new external accounts."
- To GitHub Copilot: "I switched from Claude; continue implementing API endpoints and add `db.py` helpers as needed. Use the local Postgres service and the existing `schema.sql`."

## Recommended conventions for switching

- Always keep each assistant's proposed commits small and focused.
- Use `specs/tracker.md` as the canonical progress tracker; update it after each completed task.
- Before handing off, run `git status` and either commit or stash uncommitted work.


## Next suggested tasks

- Implement `backend/db.py` connection pooling (if desired) and a minimal `db.py` wrapper to expose higher-level helpers.
- Implement FastAPI endpoints for `POST /claims` and background job wiring.
- Implement LangGraph scaffolding and checkpoint integration.


---
If you want I can also add a short README entry documenting how to hand off to Claude or create a workflow checklist. Tell me which assistant you want to work with next (Claude or me).


## Recent Activity

- Date: 2026-08-10
- Commit: `feat(api): add POST /claims endpoint with background worker; update tracker` (local commit)
- Commit hash: `8305bfa` (local)

Summary of what changed in this commit:

- Implemented `POST /claims` endpoint in `backend/main.py` that persists a new claim and enqueues a background job via FastAPI `BackgroundTasks`.
- Added `backend/worker.py` — a placeholder background worker that updates claim status and writes `audit_trail` entries (placeholder for LangGraph wiring).
- Created `backend/db.py` (DB helper) and verified the DB connection against the local Postgres `claims_dev` database.
- Created and applied `schema.sql` (tables: `claims`, `check_ledger`, `audit_trail`, `episodic_facts`).
- Updated `specs/tracker.md` to mark Phase 1/2 and the `POST /claims`/BackgroundTasks items completed.

How I tested the change locally (quick reproducible steps):

```bash
# start local Postgres (if not already running)
docker compose up -d postgres

# activate backend venv
cd backend
source .venv/bin/activate

# run a quick test using the FastAPI TestClient (this is what I ran):
python - <<'PY'
from fastapi.testclient import TestClient
from backend.main import app

client = TestClient(app)
resp = client.post('/claims', json={'claim_type':'test','claim_payload':{'foo':'bar'}})
print('POST /claims ->', resp.status_code, resp.json())
PY
```

Expected result: a JSON response with `claim_id` and `status: pending`; after the background worker runs the claim row is updated to `status: completed` and a `decision` is set to `inconclusive` (placeholder behavior).

Notes and next steps:

- Replace the placeholder `worker.run_claim_agent` with the LangGraph orchestrator wiring and `PostgresSaver` checkpointing.
- Add `GET /claims/{id}` and the `ask_human` question/answer endpoints.
- Optionally, add integration tests that run the full agent graph (mocked) against sample claims.
