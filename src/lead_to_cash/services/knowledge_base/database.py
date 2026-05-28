"""
Marine Engine Knowledge Base - Database Service

PostgreSQL database operations with asyncpg connection pool
and pgvector support for semantic search.

Production features:
- Configurable query timeouts (per-operation and global)
- Connection health checks with automatic cleanup
- Pool statistics for monitoring
- Safe table name handling (whitelist validation)
- Input validation and proper exception handling

Follows the same patterns as competitor_intel/database.py
for consistency across the codebase.
"""

import asyncio
import os
from pathlib import Path
from typing import Any, Optional

import asyncpg

from lead_to_cash.services.knowledge_base.cache_events import (
    CacheEventType,
    get_cache_event_publisher,
)
from lead_to_cash.services.knowledge_base.exceptions import (
    KBConfigurationError,
    KBValidationError,
)
from lead_to_cash.services.knowledge_base.models import (
    Application,
    ArticleScore,
    EngineApplicationMap,
    EngineModel,
    EngineSeries,
    EntityAlias,
    Manufacturer,
    MarketSegment,
)
from lead_to_cash.services.knowledge_base.tracing import trace_operation
from lead_to_cash.services.knowledge_base.unified_models import (
    AvailabilityStatus,
    DutyClass,
    EngineRating,
    ISOClassification,
)
from lead_to_cash.services.knowledge_base.validation import (
    validate_entity_type,
    validate_float_range,
    validate_id,
    validate_positive_int,
    validate_text,
)
from lead_to_cash.utils.logging import get_logger

# Use structured logger with correlation ID support
logger = get_logger(__name__)

# Whitelist of allowed table names for safe SQL operations
ALLOWED_TABLES = frozenset(
    {
        "kb_manufacturers",
        "kb_engine_series",
        "kb_engine_models",
        "kb_applications",
        "kb_market_segments",
        "kb_entity_aliases",
        "kb_article_entities",
        "kb_article_scores",
        "kb_engine_application_map",
        "kb_engine_competitor_map",
        # ADR-004: Rating-level tables
        "kb_engine_ratings",
        "kb_customer_requirements",
        "kb_rating_competitor_map",
        "kb_competitor_engagements",
        "kb_product_fit_results",
    }
)


class KnowledgeBaseDatabase:
    """
    Database service for Marine Engine Knowledge Base.

    Uses asyncpg for async PostgreSQL operations with pgvector
    support for semantic search.

    Usage:
        db = KnowledgeBaseDatabase()
        await db.initialize()

        # CRUD operations
        await db.create_manufacturer(manufacturer)
        mfr = await db.get_manufacturer(id)
        manufacturers = await db.list_manufacturers(tier=1)

        # Vector search
        results = await db.search_aliases_by_embedding(embedding, top_k=10)

        await db.close()
    """

    # Default timeouts (seconds)
    DEFAULT_COMMAND_TIMEOUT = 30.0
    DEFAULT_QUERY_TIMEOUT = 10.0
    DEFAULT_HEALTH_CHECK_TIMEOUT = 5.0

    # Pool configuration
    DEFAULT_MIN_POOL_SIZE = 2
    DEFAULT_MAX_POOL_SIZE = 10
    DEFAULT_MAX_INACTIVE_CONNECTION_LIFETIME = 300.0  # 5 minutes

    def __init__(
        self,
        database_url: Optional[str] = None,
        command_timeout: float = DEFAULT_COMMAND_TIMEOUT,
        query_timeout: float = DEFAULT_QUERY_TIMEOUT,
        min_pool_size: int = DEFAULT_MIN_POOL_SIZE,
        max_pool_size: int = DEFAULT_MAX_POOL_SIZE,
        max_inactive_connection_lifetime: float = DEFAULT_MAX_INACTIVE_CONNECTION_LIFETIME,
    ):
        """
        Initialize database service.

        Args:
            database_url: PostgreSQL connection URL. Defaults to DATABASE_URL env var.
            command_timeout: Default timeout for commands (DDL, migrations)
            query_timeout: Default timeout for queries (SELECT, INSERT, etc.)
            min_pool_size: Minimum connections in pool
            max_pool_size: Maximum connections in pool
            max_inactive_connection_lifetime: Close idle connections after this many seconds

        Note: Database URL validation is deferred until actual connection
        to allow service construction without environment variables.
        """
        # Store provided URL or defer to env var lookup
        self._database_url = database_url
        self._pool: Optional[asyncpg.Pool] = None
        self._initialized = False

        # Timeout configuration
        self._command_timeout = command_timeout
        self._query_timeout = query_timeout
        self._health_check_timeout = self.DEFAULT_HEALTH_CHECK_TIMEOUT

        # Pool configuration
        self._min_pool_size = min_pool_size
        self._max_pool_size = max_pool_size
        self._max_inactive_connection_lifetime = max_inactive_connection_lifetime

    @property
    def database_url(self) -> str:
        """Get database URL, validating on first access."""
        url = self._database_url or os.getenv("DATABASE_URL")
        if not url:
            raise KBConfigurationError(
                message="Database URL not configured",
                config_key="DATABASE_URL",
            )
        return url

    @property
    def pool(self) -> asyncpg.Pool:
        """Get the connection pool, raising if not initialized."""
        if self._pool is None:
            raise KBConfigurationError(
                message="Database not initialized. Call initialize() first.",
                config_key="pool",
            )
        return self._pool

    async def initialize(self) -> None:
        """Initialize connection pool and create tables."""
        if self._initialized:
            return

        logger.info("Initializing Knowledge Base database...")

        # Create connection pool with production settings
        self._pool = await asyncpg.create_pool(
            self.database_url,
            min_size=self._min_pool_size,
            max_size=self._max_pool_size,
            command_timeout=self._command_timeout,
            max_inactive_connection_lifetime=self._max_inactive_connection_lifetime,
        )

        # Enable pgvector and create tables
        await self._run_migrations()
        self._initialized = True

        logger.info(
            "Knowledge Base database initialized successfully",
            extra={
                "pool_size": f"{self._min_pool_size}-{self._max_pool_size}",
                "command_timeout": self._command_timeout,
                "query_timeout": self._query_timeout,
            },
        )

    async def _run_migrations(self) -> None:
        """Run SQL migrations to create tables."""
        migration_path = (
            Path(__file__).parent / "migrations" / "001_create_kb_tables.sql"
        )

        if not migration_path.exists():
            logger.warning(f"Migration file not found: {migration_path}")
            return

        sql = migration_path.read_text()

        async with self.pool.acquire() as conn:
            # Execute migration in a transaction
            async with conn.transaction():
                await conn.execute(sql)

        logger.info("Knowledge Base migrations completed")

    async def close(self) -> None:
        """Close connection pool."""
        if self._pool:
            await self._pool.close()
            self._pool = None
            self._initialized = False
            logger.info("Knowledge Base database connection closed")

    def _validate_table_name(self, table_name: str) -> str:
        """
        Validate table name against whitelist.

        Args:
            table_name: Table name to validate

        Returns:
            The validated table name

        Raises:
            KBValidationError: If table name is not in whitelist
        """
        if table_name not in ALLOWED_TABLES:
            raise KBValidationError(
                message="Invalid table name",
                field="table_name",
                expected=f"one of {sorted(ALLOWED_TABLES)}",
                actual=table_name,
            )
        return table_name

    async def _execute_with_timeout(
        self,
        conn: asyncpg.Connection,
        query: str,
        *args,
        timeout: Optional[float] = None,
    ) -> Any:
        """
        Execute a query with configurable timeout.

        Args:
            conn: Database connection
            query: SQL query
            *args: Query parameters
            timeout: Query timeout in seconds (defaults to query_timeout)

        Returns:
            Query result
        """
        timeout = timeout or self._query_timeout
        return await asyncio.wait_for(
            conn.execute(query, *args),
            timeout=timeout,
        )

    async def _fetchval_with_timeout(
        self,
        conn: asyncpg.Connection,
        query: str,
        *args,
        timeout: Optional[float] = None,
    ) -> Any:
        """
        Fetch a single value with configurable timeout.

        Args:
            conn: Database connection
            query: SQL query
            *args: Query parameters
            timeout: Query timeout in seconds (defaults to query_timeout)

        Returns:
            Single value result
        """
        timeout = timeout or self._query_timeout
        return await asyncio.wait_for(
            conn.fetchval(query, *args),
            timeout=timeout,
        )

    async def get_pool_stats(self) -> dict[str, Any]:
        """
        Get connection pool statistics for monitoring.

        Returns:
            Pool statistics including size, free, used connections
        """
        if not self._pool:
            return {
                "initialized": False,
                "size": 0,
                "free_size": 0,
                "used_size": 0,
                "min_size": self._min_pool_size,
                "max_size": self._max_pool_size,
            }

        return {
            "initialized": True,
            "size": self._pool.get_size(),
            "free_size": self._pool.get_idle_size(),
            "used_size": self._pool.get_size() - self._pool.get_idle_size(),
            "min_size": self._pool.get_min_size(),
            "max_size": self._pool.get_max_size(),
        }

    async def health_check(self) -> dict[str, Any]:
        """Check database health and return statistics.

        Returns:
            Health status with service_id, status, pool info, and table counts
        """
        from datetime import datetime, timezone

        if not self._pool:
            return {
                "service_id": "kb_database",
                "status": "unhealthy",
                "healthy": False,  # Backward compatibility
                "error": "Pool not initialized",
                "timestamp": datetime.now(timezone.utc).isoformat(),
            }

        try:
            async with self.pool.acquire() as conn:
                # Check connection with timeout
                await self._fetchval_with_timeout(
                    conn, "SELECT 1", timeout=self._health_check_timeout
                )

                # Get table counts (using safe table list)
                counts = {}
                # Use static list instead of ALLOWED_TABLES to ensure consistency
                tables = [
                    ("kb_manufacturers", "manufacturers"),
                    ("kb_engine_series", "engine_series"),
                    ("kb_engine_models", "engine_models"),
                    ("kb_applications", "applications"),
                    ("kb_market_segments", "market_segments"),
                    ("kb_entity_aliases", "entity_aliases"),
                    ("kb_article_entities", "article_entities"),
                    ("kb_article_scores", "article_scores"),
                ]

                for table_name, display_name in tables:
                    # Validate table name for safety
                    self._validate_table_name(table_name)
                    # Use parameterized-like approach with validated table
                    count = await self._fetchval_with_timeout(
                        conn,
                        f"SELECT COUNT(*) FROM {table_name}",  # Safe: table_name validated
                        timeout=self._health_check_timeout,
                    )
                    counts[display_name] = count

                pool_stats = await self.get_pool_stats()

                return {
                    "service_id": "kb_database",
                    "status": "healthy",
                    "healthy": True,  # Backward compatibility
                    "pool": pool_stats,
                    "counts": counts,
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                }

        except asyncio.TimeoutError:
            logger.error(
                "Health check timed out", extra={"timeout": self._health_check_timeout}
            )
            return {
                "service_id": "kb_database",
                "status": "unhealthy",
                "healthy": False,
                "error": f"Health check timed out after {self._health_check_timeout}s",
                "timestamp": datetime.now(timezone.utc).isoformat(),
            }
        except Exception as e:
            logger.error(f"Health check failed: {e}")
            return {
                "service_id": "kb_database",
                "status": "unhealthy",
                "healthy": False,  # Backward compatibility
                "error": str(e),
                "timestamp": datetime.now(timezone.utc).isoformat(),
            }

    # =========================================================================
    # MANUFACTURER OPERATIONS
    # =========================================================================

    @trace_operation("db_create_manufacturer")
    async def create_manufacturer(self, manufacturer: Manufacturer) -> str:
        """Create a new manufacturer."""
        # Validate input fields
        validate_id(manufacturer.id, "manufacturer.id")
        validate_text(
            manufacturer.name, "manufacturer.name", min_length=1, max_length=200
        )
        if manufacturer.tier is not None:
            validate_positive_int(
                manufacturer.tier, "manufacturer.tier", min_value=1, max_value=3
            )
        async with self.pool.acquire() as conn:
            await conn.execute(
                """
                INSERT INTO kb_manufacturers (id, name, country, tier, website, description, is_active)
                VALUES ($1, $2, $3, $4, $5, $6, $7)
                """,
                manufacturer.id,
                manufacturer.name,
                manufacturer.country,
                manufacturer.tier,
                manufacturer.website,
                manufacturer.description,
                manufacturer.is_active,
            )

        # Publish cache invalidation event
        publisher = get_cache_event_publisher()
        await publisher.publish(
            CacheEventType.MANUFACTURER_CREATED,
            entity_id=manufacturer.id,
            entity_type="manufacturer",
        )

        return manufacturer.id

    @trace_operation("db_get_manufacturer")
    async def get_manufacturer(self, manufacturer_id: str) -> Optional[Manufacturer]:
        """Get manufacturer by ID."""
        manufacturer_id = validate_id(manufacturer_id, "manufacturer_id")
        async with self.pool.acquire() as conn:
            row = await conn.fetchrow(
                "SELECT * FROM kb_manufacturers WHERE id = $1", manufacturer_id
            )

        if not row:
            return None

        return Manufacturer(
            id=row["id"],
            name=row["name"],
            country=row["country"],
            tier=row["tier"],
            website=row["website"],
            description=row["description"],
            is_active=row["is_active"],
            created_at=row["created_at"],
            updated_at=row["updated_at"],
        )

    @trace_operation("db_get_manufacturer_by_name")
    async def get_manufacturer_by_name(self, name: str) -> Optional[Manufacturer]:
        """Get manufacturer by exact name match."""
        name = validate_text(name, "name", min_length=1, max_length=200)
        async with self.pool.acquire() as conn:
            row = await conn.fetchrow(
                "SELECT * FROM kb_manufacturers WHERE LOWER(name) = LOWER($1)", name
            )

        if not row:
            return None

        return Manufacturer(
            id=row["id"],
            name=row["name"],
            country=row["country"],
            tier=row["tier"],
            website=row["website"],
            description=row["description"],
            is_active=row["is_active"],
            created_at=row["created_at"],
            updated_at=row["updated_at"],
        )

    @trace_operation("db_list_manufacturers")
    async def list_manufacturers(
        self,
        tier: Optional[int] = None,
        is_active: bool = True,
        limit: int = 100,
    ) -> list[Manufacturer]:
        """List manufacturers with optional filters."""
        limit = validate_positive_int(limit, "limit", min_value=1, max_value=1000)
        if tier is not None:
            tier = validate_positive_int(tier, "tier", min_value=1, max_value=3)
        query = "SELECT * FROM kb_manufacturers WHERE is_active = $1"
        params: list[Any] = [is_active]

        if tier is not None:
            query += " AND tier = $2"
            params.append(tier)

        query += f" ORDER BY tier, name LIMIT {limit}"

        async with self.pool.acquire() as conn:
            rows = await conn.fetch(query, *params)

        return [
            Manufacturer(
                id=row["id"],
                name=row["name"],
                country=row["country"],
                tier=row["tier"],
                website=row["website"],
                description=row["description"],
                is_active=row["is_active"],
                created_at=row["created_at"],
                updated_at=row["updated_at"],
            )
            for row in rows
        ]

    @trace_operation(
        "db_bulk_create_manufacturers",
        lambda manufacturers, **_: {
            "count": len(manufacturers) if manufacturers else 0
        },
    )
    async def bulk_create_manufacturers(self, manufacturers: list[Manufacturer]) -> int:
        """Bulk create manufacturers. Returns count of inserted rows."""
        if not manufacturers:
            return 0

        # Validate all manufacturers
        for i, m in enumerate(manufacturers):
            validate_id(m.id, f"manufacturers[{i}].id")
            validate_text(
                m.name, f"manufacturers[{i}].name", min_length=1, max_length=200
            )

        async with self.pool.acquire() as conn:
            await conn.executemany(
                """
                INSERT INTO kb_manufacturers (id, name, country, tier, website, description, is_active)
                VALUES ($1, $2, $3, $4, $5, $6, $7)
                ON CONFLICT (name) DO UPDATE SET
                    description = EXCLUDED.description,
                    website = EXCLUDED.website,
                    is_active = EXCLUDED.is_active
                """,
                [
                    (
                        m.id,
                        m.name,
                        m.country,
                        m.tier,
                        m.website,
                        m.description,
                        m.is_active,
                    )
                    for m in manufacturers
                ],
            )

        return len(manufacturers)

    # =========================================================================
    # ENGINE SERIES OPERATIONS
    # =========================================================================

    @trace_operation("db_create_engine_series")
    async def create_engine_series(self, series: EngineSeries) -> str:
        """Create a new engine series."""
        # Validate input fields
        validate_id(series.id, "series.id")
        validate_id(series.manufacturer_id, "series.manufacturer_id")
        validate_text(
            series.series_name, "series.series_name", min_length=1, max_length=200
        )
        async with self.pool.acquire() as conn:
            await conn.execute(
                """
                INSERT INTO kb_engine_series
                (id, manufacturer_id, brand, series_name, description, generation,
                 year_introduced, year_discontinued, is_current)
                VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9)
                """,
                series.id,
                series.manufacturer_id,
                series.brand,
                series.series_name,
                series.description,
                series.generation,
                series.year_introduced,
                series.year_discontinued,
                series.is_current,
            )
        return series.id

    @trace_operation("db_get_engine_series")
    async def get_engine_series(self, series_id: str) -> Optional[EngineSeries]:
        """Get engine series by ID."""
        series_id = validate_id(series_id, "series_id")
        async with self.pool.acquire() as conn:
            row = await conn.fetchrow(
                "SELECT * FROM kb_engine_series WHERE id = $1", series_id
            )

        if not row:
            return None

        return EngineSeries(
            id=row["id"],
            manufacturer_id=row["manufacturer_id"],
            brand=row["brand"],
            series_name=row["series_name"],
            description=row["description"],
            generation=row["generation"],
            year_introduced=row["year_introduced"],
            year_discontinued=row["year_discontinued"],
            is_current=row["is_current"],
            created_at=row["created_at"],
            updated_at=row["updated_at"],
        )

    @trace_operation("db_list_engine_series_by_manufacturer")
    async def list_engine_series_by_manufacturer(
        self, manufacturer_id: str, is_current: bool = True
    ) -> list[EngineSeries]:
        """List engine series for a manufacturer."""
        manufacturer_id = validate_id(manufacturer_id, "manufacturer_id")
        async with self.pool.acquire() as conn:
            rows = await conn.fetch(
                """
                SELECT * FROM kb_engine_series
                WHERE manufacturer_id = $1 AND is_current = $2
                ORDER BY brand, series_name
                """,
                manufacturer_id,
                is_current,
            )

        return [
            EngineSeries(
                id=row["id"],
                manufacturer_id=row["manufacturer_id"],
                brand=row["brand"],
                series_name=row["series_name"],
                description=row["description"],
                generation=row["generation"],
                year_introduced=row["year_introduced"],
                year_discontinued=row["year_discontinued"],
                is_current=row["is_current"],
                created_at=row["created_at"],
                updated_at=row["updated_at"],
            )
            for row in rows
        ]

    @trace_operation(
        "db_bulk_create_engine_series",
        lambda series_list, **_: {"count": len(series_list) if series_list else 0},
    )
    async def bulk_create_engine_series(self, series_list: list[EngineSeries]) -> int:
        """Bulk create engine series. Returns count of inserted rows."""
        if not series_list:
            return 0

        # Validate all series
        for i, s in enumerate(series_list):
            validate_id(s.id, f"series_list[{i}].id")
            validate_id(s.manufacturer_id, f"series_list[{i}].manufacturer_id")
            validate_text(
                s.series_name,
                f"series_list[{i}].series_name",
                min_length=1,
                max_length=200,
            )

        async with self.pool.acquire() as conn:
            await conn.executemany(
                """
                INSERT INTO kb_engine_series
                (id, manufacturer_id, brand, series_name, description, generation,
                 year_introduced, year_discontinued, is_current)
                VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9)
                ON CONFLICT (id) DO NOTHING
                """,
                [
                    (
                        s.id,
                        s.manufacturer_id,
                        s.brand,
                        s.series_name,
                        s.description,
                        s.generation,
                        s.year_introduced,
                        s.year_discontinued,
                        s.is_current,
                    )
                    for s in series_list
                ],
            )

        return len(series_list)

    # =========================================================================
    # ENGINE MODEL OPERATIONS
    # =========================================================================

    @trace_operation("db_create_engine_model")
    async def create_engine_model(self, model: EngineModel) -> str:
        """Create a new engine model."""
        import json

        # Validate input fields
        validate_id(model.id, "model.id")
        validate_id(model.series_id, "model.series_id")
        validate_text(
            model.model_name, "model.model_name", min_length=1, max_length=200
        )

        fuel_types_json = (
            json.dumps(model.get_fuel_types_list()) if model.fuel_types else None
        )

        async with self.pool.acquire() as conn:
            await conn.execute(
                """
                INSERT INTO kb_engine_models
                (id, series_id, model_name, rpm_min, rpm_max, power_min_kw, power_max_kw,
                 cylinders, configuration, displacement_liters, fuel_types,
                 dry_weight_kg, length_mm, width_mm, height_mm,
                 emission_tier, is_current_production, data_source, data_confidence)
                VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13, $14, $15, $16, $17, $18, $19)
                """,
                model.id,
                model.series_id,
                model.model_name,
                model.rpm_min,
                model.rpm_max,
                model.power_min_kw,
                model.power_max_kw,
                model.cylinders,
                model.configuration,
                model.displacement_liters,
                fuel_types_json,
                model.dry_weight_kg,
                model.length_mm,
                model.width_mm,
                model.height_mm,
                model.emission_tier,
                model.is_current_production,
                model.data_source,
                model.data_confidence,
            )
        return model.id

    @trace_operation("db_get_engine_model")
    async def get_engine_model(self, model_id: str) -> Optional[EngineModel]:
        """Get engine model by ID."""
        import json

        model_id = validate_id(model_id, "model_id")
        async with self.pool.acquire() as conn:
            row = await conn.fetchrow(
                "SELECT * FROM kb_engine_models WHERE id = $1", model_id
            )

        if not row:
            return None

        fuel_types = json.dumps(row["fuel_types"]) if row["fuel_types"] else None

        return EngineModel(
            id=row["id"],
            series_id=row["series_id"],
            model_name=row["model_name"],
            rpm_min=row["rpm_min"],
            rpm_max=row["rpm_max"],
            power_min_kw=float(row["power_min_kw"]) if row["power_min_kw"] else None,
            power_max_kw=float(row["power_max_kw"]) if row["power_max_kw"] else None,
            cylinders=row["cylinders"],
            configuration=row["configuration"],
            displacement_liters=(
                float(row["displacement_liters"])
                if row["displacement_liters"]
                else None
            ),
            fuel_types=fuel_types,
            dry_weight_kg=(
                float(row["dry_weight_kg"]) if row["dry_weight_kg"] else None
            ),
            length_mm=float(row["length_mm"]) if row["length_mm"] else None,
            width_mm=float(row["width_mm"]) if row["width_mm"] else None,
            height_mm=float(row["height_mm"]) if row["height_mm"] else None,
            emission_tier=row["emission_tier"],
            is_current_production=row["is_current_production"],
            data_source=row["data_source"],
            data_confidence=(
                float(row["data_confidence"]) if row["data_confidence"] else 0.8
            ),
            created_at=row["created_at"],
            updated_at=row["updated_at"],
        )

    @trace_operation("db_search_engine_models")
    async def search_engine_models(
        self,
        rpm_min: Optional[int] = None,
        rpm_max: Optional[int] = None,
        power_min_kw: Optional[float] = None,
        power_max_kw: Optional[float] = None,
        manufacturer_id: Optional[str] = None,
        is_current: bool = True,
        limit: int = 50,
    ) -> list[EngineModel]:
        """Search engine models with filters."""
        import json

        # Input validation
        limit = validate_positive_int(limit, "limit", min_value=1, max_value=500)
        if rpm_min is not None:
            rpm_min = validate_positive_int(
                rpm_min, "rpm_min", min_value=1, max_value=5000
            )
        if rpm_max is not None:
            rpm_max = validate_positive_int(
                rpm_max, "rpm_max", min_value=1, max_value=5000
            )
        if power_min_kw is not None:
            power_min_kw = validate_float_range(
                power_min_kw, "power_min_kw", min_value=0.0, max_value=100000.0
            )
        if power_max_kw is not None:
            power_max_kw = validate_float_range(
                power_max_kw, "power_max_kw", min_value=0.0, max_value=100000.0
            )
        if manufacturer_id is not None:
            manufacturer_id = validate_id(manufacturer_id, "manufacturer_id")

        query = """
            SELECT em.* FROM kb_engine_models em
            JOIN kb_engine_series es ON em.series_id = es.id
            WHERE em.is_current_production = $1
        """
        params: list[Any] = [is_current]
        param_idx = 2

        if rpm_min is not None:
            query += f" AND em.rpm_max >= ${param_idx}"
            params.append(rpm_min)
            param_idx += 1

        if rpm_max is not None:
            query += f" AND em.rpm_min <= ${param_idx}"
            params.append(rpm_max)
            param_idx += 1

        if power_min_kw is not None:
            query += f" AND em.power_max_kw >= ${param_idx}"
            params.append(power_min_kw)
            param_idx += 1

        if power_max_kw is not None:
            query += f" AND em.power_min_kw <= ${param_idx}"
            params.append(power_max_kw)
            param_idx += 1

        if manufacturer_id is not None:
            query += f" AND es.manufacturer_id = ${param_idx}"
            params.append(manufacturer_id)
            param_idx += 1

        query += f" ORDER BY em.model_name LIMIT {limit}"

        async with self.pool.acquire() as conn:
            rows = await conn.fetch(query, *params)

        return [
            EngineModel(
                id=row["id"],
                series_id=row["series_id"],
                model_name=row["model_name"],
                rpm_min=row["rpm_min"],
                rpm_max=row["rpm_max"],
                power_min_kw=(
                    float(row["power_min_kw"]) if row["power_min_kw"] else None
                ),
                power_max_kw=(
                    float(row["power_max_kw"]) if row["power_max_kw"] else None
                ),
                cylinders=row["cylinders"],
                configuration=row["configuration"],
                displacement_liters=(
                    float(row["displacement_liters"])
                    if row["displacement_liters"]
                    else None
                ),
                fuel_types=(
                    json.dumps(row["fuel_types"]) if row["fuel_types"] else None
                ),
                emission_tier=row["emission_tier"],
                is_current_production=row["is_current_production"],
                data_source=row["data_source"],
                data_confidence=(
                    float(row["data_confidence"]) if row["data_confidence"] else 0.8
                ),
            )
            for row in rows
        ]

    @trace_operation("db_list_engine_models")
    async def list_engine_models(
        self,
        is_current: bool = True,
        limit: int = 500,
    ) -> list[EngineModel]:
        """
        List all engine models for fuzzy matching.

        Args:
            is_current: Filter by current production status
            limit: Maximum number of models to return

        Returns:
            List of EngineModel objects
        """
        import json

        limit = validate_positive_int(limit, "limit", min_value=1, max_value=1000)
        async with self.pool.acquire() as conn:
            rows = await conn.fetch(
                """
                SELECT em.*, es.manufacturer_id
                FROM kb_engine_models em
                JOIN kb_engine_series es ON em.series_id = es.id
                WHERE em.is_current_production = $1
                ORDER BY em.model_name
                LIMIT $2
                """,
                is_current,
                limit,
            )

        return [
            EngineModel(
                id=row["id"],
                series_id=row["series_id"],
                model_name=row["model_name"],
                rpm_min=row["rpm_min"],
                rpm_max=row["rpm_max"],
                power_min_kw=(
                    float(row["power_min_kw"]) if row["power_min_kw"] else None
                ),
                power_max_kw=(
                    float(row["power_max_kw"]) if row["power_max_kw"] else None
                ),
                cylinders=row["cylinders"],
                configuration=row["configuration"],
                displacement_liters=(
                    float(row["displacement_liters"])
                    if row["displacement_liters"]
                    else None
                ),
                fuel_types=(
                    json.dumps(row["fuel_types"]) if row["fuel_types"] else None
                ),
                emission_tier=row["emission_tier"],
                is_current_production=row["is_current_production"],
                data_source=row["data_source"],
                data_confidence=(
                    float(row["data_confidence"]) if row["data_confidence"] else 0.8
                ),
            )
            for row in rows
        ]

    @trace_operation("db_list_engine_series")
    async def list_engine_series(
        self,
        is_current: bool = True,
        limit: int = 500,
    ) -> list[EngineSeries]:
        """
        List all engine series for fuzzy matching.

        Args:
            is_current: Filter by current status
            limit: Maximum number of series to return

        Returns:
            List of EngineSeries objects
        """
        limit = validate_positive_int(limit, "limit", min_value=1, max_value=1000)
        async with self.pool.acquire() as conn:
            rows = await conn.fetch(
                """
                SELECT * FROM kb_engine_series
                WHERE is_current = $1
                ORDER BY series_name
                LIMIT $2
                """,
                is_current,
                limit,
            )

        return [
            EngineSeries(
                id=row["id"],
                manufacturer_id=row["manufacturer_id"],
                brand=row["brand"],
                series_name=row["series_name"],
                description=row["description"],
                generation=row["generation"],
                year_introduced=row["year_introduced"],
                year_discontinued=row["year_discontinued"],
                is_current=row["is_current"],
                created_at=row["created_at"],
                updated_at=row["updated_at"],
            )
            for row in rows
        ]

    @trace_operation(
        "db_bulk_create_engine_models",
        lambda models, **_: {"count": len(models) if models else 0},
    )
    async def bulk_create_engine_models(self, models: list[EngineModel]) -> int:
        """Bulk create engine models. Returns count of inserted rows."""
        import json

        if not models:
            return 0

        # Validate all models
        for i, m in enumerate(models):
            validate_id(m.id, f"models[{i}].id")
            validate_id(m.series_id, f"models[{i}].series_id")
            validate_text(
                m.model_name, f"models[{i}].model_name", min_length=1, max_length=200
            )

        async with self.pool.acquire() as conn:
            await conn.executemany(
                """
                INSERT INTO kb_engine_models
                (id, series_id, model_name, rpm_min, rpm_max, power_min_kw, power_max_kw,
                 cylinders, configuration, displacement_liters, fuel_types,
                 emission_tier, is_current_production, data_source, data_confidence)
                VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13, $14, $15)
                ON CONFLICT (id) DO NOTHING
                """,
                [
                    (
                        m.id,
                        m.series_id,
                        m.model_name,
                        m.rpm_min,
                        m.rpm_max,
                        m.power_min_kw,
                        m.power_max_kw,
                        m.cylinders,
                        m.configuration,
                        m.displacement_liters,
                        (json.dumps(m.get_fuel_types_list()) if m.fuel_types else None),
                        m.emission_tier,
                        m.is_current_production,
                        m.data_source,
                        m.data_confidence,
                    )
                    for m in models
                ],
            )

        return len(models)

    # =========================================================================
    # ALIAS OPERATIONS (with vector search)
    # =========================================================================

    @trace_operation("db_create_alias")
    async def create_alias(self, alias: EntityAlias) -> str:
        """Create a new entity alias."""
        # Validate input fields
        validate_id(alias.id, "alias.id")
        validate_id(alias.entity_id, "alias.entity_id")
        validate_text(
            alias.alias_text, "alias.alias_text", min_length=1, max_length=500
        )
        async with self.pool.acquire() as conn:
            await conn.execute(
                """
                INSERT INTO kb_entity_aliases
                (id, entity_type, entity_id, alias_text, alias_type, normalized_text,
                 source, confidence, is_active)
                VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9)
                """,
                alias.id,
                alias.entity_type,
                alias.entity_id,
                alias.alias_text,
                alias.alias_type,
                alias.normalized_text or alias.alias_text.lower().strip(),
                alias.source,
                alias.confidence,
                alias.is_active,
            )

        # Publish cache invalidation event
        publisher = get_cache_event_publisher()
        await publisher.publish(
            CacheEventType.ALIAS_CREATED,
            entity_id=alias.id,
            entity_type="alias",
        )

        return alias.id

    @trace_operation("db_get_alias_by_normalized_text")
    async def get_alias_by_normalized_text(
        self, text: str, entity_type: Optional[str] = None
    ) -> Optional[EntityAlias]:
        """Get alias by exact normalized text match."""
        text = validate_text(text, "text", min_length=1, max_length=500)
        if entity_type is not None:
            entity_type = validate_entity_type(entity_type, allow_none=True)
        normalized = text.lower().strip()

        if entity_type:
            query = """
                SELECT * FROM kb_entity_aliases
                WHERE normalized_text = $1 AND entity_type = $2 AND is_active = TRUE
                ORDER BY confidence DESC LIMIT 1
            """
            params = [normalized, entity_type]
        else:
            query = """
                SELECT * FROM kb_entity_aliases
                WHERE normalized_text = $1 AND is_active = TRUE
                ORDER BY confidence DESC LIMIT 1
            """
            params = [normalized]

        async with self.pool.acquire() as conn:
            row = await conn.fetchrow(query, *params)

        if not row:
            return None

        return EntityAlias(
            id=row["id"],
            entity_type=row["entity_type"],
            entity_id=row["entity_id"],
            alias_text=row["alias_text"],
            alias_type=row["alias_type"],
            normalized_text=row["normalized_text"],
            source=row["source"],
            confidence=float(row["confidence"]) if row["confidence"] else 1.0,
            is_active=row["is_active"],
            created_at=row["created_at"],
            updated_at=row["updated_at"],
        )

    @trace_operation("db_search_aliases_by_embedding")
    async def search_aliases_by_embedding(
        self,
        embedding: list[float],
        entity_type: Optional[str] = None,
        top_k: int = 10,
        min_similarity: float = 0.6,
    ) -> list[tuple[EntityAlias, float]]:
        """
        Search aliases by embedding similarity using pgvector.

        Args:
            embedding: 1536-dim query vector
            entity_type: Optional filter by entity type
            top_k: Maximum results to return
            min_similarity: Minimum cosine similarity threshold (0-1)

        Returns:
            List of (EntityAlias, similarity_score) tuples
        """
        # Input validation
        top_k = validate_positive_int(top_k, "top_k", min_value=1, max_value=100)
        min_similarity = validate_float_range(
            min_similarity, "min_similarity", min_value=0.0, max_value=1.0
        )
        if entity_type is not None:
            entity_type = validate_entity_type(entity_type, allow_none=True)

        if len(embedding) != 1536:
            raise KBValidationError(
                message="Invalid embedding dimensions",
                field="embedding",
                expected=1536,
                actual=len(embedding),
            )

        embedding_str = "[" + ",".join(str(x) for x in embedding) + "]"

        if entity_type:
            query = """
                SELECT *,
                       1 - (embedding <=> $1::vector) as similarity
                FROM kb_entity_aliases
                WHERE embedding IS NOT NULL
                  AND entity_type = $2
                  AND is_active = TRUE
                  AND 1 - (embedding <=> $1::vector) >= $3
                ORDER BY embedding <=> $1::vector
                LIMIT $4
            """
            params = [embedding_str, entity_type, min_similarity, top_k]
        else:
            query = """
                SELECT *,
                       1 - (embedding <=> $1::vector) as similarity
                FROM kb_entity_aliases
                WHERE embedding IS NOT NULL
                  AND is_active = TRUE
                  AND 1 - (embedding <=> $1::vector) >= $2
                ORDER BY embedding <=> $1::vector
                LIMIT $3
            """
            params = [embedding_str, min_similarity, top_k]

        async with self.pool.acquire() as conn:
            rows = await conn.fetch(query, *params)

        results = []
        for row in rows:
            alias = EntityAlias(
                id=row["id"],
                entity_type=row["entity_type"],
                entity_id=row["entity_id"],
                alias_text=row["alias_text"],
                alias_type=row["alias_type"],
                normalized_text=row["normalized_text"],
                source=row["source"],
                confidence=float(row["confidence"]) if row["confidence"] else 1.0,
                is_active=row["is_active"],
            )
            results.append((alias, float(row["similarity"])))

        return results

    @trace_operation("db_update_alias_embedding")
    async def update_alias_embedding(
        self, alias_id: str, embedding: list[float]
    ) -> bool:
        """Update embedding for an alias."""
        alias_id = validate_id(alias_id, "alias_id")
        if len(embedding) != 1536:
            raise KBValidationError(
                message="Invalid embedding dimensions",
                field="embedding",
                expected=1536,
                actual=len(embedding),
            )

        embedding_str = "[" + ",".join(str(x) for x in embedding) + "]"

        async with self.pool.acquire() as conn:
            result = await conn.execute(
                """
                UPDATE kb_entity_aliases
                SET embedding = $1::vector, updated_at = NOW()
                WHERE id = $2
                """,
                embedding_str,
                alias_id,
            )

        return "UPDATE 1" in result

    @trace_operation("db_update_alias_embedding_versioned")
    async def update_alias_embedding_versioned(
        self,
        alias_id: str,
        embedding: list[float],
        embedding_model: str,
    ) -> bool:
        """
        Update embedding for an alias with model version tracking.

        This method stores the embedding along with the model name
        that generated it, enabling stale embedding detection when
        the model is upgraded.

        Args:
            alias_id: ID of the alias to update
            embedding: Embedding vector (1536 dimensions)
            embedding_model: Model name (e.g., "text-embedding-3-small")

        Returns:
            True if update succeeded, False otherwise
        """
        alias_id = validate_id(alias_id, "alias_id")
        embedding_model = validate_text(
            embedding_model, "embedding_model", min_length=1, max_length=50
        )
        if len(embedding) != 1536:
            raise KBValidationError(
                message="Invalid embedding dimensions",
                field="embedding",
                expected=1536,
                actual=len(embedding),
            )

        embedding_str = "[" + ",".join(str(x) for x in embedding) + "]"

        async with self.pool.acquire() as conn:
            result = await conn.execute(
                """
                UPDATE kb_entity_aliases
                SET embedding = $1::vector,
                    embedding_model = $2,
                    embedding_updated_at = NOW(),
                    updated_at = NOW()
                WHERE id = $3
                """,
                embedding_str,
                embedding_model,
                alias_id,
            )

        success = "UPDATE 1" in result

        # Publish cache invalidation event for embedding updates
        if success:
            publisher = get_cache_event_publisher()
            await publisher.publish(
                CacheEventType.EMBEDDING_UPDATED,
                entity_id=alias_id,
                entity_type="alias",
                metadata={"embedding_model": embedding_model},
            )

        return success

    @trace_operation(
        "db_bulk_create_aliases",
        lambda aliases, **_: {"count": len(aliases) if aliases else 0},
    )
    async def bulk_create_aliases(self, aliases: list[EntityAlias]) -> int:
        """Bulk create aliases. Returns count of inserted rows."""
        if not aliases:
            return 0

        # Validate all aliases
        for i, a in enumerate(aliases):
            validate_id(a.id, f"aliases[{i}].id")
            validate_id(a.entity_id, f"aliases[{i}].entity_id")
            validate_text(
                a.alias_text, f"aliases[{i}].alias_text", min_length=1, max_length=500
            )

        async with self.pool.acquire() as conn:
            await conn.executemany(
                """
                INSERT INTO kb_entity_aliases
                (id, entity_type, entity_id, alias_text, alias_type, normalized_text,
                 source, confidence, is_active)
                VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9)
                ON CONFLICT (id) DO NOTHING
                """,
                [
                    (
                        a.id,
                        a.entity_type,
                        a.entity_id,
                        a.alias_text,
                        a.alias_type,
                        a.normalized_text or a.alias_text.lower().strip(),
                        a.source,
                        a.confidence,
                        a.is_active,
                    )
                    for a in aliases
                ],
            )

        return len(aliases)

    @trace_operation("db_list_aliases_without_embeddings")
    async def list_aliases_without_embeddings(
        self, limit: int = 100
    ) -> list[EntityAlias]:
        """Get aliases that don't have embeddings yet (for backfill)."""
        limit = validate_positive_int(limit, "limit", min_value=1, max_value=1000)
        async with self.pool.acquire() as conn:
            rows = await conn.fetch(
                """
                SELECT * FROM kb_entity_aliases
                WHERE embedding IS NULL AND is_active = TRUE
                ORDER BY created_at
                LIMIT $1
                """,
                limit,
            )

        return [
            EntityAlias(
                id=row["id"],
                entity_type=row["entity_type"],
                entity_id=row["entity_id"],
                alias_text=row["alias_text"],
                alias_type=row["alias_type"],
                normalized_text=row["normalized_text"],
                source=row["source"],
                confidence=float(row["confidence"]) if row["confidence"] else 1.0,
                is_active=row["is_active"],
            )
            for row in rows
        ]

    # =========================================================================
    # APPLICATION & MARKET SEGMENT OPERATIONS
    # =========================================================================

    @trace_operation("db_create_application")
    async def create_application(self, application: Application) -> str:
        """Create a new application."""
        # Validate input fields
        validate_id(application.id, "application.id")
        validate_text(
            application.name, "application.name", min_length=1, max_length=200
        )
        async with self.pool.acquire() as conn:
            await conn.execute(
                """
                INSERT INTO kb_applications
                (id, name, code, description, category,
                 typical_power_range_min_kw, typical_power_range_max_kw, is_active)
                VALUES ($1, $2, $3, $4, $5, $6, $7, $8)
                """,
                application.id,
                application.name,
                application.code,
                application.description,
                application.category,
                application.typical_power_range_min_kw,
                application.typical_power_range_max_kw,
                application.is_active,
            )
        return application.id

    @trace_operation("db_list_applications")
    async def list_applications(self, is_active: bool = True) -> list[Application]:
        """List all applications."""
        async with self.pool.acquire() as conn:
            rows = await conn.fetch(
                "SELECT * FROM kb_applications WHERE is_active = $1 ORDER BY name",
                is_active,
            )

        return [
            Application(
                id=row["id"],
                name=row["name"],
                code=row["code"],
                description=row["description"],
                category=row["category"],
                typical_power_range_min_kw=(
                    float(row["typical_power_range_min_kw"])
                    if row["typical_power_range_min_kw"]
                    else None
                ),
                typical_power_range_max_kw=(
                    float(row["typical_power_range_max_kw"])
                    if row["typical_power_range_max_kw"]
                    else None
                ),
                is_active=row["is_active"],
            )
            for row in rows
        ]

    @trace_operation("db_create_market_segment")
    async def create_market_segment(self, segment: MarketSegment) -> str:
        """Create a new market segment."""
        # Validate input fields
        validate_id(segment.id, "segment.id")
        validate_text(segment.name, "segment.name", min_length=1, max_length=200)
        async with self.pool.acquire() as conn:
            await conn.execute(
                """
                INSERT INTO kb_market_segments
                (id, name, segment_type, description, priority_score,
                 growth_potential, focus_regions, is_active)
                VALUES ($1, $2, $3, $4, $5, $6, $7, $8)
                """,
                segment.id,
                segment.name,
                segment.segment_type,
                segment.description,
                segment.priority_score,
                segment.growth_potential,
                segment.focus_regions,
                segment.is_active,
            )
        return segment.id

    @trace_operation("db_list_market_segments")
    async def list_market_segments(self, is_active: bool = True) -> list[MarketSegment]:
        """List all market segments."""
        async with self.pool.acquire() as conn:
            rows = await conn.fetch(
                """
                SELECT * FROM kb_market_segments
                WHERE is_active = $1
                ORDER BY priority_score DESC
                """,
                is_active,
            )

        return [
            MarketSegment(
                id=row["id"],
                name=row["name"],
                segment_type=row["segment_type"],
                description=row["description"],
                priority_score=row["priority_score"],
                growth_potential=row["growth_potential"],
                focus_regions=row["focus_regions"],
                is_active=row["is_active"],
            )
            for row in rows
        ]

    # =========================================================================
    # ENGINE-APPLICATION MAPPING OPERATIONS
    # =========================================================================

    @trace_operation("db_create_engine_application_map")
    async def create_engine_application_map(self, mapping: EngineApplicationMap) -> str:
        """Create a new engine-application mapping."""
        # Validate input fields
        validate_id(mapping.id, "mapping.id")
        validate_id(mapping.engine_model_id, "mapping.engine_model_id")
        validate_id(mapping.application_id, "mapping.application_id")
        async with self.pool.acquire() as conn:
            await conn.execute(
                """
                INSERT INTO kb_engine_application_map
                (id, engine_model_id, application_id, suitability_score,
                 is_primary_application, notes)
                VALUES ($1, $2, $3, $4, $5, $6)
                """,
                mapping.id,
                mapping.engine_model_id,
                mapping.application_id,
                mapping.suitability_score,
                mapping.is_primary_application,
                mapping.notes,
            )
        return mapping.id

    @trace_operation(
        "db_bulk_create_engine_application_map",
        lambda mappings, **_: {"count": len(mappings) if mappings else 0},
    )
    async def bulk_create_engine_application_map(
        self, mappings: list[EngineApplicationMap]
    ) -> int:
        """Bulk create engine-application mappings. Returns count of inserted rows."""
        if not mappings:
            return 0

        # Validate all mappings
        for i, m in enumerate(mappings):
            validate_id(m.id, f"mappings[{i}].id")
            validate_id(m.engine_model_id, f"mappings[{i}].engine_model_id")
            validate_id(m.application_id, f"mappings[{i}].application_id")

        async with self.pool.acquire() as conn:
            await conn.executemany(
                """
                INSERT INTO kb_engine_application_map
                (id, engine_model_id, application_id, suitability_score,
                 is_primary_application, notes)
                VALUES ($1, $2, $3, $4, $5, $6)
                ON CONFLICT (id) DO NOTHING
                """,
                [
                    (
                        m.id,
                        m.engine_model_id,
                        m.application_id,
                        m.suitability_score,
                        m.is_primary_application,
                        m.notes,
                    )
                    for m in mappings
                ],
            )

        return len(mappings)

    @trace_operation("db_list_applications_for_engine")
    async def list_applications_for_engine(
        self, engine_model_id: str
    ) -> list[tuple[Application, float]]:
        """Get applications for an engine model with suitability scores."""
        engine_model_id = validate_id(engine_model_id, "engine_model_id")
        async with self.pool.acquire() as conn:
            rows = await conn.fetch(
                """
                SELECT a.*, eam.suitability_score, eam.is_primary_application
                FROM kb_applications a
                JOIN kb_engine_application_map eam ON a.id = eam.application_id
                WHERE eam.engine_model_id = $1 AND a.is_active = TRUE
                ORDER BY eam.suitability_score DESC
                """,
                engine_model_id,
            )

        return [
            (
                Application(
                    id=row["id"],
                    name=row["name"],
                    code=row["code"],
                    description=row["description"],
                    category=row["category"],
                    typical_power_range_min_kw=(
                        float(row["typical_power_range_min_kw"])
                        if row["typical_power_range_min_kw"]
                        else None
                    ),
                    typical_power_range_max_kw=(
                        float(row["typical_power_range_max_kw"])
                        if row["typical_power_range_max_kw"]
                        else None
                    ),
                    is_active=row["is_active"],
                ),
                float(row["suitability_score"]),
            )
            for row in rows
        ]

    # =========================================================================
    # ARTICLE SCORING OPERATIONS
    # =========================================================================

    @trace_operation("db_create_article_score")
    async def create_article_score(self, score: ArticleScore) -> str:
        """Create or update article score."""

        # Validate input fields
        validate_id(score.id, "score.id")
        validate_id(score.article_id, "score.article_id")
        validate_float_range(
            score.technical_score,
            "score.technical_score",
            min_value=0.0,
            max_value=100.0,
        )
        validate_float_range(
            score.market_score, "score.market_score", min_value=0.0, max_value=100.0
        )
        validate_float_range(
            score.commercial_score,
            "score.commercial_score",
            min_value=0.0,
            max_value=100.0,
        )
        validate_float_range(
            score.total_score, "score.total_score", min_value=0.0, max_value=100.0
        )
        if score.classification:
            validate_text(
                score.classification,
                "score.classification",
                min_length=1,
                max_length=50,
            )

        async with self.pool.acquire() as conn:
            await conn.execute(
                """
                INSERT INTO kb_article_scores
                (id, article_id, technical_score, market_score, commercial_score,
                 total_score, classification, score_breakdown,
                 scoring_model_version, scored_at, score_explanation)
                VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11)
                ON CONFLICT (article_id) DO UPDATE SET
                    technical_score = EXCLUDED.technical_score,
                    market_score = EXCLUDED.market_score,
                    commercial_score = EXCLUDED.commercial_score,
                    total_score = EXCLUDED.total_score,
                    classification = EXCLUDED.classification,
                    score_breakdown = EXCLUDED.score_breakdown,
                    scoring_model_version = EXCLUDED.scoring_model_version,
                    scored_at = EXCLUDED.scored_at,
                    score_explanation = EXCLUDED.score_explanation,
                    updated_at = NOW()
                """,
                score.id,
                score.article_id,
                score.technical_score,
                score.market_score,
                score.commercial_score,
                score.total_score,
                score.classification,
                score.score_breakdown,
                score.scoring_model_version,
                score.scored_at,
                score.score_explanation,
            )
        return score.id

    @trace_operation("db_get_article_score")
    async def get_article_score(self, article_id: str) -> Optional[ArticleScore]:
        """Get article score by article ID."""
        article_id = validate_id(article_id, "article_id")
        async with self.pool.acquire() as conn:
            row = await conn.fetchrow(
                "SELECT * FROM kb_article_scores WHERE article_id = $1", article_id
            )

        if not row:
            return None

        return ArticleScore(
            id=row["id"],
            article_id=row["article_id"],
            technical_score=(
                float(row["technical_score"]) if row["technical_score"] else 0.0
            ),
            market_score=float(row["market_score"]) if row["market_score"] else 0.0,
            commercial_score=(
                float(row["commercial_score"]) if row["commercial_score"] else 0.0
            ),
            total_score=float(row["total_score"]) if row["total_score"] else 0.0,
            classification=row["classification"],
            score_breakdown=row["score_breakdown"],
            scoring_model_version=row["scoring_model_version"],
            scored_at=row["scored_at"],
            score_explanation=row["score_explanation"],
        )

    @trace_operation("db_list_high_priority_articles")
    async def list_high_priority_articles(self, limit: int = 50) -> list[ArticleScore]:
        """List high priority articles sorted by score."""
        limit = validate_positive_int(limit, "limit", min_value=1, max_value=500)
        async with self.pool.acquire() as conn:
            rows = await conn.fetch(
                """
                SELECT * FROM kb_article_scores
                WHERE classification = 'high_priority'
                ORDER BY total_score DESC
                LIMIT $1
                """,
                limit,
            )

        return [
            ArticleScore(
                id=row["id"],
                article_id=row["article_id"],
                technical_score=(
                    float(row["technical_score"]) if row["technical_score"] else 0.0
                ),
                market_score=float(row["market_score"]) if row["market_score"] else 0.0,
                commercial_score=(
                    float(row["commercial_score"]) if row["commercial_score"] else 0.0
                ),
                total_score=float(row["total_score"]) if row["total_score"] else 0.0,
                classification=row["classification"],
                score_breakdown=row["score_breakdown"],
                scoring_model_version=row["scoring_model_version"],
                scored_at=row["scored_at"],
                score_explanation=row["score_explanation"],
            )
            for row in rows
        ]

    # =========================================================================
    # ENGINE RATING OPERATIONS (ADR-004 Unified KB)
    # =========================================================================

    def _row_to_engine_rating(self, row) -> EngineRating:
        """Convert database row to EngineRating model."""
        import json

        # Parse duty_class enum
        duty_class = None
        if row["duty_class"]:
            try:
                duty_class = DutyClass(row["duty_class"])
            except ValueError:
                duty_class = DutyClass.MEDIUM_DUTY

        # Parse iso_classification enum
        iso_class = ISOClassification.NOT_APPLICABLE
        if row.get("iso_classification"):
            try:
                iso_class = ISOClassification(row["iso_classification"])
            except ValueError:
                pass

        # Parse availability_status enum
        avail_status = AvailabilityStatus.AVAILABLE
        if row.get("availability_status"):
            try:
                avail_status = AvailabilityStatus(row["availability_status"])
            except ValueError:
                pass

        return EngineRating(
            id=row["id"],
            engine_model_id=row["engine_model_id"],
            rating_designation=row["rating_designation"],
            rating_name=row.get("rating_name"),
            duty_class=duty_class,
            iso_classification=iso_class,
            harmonized_duty_class=row.get("harmonized_duty_class"),
            oem_rating_code=row.get("oem_rating_code"),
            power_kw=float(row["power_kw"]) if row["power_kw"] else 0.0,
            power_hp=float(row["power_hp"]) if row.get("power_hp") else None,
            rpm=row["rpm"],
            load_factor_min=(
                float(row["load_factor_min"]) if row.get("load_factor_min") else None
            ),
            load_factor_max=(
                float(row["load_factor_max"]) if row.get("load_factor_max") else None
            ),
            annual_hours_min=row.get("annual_hours_min"),
            annual_hours_max=row.get("annual_hours_max"),
            dry_weight_kg=(
                float(row["dry_weight_kg"]) if row.get("dry_weight_kg") else None
            ),
            length_mm=float(row["length_mm"]) if row.get("length_mm") else None,
            width_mm=float(row["width_mm"]) if row.get("width_mm") else None,
            height_mm=float(row["height_mm"]) if row.get("height_mm") else None,
            power_density_kw_per_kg=(
                float(row["power_density_kw_per_kg"])
                if row.get("power_density_kw_per_kg")
                else None
            ),
            fuel_types=json.dumps(row["fuel_types"]) if row.get("fuel_types") else None,
            emission_tier=row.get("emission_tier"),
            aftertreatment_required=row.get("aftertreatment_required"),
            application_profiles=(
                json.dumps(row["application_profiles"])
                if row.get("application_profiles")
                else None
            ),
            primary_applications=(
                json.dumps(row["primary_applications"])
                if row.get("primary_applications")
                else None
            ),
            availability_status=avail_status,
            regions_available=(
                json.dumps(row["regions_available"])
                if row.get("regions_available")
                else None
            ),
            data_source=row["data_source"],
            data_source_url=row.get("data_source_url"),
            data_confidence=(
                float(row["data_confidence"]) if row.get("data_confidence") else 0.9
            ),
            last_verified=row.get("last_verified"),
            verified_by=row.get("verified_by"),
            notes=row.get("notes"),
        )

    @trace_operation("db_get_engine_rating")
    async def get_engine_rating(self, rating_id: str) -> Optional[EngineRating]:
        """Get engine rating by ID."""
        validate_id(rating_id, "rating_id")

        async with self.pool.acquire() as conn:
            row = await conn.fetchrow(
                "SELECT * FROM kb_engine_ratings WHERE id = $1",
                rating_id,
            )

        if not row:
            return None
        return self._row_to_engine_rating(row)

    @trace_operation("db_get_engine_rating_by_designation")
    async def get_engine_rating_by_designation(
        self,
        engine_model_id: str,
        rating_designation: str,
    ) -> Optional[EngineRating]:
        """Get engine rating by model ID and designation."""
        validate_id(engine_model_id, "engine_model_id")
        validate_text(
            rating_designation, "rating_designation", min_length=1, max_length=100
        )

        async with self.pool.acquire() as conn:
            row = await conn.fetchrow(
                """SELECT * FROM kb_engine_ratings
                   WHERE engine_model_id = $1 AND rating_designation = $2""",
                engine_model_id,
                rating_designation,
            )

        if not row:
            return None
        return self._row_to_engine_rating(row)

    @trace_operation(
        "db_list_engine_ratings",
        lambda **kwargs: {
            "filters": {k: v for k, v in kwargs.items() if v is not None}
        },
    )
    async def list_engine_ratings(
        self,
        duty_class: Optional[str] = None,
        harmonized_duty_class: Optional[str] = None,
        min_power_kw: Optional[float] = None,
        max_power_kw: Optional[float] = None,
        emission_tier: Optional[str] = None,
        availability_status: str = "available",
        limit: int = 100,
    ) -> list[EngineRating]:
        """
        List engine ratings with optional filters.

        Args:
            duty_class: Filter by duty class (e.g., "heavy_duty", "medium_duty")
            harmonized_duty_class: Filter by ISO 8528-aligned class (e.g., "CON", "HVY", "MED")
            min_power_kw: Minimum power output
            max_power_kw: Maximum power output
            emission_tier: Filter by emission tier (e.g., "IMO Tier II")
            availability_status: Filter by availability (default: "available")
            limit: Maximum results to return

        Returns:
            List of EngineRating objects
        """
        limit = validate_positive_int(limit, "limit", min_value=1, max_value=1000)

        query = "SELECT * FROM kb_engine_ratings WHERE availability_status = $1::availability_status_enum"
        params: list[Any] = [availability_status]
        param_idx = 2

        if duty_class:
            query += f" AND duty_class = ${param_idx}::duty_class_enum"
            params.append(duty_class)
            param_idx += 1

        if harmonized_duty_class:
            query += f" AND harmonized_duty_class = ${param_idx}::harmonized_duty_class"
            params.append(harmonized_duty_class)
            param_idx += 1

        if min_power_kw is not None:
            min_power_kw = validate_float_range(
                min_power_kw, "min_power_kw", min_value=0, max_value=100000
            )
            query += f" AND power_kw >= ${param_idx}"
            params.append(min_power_kw)
            param_idx += 1

        if max_power_kw is not None:
            max_power_kw = validate_float_range(
                max_power_kw, "max_power_kw", min_value=0, max_value=100000
            )
            query += f" AND power_kw <= ${param_idx}"
            params.append(max_power_kw)
            param_idx += 1

        if emission_tier:
            query += f" AND emission_tier = ${param_idx}"
            params.append(emission_tier)
            param_idx += 1

        query += f" ORDER BY power_kw LIMIT {limit}"

        async with self.pool.acquire() as conn:
            rows = await conn.fetch(query, *params)

        return [self._row_to_engine_rating(row) for row in rows]

    @trace_operation("db_list_engine_ratings_for_power_range")
    async def list_engine_ratings_for_power_range(
        self,
        required_power_kw: float,
        tolerance_pct: float = 15.0,
        duty_class: Optional[str] = None,
        limit: int = 20,
    ) -> list[EngineRating]:
        """
        Find engine ratings matching a power requirement within tolerance.

        Args:
            required_power_kw: Required power in kW
            tolerance_pct: Acceptable tolerance percentage (default: 15%)
            duty_class: Optional duty class filter
            limit: Maximum results

        Returns:
            List of EngineRating objects sorted by power match
        """
        required_power_kw = validate_float_range(
            required_power_kw, "required_power_kw", min_value=0, max_value=100000
        )
        tolerance_pct = validate_float_range(
            tolerance_pct, "tolerance_pct", min_value=0, max_value=100
        )

        min_power = required_power_kw * (1 - tolerance_pct / 100)
        max_power = required_power_kw * (1 + tolerance_pct / 100)

        return await self.list_engine_ratings(
            duty_class=duty_class,
            min_power_kw=min_power,
            max_power_kw=max_power,
            limit=limit,
        )

    @trace_operation("db_count_engine_ratings")
    async def count_engine_ratings(
        self,
        duty_class: Optional[str] = None,
        availability_status: str = "available",
    ) -> dict[str, int]:
        """
        Count engine ratings by duty class.

        Returns:
            Dictionary with duty class counts and total
        """
        if duty_class:
            query = """
                SELECT duty_class::text, COUNT(*) as count
                FROM kb_engine_ratings
                WHERE availability_status = $1::availability_status_enum
                  AND duty_class = $2::duty_class_enum
                GROUP BY duty_class
            """
            params = [availability_status, duty_class]
        else:
            query = """
                SELECT duty_class::text, COUNT(*) as count
                FROM kb_engine_ratings
                WHERE availability_status = $1::availability_status_enum
                GROUP BY duty_class
            """
            params = [availability_status]

        async with self.pool.acquire() as conn:
            rows = await conn.fetch(query, *params)

        counts = {row["duty_class"]: row["count"] for row in rows}
        counts["total"] = sum(counts.values())
        return counts

    # =========================================================================
    # OEM DUTY MAPPING OPERATIONS (ISO 8528-1:2018 Harmonized)
    # =========================================================================

    @trace_operation("db_get_oem_duty_mappings")
    async def get_oem_duty_mappings(
        self,
        manufacturer: Optional[str] = None,
        harmonized_duty_class: Optional[str] = None,
    ) -> list[dict]:
        """
        Get OEM duty class mappings from kb_oem_duty_mappings table.

        Args:
            manufacturer: Filter by manufacturer name (e.g., "MTU", "Cummins")
            harmonized_duty_class: Filter by harmonized class (e.g., "CON", "HVY")

        Returns:
            List of mapping dictionaries with OEM codes and harmonized classes
        """
        query = "SELECT * FROM kb_oem_duty_mappings WHERE 1=1"
        params: list[Any] = []
        param_idx = 1

        if manufacturer:
            query += f" AND manufacturer = ${param_idx}"
            params.append(manufacturer)
            param_idx += 1

        if harmonized_duty_class:
            query += f" AND harmonized_duty_class = ${param_idx}::harmonized_duty_class"
            params.append(harmonized_duty_class)
            param_idx += 1

        query += " ORDER BY manufacturer, oem_rating_code"

        async with self.pool.acquire() as conn:
            rows = await conn.fetch(query, *params)

        return [dict(row) for row in rows]

    @trace_operation("db_resolve_oem_rating_to_harmonized")
    async def resolve_oem_rating_to_harmonized(
        self,
        manufacturer: str,
        oem_rating_code: str,
    ) -> Optional[str]:
        """
        Resolve an OEM rating code to its harmonized duty class.

        Examples:
            ("MTU", "M93") -> "LGT"
            ("Cummins", "HD") -> "HVY"
            ("Caterpillar", "B") -> "HVY"

        Args:
            manufacturer: OEM name
            oem_rating_code: OEM-specific rating code

        Returns:
            Harmonized duty class code (CON, HVY, MED, LGT, INT, PLS) or None
        """
        query = """
            SELECT harmonized_duty_class::text
            FROM kb_oem_duty_mappings
            WHERE manufacturer = $1 AND oem_rating_code = $2
        """
        async with self.pool.acquire() as conn:
            row = await conn.fetchrow(query, manufacturer, oem_rating_code)

        return row["harmonized_duty_class"] if row else None

    @trace_operation("db_get_engines_by_harmonized_duty_class")
    async def get_engines_by_harmonized_duty_class(
        self,
        harmonized_duty_class: str,
        min_power_kw: Optional[float] = None,
        max_power_kw: Optional[float] = None,
        limit: int = 50,
    ) -> list[EngineRating]:
        """
        Get all engine ratings matching a harmonized duty class.

        This enables cross-OEM comparison using ISO 8528-aligned classifications.

        Args:
            harmonized_duty_class: ISO 8528-aligned class (CON, HVY, MED, LGT, INT, PLS)
            min_power_kw: Optional minimum power filter
            max_power_kw: Optional maximum power filter
            limit: Maximum results

        Returns:
            List of EngineRating objects
        """
        limit = validate_positive_int(limit, "limit", min_value=1, max_value=500)

        query = """
            SELECT * FROM kb_engine_ratings
            WHERE harmonized_duty_class = $1::harmonized_duty_class
              AND availability_status = 'available'::availability_status_enum
        """
        params: list[Any] = [harmonized_duty_class]
        param_idx = 2

        if min_power_kw is not None:
            query += f" AND power_kw >= ${param_idx}"
            params.append(min_power_kw)
            param_idx += 1

        if max_power_kw is not None:
            query += f" AND power_kw <= ${param_idx}"
            params.append(max_power_kw)
            param_idx += 1

        query += f" ORDER BY power_kw LIMIT {limit}"

        async with self.pool.acquire() as conn:
            rows = await conn.fetch(query, *params)

        return [self._row_to_engine_rating(row) for row in rows]

    # =========================================================================
    # COMPETITOR ENGAGEMENT METHODS (Phase 5)
    # =========================================================================

    async def create_competitor_engagement(
        self,
        customer_name: str,
        competitor: str,
        engagement_type: str,
        threat_level: str,
        customer_id: Optional[str] = None,
        is_our_customer: bool = False,
        engagement_date: Optional[str] = None,
        vessel_name: Optional[str] = None,
        vessel_type: Optional[str] = None,
        source_url: Optional[str] = None,
        source_type: Optional[str] = None,
        threat_reason: Optional[str] = None,
        requires_sales_action: bool = False,
        action_recommendation: Optional[str] = None,
        region: Optional[str] = None,
        country: Optional[str] = None,
    ) -> str:
        """
        Create a new competitor engagement record.

        Args:
            customer_name: Name of the customer (required)
            competitor: Competitor name (e.g., "caterpillar", "cummins")
            engagement_type: Type of engagement (order, partnership, pitch, etc.)
            threat_level: Threat level (high, medium, low)
            customer_id: SAP customer ID if known
            is_our_customer: True if customer is in our SAP
            engagement_date: Date of engagement (YYYY-MM-DD)
            vessel_name: Name of vessel if applicable
            vessel_type: Type of vessel
            source_url: URL of source article
            source_type: Type of source (press_release, trade_news, field_intel)
            threat_reason: Explanation of threat level
            requires_sales_action: Whether sales needs to act
            action_recommendation: Recommended action if required
            region: Geographic region
            country: Country

        Returns:
            ID of created engagement
        """
        await self._check_allowed_table("kb_competitor_engagements")
        import uuid

        engagement_id = str(uuid.uuid4())

        query = """
            INSERT INTO kb_competitor_engagements (
                id, customer_name, customer_id, is_our_customer,
                competitor, engagement_type, threat_level,
                engagement_date, vessel_name, vessel_type,
                source_url, source_type, threat_reason,
                requires_sales_action, action_recommendation,
                region, country, created_at
            ) VALUES (
                $1, $2, $3, $4,
                $5, $6::engagement_type_enum, $7::threat_level_enum,
                $8, $9, $10,
                $11, $12, $13,
                $14, $15,
                $16, $17, NOW()
            )
            RETURNING id
        """

        async with self.pool.acquire() as conn:
            await conn.execute(
                query,
                engagement_id,
                customer_name,
                customer_id,
                is_our_customer,
                competitor,
                engagement_type,
                threat_level,
                engagement_date,
                vessel_name,
                vessel_type,
                source_url,
                source_type,
                threat_reason,
                requires_sales_action,
                action_recommendation,
                region,
                country,
            )

        logger.info(
            f"Created competitor engagement {engagement_id} for {competitor} at {customer_name}"
        )
        return engagement_id

    async def list_competitor_engagements(
        self,
        requires_action: Optional[bool] = None,
        threat_level: Optional[str] = None,
        competitor: Optional[str] = None,
        is_our_customer: Optional[bool] = None,
        limit: int = 50,
    ) -> list[dict]:
        """
        List competitor engagements with optional filters.

        Args:
            requires_action: Filter by requires_sales_action flag
            threat_level: Filter by threat level (high, medium, low)
            competitor: Filter by competitor name
            is_our_customer: Filter by is_our_customer flag
            limit: Maximum results to return

        Returns:
            List of engagement records as dictionaries
        """
        await self._check_allowed_table("kb_competitor_engagements")

        conditions: list[str] = []
        params: list[Any] = []

        if requires_action is not None:
            conditions.append(f"requires_sales_action = ${len(params) + 1}")
            params.append(requires_action)

        if threat_level:
            conditions.append(f"threat_level = ${len(params) + 1}::threat_level_enum")
            params.append(threat_level)

        if competitor:
            conditions.append(f"LOWER(competitor) = ${len(params) + 1}")
            params.append(competitor.lower())

        if is_our_customer is not None:
            conditions.append(f"is_our_customer = ${len(params) + 1}")
            params.append(is_our_customer)

        where_clause = " AND ".join(conditions) if conditions else "TRUE"

        query = f"""
            SELECT
                id, customer_name, customer_id, is_our_customer,
                competitor, engagement_type::text, threat_level::text,
                engagement_date, vessel_name, vessel_type,
                source_url, source_type, threat_reason,
                requires_sales_action, action_recommendation,
                sales_rep_notified, resolution_status,
                region, country, created_at
            FROM kb_competitor_engagements
            WHERE {where_clause}
            ORDER BY
                requires_sales_action DESC,
                CASE threat_level
                    WHEN 'high' THEN 1
                    WHEN 'medium' THEN 2
                    WHEN 'low' THEN 3
                END,
                created_at DESC
            LIMIT ${len(params) + 1}
        """
        params.append(limit)

        async with self.pool.acquire() as conn:
            rows = await conn.fetch(query, *params)

        return [dict(row) for row in rows]

    async def get_high_priority_engagements(self, limit: int = 10) -> list[dict]:
        """
        Get engagements requiring immediate sales attention.

        Returns engagements that:
        - Require sales action AND not yet notified
        - OR are high threat level AND at our customers

        Args:
            limit: Maximum results to return

        Returns:
            List of high-priority engagement records
        """
        await self._check_allowed_table("kb_competitor_engagements")

        query = """
            SELECT
                id, customer_name, customer_id, is_our_customer,
                competitor, engagement_type::text, threat_level::text,
                engagement_date, vessel_name, vessel_type,
                threat_reason, action_recommendation,
                region, country, created_at
            FROM kb_competitor_engagements
            WHERE (
                (requires_sales_action = TRUE AND sales_rep_notified = FALSE)
                OR
                (threat_level = 'high'::threat_level_enum AND is_our_customer = TRUE)
            )
            AND resolution_status = 'open'
            ORDER BY
                requires_sales_action DESC,
                is_our_customer DESC,
                created_at DESC
            LIMIT $1
        """

        async with self.pool.acquire() as conn:
            rows = await conn.fetch(query, limit)

        return [dict(row) for row in rows]

    async def mark_engagement_notified(
        self,
        engagement_id: str,
        notified_to: str,
    ) -> bool:
        """
        Mark an engagement as notified to sales.

        Args:
            engagement_id: ID of the engagement
            notified_to: Email or name of person notified

        Returns:
            True if successful
        """
        await self._check_allowed_table("kb_competitor_engagements")

        query = """
            UPDATE kb_competitor_engagements
            SET sales_rep_notified = TRUE,
                notified_at = NOW(),
                notified_to = $2,
                updated_at = NOW()
            WHERE id = $1
        """

        async with self.pool.acquire() as conn:
            await conn.execute(query, engagement_id, notified_to)

        logger.info(f"Marked engagement {engagement_id} as notified to {notified_to}")
        return True

    async def count_engagements_by_competitor(self) -> dict[str, int]:
        """
        Count engagements grouped by competitor.

        Returns:
            Dictionary of competitor -> count
        """
        await self._check_allowed_table("kb_competitor_engagements")

        query = """
            SELECT
                LOWER(competitor) as competitor,
                COUNT(*) as count
            FROM kb_competitor_engagements
            GROUP BY LOWER(competitor)
            ORDER BY count DESC
        """

        async with self.pool.acquire() as conn:
            rows = await conn.fetch(query)

        return {row["competitor"]: row["count"] for row in rows}


# =============================================================================
# SINGLETON INSTANCE
# =============================================================================

_db: Optional[KnowledgeBaseDatabase] = None


def get_knowledge_base_db() -> KnowledgeBaseDatabase:
    """Get singleton database instance."""
    global _db
    if _db is None:
        _db = KnowledgeBaseDatabase()
    return _db


async def initialize_knowledge_base_db() -> KnowledgeBaseDatabase:
    """Initialize and return database instance."""
    db = get_knowledge_base_db()
    await db.initialize()
    return db
