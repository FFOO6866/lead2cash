"""
Entity Registry Database Service

Dedicated PostgreSQL database for company identity resolution.
Separate from the knowledge_base (kb_*) tables.
"""

import hashlib
import logging
import os
import uuid
from datetime import datetime, timezone
from typing import Any, Optional

import asyncpg

logger = logging.getLogger(__name__)


class EntityRegistryDatabase:
    """
    Database service for entity registry.

    Uses asyncpg for async PostgreSQL operations.
    Separate connection pool from knowledge_base database.
    """

    def __init__(self, database_url: Optional[str] = None):
        self._database_url = database_url or os.getenv("ENTITY_REGISTRY_DATABASE_URL")
        self._pool: Optional[asyncpg.Pool] = None
        self._initialized = False

    async def initialize(self) -> None:
        """Initialize database connection pool."""
        if self._initialized:
            return

        if not self._database_url:
            raise ValueError("ENTITY_REGISTRY_DATABASE_URL not configured")

        try:
            self._pool = await asyncpg.create_pool(
                self._database_url,
                min_size=2,
                max_size=10,
                command_timeout=30,
            )
            self._initialized = True
            logger.info("Entity registry database initialized")
        except Exception as e:
            logger.error(f"Failed to initialize entity registry database: {e}")
            raise

    async def close(self) -> None:
        """Close database connection pool."""
        if self._pool:
            await self._pool.close()
            self._pool = None
            self._initialized = False

    async def _get_pool(self) -> asyncpg.Pool:
        """Get connection pool, initializing if needed."""
        if not self._initialized:
            await self.initialize()
        if not self._pool:
            raise RuntimeError("Database pool not available")
        return self._pool

    # =========================================================================
    # Entity CRUD
    # =========================================================================

    async def get_entity_by_id(self, entity_id: str) -> Optional[dict]:
        """Get entity by ID."""
        pool = await self._get_pool()
        row = await pool.fetchrow(
            "SELECT * FROM entity_registry WHERE id = $1",
            uuid.UUID(entity_id),
        )
        return dict(row) if row else None

    async def get_entity_by_uen(self, uen: str) -> Optional[dict]:
        """Get entity by Singapore UEN (case-insensitive)."""
        if not uen:
            return None
        pool = await self._get_pool()
        # Use upper() on column to match the unique index idx_entity_registry_unique_uen
        row = await pool.fetchrow(
            """
            SELECT * FROM entity_registry
            WHERE upper(uen) = $1
            AND verification_status IN ('user_confirmed', 'externally_verified')
            """,
            uen.upper().strip(),
        )
        return dict(row) if row else None

    async def get_entity_by_lei(self, lei: str) -> Optional[dict]:
        """Get entity by LEI (case-insensitive)."""
        if not lei:
            return None
        pool = await self._get_pool()
        # Use upper() on column to match the unique index idx_entity_registry_unique_lei
        row = await pool.fetchrow(
            """
            SELECT * FROM entity_registry
            WHERE upper(lei) = $1
            AND verification_status IN ('user_confirmed', 'externally_verified')
            """,
            lei.upper().strip(),
        )
        return dict(row) if row else None

    async def search_entities_exact(self, name: str) -> list[dict]:
        """Search entities by exact normalized name."""
        pool = await self._get_pool()
        rows = await pool.fetch(
            """
            SELECT * FROM entity_registry
            WHERE lower(canonical_name) = lower($1)
            AND verification_status IN ('user_confirmed', 'externally_verified')
            ORDER BY created_at DESC
            LIMIT 10
            """,
            name.strip(),
        )
        return [dict(row) for row in rows]

    async def search_entities_fuzzy(
        self, name: str, threshold: float = 0.4, limit: int = 10
    ) -> list[dict]:
        """Search entities using trigram similarity."""
        pool = await self._get_pool()
        rows = await pool.fetch(
            """
            SELECT *, similarity(canonical_name, $1) AS sim_score
            FROM entity_registry
            WHERE similarity(canonical_name, $1) > $2
            AND verification_status IN ('user_confirmed', 'externally_verified')
            ORDER BY sim_score DESC
            LIMIT $3
            """,
            name.strip(),
            threshold,
            limit,
        )
        return [dict(row) for row in rows]

    async def search_by_alias(self, alias: str) -> list[dict]:
        """Search entities by alias."""
        pool = await self._get_pool()
        normalized = alias.lower().strip()
        rows = await pool.fetch(
            """
            SELECT e.*, a.alias_text, a.confidence as alias_confidence
            FROM entity_registry e
            JOIN entity_aliases a ON e.id = a.entity_id
            WHERE a.normalized_text = $1
            AND e.verification_status IN ('user_confirmed', 'externally_verified')
            ORDER BY a.confidence DESC
            LIMIT 10
            """,
            normalized,
        )
        return [dict(row) for row in rows]

    async def search_by_alias_fuzzy(
        self, alias: str, threshold: float = 0.4, limit: int = 10
    ) -> list[dict]:
        """Search aliases using trigram similarity."""
        pool = await self._get_pool()
        rows = await pool.fetch(
            """
            SELECT e.*, a.alias_text, similarity(a.alias_text, $1) AS sim_score
            FROM entity_registry e
            JOIN entity_aliases a ON e.id = a.entity_id
            WHERE similarity(a.alias_text, $1) > $2
            AND e.verification_status IN ('user_confirmed', 'externally_verified')
            ORDER BY sim_score DESC
            LIMIT $3
            """,
            alias.strip(),
            threshold,
            limit,
        )
        return [dict(row) for row in rows]

    async def search_entities_levenshtein(
        self, name: str, max_distance: int = 2, limit: int = 10
    ) -> list[dict]:
        """
        Search entities using Levenshtein edit distance.

        This catches common typos like "Maerks" -> "Maersk" that
        trigram similarity misses (transposition errors).

        Args:
            name: Company name to search
            max_distance: Maximum edit distance (default 2 for short names)
            limit: Maximum results to return

        Returns:
            List of entities with edit_distance field
        """
        pool = await self._get_pool()
        name_clean = name.strip().lower()

        try:
            # Try using levenshtein from fuzzystrmatch extension
            rows = await pool.fetch(
                """
                SELECT *, levenshtein(lower(canonical_name), $1) AS edit_distance
                FROM entity_registry
                WHERE levenshtein(lower(canonical_name), $1) <= $2
                AND verification_status IN ('user_confirmed', 'externally_verified')
                ORDER BY edit_distance ASC, created_at DESC
                LIMIT $3
                """,
                name_clean,
                max_distance,
                limit,
            )
            return [dict(row) for row in rows]
        except Exception as e:
            # fuzzystrmatch extension not available, fall back to trigram with lower threshold
            logger.debug(
                f"Levenshtein search not available, using trigram fallback: {e}"
            )
            # Use lower threshold (0.25) to catch more potential matches
            rows = await pool.fetch(
                """
                SELECT *, similarity(canonical_name, $1) AS sim_score
                FROM entity_registry
                WHERE similarity(canonical_name, $1) > 0.25
                AND verification_status IN ('user_confirmed', 'externally_verified')
                ORDER BY sim_score DESC
                LIMIT $2
                """,
                name.strip(),
                limit,
            )
            return [dict(row) for row in rows]

    async def search_by_alias_levenshtein(
        self, alias: str, max_distance: int = 2, limit: int = 10
    ) -> list[dict]:
        """
        Search aliases using Levenshtein edit distance.

        Args:
            alias: Alias text to search
            max_distance: Maximum edit distance
            limit: Maximum results to return

        Returns:
            List of entities with edit_distance field
        """
        pool = await self._get_pool()
        alias_clean = alias.strip().lower()

        try:
            rows = await pool.fetch(
                """
                SELECT e.*, a.alias_text, levenshtein(lower(a.alias_text), $1) AS edit_distance
                FROM entity_registry e
                JOIN entity_aliases a ON e.id = a.entity_id
                WHERE levenshtein(lower(a.alias_text), $1) <= $2
                AND e.verification_status IN ('user_confirmed', 'externally_verified')
                ORDER BY edit_distance ASC
                LIMIT $3
                """,
                alias_clean,
                max_distance,
                limit,
            )
            return [dict(row) for row in rows]
        except Exception as e:
            logger.debug(f"Levenshtein alias search not available: {e}")
            # Fallback to lower threshold trigram
            rows = await pool.fetch(
                """
                SELECT e.*, a.alias_text, similarity(a.alias_text, $1) AS sim_score
                FROM entity_registry e
                JOIN entity_aliases a ON e.id = a.entity_id
                WHERE similarity(a.alias_text, $1) > 0.25
                AND e.verification_status IN ('user_confirmed', 'externally_verified')
                ORDER BY sim_score DESC
                LIMIT $2
                """,
                alias.strip(),
                limit,
            )
            return [dict(row) for row in rows]

    async def create_entity(
        self,
        canonical_name: str,
        country_code: str,
        legal_name: Optional[str] = None,
        uen: Optional[str] = None,
        lei: Optional[str] = None,
        entity_type: str = "company",
        verification_status: str = "user_confirmed",
        verified_by: Optional[str] = None,
        acra_data: Optional[dict] = None,
        gleif_data: Optional[dict] = None,
        opencorporates_data: Optional[dict] = None,
    ) -> str:
        """
        Create new entity in registry or return existing if UEN/LEI matches.

        Uses atomic transaction with advisory lock to prevent race conditions.
        The advisory lock is based on the hash of UEN or LEI to ensure
        serialized access for the same identifier.

        Returns:
            Entity ID (either new or existing)
        """
        pool = await self._get_pool()

        # Normalize identifiers
        uen_upper = uen.upper().strip() if uen else None
        lei_upper = lei.upper().strip() if lei else None

        # Use a transaction with advisory lock for atomic get-or-create
        async with pool.acquire() as conn:
            async with conn.transaction():
                # Acquire advisory lock based on identifier hash
                # This serializes concurrent requests for the same UEN/LEI
                # Use hashlib for deterministic hashing (Python's hash() varies across sessions)
                lock_key = None
                if uen_upper:
                    lock_key = int(
                        hashlib.md5(f"uen:{uen_upper}".encode()).hexdigest()[:8], 16
                    ) % (2**31 - 1)
                elif lei_upper:
                    lock_key = int(
                        hashlib.md5(f"lei:{lei_upper}".encode()).hexdigest()[:8], 16
                    ) % (2**31 - 1)

                if lock_key is not None:
                    await conn.execute(
                        "SELECT pg_advisory_xact_lock($1)",
                        lock_key,
                    )

                # Check for existing entity (within transaction, after lock)
                # Include all verification statuses except 'invalid' to allow returning
                # archived entities (which can be reactivated) but not corrupted ones
                if uen_upper:
                    existing = await conn.fetchrow(
                        """
                        SELECT id FROM entity_registry
                        WHERE upper(uen) = $1
                        AND verification_status != 'invalid'
                        """,
                        uen_upper,
                    )
                    if existing:
                        logger.info(
                            f"Entity already exists with UEN {uen_upper}: {existing['id']}"
                        )
                        return str(existing["id"])

                if lei_upper:
                    existing = await conn.fetchrow(
                        """
                        SELECT id FROM entity_registry
                        WHERE upper(lei) = $1
                        AND verification_status != 'invalid'
                        """,
                        lei_upper,
                    )
                    if existing:
                        logger.info(
                            f"Entity already exists with LEI {lei_upper}: {existing['id']}"
                        )
                        return str(existing["id"])

                # Generate new ID and insert (within same transaction)
                entity_id = uuid.uuid4()

                try:
                    await conn.execute(
                        """
                        INSERT INTO entity_registry (
                            id, canonical_name, country_code, legal_name, uen, lei,
                            entity_type, verification_status, verified_by, verified_at,
                            acra_data, gleif_data, opencorporates_data
                        ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8::verification_status, $9, $10, $11, $12, $13)
                        """,
                        entity_id,
                        canonical_name,
                        country_code.upper(),
                        legal_name,
                        uen_upper,
                        lei_upper,
                        entity_type,
                        verification_status,
                        verified_by,
                        (
                            datetime.now(timezone.utc)
                            if verification_status != "unverified"
                            else None
                        ),
                        acra_data,
                        gleif_data,
                        opencorporates_data,
                    )
                    logger.info(
                        f"Created new entity: {entity_id} (UEN={uen_upper}, LEI={lei_upper})"
                    )
                    return str(entity_id)

                except asyncpg.UniqueViolationError as e:
                    # This shouldn't happen with advisory lock, but handle it anyway
                    logger.warning(f"Unexpected unique violation after lock: {e}")

                    # Look up the existing entity (match the filter used above)
                    if uen_upper:
                        existing = await conn.fetchrow(
                            """
                            SELECT id FROM entity_registry
                            WHERE upper(uen) = $1
                            AND verification_status != 'invalid'
                            """,
                            uen_upper,
                        )
                        if existing:
                            return str(existing["id"])

                    if lei_upper:
                        existing = await conn.fetchrow(
                            """
                            SELECT id FROM entity_registry
                            WHERE upper(lei) = $1
                            AND verification_status != 'invalid'
                            """,
                            lei_upper,
                        )
                        if existing:
                            return str(existing["id"])

                    # Re-raise if we still can't find it
                    raise

    async def update_entity(self, entity_id: str, **kwargs: Any) -> bool:
        """Update entity fields."""
        if not kwargs:
            return False

        pool = await self._get_pool()

        # Build SET clause
        set_parts = []
        values = []
        for i, (key, value) in enumerate(kwargs.items(), start=1):
            set_parts.append(f"{key} = ${i}")
            values.append(value)

        values.append(uuid.UUID(entity_id))

        query = f"""
            UPDATE entity_registry
            SET {", ".join(set_parts)}, updated_at = NOW()
            WHERE id = ${len(values)}
        """

        result = await pool.execute(query, *values)
        return result == "UPDATE 1"

    # =========================================================================
    # Alias Management
    # =========================================================================

    async def add_alias(
        self,
        entity_id: str,
        alias_text: str,
        alias_type: str = "common_name",
        source: str = "user_input",
        confidence: float = 1.0,
    ) -> str:
        """Add alias for entity."""
        pool = await self._get_pool()
        alias_id = uuid.uuid4()
        normalized = alias_text.lower().strip()

        await pool.execute(
            """
            INSERT INTO entity_aliases (id, entity_id, alias_text, normalized_text, alias_type, source, confidence)
            VALUES ($1, $2, $3, $4, $5, $6::entity_source_type, $7)
            ON CONFLICT (entity_id, normalized_text) DO UPDATE
            SET alias_text = EXCLUDED.alias_text, confidence = EXCLUDED.confidence
            """,
            alias_id,
            uuid.UUID(entity_id),
            alias_text,
            normalized,
            alias_type,
            source,
            confidence,
        )

        return str(alias_id)

    async def get_aliases(self, entity_id: str) -> list[dict]:
        """Get all aliases for entity."""
        pool = await self._get_pool()
        rows = await pool.fetch(
            "SELECT * FROM entity_aliases WHERE entity_id = $1 ORDER BY confidence DESC",
            uuid.UUID(entity_id),
        )
        return [dict(row) for row in rows]

    # =========================================================================
    # External Mappings
    # =========================================================================

    async def add_external_mapping(
        self,
        entity_id: str,
        external_system: str,
        external_id: str,
        external_data: Optional[dict] = None,
        verified: bool = False,
    ) -> str:
        """Add external system mapping for entity."""
        pool = await self._get_pool()
        mapping_id = uuid.uuid4()

        await pool.execute(
            """
            INSERT INTO entity_external_mappings (id, entity_id, external_system, external_id, external_data, verified, verified_at)
            VALUES ($1, $2, $3, $4, $5, $6, $7)
            ON CONFLICT (entity_id, external_system) DO UPDATE
            SET external_id = EXCLUDED.external_id, external_data = EXCLUDED.external_data,
                verified = EXCLUDED.verified, verified_at = EXCLUDED.verified_at
            """,
            mapping_id,
            uuid.UUID(entity_id),
            external_system.lower(),
            external_id,
            external_data,
            verified,
            datetime.now(timezone.utc) if verified else None,
        )

        return str(mapping_id)

    async def get_external_mapping(
        self, entity_id: str, external_system: str
    ) -> Optional[dict]:
        """Get external mapping for entity."""
        pool = await self._get_pool()
        row = await pool.fetchrow(
            "SELECT * FROM entity_external_mappings WHERE entity_id = $1 AND external_system = $2",
            uuid.UUID(entity_id),
            external_system.lower(),
        )
        return dict(row) if row else None

    async def get_entity_by_external_id(
        self, external_system: str, external_id: str
    ) -> Optional[dict]:
        """Get entity by external system ID."""
        pool = await self._get_pool()
        row = await pool.fetchrow(
            """
            SELECT e.* FROM entity_registry e
            JOIN entity_external_mappings m ON e.id = m.entity_id
            WHERE m.external_system = $1 AND m.external_id = $2
            """,
            external_system.lower(),
            external_id,
        )
        return dict(row) if row else None

    # =========================================================================
    # Resolution History
    # =========================================================================

    async def record_resolution(
        self,
        session_id: str,
        user_query: str,
        resolution_type: str,
        entity_id: Optional[str] = None,
        candidates_presented: Optional[list] = None,
        selected_rank: Optional[int] = None,
        response_time_ms: Optional[int] = None,
    ) -> str:
        """Record entity resolution attempt."""
        pool = await self._get_pool()
        history_id = uuid.uuid4()

        await pool.execute(
            """
            INSERT INTO entity_resolution_history (
                id, session_id, user_query, resolution_type, entity_id,
                candidates_presented, selected_rank, response_time_ms
            ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8)
            """,
            history_id,
            session_id,
            user_query,
            resolution_type,
            uuid.UUID(entity_id) if entity_id else None,
            candidates_presented,
            selected_rank,
            response_time_ms,
        )

        return str(history_id)

    # =========================================================================
    # Migration Support
    # =========================================================================

    async def run_migration(self, migration_sql: str) -> None:
        """Run SQL migration."""
        pool = await self._get_pool()
        await pool.execute(migration_sql)
        logger.info("Migration executed successfully")


# Singleton instance
_db_instance: Optional[EntityRegistryDatabase] = None


def get_entity_registry_db() -> EntityRegistryDatabase:
    """Get singleton database instance."""
    global _db_instance
    if _db_instance is None:
        _db_instance = EntityRegistryDatabase()
    return _db_instance
