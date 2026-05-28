"""
PostgreSQL connection pool for RRPS Lead-to-Cash.

Uses psycopg2 ThreadedConnectionPool for thread-safe connection management.
Reads DATABASE_URL from environment via AppConfig.
"""

import logging
from typing import Optional

import psycopg2
import psycopg2.pool

logger = logging.getLogger(__name__)

# Module-level pool singleton
_pool: Optional["DatabasePool"] = None


class DatabasePool:
    """Thread-safe PostgreSQL connection pool wrapper.

    Usage::

        pool = DatabasePool(database_url="postgresql://...")
        pool.initialize()

        conn = pool.getconn()
        try:
            with conn.cursor() as cur:
                cur.execute("SELECT 1")
        finally:
            pool.putconn(conn)

        pool.close()
    """

    def __init__(
        self,
        database_url: str,
        min_connections: int = 2,
        max_connections: int = 10,
    ):
        if not database_url:
            raise ValueError(
                "DATABASE_URL is required — set it in the environment or .env"
            )
        self._database_url = database_url
        self._min_connections = min_connections
        self._max_connections = max_connections
        self._pool: Optional[psycopg2.pool.ThreadedConnectionPool] = None

    def initialize(self) -> None:
        """Create the underlying connection pool.

        Raises psycopg2.OperationalError on connection failure.
        """
        if self._pool is not None:
            logger.warning("DatabasePool.initialize() called twice — ignoring")
            return

        logger.info(
            "Initializing PostgreSQL pool (min=%d, max=%d)",
            self._min_connections,
            self._max_connections,
        )
        self._pool = psycopg2.pool.ThreadedConnectionPool(
            minconn=self._min_connections,
            maxconn=self._max_connections,
            dsn=self._database_url,
        )
        logger.info("PostgreSQL connection pool ready")

    # ------------------------------------------------------------------
    # Connection lifecycle
    # ------------------------------------------------------------------

    def getconn(self):
        """Get a connection from the pool.

        Returns a psycopg2 connection object.
        Raises RuntimeError if the pool has not been initialized.
        """
        if self._pool is None:
            raise RuntimeError("DatabasePool not initialized — call initialize() first")
        return self._pool.getconn()

    def putconn(self, conn, close: bool = False) -> None:
        """Return a connection to the pool.

        Args:
            conn: The connection to return.
            close: If True, close the connection instead of returning it.
        """
        if self._pool is None:
            return
        self._pool.putconn(conn, close=close)

    # ------------------------------------------------------------------
    # Health check
    # ------------------------------------------------------------------

    def health_check(self) -> dict:
        """Check database connectivity.

        Returns a dict with ``status`` ('healthy' or 'unhealthy') and
        optional ``error`` message.
        """
        if self._pool is None:
            return {"status": "unhealthy", "error": "Pool not initialized"}

        conn = None
        try:
            conn = self.getconn()
            with conn.cursor() as cur:
                cur.execute("SELECT 1")
                cur.fetchone()
            return {"status": "healthy"}
        except Exception as exc:
            logger.error("Database health check failed: %s", exc)
            return {
                "status": "unhealthy",
                "error": "database connectivity check failed",
            }
        finally:
            if conn is not None:
                self.putconn(conn)

    # ------------------------------------------------------------------
    # Schema bootstrap
    # ------------------------------------------------------------------

    def run_schema(self, schema_path: str) -> None:
        """Execute a SQL schema file against the database.

        Args:
            schema_path: Absolute path to the .sql file.
        """
        conn = None
        try:
            conn = self.getconn()
            conn.autocommit = True
            with open(schema_path, "r", encoding="utf-8") as fh:
                sql = fh.read()
            with conn.cursor() as cur:
                cur.execute(sql)
            logger.info("Schema applied from %s", schema_path)
        except Exception:
            logger.exception("Failed to apply schema from %s", schema_path)
            raise
        finally:
            if conn is not None:
                conn.autocommit = False
                self.putconn(conn)

    # ------------------------------------------------------------------
    # Shutdown
    # ------------------------------------------------------------------

    def close(self) -> None:
        """Close all connections in the pool."""
        if self._pool is not None:
            self._pool.closeall()
            self._pool = None
            logger.info("PostgreSQL connection pool closed")

    @property
    def is_initialized(self) -> bool:
        """True if the pool has been initialized and is open."""
        return self._pool is not None


def get_pool() -> Optional["DatabasePool"]:
    """Return the module-level pool singleton (or None if not set)."""
    return _pool


def set_pool(pool: "DatabasePool") -> None:
    """Set the module-level pool singleton."""
    global _pool
    _pool = pool
