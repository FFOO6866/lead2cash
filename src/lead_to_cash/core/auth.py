"""
Authentication logic for the application.

This module handles all authentication-related functionality including:
- User authentication with bcrypt password hashing
- JWT token generation and validation
- Role-based access control (RBAC)
- Permission checking based on roles and resources

RBAC Roles:
- admin: Full system access (*)
- sales_ops: Chat, agents, validation, insights, workflows
- viewer: Read-only chat and insights
"""

import logging
import os
import secrets
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Optional

import bcrypt
import jwt
import yaml

logger = logging.getLogger(__name__)


@dataclass
class AuthUser:
    """Authenticated user information."""

    user_id: str
    username: str
    roles: list[str] = field(default_factory=list)
    tenant_id: str = "default"
    first_name: str = ""
    last_name: str = ""
    default_region: str = ""
    status: str = "active"

    @property
    def is_admin(self) -> bool:
        """Check if user has admin role."""
        return "admin" in self.roles

    @property
    def full_name(self) -> str:
        """Get full name."""
        return f"{self.first_name} {self.last_name}".strip() or self.username


# RBAC Permission Rules
# Format: role -> {resource -> [actions]}
RBAC_PERMISSIONS: dict[str, dict[str, list[str]]] = {
    "admin": {
        "*": ["*"],  # Full access to everything
    },
    "sales_ops": {
        "chat": ["read", "write"],
        "agents": ["read", "execute"],
        "validation": ["read", "execute"],
        "insights": ["read", "query"],
        "workflows": ["read", "execute"],
        "competitor_intel": ["read", "query", "refresh"],
        "marine_intel": ["read", "query", "refresh"],
    },
    "financeops": {
        "chat": ["read", "write"],
        "agents": ["read", "execute"],
        "billing": ["read", "write"],
        "collections": ["read", "write"],
        "payments": ["read"],
        "finops_dashboard": ["read"],
        "insights": ["read"],
    },
    "viewer": {
        "chat": ["read"],
        "insights": ["read"],
        "competitor_intel": ["read"],
        "marine_intel": ["read"],
    },
}


class AuthManager:
    """Authentication and authorization manager.

    Handles:
    - User authentication from YAML config
    - JWT token generation and validation
    - RBAC permission checking
    """

    def __init__(
        self,
        users_config_path: Optional[str] = None,
        jwt_secret: Optional[str] = None,
        jwt_algorithm: str = "HS256",
        jwt_expire_minutes: int = 480,  # 8 hours
    ):
        """Initialize AuthManager.

        Args:
            users_config_path: Path to users.yaml config file
            jwt_secret: Secret key for JWT signing (defaults to env var)
            jwt_algorithm: JWT algorithm (default: HS256)
            jwt_expire_minutes: JWT token expiry in minutes (default: 480 = 8 hours)
        """
        self.jwt_secret = jwt_secret or os.getenv("JWT_SECRET_KEY")
        self.jwt_algorithm = jwt_algorithm or os.getenv("JWT_ALGORITHM", "HS256")
        self.jwt_expire_minutes = int(
            os.getenv("JWT_EXPIRE_MINUTES", str(jwt_expire_minutes))
        )
        self.jwt_issuer = "rrps-lead-to-cash"

        # Validate JWT secret
        if not self.jwt_secret:
            logger.warning(
                "JWT_SECRET_KEY not set - authentication will fail. "
                "Generate one with: openssl rand -hex 32"
            )

        # Load users from config
        self._users: dict[str, dict] = {}
        self._users_config_path = users_config_path
        self._load_users()

    def _load_users(self) -> None:
        """Load users from YAML configuration file."""
        # Determine config path
        if self._users_config_path:
            config_path = Path(self._users_config_path)
        else:
            # Default: look in config directory relative to this module
            config_path = Path(__file__).parent.parent / "config" / "users.yaml"

        if not config_path.exists():
            logger.warning(f"Users config not found at {config_path}")
            return

        try:
            with open(config_path) as f:
                config = yaml.safe_load(f)

            if not config or "users" not in config:
                logger.warning("No users defined in config file")
                return

            for user_data in config["users"]:
                username = user_data.get("username")
                if username:
                    self._users[username] = user_data
                    logger.debug(f"Loaded user: {username}")

            logger.info(f"Loaded {len(self._users)} users from {config_path}")

        except Exception as e:
            logger.error(f"Failed to load users config: {e}")

    def authenticate(self, username: str, password: str) -> Optional[AuthUser]:
        """Authenticate user with username and password.

        Args:
            username: User's username (e.g., "kianseng.tee")
            password: User's password (plaintext)

        Returns:
            AuthUser if authentication successful, None otherwise
        """
        user_data = self._users.get(username)
        if not user_data:
            logger.warning(f"Authentication failed: user '{username}' not found")
            return None

        # Check user status
        if user_data.get("status") != "active":
            logger.warning(f"Authentication failed: user '{username}' is not active")
            return None

        # Verify password
        password_hash = user_data.get("password_hash")
        if not password_hash:
            logger.error(f"User '{username}' has no password_hash configured")
            return None

        try:
            if not bcrypt.checkpw(
                password.encode("utf-8"), password_hash.encode("utf-8")
            ):
                logger.warning(
                    f"Authentication failed: invalid password for '{username}'"
                )
                return None
        except Exception as e:
            logger.error(f"Password verification error for '{username}': {e}")
            return None

        # Create AuthUser
        return AuthUser(
            user_id=user_data.get("user_id", username),
            username=username,
            roles=user_data.get("roles", []),
            tenant_id=user_data.get("tenant_id", "default"),
            first_name=user_data.get("first_name", ""),
            last_name=user_data.get("last_name", ""),
            default_region=user_data.get("default_region", ""),
            status=user_data.get("status", "active"),
        )

    def generate_jwt(self, user: AuthUser, session_id: str) -> str:
        """Generate JWT token for authenticated user.

        Args:
            user: Authenticated user
            session_id: Session ID to include in token

        Returns:
            JWT token string

        JWT Payload Structure:
            {
                "sub": "kianseng.tee",        # User ID
                "username": "kianseng.tee",
                "first_name": "Kian Seng",
                "last_name": "Tee",
                "roles": ["admin", "sales_ops"],
                "tenant_id": "default",
                "session_id": "sess_abc123...",
                "iat": 1706000000,            # Issued at (Unix timestamp)
                "exp": 1706003600,            # Expiration (Unix timestamp)
                "iss": "rrps-lead-to-cash"    # Issuer
            }
        """
        if not self.jwt_secret:
            raise ValueError("JWT_SECRET_KEY not configured")

        now = datetime.now(timezone.utc)
        expire = now + timedelta(minutes=self.jwt_expire_minutes)

        payload = {
            "sub": user.user_id,
            "username": user.username,
            "first_name": user.first_name,
            "last_name": user.last_name,
            "roles": user.roles,
            "tenant_id": user.tenant_id,
            "session_id": session_id,
            "iat": int(now.timestamp()),
            "exp": int(expire.timestamp()),
            "iss": self.jwt_issuer,
        }

        return jwt.encode(payload, self.jwt_secret, algorithm=self.jwt_algorithm)

    def validate_jwt(self, token: str) -> Optional[dict]:
        """Validate JWT token and return payload.

        Args:
            token: JWT token string

        Returns:
            Token payload dict if valid, None otherwise
        """
        if not self.jwt_secret:
            logger.error("JWT_SECRET_KEY not configured")
            return None

        try:
            payload = jwt.decode(
                token,
                self.jwt_secret,
                algorithms=[self.jwt_algorithm],
                issuer=self.jwt_issuer,
            )
            return payload
        except jwt.ExpiredSignatureError:
            logger.debug("JWT token expired")
            return None
        except jwt.InvalidTokenError as e:
            logger.debug(f"Invalid JWT token: {e}")
            return None

    def check_permission(self, user: AuthUser, resource: str, action: str) -> bool:
        """Check if user has permission for resource/action.

        Args:
            user: Authenticated user
            resource: Resource name (e.g., "chat", "agents", "workflows")
            action: Action name (e.g., "read", "write", "execute")

        Returns:
            True if permitted, False otherwise
        """
        for role in user.roles:
            permissions = RBAC_PERMISSIONS.get(role, {})

            # Check for wildcard access (admin)
            if "*" in permissions:
                if "*" in permissions["*"]:
                    return True

            # Check specific resource permission
            if resource in permissions:
                allowed_actions = permissions[resource]
                if "*" in allowed_actions or action in allowed_actions:
                    return True

        return False

    def get_user_permissions(self, user: AuthUser) -> dict[str, list[str]]:
        """Get all permissions for a user based on their roles.

        Args:
            user: Authenticated user

        Returns:
            Dict of resource -> list of allowed actions
        """
        permissions: dict[str, set[str]] = {}

        for role in user.roles:
            role_permissions = RBAC_PERMISSIONS.get(role, {})

            # Handle wildcard admin access
            if "*" in role_permissions and "*" in role_permissions["*"]:
                return {"*": ["*"]}  # Full access

            for resource, actions in role_permissions.items():
                if resource not in permissions:
                    permissions[resource] = set()
                permissions[resource].update(actions)

        # Convert sets to lists for JSON serialization
        return {k: list(v) for k, v in permissions.items()}

    @staticmethod
    def hash_password(password: str) -> str:
        """Hash a password using bcrypt.

        Use this utility to generate password hashes for users.yaml.

        Args:
            password: Plaintext password

        Returns:
            Bcrypt hash string
        """
        salt = bcrypt.gensalt()
        return bcrypt.hashpw(password.encode("utf-8"), salt).decode("utf-8")

    @staticmethod
    def generate_secret_key() -> str:
        """Generate a secure secret key for JWT signing.

        Returns:
            32-byte hex string suitable for JWT_SECRET_KEY
        """
        return secrets.token_hex(32)
