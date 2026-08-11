-- Claim Assistant schema for local Postgres development

CREATE TABLE IF NOT EXISTS claims (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    submitted_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    claim_type TEXT NOT NULL,
    claim_payload JSONB NOT NULL,
    status TEXT NOT NULL DEFAULT 'pending',
    decision TEXT,
    decision_reason TEXT,
    last_updated TIMESTAMPTZ NOT NULL DEFAULT now()
);

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
