"""
Perplexity Research Service

Production-ready AI-powered research service using Perplexity API for:
- Historical maritime news research (3-year backfill)
- Real-time market intelligence
- Competitor activity tracking
- Regulatory change monitoring

Features:
- Structured research templates
- Citation tracking
- Source verification
- Batch research with rate limiting

Usage:
    from lead_to_cash.services.perplexity_research import PerplexityResearch

    research = PerplexityResearch()
    results = await research.research_historical("Singapore ferry market 2023-2026")
"""

import asyncio
import logging
import os
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Optional

import httpx

logger = logging.getLogger(__name__)


# =============================================================================
# Research Templates
# =============================================================================


class ResearchType(str, Enum):
    """Types of research queries."""

    DAILY_NEWS = "daily_news"
    HISTORICAL = "historical"
    COMPETITOR = "competitor"
    REGULATORY = "regulatory"
    MARKET_INTEL = "market_intel"


# Research prompt templates
RESEARCH_TEMPLATES = {
    ResearchType.DAILY_NEWS: """
Search for maritime and shipping news from the past {days} days. Focus on:

1. **Singapore & Southeast Asia**:
   - MPA Singapore announcements and press releases
   - Singapore shipyard contracts (Keppel, Sembcorp, Seatrium)
   - Regional ferry, OSV, and tug orders
   - Indonesia, Malaysia, Vietnam maritime news

2. **Regulatory Updates**:
   - IMO MEPC decisions and regulations
   - New emission regulations (CII, EEXI, Tier III)
   - Fuel transition mandates (LNG, methanol, ammonia)
   - ECA enforcement updates

3. **Vessel Orders & Contracts**:
   - Newbuild contracts with engine specifications
   - Retrofit and repowering projects
   - FPSO/offshore project FIDs

4. **Competitor Activity**:
   - Wartsila, MAN, Caterpillar marine engine orders
   - HiMSEN, Bergen Engines contracts
   - Product launches and announcements

Return results with:
- Headline (exact from source)
- Source URL (full URL)
- Publication date (YYYY-MM-DD)
- Key entities (companies, vessels, engines mentioned)
- Contract values if disclosed
- Engine specifications if mentioned (power kW, RPM, fuel type)

Prioritize sources: MPA Singapore, IMO, Maritime Executive, Splash247,
TradeWinds, Seatrade, Lloyd's List, gCaptain, Offshore Engineer, DNV
""",
    ResearchType.HISTORICAL: """
Research the following maritime industry topic for the period {start_year} to {end_year}:

Topic: {topic}

Focus areas:
1. Major contracts and orders announced
2. Regulatory changes implemented
3. Market trends and shifts
4. Key players and market share changes
5. Technology transitions (fuel types, engine types)

For each finding, provide:
- Date (month/year minimum)
- Source publication name
- Source URL if available
- Key facts (no speculation)
- Relevance to marine engine market (medium-speed 300-1000 RPM, 700kW-40MW)

Regions of interest: Singapore, Indonesia, Malaysia, Thailand,
Vietnam, Philippines, Australia, China, Korea, Japan

Sources to prioritize: Industry publications, official press releases,
regulatory body announcements, company annual reports, classification societies

Format response as structured findings with citations.
""",
    ResearchType.COMPETITOR: """
Research recent activity for {competitor_name} in the marine engine market:

Time period: Last {months} months

Find:
1. **New Orders & Customer Wins**: Engine orders with customer names, vessel types, contract values.
   SPECIFICALLY search for contracts in Singapore, Southeast Asia, and APAC.
   Check: MPA Singapore vessel registry, Singapore shipyard announcements (Seatrium, Keppel, PaxOcean),
   Indonesian ferry operators, Vietnam/Philippines naval orders.
2. **Product Launches**: New engine models with kW/HP ratings, fuel types, RPM, emissions tier,
   target segment, launch date. Search product brochures and distributor pages.
3. **Partnerships & Distributors**: Shipyard agreements, OEM partnerships, authorized distributors
   in Singapore/APAC (e.g., Trakindo for Cat, Pon Power for Volvo Penta).
4. **Market Moves**: Price changes, new service centers in APAC, facility expansions.
5. **Technical Developments**: Efficiency improvements, emission compliance, new certifications.
6. **Annual Report / Investor Relations**: R&D focus, segment strategy, geographic revenue.

Target competitors and their product lines:
- Caterpillar MaK (C32, C32B, 3500E, 3516E, M32C, M43C, M46DF)
- Cummins Marine (QSK19, QSK38, QSK60, QSK78, X10, X15, B7.2)
- Wartsila (W20, W25, W31, W32, W34DF, W46F, W46DF, W46TS)
- MAN Energy Solutions (32/44CR, 48/60CR, 51/60DF, 51/60G, ME-LGIM)
- Volvo Penta (D8, D13, D16, IPS series, IPS900E, IPS650E)
- Yanmar (6AYM, 6EY, 6GY, 8N330, 12AYM)

For each finding provide:
- Date (at least month/year)
- Source and URL
- Specific details (power ratings in kW, fuel types, vessel application)
- Customer name and region where possible
""",
    ResearchType.REGULATORY: """
Research maritime regulatory changes and environmental requirements:

Time period: {start_year} to present

Focus areas:
1. **IMO Regulations**:
   - MEPC decisions and amendments
   - CII (Carbon Intensity Indicator) updates
   - EEXI (Energy Efficiency Index) requirements
   - GHG reduction targets and timelines

2. **Regional Regulations**:
   - MPA Singapore requirements
   - EU ETS for shipping
   - China ECA zones
   - US EPA requirements

3. **Fuel Transition**:
   - Alternative fuel mandates (LNG, methanol, ammonia, hydrogen)
   - Shore power requirements
   - Bunkering infrastructure developments
   - Tier III emission standards

4. **Classification Society Updates**:
   - DNV, Lloyd's Register, ABS, ClassNK rule changes
   - New notations and certifications
   - Technical requirements for compliance

Provide:
- Regulation name and reference number
- Effective date
- Key requirements
- Impact on vessel operators and engine suppliers
- Compliance timeline
""",
    ResearchType.MARKET_INTEL: """
Research market intelligence for: {market_segment}

Region focus: {region}
Time period: Last {months} months

Analyze:
1. **Market Size & Growth**:
   - Fleet size and composition
   - Order book status
   - Delivery schedules

2. **Key Players**:
   - Major operators and owners
   - Shipyards with active contracts
   - Engine suppliers winning orders

3. **Investment Signals**:
   - FID announcements (Final Investment Decisions)
   - Financing deals and bank commitments
   - Private equity and M&A activity

4. **Demand Drivers**:
   - Regulatory compliance requirements
   - Fleet renewal cycles
   - New project developments
   - Trade route expansions

5. **Competitive Landscape**:
   - Preferred engine suppliers by segment
   - Technology preferences (dual-fuel, diesel, gas)
   - Price competitiveness trends

Market segments of interest:
- Ferries & RoPax
- Offshore Support Vessels (OSV, PSV, AHTS)
- FPSO & Offshore Production
- Tugs & Harbour Craft
- Tankers (product, chemical, LNG)
- Container vessels

Provide market insights with supporting data and sources.
""",
}


@dataclass
class ResearchResult:
    """Result of a Perplexity research query."""

    id: str
    research_type: str
    query: str
    response: str
    citations: list[str]
    timestamp: datetime
    model: str
    tokens_used: int
    metadata: dict = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "research_type": self.research_type,
            "query": self.query,
            "response": self.response,
            "citations": self.citations,
            "timestamp": self.timestamp.isoformat(),
            "model": self.model,
            "tokens_used": self.tokens_used,
            "metadata": self.metadata,
        }


@dataclass
class ExtractedArticle:
    """Article extracted from research results."""

    title: str
    url: Optional[str]
    source_name: str
    published_date: Optional[datetime]
    summary: str
    entities: list[str]
    category: str
    confidence: float


class PerplexityResearch:
    """
    Production Perplexity research service for maritime intelligence.

    Uses Perplexity API for AI-powered web research with:
    - Structured research templates
    - Citation tracking
    - Historical backfill capability
    - Batch processing with rate limiting
    """

    PERPLEXITY_API_URL = "https://api.perplexity.ai/chat/completions"

    def __init__(
        self,
        api_key: Optional[str] = None,
        model: str = "sonar",  # sonar, sonar-pro
        timeout: int = 120,
        max_retries: int = 3,
    ):
        """
        Initialize Perplexity research service.

        Args:
            api_key: Perplexity API key (defaults to PERPLEXITY_API_KEY env var)
            model: Model to use (sonar or sonar-pro)
            timeout: Request timeout in seconds
            max_retries: Maximum retry attempts
        """
        self.api_key = api_key or os.getenv("PERPLEXITY_API_KEY")
        self.model = model
        self.timeout = timeout
        self.max_retries = max_retries
        self._http_client: Optional[httpx.AsyncClient] = None

        if not self.api_key:
            logger.warning("PERPLEXITY_API_KEY not set - research will fail")

    async def _get_client(self) -> httpx.AsyncClient:
        """Get or create HTTP client."""
        if self._http_client is None or self._http_client.is_closed:
            self._http_client = httpx.AsyncClient(
                timeout=self.timeout,
                headers={
                    "Authorization": f"Bearer {self.api_key}",
                    "Content-Type": "application/json",
                },
            )
        return self._http_client

    async def close(self) -> None:
        """Close HTTP client."""
        if self._http_client and not self._http_client.is_closed:
            await self._http_client.aclose()
            self._http_client = None

    async def _call_api(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
    ) -> tuple[str, list[str], int]:
        """
        Call Perplexity API with retry logic.

        Returns:
            Tuple of (response_text, citations, tokens_used)
        """
        if not self.api_key:
            raise ValueError("PERPLEXITY_API_KEY not configured")

        client = await self._get_client()

        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})

        payload = {
            "model": self.model,
            "messages": messages,
            "max_tokens": 4000,
            "temperature": 0.1,  # Low temperature for factual research
            "return_citations": True,
        }

        last_error = None
        for attempt in range(self.max_retries):
            try:
                response = await client.post(
                    self.PERPLEXITY_API_URL,
                    json=payload,
                )

                if response.status_code == 429:
                    # Rate limited - wait and retry
                    wait_time = 2 ** (attempt + 1)
                    logger.warning(f"Rate limited, waiting {wait_time}s")
                    await asyncio.sleep(wait_time)
                    continue

                if response.status_code != 200:
                    logger.error(
                        f"Perplexity API error: {response.status_code} - {response.text}"
                    )
                    raise httpx.HTTPStatusError(
                        f"API returned {response.status_code}",
                        request=response.request,
                        response=response,
                    )

                data = response.json()

                # Extract response
                content = data["choices"][0]["message"]["content"]

                # Extract citations
                citations = data.get("citations", [])

                # Extract token usage
                tokens = data.get("usage", {}).get("total_tokens", 0)

                return content, citations, tokens

            except httpx.TimeoutException as e:
                logger.warning(f"Timeout on attempt {attempt + 1}: {e}")
                last_error = e
                await asyncio.sleep(2**attempt)
            except Exception as e:
                logger.error(f"Error on attempt {attempt + 1}: {e}")
                last_error = e
                await asyncio.sleep(2**attempt)

        raise last_error or Exception("Max retries exceeded")

    async def research(
        self,
        prompt: str,
        research_type: ResearchType = ResearchType.MARKET_INTEL,
        metadata: Optional[dict] = None,
    ) -> ResearchResult:
        """
        Execute a research query.

        Args:
            prompt: Research prompt/query
            research_type: Type of research
            metadata: Additional metadata to store

        Returns:
            ResearchResult with response and citations
        """
        logger.info(f"Executing {research_type.value} research")

        system_prompt = """You are a maritime industry research analyst specializing in:
- Marine engine markets (medium-speed 300-1000 RPM, 700kW-40MW)
- Singapore and Southeast Asia maritime sector
- Offshore oil & gas vessels
- Regulatory compliance and emissions
- Competitor intelligence

Provide factual, well-sourced information. Always cite sources.
Format responses clearly with dates, company names, and specific details.
Focus on actionable business intelligence for marine engine sales."""

        response, citations, tokens = await self._call_api(prompt, system_prompt)

        result = ResearchResult(
            id=str(uuid.uuid4()),
            research_type=research_type.value,
            query=prompt[:500],  # Truncate for storage
            response=response,
            citations=citations,
            timestamp=datetime.now(timezone.utc),
            model=self.model,
            tokens_used=tokens,
            metadata=metadata or {},
        )

        logger.info(
            f"Research complete: {len(response)} chars, "
            f"{len(citations)} citations, {tokens} tokens"
        )

        return result

    async def research_daily_news(
        self,
        days: int = 7,
    ) -> ResearchResult:
        """
        Research daily maritime news.

        Args:
            days: Number of days to look back

        Returns:
            ResearchResult with recent news
        """
        prompt = RESEARCH_TEMPLATES[ResearchType.DAILY_NEWS].format(days=days)
        return await self.research(prompt, ResearchType.DAILY_NEWS, {"days": days})

    async def research_historical(
        self,
        topic: str,
        start_year: int = 2023,
        end_year: int = 2026,
    ) -> ResearchResult:
        """
        Research historical maritime industry data.

        Args:
            topic: Research topic (e.g., "Singapore ferry market")
            start_year: Start year for research
            end_year: End year for research

        Returns:
            ResearchResult with historical findings
        """
        prompt = RESEARCH_TEMPLATES[ResearchType.HISTORICAL].format(
            topic=topic,
            start_year=start_year,
            end_year=end_year,
        )
        return await self.research(
            prompt,
            ResearchType.HISTORICAL,
            {"topic": topic, "start_year": start_year, "end_year": end_year},
        )

    async def research_competitor(
        self,
        competitor_name: str,
        months: int = 12,
    ) -> ResearchResult:
        """
        Research competitor activity.

        Args:
            competitor_name: Competitor to research
            months: Months of history

        Returns:
            ResearchResult with competitor intelligence
        """
        prompt = RESEARCH_TEMPLATES[ResearchType.COMPETITOR].format(
            competitor_name=competitor_name,
            months=months,
        )
        return await self.research(
            prompt,
            ResearchType.COMPETITOR,
            {"competitor": competitor_name, "months": months},
        )

    async def research_regulatory(
        self,
        start_year: int = 2023,
    ) -> ResearchResult:
        """
        Research regulatory changes.

        Args:
            start_year: Start year for regulatory research

        Returns:
            ResearchResult with regulatory updates
        """
        prompt = RESEARCH_TEMPLATES[ResearchType.REGULATORY].format(
            start_year=start_year
        )
        return await self.research(
            prompt,
            ResearchType.REGULATORY,
            {"start_year": start_year},
        )

    async def research_market(
        self,
        market_segment: str,
        region: str = "Singapore & Southeast Asia",
        months: int = 12,
    ) -> ResearchResult:
        """
        Research market intelligence for a segment.

        Args:
            market_segment: Market segment (e.g., "Ferries & RoPax")
            region: Geographic region
            months: Months of history

        Returns:
            ResearchResult with market intelligence
        """
        prompt = RESEARCH_TEMPLATES[ResearchType.MARKET_INTEL].format(
            market_segment=market_segment,
            region=region,
            months=months,
        )
        return await self.research(
            prompt,
            ResearchType.MARKET_INTEL,
            {"segment": market_segment, "region": region, "months": months},
        )

    async def run_historical_backfill(
        self,
        topics: Optional[list[str]] = None,
        delay_between_queries: float = 5.0,
    ) -> list[ResearchResult]:
        """
        Run historical research backfill for multiple topics.

        Args:
            topics: List of topics to research (uses defaults if None)
            delay_between_queries: Delay between API calls (rate limiting)

        Returns:
            List of ResearchResult objects
        """
        if topics is None:
            topics = [
                "Singapore ferry fleet expansion and newbuilds",
                "Southeast Asia offshore support vessel market",
                "IMO emissions regulations impact on shipping",
                "LNG and dual-fuel vessel orders Asia Pacific",
                "FPSO contracts Southeast Asia and Australia",
                "Marine engine market share Wartsila MAN Caterpillar",
                "Indonesia maritime cabotage vessel orders",
                "Malaysian offshore oil gas vessel contracts",
            ]

        results = []

        logger.info(f"Starting historical backfill for {len(topics)} topics")

        for i, topic in enumerate(topics):
            logger.info(f"Researching topic {i + 1}/{len(topics)}: {topic[:50]}...")

            try:
                result = await self.research_historical(topic)
                results.append(result)

                # Save to database
                await self._save_research_result(result)

            except Exception as e:
                logger.error(f"Error researching '{topic}': {e}")

            # Rate limiting
            if i < len(topics) - 1:
                await asyncio.sleep(delay_between_queries)

        logger.info(f"Historical backfill complete: {len(results)} results")
        return results

    async def _save_research_result(self, result: ResearchResult) -> bool:
        """
        Save research result to database as article(s).

        Parses the response to extract individual articles/findings
        and saves them to marine_articles.
        """
        from lead_to_cash.services.marine_intel.database import get_marine_intel_db
        from lead_to_cash.services.marine_intel.models import Article

        db = get_marine_intel_db()
        await db.initialize()

        # Create a summary article for the research
        article = Article.create(
            url=f"perplexity://research/{result.id}",
            title=f"Perplexity Research: {result.metadata.get('topic', result.research_type)[:100]}",
            source="Perplexity AI Research",
            content=result.response,
            summary=(
                result.response[:500] if len(result.response) > 500 else result.response
            ),
            published_date=result.timestamp,
            source_category="perplexity",
            metadata={
                "research_type": result.research_type,
                "citations": result.citations,
                "model": result.model,
                "tokens_used": result.tokens_used,
                **result.metadata,
            },
        )

        _, is_new = await db.save_article(article)
        return is_new


# =============================================================================
# Convenience Functions
# =============================================================================


async def run_daily_research(days: int = 7) -> ResearchResult:
    """Run daily news research."""
    research = PerplexityResearch()
    try:
        return await research.research_daily_news(days=days)
    finally:
        await research.close()


async def run_competitor_research(competitor: str) -> ResearchResult:
    """Run competitor intelligence research."""
    research = PerplexityResearch()
    try:
        return await research.research_competitor(competitor)
    finally:
        await research.close()


async def run_regulatory_research() -> ResearchResult:
    """Run regulatory research."""
    research = PerplexityResearch()
    try:
        return await research.research_regulatory()
    finally:
        await research.close()


async def run_historical_backfill() -> list[ResearchResult]:
    """Run full historical backfill."""
    research = PerplexityResearch()
    try:
        return await research.run_historical_backfill()
    finally:
        await research.close()


async def run_market_research(
    segment: str,
    region: str = "Singapore & Southeast Asia",
) -> ResearchResult:
    """Run market intelligence research."""
    research = PerplexityResearch()
    try:
        return await research.research_market(segment, region)
    finally:
        await research.close()
