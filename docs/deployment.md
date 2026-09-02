# Deployment Guide — Claim Assistant on a Linux server

Step-by-step guide and checklist for deploying this repo to a single Linux VM
(Ubuntu 22.04 / 24.04 or Debian assumed; adjust package names for RHEL/Alma).

**Target topology** — everything on one box:

```
                internet
                   │  :80 / :443
              ┌────▼─────┐
              │  Nginx   │  serves frontend/dist  +  proxies /api/ → 127.0.0.1:8000
              └────┬─────┘
         ┌─────────▼──────────┐
         │ uvicorn (systemd)  │  backend.main:app, 1 worker, BackgroundTasks agent
         └─────────┬──────────┘
              ┌─────▼─────┐
              │ Postgres  │  localhost only  (app data + LangGraph checkpoints)
              └───────────┘
       external: OpenAI API · Qdrant Cloud · LangSmith (optional)
```

> **Why one uvicorn worker?** The claim-processing agent runs in-process via FastAPI
> `BackgroundTasks` (no Celery/RQ — see `specs/tracker.md` backlog). Multiple workers
> would each hold their own connection pool and could double-run or drop background
> tasks. Scale vertically, or do the "split the worker out" backlog item first.

---

## 0 · Before you start — gather these

- [ ] SSH access to the server as a **sudo-capable** user, plus its IP or a domain name pointed at it
  - If the VM already runs another site, plan for a **dedicated subdomain** (`claims.<yourdomain>`) — see *Sharing the server with another site* below
- [ ] **OpenAI API key** with billing enabled (`sk-…`) — used for the agent LLM *and* embeddings
- [ ] **Qdrant Cloud** cluster URL + API key (the vector store is managed, not self-hosted here)
- [ ] **LangSmith** API key + project name — optional, tracing only
- [ ] A value you choose for **`AUTH_PASSWORD`** (the single shared login password for the app)
- [ ] Decide an install path — this guide uses **`/opt/claim-assistant`**
- [ ] The repo's git URL, or a way to copy the code up (`scp` a tarball)

---

## 1 · Server baseline

```bash
ssh you@SERVER_IP
sudo apt update && sudo apt -y upgrade

# Core packages
sudo apt -y install git nginx postgresql postgresql-client \
                    build-essential libpq-dev \
                    python3-venv python3-dev

# Node.js LTS (Ubuntu's apt version is too old for Vite) — NodeSource:
curl -fsSL https://deb.nodesource.com/setup_20.x | sudo -E bash -
sudo apt -y install nodejs
```

- [ ] `git --version`, `nginx -v`, `psql --version` all succeed
- [ ] `node -v` ≥ 18 and `npm -v` succeed
- [ ] **Python 3.11+** available — `python3 --version`
  - Ubuntu 24.04 ships 3.12 ✔. On 22.04 (ships 3.10) add deadsnakes:
    `sudo add-apt-repository ppa:deadsnakes/ppa && sudo apt install python3.12 python3.12-venv python3.12-dev`
    and use `python3.12` wherever this guide says `python3`.

---

## 2 · PostgreSQL

Create a database **owned by** the app user, so the app can create its own tables
(`schema.sql` and the LangGraph checkpointer both run `CREATE TABLE`), with no
PG15 `public`-schema grant fiddling.

```bash
sudo -u postgres psql <<'SQL'
CREATE ROLE claims_app LOGIN PASSWORD 'CHANGE_ME_STRONG';
CREATE DATABASE claims OWNER claims_app;
SQL
```

- [ ] Role + database created
- [ ] Connection string works over TCP with password (not peer auth):
      `psql "postgresql://claims_app:CHANGE_ME_STRONG@localhost:5432/claims" -c '\conninfo'`
- [ ] Postgres is **not** exposed to the internet — default `listen_addresses = 'localhost'`; do **not** open port 5432 in the firewall

Your `DATABASE_URL` is:
`postgresql://claims_app:CHANGE_ME_STRONG@localhost:5432/claims`

---

## 3 · Get the code

```bash
sudo mkdir -p /opt/claim-assistant
sudo chown "$USER":"$USER" /opt/claim-assistant
git clone <REPO_URL> /opt/claim-assistant
cd /opt/claim-assistant
```

- [ ] Repo is at `/opt/claim-assistant` and `git log -1` shows the commit you expect
- [ ] (If you `scp`'d a tarball instead) `schema.sql`, `backend/`, `frontend/`, `docs/files/` are all present

---

## 4 · Backend — virtualenv, config, database schema

### 4a · Python environment

```bash
cd /opt/claim-assistant
python3 -m venv backend/.venv
backend/.venv/bin/pip install -U pip
backend/.venv/bin/pip install -r backend/requirements.txt
```

- [ ] Install completes (can take a few minutes — `unstructured` and friends are large).
      If a wheel fails to build, `apt install` the `-dev` lib it names and retry.

### 4b · Create `.env.local` (repo root)

The app loads config from **`/opt/claim-assistant/.env.local`** specifically
(`backend/db.py` hard-codes that path; the ingestion/data scripts do too). Real
process environment variables also win, but a file is simplest.

```bash
cd /opt/claim-assistant
cp .env.example .env.local
nano .env.local          # fill in real values — see Appendix A
chmod 600 .env.local     # keys live here
```

- [ ] Every blank in `.env.example` is filled (`OPENAI_API_KEY`, `QDRANT_URL`, `QDRANT_API_KEY`, `AUTH_PASSWORD`, `DATABASE_URL`)
- [ ] `DATABASE_URL` points at the local `claims` DB from step 2
- [ ] `AGENT_MODE` is **not** present (removed — the orchestrator is the only path)
- [ ] `LANGSMITH_TRACING=true` only if you actually set a `LANGSMITH_API_KEY`; otherwise `false`
- [ ] `.env.local` is `chmod 600` and owned by the user the service will run as

### 4c · Apply the schema + checkpointer tables

```bash
cd /opt/claim-assistant
psql "$(grep -E '^DATABASE_URL=' .env.local | cut -d= -f2-)" -f schema.sql
backend/.venv/bin/python -m backend.setup_checkpointer
```

- [ ] `schema.sql` applied — `psql "$DATABASE_URL" -c '\dt'` lists `claims`, `check_ledger`, `audit_trail`, `episodic_facts`, `transactions`, `access_logs`, `account_profiles`
- [ ] `setup_checkpointer` prints **"PostgresSaver checkpoint tables ready."** and `\dt` now also shows `checkpoints`, `checkpoint_blobs`, `checkpoint_writes`, `checkpoint_migrations`
- [ ] DB reachable from the app:
      `backend/.venv/bin/python -c "from backend import db; db.open_pool(); print(db.test_connection()); db.close_pool()"` → `{'?column?': 1}`

---

## 5 · Qdrant — ingest the policy corpus (one-time)

```bash
cd /opt/claim-assistant
backend/.venv/bin/python scripts/ingest_policy_corpus.py
```

- [ ] Output ends with **"Upserting 114 points into Qdrant collection 'claims-policy-corpus'"** (101 `billing_dispute`/`fraud` + 13 `network_recovery`)
- [ ] The collection shows ~114 points in the Qdrant Cloud dashboard
- [ ] Re-running is safe (idempotent `uuid5`-keyed upsert) — only needed again if `docs/files/*.md` change

> Uses `OPENAI_API_KEY` for `text-embedding-3-small` (1536-dim). If you point at a
> **separate prod collection**, set `QDRANT_COLLECTION` in `.env.local` before running.

---

## 6 · (Optional) Load demo fixture data

Only if you want sample accounts/claims to show. A clean prod can skip this — processors
just submit real claims.

**Option A — generate on the server** (makes ~a dozen OpenAI calls, a few cents):

```bash
cd /opt/claim-assistant          # MUST be run from the repo root
backend/.venv/bin/python -m backend.generate_synthetic_data
```

**Option B — copy from your dev machine's DB:**

```bash
# on your laptop:
pg_dump "$DEV_DATABASE_URL" -t account_profiles -t transactions -t access_logs --data-only \
  | ssh you@SERVER_IP 'psql "postgresql://claims_app:...@localhost:5432/claims"'
```

- [ ] `psql "$DATABASE_URL" -c 'SELECT account_id FROM account_profiles ORDER BY 1'` lists `ACC-9001 … ACC-9010` (minus 9006/9007/9010, which deliberately have no profile row)
- [ ] Each loaded account has 7 transactions

---

## 7 · Frontend — build the static bundle

`frontend/src/api.js` prefixes every request with `VITE_API_BASE_URL`. Build with
`/api` so calls are same-origin and Nginx proxies them to the backend.

```bash
cd /opt/claim-assistant/frontend
npm ci
# VITE_DEMO_PASSWORD is the value the login screen's admin/processor/customer
# quick-pick buttons prefill into the password field. Set it to your real
# AUTH_PASSWORD for one-click demo logins, or to '' to disable prefill (users
# then type the password; the username is still prefilled).
VITE_API_BASE_URL=/api VITE_DEMO_PASSWORD='your-AUTH_PASSWORD-or-blank' npm run build
```

- [ ] `frontend/dist/index.html` and `frontend/dist/assets/…` regenerated (don't rely on the copy committed in the repo — it's built for `localhost:8000`)
- [ ] `grep -r "localhost:8000" dist/` returns **nothing**
- [ ] `grep -rl "/api/" dist/assets/*.js` finds the API base baked in
- [ ] The three demo users (`admin` / `processor` / `customer`, all using `AUTH_PASSWORD`)
      log in and land on their expected view — decide whether baking `VITE_DEMO_PASSWORD`
      into the bundle is acceptable for your deployment

---

## 8 · Backend service — systemd + uvicorn

Create a dedicated service user and unit (full file in **Appendix B**):

```bash
sudo useradd --system --home /opt/claim-assistant --shell /usr/sbin/nologin claimsvc || true
sudo chown -R claimsvc:claimsvc /opt/claim-assistant
sudo chmod 600 /opt/claim-assistant/.env.local
sudo nano /etc/systemd/system/claim-assistant.service   # paste Appendix B
sudo systemctl daemon-reload
sudo systemctl enable --now claim-assistant
```

- [ ] `systemctl status claim-assistant` → **active (running)**
- [ ] `journalctl -u claim-assistant -n 50` shows Uvicorn startup, **no** `RuntimeError: AUTH_PASSWORD is not set` / `DATABASE_URL is not set`
- [ ] `curl -s localhost:8000/` → `{"message":"Claim assistant backend is running."}`
- [ ] `curl -s -o /dev/null -w '%{http_code}\n' localhost:8000/claims` → **401** (auth works)
- [ ] Unit uses `--host 127.0.0.1` (never `0.0.0.0` — Nginx is the only front door) and **no `--reload`**

---

## Sharing the server with another site

**Skip this if the VM is dedicated to Claim Assistant.** If it already serves another
site, run Claim Assistant on **its own subdomain** (`claims.<yourdomain>`) with its own
Nginx `server` block and its own TLS cert. Nginx routes each request to the block whose
`server_name` matches the request's `Host` header, so two apps coexist cleanly — as long
as you don't lean on `default_server`:

- **Every `server` block names a distinct hostname.** No two blocks share a `server_name`.
- **`default_server` is only the fallback** for a request whose `Host` matches nothing
  (e.g. someone hitting the bare IP). Give each real app an exact-match `server_name` and
  it never depends on which block is the default. Do **not** add `default_server` to the
  Claim Assistant block, and do **not** remove it from the other site's block.
- **Only Claim Assistant runs on its port.** The backend is on `127.0.0.1:8000`; if the
  other site's backend also uses 8000, change one (`--port` in Appendix B + the
  `proxy_pass` in Appendix C).

**Setup**

1. **DNS** — add an `A` record `claims` → this server's public IP; confirm it before touching Nginx:
   ```bash
   dig +short claims.example.com          # must print the server's IP
   ```
2. **Nginx block** — create `/etc/nginx/sites-available/claim-assistant` from Appendix C
   with `server_name claims.example.com;`, and enable it **without touching the other site**:
   ```bash
   sudo ln -sf /etc/nginx/sites-available/claim-assistant /etc/nginx/sites-enabled/
   # do NOT `rm` sites-enabled/default if the other site is served from it
   sudo chmod o+x /opt /opt/claim-assistant /opt/claim-assistant/frontend
   sudo nginx -t && sudo systemctl reload nginx
   ```
3. **Confirm each hostname resolves to its own block** before adding TLS:
   ```bash
   curl -sI http://127.0.0.1/ -H 'Host: claims.example.com' | head -3
   sudo nginx -T | grep -nE 'server_name|listen |ssl_certificate '   # every server_name unique
   ```
4. **TLS for the subdomain only** — `sudo certbot --nginx -d claims.example.com` (step 11).
   Certbot edits **only** the block that matches `-d`, adding its `listen 443 ssl` +
   `80 → 443` redirect; the other site's blocks and cert are untouched.
5. **Verify isolation:**
   ```bash
   curl -sI https://claims.example.com/       # Claim Assistant
   curl -sI https://the-other-site.example/   # unchanged
   ```

> **`https://claims.example.com` still shows the other site?** The `Host` isn't matching
> your block. `sudo nginx -T | grep -A15 'server_name claims.example.com'` — the block
> must be loaded and (after certbot) have a `443` section; no other block may also list
> that name. `sudo systemctl reload nginx` (not just `nginx -t`), then retry. A common
> cause is the other site's block being `listen 443 ssl default_server` while yours has
> **no** `443` block yet — every HTTPS request then falls to the other site until certbot
> gives Claim Assistant its own `443` block.

---

## 9 · Nginx — static frontend + API proxy

Full server block in **Appendix C**.

```bash
sudo nano /etc/nginx/sites-available/claim-assistant   # paste Appendix C
sudo ln -sf /etc/nginx/sites-available/claim-assistant /etc/nginx/sites-enabled/
# Dedicated box only — this disables Nginx's stock welcome page. On a shared box, leave
# sites-enabled/default alone (the other site may be served from it).
sudo rm -f /etc/nginx/sites-enabled/default
# let nginx (www-data) traverse into the app dir to read dist/
sudo chmod o+x /opt /opt/claim-assistant /opt/claim-assistant/frontend
sudo nginx -t && sudo systemctl reload nginx
```

- [ ] `server_name` is a hostname you control — a **dedicated subdomain** if the box runs other sites (see the section above), the domain or the server IP if it's dedicated
- [ ] No `default_server` on the Claim Assistant block unless the box is dedicated
- [ ] `nginx -t` passes
- [ ] `curl -s https://claims.example.com/ | grep -o '<title>.*</title>'` returns the app's HTML (static bundle served)
- [ ] `curl -s -o /dev/null -w '%{http_code}\n' https://claims.example.com/api/claims` → **401** (proxy + auth reaching the backend)
- [ ] `location /api/` uses `proxy_pass http://127.0.0.1:8000/;` **with the trailing slash** (strips the `/api` prefix)
- [ ] SPA deep links work — `location / { try_files $uri /index.html; }`

---

## 10 · Firewall

```bash
sudo ufw allow OpenSSH
sudo ufw allow 'Nginx Full'      # 80 + 443
sudo ufw enable
sudo ufw status
```

- [ ] Only **22, 80, 443** are open
- [ ] **5432 is NOT open** — Postgres stays on localhost

---

## 11 · (Optional) HTTPS with Let's Encrypt

Only if you have a real domain pointed at the server.

```bash
sudo apt -y install certbot python3-certbot-nginx
sudo certbot --nginx -d claims.example.com     # use your app's hostname(s)
```

- [ ] `certbot` obtained a cert and edited **only** the block matching `-d` to add `:443` + redirect
- [ ] On a shared box: the other site's `server` blocks and cert are untouched (`sudo nginx -T | grep ssl_certificate`)
- [ ] `sudo certbot renew --dry-run` succeeds (auto-renew timer active)
- [ ] Site loads over `https://` with a valid padlock

---

## 12 · End-to-end smoke test

Open `https://claims.example.com/` (your app's hostname) in a browser:

- [ ] Password gate appears → pick **Admin** (or enter `admin` + `AUTH_PASSWORD`) → lands on the **Claims** list
- [ ] Log out → pick **Processor** → the **Agent** button and the Context / Memory / Sub-agents claim tabs are gone
- [ ] Log out → pick **Customer** → "My Claims" is empty until you file one; other users' claims are not listed
- [ ] **Start Claim** → submit one
  - with fixtures: `fraud` / account `ACC-9001` / transaction `TXN-7001`
  - without: any real account/transaction you loaded
- [ ] The claim's status badge moves `pending → processing → completed` (or `awaiting_input` if the agent asks a question — answer it)
- [ ] Open the claim — every sub-tab populates:
  - **Checks** shows PASS/FAIL/UNKNOWN/BLOCKED per required check
  - **Context** shows the model's message window + iteration counters
  - **Audit Trail** shows `run started → think → tool … → determination`
  - **Sub-agents** shows the Research → Decisioning split
- [ ] **Agent** tab (top bar) → **Tools** lists the catalog, **Graph** renders the Mermaid diagram
- [ ] For an `approve`/`inconclusive` claim, **Check Recovery Eligibility** returns a grounded result
- [ ] `journalctl -u claim-assistant -f` shows the run with **no tracebacks**
- [ ] (If LangSmith configured) the run appears as a trace in the LangSmith project

---

## 13 · Redeploy checklist (each update)

```bash
cd /opt/claim-assistant
sudo -u claimsvc git pull                      # or your deploy user, then fix ownership

# backend deps (only if backend/requirements.txt changed)
backend/.venv/bin/pip install -r backend/requirements.txt

# schema (schema.sql is CREATE TABLE IF NOT EXISTS — it does NOT add columns to
# existing tables; apply any ALTER TABLEs by hand, see specs/tracker.md)
psql "$DATABASE_URL" -f schema.sql

# frontend (only if frontend/ changed)
cd frontend && npm ci && VITE_API_BASE_URL=/api VITE_DEMO_PASSWORD='...' npm run build && cd ..

# corpus (only if docs/files/*.md changed — idempotent)
backend/.venv/bin/python scripts/ingest_policy_corpus.py

sudo systemctl restart claim-assistant
sudo systemctl reload nginx                    # only if dist path or nginx conf changed
```

- [ ] `systemctl status claim-assistant` active after restart
- [ ] Browser hard-refresh shows the new frontend build
- [ ] Re-run the step 12 smoke test on one claim

---

## Appendix A — `.env.local` for production

```ini
# --- LLM (agent + embeddings) ---
LLM_PROVIDER=openai
OPENAI_API_KEY=sk-...
OPENAI_MODEL=gpt-5.6-luna
# OpenRouter / Ollama vars only matter if LLM_PROVIDER is set to one of those.

# --- Vector store (managed) ---
QDRANT_URL=https://xxxx.cloud.qdrant.io:6333
QDRANT_API_KEY=...
QDRANT_COLLECTION=claims-policy-corpus

# --- Tracing (optional; set TRACING=false if you have no key) ---
LANGSMITH_API_KEY=lsv2_pt_...
LANGSMITH_TRACING=true
LANGSMITH_ENDPOINT=https://api.smith.langchain.com
LANGSMITH_PROJECT=claim-assistant

# --- Database (local Postgres from step 2) ---
DATABASE_URL=postgresql://claims_app:CHANGE_ME_STRONG@localhost:5432/claims

# --- App auth (the single shared login password) ---
AUTH_PASSWORD=choose-a-strong-shared-password
```

> `LANGSMITH_ENDPOINT` in the repo's `.env.example` is a placeholder — the real
> host is `https://api.smith.langchain.com`.

---

## Appendix B — `/etc/systemd/system/claim-assistant.service`

```ini
[Unit]
Description=Claim Assistant API (FastAPI/uvicorn)
After=network.target postgresql.service
Wants=postgresql.service

[Service]
Type=exec
User=claimsvc
Group=claimsvc
WorkingDirectory=/opt/claim-assistant
ExecStart=/opt/claim-assistant/backend/.venv/bin/uvicorn backend.main:app \
          --host 127.0.0.1 --port 8000 --workers 1 --timeout-keep-alive 65
Restart=on-failure
RestartSec=3

# hardening (optional but cheap)
NoNewPrivileges=true
PrivateTmp=true
ProtectSystem=full
ProtectHome=true
ReadWritePaths=/opt/claim-assistant

[Install]
WantedBy=multi-user.target
```

- `WorkingDirectory` **must** be the repo root so `backend.main:app` resolves and `.env.local` is found.
- Keep `--workers 1` (see the note at the top).
- No `--reload` in production.

---

## Appendix C — `/etc/nginx/sites-available/claim-assistant`

`server_name` is the one line to get right:

- **Dedicated box:** your domain (`claims.example.com`) or the bare `SERVER_IP`. You may
  add `default_server` to the `listen` lines so IP hits land here too.
- **Shared box (another site on the same VM):** a **dedicated subdomain**
  (`claims.<yourdomain>`) that no other `server` block names, and **no `default_server`** —
  see *Sharing the server with another site* above.

Certbot rewrites `listen 80;` into a `listen 443 ssl` block + an `80 → 443` redirect for
this `server_name`; leave `listen 80;` here and run step 11.

```nginx
server {
    listen 80;
    server_name claims.example.com;   # dedicated subdomain on a shared box; domain or IP if dedicated

    root /opt/claim-assistant/frontend/dist;
    index index.html;

    # SPA — every non-file path serves the app shell
    location / {
        try_files $uri /index.html;
    }

    # API — strip the /api prefix and forward to uvicorn
    location /api/ {
        proxy_pass http://127.0.0.1:8000/;
        proxy_http_version 1.1;
        proxy_set_header Host              $host;
        proxy_set_header X-Real-IP         $remote_addr;
        proxy_set_header X-Forwarded-For   $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_read_timeout 120s;
    }

    # long-cache the hashed asset bundles
    location /assets/ {
        expires 1y;
        add_header Cache-Control "public, immutable";
    }

    client_max_body_size 2m;
}
```

> Same-origin (`/` and `/api` under one host) means the browser makes no
> cross-origin requests, so `backend/main.py`'s dev-only `CORSMiddleware`
> (`allow_origins=["http://localhost:5173"]`) is irrelevant in this setup. If you
> ever split the frontend onto another host, update that list.

---

## Appendix D — Troubleshooting

| Symptom | Likely cause / fix |
|---|---|
| `systemctl status` shows `RuntimeError: AUTH_PASSWORD is not set in .env.local` | `.env.local` missing at `/opt/claim-assistant/.env.local`, unreadable by `claimsvc`, or the var is blank. `sudo -u claimsvc cat /opt/claim-assistant/.env.local`. |
| Startup: `DATABASE_URL is not set` | Same file issue, or `DATABASE_URL=` line empty. |
| **502 Bad Gateway** from Nginx | Backend not listening. `systemctl status claim-assistant`, `curl localhost:8000/`, `journalctl -u claim-assistant -n 100`. |
| Nginx **403 Forbidden** / blank page | `www-data` can't traverse to `dist/`. `sudo chmod o+x /opt /opt/claim-assistant /opt/claim-assistant/frontend` (or move `dist` under `/var/www`). |
| Frontend loads, but every API call is **404** | Built without `VITE_API_BASE_URL=/api`, or Nginx `location /api/` missing / `proxy_pass` has no trailing slash. Rebuild, `nginx -t`, reload. |
| **`https://claims.example.com` serves a *different* site** on a shared box | Nginx virtual-host mismatch — the `Host` matches nothing, or the other site's block, so the request falls to `default_server`. See *Sharing the server with another site*: distinct `server_name` per block, Claim Assistant gets its own `443` block via certbot, no reliance on `default_server`. |
| Login returns **`{"detail":"invalid credentials"}`** (a *401*, but the backend is reachable — `/api/` health is 200) | The bearer token ≠ `AUTH_PASSWORD` *as the running service loaded it*. Check for quotes/trailing space (`sudo -u claimsvc grep AUTH_PASSWORD .env.local \| cat -A`), a `systemd` `Environment=` override (`systemctl show claim-assistant -p Environment`), or an edit made after start (`sudo systemctl restart claim-assistant`). Test directly: `curl -s -o /dev/null -w '%{http_code}\n' -H "Authorization: Bearer <pw>" -H "X-Username: admin" http://127.0.0.1:8000/whoami`. If you use the login screen's quick-pick buttons, `VITE_DEMO_PASSWORD` (baked in at build) must equal `AUTH_PASSWORD` — otherwise type the password. |
| Login returns **`{"detail":"unknown user 'x'"}`** | Username must be `admin`, `processor`, or `customer` (lowercase). |
| Every API call **401** with `{"detail":"Not authenticated"}` | The `Authorization: Bearer …` header isn't arriving — check the frontend was built with `VITE_API_BASE_URL=/api` and Nginx isn't stripping the header. |
| Claim sticks on **processing** forever | Agent hit an exception (OpenAI/Qdrant unreachable from the server, bad key, rate limit). `journalctl -u claim-assistant -f` while submitting; check outbound HTTPS egress. |
| `psql: FATAL: Peer authentication failed` | Connect over TCP with the password: `psql "postgresql://claims_app:...@localhost:5432/claims"`, not `psql -U claims_app`. |
| `permission denied for schema public` when applying `schema.sql` | The DB isn't owned by `claims_app`. `ALTER DATABASE claims OWNER TO claims_app;` then reconnect. |
| `ingest_policy_corpus.py`: `KeyError: 'QDRANT_URL'` | Run it from `/opt/claim-assistant` (it loads `<root>/.env.local`), and make sure the Qdrant vars are set. |
| `generate_synthetic_data` errors on `.env.local` | It calls `load_dotenv(".env.local")` with a **relative** path — run it from the repo root. |
| Mermaid graph tab blank | Non-fatal; the panel auto-falls back to the ASCII rendering. Check the browser console; ensure `frontend/dist` was rebuilt on this deploy. |
