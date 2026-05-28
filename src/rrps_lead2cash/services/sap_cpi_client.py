"""
SAP CPI (Cloud Platform Integration) Client.

Handles OAuth2 authentication, CSRF tokens, and calls to SAP CPI iFlows:
- Integrum/RequestTableData: Customer master + credit check (BAPI_CUSTOMER_GETDETAIL2 + BAPI_CR_ACC_GETDETAIL)
- Integrum/GetOpportunity: CEC opportunity retrieval

Auth flow:
1. POST client_credentials to token URL -> Bearer token
2. GET CSRF token from CPI endpoint
3. POST XML payload with Bearer + CSRF headers
"""

import logging
import os
import re
import xml.etree.ElementTree as ET
from typing import Any, Dict, List, Optional

import defusedxml.ElementTree as SafeET  # M0-T07: XXE-safe parsing for external input
import requests

logger = logging.getLogger(__name__)


class SAPCPIClient:
    """
    Client for SAP CPI iFlow calls.

    Uses OAuth2 client_credentials + CSRF token authentication.
    """

    # Input validation patterns (M0-T05)
    _CUSTOMER_ID_RE = re.compile(r"^[0-9]{1,10}$")
    _CCA_RE = re.compile(r"^[0-9A-Z]{1,10}$")

    def __init__(self) -> None:
        # M1-T05: support both env var names (production uses SAP_CPI_DEV_URL)
        self._base_url = os.getenv("SAP_CPI_BASE_URL", "") or os.getenv(
            "SAP_CPI_DEV_URL", ""
        )
        self._token_url = os.getenv("SAP_CPI_TOKEN_URL", "")
        self._client_id = os.getenv("SAP_CPI_CLIENT_ID", "")
        self._client_secret = os.getenv("SAP_CPI_CLIENT_SECRET", "")
        self._kyp_iflow = os.getenv("SAP_CPI_KYP_IFLOW", "Integrum/RequestTableData")
        self._opp_iflow = os.getenv(
            "SAP_CPI_OPPORTUNITY_IFLOW", "Integrum/GetOpportunity"
        )
        self._timeout = int(os.getenv("SAP_CPI_TIMEOUT", "30"))

        # TLS verification — defaults to True (system certs), configurable via env (M0-T04)
        ca_bundle = os.getenv("SAP_CPI_CA_BUNDLE", "")
        if ca_bundle and ca_bundle.lower() not in ("true", "1", "yes"):
            self._verify = ca_bundle  # path to a CA bundle file
        else:
            self._verify = True  # system certs

        # Cached OAuth token with expiry tracking
        self._access_token: Optional[str] = None
        self._token_expires_at: Optional[float] = None  # Unix timestamp

    @property
    def is_configured(self) -> bool:
        """Check if CPI credentials are configured."""
        return bool(
            self._base_url
            and self._token_url
            and self._client_id
            and self._client_secret
        )

    # ------------------------------------------------------------------
    # OAuth2 Token
    # ------------------------------------------------------------------

    def _get_access_token(self, force_refresh: bool = False) -> str:
        """Get OAuth2 Bearer token via client_credentials grant."""
        import time

        # Check if cached token is still valid (with 60s buffer)
        if (
            self._access_token
            and not force_refresh
            and self._token_expires_at
            and time.time() < self._token_expires_at - 60
        ):
            return self._access_token

        if not self.is_configured:
            raise SAPCPIConfigError(
                "SAP CPI credentials not configured (missing BASE_URL, TOKEN_URL, CLIENT_ID, or CLIENT_SECRET)"
            )

        logger.info("Requesting OAuth2 token from %s", self._token_url)
        try:
            resp = requests.post(
                self._token_url,
                data={"grant_type": "client_credentials"},
                auth=(self._client_id, self._client_secret),
                timeout=self._timeout,
                verify=self._verify,
            )
        except requests.exceptions.RequestException as exc:
            raise SAPCPIConnectionError(f"Failed to get OAuth token: {exc}") from exc

        if resp.status_code != 200:
            raise SAPCPIAuthError(
                f"OAuth token request failed: HTTP {resp.status_code}"
            )

        token_data = resp.json()
        self._access_token = token_data["access_token"]
        self._token_expires_at = time.time() + token_data.get("expires_in", 3600)
        return self._access_token

    # ------------------------------------------------------------------
    # CSRF Token
    # ------------------------------------------------------------------

    def _get_csrf_token(self, url: str, _retry: bool = False) -> tuple:
        """Fetch CSRF token from a CPI endpoint. Returns (csrf_token, cookies)."""
        token = self._get_access_token()
        headers = {
            "Authorization": f"Bearer {token}",
            "X-CSRF-Token": "Fetch",
        }
        try:
            resp = requests.get(
                url, headers=headers, timeout=self._timeout, verify=self._verify
            )
        except requests.exceptions.RequestException as exc:
            raise SAPCPIConnectionError(f"Failed to fetch CSRF token: {exc}") from exc

        # Handle expired token during CSRF fetch
        if resp.status_code == 401 and not _retry:
            self._access_token = None
            self._token_expires_at = None
            return self._get_csrf_token(url, _retry=True)

        if resp.status_code not in (200, 201):
            raise SAPCPIConnectionError(
                f"CSRF token fetch failed: HTTP {resp.status_code}"
            )

        csrf = resp.headers.get("X-CSRF-Token", "")
        return csrf, resp.cookies

    # ------------------------------------------------------------------
    # CPI POST helper
    # ------------------------------------------------------------------

    def _post_to_cpi(
        self, iflow_path: str, xml_payload: str, _retry: bool = False
    ) -> requests.Response:
        """POST XML payload to a CPI iFlow with auth + CSRF."""
        url = f"{self._base_url}/http/{iflow_path}"
        csrf_token, cookies = self._get_csrf_token(url)
        token = self._get_access_token()

        headers = {
            "Authorization": f"Bearer {token}",
            "X-CSRF-Token": csrf_token,
            "Content-Type": "application/xml",
        }

        try:
            resp = requests.post(
                url,
                data=xml_payload.encode("utf-8"),
                headers=headers,
                cookies=cookies,
                timeout=self._timeout,
                verify=self._verify,
            )
        except requests.exceptions.RequestException as exc:
            raise SAPCPIConnectionError(
                f"CPI call to {iflow_path} failed: {exc}"
            ) from exc

        if resp.status_code == 401 and not _retry:
            # Token expired — refresh and retry exactly once
            self._access_token = None
            self._token_expires_at = None
            return self._post_to_cpi(iflow_path, xml_payload, _retry=True)

        if resp.status_code not in (200, 201):
            raise SAPCPIError(
                f"CPI {iflow_path} returned HTTP {resp.status_code}: {resp.text[:500]}"
            )

        return resp

    # ------------------------------------------------------------------
    # Credit Check (BAPI_CR_ACC_GETDETAIL)
    # ------------------------------------------------------------------

    def get_credit_check(
        self, customer_id: str, credit_control_area: str = "0111"
    ) -> Dict[str, Any]:
        """
        Get credit limit and exposure for a customer.

        Args:
            customer_id: 10-digit SAP customer number (e.g., "0022005992")
            credit_control_area: Credit control area (default "0111" for SSG Engines)

        Returns:
            Dict with credit_limit, credit_exposure, utilization_pct, status.
        """
        # M0-T05: validate inputs before building XML (prevent injection)
        if not self._CUSTOMER_ID_RE.match(customer_id):
            raise SAPCPIError(f"Invalid customer_id format: must be 1-10 digits")
        if not self._CCA_RE.match(credit_control_area):
            raise SAPCPIError(
                f"Invalid credit_control_area format: must be 1-10 alphanumeric chars"
            )

        # Build XML safely using ElementTree instead of f-strings
        root = ET.Element("KYPRequest")
        ET.SubElement(root, "CUSTOMERNO").text = customer_id
        ET.SubElement(root, "CreditControlArea").text = credit_control_area
        xml_payload = '<?xml version="1.0" encoding="UTF-8"?>' + ET.tostring(
            root, encoding="unicode"
        )

        resp = self._post_to_cpi(self._kyp_iflow, xml_payload)
        return self._parse_credit_response(resp.text, customer_id)

    def _parse_credit_response(
        self, response_text: str, customer_id: str
    ) -> Dict[str, Any]:
        """Parse the CPI credit check response.

        The CPI iFlow (Integrum/RequestTableData) returns JSON with this structure:
        {
            "CUSTOMERADDRESS": {"NAME1", "NAME2", "STREET", "CITY1", "POST_CODE1", "COUNTRY", ...},
            "CUSTOMERGENERALDETAIL": {"CUSTOMER", "COMP_CODE"},
            "RETURN": [{"TYPE", "MESSAGE"}],
            "CREDIT": {"CREDIT_LIMIT", "CREDIT_EXPOSURE", "RETURN": [...]}
        }

        KNOWN ISSUE: CPI does NOT return a CURRENCY field in the CREDIT dict.
        Currency is resolved from the entity registry based on customer_id.
        """
        import json as _json

        result = {
            "customer_id": customer_id,
            "credit_limit": 0.0,
            "credit_exposure": 0.0,
            "utilization_pct": 0.0,
            "currency": "",
            "status": "UNKNOWN",
            "customer_name": "",
            "address": "",
            "errors": [],
            "source": "SAP_CPI",
        }

        # Try JSON first (actual CPI response format)
        try:
            data = _json.loads(response_text)
            return self._parse_credit_json(data, customer_id, result)
        except (_json.JSONDecodeError, ValueError):
            pass

        # Fall back to XML parsing (use defusedxml for external input)
        try:
            root = SafeET.fromstring(response_text)
        except SafeET.ParseError:
            result["errors"].append("Failed to parse CPI response (not JSON or XML)")
            result["status"] = "ERROR"
            return result

        # Extract from XML
        for elem in root.iter():
            tag = elem.tag.split("}")[-1] if "}" in elem.tag else elem.tag
            text = (elem.text or "").strip()

            if tag == "CREDIT_LIMIT" and text:
                result["credit_limit"] = float(text)
            elif tag == "CREDIT_EXPOSURE" and text:
                result["credit_exposure"] = float(text)
            elif tag == "CURRENCY" and text:
                result["currency"] = text
            elif tag == "NAME1" and text and not result["customer_name"]:
                result["customer_name"] = text
            elif tag == "NAME2" and text and result["customer_name"]:
                result["customer_name"] += f" {text}"
            elif tag == "STREET" and text:
                result["address"] = text
            elif tag in ("CITY", "CITY1") and text:
                result["address"] += f", {text}" if result["address"] else text
            elif tag == "COUNTRY" and text and result["address"]:
                result["address"] += f", {text}"
            elif tag == "MESSAGE" and text:
                result["errors"].append(text)

        self._finalize_credit_result(result, customer_id)
        return result

    def _parse_credit_json(
        self, data: Dict, customer_id: str, result: Dict
    ) -> Dict[str, Any]:
        """Parse JSON credit response from CPI."""
        # Customer address
        addr = data.get("CUSTOMERADDRESS", {})
        name1 = addr.get("NAME1", "")
        name2 = addr.get("NAME2", "")
        result["customer_name"] = f"{name1} {name2}".strip() if name2 else name1

        street = addr.get("STREET", "")
        city = addr.get("CITY1", "")
        postal = addr.get("POST_CODE1", "")
        country = addr.get("COUNTRY", "")
        parts = [p for p in [street, f"{city} {postal}".strip(), country] if p]
        result["address"] = ", ".join(parts)

        # Messages (informational, not errors)
        for msg in data.get("RETURN", []):
            msg_text = msg.get("MESSAGE", "").strip()
            msg_type = msg.get("TYPE", "")
            if msg_text and msg_type == "E":
                result["errors"].append(msg_text)

        # Credit data
        credit = data.get("CREDIT", {})
        if credit:
            result["credit_limit"] = self._safe_float(credit.get("CREDIT_LIMIT", 0))
            result["credit_exposure"] = self._safe_float(
                credit.get("CREDIT_EXPOSURE", 0)
            )
            # CPI does NOT return CURRENCY — resolve from entity registry
            result["currency"] = credit.get("CURRENCY", "")

            # Check credit-specific errors
            for msg in credit.get("RETURN", []):
                msg_text = msg.get("MESSAGE", "").strip()
                msg_type = msg.get("TYPE", "")
                if msg_text and msg_type == "E":
                    result["errors"].append(msg_text)

        self._finalize_credit_result(result, customer_id)
        return result

    def _finalize_credit_result(self, result: Dict, customer_id: str) -> None:
        """Calculate utilization, status, and resolve missing currency/name."""
        # Resolve currency and normalize name from entity registry
        registry_entry = self._get_registry_entry(customer_id)
        if not result["currency"] and registry_entry:
            result["currency"] = registry_entry.get("currency", "")
        # Use registry name for consistency with finops/UI (CPI may return a different legal entity name)
        if registry_entry and registry_entry.get("name"):
            result["customer_name"] = registry_entry["name"]

        # Calculate utilization
        if result["credit_limit"] > 0:
            result["utilization_pct"] = round(
                (result["credit_exposure"] / result["credit_limit"]) * 100, 2
            )

        # Determine status
        if result["errors"]:
            result["status"] = "ERROR"
        elif result["credit_limit"] > 0:
            if result["credit_exposure"] > result["credit_limit"]:
                result["status"] = "BLOCKED"
            elif result["credit_exposure"] > result["credit_limit"] * 0.8:
                result["status"] = "WARNING"
            else:
                result["status"] = "OK"
        else:
            result["status"] = "NO_LIMIT"

    _entity_registry = None  # Cached singleton to avoid rebuild on every call

    def _get_registry_entry(self, customer_id: str) -> Optional[Dict]:
        """Look up customer in entity registry (cached singleton)."""
        if SAPCPIClient._entity_registry is None:
            from .entity_registry import EntityRegistry

            SAPCPIClient._entity_registry = EntityRegistry()
        return SAPCPIClient._entity_registry.resolve(customer_id)

    @staticmethod
    def _safe_float(value: Any) -> float:
        """Safely convert a value to float, rejecting NaN/Inf."""
        import math

        try:
            result = float(value)
            return result if math.isfinite(result) else 0.0
        except (ValueError, TypeError):
            return 0.0

    # ------------------------------------------------------------------
    # GetOpportunity (CEC)
    # ------------------------------------------------------------------

    def get_opportunities(self, customer_id: str) -> Dict[str, Any]:
        """
        Get CEC opportunities for a customer via CPI.

        KNOWN ISSUE (2026-03-19): The Integrum/GetOpportunity iFlow is a STUB.
        It returns the same 2 hardcoded anonymized opportunities regardless of
        the CustomerNo input. Verified by testing with real customers, bogus IDs,
        empty input, and no CustomerNo tag — all return identical data.

        The response is still parsed correctly but flagged as potentially stale.
        Per-customer filtering will work once the CPI iFlow is fixed.

        Args:
            customer_id: 10-digit SAP customer number

        Returns:
            Dict with opportunities list and metadata.
        """
        # M0-T05: validate input before building XML
        if not self._CUSTOMER_ID_RE.match(customer_id):
            raise SAPCPIError(f"Invalid customer_id format: must be 1-10 digits")

        root = ET.Element("GetOpportunity")
        ET.SubElement(root, "CustomerNo").text = customer_id
        xml_payload = ET.tostring(root, encoding="unicode")

        resp = self._post_to_cpi(self._opp_iflow, xml_payload)
        return self._parse_opportunity_response(resp.text, customer_id)

    def _parse_opportunity_response(
        self, response_text: str, customer_id: str
    ) -> Dict[str, Any]:
        """Parse the CPI GetOpportunity response.

        The iFlow returns JSON with nested Message1/Message2 structure:
        {
            "Message1": {
                "Messages": {
                    "Message1": {
                        "OpportunityCollection": {
                            "Opportunity": { ...fields... }
                        }
                    },
                    "Message2": {
                        "OpportunityBusinessTransactionDocumentReferenceCollection": ""
                    }
                }
            },
            "Message2": { ... second opportunity ... }
        }
        """
        import json as _json

        result = {
            "customer_id": customer_id,
            "opportunities": [],
            "count": 0,
            "source": "SAP_CPI",
            "iflow_status": "STUB",  # Flag: iFlow doesn't filter by customer
            "errors": [],
        }

        # Try JSON first (actual CPI response format)
        try:
            data = _json.loads(response_text)
            return self._parse_opportunity_json(data, customer_id, result)
        except (_json.JSONDecodeError, ValueError):
            pass

        # Fall back to XML (use defusedxml for external input)
        try:
            root = SafeET.fromstring(response_text)
            return self._parse_opportunity_xml(root, customer_id, result)
        except SafeET.ParseError:
            result["errors"].append(
                "Failed to parse CPI opportunity response (not JSON or XML)"
            )
            return result

    def _parse_opportunity_json(
        self, data: Dict, customer_id: str, result: Dict
    ) -> Dict[str, Any]:
        """Parse the actual JSON response from GetOpportunity iFlow.

        Handles the nested Message1/Message2 structure where each top-level
        MessageN contains one opportunity.
        """
        opportunities = []

        # Extract opportunities from nested MessageN structure
        for key, value in sorted(data.items()):
            if not key.startswith("Message") or not isinstance(value, dict):
                continue
            messages = value.get("Messages", {})
            # Look for OpportunityCollection in inner messages
            for inner_key, inner_value in messages.items():
                if not isinstance(inner_value, dict):
                    continue
                opp_collection = inner_value.get("OpportunityCollection", {})
                if isinstance(opp_collection, dict):
                    opp_data = opp_collection.get("Opportunity", {})
                    if isinstance(opp_data, dict) and opp_data.get("ID"):
                        opp = self._map_opportunity_fields(opp_data, customer_id)
                        opportunities.append(opp)

        # Deduplicate by ID (the stub returns duplicates across different structures)
        seen_ids = set()
        unique_opps = []
        for opp in opportunities:
            oid = opp.get("opportunity_id", "")
            if oid and oid not in seen_ids:
                seen_ids.add(oid)
                unique_opps.append(opp)

        result["opportunities"] = unique_opps
        result["count"] = len(unique_opps)
        return result

    def _map_opportunity_fields(
        self, opp_data: Dict, customer_id: str
    ) -> Dict[str, Any]:
        """Map CPI opportunity fields to our standard format."""
        return {
            "opportunity_id": str(opp_data.get("ID", "")),
            "name": opp_data.get("Name", ""),
            "status": opp_data.get("LifeCycleStatusCodeText", ""),
            "status_code": opp_data.get("LifeCycleStatusCode", ""),
            "revenue": self._safe_float(opp_data.get("ExpectedRevenueAmount", 0)),
            "currency": opp_data.get("ExpectedRevenueAmountCurrencyCode", ""),
            "win_probability": self._safe_float(
                opp_data.get("MTUChanceCode_TXT_SDK", 0)
            ),
            "win_probability_text": opp_data.get("MTUChancecontent_SDKText", ""),
            "start_date": opp_data.get("ExpectedProcessingStartDate", ""),
            "end_date": opp_data.get("ExpectedProcessingEndDate", ""),
            "sales_org_id": opp_data.get("SalesOrganisationID", ""),
            "ipas_project": opp_data.get("IPASProject", ""),
            "account_id": customer_id,
        }

    def _parse_opportunity_xml(
        self, root: ET.Element, customer_id: str, result: Dict
    ) -> Dict[str, Any]:
        """Parse XML opportunity response (fallback)."""
        field_map = {
            "ID": "opportunity_id",
            "Name": "name",
            "LifeCycleStatusCodeText": "status",
            "ExpectedRevenueAmount": "revenue",
            "ExpectedRevenueAmountCurrencyCode": "currency",
            "MTUChanceCode_TXT_SDK": "win_probability",
        }

        opportunities = []
        for opp_elem in root.iter():
            tag = opp_elem.tag.split("}")[-1] if "}" in opp_elem.tag else opp_elem.tag
            if tag == "Opportunity":
                opp: Dict[str, Any] = {"account_id": customer_id}
                for child in opp_elem:
                    child_tag = (
                        child.tag.split("}")[-1] if "}" in child.tag else child.tag
                    )
                    text = (child.text or "").strip()
                    if child_tag in field_map and text:
                        key = field_map[child_tag]
                        if key in ("revenue", "win_probability"):
                            opp[key] = self._safe_float(text)
                        else:
                            opp[key] = text
                if opp.get("opportunity_id"):
                    opportunities.append(opp)

        result["opportunities"] = opportunities
        result["count"] = len(opportunities)
        return result


# ============================================================================
# Custom Exceptions
# ============================================================================


class SAPCPIError(Exception):
    """Base exception for SAP CPI client errors."""

    pass


class SAPCPIConfigError(SAPCPIError):
    """SAP CPI configuration is missing or invalid."""

    pass


class SAPCPIConnectionError(SAPCPIError):
    """Failed to connect to SAP CPI."""

    pass


class SAPCPIAuthError(SAPCPIError):
    """SAP CPI authentication failed."""

    pass
