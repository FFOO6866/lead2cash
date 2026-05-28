"""
SAP CEC (Customer Engagement Center) Client

Handles opportunity retrieval and management from SAP CEC/Sales Cloud.
Routes ALL requests through SAP CPI as the single gateway per architecture.

Architecture:
    CECClient → CPIClient → SAP CPI → SAP CEC

CPI iFlows for CEC:
    - CECGetOpportunity: Get single opportunity by ID
    - CECSearchOpportunities: Search opportunities
    - CECGetOpportunitiesByAccount: Get opportunities for account
"""

import logging
import os
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Optional

from lead_to_cash.config import config
from lead_to_cash.integrations.cpi_client import CPIClient

logger = logging.getLogger(__name__)


# =============================================================================
# Data Classes
# =============================================================================


@dataclass
class Opportunity:
    """CEC Opportunity data with milestone payment fields.

    Standard CEC Fields (9 fields per client specification):
    - account_id: SAP Customer ID (10-digit)
    - status: Won, Lost, Open, Qualified
    - expected_revenue: Expected value
    - currency: ISO 4217 (EUR, USD, SGD)
    - close_date: Expected close/award date
    - win_probability: 10 (Little), 35 (Limited), 65 (Good), 90 (Very good)
    - title: Opportunity name/subject
    - start_date: Creation date
    - sales_type: OE_SALES or SERVICE_SALES

    Milestone Payment Fields (ADR-006):
    - sap_order_id: SAP S/4HANA Sales Order Number
    - ipas_quote_id: IPAS Quote Number
    """

    # Core identification
    opportunity_id: str
    account_id: str
    account_name: str

    # Status and value
    status: str  # Won, Lost, Open, Qualified
    expected_revenue: float
    currency: str

    # Dates
    close_date: Optional[datetime]
    start_date: Optional[datetime] = None

    # Classification (per client specification)
    title: Optional[str] = None
    win_probability: Optional[int] = None  # 10, 35, 65, 90
    sales_type: Optional[str] = None  # OE_SALES, SERVICE_SALES

    # Products
    products: list[dict] = field(default_factory=list)

    # Organizational
    owner: Optional[str] = None
    sales_org: Optional[str] = None
    distribution_channel: Optional[str] = None
    division: Optional[str] = None

    # Milestone Payment Fields (ADR-006)
    sap_order_id: Optional[str] = None  # SAP Sales Order Number
    ipas_quote_id: Optional[str] = None  # IPAS Quote Number

    def to_sap_mapping(self) -> dict[str, Any]:
        """Map CEC fields to SAP field names.

        Returns:
            Dictionary with SAP field names for order creation.
            Includes milestone payment references (ADR-006).
        """
        return {
            "BSTKD": self.opportunity_id,  # Customer PO reference
            "KUNNR": self.account_id.zfill(10),  # Sold-to party
            "WAERK": self.currency,  # Currency
            "VKORG": self.sales_org or "",  # Sales organization
            "VTWEG": self.distribution_channel or "",  # Distribution channel
            "SPART": self.division or "",  # Division
            # Milestone payment references (ADR-006)
            "VBELN_REF": self.sap_order_id or "",  # Sales Order reference
            "IPAS_QUOTE": self.ipas_quote_id or "",  # IPAS Quote reference
            "items": [
                {
                    "MATNR": p.get("product_id", ""),  # Material
                    "KWMENG": p.get("quantity", 0),  # Quantity
                    "VRKME": p.get("unit", "EA"),  # Sales unit
                    "EDATU": p.get("requested_date", ""),  # Delivery date
                    "WERKS": p.get("plant", ""),  # Plant
                }
                for p in self.products
            ],
        }

    def to_dict(self) -> dict[str, Any]:
        """Convert opportunity to dictionary for serialization.

        Returns:
            Dictionary representation of the opportunity.
        """
        return {
            "opportunity_id": self.opportunity_id,
            "account_id": self.account_id,
            "account_name": self.account_name,
            "status": self.status,
            "expected_revenue": self.expected_revenue,
            "currency": self.currency,
            "close_date": self.close_date.isoformat() if self.close_date else None,
            "start_date": self.start_date.isoformat() if self.start_date else None,
            "title": self.title,
            "win_probability": self.win_probability,
            "sales_type": self.sales_type,
            "products": self.products,
            "owner": self.owner,
            "sales_org": self.sales_org,
            "distribution_channel": self.distribution_channel,
            "division": self.division,
            "sap_order_id": self.sap_order_id,
            "ipas_quote_id": self.ipas_quote_id,
        }


# =============================================================================
# CPI iFlow Names for CEC
# =============================================================================


class CECiFlows:
    """CEC CPI iFlow names.

    Real CPI iFlows use "Integrum/" prefix (same pattern as MS5 credit).
    Simulator uses legacy names for handler routing.
    """

    # Real CPI iFlow path (matches deployed endpoint)
    GET_OPPORTUNITY_CPI = "Integrum/GetOpportunity"

    # Legacy names (used by CPISimulator handler routing)
    GET_OPPORTUNITY = "CECGetOpportunity"
    SEARCH_OPPORTUNITIES = "CECSearchOpportunities"
    GET_BY_ACCOUNT = "CECGetOpportunitiesByAccount"
    GET_PARTNERS = "CECGetPartners"
    GET_TERMS = "CECGetCommercialTerms"


# =============================================================================
# CEC Client
# =============================================================================


class CECClient:
    """SAP CEC (Sales Cloud) Integration Client.

    Retrieves opportunity data for Lead-to-Cash processing.
    Routes ALL requests through SAP CPI as the single gateway.

    Architecture:
        CECClient → CPIClient → SAP CPI → SAP CEC

    Simulation Mode:
        When simulation_mode=True or CPI iFlows fail, returns data from
        the CPI Simulator. This allows development and testing without
        deployed CPI iFlows.

    Usage:
        async with CECClient() as client:
            # Get opportunity
            opp = await client.get_opportunity("OPP-12345")

            # Get account opportunities
            opps = await client.get_opportunities_by_account("ACC-001")

            # Map to SAP format for order creation
            sap_data = opp.to_sap_mapping()

        # Explicit simulation mode
        client = CECClient(simulation_mode=True)
    """

    def __init__(
        self,
        cpi_client: Optional[CPIClient] = None,
        simulation_mode: bool = False,
    ):
        """Initialize CEC client.

        Args:
            cpi_client: Optional CPI client instance for reuse
            simulation_mode: If True, use CPISimulator instead of real CPI
        """
        self._simulation_mode = simulation_mode

        if simulation_mode:
            # Use CPISimulator directly for development/testing
            from lead_to_cash.integrations.cpi_simulator import CPISimulator

            self.cpi = CPISimulator()
        else:
            self.cpi = cpi_client or CPIClient()

        self._connected = False

    async def connect(self) -> None:
        """Establish connection via CPI.

        Raises:
            ValueError: If CPI is not configured
        """
        await self.cpi.connect()
        self._connected = True
        logger.info("CEC client connected via CPI")

    async def disconnect(self) -> None:
        """Close connection."""
        await self.cpi.disconnect()
        self._connected = False

    def _ensure_connected(self) -> None:
        """Ensure CEC client is connected.

        Raises:
            RuntimeError: If client not connected
        """
        if not self._connected:
            raise RuntimeError(
                "CEC client not connected. Call connect() first or use async context manager."
            )

    # =========================================================================
    # Opportunity Operations
    # =========================================================================

    async def get_opportunity(self, opportunity_id: str) -> Opportunity:
        """Get opportunity by ID.

        For real CPI: there is no single-opp endpoint, so this falls back
        to simulated data. Use get_opportunities_by_account() for real CPI data.

        For simulator: uses CECGetOpportunity handler.

        Args:
            opportunity_id: CEC opportunity ID

        Returns:
            Opportunity data

        Raises:
            RuntimeError: If client not connected
        """
        self._ensure_connected()

        from lead_to_cash.integrations.cpi_simulator import CPISimulator

        if isinstance(self.cpi, CPISimulator):
            # Simulator path — use legacy handler
            try:
                result = await self.cpi.call_iflow(
                    iflow_name=CECiFlows.GET_OPPORTUNITY,
                    payload={"opportunity_id": opportunity_id},
                )
                return self._parse_opportunity(result)
            except Exception:
                return self._get_simulated_opportunity(opportunity_id)

        # Real CPI — no single-opp endpoint exists; return simulated
        logger.info(
            f"get_opportunity({opportunity_id}): no real CPI single-opp endpoint, "
            "use get_opportunities_by_account() for real data"
        )
        return self._get_simulated_opportunity(opportunity_id)

    def _get_simulated_opportunity(self, opportunity_id: str) -> Opportunity:
        """Get simulated opportunity data.

        Creates a simulated opportunity for development/testing when
        CEC iFlows are not available.

        Args:
            opportunity_id: Opportunity ID to use

        Returns:
            Simulated Opportunity
        """
        from datetime import datetime, timedelta

        logger.info(f"Returning simulated opportunity for {opportunity_id}")

        # Create realistic simulated opportunity
        return Opportunity(
            opportunity_id=opportunity_id,
            account_id="0022005992",  # ST Engineering from simulator
            account_name="ST Engineering Marine Ltd (Simulated)",
            status="Open",
            expected_revenue=500000.00,
            currency="SGD",
            close_date=datetime.now() + timedelta(days=90),
            start_date=datetime.now(),
            title=f"Simulated Opportunity - {opportunity_id}",
            win_probability=65,
            sales_type="OE_SALES",
            products=[],
            owner="Sales Rep",
            sales_org="1000",
            distribution_channel="10",
            division="00",
            sap_order_id=None,
            ipas_quote_id=f"IPAS-SIM-{opportunity_id[-4:]}",
        )

    async def get_opportunities_by_account(
        self,
        account_id: str,
        status: Optional[str] = None,
        limit: int = 50,
    ) -> list[Opportunity]:
        """Get opportunities for an account.

        For real CPI: calls Integrum/GetOpportunity with XML payload,
        parses multimap XML response (same pattern as MS5 credit checks).

        For simulator: uses legacy CECGetOpportunitiesByAccount handler.

        Args:
            account_id: CEC account ID (will be mapped to SAP KUNNR)
            status: Filter by status (Open, Won, Lost)
            limit: Maximum results

        Returns:
            List of opportunities

        Raises:
            RuntimeError: If client not connected
        """
        self._ensure_connected()

        from lead_to_cash.integrations.cpi_simulator import CPISimulator

        if isinstance(self.cpi, CPISimulator):
            # Simulator path — no real CPI available
            from lead_to_cash.integrations.cpi_simulator import SIMULATED_OPPORTUNITIES

            normalized = account_id.zfill(10) if account_id.isdigit() else account_id
            opps_data = SIMULATED_OPPORTUNITIES.get(normalized, [])
            opps = [self._parse_opportunity(o) for o in opps_data]
            if status:
                opps = [o for o in opps if o.status == status]
            return opps[:limit]

        # Real CPI path — call Integrum/GetOpportunity with XML
        try:
            from xml.sax.saxutils import escape

            customer_no = account_id.zfill(10) if account_id.isdigit() else account_id
            xml_payload = (
                f'<?xml version="1.0" encoding="UTF-8"?>'
                f"<GetOpportunity><CustomerNo>{escape(customer_no)}</CustomerNo></GetOpportunity>"
            )

            result = await self.cpi.call_iflow_raw(
                iflow_name=CECiFlows.GET_OPPORTUNITY_CPI,
                xml_payload=xml_payload,
            )

            opportunities = self._parse_cpi_opportunity_response(result, account_id)

            # Apply status filter if requested
            if status:
                opportunities = [o for o in opportunities if o.status == status]

            return opportunities[:limit]

        except Exception as e:
            logger.error(f"CPI GetOpportunity failed for {account_id}: {e}")
            return []

    async def search_opportunities(
        self,
        query: str,
        status: Optional[str] = None,
        limit: int = 50,
    ) -> list[Opportunity]:
        """Search opportunities.

        For simulator: uses CECSearchOpportunities handler.
        For real CPI: no search endpoint exists; returns empty list.

        Args:
            query: Search query
            status: Filter by status
            limit: Maximum results

        Returns:
            List of matching opportunities

        Raises:
            RuntimeError: If client not connected
        """
        self._ensure_connected()

        from lead_to_cash.integrations.cpi_simulator import CPISimulator

        if not isinstance(self.cpi, CPISimulator):
            logger.info(
                f"search_opportunities: no real CPI search endpoint, "
                "use get_opportunities_by_account() instead"
            )
            return []

        payload = {
            "query": query,
            "limit": limit,
        }
        if status:
            payload["status"] = status

        result = await self.cpi.call_iflow(
            iflow_name=CECiFlows.SEARCH_OPPORTUNITIES,
            payload=payload,
        )

        return [self._parse_opportunity(opp) for opp in result.get("items", [])]

    async def get_commercial_terms(
        self,
        account_id: str,
        sales_org: Optional[str] = None,
    ) -> dict[str, Any]:
        """Get commercial terms for an account.

        Retrieves payment terms, Incoterms, and pricing agreements.

        Args:
            account_id: CEC account ID
            sales_org: Sales organization (defaults to config)

        Returns:
            Commercial terms data

        Raises:
            RuntimeError: If client not connected
        """
        self._ensure_connected()

        org = sales_org or config.sap_ms5.default_sales_org
        result = await self.cpi.call_iflow(
            iflow_name=CECiFlows.GET_TERMS,
            payload={
                "account_id": account_id,
                "sales_org": org or "",
            },
        )

        return {
            "payment_terms": result.get("payment_terms", ""),
            "incoterms": result.get("incoterms", ""),
            "incoterms_location": result.get("incoterms_location", ""),
            "price_list": result.get("price_list", ""),
            "currency": result.get("currency", "EUR"),
        }

    # =========================================================================
    # CPI Response Parsing
    # =========================================================================

    # SAP CEC LifeCycleStatusCode → status text mapping
    _LIFECYCLE_STATUS_MAP = {
        "1": "Open",  # In Process
        "2": "Open",  # In Process (variant)
        "3": "Lost",  # Lost
        "4": "Won",  # Won
        "5": "Open",  # Stopped / On Hold
    }

    def _parse_cpi_opportunity_response(
        self, result: dict[str, Any], account_id: str
    ) -> list[Opportunity]:
        """Parse real CPI GetOpportunity response.

        CPI returns opportunities in multimap XML format where each opportunity
        is wrapped in a separate multimap:Message block. The cpi_client XML parser
        converts this to a nested dict. We need to walk the structure to extract
        each Opportunity element.

        The XML structure from CPI:
            <multimap:Messages>
                <multimap:Message1>
                    <multimap:Messages>
                        <multimap:Message1>
                            <OpportunityCollection>
                                <Opportunity>...fields...</Opportunity>
                            </OpportunityCollection>
                        </multimap:Message1>
                        <multimap:Message2>
                            <OpportunityBusinessTransactionDocumentReferenceCollection/>
                        </multimap:Message2>
                    </multimap:Messages>
                </multimap:Message1>
                ...more Message blocks...
            </multimap:Messages>

        After XML→dict parsing, this becomes nested dicts with Message1/Message2 keys.

        Args:
            result: Parsed dict from CPI XML response
            account_id: Customer ID for this query

        Returns:
            List of Opportunity objects
        """
        opportunities = []
        seen_ids: set[str] = set()

        # Extract opportunity dicts from the nested multimap structure
        opp_dicts = self._extract_opportunities_from_multimap(result)

        for opp_data in opp_dicts:
            try:
                opp = self._parse_cpi_opportunity_fields(opp_data, account_id)
                # Deduplicate by opportunity_id
                if opp.opportunity_id and opp.opportunity_id in seen_ids:
                    continue
                seen_ids.add(opp.opportunity_id)
                opportunities.append(opp)
            except Exception as e:
                logger.warning(f"Failed to parse CPI opportunity: {e}")
                continue

        logger.info(
            f"Parsed {len(opportunities)} opportunities from CPI for {account_id}"
        )
        return opportunities

    def _extract_opportunities_from_multimap(self, data: Any) -> list[dict[str, Any]]:
        """Recursively extract Opportunity dicts from multimap structure.

        Walks the nested dict looking for 'Opportunity' keys at any depth.
        Handles both single opportunity (dict) and list of opportunities.
        """
        results = []

        if isinstance(data, dict):
            # Found an Opportunity element
            if "Opportunity" in data:
                opp = data["Opportunity"]
                if isinstance(opp, list):
                    results.extend(opp)
                elif isinstance(opp, dict):
                    results.append(opp)

            # Found OpportunityCollection
            if "OpportunityCollection" in data:
                collection = data["OpportunityCollection"]
                results.extend(self._extract_opportunities_from_multimap(collection))

            # Recurse into Message blocks (Message1, Message2, etc.)
            for key, value in data.items():
                if key.startswith("Message") or key == "Messages":
                    results.extend(self._extract_opportunities_from_multimap(value))

        elif isinstance(data, list):
            for item in data:
                results.extend(self._extract_opportunities_from_multimap(item))

        return results

    def _parse_cpi_opportunity_fields(
        self, opp: dict[str, Any], account_id: str
    ) -> Opportunity:
        """Map CPI XML field names to Opportunity dataclass.

        CPI field names (from SAP CEC/Sales Cloud):
            ID → opportunity_id
            Name → title
            LifeCycleStatusCodeText → status (Won/Lost/Open)
            LifeCycleStatusCode → status code (1-5)
            ExpectedRevenueAmount → expected_revenue
            ExpectedRevenueAmountCurrencyCode → currency
            ExpectedProcessingStartDate → start_date
            ExpectedProcessingEndDate → close_date
            MTUChanceCode_TXT_SDK → win_probability (10/35/65/90)
            SalesOrganisationID → sales_org
            IPASProject → ipas_quote_id
        """
        # Parse dates (format: "2024-12-19T00:00:00.000" or "2024-12-19T00:00:00Z")
        close_date = None
        raw_close = opp.get("ExpectedProcessingEndDate", "")
        if raw_close:
            try:
                close_date = datetime.fromisoformat(
                    raw_close.replace("Z", "+00:00").split(".")[0]
                )
            except ValueError:
                pass

        start_date = None
        raw_start = opp.get("ExpectedProcessingStartDate", "")
        if raw_start:
            try:
                start_date = datetime.fromisoformat(
                    raw_start.replace("Z", "+00:00").split(".")[0]
                )
            except ValueError:
                pass

        # Parse win probability from MTUChanceCode_TXT_SDK (e.g., "90")
        win_probability = None
        raw_chance = opp.get("MTUChanceCode_TXT_SDK", "")
        if raw_chance:
            try:
                win_probability = int(raw_chance)
            except (ValueError, TypeError):
                pass

        # Parse revenue (e.g., "999999.000000")
        expected_revenue = 0.0
        raw_revenue = opp.get("ExpectedRevenueAmount", "0")
        try:
            val = float(raw_revenue)
            # Reject NaN/inf — clamp to 0
            import math

            if math.isfinite(val):
                expected_revenue = val
        except (ValueError, TypeError):
            pass

        # Map status from LifeCycleStatusCodeText or LifeCycleStatusCode
        status_text = opp.get("LifeCycleStatusCodeText", "")
        if not status_text:
            status_code = opp.get("LifeCycleStatusCode", "")
            status_text = self._LIFECYCLE_STATUS_MAP.get(str(status_code), "Open")

        # IPAS project reference (may be empty element or whitespace in XML)
        raw_ipas = opp.get("IPASProject", "")
        ipas_project = raw_ipas.strip() if isinstance(raw_ipas, str) else raw_ipas
        ipas_project = ipas_project or None

        return Opportunity(
            opportunity_id=str(opp.get("ID", opp.get("OpportunityID", ""))),
            account_id=account_id,
            account_name=opp.get("AccountName", ""),
            status=status_text,
            expected_revenue=expected_revenue,
            currency=opp.get("ExpectedRevenueAmountCurrencyCode", "EUR"),
            close_date=close_date,
            start_date=start_date,
            title=opp.get("Name", ""),
            win_probability=win_probability,
            sales_type=opp.get("SalesType", "OE_SALES"),
            products=[],
            owner=opp.get("OwnerName"),
            sales_org=opp.get("SalesOrganisationID"),
            ipas_quote_id=ipas_project,
            sap_order_id=opp.get("SAPOrderID"),
        )

    # =========================================================================
    # Simulator Helper Methods
    # =========================================================================

    def _parse_opportunity(self, data: dict[str, Any]) -> Opportunity:
        """Parse opportunity from simulator/legacy CPI response.

        Handles all standard CEC fields plus milestone payment fields (ADR-006).
        """
        # Parse close_date
        close_date = None
        if data.get("close_date"):
            try:
                close_date = datetime.fromisoformat(data["close_date"])
            except ValueError:
                pass

        # Parse start_date
        start_date = None
        if data.get("start_date"):
            try:
                start_date = datetime.fromisoformat(data["start_date"])
            except ValueError:
                pass

        # Parse win_probability (handle string or int)
        win_probability = None
        if data.get("win_probability") is not None:
            try:
                win_probability = int(data["win_probability"])
            except (ValueError, TypeError):
                pass

        return Opportunity(
            opportunity_id=data.get("id", data.get("opportunity_id", "")),
            account_id=data.get("account_id", ""),
            account_name=data.get("account_name", ""),
            status=data.get("status", ""),
            expected_revenue=float(data.get("expected_revenue", 0)),
            currency=data.get("currency", "EUR"),
            close_date=close_date,
            start_date=start_date,
            title=data.get("title"),
            win_probability=win_probability,
            sales_type=data.get("sales_type"),
            products=data.get("products", []),
            owner=data.get("owner"),
            sales_org=data.get("sales_org"),
            distribution_channel=data.get("distribution_channel"),
            division=data.get("division"),
            # Milestone payment fields (ADR-006)
            sap_order_id=data.get("sap_order_id"),
            ipas_quote_id=data.get("ipas_quote_id"),
        )

    # =========================================================================
    # Health Check
    # =========================================================================

    async def health_check(self) -> dict[str, Any]:
        """Check CEC connectivity via CPI."""
        cpi_health = await self.cpi.health_check()
        return {
            "status": "connected" if self._connected else "disconnected",
            "cpi_status": cpi_health,
            "simulation_mode": self._simulation_mode,
            "iflows": {
                "get_opportunity": CECiFlows.GET_OPPORTUNITY,
                "search": CECiFlows.SEARCH_OPPORTUNITIES,
                "by_account": CECiFlows.GET_BY_ACCOUNT,
            },
        }

    # =========================================================================
    # Context Manager
    # =========================================================================

    async def __aenter__(self) -> "CECClient":
        """Async context manager entry."""
        await self.connect()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb) -> None:
        """Async context manager exit."""
        await self.disconnect()
