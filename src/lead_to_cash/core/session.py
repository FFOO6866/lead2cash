"""
Session management for the application.

This module handles session creation, management, and cleanup using Redis.

Features:
- Secure session ID generation (uuid4)
- Redis-backed session storage with TTL
- Optional Fernet encryption of session data at rest
- Session validation and expiration
- Session refresh on activity
- Graceful cleanup of expired sessions

Session Data Structure:
{
    "user_id": "kianseng.tee",
    "username": "kianseng.tee",
    "first_name": "Kian Seng",
    "last_name": "Tee",
    "roles": ["admin", "sales_ops"],
    "tenant_id": "default",
    "created_at": "2024-01-20T10:00:00Z",
    "last_accessed": "2024-01-20T14:30:00Z",
    "device_info": {"user_agent": "...", "ip": "..."}
}

Encryption:
    Set SESSION_ENCRYPTION_KEY env var to enable Fernet encryption.
    Generate a key: python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
"""

import json
import logging
import os
import uuid
from datetime import datetime, timezone
from typing import TYPE_CHECKING, Any, Optional

if TYPE_CHECKING:
    import redis.asyncio as aioredis

logger = logging.getLogger(__name__)


class SessionNotInitializedError(Exception):
    """Raised when session manager is used before initialization."""

    def __init__(self, component: str = "Redis"):
        self.component = component
        super().__init__(f"{component} not initialized. Call initialize() first.")


class SessionManager:
    """Redis-backed session manager.

    Handles session lifecycle:
    - Create sessions for authenticated users
    - Validate active sessions
    - Refresh sessions on activity
    - Destroy sessions on logout
    """

    def __init__(
        self,
        redis_url: Optional[str] = None,
        session_timeout: int = 3600,  # 1 hour default
        key_prefix: str = "session:",
        encryption_key: Optional[str] = None,
    ):
        """Initialize SessionManager.

        Args:
            redis_url: Redis connection URL (defaults to REDIS_URL env var)
            session_timeout: Session TTL in seconds (default: 3600 = 1 hour)
            key_prefix: Redis key prefix for sessions
            encryption_key: Fernet key for encrypting session data at rest.
                Defaults to SESSION_ENCRYPTION_KEY env var. If not set,
                sessions are stored as plaintext JSON.
        """
        self.redis_url = redis_url or os.getenv("REDIS_URL")
        self.session_timeout = int(os.getenv("SESSION_TIMEOUT", str(session_timeout)))
        self.key_prefix = key_prefix
        self._redis: Optional["aioredis.Redis"] = None
        self._initialized = False

        # Session encryption (optional but recommended for production)
        self._cipher = None
        enc_key = encryption_key or os.getenv("SESSION_ENCRYPTION_KEY")
        if enc_key:
            try:
                from cryptography.fernet import Fernet

                self._cipher = Fernet(
                    enc_key.encode() if isinstance(enc_key, str) else enc_key
                )
                logger.info("Session encryption enabled (Fernet)")
            except ImportError:
                logger.warning(
                    "SESSION_ENCRYPTION_KEY set but cryptography package not installed. "
                    "Install with: pip install cryptography"
                )
            except Exception as e:
                raise ValueError(
                    f"Invalid SESSION_ENCRYPTION_KEY: {e}. "
                    "Generate a valid key: python -c \"from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())\""
                ) from e

    def _encrypt(self, data: str) -> str:
        """Encrypt session data if encryption is configured."""
        if self._cipher:
            return self._cipher.encrypt(data.encode()).decode()
        return data

    def _decrypt(self, data: str) -> str:
        """Decrypt session data if encryption is configured.

        When SESSION_MIGRATION_MODE=true, falls back to plaintext on decryption
        failure (for transitioning from unencrypted to encrypted sessions).
        Migration mode should be disabled after SESSION_TIMEOUT elapses.
        """
        if self._cipher:
            try:
                from cryptography.fernet import InvalidToken

                return self._cipher.decrypt(data.encode()).decode()
            except InvalidToken:
                if os.getenv("SESSION_MIGRATION_MODE", "").lower() == "true":
                    logger.warning(
                        "Decryption failed — plaintext fallback (migration mode). "
                        "Disable SESSION_MIGRATION_MODE after all sessions rotate."
                    )
                    return data
                logger.warning("Decryption failed — rejecting session (not in migration mode)")
                raise
        return data

    @property
    def redis(self) -> "aioredis.Redis":
        """Get the Redis client, raising if not initialized."""
        if self._redis is None:
            raise SessionNotInitializedError("Redis")
        return self._redis

    async def initialize(self) -> bool:
        """Initialize Redis connection.

        Safe to call multiple times — cleans up any previous connection before
        creating a new one to prevent resource leaks.

        Returns:
            True if connected successfully, False otherwise
        """
        if not self.redis_url:
            logger.warning("REDIS_URL not configured - session management unavailable")
            return False

        # Close any existing connection to prevent leaks on re-initialization
        if self._redis is not None:
            try:
                await self._redis.close()
            except Exception:
                pass
            self._redis = None
            self._initialized = False

        try:
            import redis.asyncio as redis

            client = redis.from_url(
                self.redis_url,
                encoding="utf-8",
                decode_responses=True,
            )

            # Test connection before assigning to self._redis
            await client.ping()
            self._redis = client
            self._initialized = True
            logger.info("Redis session manager initialized")
            return True

        except ImportError:
            logger.error("redis package not installed - run: pip install redis")
            return False
        except Exception as e:
            logger.error(f"Failed to connect to Redis: {e}")
            return False

    async def close(self) -> None:
        """Close Redis connection."""
        if self._redis:
            try:
                await self._redis.close()
                logger.info("Redis session manager closed")
            except Exception as e:
                logger.warning(f"Error closing Redis connection: {e}")
            finally:
                self._redis = None
                self._initialized = False

    @property
    def is_available(self) -> bool:
        """Check if session manager is available."""
        return self._initialized and self._redis is not None

    def _session_key(self, session_id: str) -> str:
        """Generate Redis key for session."""
        return f"{self.key_prefix}{session_id}"

    async def create_session(
        self,
        user_id: str,
        user_data: dict[str, Any],
        device_info: Optional[dict[str, str]] = None,
    ) -> Optional[str]:
        """Create a new session for authenticated user.

        Args:
            user_id: User identifier
            user_data: User information to store in session
            device_info: Optional device/client information

        Returns:
            Session ID string if created, None on failure
        """
        if not self.is_available:
            logger.warning("Session manager not available - cannot create session")
            return None

        session_id = f"sess_{uuid.uuid4().hex}"
        now = datetime.now(timezone.utc).isoformat()

        session_data = {
            "user_id": user_id,
            "username": user_data.get("username", user_id),
            "first_name": user_data.get("first_name", ""),
            "last_name": user_data.get("last_name", ""),
            "roles": user_data.get("roles", []),
            "tenant_id": user_data.get("tenant_id", "default"),
            "created_at": now,
            "last_accessed": now,
            "device_info": device_info or {},
        }

        try:
            key = self._session_key(session_id)
            serialized = self._encrypt(json.dumps(session_data))
            await self.redis.setex(
                key,
                self.session_timeout,
                serialized,
            )
            logger.debug(f"Created session {session_id[:16]}... for user {user_id}")
            return session_id

        except Exception as e:
            logger.error(f"Failed to create session: {e}")
            return None

    async def validate_session(self, session_id: str) -> Optional[dict[str, Any]]:
        """Validate session and return session data.

        Args:
            session_id: Session identifier

        Returns:
            Session data dict if valid, None if invalid/expired
        """
        if not self.is_available:
            return None

        try:
            key = self._session_key(session_id)
            data = await self.redis.get(key)

            if not data:
                logger.debug(f"Session {session_id[:16]}... not found or expired")
                return None

            decrypted = self._decrypt(data)
            session_data = json.loads(decrypted)
            logger.debug(
                f"Validated session {session_id[:16]}... for user {session_data.get('user_id')}"
            )
            return session_data

        except json.JSONDecodeError as e:
            logger.error(f"Corrupted session data: {e}")
            return None
        except Exception as e:
            logger.error(f"Failed to validate session: {e}")
            return None

    async def refresh_session(self, session_id: str) -> bool:
        """Refresh session TTL and update last_accessed time.

        Args:
            session_id: Session identifier

        Returns:
            True if refreshed, False otherwise
        """
        if not self.is_available:
            return False

        try:
            key = self._session_key(session_id)
            data = await self.redis.get(key)

            if not data:
                return False

            decrypted = self._decrypt(data)
            session_data = json.loads(decrypted)
            session_data["last_accessed"] = datetime.now(timezone.utc).isoformat()

            serialized = self._encrypt(json.dumps(session_data))
            await self.redis.setex(
                key,
                self.session_timeout,
                serialized,
            )

            logger.debug(f"Refreshed session {session_id[:16]}...")
            return True

        except Exception as e:
            logger.error(f"Failed to refresh session: {e}")
            return False

    async def destroy_session(self, session_id: str) -> bool:
        """Destroy session (logout).

        Args:
            session_id: Session identifier

        Returns:
            True if destroyed, False otherwise
        """
        if not self.is_available:
            return False

        try:
            key = self._session_key(session_id)
            result = await self.redis.delete(key)
            if result:
                logger.debug(f"Destroyed session {session_id[:16]}...")
            return bool(result)

        except Exception as e:
            logger.error(f"Failed to destroy session: {e}")
            return False

    async def get_user_sessions(self, user_id: str) -> list[dict[str, Any]]:
        """Get all active sessions for a user.

        Args:
            user_id: User identifier

        Returns:
            List of session data dicts
        """
        if not self.is_available:
            return []

        try:
            # Scan for all session keys (be careful with large datasets)
            sessions = []
            cursor = 0

            while True:
                cursor, keys = await self.redis.scan(
                    cursor,
                    match=f"{self.key_prefix}*",
                    count=100,
                )

                for key in keys:
                    data = await self.redis.get(key)
                    if data:
                        session_data = json.loads(self._decrypt(data))
                        if session_data.get("user_id") == user_id:
                            session_data["session_id"] = key.replace(
                                self.key_prefix, ""
                            )
                            sessions.append(session_data)

                if cursor == 0:
                    break

            return sessions

        except Exception as e:
            logger.error(f"Failed to get user sessions: {e}")
            return []

    async def destroy_user_sessions(self, user_id: str) -> int:
        """Destroy all sessions for a user.

        Args:
            user_id: User identifier

        Returns:
            Number of sessions destroyed
        """
        sessions = await self.get_user_sessions(user_id)
        destroyed = 0

        for session in sessions:
            session_id = session.get("session_id")
            if session_id and await self.destroy_session(session_id):
                destroyed += 1

        logger.info(f"Destroyed {destroyed} sessions for user {user_id}")
        return destroyed
