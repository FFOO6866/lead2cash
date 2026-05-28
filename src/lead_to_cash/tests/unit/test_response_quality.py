"""
Unit Tests for Response Quality Infrastructure

Tests the core quality enforcement components:
- SourceTier hierarchy and source classification
- ScopeEnforcer scope discipline
- GroundingValidator claim verification
- OutputSchemaValidator response schema enforcement
- FollowUpResolver follow-up context resolution
- QualityMetrics observability
"""

import pytest

from lead_to_cash.core.response_quality import (
    FollowUpResolver,
    GroundingCheck,
    GroundingValidator,
    InsufficientEvidenceBuilder,
    OutputSchemaValidator,
    QualityMetrics,
    ResponseSection,
    ScopeEnforcer,
    SourceTier,
    get_highest_tier_sources,
    get_source_tier,
)


# =============================================================================
# Source Tier Tests
# =============================================================================


class TestSourceTier:
    """Tests for source tier classification and priority ordering."""

    def test_sap_is_tier_1(self):
        assert get_source_tier("SAP CPI (MS5)") == SourceTier.TIER_1_INTERNAL_STRUCTURED
        assert get_source_tier("SAP CPI") == SourceTier.TIER_1_INTERNAL_STRUCTURED
        assert get_source_tier("SAP CEC") == SourceTier.TIER_1_INTERNAL_STRUCTURED

    def test_knowledge_base_is_tier_1(self):
        assert (
            get_source_tier("Knowledge Base") == SourceTier.TIER_1_INTERNAL_STRUCTURED
        )
        assert (
            get_source_tier("Product Database") == SourceTier.TIER_1_INTERNAL_STRUCTURED
        )

    def test_vectordb_is_tier_2(self):
        assert (
            get_source_tier("Intelligence Database")
            == SourceTier.TIER_2_INTERNAL_SEMANTIC
        )
        assert (
            get_source_tier("Local Vector Database")
            == SourceTier.TIER_2_INTERNAL_SEMANTIC
        )

    def test_eodhd_is_tier_3(self):
        assert get_source_tier("EODHD") == SourceTier.TIER_3_EXTERNAL_TRUSTED
        assert get_source_tier("Financial Data") == SourceTier.TIER_3_EXTERNAL_TRUSTED

    def test_perplexity_is_tier_4(self):
        assert get_source_tier("Perplexity Search") == SourceTier.TIER_4_EXTERNAL_BROAD
        assert get_source_tier("Web Search") == SourceTier.TIER_4_EXTERNAL_BROAD

    def test_unknown_source_defaults_to_tier_4(self):
        assert (
            get_source_tier("Random Unknown Source") == SourceTier.TIER_4_EXTERNAL_BROAD
        )

    def test_tier_ordering(self):
        """Tier 1 < Tier 2 < Tier 3 < Tier 4 (lower is higher priority)."""
        assert (
            SourceTier.TIER_1_INTERNAL_STRUCTURED.value
            < SourceTier.TIER_2_INTERNAL_SEMANTIC.value
        )
        assert (
            SourceTier.TIER_2_INTERNAL_SEMANTIC.value
            < SourceTier.TIER_3_EXTERNAL_TRUSTED.value
        )
        assert (
            SourceTier.TIER_3_EXTERNAL_TRUSTED.value
            < SourceTier.TIER_4_EXTERNAL_BROAD.value
        )

    def test_get_highest_tier_sources(self):
        sources = ["SAP CPI (MS5)", "Perplexity Search", "EODHD"]
        tier, best = get_highest_tier_sources(sources)
        assert tier == SourceTier.TIER_1_INTERNAL_STRUCTURED
        assert best == ["SAP CPI (MS5)"]

    def test_get_highest_tier_sources_empty(self):
        tier, best = get_highest_tier_sources([])
        assert tier == SourceTier.TIER_4_EXTERNAL_BROAD
        assert best == []


# =============================================================================
# Scope Enforcer Tests
# =============================================================================


class TestScopeEnforcer:
    """Tests for intent scope discipline enforcement."""

    def test_product_fit_allows_specs(self):
        allowed = ScopeEnforcer.get_allowed_sections("product_fit")
        assert ResponseSection.PRODUCT_SPECS in allowed
        assert ResponseSection.ENGINE_COMPARISON in allowed

    def test_product_fit_forbids_billing(self):
        allowed = ScopeEnforcer.get_allowed_sections("product_fit")
        assert ResponseSection.BILLING_STATUS not in allowed
        assert ResponseSection.AGING_ANALYSIS not in allowed

    def test_product_fit_forbids_strategy_by_default(self):
        allowed = ScopeEnforcer.get_allowed_sections("product_fit")
        assert ResponseSection.SALES_STRATEGY not in allowed
        assert ResponseSection.ACTION_ITEMS not in allowed
        assert ResponseSection.RECOMMENDATIONS not in allowed

    def test_product_fit_allows_strategy_when_explicit(self):
        allowed = ScopeEnforcer.get_allowed_sections(
            "product_fit", explicit_request=True
        )
        assert ResponseSection.SALES_STRATEGY in allowed
        assert ResponseSection.ACTION_ITEMS in allowed

    def test_billing_ar_allows_billing_sections(self):
        allowed = ScopeEnforcer.get_allowed_sections("billing_ar")
        assert ResponseSection.BILLING_STATUS in allowed
        assert ResponseSection.AGING_ANALYSIS in allowed
        assert ResponseSection.COLLECTIONS_STATUS in allowed

    def test_billing_ar_forbids_product_specs(self):
        allowed = ScopeEnforcer.get_allowed_sections("billing_ar")
        assert ResponseSection.PRODUCT_SPECS not in allowed
        assert ResponseSection.ENGINE_COMPARISON not in allowed

    def test_competitor_intel_allows_competitor_sections(self):
        allowed = ScopeEnforcer.get_allowed_sections("competitor_intel")
        assert ResponseSection.COMPETITOR_ACTIVITY in allowed
        assert ResponseSection.ENGINE_COMPARISON in allowed
        assert ResponseSection.MARKET_TRENDS in allowed

    def test_competitor_intel_forbids_billing(self):
        allowed = ScopeEnforcer.get_allowed_sections("competitor_intel")
        assert ResponseSection.BILLING_STATUS not in allowed

    def test_unknown_intent_uses_general_defaults(self):
        allowed = ScopeEnforcer.get_allowed_sections("nonexistent_intent")
        # Should use general_question defaults
        assert ResponseSection.PRODUCT_SPECS in allowed

    def test_scope_instruction_output(self):
        instruction = ScopeEnforcer.build_scope_instruction("product_fit")
        assert "SCOPE DISCIPLINE" in instruction
        assert "product_fit" in instruction
        assert "ALLOWED" in instruction
        assert "FORBIDDEN" in instruction

    def test_detect_billing_in_product_response(self):
        """Product response should NOT contain billing/aging content."""
        response = "The engine specs are 1340 kW. The aging analysis shows 45 days overdue invoices."
        violations = ScopeEnforcer.detect_scope_violations(response, "product_fit")
        assert len(violations) > 0
        violation_sections = [v["section"] for v in violations]
        assert "aging_analysis" in violation_sections

    def test_no_violations_for_allowed_content(self):
        """Product response with only product content should pass."""
        response = "The MTU 12V 2000 delivers 1340 kW at 2250 RPM with excellent fuel consumption."
        violations = ScopeEnforcer.detect_scope_violations(response, "product_fit")
        assert len(violations) == 0

    def test_detect_strategy_in_spec_response(self):
        """Unsolicited recommendations should be flagged."""
        response = "The engine has 1340 kW. We recommend pursuing this opportunity aggressively."
        violations = ScopeEnforcer.detect_scope_violations(response, "product_fit")
        violation_sections = [v["section"] for v in violations]
        assert "recommendations" in violation_sections

    def test_detect_rrps_implications_unsolicited(self):
        """RRPS implications in non-strategy response should be flagged."""
        response = "Caterpillar revenue grew 5%. RRPS implications include potential market share loss."
        violations = ScopeEnforcer.detect_scope_violations(response, "competitor_intel")
        violation_sections = [v["section"] for v in violations]
        assert "rrps_implications" in violation_sections


# =============================================================================
# Grounding Validator Tests
# =============================================================================


class TestGroundingValidator:
    """Tests for claim grounding verification."""

    def test_grounded_numeric_claim(self):
        response = "The engine produces 1340 kW at full load."
        evidence = "MTU 12V 2000 M93 delivers 1340 kW at 2250 RPM"
        sources = ["Knowledge Base"]
        checks = GroundingValidator.check_grounding(response, sources, evidence)
        grounded = [c for c in checks if c.is_grounded]
        assert len(grounded) > 0

    def test_ungrounded_numeric_claim(self):
        response = "The engine produces 5000 kW at full load."
        evidence = "MTU 12V 2000 M93 delivers 1340 kW at 2250 RPM"
        sources = ["Knowledge Base"]
        checks = GroundingValidator.check_grounding(response, sources, evidence)
        ungrounded = [c for c in checks if not c.is_grounded]
        assert len(ungrounded) > 0

    def test_technical_claim_needs_tier_1_or_2(self):
        response = (
            "The bore x stroke is 135mm x 156mm with turbocharger efficiency of 92%."
        )
        sources = ["Perplexity Search"]  # Tier 4 — not adequate for technical claims
        checks = GroundingValidator.check_grounding(response, sources)
        # Should flag technical claims from Tier 4
        ungrounded = [c for c in checks if not c.is_grounded]
        assert len(ungrounded) > 0

    def test_technical_claim_ok_from_tier_1(self):
        response = "The bore x stroke is 135mm x 156mm."
        sources = ["Knowledge Base"]  # Tier 1
        checks = GroundingValidator.check_grounding(response, sources)
        grounded = [c for c in checks if c.is_grounded]
        assert len(grounded) > 0

    def test_grounding_instruction_output(self):
        instruction = GroundingValidator.build_grounding_instruction(
            ["SAP CPI (MS5)", "Perplexity Search", "Knowledge Base"]
        )
        assert "SOURCE GROUNDING RULES" in instruction
        assert "Tier 1" in instruction or "TIER_1" in instruction
        assert "Tier 4" in instruction or "TIER_4" in instruction


# =============================================================================
# Output Schema Validator Tests
# =============================================================================


class TestOutputSchemaValidator:
    """Tests for response schema validation."""

    def test_valid_answer_response(self):
        response = {
            "type": "answer",
            "session_id": "test-123",
            "answer": "The MTU engine delivers 1340 kW.",
            "sources": ["Knowledge Base"],
            "confidence": "HIGH",
            "timestamp": "2026-04-01T00:00:00Z",
        }
        result = OutputSchemaValidator.validate(response)
        assert result.is_valid

    def test_missing_type_field(self):
        response = {"answer": "test", "sources": []}
        result = OutputSchemaValidator.validate(response)
        assert not result.is_valid
        assert any("type" in e for e in result.errors)

    def test_missing_answer_field(self):
        response = {
            "type": "answer",
            "session_id": "test",
            "sources": [],
            "confidence": "HIGH",
            "timestamp": "2026-04-01T00:00:00Z",
        }
        result = OutputSchemaValidator.validate(response)
        assert not result.is_valid

    def test_empty_answer_text(self):
        response = {
            "type": "answer",
            "session_id": "test",
            "answer": "",
            "sources": [],
            "confidence": "HIGH",
            "timestamp": "2026-04-01T00:00:00Z",
        }
        result = OutputSchemaValidator.validate(response)
        assert not result.is_valid

    def test_invalid_confidence(self):
        response = {
            "type": "answer",
            "session_id": "test",
            "answer": "Some answer",
            "sources": ["KB"],
            "confidence": "VERY_HIGH",
            "timestamp": "2026-04-01T00:00:00Z",
        }
        result = OutputSchemaValidator.validate(response)
        assert result.is_valid  # Invalid confidence is a warning, not error
        assert len(result.warnings) > 0

    def test_valid_kyp_report(self):
        response = {
            "type": "kyp_report",
            "session_id": "test",
            "entity_name": "ST Engineering",
            "sources": ["SAP CPI"],
            "timestamp": "2026-04-01T00:00:00Z",
        }
        result = OutputSchemaValidator.validate(response)
        assert result.is_valid

    def test_valid_credit_report(self):
        response = {
            "type": "credit_report",
            "session_id": "test",
            "credit": {"limit": 100000, "utilization": 50},
            "sources": ["SAP CPI (MS5)"],
            "timestamp": "2026-04-01T00:00:00Z",
        }
        result = OutputSchemaValidator.validate(response)
        assert result.is_valid

    def test_unknown_type_passes_with_warning(self):
        response = {"type": "new_exotic_type", "data": "something"}
        result = OutputSchemaValidator.validate(response)
        assert result.is_valid
        assert len(result.warnings) > 0

    def test_ensure_type_field(self):
        response = {"answer": "test"}
        OutputSchemaValidator.ensure_type_field(response, "answer")
        assert response["type"] == "answer"

    def test_empty_sources_warning(self):
        response = {
            "type": "answer",
            "session_id": "test",
            "answer": "Some answer",
            "sources": [],
            "confidence": "HIGH",
            "timestamp": "2026-04-01T00:00:00Z",
        }
        result = OutputSchemaValidator.validate(response)
        assert result.is_valid
        assert any("sources" in w.lower() for w in result.warnings)


# =============================================================================
# Follow-Up Resolver Tests
# =============================================================================


class TestFollowUpResolver:
    """Tests for follow-up query resolution."""

    def test_tell_me_more_is_followup(self):
        assert FollowUpResolver.is_followup_query("tell me more")
        assert FollowUpResolver.is_followup_query("Tell me more about that")
        assert FollowUpResolver.is_followup_query("more details")

    def test_what_about_is_followup(self):
        assert FollowUpResolver.is_followup_query("what about offshore?")
        assert FollowUpResolver.is_followup_query("How about their financials?")

    def test_compare_is_followup(self):
        assert FollowUpResolver.is_followup_query("compare with Caterpillar")
        assert FollowUpResolver.is_followup_query("vs Cummins")

    def test_short_queries_are_followups(self):
        assert FollowUpResolver.is_followup_query("and offshore?")
        assert FollowUpResolver.is_followup_query("their fleet?")

    def test_full_new_query_is_not_followup(self):
        assert not FollowUpResolver.is_followup_query(
            "What is the credit status of Maersk in the SAP system?"
        )
        assert not FollowUpResolver.is_followup_query(
            "Run KYP due diligence on Neptune Energy"
        )

    def test_resolve_with_previous_entity(self):
        resolution = FollowUpResolver.resolve(
            current_query="tell me more",
            previous_intent="customer_intel",
            previous_entity="ST Engineering",
            previous_response_type="answer",
        )
        assert resolution.is_followup
        assert resolution.resolved_entity == "ST Engineering"
        assert resolution.resolved_intent == "customer_intel"
        assert resolution.confidence > 0.5

    def test_resolve_scope_modifier_financials(self):
        resolution = FollowUpResolver.resolve(
            current_query="and their financials?",
            previous_intent="customer_intel",
            previous_entity="Maersk",
            previous_response_type="answer",
        )
        assert resolution.is_followup
        assert resolution.resolved_entity == "Maersk"
        assert resolution.resolved_intent == "financial_analysis"

    def test_resolve_scope_modifier_products(self):
        resolution = FollowUpResolver.resolve(
            current_query="what about their products?",
            previous_intent="competitor_intel",
            previous_entity="Caterpillar",
            previous_response_type="answer",
        )
        assert resolution.is_followup
        assert resolution.resolved_intent == "product_fit"

    def test_resolve_full_report_request(self):
        resolution = FollowUpResolver.resolve(
            current_query="show me the full report",
            previous_intent="kyp_due_diligence",
            previous_entity="Neptune Energy",
            previous_response_type="kyp_report",
        )
        assert resolution.is_followup
        assert resolution.resolved_context.get("wants_full_report") is True

    def test_resolve_no_previous_context(self):
        resolution = FollowUpResolver.resolve(
            current_query="tell me more",
            previous_intent=None,
            previous_entity=None,
            previous_response_type=None,
        )
        assert not resolution.is_followup

    def test_resolve_not_followup(self):
        resolution = FollowUpResolver.resolve(
            current_query="What is the credit limit for Batam Fast Ferry?",
            previous_intent="competitor_intel",
            previous_entity="Caterpillar",
            previous_response_type="answer",
        )
        assert not resolution.is_followup


# =============================================================================
# Quality Metrics Tests
# =============================================================================


class TestQualityMetrics:
    """Tests for quality observability."""

    def test_record_scope_violation(self):
        QualityMetrics.record_scope_violation(
            "product_fit",
            [
                {
                    "section": "billing_status",
                    "matched": "aging analysis",
                    "intent": "product_fit",
                }
            ],
        )
        events = QualityMetrics.get_recent_events("scope_violation")
        assert len(events) > 0
        assert events[-1].intent == "product_fit"

    def test_record_grounding_failure(self):
        checks = [
            GroundingCheck(is_grounded=False, claim="5000 kW", issue="Not in evidence"),
            GroundingCheck(is_grounded=True, claim="1340 kW"),
        ]
        QualityMetrics.record_grounding_failure("competitor_intel", checks)
        events = QualityMetrics.get_recent_events("grounding_failure")
        assert len(events) > 0

    def test_record_schema_validation(self):
        from lead_to_cash.core.response_quality import ValidationResult

        result = ValidationResult(is_valid=False, errors=["Missing answer field"])
        QualityMetrics.record_schema_validation("answer", result)
        events = QualityMetrics.get_recent_events("schema_validation_error")
        assert len(events) > 0

    def test_bounded_event_collection(self):
        """Events should be bounded to prevent memory leak."""
        for i in range(200):
            QualityMetrics.record("test", "INFO", "test", {"i": i})
        events = QualityMetrics.get_recent_events()
        assert len(events) <= QualityMetrics._max_events


# =============================================================================
# Insufficient Evidence Builder Tests
# =============================================================================


class TestInsufficientEvidenceBuilder:
    """Tests for partial/insufficient evidence responses."""

    def test_build_partial_response(self):
        response = InsufficientEvidenceBuilder.build_partial_response(
            intent="competitor_intel",
            available_data={"Revenue": "EUR 52.6B (FY2025)", "Market Cap": "EUR 30B"},
            missing_areas=[
                "Specific engine specs for new model",
                "APAC market share data",
            ],
            sources_used=["EODHD", "Perplexity Search"],
        )
        assert "Based on available data" in response
        assert "Data not available" in response
        assert "Sources checked" in response

    def test_empty_available_data(self):
        response = InsufficientEvidenceBuilder.build_partial_response(
            intent="product_fit",
            available_data={},
            missing_areas=["No matching engine data found"],
            sources_used=["Knowledge Base"],
        )
        assert "Data not available" in response


# =============================================================================
# Golden Test Cases — Intent-to-Card Mapping
# =============================================================================


class TestIntentCardMapping:
    """
    Golden test cases: each intent should map to a specific primary card type.

    These are the canonical mappings that the system MUST follow:
    - product queries → answer (text with specs)
    - billing queries → finops_report (structured card)
    - KYP queries → kyp_report (structured card)
    - credit queries → credit_report (structured card)
    - opportunity queries → opportunity_report (structured card)
    - competitor queries → answer (narrative text)
    - market queries → answer (narrative text)
    - customer queries → answer (narrative text)
    """

    GOLDEN_CASES = [
        # (description, intent, expected_card_type, must_not_contain_sections)
        (
            "Engine specs query",
            "product_fit",
            "answer",
            ["billing_status", "aging_analysis", "sales_strategy"],
        ),
        (
            "Competitor news query",
            "competitor_intel",
            "answer",
            ["billing_status", "aging_analysis"],
        ),
        (
            "Billing items query",
            "billing_ar",
            "finops_report",
            ["product_specs", "engine_comparison"],
        ),
        (
            "KYP due diligence query",
            "kyp_due_diligence",
            "kyp_report",
            ["billing_status", "product_specs"],
        ),
        (
            "Market intel query",
            "market_intel",
            "answer",
            ["billing_status", "credit_status"],
        ),
        (
            "Customer intel query",
            "customer_intel",
            "answer",
            ["billing_status", "aging_analysis"],
        ),
    ]

    @pytest.mark.parametrize(
        "description,intent,expected_type,forbidden_sections",
        GOLDEN_CASES,
        ids=[c[0] for c in GOLDEN_CASES],
    )
    def test_intent_scope_boundaries(
        self, description, intent, expected_type, forbidden_sections
    ):
        """Verify that each intent's allowed sections exclude forbidden ones."""
        allowed = ScopeEnforcer.get_allowed_sections(intent)
        allowed_names = {s.value for s in allowed}
        for forbidden in forbidden_sections:
            assert forbidden not in allowed_names, (
                f"{description}: '{forbidden}' should be forbidden for intent '{intent}'"
            )


# =============================================================================
# Failure Taxonomy Table
# =============================================================================


FAILURE_TAXONOMY = """
| ID   | Failure Mode                      | Category      | Detection Method                | Severity |
|------|-----------------------------------|---------------|----------------------------------|----------|
| F-01 | Mixed response sections           | Scope         | ScopeEnforcer.detect_violations  | HIGH     |
| F-02 | Unsolicited recommendations       | Scope         | ScopeEnforcer (action_items)     | MEDIUM   |
| F-03 | Billing data in product response  | Scope         | ScopeEnforcer cross-intent       | HIGH     |
| F-04 | Product specs in billing response | Scope         | ScopeEnforcer cross-intent       | HIGH     |
| F-05 | Hallucinated power ratings        | Grounding     | GroundingValidator numeric       | CRITICAL |
| F-06 | Ungrounded financial figures      | Grounding     | GroundingValidator numeric       | HIGH     |
| F-07 | Tech specs from web search only   | Source Tier    | GroundingValidator tier check    | HIGH     |
| F-08 | Missing source attribution        | Attribution   | OutputSchemaValidator sources    | MEDIUM   |
| F-09 | [unknown] source label            | Attribution   | Source mapping completeness      | LOW      |
| F-10 | Follow-up loses context           | Conversation  | FollowUpResolver coverage        | HIGH     |
| F-11 | Repeated content across turns     | Conversation  | Answer dedup vs history          | MEDIUM   |
| F-12 | Wrong agent routing               | Routing       | Intent-to-agent mapping test     | HIGH     |
| F-13 | Empty answer text                 | Schema        | OutputSchemaValidator            | CRITICAL |
| F-14 | Missing type field                | Schema        | OutputSchemaValidator            | CRITICAL |
| F-15 | RBAC data leakage                 | Security      | Permission check test            | CRITICAL |
| F-16 | Finance data for sales-only user  | Security      | RBAC role filter test            | HIGH     |
"""


class TestFailureTaxonomy:
    """Verify failure taxonomy detection methods exist for each failure mode."""

    def test_scope_violation_detection(self):
        """F-01: Mixed response sections must be detectable."""
        violations = ScopeEnforcer.detect_scope_violations(
            "Revenue grew 5%. The aging analysis shows overdue items.",
            "competitor_intel",
        )
        assert len(violations) > 0

    def test_unsolicited_recommendation_detection(self):
        """F-02: Unsolicited recommendations must be detectable."""
        violations = ScopeEnforcer.detect_scope_violations(
            "Caterpillar won a contract. We recommend pursuing this deal aggressively.",
            "competitor_intel",
        )
        recommendation_violations = [
            v for v in violations if v["section"] == "recommendations"
        ]
        assert len(recommendation_violations) > 0

    def test_hallucinated_rating_detection(self):
        """F-05: Hallucinated power ratings must be flaggable."""
        checks = GroundingValidator.check_grounding(
            "The engine produces 9999 kW.",
            ["Knowledge Base"],
            "MTU 12V 2000: 1340 kW",
        )
        ungrounded = [c for c in checks if not c.is_grounded]
        assert len(ungrounded) > 0

    def test_empty_answer_detection(self):
        """F-13: Empty answers must fail validation."""
        result = OutputSchemaValidator.validate(
            {
                "type": "answer",
                "session_id": "x",
                "answer": "",
                "sources": [],
                "confidence": "LOW",
                "timestamp": "t",
            }
        )
        assert not result.is_valid

    def test_missing_type_detection(self):
        """F-14: Missing type field must fail validation."""
        result = OutputSchemaValidator.validate({"answer": "test"})
        assert not result.is_valid
