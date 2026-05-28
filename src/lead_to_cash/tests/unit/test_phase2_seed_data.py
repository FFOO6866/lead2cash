"""
Unit Tests for Phase 2 Knowledge Base Seed Data

Tests the seed data modules for rating-level data:
- seed_engine_ratings.py
- seed_customer_requirements.py
- seed_competitor_maps.py
- seed_competitor_engagements.py
"""

from lead_to_cash.services.knowledge_base.engine_master_data import (
    ENGINE_MASTER_DATA,
    DutyClass,
)
from lead_to_cash.services.knowledge_base.seed_competitor_engagements import (
    COMPETITOR_ENGAGEMENTS,
)
from lead_to_cash.services.knowledge_base.seed_competitor_maps import (
    COMPETITIVE_MAPPINGS,
)
from lead_to_cash.services.knowledge_base.seed_customer_requirements import (
    CUSTOMER_REQUIREMENTS,
)
from lead_to_cash.services.knowledge_base.seed_engine_ratings import (
    DUTY_CLASS_OPERATING_PROFILE,
    ENGINE_POWER_DATA,
    _build_rating_record,
    _get_manufacturer_from_model_name,
    _get_series_from_model_name,
)


class TestEngineMasterData:
    """Test ENGINE_MASTER_DATA reference data."""

    def test_engine_master_data_not_empty(self):
        """Verify ENGINE_MASTER_DATA has entries."""
        assert len(ENGINE_MASTER_DATA) > 0
        assert len(ENGINE_MASTER_DATA) >= 50  # At least 50 engines

    def test_all_engines_have_duty_class(self):
        """Verify all engines have a valid duty class."""
        for model_name, spec in ENGINE_MASTER_DATA.items():
            assert spec.duty_class is not None, f"{model_name} missing duty_class"
            assert isinstance(
                spec.duty_class, DutyClass
            ), f"{model_name} invalid duty_class"

    def test_all_engines_have_rating_designation(self):
        """Verify all engines have a rating designation."""
        for model_name, spec in ENGINE_MASTER_DATA.items():
            assert spec.rating_designation, f"{model_name} missing rating_designation"

    def test_mtu_engines_have_correct_rating_codes(self):
        """Verify MTU engines use correct M-code ratings."""
        mtu_engines = {
            k: v for k, v in ENGINE_MASTER_DATA.items() if k.startswith("MTU")
        }
        assert len(mtu_engines) >= 10, "Should have at least 10 MTU engines"

        for model_name, spec in mtu_engines.items():
            # MTU ratings should start with 'M'
            assert spec.rating_designation.startswith(
                "M"
            ), f"{model_name} should have M-code rating, got {spec.rating_designation}"


class TestEnginePowerData:
    """Test ENGINE_POWER_DATA reference data."""

    def test_power_data_not_empty(self):
        """Verify ENGINE_POWER_DATA has entries."""
        assert len(ENGINE_POWER_DATA) > 0
        assert len(ENGINE_POWER_DATA) >= 40  # At least 40 engines with power data

    def test_power_data_structure(self):
        """Verify power data has correct tuple structure."""
        for model_name, data in ENGINE_POWER_DATA.items():
            assert len(data) == 4, f"{model_name} should have 4 elements"
            power_kw, rpm, emission_tier, fuel_types = data
            assert isinstance(power_kw, (int, float)), f"{model_name} power_kw type"
            assert power_kw > 0, f"{model_name} power_kw should be positive"
            assert isinstance(rpm, int), f"{model_name} rpm type"
            assert rpm > 0, f"{model_name} rpm should be positive"
            assert isinstance(emission_tier, str), f"{model_name} emission_tier type"
            assert isinstance(fuel_types, list), f"{model_name} fuel_types type"

    def test_power_ranges_reasonable(self):
        """Verify power values are in reasonable marine engine range."""
        for model_name, data in ENGINE_POWER_DATA.items():
            power_kw, rpm, _, _ = data
            # Marine high-speed engines: 100 kW to 15,000 kW
            assert (
                100 <= power_kw <= 15000
            ), f"{model_name} power {power_kw} out of range"
            # High-speed engines: 750 RPM to 2500 RPM
            assert 750 <= rpm <= 2500, f"{model_name} RPM {rpm} out of range"


class TestDutyClassOperatingProfile:
    """Test DUTY_CLASS_OPERATING_PROFILE reference data."""

    def test_all_duty_classes_covered(self):
        """Verify all duty classes have operating profiles."""
        expected_classes = [
            DutyClass.CONTINUOUS,
            DutyClass.HEAVY_DUTY,
            DutyClass.MEDIUM_DUTY,
            DutyClass.LIGHT_DUTY,
            DutyClass.PLEASURE,
            DutyClass.INTERMITTENT,
        ]
        for dc in expected_classes:
            assert dc in DUTY_CLASS_OPERATING_PROFILE, f"Missing profile for {dc}"

    def test_operating_profile_structure(self):
        """Verify operating profiles have correct structure."""
        required_keys = [
            "load_factor_min",
            "load_factor_max",
            "annual_hours_min",
            "annual_hours_max",
        ]
        for dc, profile in DUTY_CLASS_OPERATING_PROFILE.items():
            for key in required_keys:
                assert key in profile, f"{dc} missing {key}"


class TestManufacturerMapping:
    """Test manufacturer mapping helper functions."""

    def test_mtu_manufacturer_mapping(self):
        """Test MTU manufacturer extraction."""
        assert (
            _get_manufacturer_from_model_name("MTU 12V 2000 M93")
            == "Rolls-Royce Power Systems"
        )
        assert (
            _get_manufacturer_from_model_name("MTU 16V 4000 M73")
            == "Rolls-Royce Power Systems"
        )

    def test_caterpillar_manufacturer_mapping(self):
        """Test Caterpillar manufacturer extraction."""
        assert _get_manufacturer_from_model_name("Cat 3516C") == "Caterpillar MaK"
        assert _get_manufacturer_from_model_name("Cat C32") == "Caterpillar MaK"

    def test_cummins_manufacturer_mapping(self):
        """Test Cummins manufacturer extraction."""
        assert _get_manufacturer_from_model_name("Cummins QSK60") == "Cummins Marine"

    def test_man_manufacturer_mapping(self):
        """Test MAN manufacturer extraction."""
        assert (
            _get_manufacturer_from_model_name("MAN D2862 LE463")
            == "MAN Energy Solutions"
        )
        assert (
            _get_manufacturer_from_model_name("MAN V12-2000CR")
            == "MAN Energy Solutions"
        )

    def test_wartsila_manufacturer_mapping(self):
        """Test Wartsila manufacturer extraction."""
        assert _get_manufacturer_from_model_name("Wartsila 6L20") == "Wärtsilä"


class TestSeriesMapping:
    """Test series mapping helper functions."""

    def test_mtu_series_mapping(self):
        """Test MTU series extraction."""
        assert _get_series_from_model_name("MTU 12V 2000 M93") == "2000"
        assert _get_series_from_model_name("MTU 16V 4000 M73") == "4000"
        assert _get_series_from_model_name("MTU 20V 8000 M91") == "8000"

    def test_caterpillar_series_mapping(self):
        """Test Caterpillar series extraction."""
        assert _get_series_from_model_name("Cat 3516C") == "3500"
        assert _get_series_from_model_name("Cat C32") == "C-Series"

    def test_cummins_series_mapping(self):
        """Test Cummins series extraction."""
        assert _get_series_from_model_name("Cummins QSK60") == "QSK"


class TestBuildRatingRecord:
    """Test _build_rating_record helper function."""

    def test_build_rating_record_with_power_data(self):
        """Test building a rating record with power data."""
        spec = ENGINE_MASTER_DATA.get("MTU 12V 2000 M93")
        assert spec is not None

        record = _build_rating_record(spec, "test-model-id")

        assert record["engine_model_id"] == "test-model-id"
        assert record["rating_designation"] == "M93"
        assert record["duty_class"] == DutyClass.LIGHT_DUTY.value
        assert record["power_kw"] == 1340  # From ENGINE_POWER_DATA
        assert record["rpm"] == 2450

    def test_build_rating_record_has_required_fields(self):
        """Test that rating records have all required fields."""
        spec = ENGINE_MASTER_DATA.get("MTU 16V 4000 M73")
        assert spec is not None

        record = _build_rating_record(spec, "test-model-id")

        required_fields = [
            "id",
            "engine_model_id",
            "rating_designation",
            "duty_class",
            "power_kw",
            "rpm",
            "emission_tier",
            "data_source",
            "created_at",
            "updated_at",
        ]
        for field in required_fields:
            assert field in record, f"Missing required field: {field}"


class TestCustomerRequirements:
    """Test CUSTOMER_REQUIREMENTS seed data."""

    def test_customer_requirements_not_empty(self):
        """Verify CUSTOMER_REQUIREMENTS has entries."""
        assert len(CUSTOMER_REQUIREMENTS) > 0
        assert len(CUSTOMER_REQUIREMENTS) >= 5  # At least 5 requirements

    def test_customer_requirements_have_required_fields(self):
        """Verify all requirements have required fields."""
        required_fields = [
            "customer_name",
            "power_required_kw",
            "duty_class_required",
            "vessel_type",
            "region",
        ]
        for req in CUSTOMER_REQUIREMENTS:
            for field in required_fields:
                assert (
                    field in req
                ), f"Requirement missing {field}: {req.get('customer_name')}"

    def test_customer_requirements_power_ranges(self):
        """Verify power requirements are in reasonable range."""
        for req in CUSTOMER_REQUIREMENTS:
            power = req.get("power_required_kw")
            assert power is not None, f"Missing power: {req.get('customer_name')}"
            assert 100 <= power <= 50000, f"Power out of range: {power}"

    def test_sap_customer_ids_present(self):
        """Verify some requirements have SAP customer IDs."""
        with_sap_id = [r for r in CUSTOMER_REQUIREMENTS if r.get("customer_id")]
        assert len(with_sap_id) >= 3, "Should have at least 3 requirements with SAP IDs"


class TestCompetitiveMappings:
    """Test COMPETITIVE_MAPPINGS seed data."""

    def test_competitive_mappings_not_empty(self):
        """Verify COMPETITIVE_MAPPINGS has entries."""
        assert len(COMPETITIVE_MAPPINGS) > 0
        assert len(COMPETITIVE_MAPPINGS) >= 5  # At least 5 mappings

    def test_competitive_mappings_have_required_fields(self):
        """Verify all mappings have required fields."""
        required_fields = [
            "our_rating_name",
            "competitor_rating_name",
            "competitive_position",
            "threat_level",
        ]
        for mapping in COMPETITIVE_MAPPINGS:
            for field in required_fields:
                assert field in mapping, f"Mapping missing {field}"

    def test_mtu_is_our_product(self):
        """Verify our ratings are MTU products."""
        for mapping in COMPETITIVE_MAPPINGS:
            our_rating = mapping.get("our_rating_name", "")
            assert our_rating.startswith(
                "MTU"
            ), f"Our rating should be MTU: {our_rating}"

    def test_valid_competitive_positions(self):
        """Verify competitive positions are valid."""
        valid_positions = [
            "strong_advantage",
            "advantage",
            "parity",
            "disadvantage",
            "strong_disadvantage",
        ]
        for mapping in COMPETITIVE_MAPPINGS:
            position = mapping.get("competitive_position")
            assert position in valid_positions, f"Invalid position: {position}"


class TestCompetitorEngagements:
    """Test COMPETITOR_ENGAGEMENTS seed data."""

    def test_competitor_engagements_not_empty(self):
        """Verify COMPETITOR_ENGAGEMENTS has entries."""
        assert len(COMPETITOR_ENGAGEMENTS) > 0
        assert len(COMPETITOR_ENGAGEMENTS) >= 5  # At least 5 engagements

    def test_competitor_engagements_have_required_fields(self):
        """Verify all engagements have required fields."""
        required_fields = [
            "customer_name",
            "competitor",
            "engagement_type",
            "threat_level",
        ]
        for engagement in COMPETITOR_ENGAGEMENTS:
            for field in required_fields:
                assert field in engagement, f"Engagement missing {field}"

    def test_valid_engagement_types(self):
        """Verify engagement types are valid."""
        valid_types = [
            "contract_win",
            "proposal",
            "demo",
            "partnership",
            "rumored",
            "lost_to_us",
        ]
        for engagement in COMPETITOR_ENGAGEMENTS:
            eng_type = engagement.get("engagement_type")
            assert eng_type in valid_types, f"Invalid type: {eng_type}"

    def test_valid_threat_levels(self):
        """Verify threat levels are valid."""
        valid_levels = [
            "critical",
            "high",
            "medium",
            "low",
            "informational",
        ]
        for engagement in COMPETITOR_ENGAGEMENTS:
            level = engagement.get("threat_level")
            assert level in valid_levels, f"Invalid threat level: {level}"

    def test_has_critical_threats(self):
        """Verify we have some critical threat scenarios for testing."""
        critical = [
            e for e in COMPETITOR_ENGAGEMENTS if e.get("threat_level") == "critical"
        ]
        assert len(critical) >= 1, "Should have at least 1 critical threat for testing"

    def test_has_wins_and_losses(self):
        """Verify we have both wins and losses for testing."""
        wins = [
            e
            for e in COMPETITOR_ENGAGEMENTS
            if e.get("engagement_type") == "lost_to_us"
        ]
        losses = [
            e
            for e in COMPETITOR_ENGAGEMENTS
            if e.get("engagement_type") == "contract_win"
        ]
        assert len(wins) >= 1, "Should have at least 1 win (lost_to_us)"
        assert (
            len(losses) >= 1
        ), "Should have at least 1 loss (contract_win by competitor)"
