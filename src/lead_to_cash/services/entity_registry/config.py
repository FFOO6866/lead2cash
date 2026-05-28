"""
Entity Resolution Configuration

Single source of truth for entity resolution thresholds and settings.
Both EntityResolutionService and EntityResolutionAgent import from here.

This module has NO dependencies on other entity_registry modules to avoid
circular imports.
"""

import os

# =============================================================================
# Auto-Confirmation Thresholds
# =============================================================================

# Auto-confirm if top candidate confidence >= this threshold
# Value is a percentage (0-100)
AUTO_CONFIRM_THRESHOLD_PERCENT = 80.0

# Auto-confirm if margin between top and second candidate >= this threshold
# Value is a percentage (0-100)
MARGIN_THRESHOLD_PERCENT = 15.0

# For backward compatibility / ratio-based code
AUTO_CONFIRM_THRESHOLD_RATIO = AUTO_CONFIRM_THRESHOLD_PERCENT / 100  # 0.80
MARGIN_THRESHOLD_RATIO = MARGIN_THRESHOLD_PERCENT / 100  # 0.15


# =============================================================================
# Search Configuration
# =============================================================================

# Fuzzy search minimum similarity threshold (pg_trgm)
FUZZY_SEARCH_THRESHOLD = 0.4

# Maximum candidates to return
MAX_CANDIDATES = 5

# Maximum ReAct cycles before stopping
MAX_REACT_CYCLES = 5


# =============================================================================
# LLM Configuration
# =============================================================================

# Default LLM model for entity resolution agent
DEFAULT_LLM_MODEL = os.getenv("OPENAI_PROD_MODEL", "gpt-4o")

# LLM temperature for consistent reasoning
LLM_TEMPERATURE = 0.1

# Max tokens for LLM response
LLM_MAX_TOKENS = 1500

# Timeout for LLM API calls (seconds)
LLM_TIMEOUT_SECONDS = 60.0
