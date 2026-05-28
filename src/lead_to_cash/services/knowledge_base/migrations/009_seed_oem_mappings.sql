-- Migration 009: Seed OEM Duty Class Mappings
-- Part of Harmonized Marine Engine Duty Classification System
--
-- This migration seeds the kb_oem_duty_mappings table with manufacturer-specific
-- duty rating codes and their mapping to ISO 8528-1:2018 aligned harmonized classes.
--
-- Source Verification Levels:
-- - primary_oem: Direct from OEM official documentation
-- - secondary_dist: From authorized distributor
-- - aggregator: From industry aggregator (needs verification)
--
-- Reference: ISO 8528-1:2018(E) Third Edition
-- License: Integrum Pte Ltd / SS Foo - Order OP-1014241

-- ============================================================================
-- IDEMPOTENT: Check if data has already been seeded
-- ============================================================================
DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM kb_oem_duty_mappings WHERE manufacturer = 'MTU') THEN
        RAISE NOTICE 'Migration 009 already applied - skipping';
        RETURN;
    END IF;

    -- ========================================================================
    -- MTU (Rolls-Royce Power Systems) - Application Groups
    -- Source: MTU Marine & Offshore Solution Guide Edition 2/22
    -- Verification: SECONDARY_DIST (distributor copy from penskeanz.com)
    -- ========================================================================
    INSERT INTO kb_oem_duty_mappings (
        manufacturer, oem_rating_code, oem_rating_name, harmonized_duty_class,
        iso_equivalent, load_factor_min_pct, load_factor_max_pct,
        annual_hours_min, annual_hours_max, full_power_hours_per_cycle, cycle_hours,
        source_verification, source_document, source_url, source_date, notes
    ) VALUES
        -- 1A: Continuous operation (unrestricted)
        ('MTU', 'M60', '1A - Continuous', 'CON',
         'COP', 70.00, 90.00, NULL, NULL, NULL, NULL,
         'secondary_dist', 'MTU Solution Guide Edition 2/22', 'https://penskeanz.com/wp-content/uploads/2023/07/16120032_MTU_SolutionGuide_Marine_00.pdf', '2022-01-01',
         'Unrestricted continuous operation. 70-90% load factor.'),

        ('MTU', 'M63', '1A - Continuous', 'CON',
         'COP', 70.00, 90.00, NULL, NULL, NULL, NULL,
         'secondary_dist', 'MTU Solution Guide Edition 2/22', 'https://penskeanz.com/wp-content/uploads/2023/07/16120032_MTU_SolutionGuide_Marine_00.pdf', '2022-01-01',
         'Unrestricted continuous operation. Cargo ships, tankers, tugboats.'),

        -- 1B: High load factors (heavy duty)
        ('MTU', 'M71', '1B - High Load', 'HVY',
         'PRP (high)', 60.00, 80.00, NULL, 5000, 10.0, 12,
         'secondary_dist', 'MTU Solution Guide Edition 2/22', 'https://penskeanz.com/wp-content/uploads/2023/07/16120032_MTU_SolutionGuide_Marine_00.pdf', '2022-01-01',
         '1B rating. High load factors, 5000 hrs/yr max. Fast ferries, workboats.'),

        ('MTU', 'M72', '1B - High Load', 'HVY',
         'PRP (high)', 60.00, 80.00, NULL, 5000, 10.0, 12,
         'secondary_dist', 'MTU Solution Guide Edition 2/22', 'https://penskeanz.com/wp-content/uploads/2023/07/16120032_MTU_SolutionGuide_Marine_00.pdf', '2022-01-01',
         '1B rating. High load factors. Fast vessels with high annual usage.'),

        ('MTU', 'M73', '1B - High Load', 'HVY',
         'PRP (high)', 60.00, 80.00, NULL, 5000, 10.0, 12,
         'secondary_dist', 'MTU Solution Guide Edition 2/22', 'https://penskeanz.com/wp-content/uploads/2023/07/16120032_MTU_SolutionGuide_Marine_00.pdf', '2022-01-01',
         '1B rating. High load factors. Higher output variant.'),

        -- 1D: Intermittent operation (medium duty)
        ('MTU', 'M91', '1D - Intermittent', 'MED',
         'PRP (mid)', 40.00, 60.00, NULL, 3000, 6.0, 12,
         'secondary_dist', 'MTU Solution Guide Edition 2/22', 'https://penskeanz.com/wp-content/uploads/2023/07/16120032_MTU_SolutionGuide_Marine_00.pdf', '2022-01-01',
         '1D rating. Intermittent operation, medium duty cycles.'),

        -- 1DS: Low load factors (light duty - high peak power, low hours)
        ('MTU', 'M93', '1DS - Low Load', 'LGT',
         'LTP', 20.00, 50.00, NULL, 1500, 2.0, 8,
         'secondary_dist', 'MTU Solution Guide Edition 2/22', 'https://penskeanz.com/wp-content/uploads/2023/07/16120032_MTU_SolutionGuide_Marine_00.pdf', '2022-01-01',
         '1DS rating. Low load factor, high peak power. Yachts, fast patrol.'),

        ('MTU', 'M96', '1DS - Low Load', 'LGT',
         'LTP', 20.00, 50.00, NULL, 1500, 2.0, 8,
         'secondary_dist', 'MTU Solution Guide Edition 2/22', 'https://penskeanz.com/wp-content/uploads/2023/07/16120032_MTU_SolutionGuide_Marine_00.pdf', '2022-01-01',
         '1DS rating. Higher output variant. Fast yachts, naval vessels.'),

        -- 1D Gas Mode
        ('MTU', 'M05-N', '1D - Gas Mode', 'MED',
         'PRP (mid)', 40.00, 60.00, NULL, 3000, 6.0, 12,
         'secondary_dist', 'MTU Solution Guide Edition 2/22', 'https://penskeanz.com/wp-content/uploads/2023/07/16120032_MTU_SolutionGuide_Marine_00.pdf', '2022-01-01',
         'Gas engine variant. Natural gas dual-fuel operation.');

    RAISE NOTICE 'Inserted MTU duty mappings (9 ratings)';

    -- ========================================================================
    -- Cummins Marine Ratings
    -- Source: Cummins Marine Ratings and Definitions (cummins.com/engines/marine-ratings)
    -- Verification: PRIMARY_OEM (official OEM website)
    -- ========================================================================
    INSERT INTO kb_oem_duty_mappings (
        manufacturer, oem_rating_code, oem_rating_name, harmonized_duty_class,
        iso_equivalent, load_factor_min_pct, load_factor_max_pct,
        annual_hours_min, annual_hours_max, full_power_hours_per_cycle, cycle_hours,
        source_verification, source_document, source_url, source_date, notes
    ) VALUES
        ('Cummins', 'CON', 'Continuous', 'CON',
         'COP', 70.00, 90.00, NULL, NULL, NULL, NULL,
         'primary_oem', 'Cummins Marine Ratings', 'https://www.cummins.com/engines/marine-ratings', '2025-01-01',
         'Unlimited operating hours. Cargo ships, tugs, dredgers.'),

        ('Cummins', 'HD', 'Heavy Duty', 'HVY',
         'PRP (high)', 60.00, 75.00, NULL, NULL, 8.0, 10,
         'primary_oem', 'Cummins Marine Ratings', 'https://www.cummins.com/engines/marine-ratings', '2025-01-01',
         'High load commercial. Ferries, fishing trawlers, OSVs.'),

        ('Cummins', 'MCD', 'Medium Continuous Duty', 'MED',
         'PRP (mid)', 40.00, 60.00, 3000, 5000, 6.0, 12,
         'primary_oem', 'Cummins Marine Ratings', 'https://www.cummins.com/engines/marine-ratings', '2025-01-01',
         'Medium commercial duty. Harbor tugs, supply vessels.'),

        ('Cummins', 'LD', 'Light Duty', 'LGT',
         'LTP', 10.00, 30.00, 1000, 3000, 1.0, 8,
         'primary_oem', 'Cummins Marine Ratings', 'https://www.cummins.com/engines/marine-ratings', '2025-01-01',
         'Light commercial. Patrol boats, pilot boats.'),

        ('Cummins', 'INT', 'Intermittent', 'INT',
         'ESP', 20.00, 40.00, 250, 1000, 2.0, 8,
         'primary_oem', 'Cummins Marine Ratings', 'https://www.cummins.com/engines/marine-ratings', '2025-01-01',
         'Intermittent commercial. Standby, peak shaving.'),

        ('Cummins', 'PLS', 'Pleasure', 'PLS',
         'Below ESP', 0.00, 30.00, 250, 1000, 1.0, 8,
         'primary_oem', 'Cummins Marine Ratings', 'https://www.cummins.com/engines/marine-ratings', '2025-01-01',
         'Pleasure craft. Yachts, sport fishing.');

    RAISE NOTICE 'Inserted Cummins duty mappings (6 ratings)';

    -- ========================================================================
    -- Caterpillar Marine Ratings
    -- Source: Cat Marine Engine Selection Guide (teknoxgroup.com - distributor)
    -- Verification: SECONDARY_DIST (distributor document)
    -- ========================================================================
    INSERT INTO kb_oem_duty_mappings (
        manufacturer, oem_rating_code, oem_rating_name, harmonized_duty_class,
        iso_equivalent, load_factor_min_pct, load_factor_max_pct,
        annual_hours_min, annual_hours_max, full_power_hours_per_cycle, cycle_hours,
        source_verification, source_document, source_url, source_date, notes
    ) VALUES
        ('Caterpillar', 'A', 'Rating A - Continuous', 'CON',
         'COP', 80.00, 100.00, NULL, NULL, NULL, NULL,
         'secondary_dist', 'Cat Marine Selection Guide', 'https://www.teknoxgroup.com/documents/caterpillar-marine-selection-guide.pdf', '2023-01-01',
         'Continuous duty. Cargo, tankers, tugboats.'),

        ('Caterpillar', 'B', 'Rating B - Heavy Duty', 'HVY',
         'PRP (high)', 60.00, 80.00, 3000, 5000, 8.0, 10,
         'secondary_dist', 'Cat Marine Selection Guide', 'https://www.teknoxgroup.com/documents/caterpillar-marine-selection-guide.pdf', '2023-01-01',
         'Heavy commercial. Ferries, fishing.'),

        ('Caterpillar', 'C', 'Rating C - Medium Duty', 'MED',
         'PRP (mid)', 40.00, 60.00, 2000, 4000, 6.0, 12,
         'secondary_dist', 'Cat Marine Selection Guide', 'https://www.teknoxgroup.com/documents/caterpillar-marine-selection-guide.pdf', '2023-01-01',
         'Medium commercial. OSVs, research vessels.'),

        ('Caterpillar', 'D', 'Rating D - Light Duty', 'LGT',
         'LTP', 20.00, 50.00, 1000, 3000, 2.0, 8,
         'secondary_dist', 'Cat Marine Selection Guide', 'https://www.teknoxgroup.com/documents/caterpillar-marine-selection-guide.pdf', '2023-01-01',
         'Light commercial. Patrol, pilot boats.'),

        ('Caterpillar', 'E', 'Rating E - Pleasure', 'PLS',
         'Below ESP', 0.00, 30.00, 0, 1000, 1.0, 8,
         'secondary_dist', 'Cat Marine Selection Guide', 'https://www.teknoxgroup.com/documents/caterpillar-marine-selection-guide.pdf', '2023-01-01',
         'Pleasure craft. Yachts.');

    RAISE NOTICE 'Inserted Caterpillar duty mappings (5 ratings)';

    -- ========================================================================
    -- MAN Engines Ratings (LE-code system)
    -- Source: IMP Corporation blog (impcorporation.com)
    -- Verification: AGGREGATOR (industry aggregator - needs OEM verification)
    -- ========================================================================
    INSERT INTO kb_oem_duty_mappings (
        manufacturer, oem_rating_code, oem_rating_name, harmonized_duty_class,
        iso_equivalent, load_factor_min_pct, load_factor_max_pct,
        annual_hours_min, annual_hours_max, full_power_hours_per_cycle, cycle_hours,
        source_verification, source_document, source_url, source_date, notes
    ) VALUES
        ('MAN', 'LE42x', 'Heavy Duty (≤1800 RPM)', 'HVY',
         'PRP (high)', 60.00, 80.00, NULL, NULL, 10.0, 12,
         'aggregator', 'IMP Corporation Marine Duty Ratings', 'https://www.impcorporation.com/blog/marine-engine-duty-ratings', '2024-01-01',
         'Heavy duty rating. Lower RPM = higher duty cycle. Continuous commercial.'),

        ('MAN', 'LE43x', 'Medium Duty (~2100 RPM)', 'MED',
         'PRP (mid)', 40.00, 60.00, NULL, 3000, 6.0, 12,
         'aggregator', 'IMP Corporation Marine Duty Ratings', 'https://www.impcorporation.com/blog/marine-engine-duty-ratings', '2024-01-01',
         'Medium duty rating. Mid-range RPM. Ferries, workboats.'),

        ('MAN', 'LE46x', 'Light Duty (~2300 RPM)', 'LGT',
         'LTP', 20.00, 50.00, NULL, 1000, 2.0, 8,
         'aggregator', 'IMP Corporation Marine Duty Ratings', 'https://www.impcorporation.com/blog/marine-engine-duty-ratings', '2024-01-01',
         'Light duty rating. Higher RPM = lower hours. Fast vessels, patrol.');

    RAISE NOTICE 'Inserted MAN duty mappings (3 ratings)';

    -- ========================================================================
    -- Volvo Penta Marine Ratings
    -- Source: Volvo Penta MC Rating Definitions (volspec.co.uk - dealer)
    -- Verification: SECONDARY_DIST (dealer document)
    -- ========================================================================
    INSERT INTO kb_oem_duty_mappings (
        manufacturer, oem_rating_code, oem_rating_name, harmonized_duty_class,
        iso_equivalent, load_factor_min_pct, load_factor_max_pct,
        annual_hours_min, annual_hours_max, full_power_hours_per_cycle, cycle_hours,
        source_verification, source_document, source_url, source_date, notes
    ) VALUES
        ('Volvo Penta', 'R1', 'Rating 1 - Continuous Commercial', 'CON',
         'COP', 80.00, 100.00, NULL, NULL, NULL, NULL,
         'secondary_dist', 'Volvo Penta MC Rating Definitions', 'https://www.volspec.co.uk/marine-engines/ratings/', '2024-01-01',
         'Continuous commercial. Workboats, ferries.'),

        ('Volvo Penta', 'R2', 'Rating 2 - Heavy Duty Commercial', 'HVY',
         'PRP (high)', 60.00, 80.00, NULL, NULL, 8.0, 10,
         'secondary_dist', 'Volvo Penta MC Rating Definitions', 'https://www.volspec.co.uk/marine-engines/ratings/', '2024-01-01',
         'Heavy commercial. High load cycles.'),

        ('Volvo Penta', 'R3', 'Rating 3 - Light Duty Commercial', 'MED',
         'PRP (mid)', 50.00, 80.00, 2000, 4000, 6.0, 12,
         'secondary_dist', 'Volvo Penta MC Rating Definitions', 'https://www.volspec.co.uk/marine-engines/ratings/', '2024-01-01',
         'Light commercial. Medium duty cycles.'),

        ('Volvo Penta', 'R4', 'Rating 4 - Special Light Duty', 'LGT',
         'LTP', 20.00, 40.00, 1000, 2000, 2.0, 8,
         'secondary_dist', 'Volvo Penta MC Rating Definitions', 'https://www.volspec.co.uk/marine-engines/ratings/', '2024-01-01',
         'Special light duty. Lower usage patterns.'),

        ('Volvo Penta', 'R5', 'Rating 5 - Pleasure Craft', 'PLS',
         'Below ESP', 0.00, 30.00, 250, 1000, 1.0, 8,
         'secondary_dist', 'Volvo Penta MC Rating Definitions', 'https://www.volspec.co.uk/marine-engines/ratings/', '2024-01-01',
         'Pleasure craft. Recreational yachts.');

    RAISE NOTICE 'Inserted Volvo Penta duty mappings (5 ratings)';

    -- ========================================================================
    -- Wartsila High-Speed Ratings
    -- Source: IMP Corporation blog (impcorporation.com)
    -- Verification: AGGREGATOR (industry aggregator - needs OEM verification)
    -- ========================================================================
    INSERT INTO kb_oem_duty_mappings (
        manufacturer, oem_rating_code, oem_rating_name, harmonized_duty_class,
        iso_equivalent, load_factor_min_pct, load_factor_max_pct,
        annual_hours_min, annual_hours_max, full_power_hours_per_cycle, cycle_hours,
        source_verification, source_document, source_url, source_date, notes
    ) VALUES
        ('Wartsila', 'A', 'Rating A - Continuous', 'CON',
         'COP', 80.00, 100.00, 5000, 8000, NULL, NULL,
         'aggregator', 'IMP Corporation Marine Duty Ratings', 'https://www.impcorporation.com/blog/marine-engine-duty-ratings', '2024-01-01',
         'Continuous operation. High-speed ferries, workboats.'),

        ('Wartsila', 'B', 'Rating B - Heavy Duty', 'HVY',
         'PRP (high)', 40.00, 80.00, 3000, 5000, 10.0, 12,
         'aggregator', 'IMP Corporation Marine Duty Ratings', 'https://www.impcorporation.com/blog/marine-engine-duty-ratings', '2024-01-01',
         'Heavy commercial duty.'),

        ('Wartsila', 'C', 'Rating C - Medium Duty', 'MED',
         'PRP (mid)', 20.00, 80.00, 2000, 4000, 6.0, 12,
         'aggregator', 'IMP Corporation Marine Duty Ratings', 'https://www.impcorporation.com/blog/marine-engine-duty-ratings', '2024-01-01',
         'Medium commercial duty.'),

        ('Wartsila', 'D', 'Rating D - Light/Intermittent', 'LGT',
         'LTP', 0.00, 50.00, 2000, 4000, 3.0, 12,
         'aggregator', 'IMP Corporation Marine Duty Ratings', 'https://www.impcorporation.com/blog/marine-engine-duty-ratings', '2024-01-01',
         'Light duty / intermittent operation.');

    RAISE NOTICE 'Inserted Wartsila duty mappings (4 ratings)';

    -- ========================================================================
    -- John Deere Marine Ratings
    -- Source: John Deere Marine Selection Guide (deere.com - official)
    -- Verification: PRIMARY_OEM (official OEM document)
    -- ========================================================================
    INSERT INTO kb_oem_duty_mappings (
        manufacturer, oem_rating_code, oem_rating_name, harmonized_duty_class,
        iso_equivalent, load_factor_min_pct, load_factor_max_pct,
        annual_hours_min, annual_hours_max, full_power_hours_per_cycle, cycle_hours,
        source_verification, source_document, source_url, source_date, notes
    ) VALUES
        ('John Deere', 'M1', 'M1 - Highest Duty', 'CON',
         'COP', 80.00, 100.00, NULL, NULL, NULL, NULL,
         'primary_oem', 'John Deere Marine Selection Guide', 'https://www.deere.com/en/marine-engines/', '2024-01-01',
         'Highest duty cycle. Continuous commercial.'),

        ('John Deere', 'M2', 'M2 - Heavy Commercial', 'HVY',
         'PRP (high)', 60.00, 80.00, NULL, NULL, 8.0, 10,
         'primary_oem', 'John Deere Marine Selection Guide', 'https://www.deere.com/en/marine-engines/', '2024-01-01',
         'Heavy commercial duty.'),

        ('John Deere', 'M3', 'M3 - Medium Commercial', 'MED',
         'PRP (mid)', 40.00, 60.00, NULL, NULL, 6.0, 12,
         'primary_oem', 'John Deere Marine Selection Guide', 'https://www.deere.com/en/marine-engines/', '2024-01-01',
         'Medium commercial duty.'),

        ('John Deere', 'M4', 'M4 - General Commercial', 'LGT',
         'LTP', 20.00, 50.00, NULL, NULL, 2.0, 8,
         'primary_oem', 'John Deere Marine Selection Guide', 'https://www.deere.com/en/marine-engines/', '2024-01-01',
         'General commercial / light duty.'),

        ('John Deere', 'M5', 'M5 - Recreational/Light', 'PLS',
         'Below ESP', 0.00, 30.00, NULL, NULL, 1.0, 8,
         'primary_oem', 'John Deere Marine Selection Guide', 'https://www.deere.com/en/marine-engines/', '2024-01-01',
         'Recreational / light duty. Pleasure craft.');

    RAISE NOTICE 'Inserted John Deere duty mappings (5 ratings)';

    -- ========================================================================
    -- Yanmar Marine Ratings (generic - needs research)
    -- Source: General industry knowledge
    -- Verification: INFERRED (needs specific Yanmar documentation)
    -- ========================================================================
    INSERT INTO kb_oem_duty_mappings (
        manufacturer, oem_rating_code, oem_rating_name, harmonized_duty_class,
        iso_equivalent, load_factor_min_pct, load_factor_max_pct,
        annual_hours_min, annual_hours_max, full_power_hours_per_cycle, cycle_hours,
        source_verification, source_document, source_url, source_date, notes
    ) VALUES
        ('Yanmar', 'COM', 'Commercial', 'HVY',
         'PRP', 50.00, 80.00, NULL, NULL, 6.0, 10,
         'inferred', 'Generic industry convention', NULL, NULL,
         'NEEDS VERIFICATION: Inferred from industry conventions.'),

        ('Yanmar', 'PLS', 'Pleasure', 'PLS',
         'Below ESP', 0.00, 30.00, 250, 1000, 1.0, 8,
         'inferred', 'Generic industry convention', NULL, NULL,
         'NEEDS VERIFICATION: Inferred from industry conventions.');

    RAISE NOTICE 'Inserted Yanmar duty mappings (2 ratings - NEEDS VERIFICATION)';

    RAISE NOTICE 'Migration 009_seed_oem_mappings.sql completed: 39 OEM duty mappings inserted';
    RAISE NOTICE 'Source verification summary:';
    RAISE NOTICE '  - primary_oem: 11 (Cummins 6, John Deere 5)';
    RAISE NOTICE '  - secondary_dist: 19 (MTU 9, Caterpillar 5, Volvo Penta 5)';
    RAISE NOTICE '  - aggregator: 7 (MAN 3, Wartsila 4)';
    RAISE NOTICE '  - inferred: 2 (Yanmar 2 - NEEDS VERIFICATION)';
END $$;

-- ============================================================================
-- Verification Queries (for manual review)
-- ============================================================================
-- SELECT manufacturer, COUNT(*), source_verification
-- FROM kb_oem_duty_mappings
-- GROUP BY manufacturer, source_verification
-- ORDER BY manufacturer;

-- SELECT harmonized_duty_class, COUNT(*)
-- FROM kb_oem_duty_mappings
-- GROUP BY harmonized_duty_class
-- ORDER BY harmonized_duty_class;
