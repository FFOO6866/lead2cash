"""
SAP CPI (Cloud Platform Integration) Client

Handles OAuth 2.0 authentication, CSRF token management, and API calls to SAP CPI.
Environments: DEV, QA, PROD
"""

import json
import logging
import xml.etree.ElementTree as _ET_stdlib
import defusedxml.ElementTree as ET  # Safe parsing (parse, fromstring)

# defusedxml only wraps parsing functions. For Element type hints
# and XML construction (which are safe), use stdlib.
_Element = _ET_stdlib.Element
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from typing import Any, Optional

import httpx

from lead_to_cash.config import config

logger = logging.getLogger(__name__)


@dataclass
class OAuthToken:
    """OAuth 2.0 token container."""

    access_token: str
    token_type: str
    expires_at: datetime
    scope: Optional[str] = None

    @property
    def is_expired(self) -> bool:
        """Check if token is expired (with 60s buffer)."""
        return datetime.now(timezone.utc) >= (self.expires_at - timedelta(seconds=60))


@dataclass
class CSRFToken:
    """CSRF token container with associated session cookies."""

    token: str
    cookies: dict[str, str] = field(default_factory=dict)
    fetched_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    @property
    def is_expired(self) -> bool:
        """Check if CSRF token is expired (5 minute TTL)."""
        return datetime.now(timezone.utc) >= (self.fetched_at + timedelta(minutes=5))


class CPIClient:
    """SAP CPI Integration Client.

    Provides authenticated access to SAP CPI iFlows and APIs.
    Handles OAuth 2.0 authentication and CSRF token management.

    Usage:
        client = CPIClient()
        await client.connect()

        # Call iFlow (CSRF token handled automatically)
        result = await client.call_iflow(
            iflow_name="Integrum/RequestTableData",
            payload={"customer_id": "1234"}
        )
    """

    def __init__(
        self,
        environment: Optional[str] = None,
        client_id: Optional[str] = None,
        client_secret: Optional[str] = None,
    ):
        """Initialize CPI client.

        Args:
            environment: Target environment (development/qa/production)
            client_id: OAuth client ID (defaults to config)
            client_secret: OAuth client secret (defaults to config)
        """
        self.environment = environment or config.environment
        self.base_url = config.sap_cpi.get_url(self.environment)
        self.client_id = client_id or config.sap_cpi.client_id
        self.client_secret = client_secret or config.sap_cpi.client_secret
        self.token_url = config.sap_cpi.token_url
        self.timeout = config.sap_cpi.timeout_seconds
        self.retry_attempts = config.sap_cpi.retry_attempts

        self._token: Optional[OAuthToken] = None
        self._csrf_token: Optional[CSRFToken] = None
        self._client: Optional[httpx.AsyncClient] = None

    async def connect(self) -> None:
        """Establish connection and obtain OAuth token.

        Raises:
            ValueError: If CPI credentials are not configured
        """
        if not self.client_id or not self.client_secret:
            raise ValueError(
                "CPI credentials not configured. "
                "Set SAP_CPI_CLIENT_ID and SAP_CPI_CLIENT_SECRET environment variables."
            )

        if not self.token_url:
            raise ValueError(
                "CPI token URL not configured. "
                "Set SAP_CPI_TOKEN_URL environment variable."
            )

        self._client = httpx.AsyncClient(timeout=self.timeout)
        await self._refresh_token()
        logger.info(f"Connected to SAP CPI ({self.environment}): {self.base_url}")

    async def disconnect(self) -> None:
        """Close connection."""
        if self._client:
            await self._client.aclose()
            self._client = None
        self._token = None
        self._csrf_token = None
        logger.info("Disconnected from SAP CPI")

    async def _refresh_token(self) -> None:
        """Refresh OAuth 2.0 access token."""
        if not self.token_url or not self._client:
            return

        response = await self._client.post(
            self.token_url,
            data={
                "grant_type": "client_credentials",
                "client_id": self.client_id,
                "client_secret": self.client_secret,
            },
        )
        response.raise_for_status()
        data = response.json()

        self._token = OAuthToken(
            access_token=data["access_token"],
            token_type=data.get("token_type", "Bearer"),
            expires_at=datetime.now(timezone.utc)
            + timedelta(seconds=data["expires_in"]),
            scope=data.get("scope"),
        )
        # Invalidate CSRF token when OAuth token is refreshed
        self._csrf_token = None
        logger.debug("OAuth token refreshed")

    async def _ensure_token(self) -> Optional[str]:
        """Ensure valid OAuth token is available."""
        if self._token and self._token.is_expired:
            await self._refresh_token()
        return self._token.access_token if self._token else None

    async def _fetch_csrf_token(self, url: str) -> CSRFToken:
        """Fetch CSRF token from SAP CPI.

        SAP CPI requires CSRF tokens for state-changing requests (POST, PUT, DELETE).
        The token is fetched via a GET request with 'x-csrf-token: fetch' header.

        Args:
            url: The iFlow URL to fetch CSRF token from

        Returns:
            CSRFToken with token value and session cookies

        Raises:
            httpx.HTTPStatusError: If CSRF token fetch fails
        """
        if not self._client:
            raise RuntimeError("CPI client not connected")

        token = await self._ensure_token()
        headers = {
            "Authorization": f"Bearer {token}",
            "x-csrf-token": "fetch",
        }

        response = await self._client.get(url, headers=headers)
        response.raise_for_status()

        csrf_token = response.headers.get("x-csrf-token", "")
        cookies = dict(response.cookies)

        if not csrf_token:
            logger.warning("No CSRF token returned from SAP CPI")

        self._csrf_token = CSRFToken(token=csrf_token, cookies=cookies)
        # Security: Do not log token value to prevent exposure in logs
        logger.debug("CSRF token fetched successfully")

        return self._csrf_token

    async def _ensure_csrf_token(self, url: str) -> CSRFToken:
        """Ensure valid CSRF token is available.

        Args:
            url: The iFlow URL to fetch CSRF token from if needed

        Returns:
            Valid CSRFToken
        """
        if self._csrf_token is None or self._csrf_token.is_expired:
            await self._fetch_csrf_token(url)
        return self._csrf_token

    async def call_iflow(
        self,
        iflow_name: str,
        payload: dict[str, Any] | str,
        method: str = "POST",
        content_type: str = "application/xml",
    ) -> dict[str, Any]:
        """Call SAP CPI iFlow.

        Automatically handles CSRF token for POST/PUT/DELETE requests.

        Args:
            iflow_name: Name/path of the iFlow (e.g., "Integrum/RequestTableData")
            payload: Request payload (dict for JSON, str for XML)
            method: HTTP method (GET, POST, PUT, DELETE)
            content_type: Content type (application/json or application/xml)

        Returns:
            Response data from iFlow (parsed as JSON)

        Raises:
            httpx.HTTPStatusError: On HTTP errors
            RuntimeError: If client not connected
        """
        # Build iFlow URL
        # Support both legacy format and direct path
        if iflow_name.startswith("/"):
            iflow_path = iflow_name
        elif "/" in iflow_name:
            # Direct path like "Integrum/RequestTableData"
            iflow_path = f"/http/{iflow_name}"
        else:
            # Legacy format: RRPS - Integrum - {iflow_name}
            iflow_path = f"/http/{config.sap_cpi.package_prefix} - {iflow_name}"

        url = f"{self.base_url}{iflow_path}"

        if not self._client:
            raise RuntimeError(
                "CPI client not connected. Call connect() first or use async context manager."
            )

        token = await self._ensure_token()
        headers: dict[str, str] = {
            "Content-Type": content_type,
            "Accept": "application/json",  # Always accept JSON response
            "Authorization": f"Bearer {token}",
        }

        # Fetch CSRF token for state-changing methods
        cookies: dict[str, str] = {}
        if method.upper() in ("POST", "PUT", "DELETE", "PATCH"):
            csrf = await self._ensure_csrf_token(url)
            headers["x-csrf-token"] = csrf.token
            cookies = csrf.cookies

        # Prepare request body
        if content_type == "application/json":
            request_json = payload if isinstance(payload, dict) else None
            request_content = payload if isinstance(payload, str) else None
        else:
            # XML or other content types
            request_json = None
            if isinstance(payload, str):
                request_content = payload
            elif isinstance(payload, dict):
                # Convert dict to simple XML (for backwards compatibility)
                request_content = self._dict_to_xml(payload)
            else:
                request_content = str(payload)

        # Execute with retry logic
        last_error: Optional[Exception] = None
        for attempt in range(self.retry_attempts):
            try:
                if method.upper() == "GET":
                    response = await self._client.get(
                        url,
                        headers=headers,
                        params=payload if isinstance(payload, dict) else None,
                        cookies=cookies,
                    )
                else:
                    response = await self._client.request(
                        method=method,
                        url=url,
                        headers=headers,
                        json=request_json,
                        content=request_content if not request_json else None,
                        cookies=cookies,
                    )

                response.raise_for_status()

                # Parse response (handle both JSON and XML responses)
                response_text = response.text
                if response_text:
                    try:
                        return response.json()
                    except (ValueError, json.JSONDecodeError):
                        # If JSON parsing fails, try XML parsing
                        try:
                            return self._parse_xml_response(response_text)
                        except (ValueError, ET.ParseError) as xml_err:
                            logger.warning(f"XML parsing failed: {xml_err}")
                            return {"raw_response": response_text}
                return {}

            except httpx.HTTPStatusError as e:
                last_error = e
                status_code = e.response.status_code

                if status_code == 401:
                    # OAuth token invalid, refresh and retry
                    logger.warning("OAuth token invalid, refreshing...")
                    await self._refresh_token()
                    token = await self._ensure_token()
                    headers["Authorization"] = f"Bearer {token}"
                    continue

                elif status_code == 403:
                    # CSRF token might be invalid, refresh and retry
                    if "x-csrf-token" in str(e.response.headers).lower():
                        logger.warning("CSRF token invalid, refreshing...")
                        self._csrf_token = None
                        csrf = await self._ensure_csrf_token(url)
                        headers["x-csrf-token"] = csrf.token
                        cookies = csrf.cookies
                        continue
                    raise

                elif status_code >= 500:
                    # Server error, retry
                    logger.warning(f"CPI server error (attempt {attempt + 1}): {e}")
                    continue

                else:
                    raise

            except httpx.RequestError as e:
                last_error = e
                logger.warning(f"CPI request error (attempt {attempt + 1}): {e}")
                continue

        if last_error:
            raise last_error
        return {}

    def _dict_to_xml(self, data: dict[str, Any], root_tag: str = "Request") -> str:
        """Convert a dictionary to simple XML.

        Args:
            data: Dictionary to convert
            root_tag: Root element tag name

        Returns:
            XML string
        """
        from xml.sax.saxutils import escape

        def _to_xml(obj: Any, tag: str) -> str:
            if isinstance(obj, dict):
                inner = "".join(_to_xml(v, k) for k, v in obj.items())
                return f"<{tag}>{inner}</{tag}>"
            elif isinstance(obj, list):
                return "".join(_to_xml(item, tag) for item in obj)
            else:
                return f"<{tag}>{escape(str(obj))}</{tag}>"

        xml_body = "".join(_to_xml(v, k) for k, v in data.items())
        return (
            f'<?xml version="1.0" encoding="UTF-8"?><{root_tag}>{xml_body}</{root_tag}>'
        )

    def _parse_xml_response(self, xml_text: str) -> dict[str, Any]:
        """Parse SAP CPI XML response to dictionary.

        Converts XML response from SAP CPI to a dict structure compatible
        with the expected JSON format used by ms5_client and other consumers.

        Args:
            xml_text: Raw XML response string

        Returns:
            Dictionary representation of XML data

        Raises:
            ET.ParseError: If XML is malformed
        """
        root = ET.fromstring(xml_text)

        def _element_to_dict(element: _Element) -> Any:
            """Recursively convert XML element to dict/list/value."""
            # Check if element has children
            children = list(element)
            if not children:
                # Leaf node - return text content
                text = element.text
                if text is None:
                    return ""
                text = text.strip()
                # Try to convert to number
                try:
                    if "." in text:
                        return float(text)
                    return int(text)
                except ValueError:
                    return text

            # Handle child elements
            result: dict[str, Any] = {}
            for child in children:
                child_tag = child.tag.split("}")[-1] if "}" in child.tag else child.tag
                child_value = _element_to_dict(child)

                if child_tag in result:
                    # Convert to list if duplicate keys
                    if not isinstance(result[child_tag], list):
                        result[child_tag] = [result[child_tag]]
                    result[child_tag].append(child_value)
                else:
                    result[child_tag] = child_value

            return result

        # Convert root element
        parsed = _element_to_dict(root)

        # If result is a dict with a single key matching root tag, unwrap it
        if isinstance(parsed, dict) and len(parsed) == 1:
            root_tag = root.tag.split("}")[-1] if "}" in root.tag else root.tag
            if root_tag in parsed:
                return parsed[root_tag]

        return parsed if isinstance(parsed, dict) else {"value": parsed}

    async def call_iflow_raw(
        self,
        iflow_name: str,
        xml_payload: str,
        method: str = "POST",
    ) -> dict[str, Any]:
        """Call SAP CPI iFlow with raw XML payload.

        Convenience method for sending pre-formatted XML.

        Args:
            iflow_name: Name/path of the iFlow
            xml_payload: Raw XML string to send
            method: HTTP method

        Returns:
            Response data from iFlow
        """
        return await self.call_iflow(
            iflow_name=iflow_name,
            payload=xml_payload,
            method=method,
            content_type="application/xml",
        )

    async def health_check(self) -> dict[str, Any]:
        """Check CPI connectivity."""
        return {
            "status": "configured" if self.client_id else "not_configured",
            "environment": self.environment,
            "base_url": self.base_url,
            "connected": self._client is not None,
            "token_valid": self._token is not None and not self._token.is_expired,
            "csrf_token_valid": (
                self._csrf_token is not None and not self._csrf_token.is_expired
            ),
        }

    async def __aenter__(self) -> "CPIClient":
        """Async context manager entry."""
        await self.connect()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb) -> None:
        """Async context manager exit."""
        await self.disconnect()
