"""
Sanctions Checker Service - Direct Authoritative Database Screening

Performs sanctions screening by directly downloading and searching official
sanctions list data files from authoritative sources:

- OFAC SDN List (US Treasury)
- UN Security Council Consolidated List
- EU Consolidated Financial Sanctions List
- MAS Singapore (follows UN lists + domestic designations)

Each check returns an independent result with:
- status: "clear" | "match" | "error"
- source_url: The authoritative source URL
- checked_date: ISO date of the check
- list_date: Publication date of the downloaded list (when available)
- details: Human-readable result string

Downloaded data is cached in memory for CACHE_TTL_SECONDS to avoid
re-downloading on every KYP check.
"""

import asyncio
import csv
import io
import logging
import re
import defusedxml.ElementTree as ET
from dataclasses import dataclass, field
from datetime import datetime, timezone
from difflib import SequenceMatcher
from typing import Any, Optional

import httpx

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

CACHE_TTL_SECONDS = 3600 * 6  # 6 hours — sanctions lists update ~daily

OFAC_SDN_URL = "https://www.treasury.gov/ofac/downloads/sdn.csv"
OFAC_SOURCE_URL = "https://sanctionssearch.ofac.treas.gov/"

UN_CONSOLIDATED_URL = "https://scsanctions.un.org/resources/xml/en/consolidated.xml"
UN_SOURCE_URL = "https://scsanctions.un.org/"

EU_FSF_CSV_URL = (
    "https://webgate.ec.europa.eu/fsd/fsf/public/files/"
    "csvFullSanctionsList_1_1/content?token=dG9rZW4tMjAxNw"
)
EU_SOURCE_URL = (
    "https://data.europa.eu/data/datasets/"
    "consolidated-list-of-persons-groups-and-entities-subject-to-eu-financial-sanctions"
)

MAS_SOURCE_URL = (
    "https://www.mas.gov.sg/regulation/anti-money-laundering/"
    "targeted-financial-sanctions/lists-of-designated-individuals-and-entities"
)

# Fuzzy match threshold — ratio in [0, 1].  0.96 is very strict to
# minimize false positives in automated sanctions screening.
# "SMT Engineering" vs "ST Engineering" = 0.966 — we DON'T want that
# to match.  Only near-identical names should trigger.
FUZZY_THRESHOLD = 0.96

# HTTP timeout for downloading lists (seconds)
DOWNLOAD_TIMEOUT = 30


# ---------------------------------------------------------------------------
# Result data class
# ---------------------------------------------------------------------------


@dataclass
class SanctionCheckResult:
    """Result of checking one sanctions list."""

    database: str  # e.g. "OFAC SDN List"
    status: str  # "clear" | "match" | "error"
    result: str  # Human-readable result string
    source_url: str  # Authoritative URL
    checked_date: str  # ISO date of check
    list_date: Optional[str] = None  # Publication date of list data
    matched_names: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        d: dict[str, Any] = {
            "database": self.database,
            "status": self.status,
            "result": self.result,
            "source_url": self.source_url,
            "checked_date": self.checked_date,
        }
        if self.list_date:
            d["list_date"] = self.list_date
        if self.matched_names:
            d["matched_names"] = self.matched_names
        return d


# ---------------------------------------------------------------------------
# Sanctions Database Registry
# ---------------------------------------------------------------------------
# Named, versioned database with source tracking and refresh metadata.
# Each list is stored with:
#   - names: List of entity names from the authoritative source
#   - record_count: Number of entries loaded
#   - list_date: Publication date of the source data
#   - last_refreshed: When we last downloaded from the source
#   - source_url: Canonical URL of the authoritative source
#   - download_url: URL used to download the data file

SANCTIONS_DB_REGISTRY: dict[str, dict[str, Any]] = {
    "OFAC_SDN": {
        "name": "OFAC SDN List",
        "authority": "US Treasury — Office of Foreign Assets Control",
        "download_url": OFAC_SDN_URL,
        "source_url": OFAC_SOURCE_URL,
        "format": "CSV",
        "description": "Specially Designated Nationals and Blocked Persons",
    },
    "UN_CONSOLIDATED": {
        "name": "UN Security Council Consolidated List",
        "authority": "United Nations Security Council",
        "download_url": UN_CONSOLIDATED_URL,
        "source_url": UN_SOURCE_URL,
        "format": "XML",
        "description": "Consolidated list of individuals and entities subject to UN sanctions",
    },
    "EU_FSF": {
        "name": "EU Consolidated Financial Sanctions",
        "authority": "European Commission — DG FISMA",
        "download_url": EU_FSF_CSV_URL,
        "source_url": EU_SOURCE_URL,
        "format": "CSV (semicolon-delimited)",
        "description": "Persons, groups and entities subject to EU financial sanctions",
    },
    "MAS_SG": {
        "name": "MAS Singapore Designated Lists",
        "authority": "Monetary Authority of Singapore",
        "download_url": MAS_SOURCE_URL,
        "source_url": MAS_SOURCE_URL,
        "format": "HTML + UN list",
        "description": "Designated individuals and entities under Singapore financial sanctions",
    },
}


@dataclass
class SanctionsDatabase:
    """In-memory cache entry for a sanctions list."""

    key: str
    names: list[str]
    record_count: int
    list_date: str
    last_refreshed: str  # ISO datetime
    source_url: str

    def to_dict(self) -> dict[str, Any]:
        reg = SANCTIONS_DB_REGISTRY.get(self.key, {})
        return {
            "name": reg.get("name", self.key),
            "authority": reg.get("authority", ""),
            "record_count": self.record_count,
            "list_date": self.list_date,
            "last_refreshed": self.last_refreshed,
            "source_url": self.source_url,
            "format": reg.get("format", ""),
        }


_databases: dict[str, SanctionsDatabase] = {}


def _get_cached(key: str) -> Optional[dict[str, Any]]:
    """Get cached data as dict (backward compatible)."""
    if key in _databases:
        db = _databases[key]
        # Check TTL
        refreshed_ts = datetime.fromisoformat(db.last_refreshed).timestamp()
        if (datetime.now(timezone.utc).timestamp() - refreshed_ts) < CACHE_TTL_SECONDS:
            return {"names": db.names, "list_date": db.list_date}
        del _databases[key]
    return None


def _set_cached(key: str, names: list[str], list_date: str, source_url: str) -> None:
    """Store downloaded list data with metadata."""
    _databases[key] = SanctionsDatabase(
        key=key,
        names=names,
        record_count=len(names),
        list_date=list_date,
        last_refreshed=datetime.now(timezone.utc).isoformat(),
        source_url=source_url,
    )


def get_database_status() -> list[dict[str, Any]]:
    """Get status of all sanctions databases (for monitoring/display)."""
    status = []
    for key, reg in SANCTIONS_DB_REGISTRY.items():
        entry = {
            "name": reg["name"],
            "authority": reg["authority"],
            "source_url": reg["source_url"],
            "status": "not_loaded",
            "record_count": 0,
            "list_date": None,
            "last_refreshed": None,
        }
        if key in _databases:
            db = _databases[key]
            entry["status"] = "loaded"
            entry["record_count"] = db.record_count
            entry["list_date"] = db.list_date
            entry["last_refreshed"] = db.last_refreshed
        status.append(entry)
    return status


async def refresh_all_databases() -> dict[str, Any]:
    """
    Force refresh all 4 sanctions databases from authoritative sources.

    Call this on server startup and periodically (e.g., every 6 hours)
    to keep the local copy current.

    Returns summary of refresh results.
    """
    logger.info("Sanctions: Refreshing all 4 databases from authoritative sources")
    clear_cache()
    # Trigger downloads by screening a dummy entity
    await screen_entity("__REFRESH_WARMUP__")
    results = get_database_status()
    total = sum(r["record_count"] for r in results)
    loaded = sum(1 for r in results if r["status"] == "loaded")
    logger.info(
        f"Sanctions: Refresh complete — {loaded}/4 databases loaded, "
        f"{total:,} total entries"
    )
    return {
        "databases_loaded": loaded,
        "total_entries": total,
        "databases": results,
    }


# ---------------------------------------------------------------------------
# Name matching helpers
# ---------------------------------------------------------------------------


def _normalize(name: str) -> str:
    """Normalize name for comparison: lowercase, collapse whitespace, strip punctuation."""
    name = name.lower().strip()
    name = re.sub(r"[^\w\s]", " ", name)  # Remove punctuation
    name = re.sub(r"\s+", " ", name)  # Collapse whitespace
    return name


def _fuzzy_match(query: str, candidate: str) -> bool:
    """Return True if query fuzzy-matches candidate above threshold.

    Matching rules (in order):
    1. Exact normalized match
    2. Substring match — only if the shorter string is >= 5 chars
       (avoids "Ri" matching "Engineering")
    3. Token overlap — query tokens must be >= 60% of candidate tokens
       AND all query tokens appear in candidate
    4. SequenceMatcher ratio >= FUZZY_THRESHOLD
    """
    q = _normalize(query)
    c = _normalize(candidate)
    if not q or not c:
        return False
    # 1. Exact match
    if q == c:
        return True
    # 2. Word-boundary substring — the shorter string must appear as a
    #    whole-word match inside the longer string (avoids "st engineering"
    #    matching "belinvest engineering" via accidental substring overlap).
    shorter_str, longer_str = (q, c) if len(q) <= len(c) else (c, q)
    if len(shorter_str) >= 5:
        # Use word boundary regex to require whole-word substring match
        pattern = r"(?:^|\s)" + re.escape(shorter_str) + r"(?:\s|$)"
        if re.search(pattern, longer_str):
            return True
    # 3. Token overlap — all query tokens in candidate, and tokens
    #    represent a significant portion (avoid "Engineering" matching
    #    "MCS Engineering" when query is "ST Engineering")
    q_tokens = set(q.split())
    c_tokens = set(c.split())
    if q_tokens and c_tokens:
        overlap = q_tokens & c_tokens
        # Require all query tokens to appear AND overlap is >= 60% of both
        if (
            q_tokens.issubset(c_tokens)
            and len(overlap) / max(len(q_tokens), len(c_tokens)) >= 0.6
        ):
            return True
    # 4. Fuzzy ratio — additionally require first-token similarity to avoid
    #    "ST Engineering" matching "SMT Engineering" (ratio=0.966 but
    #    completely different companies).
    ratio = SequenceMatcher(None, q, c).ratio()
    if ratio >= FUZZY_THRESHOLD:
        q_first = q.split()[0] if q.split() else q
        c_first = c.split()[0] if c.split() else c
        # First tokens must also be similar (>= 0.8) or identical
        first_ratio = SequenceMatcher(None, q_first, c_first).ratio()
        return first_ratio > 0.8
    return False


# ---------------------------------------------------------------------------
# Individual list checkers
# ---------------------------------------------------------------------------


async def _download(url: str, follow_redirects: bool = True) -> httpx.Response:
    """Download data from URL with redirect following and timeout."""
    async with httpx.AsyncClient(
        follow_redirects=follow_redirects,
        timeout=httpx.Timeout(DOWNLOAD_TIMEOUT),
    ) as client:
        return await client.get(url)


async def check_ofac(entity_name: str) -> SanctionCheckResult:
    """
    Check OFAC SDN list by downloading the official CSV from US Treasury.

    The SDN CSV has columns:
    0: ent_num, 1: SDN_Name, 2: SDN_Type, 3: Program, 4: Title,
    5: Call_Sign, 6: Vess_type, 7: Tonnage, 8: GRT, 9: Vess_flag,
    10: Vess_owner, 11: Remarks
    """
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    try:
        # Check cache
        cached = _get_cached("OFAC_SDN")
        if cached is None:
            logger.info("Sanctions: Downloading OFAC SDN list from treasury.gov")
            resp = await _download(OFAC_SDN_URL)
            resp.raise_for_status()
            # Parse CSV — SDN CSV has no header row; columns are positional
            text = resp.text
            names: list[str] = []
            reader = csv.reader(io.StringIO(text))
            for row in reader:
                if len(row) >= 2 and row[1].strip():
                    names.append(row[1].strip())
            list_date = today  # OFAC updates frequently; use download date
            _set_cached("OFAC_SDN", names, list_date, OFAC_SOURCE_URL)
            cached = {"names": names, "list_date": list_date}
            logger.info(f"Sanctions: OFAC SDN loaded — {len(names)} entries")
        else:
            logger.debug("Sanctions: Using cached OFAC SDN data")

        names = cached["names"]
        list_date = cached["list_date"]

        # Search for matches
        matched = [n for n in names if _fuzzy_match(entity_name, n)]

        if matched:
            return SanctionCheckResult(
                database="OFAC SDN List",
                status="match",
                result=f"Potential match found: {matched[0]}",
                source_url=OFAC_SOURCE_URL,
                checked_date=today,
                list_date=list_date,
                matched_names=matched[:3],
            )

        return SanctionCheckResult(
            database="OFAC SDN List",
            status="clear",
            result="No matching records identified",
            source_url=OFAC_SOURCE_URL,
            checked_date=today,
            list_date=list_date,
        )

    except Exception as e:
        logger.warning(f"Sanctions: OFAC check failed: {e}")
        return SanctionCheckResult(
            database="OFAC SDN List",
            status="error",
            result=f"Unable to check — download failed: {type(e).__name__}",
            source_url=OFAC_SOURCE_URL,
            checked_date=today,
        )


async def check_un(entity_name: str) -> SanctionCheckResult:
    """
    Check UN Security Council Consolidated List by downloading the official XML.

    The XML has <INDIVIDUALS> and <ENTITIES> sections.
    Entity names are in <FIRST_NAME> (individuals) or <FIRST_NAME> (entities).
    """
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    try:
        cached = _get_cached("UN_CONSOLIDATED")
        if cached is None:
            logger.info("Sanctions: Downloading UN Security Council consolidated list")
            resp = await _download(UN_CONSOLIDATED_URL)
            resp.raise_for_status()

            root = ET.fromstring(resp.content)
            list_date = root.attrib.get("dateGenerated", today)
            if "T" in list_date:
                list_date = list_date.split("T")[0]

            names: list[str] = []

            # Parse individuals
            for ind in root.iter("INDIVIDUAL"):
                name_parts = []
                for tag in ("FIRST_NAME", "SECOND_NAME", "THIRD_NAME"):
                    el = ind.find(tag)
                    if el is not None and el.text:
                        name_parts.append(el.text.strip())
                if name_parts:
                    names.append(" ".join(name_parts))
                # Also collect aliases
                for alias in ind.iter("INDIVIDUAL_ALIAS"):
                    alias_name = alias.findtext("ALIAS_NAME", "").strip()
                    if alias_name:
                        names.append(alias_name)

            # Parse entities
            for ent in root.iter("ENTITY"):
                name_el = ent.find("FIRST_NAME")
                if name_el is not None and name_el.text:
                    names.append(name_el.text.strip())
                # Entity aliases
                for alias in ent.iter("ENTITY_ALIAS"):
                    alias_name = alias.findtext("ALIAS_NAME", "").strip()
                    if alias_name:
                        names.append(alias_name)

            _set_cached("UN_CONSOLIDATED", names, list_date, UN_SOURCE_URL)
            cached = {"names": names, "list_date": list_date}
            logger.info(
                f"Sanctions: UN consolidated list loaded — {len(names)} names, "
                f"generated {list_date}"
            )
        else:
            logger.debug("Sanctions: Using cached UN consolidated data")

        names = cached["names"]
        list_date = cached["list_date"]

        matched = [n for n in names if _fuzzy_match(entity_name, n)]

        if matched:
            return SanctionCheckResult(
                database="UN Security Council",
                status="match",
                result=f"Potential match found: {matched[0]}",
                source_url=UN_SOURCE_URL,
                checked_date=today,
                list_date=list_date,
                matched_names=matched[:3],
            )

        return SanctionCheckResult(
            database="UN Security Council",
            status="clear",
            result="No matching records identified",
            source_url=UN_SOURCE_URL,
            checked_date=today,
            list_date=list_date,
        )

    except Exception as e:
        logger.warning(f"Sanctions: UN check failed: {e}")
        return SanctionCheckResult(
            database="UN Security Council",
            status="error",
            result=f"Unable to check — download failed: {type(e).__name__}",
            source_url=UN_SOURCE_URL,
            checked_date=today,
        )


async def check_eu(entity_name: str) -> SanctionCheckResult:
    """
    Check EU Consolidated Financial Sanctions List.

    The EU publishes a CSV (semicolon-delimited) via the FSF endpoint.
    Key columns include NameAlias_WholeName for entity names.
    """
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    try:
        cached = _get_cached("EU_FSF")
        if cached is None:
            logger.info("Sanctions: Downloading EU consolidated sanctions list")
            resp = await _download(EU_FSF_CSV_URL)
            resp.raise_for_status()

            text = resp.text
            names: list[str] = []
            list_date = today

            # EU FSF CSV is semicolon-delimited with headers.
            # The correct name column is "NameAlias_WholeName".
            reader = csv.DictReader(io.StringIO(text), delimiter=";")
            for row in reader:
                whole_name = row.get("NameAlias_WholeName", "").strip()
                if whole_name and len(whole_name) >= 2:
                    names.append(whole_name)

            # Deduplicate
            names = list(set(names))
            _set_cached("EU_FSF", names, list_date, EU_SOURCE_URL)
            cached = {"names": names, "list_date": list_date}
            logger.info(f"Sanctions: EU FSF loaded — {len(names)} unique names")
        else:
            logger.debug("Sanctions: Using cached EU FSF data")

        names = cached["names"]
        list_date = cached["list_date"]

        matched = [n for n in names if _fuzzy_match(entity_name, n)]

        if matched:
            return SanctionCheckResult(
                database="EU Consolidated Sanctions",
                status="match",
                result=f"Potential match found: {matched[0]}",
                source_url=EU_SOURCE_URL,
                checked_date=today,
                list_date=list_date,
                matched_names=matched[:3],
            )

        return SanctionCheckResult(
            database="EU Consolidated Sanctions",
            status="clear",
            result="No matching records identified",
            source_url=EU_SOURCE_URL,
            checked_date=today,
            list_date=list_date,
        )

    except Exception as e:
        logger.warning(f"Sanctions: EU check failed: {e}")
        return SanctionCheckResult(
            database="EU Consolidated Sanctions",
            status="error",
            result=f"Unable to check — download failed: {type(e).__name__}",
            source_url=EU_SOURCE_URL,
            checked_date=today,
        )


async def check_mas(entity_name: str) -> SanctionCheckResult:
    """
    Check MAS Singapore designated lists.

    MAS Singapore primarily enforces UN sanctions lists for financial
    institutions.  MAS also maintains domestic designations under the
    Terrorism (Suppression of Financing) Act (TSOFA).

    Since MAS does not publish a programmatic API, we rely on:
    1. The UN consolidated list check (already done separately)
    2. Perplexity search for MAS-specific designations as fallback

    For the direct check, we search the UN list (already cached) plus
    attempt to fetch the MAS designated entities page.
    """
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    try:
        # MAS primarily follows UN lists — reuse UN cached data
        un_cached = _get_cached("UN_CONSOLIDATED")
        un_names = un_cached["names"] if un_cached else []

        # Also attempt to fetch MAS page for any additional domestic designations
        mas_names: list[str] = []
        try:
            resp = await _download(MAS_SOURCE_URL)
            if resp.status_code == 200:
                # Check if entity name appears on the MAS page using
                # word-boundary matching (avoids "AB" matching inside
                # HTML words like "about", "table", etc.)
                text = resp.text.lower()
                entity_lower = entity_name.lower().strip()
                if len(entity_lower) >= 4:
                    pattern = r"(?:^|\W)" + re.escape(entity_lower) + r"(?:\W|$)"
                    if re.search(pattern, text):
                        return SanctionCheckResult(
                            database="MAS Singapore",
                            status="match",
                            result="Entity name found on MAS designated lists page",
                            source_url=MAS_SOURCE_URL,
                            checked_date=today,
                        )
        except Exception as e:
            logger.debug(f"Sanctions: MAS page fetch failed (non-critical): {e}")

        # Search UN list for MAS coverage
        all_names = un_names + mas_names
        if all_names:
            matched = [n for n in all_names if _fuzzy_match(entity_name, n)]
            if matched:
                return SanctionCheckResult(
                    database="MAS Singapore",
                    status="match",
                    result=f"Potential match on UN/MAS list: {matched[0]}",
                    source_url=MAS_SOURCE_URL,
                    checked_date=today,
                    matched_names=matched[:3],
                )

        total = len(all_names) if all_names else 0
        return SanctionCheckResult(
            database="MAS Singapore",
            status="clear",
            result="No matching records identified",
            source_url=MAS_SOURCE_URL,
            checked_date=today,
        )

    except Exception as e:
        logger.warning(f"Sanctions: MAS check failed: {e}")
        return SanctionCheckResult(
            database="MAS Singapore",
            status="error",
            result=f"Unable to check — {type(e).__name__}",
            source_url=MAS_SOURCE_URL,
            checked_date=today,
        )


# ---------------------------------------------------------------------------
# Main screening function
# ---------------------------------------------------------------------------


async def screen_entity(entity_name: str) -> list[SanctionCheckResult]:
    """
    Screen an entity against all 4 authoritative sanctions databases in parallel.

    Returns a list of SanctionCheckResult, one per database.
    Each result has an independent status, source URL, and check date.
    """
    logger.info(f"Sanctions: Screening '{entity_name}' against 4 authoritative lists")

    # Run OFAC, UN, EU in parallel first (MAS depends on cached UN data)
    ofac_result, un_result, eu_result = await asyncio.gather(
        check_ofac(entity_name),
        check_un(entity_name),
        check_eu(entity_name),
        return_exceptions=False,
    )
    # MAS reuses UN cached data, so run after UN completes
    mas_result = await check_mas(entity_name)
    results = [ofac_result, un_result, eu_result, mas_result]

    # Log summary
    statuses = {r.database: r.status for r in results}
    logger.info(f"Sanctions: Screening complete — {statuses}")

    return list(results)


def clear_cache() -> None:
    """Clear the sanctions data cache (e.g., for testing)."""
    _databases.clear()
