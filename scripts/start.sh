#!/bin/bash
set -e

PROJECT_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$PROJECT_ROOT"

echo "=== Claim Assistant — Starting ==="

# Check for .env.local
if [ ! -f .env.local ]; then
    echo "ERROR: .env.local not found. Copy .env.example and fill in real values."
    exit 1
fi

# Load env vars (for logging/validation only; docker compose and uvicorn load their own)
export $(grep -v '^#' .env.local | xargs)

# Start Postgres (if not already running)
echo "Starting Postgres via docker compose..."
docker compose up -d postgres

# Wait for Postgres to be ready
echo "Waiting for Postgres to be ready..."
for i in {1..30}; do
    if docker compose exec -T postgres pg_isready -U postgres > /dev/null 2>&1; then
        echo "Postgres is ready."
        break
    fi
    if [ $i -eq 30 ]; then
        echo "ERROR: Postgres failed to start."
        exit 1
    fi
    sleep 1
done

# Activate backend venv and start uvicorn (background)
echo "Starting FastAPI backend on port 8000..."
if [ ! -d backend/.venv ]; then
    echo "Creating Python virtualenv..."
    python3 -m venv backend/.venv
fi
source backend/.venv/bin/activate
pip install -q -r backend/requirements.txt > /dev/null 2>&1 || true

# Start uvicorn from the repo root so `backend.main:app` resolves as a package path;
# redirect output to a log file.
nohup uvicorn backend.main:app --reload --port 8000 > backend/uvicorn.log 2>&1 &
UVICORN_PID=$!
echo "uvicorn PID: $UVICORN_PID"
sleep 2

# Check if uvicorn started successfully
if ! kill -0 $UVICORN_PID 2>/dev/null; then
    echo "ERROR: uvicorn failed to start. Check backend/uvicorn.log"
    exit 1
fi

# Start frontend (background)
echo "Starting React dev server on port 5173..."
cd frontend
npm install -q > /dev/null 2>&1 || true
nohup npm run dev > vite.log 2>&1 &
VITE_PID=$!
echo "vite dev server PID: $VITE_PID"
sleep 3

cd "$PROJECT_ROOT"

echo ""
echo "=== Claim Assistant is running ==="
echo ""
echo "Frontend:  http://localhost:5173"
echo "Backend:   http://localhost:8000"
echo "Postgres:  localhost:5432"
echo ""
echo "To stop:   ./scripts/stop.sh"
echo "Logs:"
echo "  - Backend:  backend/uvicorn.log"
echo "  - Frontend: frontend/vite.log"
echo ""
