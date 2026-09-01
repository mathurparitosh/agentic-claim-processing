#!/bin/bash
set -e

PROJECT_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$PROJECT_ROOT"

echo "=== Claim Assistant — Stopping ==="

# Kill uvicorn
if [ -f backend/uvicorn.log ]; then
    UVICORN_PID=$(pgrep -f "uvicorn backend.main:app" || true)
    if [ -n "$UVICORN_PID" ]; then
        echo "Stopping uvicorn (PID: $UVICORN_PID)..."
        kill $UVICORN_PID 2>/dev/null || true
        sleep 1
    fi
fi

# Kill vite dev server
VITE_PID=$(pgrep -f "npm run dev" | grep -v grep || true)
if [ -n "$VITE_PID" ]; then
    echo "Stopping Vite dev server (PID: $VITE_PID)..."
    kill $VITE_PID 2>/dev/null || true
    sleep 1
fi

# Stop Postgres (optionally)
echo "Stopping Postgres..."
docker compose down

echo ""
echo "=== Claim Assistant stopped ==="
