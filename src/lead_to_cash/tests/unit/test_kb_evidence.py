"""
Unit Tests for KB Evidence Layer

Tests:
1. Source type detection
2. Claim type classification
3. Verification status determination
4. Domain partitioning
5. Filtering (verified only, domain filter)
6. Audit summary
7. Hard fallback
"""

import pytest

from lead_to_cash.core.kb_evidence import (
    ClaimType,
    KBDomain,
    KBEvidenceFilter,
    SourceType,
    VerificationStatus,
    VerifiedKBEntry,
)
from lead_to_cash.core.response_quality import QualityMetrics


@pytest.fixture(autouse=True)
def _clear():
    QualityMetrics._events = []
    yield


# =============================================================================
# Source type detection
# =============================================================================


class TestSourceTypeDetection:
    def test_internal_product_data(self):
        raw = {"power_kw": 1340, "rpm": 2250, "name": "MTU 12V 2000"}
        entries = KBEvidenceFilter.filter_results([raw], require_verified=False)
        assert entries[0].source_type == SourceType.INTERNAL_DATA

    def test_news_article_url(self):
        raw = {
            "source_url": "https://maritimeexecutive.com/article/ferry-order",
            "claim": "New order",
        }
        entries = KBEvidenceFilter.filter_results([raw], require_verified=False)
        assert entries[0].source_type == SourceType.NEWS_ARTICLE

    def test_product_page_url(self):
        raw = {
            "source_url": "https://wartsila.com/product/w31-engine",
            "claim": "W31 specs",
        }
        entries = KBEvidenceFilter.filter_results([raw], require_verified=False)
        assert entries[0].source_type == SourceType.PRODUCT_PAGE

    def test_investor_report_url(self):
        raw = {
            "source_url": "https://company.com/investor/annual-report-2024",
            "claim": "Revenue",
        }
        entries = KBEvidenceFilter.filter_results([raw], require_verified=False)
        assert entries[0].source_type == SourceType.INVESTOR_REPORT

    def test_unknown_when_no_url(self):
        raw = {"claim": "Some claim without URL", "description": "text"}
        entries = KBEvidenceFilter.filter_results([raw], require_verified=False)
        assert entries[0].source_type == SourceType.UNKNOWN


# =============================================================================
# Verification status
# =============================================================================


class TestVerificationStatus:
    def test_internal_data_always_trusted(self):
        raw = {"power_kw": 1340, "rpm": 2250, "name": "MTU 12V 2000"}
        entries = KBEvidenceFilter.filter_results([raw], require_verified=False)
        assert entries[0].verification_status == VerificationStatus.INTERNAL
        assert entries[0].confidence == 1.0

    def test_verified_strong_with_entity_claim_context(self):
        """All 3 checks pass: entity in excerpt, claim terms match, same sentence."""
        raw = {
            "entity": "Wartsila",
            "claim": "Wartsila won a ferry contract in Singapore",
            "source_url": "https://seatrade-maritime.com/article/wartsila-ferry",
            "supporting_excerpt": "Wartsila announced today it has won a major ferry contract in Singapore for 3 vessels",
        }
        entries = KBEvidenceFilter.filter_results([raw], require_verified=False)
        assert entries[0].verification_status == VerificationStatus.VERIFIED_STRONG
        assert entries[0].confidence == 0.9

    def test_verified_when_entity_and_claim_match(self):
        """Entity + claim match but context check may not pass (different sentences)."""
        raw = {
            "entity": "Caterpillar",
            "claim": "Caterpillar launched new marine engine",
            "source_url": "https://maritimeexecutive.com/article/cat-engine",
            "supporting_excerpt": "Caterpillar Inc reported strong Q3 results. The company also launched a new marine engine for the offshore segment.",
        }
        entries = KBEvidenceFilter.filter_results([raw], require_verified=False)
        assert entries[0].verification_status in (
            VerificationStatus.VERIFIED_STRONG,
            VerificationStatus.VERIFIED,
        )

    def test_verified_weak_partial_support(self):
        """Only claim terms match, no entity in excerpt."""
        raw = {
            "claim": "New ferry contract announced in Singapore",
            "source_url": "https://seatrade-maritime.com/article/ferry-2024",
            "supporting_excerpt": "A new ferry contract was announced for the Singapore-Batam route with delivery in 2025",
        }
        entries = KBEvidenceFilter.filter_results([raw], require_verified=False)
        assert entries[0].verification_status in (
            VerificationStatus.VERIFIED_WEAK,
            VerificationStatus.VERIFIED,
        )

    def test_unverified_without_excerpt(self):
        raw = {
            "claim": "Cat won a contract",
            "source_url": "https://caterpillar.com/news/contract",
        }
        entries = KBEvidenceFilter.filter_results([raw], require_verified=False)
        assert entries[0].verification_status == VerificationStatus.UNVERIFIED

    def test_unverified_without_url(self):
        raw = {"claim": "Some untracked claim", "description": "no source"}
        entries = KBEvidenceFilter.filter_results([raw], require_verified=False)
        assert entries[0].verification_status == VerificationStatus.UNVERIFIED


# =============================================================================
# Domain partitioning
# =============================================================================


class TestDomainPartitioning:
    def test_product_domain(self):
        raw = {"power_kw": 1340, "name": "MTU 12V 2000"}
        entries = KBEvidenceFilter.filter_results([raw], require_verified=False)
        assert entries[0].domain == KBDomain.PRODUCT

    def test_market_domain(self):
        raw = {
            "claim": "Ferry market growing in APAC",
            "source_url": "https://maritimeexecutive.com/article/ferry",
            "supporting_excerpt": "The ferry market is growing rapidly in the APAC region",
        }
        entries = KBEvidenceFilter.filter_results([raw], require_verified=False)
        assert entries[0].domain == KBDomain.MARKET

    def test_corporate_domain(self):
        raw = {
            "claim": "Revenue increased to EUR 52B",
            "source_url": "https://company.com/investor/results",
            "supporting_excerpt": "Annual revenue increased to EUR 52 billion",
        }
        entries = KBEvidenceFilter.filter_results([raw], require_verified=False)
        assert entries[0].domain == KBDomain.CORPORATE

    def test_domain_filter_restricts_results(self):
        raw_list = [
            {"power_kw": 1340, "name": "MTU"},
            {
                "claim": "Market news",
                "source_url": "https://maritimeexecutive.com/article/news",
                "supporting_excerpt": "Market trends continue upward",
            },
        ]
        product_only = KBEvidenceFilter.filter_results(
            raw_list, domain=KBDomain.PRODUCT, require_verified=False
        )
        assert len(product_only) == 1
        assert product_only[0].domain == KBDomain.PRODUCT


# =============================================================================
# Filtering (verified only)
# =============================================================================


class TestFiltering:
    def test_verified_only_excludes_unverified(self):
        raw_list = [
            {"power_kw": 1340, "name": "MTU"},  # Internal = trusted
            {"claim": "Untracked claim"},  # No URL = unverified
        ]
        verified = KBEvidenceFilter.filter_results(raw_list, require_verified=True)
        assert len(verified) == 1
        assert verified[0].verification_status == VerificationStatus.INTERNAL

    def test_require_verified_false_returns_all(self):
        raw_list = [
            {"power_kw": 1340, "name": "MTU"},
            {"claim": "Untracked claim"},
        ]
        all_entries = KBEvidenceFilter.filter_results(raw_list, require_verified=False)
        assert len(all_entries) == 2


# =============================================================================
# Hard fallback
# =============================================================================


class TestHardFallback:
    def test_no_verified_returns_none(self):
        raw_list = [{"claim": "Untracked claim"}]
        entries = KBEvidenceFilter.filter_results(raw_list, require_verified=True)
        response = KBEvidenceFilter.build_evidence_response(entries)
        assert response is None

    def test_verified_entries_build_response(self):
        raw_list = [
            {"power_kw": 1340, "name": "MTU 12V 2000", "description": "1340 kW engine"}
        ]
        entries = KBEvidenceFilter.filter_results(raw_list, require_verified=True)
        response = KBEvidenceFilter.build_evidence_response(entries)
        assert response is not None
        assert "1340" in response


# =============================================================================
# Atomic claim splitting
# =============================================================================


class TestAtomicClaims:
    def test_single_claim_not_split(self):
        raw = {"claim": "Wartsila won a ferry contract in Singapore"}
        atoms = KBEvidenceFilter.split_atomic_claims(raw)
        assert len(atoms) == 1

    def test_multi_sentence_split(self):
        raw = {
            "claim": "Wartsila won a ferry contract. Additionally Caterpillar launched new engine."
        }
        atoms = KBEvidenceFilter.split_atomic_claims(raw)
        assert len(atoms) == 2

    def test_short_claim_not_split(self):
        raw = {"claim": "Short claim"}
        atoms = KBEvidenceFilter.split_atomic_claims(raw)
        assert len(atoms) == 1

    def test_split_preserves_metadata(self):
        raw = {
            "claim": "Company A did X. Additionally Company B did Y.",
            "source_url": "https://test.com/article",
        }
        atoms = KBEvidenceFilter.split_atomic_claims(raw)
        assert len(atoms) == 2
        for a in atoms:
            assert a["source_url"] == "https://test.com/article"


# =============================================================================
# Usage policy enforcement
# =============================================================================


class TestUsagePolicy:
    def test_default_excludes_weak(self):
        """Default response building excludes VERIFIED_WEAK."""
        entries = [
            VerifiedKBEntry(
                entity="A",
                claim="Strong claim",
                claim_type=ClaimType.MARKET,
                verification_status=VerificationStatus.VERIFIED_STRONG,
                confidence=0.9,
            ),
            VerifiedKBEntry(
                entity="B",
                claim="Weak claim",
                claim_type=ClaimType.MARKET,
                verification_status=VerificationStatus.VERIFIED_WEAK,
                confidence=0.6,
            ),
        ]
        response = KBEvidenceFilter.build_evidence_response(entries)
        assert "Strong claim" in response
        assert "Weak claim" not in response

    def test_reasoning_mode_strict_primary(self):
        """Reasoning prefers INTERNAL + VERIFIED_STRONG when available."""
        entries = [
            VerifiedKBEntry(
                entity="A",
                claim="Strong",
                claim_type=ClaimType.PRODUCT,
                verification_status=VerificationStatus.VERIFIED_STRONG,
                confidence=0.9,
            ),
            VerifiedKBEntry(
                entity="B",
                claim="Normal",
                claim_type=ClaimType.PRODUCT,
                verification_status=VerificationStatus.VERIFIED,
                confidence=0.8,
            ),
            VerifiedKBEntry(
                entity="C",
                claim="Internal",
                claim_type=ClaimType.PRODUCT,
                verification_status=VerificationStatus.INTERNAL,
                confidence=1.0,
            ),
        ]
        response = KBEvidenceFilter.build_evidence_response(entries, for_reasoning=True)
        assert "Strong" in response
        assert "Internal" in response
        assert "Normal" not in response
        assert "moderately verified" not in response

    def test_reasoning_fallback_to_verified(self):
        """When no strong evidence, reasoning falls back to VERIFIED with disclaimer."""
        entries = [
            VerifiedKBEntry(
                entity="B",
                claim="Normal verified claim",
                claim_type=ClaimType.PRODUCT,
                verification_status=VerificationStatus.VERIFIED,
                confidence=0.8,
            ),
        ]
        response = KBEvidenceFilter.build_evidence_response(entries, for_reasoning=True)
        assert response is not None
        assert "Normal verified claim" in response
        assert "moderately verified" in response

    def test_no_qualified_returns_none(self):
        """All weak entries → response is None."""
        entries = [
            VerifiedKBEntry(
                entity="A",
                claim="Weak only",
                claim_type=ClaimType.MARKET,
                verification_status=VerificationStatus.VERIFIED_WEAK,
                confidence=0.6,
            ),
        ]
        response = KBEvidenceFilter.build_evidence_response(entries)
        assert response is None


# =============================================================================
# Audit summary
# =============================================================================


class TestAuditSummary:
    def test_audit_structure(self):
        raw_list = [
            {"power_kw": 1340, "name": "MTU"},
            {
                "claim": "News",
                "source_url": "https://reuters.com/article/marine-news",
                "supporting_excerpt": "Marine industry news and developments",
            },
            {"claim": "Untracked"},
        ]
        entries = KBEvidenceFilter.filter_results(raw_list, require_verified=False)
        audit = KBEvidenceFilter.get_audit_summary(entries)
        assert "total_entries" in audit
        assert "verification_rate" in audit
        assert "by_status" in audit
        assert "by_source_type" in audit
        assert "by_domain" in audit
        assert audit["total_entries"] == 3

    def test_verification_rate_correct(self):
        raw_list = [
            {"power_kw": 1340, "name": "MTU"},  # Internal
            {"claim": "Untracked"},  # Unverified
        ]
        entries = KBEvidenceFilter.filter_results(raw_list, require_verified=False)
        audit = KBEvidenceFilter.get_audit_summary(entries)
        assert audit["verification_rate"] == 0.5  # 1 internal out of 2


# =============================================================================
# Telemetry
# =============================================================================


class TestTelemetry:
    def test_filter_logs_event(self):
        KBEvidenceFilter.filter_results([{"power_kw": 1340, "name": "MTU"}])
        events = QualityMetrics.get_recent_events("kb_evidence_filter")
        assert len(events) == 1
        assert events[0].details["raw_count"] == 1


# =============================================================================
# Serialization
# =============================================================================


class TestSerialization:
    def test_entry_to_dict(self):
        entry = VerifiedKBEntry(
            entity="MTU",
            claim="1340 kW engine",
            claim_type=ClaimType.PRODUCT,
            verification_status=VerificationStatus.INTERNAL,
            domain=KBDomain.PRODUCT,
            confidence=1.0,
        )
        d = entry.to_dict()
        assert d["entity"] == "MTU"
        assert d["verification_status"] == "internal"
        assert d["domain"] == "product"
