-- Migration: product_data.py -> Unified KB
-- Generated: 2026-01-22T09:39:05.247020+00:00
-- Source: ALL_ENGINE_FACT_SHEETS with VERIFIED engine_master_data.py

-- =============================================================================
-- ROLLBACK: Run this section to undo the migration
-- =============================================================================
-- DELETE FROM kb_engine_ratings WHERE data_source = 'manufacturer_datasheet';
-- DELETE FROM kb_engine_models WHERE data_source = 'manufacturer_datasheet';
-- DELETE FROM kb_engine_series WHERE 1=1; -- Careful: may delete existing data
-- DELETE FROM kb_manufacturers WHERE 1=1; -- Careful: may delete existing data

-- =============================================================================
-- MANUFACTURERS
-- =============================================================================

INSERT INTO kb_manufacturers (id, name, country, tier, website, description, is_active)
VALUES ('98547792-ab61-496f-9e9e-a85cc3f43cf1', 'MTU (Rolls-Royce Power Systems)', 'Germany', 1, 'https://www.mtu-solutions.com/', 'Marine engine manufacturer - RRPS', TRUE)
ON CONFLICT (name) DO UPDATE SET
    website = EXCLUDED.website,
    tier = EXCLUDED.tier;

INSERT INTO kb_manufacturers (id, name, country, tier, website, description, is_active)
VALUES ('460fc5a6-2493-40f4-a936-48f7d23daaf2', 'Cummins', 'USA', 1, 'https://www.cummins.com/', 'Marine engine manufacturer - Competitor', TRUE)
ON CONFLICT (name) DO UPDATE SET
    website = EXCLUDED.website,
    tier = EXCLUDED.tier;

INSERT INTO kb_manufacturers (id, name, country, tier, website, description, is_active)
VALUES ('bc7a097c-95c5-4cbe-87d9-19a0e85c1226', 'Caterpillar', 'USA', 1, 'https://www.cat.com/', 'Marine engine manufacturer - Competitor', TRUE)
ON CONFLICT (name) DO UPDATE SET
    website = EXCLUDED.website,
    tier = EXCLUDED.tier;

INSERT INTO kb_manufacturers (id, name, country, tier, website, description, is_active)
VALUES ('437bbe73-a60a-4fcc-89e3-6a5763b45f1f', 'MAN Engines', 'Germany', 1, 'https://www.man.eu/engines/', 'Marine engine manufacturer - Competitor', TRUE)
ON CONFLICT (name) DO UPDATE SET
    website = EXCLUDED.website,
    tier = EXCLUDED.tier;

INSERT INTO kb_manufacturers (id, name, country, tier, website, description, is_active)
VALUES ('8b603958-4a73-48a0-8779-2b4d34b979b8', 'Volvo Penta', 'Sweden', 1, 'https://www.volvopenta.com/', 'Marine engine manufacturer - Competitor', TRUE)
ON CONFLICT (name) DO UPDATE SET
    website = EXCLUDED.website,
    tier = EXCLUDED.tier;

INSERT INTO kb_manufacturers (id, name, country, tier, website, description, is_active)
VALUES ('52896002-fc94-4f79-8b86-cd1474aea471', 'Yanmar', 'Japan', 2, 'https://www.yanmar.com/', 'Marine engine manufacturer - Competitor', TRUE)
ON CONFLICT (name) DO UPDATE SET
    website = EXCLUDED.website,
    tier = EXCLUDED.tier;

INSERT INTO kb_manufacturers (id, name, country, tier, website, description, is_active)
VALUES ('b4f28b58-e8e7-4f02-8a39-722014d25542', 'WEICHAI', 'China', 2, 'https://en.weichai.com/', 'Marine engine manufacturer - Competitor', TRUE)
ON CONFLICT (name) DO UPDATE SET
    website = EXCLUDED.website,
    tier = EXCLUDED.tier;

INSERT INTO kb_manufacturers (id, name, country, tier, website, description, is_active)
VALUES ('680a6d49-4618-4e57-a334-d4a401e3c09e', 'FPT Industrial', 'Italy', 2, 'https://www.fptindustrial.com/', 'Marine engine manufacturer - Competitor', TRUE)
ON CONFLICT (name) DO UPDATE SET
    website = EXCLUDED.website,
    tier = EXCLUDED.tier;

INSERT INTO kb_manufacturers (id, name, country, tier, website, description, is_active)
VALUES ('b8d5d69b-3f2c-4523-b944-341ac1dabfa9', 'Scania', 'Sweden', 2, 'https://www.scania.com/', 'Marine engine manufacturer - Competitor', TRUE)
ON CONFLICT (name) DO UPDATE SET
    website = EXCLUDED.website,
    tier = EXCLUDED.tier;

INSERT INTO kb_manufacturers (id, name, country, tier, website, description, is_active)
VALUES ('226c208f-7a0a-44d3-85ce-937a9a66e7d5', 'Wartsila', 'Finland', 1, 'https://www.wartsila.com/', 'Marine engine manufacturer - Competitor', TRUE)
ON CONFLICT (name) DO UPDATE SET
    website = EXCLUDED.website,
    tier = EXCLUDED.tier;

-- =============================================================================
-- ENGINE SERIES
-- =============================================================================

INSERT INTO kb_engine_series (id, manufacturer_id, brand, series_name, description, is_current)
VALUES ('a8efda5c-53c3-4c65-b662-37604a6b07a1', '98547792-ab61-496f-9e9e-a85cc3f43cf1', 'MTU', 'Series 2000', 'Series 2000 series marine engines', TRUE)
ON CONFLICT (manufacturer_id, series_name) DO UPDATE SET
    description = EXCLUDED.description;

INSERT INTO kb_engine_series (id, manufacturer_id, brand, series_name, description, is_current)
VALUES ('44cbbca0-8df6-40a9-87e0-02063bdcfa58', '98547792-ab61-496f-9e9e-a85cc3f43cf1', 'MTU', 'Series 4000', 'Series 4000 series marine engines', TRUE)
ON CONFLICT (manufacturer_id, series_name) DO UPDATE SET
    description = EXCLUDED.description;

INSERT INTO kb_engine_series (id, manufacturer_id, brand, series_name, description, is_current)
VALUES ('1bc94d1f-2141-46b4-a540-e2c00b7e685a', '98547792-ab61-496f-9e9e-a85cc3f43cf1', 'MTU', 'Series 4000 Gas', 'Series 4000 Gas series marine engines', TRUE)
ON CONFLICT (manufacturer_id, series_name) DO UPDATE SET
    description = EXCLUDED.description;

INSERT INTO kb_engine_series (id, manufacturer_id, brand, series_name, description, is_current)
VALUES ('65bf39ad-f63d-40ed-b026-e59daf1c0d18', '98547792-ab61-496f-9e9e-a85cc3f43cf1', 'MTU', 'Series 8000', 'Series 8000 series marine engines', TRUE)
ON CONFLICT (manufacturer_id, series_name) DO UPDATE SET
    description = EXCLUDED.description;

INSERT INTO kb_engine_series (id, manufacturer_id, brand, series_name, description, is_current)
VALUES ('9d0a698b-5d56-4230-8440-b8d8c5077591', '460fc5a6-2493-40f4-a936-48f7d23daaf2', 'Cummins', 'QSK', 'QSK series marine engines', TRUE)
ON CONFLICT (manufacturer_id, series_name) DO UPDATE SET
    description = EXCLUDED.description;

INSERT INTO kb_engine_series (id, manufacturer_id, brand, series_name, description, is_current)
VALUES ('d7173f26-3ae6-407a-9dc6-c593dfaf18ab', '460fc5a6-2493-40f4-a936-48f7d23daaf2', 'Cummins', 'QST', 'QST series marine engines', TRUE)
ON CONFLICT (manufacturer_id, series_name) DO UPDATE SET
    description = EXCLUDED.description;

INSERT INTO kb_engine_series (id, manufacturer_id, brand, series_name, description, is_current)
VALUES ('cc74ccef-e05c-44af-a604-86be633acf1f', '460fc5a6-2493-40f4-a936-48f7d23daaf2', 'Cummins', 'X15', 'X15 series marine engines', TRUE)
ON CONFLICT (manufacturer_id, series_name) DO UPDATE SET
    description = EXCLUDED.description;

INSERT INTO kb_engine_series (id, manufacturer_id, brand, series_name, description, is_current)
VALUES ('343b2d7e-4766-4d88-bbe2-80ca5c45d8fd', 'bc7a097c-95c5-4cbe-87d9-19a0e85c1226', 'Caterpillar', '3500', '3500 series marine engines', TRUE)
ON CONFLICT (manufacturer_id, series_name) DO UPDATE SET
    description = EXCLUDED.description;

INSERT INTO kb_engine_series (id, manufacturer_id, brand, series_name, description, is_current)
VALUES ('d62f9f8b-3681-4037-b724-3efe9da5837b', 'bc7a097c-95c5-4cbe-87d9-19a0e85c1226', 'Caterpillar', 'C12', 'C12 series marine engines', TRUE)
ON CONFLICT (manufacturer_id, series_name) DO UPDATE SET
    description = EXCLUDED.description;

INSERT INTO kb_engine_series (id, manufacturer_id, brand, series_name, description, is_current)
VALUES ('8a788232-cfe6-43f0-8059-69ddb30f2aa5', 'bc7a097c-95c5-4cbe-87d9-19a0e85c1226', 'Caterpillar', 'C18', 'C18 series marine engines', TRUE)
ON CONFLICT (manufacturer_id, series_name) DO UPDATE SET
    description = EXCLUDED.description;

INSERT INTO kb_engine_series (id, manufacturer_id, brand, series_name, description, is_current)
VALUES ('b1776572-488a-410a-9389-c1f0c87dd5b4', 'bc7a097c-95c5-4cbe-87d9-19a0e85c1226', 'Caterpillar', 'C32', 'C32 series marine engines', TRUE)
ON CONFLICT (manufacturer_id, series_name) DO UPDATE SET
    description = EXCLUDED.description;

INSERT INTO kb_engine_series (id, manufacturer_id, brand, series_name, description, is_current)
VALUES ('a74023e6-4746-44d8-9d49-1fbbdaec2697', '437bbe73-a60a-4fcc-89e3-6a5763b45f1f', 'MAN', 'D2676', 'D2676 series marine engines', TRUE)
ON CONFLICT (manufacturer_id, series_name) DO UPDATE SET
    description = EXCLUDED.description;

INSERT INTO kb_engine_series (id, manufacturer_id, brand, series_name, description, is_current)
VALUES ('06a56a16-cd1f-411b-9a79-17609637f5d0', '437bbe73-a60a-4fcc-89e3-6a5763b45f1f', 'MAN', 'D2862', 'D2862 series marine engines', TRUE)
ON CONFLICT (manufacturer_id, series_name) DO UPDATE SET
    description = EXCLUDED.description;

INSERT INTO kb_engine_series (id, manufacturer_id, brand, series_name, description, is_current)
VALUES ('73a4f665-6d59-4c33-9993-eeff7057e24a', '437bbe73-a60a-4fcc-89e3-6a5763b45f1f', 'MAN', 'D2868', 'D2868 series marine engines', TRUE)
ON CONFLICT (manufacturer_id, series_name) DO UPDATE SET
    description = EXCLUDED.description;

INSERT INTO kb_engine_series (id, manufacturer_id, brand, series_name, description, is_current)
VALUES ('1d4b9689-3f30-4549-95e0-f2646c7e8dad', '437bbe73-a60a-4fcc-89e3-6a5763b45f1f', 'MAN', 'V12-2000', 'V12-2000 series marine engines', TRUE)
ON CONFLICT (manufacturer_id, series_name) DO UPDATE SET
    description = EXCLUDED.description;

INSERT INTO kb_engine_series (id, manufacturer_id, brand, series_name, description, is_current)
VALUES ('ea7d30d4-d65a-4357-8daa-9f66f222dff9', '8b603958-4a73-48a0-8779-2b4d34b979b8', 'Volvo', 'D11', 'D11 series marine engines', TRUE)
ON CONFLICT (manufacturer_id, series_name) DO UPDATE SET
    description = EXCLUDED.description;

INSERT INTO kb_engine_series (id, manufacturer_id, brand, series_name, description, is_current)
VALUES ('dab7fbf4-eda5-4603-a3f5-6942fed6f069', '8b603958-4a73-48a0-8779-2b4d34b979b8', 'Volvo', 'D13', 'D13 series marine engines', TRUE)
ON CONFLICT (manufacturer_id, series_name) DO UPDATE SET
    description = EXCLUDED.description;

INSERT INTO kb_engine_series (id, manufacturer_id, brand, series_name, description, is_current)
VALUES ('dadfd1ca-0928-4d50-be4c-2c4c2cac2bae', '52896002-fc94-4f79-8b86-cd1474aea471', 'Yanmar', '6AY', '6AY series marine engines', TRUE)
ON CONFLICT (manufacturer_id, series_name) DO UPDATE SET
    description = EXCLUDED.description;

INSERT INTO kb_engine_series (id, manufacturer_id, brand, series_name, description, is_current)
VALUES ('8f01a1db-7f17-4e66-aac0-5d31cf30d9b4', '52896002-fc94-4f79-8b86-cd1474aea471', 'Yanmar', '8AY', '8AY series marine engines', TRUE)
ON CONFLICT (manufacturer_id, series_name) DO UPDATE SET
    description = EXCLUDED.description;

INSERT INTO kb_engine_series (id, manufacturer_id, brand, series_name, description, is_current)
VALUES ('5d20922a-3ad6-40f6-872f-396e2ecd9418', '52896002-fc94-4f79-8b86-cd1474aea471', 'Yanmar', '12AY', '12AY series marine engines', TRUE)
ON CONFLICT (manufacturer_id, series_name) DO UPDATE SET
    description = EXCLUDED.description;

INSERT INTO kb_engine_series (id, manufacturer_id, brand, series_name, description, is_current)
VALUES ('c10b4323-c1da-41a9-a8eb-4a2c948f2423', 'b4f28b58-e8e7-4f02-8a39-722014d25542', 'WEICHAI', 'WP13', 'WP13 series marine engines', TRUE)
ON CONFLICT (manufacturer_id, series_name) DO UPDATE SET
    description = EXCLUDED.description;

INSERT INTO kb_engine_series (id, manufacturer_id, brand, series_name, description, is_current)
VALUES ('afafd8db-ae7d-4462-a3d0-e71353760a57', 'b4f28b58-e8e7-4f02-8a39-722014d25542', 'WEICHAI', 'WHM6160', 'WHM6160 series marine engines', TRUE)
ON CONFLICT (manufacturer_id, series_name) DO UPDATE SET
    description = EXCLUDED.description;

INSERT INTO kb_engine_series (id, manufacturer_id, brand, series_name, description, is_current)
VALUES ('cc3d8bb9-edba-47d0-849f-d3a34d422c9e', 'b4f28b58-e8e7-4f02-8a39-722014d25542', 'WEICHAI', 'M33', 'M33 series marine engines', TRUE)
ON CONFLICT (manufacturer_id, series_name) DO UPDATE SET
    description = EXCLUDED.description;

INSERT INTO kb_engine_series (id, manufacturer_id, brand, series_name, description, is_current)
VALUES ('2291079c-bd06-40b4-a8b2-d45f46fa799e', '680a6d49-4618-4e57-a334-d4a401e3c09e', 'FPT', 'Cursor', 'Cursor series marine engines', TRUE)
ON CONFLICT (manufacturer_id, series_name) DO UPDATE SET
    description = EXCLUDED.description;

INSERT INTO kb_engine_series (id, manufacturer_id, brand, series_name, description, is_current)
VALUES ('5e780e4a-bdfc-428c-a07b-2d196cce08f4', 'b8d5d69b-3f2c-4523-b944-341ac1dabfa9', 'Scania', 'DI13', 'DI13 series marine engines', TRUE)
ON CONFLICT (manufacturer_id, series_name) DO UPDATE SET
    description = EXCLUDED.description;

INSERT INTO kb_engine_series (id, manufacturer_id, brand, series_name, description, is_current)
VALUES ('474b060c-efc2-48da-a188-b5e1fb206f6a', 'b8d5d69b-3f2c-4523-b944-341ac1dabfa9', 'Scania', 'DI16', 'DI16 series marine engines', TRUE)
ON CONFLICT (manufacturer_id, series_name) DO UPDATE SET
    description = EXCLUDED.description;

INSERT INTO kb_engine_series (id, manufacturer_id, brand, series_name, description, is_current)
VALUES ('91709473-6c72-4ae5-86c3-f847ab32af38', '226c208f-7a0a-44d3-85ce-937a9a66e7d5', 'Wartsila', 'Wartsila 14', 'Wartsila 14 series marine engines', TRUE)
ON CONFLICT (manufacturer_id, series_name) DO UPDATE SET
    description = EXCLUDED.description;

INSERT INTO kb_engine_series (id, manufacturer_id, brand, series_name, description, is_current)
VALUES ('21ba28fe-58a7-411a-8dea-524d96297b11', '226c208f-7a0a-44d3-85ce-937a9a66e7d5', 'Wartsila', 'Wartsila 20', 'Wartsila 20 series marine engines', TRUE)
ON CONFLICT (manufacturer_id, series_name) DO UPDATE SET
    description = EXCLUDED.description;

-- =============================================================================
-- ENGINE MODELS
-- =============================================================================

INSERT INTO kb_engine_models (id, series_id, model_name, rpm_min, rpm_max, power_min_kw, power_max_kw, cylinders, configuration, fuel_types, emission_tier, is_current_production, data_source, data_confidence)
VALUES ('f54a755f-b3fc-497d-98de-ae25e58d9686', 'a8efda5c-53c3-4c65-b662-37604a6b07a1', 'MTU 8V 2000 M72', 2250, 2250, 720, 720, 8, 'V', '["diesel", "mdo", "mgo"]', 'IMO Tier II', TRUE, 'manufacturer_datasheet', 0.95)
ON CONFLICT (model_name) DO UPDATE SET
    power_min_kw = EXCLUDED.power_min_kw,
    power_max_kw = EXCLUDED.power_max_kw,
    data_confidence = EXCLUDED.data_confidence;

INSERT INTO kb_engine_models (id, series_id, model_name, rpm_min, rpm_max, power_min_kw, power_max_kw, cylinders, configuration, fuel_types, emission_tier, is_current_production, data_source, data_confidence)
VALUES ('97cb8f68-b468-4b1a-9f34-34eda5382c5c', 'a8efda5c-53c3-4c65-b662-37604a6b07a1', 'MTU 10V 2000 M72', 2250, 2250, 900, 900, 10, 'V', '["diesel", "mdo", "mgo"]', 'IMO Tier II', TRUE, 'manufacturer_datasheet', 0.95)
ON CONFLICT (model_name) DO UPDATE SET
    power_min_kw = EXCLUDED.power_min_kw,
    power_max_kw = EXCLUDED.power_max_kw,
    data_confidence = EXCLUDED.data_confidence;

INSERT INTO kb_engine_models (id, series_id, model_name, rpm_min, rpm_max, power_min_kw, power_max_kw, cylinders, configuration, fuel_types, emission_tier, is_current_production, data_source, data_confidence)
VALUES ('c2423714-0c43-423a-9933-d2f23b92d74e', 'a8efda5c-53c3-4c65-b662-37604a6b07a1', 'MTU 12V 2000 M93', 2450, 2450, 1340, 1340, 12, 'V', '["diesel", "mdo", "mgo"]', 'IMO Tier II', TRUE, 'manufacturer_datasheet', 0.95)
ON CONFLICT (model_name) DO UPDATE SET
    power_min_kw = EXCLUDED.power_min_kw,
    power_max_kw = EXCLUDED.power_max_kw,
    data_confidence = EXCLUDED.data_confidence;

INSERT INTO kb_engine_models (id, series_id, model_name, rpm_min, rpm_max, power_min_kw, power_max_kw, cylinders, configuration, fuel_types, emission_tier, is_current_production, data_source, data_confidence)
VALUES ('0ff541a5-3a62-4232-aed4-220abe97eaa8', 'a8efda5c-53c3-4c65-b662-37604a6b07a1', 'MTU 16V 2000 M93', 2450, 2450, 1790, 1790, 16, 'V', '["diesel", "mdo", "mgo"]', 'IMO Tier II', TRUE, 'manufacturer_datasheet', 0.95)
ON CONFLICT (model_name) DO UPDATE SET
    power_min_kw = EXCLUDED.power_min_kw,
    power_max_kw = EXCLUDED.power_max_kw,
    data_confidence = EXCLUDED.data_confidence;

INSERT INTO kb_engine_models (id, series_id, model_name, rpm_min, rpm_max, power_min_kw, power_max_kw, cylinders, configuration, fuel_types, emission_tier, is_current_production, data_source, data_confidence)
VALUES ('7777d2d7-111a-4fcb-858a-f9d2601542c6', 'a8efda5c-53c3-4c65-b662-37604a6b07a1', 'MTU 16V 2000 M96', 2450, 2450, 1790, 1939, 16, 'V', '["diesel", "mdo", "mgo"]', 'IMO Tier II', TRUE, 'manufacturer_datasheet', 0.95)
ON CONFLICT (model_name) DO UPDATE SET
    power_min_kw = EXCLUDED.power_min_kw,
    power_max_kw = EXCLUDED.power_max_kw,
    data_confidence = EXCLUDED.data_confidence;

INSERT INTO kb_engine_models (id, series_id, model_name, rpm_min, rpm_max, power_min_kw, power_max_kw, cylinders, configuration, fuel_types, emission_tier, is_current_production, data_source, data_confidence)
VALUES ('fe356bdc-76c7-4922-b535-69b7bfe4a52d', '44cbbca0-8df6-40a9-87e0-02063bdcfa58', 'MTU 12V 4000 M63', 1600, 1800, 1500, 1500, 12, 'V', '["diesel", "mdo", "mgo"]', 'IMO Tier II', TRUE, 'manufacturer_datasheet', 0.9)
ON CONFLICT (model_name) DO UPDATE SET
    power_min_kw = EXCLUDED.power_min_kw,
    power_max_kw = EXCLUDED.power_max_kw,
    data_confidence = EXCLUDED.data_confidence;

INSERT INTO kb_engine_models (id, series_id, model_name, rpm_min, rpm_max, power_min_kw, power_max_kw, cylinders, configuration, fuel_types, emission_tier, is_current_production, data_source, data_confidence)
VALUES ('5db12a4a-856f-454f-9145-77f59c2fc2ec', '44cbbca0-8df6-40a9-87e0-02063bdcfa58', 'MTU 16V 4000 M63', 1600, 1800, 1920, 2240, 16, 'V', '["diesel", "mdo", "mgo"]', 'IMO Tier II', TRUE, 'manufacturer_datasheet', 0.95)
ON CONFLICT (model_name) DO UPDATE SET
    power_min_kw = EXCLUDED.power_min_kw,
    power_max_kw = EXCLUDED.power_max_kw,
    data_confidence = EXCLUDED.data_confidence;

INSERT INTO kb_engine_models (id, series_id, model_name, rpm_min, rpm_max, power_min_kw, power_max_kw, cylinders, configuration, fuel_types, emission_tier, is_current_production, data_source, data_confidence)
VALUES ('7dfb3de9-71ee-41c7-88dc-6b44095faea6', '44cbbca0-8df6-40a9-87e0-02063bdcfa58', 'MTU 12V 4000 M73', 1970, 2050, 1920, 2160, 12, 'V', '["diesel", "mdo", "mgo"]', 'IMO Tier II', TRUE, 'manufacturer_datasheet', 0.9)
ON CONFLICT (model_name) DO UPDATE SET
    power_min_kw = EXCLUDED.power_min_kw,
    power_max_kw = EXCLUDED.power_max_kw,
    data_confidence = EXCLUDED.data_confidence;

INSERT INTO kb_engine_models (id, series_id, model_name, rpm_min, rpm_max, power_min_kw, power_max_kw, cylinders, configuration, fuel_types, emission_tier, is_current_production, data_source, data_confidence)
VALUES ('4e70e7e8-e858-4851-a612-1b642af0f890', '44cbbca0-8df6-40a9-87e0-02063bdcfa58', 'MTU 16V 4000 M73', 1970, 2050, 2560, 2880, 16, 'V', '["diesel", "mdo", "mgo"]', 'IMO Tier II', TRUE, 'manufacturer_datasheet', 0.95)
ON CONFLICT (model_name) DO UPDATE SET
    power_min_kw = EXCLUDED.power_min_kw,
    power_max_kw = EXCLUDED.power_max_kw,
    data_confidence = EXCLUDED.data_confidence;

INSERT INTO kb_engine_models (id, series_id, model_name, rpm_min, rpm_max, power_min_kw, power_max_kw, cylinders, configuration, fuel_types, emission_tier, is_current_production, data_source, data_confidence)
VALUES ('5ed90e32-9da0-4078-b4bc-ac2c991a7fa9', '44cbbca0-8df6-40a9-87e0-02063bdcfa58', 'MTU 12V 4000 M93', 2100, 2100, 2340, 2580, 12, 'V', '["diesel", "mdo", "mgo"]', 'IMO Tier II', TRUE, 'manufacturer_datasheet', 0.95)
ON CONFLICT (model_name) DO UPDATE SET
    power_min_kw = EXCLUDED.power_min_kw,
    power_max_kw = EXCLUDED.power_max_kw,
    data_confidence = EXCLUDED.data_confidence;

INSERT INTO kb_engine_models (id, series_id, model_name, rpm_min, rpm_max, power_min_kw, power_max_kw, cylinders, configuration, fuel_types, emission_tier, is_current_production, data_source, data_confidence)
VALUES ('b62207c6-718b-40b2-b352-de905854cca6', '44cbbca0-8df6-40a9-87e0-02063bdcfa58', 'MTU 16V 4000 M93', 2100, 2100, 3120, 3440, 16, 'V', '["diesel", "mdo", "mgo"]', 'IMO Tier II', TRUE, 'manufacturer_datasheet', 0.95)
ON CONFLICT (model_name) DO UPDATE SET
    power_min_kw = EXCLUDED.power_min_kw,
    power_max_kw = EXCLUDED.power_max_kw,
    data_confidence = EXCLUDED.data_confidence;

INSERT INTO kb_engine_models (id, series_id, model_name, rpm_min, rpm_max, power_min_kw, power_max_kw, cylinders, configuration, fuel_types, emission_tier, is_current_production, data_source, data_confidence)
VALUES ('62ada188-ff03-46f5-9454-83572039949b', '44cbbca0-8df6-40a9-87e0-02063bdcfa58', 'MTU 20V 4000 M93', 2100, 2100, 3900, 4300, 20, 'V', '["diesel", "mdo", "mgo"]', 'IMO Tier II', TRUE, 'manufacturer_datasheet', 0.95)
ON CONFLICT (model_name) DO UPDATE SET
    power_min_kw = EXCLUDED.power_min_kw,
    power_max_kw = EXCLUDED.power_max_kw,
    data_confidence = EXCLUDED.data_confidence;

INSERT INTO kb_engine_models (id, series_id, model_name, rpm_min, rpm_max, power_min_kw, power_max_kw, cylinders, configuration, fuel_types, emission_tier, is_current_production, data_source, data_confidence)
VALUES ('abd15255-639f-4ee5-865c-464ed6fa6702', '1bc94d1f-2141-46b4-a540-e2c00b7e685a', 'MTU 12V 4000 M05-N', 1500, 1500, 1164, 1380, 12, 'V', '["natural_gas", "lng"]', 'IMO Tier III (Gas Mode)', TRUE, 'manufacturer_datasheet', 0.9)
ON CONFLICT (model_name) DO UPDATE SET
    power_min_kw = EXCLUDED.power_min_kw,
    power_max_kw = EXCLUDED.power_max_kw,
    data_confidence = EXCLUDED.data_confidence;

INSERT INTO kb_engine_models (id, series_id, model_name, rpm_min, rpm_max, power_min_kw, power_max_kw, cylinders, configuration, fuel_types, emission_tier, is_current_production, data_source, data_confidence)
VALUES ('a3f10777-0008-482c-9958-cc4123401293', '1bc94d1f-2141-46b4-a540-e2c00b7e685a', 'MTU 16V 4000 M05-N', 1500, 1500, 1552, 1840, 16, 'V', '["natural_gas", "lng"]', 'IMO Tier III (Gas Mode)', TRUE, 'manufacturer_datasheet', 0.9)
ON CONFLICT (model_name) DO UPDATE SET
    power_min_kw = EXCLUDED.power_min_kw,
    power_max_kw = EXCLUDED.power_max_kw,
    data_confidence = EXCLUDED.data_confidence;

INSERT INTO kb_engine_models (id, series_id, model_name, rpm_min, rpm_max, power_min_kw, power_max_kw, cylinders, configuration, fuel_types, emission_tier, is_current_production, data_source, data_confidence)
VALUES ('5133d902-753a-4984-b9a7-33a10b1b9987', '1bc94d1f-2141-46b4-a540-e2c00b7e685a', 'MTU 20V 4000 M05-N', 1500, 1500, 1940, 2300, 20, 'V', '["natural_gas", "lng"]', 'IMO Tier III (Gas Mode)', TRUE, 'manufacturer_datasheet', 0.9)
ON CONFLICT (model_name) DO UPDATE SET
    power_min_kw = EXCLUDED.power_min_kw,
    power_max_kw = EXCLUDED.power_max_kw,
    data_confidence = EXCLUDED.data_confidence;

INSERT INTO kb_engine_models (id, series_id, model_name, rpm_min, rpm_max, power_min_kw, power_max_kw, cylinders, configuration, fuel_types, emission_tier, is_current_production, data_source, data_confidence)
VALUES ('64770fae-ab1b-4c5e-8fc6-af3aea679ff9', '65bf39ad-f63d-40ed-b026-e59daf1c0d18', 'MTU 16V 8000 M71', 1150, 1150, 7280, 7280, 16, 'V', '["diesel", "mdo"]', 'IMO Tier II', TRUE, 'manufacturer_datasheet', 0.95)
ON CONFLICT (model_name) DO UPDATE SET
    power_min_kw = EXCLUDED.power_min_kw,
    power_max_kw = EXCLUDED.power_max_kw,
    data_confidence = EXCLUDED.data_confidence;

INSERT INTO kb_engine_models (id, series_id, model_name, rpm_min, rpm_max, power_min_kw, power_max_kw, cylinders, configuration, fuel_types, emission_tier, is_current_production, data_source, data_confidence)
VALUES ('1180a2df-0d96-4e8a-8e6b-6946e92feaae', '65bf39ad-f63d-40ed-b026-e59daf1c0d18', 'MTU 20V 8000 M91', 1150, 1150, 9100, 10000, 20, 'V', '["diesel", "mdo"]', 'IMO Tier II', TRUE, 'manufacturer_datasheet', 0.95)
ON CONFLICT (model_name) DO UPDATE SET
    power_min_kw = EXCLUDED.power_min_kw,
    power_max_kw = EXCLUDED.power_max_kw,
    data_confidence = EXCLUDED.data_confidence;

INSERT INTO kb_engine_models (id, series_id, model_name, rpm_min, rpm_max, power_min_kw, power_max_kw, cylinders, configuration, fuel_types, emission_tier, is_current_production, data_source, data_confidence)
VALUES ('085b04f4-de18-4278-9259-ea6fac98bd63', '9d0a698b-5d56-4230-8440-b8d8c5077591', 'Cummins QSK38', 1800, 1800, 1063, 1417, 12, 'V', '["diesel", "mdo", "mgo"]', 'IMO Tier II', TRUE, 'manufacturer_datasheet', 0.95)
ON CONFLICT (model_name) DO UPDATE SET
    power_min_kw = EXCLUDED.power_min_kw,
    power_max_kw = EXCLUDED.power_max_kw,
    data_confidence = EXCLUDED.data_confidence;

INSERT INTO kb_engine_models (id, series_id, model_name, rpm_min, rpm_max, power_min_kw, power_max_kw, cylinders, configuration, fuel_types, emission_tier, is_current_production, data_source, data_confidence)
VALUES ('c4da3cf2-6e9a-4648-82ae-8d3b57dd5347', '9d0a698b-5d56-4230-8440-b8d8c5077591', 'Cummins QSK50', 1800, 1800, 1268, 1700, 16, 'V', '["diesel", "mdo", "mgo"]', 'IMO Tier II', TRUE, 'manufacturer_datasheet', 0.95)
ON CONFLICT (model_name) DO UPDATE SET
    power_min_kw = EXCLUDED.power_min_kw,
    power_max_kw = EXCLUDED.power_max_kw,
    data_confidence = EXCLUDED.data_confidence;

INSERT INTO kb_engine_models (id, series_id, model_name, rpm_min, rpm_max, power_min_kw, power_max_kw, cylinders, configuration, fuel_types, emission_tier, is_current_production, data_source, data_confidence)
VALUES ('9310b10d-4ee8-47c3-a54e-486ddd2a49d6', '9d0a698b-5d56-4230-8440-b8d8c5077591', 'Cummins QSK60', 1800, 1800, 1641, 2680, 16, 'V', '["diesel", "mdo", "mgo"]', 'IMO Tier II', TRUE, 'manufacturer_datasheet', 0.95)
ON CONFLICT (model_name) DO UPDATE SET
    power_min_kw = EXCLUDED.power_min_kw,
    power_max_kw = EXCLUDED.power_max_kw,
    data_confidence = EXCLUDED.data_confidence;

INSERT INTO kb_engine_models (id, series_id, model_name, rpm_min, rpm_max, power_min_kw, power_max_kw, cylinders, configuration, fuel_types, emission_tier, is_current_production, data_source, data_confidence)
VALUES ('0a1fcf5a-a4a1-4f14-97e2-3c6cffb1cd59', '9d0a698b-5d56-4230-8440-b8d8c5077591', 'Cummins QSK78', 1800, 1800, 2610, 3028, 18, 'V', '["diesel", "mdo"]', 'IMO Tier II', TRUE, 'manufacturer_datasheet', 0.85)
ON CONFLICT (model_name) DO UPDATE SET
    power_min_kw = EXCLUDED.power_min_kw,
    power_max_kw = EXCLUDED.power_max_kw,
    data_confidence = EXCLUDED.data_confidence;

INSERT INTO kb_engine_models (id, series_id, model_name, rpm_min, rpm_max, power_min_kw, power_max_kw, cylinders, configuration, fuel_types, emission_tier, is_current_production, data_source, data_confidence)
VALUES ('544f6045-d69b-415e-a448-7e7ce301ff85', '9d0a698b-5d56-4230-8440-b8d8c5077591', 'Cummins QSK95', 1800, 1800, 2834, 3730, 16, 'V', '["diesel", "mdo"]', 'IMO Tier II', TRUE, 'manufacturer_datasheet', 0.95)
ON CONFLICT (model_name) DO UPDATE SET
    power_min_kw = EXCLUDED.power_min_kw,
    power_max_kw = EXCLUDED.power_max_kw,
    data_confidence = EXCLUDED.data_confidence;

INSERT INTO kb_engine_models (id, series_id, model_name, rpm_min, rpm_max, power_min_kw, power_max_kw, cylinders, configuration, fuel_types, emission_tier, is_current_production, data_source, data_confidence)
VALUES ('58037c0d-2d60-403e-9210-3b7e6a32d7a6', 'd7173f26-3ae6-407a-9dc6-c593dfaf18ab', 'Cummins QST30', 1800, 2100, 746, 1007, 12, 'V', '["diesel", "mdo", "mgo"]', 'IMO Tier II', TRUE, 'manufacturer_datasheet', 0.9)
ON CONFLICT (model_name) DO UPDATE SET
    power_min_kw = EXCLUDED.power_min_kw,
    power_max_kw = EXCLUDED.power_max_kw,
    data_confidence = EXCLUDED.data_confidence;

INSERT INTO kb_engine_models (id, series_id, model_name, rpm_min, rpm_max, power_min_kw, power_max_kw, cylinders, configuration, fuel_types, emission_tier, is_current_production, data_source, data_confidence)
VALUES ('9a41404b-5e1d-439e-8771-2067a7d6692e', 'cc74ccef-e05c-44af-a604-86be633acf1f', 'Cummins X15 Marine', 1800, 2100, 450, 600, 6, 'inline', '["diesel", "mdo", "mgo"]', 'IMO Tier II', TRUE, 'manufacturer_datasheet', 0.9)
ON CONFLICT (model_name) DO UPDATE SET
    power_min_kw = EXCLUDED.power_min_kw,
    power_max_kw = EXCLUDED.power_max_kw,
    data_confidence = EXCLUDED.data_confidence;

INSERT INTO kb_engine_models (id, series_id, model_name, rpm_min, rpm_max, power_min_kw, power_max_kw, cylinders, configuration, fuel_types, emission_tier, is_current_production, data_source, data_confidence)
VALUES ('2bbcdbe2-accb-4f91-ad35-edc65d7e1bc4', '9d0a698b-5d56-4230-8440-b8d8c5077591', 'Cummins QSK38-M', 1800, 1800, 895, 1193, 12, 'V', '["diesel", "mdo", "mgo"]', 'IMO Tier II', TRUE, 'manufacturer_datasheet', 0.9)
ON CONFLICT (model_name) DO UPDATE SET
    power_min_kw = EXCLUDED.power_min_kw,
    power_max_kw = EXCLUDED.power_max_kw,
    data_confidence = EXCLUDED.data_confidence;

INSERT INTO kb_engine_models (id, series_id, model_name, rpm_min, rpm_max, power_min_kw, power_max_kw, cylinders, configuration, fuel_types, emission_tier, is_current_production, data_source, data_confidence)
VALUES ('25d4de31-ecb1-437a-bb95-b9159b48888b', '343b2d7e-4766-4d88-bbe2-80ca5c45d8fd', 'Cat 3508C', 1200, 1600, 746, 895, 8, 'V', '["diesel", "mdo", "mgo"]', 'IMO Tier II', TRUE, 'manufacturer_datasheet', 0.9)
ON CONFLICT (model_name) DO UPDATE SET
    power_min_kw = EXCLUDED.power_min_kw,
    power_max_kw = EXCLUDED.power_max_kw,
    data_confidence = EXCLUDED.data_confidence;

INSERT INTO kb_engine_models (id, series_id, model_name, rpm_min, rpm_max, power_min_kw, power_max_kw, cylinders, configuration, fuel_types, emission_tier, is_current_production, data_source, data_confidence)
VALUES ('19c24f5d-219c-4acb-9b16-7bcc4c84efa2', '343b2d7e-4766-4d88-bbe2-80ca5c45d8fd', 'Cat 3512', 1200, 1800, 761, 1119, 12, 'V', '["diesel", "mdo", "mgo"]', 'IMO Tier II', TRUE, 'manufacturer_datasheet', 0.95)
ON CONFLICT (model_name) DO UPDATE SET
    power_min_kw = EXCLUDED.power_min_kw,
    power_max_kw = EXCLUDED.power_max_kw,
    data_confidence = EXCLUDED.data_confidence;

INSERT INTO kb_engine_models (id, series_id, model_name, rpm_min, rpm_max, power_min_kw, power_max_kw, cylinders, configuration, fuel_types, emission_tier, is_current_production, data_source, data_confidence)
VALUES ('3a759aa6-2b35-4f87-800c-1a2170cb1f08', '343b2d7e-4766-4d88-bbe2-80ca5c45d8fd', 'Cat 3512B', 1600, 1800, 1044, 1400, 12, 'V', '["diesel", "mdo", "mgo"]', 'IMO Tier II', TRUE, 'manufacturer_datasheet', 0.9)
ON CONFLICT (model_name) DO UPDATE SET
    power_min_kw = EXCLUDED.power_min_kw,
    power_max_kw = EXCLUDED.power_max_kw,
    data_confidence = EXCLUDED.data_confidence;

INSERT INTO kb_engine_models (id, series_id, model_name, rpm_min, rpm_max, power_min_kw, power_max_kw, cylinders, configuration, fuel_types, emission_tier, is_current_production, data_source, data_confidence)
VALUES ('59d31690-feaa-487a-b8ff-abb7674db644', '343b2d7e-4766-4d88-bbe2-80ca5c45d8fd', 'Cat 3516', 1200, 1800, 1011, 1492, 16, 'V', '["diesel", "mdo", "mgo"]', 'IMO Tier II', TRUE, 'manufacturer_datasheet', 0.95)
ON CONFLICT (model_name) DO UPDATE SET
    power_min_kw = EXCLUDED.power_min_kw,
    power_max_kw = EXCLUDED.power_max_kw,
    data_confidence = EXCLUDED.data_confidence;

INSERT INTO kb_engine_models (id, series_id, model_name, rpm_min, rpm_max, power_min_kw, power_max_kw, cylinders, configuration, fuel_types, emission_tier, is_current_production, data_source, data_confidence)
VALUES ('11e485be-6769-4789-a005-dab0b353933c', '343b2d7e-4766-4d88-bbe2-80ca5c45d8fd', 'Cat 3516B', 1600, 1800, 1340, 1680, 16, 'V', '["diesel", "mdo", "mgo"]', 'IMO Tier II', TRUE, 'manufacturer_datasheet', 0.9)
ON CONFLICT (model_name) DO UPDATE SET
    power_min_kw = EXCLUDED.power_min_kw,
    power_max_kw = EXCLUDED.power_max_kw,
    data_confidence = EXCLUDED.data_confidence;

INSERT INTO kb_engine_models (id, series_id, model_name, rpm_min, rpm_max, power_min_kw, power_max_kw, cylinders, configuration, fuel_types, emission_tier, is_current_production, data_source, data_confidence)
VALUES ('7e48efbf-a53b-4272-a828-3de16b1d111c', '343b2d7e-4766-4d88-bbe2-80ca5c45d8fd', 'Cat 3516C', 1600, 1800, 2000, 2525, 16, 'V', '["diesel", "mdo", "mgo"]', 'IMO Tier II', TRUE, 'manufacturer_datasheet', 0.9)
ON CONFLICT (model_name) DO UPDATE SET
    power_min_kw = EXCLUDED.power_min_kw,
    power_max_kw = EXCLUDED.power_max_kw,
    data_confidence = EXCLUDED.data_confidence;

INSERT INTO kb_engine_models (id, series_id, model_name, rpm_min, rpm_max, power_min_kw, power_max_kw, cylinders, configuration, fuel_types, emission_tier, is_current_production, data_source, data_confidence)
VALUES ('8ed27dbc-2170-4e22-8512-850cee9f8001', 'd62f9f8b-3681-4037-b724-3efe9da5837b', 'Cat C12.9', 1800, 2300, 373, 537, 6, 'inline', '["diesel", "mdo", "mgo"]', 'IMO Tier II', TRUE, 'manufacturer_datasheet', 0.9)
ON CONFLICT (model_name) DO UPDATE SET
    power_min_kw = EXCLUDED.power_min_kw,
    power_max_kw = EXCLUDED.power_max_kw,
    data_confidence = EXCLUDED.data_confidence;

INSERT INTO kb_engine_models (id, series_id, model_name, rpm_min, rpm_max, power_min_kw, power_max_kw, cylinders, configuration, fuel_types, emission_tier, is_current_production, data_source, data_confidence)
VALUES ('f1d83cd9-6ed8-4eff-b38a-4ca9a8b63d77', '8a788232-cfe6-43f0-8059-69ddb30f2aa5', 'Cat C18', 1800, 2100, 447, 597, 6, 'inline', '["diesel", "mdo", "mgo"]', 'IMO Tier II', TRUE, 'manufacturer_datasheet', 0.95)
ON CONFLICT (model_name) DO UPDATE SET
    power_min_kw = EXCLUDED.power_min_kw,
    power_max_kw = EXCLUDED.power_max_kw,
    data_confidence = EXCLUDED.data_confidence;

INSERT INTO kb_engine_models (id, series_id, model_name, rpm_min, rpm_max, power_min_kw, power_max_kw, cylinders, configuration, fuel_types, emission_tier, is_current_production, data_source, data_confidence)
VALUES ('f53c7c25-a699-4b85-b055-3514ed94c0ac', '8a788232-cfe6-43f0-8059-69ddb30f2aa5', 'Cat C18 ACERT', 1800, 2100, 533, 803, 6, 'inline', '["diesel", "mdo", "mgo"]', 'IMO Tier II', TRUE, 'manufacturer_datasheet', 0.9)
ON CONFLICT (model_name) DO UPDATE SET
    power_min_kw = EXCLUDED.power_min_kw,
    power_max_kw = EXCLUDED.power_max_kw,
    data_confidence = EXCLUDED.data_confidence;

INSERT INTO kb_engine_models (id, series_id, model_name, rpm_min, rpm_max, power_min_kw, power_max_kw, cylinders, configuration, fuel_types, emission_tier, is_current_production, data_source, data_confidence)
VALUES ('f4227ce4-738b-4ff9-9978-7685feb7e668', 'b1776572-488a-410a-9389-c1f0c87dd5b4', 'Cat C32', 1800, 2300, 746, 1417, 12, 'V', '["diesel", "mdo", "mgo"]', 'IMO Tier II', TRUE, 'manufacturer_datasheet', 0.95)
ON CONFLICT (model_name) DO UPDATE SET
    power_min_kw = EXCLUDED.power_min_kw,
    power_max_kw = EXCLUDED.power_max_kw,
    data_confidence = EXCLUDED.data_confidence;

INSERT INTO kb_engine_models (id, series_id, model_name, rpm_min, rpm_max, power_min_kw, power_max_kw, cylinders, configuration, fuel_types, emission_tier, is_current_production, data_source, data_confidence)
VALUES ('c4f75f6a-f1a5-4362-b863-15a89ade282d', 'b1776572-488a-410a-9389-c1f0c87dd5b4', 'Cat C32B', 2300, 2300, 1193, 1491, 12, 'V', '["diesel", "mdo", "mgo"]', 'IMO Tier II', TRUE, 'manufacturer_datasheet', 0.9)
ON CONFLICT (model_name) DO UPDATE SET
    power_min_kw = EXCLUDED.power_min_kw,
    power_max_kw = EXCLUDED.power_max_kw,
    data_confidence = EXCLUDED.data_confidence;

INSERT INTO kb_engine_models (id, series_id, model_name, rpm_min, rpm_max, power_min_kw, power_max_kw, cylinders, configuration, fuel_types, emission_tier, is_current_production, data_source, data_confidence)
VALUES ('8100cada-ae29-48da-a2be-c7be71375372', 'a74023e6-4746-44d8-9d49-1fbbdaec2697', 'MAN D2676 LE', 1800, 2100, 331, 537, 6, 'inline', '["diesel", "mdo", "mgo"]', 'IMO Tier II', TRUE, 'manufacturer_datasheet', 0.9)
ON CONFLICT (model_name) DO UPDATE SET
    power_min_kw = EXCLUDED.power_min_kw,
    power_max_kw = EXCLUDED.power_max_kw,
    data_confidence = EXCLUDED.data_confidence;

INSERT INTO kb_engine_models (id, series_id, model_name, rpm_min, rpm_max, power_min_kw, power_max_kw, cylinders, configuration, fuel_types, emission_tier, is_current_production, data_source, data_confidence)
VALUES ('05a375e5-f410-4d24-aa89-14fde8196bd4', '06a56a16-cd1f-411b-9a79-17609637f5d0', 'MAN D2862 LE463', 2100, 2100, 735, 1044, 12, 'V', '["diesel", "mdo", "mgo"]', 'IMO Tier II', TRUE, 'manufacturer_datasheet', 0.95)
ON CONFLICT (model_name) DO UPDATE SET
    power_min_kw = EXCLUDED.power_min_kw,
    power_max_kw = EXCLUDED.power_max_kw,
    data_confidence = EXCLUDED.data_confidence;

INSERT INTO kb_engine_models (id, series_id, model_name, rpm_min, rpm_max, power_min_kw, power_max_kw, cylinders, configuration, fuel_types, emission_tier, is_current_production, data_source, data_confidence)
VALUES ('09c31ebb-e6b4-4a88-bc54-9fbe8d17b558', '06a56a16-cd1f-411b-9a79-17609637f5d0', 'MAN D2862 LE443', 2100, 2100, 882, 1176, 12, 'V', '["diesel", "mdo", "mgo"]', 'IMO Tier II', TRUE, 'manufacturer_datasheet', 0.9)
ON CONFLICT (model_name) DO UPDATE SET
    power_min_kw = EXCLUDED.power_min_kw,
    power_max_kw = EXCLUDED.power_max_kw,
    data_confidence = EXCLUDED.data_confidence;

INSERT INTO kb_engine_models (id, series_id, model_name, rpm_min, rpm_max, power_min_kw, power_max_kw, cylinders, configuration, fuel_types, emission_tier, is_current_production, data_source, data_confidence)
VALUES ('f51f008b-df8e-49d1-bbec-716a3937ee46', '73a4f665-6d59-4c33-9993-eeff7057e24a', 'MAN D2868 LE433', 2100, 2300, 441, 882, 8, 'V', '["diesel", "mdo", "mgo"]', 'IMO Tier II', TRUE, 'manufacturer_datasheet', 0.9)
ON CONFLICT (model_name) DO UPDATE SET
    power_min_kw = EXCLUDED.power_min_kw,
    power_max_kw = EXCLUDED.power_max_kw,
    data_confidence = EXCLUDED.data_confidence;

INSERT INTO kb_engine_models (id, series_id, model_name, rpm_min, rpm_max, power_min_kw, power_max_kw, cylinders, configuration, fuel_types, emission_tier, is_current_production, data_source, data_confidence)
VALUES ('419318d5-f6c6-4f1a-83a5-8d05177173f0', '73a4f665-6d59-4c33-9993-eeff7057e24a', 'MAN D2868 LE423', 2100, 2100, 735, 993, 8, 'V', '["diesel", "mdo", "mgo"]', 'IMO Tier II', TRUE, 'manufacturer_datasheet', 0.9)
ON CONFLICT (model_name) DO UPDATE SET
    power_min_kw = EXCLUDED.power_min_kw,
    power_max_kw = EXCLUDED.power_max_kw,
    data_confidence = EXCLUDED.data_confidence;

INSERT INTO kb_engine_models (id, series_id, model_name, rpm_min, rpm_max, power_min_kw, power_max_kw, cylinders, configuration, fuel_types, emission_tier, is_current_production, data_source, data_confidence)
VALUES ('ed84a3ee-86ce-4f4a-a0c0-7df785ef2a32', '1d4b9689-3f30-4549-95e0-f2646c7e8dad', 'MAN V12-2000', 1800, 2100, 1044, 1324, 12, 'V', '["diesel", "mdo", "mgo"]', 'IMO Tier II', TRUE, 'manufacturer_datasheet', 0.9)
ON CONFLICT (model_name) DO UPDATE SET
    power_min_kw = EXCLUDED.power_min_kw,
    power_max_kw = EXCLUDED.power_max_kw,
    data_confidence = EXCLUDED.data_confidence;

INSERT INTO kb_engine_models (id, series_id, model_name, rpm_min, rpm_max, power_min_kw, power_max_kw, cylinders, configuration, fuel_types, emission_tier, is_current_production, data_source, data_confidence)
VALUES ('5e96f00a-1022-4a72-be7e-5720362ce4aa', '1d4b9689-3f30-4549-95e0-f2646c7e8dad', 'MAN V12-2000CR', 1800, 2100, 1193, 1471, 12, 'V', '["diesel", "mdo", "mgo"]', 'IMO Tier II', TRUE, 'manufacturer_datasheet', 0.9)
ON CONFLICT (model_name) DO UPDATE SET
    power_min_kw = EXCLUDED.power_min_kw,
    power_max_kw = EXCLUDED.power_max_kw,
    data_confidence = EXCLUDED.data_confidence;

INSERT INTO kb_engine_models (id, series_id, model_name, rpm_min, rpm_max, power_min_kw, power_max_kw, cylinders, configuration, fuel_types, emission_tier, is_current_production, data_source, data_confidence)
VALUES ('c57ad681-de44-4603-9b0e-69f135526d35', 'ea7d30d4-d65a-4357-8daa-9f66f222dff9', 'Volvo Penta D11', 1800, 2300, 298, 406, 6, 'inline', '["diesel", "mdo", "mgo"]', 'IMO Tier II', TRUE, 'manufacturer_datasheet', 0.9)
ON CONFLICT (model_name) DO UPDATE SET
    power_min_kw = EXCLUDED.power_min_kw,
    power_max_kw = EXCLUDED.power_max_kw,
    data_confidence = EXCLUDED.data_confidence;

INSERT INTO kb_engine_models (id, series_id, model_name, rpm_min, rpm_max, power_min_kw, power_max_kw, cylinders, configuration, fuel_types, emission_tier, is_current_production, data_source, data_confidence)
VALUES ('d3473c61-f4ae-48f1-9da8-f4e46450d108', 'dab7fbf4-eda5-4603-a3f5-6942fed6f069', 'Volvo Penta D13-IPS1200', 2300, 2400, 588, 662, 6, 'inline', '["diesel", "mdo", "mgo"]', 'IMO Tier II', TRUE, 'manufacturer_datasheet', 0.9)
ON CONFLICT (model_name) DO UPDATE SET
    power_min_kw = EXCLUDED.power_min_kw,
    power_max_kw = EXCLUDED.power_max_kw,
    data_confidence = EXCLUDED.data_confidence;

INSERT INTO kb_engine_models (id, series_id, model_name, rpm_min, rpm_max, power_min_kw, power_max_kw, cylinders, configuration, fuel_types, emission_tier, is_current_production, data_source, data_confidence)
VALUES ('c1fd75fb-566e-439b-bcb7-0c1d1d98fb78', 'dab7fbf4-eda5-4603-a3f5-6942fed6f069', 'Volvo Penta D13-IPS1350', 2300, 2400, 662, 735, 6, 'inline', '["diesel", "mdo", "mgo"]', 'IMO Tier II', TRUE, 'manufacturer_datasheet', 0.95)
ON CONFLICT (model_name) DO UPDATE SET
    power_min_kw = EXCLUDED.power_min_kw,
    power_max_kw = EXCLUDED.power_max_kw,
    data_confidence = EXCLUDED.data_confidence;

INSERT INTO kb_engine_models (id, series_id, model_name, rpm_min, rpm_max, power_min_kw, power_max_kw, cylinders, configuration, fuel_types, emission_tier, is_current_production, data_source, data_confidence)
VALUES ('75ffb79d-253e-4457-b4f1-807466e487d8', 'dab7fbf4-eda5-4603-a3f5-6942fed6f069', 'Volvo Penta D13-800', 2300, 2300, 515, 588, 6, 'inline', '["diesel", "mdo", "mgo"]', 'IMO Tier II', TRUE, 'manufacturer_datasheet', 0.9)
ON CONFLICT (model_name) DO UPDATE SET
    power_min_kw = EXCLUDED.power_min_kw,
    power_max_kw = EXCLUDED.power_max_kw,
    data_confidence = EXCLUDED.data_confidence;

INSERT INTO kb_engine_models (id, series_id, model_name, rpm_min, rpm_max, power_min_kw, power_max_kw, cylinders, configuration, fuel_types, emission_tier, is_current_production, data_source, data_confidence)
VALUES ('f4d21023-40e7-458c-9df7-c7fe4dba356d', 'dab7fbf4-eda5-4603-a3f5-6942fed6f069', 'Volvo Penta D13 MH', 2100, 2300, 625, 735, 6, 'inline', '["diesel", "mdo", "mgo"]', 'IMO Tier II', TRUE, 'manufacturer_datasheet', 0.9)
ON CONFLICT (model_name) DO UPDATE SET
    power_min_kw = EXCLUDED.power_min_kw,
    power_max_kw = EXCLUDED.power_max_kw,
    data_confidence = EXCLUDED.data_confidence;

INSERT INTO kb_engine_models (id, series_id, model_name, rpm_min, rpm_max, power_min_kw, power_max_kw, cylinders, configuration, fuel_types, emission_tier, is_current_production, data_source, data_confidence)
VALUES ('ecd4e332-c279-46b2-b1a9-eb7dd3b85d5e', 'dadfd1ca-0928-4d50-be4c-2c4c2cac2bae', 'Yanmar 6AYM-ETE', 1900, 1900, 485, 563, 6, 'inline', '["diesel", "mdo", "mgo"]', 'IMO Tier II', TRUE, 'manufacturer_datasheet', 0.95)
ON CONFLICT (model_name) DO UPDATE SET
    power_min_kw = EXCLUDED.power_min_kw,
    power_max_kw = EXCLUDED.power_max_kw,
    data_confidence = EXCLUDED.data_confidence;

INSERT INTO kb_engine_models (id, series_id, model_name, rpm_min, rpm_max, power_min_kw, power_max_kw, cylinders, configuration, fuel_types, emission_tier, is_current_production, data_source, data_confidence)
VALUES ('7f9b5b17-7199-40e8-bc6b-a151c404fe2d', 'dadfd1ca-0928-4d50-be4c-2c4c2cac2bae', 'Yanmar 6AYEM-GT', 1840, 2000, 485, 749, 6, 'inline', '["diesel", "mdo", "mgo"]', 'IMO Tier II', TRUE, 'manufacturer_datasheet', 0.95)
ON CONFLICT (model_name) DO UPDATE SET
    power_min_kw = EXCLUDED.power_min_kw,
    power_max_kw = EXCLUDED.power_max_kw,
    data_confidence = EXCLUDED.data_confidence;

INSERT INTO kb_engine_models (id, series_id, model_name, rpm_min, rpm_max, power_min_kw, power_max_kw, cylinders, configuration, fuel_types, emission_tier, is_current_production, data_source, data_confidence)
VALUES ('0066c62d-fc7b-4db4-98cc-ca31b27f9967', '8f01a1db-7f17-4e66-aac0-5d31cf30d9b4', 'Yanmar 8AYM-WET', 1900, 1900, 637, 716, 8, 'V', '["diesel", "mdo", "mgo"]', 'IMO Tier II', TRUE, 'manufacturer_datasheet', 0.9)
ON CONFLICT (model_name) DO UPDATE SET
    power_min_kw = EXCLUDED.power_min_kw,
    power_max_kw = EXCLUDED.power_max_kw,
    data_confidence = EXCLUDED.data_confidence;

INSERT INTO kb_engine_models (id, series_id, model_name, rpm_min, rpm_max, power_min_kw, power_max_kw, cylinders, configuration, fuel_types, emission_tier, is_current_production, data_source, data_confidence)
VALUES ('f17c58e0-edd1-4ab5-b635-11bef5bf7ffe', '5d20922a-3ad6-40f6-872f-396e2ecd9418', 'Yanmar 12AYM-WGT', 1900, 1900, 955, 1074, 12, 'V', '["diesel", "mdo", "mgo"]', 'IMO Tier II', TRUE, 'manufacturer_datasheet', 0.9)
ON CONFLICT (model_name) DO UPDATE SET
    power_min_kw = EXCLUDED.power_min_kw,
    power_max_kw = EXCLUDED.power_max_kw,
    data_confidence = EXCLUDED.data_confidence;

INSERT INTO kb_engine_models (id, series_id, model_name, rpm_min, rpm_max, power_min_kw, power_max_kw, cylinders, configuration, fuel_types, emission_tier, is_current_production, data_source, data_confidence)
VALUES ('f95d596e-725d-47f1-9a56-08d41a40dca9', 'c10b4323-c1da-41a9-a8eb-4a2c948f2423', 'WEICHAI WP13', 1800, 2100, 368, 537, 6, 'inline', '["diesel", "mdo", "mgo"]', 'IMO Tier II', TRUE, 'manufacturer_datasheet', 0.85)
ON CONFLICT (model_name) DO UPDATE SET
    power_min_kw = EXCLUDED.power_min_kw,
    power_max_kw = EXCLUDED.power_max_kw,
    data_confidence = EXCLUDED.data_confidence;

INSERT INTO kb_engine_models (id, series_id, model_name, rpm_min, rpm_max, power_min_kw, power_max_kw, cylinders, configuration, fuel_types, emission_tier, is_current_production, data_source, data_confidence)
VALUES ('7cd55999-1e5d-4531-a00b-b32018cd9ad4', 'afafd8db-ae7d-4462-a3d0-e71353760a57', 'WEICHAI WHM6160', 1500, 1800, 550, 1200, 6, 'V', '["diesel", "mdo"]', 'IMO Tier II', TRUE, 'manufacturer_datasheet', 0.85)
ON CONFLICT (model_name) DO UPDATE SET
    power_min_kw = EXCLUDED.power_min_kw,
    power_max_kw = EXCLUDED.power_max_kw,
    data_confidence = EXCLUDED.data_confidence;

INSERT INTO kb_engine_models (id, series_id, model_name, rpm_min, rpm_max, power_min_kw, power_max_kw, cylinders, configuration, fuel_types, emission_tier, is_current_production, data_source, data_confidence)
VALUES ('00bcfaa0-3fcb-4fca-a6a4-5505ef58f5cb', 'cc3d8bb9-edba-47d0-849f-d3a34d422c9e', 'WEICHAI 12M33', 1500, 1800, 1100, 2200, 12, 'V', '["diesel", "mdo"]', 'IMO Tier II', TRUE, 'manufacturer_datasheet', 0.8)
ON CONFLICT (model_name) DO UPDATE SET
    power_min_kw = EXCLUDED.power_min_kw,
    power_max_kw = EXCLUDED.power_max_kw,
    data_confidence = EXCLUDED.data_confidence;

INSERT INTO kb_engine_models (id, series_id, model_name, rpm_min, rpm_max, power_min_kw, power_max_kw, cylinders, configuration, fuel_types, emission_tier, is_current_production, data_source, data_confidence)
VALUES ('4e8dad85-5981-4b38-9e90-d3fb9eae62de', '2291079c-bd06-40b4-a8b2-d45f46fa799e', 'FPT Cursor 13', 1800, 2100, 368, 509, 6, 'inline', '["diesel", "mdo", "mgo"]', 'IMO Tier II', TRUE, 'manufacturer_datasheet', 0.9)
ON CONFLICT (model_name) DO UPDATE SET
    power_min_kw = EXCLUDED.power_min_kw,
    power_max_kw = EXCLUDED.power_max_kw,
    data_confidence = EXCLUDED.data_confidence;

INSERT INTO kb_engine_models (id, series_id, model_name, rpm_min, rpm_max, power_min_kw, power_max_kw, cylinders, configuration, fuel_types, emission_tier, is_current_production, data_source, data_confidence)
VALUES ('e77bd64e-a2dc-4056-84ce-8023153fd40e', '2291079c-bd06-40b4-a8b2-d45f46fa799e', 'FPT Cursor 16', 1800, 2100, 485, 662, 6, 'inline', '["diesel", "mdo", "mgo"]', 'IMO Tier II', TRUE, 'manufacturer_datasheet', 0.9)
ON CONFLICT (model_name) DO UPDATE SET
    power_min_kw = EXCLUDED.power_min_kw,
    power_max_kw = EXCLUDED.power_max_kw,
    data_confidence = EXCLUDED.data_confidence;

INSERT INTO kb_engine_models (id, series_id, model_name, rpm_min, rpm_max, power_min_kw, power_max_kw, cylinders, configuration, fuel_types, emission_tier, is_current_production, data_source, data_confidence)
VALUES ('c6ec290d-5893-44bd-9c1a-2dd6bfe90397', '5e780e4a-bdfc-428c-a07b-2d196cce08f4', 'Scania DI13', 1800, 2100, 405, 588, 6, 'inline', '["diesel", "mdo", "mgo"]', 'IMO Tier II', TRUE, 'manufacturer_datasheet', 0.9)
ON CONFLICT (model_name) DO UPDATE SET
    power_min_kw = EXCLUDED.power_min_kw,
    power_max_kw = EXCLUDED.power_max_kw,
    data_confidence = EXCLUDED.data_confidence;

INSERT INTO kb_engine_models (id, series_id, model_name, rpm_min, rpm_max, power_min_kw, power_max_kw, cylinders, configuration, fuel_types, emission_tier, is_current_production, data_source, data_confidence)
VALUES ('33701d9d-614d-4335-bab9-d9d35a3974e8', '474b060c-efc2-48da-a188-b5e1fb206f6a', 'Scania DI16', 1800, 2100, 588, 809, 8, 'V', '["diesel", "mdo", "mgo"]', 'IMO Tier II', TRUE, 'manufacturer_datasheet', 0.9)
ON CONFLICT (model_name) DO UPDATE SET
    power_min_kw = EXCLUDED.power_min_kw,
    power_max_kw = EXCLUDED.power_max_kw,
    data_confidence = EXCLUDED.data_confidence;

INSERT INTO kb_engine_models (id, series_id, model_name, rpm_min, rpm_max, power_min_kw, power_max_kw, cylinders, configuration, fuel_types, emission_tier, is_current_production, data_source, data_confidence)
VALUES ('182c7e21-e3de-4760-8a2b-3518e16af990', '91709473-6c72-4ae5-86c3-f847ab32af38', 'Wartsila 6L14', 1500, 1500, 735, 882, 6, 'inline', '["diesel", "mdo", "mgo"]', 'IMO Tier II', TRUE, 'manufacturer_datasheet', 0.85)
ON CONFLICT (model_name) DO UPDATE SET
    power_min_kw = EXCLUDED.power_min_kw,
    power_max_kw = EXCLUDED.power_max_kw,
    data_confidence = EXCLUDED.data_confidence;

INSERT INTO kb_engine_models (id, series_id, model_name, rpm_min, rpm_max, power_min_kw, power_max_kw, cylinders, configuration, fuel_types, emission_tier, is_current_production, data_source, data_confidence)
VALUES ('732940ee-4556-4a92-80ce-7dd0dc33465a', '91709473-6c72-4ae5-86c3-f847ab32af38', 'Wartsila 8L14', 1500, 1500, 980, 1176, 8, 'inline', '["diesel", "mdo", "mgo"]', 'IMO Tier II', TRUE, 'manufacturer_datasheet', 0.85)
ON CONFLICT (model_name) DO UPDATE SET
    power_min_kw = EXCLUDED.power_min_kw,
    power_max_kw = EXCLUDED.power_max_kw,
    data_confidence = EXCLUDED.data_confidence;

INSERT INTO kb_engine_models (id, series_id, model_name, rpm_min, rpm_max, power_min_kw, power_max_kw, cylinders, configuration, fuel_types, emission_tier, is_current_production, data_source, data_confidence)
VALUES ('3e396371-8daf-45ac-a2e4-ac8602d120a4', '91709473-6c72-4ae5-86c3-f847ab32af38', 'Wartsila 12V14', 1200, 1200, 1470, 1764, 12, 'V', '["diesel", "mdo", "mgo"]', 'IMO Tier II', TRUE, 'manufacturer_datasheet', 0.85)
ON CONFLICT (model_name) DO UPDATE SET
    power_min_kw = EXCLUDED.power_min_kw,
    power_max_kw = EXCLUDED.power_max_kw,
    data_confidence = EXCLUDED.data_confidence;

INSERT INTO kb_engine_models (id, series_id, model_name, rpm_min, rpm_max, power_min_kw, power_max_kw, cylinders, configuration, fuel_types, emission_tier, is_current_production, data_source, data_confidence)
VALUES ('a699f72f-d3a2-4886-91f9-875921b2f960', '21ba28fe-58a7-411a-8dea-524d96297b11', 'Wartsila 6L20', 1200, 1200, 1000, 1200, 6, 'inline', '["diesel", "mdo", "mgo"]', 'IMO Tier II', TRUE, 'manufacturer_datasheet', 0.85)
ON CONFLICT (model_name) DO UPDATE SET
    power_min_kw = EXCLUDED.power_min_kw,
    power_max_kw = EXCLUDED.power_max_kw,
    data_confidence = EXCLUDED.data_confidence;

INSERT INTO kb_engine_models (id, series_id, model_name, rpm_min, rpm_max, power_min_kw, power_max_kw, cylinders, configuration, fuel_types, emission_tier, is_current_production, data_source, data_confidence)
VALUES ('ba74b030-e94f-42c7-ac2c-c835b18171fb', '21ba28fe-58a7-411a-8dea-524d96297b11', 'Wartsila 8L20', 1200, 1200, 1333, 1600, 8, 'inline', '["diesel", "mdo", "mgo"]', 'IMO Tier II', TRUE, 'manufacturer_datasheet', 0.85)
ON CONFLICT (model_name) DO UPDATE SET
    power_min_kw = EXCLUDED.power_min_kw,
    power_max_kw = EXCLUDED.power_max_kw,
    data_confidence = EXCLUDED.data_confidence;

INSERT INTO kb_engine_models (id, series_id, model_name, rpm_min, rpm_max, power_min_kw, power_max_kw, cylinders, configuration, fuel_types, emission_tier, is_current_production, data_source, data_confidence)
VALUES ('dd5ed6e3-5235-4faf-ac37-2d49ea244248', '21ba28fe-58a7-411a-8dea-524d96297b11', 'Wartsila 9L20', 1200, 1200, 1500, 1800, 9, 'inline', '["diesel", "mdo", "mgo"]', 'IMO Tier II', TRUE, 'manufacturer_datasheet', 0.85)
ON CONFLICT (model_name) DO UPDATE SET
    power_min_kw = EXCLUDED.power_min_kw,
    power_max_kw = EXCLUDED.power_max_kw,
    data_confidence = EXCLUDED.data_confidence;

-- =============================================================================
-- ENGINE RATINGS (VERIFIED from engine_master_data.py)
-- =============================================================================

INSERT INTO kb_engine_ratings (
    id, engine_model_id, rating_designation, rating_name, duty_class, iso_classification,
    harmonized_duty_class, oem_rating_code,
    power_kw, power_hp, rpm, load_factor_min, load_factor_max, annual_hours_min, annual_hours_max,
    dry_weight_kg, length_mm, width_mm, height_mm, power_density_kw_per_kg,
    fuel_types, emission_tier, application_profiles, primary_applications,
    availability_status, regions_available, data_source, data_source_url, data_source_document,
    data_confidence, last_verified, verified_by, notes
) VALUES (
    '14770674-157b-4d82-a106-cdfb3b87adb7', 'f54a755f-b3fc-497d-98de-ae25e58d9686', 'M72',
    'MTU 8V 2000 M72', 'heavy_duty', 'not_applicable',
    'HVY', 'M72',
    720, 965.52, 2250,
    0.4, 0.8,
    3000, 5000,
    NULL, NULL,
    NULL, NULL, NULL,
    '["mgo", "diesel", "mdo"]', 'IMO Tier II',
    '["patrol", "crew_transfer", "commercial_workboat"]', '["patrol", "crew_transfer", "commercial_workboat"]',
    'available', '["APAC", "EMEA", "Americas"]',
    'manufacturer_datasheet', 'https://www.mtu-solutions.com/',
    'MTU 8V 2000 M72 specification sheet', 0.95,
    NOW(), 'engine_master_data', 'MTU 8V 2000 M72 high-speed marine diesel engine manufactured by MTU, a Rolls-Royce Power Systems brand (RRPS). 8-cylinder V-configuration delivering 720 kW (965 bhp) at 2250 RPM. Series 2000 platform for fast patrol boats, crew transfer vessels, and luxury yachts. Common rail fuel injection, turbocharging with charge air cooling. IMO Tier II certified. Compact footprint ideal for twin or triple installations. MTU ValueCare service packages available. Also known as MTU 8V2000M72 or 8V-2000-M72.'
)
ON CONFLICT (engine_model_id, rating_designation) DO UPDATE SET
    power_kw = EXCLUDED.power_kw,
    power_hp = EXCLUDED.power_hp,
    duty_class = EXCLUDED.duty_class,
    harmonized_duty_class = EXCLUDED.harmonized_duty_class,
    oem_rating_code = EXCLUDED.oem_rating_code,
    dry_weight_kg = EXCLUDED.dry_weight_kg,
    length_mm = EXCLUDED.length_mm,
    width_mm = EXCLUDED.width_mm,
    height_mm = EXCLUDED.height_mm,
    power_density_kw_per_kg = EXCLUDED.power_density_kw_per_kg,
    last_verified = NOW(),
    verified_by = EXCLUDED.verified_by;

INSERT INTO kb_engine_ratings (
    id, engine_model_id, rating_designation, rating_name, duty_class, iso_classification,
    harmonized_duty_class, oem_rating_code,
    power_kw, power_hp, rpm, load_factor_min, load_factor_max, annual_hours_min, annual_hours_max,
    dry_weight_kg, length_mm, width_mm, height_mm, power_density_kw_per_kg,
    fuel_types, emission_tier, application_profiles, primary_applications,
    availability_status, regions_available, data_source, data_source_url, data_source_document,
    data_confidence, last_verified, verified_by, notes
) VALUES (
    'f475b238-1acd-47bd-b7fb-c005aa72c28d', '97cb8f68-b468-4b1a-9f34-34eda5382c5c', 'M72',
    'MTU 10V 2000 M72', 'heavy_duty', 'not_applicable',
    'HVY', 'M72',
    900, 1206.8999999999999, 2250,
    0.4, 0.8,
    3000, 5000,
    NULL, NULL,
    NULL, NULL, NULL,
    '["mgo", "diesel", "mdo"]', 'IMO Tier II',
    '["fast_ferry", "crew_boat", "pilot"]', '["fast_ferry", "crew_boat", "pilot"]',
    'available', '["APAC", "EMEA", "Americas"]',
    'manufacturer_datasheet', 'https://www.mtu-solutions.com/',
    'MTU 10V 2000 M72 specification sheet', 0.95,
    NOW(), 'engine_master_data', 'MTU 10V 2000 M72 high-speed marine diesel engine by MTU Rolls-Royce Power Systems. 10-cylinder V-configuration producing 900 kW (1205 bhp) at 2250 RPM. Series 2000 platform for fast ferries, offshore crew boats, and pilot vessels. Features electronic engine management, common rail injection. IMO Tier II compliant. Popular choice for twin-engine fast craft applications. Also referred to as MTU 10V2000M72, 10V-2000-M72, or RRPS 10V2000.'
)
ON CONFLICT (engine_model_id, rating_designation) DO UPDATE SET
    power_kw = EXCLUDED.power_kw,
    power_hp = EXCLUDED.power_hp,
    duty_class = EXCLUDED.duty_class,
    harmonized_duty_class = EXCLUDED.harmonized_duty_class,
    oem_rating_code = EXCLUDED.oem_rating_code,
    dry_weight_kg = EXCLUDED.dry_weight_kg,
    length_mm = EXCLUDED.length_mm,
    width_mm = EXCLUDED.width_mm,
    height_mm = EXCLUDED.height_mm,
    power_density_kw_per_kg = EXCLUDED.power_density_kw_per_kg,
    last_verified = NOW(),
    verified_by = EXCLUDED.verified_by;

INSERT INTO kb_engine_ratings (
    id, engine_model_id, rating_designation, rating_name, duty_class, iso_classification,
    harmonized_duty_class, oem_rating_code,
    power_kw, power_hp, rpm, load_factor_min, load_factor_max, annual_hours_min, annual_hours_max,
    dry_weight_kg, length_mm, width_mm, height_mm, power_density_kw_per_kg,
    fuel_types, emission_tier, application_profiles, primary_applications,
    availability_status, regions_available, data_source, data_source_url, data_source_document,
    data_confidence, last_verified, verified_by, notes
) VALUES (
    '41b5a27d-6d2d-4269-baef-9ae067c43118', 'c2423714-0c43-423a-9933-d2f23b92d74e', 'M93',
    'MTU 12V 2000 M93', 'light_duty', 'not_applicable',
    'LGT', 'M93',
    1340, 1796.94, 2450,
    0.0, 0.5,
    1000, 3000,
    2780, 1870,
    1295, 1350, 0.482,
    '["mgo", "diesel", "mdo"]', 'IMO Tier II',
    '["yacht", "fast_patrol", "fast_ferry"]', '["yacht", "fast_patrol", "fast_ferry"]',
    'available', '["APAC", "EMEA", "Americas"]',
    'manufacturer_datasheet', 'https://www.mtu-solutions.com/',
    'MTU 12V 2000 M93 specification sheet', 0.95,
    NOW(), 'engine_master_data', 'MTU 12V 2000 M93 high-speed marine diesel engine from Rolls-Royce Power Systems MTU. 12-cylinder V-configuration delivering 1340 kW (1800 bhp) at 2450 RPM. M93 rating for heavy-duty continuous operation. Series 2000 platform optimized for fast ferries, patrol boats, and offshore supply vessels. Advanced common rail injection with MDEC electronic controls. IMO Tier II certified. Excellent power-to-weight ratio. Known as MTU 12V2000M93 or 12V-2000-M93.'
)
ON CONFLICT (engine_model_id, rating_designation) DO UPDATE SET
    power_kw = EXCLUDED.power_kw,
    power_hp = EXCLUDED.power_hp,
    duty_class = EXCLUDED.duty_class,
    harmonized_duty_class = EXCLUDED.harmonized_duty_class,
    oem_rating_code = EXCLUDED.oem_rating_code,
    dry_weight_kg = EXCLUDED.dry_weight_kg,
    length_mm = EXCLUDED.length_mm,
    width_mm = EXCLUDED.width_mm,
    height_mm = EXCLUDED.height_mm,
    power_density_kw_per_kg = EXCLUDED.power_density_kw_per_kg,
    last_verified = NOW(),
    verified_by = EXCLUDED.verified_by;

INSERT INTO kb_engine_ratings (
    id, engine_model_id, rating_designation, rating_name, duty_class, iso_classification,
    harmonized_duty_class, oem_rating_code,
    power_kw, power_hp, rpm, load_factor_min, load_factor_max, annual_hours_min, annual_hours_max,
    dry_weight_kg, length_mm, width_mm, height_mm, power_density_kw_per_kg,
    fuel_types, emission_tier, application_profiles, primary_applications,
    availability_status, regions_available, data_source, data_source_url, data_source_document,
    data_confidence, last_verified, verified_by, notes
) VALUES (
    '038ab296-e666-42d8-9d5a-b97369b597ea', '0ff541a5-3a62-4232-aed4-220abe97eaa8', 'M93',
    'MTU 16V 2000 M93', 'light_duty', 'not_applicable',
    'LGT', 'M93',
    1790, 2400.39, 2450,
    0.0, 0.5,
    1000, 3000,
    4570, 2330,
    1290, 1420, 0.3917,
    '["mgo", "diesel", "mdo"]', 'IMO Tier II',
    '["yacht", "fast_ferry", "coast_guard"]', '["yacht", "fast_ferry", "coast_guard"]',
    'available', '["APAC", "EMEA", "Americas"]',
    'manufacturer_datasheet', 'https://www.mtu-solutions.com/',
    'MTU 16V 2000 M93 specification sheet', 0.95,
    NOW(), 'engine_master_data', 'MTU 16V 2000 M93 high-speed marine diesel engine by MTU Rolls-Royce Power Systems. 16-cylinder V-configuration producing 1790 kW (2400 bhp) at 2450 RPM. Flagship of the Series 2000 M93 heavy-duty range. Ideal for fast ferries, coast guard vessels, and luxury mega-yachts requiring high power density. Common rail fuel system, turbocharging with dual-stage charge air cooling. IMO Tier II compliant. Also known as MTU 16V2000M93 or 16V-2000-M93.'
)
ON CONFLICT (engine_model_id, rating_designation) DO UPDATE SET
    power_kw = EXCLUDED.power_kw,
    power_hp = EXCLUDED.power_hp,
    duty_class = EXCLUDED.duty_class,
    harmonized_duty_class = EXCLUDED.harmonized_duty_class,
    oem_rating_code = EXCLUDED.oem_rating_code,
    dry_weight_kg = EXCLUDED.dry_weight_kg,
    length_mm = EXCLUDED.length_mm,
    width_mm = EXCLUDED.width_mm,
    height_mm = EXCLUDED.height_mm,
    power_density_kw_per_kg = EXCLUDED.power_density_kw_per_kg,
    last_verified = NOW(),
    verified_by = EXCLUDED.verified_by;

INSERT INTO kb_engine_ratings (
    id, engine_model_id, rating_designation, rating_name, duty_class, iso_classification,
    harmonized_duty_class, oem_rating_code,
    power_kw, power_hp, rpm, load_factor_min, load_factor_max, annual_hours_min, annual_hours_max,
    dry_weight_kg, length_mm, width_mm, height_mm, power_density_kw_per_kg,
    fuel_types, emission_tier, application_profiles, primary_applications,
    availability_status, regions_available, data_source, data_source_url, data_source_document,
    data_confidence, last_verified, verified_by, notes
) VALUES (
    '90190d35-eb09-45ae-bfe2-054ea75e6eb3', '7777d2d7-111a-4fcb-858a-f9d2601542c6', 'M96',
    'MTU 16V 2000 M96', 'light_duty', 'not_applicable',
    'LGT', 'M96',
    1939, 2600.199, 2450,
    0.0, 0.5,
    1000, 3000,
    NULL, NULL,
    NULL, NULL, NULL,
    '["mgo", "diesel", "mdo"]', 'IMO Tier II',
    '["yacht", "fast_patrol", "naval"]', '["yacht", "fast_patrol", "naval"]',
    'available', '["APAC", "EMEA", "Americas"]',
    'manufacturer_datasheet', 'https://www.mtu-solutions.com/',
    'MTU 16V 2000 M96 specification sheet', 0.95,
    NOW(), 'engine_master_data', 'MTU 16V 2000 M96 high-speed marine diesel engine, latest Series 2000 variant from Rolls-Royce Power Systems MTU. 16-cylinder V-configuration with 1939 kW (2600 bhp) peak output at 2450 RPM. M96 rating indicates enhanced power for demanding applications. Used in high-speed ferries, naval patrol craft, and offshore vessels. Features latest common rail technology and optimized turbocharging. IMO Tier II certified. Also referred to as MTU 16V2000M96 or RRPS Series 2000.'
)
ON CONFLICT (engine_model_id, rating_designation) DO UPDATE SET
    power_kw = EXCLUDED.power_kw,
    power_hp = EXCLUDED.power_hp,
    duty_class = EXCLUDED.duty_class,
    harmonized_duty_class = EXCLUDED.harmonized_duty_class,
    oem_rating_code = EXCLUDED.oem_rating_code,
    dry_weight_kg = EXCLUDED.dry_weight_kg,
    length_mm = EXCLUDED.length_mm,
    width_mm = EXCLUDED.width_mm,
    height_mm = EXCLUDED.height_mm,
    power_density_kw_per_kg = EXCLUDED.power_density_kw_per_kg,
    last_verified = NOW(),
    verified_by = EXCLUDED.verified_by;

INSERT INTO kb_engine_ratings (
    id, engine_model_id, rating_designation, rating_name, duty_class, iso_classification,
    harmonized_duty_class, oem_rating_code,
    power_kw, power_hp, rpm, load_factor_min, load_factor_max, annual_hours_min, annual_hours_max,
    dry_weight_kg, length_mm, width_mm, height_mm, power_density_kw_per_kg,
    fuel_types, emission_tier, application_profiles, primary_applications,
    availability_status, regions_available, data_source, data_source_url, data_source_document,
    data_confidence, last_verified, verified_by, notes
) VALUES (
    '0fde3189-466c-433e-a59e-3cb6d9f36f19', 'fe356bdc-76c7-4922-b535-69b7bfe4a52d', 'M63',
    'MTU 12V 4000 M63', 'continuous', 'not_applicable',
    'CON', 'M63',
    1500, 2011.5, 1600,
    0.8, 1.0,
    5000, 8000,
    NULL, NULL,
    NULL, NULL, NULL,
    '["mgo", "diesel", "mdo"]', 'IMO Tier II',
    '["cargo", "tanker", "dredger", "tug"]', '["cargo", "tanker", "dredger"]',
    'available', '["APAC", "EMEA", "Americas"]',
    'manufacturer_datasheet', 'https://www.mtu-solutions.com/',
    'MTU 12V 4000 M63 specification sheet', 0.9,
    NOW(), 'engine_master_data', 'MTU 12V 4000 M63 high-speed marine diesel engine from Rolls-Royce Power Systems. 12-cylinder V-configuration delivering 1500 kW (2012 bhp) at 1600-1800 RPM. Series 4000 platform for medium-duty applications including tugs, offshore vessels, and large yachts. M63 rating for light-duty operation with extended maintenance intervals. Features MTU ADEC electronic controls, common rail injection. IMO Tier II compliant. Also known as MTU 12V4000M63 or 12V-4000-M63.'
)
ON CONFLICT (engine_model_id, rating_designation) DO UPDATE SET
    power_kw = EXCLUDED.power_kw,
    power_hp = EXCLUDED.power_hp,
    duty_class = EXCLUDED.duty_class,
    harmonized_duty_class = EXCLUDED.harmonized_duty_class,
    oem_rating_code = EXCLUDED.oem_rating_code,
    dry_weight_kg = EXCLUDED.dry_weight_kg,
    length_mm = EXCLUDED.length_mm,
    width_mm = EXCLUDED.width_mm,
    height_mm = EXCLUDED.height_mm,
    power_density_kw_per_kg = EXCLUDED.power_density_kw_per_kg,
    last_verified = NOW(),
    verified_by = EXCLUDED.verified_by;

INSERT INTO kb_engine_ratings (
    id, engine_model_id, rating_designation, rating_name, duty_class, iso_classification,
    harmonized_duty_class, oem_rating_code,
    power_kw, power_hp, rpm, load_factor_min, load_factor_max, annual_hours_min, annual_hours_max,
    dry_weight_kg, length_mm, width_mm, height_mm, power_density_kw_per_kg,
    fuel_types, emission_tier, application_profiles, primary_applications,
    availability_status, regions_available, data_source, data_source_url, data_source_document,
    data_confidence, last_verified, verified_by, notes
) VALUES (
    '9b1b2a0b-e934-43de-a032-dcbc23f28964', '5db12a4a-856f-454f-9145-77f59c2fc2ec', 'M63',
    'MTU 16V 4000 M63', 'continuous', 'not_applicable',
    'CON', 'M63',
    2240, 3003.84, 1600,
    0.8, 1.0,
    5000, 8000,
    NULL, NULL,
    NULL, NULL, NULL,
    '["mgo", "diesel", "mdo"]', 'IMO Tier II',
    '["cargo", "tanker", "ferry", "tug"]', '["cargo", "tanker", "ferry"]',
    'available', '["APAC", "EMEA", "Americas"]',
    'manufacturer_datasheet', 'https://www.mtu-solutions.com/',
    'MTU 16V 4000 M63 specification sheet', 0.95,
    NOW(), 'engine_master_data', 'MTU 16V 4000 M63 high-speed marine diesel engine by MTU Rolls-Royce Power Systems. 16-cylinder V-configuration producing 1920-2240 kW (2575-3004 bhp) at 1600-1800 RPM. Series 4000 workhorse for commercial vessels, offshore support, and large motor yachts. M63 light-duty rating suitable for yachts and vessels with lower operating hours. Advanced common rail injection. IMO Tier II certified. Known as MTU 16V4000M63 or RRPS 16V4000.'
)
ON CONFLICT (engine_model_id, rating_designation) DO UPDATE SET
    power_kw = EXCLUDED.power_kw,
    power_hp = EXCLUDED.power_hp,
    duty_class = EXCLUDED.duty_class,
    harmonized_duty_class = EXCLUDED.harmonized_duty_class,
    oem_rating_code = EXCLUDED.oem_rating_code,
    dry_weight_kg = EXCLUDED.dry_weight_kg,
    length_mm = EXCLUDED.length_mm,
    width_mm = EXCLUDED.width_mm,
    height_mm = EXCLUDED.height_mm,
    power_density_kw_per_kg = EXCLUDED.power_density_kw_per_kg,
    last_verified = NOW(),
    verified_by = EXCLUDED.verified_by;

INSERT INTO kb_engine_ratings (
    id, engine_model_id, rating_designation, rating_name, duty_class, iso_classification,
    harmonized_duty_class, oem_rating_code,
    power_kw, power_hp, rpm, load_factor_min, load_factor_max, annual_hours_min, annual_hours_max,
    dry_weight_kg, length_mm, width_mm, height_mm, power_density_kw_per_kg,
    fuel_types, emission_tier, application_profiles, primary_applications,
    availability_status, regions_available, data_source, data_source_url, data_source_document,
    data_confidence, last_verified, verified_by, notes
) VALUES (
    'f6425317-e770-4864-bfeb-3bf08262e646', '7dfb3de9-71ee-41c7-88dc-6b44095faea6', 'M73',
    'MTU 12V 4000 M73', 'heavy_duty', 'not_applicable',
    'HVY', 'M73',
    2160, 2896.56, 1970,
    0.4, 0.8,
    3000, 5000,
    NULL, NULL,
    NULL, NULL, NULL,
    '["mgo", "diesel", "mdo"]', 'IMO Tier II',
    '["ferry", "patrol", "osv"]', '["ferry", "patrol", "osv"]',
    'available', '["APAC", "EMEA", "Americas"]',
    'manufacturer_datasheet', 'https://www.mtu-solutions.com/',
    'MTU 12V 4000 M73 specification sheet', 0.9,
    NOW(), 'engine_master_data', 'MTU 12V 4000 M73 high-speed marine diesel engine from Rolls-Royce Power Systems MTU. 12-cylinder V-configuration delivering 1920-2160 kW (2575-2895 bhp) at 1970-2050 RPM. M73 medium-duty rating for ferries, patrol boats, and offshore vessels. Series 4000 with optimized turbocharging for marine applications. IMO Tier II certified. Suitable for vessels requiring balance of power and economy. Also referred to as MTU 12V4000M73 or 12V-4000-M73.'
)
ON CONFLICT (engine_model_id, rating_designation) DO UPDATE SET
    power_kw = EXCLUDED.power_kw,
    power_hp = EXCLUDED.power_hp,
    duty_class = EXCLUDED.duty_class,
    harmonized_duty_class = EXCLUDED.harmonized_duty_class,
    oem_rating_code = EXCLUDED.oem_rating_code,
    dry_weight_kg = EXCLUDED.dry_weight_kg,
    length_mm = EXCLUDED.length_mm,
    width_mm = EXCLUDED.width_mm,
    height_mm = EXCLUDED.height_mm,
    power_density_kw_per_kg = EXCLUDED.power_density_kw_per_kg,
    last_verified = NOW(),
    verified_by = EXCLUDED.verified_by;

INSERT INTO kb_engine_ratings (
    id, engine_model_id, rating_designation, rating_name, duty_class, iso_classification,
    harmonized_duty_class, oem_rating_code,
    power_kw, power_hp, rpm, load_factor_min, load_factor_max, annual_hours_min, annual_hours_max,
    dry_weight_kg, length_mm, width_mm, height_mm, power_density_kw_per_kg,
    fuel_types, emission_tier, application_profiles, primary_applications,
    availability_status, regions_available, data_source, data_source_url, data_source_document,
    data_confidence, last_verified, verified_by, notes
) VALUES (
    'a7e6a845-cdf4-471c-9956-dd693415500e', '4e70e7e8-e858-4851-a612-1b642af0f890', 'M73',
    'MTU 16V 4000 M73', 'heavy_duty', 'not_applicable',
    'HVY', 'M73',
    2880, 3862.08, 1970,
    0.4, 0.8,
    3000, 5000,
    NULL, NULL,
    NULL, NULL, NULL,
    '["mgo", "diesel", "mdo"]', 'IMO Tier II',
    '["fast_ferry", "coast_guard", "naval"]', '["fast_ferry", "coast_guard", "naval"]',
    'available', '["APAC", "EMEA", "Americas"]',
    'manufacturer_datasheet', 'https://www.mtu-solutions.com/',
    'MTU 16V 4000 M73 specification sheet', 0.95,
    NOW(), 'engine_master_data', 'MTU 16V 4000 M73 high-speed marine diesel engine by Rolls-Royce Power Systems MTU. 16-cylinder V-configuration producing 2560-2880 kW (3435-3860 bhp) at 1970-2050 RPM. Popular choice for fast ferries, coast guard cutters, and naval patrol vessels. M73 medium-duty rating balances performance and durability. Series 4000 common rail technology with ADEC controls. IMO Tier II compliant. Known as MTU 16V4000M73 or RRPS Series 4000.'
)
ON CONFLICT (engine_model_id, rating_designation) DO UPDATE SET
    power_kw = EXCLUDED.power_kw,
    power_hp = EXCLUDED.power_hp,
    duty_class = EXCLUDED.duty_class,
    harmonized_duty_class = EXCLUDED.harmonized_duty_class,
    oem_rating_code = EXCLUDED.oem_rating_code,
    dry_weight_kg = EXCLUDED.dry_weight_kg,
    length_mm = EXCLUDED.length_mm,
    width_mm = EXCLUDED.width_mm,
    height_mm = EXCLUDED.height_mm,
    power_density_kw_per_kg = EXCLUDED.power_density_kw_per_kg,
    last_verified = NOW(),
    verified_by = EXCLUDED.verified_by;

INSERT INTO kb_engine_ratings (
    id, engine_model_id, rating_designation, rating_name, duty_class, iso_classification,
    harmonized_duty_class, oem_rating_code,
    power_kw, power_hp, rpm, load_factor_min, load_factor_max, annual_hours_min, annual_hours_max,
    dry_weight_kg, length_mm, width_mm, height_mm, power_density_kw_per_kg,
    fuel_types, emission_tier, application_profiles, primary_applications,
    availability_status, regions_available, data_source, data_source_url, data_source_document,
    data_confidence, last_verified, verified_by, notes
) VALUES (
    '61ffaac6-b627-4bf6-a530-9102e30c9446', '5ed90e32-9da0-4078-b4bc-ac2c991a7fa9', 'M93',
    'MTU 12V 4000 M93', 'light_duty', 'not_applicable',
    'LGT', 'M93',
    2580, 3459.7799999999997, 2100,
    0.0, 0.5,
    1000, 3000,
    7800, 3197,
    1630, 2103, 0.3308,
    '["mgo", "diesel", "mdo"]', 'IMO Tier II',
    '["yacht", "fast_ferry", "naval"]', '["yacht", "fast_ferry", "naval"]',
    'available', '["APAC", "EMEA", "Americas"]',
    'manufacturer_datasheet', 'https://www.mtu-solutions.com/',
    'MTU 12V 4000 M93 specification sheet', 0.95,
    NOW(), 'engine_master_data', 'MTU 12V 4000 M93 high-speed marine diesel engine from Rolls-Royce Power Systems. 12-cylinder V-configuration delivering 2340-2580 kW (3140-3460 bhp) at 2100 RPM. M93 heavy-duty rating for demanding commercial operations. Suited for offshore supply vessels, large ferries, and military applications. Features advanced common rail injection and two-stage turbocharging. IMO Tier II certified. Also known as MTU 12V4000M93 or 12V-4000-M93.'
)
ON CONFLICT (engine_model_id, rating_designation) DO UPDATE SET
    power_kw = EXCLUDED.power_kw,
    power_hp = EXCLUDED.power_hp,
    duty_class = EXCLUDED.duty_class,
    harmonized_duty_class = EXCLUDED.harmonized_duty_class,
    oem_rating_code = EXCLUDED.oem_rating_code,
    dry_weight_kg = EXCLUDED.dry_weight_kg,
    length_mm = EXCLUDED.length_mm,
    width_mm = EXCLUDED.width_mm,
    height_mm = EXCLUDED.height_mm,
    power_density_kw_per_kg = EXCLUDED.power_density_kw_per_kg,
    last_verified = NOW(),
    verified_by = EXCLUDED.verified_by;

INSERT INTO kb_engine_ratings (
    id, engine_model_id, rating_designation, rating_name, duty_class, iso_classification,
    harmonized_duty_class, oem_rating_code,
    power_kw, power_hp, rpm, load_factor_min, load_factor_max, annual_hours_min, annual_hours_max,
    dry_weight_kg, length_mm, width_mm, height_mm, power_density_kw_per_kg,
    fuel_types, emission_tier, application_profiles, primary_applications,
    availability_status, regions_available, data_source, data_source_url, data_source_document,
    data_confidence, last_verified, verified_by, notes
) VALUES (
    '404771df-18dd-4115-b616-3a41916324c1', 'b62207c6-718b-40b2-b352-de905854cca6', 'M93',
    'MTU 16V 4000 M93', 'light_duty', 'not_applicable',
    'LGT', 'M93',
    3440, 4613.04, 2100,
    0.0, 0.5,
    1000, 3000,
    NULL, NULL,
    NULL, NULL, NULL,
    '["mgo", "diesel", "mdo"]', 'IMO Tier II',
    '["yacht", "fast_ferry", "naval"]', '["yacht", "fast_ferry", "naval"]',
    'available', '["APAC", "EMEA", "Americas"]',
    'manufacturer_datasheet', 'https://www.mtu-solutions.com/',
    'MTU 16V 4000 M93 specification sheet', 0.95,
    NOW(), 'engine_master_data', 'MTU 16V 4000 M93 high-speed marine diesel engine by Rolls-Royce Power Systems MTU. 16-cylinder V-configuration producing 3120-3440 kW (4185-4615 bhp) at 2100 RPM. Heavy-duty M93 rating for high-utilization commercial vessels. Excellent choice for large fast ferries, offshore vessels, and naval craft. Two-stage turbocharging with charge air cooling. IMO Tier II compliant. Also referred to as MTU 16V4000M93 or RRPS 16V4000.'
)
ON CONFLICT (engine_model_id, rating_designation) DO UPDATE SET
    power_kw = EXCLUDED.power_kw,
    power_hp = EXCLUDED.power_hp,
    duty_class = EXCLUDED.duty_class,
    harmonized_duty_class = EXCLUDED.harmonized_duty_class,
    oem_rating_code = EXCLUDED.oem_rating_code,
    dry_weight_kg = EXCLUDED.dry_weight_kg,
    length_mm = EXCLUDED.length_mm,
    width_mm = EXCLUDED.width_mm,
    height_mm = EXCLUDED.height_mm,
    power_density_kw_per_kg = EXCLUDED.power_density_kw_per_kg,
    last_verified = NOW(),
    verified_by = EXCLUDED.verified_by;

INSERT INTO kb_engine_ratings (
    id, engine_model_id, rating_designation, rating_name, duty_class, iso_classification,
    harmonized_duty_class, oem_rating_code,
    power_kw, power_hp, rpm, load_factor_min, load_factor_max, annual_hours_min, annual_hours_max,
    dry_weight_kg, length_mm, width_mm, height_mm, power_density_kw_per_kg,
    fuel_types, emission_tier, application_profiles, primary_applications,
    availability_status, regions_available, data_source, data_source_url, data_source_document,
    data_confidence, last_verified, verified_by, notes
) VALUES (
    '18af809a-27ce-44d8-a3e1-0d5199546455', '62ada188-ff03-46f5-9454-83572039949b', 'M93',
    'MTU 20V 4000 M93', 'light_duty', 'not_applicable',
    'LGT', 'M93',
    4300, 5766.3, 2100,
    0.0, 0.5,
    1000, 3000,
    NULL, NULL,
    NULL, NULL, NULL,
    '["mgo", "diesel", "mdo"]', 'IMO Tier II',
    '["large_yacht", "fast_ferry", "naval"]', '["large_yacht", "fast_ferry", "naval"]',
    'available', '["APAC", "EMEA", "Americas"]',
    'manufacturer_datasheet', 'https://www.mtu-solutions.com/',
    'MTU 20V 4000 M93 specification sheet', 0.95,
    NOW(), 'engine_master_data', 'MTU 20V 4000 M93 high-speed marine diesel engine from Rolls-Royce Power Systems MTU. 20-cylinder V-configuration delivering 3900-4300 kW (5230-5766 bhp) at 2100 RPM. Flagship of the Series 4000 M93 heavy-duty range. Maximum power density for large fast ferries, mega-yachts, and naval vessels. Features advanced common rail injection, dual-stage turbocharging. IMO Tier II certified. Known as MTU 20V4000M93 or 20V-4000-M93.'
)
ON CONFLICT (engine_model_id, rating_designation) DO UPDATE SET
    power_kw = EXCLUDED.power_kw,
    power_hp = EXCLUDED.power_hp,
    duty_class = EXCLUDED.duty_class,
    harmonized_duty_class = EXCLUDED.harmonized_duty_class,
    oem_rating_code = EXCLUDED.oem_rating_code,
    dry_weight_kg = EXCLUDED.dry_weight_kg,
    length_mm = EXCLUDED.length_mm,
    width_mm = EXCLUDED.width_mm,
    height_mm = EXCLUDED.height_mm,
    power_density_kw_per_kg = EXCLUDED.power_density_kw_per_kg,
    last_verified = NOW(),
    verified_by = EXCLUDED.verified_by;

INSERT INTO kb_engine_ratings (
    id, engine_model_id, rating_designation, rating_name, duty_class, iso_classification,
    harmonized_duty_class, oem_rating_code,
    power_kw, power_hp, rpm, load_factor_min, load_factor_max, annual_hours_min, annual_hours_max,
    dry_weight_kg, length_mm, width_mm, height_mm, power_density_kw_per_kg,
    fuel_types, emission_tier, application_profiles, primary_applications,
    availability_status, regions_available, data_source, data_source_url, data_source_document,
    data_confidence, last_verified, verified_by, notes
) VALUES (
    'a57fb74f-2722-45df-91a3-2797d47d672a', 'abd15255-639f-4ee5-865c-464ed6fa6702', 'M05-N',
    'MTU 12V 4000 M05-N', 'medium_duty', 'not_applicable',
    'MED', 'M05-N',
    1380, 1850.58, 1500,
    0.2, 0.8,
    2000, 4000,
    NULL, NULL,
    NULL, NULL, NULL,
    '["lng"]', 'IMO Tier III (Gas Mode)',
    '["ferry", "osv", "workboat"]', '["ferry", "osv", "workboat"]',
    'available', '["APAC", "EMEA", "Americas"]',
    'manufacturer_datasheet', 'https://www.mtu-solutions.com/',
    'MTU 12V 4000 M05-N specification sheet', 0.9,
    NOW(), 'engine_master_data', 'MTU 12V 4000 M05-N natural gas marine engine from Rolls-Royce Power Systems. 12-cylinder V-configuration producing 1164-1380 kW at 1500 RPM. Series 4000 Gas platform for LNG-powered vessels. Achieves IMO Tier III emissions without aftertreatment in gas mode. Designed for ferries, offshore support vessels, and workboats transitioning to cleaner fuels. Spark-ignited, lean-burn combustion technology. Also known as MTU 12V4000M05N or RRPS Series 4000 Gas.'
)
ON CONFLICT (engine_model_id, rating_designation) DO UPDATE SET
    power_kw = EXCLUDED.power_kw,
    power_hp = EXCLUDED.power_hp,
    duty_class = EXCLUDED.duty_class,
    harmonized_duty_class = EXCLUDED.harmonized_duty_class,
    oem_rating_code = EXCLUDED.oem_rating_code,
    dry_weight_kg = EXCLUDED.dry_weight_kg,
    length_mm = EXCLUDED.length_mm,
    width_mm = EXCLUDED.width_mm,
    height_mm = EXCLUDED.height_mm,
    power_density_kw_per_kg = EXCLUDED.power_density_kw_per_kg,
    last_verified = NOW(),
    verified_by = EXCLUDED.verified_by;

INSERT INTO kb_engine_ratings (
    id, engine_model_id, rating_designation, rating_name, duty_class, iso_classification,
    harmonized_duty_class, oem_rating_code,
    power_kw, power_hp, rpm, load_factor_min, load_factor_max, annual_hours_min, annual_hours_max,
    dry_weight_kg, length_mm, width_mm, height_mm, power_density_kw_per_kg,
    fuel_types, emission_tier, application_profiles, primary_applications,
    availability_status, regions_available, data_source, data_source_url, data_source_document,
    data_confidence, last_verified, verified_by, notes
) VALUES (
    '8b80d6eb-3683-4f3f-a590-e1a776d10e92', 'a3f10777-0008-482c-9958-cc4123401293', 'M05-N',
    'MTU 16V 4000 M05-N', 'medium_duty', 'not_applicable',
    'MED', 'M05-N',
    1840, 2467.44, 1500,
    0.2, 0.8,
    2000, 4000,
    NULL, NULL,
    NULL, NULL, NULL,
    '["lng"]', 'IMO Tier III (Gas Mode)',
    '["ferry", "osv", "offshore"]', '["ferry", "osv", "offshore"]',
    'available', '["APAC", "EMEA", "Americas"]',
    'manufacturer_datasheet', 'https://www.mtu-solutions.com/',
    'MTU 16V 4000 M05-N specification sheet', 0.9,
    NOW(), 'engine_master_data', 'MTU 16V 4000 M05-N natural gas marine engine from Rolls-Royce Power Systems. 16-cylinder V-configuration producing 1552-1840 kW at 1500 RPM. Series 4000 Gas for LNG-fueled marine applications. IMO Tier III compliant in gas mode without SCR or aftertreatment. Ideal for environmentally regulated areas (ECAs). Applications include LNG-powered ferries and offshore vessels. Known as MTU 16V4000M05N or RRPS 16V 4000 Gas.'
)
ON CONFLICT (engine_model_id, rating_designation) DO UPDATE SET
    power_kw = EXCLUDED.power_kw,
    power_hp = EXCLUDED.power_hp,
    duty_class = EXCLUDED.duty_class,
    harmonized_duty_class = EXCLUDED.harmonized_duty_class,
    oem_rating_code = EXCLUDED.oem_rating_code,
    dry_weight_kg = EXCLUDED.dry_weight_kg,
    length_mm = EXCLUDED.length_mm,
    width_mm = EXCLUDED.width_mm,
    height_mm = EXCLUDED.height_mm,
    power_density_kw_per_kg = EXCLUDED.power_density_kw_per_kg,
    last_verified = NOW(),
    verified_by = EXCLUDED.verified_by;

INSERT INTO kb_engine_ratings (
    id, engine_model_id, rating_designation, rating_name, duty_class, iso_classification,
    harmonized_duty_class, oem_rating_code,
    power_kw, power_hp, rpm, load_factor_min, load_factor_max, annual_hours_min, annual_hours_max,
    dry_weight_kg, length_mm, width_mm, height_mm, power_density_kw_per_kg,
    fuel_types, emission_tier, application_profiles, primary_applications,
    availability_status, regions_available, data_source, data_source_url, data_source_document,
    data_confidence, last_verified, verified_by, notes
) VALUES (
    '7e1db138-b19a-40d0-8aa4-db3809f3142e', '5133d902-753a-4984-b9a7-33a10b1b9987', 'M05-N',
    'MTU 20V 4000 M05-N', 'medium_duty', 'not_applicable',
    'MED', 'M05-N',
    2300, 3084.2999999999997, 1500,
    0.2, 0.8,
    2000, 4000,
    NULL, NULL,
    NULL, NULL, NULL,
    '["lng"]', 'IMO Tier III (Gas Mode)',
    '["large_ferry", "osv"]', '["large_ferry", "osv"]',
    'available', '["APAC", "EMEA", "Americas"]',
    'manufacturer_datasheet', 'https://www.mtu-solutions.com/',
    'MTU 20V 4000 M05-N specification sheet', 0.9,
    NOW(), 'engine_master_data', 'MTU 20V 4000 M05-N natural gas marine engine, flagship of the Series 4000 Gas range. 20-cylinder V-configuration producing 1940-2300 kW at 1500 RPM. Highest power output in MTU gas marine lineup. IMO Tier III emissions compliance without aftertreatment systems. Designed for large LNG-powered ferries and offshore vessels. Lean-burn spark-ignited technology with low methane slip. Also referred to as MTU 20V4000M05N or Rolls-Royce Series 4000 Gas.'
)
ON CONFLICT (engine_model_id, rating_designation) DO UPDATE SET
    power_kw = EXCLUDED.power_kw,
    power_hp = EXCLUDED.power_hp,
    duty_class = EXCLUDED.duty_class,
    harmonized_duty_class = EXCLUDED.harmonized_duty_class,
    oem_rating_code = EXCLUDED.oem_rating_code,
    dry_weight_kg = EXCLUDED.dry_weight_kg,
    length_mm = EXCLUDED.length_mm,
    width_mm = EXCLUDED.width_mm,
    height_mm = EXCLUDED.height_mm,
    power_density_kw_per_kg = EXCLUDED.power_density_kw_per_kg,
    last_verified = NOW(),
    verified_by = EXCLUDED.verified_by;

INSERT INTO kb_engine_ratings (
    id, engine_model_id, rating_designation, rating_name, duty_class, iso_classification,
    harmonized_duty_class, oem_rating_code,
    power_kw, power_hp, rpm, load_factor_min, load_factor_max, annual_hours_min, annual_hours_max,
    dry_weight_kg, length_mm, width_mm, height_mm, power_density_kw_per_kg,
    fuel_types, emission_tier, application_profiles, primary_applications,
    availability_status, regions_available, data_source, data_source_url, data_source_document,
    data_confidence, last_verified, verified_by, notes
) VALUES (
    '401df5d7-bf34-4be8-add7-8780d06add17', '64770fae-ab1b-4c5e-8fc6-af3aea679ff9', 'M71',
    'MTU 16V 8000 M71', 'heavy_duty', 'not_applicable',
    'HVY', 'M71',
    7280, 9762.48, 1150,
    0.4, 0.8,
    3000, 5000,
    NULL, NULL,
    NULL, NULL, NULL,
    '["diesel", "mdo"]', 'IMO Tier II',
    '["ferry", "ropax", "cruise"]', '["ferry", "ropax", "cruise"]',
    'available', '["APAC", "EMEA", "Americas"]',
    'manufacturer_datasheet', 'https://www.mtu-solutions.com/',
    'MTU 16V 8000 M71 specification sheet', 0.95,
    NOW(), 'engine_master_data', 'MTU 16V 8000 M71 high-speed marine diesel engine from Rolls-Royce Power Systems MTU. 16-cylinder V-configuration delivering 7280 kW (9765 bhp) at 1150 RPM. Series 8000 platform bridges high-speed and medium-speed segments. Designed for large fast ferries, cruise ships, and naval frigates. Features common rail injection with ADEC engine management. IMO Tier II certified. Known for exceptional power density. Also referred to as MTU 16V8000M71 or RRPS Series 8000.'
)
ON CONFLICT (engine_model_id, rating_designation) DO UPDATE SET
    power_kw = EXCLUDED.power_kw,
    power_hp = EXCLUDED.power_hp,
    duty_class = EXCLUDED.duty_class,
    harmonized_duty_class = EXCLUDED.harmonized_duty_class,
    oem_rating_code = EXCLUDED.oem_rating_code,
    dry_weight_kg = EXCLUDED.dry_weight_kg,
    length_mm = EXCLUDED.length_mm,
    width_mm = EXCLUDED.width_mm,
    height_mm = EXCLUDED.height_mm,
    power_density_kw_per_kg = EXCLUDED.power_density_kw_per_kg,
    last_verified = NOW(),
    verified_by = EXCLUDED.verified_by;

INSERT INTO kb_engine_ratings (
    id, engine_model_id, rating_designation, rating_name, duty_class, iso_classification,
    harmonized_duty_class, oem_rating_code,
    power_kw, power_hp, rpm, load_factor_min, load_factor_max, annual_hours_min, annual_hours_max,
    dry_weight_kg, length_mm, width_mm, height_mm, power_density_kw_per_kg,
    fuel_types, emission_tier, application_profiles, primary_applications,
    availability_status, regions_available, data_source, data_source_url, data_source_document,
    data_confidence, last_verified, verified_by, notes
) VALUES (
    '06f635c0-ab54-48f0-ac3c-c57ca6e5db22', '1180a2df-0d96-4e8a-8e6b-6946e92feaae', 'M91',
    'MTU 20V 8000 M91', 'light_duty', 'not_applicable',
    'LGT', 'M91',
    10000, 13410.0, 1150,
    0.0, 0.5,
    1000, 3000,
    NULL, NULL,
    NULL, NULL, NULL,
    '["diesel", "mdo"]', 'IMO Tier II',
    '["yacht", "fast_ferry", "naval"]', '["yacht", "fast_ferry", "naval"]',
    'available', '["APAC", "EMEA", "Americas"]',
    'manufacturer_datasheet', 'https://www.mtu-solutions.com/',
    'MTU 20V 8000 M91 specification sheet', 0.95,
    NOW(), 'engine_master_data', 'MTU 20V 8000 M91 high-speed marine diesel engine, flagship from Rolls-Royce Power Systems MTU. 20-cylinder V-configuration producing 9100-10000 kW (12200-13400 bhp) at 1150 RPM. Highest power output in MTU marine portfolio. Applications include large fast ferries, RoPax vessels, naval corvettes and frigates. M91 heavy-duty rating for demanding operations. Features advanced common rail injection and sophisticated turbocharging. IMO Tier II compliant. Known as MTU 20V8000M91 or RRPS 20V8000.'
)
ON CONFLICT (engine_model_id, rating_designation) DO UPDATE SET
    power_kw = EXCLUDED.power_kw,
    power_hp = EXCLUDED.power_hp,
    duty_class = EXCLUDED.duty_class,
    harmonized_duty_class = EXCLUDED.harmonized_duty_class,
    oem_rating_code = EXCLUDED.oem_rating_code,
    dry_weight_kg = EXCLUDED.dry_weight_kg,
    length_mm = EXCLUDED.length_mm,
    width_mm = EXCLUDED.width_mm,
    height_mm = EXCLUDED.height_mm,
    power_density_kw_per_kg = EXCLUDED.power_density_kw_per_kg,
    last_verified = NOW(),
    verified_by = EXCLUDED.verified_by;

INSERT INTO kb_engine_ratings (
    id, engine_model_id, rating_designation, rating_name, duty_class, iso_classification,
    harmonized_duty_class, oem_rating_code,
    power_kw, power_hp, rpm, load_factor_min, load_factor_max, annual_hours_min, annual_hours_max,
    dry_weight_kg, length_mm, width_mm, height_mm, power_density_kw_per_kg,
    fuel_types, emission_tier, application_profiles, primary_applications,
    availability_status, regions_available, data_source, data_source_url, data_source_document,
    data_confidence, last_verified, verified_by, notes
) VALUES (
    '4479179f-44fa-40ac-96b8-647af5b4b607', '085b04f4-de18-4278-9259-ea6fac98bd63', 'QSK38-HD',
    'Cummins QSK38', 'heavy_duty', 'not_applicable',
    'HVY', 'QSK38-HD',
    1417, 1900.197, 1800,
    0.4, 0.8,
    3000, 5000,
    NULL, NULL,
    NULL, NULL, NULL,
    '["mgo", "diesel", "mdo"]', 'IMO Tier II',
    '["tug", "osv", "workboat"]', '["tug", "osv", "workboat"]',
    'available', '["APAC", "EMEA", "Americas"]',
    'manufacturer_datasheet', 'https://www.cummins.com/',
    'Cummins QSK38 specification sheet', 0.95,
    NOW(), 'engine_master_data', 'Cummins QSK38 high-speed marine diesel engine. 12-cylinder V-configuration delivering 1063-1417 kW (1425-1900 bhp) at 1800 RPM. 38 liter displacement with Modular Common Rail Fuel System (MCRS). Popular for offshore crew boats, tugs, and workboats. Features Quantum electronic controls, heavy-duty design. IMO Tier II compliant. Excellent service network globally. Also known as Cummins QSK38-M, QSK 38, or Cummins 38-liter marine.'
)
ON CONFLICT (engine_model_id, rating_designation) DO UPDATE SET
    power_kw = EXCLUDED.power_kw,
    power_hp = EXCLUDED.power_hp,
    duty_class = EXCLUDED.duty_class,
    harmonized_duty_class = EXCLUDED.harmonized_duty_class,
    oem_rating_code = EXCLUDED.oem_rating_code,
    dry_weight_kg = EXCLUDED.dry_weight_kg,
    length_mm = EXCLUDED.length_mm,
    width_mm = EXCLUDED.width_mm,
    height_mm = EXCLUDED.height_mm,
    power_density_kw_per_kg = EXCLUDED.power_density_kw_per_kg,
    last_verified = NOW(),
    verified_by = EXCLUDED.verified_by;

INSERT INTO kb_engine_ratings (
    id, engine_model_id, rating_designation, rating_name, duty_class, iso_classification,
    harmonized_duty_class, oem_rating_code,
    power_kw, power_hp, rpm, load_factor_min, load_factor_max, annual_hours_min, annual_hours_max,
    dry_weight_kg, length_mm, width_mm, height_mm, power_density_kw_per_kg,
    fuel_types, emission_tier, application_profiles, primary_applications,
    availability_status, regions_available, data_source, data_source_url, data_source_document,
    data_confidence, last_verified, verified_by, notes
) VALUES (
    '8ee7d9a0-68b7-48a6-a9ad-41de09e5df69', 'c4da3cf2-6e9a-4648-82ae-8d3b57dd5347', 'QSK50-HD',
    'Cummins QSK50', 'heavy_duty', 'not_applicable',
    'HVY', 'QSK50-HD',
    1700, 2279.7, 1800,
    0.4, 0.8,
    3000, 5000,
    NULL, NULL,
    NULL, NULL, NULL,
    '["mgo", "diesel", "mdo"]', 'IMO Tier II',
    '["tug", "osv", "fast_supply"]', '["tug", "osv", "fast_supply"]',
    'available', '["APAC", "EMEA", "Americas"]',
    'manufacturer_datasheet', 'https://www.cummins.com/',
    'Cummins QSK50 specification sheet', 0.95,
    NOW(), 'engine_master_data', 'Cummins QSK50 high-speed marine diesel engine. 16-cylinder V-configuration producing 1268-1700 kW (1700-2280 bhp) at 1800 RPM. 50 liter displacement with Modular Common Rail Fuel System (MCRS). Popular mid-range option between QSK38 and QSK60. Direct competitor to MTU 12V2000 M93. Applications include tugs, offshore crew boats, fast supply vessels. Features Quantum electronic controls, proven reliability. IMO Tier II compliant. Excellent parts availability through global Cummins network. Also kn'
)
ON CONFLICT (engine_model_id, rating_designation) DO UPDATE SET
    power_kw = EXCLUDED.power_kw,
    power_hp = EXCLUDED.power_hp,
    duty_class = EXCLUDED.duty_class,
    harmonized_duty_class = EXCLUDED.harmonized_duty_class,
    oem_rating_code = EXCLUDED.oem_rating_code,
    dry_weight_kg = EXCLUDED.dry_weight_kg,
    length_mm = EXCLUDED.length_mm,
    width_mm = EXCLUDED.width_mm,
    height_mm = EXCLUDED.height_mm,
    power_density_kw_per_kg = EXCLUDED.power_density_kw_per_kg,
    last_verified = NOW(),
    verified_by = EXCLUDED.verified_by;

INSERT INTO kb_engine_ratings (
    id, engine_model_id, rating_designation, rating_name, duty_class, iso_classification,
    harmonized_duty_class, oem_rating_code,
    power_kw, power_hp, rpm, load_factor_min, load_factor_max, annual_hours_min, annual_hours_max,
    dry_weight_kg, length_mm, width_mm, height_mm, power_density_kw_per_kg,
    fuel_types, emission_tier, application_profiles, primary_applications,
    availability_status, regions_available, data_source, data_source_url, data_source_document,
    data_confidence, last_verified, verified_by, notes
) VALUES (
    'c55de57e-8cc6-43f5-9c9a-a592da48ebd1', '9310b10d-4ee8-47c3-a54e-486ddd2a49d6', 'QSK60-HD',
    'Cummins QSK60', 'heavy_duty', 'not_applicable',
    'HVY', 'QSK60-HD',
    2680, 3593.88, 1800,
    0.4, 0.8,
    3000, 5000,
    8754, 3290,
    1757, 2415, 0.3061,
    '["mgo", "diesel", "mdo"]', 'IMO Tier II',
    '["tug", "osv", "ferry"]', '["tug", "osv", "ferry"]',
    'available', '["APAC", "EMEA", "Americas"]',
    'manufacturer_datasheet', 'https://www.cummins.com/',
    'Cummins QSK60 specification sheet', 0.95,
    NOW(), 'engine_master_data', 'Cummins QSK60 high-speed marine diesel engine. 16-cylinder V-configuration producing 1641-2680 kW (2200-3595 bhp) at 1800 RPM. 60.2 liter displacement, flagship of QSK marine range. Features Modular Common Rail Fuel System, Quantum electronic controls. Applications include large tugs, offshore supply vessels, fast ferries. IMO Tier II certified. Robust design proven in harsh marine environments. Known as Cummins QSK60-M, QSK 60, or Cummins 60-liter.'
)
ON CONFLICT (engine_model_id, rating_designation) DO UPDATE SET
    power_kw = EXCLUDED.power_kw,
    power_hp = EXCLUDED.power_hp,
    duty_class = EXCLUDED.duty_class,
    harmonized_duty_class = EXCLUDED.harmonized_duty_class,
    oem_rating_code = EXCLUDED.oem_rating_code,
    dry_weight_kg = EXCLUDED.dry_weight_kg,
    length_mm = EXCLUDED.length_mm,
    width_mm = EXCLUDED.width_mm,
    height_mm = EXCLUDED.height_mm,
    power_density_kw_per_kg = EXCLUDED.power_density_kw_per_kg,
    last_verified = NOW(),
    verified_by = EXCLUDED.verified_by;

INSERT INTO kb_engine_ratings (
    id, engine_model_id, rating_designation, rating_name, duty_class, iso_classification,
    harmonized_duty_class, oem_rating_code,
    power_kw, power_hp, rpm, load_factor_min, load_factor_max, annual_hours_min, annual_hours_max,
    dry_weight_kg, length_mm, width_mm, height_mm, power_density_kw_per_kg,
    fuel_types, emission_tier, application_profiles, primary_applications,
    availability_status, regions_available, data_source, data_source_url, data_source_document,
    data_confidence, last_verified, verified_by, notes
) VALUES (
    'beea6749-bd0c-4fed-b793-c9fdeaf32a53', '0a1fcf5a-a4a1-4f14-97e2-3c6cffb1cd59', 'QSK78-HD',
    'Cummins QSK78', 'heavy_duty', 'not_applicable',
    'HVY', 'QSK78-HD',
    3028, 4060.548, 1800,
    0.4, 0.8,
    3000, 5000,
    NULL, NULL,
    NULL, NULL, NULL,
    '["diesel", "mdo"]', 'IMO Tier II',
    '["tug", "osv", "ferry"]', '["tug", "osv", "ferry"]',
    'available', '["APAC", "EMEA", "Americas"]',
    'manufacturer_datasheet', 'https://www.cummins.com/',
    'Cummins QSK78 specification sheet', 0.85,
    NOW(), 'engine_master_data', 'Cummins QSK78 high-speed marine diesel engine. 18-cylinder V-configuration delivering 2610-3028 kW (3500-4060 bhp) at 1800 RPM. 78 liter displacement for high-power marine applications. Features advanced common rail injection, electronic controls. Applications include large offshore vessels, harbor tugs, and ferries. IMO Tier II compliant. Less common than QSK60 but offers higher power. Also referred to as Cummins QSK78-M or QSK 78.'
)
ON CONFLICT (engine_model_id, rating_designation) DO UPDATE SET
    power_kw = EXCLUDED.power_kw,
    power_hp = EXCLUDED.power_hp,
    duty_class = EXCLUDED.duty_class,
    harmonized_duty_class = EXCLUDED.harmonized_duty_class,
    oem_rating_code = EXCLUDED.oem_rating_code,
    dry_weight_kg = EXCLUDED.dry_weight_kg,
    length_mm = EXCLUDED.length_mm,
    width_mm = EXCLUDED.width_mm,
    height_mm = EXCLUDED.height_mm,
    power_density_kw_per_kg = EXCLUDED.power_density_kw_per_kg,
    last_verified = NOW(),
    verified_by = EXCLUDED.verified_by;

INSERT INTO kb_engine_ratings (
    id, engine_model_id, rating_designation, rating_name, duty_class, iso_classification,
    harmonized_duty_class, oem_rating_code,
    power_kw, power_hp, rpm, load_factor_min, load_factor_max, annual_hours_min, annual_hours_max,
    dry_weight_kg, length_mm, width_mm, height_mm, power_density_kw_per_kg,
    fuel_types, emission_tier, application_profiles, primary_applications,
    availability_status, regions_available, data_source, data_source_url, data_source_document,
    data_confidence, last_verified, verified_by, notes
) VALUES (
    '97635595-0d29-4ec3-a7a7-760f23a66b36', '544f6045-d69b-415e-a448-7e7ce301ff85', 'QSK95-HD',
    'Cummins QSK95', 'heavy_duty', 'not_applicable',
    'HVY', 'QSK95-HD',
    3730, 5001.93, 1800,
    0.4, 0.8,
    3000, 5000,
    NULL, NULL,
    NULL, NULL, NULL,
    '["diesel", "mdo"]', 'IMO Tier II',
    '["tug", "osv", "dredger"]', '["tug", "osv", "dredger"]',
    'available', '["APAC", "EMEA", "Americas"]',
    'manufacturer_datasheet', 'https://www.cummins.com/',
    'Cummins QSK95 specification sheet', 0.95,
    NOW(), 'engine_master_data', 'Cummins QSK95 high-speed marine diesel engine, the largest Cummins engine ever built. 16-cylinder V-configuration producing 2834-3730 kW (3800-5000 bhp) at 1800 RPM. 95 liter displacement with Modular Common Rail Fuel System. Designed for demanding marine applications including large tugs, offshore vessels, and dredgers. Features advanced Quantum electronic controls. IMO Tier II certified. Known as Cummins QSK95-M, QSK 95, or Cummins 95-liter marine.'
)
ON CONFLICT (engine_model_id, rating_designation) DO UPDATE SET
    power_kw = EXCLUDED.power_kw,
    power_hp = EXCLUDED.power_hp,
    duty_class = EXCLUDED.duty_class,
    harmonized_duty_class = EXCLUDED.harmonized_duty_class,
    oem_rating_code = EXCLUDED.oem_rating_code,
    dry_weight_kg = EXCLUDED.dry_weight_kg,
    length_mm = EXCLUDED.length_mm,
    width_mm = EXCLUDED.width_mm,
    height_mm = EXCLUDED.height_mm,
    power_density_kw_per_kg = EXCLUDED.power_density_kw_per_kg,
    last_verified = NOW(),
    verified_by = EXCLUDED.verified_by;

INSERT INTO kb_engine_ratings (
    id, engine_model_id, rating_designation, rating_name, duty_class, iso_classification,
    harmonized_duty_class, oem_rating_code,
    power_kw, power_hp, rpm, load_factor_min, load_factor_max, annual_hours_min, annual_hours_max,
    dry_weight_kg, length_mm, width_mm, height_mm, power_density_kw_per_kg,
    fuel_types, emission_tier, application_profiles, primary_applications,
    availability_status, regions_available, data_source, data_source_url, data_source_document,
    data_confidence, last_verified, verified_by, notes
) VALUES (
    'b47ddf97-d8f0-43da-929c-4f60d083d9f5', '58037c0d-2d60-403e-9210-3b7e6a32d7a6', 'QST30-M',
    'Cummins QST30', 'medium_duty', 'not_applicable',
    'MED', 'QST30-M',
    1007, 1350.387, 1800,
    0.2, 0.8,
    2000, 4000,
    NULL, NULL,
    NULL, NULL, NULL,
    '["mgo", "diesel", "mdo"]', 'IMO Tier II',
    '["workboat", "ferry", "crew_boat"]', '["workboat", "ferry", "crew_boat"]',
    'available', '["APAC", "EMEA", "Americas"]',
    'manufacturer_datasheet', 'https://www.cummins.com/',
    'Cummins QST30 specification sheet', 0.9,
    NOW(), 'engine_master_data', 'Cummins QST30 high-speed marine diesel engine. 12-cylinder V-configuration delivering 746-1007 kW (1000-1350 bhp) at 1800-2100 RPM. 30 liter displacement with electronic fuel injection. Compact design for workboats, ferries, and crew boats. Features Quantum electronic controls, proven reliability. IMO Tier II certified. Known as Cummins QST30-M, QST 30, or Cummins 30-liter marine.'
)
ON CONFLICT (engine_model_id, rating_designation) DO UPDATE SET
    power_kw = EXCLUDED.power_kw,
    power_hp = EXCLUDED.power_hp,
    duty_class = EXCLUDED.duty_class,
    harmonized_duty_class = EXCLUDED.harmonized_duty_class,
    oem_rating_code = EXCLUDED.oem_rating_code,
    dry_weight_kg = EXCLUDED.dry_weight_kg,
    length_mm = EXCLUDED.length_mm,
    width_mm = EXCLUDED.width_mm,
    height_mm = EXCLUDED.height_mm,
    power_density_kw_per_kg = EXCLUDED.power_density_kw_per_kg,
    last_verified = NOW(),
    verified_by = EXCLUDED.verified_by;

INSERT INTO kb_engine_ratings (
    id, engine_model_id, rating_designation, rating_name, duty_class, iso_classification,
    harmonized_duty_class, oem_rating_code,
    power_kw, power_hp, rpm, load_factor_min, load_factor_max, annual_hours_min, annual_hours_max,
    dry_weight_kg, length_mm, width_mm, height_mm, power_density_kw_per_kg,
    fuel_types, emission_tier, application_profiles, primary_applications,
    availability_status, regions_available, data_source, data_source_url, data_source_document,
    data_confidence, last_verified, verified_by, notes
) VALUES (
    'b06aa905-71c3-45ad-bba2-55219aa30737', '9a41404b-5e1d-439e-8771-2067a7d6692e', 'X15-M',
    'Cummins X15 Marine', 'medium_duty', 'not_applicable',
    'MED', 'X15-M',
    600, 804.6, 1800,
    0.2, 0.8,
    2000, 4000,
    NULL, NULL,
    NULL, NULL, NULL,
    '["mgo", "diesel", "mdo"]', 'IMO Tier II',
    '["workboat", "fishing", "crew_boat"]', '["workboat", "fishing", "crew_boat"]',
    'available', '["APAC", "EMEA", "Americas"]',
    'manufacturer_datasheet', 'https://www.cummins.com/',
    'Cummins X15 Marine specification sheet', 0.9,
    NOW(), 'engine_master_data', 'Cummins X15 Marine high-speed diesel engine. 6-cylinder inline configuration delivering 450-600 kW (600-800 bhp) at 1800-2100 RPM. 15 liter displacement, compact design for smaller commercial vessels. Features advanced electronic controls, fuel efficiency. IMO Tier II certified. Ideal for workboats, fishing vessels, and crew boats. Known as Cummins X15-M or X15 Marine.'
)
ON CONFLICT (engine_model_id, rating_designation) DO UPDATE SET
    power_kw = EXCLUDED.power_kw,
    power_hp = EXCLUDED.power_hp,
    duty_class = EXCLUDED.duty_class,
    harmonized_duty_class = EXCLUDED.harmonized_duty_class,
    oem_rating_code = EXCLUDED.oem_rating_code,
    dry_weight_kg = EXCLUDED.dry_weight_kg,
    length_mm = EXCLUDED.length_mm,
    width_mm = EXCLUDED.width_mm,
    height_mm = EXCLUDED.height_mm,
    power_density_kw_per_kg = EXCLUDED.power_density_kw_per_kg,
    last_verified = NOW(),
    verified_by = EXCLUDED.verified_by;

INSERT INTO kb_engine_ratings (
    id, engine_model_id, rating_designation, rating_name, duty_class, iso_classification,
    harmonized_duty_class, oem_rating_code,
    power_kw, power_hp, rpm, load_factor_min, load_factor_max, annual_hours_min, annual_hours_max,
    dry_weight_kg, length_mm, width_mm, height_mm, power_density_kw_per_kg,
    fuel_types, emission_tier, application_profiles, primary_applications,
    availability_status, regions_available, data_source, data_source_url, data_source_document,
    data_confidence, last_verified, verified_by, notes
) VALUES (
    '78cd0ac9-f6c4-4c03-8146-efeb10f37991', '2bbcdbe2-accb-4f91-ad35-edc65d7e1bc4', 'QSK38-M',
    'Cummins QSK38-M', 'medium_duty', 'not_applicable',
    'MED', 'QSK38-M',
    1193, 1599.8129999999999, 1800,
    0.2, 0.8,
    2000, 4000,
    NULL, NULL,
    NULL, NULL, NULL,
    '["mgo", "diesel", "mdo"]', 'IMO Tier II',
    '["ferry", "workboat", "patrol"]', '["ferry", "workboat", "patrol"]',
    'available', '["APAC", "EMEA", "Americas"]',
    'manufacturer_datasheet', 'https://www.cummins.com/',
    'Cummins QSK38-M specification sheet', 0.9,
    NOW(), 'engine_master_data', 'Cummins QSK38-M medium duty marine diesel engine. 12-cylinder V-configuration delivering 895-1193 kW (1200-1600 bhp) at 1800 RPM. 38 liter displacement, medium duty rating for varied applications. Features Quantum electronic controls, versatile power options. IMO Tier II certified. Applications include ferries, workboats, and patrol vessels. Known as Cummins QSK38 Medium or QSK38-M.'
)
ON CONFLICT (engine_model_id, rating_designation) DO UPDATE SET
    power_kw = EXCLUDED.power_kw,
    power_hp = EXCLUDED.power_hp,
    duty_class = EXCLUDED.duty_class,
    harmonized_duty_class = EXCLUDED.harmonized_duty_class,
    oem_rating_code = EXCLUDED.oem_rating_code,
    dry_weight_kg = EXCLUDED.dry_weight_kg,
    length_mm = EXCLUDED.length_mm,
    width_mm = EXCLUDED.width_mm,
    height_mm = EXCLUDED.height_mm,
    power_density_kw_per_kg = EXCLUDED.power_density_kw_per_kg,
    last_verified = NOW(),
    verified_by = EXCLUDED.verified_by;

INSERT INTO kb_engine_ratings (
    id, engine_model_id, rating_designation, rating_name, duty_class, iso_classification,
    harmonized_duty_class, oem_rating_code,
    power_kw, power_hp, rpm, load_factor_min, load_factor_max, annual_hours_min, annual_hours_max,
    dry_weight_kg, length_mm, width_mm, height_mm, power_density_kw_per_kg,
    fuel_types, emission_tier, application_profiles, primary_applications,
    availability_status, regions_available, data_source, data_source_url, data_source_document,
    data_confidence, last_verified, verified_by, notes
) VALUES (
    '7fd583c6-6a9d-4431-8126-14e6025485c9', '25d4de31-ecb1-437a-bb95-b9159b48888b', '3508C',
    'Cat 3508C', 'medium_duty', 'not_applicable',
    'MED', '3508C',
    895, 1200.195, 1200,
    0.2, 0.8,
    2000, 4000,
    NULL, NULL,
    NULL, NULL, NULL,
    '["mgo", "diesel", "mdo"]', 'IMO Tier II',
    '["workboat", "ferry", "fishing"]', '["workboat", "ferry", "fishing"]',
    'available', '["APAC", "EMEA", "Americas"]',
    'manufacturer_datasheet', 'https://www.cat.com/',
    'Cat 3508C specification sheet', 0.9,
    NOW(), 'engine_master_data', 'Caterpillar 3508C high-speed marine diesel engine. 8-cylinder V-configuration delivering 746-895 kW (1000-1200 bhp) at 1200-1600 RPM. 34.5 liter displacement. Smaller 3500 series platform for mid-range applications. Features ADEM electronic controls, unit injection. IMO Tier II certified. Applications include workboats, ferries, fishing vessels. Known as Cat 3508C, CAT 3508C, or Caterpillar 3508C marine.'
)
ON CONFLICT (engine_model_id, rating_designation) DO UPDATE SET
    power_kw = EXCLUDED.power_kw,
    power_hp = EXCLUDED.power_hp,
    duty_class = EXCLUDED.duty_class,
    harmonized_duty_class = EXCLUDED.harmonized_duty_class,
    oem_rating_code = EXCLUDED.oem_rating_code,
    dry_weight_kg = EXCLUDED.dry_weight_kg,
    length_mm = EXCLUDED.length_mm,
    width_mm = EXCLUDED.width_mm,
    height_mm = EXCLUDED.height_mm,
    power_density_kw_per_kg = EXCLUDED.power_density_kw_per_kg,
    last_verified = NOW(),
    verified_by = EXCLUDED.verified_by;

INSERT INTO kb_engine_ratings (
    id, engine_model_id, rating_designation, rating_name, duty_class, iso_classification,
    harmonized_duty_class, oem_rating_code,
    power_kw, power_hp, rpm, load_factor_min, load_factor_max, annual_hours_min, annual_hours_max,
    dry_weight_kg, length_mm, width_mm, height_mm, power_density_kw_per_kg,
    fuel_types, emission_tier, application_profiles, primary_applications,
    availability_status, regions_available, data_source, data_source_url, data_source_document,
    data_confidence, last_verified, verified_by, notes
) VALUES (
    'f6e95f1a-6d3f-4047-bb76-39000d7c457c', '19c24f5d-219c-4acb-9b16-7bcc4c84efa2', '3512',
    'Cat 3512', 'medium_duty', 'not_applicable',
    'MED', '3512',
    1119, 1500.579, 1200,
    0.2, 0.8,
    2000, 4000,
    NULL, NULL,
    NULL, NULL, NULL,
    '["mgo", "diesel", "mdo"]', 'IMO Tier II',
    '["tug", "workboat", "ferry", "fishing"]', '["tug", "workboat", "ferry"]',
    'available', '["APAC", "EMEA", "Americas"]',
    'manufacturer_datasheet', 'https://www.cat.com/',
    'Cat 3512 specification sheet', 0.95,
    NOW(), 'engine_master_data', 'Caterpillar 3512 high-speed marine diesel engine. 12-cylinder V-configuration delivering 761-1119 kW (1020-1500 bhp) at 1200-1800 RPM. 51.8 liter displacement. Versatile 3500 series platform for commercial marine applications. Features ADEM A4 electronic controls, unit injection fuel system. IMO Tier II compliant. Applications include tugs, workboats, ferries, fishing vessels. Extensive Cat dealer network. Also known as Cat 3512, CAT 3512, or Caterpillar 3512 marine.'
)
ON CONFLICT (engine_model_id, rating_designation) DO UPDATE SET
    power_kw = EXCLUDED.power_kw,
    power_hp = EXCLUDED.power_hp,
    duty_class = EXCLUDED.duty_class,
    harmonized_duty_class = EXCLUDED.harmonized_duty_class,
    oem_rating_code = EXCLUDED.oem_rating_code,
    dry_weight_kg = EXCLUDED.dry_weight_kg,
    length_mm = EXCLUDED.length_mm,
    width_mm = EXCLUDED.width_mm,
    height_mm = EXCLUDED.height_mm,
    power_density_kw_per_kg = EXCLUDED.power_density_kw_per_kg,
    last_verified = NOW(),
    verified_by = EXCLUDED.verified_by;

INSERT INTO kb_engine_ratings (
    id, engine_model_id, rating_designation, rating_name, duty_class, iso_classification,
    harmonized_duty_class, oem_rating_code,
    power_kw, power_hp, rpm, load_factor_min, load_factor_max, annual_hours_min, annual_hours_max,
    dry_weight_kg, length_mm, width_mm, height_mm, power_density_kw_per_kg,
    fuel_types, emission_tier, application_profiles, primary_applications,
    availability_status, regions_available, data_source, data_source_url, data_source_document,
    data_confidence, last_verified, verified_by, notes
) VALUES (
    'a78d64fb-918d-4c3f-952d-7baf7d4db71d', '3a759aa6-2b35-4f87-800c-1a2170cb1f08', '3512B',
    'Cat 3512B', 'heavy_duty', 'not_applicable',
    'HVY', '3512B',
    1400, 1877.3999999999999, 1600,
    0.4, 0.8,
    3000, 5000,
    NULL, NULL,
    NULL, NULL, NULL,
    '["mgo", "diesel", "mdo"]', 'IMO Tier II',
    '["fishing", "osv", "tug"]', '["fishing", "osv", "tug"]',
    'available', '["APAC", "EMEA", "Americas"]',
    'manufacturer_datasheet', 'https://www.cat.com/',
    'Cat 3512B specification sheet', 0.9,
    NOW(), 'engine_master_data', 'Caterpillar 3512B high-speed marine diesel engine, enhanced B-series variant. 12-cylinder V-configuration producing 1044-1400 kW (1400-1875 bhp) at 1600-1800 RPM. Improved fuel efficiency and reliability over base 3512. Features ADEM electronic controls with enhanced diagnostics. IMO Tier II certified. Popular for commercial fishing, offshore support, and tug applications. Also referred to as Cat 3512B, CAT 3512B, or Caterpillar 3512B marine.'
)
ON CONFLICT (engine_model_id, rating_designation) DO UPDATE SET
    power_kw = EXCLUDED.power_kw,
    power_hp = EXCLUDED.power_hp,
    duty_class = EXCLUDED.duty_class,
    harmonized_duty_class = EXCLUDED.harmonized_duty_class,
    oem_rating_code = EXCLUDED.oem_rating_code,
    dry_weight_kg = EXCLUDED.dry_weight_kg,
    length_mm = EXCLUDED.length_mm,
    width_mm = EXCLUDED.width_mm,
    height_mm = EXCLUDED.height_mm,
    power_density_kw_per_kg = EXCLUDED.power_density_kw_per_kg,
    last_verified = NOW(),
    verified_by = EXCLUDED.verified_by;

INSERT INTO kb_engine_ratings (
    id, engine_model_id, rating_designation, rating_name, duty_class, iso_classification,
    harmonized_duty_class, oem_rating_code,
    power_kw, power_hp, rpm, load_factor_min, load_factor_max, annual_hours_min, annual_hours_max,
    dry_weight_kg, length_mm, width_mm, height_mm, power_density_kw_per_kg,
    fuel_types, emission_tier, application_profiles, primary_applications,
    availability_status, regions_available, data_source, data_source_url, data_source_document,
    data_confidence, last_verified, verified_by, notes
) VALUES (
    '5cc23b10-7846-4692-9def-b6e07f31d4e6', '59d31690-feaa-487a-b8ff-abb7674db644', '3516',
    'Cat 3516', 'medium_duty', 'not_applicable',
    'MED', '3516',
    1492, 2000.772, 1200,
    0.2, 0.8,
    2000, 4000,
    NULL, NULL,
    NULL, NULL, NULL,
    '["mgo", "diesel", "mdo"]', 'IMO Tier II',
    '["tug", "osv", "ferry", "dredger"]', '["tug", "osv", "ferry"]',
    'available', '["APAC", "EMEA", "Americas"]',
    'manufacturer_datasheet', 'https://www.cat.com/',
    'Cat 3516 specification sheet', 0.95,
    NOW(), 'engine_master_data', 'Caterpillar 3516 high-speed marine diesel engine. 16-cylinder V-configuration delivering 1011-1492 kW (1355-2000 bhp) at 1200-1800 RPM. 69 liter displacement. Workhorse of the Cat marine fleet for medium-power applications. Features ADEM A4 controls, proven reliability. IMO Tier II compliant. Applications include tugs, OSVs, ferries, and dredgers. Global Cat dealer support. Known as Cat 3516, CAT 3516, or Caterpillar 3516 marine.'
)
ON CONFLICT (engine_model_id, rating_designation) DO UPDATE SET
    power_kw = EXCLUDED.power_kw,
    power_hp = EXCLUDED.power_hp,
    duty_class = EXCLUDED.duty_class,
    harmonized_duty_class = EXCLUDED.harmonized_duty_class,
    oem_rating_code = EXCLUDED.oem_rating_code,
    dry_weight_kg = EXCLUDED.dry_weight_kg,
    length_mm = EXCLUDED.length_mm,
    width_mm = EXCLUDED.width_mm,
    height_mm = EXCLUDED.height_mm,
    power_density_kw_per_kg = EXCLUDED.power_density_kw_per_kg,
    last_verified = NOW(),
    verified_by = EXCLUDED.verified_by;

INSERT INTO kb_engine_ratings (
    id, engine_model_id, rating_designation, rating_name, duty_class, iso_classification,
    harmonized_duty_class, oem_rating_code,
    power_kw, power_hp, rpm, load_factor_min, load_factor_max, annual_hours_min, annual_hours_max,
    dry_weight_kg, length_mm, width_mm, height_mm, power_density_kw_per_kg,
    fuel_types, emission_tier, application_profiles, primary_applications,
    availability_status, regions_available, data_source, data_source_url, data_source_document,
    data_confidence, last_verified, verified_by, notes
) VALUES (
    'cf90db98-4e82-49b0-bd70-374b726c68fc', '11e485be-6769-4789-a005-dab0b353933c', '3516B',
    'Cat 3516B', 'heavy_duty', 'not_applicable',
    'HVY', '3516B',
    1680, 2252.88, 1600,
    0.4, 0.8,
    3000, 5000,
    NULL, NULL,
    NULL, NULL, NULL,
    '["mgo", "diesel", "mdo"]', 'IMO Tier II',
    '["tug", "osv", "ferry"]', '["tug", "osv", "ferry"]',
    'available', '["APAC", "EMEA", "Americas"]',
    'manufacturer_datasheet', 'https://www.cat.com/',
    'Cat 3516B specification sheet', 0.9,
    NOW(), 'engine_master_data', 'Caterpillar 3516B high-speed marine diesel engine, enhanced B-series V16. 16-cylinder V-configuration producing 1340-1680 kW (1795-2250 bhp) at 1600-1800 RPM. Improved power output and efficiency over base 3516. Features advanced ADEM electronic controls. IMO Tier II certified. Popular for large tugs, offshore supply vessels, and ferries. Also referred to as Cat 3516B, CAT 3516B, or Caterpillar 3516B marine.'
)
ON CONFLICT (engine_model_id, rating_designation) DO UPDATE SET
    power_kw = EXCLUDED.power_kw,
    power_hp = EXCLUDED.power_hp,
    duty_class = EXCLUDED.duty_class,
    harmonized_duty_class = EXCLUDED.harmonized_duty_class,
    oem_rating_code = EXCLUDED.oem_rating_code,
    dry_weight_kg = EXCLUDED.dry_weight_kg,
    length_mm = EXCLUDED.length_mm,
    width_mm = EXCLUDED.width_mm,
    height_mm = EXCLUDED.height_mm,
    power_density_kw_per_kg = EXCLUDED.power_density_kw_per_kg,
    last_verified = NOW(),
    verified_by = EXCLUDED.verified_by;

INSERT INTO kb_engine_ratings (
    id, engine_model_id, rating_designation, rating_name, duty_class, iso_classification,
    harmonized_duty_class, oem_rating_code,
    power_kw, power_hp, rpm, load_factor_min, load_factor_max, annual_hours_min, annual_hours_max,
    dry_weight_kg, length_mm, width_mm, height_mm, power_density_kw_per_kg,
    fuel_types, emission_tier, application_profiles, primary_applications,
    availability_status, regions_available, data_source, data_source_url, data_source_document,
    data_confidence, last_verified, verified_by, notes
) VALUES (
    'de89c35f-1f46-4479-a1cb-61f3bf18efdc', '7e48efbf-a53b-4272-a828-3de16b1d111c', '3516C-HD',
    'Cat 3516C', 'heavy_duty', 'not_applicable',
    'HVY', '3516C-HD',
    2525, 3386.025, 1600,
    0.4, 0.8,
    3000, 5000,
    NULL, NULL,
    NULL, NULL, NULL,
    '["mgo", "diesel", "mdo"]', 'IMO Tier II',
    '["tug", "osv", "ferry"]', '["tug", "osv", "ferry"]',
    'available', '["APAC", "EMEA", "Americas"]',
    'manufacturer_datasheet', 'https://www.cat.com/',
    'Cat 3516C specification sheet', 0.9,
    NOW(), 'engine_master_data', 'Caterpillar 3516C high-speed marine diesel engine, flagship C-series variant. 16-cylinder V-configuration delivering 2000-2525 kW (2680-3385 bhp) at 1600-1800 RPM. Highest output in 3500 series. Features common rail fuel injection, ADEM A4 electronic management. IMO Tier II compliant. Designed for large tugs, offshore vessels, ferries requiring maximum power. Also known as Cat 3516C, CAT 3516C, or Caterpillar 3516C HD marine.'
)
ON CONFLICT (engine_model_id, rating_designation) DO UPDATE SET
    power_kw = EXCLUDED.power_kw,
    power_hp = EXCLUDED.power_hp,
    duty_class = EXCLUDED.duty_class,
    harmonized_duty_class = EXCLUDED.harmonized_duty_class,
    oem_rating_code = EXCLUDED.oem_rating_code,
    dry_weight_kg = EXCLUDED.dry_weight_kg,
    length_mm = EXCLUDED.length_mm,
    width_mm = EXCLUDED.width_mm,
    height_mm = EXCLUDED.height_mm,
    power_density_kw_per_kg = EXCLUDED.power_density_kw_per_kg,
    last_verified = NOW(),
    verified_by = EXCLUDED.verified_by;

INSERT INTO kb_engine_ratings (
    id, engine_model_id, rating_designation, rating_name, duty_class, iso_classification,
    harmonized_duty_class, oem_rating_code,
    power_kw, power_hp, rpm, load_factor_min, load_factor_max, annual_hours_min, annual_hours_max,
    dry_weight_kg, length_mm, width_mm, height_mm, power_density_kw_per_kg,
    fuel_types, emission_tier, application_profiles, primary_applications,
    availability_status, regions_available, data_source, data_source_url, data_source_document,
    data_confidence, last_verified, verified_by, notes
) VALUES (
    'bcbbb752-a850-480f-84d8-9c203a3ac248', '8ed27dbc-2170-4e22-8512-850cee9f8001', 'C12.9',
    'Cat C12.9', 'medium_duty', 'not_applicable',
    'MED', 'C12.9',
    537, 720.117, 1800,
    0.2, 0.8,
    2000, 4000,
    NULL, NULL,
    NULL, NULL, NULL,
    '["mgo", "diesel", "mdo"]', 'IMO Tier II',
    '["workboat", "fishing", "crew_boat"]', '["workboat", "fishing", "crew_boat"]',
    'available', '["APAC", "EMEA", "Americas"]',
    'manufacturer_datasheet', 'https://www.cat.com/',
    'Cat C12.9 specification sheet', 0.9,
    NOW(), 'engine_master_data', 'Caterpillar C12.9 high-speed marine diesel engine. 6-cylinder inline configuration delivering 373-537 kW (500-720 bhp) at 1800-2300 RPM. 12.9 liter displacement. Compact design ideal for smaller commercial vessels. Features ACERT technology, electronic fuel injection. IMO Tier II certified. Applications include workboats, fishing vessels, crew boats. Known as Cat C12.9, CAT C12, or Caterpillar C12.9 marine.'
)
ON CONFLICT (engine_model_id, rating_designation) DO UPDATE SET
    power_kw = EXCLUDED.power_kw,
    power_hp = EXCLUDED.power_hp,
    duty_class = EXCLUDED.duty_class,
    harmonized_duty_class = EXCLUDED.harmonized_duty_class,
    oem_rating_code = EXCLUDED.oem_rating_code,
    dry_weight_kg = EXCLUDED.dry_weight_kg,
    length_mm = EXCLUDED.length_mm,
    width_mm = EXCLUDED.width_mm,
    height_mm = EXCLUDED.height_mm,
    power_density_kw_per_kg = EXCLUDED.power_density_kw_per_kg,
    last_verified = NOW(),
    verified_by = EXCLUDED.verified_by;

INSERT INTO kb_engine_ratings (
    id, engine_model_id, rating_designation, rating_name, duty_class, iso_classification,
    harmonized_duty_class, oem_rating_code,
    power_kw, power_hp, rpm, load_factor_min, load_factor_max, annual_hours_min, annual_hours_max,
    dry_weight_kg, length_mm, width_mm, height_mm, power_density_kw_per_kg,
    fuel_types, emission_tier, application_profiles, primary_applications,
    availability_status, regions_available, data_source, data_source_url, data_source_document,
    data_confidence, last_verified, verified_by, notes
) VALUES (
    'c3d161b6-defa-499e-8c72-5705f945498e', 'f1d83cd9-6ed8-4eff-b38a-4ca9a8b63d77', 'C18',
    'Cat C18', 'medium_duty', 'not_applicable',
    'MED', 'C18',
    597, 800.577, 1800,
    0.2, 0.8,
    2000, 4000,
    NULL, NULL,
    NULL, NULL, NULL,
    '["mgo", "diesel", "mdo"]', 'IMO Tier II',
    '["workboat", "fishing", "tug", "crew_boat"]', '["workboat", "fishing", "tug"]',
    'available', '["APAC", "EMEA", "Americas"]',
    'manufacturer_datasheet', 'https://www.cat.com/',
    'Cat C18 specification sheet', 0.95,
    NOW(), 'engine_master_data', 'Caterpillar C18 high-speed marine diesel engine. 6-cylinder inline configuration delivering 447-597 kW (600-800 bhp) at 1800-2100 RPM. 18.1 liter displacement. Extremely popular workhorse for commercial marine applications. Features ACERT technology, common rail fuel injection, Cat Electronic Control Module. IMO Tier II and Tier III variants available. Applications include workboats, fishing vessels, small tugs, crew boats. Extensive global Cat dealer network. Also known as Cat C18, CAT C18 ACER'
)
ON CONFLICT (engine_model_id, rating_designation) DO UPDATE SET
    power_kw = EXCLUDED.power_kw,
    power_hp = EXCLUDED.power_hp,
    duty_class = EXCLUDED.duty_class,
    harmonized_duty_class = EXCLUDED.harmonized_duty_class,
    oem_rating_code = EXCLUDED.oem_rating_code,
    dry_weight_kg = EXCLUDED.dry_weight_kg,
    length_mm = EXCLUDED.length_mm,
    width_mm = EXCLUDED.width_mm,
    height_mm = EXCLUDED.height_mm,
    power_density_kw_per_kg = EXCLUDED.power_density_kw_per_kg,
    last_verified = NOW(),
    verified_by = EXCLUDED.verified_by;

INSERT INTO kb_engine_ratings (
    id, engine_model_id, rating_designation, rating_name, duty_class, iso_classification,
    harmonized_duty_class, oem_rating_code,
    power_kw, power_hp, rpm, load_factor_min, load_factor_max, annual_hours_min, annual_hours_max,
    dry_weight_kg, length_mm, width_mm, height_mm, power_density_kw_per_kg,
    fuel_types, emission_tier, application_profiles, primary_applications,
    availability_status, regions_available, data_source, data_source_url, data_source_document,
    data_confidence, last_verified, verified_by, notes
) VALUES (
    '4afb8a26-4912-4845-9bcb-8d376b019acb', 'f53c7c25-a699-4b85-b055-3514ed94c0ac', 'C18-ACERT',
    'Cat C18 ACERT', 'heavy_duty', 'not_applicable',
    'HVY', 'C18-ACERT',
    803, 1076.8229999999999, 1800,
    0.4, 0.8,
    3000, 5000,
    NULL, NULL,
    NULL, NULL, NULL,
    '["mgo", "diesel", "mdo"]', 'IMO Tier II',
    '["tug", "workboat", "osv"]', '["tug", "workboat", "osv"]',
    'available', '["APAC", "EMEA", "Americas"]',
    'manufacturer_datasheet', 'https://www.cat.com/',
    'Cat C18 ACERT specification sheet', 0.9,
    NOW(), 'engine_master_data', 'Caterpillar C18 ACERT heavy duty marine diesel engine. 6-cylinder inline configuration delivering 533-803 kW (715-1075 bhp) at 1800-2100 RPM. 18.1 liter displacement with ACERT technology for emissions reduction. Heavy duty rating for demanding commercial applications. IMO Tier II certified. Applications include tugs, workboats, OSVs. Known as Cat C18 ACERT HD, CAT C18 ACERT, or Caterpillar C18 heavy duty.'
)
ON CONFLICT (engine_model_id, rating_designation) DO UPDATE SET
    power_kw = EXCLUDED.power_kw,
    power_hp = EXCLUDED.power_hp,
    duty_class = EXCLUDED.duty_class,
    harmonized_duty_class = EXCLUDED.harmonized_duty_class,
    oem_rating_code = EXCLUDED.oem_rating_code,
    dry_weight_kg = EXCLUDED.dry_weight_kg,
    length_mm = EXCLUDED.length_mm,
    width_mm = EXCLUDED.width_mm,
    height_mm = EXCLUDED.height_mm,
    power_density_kw_per_kg = EXCLUDED.power_density_kw_per_kg,
    last_verified = NOW(),
    verified_by = EXCLUDED.verified_by;

INSERT INTO kb_engine_ratings (
    id, engine_model_id, rating_designation, rating_name, duty_class, iso_classification,
    harmonized_duty_class, oem_rating_code,
    power_kw, power_hp, rpm, load_factor_min, load_factor_max, annual_hours_min, annual_hours_max,
    dry_weight_kg, length_mm, width_mm, height_mm, power_density_kw_per_kg,
    fuel_types, emission_tier, application_profiles, primary_applications,
    availability_status, regions_available, data_source, data_source_url, data_source_document,
    data_confidence, last_verified, verified_by, notes
) VALUES (
    'a2e5bccf-6620-4b5d-a8b0-a226090aaf0f', 'f4227ce4-738b-4ff9-9978-7685feb7e668', 'C32',
    'Cat C32', 'medium_duty', 'not_applicable',
    'MED', 'C32',
    1417, 1900.197, 1800,
    0.2, 0.8,
    2000, 4000,
    NULL, NULL,
    NULL, NULL, NULL,
    '["mgo", "diesel", "mdo"]', 'IMO Tier II',
    '["tug", "osv", "ferry", "patrol", "yacht"]', '["tug", "osv", "ferry"]',
    'available', '["APAC", "EMEA", "Americas"]',
    'manufacturer_datasheet', 'https://www.cat.com/',
    'Cat C32 specification sheet', 0.95,
    NOW(), 'engine_master_data', 'Caterpillar C32 high-speed marine diesel engine. 12-cylinder V-configuration producing 746-1417 kW (1000-1900 bhp) at 1800-2300 RPM. 32.1 liter displacement. One of the most popular high-speed marine engines globally - direct competitor to MTU Series 2000. Features ACERT technology, common rail fuel injection, advanced electronic controls. IMO Tier II standard, Tier III with SCR available. Applications include tugs, OSVs, fast ferries, patrol boats, luxury yachts. Industry-leading Cat dealer sup'
)
ON CONFLICT (engine_model_id, rating_designation) DO UPDATE SET
    power_kw = EXCLUDED.power_kw,
    power_hp = EXCLUDED.power_hp,
    duty_class = EXCLUDED.duty_class,
    harmonized_duty_class = EXCLUDED.harmonized_duty_class,
    oem_rating_code = EXCLUDED.oem_rating_code,
    dry_weight_kg = EXCLUDED.dry_weight_kg,
    length_mm = EXCLUDED.length_mm,
    width_mm = EXCLUDED.width_mm,
    height_mm = EXCLUDED.height_mm,
    power_density_kw_per_kg = EXCLUDED.power_density_kw_per_kg,
    last_verified = NOW(),
    verified_by = EXCLUDED.verified_by;

INSERT INTO kb_engine_ratings (
    id, engine_model_id, rating_designation, rating_name, duty_class, iso_classification,
    harmonized_duty_class, oem_rating_code,
    power_kw, power_hp, rpm, load_factor_min, load_factor_max, annual_hours_min, annual_hours_max,
    dry_weight_kg, length_mm, width_mm, height_mm, power_density_kw_per_kg,
    fuel_types, emission_tier, application_profiles, primary_applications,
    availability_status, regions_available, data_source, data_source_url, data_source_document,
    data_confidence, last_verified, verified_by, notes
) VALUES (
    'efcec714-1019-403f-8022-ae7435cd90a9', 'c4f75f6a-f1a5-4362-b863-15a89ade282d', 'C32B',
    'Cat C32B', 'light_duty', 'not_applicable',
    'LGT', 'C32B',
    1491, 1999.431, 2300,
    0.0, 0.5,
    1000, 3000,
    NULL, NULL,
    NULL, NULL, NULL,
    '["mgo", "diesel", "mdo"]', 'IMO Tier II',
    '["fast_ferry", "yacht", "patrol"]', '["fast_ferry", "yacht", "patrol"]',
    'available', '["APAC", "EMEA", "Americas"]',
    'manufacturer_datasheet', 'https://www.cat.com/',
    'Cat C32B specification sheet', 0.9,
    NOW(), 'engine_master_data', 'Caterpillar C32B high-speed marine diesel engine, enhanced B-series variant with higher power density. 12-cylinder V-configuration delivering 1193-1491 kW (1600-2000 bhp) at 2300 RPM. 32.1 liter displacement. Premium variant for demanding applications requiring maximum power from C32 platform. Features enhanced ACERT technology, optimized turbocharging. IMO Tier II certified. Popular for fast ferries, large yachts, patrol vessels. Also referred to as Cat C32B, CAT C32B ACERT, Caterpillar C32B ma'
)
ON CONFLICT (engine_model_id, rating_designation) DO UPDATE SET
    power_kw = EXCLUDED.power_kw,
    power_hp = EXCLUDED.power_hp,
    duty_class = EXCLUDED.duty_class,
    harmonized_duty_class = EXCLUDED.harmonized_duty_class,
    oem_rating_code = EXCLUDED.oem_rating_code,
    dry_weight_kg = EXCLUDED.dry_weight_kg,
    length_mm = EXCLUDED.length_mm,
    width_mm = EXCLUDED.width_mm,
    height_mm = EXCLUDED.height_mm,
    power_density_kw_per_kg = EXCLUDED.power_density_kw_per_kg,
    last_verified = NOW(),
    verified_by = EXCLUDED.verified_by;

INSERT INTO kb_engine_ratings (
    id, engine_model_id, rating_designation, rating_name, duty_class, iso_classification,
    harmonized_duty_class, oem_rating_code,
    power_kw, power_hp, rpm, load_factor_min, load_factor_max, annual_hours_min, annual_hours_max,
    dry_weight_kg, length_mm, width_mm, height_mm, power_density_kw_per_kg,
    fuel_types, emission_tier, application_profiles, primary_applications,
    availability_status, regions_available, data_source, data_source_url, data_source_document,
    data_confidence, last_verified, verified_by, notes
) VALUES (
    'c8a4535a-d885-4481-846c-934ab4ef1bd7', '8100cada-ae29-48da-a2be-c7be71375372', 'D2676-LE',
    'MAN D2676 LE', 'medium_duty', 'not_applicable',
    'MED', 'D2676-LE',
    537, 720.117, 1800,
    0.2, 0.8,
    2000, 4000,
    NULL, NULL,
    NULL, NULL, NULL,
    '["mgo", "diesel", "mdo"]', 'IMO Tier II',
    '["workboat", "fishing", "crew_boat"]', '["workboat", "fishing", "crew_boat"]',
    'available', '["APAC", "EMEA", "Americas"]',
    'manufacturer_datasheet', 'https://www.man.eu/engines/',
    'MAN D2676 LE specification sheet', 0.9,
    NOW(), 'engine_master_data', 'MAN D2676 LE high-speed marine diesel engine. 6-cylinder inline configuration delivering 331-537 kW (450-720 hp) at 1800-2100 RPM. 12.4 liter displacement. Compact high-speed design for smaller commercial vessels. Features common rail injection, electronic management. IMO Tier II certified. Applications include workboats, fishing vessels, crew boats. Known as MAN D2676, D26 inline, or MAN 6-cyl marine.'
)
ON CONFLICT (engine_model_id, rating_designation) DO UPDATE SET
    power_kw = EXCLUDED.power_kw,
    power_hp = EXCLUDED.power_hp,
    duty_class = EXCLUDED.duty_class,
    harmonized_duty_class = EXCLUDED.harmonized_duty_class,
    oem_rating_code = EXCLUDED.oem_rating_code,
    dry_weight_kg = EXCLUDED.dry_weight_kg,
    length_mm = EXCLUDED.length_mm,
    width_mm = EXCLUDED.width_mm,
    height_mm = EXCLUDED.height_mm,
    power_density_kw_per_kg = EXCLUDED.power_density_kw_per_kg,
    last_verified = NOW(),
    verified_by = EXCLUDED.verified_by;

INSERT INTO kb_engine_ratings (
    id, engine_model_id, rating_designation, rating_name, duty_class, iso_classification,
    harmonized_duty_class, oem_rating_code,
    power_kw, power_hp, rpm, load_factor_min, load_factor_max, annual_hours_min, annual_hours_max,
    dry_weight_kg, length_mm, width_mm, height_mm, power_density_kw_per_kg,
    fuel_types, emission_tier, application_profiles, primary_applications,
    availability_status, regions_available, data_source, data_source_url, data_source_document,
    data_confidence, last_verified, verified_by, notes
) VALUES (
    '37ab64a9-4161-49c9-8c40-f1d22cf0bd59', '05a375e5-f410-4d24-aa89-14fde8196bd4', 'LE463',
    'MAN D2862 LE463', 'light_duty', 'not_applicable',
    'LGT', 'LE463',
    1044, 1400.004, 2100,
    0.0, 0.5,
    1000, 3000,
    2270, 1631,
    1153, 1289, 0.4599,
    '["mgo", "diesel", "mdo"]', 'IMO Tier II',
    '["fast_craft", "patrol", "yacht"]', '["fast_craft", "patrol", "yacht"]',
    'available', '["APAC", "EMEA", "Americas"]',
    'manufacturer_datasheet', 'https://www.man.eu/engines/',
    'MAN D2862 LE463 specification sheet', 0.95,
    NOW(), 'engine_master_data', 'MAN D2862 LE463 high-speed marine diesel engine from MAN Engines (MAN Truck & Bus). 12-cylinder V-configuration producing 735-1044 kW (1000-1400 mhp) at 2100 RPM. 24.2 liter displacement. Compact design for fast craft, patrol boats, and luxury yachts. Features common rail injection, EDC electronic controls. IMO Tier II certified. Note: This is MAN Engines (truck-derived), not MAN Energy Solutions (large engines). Known as MAN D2862, D28 marine, or MAN V12 marine.'
)
ON CONFLICT (engine_model_id, rating_designation) DO UPDATE SET
    power_kw = EXCLUDED.power_kw,
    power_hp = EXCLUDED.power_hp,
    duty_class = EXCLUDED.duty_class,
    harmonized_duty_class = EXCLUDED.harmonized_duty_class,
    oem_rating_code = EXCLUDED.oem_rating_code,
    dry_weight_kg = EXCLUDED.dry_weight_kg,
    length_mm = EXCLUDED.length_mm,
    width_mm = EXCLUDED.width_mm,
    height_mm = EXCLUDED.height_mm,
    power_density_kw_per_kg = EXCLUDED.power_density_kw_per_kg,
    last_verified = NOW(),
    verified_by = EXCLUDED.verified_by;

INSERT INTO kb_engine_ratings (
    id, engine_model_id, rating_designation, rating_name, duty_class, iso_classification,
    harmonized_duty_class, oem_rating_code,
    power_kw, power_hp, rpm, load_factor_min, load_factor_max, annual_hours_min, annual_hours_max,
    dry_weight_kg, length_mm, width_mm, height_mm, power_density_kw_per_kg,
    fuel_types, emission_tier, application_profiles, primary_applications,
    availability_status, regions_available, data_source, data_source_url, data_source_document,
    data_confidence, last_verified, verified_by, notes
) VALUES (
    'ceaf6366-7527-45c7-8c18-dae731ab9066', '09c31ebb-e6b4-4a88-bc54-9fbe8d17b558', 'LE443',
    'MAN D2862 LE443', 'heavy_duty', 'not_applicable',
    'HVY', 'LE443',
    1176, 1577.016, 2100,
    0.4, 0.8,
    3000, 5000,
    NULL, NULL,
    NULL, NULL, NULL,
    '["mgo", "diesel", "mdo"]', 'IMO Tier II',
    '["tug", "osv", "patrol"]', '["tug", "osv", "patrol"]',
    'available', '["APAC", "EMEA", "Americas"]',
    'manufacturer_datasheet', 'https://www.man.eu/engines/',
    'MAN D2862 LE443 specification sheet', 0.9,
    NOW(), 'engine_master_data', 'MAN D2862 LE443 heavy duty marine diesel engine. 12-cylinder V-configuration producing 882-1176 kW (1200-1575 hp) at 2100 RPM. 24.2 liter displacement. Heavy duty rating for commercial applications requiring durability. Features common rail injection, EDC electronic controls. IMO Tier II certified. Applications include tugs, OSVs, patrol vessels. Known as MAN D2862 HD, D28 heavy duty, or MAN V12 commercial.'
)
ON CONFLICT (engine_model_id, rating_designation) DO UPDATE SET
    power_kw = EXCLUDED.power_kw,
    power_hp = EXCLUDED.power_hp,
    duty_class = EXCLUDED.duty_class,
    harmonized_duty_class = EXCLUDED.harmonized_duty_class,
    oem_rating_code = EXCLUDED.oem_rating_code,
    dry_weight_kg = EXCLUDED.dry_weight_kg,
    length_mm = EXCLUDED.length_mm,
    width_mm = EXCLUDED.width_mm,
    height_mm = EXCLUDED.height_mm,
    power_density_kw_per_kg = EXCLUDED.power_density_kw_per_kg,
    last_verified = NOW(),
    verified_by = EXCLUDED.verified_by;

INSERT INTO kb_engine_ratings (
    id, engine_model_id, rating_designation, rating_name, duty_class, iso_classification,
    harmonized_duty_class, oem_rating_code,
    power_kw, power_hp, rpm, load_factor_min, load_factor_max, annual_hours_min, annual_hours_max,
    dry_weight_kg, length_mm, width_mm, height_mm, power_density_kw_per_kg,
    fuel_types, emission_tier, application_profiles, primary_applications,
    availability_status, regions_available, data_source, data_source_url, data_source_document,
    data_confidence, last_verified, verified_by, notes
) VALUES (
    '6168df5e-753b-4f13-b2b2-1ab725d60e46', 'f51f008b-df8e-49d1-bbec-716a3937ee46', 'LE433',
    'MAN D2868 LE433', 'light_duty', 'not_applicable',
    'LGT', 'LE433',
    882, 1182.762, 2100,
    0.0, 0.5,
    1000, 3000,
    NULL, NULL,
    NULL, NULL, NULL,
    '["mgo", "diesel", "mdo"]', 'IMO Tier II',
    '["fast_boat", "pilot", "ferry"]', '["fast_boat", "pilot", "ferry"]',
    'available', '["APAC", "EMEA", "Americas"]',
    'manufacturer_datasheet', 'https://www.man.eu/engines/',
    'MAN D2868 LE433 specification sheet', 0.9,
    NOW(), 'engine_master_data', 'MAN D2868 LE433 high-speed marine diesel engine from MAN Engines. 8-cylinder V-configuration producing 441-882 kW (600-1200 hp) at 2100-2300 RPM. 16.1 liter displacement. Compact and lightweight for fast boats, pilot vessels, and small ferries. Common rail injection with electronic management. IMO Tier II compliant. Part of MAN Engines marine portfolio (MAN Truck & Bus division). Also referred to as MAN D2868, D26 marine, or MAN V8 marine.'
)
ON CONFLICT (engine_model_id, rating_designation) DO UPDATE SET
    power_kw = EXCLUDED.power_kw,
    power_hp = EXCLUDED.power_hp,
    duty_class = EXCLUDED.duty_class,
    harmonized_duty_class = EXCLUDED.harmonized_duty_class,
    oem_rating_code = EXCLUDED.oem_rating_code,
    dry_weight_kg = EXCLUDED.dry_weight_kg,
    length_mm = EXCLUDED.length_mm,
    width_mm = EXCLUDED.width_mm,
    height_mm = EXCLUDED.height_mm,
    power_density_kw_per_kg = EXCLUDED.power_density_kw_per_kg,
    last_verified = NOW(),
    verified_by = EXCLUDED.verified_by;

INSERT INTO kb_engine_ratings (
    id, engine_model_id, rating_designation, rating_name, duty_class, iso_classification,
    harmonized_duty_class, oem_rating_code,
    power_kw, power_hp, rpm, load_factor_min, load_factor_max, annual_hours_min, annual_hours_max,
    dry_weight_kg, length_mm, width_mm, height_mm, power_density_kw_per_kg,
    fuel_types, emission_tier, application_profiles, primary_applications,
    availability_status, regions_available, data_source, data_source_url, data_source_document,
    data_confidence, last_verified, verified_by, notes
) VALUES (
    '82e00e39-f890-4943-bea6-835151cc8b5d', '419318d5-f6c6-4f1a-83a5-8d05177173f0', 'LE423',
    'MAN D2868 LE423', 'heavy_duty', 'not_applicable',
    'HVY', 'LE423',
    993, 1331.613, 2100,
    0.4, 0.8,
    3000, 5000,
    NULL, NULL,
    NULL, NULL, NULL,
    '["mgo", "diesel", "mdo"]', 'IMO Tier II',
    '["tug", "workboat", "patrol"]', '["tug", "workboat", "patrol"]',
    'available', '["APAC", "EMEA", "Americas"]',
    'manufacturer_datasheet', 'https://www.man.eu/engines/',
    'MAN D2868 LE423 specification sheet', 0.9,
    NOW(), 'engine_master_data', 'MAN D2868 LE423 heavy duty marine diesel engine. 8-cylinder V-configuration producing 735-993 kW (1000-1330 hp) at 2100 RPM. 16.1 liter displacement. Heavy duty rating for demanding commercial operations. Features common rail injection, electronic management. IMO Tier II certified. Applications include tugs, workboats, patrol vessels. Known as MAN D2868 HD, D26 heavy duty, or MAN V8 commercial.'
)
ON CONFLICT (engine_model_id, rating_designation) DO UPDATE SET
    power_kw = EXCLUDED.power_kw,
    power_hp = EXCLUDED.power_hp,
    duty_class = EXCLUDED.duty_class,
    harmonized_duty_class = EXCLUDED.harmonized_duty_class,
    oem_rating_code = EXCLUDED.oem_rating_code,
    dry_weight_kg = EXCLUDED.dry_weight_kg,
    length_mm = EXCLUDED.length_mm,
    width_mm = EXCLUDED.width_mm,
    height_mm = EXCLUDED.height_mm,
    power_density_kw_per_kg = EXCLUDED.power_density_kw_per_kg,
    last_verified = NOW(),
    verified_by = EXCLUDED.verified_by;

INSERT INTO kb_engine_ratings (
    id, engine_model_id, rating_designation, rating_name, duty_class, iso_classification,
    harmonized_duty_class, oem_rating_code,
    power_kw, power_hp, rpm, load_factor_min, load_factor_max, annual_hours_min, annual_hours_max,
    dry_weight_kg, length_mm, width_mm, height_mm, power_density_kw_per_kg,
    fuel_types, emission_tier, application_profiles, primary_applications,
    availability_status, regions_available, data_source, data_source_url, data_source_document,
    data_confidence, last_verified, verified_by, notes
) VALUES (
    'e6a3fada-e863-449c-b80b-654d3ea11140', 'ed84a3ee-86ce-4f4a-a0c0-7df785ef2a32', 'V12-2000',
    'MAN V12-2000', 'medium_duty', 'not_applicable',
    'MED', 'V12-2000',
    1324, 1775.484, 1800,
    0.2, 0.8,
    2000, 4000,
    NULL, NULL,
    NULL, NULL, NULL,
    '["mgo", "diesel", "mdo"]', 'IMO Tier II',
    '["osv", "ferry", "patrol"]', '["osv", "ferry", "patrol"]',
    'available', '["APAC", "EMEA", "Americas"]',
    'manufacturer_datasheet', 'https://www.man.eu/engines/',
    'MAN V12-2000 specification sheet', 0.9,
    NOW(), 'engine_master_data', 'MAN V12-2000 high-speed marine diesel engine. 12-cylinder V-configuration producing 1044-1324 kW (1400-1775 hp) at 1800-2100 RPM. 24.2 liter displacement. Direct competitor to MTU Series 2000. Features common rail injection, advanced electronic management. IMO Tier II certified. Applications include OSVs, ferries, patrol vessels. Known as MAN V12-2000, MAN 2000 marine, or V12 high-speed.'
)
ON CONFLICT (engine_model_id, rating_designation) DO UPDATE SET
    power_kw = EXCLUDED.power_kw,
    power_hp = EXCLUDED.power_hp,
    duty_class = EXCLUDED.duty_class,
    harmonized_duty_class = EXCLUDED.harmonized_duty_class,
    oem_rating_code = EXCLUDED.oem_rating_code,
    dry_weight_kg = EXCLUDED.dry_weight_kg,
    length_mm = EXCLUDED.length_mm,
    width_mm = EXCLUDED.width_mm,
    height_mm = EXCLUDED.height_mm,
    power_density_kw_per_kg = EXCLUDED.power_density_kw_per_kg,
    last_verified = NOW(),
    verified_by = EXCLUDED.verified_by;

INSERT INTO kb_engine_ratings (
    id, engine_model_id, rating_designation, rating_name, duty_class, iso_classification,
    harmonized_duty_class, oem_rating_code,
    power_kw, power_hp, rpm, load_factor_min, load_factor_max, annual_hours_min, annual_hours_max,
    dry_weight_kg, length_mm, width_mm, height_mm, power_density_kw_per_kg,
    fuel_types, emission_tier, application_profiles, primary_applications,
    availability_status, regions_available, data_source, data_source_url, data_source_document,
    data_confidence, last_verified, verified_by, notes
) VALUES (
    '2e8052b4-c235-4071-a1bd-dd37450c9ef9', '5e96f00a-1022-4a72-be7e-5720362ce4aa', 'V12-2000CR',
    'MAN V12-2000CR', 'heavy_duty', 'not_applicable',
    'HVY', 'V12-2000CR',
    1471, 1972.6109999999999, 1800,
    0.4, 0.8,
    3000, 5000,
    NULL, NULL,
    NULL, NULL, NULL,
    '["mgo", "diesel", "mdo"]', 'IMO Tier II',
    '["tug", "osv", "naval"]', '["tug", "osv", "naval"]',
    'available', '["APAC", "EMEA", "Americas"]',
    'manufacturer_datasheet', 'https://www.man.eu/engines/',
    'MAN V12-2000CR specification sheet', 0.9,
    NOW(), 'engine_master_data', 'MAN V12-2000CR common rail heavy duty marine diesel engine. 12-cylinder V-configuration producing 1193-1471 kW (1600-1970 hp) at 1800-2100 RPM. 24.2 liter displacement. Flagship MAN marine engine with common rail fuel system. Features advanced electronic controls, high power density. IMO Tier II certified. Applications include tugs, OSVs, naval vessels. Known as MAN V12-2000CR, MAN CR marine, or V12 flagship.'
)
ON CONFLICT (engine_model_id, rating_designation) DO UPDATE SET
    power_kw = EXCLUDED.power_kw,
    power_hp = EXCLUDED.power_hp,
    duty_class = EXCLUDED.duty_class,
    harmonized_duty_class = EXCLUDED.harmonized_duty_class,
    oem_rating_code = EXCLUDED.oem_rating_code,
    dry_weight_kg = EXCLUDED.dry_weight_kg,
    length_mm = EXCLUDED.length_mm,
    width_mm = EXCLUDED.width_mm,
    height_mm = EXCLUDED.height_mm,
    power_density_kw_per_kg = EXCLUDED.power_density_kw_per_kg,
    last_verified = NOW(),
    verified_by = EXCLUDED.verified_by;

INSERT INTO kb_engine_ratings (
    id, engine_model_id, rating_designation, rating_name, duty_class, iso_classification,
    harmonized_duty_class, oem_rating_code,
    power_kw, power_hp, rpm, load_factor_min, load_factor_max, annual_hours_min, annual_hours_max,
    dry_weight_kg, length_mm, width_mm, height_mm, power_density_kw_per_kg,
    fuel_types, emission_tier, application_profiles, primary_applications,
    availability_status, regions_available, data_source, data_source_url, data_source_document,
    data_confidence, last_verified, verified_by, notes
) VALUES (
    '3f512ae8-0a1d-4608-a8b9-86f4759b98d9', 'c57ad681-de44-4603-9b0e-69f135526d35', 'D11-M',
    'Volvo Penta D11', 'medium_duty', 'not_applicable',
    'MED', 'D11-M',
    406, 544.446, 1800,
    0.2, 0.8,
    2000, 4000,
    NULL, NULL,
    NULL, NULL, NULL,
    '["mgo", "diesel", "mdo"]', 'IMO Tier II',
    '["workboat", "fishing", "crew_boat"]', '["workboat", "fishing", "crew_boat"]',
    'available', '["APAC", "EMEA", "Americas"]',
    'manufacturer_datasheet', 'https://www.volvopenta.com/',
    'Volvo Penta D11 specification sheet', 0.9,
    NOW(), 'engine_master_data', 'Volvo Penta D11 high-speed marine diesel engine. 6-cylinder inline configuration producing 298-406 kW (400-545 hp) at 1800-2300 RPM. 10.8 liter displacement. Compact commercial marine design. Features common rail injection, EMS electronic management. IMO Tier II certified. Applications include workboats, fishing vessels, crew boats. Known as Volvo D11 marine, Volvo Penta D11, or D11 commercial.'
)
ON CONFLICT (engine_model_id, rating_designation) DO UPDATE SET
    power_kw = EXCLUDED.power_kw,
    power_hp = EXCLUDED.power_hp,
    duty_class = EXCLUDED.duty_class,
    harmonized_duty_class = EXCLUDED.harmonized_duty_class,
    oem_rating_code = EXCLUDED.oem_rating_code,
    dry_weight_kg = EXCLUDED.dry_weight_kg,
    length_mm = EXCLUDED.length_mm,
    width_mm = EXCLUDED.width_mm,
    height_mm = EXCLUDED.height_mm,
    power_density_kw_per_kg = EXCLUDED.power_density_kw_per_kg,
    last_verified = NOW(),
    verified_by = EXCLUDED.verified_by;

INSERT INTO kb_engine_ratings (
    id, engine_model_id, rating_designation, rating_name, duty_class, iso_classification,
    harmonized_duty_class, oem_rating_code,
    power_kw, power_hp, rpm, load_factor_min, load_factor_max, annual_hours_min, annual_hours_max,
    dry_weight_kg, length_mm, width_mm, height_mm, power_density_kw_per_kg,
    fuel_types, emission_tier, application_profiles, primary_applications,
    availability_status, regions_available, data_source, data_source_url, data_source_document,
    data_confidence, last_verified, verified_by, notes
) VALUES (
    '9b0d856d-42c2-4c0a-be51-6946bfe91c2a', 'd3473c61-f4ae-48f1-9da8-f4e46450d108', 'IPS1200',
    'Volvo Penta D13-IPS1200', 'light_duty', 'not_applicable',
    'LGT', 'IPS1200',
    662, 887.742, 2300,
    0.0, 0.5,
    1000, 3000,
    NULL, NULL,
    NULL, NULL, NULL,
    '["mgo", "diesel", "mdo"]', 'IMO Tier II',
    '["yacht", "patrol", "pilot"]', '["yacht", "patrol", "pilot"]',
    'available', '["APAC", "EMEA", "Americas"]',
    'manufacturer_datasheet', 'https://www.volvopenta.com/',
    'Volvo Penta D13-IPS1200 specification sheet', 0.9,
    NOW(), 'engine_master_data', 'Volvo Penta D13-IPS1200 high-speed marine diesel engine with IPS pod drive. 6-cylinder inline producing 588-662 kW (800-900 hp) at 2300-2400 RPM. 12.8 liter displacement. IPS system with forward-facing counter-rotating propellers. Features common rail injection, EVC electronic controls. IMO Tier II certified. Applications include yachts, patrol vessels, pilot boats. Known as Volvo Penta IPS1200, D13 IPS, or Volvo IPS pod.'
)
ON CONFLICT (engine_model_id, rating_designation) DO UPDATE SET
    power_kw = EXCLUDED.power_kw,
    power_hp = EXCLUDED.power_hp,
    duty_class = EXCLUDED.duty_class,
    harmonized_duty_class = EXCLUDED.harmonized_duty_class,
    oem_rating_code = EXCLUDED.oem_rating_code,
    dry_weight_kg = EXCLUDED.dry_weight_kg,
    length_mm = EXCLUDED.length_mm,
    width_mm = EXCLUDED.width_mm,
    height_mm = EXCLUDED.height_mm,
    power_density_kw_per_kg = EXCLUDED.power_density_kw_per_kg,
    last_verified = NOW(),
    verified_by = EXCLUDED.verified_by;

INSERT INTO kb_engine_ratings (
    id, engine_model_id, rating_designation, rating_name, duty_class, iso_classification,
    harmonized_duty_class, oem_rating_code,
    power_kw, power_hp, rpm, load_factor_min, load_factor_max, annual_hours_min, annual_hours_max,
    dry_weight_kg, length_mm, width_mm, height_mm, power_density_kw_per_kg,
    fuel_types, emission_tier, application_profiles, primary_applications,
    availability_status, regions_available, data_source, data_source_url, data_source_document,
    data_confidence, last_verified, verified_by, notes
) VALUES (
    '7d7d5805-270e-4d19-8926-aa126ab08161', 'c1fd75fb-566e-439b-bcb7-0c1d1d98fb78', 'IPS1350',
    'Volvo Penta D13-IPS1350', 'light_duty', 'not_applicable',
    'LGT', 'IPS1350',
    735, 985.635, 2300,
    0.0, 0.5,
    1000, 3000,
    NULL, NULL,
    NULL, NULL, NULL,
    '["mgo", "diesel", "mdo"]', 'IMO Tier II',
    '["yacht", "fast_cruiser"]', '["yacht", "fast_cruiser"]',
    'available', '["APAC", "EMEA", "Americas"]',
    'manufacturer_datasheet', 'https://www.volvopenta.com/',
    'Volvo Penta D13-IPS1350 specification sheet', 0.95,
    NOW(), 'engine_master_data', 'Volvo Penta D13-IPS1350 high-speed marine diesel engine with IPS pod drive system. 6-cylinder inline configuration producing 662-735 kW (900-1000 hp) at 2300-2400 RPM. 12.8 liter displacement. Revolutionary IPS (Inboard Performance System) with forward-facing counter-rotating propellers. Features common rail injection, EVC electronic controls. IMO Tier II compliant. Ideal for luxury motor yachts and fast cruisers. Also known as Volvo Penta IPS1350, D13 IPS, or Volvo IPS pod system.'
)
ON CONFLICT (engine_model_id, rating_designation) DO UPDATE SET
    power_kw = EXCLUDED.power_kw,
    power_hp = EXCLUDED.power_hp,
    duty_class = EXCLUDED.duty_class,
    harmonized_duty_class = EXCLUDED.harmonized_duty_class,
    oem_rating_code = EXCLUDED.oem_rating_code,
    dry_weight_kg = EXCLUDED.dry_weight_kg,
    length_mm = EXCLUDED.length_mm,
    width_mm = EXCLUDED.width_mm,
    height_mm = EXCLUDED.height_mm,
    power_density_kw_per_kg = EXCLUDED.power_density_kw_per_kg,
    last_verified = NOW(),
    verified_by = EXCLUDED.verified_by;

INSERT INTO kb_engine_ratings (
    id, engine_model_id, rating_designation, rating_name, duty_class, iso_classification,
    harmonized_duty_class, oem_rating_code,
    power_kw, power_hp, rpm, load_factor_min, load_factor_max, annual_hours_min, annual_hours_max,
    dry_weight_kg, length_mm, width_mm, height_mm, power_density_kw_per_kg,
    fuel_types, emission_tier, application_profiles, primary_applications,
    availability_status, regions_available, data_source, data_source_url, data_source_document,
    data_confidence, last_verified, verified_by, notes
) VALUES (
    '482a1da1-2451-4029-9493-452f6b8e61d5', '75ffb79d-253e-4457-b4f1-807466e487d8', 'D13-800',
    'Volvo Penta D13-800', 'medium_duty', 'not_applicable',
    'MED', 'D13-800',
    588, 788.508, 2300,
    0.2, 0.8,
    2000, 4000,
    NULL, NULL,
    NULL, NULL, NULL,
    '["mgo", "diesel", "mdo"]', 'IMO Tier II',
    '["workboat", "ferry", "fishing"]', '["workboat", "ferry", "fishing"]',
    'available', '["APAC", "EMEA", "Americas"]',
    'manufacturer_datasheet', 'https://www.volvopenta.com/',
    'Volvo Penta D13-800 specification sheet', 0.9,
    NOW(), 'engine_master_data', 'Volvo Penta D13-800 high-speed marine diesel engine for commercial applications. 6-cylinder inline configuration producing 515-588 kW (700-800 hp) at 2300 RPM. 12.8 liter displacement. Shaft-line installation for workboats, small ferries, and fishing vessels. Features common rail fuel injection, EMS electronic management. IMO Tier II certified. Excellent fuel efficiency and reliability. Also referred to as Volvo D13 marine, Volvo Penta D13-800, or D13 commercial.'
)
ON CONFLICT (engine_model_id, rating_designation) DO UPDATE SET
    power_kw = EXCLUDED.power_kw,
    power_hp = EXCLUDED.power_hp,
    duty_class = EXCLUDED.duty_class,
    harmonized_duty_class = EXCLUDED.harmonized_duty_class,
    oem_rating_code = EXCLUDED.oem_rating_code,
    dry_weight_kg = EXCLUDED.dry_weight_kg,
    length_mm = EXCLUDED.length_mm,
    width_mm = EXCLUDED.width_mm,
    height_mm = EXCLUDED.height_mm,
    power_density_kw_per_kg = EXCLUDED.power_density_kw_per_kg,
    last_verified = NOW(),
    verified_by = EXCLUDED.verified_by;

INSERT INTO kb_engine_ratings (
    id, engine_model_id, rating_designation, rating_name, duty_class, iso_classification,
    harmonized_duty_class, oem_rating_code,
    power_kw, power_hp, rpm, load_factor_min, load_factor_max, annual_hours_min, annual_hours_max,
    dry_weight_kg, length_mm, width_mm, height_mm, power_density_kw_per_kg,
    fuel_types, emission_tier, application_profiles, primary_applications,
    availability_status, regions_available, data_source, data_source_url, data_source_document,
    data_confidence, last_verified, verified_by, notes
) VALUES (
    '5fa39f45-f74f-4337-9fe7-482348000efb', 'f4d21023-40e7-458c-9df7-c7fe4dba356d', 'D13-MH',
    'Volvo Penta D13 MH', 'heavy_duty', 'not_applicable',
    'HVY', 'D13-MH',
    735, 985.635, 2100,
    0.4, 0.8,
    3000, 5000,
    NULL, NULL,
    NULL, NULL, NULL,
    '["mgo", "diesel", "mdo"]', 'IMO Tier II',
    '["tug", "osv", "workboat"]', '["tug", "osv", "workboat"]',
    'available', '["APAC", "EMEA", "Americas"]',
    'manufacturer_datasheet', 'https://www.volvopenta.com/',
    'Volvo Penta D13 MH specification sheet', 0.9,
    NOW(), 'engine_master_data', 'Volvo Penta D13 MH heavy duty marine diesel engine. 6-cylinder inline producing 625-735 kW (840-985 hp) at 2100-2300 RPM. 12.8 liter displacement. Heavy duty commercial rating for demanding operations. Features common rail injection, EMS electronic management. IMO Tier II certified. Applications include tugs, OSVs, workboats. Known as Volvo D13 MH, Volvo Penta D13 HD, or D13 heavy duty.'
)
ON CONFLICT (engine_model_id, rating_designation) DO UPDATE SET
    power_kw = EXCLUDED.power_kw,
    power_hp = EXCLUDED.power_hp,
    duty_class = EXCLUDED.duty_class,
    harmonized_duty_class = EXCLUDED.harmonized_duty_class,
    oem_rating_code = EXCLUDED.oem_rating_code,
    dry_weight_kg = EXCLUDED.dry_weight_kg,
    length_mm = EXCLUDED.length_mm,
    width_mm = EXCLUDED.width_mm,
    height_mm = EXCLUDED.height_mm,
    power_density_kw_per_kg = EXCLUDED.power_density_kw_per_kg,
    last_verified = NOW(),
    verified_by = EXCLUDED.verified_by;

INSERT INTO kb_engine_ratings (
    id, engine_model_id, rating_designation, rating_name, duty_class, iso_classification,
    harmonized_duty_class, oem_rating_code,
    power_kw, power_hp, rpm, load_factor_min, load_factor_max, annual_hours_min, annual_hours_max,
    dry_weight_kg, length_mm, width_mm, height_mm, power_density_kw_per_kg,
    fuel_types, emission_tier, application_profiles, primary_applications,
    availability_status, regions_available, data_source, data_source_url, data_source_document,
    data_confidence, last_verified, verified_by, notes
) VALUES (
    '0c3c4bf3-0736-4e1b-a289-751fd04c2389', 'ecd4e332-c279-46b2-b1a9-eb7dd3b85d5e', '6AYM-ETE',
    'Yanmar 6AYM-ETE', 'medium_duty', 'not_applicable',
    'MED', '6AYM-ETE',
    563, 754.983, 1900,
    0.2, 0.8,
    2000, 4000,
    NULL, NULL,
    NULL, NULL, NULL,
    '["mgo", "diesel", "mdo"]', 'IMO Tier II',
    '["workboat", "fishing", "ferry"]', '["workboat", "fishing", "ferry"]',
    'available', '["APAC", "EMEA", "Americas"]',
    'manufacturer_datasheet', 'https://www.yanmar.com/',
    'Yanmar 6AYM-ETE specification sheet', 0.95,
    NOW(), 'engine_master_data', 'Yanmar 6AYM-ETE high-speed marine diesel engine. 6-cylinder inline configuration producing 485-563 kW (650-755 hp) at 1900 RPM. 20.4 liter displacement. Japanese-built reliability for workboats, fishing vessels, and small ferries. Features electronic fuel injection with ETE turbocharging. IMO Tier II compliant. Known for durability and fuel economy. Popular in Asian markets. Also referred to as Yanmar 6AYM, 6AY marine, or Yanmar AYM series.'
)
ON CONFLICT (engine_model_id, rating_designation) DO UPDATE SET
    power_kw = EXCLUDED.power_kw,
    power_hp = EXCLUDED.power_hp,
    duty_class = EXCLUDED.duty_class,
    harmonized_duty_class = EXCLUDED.harmonized_duty_class,
    oem_rating_code = EXCLUDED.oem_rating_code,
    dry_weight_kg = EXCLUDED.dry_weight_kg,
    length_mm = EXCLUDED.length_mm,
    width_mm = EXCLUDED.width_mm,
    height_mm = EXCLUDED.height_mm,
    power_density_kw_per_kg = EXCLUDED.power_density_kw_per_kg,
    last_verified = NOW(),
    verified_by = EXCLUDED.verified_by;

INSERT INTO kb_engine_ratings (
    id, engine_model_id, rating_designation, rating_name, duty_class, iso_classification,
    harmonized_duty_class, oem_rating_code,
    power_kw, power_hp, rpm, load_factor_min, load_factor_max, annual_hours_min, annual_hours_max,
    dry_weight_kg, length_mm, width_mm, height_mm, power_density_kw_per_kg,
    fuel_types, emission_tier, application_profiles, primary_applications,
    availability_status, regions_available, data_source, data_source_url, data_source_document,
    data_confidence, last_verified, verified_by, notes
) VALUES (
    'c50542cb-7bb3-476d-bd15-2e3e15c00a2d', '7f9b5b17-7199-40e8-bc6b-a151c404fe2d', '6AYEM-GT',
    'Yanmar 6AYEM-GT', 'medium_duty', 'not_applicable',
    'MED', '6AYEM-GT',
    749, 1004.409, 1840,
    0.2, 0.8,
    2000, 4000,
    NULL, NULL,
    NULL, NULL, NULL,
    '["mgo", "diesel", "mdo"]', 'IMO Tier II',
    '["workboat", "patrol", "fast_craft"]', '["workboat", "patrol", "fast_craft"]',
    'available', '["APAC", "EMEA", "Americas"]',
    'manufacturer_datasheet', 'https://www.yanmar.com/',
    'Yanmar 6AYEM-GT specification sheet', 0.95,
    NOW(), 'engine_master_data', 'Yanmar 6AYEM-GT high-speed marine diesel engine with enhanced GT turbocharging. 6-cylinder inline configuration producing 485-749 kW (650-1005 hp) at 1840-2000 RPM. 20.4 liter displacement. Higher output variant of the AY series for fast workboats and patrol craft. Features advanced turbocharging for improved response. IMO Tier II certified. Excellent power-to-weight ratio. Known as Yanmar 6AYEM, 6AY-GT marine, or Yanmar GT series.'
)
ON CONFLICT (engine_model_id, rating_designation) DO UPDATE SET
    power_kw = EXCLUDED.power_kw,
    power_hp = EXCLUDED.power_hp,
    duty_class = EXCLUDED.duty_class,
    harmonized_duty_class = EXCLUDED.harmonized_duty_class,
    oem_rating_code = EXCLUDED.oem_rating_code,
    dry_weight_kg = EXCLUDED.dry_weight_kg,
    length_mm = EXCLUDED.length_mm,
    width_mm = EXCLUDED.width_mm,
    height_mm = EXCLUDED.height_mm,
    power_density_kw_per_kg = EXCLUDED.power_density_kw_per_kg,
    last_verified = NOW(),
    verified_by = EXCLUDED.verified_by;

INSERT INTO kb_engine_ratings (
    id, engine_model_id, rating_designation, rating_name, duty_class, iso_classification,
    harmonized_duty_class, oem_rating_code,
    power_kw, power_hp, rpm, load_factor_min, load_factor_max, annual_hours_min, annual_hours_max,
    dry_weight_kg, length_mm, width_mm, height_mm, power_density_kw_per_kg,
    fuel_types, emission_tier, application_profiles, primary_applications,
    availability_status, regions_available, data_source, data_source_url, data_source_document,
    data_confidence, last_verified, verified_by, notes
) VALUES (
    'fc78c52b-80e6-48fc-9ecb-e77efdb92f5c', '0066c62d-fc7b-4db4-98cc-ca31b27f9967', '8AYM-WET',
    'Yanmar 8AYM-WET', 'medium_duty', 'not_applicable',
    'MED', '8AYM-WET',
    716, 960.156, 1900,
    0.2, 0.8,
    2000, 4000,
    NULL, NULL,
    NULL, NULL, NULL,
    '["mgo", "diesel", "mdo"]', 'IMO Tier II',
    '["ferry", "osv", "patrol"]', '["ferry", "osv", "patrol"]',
    'available', '["APAC", "EMEA", "Americas"]',
    'manufacturer_datasheet', 'https://www.yanmar.com/',
    'Yanmar 8AYM-WET specification sheet', 0.9,
    NOW(), 'engine_master_data', 'Yanmar 8AYM-WET high-speed marine diesel engine. 8-cylinder V-configuration producing 637-716 kW (855-960 hp) at 1900 RPM. 27.2 liter displacement. Wet exhaust design for commercial applications. Features electronic fuel injection, advanced turbocharging. IMO Tier II certified. Applications include ferries, OSVs, patrol vessels. Known as Yanmar 8AYM, 8AY marine, or Yanmar V8 commercial.'
)
ON CONFLICT (engine_model_id, rating_designation) DO UPDATE SET
    power_kw = EXCLUDED.power_kw,
    power_hp = EXCLUDED.power_hp,
    duty_class = EXCLUDED.duty_class,
    harmonized_duty_class = EXCLUDED.harmonized_duty_class,
    oem_rating_code = EXCLUDED.oem_rating_code,
    dry_weight_kg = EXCLUDED.dry_weight_kg,
    length_mm = EXCLUDED.length_mm,
    width_mm = EXCLUDED.width_mm,
    height_mm = EXCLUDED.height_mm,
    power_density_kw_per_kg = EXCLUDED.power_density_kw_per_kg,
    last_verified = NOW(),
    verified_by = EXCLUDED.verified_by;

INSERT INTO kb_engine_ratings (
    id, engine_model_id, rating_designation, rating_name, duty_class, iso_classification,
    harmonized_duty_class, oem_rating_code,
    power_kw, power_hp, rpm, load_factor_min, load_factor_max, annual_hours_min, annual_hours_max,
    dry_weight_kg, length_mm, width_mm, height_mm, power_density_kw_per_kg,
    fuel_types, emission_tier, application_profiles, primary_applications,
    availability_status, regions_available, data_source, data_source_url, data_source_document,
    data_confidence, last_verified, verified_by, notes
) VALUES (
    'be3fb697-4e0e-4db7-bdc1-7065c9a97013', 'f17c58e0-edd1-4ab5-b635-11bef5bf7ffe', '12AYM-WGT',
    'Yanmar 12AYM-WGT', 'heavy_duty', 'not_applicable',
    'HVY', '12AYM-WGT',
    1074, 1440.234, 1900,
    0.4, 0.8,
    3000, 5000,
    NULL, NULL,
    NULL, NULL, NULL,
    '["mgo", "diesel", "mdo"]', 'IMO Tier II',
    '["ferry", "osv", "naval"]', '["ferry", "osv", "naval"]',
    'available', '["APAC", "EMEA", "Americas"]',
    'manufacturer_datasheet', 'https://www.yanmar.com/',
    'Yanmar 12AYM-WGT specification sheet', 0.9,
    NOW(), 'engine_master_data', 'Yanmar 12AYM-WGT high-speed marine diesel engine. 12-cylinder V-configuration producing 955-1074 kW (1280-1440 hp) at 1900 RPM. 40.8 liter displacement. Flagship Yanmar marine engine with wet exhaust and GT turbo. Features electronic fuel injection, advanced controls. IMO Tier II certified. Applications include ferries, OSVs, naval vessels. Known as Yanmar 12AYM, 12AY marine, or Yanmar V12 flagship.'
)
ON CONFLICT (engine_model_id, rating_designation) DO UPDATE SET
    power_kw = EXCLUDED.power_kw,
    power_hp = EXCLUDED.power_hp,
    duty_class = EXCLUDED.duty_class,
    harmonized_duty_class = EXCLUDED.harmonized_duty_class,
    oem_rating_code = EXCLUDED.oem_rating_code,
    dry_weight_kg = EXCLUDED.dry_weight_kg,
    length_mm = EXCLUDED.length_mm,
    width_mm = EXCLUDED.width_mm,
    height_mm = EXCLUDED.height_mm,
    power_density_kw_per_kg = EXCLUDED.power_density_kw_per_kg,
    last_verified = NOW(),
    verified_by = EXCLUDED.verified_by;

INSERT INTO kb_engine_ratings (
    id, engine_model_id, rating_designation, rating_name, duty_class, iso_classification,
    harmonized_duty_class, oem_rating_code,
    power_kw, power_hp, rpm, load_factor_min, load_factor_max, annual_hours_min, annual_hours_max,
    dry_weight_kg, length_mm, width_mm, height_mm, power_density_kw_per_kg,
    fuel_types, emission_tier, application_profiles, primary_applications,
    availability_status, regions_available, data_source, data_source_url, data_source_document,
    data_confidence, last_verified, verified_by, notes
) VALUES (
    'c6215619-4be5-464b-b999-4cb3dc5072b7', 'f95d596e-725d-47f1-9a56-08d41a40dca9', 'WP13',
    'WEICHAI WP13', 'medium_duty', 'not_applicable',
    'MED', 'WP13',
    537, 720.117, 1800,
    0.2, 0.8,
    2000, 4000,
    NULL, NULL,
    NULL, NULL, NULL,
    '["mgo", "diesel", "mdo"]', 'IMO Tier II',
    '["tug", "workboat", "fishing"]', '["tug", "workboat", "fishing"]',
    'available', '["APAC", "EMEA", "Americas"]',
    'manufacturer_datasheet', 'https://en.weichai.com/',
    'WEICHAI WP13 specification sheet', 0.85,
    NOW(), 'engine_master_data', 'WEICHAI WP13 high-speed marine diesel engine from Weichai Power, China''s largest diesel engine manufacturer. 6-cylinder inline configuration producing 368-537 kW (500-730 hp) at 1800-2100 RPM. 12.9 liter displacement. Highly competitive pricing - typically 40-50% below Western brands. Popular in Asian tug, workboat, and fishing vessel markets. Features electronic fuel injection, turbocharging. IMO Tier II certified. Also known as Weichai WP13, Weichai 13-liter, or WP13C marine. Baudouin technolo'
)
ON CONFLICT (engine_model_id, rating_designation) DO UPDATE SET
    power_kw = EXCLUDED.power_kw,
    power_hp = EXCLUDED.power_hp,
    duty_class = EXCLUDED.duty_class,
    harmonized_duty_class = EXCLUDED.harmonized_duty_class,
    oem_rating_code = EXCLUDED.oem_rating_code,
    dry_weight_kg = EXCLUDED.dry_weight_kg,
    length_mm = EXCLUDED.length_mm,
    width_mm = EXCLUDED.width_mm,
    height_mm = EXCLUDED.height_mm,
    power_density_kw_per_kg = EXCLUDED.power_density_kw_per_kg,
    last_verified = NOW(),
    verified_by = EXCLUDED.verified_by;

INSERT INTO kb_engine_ratings (
    id, engine_model_id, rating_designation, rating_name, duty_class, iso_classification,
    harmonized_duty_class, oem_rating_code,
    power_kw, power_hp, rpm, load_factor_min, load_factor_max, annual_hours_min, annual_hours_max,
    dry_weight_kg, length_mm, width_mm, height_mm, power_density_kw_per_kg,
    fuel_types, emission_tier, application_profiles, primary_applications,
    availability_status, regions_available, data_source, data_source_url, data_source_document,
    data_confidence, last_verified, verified_by, notes
) VALUES (
    '3bcccc8d-2c0d-4444-947b-308081fdd66c', '7cd55999-1e5d-4531-a00b-b32018cd9ad4', 'WHM6160',
    'WEICHAI WHM6160', 'heavy_duty', 'not_applicable',
    'HVY', 'WHM6160',
    1200, 1609.2, 1500,
    0.4, 0.8,
    3000, 5000,
    NULL, NULL,
    NULL, NULL, NULL,
    '["diesel", "mdo"]', 'IMO Tier II',
    '["tug", "osv", "cargo"]', '["tug", "osv", "cargo"]',
    'available', '["APAC", "EMEA", "Americas"]',
    'manufacturer_datasheet', 'https://en.weichai.com/',
    'WEICHAI WHM6160 specification sheet', 0.85,
    NOW(), 'engine_master_data', 'WEICHAI WHM6160 high-speed marine diesel engine series. Available in 6L, 8V, and 12V configurations producing 550-1200 kW (750-1600 hp) at 1500-1800 RPM. Designed for commercial marine applications including tugs, OSVs, and cargo vessels. Aggressive pricing strategy makes it strong competitor in Asian markets. Features common rail injection, electronic controls. IMO Tier II compliant. Known as Weichai WHM6160, 6160 series, or Weichai medium-power marine. Growing presence in Southeast Asia, Middl'
)
ON CONFLICT (engine_model_id, rating_designation) DO UPDATE SET
    power_kw = EXCLUDED.power_kw,
    power_hp = EXCLUDED.power_hp,
    duty_class = EXCLUDED.duty_class,
    harmonized_duty_class = EXCLUDED.harmonized_duty_class,
    oem_rating_code = EXCLUDED.oem_rating_code,
    dry_weight_kg = EXCLUDED.dry_weight_kg,
    length_mm = EXCLUDED.length_mm,
    width_mm = EXCLUDED.width_mm,
    height_mm = EXCLUDED.height_mm,
    power_density_kw_per_kg = EXCLUDED.power_density_kw_per_kg,
    last_verified = NOW(),
    verified_by = EXCLUDED.verified_by;

INSERT INTO kb_engine_ratings (
    id, engine_model_id, rating_designation, rating_name, duty_class, iso_classification,
    harmonized_duty_class, oem_rating_code,
    power_kw, power_hp, rpm, load_factor_min, load_factor_max, annual_hours_min, annual_hours_max,
    dry_weight_kg, length_mm, width_mm, height_mm, power_density_kw_per_kg,
    fuel_types, emission_tier, application_profiles, primary_applications,
    availability_status, regions_available, data_source, data_source_url, data_source_document,
    data_confidence, last_verified, verified_by, notes
) VALUES (
    '4d082cf9-ad82-49b8-9b9f-a40b52acc269', '00bcfaa0-3fcb-4fca-a6a4-5505ef58f5cb', '12M33C',
    'WEICHAI 12M33', 'heavy_duty', 'not_applicable',
    'HVY', '12M33C',
    2200, 2950.2, 1500,
    0.4, 0.8,
    3000, 5000,
    NULL, NULL,
    NULL, NULL, NULL,
    '["diesel", "mdo"]', 'IMO Tier II',
    '["tug", "osv", "large_vessel"]', '["tug", "osv", "large_vessel"]',
    'available', '["APAC", "EMEA", "Americas"]',
    'manufacturer_datasheet', 'https://en.weichai.com/',
    'WEICHAI 12M33 specification sheet', 0.8,
    NOW(), 'engine_master_data', 'WEICHAI 12M33 high-speed marine diesel engine, high-power offering from China''s leading engine manufacturer. 12 and 16-cylinder V-configurations producing 1100-2200 kW (1475-2950 hp) at 1500-1800 RPM. Competes directly with MTU Series 4000 and Cummins QSK series at significantly lower price point. Features modern common rail injection, electronic management. IMO Tier II certified. Growing adoption in Chinese-built vessels, Asian fleet operators. Also known as Weichai M33 series, 12M33C, 16M33C m'
)
ON CONFLICT (engine_model_id, rating_designation) DO UPDATE SET
    power_kw = EXCLUDED.power_kw,
    power_hp = EXCLUDED.power_hp,
    duty_class = EXCLUDED.duty_class,
    harmonized_duty_class = EXCLUDED.harmonized_duty_class,
    oem_rating_code = EXCLUDED.oem_rating_code,
    dry_weight_kg = EXCLUDED.dry_weight_kg,
    length_mm = EXCLUDED.length_mm,
    width_mm = EXCLUDED.width_mm,
    height_mm = EXCLUDED.height_mm,
    power_density_kw_per_kg = EXCLUDED.power_density_kw_per_kg,
    last_verified = NOW(),
    verified_by = EXCLUDED.verified_by;

INSERT INTO kb_engine_ratings (
    id, engine_model_id, rating_designation, rating_name, duty_class, iso_classification,
    harmonized_duty_class, oem_rating_code,
    power_kw, power_hp, rpm, load_factor_min, load_factor_max, annual_hours_min, annual_hours_max,
    dry_weight_kg, length_mm, width_mm, height_mm, power_density_kw_per_kg,
    fuel_types, emission_tier, application_profiles, primary_applications,
    availability_status, regions_available, data_source, data_source_url, data_source_document,
    data_confidence, last_verified, verified_by, notes
) VALUES (
    'a43e4fd5-a574-47b0-b9dc-05077713ec9c', '4e8dad85-5981-4b38-9e90-d3fb9eae62de', 'C13-500',
    'FPT Cursor 13', 'medium_duty', 'not_applicable',
    'MED', 'C13-500',
    509, 682.569, 1800,
    0.2, 0.8,
    2000, 4000,
    NULL, NULL,
    NULL, NULL, NULL,
    '["mgo", "diesel", "mdo"]', 'IMO Tier II',
    '["fishing", "workboat", "ferry"]', '["fishing", "workboat", "ferry"]',
    'available', '["APAC", "EMEA", "Americas"]',
    'manufacturer_datasheet', 'https://www.fptindustrial.com/',
    'FPT Cursor 13 specification sheet', 0.9,
    NOW(), 'engine_master_data', 'FPT Cursor 13 high-speed marine diesel engine from FPT Industrial (Iveco/CNH group). 6-cylinder inline configuration producing 368-509 kW (500-690 hp) at 1800-2100 RPM. 12.9 liter displacement. Popular in European fishing and workboat markets. Features common rail injection, HI-eSCR technology for Tier III compliance. Competitive pricing versus Caterpillar and Cummins. Known as FPT Cursor 13, Iveco Cursor 13, NEF 13, C13 marine. Strong presence in Mediterranean and Northern European markets.'
)
ON CONFLICT (engine_model_id, rating_designation) DO UPDATE SET
    power_kw = EXCLUDED.power_kw,
    power_hp = EXCLUDED.power_hp,
    duty_class = EXCLUDED.duty_class,
    harmonized_duty_class = EXCLUDED.harmonized_duty_class,
    oem_rating_code = EXCLUDED.oem_rating_code,
    dry_weight_kg = EXCLUDED.dry_weight_kg,
    length_mm = EXCLUDED.length_mm,
    width_mm = EXCLUDED.width_mm,
    height_mm = EXCLUDED.height_mm,
    power_density_kw_per_kg = EXCLUDED.power_density_kw_per_kg,
    last_verified = NOW(),
    verified_by = EXCLUDED.verified_by;

INSERT INTO kb_engine_ratings (
    id, engine_model_id, rating_designation, rating_name, duty_class, iso_classification,
    harmonized_duty_class, oem_rating_code,
    power_kw, power_hp, rpm, load_factor_min, load_factor_max, annual_hours_min, annual_hours_max,
    dry_weight_kg, length_mm, width_mm, height_mm, power_density_kw_per_kg,
    fuel_types, emission_tier, application_profiles, primary_applications,
    availability_status, regions_available, data_source, data_source_url, data_source_document,
    data_confidence, last_verified, verified_by, notes
) VALUES (
    '334ca729-2519-4aba-bb43-d6f51168b574', 'e77bd64e-a2dc-4056-84ce-8023153fd40e', 'C16-600',
    'FPT Cursor 16', 'medium_duty', 'not_applicable',
    'MED', 'C16-600',
    662, 887.742, 1800,
    0.2, 0.8,
    2000, 4000,
    NULL, NULL,
    NULL, NULL, NULL,
    '["mgo", "diesel", "mdo"]', 'IMO Tier II',
    '["fishing", "tug", "ferry", "workboat"]', '["fishing", "tug", "ferry"]',
    'available', '["APAC", "EMEA", "Americas"]',
    'manufacturer_datasheet', 'https://www.fptindustrial.com/',
    'FPT Cursor 16 specification sheet', 0.9,
    NOW(), 'engine_master_data', 'FPT Cursor 16 high-speed marine diesel engine from FPT Industrial (Iveco/CNH group). 6-cylinder inline configuration producing 485-662 kW (660-900 hp) at 1800-2100 RPM. 15.9 liter displacement. Largest Cursor series marine engine. Applications include fishing vessels, tugs, ferries, workboats. Features advanced common rail injection, available with HI-eSCR for IMO Tier III. Known as FPT Cursor 16, Iveco Cursor 16, C16 marine. Competitive alternative to MAN Engines and Volvo Penta in European mar'
)
ON CONFLICT (engine_model_id, rating_designation) DO UPDATE SET
    power_kw = EXCLUDED.power_kw,
    power_hp = EXCLUDED.power_hp,
    duty_class = EXCLUDED.duty_class,
    harmonized_duty_class = EXCLUDED.harmonized_duty_class,
    oem_rating_code = EXCLUDED.oem_rating_code,
    dry_weight_kg = EXCLUDED.dry_weight_kg,
    length_mm = EXCLUDED.length_mm,
    width_mm = EXCLUDED.width_mm,
    height_mm = EXCLUDED.height_mm,
    power_density_kw_per_kg = EXCLUDED.power_density_kw_per_kg,
    last_verified = NOW(),
    verified_by = EXCLUDED.verified_by;

INSERT INTO kb_engine_ratings (
    id, engine_model_id, rating_designation, rating_name, duty_class, iso_classification,
    harmonized_duty_class, oem_rating_code,
    power_kw, power_hp, rpm, load_factor_min, load_factor_max, annual_hours_min, annual_hours_max,
    dry_weight_kg, length_mm, width_mm, height_mm, power_density_kw_per_kg,
    fuel_types, emission_tier, application_profiles, primary_applications,
    availability_status, regions_available, data_source, data_source_url, data_source_document,
    data_confidence, last_verified, verified_by, notes
) VALUES (
    '89161792-311c-406a-8ad8-0a822cc54cc7', 'c6ec290d-5893-44bd-9c1a-2dd6bfe90397', 'DI13',
    'Scania DI13', 'medium_duty', 'not_applicable',
    'MED', 'DI13',
    588, 788.508, 1800,
    0.2, 0.8,
    2000, 4000,
    NULL, NULL,
    NULL, NULL, NULL,
    '["mgo", "diesel", "mdo"]', 'IMO Tier II',
    '["ferry", "workboat", "fishing"]', '["ferry", "workboat", "fishing"]',
    'available', '["APAC", "EMEA", "Americas"]',
    'manufacturer_datasheet', 'https://www.scania.com/',
    'Scania DI13 specification sheet', 0.9,
    NOW(), 'engine_master_data', 'Scania DI13 high-speed marine diesel engine from Scania (Traton Group). 6-cylinder inline configuration producing 405-588 kW (550-800 hp) at 1800-2100 RPM. 12.7 liter displacement. Swedish engineering with excellent reliability reputation. Direct competitor to Volvo Penta D13. Features XPI common rail fuel injection, EMS electronic management. IMO Tier II standard, Tier III with SCR available. Popular in Scandinavian markets for ferries, workboats, fishing vessels. Known as Scania DI13, DI13M, o'
)
ON CONFLICT (engine_model_id, rating_designation) DO UPDATE SET
    power_kw = EXCLUDED.power_kw,
    power_hp = EXCLUDED.power_hp,
    duty_class = EXCLUDED.duty_class,
    harmonized_duty_class = EXCLUDED.harmonized_duty_class,
    oem_rating_code = EXCLUDED.oem_rating_code,
    dry_weight_kg = EXCLUDED.dry_weight_kg,
    length_mm = EXCLUDED.length_mm,
    width_mm = EXCLUDED.width_mm,
    height_mm = EXCLUDED.height_mm,
    power_density_kw_per_kg = EXCLUDED.power_density_kw_per_kg,
    last_verified = NOW(),
    verified_by = EXCLUDED.verified_by;

INSERT INTO kb_engine_ratings (
    id, engine_model_id, rating_designation, rating_name, duty_class, iso_classification,
    harmonized_duty_class, oem_rating_code,
    power_kw, power_hp, rpm, load_factor_min, load_factor_max, annual_hours_min, annual_hours_max,
    dry_weight_kg, length_mm, width_mm, height_mm, power_density_kw_per_kg,
    fuel_types, emission_tier, application_profiles, primary_applications,
    availability_status, regions_available, data_source, data_source_url, data_source_document,
    data_confidence, last_verified, verified_by, notes
) VALUES (
    '16ab0e23-ad66-4752-9ec6-8bde2cdc2b1c', '33701d9d-614d-4335-bab9-d9d35a3974e8', 'DI16',
    'Scania DI16', 'medium_duty', 'not_applicable',
    'MED', 'DI16',
    809, 1084.869, 1800,
    0.2, 0.8,
    2000, 4000,
    NULL, NULL,
    NULL, NULL, NULL,
    '["mgo", "diesel", "mdo"]', 'IMO Tier II',
    '["ferry", "pilot", "patrol"]', '["ferry", "pilot", "patrol"]',
    'available', '["APAC", "EMEA", "Americas"]',
    'manufacturer_datasheet', 'https://www.scania.com/',
    'Scania DI16 specification sheet', 0.9,
    NOW(), 'engine_master_data', 'Scania DI16 high-speed marine diesel engine from Scania (Traton Group). 8-cylinder V-configuration producing 588-809 kW (800-1100 hp) at 1800-2100 RPM. 16.4 liter displacement. Largest Scania marine engine, competing with Cat C18 and Volvo D13 IPS. Swedish quality engineering, excellent fuel efficiency. Features XPI common rail injection, advanced EMS controls. IMO Tier II certified, Tier III with SCR. Growing market share in Northern Europe for ferries, pilot boats, patrol vessels. Known as Sca'
)
ON CONFLICT (engine_model_id, rating_designation) DO UPDATE SET
    power_kw = EXCLUDED.power_kw,
    power_hp = EXCLUDED.power_hp,
    duty_class = EXCLUDED.duty_class,
    harmonized_duty_class = EXCLUDED.harmonized_duty_class,
    oem_rating_code = EXCLUDED.oem_rating_code,
    dry_weight_kg = EXCLUDED.dry_weight_kg,
    length_mm = EXCLUDED.length_mm,
    width_mm = EXCLUDED.width_mm,
    height_mm = EXCLUDED.height_mm,
    power_density_kw_per_kg = EXCLUDED.power_density_kw_per_kg,
    last_verified = NOW(),
    verified_by = EXCLUDED.verified_by;

INSERT INTO kb_engine_ratings (
    id, engine_model_id, rating_designation, rating_name, duty_class, iso_classification,
    harmonized_duty_class, oem_rating_code,
    power_kw, power_hp, rpm, load_factor_min, load_factor_max, annual_hours_min, annual_hours_max,
    dry_weight_kg, length_mm, width_mm, height_mm, power_density_kw_per_kg,
    fuel_types, emission_tier, application_profiles, primary_applications,
    availability_status, regions_available, data_source, data_source_url, data_source_document,
    data_confidence, last_verified, verified_by, notes
) VALUES (
    '8e4734b2-f545-4f1e-893a-f9553f1f7073', '182c7e21-e3de-4760-8a2b-3518e16af990', '6L14',
    'Wartsila 6L14', 'medium_duty', 'not_applicable',
    'MED', '6L14',
    882, 1182.762, 1500,
    0.2, 0.8,
    2000, 4000,
    NULL, NULL,
    NULL, NULL, NULL,
    '["mgo", "diesel", "mdo"]', 'IMO Tier II',
    '["workboat", "ferry", "tug"]', '["workboat", "ferry", "tug"]',
    'available', '["APAC", "EMEA", "Americas"]',
    'manufacturer_datasheet', 'https://www.wartsila.com/',
    'Wartsila 6L14 specification sheet', 0.85,
    NOW(), 'engine_master_data', 'Wartsila 6L14 high-speed marine diesel engine from Wartsila Corporation. 6-cylinder inline configuration producing 735-882 kW (1000-1200 hp) at 1500 RPM. 14cm bore, compact high-speed design for workboats, ferries, and tugs. Features common rail fuel injection, electronic controls. IMO Tier II certified. Compact footprint ideal for space-constrained engine rooms. Known as Wartsila 6L14, W14, or Wartsila 14-series inline.'
)
ON CONFLICT (engine_model_id, rating_designation) DO UPDATE SET
    power_kw = EXCLUDED.power_kw,
    power_hp = EXCLUDED.power_hp,
    duty_class = EXCLUDED.duty_class,
    harmonized_duty_class = EXCLUDED.harmonized_duty_class,
    oem_rating_code = EXCLUDED.oem_rating_code,
    dry_weight_kg = EXCLUDED.dry_weight_kg,
    length_mm = EXCLUDED.length_mm,
    width_mm = EXCLUDED.width_mm,
    height_mm = EXCLUDED.height_mm,
    power_density_kw_per_kg = EXCLUDED.power_density_kw_per_kg,
    last_verified = NOW(),
    verified_by = EXCLUDED.verified_by;

INSERT INTO kb_engine_ratings (
    id, engine_model_id, rating_designation, rating_name, duty_class, iso_classification,
    harmonized_duty_class, oem_rating_code,
    power_kw, power_hp, rpm, load_factor_min, load_factor_max, annual_hours_min, annual_hours_max,
    dry_weight_kg, length_mm, width_mm, height_mm, power_density_kw_per_kg,
    fuel_types, emission_tier, application_profiles, primary_applications,
    availability_status, regions_available, data_source, data_source_url, data_source_document,
    data_confidence, last_verified, verified_by, notes
) VALUES (
    'abfac726-a29f-45ff-9c0b-73314df19443', '732940ee-4556-4a92-80ce-7dd0dc33465a', '8L14',
    'Wartsila 8L14', 'medium_duty', 'not_applicable',
    'MED', '8L14',
    1176, 1577.016, 1500,
    0.2, 0.8,
    2000, 4000,
    NULL, NULL,
    NULL, NULL, NULL,
    '["mgo", "diesel", "mdo"]', 'IMO Tier II',
    '["workboat", "ferry", "osv"]', '["workboat", "ferry", "osv"]',
    'available', '["APAC", "EMEA", "Americas"]',
    'manufacturer_datasheet', 'https://www.wartsila.com/',
    'Wartsila 8L14 specification sheet', 0.85,
    NOW(), 'engine_master_data', 'Wartsila 8L14 high-speed marine diesel engine from Wartsila Corporation. 8-cylinder inline configuration producing 980-1176 kW (1315-1580 hp) at 1500 RPM. 14cm bore, extended inline design for workboats, ferries, and offshore support vessels. Features common rail fuel injection, electronic management. IMO Tier II certified. Known as Wartsila 8L14, W14, or Wartsila 14-series 8-cylinder.'
)
ON CONFLICT (engine_model_id, rating_designation) DO UPDATE SET
    power_kw = EXCLUDED.power_kw,
    power_hp = EXCLUDED.power_hp,
    duty_class = EXCLUDED.duty_class,
    harmonized_duty_class = EXCLUDED.harmonized_duty_class,
    oem_rating_code = EXCLUDED.oem_rating_code,
    dry_weight_kg = EXCLUDED.dry_weight_kg,
    length_mm = EXCLUDED.length_mm,
    width_mm = EXCLUDED.width_mm,
    height_mm = EXCLUDED.height_mm,
    power_density_kw_per_kg = EXCLUDED.power_density_kw_per_kg,
    last_verified = NOW(),
    verified_by = EXCLUDED.verified_by;

INSERT INTO kb_engine_ratings (
    id, engine_model_id, rating_designation, rating_name, duty_class, iso_classification,
    harmonized_duty_class, oem_rating_code,
    power_kw, power_hp, rpm, load_factor_min, load_factor_max, annual_hours_min, annual_hours_max,
    dry_weight_kg, length_mm, width_mm, height_mm, power_density_kw_per_kg,
    fuel_types, emission_tier, application_profiles, primary_applications,
    availability_status, regions_available, data_source, data_source_url, data_source_document,
    data_confidence, last_verified, verified_by, notes
) VALUES (
    'e240dd67-7215-4819-9e45-6851fd1b95bd', '3e396371-8daf-45ac-a2e4-ac8602d120a4', '12V14',
    'Wartsila 12V14', 'heavy_duty', 'not_applicable',
    'HVY', '12V14',
    1764, 2365.524, 1200,
    0.4, 0.8,
    3000, 5000,
    NULL, NULL,
    NULL, NULL, NULL,
    '["mgo", "diesel", "mdo"]', 'IMO Tier II',
    '["ferry", "osv", "tug"]', '["ferry", "osv", "tug"]',
    'available', '["APAC", "EMEA", "Americas"]',
    'manufacturer_datasheet', 'https://www.wartsila.com/',
    'Wartsila 12V14 specification sheet', 0.85,
    NOW(), 'engine_master_data', 'Wartsila 12V14 high-speed marine diesel engine from Wartsila Corporation. 12-cylinder V-configuration producing 1470-1764 kW (1970-2370 hp) at 1200 RPM. 14cm bore, V-configuration for heavy-duty commercial applications. Features common rail fuel injection, advanced electronic controls. IMO Tier II certified. Applications include ferries, offshore supply vessels, and tugs. Known as Wartsila 12V14, W14V, or Wartsila 14-series V12.'
)
ON CONFLICT (engine_model_id, rating_designation) DO UPDATE SET
    power_kw = EXCLUDED.power_kw,
    power_hp = EXCLUDED.power_hp,
    duty_class = EXCLUDED.duty_class,
    harmonized_duty_class = EXCLUDED.harmonized_duty_class,
    oem_rating_code = EXCLUDED.oem_rating_code,
    dry_weight_kg = EXCLUDED.dry_weight_kg,
    length_mm = EXCLUDED.length_mm,
    width_mm = EXCLUDED.width_mm,
    height_mm = EXCLUDED.height_mm,
    power_density_kw_per_kg = EXCLUDED.power_density_kw_per_kg,
    last_verified = NOW(),
    verified_by = EXCLUDED.verified_by;

INSERT INTO kb_engine_ratings (
    id, engine_model_id, rating_designation, rating_name, duty_class, iso_classification,
    harmonized_duty_class, oem_rating_code,
    power_kw, power_hp, rpm, load_factor_min, load_factor_max, annual_hours_min, annual_hours_max,
    dry_weight_kg, length_mm, width_mm, height_mm, power_density_kw_per_kg,
    fuel_types, emission_tier, application_profiles, primary_applications,
    availability_status, regions_available, data_source, data_source_url, data_source_document,
    data_confidence, last_verified, verified_by, notes
) VALUES (
    '43e171c7-0635-41e2-ac7d-0675177e2159', 'a699f72f-d3a2-4886-91f9-875921b2f960', '6L20',
    'Wartsila 6L20', 'medium_duty', 'not_applicable',
    'MED', '6L20',
    1200, 1609.2, 1200,
    0.2, 0.8,
    2000, 4000,
    18000, 3845,
    1450, 2375, 0.0667,
    '["mgo", "diesel", "mdo"]', 'IMO Tier II',
    '["ferry", "osv", "tug"]', '["ferry", "osv", "tug"]',
    'available', '["APAC", "EMEA", "Americas"]',
    'manufacturer_datasheet', 'https://www.wartsila.com/',
    'Wartsila 6L20 specification sheet', 0.85,
    NOW(), 'engine_master_data', 'Wartsila 6L20 high-speed marine diesel engine from Wartsila Corporation. 6-cylinder inline configuration producing 1000-1200 kW (1340-1610 hp) at 1200 RPM. 20cm bore, borderline high-speed for commercial marine applications. Features common rail injection, electronic engine management. IMO Tier II certified. Applications include ferries, offshore support vessels, and tugs. Known as Wartsila 6L20, W20, or Wartsila 20-series inline.'
)
ON CONFLICT (engine_model_id, rating_designation) DO UPDATE SET
    power_kw = EXCLUDED.power_kw,
    power_hp = EXCLUDED.power_hp,
    duty_class = EXCLUDED.duty_class,
    harmonized_duty_class = EXCLUDED.harmonized_duty_class,
    oem_rating_code = EXCLUDED.oem_rating_code,
    dry_weight_kg = EXCLUDED.dry_weight_kg,
    length_mm = EXCLUDED.length_mm,
    width_mm = EXCLUDED.width_mm,
    height_mm = EXCLUDED.height_mm,
    power_density_kw_per_kg = EXCLUDED.power_density_kw_per_kg,
    last_verified = NOW(),
    verified_by = EXCLUDED.verified_by;

INSERT INTO kb_engine_ratings (
    id, engine_model_id, rating_designation, rating_name, duty_class, iso_classification,
    harmonized_duty_class, oem_rating_code,
    power_kw, power_hp, rpm, load_factor_min, load_factor_max, annual_hours_min, annual_hours_max,
    dry_weight_kg, length_mm, width_mm, height_mm, power_density_kw_per_kg,
    fuel_types, emission_tier, application_profiles, primary_applications,
    availability_status, regions_available, data_source, data_source_url, data_source_document,
    data_confidence, last_verified, verified_by, notes
) VALUES (
    '8dff4160-d8c9-44c8-9bd7-a7cae2fe9ca6', 'ba74b030-e94f-42c7-ac2c-c835b18171fb', '8L20',
    'Wartsila 8L20', 'heavy_duty', 'not_applicable',
    'HVY', '8L20',
    1600, 2145.6, 1200,
    0.4, 0.8,
    3000, 5000,
    NULL, NULL,
    NULL, NULL, NULL,
    '["mgo", "diesel", "mdo"]', 'IMO Tier II',
    '["ferry", "osv", "tug", "workboat"]', '["ferry", "osv", "tug"]',
    'available', '["APAC", "EMEA", "Americas"]',
    'manufacturer_datasheet', 'https://www.wartsila.com/',
    'Wartsila 8L20 specification sheet', 0.85,
    NOW(), 'engine_master_data', 'Wartsila 8L20 high-speed marine diesel engine from Wartsila Corporation. 8-cylinder inline configuration producing 1333-1600 kW (1790-2145 hp) at 1200 RPM. 20cm bore, heavy-duty commercial marine applications. Features common rail fuel injection, advanced electronic controls. IMO Tier II certified. Applications include ferries, offshore supply vessels, tugs, and workboats. Known as Wartsila 8L20, W20, or Wartsila 20-series 8-cylinder.'
)
ON CONFLICT (engine_model_id, rating_designation) DO UPDATE SET
    power_kw = EXCLUDED.power_kw,
    power_hp = EXCLUDED.power_hp,
    duty_class = EXCLUDED.duty_class,
    harmonized_duty_class = EXCLUDED.harmonized_duty_class,
    oem_rating_code = EXCLUDED.oem_rating_code,
    dry_weight_kg = EXCLUDED.dry_weight_kg,
    length_mm = EXCLUDED.length_mm,
    width_mm = EXCLUDED.width_mm,
    height_mm = EXCLUDED.height_mm,
    power_density_kw_per_kg = EXCLUDED.power_density_kw_per_kg,
    last_verified = NOW(),
    verified_by = EXCLUDED.verified_by;

INSERT INTO kb_engine_ratings (
    id, engine_model_id, rating_designation, rating_name, duty_class, iso_classification,
    harmonized_duty_class, oem_rating_code,
    power_kw, power_hp, rpm, load_factor_min, load_factor_max, annual_hours_min, annual_hours_max,
    dry_weight_kg, length_mm, width_mm, height_mm, power_density_kw_per_kg,
    fuel_types, emission_tier, application_profiles, primary_applications,
    availability_status, regions_available, data_source, data_source_url, data_source_document,
    data_confidence, last_verified, verified_by, notes
) VALUES (
    'eae71e02-7e49-4716-8a5e-ef24737d3c75', 'dd5ed6e3-5235-4faf-ac37-2d49ea244248', '9L20',
    'Wartsila 9L20', 'heavy_duty', 'not_applicable',
    'HVY', '9L20',
    1800, 2413.7999999999997, 1200,
    0.4, 0.8,
    3000, 5000,
    NULL, NULL,
    NULL, NULL, NULL,
    '["mgo", "diesel", "mdo"]', 'IMO Tier II',
    '["ferry", "osv", "naval"]', '["ferry", "osv", "naval"]',
    'available', '["APAC", "EMEA", "Americas"]',
    'manufacturer_datasheet', 'https://www.wartsila.com/',
    'Wartsila 9L20 specification sheet', 0.85,
    NOW(), 'engine_master_data', 'Wartsila 9L20 high-speed marine diesel engine from Wartsila Corporation. 9-cylinder inline configuration producing 1500-1800 kW (2010-2415 hp) at 1200 RPM. 20cm bore, largest inline variant of the 20-series. Features common rail fuel injection, sophisticated electronic controls. IMO Tier II certified. Applications include ferries, offshore support vessels, and naval applications. Known as Wartsila 9L20, W20, or Wartsila 20-series 9-cylinder.'
)
ON CONFLICT (engine_model_id, rating_designation) DO UPDATE SET
    power_kw = EXCLUDED.power_kw,
    power_hp = EXCLUDED.power_hp,
    duty_class = EXCLUDED.duty_class,
    harmonized_duty_class = EXCLUDED.harmonized_duty_class,
    oem_rating_code = EXCLUDED.oem_rating_code,
    dry_weight_kg = EXCLUDED.dry_weight_kg,
    length_mm = EXCLUDED.length_mm,
    width_mm = EXCLUDED.width_mm,
    height_mm = EXCLUDED.height_mm,
    power_density_kw_per_kg = EXCLUDED.power_density_kw_per_kg,
    last_verified = NOW(),
    verified_by = EXCLUDED.verified_by;