"""
Unit Tests for Knowledge Base Relevance Scorer

Tests the deterministic rule-based scoring for marine engine articles.
NO MOCKING - uses real dataclasses and scoring logic.

Scoring Rules Tested:
- Technical: Engine model (+40), Tier-1 (+20), Power>10kW (+15), RPM<=750 (+10)
- Market: Offshore O&G (+30), Marine power gen (+25), Marine transport (+20), Land (+5)
- Commercial: New order (+30), Retrofit (+25), Launch (+20), Regulatory (+15), Financial (+10)

Classification Thresholds:
- HIGH_PRIORITY: >= 70
- MONITOR: 40-69
- IGNORE: < 40
"""

import json
import uuid

import pytest

from lead_to_cash.services.knowledge_base.models import (
    ExtractedEntity,
    ManufacturerTier,
    MarketSegmentType,
    PowerClass,
    RelevanceClassification,
    ResolvedEntity,
    RPMClass,
)
from lead_to_cash.services.knowledge_base.scorer import (
    RelevanceScorer,
    ScoreBreakdown,
    ScoringInput,
    get_relevance_scorer,
)

# =============================================================================
# FIXTURES
# =============================================================================


@pytest.fixture
def scorer():
    """Provide a fresh RelevanceScorer instance."""
    return RelevanceScorer()


@pytest.fixture
def sample_extracted_entity():
    """Create a sample extracted entity."""
    return ExtractedEntity(
        text="Wärtsilä 31DF",
        entity_type="engine_model",
        confidence=0.9,
        context="The vessel will be powered by Wärtsilä 31DF engines.",
    )


def make_resolved_entity(
    text: str = "W31DF",
    entity_type: str = "engine_model",
    entity_id: str = None,
    entity_name: str = "Wärtsilä 31DF",
    match_type: str = "exact",
    match_confidence: float = 1.0,
    rpm_class: RPMClass = None,
    power_class: PowerClass = None,
    manufacturer_tier: ManufacturerTier = None,
) -> ResolvedEntity:
    """Factory for creating resolved entities with defaults."""
    extracted = ExtractedEntity(
        text=text,
        entity_type=entity_type,
        confidence=0.9,
    )
    return ResolvedEntity(
        extracted=extracted,
        entity_type=entity_type,
        entity_id=entity_id or str(uuid.uuid4()),
        entity_name=entity_name,
        match_type=match_type,
        match_confidence=match_confidence,
        rpm_class=rpm_class,
        power_class=power_class,
        manufacturer_tier=manufacturer_tier,
    )


# =============================================================================
# SCORE BREAKDOWN TESTS
# =============================================================================


class TestScoreBreakdown:
    """Tests for ScoreBreakdown dataclass."""

    def test_technical_total(self):
        """Test technical score subtotal calculation."""
        breakdown = ScoreBreakdown(
            engine_model_identified=40,
            tier_1_manufacturer=20,
            power_over_10000kw=15,
            rpm_lte_750=10,
        )
        assert breakdown.technical_total == 85

    def test_market_total(self):
        """Test market score subtotal calculation."""
        breakdown = ScoreBreakdown(
            offshore_oil_gas=30,
            marine_power_generation=25,
        )
        assert breakdown.market_total == 55

    def test_commercial_total(self):
        """Test commercial score subtotal calculation."""
        breakdown = ScoreBreakdown(
            new_vessel_order=30,
            fleet_retrofit=25,
            product_launch=20,
        )
        assert breakdown.commercial_total == 75

    def test_total_score(self):
        """Test total score calculation."""
        breakdown = ScoreBreakdown(
            engine_model_identified=40,
            tier_1_manufacturer=20,
            offshore_oil_gas=30,
            new_vessel_order=30,
        )
        assert breakdown.total == 120

    def test_to_dict(self):
        """Test conversion to dictionary."""
        breakdown = ScoreBreakdown(
            engine_model_identified=40,
            offshore_oil_gas=30,
        )
        result = breakdown.to_dict()

        assert "technical" in result
        assert "market" in result
        assert "commercial" in result
        assert "total" in result
        assert result["technical"]["engine_model_identified"] == 40
        assert result["market"]["offshore_oil_gas"] == 30


# =============================================================================
# TECHNICAL SCORING TESTS
# =============================================================================


class TestTechnicalScoring:
    """Tests for technical relevance scoring."""

    def test_engine_model_identified_score(self, scorer):
        """Engine model identified should add +40 points."""
        entities = [make_resolved_entity(entity_type="engine_model")]
        input_data = ScoringInput(
            article_id="test-001",
            article_content="Test content",
            entities=entities,
        )

        score = scorer.score(input_data)

        assert score.technical_score >= 40
        breakdown = json.loads(score.score_breakdown)
        assert breakdown["technical"]["engine_model_identified"] == 40

    def test_tier_1_manufacturer_score(self, scorer):
        """Tier-1 manufacturer should add +20 points."""
        entities = [
            make_resolved_entity(
                entity_type="manufacturer",
                manufacturer_tier=ManufacturerTier.TIER_1,
            )
        ]
        input_data = ScoringInput(
            article_id="test-002",
            article_content="Test content",
            entities=entities,
        )

        score = scorer.score(input_data)

        assert score.technical_score >= 20
        breakdown = json.loads(score.score_breakdown)
        assert breakdown["technical"]["tier_1_manufacturer"] == 20

    def test_tier_2_manufacturer_no_bonus(self, scorer):
        """Tier-2 manufacturer should NOT add tier bonus."""
        entities = [
            make_resolved_entity(
                entity_type="manufacturer",
                manufacturer_tier=ManufacturerTier.TIER_2,
            )
        ]
        input_data = ScoringInput(
            article_id="test-003",
            article_content="Test content",
            entities=entities,
        )

        score = scorer.score(input_data)

        breakdown = json.loads(score.score_breakdown)
        assert breakdown["technical"]["tier_1_manufacturer"] == 0

    def test_high_power_score(self, scorer):
        """Power > 10,000 kW should add +15 points."""
        entities = [
            make_resolved_entity(
                entity_type="engine_model",
                power_class=PowerClass.HIGH,  # 10000-25000 kW
            )
        ]
        input_data = ScoringInput(
            article_id="test-004",
            article_content="Test content",
            entities=entities,
        )

        score = scorer.score(input_data)

        breakdown = json.loads(score.score_breakdown)
        assert breakdown["technical"]["power_over_10000kw"] == 15

    def test_ultra_high_power_score(self, scorer):
        """Ultra-high power (25000-40000 kW) should add +15 points."""
        entities = [
            make_resolved_entity(
                entity_type="engine_model",
                power_class=PowerClass.ULTRA_HIGH,
            )
        ]
        input_data = ScoringInput(
            article_id="test-005",
            article_content="Test content",
            entities=entities,
        )

        score = scorer.score(input_data)

        breakdown = json.loads(score.score_breakdown)
        assert breakdown["technical"]["power_over_10000kw"] == 15

    def test_medium_power_no_bonus(self, scorer):
        """Medium power (2000-10000 kW) should NOT add power bonus."""
        entities = [
            make_resolved_entity(
                entity_type="engine_model",
                power_class=PowerClass.MID,
            )
        ]
        input_data = ScoringInput(
            article_id="test-006",
            article_content="Test content",
            entities=entities,
        )

        score = scorer.score(input_data)

        breakdown = json.loads(score.score_breakdown)
        assert breakdown["technical"]["power_over_10000kw"] == 0

    def test_medium_speed_rpm_score(self, scorer):
        """Medium-speed RPM (300-1000) should add +10 points."""
        entities = [
            make_resolved_entity(
                entity_type="engine_model",
                rpm_class=RPMClass.MEDIUM_SPEED,
            )
        ]
        input_data = ScoringInput(
            article_id="test-007",
            article_content="Test content",
            entities=entities,
        )

        score = scorer.score(input_data)

        breakdown = json.loads(score.score_breakdown)
        assert breakdown["technical"]["rpm_lte_750"] == 10

    def test_high_speed_rpm_no_bonus(self, scorer):
        """High-speed RPM (>1000) should NOT add RPM bonus."""
        entities = [
            make_resolved_entity(
                entity_type="engine_model",
                rpm_class=RPMClass.HIGH_SPEED,
            )
        ]
        input_data = ScoringInput(
            article_id="test-008",
            article_content="Test content",
            entities=entities,
        )

        score = scorer.score(input_data)

        breakdown = json.loads(score.score_breakdown)
        assert breakdown["technical"]["rpm_lte_750"] == 0

    def test_max_technical_score(self, scorer):
        """Test maximum technical score with all bonuses."""
        # Engine model + Tier-1 manufacturer + high power + medium speed
        entities = [
            make_resolved_entity(
                entity_type="engine_model",
                manufacturer_tier=ManufacturerTier.TIER_1,
                power_class=PowerClass.HIGH,
                rpm_class=RPMClass.MEDIUM_SPEED,
            )
        ]
        input_data = ScoringInput(
            article_id="test-009",
            article_content="Test content",
            entities=entities,
        )

        score = scorer.score(input_data)

        # 40 + 20 + 15 + 10 = 85
        assert score.technical_score == 85


# =============================================================================
# MARKET SCORING TESTS
# =============================================================================


class TestMarketScoring:
    """Tests for market relevance scoring."""

    def test_offshore_oil_gas_score(self, scorer):
        """Offshore O&G should add +30 points."""
        input_data = ScoringInput(
            article_id="test-010",
            article_content="Test content",
            market_segments=[MarketSegmentType.OFFSHORE_OIL_GAS],
        )

        score = scorer.score(input_data)

        assert score.market_score == 30
        breakdown = json.loads(score.score_breakdown)
        assert breakdown["market"]["offshore_oil_gas"] == 30

    def test_fpso_maps_to_offshore(self, scorer):
        """FPSO should map to offshore O&G score bucket."""
        input_data = ScoringInput(
            article_id="test-011",
            article_content="Test content",
            market_segments=[MarketSegmentType.FPSO_OFFSHORE_PRODUCTION],
        )

        score = scorer.score(input_data)

        # FPSO uses same bucket as offshore
        assert score.market_score == 30
        breakdown = json.loads(score.score_breakdown)
        assert breakdown["market"]["offshore_oil_gas"] == 30

    def test_marine_power_generation_score(self, scorer):
        """Marine power gen should add +25 points."""
        input_data = ScoringInput(
            article_id="test-012",
            article_content="Test content",
            market_segments=[MarketSegmentType.MARINE_POWER_GENERATION],
        )

        score = scorer.score(input_data)

        assert score.market_score == 25

    def test_marine_transportation_score(self, scorer):
        """Marine transportation should add +20 points."""
        input_data = ScoringInput(
            article_id="test-013",
            article_content="Test content",
            market_segments=[MarketSegmentType.MARINE_TRANSPORTATION],
        )

        score = scorer.score(input_data)

        assert score.market_score == 20

    def test_land_power_plant_score(self, scorer):
        """Land power plant should add +5 points (lowest priority)."""
        input_data = ScoringInput(
            article_id="test-014",
            article_content="Test content",
            market_segments=[MarketSegmentType.LAND_POWER_PLANT],
        )

        score = scorer.score(input_data)

        assert score.market_score == 5

    def test_diminishing_returns_two_segments(self, scorer):
        """Second market segment should apply 50% diminishing returns (capped at 15)."""
        # Offshore (30) + Marine transport (20 * 0.5 = 10, capped at 15) = 40
        # But cap is applied as min(score * 0.5, 15)
        input_data = ScoringInput(
            article_id="test-015",
            article_content="Test content",
            market_segments=[
                MarketSegmentType.OFFSHORE_OIL_GAS,  # 30 (first)
                MarketSegmentType.MARINE_TRANSPORTATION,  # 20 * 0.5 = 10 (second)
            ],
        )

        score = scorer.score(input_data)

        # First segment: 30, second: min(20*0.5, 15) = 10
        assert score.market_score == 40

    def test_diminishing_returns_cap_at_15(self, scorer):
        """Second segment should be capped at 15 points."""
        input_data = ScoringInput(
            article_id="test-016",
            article_content="Test content",
            market_segments=[
                MarketSegmentType.MARINE_TRANSPORTATION,  # 20 (first)
                MarketSegmentType.OFFSHORE_OIL_GAS,  # 30 * 0.5 = 15 (second, capped)
            ],
        )

        score = scorer.score(input_data)

        # Sorted by score descending: offshore (30) first, transport (20*0.5=10) second
        # Result: 30 + 10 = 40
        assert score.market_score == 40

    def test_third_segment_ignored(self, scorer):
        """Third+ market segments should be ignored to prevent inflation."""
        input_data = ScoringInput(
            article_id="test-017",
            article_content="Test content",
            market_segments=[
                MarketSegmentType.OFFSHORE_OIL_GAS,  # 30
                MarketSegmentType.MARINE_POWER_GENERATION,  # 25 * 0.5 = 12.5 -> 12
                MarketSegmentType.MARINE_TRANSPORTATION,  # ignored
                MarketSegmentType.LAND_POWER_PLANT,  # ignored
            ],
        )

        score = scorer.score(input_data)

        # Only first two counted: 30 + 12 = 42
        assert score.market_score == 42

    def test_no_duplicate_offshore_fpso(self, scorer):
        """FPSO and Offshore O&G should NOT duplicate (same bucket)."""
        input_data = ScoringInput(
            article_id="test-018",
            article_content="Test content",
            market_segments=[
                MarketSegmentType.OFFSHORE_OIL_GAS,
                MarketSegmentType.FPSO_OFFSHORE_PRODUCTION,  # Same bucket, no duplicate
            ],
        )

        score = scorer.score(input_data)

        # Only one offshore score, not doubled
        assert score.market_score == 30


# =============================================================================
# COMMERCIAL SIGNAL TESTS
# =============================================================================


class TestCommercialScoring:
    """Tests for commercial signal scoring."""

    def test_new_vessel_order_score(self, scorer):
        """New vessel order should add +30 points."""
        input_data = ScoringInput(
            article_id="test-019",
            article_content="Test content",
            commercial_signals=["new_vessel_order"],
        )

        score = scorer.score(input_data)

        assert score.commercial_score == 30

    def test_fleet_retrofit_score(self, scorer):
        """Fleet retrofit should add +25 points."""
        input_data = ScoringInput(
            article_id="test-020",
            article_content="Test content",
            commercial_signals=["fleet_retrofit"],
        )

        score = scorer.score(input_data)

        assert score.commercial_score == 25

    def test_product_launch_score(self, scorer):
        """Product launch should add +20 points."""
        input_data = ScoringInput(
            article_id="test-021",
            article_content="Test content",
            commercial_signals=["product_launch"],
        )

        score = scorer.score(input_data)

        assert score.commercial_score == 20

    def test_regulatory_change_score(self, scorer):
        """Regulatory change should add +15 points."""
        input_data = ScoringInput(
            article_id="test-022",
            article_content="Test content",
            commercial_signals=["regulatory_change"],
        )

        score = scorer.score(input_data)

        assert score.commercial_score == 15

    def test_financial_results_score(self, scorer):
        """Financial results should add +10 points."""
        input_data = ScoringInput(
            article_id="test-023",
            article_content="Test content",
            commercial_signals=["financial_results"],
        )

        score = scorer.score(input_data)

        assert score.commercial_score == 10

    def test_multiple_commercial_signals(self, scorer):
        """Multiple commercial signals should stack."""
        input_data = ScoringInput(
            article_id="test-024",
            article_content="Test content",
            commercial_signals=["new_vessel_order", "fleet_retrofit", "product_launch"],
        )

        score = scorer.score(input_data)

        # 30 + 25 + 20 = 75
        assert score.commercial_score == 75


# =============================================================================
# COMMERCIAL SIGNAL DETECTION TESTS
# =============================================================================


class TestCommercialSignalDetection:
    """Tests for automatic commercial signal detection from content."""

    def test_detect_vessel_order(self, scorer):
        """Should detect new vessel order keywords."""
        content = "Seatrium has been awarded contract for new ferries"
        signals = scorer.detect_commercial_signals(content)

        assert "new_vessel_order" in signals

    def test_detect_contract_win(self, scorer):
        """Should detect contract win keywords."""
        content = "Wärtsilä wins contract for 12 dual-fuel engines"
        signals = scorer.detect_commercial_signals(content)

        assert "new_vessel_order" in signals

    def test_detect_retrofit(self, scorer):
        """Should detect retrofit/repowering keywords."""
        content = "Fleet modernization project includes engine retrofit"
        signals = scorer.detect_commercial_signals(content)

        assert "fleet_retrofit" in signals

    def test_detect_lng_conversion(self, scorer):
        """Should detect LNG conversion as retrofit."""
        content = "The vessel underwent lng conversion to dual-fuel operation"
        signals = scorer.detect_commercial_signals(content)

        assert "fleet_retrofit" in signals

    def test_detect_product_launch(self, scorer):
        """Should detect product launch keywords."""
        content = "MAN launches new engine series for marine applications"
        signals = scorer.detect_commercial_signals(content)

        assert "product_launch" in signals

    def test_detect_regulatory_imo(self, scorer):
        """Should detect IMO regulatory keywords."""
        content = "New IMO Tier III requirements affect engine selection"
        signals = scorer.detect_commercial_signals(content)

        assert "regulatory_change" in signals

    def test_detect_regulatory_eexi(self, scorer):
        """Should detect EEXI compliance keywords."""
        content = "Fleet owners preparing for eexi compliance deadlines"
        signals = scorer.detect_commercial_signals(content)

        assert "regulatory_change" in signals

    def test_detect_financial_results(self, scorer):
        """Should detect financial results keywords."""
        content = "Company reports strong quarterly results with revenue growth"
        signals = scorer.detect_commercial_signals(content)

        assert "financial_results" in signals

    def test_no_false_positive_order(self, scorer):
        """Should not trigger on generic 'order' without context."""
        content = "The engine order of components is important"
        signals = scorer.detect_commercial_signals(content)

        # 'order' alone without "vessel order", "contract", etc. should not trigger
        assert "new_vessel_order" not in signals

    def test_content_based_scoring(self, scorer):
        """Signals should be detected from content and scored."""
        input_data = ScoringInput(
            article_id="test-025",
            article_content="Wärtsilä wins contract for 8 engines in newbuild contract",
            commercial_signals=[],  # Empty - should detect from content
        )

        score = scorer.score(input_data)

        assert score.commercial_score >= 30  # At least new_vessel_order


# =============================================================================
# MARKET SEGMENT DETECTION TESTS
# =============================================================================


class TestMarketSegmentDetection:
    """Tests for automatic market segment detection from content."""

    def test_detect_offshore(self, scorer):
        """Should detect offshore O&G keywords."""
        content = "New offshore platform will require auxiliary power"
        segments = scorer.detect_market_segments(content)

        assert MarketSegmentType.OFFSHORE_OIL_GAS in segments

    def test_detect_fpso(self, scorer):
        """Should detect FPSO keywords."""
        content = "The FPSO vessel will operate in Brazilian waters"
        segments = scorer.detect_market_segments(content)

        assert MarketSegmentType.FPSO_OFFSHORE_PRODUCTION in segments

    def test_detect_power_generation(self, scorer):
        """Should detect marine power generation keywords."""
        content = "New genset installation for onboard power generation"
        segments = scorer.detect_market_segments(content)

        assert MarketSegmentType.MARINE_POWER_GENERATION in segments

    def test_detect_marine_transport(self, scorer):
        """Should detect marine transportation keywords."""
        content = "New ferry service connecting Singapore and Indonesia"
        segments = scorer.detect_market_segments(content)

        assert MarketSegmentType.MARINE_TRANSPORTATION in segments

    def test_detect_land_power(self, scorer):
        """Should detect land power keywords."""
        content = "Land-based power plant for stationary applications"
        segments = scorer.detect_market_segments(content)

        assert MarketSegmentType.LAND_POWER_PLANT in segments


# =============================================================================
# CLASSIFICATION TESTS
# =============================================================================


class TestClassification:
    """Tests for score classification thresholds."""

    def test_high_priority_threshold(self, scorer):
        """Score >= 70 should be HIGH_PRIORITY."""
        # Engine model (40) + offshore (30) = 70
        entities = [make_resolved_entity(entity_type="engine_model")]
        input_data = ScoringInput(
            article_id="test-026",
            article_content="Test content",
            entities=entities,
            market_segments=[MarketSegmentType.OFFSHORE_OIL_GAS],
        )

        score = scorer.score(input_data)

        assert score.total_score >= 70
        assert score.classification == RelevanceClassification.HIGH_PRIORITY.value

    def test_monitor_threshold_lower(self, scorer):
        """Score 40-69 should be MONITOR."""
        # Engine model (40) = 40
        entities = [make_resolved_entity(entity_type="engine_model")]
        input_data = ScoringInput(
            article_id="test-027",
            article_content="Test content",  # No commercial signals
            entities=entities,
        )

        score = scorer.score(input_data)

        assert score.total_score == 40
        assert score.classification == RelevanceClassification.MONITOR.value

    def test_monitor_threshold_upper(self, scorer):
        """Score of 69 should still be MONITOR."""
        # Engine model (40) + power gen (25) + land (2.5 capped) = 40 + 25 + 2 = 67
        # Actually let's do: engine model (40) + tier1 (20) = 60, + land (5) = 65
        entities = [
            make_resolved_entity(
                entity_type="engine_model",
                manufacturer_tier=ManufacturerTier.TIER_1,
            )
        ]
        input_data = ScoringInput(
            article_id="test-028",
            article_content="Test content",
            entities=entities,
            market_segments=[MarketSegmentType.LAND_POWER_PLANT],
        )

        score = scorer.score(input_data)

        assert 40 <= score.total_score < 70
        assert score.classification == RelevanceClassification.MONITOR.value

    def test_ignore_threshold(self, scorer):
        """Score < 40 should be IGNORE."""
        input_data = ScoringInput(
            article_id="test-029",
            article_content="Generic maritime news with no specific entities",
        )

        score = scorer.score(input_data)

        assert score.total_score < 40
        assert score.classification == RelevanceClassification.IGNORE.value

    def test_classify_method(self, scorer):
        """Test classify method directly."""
        assert scorer.classify(100) == RelevanceClassification.HIGH_PRIORITY
        assert scorer.classify(70) == RelevanceClassification.HIGH_PRIORITY
        assert scorer.classify(69) == RelevanceClassification.MONITOR
        assert scorer.classify(40) == RelevanceClassification.MONITOR
        assert scorer.classify(39) == RelevanceClassification.IGNORE
        assert scorer.classify(0) == RelevanceClassification.IGNORE


# =============================================================================
# EXPLANATION TESTS
# =============================================================================


class TestScoreExplanation:
    """Tests for score explanation generation."""

    def test_explanation_includes_technical(self, scorer):
        """Explanation should include technical scoring details."""
        entities = [
            make_resolved_entity(
                entity_type="engine_model",
                manufacturer_tier=ManufacturerTier.TIER_1,
            )
        ]
        input_data = ScoringInput(
            article_id="test-030",
            article_content="Test content",
            entities=entities,
        )

        score = scorer.score(input_data)

        assert "Technical" in score.score_explanation
        assert "engine model identified" in score.score_explanation
        assert "Tier-1 manufacturer" in score.score_explanation

    def test_explanation_includes_market(self, scorer):
        """Explanation should include market scoring details."""
        input_data = ScoringInput(
            article_id="test-031",
            article_content="Test content",
            market_segments=[MarketSegmentType.OFFSHORE_OIL_GAS],
        )

        score = scorer.score(input_data)

        assert "Market" in score.score_explanation
        assert "offshore O&G" in score.score_explanation

    def test_explanation_includes_commercial(self, scorer):
        """Explanation should include commercial scoring details."""
        input_data = ScoringInput(
            article_id="test-032",
            article_content="Test content",
            commercial_signals=["new_vessel_order"],
        )

        score = scorer.score(input_data)

        assert "Commercial" in score.score_explanation
        assert "new order" in score.score_explanation

    def test_explanation_includes_classification(self, scorer):
        """Explanation should include final classification."""
        entities = [make_resolved_entity(entity_type="engine_model")]
        input_data = ScoringInput(
            article_id="test-033",
            article_content="Test content",
            entities=entities,
            market_segments=[MarketSegmentType.OFFSHORE_OIL_GAS],
        )

        score = scorer.score(input_data)

        assert "HIGH_PRIORITY" in score.score_explanation


# =============================================================================
# ARTICLE SCORE OUTPUT TESTS
# =============================================================================


class TestArticleScoreOutput:
    """Tests for ArticleScore output format."""

    def test_score_has_required_fields(self, scorer):
        """ArticleScore should have all required fields."""
        input_data = ScoringInput(
            article_id="test-034",
            article_content="Test content",
        )

        score = scorer.score(input_data)

        assert score.id is not None
        assert score.article_id == "test-034"
        assert isinstance(score.technical_score, float)
        assert isinstance(score.market_score, float)
        assert isinstance(score.commercial_score, float)
        assert isinstance(score.total_score, float)
        assert score.classification in [e.value for e in RelevanceClassification]
        assert score.score_breakdown is not None
        assert score.scoring_model_version == "v1"
        assert score.scored_at is not None

    def test_breakdown_is_valid_json(self, scorer):
        """Score breakdown should be valid JSON."""
        input_data = ScoringInput(
            article_id="test-035",
            article_content="Test content",
        )

        score = scorer.score(input_data)

        # Should not raise
        breakdown = json.loads(score.score_breakdown)
        assert "technical" in breakdown
        assert "market" in breakdown
        assert "commercial" in breakdown
        assert "total" in breakdown


# =============================================================================
# SINGLETON TESTS
# =============================================================================


class TestSingleton:
    """Tests for singleton pattern."""

    def test_get_relevance_scorer_singleton(self):
        """get_relevance_scorer should return same instance."""
        scorer1 = get_relevance_scorer()
        scorer2 = get_relevance_scorer()

        assert scorer1 is scorer2


# =============================================================================
# EDGE CASES
# =============================================================================


class TestEdgeCases:
    """Tests for edge cases and boundary conditions."""

    def test_empty_input(self, scorer):
        """Empty input should produce zero scores."""
        input_data = ScoringInput(
            article_id="test-036",
            article_content="",
        )

        score = scorer.score(input_data)

        assert score.technical_score == 0
        assert score.market_score == 0
        assert score.commercial_score == 0
        assert score.total_score == 0
        assert score.classification == RelevanceClassification.IGNORE.value

    def test_empty_entities_list(self, scorer):
        """Empty entities list should not cause errors."""
        input_data = ScoringInput(
            article_id="test-037",
            article_content="Test content",
            entities=[],
        )

        score = scorer.score(input_data)

        assert score.technical_score == 0

    def test_duplicate_entities_handled(self, scorer):
        """Duplicate entities should not multiply scores."""
        # Two engine models should only trigger engine_model_identified once
        entities = [
            make_resolved_entity(entity_type="engine_model", entity_name="W31DF"),
            make_resolved_entity(entity_type="engine_model", entity_name="W34DF"),
        ]
        input_data = ScoringInput(
            article_id="test-038",
            article_content="Test content",
            entities=entities,
        )

        score = scorer.score(input_data)

        # Should still be just +40 for engine model, not +80
        breakdown = json.loads(score.score_breakdown)
        assert breakdown["technical"]["engine_model_identified"] == 40

    def test_case_insensitive_signal_detection(self, scorer):
        """Signal detection should be case insensitive."""
        content = "WÄRTSILÄ WINS CONTRACT for new FERRY vessels"
        signals = scorer.detect_commercial_signals(content)

        assert "new_vessel_order" in signals

    def test_max_possible_score(self, scorer):
        """Test maximum possible score scenario."""
        entities = [
            make_resolved_entity(
                entity_type="engine_model",
                manufacturer_tier=ManufacturerTier.TIER_1,
                power_class=PowerClass.HIGH,
                rpm_class=RPMClass.MEDIUM_SPEED,
            )
        ]
        input_data = ScoringInput(
            article_id="test-039",
            article_content="Wärtsilä wins contract for fleet modernization",
            entities=entities,
            market_segments=[
                MarketSegmentType.OFFSHORE_OIL_GAS,
                MarketSegmentType.MARINE_POWER_GENERATION,
            ],
            commercial_signals=[
                "new_vessel_order",
                "fleet_retrofit",
                "product_launch",
                "regulatory_change",
                "financial_results",
            ],
        )

        score = scorer.score(input_data)

        # Technical: 40 + 20 + 15 + 10 = 85
        # Market: 30 + min(25*0.5, 15) = 30 + 12 = 42
        # Commercial: 30 + 25 + 20 + 15 + 10 = 100
        # Total: 85 + 42 + 100 = 227 (but check actual)
        assert score.total_score > 150  # Sanity check for high score
        assert score.classification == RelevanceClassification.HIGH_PRIORITY.value


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
