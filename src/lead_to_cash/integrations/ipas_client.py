"""
SAP IPAS (Intelligent Product Advisor System) Client

Handles product configuration retrieval for Lead-to-Cash processing.
Routes ALL requests through SAP CPI as the single gateway per architecture.

Architecture:
    IPASClient → CPIClient → SAP CPI → IPAS (via NEW CPI Interface)

CPI iFlows for IPAS (NEW interfaces per architecture):
    - IPASGetConfiguration: Get product configuration by ID
    - IPASGetByOpportunity: Get configurations for opportunity
    - IPASGetProductCatalog: Get product catalog
    - IPASValidateConfiguration: Validate configuration characteristics

Simulation Mode:
    When CPI iFlows are not deployed, IPASClient can parse the SSZ sample.XML
    file directly to return simulated product configuration data.
"""

import logging
import defusedxml.ElementTree as ET
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Optional

from lead_to_cash.integrations.cpi_client import CPIClient

logger = logging.getLogger(__name__)

# Path to sample IPAS XML file for simulation
SAMPLE_XML_PATH = Path(__file__).parent.parent / "docs" / "SSZ sample.XML"


# =============================================================================
# Data Classes
# =============================================================================


@dataclass
class ProductConfiguration:
    """IPAS Product Configuration."""

    config_id: str
    product_id: str
    product_name: str
    variant: Optional[str]
    bom_items: list[dict]
    characteristics: dict[str, Any]
    pricing_relevant: bool = True
    simulated: bool = False  # Flag indicating this is simulated data

    def get_materials(self) -> list[str]:
        """Get list of material numbers from BOM.

        Returns:
            List of SAP material numbers (MATNR)
        """
        return [item.get("material", "") for item in self.bom_items]

    def to_order_items(self) -> list[dict]:
        """Convert BOM to SAP order item format.

        Returns:
            List of items formatted for SAP sales order
        """
        items = []
        for i, bom_item in enumerate(self.bom_items):
            items.append(
                {
                    "ITM_NUMBER": str((i + 1) * 10).zfill(6),
                    "MATERIAL": bom_item.get("material", ""),
                    "TARGET_QTY": bom_item.get("quantity", 1),
                    "SALES_UNIT": bom_item.get("unit", "EA"),
                    "PLANT": bom_item.get("plant", ""),
                }
            )
        return items

    @classmethod
    def from_xml(cls, xml_path: Path, config_id: str = "") -> "ProductConfiguration":
        """Parse ProductConfiguration from IPAS XML file.

        Args:
            xml_path: Path to IPAS XML file
            config_id: Override config ID (uses file Message_ID if empty)

        Returns:
            ProductConfiguration parsed from XML
        """
        tree = ET.parse(xml_path)
        root = tree.getroot()

        # Parse DocumentProperties
        doc_props = root.find("DocumentProperties")
        message_id = doc_props.findtext("Message_ID", "") if doc_props else ""

        # Parse Header
        header = root.find("Header")
        if header is None:
            raise ValueError("Invalid IPAS XML: missing Header element")

        ipas_order_number = header.findtext("IPAS_Order_Number", "")
        engine_type = header.findtext("Engine_Type", "")
        power = header.findtext("Power", "")
        cylinder = header.findtext("Cylinder", "")
        series = header.findtext("Series", "")
        currency = header.findtext("Currency_Code", "EUR")
        sold_to = header.findtext("Sold_To_Party", "")
        incoterms = header.findtext("Incoterms_1", "")
        distr_channel = header.findtext("Distr_Channel", "")

        # Parse BOM items from Engines/Engine/Item elements
        bom_items = []
        engines_elem = root.find("Engines")
        if engines_elem:
            for engine in engines_elem.findall("Engine"):
                engine_number = engine.findtext("Engine_Number", "")
                engine.findtext("Gross_Price", "0").strip()

                for item in engine.findall("Item"):
                    bom_items.append(
                        {
                            "material": item.findtext("Material", ""),
                            "quantity": int(item.findtext("Quantity", "1")),
                            "engine_number": item.findtext(
                                "Engine_Number", engine_number
                            ),
                            "item_number": item.findtext("Item_Number", ""),
                            "delivery_date": item.findtext("Delivery_Date", ""),
                            "assembly_note": item.findtext("Assembly_Note", ""),
                            "packaging_group": item.findtext("Packaging_Group", ""),
                            "unit": "EA",
                            "plant": "",
                        }
                    )

        # Build characteristics from header fields
        characteristics = {
            "ENGINE_TYPE": engine_type,
            "POWER": power,
            "CYLINDER": cylinder,
            "SERIES": series,
            "CURRENCY": currency,
            "SOLD_TO_PARTY": sold_to,
            "INCOTERMS": incoterms,
            "DISTR_CHANNEL": distr_channel,
            "IPAS_ORDER_NUMBER": ipas_order_number,
        }

        return cls(
            config_id=config_id or message_id or ipas_order_number,
            product_id=engine_type,
            product_name=f"MTU {engine_type} ({power}kW)",
            variant=series,
            bom_items=bom_items,
            characteristics=characteristics,
            pricing_relevant=True,
            simulated=True,
        )


@dataclass
class ProductCatalog:
    """IPAS Product Catalog entry."""

    product_id: str
    name: str
    description: str
    category: str
    configurable: bool
    base_price: Optional[float] = None
    currency: str = "EUR"


# =============================================================================
# CPI iFlow Names for IPAS
# =============================================================================


class IPASiFlows:
    """IPAS CPI iFlow names (NEW interfaces per architecture)."""

    GET_CONFIGURATION = "IPASGetConfiguration"
    GET_BY_OPPORTUNITY = "IPASGetByOpportunity"
    GET_PRODUCT_CATALOG = "IPASGetProductCatalog"
    VALIDATE_CONFIGURATION = "IPASValidateConfiguration"
    GET_BOM = "IPASGetBOM"


# =============================================================================
# IPAS Client
# =============================================================================


class IPASClient:
    """SAP IPAS (Intelligent Product Advisor System) Client.

    Retrieves product configurations for sales orders.
    Routes ALL requests through SAP CPI as the single gateway.

    Architecture:
        IPASClient → CPIClient → SAP CPI → IPAS (NEW CPI Interface)

    Simulation Mode:
        When simulation_mode=True or CPI iFlows fail, returns data parsed
        from the SSZ sample.XML file. This allows development and testing
        without deployed CPI iFlows.

    Usage:
        async with IPASClient() as client:
            # Get product configuration
            config = await client.get_configuration("CFG-12345")

            # Get materials for order
            materials = config.get_materials()

            # Convert to order items
            items = config.to_order_items()

        # Explicit simulation mode
        client = IPASClient(simulation_mode=True)
    """

    def __init__(
        self,
        cpi_client: Optional[CPIClient] = None,
        simulation_mode: bool = False,
    ):
        """Initialize IPAS client.

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
        self._cached_xml_config: Optional[ProductConfiguration] = None

    async def connect(self) -> None:
        """Establish connection via CPI.

        Raises:
            ValueError: If CPI is not configured
        """
        await self.cpi.connect()
        self._connected = True
        logger.info("IPAS client connected via CPI")

    async def disconnect(self) -> None:
        """Close connection."""
        await self.cpi.disconnect()
        self._connected = False

    def _ensure_connected(self) -> None:
        """Ensure IPAS client is connected.

        Raises:
            RuntimeError: If client not connected
        """
        if not self._connected:
            raise RuntimeError(
                "IPAS client not connected. Call connect() first or use async context manager."
            )

    # =========================================================================
    # Configuration Operations
    # =========================================================================

    async def get_configuration(self, config_id: str) -> ProductConfiguration:
        """Get product configuration by ID.

        Routes through CPI using NEW IPAS interface. Falls back to
        simulation mode if CPI iFlow is unavailable.

        Args:
            config_id: IPAS configuration ID

        Returns:
            ProductConfiguration with BOM and characteristics

        Raises:
            RuntimeError: If client not connected
        """
        self._ensure_connected()

        # Use simulation mode if explicitly requested
        if self._simulation_mode:
            return self._get_simulated_configuration(config_id)

        try:
            result = await self.cpi.call_iflow(
                iflow_name=IPASiFlows.GET_CONFIGURATION,
                payload={"config_id": config_id},
            )
            return self._parse_configuration(result)
        except Exception as e:
            # Fall back to simulation if CPI call fails
            logger.warning(
                f"IPAS CPI iFlow failed ({e}), falling back to simulation mode"
            )
            return self._get_simulated_configuration(config_id)

    def _get_simulated_configuration(self, config_id: str) -> ProductConfiguration:
        """Get simulated configuration from XML file.

        Args:
            config_id: Configuration ID to use

        Returns:
            ProductConfiguration parsed from sample XML
        """
        # Cache the parsed XML to avoid repeated parsing
        if self._cached_xml_config is None:
            if SAMPLE_XML_PATH.exists():
                self._cached_xml_config = ProductConfiguration.from_xml(
                    SAMPLE_XML_PATH, config_id
                )
                logger.info(
                    f"Loaded simulated IPAS config from {SAMPLE_XML_PATH.name}: "
                    f"{len(self._cached_xml_config.bom_items)} BOM items"
                )
            else:
                # Return minimal simulated config if XML not found
                logger.warning(f"Sample XML not found at {SAMPLE_XML_PATH}")
                self._cached_xml_config = ProductConfiguration(
                    config_id=config_id,
                    product_id="MTU-12V2000",
                    product_name="MTU 12V2000 (simulated)",
                    variant="G65SZ",
                    bom_items=[
                        {"material": "SIMULATED-ITEM-001", "quantity": 1, "unit": "EA"},
                        {"material": "SIMULATED-ITEM-002", "quantity": 1, "unit": "EA"},
                    ],
                    characteristics={"ENGINE_TYPE": "12V2000", "SIMULATED": "true"},
                    simulated=True,
                )

        # Return a copy with the requested config_id
        config = self._cached_xml_config
        return ProductConfiguration(
            config_id=config_id,
            product_id=config.product_id,
            product_name=config.product_name,
            variant=config.variant,
            bom_items=config.bom_items,
            characteristics=config.characteristics,
            pricing_relevant=config.pricing_relevant,
            simulated=True,
        )

    async def get_configuration_by_opportunity(
        self,
        opportunity_id: str,
    ) -> list[ProductConfiguration]:
        """Get product configurations for an opportunity.

        Routes through CPI using NEW IPAS interface.

        Args:
            opportunity_id: CEC opportunity ID

        Returns:
            List of product configurations

        Raises:
            RuntimeError: If client not connected
        """
        self._ensure_connected()

        result = await self.cpi.call_iflow(
            iflow_name=IPASiFlows.GET_BY_OPPORTUNITY,
            payload={"opportunity_id": opportunity_id},
        )

        return [self._parse_configuration(cfg) for cfg in result.get("items", [])]

    async def get_product_catalog(
        self,
        category: Optional[str] = None,
        search: Optional[str] = None,
        limit: int = 50,
    ) -> list[ProductCatalog]:
        """Get product catalog.

        Routes through CPI using NEW IPAS interface.

        Args:
            category: Filter by category
            search: Search term
            limit: Maximum results

        Returns:
            List of products

        Raises:
            RuntimeError: If client not connected
        """
        self._ensure_connected()

        payload: dict[str, Any] = {"limit": limit}
        if category:
            payload["category"] = category
        if search:
            payload["search"] = search

        result = await self.cpi.call_iflow(
            iflow_name=IPASiFlows.GET_PRODUCT_CATALOG,
            payload=payload,
        )

        return [
            ProductCatalog(
                product_id=p.get("id", p.get("product_id", "")),
                name=p.get("name", ""),
                description=p.get("description", ""),
                category=p.get("category", ""),
                configurable=p.get("configurable", False),
                base_price=p.get("base_price"),
                currency=p.get("currency", "EUR"),
            )
            for p in result.get("items", [])
        ]

    async def validate_configuration(
        self,
        config_id: str,
        characteristics: dict[str, Any],
    ) -> dict[str, Any]:
        """Validate configuration characteristics.

        Routes through CPI using NEW IPAS interface.

        Args:
            config_id: Configuration ID
            characteristics: Characteristics to validate

        Returns:
            Validation result with is_valid and messages

        Raises:
            RuntimeError: If client not connected
        """
        self._ensure_connected()

        result = await self.cpi.call_iflow(
            iflow_name=IPASiFlows.VALIDATE_CONFIGURATION,
            payload={
                "config_id": config_id,
                "characteristics": characteristics,
            },
        )

        return {
            "is_valid": result.get("is_valid", False),
            "messages": result.get("messages", []),
            "errors": result.get("errors", []),
            "warnings": result.get("warnings", []),
        }

    async def get_bom(
        self,
        product_id: str,
        variant: Optional[str] = None,
    ) -> list[dict]:
        """Get bill of materials for a product.

        Routes through CPI using NEW IPAS interface.

        Args:
            product_id: Product ID
            variant: Optional variant code

        Returns:
            List of BOM items

        Raises:
            RuntimeError: If client not connected
        """
        self._ensure_connected()

        payload: dict[str, Any] = {"product_id": product_id}
        if variant:
            payload["variant"] = variant

        result = await self.cpi.call_iflow(
            iflow_name=IPASiFlows.GET_BOM,
            payload=payload,
        )

        return result.get("bom_items", [])

    # =========================================================================
    # Helper Methods
    # =========================================================================

    def _parse_configuration(self, data: dict[str, Any]) -> ProductConfiguration:
        """Parse configuration from CPI response."""
        return ProductConfiguration(
            config_id=data.get("id", data.get("config_id", "")),
            product_id=data.get("product_id", ""),
            product_name=data.get("product_name", ""),
            variant=data.get("variant"),
            bom_items=data.get("bom_items", []),
            characteristics=data.get("characteristics", {}),
            pricing_relevant=data.get("pricing_relevant", True),
        )

    # =========================================================================
    # Health Check
    # =========================================================================

    async def health_check(self) -> dict[str, Any]:
        """Check IPAS connectivity via CPI."""
        cpi_health = await self.cpi.health_check()
        return {
            "status": "connected" if self._connected else "disconnected",
            "cpi_status": cpi_health,
            "interface_type": "NEW",  # Per architecture diagram
            "simulation_mode": self._simulation_mode,
            "sample_xml_available": SAMPLE_XML_PATH.exists(),
            "iflows": {
                "get_configuration": IPASiFlows.GET_CONFIGURATION,
                "by_opportunity": IPASiFlows.GET_BY_OPPORTUNITY,
                "product_catalog": IPASiFlows.GET_PRODUCT_CATALOG,
                "validate": IPASiFlows.VALIDATE_CONFIGURATION,
            },
        }

    # =========================================================================
    # Context Manager
    # =========================================================================

    async def __aenter__(self) -> "IPASClient":
        """Async context manager entry."""
        await self.connect()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb) -> None:
        """Async context manager exit."""
        await self.disconnect()
