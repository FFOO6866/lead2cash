"""
Audit store for RRPS Lead-to-Cash.

Provides append-only event logging and field provenance tracking
for TE-14 (audit trail) and TE-15 (provenance tracking).

All queries use parameterized %s placeholders — NO f-string SQL.
"""

import json
import logging
import uuid as _uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

import psycopg2.extras

from .connection import DatabasePool

logger = logging.getLogger(__name__)

# Allowed event types (must match CHECK constraint in schema.sql)
ALLOWED_EVENT_TYPES = frozenset(
    {
        "CREATED",
        "VALIDATED",
        "ENRICHED",
        "CPI_SENT",
        "CPI_RESPONSE",
        "SAP_POSTED",
        "SAP_ERROR",
        "STATUS_CHANGE",
        "KYP_CHECK",
        "CREDIT_CHECK",
        "FIELD_OVERRIDE",
        "APPROVAL",
        "REJECTION",
        "COMMENT",
    }
)

# Allowed provenance sources (must match CHECK constraint in schema.sql)
ALLOWED_SOURCES = frozenset(
    {
        "SAP_CPI",
        "ARAVO",
        "IPAS",
        "USER",
        "SYSTEM",
    }
)


def _validate_uuid(value: str) -> str:
    """Validate that value is a valid UUID string.

    Raises ValueError if the format is invalid.
    """
    try:
        parsed = _uuid.UUID(str(value))
    except (ValueError, AttributeError) as exc:
        raise ValueError(f"Invalid UUID format: {value!r}") from exc
    return str(parsed)


class AuditStore:
    """Append-only audit store backed by PostgreSQL.

    Wraps the ``transactions``, ``events``, and ``field_provenance`` tables.
    """

    def __init__(self, db_pool: DatabasePool):
        if db_pool is None:
            raise TypeError("AuditStore requires a DatabasePool instance")
        self._pool = db_pool

    # ------------------------------------------------------------------
    # Transactions
    # ------------------------------------------------------------------

    def create_transaction(
        self,
        correlation_id: str,
        user_id: Optional[str] = None,
        status: str = "draft",
    ) -> dict:
        """Create a new transaction record.

        Args:
            correlation_id: UUID identifying this transaction.
            user_id: Optional user/agent who initiated it.
            status: Initial status (default 'draft').

        Returns:
            Dict with the inserted row data.
        """
        cid = _validate_uuid(correlation_id)
        conn = self._pool.getconn()
        try:
            with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
                cur.execute(
                    """
                    INSERT INTO transactions (correlation_id, user_id, status)
                    VALUES (%s, %s, %s)
                    RETURNING correlation_id, vbeln, status, created_at, updated_at, user_id
                    """,
                    (cid, user_id, status),
                )
                row = cur.fetchone()
            conn.commit()
            logger.info("Transaction created: %s", cid)
            return _row_to_dict(row)
        except Exception:
            conn.rollback()
            raise
        finally:
            self._pool.putconn(conn)

    def update_transaction(
        self,
        correlation_id: str,
        *,
        vbeln: Optional[str] = None,
        status: Optional[str] = None,
        idoc_snapshot: Optional[dict] = None,
    ) -> Optional[dict]:
        """Update mutable fields on a transaction.

        Only non-None arguments are applied.

        Returns:
            Updated row dict, or None if no matching transaction.
        """
        cid = _validate_uuid(correlation_id)

        # Build dynamic SET clause — parameterized
        sets: List[str] = []
        params: List[Any] = []
        if vbeln is not None:
            sets.append("vbeln = %s")
            params.append(vbeln)
        if status is not None:
            sets.append("status = %s")
            params.append(status)
        if idoc_snapshot is not None:
            sets.append("idoc_snapshot = %s")
            params.append(json.dumps(idoc_snapshot))

        if not sets:
            return self.get_transaction(correlation_id)

        params.append(cid)  # WHERE clause

        conn = self._pool.getconn()
        try:
            with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
                cur.execute(
                    f"UPDATE transactions SET {', '.join(sets)} WHERE correlation_id = %s "
                    "RETURNING correlation_id, vbeln, status, created_at, updated_at, user_id",
                    params,
                )
                row = cur.fetchone()
            conn.commit()
            if row:
                logger.info("Transaction updated: %s", cid)
            return _row_to_dict(row) if row else None
        except Exception:
            conn.rollback()
            raise
        finally:
            self._pool.putconn(conn)

    def get_transaction(self, correlation_id: str) -> Optional[dict]:
        """Retrieve a transaction with its events and provenance records.

        Returns:
            Dict with ``transaction``, ``events``, and ``provenance`` keys,
            or None if no matching transaction.
        """
        cid = _validate_uuid(correlation_id)
        conn = self._pool.getconn()
        try:
            with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
                # Transaction row
                cur.execute(
                    """
                    SELECT correlation_id, vbeln, idoc_snapshot, status,
                           created_at, updated_at, user_id
                    FROM transactions
                    WHERE correlation_id = %s
                    """,
                    (cid,),
                )
                txn_row = cur.fetchone()
                if txn_row is None:
                    return None

                # Events
                cur.execute(
                    """
                    SELECT id, event_type, data, timestamp
                    FROM events
                    WHERE transaction_id = %s
                    ORDER BY timestamp ASC
                    """,
                    (cid,),
                )
                event_rows = cur.fetchall()

                # Provenance
                cur.execute(
                    """
                    SELECT id, field_name, source, confidence,
                           original_value, final_value, rule_id, created_at
                    FROM field_provenance
                    WHERE transaction_id = %s
                    ORDER BY created_at ASC
                    """,
                    (cid,),
                )
                prov_rows = cur.fetchall()

            return {
                "transaction": _row_to_dict(txn_row),
                "events": [_row_to_dict(r) for r in event_rows],
                "provenance": [_row_to_dict(r) for r in prov_rows],
            }
        finally:
            self._pool.putconn(conn)

    def get_by_vbeln(self, vbeln: str) -> Optional[dict]:
        """Look up a transaction by SAP sales document number.

        Returns the same structure as ``get_transaction``, or None.
        """
        if not vbeln or not vbeln.strip():
            raise ValueError("vbeln must be a non-empty string")

        conn = self._pool.getconn()
        try:
            with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
                cur.execute(
                    "SELECT correlation_id FROM transactions WHERE vbeln = %s LIMIT 1",
                    (vbeln,),
                )
                row = cur.fetchone()
                if row is None:
                    return None
            # Delegate to get_transaction for the full join
            return self.get_transaction(str(row["correlation_id"]))
        finally:
            self._pool.putconn(conn)

    # ------------------------------------------------------------------
    # Events (APPEND-ONLY)
    # ------------------------------------------------------------------

    def log_event(
        self,
        correlation_id: str,
        event_type: str,
        data: dict,
    ) -> int:
        """Append an event to the audit log.

        Args:
            correlation_id: UUID of the parent transaction.
            event_type: Must be one of ALLOWED_EVENT_TYPES.
            data: Arbitrary JSON-serializable payload.

        Returns:
            The auto-generated event ``id``.

        Raises:
            ValueError: If correlation_id is not a valid UUID or
                        event_type is not in the allowed set.
        """
        cid = _validate_uuid(correlation_id)

        if event_type not in ALLOWED_EVENT_TYPES:
            raise ValueError(
                f"Invalid event_type {event_type!r}. "
                f"Allowed: {sorted(ALLOWED_EVENT_TYPES)}"
            )

        if not isinstance(data, dict):
            raise TypeError("event data must be a dict")

        conn = self._pool.getconn()
        try:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO events (transaction_id, event_type, data)
                    VALUES (%s, %s, %s)
                    RETURNING id
                    """,
                    (cid, event_type, json.dumps(data)),
                )
                event_id = cur.fetchone()[0]
            conn.commit()
            logger.debug(
                "Event logged: txn=%s type=%s id=%d", cid, event_type, event_id
            )
            return event_id
        except Exception:
            conn.rollback()
            raise
        finally:
            self._pool.putconn(conn)

    # ------------------------------------------------------------------
    # Field Provenance (APPEND-ONLY)
    # ------------------------------------------------------------------

    def log_provenance(
        self,
        correlation_id: str,
        field_name: str,
        source: str,
        confidence: float,
        original_value: Optional[str] = None,
        final_value: Optional[str] = None,
        rule_id: Optional[str] = None,
    ) -> int:
        """Append a field provenance record.

        Args:
            correlation_id: UUID of the parent transaction.
            field_name: Dotted field path (e.g. ``header.soldTo``).
            source: Must be one of ALLOWED_SOURCES.
            confidence: Float between 0.0 and 1.0.
            original_value: Raw value from source system.
            final_value: Value after derivation/override.
            rule_id: Derivation rule identifier (if applicable).

        Returns:
            The auto-generated provenance record ``id``.

        Raises:
            ValueError: On invalid UUID, source, or confidence range.
        """
        cid = _validate_uuid(correlation_id)

        if source not in ALLOWED_SOURCES:
            raise ValueError(
                f"Invalid source {source!r}. Allowed: {sorted(ALLOWED_SOURCES)}"
            )

        if not isinstance(confidence, (int, float)):
            raise TypeError("confidence must be a number")
        if not (0.0 <= confidence <= 1.0):
            raise ValueError(
                f"confidence must be between 0.0 and 1.0, got {confidence}"
            )

        if not field_name or not field_name.strip():
            raise ValueError("field_name must be a non-empty string")

        conn = self._pool.getconn()
        try:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO field_provenance
                        (transaction_id, field_name, source, confidence,
                         original_value, final_value, rule_id)
                    VALUES (%s, %s, %s, %s, %s, %s, %s)
                    RETURNING id
                    """,
                    (
                        cid,
                        field_name,
                        source,
                        confidence,
                        original_value,
                        final_value,
                        rule_id,
                    ),
                )
                prov_id = cur.fetchone()[0]
            conn.commit()
            logger.debug(
                "Provenance logged: txn=%s field=%s source=%s id=%d",
                cid,
                field_name,
                source,
                prov_id,
            )
            return prov_id
        except Exception:
            conn.rollback()
            raise
        finally:
            self._pool.putconn(conn)

    # ------------------------------------------------------------------
    # Batch helpers
    # ------------------------------------------------------------------

    def log_provenance_batch(
        self,
        correlation_id: str,
        records: List[Dict[str, Any]],
    ) -> List[int]:
        """Insert multiple provenance records in a single transaction.

        Each record dict must have keys: ``field_name``, ``source``,
        ``confidence``. Optional: ``original_value``, ``final_value``,
        ``rule_id``.

        Returns:
            List of auto-generated provenance record IDs.
        """
        cid = _validate_uuid(correlation_id)
        ids: List[int] = []

        conn = self._pool.getconn()
        try:
            with conn.cursor() as cur:
                for rec in records:
                    source = rec["source"]
                    confidence = rec["confidence"]
                    field_name = rec["field_name"]

                    if source not in ALLOWED_SOURCES:
                        raise ValueError(f"Invalid source {source!r} in batch record")
                    if not (0.0 <= float(confidence) <= 1.0):
                        raise ValueError(
                            f"confidence out of range in batch record: {confidence}"
                        )

                    cur.execute(
                        """
                        INSERT INTO field_provenance
                            (transaction_id, field_name, source, confidence,
                             original_value, final_value, rule_id)
                        VALUES (%s, %s, %s, %s, %s, %s, %s)
                        RETURNING id
                        """,
                        (
                            cid,
                            field_name,
                            source,
                            float(confidence),
                            rec.get("original_value"),
                            rec.get("final_value"),
                            rec.get("rule_id"),
                        ),
                    )
                    ids.append(cur.fetchone()[0])
            conn.commit()
            logger.info("Batch provenance logged: txn=%s count=%d", cid, len(ids))
            return ids
        except Exception:
            conn.rollback()
            raise
        finally:
            self._pool.putconn(conn)


# ======================================================================
# Helpers
# ======================================================================


def _row_to_dict(row) -> dict:
    """Convert a RealDictRow to a plain dict with JSON-safe values."""
    if row is None:
        return {}
    result = dict(row)
    for key, val in result.items():
        if isinstance(val, datetime):
            result[key] = val.isoformat()
        elif isinstance(val, _uuid.UUID):
            result[key] = str(val)
    return result
