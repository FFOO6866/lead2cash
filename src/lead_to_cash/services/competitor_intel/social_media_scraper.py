"""
Social Media Scraper for Competitor Intelligence

Uses Perplexity API to search for competitor social media mentions:
- LinkedIn company page posts
- Twitter/X official account posts
- YouTube channel videos

This approach avoids the need for official social media API keys
while still capturing relevant competitor intelligence.
"""

import logging
import os
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Optional

import httpx

logger = logging.getLogger(__name__)


@dataclass
class SocialMediaContent:
    """Content discovered from social media via Perplexity search."""

    competitor: str
    platform: str  # linkedin, twitter, youtube
    source_channel: str  # Maps to SourceChannel enum
    headline: str
    content: str
    source_url: str = ""
    published_date: Optional[datetime] = None
    discovered_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    metadata: dict = field(default_factory=dict)


class SocialMediaScraper:
    """
    Social media monitoring using Perplexity API search.

    Uses Perplexity to search for competitor mentions on:
    - LinkedIn company pages
    - Twitter/X official accounts
    - YouTube channels

    This provides a unified approach without needing separate
    API keys for each social platform.
    """

    # Social media account identifiers
    SOCIAL_ACCOUNTS = {
        "caterpillar": {
            "linkedin": "company/caterpillar-inc",
            "twitter": "CaterpillarInc",
            "youtube": "caterpillarinc",
            "display_name": "Caterpillar Inc",
        },
        "cummins": {
            "linkedin": "company/cummins-inc",
            "twitter": "Cummins",
            "youtube": "caborocummins",
            "display_name": "Cummins",
        },
        "man_energy": {
            "linkedin": "company/man-energy-solutions",
            "twitter": "MANEngSolutions",
            "youtube": "MANEnergySolutions",
            "display_name": "MAN Energy Solutions",
        },
    }

    # API configuration
    PERPLEXITY_API_URL = "https://api.perplexity.ai/chat/completions"
    TIMEOUT = 60.0

    def __init__(self, api_key: Optional[str] = None):
        """
        Initialize social media scraper.

        Args:
            api_key: Perplexity API key. If not provided, uses PERPLEXITY_API_KEY env var.
        """
        self.api_key = api_key or os.getenv("PERPLEXITY_API_KEY")
        self._client: Optional[httpx.AsyncClient] = None

        if not self.api_key:
            logger.warning(
                "PERPLEXITY_API_KEY not configured. Social media monitoring will not work."
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

    def is_configured(self) -> bool:
        """Check if service is configured with API key."""
        return self.api_key is not None and len(self.api_key) > 0

    async def _query_perplexity(
        self, prompt: str, system_prompt: Optional[str] = None
    ) -> Optional[dict]:
        """
        Query Perplexity API.

        Args:
            prompt: User prompt
            system_prompt: Optional system prompt

        Returns:
            API response or None
        """
        if not self.is_configured():
            logger.warning("Perplexity API key not configured")
            return None

        client = await self._get_client()

        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})

        try:
            response = await client.post(
                self.PERPLEXITY_API_URL,
                headers={
                    "Authorization": f"Bearer {self.api_key}",
                    "Content-Type": "application/json",
                },
                json={
                    "model": "sonar",
                    "messages": messages,
                    "temperature": 0.2,
                    "return_citations": True,
                },
            )

            if response.status_code == 200:
                return response.json()
            else:
                logger.error(f"Perplexity API error: {response.status_code}")
                return None

        except httpx.RequestError as e:
            logger.error(f"Perplexity request error: {e}")
            return None

    async def search_linkedin_mentions(
        self, competitor: str
    ) -> list[SocialMediaContent]:
        """
        Search for competitor LinkedIn posts and mentions.

        Args:
            competitor: Competitor identifier

        Returns:
            List of social media content items
        """
        if competitor not in self.SOCIAL_ACCOUNTS:
            return []

        account = self.SOCIAL_ACCOUNTS[competitor]
        display_name = account["display_name"]
        linkedin_handle = account["linkedin"]

        prompt = f"""Search for recent LinkedIn posts and announcements from {display_name} ({linkedin_handle}).

Focus on finding:
1. Customer announcements and contract wins
2. Product launches and new engine platforms
3. Partnership announcements
4. Technology updates (dual fuel, methanol, ammonia, hydrogen)
5. Marine and offshore project involvement
6. Event participation (Sea Asia, Nor-Shipping, etc.)

For each post found, provide:
- Post headline/title
- Key content summary
- Any customer or project names mentioned
- Date if available
- LinkedIn post URL if available

Search specifically for marine, offshore, and power systems related content from the past 30 days."""

        system_prompt = """You are a competitive intelligence analyst searching for marine engine competitor activity on LinkedIn.
Focus on business announcements, contract wins, product launches, and technology developments.
Extract specific company names, project names, vessel types, and dates when mentioned.
Prioritize marine and offshore content over general corporate posts."""

        response = await self._query_perplexity(prompt, system_prompt)
        if not response:
            return []

        return self._parse_social_response(response, competitor, "linkedin", "LINKEDIN")

    async def search_twitter_mentions(
        self, competitor: str
    ) -> list[SocialMediaContent]:
        """
        Search for competitor Twitter/X posts and mentions.

        Args:
            competitor: Competitor identifier

        Returns:
            List of social media content items
        """
        if competitor not in self.SOCIAL_ACCOUNTS:
            return []

        account = self.SOCIAL_ACCOUNTS[competitor]
        display_name = account["display_name"]
        twitter_handle = account["twitter"]

        prompt = f"""Search for recent Twitter/X posts and announcements from {display_name} (@{twitter_handle}).

Focus on finding:
1. Contract wins and customer announcements
2. New product announcements
3. Technology demonstrations and fuel transition updates
4. Event participation and trade show announcements
5. Marine and offshore project mentions
6. Partnerships and collaborations

For each tweet/post found, provide:
- Tweet content summary
- Any hashtags used
- Customer or project names mentioned
- Date if available
- Twitter URL if available

Search for marine, offshore, and power systems related tweets from the past 30 days."""

        system_prompt = """You are a competitive intelligence analyst searching for marine engine competitor activity on Twitter/X.
Focus on business announcements, contract wins, and technology news.
Extract specific company names, vessel names, and project details when mentioned.
Prioritize marine and offshore content."""

        response = await self._query_perplexity(prompt, system_prompt)
        if not response:
            return []

        return self._parse_social_response(response, competitor, "twitter", "TWITTER_X")

    async def search_youtube_videos(self, competitor: str) -> list[SocialMediaContent]:
        """
        Search for competitor YouTube videos.

        Args:
            competitor: Competitor identifier

        Returns:
            List of social media content items
        """
        if competitor not in self.SOCIAL_ACCOUNTS:
            return []

        account = self.SOCIAL_ACCOUNTS[competitor]
        display_name = account["display_name"]
        youtube_handle = account["youtube"]

        prompt = f"""Search for recent YouTube videos from {display_name} ({youtube_handle} channel).

Focus on finding:
1. Product launch videos for new engines
2. Technology demonstration videos
3. Customer testimonial videos
4. Sustainability and fuel transition content
5. Trade show and event coverage
6. Marine and offshore application videos

For each video found, provide:
- Video title
- Brief description of content
- Products or technologies featured
- Customer names if mentioned
- Upload date if available
- YouTube URL

Search for marine, offshore, and power systems related videos from the past 90 days."""

        system_prompt = """You are a competitive intelligence analyst searching for marine engine competitor videos on YouTube.
Focus on product launches, technology demonstrations, and customer case studies.
Extract engine models, fuel types, and customer names when mentioned.
Prioritize marine propulsion and offshore power system content."""

        response = await self._query_perplexity(prompt, system_prompt)
        if not response:
            return []

        return self._parse_social_response(response, competitor, "youtube", "YOUTUBE")

    def _parse_social_response(
        self,
        response: dict,
        competitor: str,
        platform: str,
        source_channel: str,
    ) -> list[SocialMediaContent]:
        """
        Parse Perplexity response into social media content items.

        Args:
            response: Perplexity API response
            competitor: Competitor identifier
            platform: Social platform name
            source_channel: SourceChannel enum value

        Returns:
            List of SocialMediaContent items
        """
        results = []

        try:
            content = response["choices"][0]["message"]["content"]
            citations = response.get("citations", [])

            # Extract source URLs from citations
            source_urls = []
            for c in citations:
                if isinstance(c, str):
                    source_urls.append(c)
                elif isinstance(c, dict):
                    source_urls.append(c.get("url", ""))

            # Create a single content item with the full response
            # (Perplexity returns synthesized content, not individual posts)
            results.append(
                SocialMediaContent(
                    competitor=competitor,
                    platform=platform,
                    source_channel=source_channel,
                    headline=f"{self.SOCIAL_ACCOUNTS[competitor]['display_name']} - {platform.title()} Activity",
                    content=content,
                    source_url=source_urls[0] if source_urls else "",
                    metadata={
                        "all_sources": source_urls[:5],
                        "platform": platform,
                    },
                )
            )

        except (KeyError, IndexError) as e:
            logger.error(f"Error parsing Perplexity response: {e}")

        return results

    async def search_all_platforms(self, competitor: str) -> list[SocialMediaContent]:
        """
        Search all social platforms for a competitor.

        Args:
            competitor: Competitor identifier

        Returns:
            Combined list from all platforms
        """
        results = []

        # LinkedIn
        linkedin = await self.search_linkedin_mentions(competitor)
        results.extend(linkedin)
        logger.info(f"Found {len(linkedin)} LinkedIn items for {competitor}")

        # Twitter
        twitter = await self.search_twitter_mentions(competitor)
        results.extend(twitter)
        logger.info(f"Found {len(twitter)} Twitter items for {competitor}")

        # YouTube
        youtube = await self.search_youtube_videos(competitor)
        results.extend(youtube)
        logger.info(f"Found {len(youtube)} YouTube items for {competitor}")

        return results

    async def search_all_competitors(self) -> list[SocialMediaContent]:
        """
        Search all social platforms for all competitors.

        Returns:
            Combined list from all competitors and platforms
        """
        results = []

        for competitor in self.SOCIAL_ACCOUNTS.keys():
            logger.info(f"Searching social media for {competitor}")
            items = await self.search_all_platforms(competitor)
            results.extend(items)

        return results

    async def search_competitor_news(
        self, competitor: str, topic: Optional[str] = None
    ) -> list[SocialMediaContent]:
        """
        Search for general news and social mentions of a competitor.

        Args:
            competitor: Competitor identifier
            topic: Optional topic focus (e.g., "contract wins", "product launches")

        Returns:
            List of social media content items
        """
        if competitor not in self.SOCIAL_ACCOUNTS:
            return []

        display_name = self.SOCIAL_ACCOUNTS[competitor]["display_name"]

        topic_focus = f"focusing on {topic}" if topic else "recent activity"

        prompt = f"""Search for the latest news and social media mentions of {display_name} marine engines and power systems, {topic_focus}.

Include:
1. News articles mentioning {display_name} marine products
2. Social media posts about contract wins or deliveries
3. Industry coverage of {display_name} technology
4. Mentions in marine trade publications

For each item, provide:
- Headline/title
- Key content
- Source (news site, social platform)
- Date if available
- URL

Focus on marine, offshore, and power systems. Past 30 days."""

        response = await self._query_perplexity(prompt)
        if not response:
            return []

        return self._parse_social_response(response, competitor, "news", "PERPLEXITY")


# Singleton instance
_scraper: Optional[SocialMediaScraper] = None


def get_social_media_scraper() -> SocialMediaScraper:
    """Get or create the social media scraper singleton."""
    global _scraper
    if _scraper is None:
        _scraper = SocialMediaScraper()
    return _scraper
