"""
Unit Tests for Response Enforcement

Tests that the enforcement layer actively modifies responses:
1. Strips out-of-scope headed sections
2. Strips inline recommendations/action items
3. Annotates ungrounded financial claims
4. Replaces ungrounded technical specs with disclaimers
5. Respects severity thresholds
6. Preserves valid content
"""

import pytest

from lead_to_cash.core.response_quality import (
    EnforcementResult,
    EnforcementSeverity,
    ResponseEnforcer,
    ResponseSection,
    ScopeEnforcer,
)


# =============================================================================
# Scope Enforcement — Headed Section Stripping
# =============================================================================


class TestScopeEnforcementSections:
    """Test stripping of markdown-headed out-of-scope sections."""

    def test_strip_recommendations_from_product_response(self):
        text = (
            "## Product Specifications\n"
            "The MTU 12V 2000 M93 delivers 1,340 kW.\n\n"
            "## Recommendations\n"
            "We recommend pursuing this opportunity aggressively.\n"
            "Contact the customer within 48 hours.\n\n"
            "## Summary\n"
            "The engine is well-suited for this application.\n"
        )
        result = ResponseEnforcer.enforce(
            text,
            "product_fit",
            ["Knowledge Base"],
            "MTU 12V 2000 M93: 1,340 kW",  # evidence grounds the kW claim
        )
        assert "Recommendations" not in result.enforced_text
        assert "pursuing this opportunity" not in result.enforced_text
        assert "Product Specifications" in result.enforced_text
        assert "1,340 kW" in result.enforced_text
        assert "Summary" in result.enforced_text
        assert result.scope_violations_removed >= 1

    def test_strip_action_items_from_competitor_response(self):
        text = (
            "## Competitive Analysis\n"
            "Caterpillar won 3 contracts in APAC.\n\n"
            "## Next Steps\n"
            "- Schedule meeting with customer\n"
            "- Prepare counter-proposal\n"
            "- Review pricing strategy\n"
        )
        result = ResponseEnforcer.enforce(
            text, "competitor_intel", ["Intelligence Database"]
        )
        assert "Next Steps" not in result.enforced_text
        assert "Schedule meeting" not in result.enforced_text
        assert "Competitive Analysis" in result.enforced_text
        assert result.scope_violations_removed >= 1

    def test_strip_rrps_implications_from_market_intel(self):
        text = (
            "## Market Trends\n"
            "Ferry market growing 12% in APAC.\n\n"
            "## Implications for RRPS\n"
            "This growth represents a significant opportunity for MTU.\n"
        )
        result = ResponseEnforcer.enforce(text, "market_intel", ["Web Search"])
        assert "Implications for RRPS" not in result.enforced_text
        assert "Market Trends" in result.enforced_text
        assert result.scope_violations_removed >= 1

    def test_strip_billing_from_product_response(self):
        text = (
            "## Engine Specifications\n"
            "Power output: 2,340 kW at 1,800 RPM.\n\n"
            "## Billing Status\n"
            "Outstanding invoices: EUR 450,000\n"
            "Aging: 30-45 days overdue\n\n"
            "## Conclusion\n"
            "Suitable for OSV applications.\n"
        )
        result = ResponseEnforcer.enforce(text, "product_fit", ["Knowledge Base"])
        assert "Billing Status" not in result.enforced_text
        assert "Outstanding invoices" not in result.enforced_text
        assert "Engine Specifications" in result.enforced_text
        assert result.scope_violations_removed >= 1

    def test_no_stripping_when_section_allowed(self):
        text = (
            "## Billing Status\n"
            "Outstanding invoices: EUR 450,000\n\n"
            "## Aging Analysis\n"
            "30-45 days: EUR 120,000\n"
        )
        result = ResponseEnforcer.enforce(text, "billing_ar", ["SAP CPI (MS5)"])
        assert "Billing Status" in result.enforced_text
        assert "Aging Analysis" in result.enforced_text
        assert result.scope_violations_removed == 0

    def test_preserve_content_without_sections(self):
        text = "The MTU 12V 2000 M93 delivers 1,340 kW at 2,250 RPM."
        result = ResponseEnforcer.enforce(
            text,
            "product_fit",
            ["Knowledge Base"],
            "MTU 12V 2000 M93: 1,340 kW at 2,250 RPM",  # evidence grounds claims
        )
        assert result.enforced_text == text
        assert not result.was_modified


# =============================================================================
# Scope Enforcement — Inline Content Stripping
# =============================================================================


class TestInlineScopeEnforcement:
    """Test stripping of inline recommendations and action items."""

    def test_strip_inline_we_recommend(self):
        text = (
            "Caterpillar won 3 contracts in APAC.\n"
            "We recommend focusing on the ferry segment.\n"
            "Their market share increased 5%.\n"
        )
        result = ResponseEnforcer.enforce(
            text, "competitor_intel", ["Intelligence Database"]
        )
        assert "We recommend" not in result.enforced_text
        assert "Caterpillar won" in result.enforced_text
        assert "market share" in result.enforced_text

    def test_strip_inline_rrps_should(self):
        text = (
            "Market growing in APAC.\n"
            "RRPS should increase investment in the region.\n"
            "Key growth areas include ferry and OSV.\n"
        )
        result = ResponseEnforcer.enforce(text, "market_intel", ["Web Search"])
        assert "RRPS should" not in result.enforced_text
        assert "Market growing" in result.enforced_text

    def test_strip_inline_next_steps_list(self):
        text = (
            "Analysis complete.\n\n"
            "**Next steps:**\n"
            "- Contact the customer\n"
            "- Prepare a proposal\n"
            "- Schedule follow-up\n\n"
            "Data sourced from internal systems.\n"
        )
        result = ResponseEnforcer.enforce(text, "product_fit", ["Knowledge Base"])
        assert "Next steps" not in result.enforced_text
        assert "Contact the customer" not in result.enforced_text
        assert "Analysis complete" in result.enforced_text

    def test_no_strip_when_recommendations_allowed(self):
        """General questions allow most sections — don't strip."""
        text = (
            "Based on the analysis:\n"
            "We recommend the MTU 4000 series for this application.\n"
        )
        # general_question allows product_specs, but recommendations are
        # EXPLICIT_REQUEST_ONLY — so they should still be stripped
        result = ResponseEnforcer.enforce(text, "general_question", ["Knowledge Base"])
        assert "We recommend" not in result.enforced_text


# =============================================================================
# Grounding Enforcement — Technical Specs
# =============================================================================


class TestGroundingEnforcementSpecs:
    """Technical specs without Tier 1-2 source must be replaced."""

    def test_ungrounded_kw_in_product_response(self):
        text = "The engine delivers 5,000 kW at full load."
        evidence = "No matching data"  # Number not in evidence
        result = ResponseEnforcer.enforce(
            text, "product_fit", ["Perplexity Search"], evidence
        )
        assert "5,000 kW" not in result.enforced_text
        assert "not verified" in result.enforced_text
        assert result.claims_replaced >= 1

    def test_grounded_kw_not_replaced(self):
        text = "The MTU delivers 1,340 kW at 2,250 RPM."
        evidence = "MTU 12V 2000 M93: 1,340 kW at 2,250 RPM"  # Exact match
        result = ResponseEnforcer.enforce(
            text, "product_fit", ["Knowledge Base"], evidence
        )
        assert "1,340 kW" in result.enforced_text
        assert result.claims_replaced == 0

    def test_ungrounded_spec_in_competitor_response(self):
        text = "The Caterpillar C32 delivers 1,200 kW."
        evidence = "Caterpillar Marine Division news"  # No kW in evidence
        result = ResponseEnforcer.enforce(
            text, "competitor_intel", ["Perplexity Search"], evidence
        )
        assert "1,200 kW" not in result.enforced_text
        assert "not verified" in result.enforced_text

    def test_spec_with_tier1_source_preserved(self):
        """Specs from KB (Tier 1) should not be touched."""
        text = "Power output: 2,340 kW."
        evidence = "MTU 12V 4000 M93: 2,340 kW"
        result = ResponseEnforcer.enforce(
            text, "product_fit", ["Knowledge Base"], evidence
        )
        assert "2,340 kW" in result.enforced_text
        assert result.claims_replaced == 0


# =============================================================================
# Grounding Enforcement — Financial Claims
# =============================================================================


class TestGroundingEnforcementFinancial:
    """Financial claims without evidence get annotated (not replaced)."""

    def test_ungrounded_financial_annotated(self):
        text = "Revenue was USD 52.6 billion in FY2024."
        evidence = "Company profile data"  # No financial figures
        result = ResponseEnforcer.enforce(
            text, "competitor_intel", ["Perplexity Search"], evidence
        )
        assert "(unverified)" in result.enforced_text
        assert "52.6" in result.enforced_text  # Claim preserved, just annotated
        assert result.claims_annotated >= 1

    def test_grounded_financial_not_annotated(self):
        text = "Revenue was EUR 52.6 billion."
        evidence = "Annual report: Revenue EUR 52.6 billion"  # Exact match
        result = ResponseEnforcer.enforce(
            text, "financial_analysis", ["EODHD"], evidence
        )
        assert "(unverified)" not in result.enforced_text
        assert result.claims_annotated == 0


# =============================================================================
# Severity Classification
# =============================================================================


class TestSeverityClassification:
    """Test that severity is classified correctly for different claim types."""

    def test_technical_spec_no_source_is_critical(self):
        from lead_to_cash.core.response_quality import GroundingCheck

        check = GroundingCheck(
            is_grounded=False,
            claim="5000 kW",
            source_tier=None,
            issue="Not in evidence",
        )
        severity = ResponseEnforcer._classify_grounding_severity(check, "product_fit")
        assert severity == EnforcementSeverity.CRITICAL

    def test_financial_no_evidence_is_medium(self):
        from lead_to_cash.core.response_quality import GroundingCheck

        check = GroundingCheck(
            is_grounded=False,
            claim="USD 500 million",
            source_tier=None,
            issue="Not in evidence",
        )
        severity = ResponseEnforcer._classify_grounding_severity(
            check, "competitor_intel"
        )
        assert severity == EnforcementSeverity.MEDIUM

    def test_general_claim_is_low(self):
        from lead_to_cash.core.response_quality import GroundingCheck

        check = GroundingCheck(
            is_grounded=False,
            claim="in 2024 the company",
            source_tier=None,
            issue="Not in evidence",
        )
        severity = ResponseEnforcer._classify_grounding_severity(check, "market_intel")
        assert severity == EnforcementSeverity.LOW


# =============================================================================
# Combined Enforcement
# =============================================================================


class TestCombinedEnforcement:
    """Test multiple enforcement actions on a single response."""

    def test_scope_and_grounding_together(self):
        text = (
            "## Product Analysis\n"
            "The engine produces 9,999 kW at maximum output.\n\n"
            "## Recommendations\n"
            "We recommend immediate procurement.\n\n"
            "## Technical Summary\n"
            "Well-suited for offshore applications.\n"
        )
        result = ResponseEnforcer.enforce(
            text, "product_fit", ["Perplexity Search"], "No matching specs"
        )
        # Recommendations section should be stripped
        assert "Recommendations" not in result.enforced_text
        assert "immediate procurement" not in result.enforced_text
        # Ungrounded spec should be replaced
        assert "9,999 kW" not in result.enforced_text
        # Valid content preserved
        assert "Product Analysis" in result.enforced_text
        assert "Technical Summary" in result.enforced_text
        assert result.was_modified

    def test_enforcement_result_summary(self):
        text = "Data shows 5,000 kW output.\n## Next Steps\n- Contact customer\n"
        result = ResponseEnforcer.enforce(
            text, "product_fit", ["Perplexity Search"], "No data"
        )
        assert result.was_modified
        summary = result.summary
        assert "removed" in summary or "replaced" in summary or "annotated" in summary


# =============================================================================
# Edge Cases
# =============================================================================


class TestEnforcementEdgeCases:
    """Edge cases for enforcement behavior."""

    def test_empty_response(self):
        result = ResponseEnforcer.enforce("", "product_fit", [])
        assert result.enforced_text == ""
        assert not result.was_modified

    def test_response_with_only_valid_content(self):
        text = "The ferry market in APAC is growing steadily."
        result = ResponseEnforcer.enforce(
            text, "market_intel", ["Intelligence Database"]
        )
        assert result.enforced_text == text
        assert not result.was_modified

    def test_whitespace_cleanup(self):
        text = "Line 1\n\n\n\n\nLine 2\n\n\n\nLine 3"
        cleaned = ResponseEnforcer.cleanup_whitespace(text)
        assert "\n\n\n" not in cleaned
        assert "Line 1" in cleaned
        assert "Line 3" in cleaned

    def test_billing_response_not_enforced_for_billing_intent(self):
        """Billing content in billing_ar response should NOT be touched."""
        text = (
            "## Billing Status\n"
            "Total outstanding: EUR 1.2M\n"
            "## Aging Analysis\n"
            "45+ days: EUR 350K\n"
        )
        # SAP data provides the evidence — claims are grounded
        evidence = "Outstanding: EUR 1.2M, Aging 45+ days: EUR 350K"
        result = ResponseEnforcer.enforce(
            text, "billing_ar", ["SAP CPI (MS5)"], evidence
        )
        assert result.enforced_text == text
        assert not result.was_modified

    def test_general_question_lenient(self):
        """General questions should be lenient — fewer enforcements."""
        text = "The market is worth USD 50 billion globally."
        result = ResponseEnforcer.enforce(
            text, "general_question", ["Perplexity Search"], "market data"
        )
        # General intent + financial claim → MEDIUM → annotate, not replace
        # But the claim may or may not match depending on evidence
        # The key test: it should NOT be completely removed
        assert "50" in result.enforced_text

    def test_enforcement_preserves_citations(self):
        text = "Revenue grew 15% [1]. Market cap is EUR 30B [2]."
        result = ResponseEnforcer.enforce(
            text, "competitor_intel", ["EODHD"], "Revenue grew 15%. Market cap EUR 30B."
        )
        # Citations should be preserved
        assert "[1]" in result.enforced_text
        assert "[2]" in result.enforced_text


# =============================================================================
# Critical Scenarios
# =============================================================================


class TestCriticalScenarios:
    """The exact scenarios that motivated enforcement."""

    def test_product_response_with_unsolicited_strategy(self):
        """
        User asked for engine specs.
        LLM added strategy section.
        Enforcement should strip the strategy.
        """
        text = (
            "## MTU 4000 Series\n"
            "The MTU 16V 4000 M63 delivers approximately 2,400 kW in continuous duty.\n\n"
            "## Sales Strategy\n"
            "Position this engine against Caterpillar 3516C.\n"
            "Emphasize total cost of ownership advantage.\n"
            "Target ferry operators in Southeast Asia.\n\n"
            "## Applications\n"
            "Suitable for ferries, OSV, and tugs.\n"
        )
        result = ResponseEnforcer.enforce(
            text,
            "product_fit",
            ["Knowledge Base"],
            "MTU 16V 4000 M63: ~2,400 kW continuous",
        )
        # Strategy stripped
        assert "Sales Strategy" not in result.enforced_text
        assert "Position this engine" not in result.enforced_text
        # Valid content preserved
        assert "MTU 4000 Series" in result.enforced_text
        assert "2,400 kW" in result.enforced_text
        assert "Applications" in result.enforced_text

    def test_competitor_response_with_hallucinated_spec(self):
        """
        LLM hallucinated a competitor engine spec.
        Enforcement should replace the ungrounded claim.
        """
        text = (
            "Caterpillar recently launched the C32E with 1,450 kW output, "
            "targeting the high-speed ferry segment."
        )
        result = ResponseEnforcer.enforce(
            text,
            "competitor_intel",
            ["Perplexity Search"],
            "Caterpillar marine division news update",
        )
        # The hallucinated spec should be replaced
        assert "1,450 kW" not in result.enforced_text
        assert "not verified" in result.enforced_text
        # The rest of the content should remain
        assert "Caterpillar" in result.enforced_text
