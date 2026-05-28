"""
Persistent Sanctions Database — PostgreSQL-backed sanctions screening.

Replaces the in-memory download-on-demand approach with a database-backed
store that persists across container restarts. Data is refreshed from
authoritative sources (OFAC, UN, EU, MAS) when stale (>24 hours).

KYP screening queries the database instead of downloading 50K+ entries
from 4 government websites live, eliminating the 15-20s cold-start penalty.
"""

import asyncio
import csv
import io
import logging
import os
import re
from datetime import datetime, timezone, timedelta
from difflib import SequenceMatcher
from pathlib import Path
from typing import Any, Optional

import asyncpg
import httpx

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

REFRESH_INTERVAL_HOURS = 24  # Refresh from sources every 24 hours
DOWNLOAD_TIMEOUT = 30  # HTTP timeout for downloads (seconds)
FUZZY_THRESHOLD = 0.96  # Very strict to minimize false positives

# Source URLs
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

MIGRATION_FILE = (
    Path(__file__).parent / "migrations" / "001_create_sanctions_tables.sql"
)


# ---------------------------------------------------------------------------
# Name matching (same logic as original sanctions_checker.py)
# ---------------------------------------------------------------------------


def _normalize(name: str) -> str:
    """Normalize name: lowercase, strip punctuation, collapse whitespace."""
    name = name.lower().strip()
    name = re.sub(r"[^\w\s]", " ", name)
    name = re.sub(r"\s+", " ", name)
    return name


def _fuzzy_match(query: str, candidate: str) -> bool:
    """4-tier fuzzy matching: exact → substring → token overlap → SequenceMatcher."""
    q = _normalize(query)
    c = _normalize(candidate)
    if not q or not c:
        return False
    if q == c:
        return True
    shorter_str, longer_str = (q, c) if len(q) <= len(c) else (c, q)
    if len(shorter_str) >= 5:
        pattern = r"(?:^|\s)" + re.escape(shorter_str) + r"(?:\s|$)"
        if re.search(pattern, longer_str):
            return True
    q_tokens = set(q.split())
    c_tokens = set(c.split())
    if q_tokens and c_tokens:
        overlap = q_tokens & c_tokens
        if (
            q_tokens.issubset(c_tokens)
            and len(overlap) / max(len(q_tokens), len(c_tokens)) >= 0.6
        ):
            return True
    ratio = SequenceMatcher(None, q, c).ratio()
    if ratio >= FUZZY_THRESHOLD:
        q_first = q.split()[0] if q.split() else q
        c_first = c.split()[0] if c.split() else c
        first_ratio = SequenceMatcher(None, q_first, c_first).ratio()
        return first_ratio > 0.8
    return False


# ---------------------------------------------------------------------------
# Result dataclass (same as original)
# ---------------------------------------------------------------------------

from dataclasses import dataclass, field


@dataclass
class SanctionCheckResult:
    """Result of checking one sanctions list."""

    database: str
    status: str  # "clear" | "match" | "error"
    result: str
    source_url: str
    checked_date: str
    list_date: Optional[str] = None
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
# Sanctions Database Service
# ---------------------------------------------------------------------------


class SanctionsDatabaseService:
    """PostgreSQL-backed sanctions screening service."""

    def __init__(self, database_url: Optional[str] = None):
        self._database_url = database_url or os.environ.get("DATABASE_URL", "")
        self._pool: Optional[asyncpg.Pool] = None
        self._initialized = False

    async def initialize(self) -> bool:
        """Initialize DB pool, run migration, refresh if stale."""
        if self._initialized:
            return True
        if not self._database_url:
            logger.warning("Sanctions DB: No DATABASE_URL configured")
            return False
        try:
            self._pool = await asyncpg.create_pool(
                self._database_url,
                min_size=1,
                max_size=3,
                command_timeout=30,
                server_settings={"jit": "off"},
            )
            await self._run_migration()
            self._initialized = True
            logger.info("Sanctions DB: Initialized")
            return True
        except Exception as e:
            logger.error(f"Sanctions DB: Init failed: {e}")
            return False

    async def _run_migration(self):
        """Apply the sanctions table migration."""
        if not MIGRATION_FILE.exists():
            logger.warning(f"Sanctions DB: Migration file not found: {MIGRATION_FILE}")
            return
        sql = MIGRATION_FILE.read_text()
        async with self._pool.acquire() as conn:
            await conn.execute(sql)
        logger.info("Sanctions DB: Migration applied")

    async def is_stale(self) -> bool:
        """Check if any source needs refreshing (>24hrs or not loaded)."""
        async with self._pool.acquire() as conn:
            row = await conn.fetchrow(
                """
                SELECT COUNT(*) as total,
                       COUNT(*) FILTER (
                           WHERE status = 'loaded'
                           AND last_refreshed > NOW() - INTERVAL '24 hours'
                       ) as fresh
                FROM sanctions_list_metadata
                """
            )
            return row["fresh"] < row["total"]

    async def get_entry_count(self) -> int:
        """Total entries in the database."""
        async with self._pool.acquire() as conn:
            return await conn.fetchval("SELECT COUNT(*) FROM sanctions_entries")

    # ------------------------------------------------------------------
    # Download + parse from authoritative sources
    # ------------------------------------------------------------------

    async def refresh_all(self) -> dict[str, Any]:
        """Download all 4 sanctions lists and bulk-insert into PostgreSQL."""
        logger.info("Sanctions DB: Refreshing all 4 lists from authoritative sources")
        results = await asyncio.gather(
            self._refresh_ofac(),
            self._refresh_un(),
            self._refresh_eu(),
            return_exceptions=True,
        )
        # MAS uses UN data, refresh after UN is loaded
        mas_result = await self._refresh_mas()

        total = await self.get_entry_count()
        loaded = 0
        async with self._pool.acquire() as conn:
            rows = await conn.fetch(
                "SELECT source_key, record_count, status FROM sanctions_list_metadata"
            )
            loaded = sum(1 for r in rows if r["status"] == "loaded")

        summary = {
            "databases_loaded": loaded,
            "total_entries": total,
            "errors": [str(r) for r in results if isinstance(r, Exception)],
        }
        logger.info(
            f"Sanctions DB: Refresh complete — {loaded}/4 loaded, "
            f"{total:,} total entries"
        )
        return summary

    async def _bulk_insert(
        self,
        source_key: str,
        entries: list[tuple[str, str, bool]],  # (name, normalized, is_alias)
        list_date: str,
    ):
        """Replace all entries for a source and update metadata."""
        from datetime import date as _date

        # Convert string date to date object for asyncpg
        try:
            _list_date = _date.fromisoformat(list_date)
        except (ValueError, TypeError):
            _list_date = _date.today()

        async with self._pool.acquire() as conn:
            async with conn.transaction():
                # Delete old entries for this source
                await conn.execute(
                    "DELETE FROM sanctions_entries WHERE source_key = $1",
                    source_key,
                )
                # Bulk insert
                if entries:
                    await conn.executemany(
                        """
                        INSERT INTO sanctions_entries
                            (source_key, entity_name, entity_name_normalized, is_alias)
                        VALUES ($1, $2, $3, $4)
                        """,
                        [
                            (source_key, name, norm, alias)
                            for name, norm, alias in entries
                        ],
                    )
                # Update metadata
                await conn.execute(
                    """
                    UPDATE sanctions_list_metadata
                    SET record_count = $2, list_date = $3,
                        last_refreshed = NOW(), status = 'loaded'
                    WHERE source_key = $1
                    """,
                    source_key,
                    len(entries),
                    _list_date,
                )
        logger.info(f"Sanctions DB: {source_key} loaded — {len(entries)} entries")

    async def _refresh_ofac(self):
        """Download and store OFAC SDN list."""
        today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        try:
            await self._update_status("OFAC_SDN", "loading")
            resp = await _download(OFAC_SDN_URL)
            resp.raise_for_status()
            entries = []
            reader = csv.reader(io.StringIO(resp.text))
            for row in reader:
                if len(row) >= 2 and row[1].strip():
                    name = row[1].strip()
                    entries.append((name, _normalize(name), False))
            await self._bulk_insert("OFAC_SDN", entries, today)
        except Exception as e:
            logger.error(f"Sanctions DB: OFAC refresh failed: {e}")
            await self._update_status("OFAC_SDN", "error")
            raise

    async def _refresh_un(self):
        """Download and store UN Security Council consolidated list."""
        today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        try:
            await self._update_status("UN_CONSOLIDATED", "loading")
            import defusedxml.ElementTree as ET

            resp = await _download(UN_CONSOLIDATED_URL)
            resp.raise_for_status()
            root = ET.fromstring(resp.content)

            # Extract list date from root attribute
            list_date = root.attrib.get("dateGenerated", today)
            if "T" in list_date:
                list_date = list_date.split("T")[0]

            entries = []
            # Individuals
            for ind in root.iter("INDIVIDUAL"):
                parts = []
                for tag in ("FIRST_NAME", "SECOND_NAME", "THIRD_NAME"):
                    el = ind.find(tag)
                    if el is not None and el.text:
                        parts.append(el.text.strip())
                if parts:
                    name = " ".join(parts)
                    entries.append((name, _normalize(name), False))
                # Aliases
                for alias_el in ind.iter("INDIVIDUAL_ALIAS"):
                    alias_name_el = alias_el.find("ALIAS_NAME")
                    if alias_name_el is not None and alias_name_el.text:
                        aname = alias_name_el.text.strip()
                        entries.append((aname, _normalize(aname), True))

            # Entities
            for ent in root.iter("ENTITY"):
                name_el = ent.find("FIRST_NAME")
                if name_el is not None and name_el.text:
                    name = name_el.text.strip()
                    entries.append((name, _normalize(name), False))
                for alias_el in ent.iter("ENTITY_ALIAS"):
                    alias_name_el = alias_el.find("ALIAS_NAME")
                    if alias_name_el is not None and alias_name_el.text:
                        aname = alias_name_el.text.strip()
                        entries.append((aname, _normalize(aname), True))

            await self._bulk_insert("UN_CONSOLIDATED", entries, list_date)
        except Exception as e:
            logger.error(f"Sanctions DB: UN refresh failed: {e}")
            await self._update_status("UN_CONSOLIDATED", "error")
            raise

    async def _refresh_eu(self):
        """Download and store EU consolidated financial sanctions list."""
        today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        try:
            await self._update_status("EU_FSF", "loading")
            resp = await _download(EU_FSF_CSV_URL)
            resp.raise_for_status()
            entries = []
            seen = set()
            reader = csv.DictReader(io.StringIO(resp.text), delimiter=";")
            for row in reader:
                whole_name = row.get("NameAlias_WholeName", "").strip()
                if whole_name and len(whole_name) >= 2 and whole_name not in seen:
                    seen.add(whole_name)
                    entries.append((whole_name, _normalize(whole_name), False))
            await self._bulk_insert("EU_FSF", entries, today)
        except Exception as e:
            logger.error(f"Sanctions DB: EU refresh failed: {e}")
            await self._update_status("EU_FSF", "error")
            raise

    async def _refresh_mas(self):
        """MAS Singapore enforces UN sanctions — copy UN entries + mark as MAS."""
        try:
            await self._update_status("MAS_SG", "loading")
            async with self._pool.acquire() as conn:
                # Count UN entries (MAS enforces the same list)
                un_count = await conn.fetchval(
                    "SELECT COUNT(*) FROM sanctions_entries WHERE source_key = 'UN_CONSOLIDATED'"
                )
                un_date = await conn.fetchval(
                    "SELECT list_date FROM sanctions_list_metadata WHERE source_key = 'UN_CONSOLIDATED'"
                )
                # MAS doesn't have a separate downloadable list — it enforces UN sanctions.
                # We record the UN data as MAS's backing data.
                await conn.execute(
                    """
                    UPDATE sanctions_list_metadata
                    SET record_count = $1, list_date = $2,
                        last_refreshed = NOW(), status = 'loaded'
                    WHERE source_key = 'MAS_SG'
                    """,
                    un_count,
                    un_date,
                )
            logger.info(f"Sanctions DB: MAS_SG linked to UN data ({un_count} entries)")
        except Exception as e:
            logger.error(f"Sanctions DB: MAS refresh failed: {e}")
            await self._update_status("MAS_SG", "error")

    async def _update_status(self, source_key: str, status: str):
        async with self._pool.acquire() as conn:
            await conn.execute(
                "UPDATE sanctions_list_metadata SET status = $2 WHERE source_key = $1",
                source_key,
                status,
            )

    # ------------------------------------------------------------------
    # Screening — query PostgreSQL instead of in-memory cache
    # ------------------------------------------------------------------

    async def screen_entity(self, entity_name: str) -> list[SanctionCheckResult]:
        """Screen entity against all 4 lists stored in PostgreSQL."""
        today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        entity_normalized = _normalize(entity_name)

        if not self._initialized or not self._pool:
            logger.warning("Sanctions DB not initialized, cannot screen")
            return [
                SanctionCheckResult(
                    database=db_name,
                    status="error",
                    result="Sanctions database not available",
                    source_url="",
                    checked_date=today,
                )
                for db_name in [
                    "OFAC SDN List",
                    "UN Security Council",
                    "EU Consolidated Sanctions",
                    "MAS Singapore",
                ]
            ]

        # Load metadata
        async with self._pool.acquire() as conn:
            meta_rows = await conn.fetch(
                "SELECT source_key, source_name, source_url, list_date, status "
                "FROM sanctions_list_metadata ORDER BY source_key"
            )

        # For each source, load candidate names and fuzzy-match
        results = []
        for meta in meta_rows:
            source_key = meta["source_key"]
            db_name = meta["source_name"]
            source_url = meta["source_url"] or ""
            list_date = str(meta["list_date"]) if meta["list_date"] else None
            status = meta["status"]

            if status != "loaded":
                results.append(
                    SanctionCheckResult(
                        database=db_name,
                        status="error",
                        result=f"List not loaded (status: {status})",
                        source_url=source_url,
                        checked_date=today,
                    )
                )
                continue

            # For MAS, screen against UN entries (MAS enforces UN sanctions)
            query_source = "UN_CONSOLIDATED" if source_key == "MAS_SG" else source_key

            # Pre-filter: get candidates where normalized name shares tokens
            # with the query. This avoids loading 50K names into Python.
            query_tokens = entity_normalized.split()
            if query_tokens:
                # Use ANY token to pre-filter (broad net, fuzzy_match narrows)
                token_conditions = " OR ".join(
                    f"entity_name_normalized LIKE '%' || ${i + 2} || '%'"
                    for i in range(len(query_tokens))
                )
                candidates = await self._pool.fetch(
                    f"""
                    SELECT entity_name FROM sanctions_entries
                    WHERE source_key = $1 AND ({token_conditions})
                    """,
                    query_source,
                    *query_tokens,
                )
            else:
                candidates = []

            # Fuzzy match in Python (preserves exact same matching logic)
            matched = [
                r["entity_name"]
                for r in candidates
                if _fuzzy_match(entity_name, r["entity_name"])
            ]

            if matched:
                results.append(
                    SanctionCheckResult(
                        database=db_name,
                        status="match",
                        result=f"Potential match found: {matched[0]}",
                        source_url=source_url,
                        checked_date=today,
                        list_date=list_date,
                        matched_names=matched[:3],
                    )
                )
            else:
                results.append(
                    SanctionCheckResult(
                        database=db_name,
                        status="clear",
                        result="No matching records identified",
                        source_url=source_url,
                        checked_date=today,
                        list_date=list_date,
                    )
                )

        return results

    async def get_database_status(self) -> list[dict[str, Any]]:
        """Get status of all sanctions databases."""
        async with self._pool.acquire() as conn:
            rows = await conn.fetch(
                "SELECT * FROM sanctions_list_metadata ORDER BY source_key"
            )
        return [dict(r) for r in rows]

    async def close(self):
        if self._pool:
            await self._pool.close()
            self._pool = None


# ---------------------------------------------------------------------------
# Module-level helper (download)
# ---------------------------------------------------------------------------


async def _download(url: str) -> httpx.Response:
    """Download data from URL with redirect following."""
    async with httpx.AsyncClient(
        follow_redirects=True,
        timeout=httpx.Timeout(DOWNLOAD_TIMEOUT),
    ) as client:
        return await client.get(url)


# ---------------------------------------------------------------------------
# Module-level singleton
# ---------------------------------------------------------------------------

_service: Optional[SanctionsDatabaseService] = None


async def get_sanctions_service() -> SanctionsDatabaseService:
    """Get or create the singleton sanctions service."""
    global _service
    if _service is None:
        _service = SanctionsDatabaseService()
    if not _service._initialized:
        await _service.initialize()
    return _service
