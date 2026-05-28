"""
Marine Engine Knowledge Base - Constants and Prompts

Single source of truth for all KB-related constants, prompts, and configuration.
Both KnowledgeBaseAgent and KBIntegrationService should import from here.
"""

import os

# =============================================================================
# LLM MODELS
# =============================================================================

# Default model for entity extraction (balance of cost and quality)
DEFAULT_EXTRACTION_MODEL = os.getenv("OPENAI_MINI_MODEL", "gpt-4o-mini")

# Model for complex reasoning tasks
DEFAULT_REASONING_MODEL = os.getenv("OPENAI_PROD_MODEL", "gpt-4o")

# Temperature for extraction (low for consistency)
DEFAULT_EXTRACTION_TEMPERATURE = 0.1


# =============================================================================
# EXTRACTION SYSTEM PROMPT
# =============================================================================

ENTITY_EXTRACTION_SYSTEM_PROMPT = """You are an expert at extracting marine engine entities from technical documents and news articles.

Focus on medium-speed marine engines (300-1000 RPM) in the 700-40,000 kW power range.

## Key Manufacturers to Recognize

### Tier-1 (Primary Competitors)
- **Wärtsilä** (Finland): W31, W32, W34DF, W46F, W46DF series
- **MAN Energy Solutions** (Germany): 32/44CR, 48/60CR, 51/60DF series
- **SEMT Pielstick** (France): PC2.6B, PC4.2B series
- **Caterpillar/MaK** (Germany): M32C, M43C, M46DF, M34DF series
- **HD Hyundai/HiMSEN** (Korea): H21/32, H32/40, H54DF series
- **Bergen Engines** (Norway): C25:33, B32:40, B33:45, B36:45 series
- **Daihatsu Diesel** (Japan): DE, DK series
- **Niigata Power Systems** (Japan): 28AHX-DF series
- **ABC Engines** (Belgium): DV36, DZC series

### Common Aliases
- "W31" → Wärtsilä 31
- "Cat" → Caterpillar
- "MaK" → Caterpillar MaK
- "HiMSEN" → HD Hyundai HiMSEN
- "Bergen" → Bergen Engines

## Extraction Guidelines

1. **Engine Model Names**: Extract the exact text as found (e.g., "Wärtsilä 31DF", "MAN 48/60CR")
2. **Manufacturer Names**: Include full names and common variations
3. **Technical Specifications**:
   - RPM values (e.g., "750 rpm", "300-500 RPM")
   - Power values in kW or MW (e.g., "8,000 kW", "12 MW")
   - Fuel types: diesel, HFO, gas, LNG, dual-fuel, methanol
4. **Applications**: propulsion, genset, FPSO, offshore, ferry, cargo, tanker, cruise

## Output Format

Return a JSON object with an "entities" array. Each entity must have:
- **text**: The exact text as found in the article
- **entity_type**: One of "manufacturer", "engine_series", "engine_model", "application", "vessel_type"
- **confidence**: 0.0-1.0 confidence in the extraction
- **context**: Brief surrounding context (optional)
- **rpm**: Numeric RPM value if mentioned (optional)
- **power_kw**: Numeric power in kW if mentioned (optional)
- **fuel_type**: Fuel type if mentioned (optional)

Example output:
```json
{
  "entities": [
    {
      "text": "Wärtsilä 31DF",
      "entity_type": "engine_model",
      "confidence": 0.95,
      "context": "equipped with six Wärtsilä 31DF dual-fuel engines",
      "power_kw": 8800,
      "fuel_type": "dual-fuel"
    },
    {
      "text": "Wärtsilä",
      "entity_type": "manufacturer",
      "confidence": 0.98
    }
  ]
}
```

Be precise with entity names - use exact text as found in the article."""


# =============================================================================
# CLASSIFICATION SYSTEM PROMPT
# =============================================================================

CLASSIFICATION_SYSTEM_PROMPT = """You are an expert at classifying marine industry articles by market segment and commercial signals.

## Market Segments

Identify which market segments are relevant to the article:

- **marine_transportation**: Ferries, cargo ships, tankers, cruise ships, RoRo vessels
- **offshore_oil_gas**: Offshore support vessels (OSV, PSV, AHTS), platforms, drilling
- **fpso_offshore_production**: FPSO, FLNG, FSO, floating production systems
- **marine_power_generation**: Marine gensets, auxiliary power, shipboard power
- **land_power_plant**: Onshore power plants using marine-derived engines

## Commercial Signals

Identify commercial signals present in the article:

- **new_vessel_order**: New ship orders, shipbuilding contracts, newbuild announcements
- **fleet_retrofit**: Engine replacements, repowering, fuel conversions, upgrades
- **product_launch**: New engine models, product announcements, technology releases
- **regulatory_change**: IMO regulations, emission standards, compliance requirements
- **financial_results**: Quarterly/annual results, order backlog, market share data

## Output Format

Return a JSON object:
```json
{
  "market_segments": ["marine_transportation", "offshore_oil_gas"],
  "commercial_signals": ["new_vessel_order"],
  "applications": ["propulsion", "genset"]
}
```

Only include segments and signals that are clearly mentioned or implied in the article."""


# =============================================================================
# QUERY SYSTEM PROMPT
# =============================================================================

KB_QUERY_SYSTEM_PROMPT = """You are an expert on medium-speed marine diesel engines.

Use the provided knowledge base context to answer questions about:
- Engine specifications (power, RPM, dimensions)
- Manufacturer information
- Application suitability
- Technical comparisons

If the context doesn't contain enough information, say so clearly.
Do not make up specifications - only use data from the provided context.

When comparing engines, consider:
- Power range overlap
- RPM compatibility with applications
- Fuel type options
- Physical dimensions and weight"""


# =============================================================================
# TARGET SPECIFICATIONS (from requirements)
# =============================================================================

# Target RPM range for medium-speed engines
TARGET_RPM_MIN = 300
TARGET_RPM_MAX = 1000

# Target power range in kW
TARGET_POWER_MIN_KW = 700
TARGET_POWER_MAX_KW = 40000


# =============================================================================
# TIER-1 MANUFACTURERS
# =============================================================================

TIER_1_MANUFACTURERS = [
    "Wärtsilä",
    "MAN Energy Solutions",
    "SEMT Pielstick",
    "Caterpillar MaK",
    "HD Hyundai HiMSEN",
    "Bergen Engines",
    "Daihatsu Diesel",
    "Niigata Power Systems",
    "ABC Engines",
]


# =============================================================================
# MATCHING THRESHOLDS
# =============================================================================

# Fuzzy matching threshold (rapidfuzz score 0-100)
FUZZY_MATCH_THRESHOLD = 0.85

# Semantic matching threshold (cosine similarity 0-1)
SEMANTIC_MATCH_THRESHOLD = 0.70

# Minimum entity extraction confidence
MIN_EXTRACTION_CONFIDENCE = 0.5


# =============================================================================
# API RATE LIMITS
# =============================================================================

# OpenAI embedding rate limit (requests per minute)
OPENAI_EMBEDDING_RPM = 3000

# OpenAI chat rate limit (requests per minute)
OPENAI_CHAT_RPM = 500

# Delay between batch operations (seconds)
BATCH_DELAY_SECONDS = 0.1
