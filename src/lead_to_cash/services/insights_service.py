"""
RRPS Industry Insights Service

Provides industry news and competitor intelligence using Perplexity API
for web research on Marine, Offshore Oil & Gas, and Marine Transportation sectors.

Industry News Focus:
- Customer announcements (shipowners/operators fleet plans, vessel orders)
- Shipyard contracts (newbuilds, repairs, conversions)
- Project sanctioning (offshore FIDs, infrastructure projects)
- Regulatory initiatives (MPA, IMO rules driving upgrades)
- Industry tenders (RFPs, fleet renewal programs)

All focused on identifying potential RRPS customers and engine sales opportunities.
"""

import asyncio
import json
import logging
import os
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Optional

from lead_to_cash.utils import AsyncHTTPClientMixin

logger = logging.getLogger(__name__)


@dataclass
class InsightResult:
    """Result from an insight query."""

    content: str
    sources: list[str] = field(default_factory=list)
    category: str = ""
    timestamp: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )

    def to_dict(self) -> dict[str, Any]:
        return {
            "content": self.content,
            "sources": self.sources,
            "category": self.category,
            "timestamp": self.timestamp,
        }


class InsightsService(AsyncHTTPClientMixin):
    """Service for retrieving industry insights using Perplexity API.

    Inherits from AsyncHTTPClientMixin for HTTP client lifecycle management.
    Use as async context manager for automatic cleanup:

        async with InsightsService() as service:
            results = await service.get_industry_news()
    """

    INDUSTRIES = ["Marine", "Offshore Oil & Gas", "Marine Transportation"]
    COMPETITORS = ["Caterpillar", "Cummins", "MAN Energy Solutions"]

    # Priority regions for RRPS marine engine sales
    PRIORITY_REGIONS = [
        "Singapore",
        "Indonesia",
        "Malaysia",
        "Thailand",
        "Vietnam",
        "Philippines",
        "Australia",
        "China",
        "Korea",
        "Japan",
        "India",
    ]

    # Priority sectors
    PRIORITY_SECTORS = [
        "Marine transportation (ferries, ports, harbour craft, tugs, shipping)",
        "Offshore oil & gas (OSVs, FPSOs, offshore construction vessels)",
        "Marine & offshore engineering (shipyards, MRO, retrofits)",
    ]

    # Industry-specific news sources - Singapore & APAC focus
    INDUSTRY_SOURCES = [
        # Singapore Regulatory
        "Maritime & Port Authority of Singapore (MPA)",
        "Singapore Maritime Foundation (SMF)",
        "Association of Singapore Marine & Offshore Energy Industries (ASMI)",
        "Singapore Shipping Association (SSA)",
        # Trade Media
        "The Maritime Executive",
        "Seatrade Maritime",
        "Splash247",
        "Offshore Engineer",
        "TradeWinds",
        "Lloyd's List",
        # Shipyards
        "Seatrium",
        "PaxOcean",
        "ASL Marine",
        "Penguin Shipyard",
    ]

    # Sales signal types
    SALES_SIGNALS = [
        "NEWBUILD - New vessel orders and shipyard contracts",
        "RETROFIT_REPOWER - Engine replacement and upgrade projects",
        "OFFSHORE_PROJECT - Oil & gas project sanctions creating vessel demand",
        "REGULATION - Emissions standards driving engine upgrades",
        "FUEL_TRANSITION - Dual-fuel, LNG, methanol, ammonia conversions",
        "FLEET_EXPANSION - Operator fleet growth",
        "INCIDENT_RELIABILITY - Engine failures creating replacement opportunities",
        "FINANCING_CAPEX - Major capital expenditure announcements",
    ]

    def __init__(self) -> None:
        """Initialize InsightsService with Perplexity API configuration."""
        super().__init__(timeout=60.0)
        self.api_key = os.getenv("PERPLEXITY_API_KEY")
        self.api_url = "https://api.perplexity.ai/chat/completions"

    async def _query_perplexity(self, prompt: str) -> InsightResult:
        """Query Perplexity API for insights."""
        if not self.api_key:
            logger.warning("PERPLEXITY_API_KEY not configured")
            return InsightResult(
                content="Perplexity API not configured. Please set PERPLEXITY_API_KEY environment variable.",
                sources=[],
                category="error",
            )

        try:
            client = await self._get_client()
            response = await client.post(
                self.api_url,
                headers={
                    "Authorization": f"Bearer {self.api_key}",
                    "Content-Type": "application/json",
                },
                json={
                    "model": "sonar",
                    "messages": [
                        {
                            "role": "system",
                            "content": """You are a marine industry sales intelligence analyst for RRPS (Rolls-Royce Power Systems), specializing in identifying sales opportunities for marine engines in Singapore and Asia-Pacific markets.

Your expertise covers:
- Marine propulsion systems for ferries, tugs, OSVs, harbour craft
- Offshore oil & gas vessel requirements (AHTS, PSV, FPSO)
- Shipyard contracts and newbuild programs
- Engine repower and retrofit projects
- IMO emissions regulations and fuel transition (LNG, methanol, ammonia)
- Maritime authority announcements (MPA Singapore, class societies)

Provide specific, actionable intelligence with:
- Named companies, shipyards, and vessel operators
- Contract values and vessel specifications when available
- Clear sales signals (newbuild, retrofit, fuel transition, fleet expansion)
- Concrete next-step recommendations for sales teams

Focus on Singapore, Indonesia, Malaysia, Thailand, Vietnam, Philippines, Australia, China, Korea, Japan, and India.""",
                        },
                        {"role": "user", "content": prompt},
                    ],
                    "temperature": 0.2,
                    "return_citations": True,
                },
            )

            if response.status_code == 200:
                data = response.json()
                content = data["choices"][0]["message"]["content"]
                citations = data.get("citations", [])
                # Citations can be strings (URLs) or dicts with url/title
                sources: list[str] = []
                for c in citations:
                    if isinstance(c, str):
                        sources.append(c)
                    elif isinstance(c, dict):
                        url = c.get("url") or c.get("title") or "Unknown"
                        sources.append(url)

                return InsightResult(
                    content=content,
                    sources=sources[:5],  # Limit to 5 sources
                    category="perplexity",
                )
            else:
                logger.error(f"Perplexity API error: {response.status_code}")
                return InsightResult(
                    content=f"API request failed with status {response.status_code}",
                    sources=[],
                    category="error",
                )

        except Exception as e:
            logger.error(f"Perplexity query error: {e}")
            return InsightResult(
                content=f"Error querying insights: {str(e)}",
                sources=[],
                category="error",
            )

    async def get_industry_news(self) -> InsightResult:
        """Get latest industry news identifying marine engine sales opportunities in Asia-Pacific."""
        # Use current date and extended range for better results
        current_year = datetime.now().year

        # Build targeted search prompts for different opportunity categories
        search_prompts = self._build_targeted_search_prompts(current_year)

        # Execute searches in PARALLEL for faster response
        tasks = [self._query_perplexity(prompt) for prompt in search_prompts]
        search_results = await asyncio.gather(*tasks, return_exceptions=True)

        # Process results, handling any exceptions
        results: list[str] = []
        all_sources: list[str] = []

        for i, result in enumerate(search_results):
            if isinstance(result, BaseException):
                logger.warning(f"Search query {i+1} failed: {result}")
                continue
            if result.category != "error":
                results.append(result.content)
                all_sources.extend(result.sources)

        # Combine all results
        if not results:
            return InsightResult(
                content="No industry news found. Please check API configuration.",
                sources=[],
                category="error",
            )

        # Deduplicate sources
        unique_sources = list(dict.fromkeys(all_sources))[:10]

        combined_content = "\n\n---\n\n".join(results)

        return InsightResult(
            content=combined_content,
            sources=unique_sources,
            category="industry_news",
        )

    def _build_targeted_search_prompts(self, year: int) -> list[str]:
        """Build targeted search prompts for different opportunity categories."""

        # Base instruction for all searches
        base_instruction = """Find SPECIFIC, RECENT announcements with:
- Named companies (operator + shipyard)
- Contract values or vessel counts
- Delivery timelines
- Source URLs for verification

DO NOT include: market forecasts, analyst opinions, or general trends.
Only include ACTUAL DEALS, CONTRACTS, TENDERS, or OFFICIAL ANNOUNCEMENTS."""

        prompts = []

        # 1. NEWBUILD CONTRACTS - Singapore & Southeast Asia Shipyards
        prompts.append(
            f"""Search for vessel newbuild contracts awarded to Singapore and Southeast Asia shipyards in the past 90 days.

{base_instruction}

SPECIFIC SEARCHES:
- "Seatrium" OR "Sembcorp Marine" contract awarded {year}
- "PaxOcean" vessel order
- "ASL Marine" newbuild contract
- "Penguin Shipyard" ferry order
- "Nam Cheong" OSV contract Malaysia
- "Batamec" shipyard Indonesia order
- Singapore shipyard vessel contract {year}

For each contract found, extract:
1. HEADLINE: "[Operator] orders [X] [vessel type] from [Shipyard]"
2. OPERATOR: Company ordering the vessel
3. SHIPYARD: Where vessels will be built
4. VESSEL TYPE: Ferry, tug, OSV, PSV, AHTS, tanker, etc.
5. VESSEL COUNT: Number of vessels
6. CONTRACT VALUE: In USD or local currency
7. DELIVERY: Expected delivery date/year
8. ENGINE SPECS: Power requirements if mentioned
9. SOURCE URL: Article link"""
        )

        # 2. FERRY & PASSENGER VESSEL ORDERS - High engine value
        prompts.append(
            f"""Search for ferry and passenger vessel orders in Asia-Pacific in the past 90 days.

{base_instruction}

SPECIFIC SEARCHES:
- Indonesia ferry newbuild order {year}
- Philippines ferry vessel contract
- Malaysia RoRo passenger ship order
- Thailand ferry operator fleet
- Vietnam passenger vessel shipbuilding
- "ASDP Indonesia Ferry" vessel order
- "Pelni" newbuild ferry
- "2GO" Philippines ferry
- "Bintan Resort Ferries" vessel
- "Batam Fast Ferry" newbuild

Priority: Ferries require 1,500-6,000 kW engines - high value opportunity.

Extract for each:
1. HEADLINE: "[Operator] orders [X] ferries from [Shipyard]"
2. OPERATOR & COUNTRY
3. VESSEL SPECS: Passenger capacity, vehicle capacity
4. SHIPYARD
5. CONTRACT VALUE
6. DELIVERY TIMELINE
7. SOURCE URL"""
        )

        # 3. OFFSHORE OIL & GAS - OSV Demand
        prompts.append(
            f"""Search for offshore oil & gas project announcements creating vessel demand in Asia-Pacific in the past 90 days.

{base_instruction}

SPECIFIC SEARCHES:
- Petronas offshore project FID {year}
- Pertamina offshore development sanctioned
- PTTEP project vessel requirement
- Woodside Asia Pacific offshore
- Santos offshore project Indonesia
- "offshore support vessel" charter Asia {year}
- FPSO contract awarded Southeast Asia
- Subsea construction vessel Asia Pacific

For each project/contract:
1. HEADLINE: "[Company] sanctions [Project] - [X] OSVs required"
2. OIL COMPANY: Petronas, Pertamina, PTTEP, etc.
3. PROJECT NAME & LOCATION
4. VESSEL DEMAND: Number and type of OSVs needed
5. PROJECT VALUE: If disclosed
6. TIMELINE: First oil/gas date
7. SOURCE URL"""
        )

        # 4. TUG & HARBOUR CRAFT - Singapore Focus
        prompts.append(
            f"""Search for tug boat and harbour craft orders in Singapore and Asia in the past 90 days.

{base_instruction}

SPECIFIC SEARCHES:
- Singapore harbour craft tender MPA {year}
- "PSA Marine" tug order
- "Keppel Smit Towage" newbuild
- "Pacific Carriers" vessel order
- Malaysia port tug contract
- Indonesia tugboat newbuild order
- Harbour tug ASD order Asia

Tugs require 2,500-6,000 kW engines - key RRPS market.

Extract:
1. HEADLINE: "[Operator] orders [X] tugs from [Shipyard]"
2. OPERATOR & COUNTRY
3. TUG TYPE: ASD, conventional, escort
4. BOLLARD PULL: If specified
5. SHIPYARD
6. CONTRACT VALUE
7. DELIVERY
8. SOURCE URL"""
        )

        # 5. FLEET RENEWAL & RETROFIT PROGRAMS
        prompts.append(
            f"""Search for fleet renewal programs and vessel retrofit/repower projects in Asia-Pacific in the past 90 days.

{base_instruction}

SPECIFIC SEARCHES:
- Fleet renewal program ferry operator Asia {year}
- Engine repower retrofit vessel Singapore
- Vessel modernization contract Malaysia
- IMO Tier III retrofit Asia Pacific
- Dual fuel conversion order Asia
- LNG retrofit vessel Singapore
- "green shipping" retrofit contract
- Decarbonization vessel upgrade Asia

Retrofits = replacement engine opportunity for RRPS.

Extract:
1. HEADLINE: "[Operator] announces [X]-vessel retrofit program"
2. OPERATOR & FLEET SIZE
3. RETROFIT TYPE: Repower, dual-fuel conversion, emissions upgrade
4. SHIPYARD: If specified
5. PROGRAM VALUE
6. TIMELINE
7. SOURCE URL"""
        )

        # 6. GOVERNMENT TENDERS & PUBLIC PROCUREMENT
        prompts.append(
            f"""Search for government vessel tenders and public procurement in Southeast Asia in the past 90 days.

{base_instruction}

SPECIFIC SEARCHES:
- MPA Singapore vessel tender {year}
- Indonesia government ferry tender
- Malaysia marine department vessel procurement
- Philippines coast guard vessel order
- Thailand navy patrol boat tender
- Vietnam border guard vessel
- Government RFP vessel Southeast Asia {year}

Government tenders = large, multi-vessel opportunities.

Extract:
1. HEADLINE: "[Government Agency] tenders for [X] vessels"
2. AGENCY & COUNTRY
3. VESSEL TYPE & COUNT
4. TENDER VALUE: Budget if disclosed
5. DEADLINE: Tender submission date
6. REQUIREMENTS: Specs if available
7. SOURCE URL"""
        )

        # 7. KOREAN & CHINESE SHIPYARD ORDERS for APAC Operators
        prompts.append(
            f"""Search for orders placed by Asia-Pacific operators at Korean and Chinese shipyards in the past 90 days.

{base_instruction}

SPECIFIC SEARCHES:
- "Hyundai Heavy Industries" vessel order Asia operator {year}
- "Samsung Heavy Industries" contract Southeast Asia
- "Daewoo" DSME vessel order Asia Pacific
- "Yangzijiang Shipbuilding" ferry order
- "CSSC" vessel contract Asia operator
- "Hudong-Zhonghua" LNG carrier order
- Korean shipyard OSV order Asia {year}

Extract:
1. HEADLINE: "[APAC Operator] orders [X] vessels from [Korean/Chinese Shipyard]"
2. OPERATOR: The Asia-Pacific company ordering
3. SHIPYARD: Korean or Chinese yard
4. VESSEL TYPE & COUNT
5. CONTRACT VALUE
6. DELIVERY
7. SOURCE URL"""
        )

        return prompts

    # Response framework for LLM synthesis
    SALES_BRIEFING_FRAMEWORK = """You are a sales intelligence analyst for RRPS (Rolls-Royce Power Systems) marine engines.

Your task is to synthesize the provided opportunity data into an executive sales briefing.

RESPONSE FRAMEWORK (follow this structure):

1. EXECUTIVE SUMMARY (2-3 sentences)
   - Total opportunities and priority breakdown
   - Key market trends observed
   - Most urgent action items

2. HIGH-PRIORITY OPPORTUNITIES (if any)
   For each high-priority opportunity:
   - Company and deal headline
   - Why it matters for RRPS
   - Recommended immediate action
   - Timeline if known

3. MARKET SIGNALS BY CATEGORY
   Group insights by signal type (Newbuild, Retrofit, Offshore, etc.)
   For each category with opportunities:
   - Brief summary of activity
   - Key companies involved
   - Sales implications

4. RECOMMENDED ACTIONS
   - Top 3 immediate actions for the sales team
   - Key contacts to pursue
   - Upcoming deadlines or events

GUIDELINES:
- Be concise and actionable
- Focus on WHAT to do, not search methodology
- Never mention "no results found" - only include categories with actual opportunities
- Use specific company names and values when available
- Prioritize Singapore and Southeast Asia markets"""

    async def get_structured_industry_news(self) -> dict[str, Any]:
        """
        Get structured industry news from the database, synthesized by LLM.

        Flow:
        1. Read opportunities from database (fast)
        2. LLM synthesizes into executive briefing using guided framework
        3. Returns actionable insights for sales team

        Returns:
            Dictionary with structured insights suitable for sales consumption
        """
        from lead_to_cash.services.marine_intel import get_marine_intel_db

        try:
            db = get_marine_intel_db()
            await db.initialize()

            # Get recent opportunities from database (last 30 days, sorted by priority)
            opportunities = await db.get_recent_opportunities(days=30, limit=50)

            if not opportunities:
                return {
                    "status": "success",
                    "message": "No recent opportunities in database. Use 'refresh' to trigger new research.",
                    "insights_count": 0,
                    "high_priority_count": 0,
                    "insights": [],
                    "sales_report": "No recent opportunities found. Run the research job to populate data.",
                    "can_refresh": True,
                }

            # Convert opportunities to structured data for LLM
            insights = [
                self._convert_opportunity_to_insight(opp) for opp in opportunities
            ]

            # Count by priority
            high_priority = sum(1 for opp in opportunities if opp.priority >= 8)
            medium_priority = sum(1 for opp in opportunities if 5 <= opp.priority < 8)
            low_priority = sum(1 for opp in opportunities if opp.priority < 5)

            # Use LLM to synthesize the briefing
            sales_report = await self._synthesize_sales_briefing(opportunities)

            return {
                "status": "success",
                "insights_count": len(insights),
                "high_priority_count": high_priority,
                "medium_priority_count": medium_priority,
                "low_priority_count": low_priority,
                "insights": insights,
                "sales_report": sales_report,
                "data_source": "database",
                "data_freshness": "last_30_days",
                "can_refresh": True,
            }

        except Exception as e:
            logger.error(f"Failed to get structured industry news: {e}")
            return {
                "status": "error",
                "message": f"Failed to retrieve insights: {str(e)}",
                "insights_count": 0,
                "insights": [],
            }

    async def _synthesize_sales_briefing(self, opportunities: list) -> str:
        """
        Use LLM to synthesize opportunities into an executive sales briefing.

        Args:
            opportunities: List of MarineOpportunity objects from database

        Returns:
            Synthesized sales briefing text
        """
        import os

        openai_api_key = os.getenv("OPENAI_API_KEY")
        if not openai_api_key:
            logger.warning("OPENAI_API_KEY not configured, using basic formatting")
            return self._basic_format_opportunities(opportunities)

        # Prepare opportunity data for LLM
        opp_data = []
        for opp in opportunities:
            opp_data.append(
                {
                    "headline": opp.headline,
                    "companies": opp.companies_involved,
                    "country": opp.country,
                    "region": opp.region,
                    "vessel_types": opp.vessel_types,
                    "sales_signals": opp.sales_signals,
                    "sales_explanation": opp.sales_explanation,
                    "suggested_action": opp.suggested_action,
                    "priority": opp.priority,
                    "estimated_value": opp.estimated_value,
                    "engine_power_range": opp.engine_power_range,
                    "source": opp.source_name,
                }
            )

        # Build prompt
        user_prompt = f"""Based on the following {len(opportunities)} sales opportunities from our intelligence database, create an executive sales briefing:

OPPORTUNITY DATA:
{json.dumps(opp_data, indent=2)}

Create a concise, actionable briefing following the response framework. Focus on what matters for the RRPS sales team."""

        try:
            client = await self._get_client()
            response = await client.post(
                "https://api.openai.com/v1/chat/completions",
                headers={
                    "Authorization": f"Bearer {openai_api_key}",
                    "Content-Type": "application/json",
                },
                json={
                    "model": os.getenv("OPENAI_MINI_MODEL", "gpt-4o-mini"),
                    "messages": [
                        {"role": "system", "content": self.SALES_BRIEFING_FRAMEWORK},
                        {"role": "user", "content": user_prompt},
                    ],
                    "temperature": 0.3,
                    "max_tokens": 2000,
                },
            )

            if response.status_code == 200:
                data = response.json()
                return data["choices"][0]["message"]["content"]
            else:
                logger.error(f"OpenAI API error: {response.status_code}")
                return self._basic_format_opportunities(opportunities)

        except Exception as e:
            logger.error(f"LLM synthesis failed: {e}")
            return self._basic_format_opportunities(opportunities)

    def _basic_format_opportunities(self, opportunities: list) -> str:
        """Basic formatting fallback when LLM is unavailable."""
        lines = [
            "RRPS MARINE SALES INTELLIGENCE BRIEFING",
            f"Generated: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}",
            "",
            f"Total Opportunities: {len(opportunities)}",
            f"High Priority: {sum(1 for o in opportunities if o.priority >= 8)}",
            "",
        ]

        for opp in sorted(opportunities, key=lambda x: -x.priority)[:10]:
            lines.extend(
                [
                    f"{'***' if opp.priority >= 8 else '**' if opp.priority >= 5 else '*'} {opp.headline}",
                    f"   Companies: {', '.join(opp.companies_involved[:3]) if opp.companies_involved else 'Unknown'}",
                    f"   Region: {opp.country}",
                    f"   Action: {opp.suggested_action}",
                    "",
                ]
            )

        return "\n".join(lines)

    def _convert_opportunity_to_insight(self, opp) -> dict[str, Any]:
        """Convert a MarineOpportunity to a structured insight dict."""
        # Map priority to level
        if opp.priority >= 8:
            priority_level = "HIGH"
        elif opp.priority >= 5:
            priority_level = "MEDIUM"
        else:
            priority_level = "LOW"

        # Get primary signal type
        signal_type = opp.sales_signals[0].upper() if opp.sales_signals else "NEWBUILD"

        return {
            "id": opp.id,
            "headline": opp.headline,
            "signal_type": signal_type,
            "priority": priority_level,
            "score": opp.priority * 10,
            "companies": {
                "operator": (
                    opp.companies_involved[0] if opp.companies_involved else "Unknown"
                ),
                "operator_country": opp.country,
                "shipyard": (
                    opp.companies_involved[1]
                    if len(opp.companies_involved) > 1
                    else None
                ),
            },
            "deal_details": {
                "vessel_type": opp.vessel_types[0] if opp.vessel_types else "Unknown",
                "vessel_count": None,
                "contract_value_usd": opp.estimated_value,
                "delivery_timeline": None,
            },
            "engine_requirement": (
                {
                    "power_range_kw": opp.engine_power_range,
                }
                if opp.engine_power_range
                else None
            ),
            "why_it_matters": opp.sales_explanation,
            "sales_action": {
                "priority": priority_level,
                "action": opp.suggested_action,
            },
            "country": opp.country,
            "region": opp.region,
            "source": {
                "name": opp.source_name,
                "url": opp.source_url,
                "published_date": (
                    opp.published_date.isoformat() if opp.published_date else None
                ),
            },
            "discovered_at": opp.discovered_at.isoformat(),
        }

    async def get_competitor_updates(self) -> InsightResult:
        """Get latest updates on competitors: Caterpillar, Cummins, MAN."""
        prompt = f"""Provide the latest business updates and news about these marine and industrial engine competitors:

Competitors: {', '.join(self.COMPETITORS)}

For each competitor, include:
1. Recent product announcements
2. Financial performance highlights
3. Major contracts or partnerships
4. Strategic initiatives
5. Market positioning changes

Focus on developments relevant to marine propulsion, power generation, and industrial engines. Provide specific data points where available."""

        result = await self._query_perplexity(prompt)
        result.category = "competitor_intel"
        return result

    async def get_customer_research(self, customer_name: str) -> InsightResult:
        """Research a specific customer/company for due diligence."""
        prompt = f"""Provide a business intelligence summary for: {customer_name}

Include:
1. Company overview and core business
2. Recent news and developments
3. Financial health indicators (if public)
4. Key executives and decision makers
5. Industry position and reputation
6. Any relevant concerns or red flags

Focus on information relevant for a B2B sales relationship in marine/industrial equipment."""

        result = await self._query_perplexity(prompt)
        result.category = "customer_research"
        return result

    async def search_insights(self, query: str) -> InsightResult:
        """General search for industry insights based on user query."""
        prompt = f"""As an industry analyst for marine engines and power systems, answer the following query:

Query: {query}

Provide factual, business-relevant information with specific data points. Focus on insights useful for sales professionals in the marine and industrial power sector. If the query relates to specific companies, include relevant competitive context."""

        result = await self._query_perplexity(prompt)
        result.category = "search"
        return result


# Singleton instance
_insights_service: Optional[InsightsService] = None


def get_insights_service() -> InsightsService:
    """Get or create the insights service singleton."""
    global _insights_service
    if _insights_service is None:
        _insights_service = InsightsService()
    return _insights_service
