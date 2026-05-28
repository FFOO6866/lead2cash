"""
Industry News Insight Parser

Parses raw Perplexity search results into structured sales opportunities.
Focuses on identifying potential RRPS customers and engine sales opportunities.

Industry News Categories:
1. Customer Announcements - Shipowners/operators fleet plans, vessel orders
2. Shipyard Contracts - Contract awards, vessel specifications
3. Project Sanctioning - Offshore FIDs, infrastructure creating vessel demand
4. Regulatory Initiatives - MPA, IMO rules driving engine upgrades
5. Industry Tenders - RFPs, fleet renewal programs, public tenders

NOT competitor tracking (that's handled by get_competitor_updates).
"""

import json
import logging
import os
import re
from typing import Any, Optional

import httpx

from lead_to_cash.services.marine_intel.structured_insight import (
    CompanyInfo,
    DataQuality,
    DealDetails,
    EngineRequirement,
    InsightCollectionResponse,
    Priority,
    SalesAction,
    SalesSignalType,
    SourceInfo,
    SourceReliability,
    StructuredInsight,
)

logger = logging.getLogger(__name__)


# =============================================================================
# LLM Extraction Prompt
# =============================================================================

EXTRACTION_SYSTEM_PROMPT = """You are a marine industry sales intelligence analyst extracting structured data from news articles.

Your job is to identify SALES OPPORTUNITIES for RRPS (Rolls-Royce Power Systems) marine engines.

FOCUS ON:
1. CUSTOMER ANNOUNCEMENTS - Shipowners/operators announcing:
   - New vessel orders
   - Fleet expansion plans
   - Vessel replacement/renewal programs
   - Charter requirements

2. SHIPYARD CONTRACTS - Contract awards including:
   - Newbuild contracts (who ordered what from which shipyard)
   - Repair/upgrade contracts
   - Conversion projects

3. PROJECT SANCTIONING - Projects creating vessel demand:
   - Offshore oil & gas FIDs (Final Investment Decisions)
   - EPCIC contracts requiring OSVs
   - Port/terminal developments needing harbour craft

4. REGULATORY INITIATIVES - Rules driving engine upgrades:
   - MPA Singapore green ship requirements
   - IMO emissions regulations (Tier III, CII, EEXI)
   - National decarbonization mandates

5. INDUSTRY TENDERS - Active procurement:
   - Government vessel tenders
   - Operator RFPs for newbuilds
   - Fleet renewal programs

DO NOT include:
- General market commentary or forecasts
- Company financial results (unless announcing vessel purchases)
- Competitor product launches (Caterpillar, Cummins, MAN, Wartsila)
- Industry events without specific opportunities

PRIORITY REGIONS: Singapore, Indonesia, Malaysia, Thailand, Vietnam, Philippines, Australia, China, Korea, Japan, India

OUTPUT FORMAT: Return a JSON array of opportunities. Each opportunity MUST have:
- headline: Specific "[Company] [action] [details]" format
- published_date: Article publication date in YYYY-MM-DD format. Extract from article text, byline, or dateline. If no date found, use null.
- signal_type: One of NEWBUILD, RETROFIT_REPOWER, OFFSHORE_PROJECT, REGULATION, FUEL_TRANSITION, FLEET_EXPANSION, INCIDENT_RELIABILITY, FINANCING_CAPEX
- customer: The potential RRPS customer (shipowner, operator, or shipyard)
- customer_country: Country of the customer
- shipyard: Shipyard involved (if known)
- vessel_type: Type of vessel
- vessel_count: Number of vessels (if known)
- contract_value: Value in USD or local currency (if disclosed)
- engine_opportunity: Description of engine sales opportunity
- power_range_kw: Estimated engine power range
- why_it_matters: Why RRPS should care
- sales_action: Recommended next step
- source_url: Article URL
- source_name: Publication name
- confidence: low/medium/high based on data completeness

If no specific opportunities are found, return: {"opportunities": [], "market_summary": "brief explanation"}"""


EXTRACTION_USER_PROMPT = """Extract structured sales opportunities from this industry news content.

Remember:
- Focus on CUSTOMERS (who might buy RRPS engines)
- Include SPECIFIC company names and transaction details
- Estimate engine requirements based on vessel type/size
- Recommend concrete sales actions

Content to analyze:
{content}

Sources mentioned:
{sources}

Return JSON with "opportunities" array."""


# =============================================================================
# Engine Power Estimation
# =============================================================================

ENGINE_POWER_ESTIMATES = {
    # Ferries
    "ferry": {"small": "800-1500", "medium": "1500-3000", "large": "3000-6000"},
    "passenger_ferry": {
        "small": "800-1500",
        "medium": "1500-3000",
        "large": "3000-6000",
    },
    "ro_pax": {"small": "2000-4000", "medium": "4000-8000", "large": "8000-15000"},
    # Tugs
    "tug": {"small": "1500-2500", "medium": "2500-4000", "large": "4000-6000"},
    "harbour_tug": {"small": "1000-2000", "medium": "2000-3500", "large": "3500-5000"},
    "ahts": {"small": "4000-6000", "medium": "6000-10000", "large": "10000-16000"},
    # OSVs
    "osv": {"small": "2000-4000", "medium": "4000-6000", "large": "6000-10000"},
    "psv": {"small": "3000-5000", "medium": "5000-8000", "large": "8000-12000"},
    # Harbour craft
    "harbour_craft": {"small": "500-1000", "medium": "1000-2000", "large": "2000-3500"},
    "pilot_boat": {"small": "500-800", "medium": "800-1200", "large": "1200-1800"},
    "workboat": {"small": "500-1000", "medium": "1000-2000", "large": "2000-4000"},
    # Cargo
    "cargo": {"small": "2000-4000", "medium": "4000-8000", "large": "8000-15000"},
    "tanker": {"small": "3000-6000", "medium": "6000-12000", "large": "12000-25000"},
    "container": {
        "small": "5000-10000",
        "medium": "10000-20000",
        "large": "20000-40000",
    },
    # Offshore
    "fpso": {"small": "10000-20000", "medium": "20000-40000", "large": "40000-80000"},
    "construction_vessel": {
        "small": "5000-10000",
        "medium": "10000-20000",
        "large": "20000-40000",
    },
    "dredger": {"small": "3000-6000", "medium": "6000-12000", "large": "12000-25000"},
    # Other
    "yacht": {"small": "500-1500", "medium": "1500-3000", "large": "3000-6000"},
    "fishing": {"small": "500-1000", "medium": "1000-2000", "large": "2000-4000"},
    "cruise": {"small": "10000-20000", "medium": "20000-40000", "large": "40000-80000"},
}


def estimate_engine_power(vessel_type: str, size_indicator: str = "medium") -> str:
    """Estimate engine power range based on vessel type."""
    vessel_type_lower = vessel_type.lower().replace(" ", "_").replace("-", "_")

    # Try exact match
    if vessel_type_lower in ENGINE_POWER_ESTIMATES:
        return ENGINE_POWER_ESTIMATES[vessel_type_lower].get(
            size_indicator, "2000-4000"
        )

    # Try partial match
    for key, values in ENGINE_POWER_ESTIMATES.items():
        if key in vessel_type_lower or vessel_type_lower in key:
            return values.get(size_indicator, "2000-4000")

    # Default
    return "2000-4000"


# =============================================================================
# Region Mapping
# =============================================================================

REGION_MAPPING = {
    "singapore": "singapore",
    "indonesia": "indonesia",
    "malaysia": "malaysia",
    "thailand": "thailand",
    "vietnam": "vietnam",
    "philippines": "philippines",
    "australia": "australia",
    "china": "china",
    "korea": "korea",
    "south korea": "korea",
    "japan": "japan",
    "india": "india",
    "taiwan": "apac_other",
    "hong kong": "apac_other",
    "myanmar": "apac_other",
    "brunei": "apac_other",
    "cambodia": "apac_other",
    "laos": "apac_other",
    "bangladesh": "apac_other",
    "pakistan": "apac_other",
    "sri lanka": "apac_other",
    "new zealand": "apac_other",
    "papua new guinea": "apac_other",
}


def map_country_to_region(country: str) -> str:
    """Map country name to region code."""
    country_lower = country.lower().strip()
    region = REGION_MAPPING.get(country_lower, "apac_other")
    if region == "apac_other" and country_lower and country_lower not in REGION_MAPPING:
        logger.warning(f"REGION_MAPPING: unmapped country '{country}' → apac_other")
    return region


# =============================================================================
# Post-Extraction Validator
# =============================================================================

# Competitor brands that should NOT be stored as opportunities
_COMPETITOR_BRANDS = frozenset(
    s.lower()
    for s in [
        "Caterpillar",
        "CAT",
        "MaK",
        "Cummins",
        "MAN Energy Solutions",
        "MAN",
        "Wartsila",
        "Wärtsilä",
        "HiMSEN",
        "HD Hyundai",
        "Yanmar",
        "Volvo Penta",
        "Daihatsu",
        "Niigata",
        "Siemens Energy",
        "WinGD",
        "Everllence",
    ]
)

# Domains that indicate primary (official) sources
_PRIMARY_DOMAINS = frozenset(
    [
        "mpa.gov.sg",
        "imo.org",
        "dnv.com",
        "sgx.com",
        "rolls-royce.com",
        "mtu-solutions.com",
        # Company press rooms
        "seatrium.com",
        "paxocean.com",
        "asl.com.sg",
        "maersk.com",
        "cosco.com",
        "wartsila.com",
        "man-es.com",
    ]
)

# Corporate suffixes to strip for normalization
_CORP_SUFFIXES = re.compile(
    r"\s*\b(?:Pte\.?\s*Ltd\.?|Ltd\.?|Inc\.?|Corp\.?|Co\.?\s*,?\s*Ltd\.?|"
    r"LLC|PLC|GmbH|BV|SA|SRL|AG|Private|Limited|Corporation|Company|"
    r"Incorporated|Bhd|Sdn\.?\s*Bhd\.?|Tbk)\s*\.?\s*$",
    re.IGNORECASE,
)


def normalize_company_name(name: str) -> str:
    """Normalize company name for consistent storage and matching."""
    if not name:
        return name
    # Strip corporate suffixes
    cleaned = _CORP_SUFFIXES.sub("", name).strip()
    # Remove parenthetical content
    cleaned = re.sub(r"\s*\([^)]*\)\s*", " ", cleaned).strip()
    # Collapse whitespace
    cleaned = re.sub(r"\s+", " ", cleaned)
    return cleaned or name


def determine_source_reliability(source_url: str, source_name: str) -> str:
    """Determine source reliability tier from URL domain."""
    if not source_url:
        return "secondary"
    try:
        from urllib.parse import urlparse

        domain = urlparse(source_url).netloc.lower().replace("www.", "")
        if domain in _PRIMARY_DOMAINS:
            return "primary"
    except Exception:
        pass
    return "secondary"


def validate_extracted_opportunity(opp: dict) -> tuple[dict, list[str]]:
    """
    Validate and clean an extracted opportunity dict before conversion.

    Returns:
        (cleaned_opp, warnings) — cleaned opportunity dict and list of warnings
    """
    warnings: list[str] = []

    # 1. Normalize company names
    for field in ("customer", "shipyard"):
        if opp.get(field) and opp[field] != "Unknown":
            original = opp[field]
            opp[field] = normalize_company_name(opp[field])
            if opp[field] != original:
                warnings.append(f"Normalized {field}: '{original}' → '{opp[field]}'")

    # 2. Check for competitor brands in customer/headline
    _headline_lower = (opp.get("headline") or "").lower()
    _customer_lower = (opp.get("customer") or "").lower()
    for brand in _COMPETITOR_BRANDS:
        if brand in _customer_lower:
            warnings.append(f"REJECTED: competitor brand '{brand}' in customer field")
            return opp, ["REJECT: competitor_in_customer"]

    # 3. Validate country → region mapping
    country = opp.get("customer_country", "")
    if country:
        region = map_country_to_region(country)
        if region == "apac_other" and country.lower() not in REGION_MAPPING:
            warnings.append(f"Unmapped country: '{country}'")

    # 4. Assign source reliability
    source_url = opp.get("source_url", "")
    source_name = opp.get("source_name", "")
    opp["_source_reliability"] = determine_source_reliability(source_url, source_name)

    # 5. Validate published_date is not in the future
    pub_date = opp.get("published_date")
    if pub_date and isinstance(pub_date, str):
        try:
            from datetime import datetime as _dt, timezone as _tz

            parsed = _dt.strptime(pub_date[:10], "%Y-%m-%d")
            if parsed > _dt.now(_tz.utc).replace(tzinfo=None):
                warnings.append(f"Future date rejected: {pub_date}")
                opp["published_date"] = None
        except (ValueError, TypeError):
            pass

    return opp, warnings


# =============================================================================
# Signal Type Mapping
# =============================================================================

SIGNAL_KEYWORDS = {
    SalesSignalType.NEWBUILD: [
        "newbuild",
        "new build",
        "new vessel",
        "vessel order",
        "shipbuilding",
        "contract award",
        "orders",
        "commissioned",
        "construction contract",
    ],
    SalesSignalType.RETROFIT_REPOWER: [
        "retrofit",
        "repower",
        "repowering",
        "engine replacement",
        "upgrade",
        "modernization",
        "conversion",
        "life extension",
        "refurbishment",
    ],
    SalesSignalType.OFFSHORE_PROJECT: [
        "fid",
        "final investment decision",
        "offshore",
        "epcic",
        "fpso",
        "oil & gas",
        "oil and gas",
        "field development",
        "subsea",
    ],
    SalesSignalType.REGULATION: [
        "imo",
        "mpa",
        "regulation",
        "emissions",
        "tier iii",
        "eexi",
        "cii",
        "decarbonization",
        "decarbonisation",
        "green ship",
        "environmental",
    ],
    SalesSignalType.FUEL_TRANSITION: [
        "lng",
        "methanol",
        "ammonia",
        "dual fuel",
        "dual-fuel",
        "hydrogen",
        "alternative fuel",
        "green fuel",
        "biofuel",
        "electric",
        "hybrid",
    ],
    SalesSignalType.FLEET_EXPANSION: [
        "fleet expansion",
        "fleet growth",
        "fleet renewal",
        "additional vessels",
        "expanding fleet",
        "fleet modernization",
    ],
    SalesSignalType.INCIDENT_RELIABILITY: [
        "engine failure",
        "breakdown",
        "grounding",
        "collision",
        "incident",
        "investigation",
        "reliability",
        "mechanical failure",
    ],
    SalesSignalType.FINANCING_CAPEX: [
        "financing",
        "capex",
        "capital expenditure",
        "investment",
        "funding",
        "loan",
        "lease",
        "charter",
    ],
}


def detect_signal_type(text: str) -> SalesSignalType:
    """Detect the primary signal type from text content."""
    text_lower = text.lower()

    # Count keyword matches for each signal type
    scores = {}
    for signal_type, keywords in SIGNAL_KEYWORDS.items():
        score = sum(1 for kw in keywords if kw in text_lower)
        if score > 0:
            scores[signal_type] = score

    if not scores:
        return SalesSignalType.NEWBUILD  # Default

    # Return highest scoring signal
    return max(scores, key=lambda k: scores.get(k, 0))


# =============================================================================
# Insight Parser Class
# =============================================================================


class InsightParser:
    """
    Parses raw industry news into structured sales opportunities.

    Uses OpenAI to extract structured data from Perplexity search results,
    then formats into StructuredInsight objects for sales team consumption.
    """

    def __init__(self, openai_api_key: Optional[str] = None):
        """
        Initialize parser.

        Args:
            openai_api_key: OpenAI API key. If not provided, uses OPENAI_API_KEY env var.
        """
        self.api_key = openai_api_key or os.getenv("OPENAI_API_KEY")
        self.api_url = "https://api.openai.com/v1/chat/completions"
        self._client: httpx.AsyncClient | None = None

    async def _get_client(self) -> httpx.AsyncClient:
        """Get or create HTTP client."""
        if self._client is None:
            self._client = httpx.AsyncClient(timeout=60.0)
        return self._client

    async def close(self):
        """Close HTTP client."""
        if self._client:
            await self._client.aclose()
            self._client = None

    async def parse_industry_news(
        self,
        raw_content: str,
        sources: list[str],
    ) -> InsightCollectionResponse:
        """
        Parse raw industry news content into structured insights.

        Args:
            raw_content: Raw text content from Perplexity
            sources: List of source URLs

        Returns:
            InsightCollectionResponse with structured opportunities
        """
        if not self.api_key:
            logger.warning("OpenAI API key not configured, using basic parsing")
            return self._basic_parse(raw_content, sources)

        try:
            # Call OpenAI for structured extraction
            extracted = await self._extract_with_llm(raw_content, sources)

            if not extracted or not extracted.get("opportunities"):
                return InsightCollectionResponse(
                    status="success",
                    insights_count=0,
                    message=extracted.get(
                        "market_summary",
                        "No specific opportunities found matching criteria.",
                    ),
                    recommendations=[
                        "Expand search to 60-day window",
                        "Check MPA Singapore tender portal directly",
                        "Monitor Seatrium quarterly announcements",
                        "Review SGX filings for marine companies",
                    ],
                    market_context=extracted.get("market_context"),
                    search_metadata={
                        "sources_checked": len(sources),
                        "extraction_method": "llm",
                    },
                )

            # Validate and convert to StructuredInsight objects
            insights = []
            for opp in extracted["opportunities"]:
                try:
                    # Post-extraction validation: normalize, reject competitors, check dates
                    opp, val_warnings = validate_extracted_opportunity(opp)
                    if val_warnings and val_warnings[0].startswith("REJECT"):
                        logger.info(
                            f"VALIDATOR: Rejected opportunity: {val_warnings[0]} "
                            f"— {opp.get('headline', '')[:80]}"
                        )
                        continue
                    for w in val_warnings:
                        logger.debug(f"VALIDATOR: {w}")

                    insight = self._convert_to_structured_insight(opp)
                    insights.append(insight)
                except Exception as e:
                    logger.warning(f"Failed to convert opportunity: {e}")
                    continue

            # Count by priority
            high = sum(1 for i in insights if i.priority == Priority.HIGH)
            medium = sum(1 for i in insights if i.priority == Priority.MEDIUM)
            low = sum(
                1 for i in insights if i.priority in (Priority.LOW, Priority.UNVERIFIED)
            )

            return InsightCollectionResponse(
                status="success",
                insights_count=len(insights),
                high_priority_count=high,
                medium_priority_count=medium,
                low_priority_count=low,
                insights=insights,
                search_metadata={
                    "sources_checked": len(sources),
                    "extraction_method": "llm",
                    "raw_opportunities": len(extracted["opportunities"]),
                },
            )

        except Exception as e:
            logger.error(f"LLM extraction failed: {e}")
            return self._basic_parse(raw_content, sources)

    async def _extract_with_llm(
        self,
        content: str,
        sources: list[str],
    ) -> dict[str, Any]:
        """Extract structured data using OpenAI."""
        client = await self._get_client()

        # Truncate content if too long
        if len(content) > 12000:
            content = content[:12000] + "...[truncated]"

        sources_text = "\n".join(f"- {s}" for s in sources[:10])

        try:
            response = await client.post(
                self.api_url,
                headers={
                    "Authorization": f"Bearer {self.api_key}",
                    "Content-Type": "application/json",
                },
                json={
                    "model": os.getenv("OPENAI_MINI_MODEL", "gpt-4o-mini"),
                    "messages": [
                        {"role": "system", "content": EXTRACTION_SYSTEM_PROMPT},
                        {
                            "role": "user",
                            "content": EXTRACTION_USER_PROMPT.format(
                                content=content,
                                sources=sources_text,
                            ),
                        },
                    ],
                    "temperature": 0.1,
                    "response_format": {"type": "json_object"},
                },
            )

            if response.status_code == 200:
                data = response.json()
                result_text = data["choices"][0]["message"]["content"]
                return json.loads(result_text)
            else:
                logger.error(
                    f"OpenAI API error: {response.status_code} - {response.text}"
                )
                return {"opportunities": [], "market_summary": "API extraction failed"}

        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse LLM response as JSON: {e}")
            return {"opportunities": [], "market_summary": "Failed to parse extraction"}
        except Exception as e:
            logger.error(f"LLM extraction error: {e}")
            raise

    def _convert_to_structured_insight(self, opp: dict) -> StructuredInsight:
        """Convert extracted opportunity dict to StructuredInsight."""
        # Determine signal type
        signal_str = opp.get("signal_type", "NEWBUILD").upper().replace(" ", "_")
        try:
            signal_type = SalesSignalType(signal_str)
        except ValueError:
            signal_type = detect_signal_type(
                opp.get("headline", "") + " " + opp.get("why_it_matters", "")
            )

        # Get country and region
        country = opp.get("customer_country") or opp.get("country") or "Unknown"
        region = map_country_to_region(country)

        # Estimate engine power if not provided
        power_range = opp.get("power_range_kw")
        if not power_range:
            vessel_type = opp.get("vessel_type", "")
            power_range = estimate_engine_power(vessel_type)

        # Build CompanyInfo
        companies = CompanyInfo(
            operator=opp.get("customer") or opp.get("operator") or "Unknown",
            operator_country=country,
            shipyard=opp.get("shipyard"),
            shipyard_country=opp.get("shipyard_country"),
            engine_supplier=opp.get("engine_supplier", "Unknown - OPPORTUNITY"),
        )

        # Build DealDetails
        contract_value = opp.get("contract_value")
        contract_value_usd = None
        contract_value_local = None

        if contract_value:
            if isinstance(contract_value, (int, float)):
                contract_value_usd = float(contract_value)
            elif isinstance(contract_value, str):
                # Try to extract USD value
                usd_match = re.search(r"USD?\s*([\d,.]+)\s*[MmBb]?", contract_value)
                if usd_match:
                    val = float(usd_match.group(1).replace(",", ""))
                    if "b" in contract_value.lower():
                        val *= 1_000_000_000
                    elif "m" in contract_value.lower():
                        val *= 1_000_000
                    contract_value_usd = val
                else:
                    contract_value_local = contract_value

        deal_details = DealDetails(
            vessel_type=opp.get("vessel_type", "Unknown"),
            vessel_count=opp.get("vessel_count"),
            contract_value_usd=contract_value_usd,
            contract_value_local=contract_value_local,
            delivery_timeline=opp.get("delivery_timeline") or opp.get("timeline"),
        )

        # Build EngineRequirement
        engine_req = None
        if power_range or opp.get("engine_opportunity"):
            engine_req = EngineRequirement(
                power_range_kw=power_range,
                engine_count=opp.get("engine_count"),
                fuel_type=opp.get("fuel_type"),
                notes=opp.get("engine_opportunity"),
            )

        # Build SalesAction
        confidence = opp.get("confidence", "medium").lower()
        priority_map = {
            "high": Priority.HIGH,
            "medium": Priority.MEDIUM,
            "low": Priority.LOW,
        }
        action_priority = priority_map.get(confidence, Priority.MEDIUM)

        sales_action = SalesAction(
            priority=action_priority,
            action=opp.get(
                "sales_action", "Contact customer to discuss engine requirements"
            ),
            contact_target=opp.get("contact_target"),
            timeline=opp.get("timeline") or opp.get("decision_timeline"),
            competition=opp.get("competition"),
        )

        # Build DataQuality — use validator's source reliability if available
        _reliability_str = opp.get("_source_reliability", "secondary")
        _reliability_map = {
            "primary": SourceReliability.PRIMARY,
            "secondary": SourceReliability.SECONDARY,
            "rumor": SourceReliability.RUMOR,
        }
        _source_rel = _reliability_map.get(
            _reliability_str, SourceReliability.SECONDARY
        )

        data_quality = DataQuality(
            has_company_names=bool(
                companies.operator and companies.operator != "Unknown"
            ),
            has_contract_value=bool(contract_value_usd or contract_value_local),
            has_vessel_specs=bool(
                deal_details.vessel_type and deal_details.vessel_type != "Unknown"
            ),
            has_engine_requirements=bool(engine_req and engine_req.power_range_kw),
            has_timeline=bool(deal_details.delivery_timeline),
            source_reliability=_source_rel,
        )

        # Build SourceInfo — parse published_date from LLM extraction
        _pub_date_raw = opp.get("published_date")
        _pub_date = None
        if _pub_date_raw and isinstance(_pub_date_raw, str):
            try:
                from datetime import datetime as _dt

                _pub_date = _dt.strptime(_pub_date_raw[:10], "%Y-%m-%d")
            except (ValueError, TypeError):
                pass  # LLM returned unparseable date — leave as None

        source = SourceInfo(
            name=opp.get("source_name", "Industry Source"),
            url=opp.get("source_url"),
            published_date=_pub_date,
        )

        # Create insight
        insight = StructuredInsight(
            headline=opp.get("headline", "Untitled Opportunity"),
            signal_type=signal_type,
            priority=action_priority,
            companies=companies,
            deal_details=deal_details,
            engine_requirement=engine_req,
            why_it_matters=opp.get(
                "why_it_matters", "Potential engine sales opportunity identified."
            ),
            sales_action=sales_action,
            country=country,
            region=region,
            source=source,
            score=0,  # Will be calculated
            data_quality=data_quality,
            raw_excerpt=opp.get("raw_excerpt"),
        )

        # Calculate score and update priority
        insight.score = insight.calculate_score()
        insight.priority = insight.determine_priority()
        insight.sales_action.priority = insight.priority

        return insight

    def _basic_parse(
        self,
        content: str,
        sources: list[str],
    ) -> InsightCollectionResponse:
        """
        Basic parsing without LLM (fallback).

        Attempts to extract opportunities using regex patterns.
        """
        # This is a basic fallback - LLM extraction unavailable - just return the raw content with a note
        return InsightCollectionResponse(
            status="success",
            insights_count=0,
            message="LLM extraction unavailable. Raw content provided for manual review.",
            recommendations=[
                "Configure OPENAI_API_KEY for structured extraction",
                "Review raw content manually for opportunities",
            ],
            search_metadata={
                "sources_checked": len(sources),
                "extraction_method": "basic_fallback",
                "raw_content_length": len(content),
            },
            market_context=content[:1000] + "..." if len(content) > 1000 else content,
        )


# =============================================================================
# Singleton Instance
# =============================================================================

_parser: Optional["InsightParser"] = None


def get_insight_parser() -> InsightParser:
    """Get or create the insight parser singleton."""
    global _parser
    if _parser is None:
        _parser = InsightParser()
    return _parser
