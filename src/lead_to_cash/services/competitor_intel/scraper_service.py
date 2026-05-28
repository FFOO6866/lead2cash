"""
Competitor Intelligence Scraper Service

Hybrid content collection using:
- Perplexity API for news, wins, case studies, market intelligence
- Direct web scraping for product pages
- PDF parsing for annual reports
"""

import logging
import os
import uuid
from datetime import datetime, timezone
from typing import Any, Optional

import httpx

from lead_to_cash.services.competitor_intel.database import get_competitor_db
from lead_to_cash.services.competitor_intel.models import (
    Competitor,
    CompetitorDocument,
    ContentType,
    ScrapingJob,
    SourceType,
)

logger = logging.getLogger(__name__)


class CompetitorScraperService:
    """
    Scraper service for gathering comprehensive competitor intelligence.

    Collects:
    - Contract wins and deal announcements
    - Customer success stories and case studies
    - Product launches and specifications
    - Partnership and acquisition news
    - Executive changes and strategic moves
    - Market analysis and pricing information
    - Social media highlights
    """

    # Competitor information for targeted scraping
    COMPETITORS = {
        Competitor.CATERPILLAR: {
            "name": "Caterpillar",
            "aliases": ["Cat", "CAT", "Caterpillar Inc", "Caterpillar Marine"],
            "domains": ["caterpillar.com", "cat.com"],
            "marine_division": "Cat Marine Power Systems",
            "focus_products": [
                "marine engines",
                "generator sets",
                "propulsion systems",
            ],
        },
        Competitor.CUMMINS: {
            "name": "Cummins",
            "aliases": ["Cummins Inc", "Cummins Marine"],
            "domains": ["cummins.com"],
            "marine_division": "Cummins Marine",
            "focus_products": [
                "marine engines",
                "generators",
                "propulsion",
                "hybrid systems",
            ],
        },
        Competitor.MAN_ENERGY: {
            "name": "MAN Energy Solutions",
            "aliases": ["MAN ES", "MAN Diesel", "MAN Diesel & Turbo"],
            "domains": ["man-es.com"],
            "marine_division": "MAN Energy Solutions Marine",
            "focus_products": [
                "two-stroke engines",
                "four-stroke engines",
                "turbochargers",
                "propellers",
            ],
        },
    }

    # Industry segments relevant to RRPS
    INDUSTRY_SEGMENTS = [
        "marine propulsion",
        "offshore oil and gas",
        "marine transportation",
        "commercial shipping",
        "cruise ships",
        "ferries",
        "offshore vessels",
        "tugboats",
        "yachts",
        "naval defense",
        "power generation",
    ]

    def __init__(self):
        self.api_key = os.getenv("PERPLEXITY_API_KEY")
        self.api_url = "https://api.perplexity.ai/chat/completions"
        self._client: Optional[httpx.AsyncClient] = None
        # Note: Use self.db property instead of storing reference at init time
        # This ensures we always get the current initialized singleton

    @property
    def db(self):
        """Get the database singleton - always returns current initialized instance."""
        return get_competitor_db()

    async def _get_client(self) -> httpx.AsyncClient:
        """Get or create HTTP client."""
        if self._client is None:
            self._client = httpx.AsyncClient(timeout=90.0)
        return self._client

    async def close(self):
        """Close HTTP client."""
        if self._client:
            await self._client.aclose()
            self._client = None

    # =========================================================================
    # Perplexity API Queries - Comprehensive Intelligence
    # =========================================================================

    async def _query_perplexity(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
    ) -> dict[str, Any]:
        """Query Perplexity API for competitor intelligence."""
        if not self.api_key:
            logger.warning("PERPLEXITY_API_KEY not configured")
            return {"content": "", "sources": [], "error": "API key not configured"}

        default_system = """You are a competitive intelligence analyst for Rolls-Royce Power Systems.
Your role is to gather actionable intelligence about marine engine competitors.
Focus on information relevant to B2B sales: contract wins, customer relationships,
product advantages/disadvantages, pricing signals, and market positioning.
Be specific with names, dates, and figures when available."""

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
                        {"role": "system", "content": system_prompt or default_system},
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
                sources: list[str] = []
                for c in citations:
                    if isinstance(c, str):
                        sources.append(c)
                    elif isinstance(c, dict):
                        url = c.get("url") or c.get("title") or "Unknown"
                        sources.append(url)

                return {"content": content, "sources": sources[:10]}
            else:
                logger.error(f"Perplexity API error: {response.status_code}")
                return {
                    "content": "",
                    "sources": [],
                    "error": f"API error {response.status_code}",
                }

        except Exception as e:
            logger.error(f"Perplexity query error: {e}")
            return {"content": "", "sources": [], "error": str(e)}

    async def fetch_contract_wins(self, competitor: str) -> list[CompetitorDocument]:
        """Fetch recent contract wins and deal announcements."""
        comp_info = self.COMPETITORS.get(Competitor(competitor), {})
        comp_name = comp_info.get("name", competitor)

        prompt = f"""Find recent contract wins, deal announcements, and order wins for {comp_name}
in the marine engine, power systems, and offshore sectors.

For each win, provide:
1. Customer name and type (shipping company, offshore operator, navy, etc.)
2. Contract value if disclosed
3. Products/services included (engine model, kW rating, quantity)
4. Geographic region
5. Date announced
6. Why they won (if mentioned)

PRIORITY REGIONS: Singapore, Indonesia, Malaysia, Vietnam, Philippines, Australia, APAC.
Search for: Singapore harbour craft operators, APAC ferry companies, Southeast Asian
shipyards (Seatrium, Keppel, PaxOcean, Penguin Shipyard, ASL Marine, Damen Singapore).
Also include global wins from the past 12 months."""

        result = await self._query_perplexity(prompt)

        if result.get("error") or not result.get("content"):
            return []

        doc = CompetitorDocument(
            id=str(uuid.uuid4()),
            competitor=competitor,
            content_type=ContentType.CONTRACT_WIN.value,
            source_type=SourceType.PERPLEXITY.value,
            title=f"{comp_name} - Recent Contract Wins",
            content=result["content"],
            summary=f"Contract wins and deal announcements for {comp_name}",
            source_url=result["sources"][0] if result["sources"] else "",
            scraped_at=datetime.now(timezone.utc),
            metadata={"sources": result["sources"], "query_type": "contract_wins"},
        )

        await self.db.save_document(doc)
        return [doc]

    async def fetch_customer_success(self, competitor: str) -> list[CompetitorDocument]:
        """Fetch customer success stories and case studies."""
        comp_info = self.COMPETITORS.get(Competitor(competitor), {})
        comp_name = comp_info.get("name", competitor)

        prompt = f"""Find customer success stories, case studies, and testimonials for {comp_name}
marine engines and power systems.

Include:
1. Customer name and application
2. Products used and results achieved
3. Performance metrics (fuel efficiency, reliability, etc.)
4. Customer quotes or endorsements
5. Any competitive displacement mentioned (switching from other brands)

Focus on marine, offshore, and power generation applications."""

        result = await self._query_perplexity(prompt)

        if result.get("error") or not result.get("content"):
            return []

        doc = CompetitorDocument(
            id=str(uuid.uuid4()),
            competitor=competitor,
            content_type=ContentType.CUSTOMER_SUCCESS.value,
            source_type=SourceType.PERPLEXITY.value,
            title=f"{comp_name} - Customer Success Stories",
            content=result["content"],
            summary=f"Customer success stories for {comp_name}",
            source_url=result["sources"][0] if result["sources"] else "",
            scraped_at=datetime.now(timezone.utc),
            metadata={"sources": result["sources"], "query_type": "customer_success"},
        )

        await self.db.save_document(doc)
        return [doc]

    async def fetch_product_launches(self, competitor: str) -> list[CompetitorDocument]:
        """Fetch new product launches and technology announcements."""
        comp_info = self.COMPETITORS.get(Competitor(competitor), {})
        comp_name = comp_info.get("name", competitor)

        prompt = f"""Find recent product launches, new technology announcements, and R&D updates
from {comp_name} in marine engines and power systems.

Include:
1. New engine models and specifications
2. Technology innovations (emissions, efficiency, hybrid, alternative fuels)
3. Service and aftermarket offerings
4. Digital and connectivity solutions
5. Comparison with previous models or competitors

Focus on announcements from the past 12 months."""

        result = await self._query_perplexity(prompt)

        if result.get("error") or not result.get("content"):
            return []

        doc = CompetitorDocument(
            id=str(uuid.uuid4()),
            competitor=competitor,
            content_type=ContentType.PRODUCT_LAUNCH.value,
            source_type=SourceType.PERPLEXITY.value,
            title=f"{comp_name} - Product Launches & Technology",
            content=result["content"],
            summary=f"Product launches and technology updates for {comp_name}",
            source_url=result["sources"][0] if result["sources"] else "",
            scraped_at=datetime.now(timezone.utc),
            metadata={"sources": result["sources"], "query_type": "product_launches"},
        )

        await self.db.save_document(doc)
        return [doc]

    async def fetch_strategic_moves(self, competitor: str) -> list[CompetitorDocument]:
        """Fetch partnerships, acquisitions, and strategic initiatives."""
        comp_info = self.COMPETITORS.get(Competitor(competitor), {})
        comp_name = comp_info.get("name", competitor)

        prompt = f"""Find recent strategic moves by {comp_name} including:

1. Partnerships and joint ventures
2. Acquisitions and investments
3. Geographic expansion (new facilities, markets)
4. Executive changes and leadership updates
5. Sustainability and emissions reduction initiatives
6. Digital transformation efforts
7. Supply chain changes

Focus on developments from the past 12 months that could impact competitive positioning."""

        result = await self._query_perplexity(prompt)

        if result.get("error") or not result.get("content"):
            return []

        doc = CompetitorDocument(
            id=str(uuid.uuid4()),
            competitor=competitor,
            content_type=ContentType.PARTNERSHIP.value,
            source_type=SourceType.PERPLEXITY.value,
            title=f"{comp_name} - Strategic Moves",
            content=result["content"],
            summary=f"Strategic initiatives and partnerships for {comp_name}",
            source_url=result["sources"][0] if result["sources"] else "",
            scraped_at=datetime.now(timezone.utc),
            metadata={"sources": result["sources"], "query_type": "strategic_moves"},
        )

        await self.db.save_document(doc)
        return [doc]

    async def fetch_market_positioning(
        self, competitor: str
    ) -> list[CompetitorDocument]:
        """Fetch market share and competitive positioning information."""
        comp_info = self.COMPETITORS.get(Competitor(competitor), {})
        comp_name = comp_info.get("name", competitor)

        prompt = f"""Analyze {comp_name}'s market position in marine engines and power systems:

1. Estimated market share by segment (marine propulsion, gensets, offshore)
2. Key competitive advantages and weaknesses vs Rolls-Royce, Wartsila, others
3. Pricing positioning (premium, mid-market, value)
4. Customer perception and brand strength
5. Geographic strengths and weaknesses
6. Service network and aftermarket presence

Provide specific data points and analyst opinions where available."""

        result = await self._query_perplexity(prompt)

        if result.get("error") or not result.get("content"):
            return []

        doc = CompetitorDocument(
            id=str(uuid.uuid4()),
            competitor=competitor,
            content_type=ContentType.MARKET_ANALYSIS.value,
            source_type=SourceType.PERPLEXITY.value,
            title=f"{comp_name} - Market Position Analysis",
            content=result["content"],
            summary=f"Market positioning analysis for {comp_name}",
            source_url=result["sources"][0] if result["sources"] else "",
            scraped_at=datetime.now(timezone.utc),
            metadata={"sources": result["sources"], "query_type": "market_positioning"},
        )

        await self.db.save_document(doc)
        return [doc]

    async def fetch_financial_performance(
        self, competitor: str
    ) -> list[CompetitorDocument]:
        """Fetch financial highlights and business performance."""
        comp_info = self.COMPETITORS.get(Competitor(competitor), {})
        comp_name = comp_info.get("name", competitor)

        prompt = f"""Find financial performance information for {comp_name}'s marine and power systems business:

1. Revenue and growth trends
2. Order backlog and intake
3. Profitability and margins
4. Investment in R&D
5. Guidance and outlook
6. Analyst ratings and price targets

Focus on the most recent quarterly and annual results."""

        result = await self._query_perplexity(prompt)

        if result.get("error") or not result.get("content"):
            return []

        doc = CompetitorDocument(
            id=str(uuid.uuid4()),
            competitor=competitor,
            content_type=ContentType.QUARTERLY_REPORT.value,
            source_type=SourceType.PERPLEXITY.value,
            title=f"{comp_name} - Financial Performance",
            content=result["content"],
            summary=f"Financial performance highlights for {comp_name}",
            source_url=result["sources"][0] if result["sources"] else "",
            scraped_at=datetime.now(timezone.utc),
            metadata={
                "sources": result["sources"],
                "query_type": "financial_performance",
            },
        )

        await self.db.save_document(doc)
        return [doc]

    async def fetch_industry_news(self, competitor: str) -> list[CompetitorDocument]:
        """Fetch general news and press coverage."""
        comp_info = self.COMPETITORS.get(Competitor(competitor), {})
        comp_name = comp_info.get("name", competitor)

        prompt = f"""Find the latest news about {comp_name} in marine engines and power systems from the past month:

1. Press releases and announcements
2. Trade publication coverage (Lloyd's List, TradeWinds, Marine Log)
3. Industry event participation
4. Awards and recognition
5. Any controversies or challenges

Provide headlines with brief summaries."""

        result = await self._query_perplexity(prompt)

        if result.get("error") or not result.get("content"):
            return []

        doc = CompetitorDocument(
            id=str(uuid.uuid4()),
            competitor=competitor,
            content_type=ContentType.NEWS.value,
            source_type=SourceType.PERPLEXITY.value,
            title=f"{comp_name} - Latest News",
            content=result["content"],
            summary=f"Recent news coverage for {comp_name}",
            source_url=result["sources"][0] if result["sources"] else "",
            scraped_at=datetime.now(timezone.utc),
            metadata={"sources": result["sources"], "query_type": "industry_news"},
        )

        await self.db.save_document(doc)
        return [doc]

    # =========================================================================
    # Full Competitor Refresh
    # =========================================================================

    async def refresh_competitor(self, competitor: str) -> dict[str, Any]:
        """Run full intelligence refresh for a single competitor."""
        logger.info(f"Starting full refresh for {competitor}")

        documents = []

        # Run all intelligence gathering queries
        queries = [
            self.fetch_contract_wins(competitor),
            self.fetch_customer_success(competitor),
            self.fetch_product_launches(competitor),
            self.fetch_strategic_moves(competitor),
            self.fetch_market_positioning(competitor),
            self.fetch_financial_performance(competitor),
            self.fetch_industry_news(competitor),
        ]

        for query_coro in queries:
            try:
                docs = await query_coro
                documents.extend(docs)
            except Exception as e:
                logger.error(f"Query error for {competitor}: {e}")

        return {
            "competitor": competitor,
            "documents_created": len(documents),
            "document_ids": [d.id for d in documents],
        }

    async def refresh_all_competitors(self) -> ScrapingJob:
        """Run full intelligence refresh for all competitors."""
        job = ScrapingJob(
            id=str(uuid.uuid4()),
            job_type="daily_refresh",
            status="running",
            started_at=datetime.now(timezone.utc),
        )
        await self.db.save_job(job)

        logger.info(f"Starting full competitor refresh - Job {job.id}")

        total_docs = 0
        total_failed = 0

        for competitor in Competitor:
            try:
                result = await self.refresh_competitor(competitor.value)
                total_docs += result["documents_created"]
            except Exception as e:
                logger.error(f"Failed to refresh {competitor.value}: {e}")
                total_failed += 1

        job.status = "completed"
        job.completed_at = datetime.now(timezone.utc)
        job.documents_processed = total_docs
        job.documents_failed = total_failed
        await self.db.save_job(job)

        logger.info(f"Refresh complete - {total_docs} documents created")

        return job

    # =========================================================================
    # Search and Query
    # =========================================================================

    async def search_intelligence(
        self,
        query: str,
        competitor: Optional[str] = None,
    ) -> dict[str, Any]:
        """
        Search competitor intelligence with a custom query.

        Uses Perplexity for real-time search when needed.
        """
        comp_filter = ""
        if competitor:
            comp_info = self.COMPETITORS.get(Competitor(competitor), {})
            comp_filter = f"Focus specifically on {comp_info.get('name', competitor)}. "

        prompt = f"""{comp_filter}As a competitive intelligence analyst for Rolls-Royce Power Systems
marine division, answer this query:

{query}

Provide actionable intelligence with specific details, names, dates, and figures.
Include sources for verification."""

        result = await self._query_perplexity(prompt)

        return {
            "query": query,
            "competitor": competitor,
            "content": result.get("content", ""),
            "sources": result.get("sources", []),
            "error": result.get("error"),
        }


# Singleton instance
_scraper: Optional[CompetitorScraperService] = None


def get_scraper_service() -> CompetitorScraperService:
    """Get or create the scraper service singleton."""
    global _scraper
    if _scraper is None:
        _scraper = CompetitorScraperService()
    return _scraper
