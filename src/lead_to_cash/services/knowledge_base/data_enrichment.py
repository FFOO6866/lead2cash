"""
Marine Engine Knowledge Base - LLM-Powered Data Enrichment

Uses LLM to:
1. Fetch and parse manufacturer datasheets from official sources
2. Extract detailed engine specifications
3. Compare and validate data across sources
4. Populate the database with verified information

Source URLs (from requirements):
- Wärtsilä: https://www.wartsila.com/marine/products/engines
- MAN: https://www.man-es.com/marine/products/engines
- Caterpillar/MaK: https://www.cat.com, https://www.mak-cat.com
- Hyundai HiMSEN: https://www.hyundai-engine.com
- Bergen: https://www.bergenengines.com
- Daihatsu: https://www.dhtd.co.jp/en/products
- Niigata: https://www.niigata-power.com
- ABC: https://www.abc-engines.com

Features:
- Circuit breaker for OpenAI API protection
- Retry with exponential backoff for transient failures
"""

import asyncio
import json
import uuid
from dataclasses import dataclass
from typing import Any, Optional

import httpx
from bs4 import BeautifulSoup

from lead_to_cash.config import config
from lead_to_cash.services.knowledge_base.database import (
    KnowledgeBaseDatabase,
    get_knowledge_base_db,
)
from lead_to_cash.services.knowledge_base.models import (
    EngineModel,
)
from lead_to_cash.utils.logging import get_logger
from lead_to_cash.utils.resilience import (
    CircuitBreaker,
    DistributedCircuitBreaker,
    RedisRateLimiter,
    retry_with_backoff,
)

# Use structured logger with correlation ID support
logger = get_logger(__name__)


# =============================================================================
# SOURCE CONFIGURATION
# =============================================================================

MANUFACTURER_SOURCES = {
    "Wärtsilä": {
        "base_url": "https://www.wartsila.com",
        "product_pages": [
            "/marine/products/engines-and-generating-sets/wartsila-31",
            "/marine/products/engines-and-generating-sets/wartsila-46f",
        ],
        "pdf_patterns": [r"\.pdf$", r"project-guide", r"product-guide"],
    },
    "MAN Energy Solutions": {
        "base_url": "https://www.man-es.com",
        "product_pages": [
            "/marine/products/four-stroke-engines/32-44cr",
            "/marine/products/four-stroke-engines/48-60cr",
        ],
        "pdf_patterns": [r"\.pdf$", r"project-guide"],
    },
    "Caterpillar MaK": {
        "base_url": "https://www.cat.com",
        "alt_url": "https://www.mak-cat.com",
        "product_pages": [
            "/en_US/products/new/power-systems/marine-power-systems/commercial-propulsion-engines",
        ],
        "pdf_patterns": [r"\.pdf$", r"spec-sheet"],
    },
    "HD Hyundai HiMSEN": {
        "base_url": "https://www.hyundai-engine.com",
        "product_pages": [
            "/en/product/engine",
        ],
        "pdf_patterns": [r"\.pdf$", r"catalogue"],
    },
    "Bergen Engines": {
        "base_url": "https://www.bergenengines.com",
        "product_pages": [
            "/products/marine/",
        ],
        "pdf_patterns": [r"\.pdf$", r"datasheet"],
    },
}


@dataclass
class ExtractedSpec:
    """Specification extracted from source."""

    model_name: str
    rpm_min: Optional[int] = None
    rpm_max: Optional[int] = None
    power_min_kw: Optional[float] = None
    power_max_kw: Optional[float] = None
    cylinders: Optional[int] = None
    configuration: Optional[str] = None
    displacement_liters: Optional[float] = None
    fuel_types: Optional[list[str]] = None
    dry_weight_kg: Optional[float] = None
    length_mm: Optional[float] = None
    width_mm: Optional[float] = None
    height_mm: Optional[float] = None
    emission_tier: Optional[str] = None
    source_url: Optional[str] = None
    confidence: float = 0.8

    def to_dict(self) -> dict:
        """Convert to dictionary."""
        return {
            "model_name": self.model_name,
            "rpm_min": self.rpm_min,
            "rpm_max": self.rpm_max,
            "power_min_kw": self.power_min_kw,
            "power_max_kw": self.power_max_kw,
            "cylinders": self.cylinders,
            "configuration": self.configuration,
            "displacement_liters": self.displacement_liters,
            "fuel_types": self.fuel_types,
            "dry_weight_kg": self.dry_weight_kg,
            "length_mm": self.length_mm,
            "width_mm": self.width_mm,
            "height_mm": self.height_mm,
            "emission_tier": self.emission_tier,
            "source_url": self.source_url,
            "confidence": self.confidence,
        }


class DataEnrichmentService:
    """
    LLM-powered data enrichment for marine engine specifications.

    Uses OpenAI to:
    1. Parse web pages and PDFs from manufacturer sites
    2. Extract structured specifications
    3. Compare and validate data
    4. Update the knowledge base

    Usage:
        service = DataEnrichmentService()
        await service.initialize()

        # Enrich single manufacturer
        specs = await service.enrich_manufacturer("Wärtsilä")

        # Enrich all manufacturers
        results = await service.enrich_all()

        # Update database with enriched data
        await service.update_database(specs)
    """

    EXTRACTION_PROMPT = """You are an expert at extracting marine engine specifications from technical documents.

Extract the following information for each engine model mentioned:
- Model name (exact designation)
- RPM range (min and max operating speed)
- Power range in kW (min and max output)
- Number of cylinders
- Configuration (V, inline, L)
- Displacement in liters
- Fuel types supported (diesel, gas, dual-fuel, LNG, HFO)
- Dry weight in kg
- Dimensions (length, width, height in mm)
- Emission tier (IMO Tier II, IMO Tier III, EPA Tier 4)

Return the data as a JSON array with the following structure:
```json
[
  {
    "model_name": "Model X",
    "rpm_min": 500,
    "rpm_max": 600,
    "power_min_kw": 5000,
    "power_max_kw": 10000,
    "cylinders": 12,
    "configuration": "V",
    "displacement_liters": 150.5,
    "fuel_types": ["diesel", "gas"],
    "dry_weight_kg": 45000,
    "length_mm": 8500,
    "width_mm": 2200,
    "height_mm": 4500,
    "emission_tier": "IMO Tier III"
  }
]
```

If a value is not available or unclear, use null.
Only include models in the medium-speed range (300-1000 RPM) with power 700-40,000 kW.

Document content:
{content}
"""

    COMPARISON_PROMPT = """You are comparing marine engine specifications from multiple sources.

Given the following specifications for the same engine model from different sources,
determine the most accurate values and explain any discrepancies.

Source 1 ({source1}):
{spec1}

Source 2 ({source2}):
{spec2}

Return a JSON object with:
1. "merged_spec": The best values from both sources
2. "confidence": Overall confidence (0-1) in the merged data
3. "discrepancies": List of fields with different values and which source is likely correct
4. "notes": Any important observations

Example:
```json
{{
  "merged_spec": {{...}},
  "confidence": 0.9,
  "discrepancies": [
    {{"field": "power_max_kw", "source1_value": 10000, "source2_value": 10400, "preferred": "source2", "reason": "Source 2 is more recent datasheet"}}
  ],
  "notes": "Source 2 appears to be from 2024, while Source 1 is from 2022"
}}
```
"""

    def __init__(
        self,
        api_key: Optional[str] = None,
        db: Optional[KnowledgeBaseDatabase] = None,
    ):
        """Initialize data enrichment service."""
        # Load from config
        kb_config = config.knowledge_base

        self.api_key = api_key or kb_config.openai_api_key
        if not self.api_key:
            raise ValueError("OPENAI_API_KEY environment variable not set")

        # Config values
        self._model = kb_config.openai_model
        self._max_content_chars = kb_config.max_content_chars
        self._extraction_temperature = kb_config.extraction_temperature
        self._api_timeout = kb_config.api_timeout
        self._enrichment_timeout = kb_config.enrichment_timeout

        self._db = db
        self._client: Optional[Any] = None
        self._http_client: Optional[httpx.AsyncClient] = None
        self._initialized = False

        # Distributed circuit breaker (uses Redis if available, falls back to local)
        self._circuit_breaker: DistributedCircuitBreaker | CircuitBreaker = (
            DistributedCircuitBreaker(
                name="kb_enrichment_openai",
                redis_url=kb_config.redis_url,
                failure_threshold=kb_config.circuit_failure_threshold,
                recovery_timeout=kb_config.circuit_recovery_timeout,
                half_open_max_calls=kb_config.circuit_half_open_calls,
            )
        )

        # Real rate limiter (uses Redis if available)
        self._rate_limiter: Optional[RedisRateLimiter] = None
        if kb_config.redis_url:
            self._rate_limiter = RedisRateLimiter(
                redis_url=kb_config.redis_url,
                requests_per_window=kb_config.rate_limit_requests,
                window_seconds=kb_config.rate_limit_window_seconds,
                key_prefix="ratelimit:kb_enrichment:",
            )

    async def initialize(self) -> None:
        """Initialize OpenAI client, database, and resilience components."""
        if self._initialized:
            return

        import openai

        self._client = openai.AsyncOpenAI(api_key=self.api_key)
        self._http_client = httpx.AsyncClient(
            timeout=self._api_timeout,
            follow_redirects=True,
            headers={
                "User-Agent": "Mozilla/5.0 (compatible; MarineEngineKB/1.0; +https://rr.kailash.ai)"
            },
        )

        if self._db is None:
            self._db = get_knowledge_base_db()
            await self._db.initialize()

        # Initialize distributed circuit breaker
        await self._circuit_breaker.initialize()

        # Initialize rate limiter if available
        if self._rate_limiter:
            await self._rate_limiter.initialize()

        self._initialized = True
        cb_mode = (
            "distributed"
            if getattr(self._circuit_breaker, "is_distributed", False)
            else "local"
        )
        rl_mode = (
            "Redis"
            if (self._rate_limiter and self._rate_limiter.is_available)
            else "disabled"
        )
        logger.info(
            f"Data enrichment service initialized (circuit_breaker={cb_mode}, rate_limiter={rl_mode})"
        )

    async def close(self) -> None:
        """Close HTTP client."""
        if self._http_client:
            await self._http_client.aclose()

    async def fetch_page(self, url: str) -> Optional[str]:
        """Fetch and parse a web page."""
        try:
            response = await self._http_client.get(url)
            response.raise_for_status()

            soup = BeautifulSoup(response.text, "html.parser")

            # Remove script and style elements
            for script in soup(["script", "style", "nav", "footer", "header"]):
                script.decompose()

            # Get text content
            text = soup.get_text(separator="\n", strip=True)

            # Clean up whitespace
            lines = [line.strip() for line in text.split("\n") if line.strip()]
            return "\n".join(lines)

        except Exception as e:
            logger.error(f"Failed to fetch {url}: {e}")
            return None

    async def extract_specs_from_content(
        self, content: str, source_url: str
    ) -> list[ExtractedSpec]:
        """Use LLM to extract specifications from content.

        Features:
        - Distributed circuit breaker protection for OpenAI API
        - Real rate limiting via Redis (if available)
        - Retry with exponential backoff for transient failures
        - Configurable model, temperature, and content limits
        """
        if not content or len(content) < 100:
            return []

        # Check circuit breaker (async for distributed)
        can_execute = await self._circuit_breaker.can_execute()
        if not can_execute:
            state = await self._circuit_breaker.get_state()
            logger.warning(f"OpenAI API circuit breaker is open (state={state})")
            return []

        # Rate limiting (if Redis available)
        if self._rate_limiter and self._rate_limiter.is_available:
            allowed = await self._rate_limiter.acquire()
            if not allowed:
                logger.warning("Rate limit exceeded for KB enrichment API")
                return []

        # Truncate if too long (from config)
        if len(content) > self._max_content_chars:
            content = content[: self._max_content_chars] + "\n...[truncated]"

        async def _call_api():
            response = await self._client.chat.completions.create(
                model=self._model,
                messages=[
                    {
                        "role": "system",
                        "content": "You are an expert at extracting structured data from technical documents. Always return valid JSON.",
                    },
                    {
                        "role": "user",
                        "content": self.EXTRACTION_PROMPT.format(content=content),
                    },
                ],
                temperature=self._extraction_temperature,
                response_format={"type": "json_object"},
            )
            return response

        try:
            # Retry with exponential backoff
            response = await retry_with_backoff(
                _call_api,
                max_retries=3,
                base_delay=1.0,
                max_delay=10.0,
            )
            await self._circuit_breaker.record_success()

            result = response.choices[0].message.content

            # Parse JSON
            data = json.loads(result)

            # Handle both array and object with "engines" key
            specs_data = data if isinstance(data, list) else data.get("engines", [])

            specs = []
            for s in specs_data:
                spec = ExtractedSpec(
                    model_name=s.get("model_name", "Unknown"),
                    rpm_min=s.get("rpm_min"),
                    rpm_max=s.get("rpm_max"),
                    power_min_kw=s.get("power_min_kw"),
                    power_max_kw=s.get("power_max_kw"),
                    cylinders=s.get("cylinders"),
                    configuration=s.get("configuration"),
                    displacement_liters=s.get("displacement_liters"),
                    fuel_types=s.get("fuel_types"),
                    dry_weight_kg=s.get("dry_weight_kg"),
                    length_mm=s.get("length_mm"),
                    width_mm=s.get("width_mm"),
                    height_mm=s.get("height_mm"),
                    emission_tier=s.get("emission_tier"),
                    source_url=source_url,
                    confidence=0.85,
                )
                specs.append(spec)

            logger.info(f"Extracted {len(specs)} specs from {source_url}")
            return specs

        except Exception as e:
            await self._circuit_breaker.record_failure()
            logger.error(f"LLM extraction failed: {e}")
            return []

    async def enrich_manufacturer(self, manufacturer_name: str) -> list[ExtractedSpec]:
        """
        Enrich data for a specific manufacturer.

        Fetches product pages, extracts specs using LLM, and returns
        structured specifications.
        """
        if not self._initialized:
            await self.initialize()

        source_config = MANUFACTURER_SOURCES.get(manufacturer_name)
        if not source_config:
            logger.warning(f"No source config for manufacturer: {manufacturer_name}")
            return []

        all_specs = []
        base_url = source_config["base_url"]

        for page_path in source_config.get("product_pages", []):
            url = f"{base_url}{page_path}"
            logger.info(f"Fetching {url}")

            content = await self.fetch_page(url)
            if content:
                specs = await self.extract_specs_from_content(content, url)
                all_specs.extend(specs)

        logger.info(f"Enriched {len(all_specs)} specs for {manufacturer_name}")
        return all_specs

    async def enrich_all(self) -> dict[str, list[ExtractedSpec]]:
        """
        Enrich data for all configured manufacturers.

        Returns:
            Dict mapping manufacturer name to list of extracted specs
        """
        if not self._initialized:
            await self.initialize()

        results = {}

        for manufacturer_name in MANUFACTURER_SOURCES:
            try:
                specs = await self.enrich_manufacturer(manufacturer_name)
                results[manufacturer_name] = specs
            except Exception as e:
                logger.error(f"Failed to enrich {manufacturer_name}: {e}")
                results[manufacturer_name] = []

        return results

    async def compare_specs(
        self,
        spec1: ExtractedSpec,
        spec2: ExtractedSpec,
        source1_name: str = "Source 1",
        source2_name: str = "Source 2",
    ) -> dict:
        """
        Compare two specifications for the same model using LLM.

        Returns merged spec with confidence and discrepancy notes.

        Features:
        - Distributed circuit breaker protection for OpenAI API
        - Real rate limiting via Redis (if available)
        - Retry with exponential backoff for transient failures
        """
        if not self._initialized:
            await self.initialize()

        # Check circuit breaker (async for distributed)
        can_execute = await self._circuit_breaker.can_execute()
        if not can_execute:
            state = await self._circuit_breaker.get_state()
            logger.warning(f"OpenAI API circuit breaker is open (state={state})")
            return {
                "merged_spec": spec1.to_dict(),
                "confidence": 0.5,
                "discrepancies": [],
                "notes": "Circuit breaker open - using first spec as fallback",
            }

        # Rate limiting (if Redis available)
        if self._rate_limiter and self._rate_limiter.is_available:
            allowed = await self._rate_limiter.acquire()
            if not allowed:
                logger.warning("Rate limit exceeded for KB enrichment API")
                return {
                    "merged_spec": spec1.to_dict(),
                    "confidence": 0.5,
                    "discrepancies": [],
                    "notes": "Rate limited - using first spec as fallback",
                }

        async def _call_api():
            response = await self._client.chat.completions.create(
                model=self._model,
                messages=[
                    {
                        "role": "system",
                        "content": "You are an expert at validating and merging technical specifications. Always return valid JSON.",
                    },
                    {
                        "role": "user",
                        "content": self.COMPARISON_PROMPT.format(
                            source1=source1_name,
                            source2=source2_name,
                            spec1=json.dumps(spec1.to_dict(), indent=2),
                            spec2=json.dumps(spec2.to_dict(), indent=2),
                        ),
                    },
                ],
                temperature=self._extraction_temperature,
                response_format={"type": "json_object"},
            )
            return response

        try:
            # Retry with exponential backoff
            response = await retry_with_backoff(
                _call_api,
                max_retries=3,
                base_delay=1.0,
                max_delay=10.0,
            )
            await self._circuit_breaker.record_success()

            result = json.loads(response.choices[0].message.content)
            return result

        except Exception as e:
            await self._circuit_breaker.record_failure()
            logger.error(f"Comparison failed: {e}")
            # Return first spec as fallback
            return {
                "merged_spec": spec1.to_dict(),
                "confidence": 0.7,
                "discrepancies": [],
                "notes": f"Comparison failed: {e}",
            }

    async def update_database(self, specs: list[ExtractedSpec], series_id: str) -> int:
        """
        Update database with enriched specifications.

        Args:
            specs: List of extracted specifications
            series_id: ID of the engine series to associate models with

        Returns:
            Count of updated/created models
        """
        if not self._initialized:
            await self.initialize()

        count = 0

        for spec in specs:
            model = EngineModel(
                id=str(uuid.uuid4()),
                series_id=series_id,
                model_name=spec.model_name,
                rpm_min=spec.rpm_min,
                rpm_max=spec.rpm_max,
                power_min_kw=spec.power_min_kw,
                power_max_kw=spec.power_max_kw,
                cylinders=spec.cylinders,
                configuration=spec.configuration,
                displacement_liters=spec.displacement_liters,
                fuel_types=json.dumps(spec.fuel_types) if spec.fuel_types else None,
                dry_weight_kg=spec.dry_weight_kg,
                length_mm=spec.length_mm,
                width_mm=spec.width_mm,
                height_mm=spec.height_mm,
                emission_tier=spec.emission_tier,
                is_current_production=True,
                data_source=spec.source_url,
                data_confidence=spec.confidence,
            )

            try:
                await self._db.create_engine_model(model)
                count += 1
            except Exception as e:
                logger.error(f"Failed to create model {spec.model_name}: {e}")

        logger.info(f"Updated {count} engine models in database")
        return count

    async def health_check(self) -> dict:
        """Check service health.

        Returns:
            Health status with service_id, status, component availability,
            and circuit breaker state.
        """
        from datetime import datetime, timezone

        openai_ok = self._client is not None
        http_ok = self._http_client is not None

        # Get circuit breaker state
        cb_state = await self._circuit_breaker.get_state()
        cb_is_open = cb_state == "OPEN"

        # Determine overall status
        if not self._initialized:
            status = "unhealthy"
        elif cb_is_open:
            status = "degraded"  # Circuit breaker is open
        elif openai_ok and http_ok:
            status = "healthy"
        elif openai_ok:
            status = "degraded"  # OpenAI ok but no HTTP client
        else:
            status = "degraded"  # Initialized but no OpenAI

        return {
            "service_id": "kb_data_enrichment",
            "status": status,
            "initialized": self._initialized,
            "openai_available": openai_ok,
            "http_client_available": http_ok,
            "sources_configured": len(MANUFACTURER_SOURCES),
            "circuit_breaker": {
                "state": cb_state,
                "is_distributed": getattr(
                    self._circuit_breaker, "is_distributed", False
                ),
            },
            "rate_limiter": {
                "available": (
                    self._rate_limiter.is_available if self._rate_limiter else False
                ),
            },
            "config": {
                "model": self._model,
                "max_content_chars": self._max_content_chars,
                "api_timeout": self._api_timeout,
            },
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }


# =============================================================================
# SINGLETON INSTANCE
# =============================================================================

_service: Optional[DataEnrichmentService] = None


def get_data_enrichment_service() -> DataEnrichmentService:
    """Get singleton data enrichment service instance."""
    global _service
    if _service is None:
        _service = DataEnrichmentService()
    return _service


async def initialize_data_enrichment_service() -> DataEnrichmentService:
    """Initialize and return data enrichment service instance."""
    service = get_data_enrichment_service()
    await service.initialize()
    return service


# =============================================================================
# CLI ENTRY POINT
# =============================================================================

if __name__ == "__main__":
    import asyncio

    async def main():
        """Run enrichment as CLI command."""
        from dotenv import load_dotenv

        load_dotenv()

        service = await initialize_data_enrichment_service()

        print("\nFetching and enriching engine specifications...")
        results = await service.enrich_all()

        for manufacturer, specs in results.items():
            print(f"\n{manufacturer}: {len(specs)} specifications")
            for spec in specs[:3]:  # Show first 3
                print(
                    f"  - {spec.model_name}: {spec.power_min_kw}-{spec.power_max_kw} kW"
                )

        await service.close()

    asyncio.run(main())
