"""Quick API tests using FastAPI TestClient (no external services required)."""
import json
import os
from uuid import uuid4

import pytest
from dotenv import load_dotenv
from fastapi.testclient import TestClient

load_dotenv(".env.local")

from backend.main import app

PASSWORD = os.getenv("AUTH_PASSWORD")


@pytest.fixture
def client():
    """FastAPI TestClient."""
    return TestClient(app)


@pytest.fixture
def auth_headers():
    """Standard auth header."""
    return {"Authorization": f"Bearer {PASSWORD}"}


class TestAuth:
    def test_health_no_auth(self, client):
        """Health check doesn't require auth."""
        resp = client.get("/")
        assert resp.status_code == 200

    def test_no_auth_header(self, client):
        """Missing auth returns 401."""
        resp = client.get("/claims")
        assert resp.status_code == 401

    def test_wrong_password(self, client):
        """Wrong password returns 401."""
        resp = client.get("/claims", headers={"Authorization": "Bearer wrong"})
        assert resp.status_code == 401

    def test_correct_auth(self, client, auth_headers):
        """Correct password accepts request."""
        resp = client.get("/claims", headers=auth_headers)
        assert resp.status_code == 200


class TestListEndpoints:
    def test_list_accounts(self, client, auth_headers):
        """GET /accounts returns list of accounts."""
        resp = client.get("/accounts", headers=auth_headers)
        assert resp.status_code == 200
        assert isinstance(resp.json(), list)

    def test_list_claims(self, client, auth_headers):
        """GET /claims returns list of claims."""
        resp = client.get("/claims", headers=auth_headers)
        assert resp.status_code == 200
        assert isinstance(resp.json(), list)

    def test_account_transactions(self, client, auth_headers):
        """GET /accounts/{id}/transactions returns transactions for that account."""
        # First get an account
        accounts_resp = client.get("/accounts", headers=auth_headers)
        accounts = accounts_resp.json()
        if accounts:
            account_id = accounts[0]["id"]
            resp = client.get(f"/accounts/{account_id}/transactions", headers=auth_headers)
            assert resp.status_code == 200
            assert isinstance(resp.json(), list)


class TestClaimLifecycle:
    def test_submit_claim(self, client, auth_headers):
        """POST /claims creates a claim."""
        payload = {
            "claim_type": "fraud",
            "claim_payload": {
                "account_id": "ACC-9001",
                "disputed_transaction_id": "TXN-7001",
                "reason": "unauthorized_transaction",
                "filed_at": "2026-07-20T09:00:00Z",
            },
        }
        resp = client.post("/claims", json=payload, headers=auth_headers)
        assert resp.status_code == 200
        data = resp.json()
        assert "claim_id" in data
        assert data["status"] == "pending"
        return data["claim_id"]

    def test_get_claim(self, client, auth_headers):
        """GET /claims/{id} retrieves a claim."""
        # Submit a claim
        payload = {
            "claim_type": "fraud",
            "claim_payload": {
                "account_id": "ACC-9001",
                "disputed_transaction_id": "TXN-7001",
                "reason": "unauthorized_transaction",
                "filed_at": "2026-07-20T09:00:00Z",
            },
        }
        submit_resp = client.post("/claims", json=payload, headers=auth_headers)
        claim_id = submit_resp.json()["claim_id"]

        # Get the claim
        resp = client.get(f"/claims/{claim_id}", headers=auth_headers)
        assert resp.status_code == 200
        data = resp.json()
        assert data["id"] == claim_id
        assert data["claim_type"] == "fraud"

    def test_invalid_claim_id(self, client, auth_headers):
        """GET /claims/{id} with invalid id returns 404."""
        resp = client.get(f"/claims/{uuid4()}", headers=auth_headers)
        assert resp.status_code == 404


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
