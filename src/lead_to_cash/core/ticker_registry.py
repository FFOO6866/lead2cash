"""
Centralized ticker mappings to mitigate EODHD search issues for regional exchanges.

LIMITATION: This registry only covers explicitly mapped companies (~30 SGX stocks).
For unmapped companies, the EODHD search fallback may still return incorrect exchanges.
SGX has ~700 listed companies; this is a partial mitigation, not a complete solution.

EODHD search API issues:
- Returns Frankfurt/OTC listings before SGX for Singapore companies
- Marks ADRs as "isPrimary" instead of the actual home exchange listing
- Example: "Singapore Technologies" returns SJX.F (Frankfurt) first, SGGKY.US (ADR) as primary

To add a new company:
1. Add entry to KNOWN_TICKERS below
2. Run: pytest tests/unit/core/test_ticker_registry.py -v

FUTURE IMPROVEMENT (TODO):
Consider caching SGX ticker list from EODHD /exchange/SG endpoint at startup
to automatically cover all SGX-listed companies without manual maintenance.
See: https://eodhd.com/api/exchange-symbol-list/SG
"""

import logging

logger = logging.getLogger(__name__)


# Simple mapping: lowercase company name -> ticker symbol
# No redundant search_name field - if we have the ticker, we don't need to search
KNOWN_TICKERS: dict[str, str] = {
    # ============================================================
    # Singapore Exchange (SGX) - Major Companies
    # ============================================================
    # ST Engineering (S63.SG)
    "st engineering": "S63.SG",
    "st engineering ltd": "S63.SG",
    "st eng": "S63.SG",
    "stengg": "S63.SG",
    "ste": "S63.SG",
    "singapore technologies": "S63.SG",
    "singapore technologies engineering": "S63.SG",
    "singapore technologies engineering ltd": "S63.SG",
    # Sembcorp Industries (U96.SG)
    "sembcorp": "U96.SG",
    "sembcorp industries": "U96.SG",
    # Keppel Corporation (BN4.SG)
    "keppel": "BN4.SG",
    "keppel corporation": "BN4.SG",
    "keppel corp": "BN4.SG",
    # DBS Group (D05.SG)
    "dbs": "D05.SG",
    "dbs group": "D05.SG",
    "dbs bank": "D05.SG",
    # OCBC Bank (O39.SG)
    "ocbc": "O39.SG",
    "ocbc bank": "O39.SG",
    "oversea-chinese banking": "O39.SG",
    # UOB (U11.SG)
    "uob": "U11.SG",
    "united overseas bank": "U11.SG",
    # Singtel (Z74.SG)
    "singtel": "Z74.SG",
    "singapore telecommunications": "Z74.SG",
    "singapore telecom": "Z74.SG",
    # CapitaLand Investment (9CI.SG)
    "capitaland": "9CI.SG",
    "capitaland investment": "9CI.SG",
    # Wilmar International (F34.SG)
    "wilmar": "F34.SG",
    "wilmar international": "F34.SG",
    # ============================================================
    # Additional SGX Companies
    # ============================================================
    # Seatrium (5E2.SG) - formerly Sembcorp Marine + Keppel O&M
    "seatrium": "5E2.SG",
    "sembcorp marine": "5E2.SG",
    # ComfortDelGro (C52.SG)
    "comfortdelgro": "C52.SG",
    "comfort delgro": "C52.SG",
    "cdg": "C52.SG",
    # Genting Singapore (G13.SG)
    "genting singapore": "G13.SG",
    "genting sg": "G13.SG",
    # Yangzijiang Shipbuilding (BS6.SG)
    "yangzijiang": "BS6.SG",
    "yangzijiang shipbuilding": "BS6.SG",
    "yzj": "BS6.SG",
    # Jardine Cycle & Carriage (C07.SG)
    "jardine cycle": "C07.SG",
    "jardine cycle & carriage": "C07.SG",
    # Thai Beverage (Y92.SG)
    "thai beverage": "Y92.SG",
    "thaibev": "Y92.SG",
    # Venture Corporation (V03.SG)
    "venture": "V03.SG",
    "venture corporation": "V03.SG",
    # City Developments (C09.SG)
    "city developments": "C09.SG",
    "cdl": "C09.SG",
    # Singapore Airlines (C6L.SG)
    "singapore airlines": "C6L.SG",
    "sia": "C6L.SG",
    # SATS (S58.SG)
    "sats": "S58.SG",
    "sats ltd": "S58.SG",
    # ============================================================
    # REITs
    # ============================================================
    "mapletree logistics": "M44U.SG",
    "mlt": "M44U.SG",
    "capitaland integrated": "C38U.SG",
    "cict": "C38U.SG",
    "ascendas reit": "A17U.SG",
    "ascendas": "A17U.SG",
    # ============================================================
    # Marine & Offshore (Relevant to MTU/RRPS business)
    # ============================================================
    "marco polo marine": "5LY.SG",
    "penguin international": "BTM.SG",
    "asl marine": "A04.SG",
    "pacific radiance": "T8V.SG",
}

# Preferred exchanges for fallback selection (in priority order)
# US is LAST to prioritize home exchange listings (SG, HK) over ADRs for Asian companies
# but still selected for actual US companies when no other preferred exchange is found
PREFERRED_EXCHANGES: list[str] = ["SG", "HK", "LSE", "XETRA", "US"]

# Exchanges where isPrimary flag should NOT be trusted in the FIRST pass
# US is included to prevent ADRs (marked isPrimary) from beating home exchange listings
# However, US is still in PREFERRED_EXCHANGES so legitimate US companies are found via second pass
# OTC/Pink Sheet listings are often incorrectly marked as primary
UNTRUSTED_PRIMARY_EXCHANGES: set[str] = {"US", "PNK", "OTC", "OTCQX", "OTCQB", "F"}


# Legal suffixes to strip during ticker lookup (longest-first within each group).
# Only pure legal-entity suffixes — NOT business words like "group" or "holdings"
# which are often part of the actual company name.
_LEGAL_SUFFIXES = [
    " pte. ltd.",
    " pte. ltd",
    " pte ltd",
    " pvt. ltd.",
    " pvt. ltd",
    " pvt ltd",
    " pty. ltd.",
    " pty. ltd",
    " pty ltd",
    " ltd.",
    " ltd",
    " inc.",
    " inc",
    " corp.",
    " corp",
    " co.",
    " gmbh",
    " ag",
    " sa",
    " se",
    " a/s",
    " as",
    " asa",
    " plc",
    " llc",
    " lp",
    " llp",
    " bv",
    " nv",
]


def resolve_ticker(company_name: str) -> str | None:
    """
    Return known ticker symbol for a company, or None to trigger search fallback.

    Tries exact match first, then strips ONE legal suffix (Ltd, Inc, GmbH, etc.)
    to handle SAP customer names like "ST Engineering Ltd" matching "st engineering".
    Only strips the first matching suffix — no chain-stripping.

    Args:
        company_name: Company name (case-insensitive)

    Returns:
        Ticker symbol (e.g., "S63.SG") or None if not in registry
    """
    name = company_name.strip().lower()

    # Exact match
    result = KNOWN_TICKERS.get(name)
    if result:
        return result

    # Strip first matching legal suffix and retry (single pass only)
    for suffix in _LEGAL_SUFFIXES:
        if name.endswith(suffix):
            stripped = name[: -len(suffix)].rstrip()
            if not stripped:
                break  # Don't look up empty string
            result = KNOWN_TICKERS.get(stripped)
            if result:
                logger.debug(
                    f"Ticker resolved after stripping suffix '{suffix}': "
                    f"'{company_name}' -> {result}"
                )
                return result
            break  # Only strip ONE suffix — no chain-stripping

    return None


def select_best_listing(
    results: list[dict], company_name: str | None = None
) -> dict | None:
    """
    Select the best listing from EODHD search results.

    Selection priority:
    1. Listing marked as isPrimary ON A TRUSTED EXCHANGE (SG, HK, LSE, XETRA)
    2. Listing on preferred exchange (SG > HK > LSE > XETRA) - US excluded
    3. Listing marked as isPrimary on untrusted exchange (US, OTC) - last resort
    4. First result as fallback

    Args:
        results: List of EODHD search results
        company_name: Optional company name for logging context

    Returns:
        Best matching result dict, or None if empty
    """
    if not results:
        return None

    context = f" for '{company_name}'" if company_name else ""

    # First pass: find primary listing on TRUSTED exchange only
    for r in results:
        exchange = r.get("Exchange")
        # Skip results with missing or empty Exchange field
        if not exchange:
            continue
        if r.get("isPrimary") and exchange not in UNTRUSTED_PRIMARY_EXCHANGES:
            logger.debug(
                f"Selected primary listing on trusted exchange: "
                f"{r.get('Code')}.{r.get('Exchange')}{context}"
            )
            return r

    # Second pass: prefer exchanges in priority order (US excluded)
    for exchange in PREFERRED_EXCHANGES:
        for r in results:
            if r.get("Exchange") == exchange:
                logger.debug(
                    f"Selected {exchange} listing (preferred exchange): "
                    f"{r.get('Code')}.{r.get('Exchange')}{context}"
                )
                return r

    # Third pass: accept isPrimary on untrusted exchange as last resort
    for r in results:
        if r.get("isPrimary"):
            logger.warning(
                f"Using isPrimary on untrusted exchange {r.get('Exchange')}: "
                f"{r.get('Code')}.{r.get('Exchange')}{context} - may be ADR/OTC"
            )
            return r

    # Fallback to first result
    logger.warning(
        f"Fallback to first search result: {results[0].get('Code')}."
        f"{results[0].get('Exchange')}{context} - no preferred exchange found"
    )
    return results[0]


def log_fallback_warning(company_name: str) -> None:
    """
    Log a warning when falling back to EODHD search for unknown company.

    Call this when resolve_ticker() returns None to track missing mappings.

    Args:
        company_name: Original company name from user query
    """
    logger.warning(
        f"TICKER_REGISTRY_MISS: No known ticker for '{company_name}', "
        f"using EODHD search fallback. "
        f"Consider adding to ticker_registry.py if this is a major SGX company."
    )


def get_registry_stats() -> dict:
    """
    Return statistics about the ticker registry for monitoring.

    Returns:
        Dict with counts of unique tickers, aliases, etc.
    """
    unique_tickers = set(KNOWN_TICKERS.values())

    return {
        "total_aliases": len(KNOWN_TICKERS),
        "unique_tickers": len(unique_tickers),
        "exchanges_covered": list(set(t.split(".")[-1] for t in unique_tickers)),
    }
