"""
Signal Extractor for Competitor Intelligence

Kaizen-style agent for extracting structured signals from raw content.
Uses LLM for intelligent entity extraction and classification.
"""

import json
import logging
import os
from typing import Optional

import httpx

from lead_to_cash.services.competitor_intel.keyword_detector import get_keyword_detector
from lead_to_cash.services.competitor_intel.signal_models import (
    CompetitorSignal,
    SourceChannel,
)
from lead_to_cash.services.competitor_intel.signal_scorer import get_signal_scorer
from lead_to_cash.services.competitor_intel.social_media_scraper import (
    SocialMediaContent,
)
from lead_to_cash.services.competitor_intel.targeted_web_scraper import ScrapedContent

logger = logging.getLogger(__name__)


class SignalExtractor:
    """
    Extracts structured competitor intelligence signals from raw content.

    Uses a combination of:
    - Keyword detection for initial classification
    - LLM-based entity extraction for complex content
    - Scoring algorithm for prioritization

    Processes content from:
    - Web scraper (newsroom, product pages, insights)
    - Social media scraper (LinkedIn, Twitter, YouTube via Perplexity)
    - EODHD financial data
    """

    # OpenAI/LLM configuration
    OPENAI_API_URL = "https://api.openai.com/v1/chat/completions"
    DEFAULT_MODEL = os.getenv("OPENAI_MINI_MODEL", "gpt-4o-mini")
    TIMEOUT = 60.0

    # Extraction prompt template
    EXTRACTION_PROMPT = """Analyze the following competitor content and extract structured intelligence.

COMPETITOR: {competitor}
SOURCE: {source_channel}
CONTENT:
{content}

Extract the following information in JSON format:

{{
    "signal_type": "One of: CONTRACT_WIN, CUSTOMER_ANNOUNCEMENT, PRODUCT_LAUNCH, TECHNOLOGY_POV, THOUGHT_LEADERSHIP, EVENT_MARKETING, PARTNERSHIP, REGULATORY_POSITIONING",
    "headline": "Concise headline summarizing the key point (max 100 chars)",
    "description": "Detailed description of the intelligence (2-3 sentences)",
    "customer_mentioned": "Customer/company name if mentioned, null otherwise",
    "project_name": "Project or vessel name if mentioned, null otherwise",
    "vessel_type": "Type of vessel if mentioned (ferry, OSV, tug, FPSO, etc.), null otherwise",
    "engine_model": "Engine model or product line if mentioned, null otherwise",
    "fuel_type": "Fuel type if mentioned (diesel, LNG, dual_fuel, methanol, ammonia, hydrogen), null otherwise",
    "contract_value_usd": "Contract value in USD if mentioned, null otherwise (number only)",
    "region": "Geographic region if mentioned, null otherwise",
    "country": "Specific country if mentioned, null otherwise",
    "is_marine_relevant": true/false,
    "confidence_score": 0.0-1.0 (confidence in extraction accuracy)
}}

Focus on marine engines, offshore power systems, and fuel transition technologies.
If the content is not relevant to marine/offshore, set is_marine_relevant to false.
Return ONLY valid JSON, no other text."""

    def __init__(self, api_key: Optional[str] = None, model: Optional[str] = None):
        """
        Initialize signal extractor.

        Args:
            api_key: OpenAI API key. Uses OPENAI_API_KEY env var if not provided.
            model: LLM model to use. Defaults to gpt-4o-mini.
        """
        self.api_key = api_key or os.getenv("OPENAI_API_KEY")
        self.model = model or self.DEFAULT_MODEL
        self._client: Optional[httpx.AsyncClient] = None
        self._keyword_detector = get_keyword_detector()
        self._scorer = get_signal_scorer()

        if not self.api_key:
            logger.warning(
                "OPENAI_API_KEY not configured. LLM extraction will not be available."
            )

    async def _get_client(self) -> httpx.AsyncClient:
        """Get or create HTTP client."""
        if self._client is None:
            self._client = httpx.AsyncClient(timeout=self.TIMEOUT)
        return self._client

    async def close(self):
        """Close HTTP client."""
        if self._client:
            await self._client.aclose()
            self._client = None

    def is_llm_configured(self) -> bool:
        """Check if LLM is configured."""
        return self.api_key is not None and len(self.api_key) > 0

    async def _call_llm(self, prompt: str) -> Optional[str]:
        """
        Call OpenAI API for extraction.

        Args:
            prompt: Extraction prompt

        Returns:
            LLM response or None
        """
        if not self.is_llm_configured():
            return None

        client = await self._get_client()

        try:
            response = await client.post(
                self.OPENAI_API_URL,
                headers={
                    "Authorization": f"Bearer {self.api_key}",
                    "Content-Type": "application/json",
                },
                json={
                    "model": self.model,
                    "messages": [
                        {
                            "role": "system",
                            "content": "You are a competitive intelligence analyst specializing in marine engines and power systems. Extract structured data from competitor content.",
                        },
                        {"role": "user", "content": prompt},
                    ],
                    "temperature": 0.1,
                    "response_format": {"type": "json_object"},
                },
            )

            if response.status_code == 200:
                data = response.json()
                return data["choices"][0]["message"]["content"]
            else:
                logger.error(f"OpenAI API error: {response.status_code}")
                return None

        except httpx.RequestError as e:
            logger.error(f"OpenAI request error: {e}")
            return None

    def _extract_with_keywords(
        self, content: str, competitor: str, source_channel: str
    ) -> CompetitorSignal:
        """
        Extract signal using keyword detection only (fallback).

        Args:
            content: Raw content
            competitor: Competitor identifier
            source_channel: Source channel

        Returns:
            CompetitorSignal with keyword-based extraction
        """
        detection = self._keyword_detector.detect(content)

        # Suggest signal type
        signal_type = detection.suggest_signal_type()

        # Extract title (first line or first 100 chars)
        lines = content.strip().split("\n")
        headline = lines[0][:100] if lines else content[:100]

        # Create signal
        signal = CompetitorSignal.create(
            competitor=competitor,
            signal_type=signal_type,
            source_channel=source_channel,
            headline=headline,
            description=content[:500] if len(content) > 500 else content,
            raw_content=content,
            is_apac=detection.is_apac_relevant(),
            is_singapore=detection.is_singapore_relevant(),
            keywords_matched=detection.all_matches,
            fuel_type=self._keyword_detector.extract_fuel_type(content),
            vessel_type=self._keyword_detector.extract_vessel_type(content),
        )

        # Score the signal
        self._scorer.score_and_update_signal(signal)

        return signal

    async def extract_signal(
        self,
        content: str,
        competitor: str,
        source_channel: str,
        source_url: str = "",
        use_llm: bool = True,
    ) -> CompetitorSignal:
        """
        Extract a structured signal from raw content.

        Args:
            content: Raw content to analyze
            competitor: Competitor identifier
            source_channel: Source channel (website_newsroom, linkedin, etc.)
            source_url: Source URL
            use_llm: Whether to use LLM for extraction

        Returns:
            CompetitorSignal with extracted data
        """
        # Try LLM extraction first if configured
        if use_llm and self.is_llm_configured():
            prompt = self.EXTRACTION_PROMPT.format(
                competitor=competitor,
                source_channel=source_channel,
                content=content[:3000],  # Limit content length
            )

            llm_response = await self._call_llm(prompt)

            if llm_response:
                try:
                    extracted = json.loads(llm_response)

                    signal = CompetitorSignal.create(
                        competitor=competitor,
                        signal_type=extracted.get("signal_type", "THOUGHT_LEADERSHIP"),
                        source_channel=source_channel,
                        headline=extracted.get("headline", content[:100]),
                        description=extracted.get("description", ""),
                        raw_content=content,
                        customer_mentioned=extracted.get("customer_mentioned"),
                        project_name=extracted.get("project_name"),
                        vessel_type=extracted.get("vessel_type"),
                        engine_model=extracted.get("engine_model"),
                        fuel_type=extracted.get("fuel_type"),
                        contract_value_usd=extracted.get("contract_value_usd"),
                        region=extracted.get("region"),
                        country=extracted.get("country"),
                        source_url=source_url,
                        metadata={
                            "extraction_method": "llm",
                            "confidence": extracted.get("confidence_score", 0.5),
                            "is_marine_relevant": extracted.get(
                                "is_marine_relevant", True
                            ),
                        },
                    )

                    # Score the signal
                    self._scorer.score_and_update_signal(signal)

                    return signal

                except json.JSONDecodeError as e:
                    logger.warning(f"Failed to parse LLM response: {e}")

        # Fallback to keyword-based extraction
        signal = self._extract_with_keywords(content, competitor, source_channel)
        signal.source_url = source_url
        signal.metadata["extraction_method"] = "keywords"

        return signal

    async def extract_from_scraped_content(
        self, scraped: ScrapedContent, use_llm: bool = True
    ) -> CompetitorSignal:
        """
        Extract signal from ScrapedContent (web scraper output).

        Args:
            scraped: ScrapedContent from targeted web scraper
            use_llm: Whether to use LLM

        Returns:
            CompetitorSignal
        """
        # Map source channel
        channel_map = {
            "website_newsroom": SourceChannel.WEBSITE_NEWSROOM.value,
            "website_product": SourceChannel.WEBSITE_PRODUCT.value,
            "website_insights": SourceChannel.WEBSITE_INSIGHTS.value,
        }
        source_channel = channel_map.get(
            scraped.source_channel, SourceChannel.WEBSITE_NEWSROOM.value
        )

        signal = await self.extract_signal(
            content=f"{scraped.title}\n\n{scraped.content}",
            competitor=scraped.competitor,
            source_channel=source_channel,
            source_url=scraped.url,
            use_llm=use_llm,
        )

        # Preserve scraped metadata
        if scraped.published_date:
            signal.published_date = scraped.published_date

        return signal

    async def extract_from_social_content(
        self, social: SocialMediaContent, use_llm: bool = True
    ) -> CompetitorSignal:
        """
        Extract signal from SocialMediaContent.

        Args:
            social: SocialMediaContent from social media scraper
            use_llm: Whether to use LLM

        Returns:
            CompetitorSignal
        """
        # Map source channel
        channel_map = {
            "LINKEDIN": SourceChannel.LINKEDIN.value,
            "TWITTER_X": SourceChannel.TWITTER_X.value,
            "YOUTUBE": SourceChannel.YOUTUBE.value,
            "PERPLEXITY": SourceChannel.PERPLEXITY.value,
        }
        source_channel = channel_map.get(
            social.source_channel, SourceChannel.PERPLEXITY.value
        )

        signal = await self.extract_signal(
            content=f"{social.headline}\n\n{social.content}",
            competitor=social.competitor,
            source_channel=source_channel,
            source_url=social.source_url,
            use_llm=use_llm,
        )

        # Preserve social metadata
        if social.published_date:
            signal.published_date = social.published_date
        signal.metadata["platform"] = social.platform

        return signal

    async def batch_extract(
        self,
        contents: list[tuple[str, str, str, str]],
        use_llm: bool = True,
    ) -> list[CompetitorSignal]:
        """
        Extract signals from multiple content items.

        Args:
            contents: List of (content, competitor, source_channel, source_url) tuples
            use_llm: Whether to use LLM

        Returns:
            List of CompetitorSignals
        """
        signals = []

        for content, competitor, source_channel, source_url in contents:
            try:
                signal = await self.extract_signal(
                    content=content,
                    competitor=competitor,
                    source_channel=source_channel,
                    source_url=source_url,
                    use_llm=use_llm,
                )
                signals.append(signal)
            except Exception as e:
                logger.error(f"Error extracting signal: {e}")
                continue

        return signals


# Singleton instance
_extractor: Optional[SignalExtractor] = None


def get_signal_extractor() -> SignalExtractor:
    """Get or create the signal extractor singleton."""
    global _extractor
    if _extractor is None:
        _extractor = SignalExtractor()
    return _extractor
