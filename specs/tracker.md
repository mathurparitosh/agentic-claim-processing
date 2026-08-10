# Claim Assistant — Implementation Tracker

Companion to [requirements.md](requirements.md) and [technical.md](technical.md).
Work through phases in order — each one depends on the previous. Check items off as
you go.

## Legend

- `🌐 EXTERNAL` — happens outside this repo/VS Code: a web dashboard, an account
  signup, an SSH session on the Ubuntu server.
- `💻 LOCAL` — happens in this repo, in your terminal or VS Code.
- Unchecked `[ ]` = not started. Check to `[x]` when done.

---

## Phase 0 — Accounts & External Prerequisites

Do all of this first — nothing in Phase 1+ can run without these keys/services.

### OpenAI (LLM + embeddings + reranking)
- [x] 🌐 Sign up / log in at platform.openai.com
- [x] 🌐 Add a payment method under **Billing → Payment methods** (API calls fail without one) — confirm this is done
- [x] 🌐 Create an API key under **API keys → Create new secret key** — copy it immediately, it's shown once
  - ⚠️ `OPENAI_API_KEY` in `.env.local` currently holds the **LangSmith** key value (`lsv2_pt_...` prefix) instead of an actual OpenAI key (`sk-...` prefix) — go back to the OpenAI dashboard and copy the real key in before Phase 3+.
- [x] 🌐 Set a usage limit/budget alert under **Billing → Limits** (recommended, not required)

### Pinecone (semantic memory / policy corpus)
- [x] 🌐 Sign up at app.pinecone.io
- [x] 🌐 Create or select a project
- [x] 🌐 Create an index:
  - name: `claims-policy-corpus` (or your choice — record it, it goes in `.env`)
  - dimension: **1536** (must match `text-embedding-3-small`)
  - metric: **cosine**
  - type: Serverless, region close to your Ubuntu server
- [x] 🌐 Generate an API key under **API Keys**

### LangSmith (dev-time tracing)
- [x] 🌐 Sign up at smith.langchain.com
- [x] 🌐 Create a project, e.g. `claim-assistant`
- [x] 🌐 Generate an API key under **Settings → API Keys**

### Ubuntu deployment server
- [x] 🌐 Confirm SSH access: hostname/IP, SSH key or password, a sudo-capable user
- [x] 🌐 Decide: access via server IP, or point an existing domain at it (optional — not required to ship)

### Version control (recommended, not strictly required)
- [ ] 🌐 Create a GitHub (or other git host) repo — makes it far easier to get code onto the Ubuntu server later
- [ ] 💻 `git init` in this project directory (currently **not** a git repo)
- [ ] 💻 Add a `.gitignore` (`.env`, `__pycache__/`, `node_modules/`, `*.pyc`, etc.)

### Local dev tooling
- [ ] 🌐 Install Docker Desktop (or Docker Engine) locally — for a local Postgres instance during development. This is a one-time installer download, no account required.
- [ ] 🌐 Install Node.js (LTS) and Python 3.11+ locally if not already present

---

## Phase 1 — Project Scaffolding

- [ ] 💻 Create `backend/` and `frontend/` folders
- [ ] 💻 Python virtualenv in `backend/`; install: `fastapi uvicorn[standard] langgraph langgraph-checkpoint-postgres langchain-openai pinecone psycopg[binary] python-dotenv langsmith unstructured`
- [ ] 💻 Scaffold React app in `frontend/` (Vite)
- [ ] 💻 `docker-compose.yml` with a local Postgres service for dev (mirrors the prod Postgres engine)
- [x] 💻 `.env.example` / `.env.local` listing every required variable:
  - `OPENAI_API_KEY`
  - `PINECONE_API_KEY`, `PINECONE_INDEX`
  - `LANGSMITH_API_KEY`, `LANGSMITH_TRACING=true`, `LANGSMITH_ENDPOINT`, `LANGSMITH_PROJECT`
  - `DATABASE_URL`
  - `AUTH_PASSWORD` (shared-password gate)
- [ ] 💻 Fill in remaining real values from Phase 0 (Pinecone, DB, auth password) — never commit `.env.local`
- [ ] 💻 Add `.env.local` to `.gitignore` before the first `git init`/commit (project isn't a git repo yet)

---

## Phase 2 — Data Layer (Postgres)

- [ ] 💻 Write `schema.sql`: `claims`, `check_ledger`, `audit_trail`, `episodic_facts` tables (per technical.md's memory-to-store mapping)
- [ ] 💻 Apply `schema.sql` to local dev Postgres (via `docker compose up` + `psql`)
- [ ] 💻 Confirm LangGraph's `PostgresSaver.setup()` creates its own checkpointer tables against the same DB
- [ ] 💻 Small `db.py` connection helper shared by the API and agent code

---

## Phase 3 — RAG Ingestion Pipeline

- [ ] 🌐/💻 Source or author sample policy & regulation documents (Word/PDF). **This is a content-authoring task, not code** — write/collect these in Word or Google Docs outside VS Code, then drop the files into a `policy_docs/` folder in the repo.
- [ ] 💻 Ingestion script: `unstructured` parse → custom clause-boundary chunker (per requirements.md §9) → embed via `text-embedding-3-small` → upsert to Pinecone
- [ ] 💻 Run ingestion once against the Pinecone index created in Phase 0
- [ ] 💻 Retrieval function: query → top **k=20** → GPT rerank → relevance-floor check → top **3** (or zero, per requirements.md §9)
- [ ] 💻 Manual smoke test: run one sample query, confirm sensible results + citations come back

---

## Phase 4 — Tools & Agent Core (LangGraph)

- [ ] 💻 Implement tool functions: retrieval, grounding, computation, `ask_human`, `write_determination` (per requirements.md §8)
- [ ] 💻 Synthetic data generator script (GPT-generated transaction/log/account records) — review each generated record against its claim's intended expected outcome (per technical.md's Synthetic Data row)
- [ ] 💻 Load generated synthetic data into Postgres fixture tables
- [ ] 💻 Build the LangGraph graph: Think/Act/Observe nodes, termination logic reading the Check Ledger (requirements.md §5), `PostgresSaver` checkpointer wired in
- [ ] 💻 Episodic memory read/write helpers against `episodic_facts`
- [ ] 💻 Smoke test: run the graph against one hand-picked claim end-to-end, locally, outside the API layer

---

## Phase 5 — Orchestrator & API (FastAPI)

- [ ] 💻 Endpoints: `POST /claims`, `GET /claims/{id}`, `GET /claims/{id}/questions`, `POST /claims/{id}/answer`, `GET /claims/{id}/decision`
- [ ] 💻 Wire claim submission to `BackgroundTasks` running the LangGraph agent (per technical.md's Background Execution row)
- [ ] 💻 Shared-password auth middleware on the API
- [ ] 💻 End-to-end local test via curl/HTTP: submit → poll status → answer a question if one comes up → see final decision

---

## Phase 6 — Frontend (React)

- [ ] 💻 Claim submission form
- [ ] 💻 Claim list / status view (polls the backend — per the `ask_human` channel decision)
- [ ] 💻 Question/answer UI for `ask_human`
- [ ] 💻 Decision view: Approve/Deny/Inconclusive + citations + check-ledger breakdown
- [ ] 💻 Password-gate screen
- [ ] 💻 End-to-end test in-browser against the local backend

---

## Phase 7 — Observability & Audit

- [ ] 💻 Wire LangSmith tracing using the Phase 0 credentials
- [ ] 💻 Confirm `audit_trail` rows are written for every tool call, retrieval detail, and final determination (requirements.md §11)
- [ ] 💻 Manual check: pull up one LangSmith trace and the corresponding `audit_trail` rows side by side — confirm they tell the same story

---

## Phase 8 — Evaluation (10 test claims)

- [ ] 💻 Design 10 claims spanning claim types + evidence-completeness levels, each with a predetermined expected outcome (requirements.md §12) — write these out (e.g. a markdown table) before generating synthetic evidence for them
- [ ] 💻 Generate synthetic evidence per claim (Phase 4 generator)
- [ ] 💻 Jupyter notebook: run all 10 through the agent, compare actual vs. expected decision + check trace
- [ ] 💻 Fix discrepancies; re-run until the eval set passes, or document known gaps

---

## Phase 9 — Deployment (your Ubuntu server)

- [ ] 🌐 SSH into the server
- [ ] 🌐 Install system packages: Python 3.11+, Node.js/npm, PostgreSQL server, Nginx, git
- [ ] 🌐 Create a Postgres DB + user on the server; apply `schema.sql`; note the connection string
- [ ] 🌐 Get the code onto the server (`git clone`, or `scp` if not using git)
- [ ] 🌐 Create the server-side `.env` with real production values (OpenAI/Pinecone/LangSmith keys, prod `DATABASE_URL`, `AUTH_PASSWORD`) — copied manually, never committed
- [ ] 🌐 `npm run build` the React app; point Nginx at the static output
- [ ] 🌐 Create a systemd unit for the FastAPI app (uvicorn) so it restarts on crash/reboot
- [ ] 🌐 Configure Nginx as a reverse proxy: static frontend + `/api` → FastAPI (uvicorn)
- [ ] 🌐 `ufw allow` only what's needed (80, 443, OpenSSH) — nothing else should be open to the internet
- [ ] 🌐 (Optional) Point a domain at the server + get a TLS cert via certbot; otherwise access over HTTP via the server's IP
- [ ] 🌐 Run the Pinecone ingestion script once against production (same index, or a separate prod index for dev/prod separation)
- [ ] 🌐 Smoke test the deployed URL end-to-end

---

## Phase 10 — Capstone Wrap-up

- [ ] 💻 Record/prepare a demo walkthrough referencing requirements.md and technical.md
- [ ] 💻 Confirm technical.md and the `.drawio` diagram still match what was actually built; update if implementation diverged
- [ ] 💻 Write up known limitations / follow-ups (e.g., multi-user auth, CI-based test harness, dedicated reranker)
