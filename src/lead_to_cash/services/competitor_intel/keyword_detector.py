"""
Keyword Detector for Competitor Intelligence

Detects keywords in content to classify signal types, extract entities,
and assess geographic relevance for RRPS competitive intelligence.
"""

import re
from dataclasses import dataclass, field
from typing import Optional


@dataclass
class KeywordMatch:
    """Result of keyword detection."""

    category: str
    keyword: str
    context: str  # Surrounding text
    position: int  # Character position in text


@dataclass
class DetectionResult:
    """Full result of keyword detection on content."""

    # Signal type keywords
    contract_keywords: list[str] = field(default_factory=list)
    customer_keywords: list[str] = field(default_factory=list)
    product_keywords: list[str] = field(default_factory=list)
    technology_keywords: list[str] = field(default_factory=list)
    event_keywords: list[str] = field(default_factory=list)
    partnership_keywords: list[str] = field(default_factory=list)
    regulatory_keywords: list[str] = field(default_factory=list)

    # Fuel transition keywords
    fuel_keywords: list[str] = field(default_factory=list)

    # Vessel/project type keywords
    vessel_keywords: list[str] = field(default_factory=list)

    # Geographic keywords
    apac_keywords: list[str] = field(default_factory=list)
    singapore_keywords: list[str] = field(default_factory=list)

    # Non-marine indicators
    non_marine_keywords: list[str] = field(default_factory=list)

    # Generic branding indicators
    generic_branding_keywords: list[str] = field(default_factory=list)

    # All matches
    all_matches: list[str] = field(default_factory=list)

    def has_contract_signals(self) -> bool:
        return len(self.contract_keywords) > 0

    def has_fuel_transition(self) -> bool:
        return len(self.fuel_keywords) > 0

    def is_apac_relevant(self) -> bool:
        return len(self.apac_keywords) > 0

    def is_singapore_relevant(self) -> bool:
        return len(self.singapore_keywords) > 0

    def is_marine_relevant(self) -> bool:
        """Check if content is marine-relevant based on vessel keywords."""
        return len(self.vessel_keywords) > 0

    def is_generic_branding(self) -> bool:
        """Check if content is generic branding without substance."""
        return (
            len(self.generic_branding_keywords) > 0
            and len(self.contract_keywords) == 0
            and len(self.product_keywords) == 0
            and len(self.technology_keywords) == 0
        )

    def suggest_signal_type(self) -> str:
        """Suggest the most likely signal type based on detected keywords."""
        if self.contract_keywords:
            return "CONTRACT_WIN"
        if self.customer_keywords and not self.contract_keywords:
            return "CUSTOMER_ANNOUNCEMENT"
        if self.product_keywords:
            return "PRODUCT_LAUNCH"
        if self.technology_keywords or self.fuel_keywords:
            return "TECHNOLOGY_POV"
        if self.event_keywords:
            return "EVENT_MARKETING"
        if self.partnership_keywords:
            return "PARTNERSHIP"
        if self.regulatory_keywords:
            return "REGULATORY_POSITIONING"
        return "THOUGHT_LEADERSHIP"


class KeywordDetector:
    """
    Keyword detection for competitor intelligence signals.

    Detects keywords to:
    - Classify signal types (CONTRACT_WIN, PRODUCT_LAUNCH, etc.)
    - Extract entities (vessels, customers, fuel types)
    - Assess geographic relevance (APAC, Singapore)
    - Identify non-marine content for score penalties
    """

    # Contract/win-related keywords
    CONTRACT_KEYWORDS = [
        "contract awarded",
        "contract signed",
        "selected",
        "chosen",
        "won",
        "wins",
        "order placed",
        "secured contract",
        "deal signed",
        "awarded",
        "awarded contract",
        "purchase order",
        "contracted for",
        "multi-year contract",
        "framework agreement",
        "supply agreement",
        "powered by",
        "will be powered",
        "engines ordered",
        "propulsion contract",
    ]

    # Customer announcement keywords
    CUSTOMER_KEYWORDS = [
        "delivered to",
        "handed over",
        "customer",
        "operator",
        "shipowner",
        "fleet operator",
        "delivery of",
        "commissioning",
        "entered service",
        "maiden voyage",
        "launched for",
        "christened",
        "naming ceremony",
    ]

    # Product launch keywords
    PRODUCT_KEYWORDS = [
        "new engine",
        "new product",
        "launched",
        "unveil",
        "unveiled",
        "introduces",
        "introducing",
        "announces",
        "announcing",
        "next generation",
        "upgraded",
        "enhanced",
        "new platform",
        "new series",
        "new model",
        "product launch",
        "market launch",
        "debut",
        "first of its kind",
        "breakthrough",
        "innovation",
    ]

    # Technology/fuel transition keywords
    TECHNOLOGY_KEYWORDS = [
        "technology",
        "innovation",
        "r&d",
        "research",
        "development",
        "digital",
        "smart",
        "automation",
        "ai",
        "artificial intelligence",
        "machine learning",
        "iot",
        "connectivity",
        "predictive maintenance",
        "efficiency",
        "optimization",
    ]

    # Fuel transition keywords (important for marine)
    FUEL_KEYWORDS = [
        "dual fuel",
        "dual-fuel",
        "methanol",
        "ammonia",
        "hydrogen",
        "lng",
        "liquefied natural gas",
        "decarbonization",
        "decarbonisation",
        "net zero",
        "net-zero",
        "carbon neutral",
        "carbon-neutral",
        "emissions reduction",
        "green fuel",
        "alternative fuel",
        "fuel transition",
        "hybrid",
        "electric",
        "battery",
        "fuel cell",
        "e-fuel",
        "bio-fuel",
        "biofuel",
    ]

    # Event/marketing keywords
    EVENT_KEYWORDS = [
        "exhibition",
        "trade show",
        "conference",
        "event",
        "summit",
        "forum",
        "sea asia",
        "nor-shipping",
        "norshipping",
        "otc asia",
        "smo",
        "singapore maritime",
        "posidonia",
        "europort",
        "marintec",
        "smm hamburg",
        "webinar",
        "presentation",
        "speaking",
        "booth",
        "stand",
    ]

    # Partnership keywords
    PARTNERSHIP_KEYWORDS = [
        "partnership",
        "partner",
        "partnering",
        "collaboration",
        "collaborate",
        "joint venture",
        "jv",
        "memorandum of understanding",
        "mou",
        "strategic alliance",
        "teaming agreement",
        "cooperation",
    ]

    # Regulatory keywords
    REGULATORY_KEYWORDS = [
        "tier iii",
        "tier 3",
        "imo",
        "imo 2020",
        "imo 2030",
        "imo 2050",
        "marpol",
        "eexi",
        "cii",
        "eu ets",
        "fueleu",
        "compliance",
        "regulation",
        "regulatory",
        "emission standard",
        "emissions standard",
        "environmental",
        "green shipping",
        "maritime decarbonization",
    ]

    # Vessel/project type keywords
    VESSEL_KEYWORDS = [
        "vessel",
        "ship",
        "ferry",
        "ferries",
        "osv",
        "offshore support vessel",
        "ahts",
        "anchor handling",
        "psv",
        "platform supply",
        "tug",
        "tugboat",
        "towage",
        "fpso",
        "fso",
        "drilling",
        "drill ship",
        "patrol",
        "patrol vessel",
        "coast guard",
        "naval",
        "navy",
        "workboat",
        "crew boat",
        "harbour craft",
        "harbor craft",
        "pilot boat",
        "dredger",
        "dredging",
        "tanker",
        "bulk carrier",
        "container",
        "ro-ro",
        "roro",
        "cruise",
        "yacht",
        "superyacht",
        "fishing vessel",
        "trawler",
        "research vessel",
        "icebreaker",
        "offshore",
        "marine",
        "maritime",
        "newbuild",
        "new build",
        "retrofit",
        "repower",
        "repowering",
        "conversion",
    ]

    # APAC geographic keywords
    APAC_KEYWORDS = [
        "asia pacific",
        "asia-pacific",
        "apac",
        "southeast asia",
        "asean",
        "asia",
        "china",
        "chinese",
        "japan",
        "japanese",
        "korea",
        "korean",
        "south korea",
        "taiwan",
        "indonesia",
        "indonesian",
        "malaysia",
        "malaysian",
        "thailand",
        "thai",
        "vietnam",
        "vietnamese",
        "philippines",
        "philippine",
        "filipino",
        "australia",
        "australian",
        "new zealand",
        "india",
        "indian",
        "bangladesh",
        "myanmar",
        "pacific",
    ]

    # Singapore-specific keywords
    SINGAPORE_KEYWORDS = [
        "singapore",
        "singaporean",
        "mpa singapore",
        "maritime port authority",
        "psa",
        "jurong",
        "keppel",
        "sembcorp",
        "seatrium",
        "paxocean",
        "asl marine",
        "penguin shipyard",
        "singapore strait",
        "changi",
        "tuas",
    ]

    # Non-marine keywords (for penalty scoring)
    NON_MARINE_KEYWORDS = [
        "mining",
        "construction equipment",
        "excavator",
        "loader",
        "dozer",
        "agriculture",
        "farming",
        "tractor",
        "locomotive",
        "rail",
        "railway",
        "truck",
        "on-highway",
        "automotive",
        "car",
        "suv",
    ]

    # Generic branding keywords (for penalty scoring)
    GENERIC_BRANDING_KEYWORDS = [
        "proud to",
        "excited to",
        "thrilled to",
        "honored to",
        "delighted to",
        "pleased to",
        "celebrating",
        "anniversary",
        "milestone",
        "company culture",
        "employee spotlight",
        "team building",
        "corporate responsibility",
        "csr",
        "diversity",
        "inclusion",
        "sustainability report",
        "annual report",
        "earnings call",
        "investor day",
        "shareholder",
    ]

    def __init__(self):
        """Initialize the keyword detector."""
        # Compile regex patterns for efficiency
        self._patterns: dict[str, re.Pattern] = {}
        self._compile_patterns()

    def _compile_patterns(self):
        """Pre-compile regex patterns for all keyword lists."""
        keyword_lists = {
            "contract": self.CONTRACT_KEYWORDS,
            "customer": self.CUSTOMER_KEYWORDS,
            "product": self.PRODUCT_KEYWORDS,
            "technology": self.TECHNOLOGY_KEYWORDS,
            "fuel": self.FUEL_KEYWORDS,
            "event": self.EVENT_KEYWORDS,
            "partnership": self.PARTNERSHIP_KEYWORDS,
            "regulatory": self.REGULATORY_KEYWORDS,
            "vessel": self.VESSEL_KEYWORDS,
            "apac": self.APAC_KEYWORDS,
            "singapore": self.SINGAPORE_KEYWORDS,
            "non_marine": self.NON_MARINE_KEYWORDS,
            "generic_branding": self.GENERIC_BRANDING_KEYWORDS,
        }

        for name, keywords in keyword_lists.items():
            # Create a pattern that matches any of the keywords (case-insensitive)
            # Use word boundaries to avoid partial matches
            pattern = r"\b(" + "|".join(re.escape(k) for k in keywords) + r")\b"
            self._patterns[name] = re.compile(pattern, re.IGNORECASE)

    def detect(self, text: str) -> DetectionResult:
        """
        Detect keywords in text and return classification result.

        Args:
            text: Content to analyze

        Returns:
            DetectionResult with all matched keywords by category
        """
        if not text:
            return DetectionResult()

        result = DetectionResult()

        # Find matches for each category
        for match in self._patterns["contract"].finditer(text):
            result.contract_keywords.append(match.group().lower())
            result.all_matches.append(match.group().lower())

        for match in self._patterns["customer"].finditer(text):
            result.customer_keywords.append(match.group().lower())
            result.all_matches.append(match.group().lower())

        for match in self._patterns["product"].finditer(text):
            result.product_keywords.append(match.group().lower())
            result.all_matches.append(match.group().lower())

        for match in self._patterns["technology"].finditer(text):
            result.technology_keywords.append(match.group().lower())
            result.all_matches.append(match.group().lower())

        for match in self._patterns["fuel"].finditer(text):
            result.fuel_keywords.append(match.group().lower())
            result.all_matches.append(match.group().lower())

        for match in self._patterns["event"].finditer(text):
            result.event_keywords.append(match.group().lower())
            result.all_matches.append(match.group().lower())

        for match in self._patterns["partnership"].finditer(text):
            result.partnership_keywords.append(match.group().lower())
            result.all_matches.append(match.group().lower())

        for match in self._patterns["regulatory"].finditer(text):
            result.regulatory_keywords.append(match.group().lower())
            result.all_matches.append(match.group().lower())

        for match in self._patterns["vessel"].finditer(text):
            result.vessel_keywords.append(match.group().lower())
            result.all_matches.append(match.group().lower())

        for match in self._patterns["apac"].finditer(text):
            result.apac_keywords.append(match.group().lower())
            result.all_matches.append(match.group().lower())

        for match in self._patterns["singapore"].finditer(text):
            result.singapore_keywords.append(match.group().lower())
            result.all_matches.append(match.group().lower())

        for match in self._patterns["non_marine"].finditer(text):
            result.non_marine_keywords.append(match.group().lower())
            result.all_matches.append(match.group().lower())

        for match in self._patterns["generic_branding"].finditer(text):
            result.generic_branding_keywords.append(match.group().lower())
            result.all_matches.append(match.group().lower())

        # Deduplicate
        result.contract_keywords = list(set(result.contract_keywords))
        result.customer_keywords = list(set(result.customer_keywords))
        result.product_keywords = list(set(result.product_keywords))
        result.technology_keywords = list(set(result.technology_keywords))
        result.fuel_keywords = list(set(result.fuel_keywords))
        result.event_keywords = list(set(result.event_keywords))
        result.partnership_keywords = list(set(result.partnership_keywords))
        result.regulatory_keywords = list(set(result.regulatory_keywords))
        result.vessel_keywords = list(set(result.vessel_keywords))
        result.apac_keywords = list(set(result.apac_keywords))
        result.singapore_keywords = list(set(result.singapore_keywords))
        result.non_marine_keywords = list(set(result.non_marine_keywords))
        result.generic_branding_keywords = list(set(result.generic_branding_keywords))
        result.all_matches = list(set(result.all_matches))

        return result

    def extract_fuel_type(self, text: str) -> Optional[str]:
        """
        Extract the primary fuel type mentioned in text.

        Returns:
            Fuel type string or None if not detected
        """
        text_lower = text.lower()

        # Check for specific fuel types (order matters - most specific first)
        if "ammonia" in text_lower:
            return "ammonia"
        if "hydrogen" in text_lower or "fuel cell" in text_lower:
            return "hydrogen"
        if "methanol" in text_lower:
            return "methanol"
        if "dual fuel" in text_lower or "dual-fuel" in text_lower:
            return "dual_fuel"
        if "lng" in text_lower or "liquefied natural gas" in text_lower:
            return "lng"
        if "hybrid" in text_lower or "battery" in text_lower:
            return "hybrid"
        if "electric" in text_lower and "battery" in text_lower:
            return "electric"

        return None

    def extract_vessel_type(self, text: str) -> Optional[str]:
        """
        Extract the primary vessel type mentioned in text.

        Returns:
            Vessel type string or None if not detected
        """
        text_lower = text.lower()

        # Check vessel types (order matters - most specific first)
        if "fpso" in text_lower or "floating production" in text_lower:
            return "FPSO"
        if "ahts" in text_lower or "anchor handling" in text_lower:
            return "AHTS"
        if "psv" in text_lower or "platform supply" in text_lower:
            return "PSV"
        if "osv" in text_lower or "offshore support" in text_lower:
            return "OSV"
        if "ferry" in text_lower or "ferries" in text_lower:
            return "ferry"
        if "tug" in text_lower or "tugboat" in text_lower or "towage" in text_lower:
            return "tug"
        if "patrol" in text_lower:
            return "patrol_vessel"
        if "dredg" in text_lower:
            return "dredger"
        if "tanker" in text_lower:
            return "tanker"
        if "cruise" in text_lower:
            return "cruise"
        if "yacht" in text_lower:
            return "yacht"
        if "workboat" in text_lower or "crew boat" in text_lower:
            return "workboat"
        if "fishing" in text_lower or "trawler" in text_lower:
            return "fishing_vessel"
        if "container" in text_lower:
            return "container"
        if "bulk" in text_lower:
            return "bulk_carrier"
        if "naval" in text_lower or "navy" in text_lower:
            return "naval"

        return None


# Singleton instance
_detector: Optional[KeywordDetector] = None


def get_keyword_detector() -> KeywordDetector:
    """Get or create the keyword detector singleton."""
    global _detector
    if _detector is None:
        _detector = KeywordDetector()
    return _detector
