-- Claim Assistant schema for local Postgres development

CREATE TABLE IF NOT EXISTS claims (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    submitted_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    claim_type TEXT NOT NULL,
    claim_payload JSONB NOT NULL,
    status TEXT NOT NULL DEFAULT 'pending',
    decision TEXT,
    decision_reason TEXT,
    -- Set while status = 'awaiting_input': {"question": ..., "check_name": ...} from
    -- the ask_human tool's interrupt payload (backend/agent/tools.py). Cleared on answer.
    pending_question JSONB,
    -- Username of the user who submitted the claim (backend/auth.py: admin | processor
    -- | customer). Used to scope a customer to only the claims they filed. NULL for
    -- rows created before multi-user auth existed.
    filed_by TEXT,
    last_updated TIMESTAMPTZ NOT NULL DEFAULT now()
);
-- Retrofit for databases created before `filed_by` was added (CREATE TABLE above
-- won't add columns to an existing table).
ALTER TABLE claims ADD COLUMN IF NOT EXISTS filed_by TEXT;

CREATE TABLE IF NOT EXISTS check_ledger (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    claim_id UUID NOT NULL REFERENCES claims(id) ON DELETE CASCADE,
    check_name TEXT NOT NULL,
    check_status TEXT NOT NULL,
    detail JSONB,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE(claim_id, check_name)
);

CREATE TABLE IF NOT EXISTS audit_trail (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    claim_id UUID NOT NULL REFERENCES claims(id) ON DELETE CASCADE,
    event_type TEXT NOT NULL,
    event_subtype TEXT,
    payload JSONB,
    source TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS episodic_facts (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    entity_id TEXT NOT NULL,
    entity_type TEXT NOT NULL,
    fact_key TEXT NOT NULL,
    fact_value JSONB NOT NULL,
    provenance JSONB,
    inserted_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE(entity_id, entity_type, fact_key)
);

CREATE INDEX IF NOT EXISTS idx_check_ledger_claim_id ON check_ledger(claim_id);
CREATE INDEX IF NOT EXISTS idx_audit_trail_claim_id ON audit_trail(claim_id);
CREATE INDEX IF NOT EXISTS idx_episodic_facts_entity ON episodic_facts(entity_id, entity_type);

-- Synthetic research-source fixtures (Phase 4). Backs the Grounding tools; data is
-- LLM-generated, not real customer data. See specs/technical.md §4.

CREATE TABLE IF NOT EXISTS transactions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    account_id TEXT NOT NULL,
    transaction_ref TEXT NOT NULL,
    occurred_at TIMESTAMPTZ NOT NULL,
    amount NUMERIC(12, 2) NOT NULL,
    merchant TEXT,
    location TEXT,
    channel TEXT,
    status TEXT NOT NULL DEFAULT 'posted',
    raw JSONB,
    UNIQUE(account_id, transaction_ref)
);

CREATE TABLE IF NOT EXISTS access_logs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    account_id TEXT NOT NULL,
    occurred_at TIMESTAMPTZ NOT NULL,
    event_type TEXT NOT NULL,
    device_id TEXT,
    ip_address TEXT,
    location TEXT,
    risk_flag BOOLEAN NOT NULL DEFAULT false,
    raw JSONB
);

CREATE TABLE IF NOT EXISTS account_profiles (
    account_id TEXT PRIMARY KEY,
    member_name TEXT,
    opened_at TIMESTAMPTZ,
    standing TEXT NOT NULL DEFAULT 'good',
    fraud_red_flags JSONB NOT NULL DEFAULT '[]'::jsonb,
    dispute_history_count INT NOT NULL DEFAULT 0,
    raw JSONB
);

CREATE INDEX IF NOT EXISTS idx_transactions_account_id ON transactions(account_id);
CREATE INDEX IF NOT EXISTS idx_access_logs_account_id ON access_logs(account_id);
