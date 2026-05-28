#!/usr/bin/env python3
"""
Comprehensive Chat System Stress Test
Tests the AI chat across multiple domains with deep follow-ups.
"""

import asyncio
import time
from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional

import httpx

BASE_URL = "http://localhost:8000"

# Test user credentials (from users.yaml)
TEST_USERNAME = "sewsen.goh"
TEST_PASSWORD = "FinOps2026Demo"


@dataclass
class TestResult:
    """Captures test execution details."""

    question: str
    response_time: float
    status_code: int
    response_type: str  # answer, clarification_needed, error
    answer: Optional[str] = None
    sources: list = field(default_factory=list)
    confidence: Optional[str] = None
    follow_ups: list = field(default_factory=list)
    error: Optional[str] = None
    session_id: Optional[str] = None
    answer_length: int = 0

    def summary(self) -> str:
        """One-line summary."""
        status = (
            "✅"
            if self.status_code == 200 and self.response_type == "answer"
            else "⚠️" if self.response_type == "clarification_needed" else "❌"
        )
        return f"{status} [{self.response_time:.1f}s] {self.response_type}: {self.question[:60]}..."


async def authenticate(client: httpx.AsyncClient) -> bool:
    """Authenticate and store cookies in client."""
    print("🔐 Authenticating...")
    try:
        response = await client.post(
            f"{BASE_URL}/api/v1/auth/login",
            json={"username": TEST_USERNAME, "password": TEST_PASSWORD},
        )
        if response.status_code == 200:
            print(f"✅ Authenticated as {TEST_USERNAME}")
            return True
        else:
            print(f"❌ Authentication failed: {response.text}")
            return False
    except Exception as e:
        print(f"❌ Authentication error: {e}")
        return False


async def send_chat(
    client: httpx.AsyncClient,
    message: str,
    session_id: Optional[str] = None,
    clarification_response: Optional[dict] = None,
) -> TestResult:
    """Send a chat message and capture the result."""
    start = time.time()

    payload = {"message": message}
    if session_id:
        payload["session_id"] = session_id
    if clarification_response:
        payload["clarification_response"] = clarification_response

    try:
        response = await client.post(
            f"{BASE_URL}/api/v1/chat",
            json=payload,
            timeout=120.0,  # 2 min timeout for complex queries
        )
        elapsed = time.time() - start

        if response.status_code == 200:
            data = response.json()
            answer = data.get("answer", "")
            return TestResult(
                question=message,
                response_time=elapsed,
                status_code=200,
                response_type=data.get("type", "unknown"),
                answer=answer,
                sources=data.get("sources", []),
                confidence=data.get("confidence"),
                follow_ups=data.get("follow_up_suggestions", []),
                session_id=data.get("session_id"),
                answer_length=len(answer) if answer else 0,
            )
        else:
            return TestResult(
                question=message,
                response_time=elapsed,
                status_code=response.status_code,
                response_type="error",
                error=response.text[:500],
            )
    except Exception as e:
        return TestResult(
            question=message,
            response_time=time.time() - start,
            status_code=0,
            response_type="exception",
            error=str(e),
        )


async def test_conversation_flow(
    client: httpx.AsyncClient,
    questions: list[str],
    category: str,
) -> list[TestResult]:
    """Test a multi-turn conversation with follow-ups."""
    results = []
    session_id = None

    print(f"\n{'='*80}")
    print(f"📋 TESTING: {category}")
    print(f"{'='*80}")

    for i, q in enumerate(questions, 1):
        print(f"\n[{i}/{len(questions)}] Sending: {q}")
        result = await send_chat(client, q, session_id=session_id)
        results.append(result)

        # Capture session for continuity
        if result.session_id:
            session_id = result.session_id

        # Print result summary
        print(f"  → {result.summary()}")
        if result.answer:
            # Print first 400 chars of answer
            preview = result.answer[:400].replace("\n", " ")
            print(f"  → Answer preview: {preview}...")
            print(f"  → Answer length: {result.answer_length} chars")
        if result.sources:
            print(f"  → Sources: {len(result.sources)} sources")
        if result.follow_ups:
            print(f"  → Follow-ups: {result.follow_ups[:3]}")
        if result.error:
            print(f"  → ERROR: {result.error[:200]}")

        # Small delay between questions
        await asyncio.sleep(0.5)

    return results


async def run_all_tests():
    """Run comprehensive test suite."""
    all_results = {}

    async with httpx.AsyncClient() as client:
        # Authenticate first
        if not await authenticate(client):
            print("❌ Cannot continue without authentication")
            return {}

        # ============================================================
        # TEST 1: Market Intelligence - Deep Drill
        # ============================================================
        market_questions = [
            "What are the latest developments in the marine propulsion market?",
            "Tell me more about the Asia Pacific region specifically",
            "Which companies are leading in that region?",
            "What's their market share?",
            "How does MTU compare to them?",
        ]
        all_results["Market Intelligence"] = await test_conversation_flow(
            client, market_questions, "Market Intelligence - Deep Drill"
        )

        # ============================================================
        # TEST 2: Regulations & Compliance
        # ============================================================
        regulation_questions = [
            "What regulations are affecting the offshore oil & gas sector in 2025-2026?",
            "How do these impact engine selection?",
            "What specific certifications do we need for North Sea operations?",
            "Which of our engines already have these certifications?",
        ]
        all_results["Regulations"] = await test_conversation_flow(
            client, regulation_questions, "Regulations & Compliance"
        )

        # ============================================================
        # TEST 3: IMO Emissions Standards
        # ============================================================
        emissions_questions = [
            "What's happening with IMO emissions standards and how does it impact engine selection?",
            "What's IMO Tier III specifically?",
            "Which MTU engines comply with IMO Tier III?",
            "What about Tier IV?",
            "Compare compliance costs between Tier II and Tier III engines",
        ]
        all_results["IMO Emissions"] = await test_conversation_flow(
            client, emissions_questions, "IMO Emissions Deep Dive"
        )

        # ============================================================
        # TEST 4: Ferry Electrification
        # ============================================================
        ferry_questions = [
            "What are the trends in ferry electrification and hybrid propulsion?",
            "Which ferry operators are adopting hybrid solutions?",
            "What hybrid products does MTU offer for ferries?",
            "Compare hybrid vs pure diesel for a 50m passenger ferry",
            "What's the typical ROI for hybrid conversion?",
        ]
        all_results["Ferry Electrification"] = await test_conversation_flow(
            client, ferry_questions, "Ferry Electrification Trends"
        )

        # ============================================================
        # TEST 5: Offshore Wind
        # ============================================================
        offshore_questions = [
            "What's the outlook for offshore wind vessel market?",
            "What types of vessels are needed for offshore wind?",
            "Which MTU engines are suitable for crew transfer vessels?",
            "What about service operation vessels?",
            "Who are the main shipbuilders for this segment?",
        ]
        all_results["Offshore Wind"] = await test_conversation_flow(
            client, offshore_questions, "Offshore Wind Vessel Market"
        )

        # ============================================================
        # TEST 6: Southeast Asia Market Intel
        # ============================================================
        sea_questions = [
            "Give me market intelligence for Southeast Asia marine sector",
            "What about Singapore specifically?",
            "Who are our existing customers in Singapore?",
            "What opportunities are in the pipeline?",
            "Who are our main competitors in Singapore?",
        ]
        all_results["SE Asia Market"] = await test_conversation_flow(
            client, sea_questions, "Southeast Asia Market Intelligence"
        )

        # ============================================================
        # TEST 7: Product Comparison - Series 4000 vs 2000
        # ============================================================
        product_compare_questions = [
            "Compare MTU Series 4000 vs Series 2000 for ferry applications",
            "What's the power range difference?",
            "Which is more fuel efficient?",
            "What about maintenance costs?",
            "For a 100-passenger ferry, which would you recommend?",
        ]
        all_results["Product Comparison"] = await test_conversation_flow(
            client,
            product_compare_questions,
            "Product Comparison - Series 4000 vs 2000",
        )

        # ============================================================
        # TEST 8: Tugboat Applications
        # ============================================================
        tugboat_questions = [
            "What MTU engines are best for tugboat applications?",
            "What power range do tugs typically need?",
            "Compare our tugboat offerings vs Caterpillar",
            "What's the typical maintenance schedule for tug engines?",
            "Any recent tug orders we've won?",
        ]
        all_results["Tugboat"] = await test_conversation_flow(
            client, tugboat_questions, "Tugboat Applications"
        )

        # ============================================================
        # TEST 9: Specific Engine Specs
        # ============================================================
        engine_spec_questions = [
            "What are the fuel efficiency specs for MTU 16V4000 M65L?",
            "What applications is this engine designed for?",
            "What's the power output?",
            "How does it compare to the 12V4000 variant?",
            "What's the MTBO for this engine?",
        ]
        all_results["Engine Specs"] = await test_conversation_flow(
            client, engine_spec_questions, "Specific Engine Specs - 16V4000"
        )

        # ============================================================
        # TEST 10: Offshore Supply Vessels
        # ============================================================
        osv_questions = [
            "What power range do we offer for offshore supply vessels?",
            "What's the typical OSV power requirement?",
            "Which engines are most popular for OSVs?",
            "What about dynamic positioning requirements?",
            "Compare our OSV solutions vs Wärtsilä",
        ]
        all_results["OSV"] = await test_conversation_flow(
            client, osv_questions, "Offshore Supply Vessels"
        )

        # ============================================================
        # TEST 11: Gas vs Diesel Comparison
        # ============================================================
        gas_diesel_questions = [
            "Compare our gas engines vs diesel for power generation",
            "What's the efficiency difference?",
            "Which is more cost-effective for baseload?",
            "What about emissions comparison?",
            "Any gas engine installations in Southeast Asia?",
        ]
        all_results["Gas vs Diesel"] = await test_conversation_flow(
            client, gas_diesel_questions, "Gas vs Diesel Comparison"
        )

        # ============================================================
        # TEST 12: Maintenance Intervals
        # ============================================================
        maintenance_questions = [
            "What are the maintenance intervals for Series 4000 marine engines?",
            "What's included in the 8000-hour service?",
            "What about the major overhaul interval?",
            "How does this compare to competitor maintenance schedules?",
            "What's the typical MTBO?",
        ]
        all_results["Maintenance"] = await test_conversation_flow(
            client, maintenance_questions, "Maintenance Intervals"
        )

        # ============================================================
        # TEST 13: KYP - ST Engineering (Full Flow)
        # ============================================================
        kyp_st_questions = [
            "Run KYP on ST Engineering",
            "Show me the full report",
            "What's their credit status?",
            "Any recent news about them?",
            "What products have we sold to them?",
        ]
        all_results["KYP ST Engineering"] = await test_conversation_flow(
            client, kyp_st_questions, "KYP - ST Engineering"
        )

        # ============================================================
        # TEST 14: KYP - Maersk (Full Flow)
        # ============================================================
        kyp_maersk_questions = [
            "Run KYP on Maersk",
            "What's their financial health?",
            "Any litigation or legal issues?",
            "What's our relationship history with them?",
            "What opportunities exist?",
        ]
        all_results["KYP Maersk"] = await test_conversation_flow(
            client, kyp_maersk_questions, "KYP - Maersk"
        )

        # ============================================================
        # TEST 15: Competitor - Caterpillar
        # ============================================================
        cat_questions = [
            "What's our competitive position against Caterpillar in marine?",
            "Where are they stronger than us?",
            "Where do we have advantages?",
            "What deals have we lost to them recently?",
            "What's their pricing strategy?",
        ]
        all_results["Competitor Caterpillar"] = await test_conversation_flow(
            client, cat_questions, "Competitor Analysis - Caterpillar"
        )

        # ============================================================
        # TEST 16: Competitor - Wärtsilä
        # ============================================================
        wartsila_questions = [
            "How do we compare to Wärtsilä for offshore applications?",
            "What's their market share in offshore?",
            "What products do they offer that we don't?",
            "Any recent wins or losses against them?",
            "How does their service network compare?",
        ]
        all_results["Competitor Wärtsilä"] = await test_conversation_flow(
            client, wartsila_questions, "Competitor Analysis - Wärtsilä"
        )

        # ============================================================
        # TEST 17: Competitor - MAN
        # ============================================================
        man_questions = [
            "Give me competitor analysis for MAN Energy Solutions",
            "What's their focus in the marine market?",
            "How does their medium-speed range compare to ours?",
            "What customers do we compete for?",
            "Any strategic shifts we should know about?",
        ]
        all_results["Competitor MAN"] = await test_conversation_flow(
            client, man_questions, "Competitor Analysis - MAN"
        )

        # ============================================================
        # TEST 18: Recent Wins
        # ============================================================
        wins_questions = [
            "What are recent customer wins in the ferry segment?",
            "Which shipyards were involved?",
            "What was the contract value?",
            "Who did we beat?",
            "What products were specified?",
        ]
        all_results["Recent Wins"] = await test_conversation_flow(
            client, wins_questions, "Recent Customer Wins"
        )

        # ============================================================
        # TEST 19: Cross-Domain Context Test
        # ============================================================
        cross_domain_questions = [
            "What engines do we sell to Batam Fast Ferry?",
            "How is their credit status?",
            "What's the ferry market like in Indonesia?",
            "Who are our competitors there?",
            "Any recent news about Indonesian ferry operators?",
        ]
        all_results["Cross-Domain"] = await test_conversation_flow(
            client, cross_domain_questions, "Cross-Domain Context Test"
        )

        # ============================================================
        # TEST 20: Ambiguous Query Test
        # ============================================================
        ambiguous_questions = [
            "Tell me about engines",
            "What about power?",
            "And maintenance?",
            "Compare them",
            "Which is best?",
        ]
        all_results["Ambiguous"] = await test_conversation_flow(
            client, ambiguous_questions, "Ambiguous Query Handling"
        )

        # ============================================================
        # TEST 21: Edge Cases - Empty/Short Queries
        # ============================================================
        edge_cases = [
            "hi",
            "help",
            "?",
            "MTU",
            "price",
        ]
        all_results["Edge Cases"] = await test_conversation_flow(
            client, edge_cases, "Edge Cases - Short/Vague Queries"
        )

        # ============================================================
        # TEST 22: Pronoun Resolution Test
        # ============================================================
        pronoun_questions = [
            "What engines does Maersk use?",
            "What's their credit limit?",
            "When did they last order from us?",
            "What do they typically buy?",
            "Are they a good customer?",
        ]
        all_results["Pronoun Resolution"] = await test_conversation_flow(
            client, pronoun_questions, "Pronoun Resolution Test"
        )

        # ============================================================
        # TEST 23: Numeric/Data Precision Test
        # ============================================================
        numeric_questions = [
            "What's the exact power output of MTU 20V4000?",
            "What's the fuel consumption at 85% load?",
            "What's the weight?",
            "What are the dimensions?",
            "What's the price range?",
        ]
        all_results["Numeric Precision"] = await test_conversation_flow(
            client, numeric_questions, "Numeric/Data Precision Test"
        )

        # ============================================================
        # TEST 24: FinOps Queries (for financeops user)
        # ============================================================
        finops_questions = [
            "What's the aging report for ST Engineering?",
            "Show me overdue invoices",
            "What's our DSO trend?",
            "Which customers have payment issues?",
            "What's the collection forecast for this month?",
        ]
        all_results["FinOps Queries"] = await test_conversation_flow(
            client, finops_questions, "FinOps Queries"
        )

        # ============================================================
        # TEST 25: Mixed Context Switching
        # ============================================================
        context_switch_questions = [
            "Run KYP on Batam Fast Ferry",
            "What's the weather in Singapore?",  # Should handle gracefully
            "Back to Batam - what's their credit status?",
            "Compare them to Maersk",
            "Who has better payment history?",
        ]
        all_results["Context Switching"] = await test_conversation_flow(
            client, context_switch_questions, "Context Switching Test"
        )

    return all_results


def generate_report(all_results: dict) -> str:
    """Generate a comprehensive test report."""
    report = []
    report.append("\n" + "=" * 100)
    report.append("🔬 COMPREHENSIVE CHAT SYSTEM TEST REPORT")
    report.append(f"Generated: {datetime.now().isoformat()}")
    report.append("=" * 100)

    total_tests = 0
    total_success = 0
    total_clarifications = 0
    total_errors = 0
    total_time = 0

    issues = []
    category_stats = {}

    for category, results in all_results.items():
        report.append(f"\n📂 {category}")
        report.append("-" * 60)

        cat_success = 0
        cat_clarification = 0
        cat_error = 0
        cat_time = 0

        for r in results:
            total_tests += 1
            total_time += r.response_time
            cat_time += r.response_time

            if r.response_type == "answer":
                total_success += 1
                cat_success += 1
                status = "✅"
            elif r.response_type == "clarification_needed":
                total_clarifications += 1
                cat_clarification += 1
                status = "⚠️"
                issues.append(f"CLARIFICATION: {category} - {r.question[:50]}")
            else:
                total_errors += 1
                cat_error += 1
                status = "❌"
                issues.append(
                    f"ERROR: {category} - {r.question[:50]} - {r.error[:100] if r.error else 'unknown'}"
                )

            report.append(f"  {status} [{r.response_time:.1f}s] {r.question[:70]}")

            # Flag slow responses
            if r.response_time > 30:
                issues.append(
                    f"SLOW: {category} - {r.question[:50]} took {r.response_time:.1f}s"
                )

            # Flag empty answers
            if r.response_type == "answer" and (not r.answer or len(r.answer) < 50):
                issues.append(
                    f"SHORT ANSWER: {category} - {r.question[:50]} - only {len(r.answer or '')} chars"
                )

            # Flag very long answers (might be verbose/unfocused)
            if r.response_type == "answer" and r.answer and len(r.answer) > 5000:
                issues.append(
                    f"VERY LONG ANSWER: {category} - {r.question[:50]} - {len(r.answer)} chars"
                )

            # Flag no sources when expected
            if r.response_type == "answer" and not r.sources:
                # Some questions may not need sources, but flag them
                if any(
                    kw in r.question.lower()
                    for kw in [
                        "kyp",
                        "credit",
                        "competitor",
                        "market",
                        "news",
                        "recent",
                    ]
                ):
                    issues.append(f"NO SOURCES: {category} - {r.question[:50]}")

            # Flag no follow-ups
            if r.response_type == "answer" and not r.follow_ups:
                issues.append(f"NO FOLLOW-UPS: {category} - {r.question[:50]}")

        category_stats[category] = {
            "success": cat_success,
            "clarification": cat_clarification,
            "error": cat_error,
            "time": cat_time,
            "total": len(results),
        }

    # Summary Statistics
    report.append("\n" + "=" * 100)
    report.append("📊 SUMMARY STATISTICS")
    report.append("=" * 100)
    report.append(f"Total Questions Tested: {total_tests}")
    report.append(
        f"Successful Answers:     {total_success} ({100*total_success/total_tests:.1f}%)"
    )
    report.append(
        f"Clarifications Needed:  {total_clarifications} ({100*total_clarifications/total_tests:.1f}%)"
    )
    report.append(
        f"Errors/Failures:        {total_errors} ({100*total_errors/total_tests:.1f}%)"
    )
    report.append(f"Total Time:             {total_time:.1f}s")
    report.append(f"Average Response Time:  {total_time/total_tests:.1f}s")

    # Category Performance
    report.append("\n" + "=" * 100)
    report.append("📈 CATEGORY PERFORMANCE")
    report.append("=" * 100)
    for cat, stats in category_stats.items():
        success_rate = (
            100 * stats["success"] / stats["total"] if stats["total"] > 0 else 0
        )
        avg_time = stats["time"] / stats["total"] if stats["total"] > 0 else 0
        report.append(
            f"  {cat}: {success_rate:.0f}% success, {avg_time:.1f}s avg, {stats['error']} errors"
        )

    # Issues Found
    report.append("\n" + "=" * 100)
    report.append("🐛 ISSUES FOUND")
    report.append("=" * 100)

    # Group issues by type
    error_issues = [i for i in issues if i.startswith("ERROR")]
    clarification_issues = [i for i in issues if i.startswith("CLARIFICATION")]
    slow_issues = [i for i in issues if i.startswith("SLOW")]
    short_issues = [i for i in issues if i.startswith("SHORT")]
    long_issues = [i for i in issues if i.startswith("VERY LONG")]
    source_issues = [i for i in issues if i.startswith("NO SOURCES")]
    followup_issues = [i for i in issues if i.startswith("NO FOLLOW-UPS")]

    if error_issues:
        report.append(f"\n❌ ERRORS ({len(error_issues)}):")
        for i in error_issues[:20]:  # Limit to first 20
            report.append(f"  • {i}")

    if clarification_issues:
        report.append(f"\n⚠️ CLARIFICATIONS NEEDED ({len(clarification_issues)}):")
        for i in clarification_issues[:20]:
            report.append(f"  • {i}")

    if slow_issues:
        report.append(f"\n🐢 SLOW RESPONSES ({len(slow_issues)}):")
        for i in slow_issues[:10]:
            report.append(f"  • {i}")

    if short_issues:
        report.append(f"\n📝 SHORT ANSWERS ({len(short_issues)}):")
        for i in short_issues[:10]:
            report.append(f"  • {i}")

    if long_issues:
        report.append(f"\n📜 VERY LONG ANSWERS ({len(long_issues)}):")
        for i in long_issues[:10]:
            report.append(f"  • {i}")

    if source_issues:
        report.append(f"\n📚 NO SOURCES PROVIDED ({len(source_issues)}):")
        for i in source_issues[:10]:
            report.append(f"  • {i}")

    if followup_issues:
        report.append(f"\n➡️ NO FOLLOW-UPS ({len(followup_issues)}):")
        for i in followup_issues[:10]:
            report.append(f"  • {i}")

    if not issues:
        report.append("  ✅ No issues found!")

    return "\n".join(report)


if __name__ == "__main__":
    print("Starting comprehensive chat system test...")
    print("This will take several minutes as it tests 100+ questions with follow-ups.")
    print()

    results = asyncio.run(run_all_tests())

    if results:
        report = generate_report(results)
        print(report)

        # Save report
        with open("/tmp/chat_test_report.txt", "w") as f:
            f.write(report)
        print("\n📄 Report saved to /tmp/chat_test_report.txt")
    else:
        print("❌ No results collected - tests failed to run")
