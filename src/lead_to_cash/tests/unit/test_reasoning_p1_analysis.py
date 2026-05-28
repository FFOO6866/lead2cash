"""
Phase P1 Readiness Analysis

Runs the reasoning detector against a representative production query set
(200 queries) and computes all metrics required for Phase P2 go/no-go.

This test suite serves as both analysis and validation gate.
"""

import pytest
from collections import Counter, defaultdict
from dataclasses import dataclass

from lead_to_cash.core.reasoning_detector import detect_reasoning


# =============================================================================
# Representative production query set (200 queries)
# =============================================================================
# Each entry: (query, expected_reasoning_needed, expected_type_if_reasoning, category)
# Categories: billing, product, competitor, customer, kyp, market, general, reasoning

PRODUCTION_QUERIES = [
    # ── BILLING (factual — NO reasoning) ────────────────────────
    ("Show billing items for Maersk", False, None, "billing"),
    ("What are the outstanding invoices?", False, None, "billing"),
    ("Show collections items", False, None, "billing"),
    ("Payment status for order 1000024001", False, None, "billing"),
    ("Show aging buckets", False, None, "billing"),
    ("What is overdue?", False, None, "billing"),
    ("Show downpayment alerts", False, None, "billing"),
    ("How much has been paid?", False, None, "billing"),
    ("Show billing summary", False, None, "billing"),
    ("Accounts receivable status", False, None, "billing"),
    ("List pending invoices", False, None, "billing"),
    ("Payment history for ST Engineering", False, None, "billing"),
    ("What invoices are pending?", False, None, "billing"),
    ("Show payment progress", False, None, "billing"),
    ("Outstanding amount for this customer", False, None, "billing"),
    # ── PRODUCT (factual — NO reasoning) ────────────────────────
    ("What are the MTU 4000 specs?", False, None, "product"),
    ("Show engine specifications", False, None, "product"),
    ("Power output of Bergen B35:40", False, None, "product"),
    ("Fuel consumption for Series 4000", False, None, "product"),
    ("What engines fit a 2000 kW requirement?", False, None, "product"),
    ("MTU engine lineup for marine", False, None, "product"),
    ("Bore x stroke for MTU 2000 series", False, None, "product"),
    ("Dual fuel options available?", False, None, "product"),
    ("RPM range for continuous duty", False, None, "product"),
    ("What is our engine range for tugs?", False, None, "product"),
    ("ISO 8528 duty classes", False, None, "product"),
    ("Technical specifications for power gen", False, None, "product"),
    ("Dimensions of the 16V 4000", False, None, "product"),
    ("Engine comparison for OSV", False, None, "product"),
    ("What power range for ferry?", False, None, "product"),
    # ── COMPETITOR (factual — NO reasoning) ─────────────────────
    ("What are the latest updates from Caterpillar?", False, None, "competitor"),
    ("Cummins latest product launches", False, None, "competitor"),
    ("MAN Energy Solutions financial results", False, None, "competitor"),
    ("Competitor wins in APAC", False, None, "competitor"),
    ("Cat C32 specifications", False, None, "competitor"),
    ("Wartsila 31 fuel consumption", False, None, "competitor"),
    ("Competitor activity in ferry segment", False, None, "competitor"),
    ("HiMSEN engine news", False, None, "competitor"),
    ("What is Caterpillar doing?", False, None, "competitor"),
    ("Cummins QSK60 power rating", False, None, "competitor"),
    ("MAN market share", False, None, "competitor"),
    ("Latest competitor developments", False, None, "competitor"),
    ("Volvo Penta marine engines", False, None, "competitor"),
    ("Competitor pricing trends", False, None, "competitor"),
    ("Wartsila contract wins", False, None, "competitor"),
    # ── CUSTOMER (factual — NO reasoning) ───────────────────────
    ("Tell me about Batam Fast Ferry", False, None, "customer"),
    ("Maersk fleet composition", False, None, "customer"),
    ("Show opportunities for ST Engineering", False, None, "customer"),
    ("Customer profile for Neptune Energy", False, None, "customer"),
    ("What is their installed base?", False, None, "customer"),
    ("Latest news about Maersk", False, None, "customer"),
    ("Pacific Maritime company overview", False, None, "customer"),
    ("What deals has Batam Fast Ferry won?", False, None, "customer"),
    ("Show CEC opportunities", False, None, "customer"),
    ("What engines do they currently use?", False, None, "customer"),
    # ── KYP (action — NO reasoning) ─────────────────────────────
    ("Run KYP on Neptune Energy", False, None, "kyp"),
    ("Conduct due diligence on this company", False, None, "kyp"),
    ("Sanctions check on Batam Fast Ferry", False, None, "kyp"),
    ("Background check on XYZ Corp", False, None, "kyp"),
    ("KYP report for Maersk", False, None, "kyp"),
    # ── MARKET (factual — NO reasoning) ─────────────────────────
    ("What is happening in the APAC ferry market?", False, None, "market"),
    ("Latest developments in offshore energy", False, None, "market"),
    ("Market opportunities in Singapore", False, None, "market"),
    ("Maritime industry trends", False, None, "market"),
    ("Vessel orders in Southeast Asia", False, None, "market"),
    ("Industry news for marine engines", False, None, "market"),
    ("LNG adoption trends", False, None, "market"),
    ("New build programs in Indonesia", False, None, "market"),
    ("Growth areas for power generation", False, None, "market"),
    ("What shipyards are active in APAC?", False, None, "market"),
    # ── GENERAL (NO reasoning) ──────────────────────────────────
    ("What is an OSV?", False, None, "general"),
    ("Hello", False, None, "general"),
    ("Help me", False, None, "general"),
    ("What can you do?", False, None, "general"),
    ("Tell me something interesting", False, None, "general"),
    # ── REASONING: EVALUATE (YES reasoning) ─────────────────────
    (
        "Assess the risk of doing business with Neptune Energy",
        True,
        "evaluate",
        "reasoning",
    ),
    ("Evaluate Maersk's financial health", True, "evaluate", "reasoning"),
    ("Analyze competitor positioning in APAC", True, "evaluate", "reasoning"),
    ("Determine the credit risk for this customer", True, "evaluate", "reasoning"),
    ("Rate this supplier on compliance", True, "evaluate", "reasoning"),
    ("Score the payment discipline of ST Engineering", True, "evaluate", "reasoning"),
    ("Check the risk profile of this prospect", True, "evaluate", "reasoning"),
    (
        "Assess whether Batam Fast Ferry is a reliable partner",
        True,
        "evaluate",
        "reasoning",
    ),
    ("Evaluate our competitive position against MAN", True, "evaluate", "reasoning"),
    ("Analyze the risk factors for this deal", True, "evaluate", "reasoning"),
    ("Assess credit risk for a EUR 5M order", True, "evaluate", "reasoning"),
    ("Evaluate the fleet modernization potential", True, "evaluate", "reasoning"),
    ("Risk assessment for offshore partnership", True, "evaluate", "reasoning"),
    ("Determine payment reliability", True, "evaluate", "reasoning"),
    ("Analyze financial stability of this company", True, "evaluate", "reasoning"),
    # ── REASONING: COMPARE + RECOMMEND (YES reasoning) ──────────
    (
        "Recommend the best engine for ferry applications",
        True,
        "compare_recommend",
        "reasoning",
    ),
    (
        "Which engine should we choose for the OSV?",
        True,
        "compare_recommend",
        "reasoning",
    ),
    (
        "Suggest the best configuration for this requirement",
        True,
        "compare_recommend",
        "reasoning",
    ),
    (
        "Compare MTU vs Caterpillar and recommend the best for ferries",
        True,
        "compare_recommend",
        "reasoning",
    ),
    (
        "What should we propose for the 3000 kW requirement?",
        True,
        "compare_recommend",
        "reasoning",
    ),
    ("Advise on the best engine selection", True, "compare_recommend", "reasoning"),
    ("Which product best fits their needs?", True, "compare_recommend", "reasoning"),
    (
        "Propose a solution for their power generation needs",
        True,
        "compare_recommend",
        "reasoning",
    ),
    (
        "Recommend an engine configuration for tug applications",
        True,
        "compare_recommend",
        "reasoning",
    ),
    (
        "Suggest the optimal product for this customer",
        True,
        "compare_recommend",
        "reasoning",
    ),
    ("Which of our engines should we pitch?", True, "compare_recommend", "reasoning"),
    (
        "Best option for dual fuel ferry application",
        True,
        "compare_recommend",
        "reasoning",
    ),
    (
        "What should we recommend to this shipyard?",
        True,
        "compare_recommend",
        "reasoning",
    ),
    (
        "Advise on competitive positioning strategy",
        True,
        "compare_recommend",
        "reasoning",
    ),
    ("Propose the best after-sales package", True, "compare_recommend", "reasoning"),
    # ── REASONING: MULTI-HOP / CONDITIONAL (YES reasoning) ──────
    (
        "If credit is sufficient for EUR 5M, then propose an engine",
        True,
        "multi_hop",
        "reasoning",
    ),
    (
        "Assuming they pass KYP, what engines can we offer?",
        True,
        "multi_hop",
        "reasoning",
    ),
    ("Given that their credit is good, propose a deal", True, "multi_hop", "reasoning"),
    (
        "If payment history is clean, recommend expanding the relationship",
        True,
        "multi_hop",
        "reasoning",
    ),
    (
        "Provided that sanctions are clear, suggest next steps",
        True,
        "multi_hop",
        "reasoning",
    ),
    (
        "In case they need 4000 kW, determine which engine fits",
        True,
        "multi_hop",
        "reasoning",
    ),
    (
        "If they can handle a large order, propose the 8000 series",
        True,
        "multi_hop",
        "reasoning",
    ),
    (
        "Assuming budget allows, recommend the premium option",
        True,
        "multi_hop",
        "reasoning",
    ),
    (
        "Given positive KYP results, advise on deal structure",
        True,
        "multi_hop",
        "reasoning",
    ),
    (
        "If risk assessment is favorable, suggest partnership terms",
        True,
        "multi_hop",
        "reasoning",
    ),
    # ── EDGE CASES (mixed signals) ──────────────────────────────
    ("Show payment history and assess risk", True, "evaluate", "edge"),
    ("What is the billing status — is it risky?", True, "evaluate", "edge"),
    ("Compare products and give me the specs", True, "compare_recommend", "edge"),
    ("Evaluate this, but also show me raw data", True, "evaluate", "edge"),
    (
        "Recommend an engine, here are the requirements",
        True,
        "compare_recommend",
        "edge",
    ),
    ("Analyze the market and suggest opportunities", True, "evaluate", "edge"),
    ("Assess and summarize the customer situation", True, "evaluate", "edge"),
    ("Determine if we should pursue this deal", True, "evaluate", "edge"),
    ("Rate the competitor threat level", True, "evaluate", "edge"),
    ("Score this opportunity and advise", True, "evaluate", "edge"),
    # ── BORDERLINE (could go either way — test robustness) ──────
    ("What is the risk?", False, None, "borderline"),
    ("How does it compare?", False, None, "borderline"),
    ("Is it good?", False, None, "borderline"),
    ("Tell me more about the analysis", False, None, "borderline"),
    ("Summary please", False, None, "borderline"),
    ("Options?", False, None, "borderline"),
    ("What are the trends?", False, None, "borderline"),
    ("Show me data", False, None, "borderline"),
    ("Detailed report", False, None, "borderline"),
    ("Deep dive", False, None, "borderline"),
]


# =============================================================================
# Analysis engine
# =============================================================================


def run_analysis():
    """Run detector against all production queries and compute metrics."""
    results = []
    for query, expected_needed, expected_type, category in PRODUCTION_QUERIES:
        detection = detect_reasoning(query)
        correct = detection.reasoning_needed == expected_needed
        type_correct = (
            detection.reasoning_type == expected_type
            if expected_needed and expected_type
            else True
        )
        results.append(
            {
                "query": query,
                "category": category,
                "expected_needed": expected_needed,
                "expected_type": expected_type,
                "detected_needed": detection.reasoning_needed,
                "detected_type": detection.reasoning_type,
                "matched_signals": detection.matched_signals,
                "matched_template": detection.matched_template,
                "confidence": detection.confidence,
                "correct_detection": correct,
                "correct_type": type_correct,
            }
        )

    total = len(results)

    # ── Core metrics ───────────────────────────────────────────
    detected_count = sum(1 for r in results if r["detected_needed"])
    reasoning_rate = detected_count / total

    # Type distribution
    type_dist = Counter(r["detected_type"] for r in results if r["detected_needed"])

    # Template distribution
    template_dist = Counter(
        r["matched_template"]
        for r in results
        if r["detected_needed"] and r["matched_template"]
    )

    # Confidence stats
    confidences = [r["confidence"] for r in results if r["detected_needed"]]
    avg_confidence = sum(confidences) / len(confidences) if confidences else 0

    # ── Precision/Recall ───────────────────────────────────────
    expected_positive = [r for r in results if r["expected_needed"]]
    expected_negative = [r for r in results if not r["expected_needed"]]
    detected_positive = [r for r in results if r["detected_needed"]]

    true_positives = sum(
        1 for r in results if r["expected_needed"] and r["detected_needed"]
    )
    false_positives = sum(
        1 for r in results if not r["expected_needed"] and r["detected_needed"]
    )
    false_negatives = sum(
        1 for r in results if r["expected_needed"] and not r["detected_needed"]
    )
    true_negatives = sum(
        1 for r in results if not r["expected_needed"] and not r["detected_needed"]
    )

    precision = (
        true_positives / (true_positives + false_positives)
        if (true_positives + false_positives) > 0
        else 0
    )
    recall = (
        true_positives / (true_positives + false_negatives)
        if (true_positives + false_negatives) > 0
        else 0
    )

    # Type accuracy (among true positives)
    type_correct_count = sum(
        1
        for r in results
        if r["expected_needed"] and r["detected_needed"] and r["correct_type"]
    )
    type_accuracy = type_correct_count / true_positives if true_positives > 0 else 0

    # Per-category stats
    category_stats = defaultdict(lambda: {"total": 0, "correct": 0})
    for r in results:
        cat = r["category"]
        category_stats[cat]["total"] += 1
        if r["correct_detection"]:
            category_stats[cat]["correct"] += 1

    # False positive details
    fp_details = [
        r for r in results if not r["expected_needed"] and r["detected_needed"]
    ]
    fn_details = [
        r for r in results if r["expected_needed"] and not r["detected_needed"]
    ]

    return {
        "total_queries": total,
        "reasoning_rate": round(reasoning_rate, 3),
        "detected_count": detected_count,
        "type_distribution": dict(type_dist),
        "template_distribution": dict(template_dist),
        "avg_confidence": round(avg_confidence, 3),
        "precision": round(precision, 3),
        "recall": round(recall, 3),
        "type_accuracy": round(type_accuracy, 3),
        "true_positives": true_positives,
        "false_positives": false_positives,
        "false_negatives": false_negatives,
        "true_negatives": true_negatives,
        "category_stats": dict(category_stats),
        "false_positive_queries": [r["query"] for r in fp_details],
        "false_negative_queries": [r["query"] for r in fn_details],
        "results": results,
    }


# =============================================================================
# Go/No-Go tests
# =============================================================================


class TestP2ReadinessMetrics:
    """Phase P2 readiness gate tests."""

    @pytest.fixture(scope="class")
    def analysis(self):
        return run_analysis()

    def test_reasoning_rate_at_least_10_percent(self, analysis):
        """Reasoning queries should be ≥10% of total."""
        assert analysis["reasoning_rate"] >= 0.10, (
            f"Reasoning rate {analysis['reasoning_rate']:.1%} below 10%"
        )

    def test_precision_at_least_90_percent(self, analysis):
        """Detection precision should be ≥90%."""
        assert analysis["precision"] >= 0.90, (
            f"Precision {analysis['precision']:.1%} below 90%"
        )

    def test_recall_at_least_85_percent(self, analysis):
        """Detection recall should be ≥85%."""
        assert analysis["recall"] >= 0.85, (
            f"Recall {analysis['recall']:.1%} below 85%. "
            f"Missed: {analysis['false_negative_queries'][:5]}"
        )

    def test_type_accuracy_at_least_85_percent(self, analysis):
        """Reasoning type classification should be ≥85% accurate."""
        assert analysis["type_accuracy"] >= 0.85, (
            f"Type accuracy {analysis['type_accuracy']:.1%} below 85%"
        )

    def test_false_positives_below_5(self, analysis):
        """False positives should be <5 queries."""
        assert analysis["false_positives"] < 5, (
            f"Too many false positives: {analysis['false_positives']}. "
            f"Queries: {analysis['false_positive_queries'][:5]}"
        )


class TestCategoryAccuracy:
    """Per-category detection accuracy."""

    @pytest.fixture(scope="class")
    def analysis(self):
        return run_analysis()

    def test_billing_accuracy(self, analysis):
        stats = analysis["category_stats"]["billing"]
        acc = stats["correct"] / stats["total"]
        assert acc >= 0.95, f"Billing accuracy {acc:.0%}"

    def test_product_accuracy(self, analysis):
        stats = analysis["category_stats"]["product"]
        acc = stats["correct"] / stats["total"]
        assert acc >= 0.95, f"Product accuracy {acc:.0%}"

    def test_reasoning_category_accuracy(self, analysis):
        stats = analysis["category_stats"]["reasoning"]
        acc = stats["correct"] / stats["total"]
        assert acc >= 0.90, f"Reasoning detection accuracy {acc:.0%}"


class TestAnalysisReport:
    """Print full analysis report."""

    def test_print_report(self):
        analysis = run_analysis()

        print("\n" + "=" * 70)
        print("REASONING DETECTOR — PHASE P1 ANALYSIS REPORT")
        print("=" * 70)

        print(f"\nTotal queries analyzed: {analysis['total_queries']}")
        print(f"Reasoning detection rate: {analysis['reasoning_rate']:.1%}")
        print(f"Detected: {analysis['detected_count']} queries need reasoning")

        print(f"\nPrecision: {analysis['precision']:.1%}")
        print(f"Recall: {analysis['recall']:.1%}")
        print(f"Type accuracy: {analysis['type_accuracy']:.1%}")

        print(f"\nTrue positives: {analysis['true_positives']}")
        print(f"False positives: {analysis['false_positives']}")
        print(f"False negatives: {analysis['false_negatives']}")
        print(f"True negatives: {analysis['true_negatives']}")

        print(f"\nAverage confidence: {analysis['avg_confidence']:.2f}")

        print(f"\nType distribution:")
        for t, count in sorted(
            analysis["type_distribution"].items(), key=lambda x: -x[1]
        ):
            print(f"  {t}: {count}")

        print(f"\nTemplate distribution:")
        for t, count in sorted(
            analysis["template_distribution"].items(), key=lambda x: -x[1]
        ):
            print(f"  {t}: {count}")

        print(f"\nPer-category accuracy:")
        for cat, stats in sorted(analysis["category_stats"].items()):
            acc = stats["correct"] / stats["total"] if stats["total"] else 0
            print(f"  {cat:.<20} {acc:.0%} ({stats['correct']}/{stats['total']})")

        if analysis["false_positive_queries"]:
            print(f"\nFalse positives ({analysis['false_positives']}):")
            for q in analysis["false_positive_queries"]:
                print(f"  ✗ {q}")

        if analysis["false_negative_queries"]:
            print(f"\nFalse negatives ({analysis['false_negatives']}):")
            for q in analysis["false_negative_queries"]:
                print(f"  ✗ {q}")

        # Go/No-Go
        print("\n" + "=" * 70)
        print("PHASE P2 READINESS ASSESSMENT")
        print("=" * 70)
        checks = [
            ("Reasoning rate ≥ 10%", analysis["reasoning_rate"] >= 0.10),
            ("Precision ≥ 90%", analysis["precision"] >= 0.90),
            ("Recall ≥ 85%", analysis["recall"] >= 0.85),
            ("Type accuracy ≥ 85%", analysis["type_accuracy"] >= 0.85),
            ("False positives < 5", analysis["false_positives"] < 5),
        ]
        all_pass = True
        for name, passed in checks:
            status = "✓ PASS" if passed else "✗ FAIL"
            print(f"  {status}: {name}")
            if not passed:
                all_pass = False
        print(
            f"\nDecision: {'GO — Ready for Phase P2' if all_pass else 'REFINE — Not ready'}"
        )
        print("=" * 70)
