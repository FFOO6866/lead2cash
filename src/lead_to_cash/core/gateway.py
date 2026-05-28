"""
RRPS Lead-to-Cash Gateway

FastAPI gateway for SAP integration workflows using Kailash SDK.
Provides REST API endpoints for Lead-to-Cash operations.
"""

import asyncio
import ipaddress
import json
import logging
import os
import platform
import re
import secrets
import time
import uuid
from collections import defaultdict
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from fastapi import BackgroundTasks, Depends, FastAPI, HTTPException, Request, Security
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import (
    FileResponse,
    HTMLResponse,
    JSONResponse,
    RedirectResponse,
    StreamingResponse,
)
from fastapi.security import APIKeyHeader
from kailash.runtime import AsyncLocalRuntime
from pydantic import BaseModel, Field, field_validator

from lead_to_cash.agents import AgentRegistry
from lead_to_cash.config import config
from lead_to_cash.core.auth import AuthManager, AuthUser
from lead_to_cash.core.session import SessionManager
from lead_to_cash.integrations import (
    CECClient,
    CPIClient,
    IPASClient,
    MS5Client,
)
from lead_to_cash.services import CustomerValidationService, get_insights_service
from lead_to_cash.services.competitor_intel import (
    initialize_competitor_db,
    start_enhanced_scheduler,
    stop_scheduler,
)
from lead_to_cash.services.marine_intel import (
    initialize_marine_intel_db,
    run_historical_backfill,
)
from lead_to_cash.services.marine_intel import (
    run_manual_research as run_marine_research,
)
from lead_to_cash.services.marine_intel import (
    run_manual_targeted_research,
    start_marine_scheduler,
    stop_marine_scheduler,
)
from lead_to_cash.services.scheduler_watchdog import (
    get_watchdog,
    initialize_watchdog,
)

# =============================================================================
# OpenTelemetry Tracing (Optional - graceful degradation if not installed)
# =============================================================================

OTEL_ENABLED = False
tracer = None

try:
    from opentelemetry import trace
    from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
    from opentelemetry.sdk.resources import Resource
    from opentelemetry.sdk.trace import TracerProvider
    from opentelemetry.sdk.trace.export import BatchSpanProcessor

    # Check if OTEL_EXPORTER_OTLP_ENDPOINT is configured
    OTEL_ENDPOINT = os.getenv("OTEL_EXPORTER_OTLP_ENDPOINT")

    if OTEL_ENDPOINT:
        # Initialize OpenTelemetry
        resource = Resource.create(
            {
                "service.name": "lead-to-cash",
                "service.version": os.getenv("BUILD_VERSION", "dev"),
                "deployment.environment": os.getenv("ENVIRONMENT", "development"),
            }
        )

        provider = TracerProvider(resource=resource)
        processor = BatchSpanProcessor(OTLPSpanExporter(endpoint=OTEL_ENDPOINT))
        provider.add_span_processor(processor)
        trace.set_tracer_provider(provider)

        tracer = trace.get_tracer("lead_to_cash.gateway")
        OTEL_ENABLED = True
        logging.getLogger(__name__).info(
            f"OpenTelemetry tracing enabled, exporting to {OTEL_ENDPOINT}"
        )
    else:
        logging.getLogger(__name__).info(
            "OpenTelemetry disabled - OTEL_EXPORTER_OTLP_ENDPOINT not set"
        )

except ImportError:
    logging.getLogger(__name__).info("OpenTelemetry not installed - tracing disabled")

# Frontend directory
FRONTEND_DIR = Path(__file__).parent.parent / "frontend"

# Documentation directory (built Sphinx docs)
# In Docker: /app/docs/_build/html
# In local dev: ../../../docs/_build/html (relative to this file)
_docker_docs = Path("/app/docs/_build/html")
_local_docs = (
    Path(__file__).parent.parent.parent.parent.parent / "docs" / "_build" / "html"
)
DOCS_DIR = _docker_docs if _docker_docs.exists() else _local_docs

# =============================================================================
# Pydantic Request/Response Models for Input Validation
# =============================================================================


def _sanitize_text(v: str) -> str:
    """Sanitize text to prevent injection attacks.

    Removes:
    - Null bytes
    - Control characters (except newlines and tabs)
    - Excessive whitespace
    """
    if not v:
        return v
    # Remove null bytes
    v = v.replace("\x00", "")
    # Remove control characters except newlines and tabs
    v = re.sub(r"[\x01-\x08\x0b\x0c\x0e-\x1f\x7f]", "", v)
    # Limit consecutive whitespace
    v = re.sub(r"\s{10,}", " " * 10, v)
    return v.strip()


class LoginRequest(BaseModel):
    """Request model for user login."""

    username: str = Field(..., min_length=1, max_length=100, description="Username")
    password: str = Field(..., min_length=1, max_length=100, description="Password")

    @field_validator("username")
    @classmethod
    def sanitize_username(cls, v: str) -> str:
        """Sanitize username - only allow safe characters."""
        v = v.strip()
        # Username should be alphanumeric with dots and underscores
        if not re.match(r"^[a-zA-Z0-9._-]+$", v):
            raise ValueError("Username contains invalid characters")
        return v


class ChatRequest(BaseModel):
    """Request model for conversational chat with session support.

    Implements orchestration_guide.md Section 5: Conversation Management.
    """

    message: str = Field(
        ..., min_length=1, max_length=10000, description="User message"
    )
    session_id: Optional[str] = Field(
        default=None,
        description="Session ID for multi-turn conversation continuity",
    )
    clarification_response: Optional[dict] = Field(
        default=None,
        description="Response to a clarification question (question_id, answer)",
    )
    confirmed_entity: Optional[dict] = Field(
        default=None,
        description="Confirmed entity from user selection (customer_id, customer_name)",
    )
    original_task_type: Optional[str] = Field(
        default=None,
        description="Original task type from entity confirmation (to avoid re-interpretation)",
    )

    @field_validator("message")
    @classmethod
    def sanitize_message(cls, v: str) -> str:
        """Sanitize message text to prevent injection attacks."""
        return _sanitize_text(v)


class CustomerValidationRequest(BaseModel):
    """Request model for customer validation."""

    customer_id: str = Field(
        ..., min_length=1, max_length=20, description="Customer ID"
    )
    order_value: float = Field(
        default=0.0, ge=0, description="Order value for credit check"
    )
    sales_org: Optional[str] = Field(
        default=None, max_length=10, description="Sales organization"
    )

    @field_validator("customer_id")
    @classmethod
    def validate_customer_id(cls, v: str) -> str:
        """Validate customer_id contains only alphanumeric characters."""
        # Remove whitespace
        v = v.strip()

        # Check for valid characters (alphanumeric, dashes, underscores)
        if not re.match(r"^[a-zA-Z0-9_-]+$", v):
            raise ValueError(
                "customer_id must contain only alphanumeric characters, dashes, or underscores"
            )

        return v


class TwoTierValidationRequest(BaseModel):
    """Request model for two-tier customer validation."""

    customer: str = Field(
        ..., min_length=1, max_length=100, description="Customer name or SAP ID"
    )
    order_value: float = Field(
        default=0.0, ge=0, description="Order value for credit check"
    )

    @field_validator("customer")
    @classmethod
    def sanitize_customer(cls, v: str) -> str:
        """Sanitize customer text."""
        return _sanitize_text(v)


class InsightsSearchRequest(BaseModel):
    """Request model for insights search."""

    query: str = Field(..., min_length=1, max_length=1000, description="Search query")

    @field_validator("query")
    @classmethod
    def sanitize_query(cls, v: str) -> str:
        """Sanitize query text."""
        return _sanitize_text(v)


class CompetitorQueryRequest(BaseModel):
    """Request model for competitor intelligence query."""

    query: str = Field(..., min_length=1, max_length=1000, description="Query string")
    competitor: Optional[str] = Field(
        default=None, description="Filter by competitor name"
    )

    @field_validator("query")
    @classmethod
    def sanitize_query(cls, v: str) -> str:
        """Sanitize query text."""
        return _sanitize_text(v)

    @field_validator("competitor")
    @classmethod
    def sanitize_competitor(cls, v: Optional[str]) -> Optional[str]:
        """Sanitize competitor text."""
        return _sanitize_text(v) if v else v


class CompetitorRefreshRequest(BaseModel):
    """Request model for competitor data refresh."""

    competitor: Optional[str] = Field(
        default=None, max_length=100, description="Specific competitor to refresh"
    )

    @field_validator("competitor")
    @classmethod
    def sanitize_competitor(cls, v: Optional[str]) -> Optional[str]:
        """Sanitize competitor text."""
        return _sanitize_text(v) if v else v


class MarineResearchRequest(BaseModel):
    """Request model for marine intelligence research."""

    region: Optional[str] = Field(
        default=None, max_length=50, description="Target region"
    )
    sector: Optional[str] = Field(
        default=None, max_length=50, description="Target sector"
    )
    category: Optional[str] = Field(
        default=None, max_length=50, description="Research category"
    )

    @field_validator("region", "sector", "category")
    @classmethod
    def sanitize_fields(cls, v: Optional[str]) -> Optional[str]:
        """Sanitize text fields."""
        return _sanitize_text(v) if v else v


class WorkflowExecuteRequest(BaseModel):
    """Request model for workflow execution."""

    customer_id: Optional[str] = Field(
        default=None, max_length=20, description="Customer ID for validation"
    )
    opportunity_id: Optional[str] = Field(
        default=None, max_length=50, description="Opportunity ID"
    )
    order_data: Optional[dict] = Field(
        default=None, description="Order data for simulation"
    )

    @field_validator("customer_id", "opportunity_id")
    @classmethod
    def sanitize_id_fields(cls, v: Optional[str]) -> Optional[str]:
        """Sanitize ID fields - remove non-alphanumeric chars."""
        if not v:
            return v
        # IDs should be alphanumeric only (plus hyphens/underscores)
        v = _sanitize_text(v)
        # Additional validation for IDs - only allow safe characters
        return re.sub(r"[^a-zA-Z0-9\-_]", "", v)


# =============================================================================
# Rate Limiting
# =============================================================================
# Uses Redis for distributed rate limiting (works with multiple workers).
# Falls back to in-memory rate limiting if Redis unavailable.

from lead_to_cash.utils.resilience import RedisRateLimiter  # noqa: E402

RATE_LIMIT_REQUESTS = int(
    os.getenv("RATE_LIMIT_REQUESTS", "300")
)  # requests per window (increased from 100)
RATE_LIMIT_WINDOW = int(os.getenv("RATE_LIMIT_WINDOW", "60"))  # window in seconds
REDIS_URL = os.getenv("REDIS_URL")

# Redis rate limiter (initialized at startup)
_redis_rate_limiter: Optional[RedisRateLimiter] = None

# Fallback: In-memory rate limiter for single-worker or Redis unavailable
_rate_limit_store: dict[str, list[tuple[float, int]]] = defaultdict(list)
_rate_limit_last_cleanup = time.time()
_RATE_LIMIT_CLEANUP_INTERVAL = 300  # Cleanup every 5 minutes


def _cleanup_rate_limit_store() -> None:
    """Remove stale entries from in-memory rate limit store."""
    global _rate_limit_last_cleanup
    now = time.time()

    # Only cleanup periodically
    if now - _rate_limit_last_cleanup < _RATE_LIMIT_CLEANUP_INTERVAL:
        return

    _rate_limit_last_cleanup = now
    window_start = now - RATE_LIMIT_WINDOW

    # Find IPs with no recent requests
    to_remove = []
    for ip, entries in _rate_limit_store.items():
        # Filter to recent entries
        recent = [(ts, count) for ts, count in entries if ts > window_start]
        if not recent:
            to_remove.append(ip)
        else:
            _rate_limit_store[ip] = recent

    for ip in to_remove:
        del _rate_limit_store[ip]


def _get_client_ip(request: Request) -> str:
    """Get client IP from request with trusted proxy support.

    SECURITY: Only trusts X-Real-IP/X-Forwarded-For headers when the
    direct connection comes from a trusted proxy. This prevents rate
    limit bypass via header spoofing from untrusted sources.

    Configuration:
    1. Set TRUSTED_PROXIES env var with comma-separated proxy IPs
    2. Configure your reverse proxy (nginx/traefik) to set X-Real-IP
    3. Default trusted proxies: 127.0.0.1, 172.30.0.1 (Docker network)

    Args:
        request: The incoming HTTP request

    Returns:
        Client IP address for rate limiting
    """
    # Get direct connection IP
    direct_ip = request.client.host if request.client else ""

    if not direct_ip:
        return "unknown"

    # Check if request comes from a trusted proxy
    trusted_proxies = getattr(config, "trusted_proxies", ["127.0.0.1"])

    if direct_ip in trusted_proxies:
        # Trust proxy headers - check X-Real-IP first (nginx default)
        real_ip = request.headers.get("X-Real-IP")
        if real_ip:
            # Validate it looks like an IP (basic check)
            if _is_valid_ip(real_ip):
                return real_ip

        # Fall back to X-Forwarded-For (first IP in chain is original client)
        forwarded_for = request.headers.get("X-Forwarded-For")
        if forwarded_for:
            # X-Forwarded-For format: "client, proxy1, proxy2"
            client_ip = forwarded_for.split(",")[0].strip()
            if _is_valid_ip(client_ip):
                return client_ip

    # Not from trusted proxy or no valid proxy headers - use direct IP
    return direct_ip


def _is_valid_ip(ip: str) -> bool:
    """Validate that string is a valid IP address using Python's ipaddress module.

    Args:
        ip: String to validate

    Returns:
        True if string is a valid IPv4 or IPv6 address

    Note:
        Uses Python's ipaddress module for strict validation.
        Rejects:
        - IPv4 with leading zeros (e.g., "192.168.001.001") - security risk
        - Invalid octets (e.g., "256.1.1.1")
        - Malformed addresses
        Accepts:
        - Standard IPv4 (e.g., "192.168.1.1")
        - IPv6 shorthand notation (e.g., "::1")
        - Full IPv6 (e.g., "2001:db8::1")
    """
    if not ip:
        return False

    try:
        ipaddress.ip_address(ip)
        return True
    except ValueError:
        return False


def _check_rate_limit(client_ip: str) -> bool:
    """Check if client has exceeded rate limit. Returns True if allowed."""
    now = time.time()
    window_start = now - RATE_LIMIT_WINDOW

    # Periodically cleanup stale entries from other IPs
    _cleanup_rate_limit_store()

    # Clean old entries for this IP
    _rate_limit_store[client_ip] = [
        (ts, count) for ts, count in _rate_limit_store[client_ip] if ts > window_start
    ]

    # Count requests in window
    total_requests = sum(count for _, count in _rate_limit_store[client_ip])

    if total_requests >= RATE_LIMIT_REQUESTS:
        return False

    # Add this request
    _rate_limit_store[client_ip].append((now, 1))
    return True


# =============================================================================
# Login Brute Force Protection
# =============================================================================
# Two layers of login rate limiting:
# 1. Per (IP, username) pair: prevents lockout DoS (attacker can only exhaust own IP)
# 2. Per IP aggregate: caps total failed attempts from one IP across all usernames
#
# Uses Redis when available (multi-worker safe), falls back to in-memory.

LOGIN_MAX_ATTEMPTS = max(int(os.getenv("LOGIN_MAX_ATTEMPTS", "5")), 1)
LOGIN_IP_MAX_ATTEMPTS = max(int(os.getenv("LOGIN_IP_MAX_ATTEMPTS", "30")), 1)
LOGIN_LOCKOUT_SECONDS = int(os.getenv("LOGIN_LOCKOUT_SECONDS", "300"))  # 5 minutes
_LOGIN_MAX_TRACKED_KEYS = 10000  # In-memory cap (LRU eviction)

# Redis-backed login rate limiters (initialized at startup, None if unavailable)
_redis_login_pair_limiter: Optional[RedisRateLimiter] = None
_redis_login_ip_limiter: Optional[RedisRateLimiter] = None

# Fallback in-memory tracking (single-worker only)
_login_failed_attempts: dict[str, list[float]] = {}
_login_cleanup_last = time.time()


def _cleanup_login_attempts() -> None:
    """Periodically prune stale entries from in-memory login tracking."""
    global _login_cleanup_last
    now = time.time()
    if now - _login_cleanup_last < 300:  # Every 5 minutes
        return
    _login_cleanup_last = now
    cutoff = now - LOGIN_LOCKOUT_SECONDS
    stale = [
        k for k, v in _login_failed_attempts.items() if all(ts <= cutoff for ts in v)
    ]
    for k in stale:
        del _login_failed_attempts[k]


async def _check_login_rate_limit(key: str) -> tuple[bool, int]:
    """Check if a login key is locked out.

    Uses Redis if available (multi-worker safe), falls back to in-memory.
    Keys prefixed with "ip:" use LOGIN_IP_MAX_ATTEMPTS (aggregate per-IP cap).
    All other keys use LOGIN_MAX_ATTEMPTS (per pair cap).

    Returns:
        (is_allowed, seconds_remaining) — if not allowed, seconds_remaining > 0
    """
    is_ip_key = key.startswith("ip:")
    max_attempts = LOGIN_IP_MAX_ATTEMPTS if is_ip_key else LOGIN_MAX_ATTEMPTS

    # Try Redis first (multi-worker safe)
    # IMPORTANT: Use check_only() (read-only) — does NOT record an entry.
    # Recording happens only in _record_failed_login() via is_allowed().
    # This prevents double-counting and avoids consuming slots for successful logins.
    redis_limiter = _redis_login_ip_limiter if is_ip_key else _redis_login_pair_limiter
    if redis_limiter and redis_limiter.is_available:
        under_limit = await redis_limiter.check_only(key)
        if not under_limit:
            remaining = LOGIN_LOCKOUT_SECONDS  # Approximate; Redis uses sliding window
            return False, remaining
        return True, 0

    # Fallback: in-memory tracking
    _cleanup_login_attempts()
    now = time.time()
    cutoff = now - LOGIN_LOCKOUT_SECONDS

    if key not in _login_failed_attempts:
        return True, 0

    _login_failed_attempts[key] = [
        ts for ts in _login_failed_attempts[key] if ts > cutoff
    ]

    recent_count = len(_login_failed_attempts[key])
    if recent_count >= max_attempts:
        oldest = _login_failed_attempts[key][0]
        remaining = int(oldest + LOGIN_LOCKOUT_SECONDS - now) + 1
        return False, max(remaining, 1)

    return True, 0


async def _record_failed_login(key: str) -> None:
    """Record a failed login attempt in Redis or in-memory.

    This is the ONLY place that records login attempts. _check_login_rate_limit
    uses check_only() (read-only) to avoid double-counting and to prevent
    successful logins from consuming rate limit slots.
    """
    is_ip_key = key.startswith("ip:")
    redis_limiter = _redis_login_ip_limiter if is_ip_key else _redis_login_pair_limiter

    # Redis path — is_allowed() atomically records + checks in one Lua call
    if redis_limiter and redis_limiter.is_available:
        await redis_limiter.is_allowed(key)
        return

    # Fallback: in-memory with LRU eviction
    if (
        len(_login_failed_attempts) >= _LOGIN_MAX_TRACKED_KEYS
        and key not in _login_failed_attempts
    ):
        _cleanup_login_attempts()
        if len(_login_failed_attempts) >= _LOGIN_MAX_TRACKED_KEYS:
            oldest_key = min(
                _login_failed_attempts,
                key=lambda k: _login_failed_attempts[k][-1]
                if _login_failed_attempts[k]
                else 0,
            )
            del _login_failed_attempts[oldest_key]
    now = time.time()
    if key not in _login_failed_attempts:
        _login_failed_attempts[key] = []
    _login_failed_attempts[key].append(now)


async def _clear_failed_logins(key: str) -> None:
    """Clear failed login tracking on successful login."""
    is_ip_key = key.startswith("ip:")
    redis_limiter = _redis_login_ip_limiter if is_ip_key else _redis_login_pair_limiter

    if redis_limiter and redis_limiter.is_available:
        await redis_limiter.reset(key)
        return

    _login_failed_attempts.pop(key, None)


# =============================================================================
# API Key Authentication
# =============================================================================

API_KEY_HEADER = APIKeyHeader(name="X-API-Key", auto_error=False)
# Support multiple API keys for rotation: API_KEY=key1,key2 (comma-separated)
_raw_api_key = os.getenv("API_KEY", "")
API_KEYS: list[str] = [k.strip() for k in _raw_api_key.split(",") if k.strip()]
API_KEY = API_KEYS[0] if API_KEYS else None  # Primary key for backward compat
AUTH_DISABLED = not API_KEY

# Track authentication status for startup logging
_auth_warning_logged = False


def _log_auth_status() -> None:
    """Log authentication status at startup - called from lifespan."""
    global _auth_warning_logged
    if _auth_warning_logged:
        return
    _auth_warning_logged = True

    _env = os.getenv("ENVIRONMENT", "development")
    _logger = logging.getLogger(__name__)

    if AUTH_DISABLED:
        if _env == "production":
            _logger.critical(
                "=" * 70 + "\n"
                "SECURITY CRITICAL: API_KEY not set in PRODUCTION!\n"
                "All API endpoints are UNPROTECTED.\n"
                "Set the API_KEY environment variable immediately.\n"
                "=" * 70
            )
        else:
            _logger.warning(
                "Authentication DISABLED - API_KEY not set. "
                "This is acceptable for development but NOT for production."
            )
    else:
        _logger.info("API key authentication ENABLED")


# Public endpoints that don't require authentication
# Note: /docs, /openapi.json, /redoc disabled in production via FastAPI config.
# /metrics removed from public endpoints — requires authentication.
PUBLIC_ENDPOINTS = {
    "/",
    "/health",
    "/login",
    "/projdocs",  # Project documentation
    "/api/v1/auth/login",  # Login endpoint is public
}

# Endpoints that require authentication (session-based)
# Use wildcard (*) at end for prefix matching (e.g., "/api/v1/finops/*")
AUTH_REQUIRED_ENDPOINTS = {
    "/chat",
    "/api/v1/agents",
    "/api/v1/auth/me",  # User profile endpoint
    "/api/v1/chat",
    "/api/v1/chat/stream",  # Streaming chat endpoint
    "/api/v1/validation/*",
    "/api/v1/insights/*",
    "/api/v1/workflows/*",
    "/api/v1/finops/*",  # FinanceOps dashboard endpoints
    "/api/v1/ipas/*",  # IPAS order entry endpoints
    "/api/v1/debug/*",  # Debug endpoints (admin-only RBAC enforced at handler level)
}


async def verify_api_key(
    request: Request,
    api_key: Optional[str] = Security(API_KEY_HEADER),
) -> Optional[str]:
    """Verify API key for protected endpoints."""
    # Skip auth for public endpoints
    if request.url.path in PUBLIC_ENDPOINTS or request.url.path.startswith("/projdocs"):
        return None

    # Skip auth if API_KEY not configured (development mode)
    if not API_KEY:
        return None

    # Skip API key validation if user already authenticated via middleware (JWT/session)
    # This allows browser-based users with valid JWT cookies to access protected endpoints
    if hasattr(request.state, "user") and request.state.user:
        return None

    # Verify API key for programmatic access (no JWT/session)
    if not api_key:
        raise HTTPException(
            status_code=401,
            detail="API key required. Provide X-API-Key header.",
        )

    # Constant-time comparison against all rotation keys (no short-circuit)
    matched = False
    for k in API_KEYS:
        if secrets.compare_digest(api_key, k):
            matched = True
        # No break — always iterate all keys to prevent timing side-channel
    if not matched:
        raise HTTPException(
            status_code=401,
            detail="Invalid API key",
        )

    return api_key


# =============================================================================
# Error Handling Helper
# =============================================================================


def _safe_error_response(e: Exception, context: str = "") -> str:
    """Return a safe error message without exposing internals."""
    # Log the full error for debugging
    logger.error(f"{context}: {type(e).__name__}: {str(e)}")

    # Return generic message in production
    if config.environment == "production":
        return f"An error occurred while {context.lower() or 'processing your request'}. Please try again or contact support."

    # In development, return more details
    return f"{type(e).__name__}: {str(e)}"


def _get_user_permissions(roles: list[str]) -> dict[str, list[str]]:
    """
    Get user permissions based on roles.

    This implements data-layer RBAC - what DATA the user can see.
    Routing is NOT affected by permissions; any user can ask any question.

    Permission format: {resource: [actions]}
    Example: {"billing": ["read", "write"], "marine_intel": ["read"]}

    Role mappings:
    - admin: Full access to everything
    - sales_ops: Marine intel, competitor intel, knowledge base, insights
    - financeops: Billing, collections, AR, plus insights
    - viewer: Read-only access to non-financial data
    """
    permissions = {}

    if "admin" in roles:
        # Admin has full access
        permissions = {"*": ["*"]}
    else:
        # Base permissions for all authenticated users
        permissions["knowledge_base"] = ["read"]
        permissions["general"] = ["read"]

        if "sales_ops" in roles:
            permissions["marine_intel"] = ["read", "write"]
            permissions["competitor_intel"] = ["read", "write"]
            permissions["insights"] = ["read"]
            permissions["kyp"] = ["read"]
            permissions["customer"] = ["read"]

        if "financeops" in roles:
            permissions["billing"] = ["read", "write"]
            permissions["collections"] = ["read", "write"]
            permissions["insights"] = ["read"]
            permissions["kyp"] = ["read"]
            permissions["customer"] = ["read", "write"]

        if "viewer" in roles:
            permissions["marine_intel"] = ["read"]
            permissions["competitor_intel"] = ["read"]
            permissions["knowledge_base"] = ["read"]

    return permissions


# Configure logging
logging.basicConfig(
    level=getattr(logging, config.sdk_log_level),
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)

# Global runtime and client instances
runtime = None
cpi_client = None
ms5_client = None
cec_client = None
ipas_client = None
agent_registry = None
customer_validation_service = None
auth_manager = None
session_manager = None

# Background job tracking with TTL
_refresh_jobs: dict[str, dict] = {}
_JOB_MAX_AGE_SECONDS = 3600  # Clean up jobs older than 1 hour


def _cleanup_old_jobs() -> None:
    """Remove completed/failed jobs older than max age."""
    now = time.time()
    to_remove = []
    for job_id, job in _refresh_jobs.items():
        # Check if job has a completion time
        completed_at = job.get("completed_at")
        if completed_at:
            try:
                completed_time = datetime.fromisoformat(
                    completed_at.replace("Z", "+00:00")
                )
                age = now - completed_time.timestamp()
                if age > _JOB_MAX_AGE_SECONDS:
                    to_remove.append(job_id)
            except (ValueError, AttributeError):
                pass
    for job_id in to_remove:
        del _refresh_jobs[job_id]


def _safe_job_error(e: Exception, context: str = "") -> str:
    """Return safe error message for background jobs."""
    logger.error(f"Background job error - {context}: {type(e).__name__}: {str(e)}")
    if config.environment == "production":
        return f"Job failed: {context or 'processing error'}. Check server logs for details."
    return f"{type(e).__name__}: {str(e)}"


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan manager - initialize/cleanup resources."""
    global \
        runtime, \
        cpi_client, \
        ms5_client, \
        cec_client, \
        ipas_client, \
        agent_registry, \
        customer_validation_service, \
        auth_manager, \
        session_manager

    # Startup
    logger.info(f"Starting {config.app_name} v{config.app_version}")
    logger.info(f"Environment: {config.environment}")

    # CRITICAL: Fail startup in production if API_KEY not set
    # This is an explicit check that runs BEFORE any services initialize
    if config.environment == "production" and not API_KEY:
        logger.critical(
            "=" * 70 + "\n"
            "FATAL: Cannot start server - API_KEY not set in production!\n"
            "All API endpoints would be UNPROTECTED.\n"
            "Set the API_KEY environment variable and restart.\n"
            "=" * 70
        )
        raise RuntimeError(
            "FATAL: API_KEY environment variable is required in production. "
            "Set API_KEY and restart the server."
        )

    # Log authentication status (informational)
    _log_auth_status()

    # Initialize runtime
    runtime = AsyncLocalRuntime()
    logger.info("AsyncLocalRuntime initialized")

    # Initialize authentication and session management
    auth_manager = AuthManager()
    if auth_manager._users:
        logger.info(f"Auth manager initialized with {len(auth_manager._users)} users")
    else:
        logger.warning("Auth manager initialized but no users loaded")

    session_manager = SessionManager()
    if await session_manager.initialize():
        logger.info("Session manager initialized (Redis)")
    else:
        logger.warning("Session manager unavailable - sessions will not persist")

    # Initialize SAP clients - log configuration status, don't connect if not configured
    sap_status = config.is_sap_configured()

    # DEBUG: Log SAP configuration status
    logger.info(f"SAP configuration status: {sap_status}")
    logger.info(
        f"CPI client_id set: {bool(config.sap_cpi.client_id)}, len={len(config.sap_cpi.client_id or '')}"
    )
    logger.info(
        f"CPI client_secret set: {bool(config.sap_cpi.client_secret)}, len={len(config.sap_cpi.client_secret or '')}"
    )
    logger.info(f"CPI token_url: {config.sap_cpi.token_url}")
    logger.info(f"CPI prod_url: {config.sap_cpi.prod_url}")
    logger.info(f"CPI environment: {config.environment}")

    # CPI Client (required for MS5)
    # No simulator fallback — credit data must come from real SAP CPI
    cpi_client = None
    if sap_status.get("cpi"):
        cpi_client = CPIClient()
        logger.info(f"Attempting CPI connection to {cpi_client.base_url}")
        try:
            await cpi_client.connect()
            logger.info("CPI client connected (production mode)")
        except Exception as e:
            import traceback

            logger.warning(f"CPI connection failed: {e}")
            logger.warning(f"CPI connection error type: {type(e).__name__}")
            logger.warning(f"CPI connection traceback: {traceback.format_exc()}")
            cpi_client = None
            logger.warning(
                "CPI unavailable — credit/customer data will not be available"
            )
    else:
        logger.warning(
            "CPI not configured (client_id or client_secret missing) — "
            "credit/customer data will not be available"
        )

    # MS5 Client (depends on CPI — no simulator fallback)
    ms5_client = None
    if cpi_client:
        ms5_client = MS5Client(cpi_client=cpi_client)
        try:
            await ms5_client.connect()
            logger.info("MS5 client connected")
        except ValueError as e:
            logger.warning(f"MS5 not available: {e}")
            ms5_client = None
    else:
        logger.warning("MS5 skipped — CPI client not available")

    # CEC Client (shares CPI client for real CPI opportunity retrieval)
    cec_client = None
    if cpi_client:
        cec_client = CECClient(cpi_client=cpi_client)
        try:
            await cec_client.connect()
            logger.info("CEC client connected (via shared CPI client)")
        except ValueError as e:
            logger.warning(f"CEC not available: {e}")
            cec_client = None
    else:
        logger.warning("CEC skipped — CPI client not available")

    # IPAS Client
    ipas_client = IPASClient()
    if sap_status.get("ipas"):
        try:
            await ipas_client.connect()
            logger.info("IPAS client connected")
        except ValueError as e:
            logger.warning(f"IPAS not available: {e}")
    else:
        logger.warning("IPAS not configured - product configuration unavailable")

    logger.info("SAP integration initialization complete")

    # Initialize PostgreSQL + pgvector database for competitor intelligence
    competitor_db = None
    try:
        competitor_db = await initialize_competitor_db()
        logger.info(
            "PostgreSQL + pgvector competitor intelligence database initialized"
        )
    except Exception as e:
        logger.warning(f"Competitor intelligence database initialization failed: {e}")
        logger.warning("Competitor intelligence RAG will be unavailable")

    # Initialize Sanctions Database (PostgreSQL-backed, replaces live downloads)
    try:
        from lead_to_cash.services.sanctions.database import get_sanctions_service

        sanctions_svc = await get_sanctions_service()
        if await sanctions_svc.is_stale():
            logger.info(
                "Sanctions DB: Data is stale, refreshing from authoritative sources"
            )
            asyncio.create_task(sanctions_svc.refresh_all())
        else:
            count = await sanctions_svc.get_entry_count()
            logger.info(f"Sanctions DB: Ready ({count:,} entries, fresh)")
    except Exception as e:
        logger.warning(f"Sanctions DB initialization failed: {e}")
        logger.warning("KYP sanctions screening will fall back to live downloads")

    # Initialize Redis Rate Limiters (for distributed, multi-worker rate limiting)
    global _redis_rate_limiter, _redis_login_pair_limiter, _redis_login_ip_limiter
    if REDIS_URL:
        # General API rate limiter
        _redis_rate_limiter = RedisRateLimiter(
            redis_url=REDIS_URL,
            requests_per_window=RATE_LIMIT_REQUESTS,
            window_seconds=RATE_LIMIT_WINDOW,
        )
        if await _redis_rate_limiter.initialize():
            logger.info("Redis rate limiter enabled (distributed mode)")
        else:
            logger.warning("Redis rate limiter failed - using in-memory fallback")
            _redis_rate_limiter = None

        # Login brute force limiters (per-pair and per-IP aggregate)
        _redis_login_pair_limiter = RedisRateLimiter(
            redis_url=REDIS_URL,
            requests_per_window=LOGIN_MAX_ATTEMPTS,
            window_seconds=LOGIN_LOCKOUT_SECONDS,
            key_prefix="login_pair:",
        )
        _redis_login_ip_limiter = RedisRateLimiter(
            redis_url=REDIS_URL,
            requests_per_window=LOGIN_IP_MAX_ATTEMPTS,
            window_seconds=LOGIN_LOCKOUT_SECONDS,
            key_prefix="login_ip:",
        )
        pair_ok = await _redis_login_pair_limiter.initialize()
        ip_ok = await _redis_login_ip_limiter.initialize()
        if pair_ok and ip_ok:
            logger.info(
                f"Redis login rate limiting enabled "
                f"(pair:{LOGIN_MAX_ATTEMPTS}/{LOGIN_LOCKOUT_SECONDS}s, "
                f"ip:{LOGIN_IP_MAX_ATTEMPTS}/{LOGIN_LOCKOUT_SECONDS}s)"
            )
        else:
            logger.warning(
                "Redis login rate limiting failed - using in-memory fallback"
            )
            _redis_login_pair_limiter = None
            _redis_login_ip_limiter = None
    else:
        logger.warning(
            "REDIS_URL not configured - using in-memory rate limiting "
            "(WARNING: Not suitable for multi-worker deployments)"
        )

    # Initialize Agent Registry
    try:
        agent_registry = AgentRegistry()
        await agent_registry.initialize()
        logger.info(
            f"Agent registry initialized with {len(agent_registry.list_agents())} agents"
        )
    except Exception as e:
        logger.warning(f"Agent registry initialization failed: {e}")
        agent_registry = None

    # Initialize Customer Validation Service (Two-Tier KYP + SAP/ECC)
    # No simulator fallback — credit data must come from real SAP CPI
    try:
        kyp_reports_path = Path(__file__).parent.parent.parent.parent / "data"
        customer_validation_service = CustomerValidationService(
            ms5_client=ms5_client,
            kyp_reports_dir=str(kyp_reports_path),
            credit_control_area=os.getenv("SAP_MS5_CREDIT_CONTROL_AREA", "0111"),
            sales_org="1000",
        )
        if ms5_client and ms5_client._connected:
            customer_validation_service.set_connected(True)
            logger.info("Customer Validation Service initialized (real SAP CPI)")
        else:
            customer_validation_service.set_connected(False)
            logger.warning(
                "Customer Validation Service initialized but SAP CPI not connected — credit queries will return 'unavailable'"
            )
    except Exception as e:
        logger.warning(f"Customer validation service initialization failed: {e}")
        customer_validation_service = None

    # Start enhanced scheduler for competitor intelligence (all jobs)
    try:
        start_enhanced_scheduler()
        logger.info(
            "Competitor intelligence ENHANCED scheduler started "
            "(daily: refresh, newsroom, social | weekly: crawl, financials, digest)"
        )
    except Exception as e:
        logger.warning(f"Scheduler initialization failed: {e}")

    # Initialize Marine Sales Intelligence database
    marine_intel_db = None
    try:
        marine_intel_db = await initialize_marine_intel_db()
        logger.info("Marine sales intelligence database initialized")
    except Exception as e:
        logger.warning(f"Marine intelligence database initialization failed: {e}")
        logger.warning("Marine sales intelligence will be unavailable")

    # Start marine intelligence scheduler
    try:
        start_marine_scheduler()
        logger.info(
            "Marine intelligence scheduler started (daily research at 7 AM SGT)"
        )
    except Exception as e:
        logger.warning(f"Marine scheduler initialization failed: {e}")

    # Initialize scheduler watchdog for unified monitoring
    try:
        await initialize_watchdog()
        logger.info("Scheduler watchdog initialized - monitoring all background jobs")
    except Exception as e:
        logger.warning(f"Watchdog initialization failed: {e}")

    yield

    # Shutdown
    logger.info(f"Shutting down {config.app_name}")

    # Stop competitor intelligence scheduler
    try:
        stop_scheduler()
        logger.info("Competitor intelligence scheduler stopped")
    except Exception as e:
        logger.warning(f"Scheduler shutdown error: {e}")

    # Stop marine intelligence scheduler
    try:
        stop_marine_scheduler()
        logger.info("Marine intelligence scheduler stopped")
    except Exception as e:
        logger.warning(f"Marine scheduler shutdown error: {e}")

    # Close marine intelligence database
    if marine_intel_db:
        try:
            await marine_intel_db.close()
            logger.info("Marine intelligence database closed")
        except Exception as e:
            logger.warning(f"Marine database shutdown error: {e}")

    # Close session manager
    if session_manager:
        await session_manager.close()
        logger.info("Session manager closed")

    # Shutdown customer validation service (don't disconnect - shares ms5_client)
    if customer_validation_service:
        customer_validation_service.set_connected(False)
        logger.info("Customer validation service shutdown complete")

    # Shutdown agent registry
    if agent_registry:
        await agent_registry.shutdown()
        logger.info("Agent registry shutdown complete")

    # Close competitor intelligence database
    if competitor_db:
        try:
            await competitor_db.close()
            logger.info("Competitor intelligence database closed")
        except Exception as e:
            logger.warning(f"Database shutdown error: {e}")

    # Disconnect SAP clients
    if ms5_client and ms5_client._connected:
        await ms5_client.disconnect()
        logger.info("MS5 client disconnected")
    if cec_client and cec_client._connected:
        await cec_client.disconnect()
        logger.info("CEC client disconnected")
    if ipas_client and ipas_client._connected:
        await ipas_client.disconnect()
        logger.info("IPAS client disconnected")
    runtime = None


# Create FastAPI app
# In production, disable OpenAPI docs to prevent API surface disclosure
_is_production = config.environment == "production"
app = FastAPI(
    title=config.app_name,
    description=config.app_description,
    version=config.app_version,
    lifespan=lifespan,
    docs_url=None if _is_production else "/docs",
    redoc_url=None if _is_production else "/redoc",
    openapi_url=None if _is_production else "/openapi.json",
)

# Validate CORS origins - don't allow wildcard with credentials
_cors_origins = config.allowed_origins
if "*" in _cors_origins:
    logger.warning(
        "SECURITY WARNING: Wildcard (*) in CORS origins is not recommended for production. "
        "Set explicit origins in ALLOWED_ORIGINS environment variable."
    )
    # In production, don't allow wildcard - use default safe origins
    if config.environment == "production":
        _cors_origins = ["https://rr.kailash.ai"]
        logger.info(f"Production mode: CORS restricted to {_cors_origins}")

# Define allowed headers explicitly (security best practice)
# Never use ["*"] with allow_credentials=True
_allowed_headers = [
    "Accept",
    "Accept-Language",
    "Content-Language",
    "Content-Type",
    "Authorization",
    "X-API-Key",
    "X-Request-ID",
    "X-Correlation-ID",
]

# Add CORS middleware with validated origins and explicit headers
app.add_middleware(
    CORSMiddleware,
    allow_origins=_cors_origins,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
    allow_headers=_allowed_headers,
)


# =============================================================================
# Security Headers Middleware (Development Only)
# =============================================================================
# In production, nginx sets security headers. This middleware provides headers
# only in development where nginx is not present.
#
# IMPORTANT: Do NOT add security headers in production - nginx handles them.
# Adding headers here AND in nginx causes duplicate headers in responses.
# =============================================================================


@app.middleware("http")
async def security_headers_middleware(request: Request, call_next):
    """Add security headers in development mode only.

    In production, nginx is the authoritative source for security headers.
    This middleware only runs in development/testing where nginx is absent.

    Headers (development only):
    - X-Content-Type-Options: Prevents MIME type sniffing
    - X-Frame-Options: Prevents clickjacking
    - X-XSS-Protection: Enables XSS filter in older browsers
    - Referrer-Policy: Controls referrer information
    - Permissions-Policy: Restricts browser features

    Note: HSTS is never set by this middleware (requires HTTPS via nginx).
    """
    response = await call_next(request)

    # Only set security headers in development (nginx handles production)
    if config.environment != "production":
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["X-XSS-Protection"] = "1; mode=block"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        response.headers["Permissions-Policy"] = (
            "accelerometer=(), camera=(), geolocation=(), gyroscope=(), "
            "magnetometer=(), microphone=(), payment=(), usb=()"
        )

    return response


# =============================================================================
# OpenTelemetry Tracing Middleware
# =============================================================================


@app.middleware("http")
async def tracing_middleware(request: Request, call_next):
    """Add OpenTelemetry tracing to all requests.

    Creates a span for every HTTP request with method, path, and status code.
    Stores trace context in request.state for propagation to downstream services.
    """
    if not OTEL_ENABLED or not tracer:
        return await call_next(request)

    # Skip detailed tracing for health checks (but still trace if explicitly requested)
    if request.url.path in {"/health", "/metrics"}:
        return await call_next(request)

    # Create span for this request
    with tracer.start_as_current_span(
        f"{request.method} {request.url.path}",
        attributes={
            "http.method": request.method,
            "http.url": str(request.url),
            "http.route": request.url.path,
            "http.client_ip": request.client.host if request.client else "unknown",
        },
    ) as span:
        # Store trace context in request state for propagation
        try:
            from opentelemetry import trace as otel_trace

            request.state.trace_context = (
                otel_trace.get_current_span().get_span_context()
            )
        except Exception:
            pass

        try:
            response = await call_next(request)
            span.set_attribute("http.status_code", response.status_code)

            if response.status_code >= 400:
                span.set_attribute("error", True)

            return response

        except Exception as e:
            span.set_attribute("error", True)
            span.set_attribute("error.message", str(e))
            raise


# =============================================================================
# Rate Limiting Middleware
# =============================================================================


@app.middleware("http")
async def rate_limit_middleware(request: Request, call_next):
    """Apply rate limiting to all requests.

    Uses Redis for distributed rate limiting when available (multi-worker safe).
    Falls back to in-memory rate limiting if Redis unavailable.
    """
    path = request.url.path

    # Skip rate limiting for public/static endpoints
    if (
        path
        in {
            "/health",
            "/",
            "/login",
            "/api/v1/auth/me",
        }
        or path.startswith("/static")
        or path.startswith("/projdocs")
        or path.endswith(
            (".css", ".js", ".png", ".jpg", ".ico", ".svg", ".woff", ".woff2")
        )
    ):
        return await call_next(request)

    client_ip = _get_client_ip(request)

    # Use Redis rate limiter if available (distributed, multi-worker safe)
    if _redis_rate_limiter and _redis_rate_limiter.is_available:
        is_allowed = await _redis_rate_limiter.is_allowed(client_ip)
        if not is_allowed:
            remaining = await _redis_rate_limiter.get_remaining(client_ip)
            logger.warning(
                f"Rate limit exceeded for {client_ip} (Redis, remaining={remaining})"
            )
            return JSONResponse(
                status_code=429,
                content={
                    "detail": "Rate limit exceeded. Please try again later.",
                    "retry_after": RATE_LIMIT_WINDOW,
                    "limit": RATE_LIMIT_REQUESTS,
                    "remaining": remaining,
                },
                headers={
                    "Retry-After": str(RATE_LIMIT_WINDOW),
                    "X-RateLimit-Limit": str(RATE_LIMIT_REQUESTS),
                    "X-RateLimit-Remaining": str(remaining),
                },
            )
    else:
        # Fallback to in-memory rate limiting (single worker only)
        if not _check_rate_limit(client_ip):
            logger.warning(f"Rate limit exceeded for {client_ip} (in-memory)")
            return JSONResponse(
                status_code=429,
                content={
                    "detail": "Rate limit exceeded. Please try again later.",
                    "retry_after": RATE_LIMIT_WINDOW,
                },
                headers={"Retry-After": str(RATE_LIMIT_WINDOW)},
            )

    return await call_next(request)


# =============================================================================
# Authentication Middleware
# =============================================================================


async def _resolve_user_identity(
    request, jwt_token, session_token, auth_manager, session_manager
):
    """Resolve user identity from JWT or session token and set request.state.user.

    Called when API key auth succeeds but we still need user identity for
    session isolation and RBAC.
    """
    if jwt_token and auth_manager:
        payload = auth_manager.validate_jwt(jwt_token)
        if payload:
            if "user_id" not in payload and "sub" in payload:
                payload["user_id"] = payload["sub"]
            request.state.user = payload
            request.state.session_id = payload.get("session_id")
            return
    if session_token and session_manager and session_manager.is_available:
        session_data = await session_manager.validate_session(session_token)
        if session_data:
            request.state.user = session_data
            request.state.session_id = session_token
            return


@app.middleware("http")
async def auth_middleware(request: Request, call_next):
    """Session-based authentication middleware.

    Checks for valid session cookie on protected endpoints.
    Also supports X-API-Key header for programmatic access.
    Redirects to /login for browser requests, returns 401 for API requests.
    """
    path = request.url.path

    # Skip auth for public endpoints
    if (
        path in PUBLIC_ENDPOINTS
        or path.startswith("/static")
        or path.startswith("/projdocs")
    ):
        return await call_next(request)

    # Get session token from cookie
    session_token = request.cookies.get("session_token")
    jwt_token = request.cookies.get("jwt_token")

    # Get API key from header (for programmatic access)
    api_key_header = request.headers.get("X-API-Key")

    # Check if this is an API endpoint that requires auth
    is_api_request = path.startswith("/api/")
    needs_auth = path in AUTH_REQUIRED_ENDPOINTS or any(
        path.startswith(ep.rstrip("*")) for ep in AUTH_REQUIRED_ENDPOINTS if "*" in ep
    )

    # Allow API key authentication for API endpoints
    if is_api_request and api_key_header:
        # If API_KEY is not configured, allow any key (dev mode)
        if not API_KEY:
            # Still resolve user identity from session/JWT if available
            await _resolve_user_identity(
                request, jwt_token, session_token, auth_manager, session_manager
            )
            return await call_next(request)
        # Validate API key — constant-time check against all rotation keys
        key_matched = False
        for k in API_KEYS:
            if secrets.compare_digest(api_key_header, k):
                key_matched = True
        if key_matched:
            # Still resolve user identity from session/JWT if available
            await _resolve_user_identity(
                request, jwt_token, session_token, auth_manager, session_manager
            )
            return await call_next(request)
        # Invalid API key - continue to check session/JWT

    # For chat page, check session or JWT and redirect to login if not authenticated
    # Auth logic mirrors the API path (lines 1480-1520) to prevent redirect loops:
    # 1. Session-based auth (preferred when Redis is available)
    # 2. JWT auth with session revocation check (same as API path)
    if path == "/chat":
        user_data = None

        # Try session-based auth first (if Redis available)
        if session_token and session_manager and session_manager.is_available:
            session_data = await session_manager.validate_session(session_token)
            if session_data:
                user_data = session_data
                await session_manager.refresh_session(session_token)

        # Fallback to JWT auth (matches API auth path to prevent inconsistency)
        if user_data is None and jwt_token and auth_manager:
            jwt_payload = auth_manager.validate_jwt(jwt_token)
            if jwt_payload:
                if "user_id" not in jwt_payload and "sub" in jwt_payload:
                    jwt_payload["user_id"] = jwt_payload["sub"]
                # If session_token exists but was invalid, reject (user logged out)
                if session_token and session_manager and session_manager.is_available:
                    # Session was explicitly invalidated — don't accept JWT
                    logger.debug(
                        "Chat: JWT valid but session expired/revoked — rejecting"
                    )
                else:
                    # No session_token cookie or Redis unavailable — accept JWT
                    user_data = jwt_payload
                    logger.info(
                        "Chat: Using JWT auth (no session cookie or Redis unavailable)"
                    )

        # If no valid auth, redirect to login
        if user_data is None:
            response = JSONResponse(
                status_code=307,
                content={"redirect": "/login"},
                headers={"Location": "/login"},
            )
            # Clear invalid session cookie (but keep JWT if it might still be valid)
            response.delete_cookie("session_token", path="/")
            return response

        # Store user info in request state
        request.state.user = user_data
        request.state.session_id = session_token

    # For API endpoints, validate JWT or session
    elif is_api_request and needs_auth:
        if jwt_token and auth_manager:
            payload = auth_manager.validate_jwt(jwt_token)
            if payload:
                # Valid JWT - normalize user_id from JWT "sub" claim
                if "user_id" not in payload and "sub" in payload:
                    payload["user_id"] = payload["sub"]
                request.state.user = payload
                request.state.session_id = payload.get("session_id")

                # Validate session still exists (rejects logged-out JWTs)
                if session_token and session_manager and session_manager.is_available:
                    session_valid = await session_manager.validate_session(
                        session_token
                    )
                    if not session_valid:
                        return JSONResponse(
                            status_code=401,
                            content={"detail": "Session expired or logged out"},
                        )
                    await session_manager.refresh_session(session_token)
            else:
                return JSONResponse(
                    status_code=401,
                    content={"detail": "Invalid or expired token"},
                )
        elif session_token and session_manager and session_manager.is_available:
            session_data = await session_manager.validate_session(session_token)
            if session_data:
                request.state.user = session_data
                request.state.session_id = session_token
                await session_manager.refresh_session(session_token)
            else:
                return JSONResponse(
                    status_code=401,
                    content={"detail": "Invalid or expired session"},
                )
        else:
            # No auth credentials provided
            return JSONResponse(
                status_code=401,
                content={"detail": "Authentication required"},
            )

    return await call_next(request)


# =============================================================================
# Authentication Endpoints
# =============================================================================


@app.post("/api/v1/auth/login")
async def login(request: Request, body: LoginRequest):
    """Authenticate user and create session.

    Request body:
    {
        "username": "kianseng.tee",
        "password": "your_password"
    }

    Returns:
    {
        "success": true,
        "user": {
            "user_id": "kianseng.tee",
            "username": "kianseng.tee",
            "roles": ["admin", "sales_ops"],
            "full_name": "Kian Seng Tee"
        }
    }
    """
    if not auth_manager:
        raise HTTPException(
            status_code=503, detail="Authentication service unavailable"
        )

    # Login brute force protection — two layers:
    # 1. Per (IP, username) pair: prevents lockout DoS
    # 2. Per IP aggregate: caps total attempts across all usernames from one IP
    client_ip = _get_client_ip(request)
    login_key = f"{client_ip}:{body.username}"
    ip_key = f"ip:{client_ip}"

    # Check per-IP aggregate limit first (caps credential stuffing across usernames)
    ip_allowed, ip_remaining = await _check_login_rate_limit(ip_key)
    if not ip_allowed:
        logger.warning(f"Login blocked for IP {client_ip} — aggregate limit exceeded")
        raise HTTPException(
            status_code=429,
            detail=f"Too many failed login attempts. Try again in {ip_remaining} seconds.",
            headers={"Retry-After": str(ip_remaining)},
        )

    # Check per (IP, username) pair limit
    allowed, remaining = await _check_login_rate_limit(login_key)
    if not allowed:
        logger.warning(
            f"Login blocked for {client_ip} / {body.username} — too many failed attempts"
        )
        raise HTTPException(
            status_code=429,
            detail=f"Too many failed login attempts. Try again in {remaining} seconds.",
            headers={"Retry-After": str(remaining)},
        )

    # Authenticate user
    user = auth_manager.authenticate(body.username, body.password)
    if not user:
        await _record_failed_login(login_key)
        await _record_failed_login(ip_key)
        raise HTTPException(status_code=401, detail="Invalid username or password")

    # Successful login — clear pair tracking (keep IP aggregate for other pairs)
    await _clear_failed_logins(login_key)

    # Get device info for session
    device_info = {
        "user_agent": request.headers.get("user-agent", "unknown"),
        "ip": _get_client_ip(request),
    }

    # Create session with retry logic for transient Redis failures
    # If Redis is unavailable, attempt to reconnect before retrying
    session_id = None
    max_retries = 3
    retry_delay = 0.1  # Initial delay in seconds (exponential backoff)

    if session_manager:
        for attempt in range(max_retries):
            try:
                # If session manager is not available, attempt to reinitialize
                if not session_manager.is_available and attempt > 0:
                    logger.info(
                        f"Attempting Redis reconnection (attempt {attempt + 1})"
                    )
                    try:
                        await session_manager.initialize()
                    except Exception as init_err:
                        logger.warning(f"Redis reconnection failed: {init_err}")

                # Attempt session creation
                session_id = await session_manager.create_session(
                    user_id=user.user_id,
                    user_data={
                        "username": user.username,
                        "roles": user.roles,
                        "tenant_id": user.tenant_id,
                        "first_name": user.first_name,
                        "last_name": user.last_name,
                    },
                    device_info=device_info,
                )
                if session_id:
                    if attempt > 0:
                        logger.info(f"Session created on retry attempt {attempt + 1}")
                    break  # Success
                else:
                    # create_session returned None (Redis still unavailable)
                    if attempt < max_retries - 1:
                        logger.warning(
                            f"Session creation attempt {attempt + 1}/{max_retries} failed "
                            "(session store unavailable), will retry"
                        )
            except Exception as e:
                logger.warning(
                    f"Session creation attempt {attempt + 1}/{max_retries} failed: {e}"
                )

            if attempt < max_retries - 1:
                await asyncio.sleep(retry_delay)
                retry_delay *= 2  # Exponential backoff

    if not session_id:
        # In production with REQUIRE_SESSION_STORE=True, fail if session store unavailable
        # This ensures proper session revocation and security controls
        if config.environment == "production" and getattr(
            config, "require_session_store", True
        ):
            logger.error(
                f"Session manager unavailable in production after {max_retries} retries - login rejected. "
                "Set REQUIRE_SESSION_STORE=False to allow JWT-only auth (not recommended)."
            )
            raise HTTPException(
                status_code=503,
                detail="Authentication service temporarily unavailable. Please try again later.",
            )

        # Development/non-production: Generate fallback session ID for JWT-only auth
        session_id = f"sess_{uuid.uuid4().hex}"
        logger.warning(
            "Session manager unavailable - using JWT-only auth. "
            "Note: Session revocation will not work in this mode."
        )

    # Generate JWT token
    jwt_token = auth_manager.generate_jwt(user, session_id)

    # Create response
    response = JSONResponse(
        content={
            "success": True,
            "user": {
                "user_id": user.user_id,
                "username": user.username,
                "roles": user.roles,
                "full_name": user.full_name,
                "tenant_id": user.tenant_id,
            },
        }
    )

    # Set cookies
    # Session token - HttpOnly, secure in production
    is_production = config.environment == "production"
    response.set_cookie(
        key="session_token",
        value=session_id,
        httponly=True,
        secure=is_production,
        samesite="lax",
        max_age=config.session_timeout,
        path="/",  # Explicit path for proper cookie management
    )

    # JWT token - HttpOnly, secure in production
    response.set_cookie(
        key="jwt_token",
        value=jwt_token,
        httponly=True,
        secure=is_production,
        samesite="lax",
        max_age=auth_manager.jwt_expire_minutes * 60,
        path="/",  # Explicit path for proper cookie management
    )

    logger.info(f"User '{user.username}' logged in successfully")
    return response


@app.post("/api/v1/auth/logout")
async def logout(request: Request):
    """Logout user and destroy session.

    Returns:
    {
        "success": true,
        "message": "Logged out successfully"
    }
    """
    session_token = request.cookies.get("session_token")

    if session_token and session_manager and session_manager.is_available:
        await session_manager.destroy_session(session_token)
        logger.info(f"Session {session_token[:16]}... destroyed")

    response = JSONResponse(
        content={
            "success": True,
            "message": "Logged out successfully",
        }
    )

    # Clear cookies - must match path used when setting
    response.delete_cookie("session_token", path="/")
    response.delete_cookie("jwt_token", path="/")

    return response


async def get_current_user(request: Request) -> AuthUser:
    """Dependency function to get authenticated user as AuthUser object.

    Used by protected endpoints that need the user object.
    Raises 401 if not authenticated.
    """
    user_data = getattr(request.state, "user", None)
    if not user_data:
        raise HTTPException(status_code=401, detail="Not authenticated")

    return AuthUser(
        user_id=user_data.get("user_id", ""),
        username=user_data.get("username", ""),
        roles=user_data.get("roles", []),
        tenant_id=user_data.get("tenant_id", "default"),
        first_name=user_data.get("first_name", ""),
        last_name=user_data.get("last_name", ""),
    )


async def get_optional_user(request: Request) -> Optional[AuthUser]:
    """Returns user if session-authenticated, service user if API-key-only."""
    user_data = getattr(request.state, "user", None)
    if user_data:
        return AuthUser(
            user_id=user_data.get("user_id", ""),
            username=user_data.get("username", ""),
            roles=user_data.get("roles", []),
            tenant_id=user_data.get("tenant_id", "default"),
            first_name=user_data.get("first_name", ""),
            last_name=user_data.get("last_name", ""),
        )
    api_key = request.headers.get("X-API-Key")
    if api_key:
        return AuthUser(
            user_id="api_service",
            username="api_service",
            roles=["sales_ops", "financeops"],
            tenant_id="default",
            first_name="API",
            last_name="Service",
        )
    return None


@app.get("/api/v1/auth/me")
async def get_current_user_info(request: Request):
    """Get current authenticated user information.

    Returns:
    {
        "user": {
            "user_id": "kianseng.tee",
            "username": "kianseng.tee",
            "first_name": "Kian Seng",
            "last_name": "Tee",
            "full_name": "Kian Seng Tee",
            "roles": ["admin", "sales_ops"],
            "tenant_id": "default",
            "permissions": {...}
        }
    }
    """
    # Check for user in request state (set by middleware)
    user_data = getattr(request.state, "user", None)
    if not user_data:
        raise HTTPException(status_code=401, detail="Not authenticated")

    # Get permissions for user
    permissions = {}
    if auth_manager:
        # Create AuthUser from session data
        user = AuthUser(
            user_id=user_data.get("user_id", ""),
            username=user_data.get("username", ""),
            roles=user_data.get("roles", []),
            tenant_id=user_data.get("tenant_id", "default"),
        )
        permissions = auth_manager.get_user_permissions(user)

    # Build full name from first/last name
    first_name = user_data.get("first_name", "")
    last_name = user_data.get("last_name", "")
    full_name = f"{first_name} {last_name}".strip() or user_data.get("username", "")

    return {
        "user": {
            "user_id": user_data.get("user_id"),
            "username": user_data.get("username"),
            "first_name": first_name,
            "last_name": last_name,
            "full_name": full_name,
            "roles": user_data.get("roles", []),
            "tenant_id": user_data.get("tenant_id", "default"),
            "permissions": permissions,
        }
    }


# =============================================================================
# Chat Interface Route
# =============================================================================


@app.get("/login", response_class=HTMLResponse)
async def login_page():
    """Serve the login page."""
    login_file = FRONTEND_DIR / "login.html"
    if login_file.exists():
        return FileResponse(
            login_file,
            media_type="text/html",
            headers={"Cache-Control": "no-cache, no-store, must-revalidate"},
        )
    else:
        raise HTTPException(status_code=404, detail="Login page not found")


@app.get("/chat", response_class=HTMLResponse)
async def chat_page():
    """Serve the Sales Ops Agent chat interface."""
    chat_file = FRONTEND_DIR / "chat.html"
    if chat_file.exists():
        content = chat_file.read_text()
        return HTMLResponse(
            content=content,
            headers={
                "Cache-Control": "no-cache, no-store, must-revalidate",
                "Pragma": "no-cache",
                "Expires": "0",
            },
        )
    else:
        raise HTTPException(status_code=404, detail="Chat interface not found")


@app.get("/static/images/{image_name}")
async def serve_static_image(image_name: str):
    """Serve static images."""
    image_file = FRONTEND_DIR / "public" / "static" / "images" / image_name
    # Path traversal guard: resolve and verify containment
    base_dir = (FRONTEND_DIR / "public" / "static" / "images").resolve()
    resolved = image_file.resolve()
    if not str(resolved).startswith(str(base_dir) + "/") and resolved != base_dir:
        raise HTTPException(status_code=404, detail="Image not found")
    if image_file.exists():
        # Determine media type
        suffix = image_file.suffix.lower()
        media_types = {
            ".png": "image/png",
            ".jpg": "image/jpeg",
            ".jpeg": "image/jpeg",
            ".gif": "image/gif",
            ".svg": "image/svg+xml",
            ".webp": "image/webp",
        }
        media_type = media_types.get(suffix, "application/octet-stream")
        return FileResponse(
            image_file,
            media_type=media_type,
            headers={"Cache-Control": "public, max-age=86400"},  # Cache for 1 day
        )
    else:
        raise HTTPException(status_code=404, detail="Image not found")


# =============================================================================
# Documentation Endpoints
# =============================================================================


@app.get("/projdocs")
async def docs_index():
    """Redirect to documentation index."""
    return RedirectResponse(url="/projdocs/index.html")


@app.get("/projdocs/{path:path}")
async def serve_docs(path: str):
    """Serve project documentation (Sphinx-generated)."""
    if not path:
        path = "index.html"

    doc_file = DOCS_DIR / path
    # Path traversal guard: resolve and verify containment
    base_dir = DOCS_DIR.resolve()
    resolved = doc_file.resolve()
    if not str(resolved).startswith(str(base_dir) + "/") and resolved != base_dir:
        raise HTTPException(status_code=404, detail="Documentation page not found")
    if doc_file.exists() and doc_file.is_file():
        # Determine media type
        suffix = doc_file.suffix.lower()
        media_types = {
            ".html": "text/html",
            ".css": "text/css",
            ".js": "application/javascript",
            ".json": "application/json",
            ".png": "image/png",
            ".jpg": "image/jpeg",
            ".jpeg": "image/jpeg",
            ".gif": "image/gif",
            ".svg": "image/svg+xml",
            ".woff": "font/woff",
            ".woff2": "font/woff2",
            ".ttf": "font/ttf",
            ".eot": "application/vnd.ms-fontobject",
        }
        media_type = media_types.get(suffix, "application/octet-stream")
        return FileResponse(
            doc_file,
            media_type=media_type,
            headers={"Cache-Control": "public, max-age=3600"},  # Cache for 1 hour
        )
    else:
        raise HTTPException(status_code=404, detail="Documentation page not found")


# =============================================================================
# Health & Status Endpoints
# =============================================================================


@app.get("/")
async def root():
    """Root endpoint - redirect to login page."""
    return RedirectResponse(url="/login")


@app.get("/health")
async def health_check():
    """Health check endpoint for load balancers.

    Returns degraded status if SAP connectivity or session store is down,
    and attempts auto-recovery of failed connections.
    """
    status = "ok"
    checks = {}

    # Check session store (with timeout to avoid blocking ALB probes)
    if session_manager:
        if session_manager.is_available:
            checks["session_store"] = "connected"
        else:
            checks["session_store"] = "disconnected"
            status = "degraded"
            # Auto-recovery: attempt Redis reconnection with 2s timeout
            try:
                reconnected = await asyncio.wait_for(
                    session_manager.initialize(), timeout=2.0
                )
                if reconnected:
                    checks["session_store"] = "reconnected"
                    status = "ok"
                    logger.info("Health check auto-recovered Redis session store")
            except (asyncio.TimeoutError, Exception):
                pass

    # Check SAP CPI connectivity (local state check only — fast)
    if cpi_client:
        try:
            cpi_health = await cpi_client.health_check()
            cpi_ok = cpi_health.get("status") == "connected" or cpi_health.get(
                "connected", False
            )
            checks["sap_cpi"] = "connected" if cpi_ok else "disconnected"
            if not cpi_ok:
                status = "degraded"
        except Exception:
            checks["sap_cpi"] = "error"
            status = "degraded"

    return {
        "status": status,
        "version": config.app_version,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "message": "Service healthy" if status == "ok" else "Service degraded",
        "checks": checks,
    }


@app.get("/api/v1/status")
async def detailed_status(_api_key: Optional[str] = Depends(verify_api_key)):
    """Detailed system status including SAP connectivity."""
    # Get health status from each client
    cpi_health = await cpi_client.health_check() if cpi_client else {}
    ms5_health = await ms5_client.health_check() if ms5_client else {}
    cec_health = await cec_client.health_check() if cec_client else {}
    ipas_health = await ipas_client.health_check() if ipas_client else {}

    return {
        "service": config.app_name,
        "version": config.app_version,
        "environment": config.environment,
        "runtime": {
            "active": runtime is not None,
            "type": "AsyncLocalRuntime",
            "python_version": platform.python_version(),
        },
        "sap_integration": {
            "cpi": cpi_health,
            "ms5": ms5_health,
            "cec": cec_health,
            "ipas": ipas_health,
        },
        "kpi_targets": {
            "field_autofill": f"{config.kpi_field_autofill_target:.0%}",
            "first_time_right": f"{config.kpi_first_time_right_target:.0%}",
            "cycle_time_reduction": f"{config.kpi_cycle_time_reduction:.0%}",
            "billing_ready": f"{config.kpi_billing_ready_target:.0%}",
            "traceability": f"{config.kpi_traceability_target:.0%}",
        },
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }


@app.get("/metrics")
async def metrics(_api_key: Optional[str] = Depends(verify_api_key)):
    """Prometheus-compatible metrics endpoint (requires authentication)."""
    return {
        "app_info": {
            "name": config.app_name,
            "version": config.app_version,
            "environment": config.environment,
        },
        "runtime_info": {
            "runtime_active": runtime is not None,
            "python_version": platform.python_version(),
        },
        "sap_configured": config.is_sap_configured(),
    }


# =============================================================================
# Scheduler Watchdog Endpoints
# =============================================================================


@app.get("/api/v1/scheduler/health")
async def get_scheduler_health(_api_key: Optional[str] = Depends(verify_api_key)):
    """
    Get unified health status of all background job schedulers.

    Returns health information for:
    - Competitor Intelligence Scheduler
    - Marine Sales Intelligence Scheduler

    Includes job counts, health states, stale jobs, and recent failures.
    """
    try:
        watchdog = get_watchdog()
        health = await watchdog.get_health()

        return {
            "success": True,
            **health.to_dict(),
        }
    except Exception as e:
        logger.error(f"Failed to get scheduler health: {e}", exc_info=True)
        return {
            "success": False,
            "overall_health": "unknown",
            "error": str(e),
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }


@app.get("/api/v1/scheduler/jobs")
async def list_scheduler_jobs(_api_key: Optional[str] = Depends(verify_api_key)):
    """
    List all scheduled jobs and their status.

    Returns detailed information for each job including:
    - Next scheduled run time
    - Last run time and status
    - Run counts and failure rates
    - Health assessment
    """
    try:
        watchdog = get_watchdog()
        jobs = await watchdog.get_all_job_statuses()

        return {
            "success": True,
            "job_count": len(jobs),
            "jobs": [job.to_dict() for job in jobs],
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
    except Exception as e:
        logger.error(f"Failed to list scheduler jobs: {e}", exc_info=True)
        return {
            "success": False,
            "job_count": 0,
            "jobs": [],
            "error": str(e),
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }


@app.get("/api/v1/scheduler/history")
async def get_scheduler_history(
    scheduler: Optional[str] = None,
    job_type: Optional[str] = None,
    limit: int = 20,
    _api_key: Optional[str] = Depends(verify_api_key),
):
    """
    Get recent job execution history.

    Query Parameters:
        scheduler: Filter by scheduler ("competitor_intel" or "marine_intel")
        job_type: Filter by job type (e.g., "daily_refresh", "daily_research")
        limit: Maximum number of records (default: 20, max: 100)
    """
    try:
        from lead_to_cash.services.scheduler_watchdog import SchedulerType

        watchdog = get_watchdog()

        scheduler_type = None
        if scheduler:
            try:
                scheduler_type = SchedulerType(scheduler)
            except ValueError:
                return {
                    "success": False,
                    "error": f"Invalid scheduler: {scheduler}. Use 'competitor_intel' or 'marine_intel'",
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                }

        limit = min(max(1, limit), 100)
        history = await watchdog.get_job_history(scheduler_type, job_type, limit)

        return {
            "success": True,
            "count": len(history),
            "history": history,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
    except Exception as e:
        logger.error(f"Failed to get scheduler history: {e}", exc_info=True)
        return {
            "success": False,
            "count": 0,
            "history": [],
            "error": str(e),
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }


@app.post("/api/v1/scheduler/cleanup")
async def cleanup_stale_jobs(_api_key: Optional[str] = Depends(verify_api_key)):
    """
    Clean up stale jobs across all schedulers.

    Marks as failed any jobs that have been "running" for more than 60 minutes.
    This handles orphaned jobs from container restarts.
    """
    try:
        watchdog = get_watchdog()
        results = await watchdog.cleanup_stale_jobs()

        total = sum(results.values())
        return {
            "success": True,
            "jobs_cleaned": total,
            "by_scheduler": results,
            "message": (
                f"Cleaned up {total} stale job(s)"
                if total > 0
                else "No stale jobs found"
            ),
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
    except Exception as e:
        logger.error(f"Failed to cleanup stale jobs: {e}", exc_info=True)
        return {
            "success": False,
            "error": str(e),
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }


# =============================================================================
# Debug Endpoints (disabled in production)
# =============================================================================


@app.get("/api/v1/debug/cpi-config")
async def debug_cpi_config(
    user: AuthUser = Depends(get_current_user),
    _api_key: Optional[str] = Depends(verify_api_key),
):
    """Debug endpoint to check CPI configuration (admin only, non-production)."""
    if config.environment == "production":
        raise HTTPException(status_code=404, detail="Not found")
    if "admin" not in user.roles:
        raise HTTPException(status_code=403, detail="Admin access required")
    import os as env_os

    return {
        "config_loaded": {
            "client_id_set": bool(config.sap_cpi.client_id),
            "client_id_len": len(config.sap_cpi.client_id or ""),
            "client_secret_set": bool(config.sap_cpi.client_secret),
            "client_secret_len": len(config.sap_cpi.client_secret or ""),
            "token_url": config.sap_cpi.token_url,
            "dev_url": config.sap_cpi.dev_url,
            "qa_url": config.sap_cpi.qa_url,
            "prod_url": config.sap_cpi.prod_url,
            "environment": config.environment,
        },
        "env_vars_present": {
            "SAP_CPI_CLIENT_ID": bool(env_os.getenv("SAP_CPI_CLIENT_ID")),
            "SAP_CPI_CLIENT_SECRET": bool(env_os.getenv("SAP_CPI_CLIENT_SECRET")),
            "SAP_CPI_TOKEN_URL": bool(env_os.getenv("SAP_CPI_TOKEN_URL")),
            "SAP_CPI_DEV_URL": bool(env_os.getenv("SAP_CPI_DEV_URL")),
            "SAP_CPI_QA_URL": bool(env_os.getenv("SAP_CPI_QA_URL")),
            "SAP_CPI_PROD_URL": bool(env_os.getenv("SAP_CPI_PROD_URL")),
        },
        "is_sap_configured": config.is_sap_configured(),
        "cpi_client_type": type(cpi_client).__name__ if cpi_client else "None",
        "cpi_health": await cpi_client.health_check() if cpi_client else {},
    }


@app.get("/api/v1/debug/entity-registry")
async def debug_entity_registry(
    user: AuthUser = Depends(get_current_user),
    _api_key: Optional[str] = Depends(verify_api_key),
):
    """Debug endpoint to check entity registry database configuration (admin only, non-production)."""
    if config.environment == "production":
        raise HTTPException(status_code=404, detail="Not found")
    if "admin" not in user.roles:
        raise HTTPException(status_code=403, detail="Admin access required")
    import os as env_os
    import re

    import asyncpg

    db_url = env_os.getenv("ENTITY_REGISTRY_DATABASE_URL", "")
    main_db_url = env_os.getenv("DATABASE_URL", "")

    # Mask password in URL for display
    def mask_url(url):
        return re.sub(r"://([^:]+):([^@]+)@", r"://\1:***@", url) if url else ""

    result = {
        "entity_registry_url_set": bool(db_url),
        "entity_registry_url_masked": mask_url(db_url),
        "entity_registry_url_len": len(db_url),
        "main_db_url_set": bool(main_db_url),
        "main_db_url_masked": mask_url(main_db_url),
        "main_db_url_len": len(main_db_url),
        "postgres_password_len": len(env_os.getenv("POSTGRES_PASSWORD", "")),
    }

    # Test main database connection first
    try:
        conn = await asyncpg.connect(main_db_url)
        result["main_db_test"] = "SUCCESS"
        # List all databases to check if entity_registry exists
        rows = await conn.fetch(
            "SELECT datname FROM pg_database WHERE datname = 'entity_registry'"
        )
        result["entity_registry_db_exists"] = len(rows) > 0
        await conn.close()
    except Exception as e:
        result["main_db_test"] = "FAILED"
        result["main_db_error"] = str(e)

    # Try direct connection to entity_registry database
    try:
        conn = await asyncpg.connect(db_url)
        result["entity_registry_direct_test"] = "SUCCESS"
        await conn.close()
    except Exception as e:
        result["entity_registry_direct_test"] = "FAILED"
        result["entity_registry_direct_error"] = str(e)

    # Try via EntityResolutionService
    try:
        from lead_to_cash.services.entity_registry import EntityResolutionService

        entity_service = EntityResolutionService()
        await entity_service.initialize()
        result["entity_service_test"] = "SUCCESS"
        result["database_url_used"] = (
            mask_url(entity_service._db._database_url) if entity_service._db else ""
        )
    except Exception as e:
        result["entity_service_test"] = "FAILED"
        result["entity_service_error"] = str(e)
        result["error_type"] = type(e).__name__

    return result


@app.get("/api/v1/debug/cpi-kyp")
async def debug_cpi_kyp(
    customer_id: str,
    credit_control_area: str = "0111",
    user: AuthUser = Depends(get_current_user),
    _api_key: Optional[str] = Depends(verify_api_key),
):
    """Debug endpoint to test CPI KYP lookup directly with known customer ID (admin only, non-production)."""
    if config.environment == "production":
        raise HTTPException(status_code=404, detail="Not found")
    if "admin" not in user.roles:
        raise HTTPException(status_code=403, detail="Admin access required")
    if not ms5_client:
        return {"error": "MS5 client not initialized"}

    try:
        # Use the working KYP endpoint (Integrum/RequestTableData)
        result = await ms5_client.get_customer_with_credit(
            customer_id=customer_id,
            credit_control_area=credit_control_area,
        )
        # CustomerData has: name, customer_id, tax_number_1, address, credit
        credit = result.credit
        address = result.address or {}
        return {
            "success": True,
            "customer_id": customer_id,
            "cpi_client_type": type(cpi_client).__name__,
            "iflow": ms5_client.DEFAULT_KYP_IFLOW,
            "customer": {
                "name": result.name,
                "tax_number_1": result.tax_number_1,
                "country": address.get("country", ""),
                "city": address.get("city", ""),
            },
            "credit": (
                {
                    "credit_limit": credit.credit_limit if credit else 0,
                    "credit_exposure": credit.credit_exposure if credit else 0,
                    "available_credit": credit.available_credit if credit else 0,
                    "utilization_percent": credit.utilization_percent if credit else 0,
                }
                if credit
                else None
            ),
        }
    except Exception as e:
        logger.error(f"Debug CPI KYP error for {customer_id}: {e}", exc_info=True)
        return {
            "success": False,
            "customer_id": customer_id,
            "error": str(e),
            "error_type": type(e).__name__,
        }


@app.get("/api/v1/debug/cpi-search")
async def debug_cpi_search(
    name: str,
    max_results: int = 10,
    verbose: bool = False,
    user: AuthUser = Depends(get_current_user),
    _api_key: Optional[str] = Depends(verify_api_key),
):
    """Debug endpoint to test customer search by name (admin only, non-production)."""
    if config.environment == "production":
        raise HTTPException(status_code=404, detail="Not found")
    if "admin" not in user.roles:
        raise HTTPException(status_code=403, detail="Admin access required")
    if not ms5_client:
        return {"error": "MS5 client not initialized"}

    debug_info = {"steps": []} if verbose else None

    try:
        if verbose:
            # Verbose mode: show entity resolution steps
            from lead_to_cash.services.entity_registry import EntityResolutionService

            entity_service = EntityResolutionService()
            await entity_service.initialize()
            debug_info["steps"].append("EntityResolutionService initialized")

            # Resolve entity
            result = await entity_service.resolve(name, search_external=False)
            debug_info["steps"].append("Entity resolution complete")
            debug_info["exact_match"] = (
                result.exact_match.canonical_name if result.exact_match else None
            )
            debug_info["candidate_count"] = (
                len(result.candidates) if result.candidates else 0
            )
            debug_info["candidates"] = [
                {"name": c.canonical_name, "entity_id": c.entity_id, "uen": c.uen}
                for c in (result.candidates or [])[:5]
            ]

            # Check SAP mappings
            candidates = (
                [result.exact_match]
                if result.exact_match
                else (result.candidates or [])
            )
            for c in candidates[:3]:
                if c and c.entity_id:
                    sap_id = await entity_service.get_entity_for_system(
                        c.entity_id, "sap"
                    )
                    debug_info["steps"].append(
                        f"SAP mapping for {c.canonical_name} (entity_id={c.entity_id}): {sap_id}"
                    )

        results = await ms5_client.search_customers(
            name=name,
            max_results=max_results,
        )

        response = {
            "success": True,
            "query": name,
            "cpi_client_type": type(cpi_client).__name__,
            "result_count": len(results),
            "customers": [
                {
                    "customer_id": r.customer_id,
                    "name": r.name,
                    "tax_number_1": r.tax_number_1,
                    "country": r.country,
                    "city": r.city,
                }
                for r in results
            ],
        }
        if debug_info:
            response["debug"] = debug_info
        return response
    except Exception as e:
        logger.error(f"Debug CPI search error for '{name}': {e}", exc_info=True)
        return {
            "success": False,
            "query": name,
            "error": str(e),
            "error_type": type(e).__name__,
            "debug": debug_info,
        }


# =============================================================================
# Workflow Endpoints
# =============================================================================


@app.get("/api/v1/workflows")
async def list_workflows(_api_key: Optional[str] = Depends(verify_api_key)):
    """List available workflows."""
    return {
        "workflows": [
            {
                "name": "customer_validation",
                "description": "Validate customer data against SAP MS5",
                "endpoint": "/api/v1/workflows/customer_validation/execute",
                "agent": "Due Diligence",
            },
            {
                "name": "opportunity_retrieval",
                "description": "Retrieve opportunity from CEC",
                "endpoint": "/api/v1/workflows/opportunity_retrieval/execute",
                "agent": "Opportunity",
            },
            {
                "name": "order_simulation",
                "description": "Simulate sales order in SAP",
                "endpoint": "/api/v1/workflows/order_simulation/execute",
                "agent": "Financial Ops",
            },
        ]
    }


@app.post("/api/v1/workflows/{workflow_name}/execute")
async def execute_workflow(
    workflow_name: str,
    body: WorkflowExecuteRequest,
    _api_key: Optional[str] = Depends(verify_api_key),
):
    """Execute a workflow by name."""
    global runtime

    if runtime is None:
        raise HTTPException(status_code=500, detail="Runtime not initialized")

    try:
        # Route to appropriate workflow
        if workflow_name == "customer_validation":
            if not ms5_client or not ms5_client._connected:
                raise HTTPException(
                    status_code=503,
                    detail="SAP MS5 not configured. Set CPI credentials to enable customer validation.",
                )
            if not body.customer_id:
                raise HTTPException(status_code=400, detail="customer_id is required")
            customer = await ms5_client.get_customer(body.customer_id)
            return {
                "workflow": workflow_name,
                "status": "completed",
                "result": {
                    "customer_id": customer.customer_id,
                    "name": customer.name,
                    "address": customer.address,
                    "credit_limit": customer.credit_limit,
                    "payment_terms": customer.payment_terms,
                },
            }

        elif workflow_name == "opportunity_retrieval":
            if not cec_client or not cec_client._client:
                raise HTTPException(
                    status_code=503,
                    detail="SAP CEC not configured. Set SAP_CEC_URL and credentials to enable opportunity retrieval.",
                )
            if not body.opportunity_id:
                raise HTTPException(
                    status_code=400, detail="opportunity_id is required"
                )
            opportunity = await cec_client.get_opportunity(body.opportunity_id)
            return {
                "workflow": workflow_name,
                "status": "completed",
                "result": {
                    "opportunity_id": opportunity.opportunity_id,
                    "account_id": opportunity.account_id,
                    "account_name": opportunity.account_name,
                    "status": opportunity.status,
                    "expected_revenue": opportunity.expected_revenue,
                    "currency": opportunity.currency,
                    "sap_mapping": opportunity.to_sap_mapping(),
                },
            }

        elif workflow_name == "order_simulation":
            if not ms5_client or not ms5_client._connected:
                raise HTTPException(
                    status_code=503,
                    detail="SAP MS5 not configured. Set CPI credentials to enable order simulation.",
                )
            if not body.order_data:
                raise HTTPException(status_code=400, detail="order_data is required")
            simulation = await ms5_client.simulate_order(body.order_data)
            return {
                "workflow": workflow_name,
                "status": "completed",
                "result": {
                    "is_valid": simulation.is_valid,
                    "net_value": simulation.net_value,
                    "currency": simulation.currency,
                    "messages": simulation.messages,
                },
            }

        else:
            return {
                "workflow": workflow_name,
                "status": "not_implemented",
                "message": f"Workflow '{workflow_name}' is not implemented yet",
                "available_workflows": [
                    "customer_validation",
                    "opportunity_retrieval",
                    "order_simulation",
                ],
            }

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=_safe_error_response(e, f"executing workflow {workflow_name}"),
        )


# =============================================================================
# Agent Endpoints
# =============================================================================


@app.get("/api/v1/agents")
async def list_agents(_api_key: Optional[str] = Depends(verify_api_key)):
    """List available agents and their capabilities."""
    if not agent_registry:
        raise HTTPException(
            status_code=503,
            detail="Agent registry not initialized. Check server logs.",
        )

    agents = agent_registry.list_agents()
    capabilities = agent_registry.list_capabilities()

    return {
        "agents": agents,
        "capabilities": capabilities,
        "total_agents": len(agents),
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }


@app.post("/api/v1/chat")
async def chat(
    request: Request,
    body: ChatRequest,
    session_id: Optional[str] = None,
    _api_key: Optional[str] = Depends(verify_api_key),
):
    """Conversational chat endpoint with multi-turn support.

    Implements orchestration_guide.md Section 5: Conversation Management.

    This endpoint provides the FULL orchestration flow:
    1. Query Understanding - LLM-based intent classification
    2. Clarification Check - Block if clarification needed
    3. Data Inventory Check - Know what data is available
    4. Tool Selection - Plan tool execution
    5. Tool Execution - Execute tools with ReAct pattern
    6. Response + Follow-ups - Generate response with suggestions
    7. Data-layer RBAC - Filter response based on user permissions

    Architecture (Unified Semantic Routing):
    - All users use the SAME routing path (ConversationManager + ToolExecutor)
    - Agent selection is based on query CONTENT (semantic), not user role
    - RBAC controls DATA ACCESS, not conversation routing
    - Users can ask any question; permissions filter what data they see

    Headers:
        X-Session-ID: Optional session ID for conversation continuity

    Request body:
    {
        "message": "What contracts has Caterpillar won?",
        "clarification_response": {  // Optional, if responding to clarification
            "question_id": "time_period",
            "answer": "Last 3 months"
        }
    }

    Response (answer):
    {
        "session_id": "uuid",
        "type": "answer",
        "answer": "...",
        "sources": [...],
        "confidence": "HIGH",
        "data_coverage": {...},
        "follow_up_suggestions": [...],
        "timestamp": "2026-01-20T..."
    }

    Response (clarification needed):
    {
        "session_id": "uuid",
        "type": "clarification_needed",
        "questions": [
            {
                "id": "time_period",
                "question": "What time period?",
                "type": "choice",
                "options": [...]
            }
        ],
        "partial_understanding": {...}
    }
    """
    if not agent_registry:
        raise HTTPException(
            status_code=503,
            detail="Agent registry not initialized. Check server logs.",
        )

    # Get user roles from request state (set by auth middleware)
    user_data = getattr(request.state, "user", None)
    user_roles = user_data.get("roles", []) if user_data else []
    if not user_roles and request.headers.get("X-API-Key"):
        user_roles = ["sales_ops", "financeops"]

    # Get session ID from: body (preferred) > query param > header > new UUID
    session_header = request.headers.get("X-Session-ID")
    actual_session_id = (
        body.session_id or session_id or session_header or str(uuid.uuid4())
    )
    logger.debug(
        f"Chat session resolution: body.session_id={body.session_id}, "
        f"query_param={session_id}, header={session_header}, "
        f"actual={actual_session_id}"
    )

    # Get trace context from middleware if available
    trace_context = getattr(request.state, "trace_context", None)

    # Build user context for data-layer RBAC (NOT routing)
    # RBAC controls DATA ACCESS, not conversation routing
    # Any user can ask any question; permissions filter what data they see
    user_context = {
        "user_id": user_data.get("user_id", "") if user_data else "",
        "roles": user_roles,
        "permissions": _get_user_permissions(user_roles),
        "default_region": user_data.get("default_region", "") if user_data else "",
    }
    logger.debug(f"Chat user context: roles={user_roles}")

    # Helper function for unified semantic routing
    async def process_with_unified_routing():
        """
        Process chat request with unified semantic routing.

        Key principle: RBAC controls DATA ACCESS, not conversation routing.
        - Any user can ask any question (market intel, competitor, KYP, billing, etc.)
        - The best agent is selected based on query CONTENT, not user role
        - Data-layer RBAC filters WHAT DATA the user can see in the response
        - If user lacks permission for certain data, they get a graceful message
        """
        # Use unified registry.process() for ALL users
        # Pass user_context for data-layer RBAC enforcement
        return await agent_registry.process(
            request=body.message,
            session_id=actual_session_id,
            clarification_response=body.clarification_response,
            trace_context=trace_context,
            user_context=user_context,
            confirmed_entity=body.confirmed_entity,
            original_task_type=body.original_task_type,
        )

    # OpenTelemetry tracing for chat processing
    if OTEL_ENABLED and tracer:
        with tracer.start_as_current_span(
            "chat_process",
            attributes={
                "message.preview": body.message[:100],
                "message.length": len(body.message),
                "session.id": actual_session_id,
                "has_clarification_response": body.clarification_response is not None,
                "user.roles": ",".join(user_roles),
            },
        ) as span:
            try:
                # Use unified semantic routing (not role-based)
                result = await process_with_unified_routing()

                # Add result attributes to span
                span.set_attribute("response.type", result.get("type", "unknown"))
                if result.get("type") == "answer":
                    span.set_attribute(
                        "confidence", result.get("confidence", "unknown")
                    )

                # Ensure session_id is in response
                result["session_id"] = actual_session_id
                result["timestamp"] = datetime.now(timezone.utc).isoformat()

                return result

            except HTTPException:
                span.set_attribute("error", True)
                raise
            except Exception as e:
                span.set_attribute("error", True)
                span.set_attribute("error.message", str(e))
                logger.error(f"Chat processing failed: {e}", exc_info=True)
                # Return proper error format for frontend (not HTTPException)
                return {
                    "type": "error",
                    "session_id": actual_session_id,
                    "error": _safe_error_response(e, "processing chat message"),
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                }
    else:
        # Non-traced execution path
        try:
            # Use unified semantic routing (not role-based)
            result = await process_with_unified_routing()

            # Ensure session_id is in response
            result["session_id"] = actual_session_id
            result["timestamp"] = datetime.now(timezone.utc).isoformat()

            return result

        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Chat processing failed: {e}", exc_info=True)
            # Return proper error format for frontend (not HTTPException)
            return {
                "type": "error",
                "session_id": actual_session_id,
                "error": _safe_error_response(e, "processing chat message"),
                "timestamp": datetime.now(timezone.utc).isoformat(),
            }


@app.post("/api/v1/chat/stream")
async def chat_stream(
    request: Request,
    body: ChatRequest,
    session_id: Optional[str] = None,
    _api_key: Optional[str] = Depends(verify_api_key),
):
    """
    Streaming chat endpoint with Server-Sent Events (SSE).

    Returns a stream of events as the response is generated:
    - type=session: Session ID confirmation
    - type=status: Progress updates (understanding, gathering, synthesizing)
    - type=tools_complete: Data sources used and URLs collected
    - type=token: Individual response tokens (for streaming display)
    - type=done: Final metadata (confidence, follow-up suggestions)
    - type=error: Error if something goes wrong
    - type=clarification_needed: If clarification is required

    Headers:
        X-Session-ID: Optional session ID for conversation continuity

    Response format: Server-Sent Events (text/event-stream)
        data: {"type": "token", "content": "The "}
        data: {"type": "token", "content": "latest "}
        ...
        data: {"type": "done", "confidence": "HIGH", ...}
    """
    if not agent_registry:
        raise HTTPException(
            status_code=503,
            detail="Agent registry not initialized. Check server logs.",
        )

    # Get session ID from: body (preferred) > query param > header > new UUID
    session_header = request.headers.get("X-Session-ID")
    actual_session_id = (
        body.session_id or session_id or session_header or str(uuid.uuid4())
    )
    logger.debug(
        f"Chat stream session resolution: body.session_id={body.session_id}, "
        f"query_param={session_id}, header={session_header}, "
        f"actual={actual_session_id}"
    )

    # Get conversation manager from registry
    conversation_manager = agent_registry._conversation_manager
    if not conversation_manager:
        raise HTTPException(
            status_code=503,
            detail="Conversation manager not initialized.",
        )

    # Build user context for session ownership binding
    user_data = getattr(request.state, "user", None)
    user_roles = user_data.get("roles", []) if user_data else []
    if not user_roles and request.headers.get("X-API-Key"):
        user_roles = ["sales_ops", "financeops"]
    stream_user_context = {
        "user_id": user_data.get("user_id", "") if user_data else "",
        "roles": user_roles,
        "permissions": _get_user_permissions(user_roles),
    }

    async def event_generator():
        """
        Generate SSE events from streaming response.

        Handles client disconnection gracefully by checking request status
        and propagating CancelledError for proper cleanup.
        """
        generator = None
        try:
            generator = conversation_manager.process_message_streaming(
                session_id=actual_session_id,
                message=body.message,
                user_context=stream_user_context,
            )
            async for event in generator:
                # Check if client disconnected before yielding
                if await request.is_disconnected():
                    logger.info(
                        f"Client disconnected during streaming (session={actual_session_id})"
                    )
                    break

                # Format as SSE: data: {json}\n\n
                yield f"data: {json.dumps(event)}\n\n"

        except asyncio.CancelledError:
            # Client disconnected - this is expected, clean exit
            logger.info(f"Streaming cancelled for session {actual_session_id}")
            raise  # Re-raise to trigger cleanup

        except Exception as e:
            logger.error(f"Streaming error: {e}")
            # Only yield error if client is still connected
            if not await request.is_disconnected():
                error_event = {
                    "type": "error",
                    "error": _safe_error_response(e, "streaming chat"),
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                }
                yield f"data: {json.dumps(error_event)}\n\n"

        finally:
            # Cleanup: Close the generator if it exists
            if generator is not None:
                try:
                    await generator.aclose()
                except Exception:
                    pass  # Ignore cleanup errors

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",  # Disable nginx buffering
            "X-Session-ID": actual_session_id,  # Return session ID in response
        },
    )


@app.post("/api/v1/agents/due-diligence/validate")
async def validate_customer(
    body: CustomerValidationRequest,
    _api_key: Optional[str] = Depends(verify_api_key),
):
    """Validate customer using Due Diligence agent.

    Example request body:
    {
        "customer_id": "1234567",
        "order_value": 50000.0,
        "sales_org": "US01"  // optional
    }
    """
    if not agent_registry:
        raise HTTPException(
            status_code=503,
            detail="Agent registry not initialized. Check server logs.",
        )

    try:
        # Get Due Diligence agent from registry
        dd_agent = agent_registry.get_agent("due_diligence")
        if not dd_agent:
            raise HTTPException(
                status_code=503,
                detail="Due Diligence agent not available",
            )

        # Perform validation
        result = await dd_agent.validate_customer(
            customer_id=body.customer_id,
            order_value=body.order_value,
            sales_org=body.sales_org,
        )

        return {
            "status": "completed",
            "validation_result": result.to_dict(),
            "can_proceed": result.can_proceed,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
    except HTTPException:
        raise
    except RuntimeError as e:
        # SAP connection errors
        raise HTTPException(
            status_code=503,
            detail=_safe_error_response(e, "connecting to SAP system"),
        )
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=_safe_error_response(e, "validating customer"),
        )


# =============================================================================
# Customer Validation Endpoints (Two-Tier KYP + SAP/ECC)
# =============================================================================


@app.get("/api/v1/validation/customers")
async def list_validation_customers(_api_key: Optional[str] = Depends(verify_api_key)):
    """
    List available customers for validation.
    Returns customers from the CPI simulator for selection.
    """
    if not customer_validation_service:
        raise HTTPException(
            status_code=503,
            detail="Customer validation service not initialized",
        )

    try:
        customers = await customer_validation_service.list_customers()
        return {
            "success": True,
            "customers": customers,
            "count": len(customers),
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=_safe_error_response(e, "listing customers"),
        )


@app.post("/api/v1/validation/validate")
async def validate_customer_two_tier(
    body: TwoTierValidationRequest,
    _api_key: Optional[str] = Depends(verify_api_key),
):
    """
    Perform comprehensive two-tier customer validation.

    Combines:
    - Tier 1: KYP Compliance Assessment (external due diligence)
    - Tier 2: SAP/ECC Validation (transactional due diligence)

    Request body:
    {
        "customer": "BatamFast",  // Customer name or SAP ID
        "order_value": 50000.0    // Optional: order value for credit check
    }

    Response includes:
    - Overall status (APPROVED, CONDITIONAL, BLOCKED, PENDING)
    - Tier 1 KYP results (risk rating, compliance status)
    - Tier 2 SAP results (master data, credit, payment terms)
    - Combined issues and conditions
    """
    if not customer_validation_service:
        raise HTTPException(
            status_code=503,
            detail="Customer validation service not initialized",
        )

    try:
        result = await customer_validation_service.validate_customer(
            customer_identifier=body.customer,
            order_value=body.order_value,
        )

        return {
            "success": True,
            "validation": result.to_dict(),
            "summary": result.to_summary(),
            "can_proceed": result.can_proceed,
            "overall_status": result.overall_status.value,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=_safe_error_response(e, "validating customer"),
        )


@app.get("/api/v1/validation/kyp/{customer_name}")
async def get_kyp_assessment(
    customer_name: str,
    _api_key: Optional[str] = Depends(verify_api_key),
):
    """
    Get KYP compliance assessment for a customer (Tier 1 only).

    Path parameter:
        customer_name: Customer/partner name

    Returns KYP risk assessment including:
    - Risk rating (LOW, MEDIUM, MEDIUM-HIGH, HIGH)
    - Approval status
    - Issues and conditions
    """
    if not customer_validation_service:
        raise HTTPException(
            status_code=503,
            detail="Customer validation service not initialized",
        )

    try:
        from lead_to_cash.services import KYPProcessor

        processor = KYPProcessor()
        result = await processor.get_risk_assessment(customer_name)

        return {
            "success": True,
            "assessment": result.to_dict(),
            "summary": result.summary,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=_safe_error_response(e, "getting KYP assessment"),
        )


# =============================================================================
# Insights Endpoints (Perplexity-powered)
# =============================================================================


@app.get("/api/v1/insights/industry")
async def get_industry_news(_api_key: Optional[str] = Depends(verify_api_key)):
    """Get latest industry news for Marine, Offshore Oil & Gas, Marine Transportation."""
    try:
        insights = get_insights_service()
        result = await insights.get_industry_news()
        return {
            "success": True,
            "result": {
                "summary": result.content,
                "response": result.content,
                "sources": result.sources,
                "category": result.category,
            },
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=_safe_error_response(e, "getting industry news"),
        )


@app.get("/api/v1/insights/industry/structured")
async def get_structured_industry_news(
    format: str = "json",
    _api_key: Optional[str] = Depends(verify_api_key),
):
    """
    Get structured industry news with actionable sales opportunities.

    Returns properly formatted insights for the sales team with:
    - Specific company names and transaction details
    - Sales signals (NEWBUILD, RETROFIT, OFFSHORE_PROJECT, etc.)
    - Engine requirements and power specifications
    - Recommended sales actions

    Query Parameters:
        format: Response format - "json" (default) or "report" (sales-friendly text)

    Returns:
        Structured insights with opportunities for RRPS engine sales
    """
    try:
        insights = get_insights_service()
        result = await insights.get_structured_industry_news()

        if format == "report":
            # Return the formatted sales report as text
            return {
                "success": True,
                "format": "report",
                "report": result.get("sales_report", "No report available"),
                "insights_count": result.get("insights_count", 0),
                "high_priority_count": result.get("high_priority_count", 0),
                "timestamp": datetime.now(timezone.utc).isoformat(),
            }
        else:
            # Return full JSON structure
            return {
                "success": True,
                "format": "json",
                **result,
                "timestamp": datetime.now(timezone.utc).isoformat(),
            }
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=_safe_error_response(e, "getting structured industry news"),
        )


@app.get("/api/v1/insights/competitors")
async def get_competitor_updates(_api_key: Optional[str] = Depends(verify_api_key)):
    """Get latest updates on competitors: Caterpillar, Cummins, MAN."""
    try:
        insights = get_insights_service()
        result = await insights.get_competitor_updates()
        return {
            "success": True,
            "result": {
                "summary": result.content,
                "response": result.content,
                "sources": result.sources,
                "category": result.category,
            },
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=_safe_error_response(e, "getting competitor updates"),
        )


@app.post("/api/v1/insights/search")
async def search_insights(
    body: InsightsSearchRequest,
    _api_key: Optional[str] = Depends(verify_api_key),
):
    """Search for industry insights based on user query."""
    try:
        insights = get_insights_service()
        result = await insights.search_insights(body.query)
        return {
            "success": True,
            "result": {
                "summary": result.content,
                "response": result.content,
                "sources": result.sources,
                "category": result.category,
            },
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=_safe_error_response(e, "searching insights"),
        )


# =============================================================================
# Competitor Intelligence Endpoints
# =============================================================================


@app.post("/api/v1/competitor-intel/query")
async def query_competitor_intel(
    body: CompetitorQueryRequest,
    _api_key: Optional[str] = Depends(verify_api_key),
):
    """
    Query competitor intelligence using RAG.

    Request body:
    {
        "query": "What are Caterpillar's recent marine engine wins?",
        "competitor": "caterpillar"  // optional filter
    }
    """
    try:
        # Get competitor intel agent from registry
        if agent_registry:
            competitor_agent = agent_registry._agents.get("competitor_intel")
            if competitor_agent:
                result = await competitor_agent.agent.query(
                    body.query, competitor=body.competitor
                )
                return {
                    "success": True,
                    "result": result,
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                }

        # Fallback to insights service
        insights = get_insights_service()
        result = await insights.search_insights(body.query)
        return {
            "success": True,
            "result": {
                "answer": result.content,
                "sources": result.sources,
                "confidence": "medium",
            },
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=_safe_error_response(e, "querying competitor intelligence"),
        )


async def _run_competitor_refresh(job_id: str, competitor: str | None):
    """Background task to refresh competitor intelligence."""
    global _refresh_jobs

    try:
        _refresh_jobs[job_id]["status"] = "running"
        _refresh_jobs[job_id]["started_at"] = datetime.now(timezone.utc).isoformat()

        if agent_registry:
            competitor_agent = agent_registry._agents.get("competitor_intel")
            if competitor_agent:
                result = await competitor_agent.agent.refresh_data(competitor)
                _refresh_jobs[job_id]["status"] = "completed"
                _refresh_jobs[job_id]["result"] = result
                _refresh_jobs[job_id]["completed_at"] = datetime.now(
                    timezone.utc
                ).isoformat()
                logger.info(f"Competitor refresh job {job_id} completed")
                return

        _refresh_jobs[job_id]["status"] = "failed"
        _refresh_jobs[job_id]["error"] = "Competitor intelligence agent not available"
        _refresh_jobs[job_id]["completed_at"] = datetime.now(timezone.utc).isoformat()
    except Exception as e:
        _refresh_jobs[job_id]["status"] = "failed"
        _refresh_jobs[job_id]["error"] = _safe_job_error(
            e, "refreshing competitor data"
        )
        _refresh_jobs[job_id]["completed_at"] = datetime.now(timezone.utc).isoformat()


@app.post("/api/v1/competitor-intel/refresh")
async def refresh_competitor_intel(
    body: CompetitorRefreshRequest,
    background_tasks: BackgroundTasks,
    _api_key: Optional[str] = Depends(verify_api_key),
):
    """
    Trigger a refresh of competitor intelligence data.
    Runs in background to avoid timeout.

    Request body:
    {
        "competitor": "caterpillar"  // optional, refresh specific competitor
    }
    """
    try:
        if not agent_registry:
            raise HTTPException(
                status_code=503, detail="Agent registry not initialized"
            )

        competitor_agent = agent_registry._agents.get("competitor_intel")
        if not competitor_agent:
            raise HTTPException(
                status_code=503, detail="Competitor intelligence agent not available"
            )

        # Create job and run in background
        job_id = str(uuid.uuid4())[:8]
        _refresh_jobs[job_id] = {
            "job_id": job_id,
            "status": "queued",
            "competitor": body.competitor,
            "created_at": datetime.now(timezone.utc).isoformat(),
        }

        # Use asyncio.create_task for true background execution
        asyncio.create_task(_run_competitor_refresh(job_id, body.competitor))

        return {
            "success": True,
            "message": "Refresh started in background",
            "job_id": job_id,
            "check_status": f"/api/v1/competitor-intel/jobs/{job_id}",
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=_safe_error_response(e, "refreshing competitor intelligence"),
        )


@app.get("/api/v1/competitor-intel/jobs/{job_id}")
async def get_refresh_job_status(
    job_id: str,
    _api_key: Optional[str] = Depends(verify_api_key),
):
    """Get status of a competitor intelligence refresh job."""
    # Cleanup old jobs periodically
    _cleanup_old_jobs()

    if job_id not in _refresh_jobs:
        raise HTTPException(status_code=404, detail="Job not found")

    return {
        "success": True,
        "job": _refresh_jobs[job_id],
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }


@app.get("/api/v1/competitor-intel/status")
async def get_competitor_intel_status(
    _api_key: Optional[str] = Depends(verify_api_key),
):
    """Get status of competitor intelligence system."""
    try:
        if agent_registry:
            competitor_agent = agent_registry._agents.get("competitor_intel")
            if competitor_agent:
                stats = await competitor_agent.agent.get_stats()
                health = await competitor_agent.agent.health_check()
                return {
                    "success": True,
                    "status": "operational",
                    "stats": stats,
                    "health": health,
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                }

        return {
            "success": True,
            "status": "not_initialized",
            "stats": {},
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=_safe_error_response(e, "getting competitor intel status"),
        )


# =============================================================================
# Marine Sales Intelligence Endpoints
# =============================================================================


@app.get("/api/v1/marine-intel/opportunities")
async def get_marine_opportunities(
    region: Optional[str] = None,
    sector: Optional[str] = None,
    signal_type: Optional[str] = None,
    min_priority: int = 1,
    limit: int = 50,
    _api_key: Optional[str] = Depends(verify_api_key),
):
    """
    Get marine sales opportunities from the intelligence database.

    Query Parameters:
        region: Filter by region (singapore, indonesia, malaysia, etc.)
        sector: Filter by sector (marine_transportation, offshore_oil_gas, etc.)
        signal_type: Filter by sales signal (newbuild, retrofit_repower, etc.)
        min_priority: Minimum priority score (1-10)
        limit: Maximum number of results (default 50)
    """
    try:
        from lead_to_cash.services.marine_intel import get_marine_intel_db

        db = get_marine_intel_db()

        # Get opportunities from database
        opportunities = await db.list_opportunities(
            region=region,
            sector=sector,
            sales_signal=signal_type,
            min_priority=min_priority,
            limit=limit,
        )

        return {
            "success": True,
            "opportunities": [opp.to_dict() for opp in opportunities],
            "count": len(opportunities),
            "filters": {
                "region": region,
                "sector": sector,
                "signal_type": signal_type,
                "min_priority": min_priority,
            },
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=_safe_error_response(e, "getting marine opportunities"),
        )


@app.get("/api/v1/marine-intel/accounts")
async def get_marine_accounts(
    sector: Optional[str] = None,
    limit: int = 50,
    sort_by: str = "opportunity_count",
    _api_key: Optional[str] = Depends(verify_api_key),
):
    """
    Get tracked marine accounts (companies) with opportunity counts.

    Query Parameters:
        sector: Filter by sector
        limit: Maximum number of results
        sort_by: Sort field (opportunity_count, mention_count, total_score)
    """
    try:
        from lead_to_cash.services.marine_intel import get_marine_intel_db

        db = get_marine_intel_db()
        # Map sort_by to the 'by' parameter expected by get_top_accounts
        by_map = {
            "opportunity_count": "opportunities",
            "mention_count": "mentions",
            "total_score": "score",
        }
        by_value = by_map.get(sort_by, "score")
        accounts = await db.get_top_accounts(
            limit=limit if not sector else limit * 2,  # Fetch more if filtering
            by=by_value,
        )

        # Apply sector filter if specified
        if sector:
            accounts = [
                acc
                for acc in accounts
                if acc.sector and sector.lower() in acc.sector.lower()
            ][:limit]

        return {
            "success": True,
            "accounts": [acc.to_dict() for acc in accounts],
            "count": len(accounts),
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=_safe_error_response(e, "getting marine accounts"),
        )


@app.get("/api/v1/marine-intel/articles")
async def get_marine_articles(
    source: Optional[str] = None,
    processed: Optional[bool] = None,
    limit: int = 50,
    _api_key: Optional[str] = Depends(verify_api_key),
):
    """
    Get source articles from marine intelligence research.

    Query Parameters:
        source: Filter by source name
        processed: Filter by processing status
        limit: Maximum number of results
    """
    try:
        from lead_to_cash.services.marine_intel import get_marine_intel_db

        db = get_marine_intel_db()
        articles = await db.list_articles(
            source=source,
            is_processed=processed,
            limit=limit,
        )

        return {
            "success": True,
            "articles": [art.to_dict() for art in articles],
            "count": len(articles),
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=_safe_error_response(e, "getting marine articles"),
        )


@app.post("/api/v1/marine-intel/research")
async def trigger_marine_research(
    body: MarineResearchRequest,
    background_tasks: BackgroundTasks,
    _api_key: Optional[str] = Depends(verify_api_key),
):
    """
    Trigger manual marine intelligence research.

    Request body (all optional):
    {
        "region": "singapore",       // Target specific region
        "sector": "offshore_oil_gas", // Target specific sector
        "category": "newbuild"        // Target specific research category
    }

    If no filters provided, runs full daily research.
    """
    try:
        # Generate job ID (consistent 8-char format)
        job_id = str(uuid.uuid4())[:8]

        # Determine research type
        if body.region or body.sector or body.category:
            research_type = "targeted"
        else:
            research_type = "full"

        # Initialize job entry BEFORE starting background task
        _refresh_jobs[job_id] = {
            "job_id": job_id,
            "status": "queued",
            "research_type": research_type,
            "filters": {
                "region": body.region,
                "sector": body.sector,
                "category": body.category,
            },
            "created_at": datetime.now(timezone.utc).isoformat(),
        }

        # Run in background
        if research_type == "targeted":
            background_tasks.add_task(
                _run_targeted_marine_research,
                job_id,
                body.region,
                body.sector,
                body.category,
            )
        else:
            background_tasks.add_task(_run_full_marine_research, job_id)

        return {
            "success": True,
            "job_id": job_id,
            "research_type": research_type,
            "check_status": f"/api/v1/competitor-intel/jobs/{job_id}",
            "filters": {
                "region": body.region,
                "sector": body.sector,
                "category": body.category,
            },
            "message": "Research job started in background",
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=_safe_error_response(e, "triggering marine research"),
        )


async def _run_full_marine_research(job_id: str):
    """Background task to run full marine research."""
    try:
        # Update status to running
        if job_id in _refresh_jobs:
            _refresh_jobs[job_id]["status"] = "running"
            _refresh_jobs[job_id]["started_at"] = datetime.now(timezone.utc).isoformat()

        result = await run_marine_research()

        # Update with completion
        if job_id in _refresh_jobs:
            _refresh_jobs[job_id]["status"] = "completed"
            _refresh_jobs[job_id]["result"] = result
            _refresh_jobs[job_id]["completed_at"] = datetime.now(
                timezone.utc
            ).isoformat()
        else:
            _refresh_jobs[job_id] = {
                "status": "completed",
                "result": result,
                "completed_at": datetime.now(timezone.utc).isoformat(),
            }
    except Exception as e:
        if job_id in _refresh_jobs:
            _refresh_jobs[job_id]["status"] = "failed"
            _refresh_jobs[job_id]["error"] = _safe_job_error(
                e, "running marine research"
            )
            _refresh_jobs[job_id]["completed_at"] = datetime.now(
                timezone.utc
            ).isoformat()
        else:
            _refresh_jobs[job_id] = {
                "status": "failed",
                "error": _safe_job_error(e, "running marine research"),
                "completed_at": datetime.now(timezone.utc).isoformat(),
            }


async def _run_targeted_marine_research(
    job_id: str,
    region: Optional[str] = None,
    sector: Optional[str] = None,
    category: Optional[str] = None,
):
    """Background task to run targeted marine research."""
    try:
        # Update status to running
        if job_id in _refresh_jobs:
            _refresh_jobs[job_id]["status"] = "running"
            _refresh_jobs[job_id]["started_at"] = datetime.now(timezone.utc).isoformat()

        result = await run_manual_targeted_research(
            region=region,
            sector=sector,
            category=category,
        )

        # Update with completion
        if job_id in _refresh_jobs:
            _refresh_jobs[job_id]["status"] = "completed"
            _refresh_jobs[job_id]["result"] = result
            _refresh_jobs[job_id]["completed_at"] = datetime.now(
                timezone.utc
            ).isoformat()
        else:
            _refresh_jobs[job_id] = {
                "status": "completed",
                "result": result,
                "completed_at": datetime.now(timezone.utc).isoformat(),
            }
    except Exception as e:
        if job_id in _refresh_jobs:
            _refresh_jobs[job_id]["status"] = "failed"
            _refresh_jobs[job_id]["error"] = _safe_job_error(
                e, "running targeted marine research"
            )
            _refresh_jobs[job_id]["completed_at"] = datetime.now(
                timezone.utc
            ).isoformat()
        else:
            _refresh_jobs[job_id] = {
                "status": "failed",
                "error": _safe_job_error(e, "running targeted marine research"),
                "completed_at": datetime.now(timezone.utc).isoformat(),
            }


class HistoricalBackfillRequest(BaseModel):
    """Request body for historical backfill."""

    years: list[int] | None = Field(
        default=None,
        description="Years to backfill (default: [2023, 2024, 2025])",
    )
    categories: list[str] | None = Field(
        default=None,
        description="KB categories to query (default: all)",
    )
    region: str = Field(
        default="Asia Pacific Singapore",
        description="Geographic focus for queries",
    )


@app.post("/api/v1/marine-intel/backfill")
async def trigger_historical_backfill(
    body: HistoricalBackfillRequest,
    background_tasks: BackgroundTasks,
    _api_key: Optional[str] = Depends(verify_api_key),
):
    """
    Trigger historical backfill for past years using KB-aware queries.

    This searches news archives based on:
    - RRPS products (MTU Series 2000, 4000, 4000 Gas, 8000)
    - Competitor products (Cummins QSK, Cat 3500, MAN, Volvo Penta, Yanmar)
    - Target industries (ferry, offshore, workboat, patrol, yacht)

    Request body (all optional):
    {
        "years": [2023, 2024, 2025],  // Years to backfill
        "categories": ["mtu_series_4000", "cummins_qsk"],  // Specific KB categories
        "region": "Asia Pacific Singapore"  // Geographic focus
    }

    Available categories:
    - mtu_series_2000, mtu_series_4000, mtu_series_4000_gas, mtu_series_8000
    - cummins_qsk, caterpillar_3500, man_engines, volvo_penta, yanmar
    - ferry_passenger, offshore_osv, workboat_tug, patrol_defense, yacht_luxury
    """
    try:
        job_id = f"backfill_{uuid.uuid4().hex[:8]}"

        # Initialize job entry
        _refresh_jobs[job_id] = {
            "job_id": job_id,
            "status": "queued",
            "research_type": "historical_backfill",
            "config": {
                "years": body.years or [2023, 2024, 2025],
                "categories": body.categories or "all",
                "region": body.region,
            },
            "created_at": datetime.now(timezone.utc).isoformat(),
        }

        # Run in background
        background_tasks.add_task(
            _run_historical_backfill,
            job_id,
            body.years,
            body.categories,
            body.region,
        )

        return {
            "success": True,
            "job_id": job_id,
            "check_status": f"/api/v1/competitor-intel/jobs/{job_id}",
            "config": {
                "years": body.years or [2023, 2024, 2025],
                "categories": body.categories or "all",
                "region": body.region,
            },
            "message": "Historical backfill job started in background",
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=_safe_error_response(e, "triggering historical backfill"),
        )


async def _run_historical_backfill(
    job_id: str,
    years: list[int] | None = None,
    categories: list[str] | None = None,
    region: str = "Asia Pacific Singapore",
):
    """Background task to run historical backfill."""
    try:
        # Update status to running
        if job_id in _refresh_jobs:
            _refresh_jobs[job_id]["status"] = "running"
            _refresh_jobs[job_id]["started_at"] = datetime.now(timezone.utc).isoformat()

        result = await run_historical_backfill(
            years=years,
            categories=categories,
            region=region,
        )

        # Update with completion
        if job_id in _refresh_jobs:
            _refresh_jobs[job_id]["status"] = "completed"
            _refresh_jobs[job_id]["result"] = result
            _refresh_jobs[job_id]["completed_at"] = datetime.now(
                timezone.utc
            ).isoformat()
        else:
            _refresh_jobs[job_id] = {
                "status": "completed",
                "result": result,
                "completed_at": datetime.now(timezone.utc).isoformat(),
            }
    except Exception as e:
        if job_id in _refresh_jobs:
            _refresh_jobs[job_id]["status"] = "failed"
            _refresh_jobs[job_id]["error"] = _safe_job_error(
                e, "running historical backfill"
            )
            _refresh_jobs[job_id]["completed_at"] = datetime.now(
                timezone.utc
            ).isoformat()
        else:
            _refresh_jobs[job_id] = {
                "status": "failed",
                "error": _safe_job_error(e, "running historical backfill"),
                "completed_at": datetime.now(timezone.utc).isoformat(),
            }


@app.get("/api/v1/marine-intel/status")
async def get_marine_intel_status(_api_key: Optional[str] = Depends(verify_api_key)):
    """Get status of marine sales intelligence system."""
    try:
        from lead_to_cash.services.marine_intel import get_marine_intel_db

        db = get_marine_intel_db()
        stats = await db.get_stats()
        latest_job = await db.get_latest_job()

        return {
            "success": True,
            "status": "operational",
            "stats": stats,
            "latest_job": latest_job.to_dict() if latest_job else None,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
    except Exception as e:
        # Log the actual error for debugging
        logger.error(f"Marine intel status error: {type(e).__name__}: {str(e)}")
        # Return a degraded status response (not an error) since this is a status endpoint
        return {
            "success": False,
            "status": "not_initialized",
            "stats": {},
            "message": (
                "Marine intelligence database not available"
                if config.environment == "production"
                else str(e)
            ),
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }


@app.post("/api/v1/marine-intel/jobs/cleanup")
async def cleanup_stale_marine_jobs(_api_key: Optional[str] = Depends(verify_api_key)):
    """
    Clean up stale marine intel jobs.

    Marks as failed any jobs that have been "running" for more than 10 minutes
    with no progress (queries_executed = 0). This handles orphaned jobs from
    container restarts.
    """
    try:
        from lead_to_cash.services.marine_intel import get_marine_intel_db

        db = get_marine_intel_db()
        count = await db.cleanup_stale_jobs(stale_minutes=10)

        return {
            "success": True,
            "jobs_cleaned": count,
            "message": (
                f"Cleaned up {count} stale job(s)"
                if count > 0
                else "No stale jobs found"
            ),
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
    except Exception as e:
        logger.error(f"Stale job cleanup error: {type(e).__name__}: {e}")
        raise HTTPException(
            status_code=500,
            detail=_safe_error_response(e, "cleaning up stale jobs"),
        )


# =============================================================================
# Marine Intel Semantic Search Endpoints
# =============================================================================


class SemanticSearchRequest(BaseModel):
    """Request model for semantic search."""

    query: str = Field(..., description="Natural language search query")
    top_k: int = Field(default=10, description="Maximum number of results")
    min_similarity: float = Field(
        default=0.6, description="Minimum similarity threshold (0-1)"
    )


class SimilarArticlesRequest(BaseModel):
    """Request model for similar articles search."""

    article_id: str = Field(..., description="Source article ID")
    top_k: int = Field(default=5, description="Maximum number of similar articles")
    min_similarity: float = Field(
        default=0.7, description="Minimum similarity threshold"
    )


@app.post("/api/v1/marine-intel/search")
async def semantic_search_marine_articles(
    body: SemanticSearchRequest,
    _api_key: Optional[str] = Depends(verify_api_key),
):
    """
    Semantic search across marine intelligence articles.

    Uses OpenAI embeddings and pgvector for similarity search.

    Request body:
    {
        "query": "methanol-powered ferries in Southeast Asia",
        "top_k": 10,
        "min_similarity": 0.6
    }

    Returns articles ranked by semantic similarity.
    """
    try:
        from lead_to_cash.services.marine_intel.embedding_service import (
            get_marine_embedding_service,
        )

        service = get_marine_embedding_service()
        results = await service.search_articles(
            query=body.query,
            top_k=body.top_k,
            min_similarity=body.min_similarity,
        )

        return {
            "success": True,
            "query": body.query,
            "results": [
                {
                    **article.to_dict(),
                    "similarity": round(similarity, 3),
                }
                for article, similarity in results
            ],
            "count": len(results),
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=_safe_error_response(e, "semantic search"),
        )


@app.post("/api/v1/marine-intel/similar")
async def get_similar_marine_articles(
    body: SimilarArticlesRequest,
    _api_key: Optional[str] = Depends(verify_api_key),
):
    """
    Find articles similar to a given article.

    Request body:
    {
        "article_id": "uuid-of-article",
        "top_k": 5,
        "min_similarity": 0.7
    }

    Returns similar articles ranked by similarity.
    """
    try:
        from lead_to_cash.services.marine_intel.embedding_service import (
            get_marine_embedding_service,
        )

        service = get_marine_embedding_service()
        results = await service.find_similar_articles(
            article_id=body.article_id,
            top_k=body.top_k,
            min_similarity=body.min_similarity,
        )

        return {
            "success": True,
            "source_article_id": body.article_id,
            "similar_articles": [
                {
                    **article.to_dict(),
                    "similarity": round(similarity, 3),
                }
                for article, similarity in results
            ],
            "count": len(results),
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=_safe_error_response(e, "finding similar articles"),
        )


@app.get("/api/v1/marine-intel/embeddings/stats")
async def get_marine_embedding_stats(
    _api_key: Optional[str] = Depends(verify_api_key),
):
    """Get embedding statistics for marine intelligence."""
    try:
        from lead_to_cash.services.marine_intel import get_marine_intel_db

        db = get_marine_intel_db()
        stats = await db.get_embedding_stats()

        return {
            "success": True,
            "stats": stats,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=_safe_error_response(e, "getting embedding stats"),
        )


class EmbeddingBackfillRequest(BaseModel):
    """Request model for embedding backfill."""

    batch_size: int = Field(default=50, description="Articles per batch")
    max_articles: int = Field(default=500, description="Maximum articles to process")


@app.post("/api/v1/marine-intel/embeddings/backfill")
async def trigger_embedding_backfill(
    body: EmbeddingBackfillRequest,
    background_tasks: BackgroundTasks,
    _api_key: Optional[str] = Depends(verify_api_key),
):
    """
    Trigger embedding backfill for articles without embeddings.

    Request body:
    {
        "batch_size": 50,
        "max_articles": 500
    }

    Runs in background. Check status via job endpoint.
    """
    try:
        job_id = str(uuid.uuid4())[:8]

        _refresh_jobs[job_id] = {
            "job_id": job_id,
            "status": "queued",
            "job_type": "embedding_backfill",
            "params": {
                "batch_size": body.batch_size,
                "max_articles": body.max_articles,
            },
            "created_at": datetime.now(timezone.utc).isoformat(),
        }

        async def run_backfill():
            try:
                _refresh_jobs[job_id]["status"] = "running"
                _refresh_jobs[job_id]["started_at"] = datetime.now(
                    timezone.utc
                ).isoformat()

                from lead_to_cash.services.marine_intel.scheduler import (
                    run_manual_embedding_backfill,
                )

                result = await run_manual_embedding_backfill(
                    batch_size=body.batch_size,
                    max_articles=body.max_articles,
                )

                _refresh_jobs[job_id]["status"] = "completed"
                _refresh_jobs[job_id]["result"] = result
                _refresh_jobs[job_id]["completed_at"] = datetime.now(
                    timezone.utc
                ).isoformat()
            except Exception as e:
                _refresh_jobs[job_id]["status"] = "failed"
                _refresh_jobs[job_id]["error"] = str(e)
                _refresh_jobs[job_id]["completed_at"] = datetime.now(
                    timezone.utc
                ).isoformat()

        background_tasks.add_task(run_backfill)

        return {
            "success": True,
            "job_id": job_id,
            "message": "Embedding backfill started in background",
            "check_status": f"/api/v1/competitor-intel/jobs/{job_id}",
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=_safe_error_response(e, "triggering embedding backfill"),
        )


@app.post("/api/v1/marine-intel/retention/cleanup")
async def trigger_retention_cleanup(
    background_tasks: BackgroundTasks,
    _api_key: Optional[str] = Depends(verify_api_key),
):
    """
    Trigger manual retention cleanup job.

    Transitions articles between retention tiers:
    - Hot → Warm (>12 months): Remove content, keep summary
    - Warm → Cold (>24 months): Minimize metadata
    - Cold → Delete (>36 months): Remove from database

    Embeddings are preserved across all tiers.
    """
    try:
        job_id = str(uuid.uuid4())[:8]

        _refresh_jobs[job_id] = {
            "job_id": job_id,
            "status": "queued",
            "job_type": "retention_cleanup",
            "created_at": datetime.now(timezone.utc).isoformat(),
        }

        async def run_cleanup():
            try:
                _refresh_jobs[job_id]["status"] = "running"
                _refresh_jobs[job_id]["started_at"] = datetime.now(
                    timezone.utc
                ).isoformat()

                from lead_to_cash.services.marine_intel.scheduler import (
                    run_manual_retention_cleanup,
                )

                result = await run_manual_retention_cleanup()

                _refresh_jobs[job_id]["status"] = "completed"
                _refresh_jobs[job_id]["result"] = result
                _refresh_jobs[job_id]["completed_at"] = datetime.now(
                    timezone.utc
                ).isoformat()
            except Exception as e:
                _refresh_jobs[job_id]["status"] = "failed"
                _refresh_jobs[job_id]["error"] = str(e)
                _refresh_jobs[job_id]["completed_at"] = datetime.now(
                    timezone.utc
                ).isoformat()

        background_tasks.add_task(run_cleanup)

        return {
            "success": True,
            "job_id": job_id,
            "message": "Retention cleanup started in background",
            "check_status": f"/api/v1/competitor-intel/jobs/{job_id}",
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=_safe_error_response(e, "triggering retention cleanup"),
        )


@app.get("/api/v1/marine-intel/retention/stats")
async def get_retention_stats(
    _api_key: Optional[str] = Depends(verify_api_key),
):
    """Get retention tier statistics and policy information."""
    try:
        from lead_to_cash.services.marine_intel.retention_service import (
            get_retention_service,
        )

        service = get_retention_service()
        stats = await service.get_retention_stats()

        return {
            "success": True,
            "stats": stats,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=_safe_error_response(e, "getting retention stats"),
        )


@app.get("/api/v1/marine-intel/retention/preview")
async def preview_retention_cleanup(
    _api_key: Optional[str] = Depends(verify_api_key),
):
    """Preview what a retention cleanup would do without making changes."""
    try:
        from lead_to_cash.services.marine_intel.retention_service import (
            get_retention_service,
        )

        service = get_retention_service()
        preview = await service.preview_retention_job()

        return {
            "success": True,
            "preview": preview,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=_safe_error_response(e, "previewing retention cleanup"),
        )


# =============================================================================
# Unified Intelligence Search Endpoints
# =============================================================================


class UnifiedSearchRequest(BaseModel):
    """Request model for unified intelligence search."""

    query: str = Field(..., description="Natural language search query")
    sources: Optional[list[str]] = Field(
        default=None,
        description="Sources to search (marine, competitor). Default: both",
    )
    top_k: int = Field(default=20, description="Maximum number of results")
    use_semantic: bool = Field(default=True, description="Use semantic search")


class IntelligenceQuestionRequest(BaseModel):
    """Request model for intelligence Q&A."""

    question: str = Field(..., description="Natural language question")
    sources: Optional[list[str]] = Field(
        default=None, description="Sources to search for context"
    )


@app.post("/api/v1/intelligence/search")
async def unified_intelligence_search(
    body: UnifiedSearchRequest,
    _api_key: Optional[str] = Depends(verify_api_key),
):
    """
    Unified semantic search across all intelligence sources.

    Searches both marine and competitor intelligence databases
    and returns merged, ranked results.

    Request body:
    {
        "query": "Caterpillar engine orders in Singapore",
        "sources": ["marine", "competitor"],  // optional
        "top_k": 20,
        "use_semantic": true
    }
    """
    try:
        from lead_to_cash.services.intelligence_query_service import (
            get_intelligence_query_service,
        )

        service = get_intelligence_query_service()
        result = await service.search(
            query=body.query,
            sources=body.sources,
            use_semantic=body.use_semantic,
            top_k=body.top_k,
        )

        return {
            "success": True,
            **result.to_dict(),
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=_safe_error_response(e, "unified intelligence search"),
        )


@app.post("/api/v1/intelligence/ask")
async def ask_intelligence(
    body: IntelligenceQuestionRequest,
    _api_key: Optional[str] = Depends(verify_api_key),
):
    """
    Ask a natural language question about intelligence data.

    Uses RAG to search relevant documents and synthesize an answer.

    Request body:
    {
        "question": "What are the recent newbuild orders in Singapore?",
        "sources": ["marine"]  // optional
    }
    """
    try:
        from lead_to_cash.services.intelligence_query_service import (
            get_intelligence_query_service,
        )

        service = get_intelligence_query_service()
        result = await service.ask(
            question=body.question,
            context_sources=body.sources,
        )

        return {
            "success": True,
            **result.to_dict(),
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=_safe_error_response(e, "intelligence Q&A"),
        )


@app.get("/api/v1/intelligence/stats")
async def get_intelligence_stats(
    _api_key: Optional[str] = Depends(verify_api_key),
):
    """Get combined statistics from all intelligence sources."""
    try:
        from lead_to_cash.services.intelligence_query_service import (
            get_intelligence_query_service,
        )

        service = get_intelligence_query_service()
        stats = await service.get_stats()

        return {
            "success": True,
            "stats": stats,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=_safe_error_response(e, "getting intelligence stats"),
        )


# =============================================================================
# FinanceOps Dashboard Endpoints (Story 4.x)
# =============================================================================


def _check_finops_permission(user: AuthUser) -> None:
    """Check if user has finops permissions.

    Raises HTTPException 403 if user doesn't have billing read permission.
    """
    global auth_manager
    if not auth_manager:
        raise HTTPException(
            status_code=503, detail="Authentication service unavailable"
        )

    if user is None:
        raise HTTPException(status_code=401, detail="Not authenticated")
    if not auth_manager.check_permission(user, "billing", "read"):
        raise HTTPException(
            status_code=403,
            detail="Access denied. FinanceOps dashboard requires billing permissions.",
        )


@app.get("/api/v1/finops/summary")
async def get_finops_summary(
    user: Optional[AuthUser] = Depends(get_optional_user),
    _api_key: Optional[str] = Depends(verify_api_key),
):
    """
    Get billing and collections summary for dashboard badges.

    Requires: financeops role with billing:read permission.

    Returns:
        - billing_count: Number of items pending billing
        - billing_amount: Total amount pending billing
        - collections_count: Number of items pending collection
        - collections_amount: Total amount pending collection
        - overdue_count: Number of overdue items
        - overdue_amount: Total overdue amount
        - currency: Primary currency
        - as_of_date: Date of the summary
    """
    _check_finops_permission(user)

    try:
        from lead_to_cash.services.financeops.billing_brain import BillingBrainService

        async with BillingBrainService() as brain:
            summary = await brain.get_summary()

        return {
            "success": True,
            # Map billing brain summary to badge fields the frontend expects
            "billing_count": summary.overdue
            + summary.due_this_week
            + summary.due_this_month,
            "billing_amount": summary.total_overdue_amount
            + summary.total_due_soon_amount,
            "collections_count": summary.billed_unpaid,
            "collections_amount": 0.0,
            "overdue_count": summary.overdue + summary.blocked,
            "overdue_amount": summary.total_overdue_amount,
            "downpayment_count": 0,  # Folded into billing_count
            "downpayment_amount": 0.0,
            "currency": summary.currency,
            "as_of_date": None,
            # Extended brain summary for richer frontend
            **{f"brain_{k}": v for k, v in summary.to_dict().items()},
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=_safe_error_response(e, "getting finops summary"),
        )


@app.get("/api/v1/finops/billing")
async def get_finops_billing_items(
    customer_id: Optional[str] = None,
    status: Optional[str] = None,
    user: Optional[AuthUser] = Depends(get_optional_user),
    _api_key: Optional[str] = Depends(verify_api_key),
):
    """
    Get billing items, optionally filtered.

    Requires: financeops role with billing:read permission.

    Query Parameters:
        customer_id: Filter by SAP customer ID (10-digit format: 0000123456)
        status: Filter by status (PENDING_BILLING, PENDING_COLLECTION, etc.)

    Returns list of billing items with:
        - document_number
        - customer_id, customer_name
        - total_amount, currency
        - status
        - payment_term (harmonized)
        - next_action_date, days_to_action
        - aging_bucket
    """
    _check_finops_permission(user)

    # Validate customer_id format if provided
    if customer_id and not re.match(r"^\d{10}$", customer_id):
        raise HTTPException(
            status_code=400,
            detail="Invalid customer_id format. Expected 10-digit SAP customer ID (e.g., 0000123456)",
        )

    # Validate status if provided
    allowed_statuses = [
        "PENDING_BILLING",
        "PENDING_COLLECTION",
        "PARTIALLY_PAID",
        "PAID",
        "OVERDUE",
    ]
    if status and status not in allowed_statuses:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid status '{status}'. Allowed values: {', '.join(allowed_statuses)}",
        )

    try:
        from lead_to_cash.services.financeops.billing_brain import BillingBrainService

        # Billing = pre-invoice milestones (not yet billed)
        _BILLING_STATES = {"OVERDUE", "DUE_THIS_WEEK", "DUE_THIS_MONTH", "UPCOMING", "BLOCKED"}

        async with BillingBrainService() as brain:
            all_alerts = await brain.get_all_alerts(
                customer_id=customer_id,
            )

        # Filter to billing-relevant states
        items = [a for a in all_alerts if a.state.value in _BILLING_STATES]

        # Apply status filter if provided (map old statuses to brain states)
        if status:
            status_map = {
                "PENDING_BILLING": {"OVERDUE", "DUE_THIS_WEEK", "DUE_THIS_MONTH", "UPCOMING"},
                "OVERDUE": {"OVERDUE"},
                "PENDING_COLLECTION": set(),
                "PARTIALLY_PAID": set(),
                "PAID": set(),
            }
            allowed = status_map.get(status, {status})
            items = [a for a in items if a.state.value in allowed]

        return {
            "success": True,
            "items": [item.to_dict() for item in items],
            "count": len(items),
            "filters": {
                "customer_id": customer_id,
                "status": status,
            },
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=_safe_error_response(e, "getting billing items"),
        )


@app.get("/api/v1/finops/collections")
async def get_finops_collections_items(
    customer_id: Optional[str] = None,
    status: Optional[str] = None,
    user: Optional[AuthUser] = Depends(get_optional_user),
    _api_key: Optional[str] = Depends(verify_api_key),
):
    """
    Get items requiring collection action.

    Requires: financeops role with collections:read permission.

    Query Parameters:
        customer_id: Filter by SAP customer ID (10-digit format)
        status: Filter by status (PENDING_COLLECTION, PARTIALLY_PAID, OVERDUE)

    Returns collection-relevant items with aging information.
    """
    _check_finops_permission(user)

    # Validate customer_id format if provided
    if customer_id and not re.match(r"^\d{10}$", customer_id):
        raise HTTPException(
            status_code=400,
            detail="Invalid customer_id format. Expected 10-digit SAP customer ID",
        )

    # Validate status if provided (collections-relevant statuses only)
    allowed_statuses = ["PENDING_COLLECTION", "PARTIALLY_PAID", "OVERDUE"]
    if status and status not in allowed_statuses:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid status '{status}'. Allowed values for collections: {', '.join(allowed_statuses)}",
        )

    try:
        from lead_to_cash.services.financeops.billing_brain import BillingBrainService

        # Collections = billed but unpaid milestones
        async with BillingBrainService() as brain:
            all_alerts = await brain.get_all_alerts(
                customer_id=customer_id,
                include_settled=True,
            )

        # Filter to collections-relevant states
        _COLLECTIONS_STATES = {"BILLED_UNPAID", "BILLED_PAID"}
        items = [a for a in all_alerts if a.state.value in _COLLECTIONS_STATES]

        # Apply status filter
        if status:
            status_map = {
                "PENDING_COLLECTION": {"BILLED_UNPAID"},
                "PARTIALLY_PAID": set(),
                "OVERDUE": set(),
            }
            allowed = status_map.get(status, {status})
            items = [a for a in items if a.state.value in allowed]

        return {
            "success": True,
            "items": [item.to_dict() for item in items],
            "count": len(items),
            "filters": {
                "customer_id": customer_id,
                "status": status,
            },
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=_safe_error_response(e, "getting collections items"),
        )


@app.get("/api/v1/finops/aging")
async def get_finops_aging_buckets(
    user: Optional[AuthUser] = Depends(get_optional_user),
    _api_key: Optional[str] = Depends(verify_api_key),
):
    """
    Get aging bucket breakdown.

    Requires: financeops role with collections:read permission.

    Returns:
        - CURRENT: Items not yet due
        - 1-30: Items 1-30 days overdue
        - 31-60: Items 31-60 days overdue
        - 61-90: Items 61-90 days overdue
        - 90+: Items more than 90 days overdue

    Each bucket contains count and amount.
    """
    _check_finops_permission(user)

    try:
        from lead_to_cash.services.financeops.billing_brain import BillingBrainService

        async with BillingBrainService() as brain:
            all_alerts = await brain.get_all_alerts(include_settled=False)

        # Build aging buckets from milestone alerts
        buckets = {
            "CURRENT": {"count": 0, "amount": 0.0},
            "1-30": {"count": 0, "amount": 0.0},
            "31-60": {"count": 0, "amount": 0.0},
            "61-90": {"count": 0, "amount": 0.0},
            "90+": {"count": 0, "amount": 0.0},
        }
        currency = "EUR"

        for alert in all_alerts:
            amt = alert.milestone_amount or 0.0
            days = -alert.days_until_due  # positive = overdue
            currency = alert.order_currency or currency

            if days <= 0:
                buckets["CURRENT"]["count"] += 1
                buckets["CURRENT"]["amount"] += amt
            elif days <= 30:
                buckets["1-30"]["count"] += 1
                buckets["1-30"]["amount"] += amt
            elif days <= 60:
                buckets["31-60"]["count"] += 1
                buckets["31-60"]["amount"] += amt
            elif days <= 90:
                buckets["61-90"]["count"] += 1
                buckets["61-90"]["amount"] += amt
            else:
                buckets["90+"]["count"] += 1
                buckets["90+"]["amount"] += amt

        # Round amounts
        for b in buckets.values():
            b["amount"] = round(b["amount"], 2)

        return {
            "success": True,
            "buckets": buckets,
            "currency": currency,
            "total_items": sum(b["count"] for b in buckets.values()),
            "total_amount": round(sum(b["amount"] for b in buckets.values()), 2),
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=_safe_error_response(e, "getting aging buckets"),
        )


@app.get("/api/v1/finops/payment-terms/{customer_id}")
async def get_finops_payment_terms(
    customer_id: str,
    user: Optional[AuthUser] = Depends(get_optional_user),
    _api_key: Optional[str] = Depends(verify_api_key),
):
    """
    Get harmonized payment terms for a specific customer.

    Requires: financeops role with payments:read permission.

    Path Parameters:
        customer_id: SAP customer ID (10-digit format)

    Returns:
        - raw_text: Original payment terms text from SAP
        - term_type: Parsed type (NET, ADVANCE, MILESTONE, LC, etc.)
        - milestones: List of payment milestones with percentages, triggers, methods
        - total_advance_pct: Sum of advance payment percentages
        - total_balance_pct: Sum of balance payment percentages
        - primary_method: Main payment method (TT, LC_SIGHT, etc.)
        - has_lc: Whether Letter of Credit is required
        - has_bank_guarantee: Whether Bank Guarantee is required
        - confidence: Parsing confidence score (0-1)
    """
    _check_finops_permission(user)

    # Validate customer_id format
    if not re.match(r"^\d{10}$", customer_id):
        raise HTTPException(
            status_code=400,
            detail="Invalid customer_id format. Expected 10-digit SAP customer ID",
        )

    try:
        from lead_to_cash.services.financeops import FinOpsDataService

        async with FinOpsDataService() as service:
            terms = await service.get_payment_terms(customer_id)

        if not terms:
            raise HTTPException(
                status_code=404,
                detail=f"No payment terms found for customer {customer_id}",
            )

        return {
            "success": True,
            "customer_id": customer_id,
            "payment_terms": terms,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=_safe_error_response(e, "getting payment terms"),
        )


@app.post("/api/v1/finops/refresh")
async def refresh_finops_data(
    user: Optional[AuthUser] = Depends(get_optional_user),
    _api_key: Optional[str] = Depends(verify_api_key),
):
    """
    Manually refresh FinOps data from source systems.

    Requires: financeops role with billing:read permission.

    This endpoint triggers a cache refresh for billing/collections data.
    Use when you need the latest data from SAP CPI.

    Returns:
        - success: Boolean indicating refresh completed
        - refreshed_at: ISO timestamp of refresh
        - message: Status message
    """
    _check_finops_permission(user)

    try:
        from lead_to_cash.services.financeops import FinOpsDataService

        # Create service and trigger refresh (reconnect)
        async with FinOpsDataService() as service:
            # Get fresh data to verify refresh worked
            summary = await service.get_summary_counts()

        return {
            "success": True,
            "refreshed_at": datetime.now(timezone.utc).isoformat(),
            "message": "FinOps data refreshed successfully",
            "summary": {
                "billing_count": summary.billing_count,
                "collections_count": summary.collections_count,
                "overdue_count": summary.overdue_count,
            },
        }
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=_safe_error_response(e, "refreshing finops data"),
        )


# =============================================================================
# IPAS Order Entry Endpoints
# =============================================================================


@app.get("/api/v1/ipas/summary")
async def get_ipas_summary(
    _api_key: Optional[str] = Depends(verify_api_key),
):
    """
    Get IPAS pending orders summary.

    Returns count of pending orders ready for MS5 entry.
    """
    from lead_to_cash.services.ipas_order_service import get_ipas_order_service

    try:
        service = get_ipas_order_service()
        summary = service.get_summary()
        return {
            "pending_count": summary["pending_count"],
            "total_engines": summary["total_engines"],
            "total_items": summary["total_items"],
            "value_by_currency": summary["value_by_currency"],
            "last_scan": summary["last_scan"],
        }
    except Exception as e:
        logger.error(f"Error getting IPAS summary: {e}")
        raise HTTPException(
            status_code=500,
            detail=_safe_error_response(e, "getting IPAS summary"),
        )


@app.get("/api/v1/ipas/orders")
async def get_ipas_pending_orders(
    _api_key: Optional[str] = Depends(verify_api_key),
):
    """
    Get all pending IPAS orders ready for MS5 entry.

    Returns list of orders with summary information.
    """
    from lead_to_cash.services.ipas_order_service import get_ipas_order_service

    try:
        service = get_ipas_order_service()
        orders = service.get_pending_orders()

        # Return summary view of orders (sales-relevant fields)
        return {
            "orders": [
                {
                    "order_id": o.order_id,
                    "message_id": o.message_id,
                    "project_number": o.header.ipas_project_number,
                    "customer_po": o.header.purchase_order_number,
                    "document_date": o.header.document_date,
                    "delivery_date": o.engines[0].delivery_date if o.engines else "",
                    "engine_type": o.product.engine_type,
                    "sold_to_party": o.customers.sold_to_party,
                    "end_customer_country": o.customers.end_customer_country,
                    "total_engines": o.total_engines,
                    "total_items": o.total_items,
                    "total_value": o.total_value,
                    "currency": o.commercial.currency_code,
                    "incoterms": f"{o.commercial.incoterms_1} {o.commercial.incoterms_2}".strip(),
                }
                for o in orders
            ],
            "count": len(orders),
        }
    except Exception as e:
        logger.error(f"Error getting IPAS orders: {e}")
        raise HTTPException(
            status_code=500,
            detail=_safe_error_response(e, "getting IPAS orders"),
        )


@app.get("/api/v1/ipas/orders/{order_id}")
async def get_ipas_order_detail(
    order_id: str,
    _api_key: Optional[str] = Depends(verify_api_key),
):
    """
    Get detailed IPAS order for MS5 entry.

    Returns full order data structured for MS5 SAP entry screen.
    Fields are organized in MS5 entry sequence:
    1. Header (Sales Org, Order Type, etc.)
    2. Customers (Sold-to, Ship-to, Bill-to, End Customer)
    3. Product (Engine Type, Power, Series, etc.)
    4. Commercial (Incoterms, Payment Terms, Currency)
    5. Delivery (Location, Shipping, Regions)
    6. Classification (Society, Emissions, Flag State)
    7. Engines with line items (Materials, Quantities, Dates)
    """
    from lead_to_cash.services.ipas_order_service import get_ipas_order_service

    try:
        service = get_ipas_order_service()
        order = service.get_order(order_id)

        if not order:
            raise HTTPException(
                status_code=404,
                detail=f"Order {order_id} not found",
            )

        return order.to_dict()
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting IPAS order {order_id}: {e}")
        raise HTTPException(
            status_code=500,
            detail=_safe_error_response(e, f"getting IPAS order {order_id}"),
        )


@app.post("/api/v1/ipas/orders/{order_id}/export")
async def export_ipas_order_excel(
    order_id: str,
    request: Request,
    user: AuthUser = Depends(get_current_user),
    _api_key: Optional[str] = Depends(verify_api_key),
):
    """
    Export IPAS order as SAP-compatible Excel file.

    Generates XLSX with Header, Line Items, Partners, and Billing Plan sheets
    in SAP VA01 new order creation format.

    Accepts optional payment_terms override in request body.
    """
    from io import BytesIO

    from lead_to_cash.services.ipas_order_service import get_ipas_order_service

    try:
        import openpyxl
        from openpyxl.styles import Alignment, Font, PatternFill
    except ImportError:
        raise HTTPException(status_code=500, detail="openpyxl not installed")

    try:
        service = get_ipas_order_service()
        order = service.get_order(order_id)
        if not order:
            raise HTTPException(status_code=404, detail=f"Order {order_id} not found")

        # Get optional payment terms override
        body = {}
        try:
            body = await request.json()
        except Exception:
            pass
        payment_terms = body.get("payment_terms", order.commercial.payment_terms or "")

        # Create workbook
        wb = openpyxl.Workbook()

        # Styles
        header_fill = PatternFill(
            start_color="1F4E79", end_color="1F4E79", fill_type="solid"
        )
        header_font = Font(color="FFFFFF", bold=True, size=10)
        data_font = Font(size=10)
        wrap_align = Alignment(wrap_text=True, vertical="top")

        def style_header(ws, headers):
            for col, h in enumerate(headers, 1):
                cell = ws.cell(row=1, column=col, value=h)
                cell.fill = header_fill
                cell.font = header_font
                cell.alignment = Alignment(horizontal="center")

        # --- Sheet 1: Order Header ---
        ws1 = wb.active
        ws1.title = "Order Header"
        header_fields = [
            ("SAP Field", "Value", "Description"),
        ]
        header_data = [
            ("AUART", order.header.order_type or "ZEN2", "Order Type"),
            ("VKORG", order.header.sales_org or "SG01", "Sales Organization"),
            (
                "VTWEG",
                order.header.distribution_channel or "10",
                "Distribution Channel",
            ),
            ("SPART", "00", "Division"),
            ("BSTNK", order.header.purchase_order_number, "Customer PO Number"),
            ("BSTDK", order.header.purchase_order_date, "Customer PO Date"),
            ("AUDAT", order.header.document_date, "Document Date"),
            ("WAERK", order.commercial.currency_code, "Currency"),
            ("INCO1", order.commercial.incoterms_1, "Incoterms"),
            ("INCO2", order.commercial.incoterms_2, "Incoterms Location"),
            ("ZTERM", payment_terms, "Payment Terms"),
            ("IPAS_ORDER", order.header.ipas_order_number, "IPAS Order Number"),
            ("IPAS_PROJECT", order.header.ipas_project_number, "IPAS Project Number"),
        ]
        style_header(ws1, ["SAP Field", "Value", "Description"])
        for idx, (field, value, desc) in enumerate(header_data, 2):
            ws1.cell(row=idx, column=1, value=field).font = data_font
            ws1.cell(row=idx, column=2, value=str(value or "")).font = data_font
            ws1.cell(row=idx, column=3, value=desc).font = data_font
        ws1.column_dimensions["A"].width = 18
        ws1.column_dimensions["B"].width = 35
        ws1.column_dimensions["C"].width = 30

        # --- Sheet 2: Line Items ---
        ws2 = wb.create_sheet("Line Items")
        item_headers = [
            "Item No",
            "Material",
            "Description",
            "Quantity",
            "Unit",
            "Plant",
            "Delivery Date",
            "Engine No",
            "Assembly Note",
        ]
        style_header(ws2, item_headers)
        row = 2
        for eng in order.engines:
            for item in eng.items:
                ws2.cell(row=row, column=1, value=item.item_number).font = data_font
                ws2.cell(row=row, column=2, value=item.material).font = data_font
                ws2.cell(
                    row=row, column=3, value=item.material_description
                ).font = data_font
                ws2.cell(row=row, column=4, value=item.quantity).font = data_font
                ws2.cell(row=row, column=5, value=item.unit or "EA").font = data_font
                ws2.cell(row=row, column=6, value=item.plant or "0011").font = data_font
                ws2.cell(row=row, column=7, value=item.delivery_date).font = data_font
                ws2.cell(row=row, column=8, value=item.engine_number).font = data_font
                ws2.cell(row=row, column=9, value=item.assembly_note).font = data_font
                row += 1
        for col in range(1, 10):
            ws2.column_dimensions[openpyxl.utils.get_column_letter(col)].width = 16

        # --- Sheet 3: Partners ---
        ws3 = wb.create_sheet("Partners")
        partner_headers = ["Partner Role", "Customer ID", "Description"]
        style_header(ws3, partner_headers)
        partner_data = [
            ("AG (Sold-to)", order.customers.sold_to_party, "Sold-to Party"),
            ("WE (Ship-to)", order.customers.ship_to_party, "Ship-to Party"),
            ("RE (Bill-to)", order.customers.bill_to_party, "Bill-to Party"),
            ("RG (Payer)", order.customers.payer, "Payer"),
            ("ZE (End Customer)", order.customers.end_customer, "End Customer"),
        ]
        for idx, (role, cust_id, desc) in enumerate(partner_data, 2):
            ws3.cell(row=idx, column=1, value=role).font = data_font
            ws3.cell(row=idx, column=2, value=cust_id or "").font = data_font
            ws3.cell(row=idx, column=3, value=desc).font = data_font
        ws3.column_dimensions["A"].width = 18
        ws3.column_dimensions["B"].width = 18
        ws3.column_dimensions["C"].width = 25

        # --- Sheet 4: Product & Classification ---
        ws4 = wb.create_sheet("Product & Classification")
        prod_headers = ["Field", "Value"]
        style_header(ws4, prod_headers)
        prod_data = [
            ("Engine Type", order.product.engine_type),
            ("Series", order.product.series),
            ("Cylinder", order.product.cylinder),
            ("Power", f"{order.product.power} {order.product.power_unit}"),
            ("Engine Speed", order.product.engine_speed),
            ("Application Coarse", order.product.application_coarse),
            ("Application Fine", order.product.application_fine),
            ("Application Group", order.product.application_group),
            ("Type of Service", order.product.type_of_service),
            ("Product Category", order.product.product_category),
            ("Propulsion Type", order.product.propulsion_type),
            ("Business Type", order.product.business_type),
            ("Object Type", order.product.ipas_object_type),
            ("Project Type", order.product.project_type),
            ("Classification Society", order.classification.classification_society),
            ("Emission Cert Authority", order.classification.emission_cert_authority),
            ("Flag State", order.classification.flag_state),
            ("Exhaust Regulation", order.classification.exhaust_regulation),
        ]
        for idx, (field, value) in enumerate(prod_data, 2):
            ws4.cell(row=idx, column=1, value=field).font = data_font
            ws4.cell(row=idx, column=2, value=str(value or "")).font = data_font
        ws4.column_dimensions["A"].width = 25
        ws4.column_dimensions["B"].width = 25

        # --- Sheet 5: Payment Terms ---
        ws5 = wb.create_sheet("Payment Terms")
        style_header(ws5, ["Payment Terms"])
        cell = ws5.cell(row=2, column=1, value=payment_terms)
        cell.font = data_font
        cell.alignment = wrap_align
        ws5.column_dimensions["A"].width = 80
        ws5.row_dimensions[2].height = 80

        # Save to buffer
        buffer = BytesIO()
        wb.save(buffer)
        buffer.seek(0)

        from starlette.responses import StreamingResponse

        return StreamingResponse(
            buffer,
            media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            headers={
                "Content-Disposition": f'attachment; filename="SAP_Order_{order_id}.xlsx"'
            },
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error exporting IPAS order {order_id}: {e}")
        raise HTTPException(
            status_code=500,
            detail=_safe_error_response(e, f"exporting IPAS order {order_id}"),
        )


# =============================================================================
# SAP Integration Test Endpoints
# =============================================================================


@app.get("/api/v1/test")
async def test_auth(_api_key: Optional[str] = Depends(verify_api_key)):
    """Test authentication endpoint."""
    return {
        "status": "ok",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "message": "Authentication successful",
    }


class EchoRequest(BaseModel):
    """Request model for echo endpoint."""

    data: Optional[dict] = Field(default=None, description="Data to echo back")


@app.post("/api/v1/echo")
async def echo(
    body: EchoRequest,
    _api_key: Optional[str] = Depends(verify_api_key),
):
    """Echo test endpoint for bidirectional communication."""
    return {
        "status": "ok",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "received": body.model_dump(),
    }


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        app,
        host=config.api_host,
        port=config.api_port,
        log_level=config.sdk_log_level.lower(),
    )
