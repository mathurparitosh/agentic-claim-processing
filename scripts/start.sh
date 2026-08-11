#!/usr/bin/env bash
# Start local Postgres, the FastAPI backend, and the Vite frontend for local dev.
# Idempotent: safe to re-run (frees ports 8000/5173 first if something's already there).
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
LOG_DIR="$ROOT_DIR/.run/logs"
PID_DIR="$ROOT_DIR/.run/pids"
mkdir -p "$LOG_DIR" "$PID_DIR"

if [ ! -f "$ROOT_DIR/.env.local" ]; then
  echo "ERROR: .env.local not found. Copy .env.example to .env.local and fill in real values first." >&2
  exit 1
fi

if ! docker info >/dev/null 2>&1; then
  echo "ERROR: Docker daemon isn't running. Start Docker Desktop and re-run this script." >&2
  exit 1
fi

echo "==> Starting local Postgres (docker compose)..."
(cd "$ROOT_DIR" && docker compose up -d postgres)

echo "==> Waiting for Postgres to accept connections..."
for i in $(seq 1 30); do
  if (cd "$ROOT_DIR" && docker compose exec -T postgres pg_isready -U postgres) >/dev/null 2>&1; then
    echo "    Postgres is ready."
    break
  fi
  if [ "$i" -eq 30 ]; then
    echo "ERROR: Postgres did not become ready in time." >&2
    exit 1
  fi
  sleep 1
done

echo "==> Freeing ports 8000 (backend) and 5173 (frontend) if already in use..."
lsof -ti:8000 -sTCP:LISTEN | xargs -r kill 2>/dev/null || true
lsof -ti:5173 -sTCP:LISTEN | xargs -r kill 2>/dev/null || true
sleep 1

echo "==> Starting backend (uvicorn) on :8000..."
(
  cd "$ROOT_DIR"
  # shellcheck disable=SC1091
  source backend/.venv/bin/activate
  nohup uvicorn backend.main:app --port 8000 > "$LOG_DIR/backend.log" 2>&1 &
  echo $! > "$PID_DIR/backend.pid"
)

echo "==> Starting frontend (vite) on :5173..."
(
  cd "$ROOT_DIR/frontend"
  # npm wraps the actual vite process, so this PID is best-effort bookkeeping only --
  # stop.sh frees the port directly rather than relying on it.
  nohup npm run dev > "$LOG_DIR/frontend.log" 2>&1 &
  echo $! > "$PID_DIR/frontend.pid"
)

echo "==> Waiting for backend..."
for i in $(seq 1 30); do
  if curl -sf http://localhost:8000/ >/dev/null; then
    echo "    Backend is up."
    break
  fi
  if [ "$i" -eq 30 ]; then
    echo "ERROR: Backend did not start in time. Check $LOG_DIR/backend.log" >&2
    exit 1
  fi
  sleep 1
done

echo "==> Waiting for frontend..."
for i in $(seq 1 30); do
  if curl -sf http://localhost:5173/ >/dev/null; then
    echo "    Frontend is up."
    break
  fi
  if [ "$i" -eq 30 ]; then
    echo "ERROR: Frontend did not start in time. Check $LOG_DIR/frontend.log" >&2
    exit 1
  fi
  sleep 1
done

echo ""
echo "Claim Assistant is running:"
echo "  Frontend: http://localhost:5173"
echo "  Backend:  http://localhost:8000"
echo ""
echo "Logs: $LOG_DIR/backend.log, $LOG_DIR/frontend.log"
echo "Stop with: scripts/stop.sh"
