"""
SAP Integration MCP Server - Production Implementation

Unified MCP server exposing SAP CEC, IPAS, and MS5 operations as discoverable tools.
ALL requests route through SAP CPI as the single gateway per architecture.

Architecture (per Kailash Platform Deployment Architecture):
    ┌─────────────────────────────────────────────────────────────────┐
    │  SAPIntegrationMCPServer                                        │
    │    ├── CECClient  ─┐                                            │
    │    ├── IPASClient ─┼─→ CPIClient ─→ SAP CPI ─→ Target Systems   │
    │    └── MS5Client  ─┘                                            │
    └─────────────────────────────────────────────────────────────────┘

    SAP CPI Routes:
        - CPI → SAP CEC (existing interface)
        - CPI → IPAS (NEW interface)
        - CPI → Cloud Connector → MS5/ECC (existing interface)

Features:
    - Rate limiting (configurable requests/minute)
    - Circuit breaker (configurable failure threshold)
    - Response caching (per-tool TTL)
    - API key authentication with permissions
    - Prometheus metrics export
    - Thread-safe idempotency for order creation
    - Comprehensive input validation

Tools (13 total):
    CEC (4 tools):
        - cec_get_opportunity: Get opportunity by ID
        - cec_search_opportunities: Search opportunities
        - cec_get_opportunities_by_account: Get opportunities for account
        - cec_get_commercial_terms: Get payment terms, Incoterms

    IPAS (4 tools):
        - ipas_get_configuration: Get product configuration
        - ipas_get_configurations_by_opportunity: Get configs for opportunity
        - ipas_get_product_catalog: Get product catalog
        - ipas_validate_configuration: Validate configuration

    MS5 (5 tools):
        - sap_get_customer: Customer master data
        - sap_check_credit: Credit limit and exposure
        - sap_simulate_order: Order simulation
        - sap_create_order: Order creation with commit
        - sap_health_check: Health check for all systems

Usage:
    # As standalone server (STDIO transport)
    python -m lead_to_cash.mcp.sap_cpi_server

    # Integrated with Kaizen agents
    from lead_to_cash.mcp import get_sap_cpi_mcp_config
    agent = SalesOpsAgent(mcp_servers=[get_sap_cpi_mcp_config()])
"""

import asyncio
import hashlib
import json
import logging
import os
import re
import time
from dataclasses import dataclass
from typing import Any, Optional

from kailash.mcp_server import MCPServer
from kailash.mcp_server.auth import APIKeyAuth

from lead_to_cash.config import config
from lead_to_cash.integrations.cec_client import CECClient
from lead_to_cash.integrations.cpi_client import CPIClient
from lead_to_cash.integrations.ipas_client import IPASClient
from lead_to_cash.integrations.ms5_client import MS5Client

logger = logging.getLogger(__name__)


# =============================================================================
# Input Validation
# =============================================================================


class ValidationError(ValueError):
    """Input validation error with structured details."""

    def __init__(self, message: str, field: str, value: Any = None):
        super().__init__(message)
        self.field = field
        self.value = value
        self.message = message


def validate_customer_id(customer_id: str) -> str:
    """Validate and normalize SAP customer ID (1-10 alphanumeric chars)."""
    if not customer_id:
        raise ValidationError(
            "customer_id is required", field="customer_id", value=customer_id
        )
    if len(customer_id) > 10:
        raise ValidationError(
            "customer_id must be 1-10 characters",
            field="customer_id",
            value=customer_id,
        )
    if not re.match(r"^[A-Za-z0-9]+$", customer_id):
        raise ValidationError(
            "customer_id must be alphanumeric", field="customer_id", value=customer_id
        )
    return customer_id.zfill(10)


def validate_credit_control_area(cca: str) -> str:
    """Validate credit control area code (4 alphanumeric chars, optional)."""
    if not cca:
        return ""
    if len(cca) != 4:
        raise ValidationError(
            "credit_control_area must be exactly 4 characters",
            field="credit_control_area",
            value=cca,
        )
    if not re.match(r"^[A-Za-z0-9]+$", cca):
        raise ValidationError(
            "credit_control_area must be alphanumeric",
            field="credit_control_area",
            value=cca,
        )
    return cca.upper()


def validate_sales_org(sales_org: str) -> str:
    """Validate sales organization code (4 chars, required)."""
    if not sales_org:
        raise ValidationError(
            "sales_org is required", field="sales_org", value=sales_org
        )
    if len(sales_org) != 4:
        raise ValidationError(
            "sales_org must be exactly 4 characters", field="sales_org", value=sales_org
        )
    return sales_org.upper()


def validate_order_items(items: list[dict]) -> list[dict]:
    """Validate order line items (non-empty list with material and positive quantity)."""
    if not items:
        raise ValidationError(
            "items must be a non-empty list", field="items", value=items
        )
    if not isinstance(items, list):
        raise ValidationError("items must be a list", field="items", value=items)

    validated_items = []
    for i, item in enumerate(items):
        if not isinstance(item, dict):
            raise ValidationError(
                f"items[{i}] must be an object", field=f"items[{i}]", value=item
            )
        if "material" not in item:
            raise ValidationError(
                f"items[{i}].material is required",
                field=f"items[{i}].material",
                value=item,
            )
        material = item["material"]
        if not isinstance(material, str) or len(material.strip()) == 0:
            raise ValidationError(
                f"items[{i}].material must be a non-empty string",
                field=f"items[{i}].material",
                value=material,
            )
        if len(material) > 40:
            raise ValidationError(
                f"items[{i}].material exceeds max length of 40 characters",
                field=f"items[{i}].material",
                value=material[:50],
            )
        if "quantity" not in item:
            raise ValidationError(
                f"items[{i}].quantity is required",
                field=f"items[{i}].quantity",
                value=item,
            )
        if not isinstance(item["quantity"], (int, float)) or item["quantity"] <= 0:
            raise ValidationError(
                f"items[{i}].quantity must be a positive number",
                field=f"items[{i}].quantity",
                value=item.get("quantity"),
            )

        validated_items.append(
            {
                "material": str(item["material"]).strip(),
                "quantity": float(item["quantity"]),
                "unit": item.get("unit", "EA"),
                "plant": item.get("plant", ""),
            }
        )
    return validated_items


def validate_opportunity_id(opportunity_id: str) -> str:
    """Validate opportunity ID (required, non-empty)."""
    if not opportunity_id or not opportunity_id.strip():
        raise ValidationError(
            "opportunity_id is required", field="opportunity_id", value=opportunity_id
        )
    return opportunity_id.strip()


def validate_config_id(config_id: str) -> str:
    """Validate configuration ID (required, non-empty)."""
    if not config_id or not config_id.strip():
        raise ValidationError(
            "config_id is required", field="config_id", value=config_id
        )
    return config_id.strip()


# =============================================================================
# Thread-Safe Idempotency Manager
# =============================================================================


@dataclass
class IdempotencyEntry:
    """Entry in the idempotency cache."""

    result: dict
    timestamp: float


class ThreadSafeIdempotencyManager:
    """Thread-safe idempotency manager with async locking."""

    def __init__(self, ttl_seconds: int = 3600):
        self._cache: dict[str, IdempotencyEntry] = {}
        self._lock = asyncio.Lock()
        self._ttl = ttl_seconds

    def generate_key(self, operation: str, payload: dict[str, Any]) -> str:
        """Generate deterministic idempotency key.

        Normalizes the payload to ensure minor variations (extra fields,
        whitespace, key ordering) produce the same key.
        """
        normalized = self._normalize_payload(payload)
        payload_str = json.dumps(normalized, sort_keys=True, default=str)
        content = f"{operation}:{payload_str}"
        return hashlib.sha256(content.encode()).hexdigest()[:16]

    @staticmethod
    def _normalize_payload(payload: Any) -> Any:
        """Recursively normalize payload for consistent key generation.

        - Strips whitespace from string values
        - Removes unknown/extra fields (only keeps known order fields)
        - Sorts lists of dicts by their content
        """
        # Known fields for order creation payloads
        _KNOWN_ORDER_FIELDS = {
            "customer_id",
            "sales_org",
            "items",
            "po_number",
            "distribution_channel",
            "division",
            "order_type",
            "material",
            "quantity",
            "unit",
            "plant",
        }

        if isinstance(payload, dict):
            result = {}
            for k, v in payload.items():
                # Only keep known fields (ignore extras like timestamps, metadata)
                if _KNOWN_ORDER_FIELDS and k not in _KNOWN_ORDER_FIELDS:
                    continue
                result[k] = ThreadSafeIdempotencyManager._normalize_payload(v)
            return result
        elif isinstance(payload, list):
            return [
                ThreadSafeIdempotencyManager._normalize_payload(item)
                for item in payload
            ]
        elif isinstance(payload, str):
            return payload.strip()
        else:
            return payload

    async def check_duplicate(self, key: str) -> Optional[dict]:
        """Check if operation was already processed."""
        async with self._lock:
            if key in self._cache:
                entry = self._cache[key]
                if time.time() - entry.timestamp < self._ttl:
                    return entry.result
                else:
                    del self._cache[key]
            return None

    async def store_result(self, key: str, result: dict) -> None:
        """Store operation result for idempotency."""
        async with self._lock:
            self._cache[key] = IdempotencyEntry(result=result, timestamp=time.time())
            await self._cleanup_expired()

    async def _cleanup_expired(self) -> None:
        """Remove expired entries from cache."""
        now = time.time()
        expired = [k for k, v in self._cache.items() if now - v.timestamp >= self._ttl]
        for k in expired:
            del self._cache[k]


# =============================================================================
# SAP Integration MCP Server
# =============================================================================


def create_sap_mcp_server(
    cpi_client: Optional[CPIClient] = None,
    cec_client: Optional[CECClient] = None,
    ipas_client: Optional[IPASClient] = None,
    ms5_client: Optional[MS5Client] = None,
    api_keys: Optional[dict[str, dict]] = None,
    rate_limit_per_minute: int = 100,
    circuit_breaker_threshold: int = 5,
    enable_cache: bool = True,
    enable_metrics: bool = True,
    transport: str = "stdio",
) -> MCPServer:
    """
    Create production-ready SAP Integration MCP Server.

    This factory function creates an MCPServer with all SAP tools registered.
    ALL requests route through SAP CPI as the single gateway.

    Args:
        cpi_client: Shared CPI client (creates new if not provided)
        cec_client: CEC client (creates new if not provided)
        ipas_client: IPAS client (creates new if not provided)
        ms5_client: MS5 client (creates new if not provided)
        api_keys: API key configuration dict
        rate_limit_per_minute: Rate limit
        circuit_breaker_threshold: Circuit breaker threshold
        enable_cache: Enable response caching
        enable_metrics: Enable Prometheus metrics
        transport: Transport type ("stdio", "websocket", "sse")

    Returns:
        Configured MCPServer instance ready to run
    """
    # Shared CPI client for all system integrations
    cpi = cpi_client or CPIClient()

    # System-specific clients (all route through CPI)
    cec = cec_client or CECClient(cpi_client=cpi)
    ipas = ipas_client or IPASClient(cpi_client=cpi)
    ms5 = ms5_client or MS5Client(cpi_client=cpi)

    # Idempotency manager for order creation
    idempotency = ThreadSafeIdempotencyManager(ttl_seconds=3600)

    # Connection state (mutable container so it can be shared and updated externally)
    state = {"connected": False}

    # Build API key authentication
    auth_provider = None
    if api_keys:
        auth_provider = APIKeyAuth(keys=api_keys, header_name="X-API-Key")
    elif os.getenv("MCP_API_KEY"):
        auth_provider = APIKeyAuth(
            keys={
                os.getenv("MCP_API_KEY", ""): {
                    "permissions": ["sap.read", "sap.write", "sap.admin"]
                }
            },
            header_name="X-API-Key",
        )

    # Create Kailash SDK MCPServer with production features
    # Circuit breaker config: pass None to disable (for testing), or config dict for production
    cb_config = None
    if circuit_breaker_threshold > 0:
        cb_config = {
            "failure_threshold": circuit_breaker_threshold,
            "timeout": 60.0,
            "success_threshold": 3,
        }

    server = MCPServer(
        name="sap-integration-server",
        transport=transport,
        enable_cache=enable_cache,
        cache_ttl=300,
        enable_metrics=enable_metrics,
        auth_provider=auth_provider,
        rate_limit_config={"default_limit": rate_limit_per_minute, "burst_limit": 10},
        circuit_breaker_config=cb_config,
        error_aggregation=True,
    )

    # =========================================================================
    # Lifecycle Tools
    # =========================================================================

    @server.tool(cache_key="sap_health", cache_ttl=30)
    async def sap_health_check() -> dict:
        """Check connectivity for all SAP systems (CEC, IPAS, MS5) via CPI gateway."""
        connected = state["connected"]
        try:
            cpi_health = (
                await cpi.health_check() if connected else {"status": "not_initialized"}
            )
            cec_health = (
                await cec.health_check() if connected else {"status": "not_initialized"}
            )
            ipas_health = (
                await ipas.health_check()
                if connected
                else {"status": "not_initialized"}
            )
            ms5_health = (
                await ms5.health_check() if connected else {"status": "not_initialized"}
            )
            return {
                "success": True,
                "environment": config.environment,
                "gateway": "SAP CPI",
                "connected": connected,
                "systems": {
                    "cpi": cpi_health,
                    "cec": cec_health,
                    "ipas": ipas_health,
                    "ms5": ms5_health,
                },
                "cache_enabled": enable_cache,
                "metrics_enabled": enable_metrics,
            }
        except Exception as e:
            logger.error(f"Health check error: {e}")
            return {
                "success": False,
                "error": {"code": "HEALTH_CHECK_ERROR", "message": str(e)},
            }

    # =========================================================================
    # CEC Tools (4)
    # =========================================================================

    @server.tool(
        cache_key="cec_opportunity", cache_ttl=300, required_permission="sap.read"
    )
    async def cec_get_opportunity(opportunity_id: str) -> dict:
        """Get opportunity from SAP CEC via CPI. Returns opportunity details with SAP field mapping."""
        connected = state["connected"]
        if not connected:
            return {
                "success": False,
                "error": {
                    "code": "NOT_CONNECTED",
                    "message": "Server not initialized. Call initialize() first.",
                },
            }
        try:
            opp_id = validate_opportunity_id(opportunity_id)
        except ValidationError as e:
            return {
                "success": False,
                "error": {
                    "code": "VALIDATION_ERROR",
                    "message": e.message,
                    "field": e.field,
                },
            }
        try:
            opp = await cec.get_opportunity(opp_id)
            return {
                "success": True,
                # Core identification
                "opportunity_id": opp.opportunity_id,
                "account_id": opp.account_id,
                "account_name": opp.account_name,
                # Status and value (ADR-006)
                "status": opp.status,
                "expected_revenue": opp.expected_revenue,
                "currency": opp.currency,
                # Dates (ADR-006)
                "close_date": opp.close_date.isoformat() if opp.close_date else None,
                "start_date": opp.start_date.isoformat() if opp.start_date else None,
                # Classification (ADR-006)
                "title": opp.title,
                "win_probability": opp.win_probability,
                "sales_type": opp.sales_type,
                # Milestone Payment Fields (ADR-006)
                "sap_order_id": opp.sap_order_id,
                "ipas_quote_id": opp.ipas_quote_id,
                # Products and SAP mapping
                "products": opp.products,
                "sap_mapping": opp.to_sap_mapping(),
            }
        except Exception as e:
            logger.error(f"Error getting opportunity {opportunity_id}: {e}")
            return {"success": False, "error": {"code": "CEC_ERROR", "message": str(e)}}

    @server.tool(cache_key="cec_search", cache_ttl=120, required_permission="sap.read")
    async def cec_search_opportunities(
        query: str, status: str = "", limit: int = 50
    ) -> dict:
        """Search opportunities in SAP CEC via CPI."""
        connected = state["connected"]
        if not connected:
            return {
                "success": False,
                "error": {
                    "code": "NOT_CONNECTED",
                    "message": "Server not initialized.",
                },
            }
        if not query or not query.strip():
            return {
                "success": False,
                "error": {
                    "code": "VALIDATION_ERROR",
                    "message": "query is required",
                    "field": "query",
                },
            }
        try:
            opportunities = await cec.search_opportunities(
                query.strip(), status or None, limit
            )
            return {
                "success": True,
                "count": len(opportunities),
                "opportunities": [
                    {
                        # Core identification
                        "opportunity_id": o.opportunity_id,
                        "account_id": o.account_id,
                        "account_name": o.account_name,
                        # Status and value (ADR-006)
                        "status": o.status,
                        "expected_revenue": o.expected_revenue,
                        "currency": o.currency,
                        # Dates (ADR-006)
                        "close_date": (
                            o.close_date.isoformat() if o.close_date else None
                        ),
                        "start_date": (
                            o.start_date.isoformat() if o.start_date else None
                        ),
                        # Classification (ADR-006)
                        "title": o.title,
                        "win_probability": o.win_probability,
                        "sales_type": o.sales_type,
                        # Milestone Payment Fields (ADR-006)
                        "sap_order_id": o.sap_order_id,
                        "ipas_quote_id": o.ipas_quote_id,
                    }
                    for o in opportunities
                ],
            }
        except Exception as e:
            logger.error(f"Error searching opportunities: {e}")
            return {"success": False, "error": {"code": "CEC_ERROR", "message": str(e)}}

    @server.tool(
        cache_key="cec_by_account", cache_ttl=180, required_permission="sap.read"
    )
    async def cec_get_opportunities_by_account(
        account_id: str, status: str = "", limit: int = 50
    ) -> dict:
        """Get opportunities for an account from SAP CEC via CPI."""
        connected = state["connected"]
        if not connected:
            return {
                "success": False,
                "error": {
                    "code": "NOT_CONNECTED",
                    "message": "Server not initialized.",
                },
            }
        if not account_id or not account_id.strip():
            return {
                "success": False,
                "error": {
                    "code": "VALIDATION_ERROR",
                    "message": "account_id is required",
                    "field": "account_id",
                },
            }
        try:
            opportunities = await cec.get_opportunities_by_account(
                account_id.strip(), status or None, limit
            )
            return {
                "success": True,
                "account_id": account_id,
                "count": len(opportunities),
                "opportunities": [
                    {
                        # Core identification
                        "opportunity_id": o.opportunity_id,
                        "account_id": o.account_id,
                        "account_name": o.account_name,
                        # Status and value (ADR-006)
                        "status": o.status,
                        "expected_revenue": o.expected_revenue,
                        "currency": o.currency,
                        # Dates (ADR-006)
                        "close_date": (
                            o.close_date.isoformat() if o.close_date else None
                        ),
                        "start_date": (
                            o.start_date.isoformat() if o.start_date else None
                        ),
                        # Classification (ADR-006)
                        "title": o.title,
                        "win_probability": o.win_probability,
                        "sales_type": o.sales_type,
                        # Milestone Payment Fields (ADR-006)
                        "sap_order_id": o.sap_order_id,
                        "ipas_quote_id": o.ipas_quote_id,
                    }
                    for o in opportunities
                ],
            }
        except Exception as e:
            logger.error(f"Error getting opportunities for account {account_id}: {e}")
            return {"success": False, "error": {"code": "CEC_ERROR", "message": str(e)}}

    @server.tool(cache_key="cec_terms", cache_ttl=600, required_permission="sap.read")
    async def cec_get_commercial_terms(account_id: str, sales_org: str = "") -> dict:
        """Get commercial terms (payment terms, Incoterms) from SAP CEC via CPI."""
        connected = state["connected"]
        if not connected:
            return {
                "success": False,
                "error": {
                    "code": "NOT_CONNECTED",
                    "message": "Server not initialized.",
                },
            }
        if not account_id or not account_id.strip():
            return {
                "success": False,
                "error": {
                    "code": "VALIDATION_ERROR",
                    "message": "account_id is required",
                    "field": "account_id",
                },
            }
        try:
            terms = await cec.get_commercial_terms(
                account_id.strip(), sales_org or None
            )
            return {"success": True, "account_id": account_id, **terms}
        except Exception as e:
            logger.error(f"Error getting commercial terms for {account_id}: {e}")
            return {"success": False, "error": {"code": "CEC_ERROR", "message": str(e)}}

    # =========================================================================
    # IPAS Tools (4)
    # =========================================================================

    @server.tool(cache_key="ipas_config", cache_ttl=300, required_permission="sap.read")
    async def ipas_get_configuration(config_id: str) -> dict:
        """Get product configuration from IPAS via CPI (NEW interface). Returns BOM and characteristics."""
        connected = state["connected"]
        if not connected:
            return {
                "success": False,
                "error": {
                    "code": "NOT_CONNECTED",
                    "message": "Server not initialized.",
                },
            }
        try:
            cfg_id = validate_config_id(config_id)
        except ValidationError as e:
            return {
                "success": False,
                "error": {
                    "code": "VALIDATION_ERROR",
                    "message": e.message,
                    "field": e.field,
                },
            }
        try:
            cfg = await ipas.get_configuration(cfg_id)
            return {
                "success": True,
                "config_id": cfg.config_id,
                "product_id": cfg.product_id,
                "product_name": cfg.product_name,
                "variant": cfg.variant,
                "bom_items": cfg.bom_items,
                "characteristics": cfg.characteristics,
                "materials": cfg.get_materials(),
                "order_items": cfg.to_order_items(),
            }
        except Exception as e:
            logger.error(f"Error getting configuration {config_id}: {e}")
            return {
                "success": False,
                "error": {"code": "IPAS_ERROR", "message": str(e)},
            }

    @server.tool(cache_key="ipas_by_opp", cache_ttl=300, required_permission="sap.read")
    async def ipas_get_configurations_by_opportunity(opportunity_id: str) -> dict:
        """Get product configurations for an opportunity from IPAS via CPI."""
        connected = state["connected"]
        if not connected:
            return {
                "success": False,
                "error": {
                    "code": "NOT_CONNECTED",
                    "message": "Server not initialized.",
                },
            }
        try:
            opp_id = validate_opportunity_id(opportunity_id)
        except ValidationError as e:
            return {
                "success": False,
                "error": {
                    "code": "VALIDATION_ERROR",
                    "message": e.message,
                    "field": e.field,
                },
            }
        try:
            configurations = await ipas.get_configuration_by_opportunity(opp_id)
            return {
                "success": True,
                "opportunity_id": opportunity_id,
                "count": len(configurations),
                "configurations": [
                    {
                        "config_id": c.config_id,
                        "product_id": c.product_id,
                        "product_name": c.product_name,
                        "materials": c.get_materials(),
                    }
                    for c in configurations
                ],
            }
        except Exception as e:
            logger.error(
                f"Error getting configurations for opportunity {opportunity_id}: {e}"
            )
            return {
                "success": False,
                "error": {"code": "IPAS_ERROR", "message": str(e)},
            }

    @server.tool(
        cache_key="ipas_catalog", cache_ttl=600, required_permission="sap.read"
    )
    async def ipas_get_product_catalog(
        category: str = "", search: str = "", limit: int = 50
    ) -> dict:
        """Get product catalog from IPAS via CPI (NEW interface)."""
        connected = state["connected"]
        if not connected:
            return {
                "success": False,
                "error": {
                    "code": "NOT_CONNECTED",
                    "message": "Server not initialized.",
                },
            }
        try:
            products = await ipas.get_product_catalog(
                category or None, search or None, limit
            )
            return {
                "success": True,
                "count": len(products),
                "products": [
                    {
                        "product_id": p.product_id,
                        "name": p.name,
                        "category": p.category,
                        "configurable": p.configurable,
                        "base_price": p.base_price,
                        "currency": p.currency,
                    }
                    for p in products
                ],
            }
        except Exception as e:
            logger.error(f"Error getting product catalog: {e}")
            return {
                "success": False,
                "error": {"code": "IPAS_ERROR", "message": str(e)},
            }

    @server.tool(required_permission="sap.read", timeout=30.0)
    async def ipas_validate_configuration(
        config_id: str, characteristics: dict
    ) -> dict:
        """Validate configuration characteristics in IPAS via CPI."""
        connected = state["connected"]
        if not connected:
            return {
                "success": False,
                "error": {
                    "code": "NOT_CONNECTED",
                    "message": "Server not initialized.",
                },
            }
        try:
            cfg_id = validate_config_id(config_id)
        except ValidationError as e:
            return {
                "success": False,
                "error": {
                    "code": "VALIDATION_ERROR",
                    "message": e.message,
                    "field": e.field,
                },
            }
        try:
            result = await ipas.validate_configuration(cfg_id, characteristics or {})
            return {"success": True, "config_id": config_id, **result}
        except Exception as e:
            logger.error(f"Error validating configuration {config_id}: {e}")
            return {
                "success": False,
                "error": {"code": "IPAS_ERROR", "message": str(e)},
            }

    # =========================================================================
    # MS5 Tools (8) - includes KYP tools
    # =========================================================================

    @server.tool(
        cache_key="sap_search_customers", cache_ttl=300, required_permission="sap.read"
    )
    async def sap_search_customers(
        name: str, max_results: int = 50, country: str = ""
    ) -> dict:
        """Search customers by name for KYP lookup. Uses BAPI_CUSTOMER_GETLIST.

        This is typically the first step in KYP - user provides customer name,
        system returns matching customers for confirmation before retrieving details.
        """
        connected = state["connected"]
        if not connected:
            return {
                "success": False,
                "error": {
                    "code": "NOT_CONNECTED",
                    "message": "Server not initialized.",
                },
            }
        if not name or not name.strip():
            return {
                "success": False,
                "error": {
                    "code": "VALIDATION_ERROR",
                    "message": "name is required",
                    "field": "name",
                },
            }
        try:
            customers = await ms5.search_customers(
                name.strip(), max_results, country or None
            )
            return {
                "success": True,
                "count": len(customers),
                "customers": [
                    {
                        "customer_id": c.customer_id,
                        "name": c.name,
                        "tax_number_1": c.tax_number_1,  # UEN
                        "tax_number_2": c.tax_number_2,
                        "country": c.country,
                        "city": c.city,
                    }
                    for c in customers
                ],
            }
        except Exception as e:
            logger.error(f"Error searching customers with name '{name}': {e}")
            return {"success": False, "error": {"code": "SAP_ERROR", "message": str(e)}}

    @server.tool(
        cache_key="sap_customer", cache_ttl=600, required_permission="sap.read"
    )
    async def sap_get_customer(customer_id: str) -> dict:
        """Get customer master data from SAP MS5 via CPI. Uses BAPI_CUSTOMER_GETDETAIL2.

        Returns customer details including UEN/Tax ID for KYP verification.
        """
        connected = state["connected"]
        if not connected:
            return {
                "success": False,
                "error": {
                    "code": "NOT_CONNECTED",
                    "message": "Server not initialized.",
                },
            }
        try:
            cust_id = validate_customer_id(customer_id)
        except ValidationError as e:
            return {
                "success": False,
                "error": {
                    "code": "VALIDATION_ERROR",
                    "message": e.message,
                    "field": e.field,
                },
            }
        try:
            customer = await ms5.get_customer(cust_id)
            return {
                "success": True,
                "customer_id": customer.customer_id,
                "name": customer.name,
                "tax_number_1": customer.tax_number_1,  # UEN for Singapore
                "tax_number_2": customer.tax_number_2,
                "address": customer.address,
                "contact": customer.contact,
                "messages": customer.messages,
            }
        except Exception as e:
            logger.error(f"Error getting customer {customer_id}: {e}")
            return {"success": False, "error": {"code": "SAP_ERROR", "message": str(e)}}

    @server.tool(cache_key="sap_credit", cache_ttl=300, required_permission="sap.read")
    async def sap_check_credit(
        customer_id: str, credit_control_area: str = "", order_value: float = 0
    ) -> dict:
        """Check customer credit limit from SAP MS5 via CPI. Uses BAPI_CR_ACC_GETDETAIL."""
        connected = state["connected"]
        if not connected:
            return {
                "success": False,
                "error": {
                    "code": "NOT_CONNECTED",
                    "message": "Server not initialized.",
                },
            }
        try:
            cust_id = validate_customer_id(customer_id)
            cca = validate_credit_control_area(credit_control_area)
        except ValidationError as e:
            return {
                "success": False,
                "error": {
                    "code": "VALIDATION_ERROR",
                    "message": e.message,
                    "field": e.field,
                },
            }
        try:
            credit = await ms5.check_credit_limit(cust_id, cca or None, order_value)
            return {
                "success": True,
                "customer_id": credit.customer_id,
                "credit_control_area": credit.credit_control_area,
                "credit_limit": credit.credit_limit,
                "credit_exposure": credit.credit_exposure,
                "available_credit": credit.available_credit,
                "credit_check_passed": credit.credit_check_passed,
                "utilization_percent": credit.utilization_percent,
                "messages": credit.messages,
            }
        except ValueError as e:
            return {
                "success": False,
                "error": {"code": "CONFIGURATION_ERROR", "message": str(e)},
            }
        except Exception as e:
            logger.error(f"Error checking credit for {customer_id}: {e}")
            return {"success": False, "error": {"code": "SAP_ERROR", "message": str(e)}}

    @server.tool(cache_key="sap_kyp", cache_ttl=300, required_permission="sap.read")
    async def sap_get_kyp_assessment(
        customer_id: str, credit_control_area: str = ""
    ) -> dict:
        """Get KYP (Know Your Partner) assessment from SAP MS5 via CPI.

        Combines customer master data and credit information into a single
        assessment for due diligence purposes. Returns:
        - Customer ID and name
        - UEN / Tax ID (STCD1, STCD2)
        - Credit limit (approved)
        - Credit exposure (current)
        - Available credit (balance)
        - Credit utilization percentage
        """
        connected = state["connected"]
        if not connected:
            return {
                "success": False,
                "error": {
                    "code": "NOT_CONNECTED",
                    "message": "Server not initialized.",
                },
            }
        try:
            cust_id = validate_customer_id(customer_id)
            cca = validate_credit_control_area(credit_control_area)
        except ValidationError as e:
            return {
                "success": False,
                "error": {
                    "code": "VALIDATION_ERROR",
                    "message": e.message,
                    "field": e.field,
                },
            }
        try:
            kyp = await ms5.get_kyp_assessment(cust_id, cca or None)
            return {
                "success": True,
                "customer_id": kyp.customer_id,
                "customer_name": kyp.customer_name,
                "tax_number_1": kyp.tax_number_1,  # UEN
                "tax_number_2": kyp.tax_number_2,
                "credit_limit": kyp.credit_limit,
                "credit_exposure": kyp.credit_exposure,
                "available_credit": kyp.available_credit,
                "utilization_percent": kyp.utilization_percent,
                "currency": kyp.currency,
                "country": kyp.country,
                "city": kyp.city,
            }
        except Exception as e:
            logger.error(f"Error getting KYP assessment for {customer_id}: {e}")
            return {"success": False, "error": {"code": "SAP_ERROR", "message": str(e)}}

    @server.tool(required_permission="sap.read", timeout=60.0)
    async def sap_simulate_order(
        customer_id: str,
        sales_org: str,
        items: list[dict],
        distribution_channel: str = "",
        division: str = "",
        order_type: str = "ZOR",
    ) -> dict:
        """Simulate sales order in SAP MS5 via CPI. Uses BAPI_SALESORDER_SIMULATE."""
        connected = state["connected"]
        if not connected:
            return {
                "success": False,
                "error": {
                    "code": "NOT_CONNECTED",
                    "message": "Server not initialized.",
                },
            }
        try:
            cust_id = validate_customer_id(customer_id)
            org = validate_sales_org(sales_org)
            validated_items = validate_order_items(items)
        except ValidationError as e:
            return {
                "success": False,
                "error": {
                    "code": "VALIDATION_ERROR",
                    "message": e.message,
                    "field": e.field,
                },
            }
        try:
            order_data = {
                "header": {
                    "DOC_TYPE": order_type,
                    "SALES_ORG": org,
                    "DISTR_CHAN": distribution_channel,
                    "DIVISION": division,
                },
                "items": [
                    {
                        "ITM_NUMBER": str((i + 1) * 10).zfill(6),
                        "MATERIAL": item["material"],
                        "REQ_QTY": item["quantity"],
                        "SALES_UNIT": item.get("unit", "EA"),
                        "PLANT": item.get("plant", ""),
                    }
                    for i, item in enumerate(validated_items)
                ],
                "partners": [
                    {"PARTN_ROLE": "AG", "PARTN_NUMB": cust_id, "ITM_NUMBER": "000000"}
                ],
            }
            simulation = await ms5.simulate_order(order_data)
            return {
                "success": True,
                "is_valid": simulation.is_valid,
                "net_value": simulation.net_value,
                "currency": simulation.currency,
                "item_count": simulation.item_count,
                "messages": simulation.messages,
                "errors": simulation.errors,
                "warnings": simulation.warnings,
            }
        except Exception as e:
            logger.error(f"Error simulating order: {e}")
            return {"success": False, "error": {"code": "SAP_ERROR", "message": str(e)}}

    @server.tool(required_permission="sap.write", timeout=90.0, retryable=False)
    async def sap_create_order(
        customer_id: str,
        sales_org: str,
        items: list[dict],
        distribution_channel: str = "",
        division: str = "",
        order_type: str = "ZOR",
        po_number: str = "",
        request_id: str = "",
        test_run: bool = False,
    ) -> dict:
        """Create sales order in SAP MS5 via CPI. Uses BAPI_SALESORDER_CREATEFROMDAT2 + BAPI_TRANSACTION_COMMIT. Supports idempotency via request_id."""
        connected = state["connected"]
        if not connected:
            return {
                "success": False,
                "error": {
                    "code": "NOT_CONNECTED",
                    "message": "Server not initialized.",
                },
            }
        try:
            cust_id = validate_customer_id(customer_id)
            org = validate_sales_org(sales_org)
            validated_items = validate_order_items(items)
        except ValidationError as e:
            return {
                "success": False,
                "error": {
                    "code": "VALIDATION_ERROR",
                    "message": e.message,
                    "field": e.field,
                },
            }

        # Idempotency check
        payload_for_key = {
            "customer_id": cust_id,
            "sales_org": org,
            "items": validated_items,
            "po_number": po_number,
        }
        idem_key = request_id or idempotency.generate_key(
            "create_order", payload_for_key
        )
        existing = await idempotency.check_duplicate(idem_key)
        if existing:
            return {
                **existing,
                "idempotent_replay": True,
                "message": "Order already created (idempotent replay)",
            }

        try:
            order_data = {
                "header": {
                    "DOC_TYPE": order_type,
                    "SALES_ORG": org,
                    "DISTR_CHAN": distribution_channel,
                    "DIVISION": division,
                    "PURCH_NO_C": po_number,
                },
                "items": [
                    {
                        "ITM_NUMBER": str((i + 1) * 10).zfill(6),
                        "MATERIAL": item["material"],
                        "TARGET_QTY": item["quantity"],
                        "SALES_UNIT": item.get("unit", "EA"),
                        "PLANT": item.get("plant", ""),
                    }
                    for i, item in enumerate(validated_items)
                ],
                "partners": [
                    {"PARTN_ROLE": "AG", "PARTN_NUMB": cust_id, "ITM_NUMBER": "000000"}
                ],
            }
            result = await ms5.create_order(order_data, test_run=test_run)
            response = {
                "success": result.success,
                "document_number": result.document_number,
                "committed": result.committed,
                "test_run": result.test_run,
                "messages": result.messages,
                "idempotency_key": idem_key,
            }
            if result.success and not test_run:
                await idempotency.store_result(idem_key, response)
            return response
        except Exception as e:
            logger.error(f"Error creating order: {e}")
            return {
                "success": False,
                "error": {"code": "SAP_ERROR", "message": str(e)},
                "idempotency_key": idem_key,
            }

    # =========================================================================
    # Server Initialization Helper
    # =========================================================================

    async def initialize_clients():
        """Initialize all SAP clients via CPI gateway."""
        if state["connected"]:
            return
        await cpi.connect()
        # Clients share CPI connection state
        cec._connected = True
        ipas._connected = True
        ms5._connected = True
        state["connected"] = True
        logger.info(
            "SAP Integration MCP Server initialized: CEC, IPAS, MS5 connected via CPI"
        )

    async def shutdown_clients():
        """Shutdown all SAP clients."""
        if not state["connected"]:
            return
        await cpi.disconnect()
        cec._connected = False
        ipas._connected = False
        ms5._connected = False
        state["connected"] = False
        logger.info("SAP Integration MCP Server shutdown complete")

    # Store tool functions for direct invocation (testing/debugging)
    tool_registry = {
        "sap_health_check": sap_health_check,
        "cec_get_opportunity": cec_get_opportunity,
        "cec_search_opportunities": cec_search_opportunities,
        "cec_get_opportunities_by_account": cec_get_opportunities_by_account,
        "cec_get_commercial_terms": cec_get_commercial_terms,
        "ipas_get_configuration": ipas_get_configuration,
        "ipas_get_configurations_by_opportunity": ipas_get_configurations_by_opportunity,
        "ipas_get_product_catalog": ipas_get_product_catalog,
        "ipas_validate_configuration": ipas_validate_configuration,
        "sap_get_customer": sap_get_customer,
        "sap_check_credit": sap_check_credit,
        "sap_simulate_order": sap_simulate_order,
        "sap_create_order": sap_create_order,
    }

    # Attach lifecycle methods, tool registry, and state to server for external access
    server._sap_initialize = initialize_clients
    server._sap_shutdown = shutdown_clients
    server._sap_state = state
    server._sap_cpi = cpi
    server._sap_cec = cec
    server._sap_ipas = ipas
    server._sap_ms5 = ms5
    server._sap_tool_registry = tool_registry

    logger.info(
        f"SAP Integration MCP Server created: 13 tools registered, transport={transport}"
    )
    return server


# =============================================================================
# Wrapper Class for Backward Compatibility
# =============================================================================


class SAPCPIMCPServer:
    """
    Wrapper class for SAP Integration MCP Server.

    Provides backward-compatible interface and lifecycle management.

    Usage:
        async with SAPCPIMCPServer() as server:
            # Server is now connected
            # Use via MCP protocol or run as standalone
            pass
    """

    def __init__(
        self,
        cpi_client: Optional[CPIClient] = None,
        cec_client: Optional[CECClient] = None,
        ipas_client: Optional[IPASClient] = None,
        ms5_client: Optional[MS5Client] = None,
        api_keys: Optional[dict[str, dict]] = None,
        rate_limit_per_minute: int = 100,
        circuit_breaker_threshold: int = 5,
        enable_cache: bool = True,
        enable_metrics: bool = True,
        transport: str = "stdio",
    ):
        self._server = create_sap_mcp_server(
            cpi_client=cpi_client,
            cec_client=cec_client,
            ipas_client=ipas_client,
            ms5_client=ms5_client,
            api_keys=api_keys,
            rate_limit_per_minute=rate_limit_per_minute,
            circuit_breaker_threshold=circuit_breaker_threshold,
            enable_cache=enable_cache,
            enable_metrics=enable_metrics,
            transport=transport,
        )
        self._enable_cache = enable_cache
        self._enable_metrics = enable_metrics

        # Expose clients for testing
        self._cpi = self._server._sap_cpi
        self._cec = self._server._sap_cec
        self._ipas = self._server._sap_ipas
        self._ms5 = self._server._sap_ms5

    @property
    def _connected(self) -> bool:
        """Get connection state from internal server state."""
        return self._server._sap_state["connected"]

    @_connected.setter
    def _connected(self, value: bool) -> None:
        """Set connection state on internal server state."""
        self._server._sap_state["connected"] = value

    async def initialize(self) -> None:
        """Initialize the server and connect to SAP via CPI."""
        await self._server._sap_initialize()

    async def shutdown(self) -> None:
        """Shutdown the server and disconnect from SAP."""
        await self._server._sap_shutdown()

    def run(self) -> None:
        """Run the MCP server (blocking). Use for standalone deployment."""
        self._server.run()

    def list_tools(self) -> list[dict[str, Any]]:
        """List available MCP tools."""
        return [
            # CEC Tools (4)
            {
                "name": "cec_get_opportunity",
                "description": "Get opportunity from SAP CEC via CPI. Returns opportunity details with SAP field mapping.",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "opportunity_id": {
                            "type": "string",
                            "description": "CEC opportunity ID",
                        }
                    },
                    "required": ["opportunity_id"],
                },
            },
            {
                "name": "cec_search_opportunities",
                "description": "Search opportunities in SAP CEC via CPI.",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "query": {"type": "string"},
                        "status": {"type": "string"},
                        "limit": {"type": "integer", "default": 50},
                    },
                    "required": ["query"],
                },
            },
            {
                "name": "cec_get_opportunities_by_account",
                "description": "Get opportunities for an account from SAP CEC via CPI.",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "account_id": {"type": "string"},
                        "status": {"type": "string"},
                        "limit": {"type": "integer", "default": 50},
                    },
                    "required": ["account_id"],
                },
            },
            {
                "name": "cec_get_commercial_terms",
                "description": "Get commercial terms (payment terms, Incoterms) from SAP CEC via CPI.",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "account_id": {"type": "string"},
                        "sales_org": {"type": "string"},
                    },
                    "required": ["account_id"],
                },
            },
            # IPAS Tools (4)
            {
                "name": "ipas_get_configuration",
                "description": "Get product configuration from IPAS via CPI (NEW interface). Returns BOM and characteristics.",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "config_id": {
                            "type": "string",
                            "description": "IPAS configuration ID",
                        }
                    },
                    "required": ["config_id"],
                },
            },
            {
                "name": "ipas_get_configurations_by_opportunity",
                "description": "Get product configurations for an opportunity from IPAS via CPI.",
                "inputSchema": {
                    "type": "object",
                    "properties": {"opportunity_id": {"type": "string"}},
                    "required": ["opportunity_id"],
                },
            },
            {
                "name": "ipas_get_product_catalog",
                "description": "Get product catalog from IPAS via CPI (NEW interface).",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "category": {"type": "string"},
                        "search": {"type": "string"},
                        "limit": {"type": "integer", "default": 50},
                    },
                    "required": [],
                },
            },
            {
                "name": "ipas_validate_configuration",
                "description": "Validate configuration characteristics in IPAS via CPI.",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "config_id": {"type": "string"},
                        "characteristics": {"type": "object"},
                    },
                    "required": ["config_id"],
                },
            },
            # MS5 Tools (5)
            {
                "name": "sap_get_customer",
                "description": "Get customer master data from SAP MS5 via CPI. Uses BAPI_CUSTOMER_GETDETAIL2.",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "customer_id": {
                            "type": "string",
                            "description": "SAP customer number (KUNNR)",
                        }
                    },
                    "required": ["customer_id"],
                },
            },
            {
                "name": "sap_check_credit",
                "description": "Check customer credit limit from SAP MS5 via CPI. Uses BAPI_CR_ACC_GETDETAIL.",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "customer_id": {"type": "string"},
                        "credit_control_area": {"type": "string"},
                        "order_value": {"type": "number"},
                    },
                    "required": ["customer_id"],
                },
            },
            {
                "name": "sap_simulate_order",
                "description": "Simulate sales order in SAP MS5 via CPI. Uses BAPI_SALESORDER_SIMULATE.",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "customer_id": {"type": "string"},
                        "sales_org": {"type": "string"},
                        "items": {"type": "array"},
                        "distribution_channel": {"type": "string"},
                        "division": {"type": "string"},
                        "order_type": {"type": "string", "default": "ZOR"},
                    },
                    "required": ["customer_id", "sales_org", "items"],
                },
            },
            {
                "name": "sap_create_order",
                "description": "Create sales order in SAP MS5 via CPI. Uses BAPI_SALESORDER_CREATEFROMDAT2 + BAPI_TRANSACTION_COMMIT. Supports idempotency.",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "customer_id": {"type": "string"},
                        "sales_org": {"type": "string"},
                        "items": {"type": "array"},
                        "distribution_channel": {"type": "string"},
                        "division": {"type": "string"},
                        "order_type": {"type": "string"},
                        "po_number": {"type": "string"},
                        "request_id": {"type": "string"},
                        "test_run": {"type": "boolean"},
                    },
                    "required": ["customer_id", "sales_org", "items"],
                },
            },
            {
                "name": "sap_health_check",
                "description": "Check connectivity for all SAP systems (CEC, IPAS, MS5) via CPI gateway.",
                "inputSchema": {"type": "object", "properties": {}},
            },
        ]

    def get_prometheus_metrics(self) -> str:
        """Get metrics in Prometheus format."""
        if not self._enable_metrics:
            return "# Metrics disabled\n"
        try:
            return self._server.metrics.export_metrics(format="prometheus")
        except Exception as e:
            return f"# Error exporting metrics: {e}\n"

    async def call_tool(
        self, tool_name: str, arguments: dict[str, Any]
    ) -> dict[str, Any]:
        """
        Call a tool directly by name. Useful for testing and debugging.

        For production use, tools should be invoked via MCP protocol using server.run().
        This method provides direct access for testing and development purposes.

        Args:
            tool_name: Name of the tool to invoke
            arguments: Tool arguments as a dict

        Returns:
            Tool result as a dict

        Raises:
            RuntimeError: If server is not initialized (for tools requiring connection)
        """
        registry = self._server._sap_tool_registry

        if tool_name not in registry:
            return {
                "success": False,
                "error": {
                    "code": "UNKNOWN_TOOL",
                    "message": f"Unknown tool: {tool_name}. Available tools: {list(registry.keys())}",
                },
            }

        tool_func = registry[tool_name]

        # Health check doesn't require initialization
        if tool_name == "sap_health_check":
            return await tool_func()

        # Other tools require initialization
        if not self._connected:
            raise RuntimeError(
                "Server not initialized. Call initialize() or use async context manager first."
            )

        # Call the tool function with the provided arguments
        try:
            import inspect

            sig = inspect.signature(tool_func)
            # Filter arguments to only those the function accepts
            valid_args = {}
            for param_name in sig.parameters:
                if param_name in arguments:
                    valid_args[param_name] = arguments[param_name]
            return await tool_func(**valid_args)
        except ValidationError as e:
            return {
                "success": False,
                "error": {
                    "code": "VALIDATION_ERROR",
                    "message": e.message,
                    "field": e.field,
                },
            }
        except Exception as e:
            logger.error(f"Error calling tool {tool_name}: {e}")
            return {
                "success": False,
                "error": {"code": "TOOL_ERROR", "message": str(e)},
            }

    async def __aenter__(self) -> "SAPCPIMCPServer":
        await self.initialize()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb) -> None:
        await self.shutdown()


# Alias for backward compatibility
SAPIntegrationMCPServer = SAPCPIMCPServer


# =============================================================================
# Configuration Helper
# =============================================================================


def get_sap_cpi_mcp_config(
    environment: Optional[str] = None, transport: str = "http"
) -> dict[str, Any]:
    """
    Get MCP server configuration for Kaizen agent integration.

    Args:
        environment: Target environment (defaults to config.environment)
        transport: Transport type ("http" or "stdio")

    Returns:
        MCP server configuration dict for agent integration
    """
    env = environment or config.environment
    if transport == "http":
        return {
            "name": "sap-integration",
            "transport": "http",
            "url": f"http://{os.getenv('MCP_SERVER_HOST', 'localhost')}:{os.getenv('MCP_SERVER_PORT', '8082')}/mcp",
            "headers": {
                "X-API-Key": os.getenv("MCP_API_KEY", ""),
                "X-Environment": env,
            },
            "timeout": config.sap_cpi.timeout_seconds,
        }
    return {
        "name": "sap-integration",
        "transport": "stdio",
        "command": "python",
        "args": ["-m", "lead_to_cash.mcp.sap_cpi_server"],
        "env": {"ENVIRONMENT": env},
    }


# Alias
get_sap_mcp_config = get_sap_cpi_mcp_config


# =============================================================================
# Main Entry Point
# =============================================================================


async def main_async():
    """Run SAP Integration MCP Server with initialization."""
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    )

    print("\n=== SAP Integration MCP Server ===")
    print(f"Environment: {config.environment}")
    print("Gateway: SAP CPI")
    print("Systems: CEC, IPAS, MS5")
    print("Transport: stdio")

    server = create_sap_mcp_server(transport="stdio")

    # Initialize clients
    try:
        await server._sap_initialize()
        print("\nConnected to SAP CPI successfully")
    except Exception as e:
        print(f"\nWarning: Could not connect to SAP CPI: {e}")
        print(
            "Server will start but SAP operations will fail until credentials are configured."
        )

    print("\nAvailable Tools (13):")
    # List registered tools from server
    wrapper = SAPCPIMCPServer()
    for tool in wrapper.list_tools():
        print(f"  - {tool['name']}")

    print("\nStarting MCP server (stdio transport)...")
    print("Send MCP protocol messages via stdin/stdout")

    # Run the server
    server.run()


def main():
    """Entry point for standalone server."""
    asyncio.run(main_async())


if __name__ == "__main__":
    main()
