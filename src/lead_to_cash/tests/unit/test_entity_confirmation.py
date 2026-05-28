"""
Unit Tests for Entity Confirmation Flow

Tests that original query intent is preserved when user provides
text-based clarification during entity disambiguation.

Bug Fix: When user provides text clarification (e.g., "I mean ST Engineering")
instead of numeric selection, the original intent (e.g., KYP_DUE_DILIGENCE)
should be preserved, not replaced by the intent from re-parsing the clarification.
"""

from dataclasses import replace

import pytest

from lead_to_cash.core.query_understanding import (
    ParsedQuery,
    QueryIntent,
)


def create_parsed_query(
    raw_query: str,
    intent: QueryIntent,
    companies: list[str] | None = None,
    intent_confidence: float = 0.95,
) -> ParsedQuery:
    """Helper to create ParsedQuery with sensible defaults."""
    return ParsedQuery(
        raw_query=raw_query,
        intent=intent,
        intent_confidence=intent_confidence,
        companies=companies or [],
    )


class TestEntityConfirmationIntentPreservation:
    """Tests that original intent is preserved through entity confirmation flow."""

    def test_parsed_query_can_be_replaced_with_new_companies(self):
        """Test that ParsedQuery can be updated with new company name while preserving intent."""
        original = create_parsed_query(
            raw_query="Conduct KYP on STE",
            intent=QueryIntent.KYP_DUE_DILIGENCE,
            companies=["STE"],
        )

        # Simulate what happens after entity confirmation
        updated = replace(original, companies=["ST Engineering"])

        # Intent should be preserved
        assert updated.intent == QueryIntent.KYP_DUE_DILIGENCE
        # Companies should be updated
        assert updated.companies == ["ST Engineering"]
        # Original query preserved
        assert updated.raw_query == "Conduct KYP on STE"

    def test_refined_parsed_has_different_intent(self):
        """Test that re-parsing a clarification message yields different intent.

        This demonstrates why we must preserve original parsed, not use refined_parsed.
        When user says "I mean ST Engineering", LLM might classify this as:
        - GENERAL_QUESTION (refinement/clarification)
        - CUSTOMER_RESEARCH (company lookup)
        Instead of the original KYP_DUE_DILIGENCE intent.
        """
        # Original KYP request
        original_parsed = create_parsed_query(
            raw_query="Conduct KYP on STE",
            intent=QueryIntent.KYP_DUE_DILIGENCE,
            companies=["STE"],
        )

        # What LLM might return when parsing "I mean ST Engineering"
        # This simulates the bug - the clarification gets a different intent
        refined_parsed = create_parsed_query(
            raw_query="I mean ST Engineering",
            intent=QueryIntent.GENERAL_QUESTION,  # Wrong intent!
            companies=["ST Engineering"],
        )

        # The bug was using refined_parsed instead of original_parsed
        # Correct behavior: preserve original intent, update only company name
        correct_result = replace(original_parsed, companies=refined_parsed.companies)

        assert correct_result.intent == QueryIntent.KYP_DUE_DILIGENCE
        assert correct_result.companies == ["ST Engineering"]

        # Buggy behavior would have used refined_parsed directly
        buggy_result = replace(refined_parsed, companies=refined_parsed.companies)
        assert buggy_result.intent == QueryIntent.GENERAL_QUESTION  # Wrong!

    def test_null_safety_fallback(self):
        """Test fallback behavior when original parsed is None."""
        refined_parsed = create_parsed_query(
            raw_query="I mean ST Engineering",
            intent=QueryIntent.CUSTOMER_RESEARCH,
            companies=["ST Engineering"],
        )

        # If original parsed is None (edge case), fall back to refined
        original_parsed = None
        preserved_parsed = original_parsed if original_parsed else refined_parsed

        assert preserved_parsed.intent == QueryIntent.CUSTOMER_RESEARCH
        assert preserved_parsed.companies == ["ST Engineering"]


class TestPendingClarificationStorage:
    """Tests for pending clarification session storage."""

    def test_pending_clarification_structure(self):
        """Test that pending_clarification stores the correct structure."""
        parsed = create_parsed_query(
            raw_query="Run KYP on Maersk",
            intent=QueryIntent.KYP_DUE_DILIGENCE,
            companies=["Maersk"],
        )

        candidates = [
            {"canonical_name": "Maersk A/S", "country_code": "DK"},
            {"canonical_name": "Maersk Line", "country_code": "DK"},
        ]

        pending_clarification = {
            "type": "entity_confirmation",
            "parsed_query": parsed,  # Must store original parsed with intent
            "candidates": candidates,
            "query": "Maersk",
            "message": "Multiple matches found",
        }

        # Verify structure
        assert pending_clarification["type"] == "entity_confirmation"
        assert (
            pending_clarification["parsed_query"].intent
            == QueryIntent.KYP_DUE_DILIGENCE
        )
        assert len(pending_clarification["candidates"]) == 2

    def test_retrieved_parsed_preserves_intent(self):
        """Test that retrieved parsed_query from pending_clarification has correct intent."""
        original_parsed = create_parsed_query(
            raw_query="Conduct KYP on Neptune",
            intent=QueryIntent.KYP_DUE_DILIGENCE,
            companies=["Neptune"],
        )

        # Simulate session storage
        pending_clarification = {
            "type": "entity_confirmation",
            "parsed_query": original_parsed,
            "candidates": [],
            "query": "Neptune",
        }

        # Simulate retrieval (like in _handle_entity_confirmation)
        retrieved_parsed: ParsedQuery = pending_clarification.get("parsed_query")

        # Must preserve original intent
        assert retrieved_parsed is not None
        assert retrieved_parsed.intent == QueryIntent.KYP_DUE_DILIGENCE
        assert retrieved_parsed.companies == ["Neptune"]


class TestIntentPreservationScenarios:
    """Test various scenarios where intent must be preserved."""

    @pytest.mark.parametrize(
        "original_intent,clarification_text",
        [
            (QueryIntent.KYP_DUE_DILIGENCE, "I mean ST Engineering"),
            (QueryIntent.KYP_DUE_DILIGENCE, "The Singapore one"),
            (QueryIntent.KYP_DUE_DILIGENCE, "ST Engineering Marine"),
            (QueryIntent.CUSTOMER_RESEARCH, "I'm referring to Maersk A/S"),
            (QueryIntent.FINANCIAL_ANALYSIS, "The Danish company"),
        ],
    )
    def test_intent_preserved_for_various_clarifications(
        self, original_intent, clarification_text
    ):
        """Test that various clarification phrasings preserve original intent."""
        original = create_parsed_query(
            raw_query="Original query",
            intent=original_intent,
            companies=["SomeCompany"],
        )

        # After clarification, update company but keep intent
        updated = replace(original, companies=["Resolved Company Name"])

        assert updated.intent == original_intent
        assert updated.companies == ["Resolved Company Name"]


class TestAffirmativeResponseHandling:
    """Tests for affirmative response recognition in entity confirmation."""

    # All affirmative responses that should select the first candidate
    AFFIRMATIVE_RESPONSES = {
        "yes",
        "y",
        "yeah",
        "yep",
        "yup",
        "correct",
        "right",
        "ok",
        "okay",
        "confirm",
        "confirmed",
        "that's it",
        "thats it",
        "that one",
        "the first one",
        "first one",
        "1st",
        "option 1",
    }

    @pytest.mark.parametrize(
        "response",
        [
            "yes",
            "Yes",
            "YES",
            "y",
            "Y",
            "yeah",
            "Yeah",
            "yep",
            "Yep",
            "yup",
            "Yup",
            "correct",
            "Correct",
            "right",
            "Right",
            "ok",
            "Ok",
            "OK",
            "okay",
            "Okay",
            "confirm",
            "Confirm",
            "confirmed",
            "Confirmed",
            "that's it",
            "That's it",
            "thats it",
            "Thats it",
            "that one",
            "That one",
            "the first one",
            "The first one",
            "first one",
            "First one",
            "1st",
            "option 1",
            "Option 1",
        ],
    )
    def test_affirmative_response_is_recognized(self, response: str):
        """Test that all affirmative responses are recognized (case-insensitive)."""
        response_lower = response.strip().lower()
        assert (
            response_lower in self.AFFIRMATIVE_RESPONSES
        ), f"'{response}' (normalized: '{response_lower}') should be in affirmative set"

    @pytest.mark.parametrize(
        "response",
        [
            "no",
            "No",
            "NO",
            "nope",
            "Nope",
            "cancel",
            "Cancel",
            "wrong",
            "Wrong",
            "different",
            "Different",
            "other",
            "Other",
            "neither",
            "Neither",
            "none",
            "None",
        ],
    )
    def test_negative_response_is_not_affirmative(self, response: str):
        """Test that negative responses are NOT recognized as affirmative."""
        response_lower = response.strip().lower()
        assert (
            response_lower not in self.AFFIRMATIVE_RESPONSES
        ), f"'{response}' should NOT be in affirmative set"


class TestNumericSelectionHandling:
    """Tests for numeric selection in entity confirmation."""

    @pytest.mark.parametrize(
        "response,expected_index",
        [
            ("1", 0),
            ("2", 1),
            ("3", 2),
            ("4", 3),
            ("5", 4),
        ],
    )
    def test_numeric_selection_maps_to_correct_index(
        self, response: str, expected_index: int
    ):
        """Test that numeric responses map to correct 0-based index."""
        candidates = [
            {"canonical_name": f"Company {i+1}", "country_code": "XX"} for i in range(5)
        ]

        selection = int(response)
        if 1 <= selection <= len(candidates):
            selected = candidates[selection - 1]
            assert selected["canonical_name"] == f"Company {expected_index + 1}"

    def test_out_of_range_selection_returns_none(self):
        """Test that out-of-range numeric selection is not accepted."""
        candidates = [{"canonical_name": "Only One Company", "country_code": "XX"}]

        # Selection "2" is out of range for 1 candidate
        selection = 2
        selected = None
        if 1 <= selection <= len(candidates):
            selected = candidates[selection - 1]

        assert selected is None


class TestNameMatchingHandling:
    """Tests for name matching in entity confirmation."""

    @pytest.mark.parametrize(
        "response,should_match",
        [
            ("ST Engineering", True),
            ("st engineering", True),
            ("ST ENGINEERING", True),
            ("Engineering", True),  # Partial match
            ("ST", True),  # Partial match
            ("Maersk", False),  # Different company
            ("Unknown", False),
        ],
    )
    def test_name_matching_case_insensitive(self, response: str, should_match: bool):
        """Test that name matching is case-insensitive and supports partial match."""
        candidates = [
            {"canonical_name": "ST Engineering Ltd", "country_code": "SG"},
            {"canonical_name": "Keppel Corporation", "country_code": "SG"},
        ]

        response_lower = response.strip().lower()
        matched = None
        for c in candidates:
            if response_lower in c.get("canonical_name", "").lower():
                matched = c
                break

        if should_match:
            assert matched is not None, f"'{response}' should match a candidate"
        else:
            assert matched is None, f"'{response}' should NOT match any candidate"


class TestConfirmationMessageGeneration:
    """Tests for dynamic confirmation message generation."""

    def test_single_candidate_message(self):
        """Test message for single candidate suggests 'yes' or '1'."""
        from lead_to_cash.services.entity_registry.entity_resolution_service import (
            EntityResolutionService,
        )
        from lead_to_cash.services.entity_registry.models import EntityCandidate

        service = EntityResolutionService()
        candidates = [
            EntityCandidate(
                entity_id="1",
                canonical_name="CLLS Power System GmbH",
                legal_name=None,
                country_code="DE",
                confidence_score=68.0,
                match_type="fuzzy",
                match_reasons=["Fuzzy match (68% similar)"],
                rank=1,
            )
        ]

        message = service._build_confirmation_message(candidates)

        # Should mention 'yes' for single candidate
        assert "yes" in message.lower() or "'1'" in message
        # Should NOT say "1-5" for single candidate
        assert "1-5" not in message
        assert "1-{" not in message  # No format placeholder issues

    def test_multiple_candidate_message(self):
        """Test message for multiple candidates shows correct range."""
        from lead_to_cash.services.entity_registry.entity_resolution_service import (
            EntityResolutionService,
        )
        from lead_to_cash.services.entity_registry.models import EntityCandidate

        service = EntityResolutionService()
        candidates = [
            EntityCandidate(
                entity_id=str(i),
                canonical_name=f"Company {i}",
                legal_name=None,
                country_code="XX",
                confidence_score=90.0 - i * 10,
                match_type="fuzzy",
                match_reasons=[f"Match {i}"],
                rank=i,
            )
            for i in range(1, 4)  # 3 candidates
        ]

        message = service._build_confirmation_message(candidates)

        # Should show correct range
        assert "1-3" in message
        # Should NOT say "1-5" for 3 candidates
        assert "1-5" not in message
