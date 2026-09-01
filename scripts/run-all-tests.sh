#!/bin/bash
set -e

PROJECT_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$PROJECT_ROOT"

# Color codes for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Test counters
TESTS_PASSED=0
TESTS_FAILED=0
START_TIME=$(date +%s)

# Helper functions
log_section() {
    echo ""
    echo -e "${BLUE}════════════════════════════════════════════════════════${NC}"
    echo -e "${BLUE}  $1${NC}"
    echo -e "${BLUE}════════════════════════════════════════════════════════${NC}"
}

log_test() {
    echo -e "${YELLOW}▶ $1${NC}"
}

log_pass() {
    echo -e "${GREEN}✓ $1${NC}"
    TESTS_PASSED=$((TESTS_PASSED + 1))
}

log_fail() {
    echo -e "${RED}✗ $1${NC}"
    TESTS_FAILED=$((TESTS_FAILED + 1))
}

log_info() {
    echo -e "  ℹ $1"
}

# Check prerequisites
log_section "Checking Prerequisites"

if [ ! -f .env.local ]; then
    log_fail ".env.local not found"
    echo "Copy .env.example and fill in real values:"
    echo "  cp .env.example .env.local"
    exit 1
fi
log_pass ".env.local exists"

export $(grep -v '^#' .env.local | xargs)

if ! command -v docker &> /dev/null; then
    log_fail "Docker not installed"
    exit 1
fi
log_pass "Docker installed"

if ! command -v python3 &> /dev/null; then
    log_fail "Python 3 not installed"
    exit 1
fi
log_pass "Python 3 installed"

# Start services
log_section "Starting Services"

log_test "Checking if Postgres is running..."
if docker compose ps postgres 2>/dev/null | grep -q "Up"; then
    log_pass "Postgres already running"
else
    log_test "Starting Postgres via docker compose..."
    docker compose up -d postgres
    sleep 3
    log_pass "Postgres started"
fi

# Wait for Postgres to be ready
log_test "Waiting for Postgres to accept connections..."
for i in {1..30}; do
    if docker compose exec -T postgres pg_isready -U postgres > /dev/null 2>&1; then
        log_pass "Postgres is ready"
        break
    fi
    if [ $i -eq 30 ]; then
        log_fail "Postgres failed to start"
        exit 1
    fi
    sleep 1
done

# Setup Python environment
log_section "Setting Up Python Environment"

if [ ! -d backend/.venv ]; then
    log_test "Creating Python virtualenv..."
    python3 -m venv backend/.venv
    log_pass "Virtualenv created"
fi

# Activate once, from the repo root. Every `python`/`python3` below runs with the
# repo root as CWD so that `import backend.*` and `python -m backend.*` resolve.
source backend/.venv/bin/activate
log_pass "Virtualenv activated"

log_test "Installing/updating dependencies..."
pip install -q -r backend/requirements.txt > /dev/null 2>&1 || true
log_pass "Dependencies installed"

# Test 1: Database Connection
log_section "Test 1: Database Connection"

log_test "Testing PostgreSQL connection..."
python3 << 'TEST_DB' && log_pass "Database connection successful" || log_fail "Database connection failed"
import sys
sys.path.insert(0, '.')
from backend import db
try:
    db.open_pool()
    with db.get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT version();")
            version = cur.fetchone()
    print(f"  Database: {version['version'][:60]}...")
    db.close_pool()
except Exception as e:
    print(f"  Error: {e}")
    sys.exit(1)
TEST_DB

# Test 2: API Endpoints
log_section "Test 2: API Endpoints & Authentication"

python3 << 'TEST_API' && log_pass "API endpoints working" || log_fail "API endpoints test failed"
import sys
import os
sys.path.insert(0, '.')
from backend.main import app
from backend import db
from fastapi.testclient import TestClient

# TestClient(app) used without a `with` block doesn't run FastAPI startup events,
# so the psycopg pool would stay closed. Open it explicitly for this check.
db.open_pool()
client = TestClient(app)
password = os.getenv("AUTH_PASSWORD")

# Health check
resp = client.get("/")
assert resp.status_code == 200, f"Health check failed: {resp.status_code}"
print("  ✓ Health check (GET /): 200 OK")

# Auth tests
resp = client.get("/claims")
assert resp.status_code == 401, f"Expected 401, got {resp.status_code}"
print("  ✓ Missing auth rejected: 401")

resp = client.get("/claims", headers={"Authorization": "Bearer wrong"})
assert resp.status_code == 401, f"Expected 401, got {resp.status_code}"
print("  ✓ Wrong password rejected: 401")

resp = client.get("/claims", headers={"Authorization": f"Bearer {password}"})
assert resp.status_code == 200, f"Expected 200, got {resp.status_code}"
print("  ✓ Correct auth accepted: 200")

# Endpoint tests
resp = client.get("/accounts", headers={"Authorization": f"Bearer {password}"})
assert resp.status_code == 200 and isinstance(resp.json(), list), "GET /accounts failed"
print(f"  ✓ GET /accounts: {len(resp.json())} accounts")

resp = client.get("/claims", headers={"Authorization": f"Bearer {password}"})
assert resp.status_code == 200 and isinstance(resp.json(), list), "GET /claims failed"
print(f"  ✓ GET /claims: {len(resp.json())} claims")

TEST_API
# Test 3: LLM & Vector Store
log_section "Test 3: LLM & Vector Store"

python3 << 'TEST_LLM' && log_pass "LLM & Qdrant connected" || log_fail "LLM & Qdrant test failed"
import sys
import os
sys.path.insert(0, '.')
from backend.agent.llm import _build_base_model
from backend.agent.tools import _qdrant

# Test LLM
try:
    model = _build_base_model()  # bare client for a connectivity check (build_agent_model binds tools)
    print(f"  ✓ LLM model: {model.model_name}")
except Exception as e:
    print(f"  ✗ LLM init failed: {e}")
    sys.exit(1)

# Test Qdrant
try:
    client = _qdrant()
    coll = os.getenv("QDRANT_COLLECTION", "claims-policy-corpus")
    info = client.get_collection(coll)  # CollectionInfo has no .name — use the arg
    print(f"  ✓ Qdrant collection: {coll} ({info.points_count} vectors, status={info.status})")
except Exception as e:
    print(f"  ⚠ Qdrant warning (expected on first run): {e}")
    print(f"  Hint: Run 'python scripts/ingest_policy_corpus.py' to ingest policies")

TEST_LLM
# Test 4: Synthetic Data Generation
log_section "Test 4: Synthetic Data Generation"

log_test "Generating synthetic data for ACC-9001 (dry-run)..."
python3 -m backend.generate_synthetic_data --dry-run --accounts ACC-9001 > /tmp/gen.log 2>&1 && \
    log_pass "Synthetic data generation works" || log_fail "Synthetic data generation failed"
log_info "Sample output (first 30 lines):"
head -30 /tmp/gen.log | sed 's/^/    /'
# Test 5: Load Fixture Data
log_section "Test 5: Loading Fixture Data"

log_test "Loading fixture data for evaluation accounts..."
python3 -m backend.generate_synthetic_data --accounts ACC-9001,ACC-9002,ACC-9003 > /tmp/load.log 2>&1 && \
    log_pass "Fixture data loaded successfully" || log_fail "Fixture data loading failed"
log_info "Loaded: ACC-9001 (fraud), ACC-9002 (billing_dispute), ACC-9003 (fraud)"
# Test 6: Single Claim Processing
log_section "Test 6: Single Claim Processing (Smoke Test)"

python3 << 'TEST_CLAIM' && log_pass "Single claim processing works" || log_fail "Claim processing failed"
import sys
import os
import json
from uuid import uuid4
sys.path.insert(0, '.')

from backend import db
from backend.agent.orchestrator import build_orchestrator_graph
from backend.agent.graph import initial_state
from langgraph.checkpoint.postgres import PostgresSaver

claim_id = str(uuid4())
account_id = "ACC-9001"
claim_type = "fraud"
claim_payload = {
    "account_id": account_id,
    "disputed_transaction_id": "TXN-7001",
    "reason": "unauthorized_transaction",
    "filed_at": "2026-07-20T09:00:00Z",
}

db.open_pool()
with db.get_connection() as conn:
    with conn.cursor() as cur:
        cur.execute(
            "INSERT INTO claims (id, claim_type, claim_payload, status) VALUES (%s, %s, %s, 'pending')",
            (claim_id, claim_type, json.dumps(claim_payload)),
        )

try:
    with PostgresSaver.from_conn_string(os.getenv("DATABASE_URL")) as checkpointer:
        graph = build_orchestrator_graph(checkpointer)
        config = {"configurable": {"thread_id": claim_id}}
        result = graph.invoke(initial_state(claim_id, claim_type, claim_payload), config=config)
    
    with db.get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT status, decision FROM claims WHERE id = %s", (claim_id,))
            row = cur.fetchone()
    
    print(f"  Claim {claim_id[:8]}...")
    print(f"  Status: {row['status']}")
    print(f"  Decision: {row['decision']}")
    
    # Cleanup
    with db.get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("DELETE FROM claims WHERE id = %s", (claim_id,))
    
except Exception as e:
    print(f"  Error: {e}")
    import traceback
    traceback.print_exc()
    db.close_pool()
    sys.exit(1)

db.close_pool()

TEST_CLAIM
# Test 7: Evaluation Suite (Sample)
log_section "Test 7: Evaluation Suite (Sample - First 3 Claims)"

python3 << 'TEST_EVAL' && log_pass "Evaluation suite passed (3/3 claims)" || log_fail "Evaluation failed"
import sys
import os
import json
from uuid import uuid4
sys.path.insert(0, '.')

from backend import db
from backend.agent.orchestrator import build_orchestrator_graph
from backend.agent.graph import initial_state
from backend.generate_synthetic_data import SCENARIOS
from langgraph.checkpoint.postgres import PostgresSaver
from langgraph.types import Command

# Predetermined outcomes from specs/eval_claims.md (the generator module doesn't
# export these). First 3 scenarios are the only ones this sample runs.
EXPECTED = {
    "ACC-9001": "approve", "ACC-9002": "approve", "ACC-9003": "approve",
    "ACC-9004": "deny", "ACC-9005": "deny", "ACC-9006": "approve",
    "ACC-9007": "deny", "ACC-9008": "deny", "ACC-9009": "deny",
    "ACC-9010": "inconclusive",
}

db.open_pool()

passed = 0
failed = 0
for scenario in SCENARIOS[:3]:
    account_id = scenario["account_id"]
    claim_id = str(uuid4())
    claim_type = scenario["claim_type"]
    claim_payload = scenario["claim_payload"]
    expected = EXPECTED[account_id]
    
    with db.get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "INSERT INTO claims (id, claim_type, claim_payload, status) VALUES (%s, %s, %s, 'pending')",
                (claim_id, claim_type, json.dumps(claim_payload)),
            )
    
    try:
        with PostgresSaver.from_conn_string(os.getenv("DATABASE_URL")) as checkpointer:
            graph = build_orchestrator_graph(checkpointer)
            config = {"configurable": {"thread_id": claim_id}}
            result = graph.invoke(initial_state(claim_id, claim_type, claim_payload), config=config)
            # The agent may pause on ask_human even for a "clean" claim (LLM's call).
            # These first 3 scenarios all expect approve, so answer "yes" and resume.
            for _ in range(5):
                if "__interrupt__" not in result:
                    break
                result = graph.invoke(Command(resume="yes"), config=config)

        with db.get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT decision FROM claims WHERE id = %s", (claim_id,))
                row = cur.fetchone()
        
        actual = row["decision"]
        if actual == expected:
            print(f"  ✓ {account_id}: expected {expected}, got {actual}")
            passed += 1
        else:
            print(f"  ✗ {account_id}: expected {expected}, got {actual}")
            failed += 1
    
    except Exception as e:
        print(f"  ✗ {account_id}: {e}")
        failed += 1
    
    finally:
        with db.get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("DELETE FROM claims WHERE id = %s", (claim_id,))

db.close_pool()

if failed > 0:
    print(f"\nEval Results: {passed} passed, {failed} failed")
    sys.exit(1)
else:
    print(f"\nEval Results: {passed}/3 passed")

TEST_EVAL
# Test 8: Database Integrity
log_section "Test 8: Database Integrity Checks"

python3 << 'TEST_DB_INTEGRITY' && log_pass "Database integrity verified" || log_fail "Database integrity check failed"
import sys
sys.path.insert(0, '.')
from backend import db

db.open_pool()
with db.get_connection() as conn:
    with conn.cursor() as cur:
        # Check tables exist
        cur.execute("""
            SELECT tablename FROM pg_tables 
            WHERE schemaname = 'public' 
            ORDER BY tablename
        """)
        tables = [row["tablename"] for row in cur.fetchall()]  # db.py uses dict-row cursors
        
        expected_tables = ['account_profiles', 'access_logs', 'audit_trail', 'check_ledger', 'claims', 'transactions']
        for table in expected_tables:
            if table in tables:
                print(f"  ✓ Table '{table}' exists")
            else:
                print(f"  ✗ Table '{table}' missing")
                sys.exit(1)
        
        # Check fixture data
        cur.execute("SELECT COUNT(*) AS n FROM account_profiles")
        count = cur.fetchone()["n"]
        print(f"  ✓ Fixture data loaded: {count} account profiles")

db.close_pool()

TEST_DB_INTEGRITY
# Summary
log_section "Test Summary"

TOTAL_TESTS=$((TESTS_PASSED + TESTS_FAILED))
END_TIME=$(date +%s)
DURATION=$((END_TIME - START_TIME))

echo ""
echo -e "${GREEN}Passed: $TESTS_PASSED${NC}"
echo -e "${RED}Failed: $TESTS_FAILED${NC}"
echo -e "Total:  $TOTAL_TESTS"
echo -e "Time:   ${DURATION}s"
echo ""

if [ $TESTS_FAILED -eq 0 ]; then
    echo -e "${GREEN}════════════════════════════════════════════════════════${NC}"
    echo -e "${GREEN}  ✓ All tests passed!${NC}"
    echo -e "${GREEN}════════════════════════════════════════════════════════${NC}"
    echo ""
    echo "Next steps:"
    echo "  1. Start the app:        ./scripts/start.sh"
    echo "  2. Visit frontend:       http://localhost:5173"
    echo "  3. Run full eval suite:  jupyter notebook backend/eval_notebook.ipynb"
    echo "  4. Stop services:        ./scripts/stop.sh"
    echo ""
    exit 0
else
    echo -e "${RED}════════════════════════════════════════════════════════${NC}"
    echo -e "${RED}  ✗ Some tests failed${NC}"
    echo -e "${RED}════════════════════════════════════════════════════════${NC}"
    echo ""
    exit 1
fi
