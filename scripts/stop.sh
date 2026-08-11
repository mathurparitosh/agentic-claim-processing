#!/usr/bin/env bash
# Stop the backend/frontend dev servers started by scripts/start.sh.
# Local Postgres is left running by default (fast restarts); pass --db to also stop it.
set -uo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PID_DIR="$ROOT_DIR/.run/pids"

stop_by_pidfile() {
  local name="$1" pidfile="$2"
  if [ -f "$pidfile" ]; then
    local pid
    pid=$(cat "$pidfile")
    if kill -0 "$pid" 2>/dev/null; then
      echo "==> Stopping $name (pid $pid)..."
      kill "$pid" 2>/dev/null
    fi
    rm -f "$pidfile"
  fi
}

stop_by_pidfile "backend" "$PID_DIR/backend.pid"
stop_by_pidfile "frontend" "$PID_DIR/frontend.pid"

# Belt and suspenders: `npm run dev`'s PID is just the npm wrapper (npm doesn't forward
# signals to the vite child it spawns), so the pidfile kill above often won't free :5173.
# Freeing the ports directly is what actually guarantees a clean stop.
echo "==> Freeing ports 8000 and 5173..."
lsof -ti:8000 -sTCP:LISTEN | xargs -r kill 2>/dev/null || true
lsof -ti:5173 -sTCP:LISTEN | xargs -r kill 2>/dev/null || true

if [ "${1:-}" = "--db" ]; then
  echo "==> Stopping local Postgres (docker compose stop postgres)..."
  (cd "$ROOT_DIR" && docker compose stop postgres)
else
  echo "==> Leaving local Postgres running (pass --db to also stop it: scripts/stop.sh --db)."
fi

echo "Done."
