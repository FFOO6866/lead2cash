"""
EODHD Service for Competitor Financial Data

Integrates with EODHD API to fetch financial data for competitor tracking:
- Quarterly and annual financials
- Revenue, operating income, R&D spending
- Order backlog (where available)
- Segment performance

Tickers:
- CAT (Caterpillar Inc)
- CMI (Cummins Inc)
- MAN Energy Solutions (part of VW group - limited data)
"""

import logging
import os
from datetime import datetime, timezone
from typing import Any, Optional

import httpx

from lead_to_cash.services.competitor_intel.signal_models import CompetitorFinancials

logger = logging.getLogger(__name__)


class EODHDService:
    """
    EODHD API integration for competitor financial data.

    API Endpoints:
    - /fundamentals/{TICKER}.US - Full fundamentals data
    - /eod/{TICKER}.US - End of day prices

    Rate Limits:
    - Depends on subscription plan
    - Default: 100 requests/minute

    Note: MAN Energy Solutions is part of VW group (VWAGY),
    so segment-specific data may be limited.
    """

    # API configuration
    BASE_URL = "https://eodhd.com/api"

    # Competitor ticker mapping
    COMPETITOR_TICKERS = {
        "caterpillar": "CAT.US",
        "cummins": "CMI.US",
        # MAN ES is part of VW group - limited segment data
        "man_energy": None,
    }

    # Competitor names for display
    COMPETITOR_NAMES = {
        "caterpillar": "Caterpillar Inc",
        "cummins": "Cummins Inc",
        "man_energy": "MAN Energy Solutions",
    }

    def __init__(self, api_key: Optional[str] = None):
        """
        Initialize EODHD service.

        Args:
            api_key: EODHD API key. If not provided, uses EODHD_API_KEY env var.
        """
        self.api_key = api_key or os.getenv("EODHD_API_KEY")
        self._client: Optional[httpx.AsyncClient] = None

        if not self.api_key:
            logger.warning(
                "EODHD_API_KEY not configured. Financial data will not be available."
            )

    async def _get_client(self) -> httpx.AsyncClient:
        """Get or create HTTP client."""
        if self._client is None:
            self._client = httpx.AsyncClient(timeout=30.0)
        return self._client

    async def close(self):
        """Close HTTP client."""
        if self._client:
            await self._client.aclose()
            self._client = None

    def is_configured(self) -> bool:
        """Check if service is configured with API key."""
        return self.api_key is not None and len(self.api_key) > 0

    async def _make_request(
        self, endpoint: str, params: Optional[dict] = None
    ) -> Optional[dict]:
        """
        Make API request to EODHD.

        Args:
            endpoint: API endpoint (e.g., /fundamentals/CAT.US)
            params: Additional query parameters

        Returns:
            JSON response or None if failed
        """
        if not self.is_configured():
            logger.warning("EODHD API key not configured")
            return None

        client = await self._get_client()
        url = f"{self.BASE_URL}{endpoint}"

        # Add API key and format
        request_params = {
            "api_token": self.api_key,
            "fmt": "json",
        }
        if params:
            request_params.update(params)

        try:
            response = await client.get(url, params=request_params)

            if response.status_code == 200:
                return response.json()
            elif response.status_code == 401:
                logger.error("EODHD API key is invalid or unauthorized")
                return None
            elif response.status_code == 429:
                logger.warning("EODHD rate limit exceeded")
                return None
            else:
                logger.error(f"EODHD API error: {response.status_code}")
                return None

        except httpx.RequestError as e:
            logger.error(f"EODHD request error: {e}")
            return None

    async def fetch_fundamentals(self, ticker: str) -> Optional[dict]:
        """
        Fetch full fundamentals data for a ticker.

        Args:
            ticker: Stock ticker (e.g., CAT.US)

        Returns:
            Fundamentals data or None
        """
        return await self._make_request(f"/fundamentals/{ticker}")

    async def fetch_quarterly_financials(
        self, competitor: str
    ) -> Optional[CompetitorFinancials]:
        """
        Fetch latest quarterly financial data for a competitor.

        Args:
            competitor: Competitor identifier (caterpillar, cummins, man_energy)

        Returns:
            CompetitorFinancials object or None
        """
        ticker = self.COMPETITOR_TICKERS.get(competitor)
        if not ticker:
            logger.warning(f"No ticker available for {competitor}")
            return None

        data = await self.fetch_fundamentals(ticker)
        if not data:
            return None

        try:
            # Extract financials from response
            financials = data.get("Financials", {})
            income_statement = financials.get("Income_Statement", {}).get(
                "quarterly", {}
            )

            # Get most recent quarter
            if not income_statement:
                logger.warning(f"No quarterly income statement data for {ticker}")
                return None

            # Get the most recent period
            periods = sorted(income_statement.keys(), reverse=True)
            if not periods:
                return None

            latest_period = periods[0]
            latest_data = income_statement[latest_period]

            # Parse report date
            report_date = self._parse_date(latest_period)
            if not report_date:
                report_date = datetime.now(timezone.utc)

            # Extract key metrics
            revenue = self._safe_float(latest_data.get("totalRevenue"))
            operating_income = self._safe_float(latest_data.get("operatingIncome"))
            net_income = self._safe_float(latest_data.get("netIncome"))
            gross_profit = self._safe_float(latest_data.get("grossProfit"))
            rd_spending = self._safe_float(latest_data.get("researchDevelopment"))

            # Calculate margins
            gross_margin = None
            operating_margin = None
            if revenue and revenue > 0:
                if gross_profit:
                    gross_margin = (gross_profit / revenue) * 100
                if operating_income:
                    operating_margin = (operating_income / revenue) * 100

            # Calculate YoY growth if we have prior year data
            revenue_growth_yoy = None
            if len(periods) >= 5:  # Need at least 4 quarters back
                prior_year_period = periods[4]  # ~1 year ago
                prior_data = income_statement.get(prior_year_period, {})
                prior_revenue = self._safe_float(prior_data.get("totalRevenue"))
                if prior_revenue and prior_revenue > 0 and revenue:
                    revenue_growth_yoy = (
                        (revenue - prior_revenue) / prior_revenue
                    ) * 100

            # Calculate QoQ growth
            revenue_growth_qoq = None
            if len(periods) >= 2:
                prior_period = periods[1]
                prior_data = income_statement.get(prior_period, {})
                prior_revenue = self._safe_float(prior_data.get("totalRevenue"))
                if prior_revenue and prior_revenue > 0 and revenue:
                    revenue_growth_qoq = (
                        (revenue - prior_revenue) / prior_revenue
                    ) * 100

            # Format fiscal period (e.g., "Q4 2025")
            fiscal_period = self._format_fiscal_period(latest_period)

            return CompetitorFinancials.create(
                competitor=competitor,
                ticker=ticker,
                period_type="quarterly",
                fiscal_period=fiscal_period,
                report_date=report_date,
                revenue_usd=revenue,
                operating_income_usd=operating_income,
                net_income_usd=net_income,
                rd_spending_usd=rd_spending,
                gross_margin_pct=gross_margin,
                operating_margin_pct=operating_margin,
                revenue_growth_yoy_pct=revenue_growth_yoy,
                revenue_growth_qoq_pct=revenue_growth_qoq,
                source_url=f"https://eodhd.com/financial-apis/fundamentals-api?s={ticker}",
                raw_data=latest_data,
            )

        except Exception as e:
            logger.error(f"Error parsing financials for {competitor}: {e}")
            return None

    async def fetch_annual_financials(
        self, competitor: str
    ) -> Optional[CompetitorFinancials]:
        """
        Fetch latest annual financial data for a competitor.

        Args:
            competitor: Competitor identifier

        Returns:
            CompetitorFinancials object or None
        """
        ticker = self.COMPETITOR_TICKERS.get(competitor)
        if not ticker:
            logger.warning(f"No ticker available for {competitor}")
            return None

        data = await self.fetch_fundamentals(ticker)
        if not data:
            return None

        try:
            financials = data.get("Financials", {})
            income_statement = financials.get("Income_Statement", {}).get("yearly", {})

            if not income_statement:
                return None

            # Get most recent year
            periods = sorted(income_statement.keys(), reverse=True)
            if not periods:
                return None

            latest_period = periods[0]
            latest_data = income_statement[latest_period]

            report_date = self._parse_date(latest_period)
            if not report_date:
                report_date = datetime.now(timezone.utc)

            # Extract metrics
            revenue = self._safe_float(latest_data.get("totalRevenue"))
            operating_income = self._safe_float(latest_data.get("operatingIncome"))
            net_income = self._safe_float(latest_data.get("netIncome"))
            gross_profit = self._safe_float(latest_data.get("grossProfit"))
            rd_spending = self._safe_float(latest_data.get("researchDevelopment"))

            # Margins
            gross_margin = None
            operating_margin = None
            if revenue and revenue > 0:
                if gross_profit:
                    gross_margin = (gross_profit / revenue) * 100
                if operating_income:
                    operating_margin = (operating_income / revenue) * 100

            # YoY growth
            revenue_growth_yoy = None
            if len(periods) >= 2:
                prior_period = periods[1]
                prior_data = income_statement.get(prior_period, {})
                prior_revenue = self._safe_float(prior_data.get("totalRevenue"))
                if prior_revenue and prior_revenue > 0 and revenue:
                    revenue_growth_yoy = (
                        (revenue - prior_revenue) / prior_revenue
                    ) * 100

            fiscal_period = f"FY {latest_period[:4]}"

            return CompetitorFinancials.create(
                competitor=competitor,
                ticker=ticker,
                period_type="annual",
                fiscal_period=fiscal_period,
                report_date=report_date,
                revenue_usd=revenue,
                operating_income_usd=operating_income,
                net_income_usd=net_income,
                rd_spending_usd=rd_spending,
                gross_margin_pct=gross_margin,
                operating_margin_pct=operating_margin,
                revenue_growth_yoy_pct=revenue_growth_yoy,
                source_url=f"https://eodhd.com/financial-apis/fundamentals-api?s={ticker}",
                raw_data=latest_data,
            )

        except Exception as e:
            logger.error(f"Error parsing annual financials for {competitor}: {e}")
            return None

    async def refresh_all_financials(self) -> list[CompetitorFinancials]:
        """
        Refresh financial data for all competitors with available tickers.

        Returns:
            List of CompetitorFinancials objects
        """
        results = []

        for competitor, ticker in self.COMPETITOR_TICKERS.items():
            if not ticker:
                logger.info(f"Skipping {competitor} - no ticker available")
                continue

            logger.info(f"Fetching financials for {competitor} ({ticker})")

            # Fetch quarterly
            quarterly = await self.fetch_quarterly_financials(competitor)
            if quarterly:
                results.append(quarterly)
                logger.info(
                    f"Got quarterly data for {competitor}: {quarterly.fiscal_period}"
                )

            # Fetch annual
            annual = await self.fetch_annual_financials(competitor)
            if annual:
                results.append(annual)
                logger.info(f"Got annual data for {competitor}: {annual.fiscal_period}")

        return results

    async def get_segment_data(self, competitor: str) -> Optional[dict[str, Any]]:
        """
        Try to extract segment-level data for marine/power systems.

        Note: This may not be available for all companies or may require
        manual extraction from SEC filings.

        Args:
            competitor: Competitor identifier

        Returns:
            Segment data dict or None
        """
        ticker = self.COMPETITOR_TICKERS.get(competitor)
        if not ticker:
            return None

        data = await self.fetch_fundamentals(ticker)
        if not data:
            return None

        # Try to find segment data in highlights or other sections
        highlights = data.get("Highlights", {})
        general = data.get("General", {})

        # For Caterpillar, look for "Resource Industries" or "Energy & Transportation"
        # For Cummins, look for "Components" or "Power Systems"

        segment_data = {
            "company": self.COMPETITOR_NAMES.get(competitor, competitor),
            "ticker": ticker,
            "market_cap": highlights.get("MarketCapitalization"),
            "pe_ratio": highlights.get("PERatio"),
            "dividend_yield": highlights.get("DividendYield"),
            "52_week_high": highlights.get("52WeekHigh"),
            "52_week_low": highlights.get("52WeekLow"),
            "description": general.get("Description", "")[:500],
        }

        return segment_data

    def _safe_float(self, value: Any) -> Optional[float]:
        """Safely convert value to float."""
        if value is None:
            return None
        try:
            return float(value)
        except (ValueError, TypeError):
            return None

    def _parse_date(self, date_str: str) -> Optional[datetime]:
        """Parse date string from EODHD format."""
        if not date_str:
            return None

        formats = [
            "%Y-%m-%d",
            "%Y-%m",
            "%Y",
        ]

        for fmt in formats:
            try:
                dt = datetime.strptime(date_str[: len(fmt.replace("%", ""))], fmt)
                return dt.replace(tzinfo=timezone.utc)
            except ValueError:
                continue

        return None

    def _format_fiscal_period(self, period_str: str) -> str:
        """
        Format period string to fiscal period label.

        Args:
            period_str: Date string like "2025-12-31"

        Returns:
            Fiscal period like "Q4 2025"
        """
        try:
            dt = datetime.strptime(period_str[:10], "%Y-%m-%d")
            quarter = (dt.month - 1) // 3 + 1
            return f"Q{quarter} {dt.year}"
        except ValueError:
            return period_str[:10]


# Singleton instance
_service: Optional[EODHDService] = None


def get_eodhd_service() -> EODHDService:
    """Get or create the EODHD service singleton."""
    global _service
    if _service is None:
        _service = EODHDService()
    return _service
