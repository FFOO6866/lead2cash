"""
Unit Tests for Citation Verifier

Tests:
1. Junk domain rejection
2. Trusted publisher verification
3. Out-of-range citation rejection
4. Homepage URL detection
5. Content filtering after verification
6. Verified-only content building
7. Telemetry logging
"""

import pytest

from lead_to_cash.core.citation_verifier import (
    CitationVerifier,
    CitationVerificationResult,
    VerifiedClaim,
)
from lead_to_cash.core.response_quality import QualityMetrics


@pytest.fixture(autouse=True)
def _clear():
    QualityMetrics._events = []
    yield


class TestJunkDomainRejection:
    """Citations from junk domains must be rejected."""

    def test_youtube_rejected(self):
        result = CitationVerifier.verify_output(
            "Something [1] happened.",
            ["https://www.youtube.com/watch?v=abc123"],
        )
        assert len(result.rejected_claims) == 1
        assert result.rejected_claims[0]["reason"] == "junk_domain"

    def test_reddit_rejected(self):
        result = CitationVerifier.verify_output(
            "Discussion [1] about engines.",
            ["https://reddit.com/r/maritime/comments/abc"],
        )
        assert len(result.rejected_claims) == 1

    def test_wikipedia_rejected(self):
        result = CitationVerifier.verify_output(
            "According to [1] the company was founded.",
            ["https://en.wikipedia.org/wiki/Caterpillar_Inc"],
        )
        assert len(result.rejected_claims) == 1


class TestTrustedPublisherVerification:
    """Citations from trusted publishers should be verified."""

    def test_maritime_executive_verified(self):
        result = CitationVerifier.verify_output(
            "New ferry order announced [1] in Singapore.",
            ["https://maritimeexecutive.com/article/new-ferry-order-2024"],
        )
        assert len(result.verified_claims) == 1
        assert result.verified_claims[0].publisher == "Maritime Executive"
        assert result.verified_claims[0].verification_status == "VERIFIED"

    def test_reuters_verified(self):
        result = CitationVerifier.verify_output(
            "Revenue grew 15% [1] in Q3.",
            ["https://reuters.com/business/caterpillar-q3-results-2024"],
        )
        assert len(result.verified_claims) == 1
        assert result.verified_claims[0].confidence == 0.8

    def test_unknown_publisher_lower_confidence(self):
        result = CitationVerifier.verify_output(
            "Contract signed [1] for new vessels.",
            ["https://obscure-maritime-blog.com/article/contract-2024-abc"],
        )
        assert len(result.verified_claims) == 1
        assert result.verified_claims[0].confidence == 0.5
        assert result.verified_claims[0].verification_status == "UNVERIFIED"


class TestOutOfRangeCitation:
    """Citations referencing non-existent sources must be rejected."""

    def test_ref_beyond_list(self):
        result = CitationVerifier.verify_output(
            "Claim [5] is not supported.",
            ["https://reuters.com/article1"],
        )
        assert len(result.rejected_claims) == 1
        assert result.rejected_claims[0]["reason"] == "citation_index_out_of_range"

    def test_ref_zero(self):
        result = CitationVerifier.verify_output(
            "Claim [0] invalid ref.",
            ["https://reuters.com/article1"],
        )
        assert len(result.rejected_claims) == 1


class TestHomepageDetection:
    """URLs that are homepages (no article path) should be flagged."""

    def test_homepage_url(self):
        result = CitationVerifier.verify_output(
            "According to [1] the market grew.",
            ["https://reuters.com/"],
        )
        assert len(result.unverified_claims) == 1
        assert "homepage" in result.unverified_claims[0]["reason"]

    def test_short_path_flagged(self):
        result = CitationVerifier.verify_output(
            "Data from [1] shows growth.",
            ["https://reuters.com/biz"],  # Very short path
        )
        assert len(result.unverified_claims) == 1


class TestContentFiltering:
    """Test that verified/rejected citations are properly handled in content."""

    def test_rejected_citation_removed_from_content(self):
        content = "Good data [1] and junk data [2] and more [3]."
        citations = [
            "https://reuters.com/article/real-article-about-marine",
            "https://youtube.com/watch?v=junk",
            "https://maritimeexecutive.com/article/real-maritime-news",
        ]
        verification = CitationVerifier.verify_output(content, citations)
        filtered = CitationVerifier.filter_content_by_verification(
            content, citations, verification
        )
        assert "[2]" not in filtered  # YouTube removed
        assert "[1]" in filtered  # Reuters kept
        assert "[3]" in filtered  # Maritime Exec kept

    def test_no_citations_returns_original(self):
        content = "No citations here."
        filtered = CitationVerifier.filter_content_by_verification(
            content, [], CitationVerificationResult()
        )
        assert filtered == content


class TestVerifiedOnlyContent:
    """Test building content from verified claims only."""

    def test_build_from_verified(self):
        verification = CitationVerificationResult(
            total_claims=2,
            verified_claims=[
                VerifiedClaim(
                    claim="New ferry order in Singapore",
                    article_url="https://maritimeexecutive.com/article/ferry-2024",
                    article_title="Singapore Ferry Order",
                    publisher="Maritime Executive",
                    supporting_excerpt="Singapore announced...",
                    confidence=0.8,
                    verification_status="VERIFIED",
                ),
            ],
        )
        content = CitationVerifier.build_verified_only_content(verification)
        assert content is not None
        assert "New ferry order" in content
        assert "Maritime Executive" in content

    def test_no_verified_returns_none(self):
        verification = CitationVerificationResult(total_claims=1)
        assert CitationVerifier.build_verified_only_content(verification) is None


class TestVerificationRate:
    """Test verification rate calculation."""

    def test_full_verification(self):
        result = CitationVerifier.verify_output(
            "Claim [1] and claim [2].",
            [
                "https://reuters.com/article/marine-engine-contract-2024",
                "https://maritimeexecutive.com/article/apac-ferry-market",
            ],
        )
        assert result.verification_rate == 1.0

    def test_partial_verification(self):
        result = CitationVerifier.verify_output(
            "Good [1] and junk [2].",
            [
                "https://reuters.com/article/marine-engine-contract-2024",
                "https://youtube.com/watch?v=junk",
            ],
        )
        assert result.verification_rate == 0.5

    def test_zero_verification(self):
        result = CitationVerifier.verify_output(
            "Junk [1] only.",
            ["https://youtube.com/watch?v=junk"],
        )
        assert result.verification_rate == 0.0


class TestTelemetry:
    """Test that verification events are logged."""

    def test_verification_logged(self):
        CitationVerifier.verify_output(
            "Test [1].",
            ["https://reuters.com/article/test-article-content"],
        )
        events = QualityMetrics.get_recent_events("citation_verification")
        assert len(events) == 1
        assert "verified" in events[0].details


class TestSerializability:
    """Test to_dict for logging."""

    def test_result_to_dict(self):
        result = CitationVerifier.verify_output(
            "Test [1].",
            ["https://reuters.com/article/test-article-2024"],
        )
        d = result.to_dict()
        assert "total_claims" in d
        assert "verified" in d
        assert "rejected" in d
        assert "verification_rate" in d


# =============================================================================
# Entity alignment verification
# =============================================================================


class TestEntityAlignment:
    """Test entity-in-content verification."""

    def test_entity_found_in_context(self):
        result = CitationVerifier.verify_claim_entity_alignment(
            "Caterpillar won a ferry contract",
            ["Caterpillar"],
            "Caterpillar Marine announced a new ferry contract for 3 vessels in Singapore.",
        )
        assert result["entity_found"] is True
        assert result["claim_supported"] is True
        assert result["pass"] is True

    def test_entity_not_in_context(self):
        result = CitationVerifier.verify_claim_entity_alignment(
            "Caterpillar won a ferry contract",
            ["Caterpillar"],
            "The ferry market grew 12% in the APAC region last year.",
        )
        assert result["entity_found"] is False
        assert result["pass"] is False

    def test_claim_not_supported(self):
        result = CitationVerifier.verify_claim_entity_alignment(
            "Caterpillar won a ferry contract worth EUR 50M",
            ["Caterpillar"],
            "Caterpillar reported strong quarterly earnings in Q3 2024.",
        )
        assert result["entity_found"] is True
        assert result["claim_supported"] is False
        assert result["pass"] is False


# =============================================================================
# Fact / inference separation
# =============================================================================


class TestFactInferenceSeparation:
    """Test separation of facts from inferences."""

    def test_facts_detected(self):
        content = "Caterpillar won a contract for 3 vessels. Revenue grew 15% in Q3."
        result = CitationVerifier.separate_fact_inference(content)
        assert len(result["facts"]) >= 1

    def test_inferences_detected(self):
        content = (
            "The deal was signed in Singapore. "
            "This suggests a significant opportunity for RRPS in the region."
        )
        result = CitationVerifier.separate_fact_inference(content)
        assert len(result["inferences"]) >= 1
        assert any("suggests" in s.lower() for s in result["inferences"])

    def test_mixed_content_separated(self):
        content = (
            "Wartsila won a ferry contract in Singapore. "
            "This could mean increased competition for MTU in the region. "
            "The contract is worth EUR 25M."
        )
        result = CitationVerifier.separate_fact_inference(content)
        assert len(result["facts"]) >= 1
        assert len(result["inferences"]) >= 1


# =============================================================================
# Market insight enforcement
# =============================================================================


class TestMarketInsightEnforcement:
    """Test full market insight quality enforcement."""

    def test_verified_with_entity(self):
        result = CitationVerifier.enforce_market_insight_quality(
            content="Caterpillar won a ferry contract [1] in Singapore.",
            citations=[
                "https://maritimeexecutive.com/article/caterpillar-ferry-contract-2024"
            ],
            entities=["Caterpillar"],
        )
        assert result["status"] == "verified"
        assert result["content"] is not None

    def test_no_verified_claims_fallback(self):
        result = CitationVerifier.enforce_market_insight_quality(
            content="Something happened [1].",
            citations=["https://youtube.com/watch?v=junk"],
            entities=["Caterpillar"],
        )
        assert result["status"] == "insufficient_evidence"
        assert result["fallback_message"] is not None
        assert "No strongly relevant" in result["fallback_message"]

    def test_telemetry_logged(self):
        CitationVerifier.enforce_market_insight_quality(
            content="Test [1].",
            citations=["https://reuters.com/article/test-article-marine"],
            entities=["Test"],
        )
        events = QualityMetrics.get_recent_events("market_insight_enforcement")
        assert len(events) > 0
