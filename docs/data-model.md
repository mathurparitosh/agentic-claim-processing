# Data Model — table-by-table

What every table in the local Postgres database (`claims_dev`) is for, plus the one
non-Postgres store (Qdrant). Companion to [`../schema.sql`](../schema.sql),
[`../specs/requirements.md`](../specs/requirements.md), and
[`../specs/technical.md`](../specs/technical.md) §2/§4.

Four groups:

| Group | Tables | Defined in | FK to `claims`? |
|---|---|---|---|
| Claims domain | `claims`, `check_ledger`, `audit_trail`, `episodic_facts` | `schema.sql` | first two cascade; `episodic_facts` no |
| Synthetic research fixtures | `transactions`, `access_logs`, `account_profiles` | `schema.sql` | no (keyed by `account_id` string) |
| LangGraph checkpointer | `checkpoints`, `checkpoint_blobs`, `checkpoint_writes`, `checkpoint_migrations` | `PostgresSaver.setup()` (`backend/setup_checkpointer.py`) | no (keyed by `thread_id` = claim id) |
| Semantic memory (not Postgres) | Qdrant collection `claims-policy-corpus` | `scripts/ingest_policy_corpus.py` | n/a |

---

## Claims domain — the application's own data

### `claims`

System of record for every submitted claim, one row each. Written by `POST /claims`,
updated by `backend/worker.py` and `backend/agent/ledger.py`'s `finalize_decision`.

| Column | Notes |
|---|---|
| `id` (UUID) | Primary key. Also used verbatim as the LangGraph `thread_id`. |
| `claim_type` | `Fraud` or `Billing Dispute`. |
| `claim_payload` (JSONB) | `account_id`, `disputed_transaction_id`, Title Case `reason`, `filed_at`. |
| `status` | `pending → processing → awaiting_input ↔ processing → completed` (or `failed`). |
| `decision` / `decision_reason` | `approve` \| `deny` \| `inconclusive`, filled only at finalize. |
| `pending_question` (JSONB) | Set while `awaiting_input` from the `ask_human` interrupt payload; cleared on answer. |
| `submitted_at` / `last_updated` | Timestamps. |

### `check_ledger`

The **structured short-term memory** the decision is computed from
(requirements.md §6). One row per required check per claim
(`UNIQUE(claim_id, check_name)`), `ON DELETE CASCADE` from `claims`.

| Column | Notes |
|---|---|
| `check_name` | e.g. `transaction_exists`, `policy_liability_rule` — the required checks per `claim_type` (`backend/agent/checks.py`, taxonomy in technical.md §4). |
| `check_status` | `UNKNOWN` \| `PASS` \| `FAIL` \| `BLOCKED`. |
| `detail` (JSONB) | The tool result or human answer that closed the check. |

Seeded all-`UNKNOWN` at run start; each tool result maps to updates here;
`compute_decision()` reads the final state (any `FAIL` → deny, all `PASS` → approve,
otherwise inconclusive). Only `ledger.py` writes it.

### `audit_trail`

Append-only event log (requirements.md §11), `ON DELETE CASCADE` from `claims`.
Every row is tagged `source` = `agent` or `human`. This is what the frontend
**Audit Trail** tab renders. Only `ledger.log_audit` writes it.

| Column | Notes |
|---|---|
| `event_type` | `claim_submitted`, `run_started`, `agent_think`, `tool_call`, `human_answer`, `determination_written`, `recovery_assessment`. |
| `event_subtype` | Sub-agent name for `agent_think`; tool name for `tool_call`; the decision for `determination_written`. |
| `payload` (JSONB) | Full detail: model/provider, proposed tools, tool args + full result (incl. all ~20 retrieval candidates + scores, per requirements.md §9), which checks were updated, etc. |

### `episodic_facts`

**Long-term cross-claim memory** (technical.md §2) — facts about recurring entities so
a later claim touching the same account doesn't re-derive them. **Not** linked to
`claims`, so it survives `DELETE FROM claims`.

| Column | Notes |
|---|---|
| key | `UNIQUE(entity_id, entity_type, fact_key)` — e.g. `("ACC-9001", "account", "account_standing")`. |
| `fact_value` (JSONB) | The remembered value. |
| `provenance` (JSONB) | Which claim / tool established it. |

Read in `init_node`; written after `account_standing` / `account_red_flags` grounding
calls (`backend/agent/episodic.py`).

---

## Synthetic "research source" fixtures — what the Grounding tools read

LLM-generated stand-ins for real bank systems (technical.md §4), loaded by
`backend/generate_synthetic_data.py`. Keyed by `account_id` string, **no FK to
claims** — kept when you clear claims.

### `transactions`

Per-account transaction history. `UNIQUE(account_id, transaction_ref)`.
Backs `lookup_transaction` (resolves `transaction_exists`) and the computation tools
`check_transaction_anomaly` / `check_duplicate_charge`.
Columns: `occurred_at`, `amount`, `merchant`, `location`, `channel`, `status`.

### `access_logs`

Per-account login / device events. Backs `lookup_access_logs`
(resolves `system_access_log_check`). Key column: `risk_flag` (boolean) — a flagged
login near the disputed transaction's time is what makes that check PASS.

### `account_profiles`

One row per account (`account_id` is the PK). Backs `lookup_account_profile`
(resolves `account_standing` and `account_red_flags`).
Columns: `standing` (`good` / `suspended` / …), `fraud_red_flags` (JSONB array),
`dispute_history_count`. A deliberately missing row in some eval scenarios forces
`ask_human`.

---

## LangGraph checkpointer — agent run-state

Created by `PostgresSaver.setup()` (`backend/setup_checkpointer.py`), **not**
`schema.sql`. Keyed by `thread_id` (= the claim `id` as text). This is what lets a
claim paused on `ask_human` resume later, even across a backend restart
(requirements.md §13, "Resumability"). **Not** FK'd to `claims`, so rows are orphaned
(harmless) after `DELETE FROM claims`; `TRUNCATE` them to tidy up.

| Table | Role |
|---|---|
| `checkpoints` | One row per graph super-step per thread — snapshot of graph position and channel versions after each node. The save points the graph resumes from. |
| `checkpoint_blobs` | The actual serialized channel values (messages, `checks`, counters…) referenced by `checkpoints`; split out because they're larger blobs. |
| `checkpoint_writes` | Writes a node emitted *during* a super-step that isn't fully committed — needed to resume from the middle of a step (the `ask_human` interrupt case). |
| `checkpoint_migrations` | Internal schema-version bookkeeping for the checkpointer library. **Never touch.** |

---

## Not a table: the policy corpus (Qdrant)

**Semantic long-term memory** — the RAG side — lives in **Qdrant**, collection
`claims-policy-corpus`: ~114 policy / regulation clause chunks with embeddings
(`text-embedding-3-small`), filtered by `claim_type`
(`billing_dispute` / `fraud` / `network_recovery`). Queried by `search_policy` (main
loop) and `search_network_policy` (Recovery agent). Entirely separate from Postgres;
ingested by `scripts/ingest_policy_corpus.py`.

---

## Connecting a GUI (pgAdmin)

The Postgres container publishes `5432` on the host (`docker-compose.yml`), so any
client connects to `localhost` with the credentials baked into that file.

### Install pgAdmin (macOS)

```bash
brew install --cask pgadmin4
```

No Homebrew? Download the macOS `.dmg` from <https://www.pgadmin.org/download/pgadmin-4-macos/>
and drag it to Applications. (Windows/Linux builds are on the same download page.)

### Register the connection

1. Start the database if it isn't up: `docker compose up -d postgres`.
2. Open pgAdmin. On first launch it asks you to set a **master password** — that's a
   local pgAdmin vault password, unrelated to Postgres; pick anything.
3. Left panel → right-click **Servers** → **Register → Server…**
4. **General** tab → **Name:** `claims_dev (docker)` (any label).
5. **Connection** tab:

   | Field | Value |
   |---|---|
   | Host name/address | `localhost` |
   | Port | `5432` |
   | Maintenance database | `claims_dev` |
   | Username | `postgres` |
   | Password | `password` |
   | Save password | ✔ (optional) |

6. **Save.** Expand
   `claims_dev (docker) → Databases → claims_dev → Schemas → public → Tables` to see
   every table from this doc. Right-click a table → **View/Edit Data → All Rows**, or
   use **Tools → Query Tool** to run SQL (e.g. the cleanup recipes below).

### If pgAdmin itself runs in Docker

Use the host's Docker gateway instead of `localhost`:

```bash
docker run -d --name pgadmin -p 5050:80 \
  -e PGADMIN_DEFAULT_EMAIL=admin@local.dev \
  -e PGADMIN_DEFAULT_PASSWORD=admin \
  dpage/pgadmin4
```

Then open <http://localhost:5050> and register the server with **Host name/address:**
`host.docker.internal` (Docker Desktop on macOS/Windows), port `5432`, same
db/user/password as above. On Linux, add `--add-host=host.docker.internal:host-gateway`
to the `docker run` command, or point the host at the compose network instead.

### Credentials reference

All from `docker-compose.yml` → `services.postgres.environment`:

| | |
|---|---|
| host / port | `localhost` / `5432` (`host.docker.internal` from another container) |
| database | `claims_dev` |
| user / password | `postgres` / `password` |
| connection URL | `postgresql://postgres:password@localhost:5432/claims_dev` (this is `DATABASE_URL` in `.env.local`) |

---

## Cleanup recipes

```sql
-- Just the claims (check_ledger + audit_trail cascade automatically)
DELETE FROM claims;

-- Full clean slate: also derived memory + all agent run-state
BEGIN;
DELETE FROM claims;
DELETE FROM episodic_facts;
TRUNCATE checkpoints, checkpoint_blobs, checkpoint_writes;   -- keep checkpoint_migrations
COMMIT;
```

Never clear as part of "cleaning up claims": `transactions`, `access_logs`,
`account_profiles` (reload cost), `checkpoint_migrations`, or the Qdrant collection.

Run from the host:
```bash
docker compose exec -T postgres psql -U postgres -d claims_dev -c 'DELETE FROM claims;'
```
