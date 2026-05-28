-- Migration 006: Classification Society Type Approvals
-- Part of KB Enhancement Phase 2: Schema Improvements
--
-- This migration adds:
-- 1. Classification society reference table
-- 2. Engine type approvals table (certifications by class society)
-- 3. Support for Lloyd's, DNV, BV, ABS, ClassNK, etc.

-- ============================================================================
-- IDEMPOTENT: Check if migration has already been applied
-- ============================================================================
DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM information_schema.tables
               WHERE table_name = 'kb_classification_societies') THEN
        RAISE NOTICE 'Migration 006 already applied - skipping';
        RETURN;
    END IF;

    -- ========================================================================
    -- Classification Societies Reference Table
    -- ========================================================================
    CREATE TABLE kb_classification_societies (
        id UUID PRIMARY KEY DEFAULT gen_random_uuid(),

        -- Society code (e.g., 'LR', 'DNV', 'BV')
        code TEXT NOT NULL UNIQUE,

        -- Full name
        name TEXT NOT NULL,

        -- Headquarters country
        country TEXT NOT NULL,

        -- Is IACS member (International Association of Classification Societies)
        is_iacs_member BOOLEAN NOT NULL DEFAULT FALSE,

        -- Common notations this society uses
        common_notations TEXT[],

        -- Description
        description TEXT,

        -- Timestamps
        created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
        updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
    );

    RAISE NOTICE 'Created kb_classification_societies table';

    -- ========================================================================
    -- Insert Major Classification Societies
    -- ========================================================================
    INSERT INTO kb_classification_societies (code, name, country, is_iacs_member, common_notations, description)
    VALUES
        ('LR', 'Lloyd''s Register', 'United Kingdom', TRUE,
         ARRAY['100A1', 'LMC', 'UMS', 'ECO'],
         'Founded 1760, world''s oldest classification society. Strong in tankers, offshore.'),

        ('DNV', 'DNV (Det Norske Veritas)', 'Norway', TRUE,
         ARRAY['1A1', 'CLEAN', 'COMFORT', 'ICE'],
         'Merged with GL in 2013. Leading in offshore, cruise, ferries.'),

        ('BV', 'Bureau Veritas', 'France', TRUE,
         ARRAY['I HULL', 'MACH', 'AUT-UMS', 'GREEN'],
         'Strong in container ships, tankers. Growing in offshore.'),

        ('ABS', 'American Bureau of Shipping', 'United States', TRUE,
         ARRAY['A1', 'AMS', 'ACCU', 'CPS'],
         'Dominant in US market, offshore, LNG carriers.'),

        ('NK', 'ClassNK (Nippon Kaiji Kyokai)', 'Japan', TRUE,
         ARRAY['NS', 'MNS', 'M0', 'IWS'],
         'World''s largest by tonnage. Strong in bulk carriers, tankers.'),

        ('RINA', 'RINA (Registro Italiano Navale)', 'Italy', TRUE,
         ARRAY['C', 'M', 'A', 'STAR'],
         'Strong in cruise ships, ferries, yachts. Mediterranean focus.'),

        ('CCS', 'China Classification Society', 'China', TRUE,
         ARRAY['CSA', 'CSM', 'VeriSTAR'],
         'Fastest growing. Dominant in Chinese shipbuilding.'),

        ('KR', 'Korean Register', 'South Korea', TRUE,
         ARRAY['KRS', 'KR1', 'MLC', 'AUT'],
         'Strong in Korean shipyards. Growing international presence.'),

        ('RS', 'Russian Maritime Register', 'Russia', TRUE,
         ARRAY['KM', 'Ice', 'AUT1', 'ECO'],
         'Dominant in Russian Arctic shipping and icebreakers.'),

        ('IRS', 'Indian Register of Shipping', 'India', TRUE,
         ARRAY['100A1', 'LMC', 'DP', 'CLEAN'],
         'Growing with Indian shipbuilding industry.');

    RAISE NOTICE 'Inserted 10 classification societies';

    -- ========================================================================
    -- Engine Type Approvals Table
    -- Links engine ratings to classification society certifications
    -- ========================================================================
    CREATE TABLE kb_engine_type_approvals (
        id UUID PRIMARY KEY DEFAULT gen_random_uuid(),

        -- Foreign keys
        engine_rating_id VARCHAR(36) NOT NULL REFERENCES kb_engine_ratings(id) ON DELETE CASCADE,
        classification_society_id UUID NOT NULL REFERENCES kb_classification_societies(id) ON DELETE CASCADE,

        -- Approval certificate number
        approval_certificate TEXT,

        -- Notations granted (e.g., ['100A1', 'LMC', 'UMS'])
        notations TEXT[],

        -- Approval status
        approval_status TEXT NOT NULL DEFAULT 'approved' CHECK (approval_status IN (
            'approved',      -- Currently valid
            'pending',       -- Application submitted
            'expired',       -- Was valid, now expired
            'withdrawn'      -- Withdrawn by manufacturer or society
        )),

        -- Valid dates
        valid_from DATE,
        valid_until DATE,

        -- Notes
        notes TEXT,

        -- Timestamps
        created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
        updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),

        -- Each rating can have multiple approvals from same society (different notations)
        UNIQUE(engine_rating_id, classification_society_id, approval_certificate)
    );

    -- Indexes for fast lookups
    CREATE INDEX idx_type_approvals_rating_id
        ON kb_engine_type_approvals(engine_rating_id);

    CREATE INDEX idx_type_approvals_society_id
        ON kb_engine_type_approvals(classification_society_id);

    CREATE INDEX idx_type_approvals_status
        ON kb_engine_type_approvals(approval_status)
        WHERE approval_status = 'approved';

    RAISE NOTICE 'Created kb_engine_type_approvals table';

    -- ========================================================================
    -- Triggers for updated_at
    -- ========================================================================
    CREATE TRIGGER trg_classification_societies_updated_at
        BEFORE UPDATE ON kb_classification_societies
        FOR EACH ROW EXECUTE FUNCTION update_kb_timestamp();

    CREATE TRIGGER trg_type_approvals_updated_at
        BEFORE UPDATE ON kb_engine_type_approvals
        FOR EACH ROW EXECUTE FUNCTION update_kb_timestamp();

    RAISE NOTICE 'Created update triggers';

    RAISE NOTICE 'Migration 006_classification_society.sql completed successfully';
END $$;

-- ============================================================================
-- Comments
-- ============================================================================
COMMENT ON TABLE kb_classification_societies IS
    'Reference table of marine classification societies (Lloyd''s, DNV, ABS, etc.)';

COMMENT ON TABLE kb_engine_type_approvals IS
    'Engine type approvals/certifications by classification societies';

COMMENT ON COLUMN kb_engine_type_approvals.notations IS
    'Classification notations granted (e.g., 100A1, LMC, UMS for Lloyd''s)';

COMMENT ON COLUMN kb_engine_type_approvals.approval_status IS
    'Current status: approved, pending, expired, or withdrawn';
