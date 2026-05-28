-- RRPS Lead-to-Cash PostgreSQL Schema
-- Migration: 001_initial_schema
--
-- Tables:
--   transactions  — Tracks each order/correlation lifecycle
--   events        — APPEND-ONLY event log per transaction
--   field_provenance — APPEND-ONLY field derivation audit trail
--
-- Conventions:
--   - All timestamps are TIMESTAMPTZ (UTC)
--   - correlation_id is UUID, used as primary key in transactions
--   - events and field_provenance are APPEND-ONLY: no UPDATE or DELETE
--   - JSONB columns store flexible payloads (idoc_snapshot, event data)

BEGIN;

-- ==========================================================================
-- transactions: one row per correlation lifecycle
-- ==========================================================================
CREATE TABLE IF NOT EXISTS transactions (
    correlation_id  UUID            PRIMARY KEY,
    vbeln           VARCHAR(10)     NULL,           -- SAP sales document number
    idoc_snapshot   JSONB           NULL,           -- Latest IDoc payload snapshot
    status          VARCHAR(20)     NOT NULL DEFAULT 'draft',
    created_at      TIMESTAMPTZ     NOT NULL DEFAULT NOW(),
    updated_at      TIMESTAMPTZ     NULL,
    user_id         VARCHAR(100)    NULL
);

-- Index: lookup by SAP order number
CREATE INDEX IF NOT EXISTS idx_transactions_vbeln
    ON transactions (vbeln)
    WHERE vbeln IS NOT NULL;

-- Index: filter by status
CREATE INDEX IF NOT EXISTS idx_transactions_status
    ON transactions (status);


-- ==========================================================================
-- events: APPEND-ONLY event log (no UPDATE, no DELETE)
-- ==========================================================================
CREATE TABLE IF NOT EXISTS events (
    id              SERIAL          PRIMARY KEY,
    transaction_id  UUID            NOT NULL
                                    REFERENCES transactions (correlation_id)
                                    ON DELETE CASCADE,
    event_type      VARCHAR(50)     NOT NULL
                                    CHECK (event_type IN (
                                        'CREATED',
                                        'VALIDATED',
                                        'ENRICHED',
                                        'CPI_SENT',
                                        'CPI_RESPONSE',
                                        'SAP_POSTED',
                                        'SAP_ERROR',
                                        'STATUS_CHANGE',
                                        'KYP_CHECK',
                                        'CREDIT_CHECK',
                                        'FIELD_OVERRIDE',
                                        'APPROVAL',
                                        'REJECTION',
                                        'COMMENT'
                                    )),
    data            JSONB           NOT NULL DEFAULT '{}',
    timestamp       TIMESTAMPTZ     NOT NULL DEFAULT NOW()
);

-- Index: lookup events by transaction
CREATE INDEX IF NOT EXISTS idx_events_transaction_id
    ON events (transaction_id);

-- Composite index: filter events by type within a time range
CREATE INDEX IF NOT EXISTS idx_events_type_timestamp
    ON events (event_type, timestamp);


-- ==========================================================================
-- field_provenance: APPEND-ONLY field derivation audit trail
-- ==========================================================================
CREATE TABLE IF NOT EXISTS field_provenance (
    id              SERIAL          PRIMARY KEY,
    transaction_id  UUID            NOT NULL
                                    REFERENCES transactions (correlation_id)
                                    ON DELETE CASCADE,
    field_name      VARCHAR(200)    NOT NULL,
    source          VARCHAR(20)     NOT NULL
                                    CHECK (source IN (
                                        'SAP_CPI',
                                        'ARAVO',
                                        'IPAS',
                                        'USER',
                                        'SYSTEM'
                                    )),
    confidence      DECIMAL(3,2)    NOT NULL
                                    CHECK (confidence >= 0.0 AND confidence <= 1.0),
    original_value  TEXT            NULL,
    final_value     TEXT            NULL,
    rule_id         VARCHAR(100)    NULL,
    created_at      TIMESTAMPTZ     NOT NULL DEFAULT NOW()
);

-- Index: lookup provenance by transaction
CREATE INDEX IF NOT EXISTS idx_field_provenance_transaction_id
    ON field_provenance (transaction_id);

-- Index: lookup provenance by field name
CREATE INDEX IF NOT EXISTS idx_field_provenance_field_name
    ON field_provenance (field_name);


-- ==========================================================================
-- Revoke UPDATE/DELETE on append-only tables via trigger (defense-in-depth)
-- ==========================================================================

-- Trigger function: block UPDATE and DELETE on append-only tables
CREATE OR REPLACE FUNCTION block_modify()
RETURNS TRIGGER AS $$
BEGIN
    RAISE EXCEPTION 'Table % is APPEND-ONLY: % operations are not allowed',
        TG_TABLE_NAME, TG_OP;
    RETURN NULL;
END;
$$ LANGUAGE plpgsql;

-- Apply to events
DROP TRIGGER IF EXISTS trg_events_no_update ON events;
CREATE TRIGGER trg_events_no_update
    BEFORE UPDATE OR DELETE ON events
    FOR EACH ROW EXECUTE FUNCTION block_modify();

-- Apply to field_provenance
DROP TRIGGER IF EXISTS trg_field_provenance_no_update ON field_provenance;
CREATE TRIGGER trg_field_provenance_no_update
    BEFORE UPDATE OR DELETE ON field_provenance
    FOR EACH ROW EXECUTE FUNCTION block_modify();


-- ==========================================================================
-- Auto-update updated_at on transactions
-- ==========================================================================

CREATE OR REPLACE FUNCTION update_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trg_transactions_updated_at ON transactions;
CREATE TRIGGER trg_transactions_updated_at
    BEFORE UPDATE ON transactions
    FOR EACH ROW EXECUTE FUNCTION update_updated_at();

COMMIT;
