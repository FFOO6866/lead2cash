"""
IPAS Order Service

Parses IPAS XML files and maps to MS5 SAP order entry format.
Supports FTP folder monitoring for new order detection.

The field mapping follows the MS5 SAP entry screen sequence as defined in:
- RRPS_Lead_to_Cash_Master_Field_Mapping v2.xlsx

MS5 Order Entry Screen Sections:
1. Header Data (Sales Org, Distribution Channel, Division)
2. Customer Data (Sold-to, Ship-to, Bill-to, End Customer)
3. Product Data (Engine Type, Series, Cylinder, Power)
4. Commercial Terms (Incoterms, Payment Terms, Currency)
5. Delivery Data (Delivery Location, Dates, Shipping)
6. Order Items (BOM/Materials with quantities and dates)
"""

import logging
import os
import defusedxml.ElementTree as ET
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Optional

logger = logging.getLogger(__name__)

# Default folder for IPAS XML files (can be overridden via environment)
DEFAULT_IPAS_FOLDER = Path(__file__).parent.parent / "docs"
_PROJECT_ROOT = Path(__file__).parent.parent.parent.parent.resolve()

_env_folder = os.getenv("IPAS_XML_FOLDER")
if _env_folder:
    _resolved = Path(_env_folder).resolve()
    # Validate env folder is within project root or /tmp (for tests)
    if not (
        str(_resolved).startswith(str(_PROJECT_ROOT))
        or str(_resolved).startswith("/tmp")
    ):
        logger.warning(
            f"IPAS_XML_FOLDER '{_env_folder}' is outside project root, "
            f"falling back to default"
        )
        IPAS_FOLDER = DEFAULT_IPAS_FOLDER
    else:
        IPAS_FOLDER = _resolved
else:
    IPAS_FOLDER = DEFAULT_IPAS_FOLDER


# =============================================================================
# Data Classes - Mapped to MS5 Entry Sequence
# =============================================================================


@dataclass
class MS5HeaderData:
    """MS5 Order Header - Section 1: Organization Data."""

    sales_org: str = ""  # VBAK-VKORG
    distribution_channel: str = ""  # VBAK-VTWEG
    division: str = ""  # VBAK-SPART
    sales_office: str = ""  # VBAK-VKBUR
    order_type: str = "ZEN2"  # VBAK-AUART (Default)
    ipas_order_number: str = ""
    ipas_project_number: str = ""
    document_date: str = ""
    purchase_order_number: str = ""  # VBAK-BSTNK
    purchase_order_date: str = ""


@dataclass
class MS5CustomerData:
    """MS5 Order Header - Section 2: Customer Partners."""

    sold_to_party: str = ""  # VBPA-KUNNR (PARVW=AG)
    sold_to_name: str = ""
    ship_to_party: str = ""  # VBPA-KUNNR (PARVW=WE)
    ship_to_name: str = ""
    bill_to_party: str = ""  # VBPA-KUNNR (PARVW=RE)
    bill_to_name: str = ""
    payer: str = ""  # VBPA-KUNNR (PARVW=RG)
    end_customer: str = ""
    end_customer_country: str = ""
    end_customer_group: str = ""


@dataclass
class MS5ProductData:
    """MS5 Order Header - Section 3: Product Configuration + MTU Specific Fields."""

    # Product Configuration
    engine_type: str = ""  # Main product
    series: str = ""
    cylinder: str = ""
    power: str = ""
    power_unit: str = "KW"
    engine_speed: str = ""

    # MTU Specific Fields (SAP Additional Data B tab)
    application_coarse: str = ""  # Application ID
    application_fine: str = ""
    application_group: str = ""  # Application Group ID
    type_of_service: str = ""  # Type of Service ID
    product_category: str = ""  # Product category
    propulsion_type: str = ""  # Propulsion Type
    propulsion_sup_key: str = ""  # Prop. Sup. Key (Propulsion in XML)
    business_type: str = ""  # Business Type
    ipas_object_type: str = ""  # Object Type
    project_type: str = ""  # Project Type


@dataclass
class MS5CommercialTerms:
    """MS5 Order Header - Section 4: Commercial Terms."""

    incoterms_1: str = ""  # VBKD-INCO1
    incoterms_2: str = ""  # VBKD-INCO2 (Location)
    payment_terms: str = ""  # VBKD-ZTERM
    payment_terms_text: str = ""  # Full text from RFC_READ_TEXT
    currency_code: str = ""  # Order currency
    invoice_language: str = "EN"
    delivery_note_language: str = "EN"
    billing_plan_relevant: bool = False


@dataclass
class MS5DeliveryData:
    """MS5 Order Header - Section 5: Delivery & Shipping."""

    delivery_location: str = ""
    shipping_type: str = ""
    direct_ship: bool = False
    initiator_region: str = ""
    target_region: str = ""
    purchased_from_region: str = ""
    producing_factory: str = ""
    ordering_location: str = ""


@dataclass
class MS5ClassificationData:
    """MS5 Order Header - Section 6: Classification & Compliance (EPA Relevant)."""

    classification_society: str = ""
    emission_cert_authority: str = ""
    flag_state: str = ""
    exhaust_regulation: str = ""
    construction_no_vessel: str = ""
    shipbuilder_yard: str = ""


@dataclass
class MS5OthersData:
    """MS5 Order Header - Section: Others (miscellaneous fields)."""

    ipas_distribution_channel: str = ""  # Distr_Channel in XML
    penalty: str = ""
    scope_of_supply_complete: str = ""
    demagnesation: str = ""
    delivery_language: str = ""  # Delivery_Note_Language in XML


@dataclass
class MS5OrderItem:
    """MS5 Order Line Item - BOM Component."""

    item_number: str = ""  # VBAP item number (10, 20, 30...)
    engine_number: str = ""  # Engine sequence in order
    material: str = ""  # VBAP-MATNR
    material_description: str = ""
    quantity: int = 1  # VBAP-KWMENG
    unit: str = "EA"  # Sales UoM
    delivery_date: str = ""  # Requested delivery date
    plant: str = ""  # Delivering plant
    item_category: str = ""  # VBAP-PSTYV
    gross_price: float = 0.0
    assembly_note: str = ""
    packaging_group: str = ""
    item_type: str = "M"  # M=Material


@dataclass
class MS5Engine:
    """Engine configuration within order."""

    engine_number: str = ""
    engine_type: str = ""
    quantity: int = 1
    delivery_date: str = ""
    ship_to_party: str = ""
    shipping_type: str = ""
    packaging_group: str = ""
    gross_price: float = 0.0
    absolute_discount: float = 0.0
    exhaust_regulation: str = ""
    items: list[MS5OrderItem] = field(default_factory=list)


@dataclass
class IPASOrder:
    """Complete IPAS Order mapped to MS5 entry structure."""

    # Metadata
    order_id: str = ""
    file_name: str = ""
    file_path: str = ""
    created_date: str = ""
    source: str = "IPAS"
    format_version: str = ""
    target_id: str = ""
    target_desc: str = ""
    message_id: str = ""
    order_status: str = ""

    # MS5 Sections (in entry screen order)
    header: MS5HeaderData = field(default_factory=MS5HeaderData)
    customers: MS5CustomerData = field(default_factory=MS5CustomerData)
    product: MS5ProductData = field(default_factory=MS5ProductData)
    commercial: MS5CommercialTerms = field(default_factory=MS5CommercialTerms)
    delivery: MS5DeliveryData = field(default_factory=MS5DeliveryData)
    classification: MS5ClassificationData = field(default_factory=MS5ClassificationData)
    others: MS5OthersData = field(default_factory=MS5OthersData)

    # Engines and Items
    engines: list[MS5Engine] = field(default_factory=list)

    # Cross-references (resolved after parsing)
    linked_sap_order: Optional[str] = None
    linked_opportunity: Optional[dict] = None

    # Computed fields
    total_engines: int = 0
    total_items: int = 0
    total_value: float = 0.0

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "order_id": self.order_id,
            "file_name": self.file_name,
            "created_date": self.created_date,
            "source": self.source,
            "message_id": self.message_id,
            "order_status": self.order_status,
            "header": {
                "sales_org": self.header.sales_org,
                "distribution_channel": self.header.distribution_channel,
                "division": self.header.division,
                "sales_office": self.header.sales_office,
                "order_type": self.header.order_type,
                "ipas_order_number": self.header.ipas_order_number,
                "ipas_project_number": self.header.ipas_project_number,
                "document_date": self.header.document_date,
                "purchase_order_number": self.header.purchase_order_number,
                "purchase_order_date": self.header.purchase_order_date,
            },
            "customers": {
                "sold_to_party": self.customers.sold_to_party,
                "sold_to_name": self.customers.sold_to_name,
                "ship_to_party": self.customers.ship_to_party,
                "ship_to_name": self.customers.ship_to_name,
                "bill_to_party": self.customers.bill_to_party,
                "bill_to_name": self.customers.bill_to_name,
                "payer": self.customers.payer,
                "end_customer": self.customers.end_customer,
                "end_customer_country": self.customers.end_customer_country,
                "end_customer_group": self.customers.end_customer_group,
            },
            "product": {
                "engine_type": self.product.engine_type,
                "series": self.product.series,
                "cylinder": self.product.cylinder,
                "power": self.product.power,
                "power_unit": self.product.power_unit,
                "engine_speed": self.product.engine_speed,
                "application_coarse": self.product.application_coarse,
                "application_fine": self.product.application_fine,
                "application_group": self.product.application_group,
                "type_of_service": self.product.type_of_service,
                "product_category": self.product.product_category,
                "propulsion_type": self.product.propulsion_type,
                "propulsion_sup_key": self.product.propulsion_sup_key,
                "business_type": self.product.business_type,
                "ipas_object_type": self.product.ipas_object_type,
                "project_type": self.product.project_type,
            },
            "commercial": {
                "incoterms_1": self.commercial.incoterms_1,
                "incoterms_2": self.commercial.incoterms_2,
                "payment_terms": self.commercial.payment_terms,
                "payment_terms_text": self.commercial.payment_terms_text,
                "currency_code": self.commercial.currency_code,
                "invoice_language": self.commercial.invoice_language,
                "billing_plan_relevant": self.commercial.billing_plan_relevant,
            },
            "delivery": {
                "delivery_location": self.delivery.delivery_location,
                "shipping_type": self.delivery.shipping_type,
                "direct_ship": self.delivery.direct_ship,
                "initiator_region": self.delivery.initiator_region,
                "target_region": self.delivery.target_region,
                "purchased_from_region": self.delivery.purchased_from_region,
                "producing_factory": self.delivery.producing_factory,
                "ordering_location": self.delivery.ordering_location,
            },
            "classification": {
                "classification_society": self.classification.classification_society,
                "emission_cert_authority": self.classification.emission_cert_authority,
                "flag_state": self.classification.flag_state,
                "exhaust_regulation": self.classification.exhaust_regulation,
                "construction_no_vessel": self.classification.construction_no_vessel,
                "shipbuilder_yard": self.classification.shipbuilder_yard,
            },
            "others": {
                "ipas_distribution_channel": self.others.ipas_distribution_channel,
                "penalty": self.others.penalty,
                "scope_of_supply_complete": self.others.scope_of_supply_complete,
                "demagnesation": self.others.demagnesation,
                "delivery_language": self.others.delivery_language,
            },
            "engines": [
                {
                    "engine_number": eng.engine_number,
                    "engine_type": eng.engine_type,
                    "quantity": eng.quantity,
                    "delivery_date": eng.delivery_date,
                    "ship_to_party": eng.ship_to_party,
                    "gross_price": eng.gross_price,
                    "items": [
                        {
                            "item_number": item.item_number,
                            "material": item.material,
                            "quantity": item.quantity,
                            "delivery_date": item.delivery_date,
                            "assembly_note": item.assembly_note,
                        }
                        for item in eng.items
                    ],
                }
                for eng in self.engines
            ],
            "summary": {
                "total_engines": self.total_engines,
                "total_items": self.total_items,
                "total_value": self.total_value,
                "currency": self.commercial.currency_code,
            },
            "linked_sap_order": self.linked_sap_order,
            "linked_opportunity": self.linked_opportunity,
        }


# =============================================================================
# IPAS XML Parser
# =============================================================================


class IPASOrderParser:
    """Parser for IPAS XML order files."""

    @staticmethod
    def parse_file(file_path: Path) -> IPASOrder:
        """Parse IPAS XML file into MS5 order structure.

        Args:
            file_path: Path to IPAS XML file

        Returns:
            IPASOrder with all fields mapped to MS5 structure
        """
        # Ensure file_path is a Path object
        if isinstance(file_path, str):
            file_path = Path(file_path)

        tree = ET.parse(file_path)
        root = tree.getroot()

        order = IPASOrder()
        order.file_name = file_path.name
        order.file_path = str(file_path)

        # Parse DocumentProperties
        doc_props = root.find("DocumentProperties")
        if doc_props is not None:
            order.created_date = doc_props.findtext("Created", "")
            order.source = doc_props.findtext("Source", "IPAS")
            order.format_version = doc_props.findtext("Format_Version", "")
            order.target_id = doc_props.findtext("Target_ID", "")
            order.target_desc = doc_props.findtext("Target_Desc", "")
            order.message_id = doc_props.findtext("Message_ID", "")

        # Parse Header
        header = root.find("Header")
        if header is not None:
            order.order_status = header.findtext("IPAS_Order_Status", "")
            order.order_id = header.findtext("IPAS_Order_Number", "")

            # Section 1: Header/Organization Data
            order.header = MS5HeaderData(
                ipas_order_number=header.findtext("IPAS_Order_Number", ""),
                ipas_project_number=header.findtext("IPAS_Project_Number", ""),
                document_date=header.findtext("Document_Date", ""),
                distribution_channel=header.findtext("Distr_Channel", ""),
                purchase_order_number=header.findtext("Purchase_Order_Number", ""),
                purchase_order_date=header.findtext("Purchase_Order_Date", ""),
            )

            # Section 2: Customer Data
            order.customers = MS5CustomerData(
                sold_to_party=header.findtext("Sold_To_Party", ""),
                ship_to_party=header.findtext("Ship_To_Party", ""),
                bill_to_party=header.findtext("Bill_To_Party", ""),
                end_customer=header.findtext("End_Customer", ""),
                end_customer_country=header.findtext("End_Customer_Country", ""),
                end_customer_group=header.findtext("End_Customer_Group", ""),
            )

            # Section 3: Product Data
            order.product = MS5ProductData(
                engine_type=header.findtext("Engine_Type", ""),
                series=header.findtext("Series", ""),
                cylinder=header.findtext("Cylinder", ""),
                power=header.findtext("Power", ""),
                power_unit=header.findtext("Power_Unit", "KW"),
                engine_speed=header.findtext("Engine_Speed", ""),
                application_coarse=header.findtext("Application_coarse", ""),
                application_fine=header.findtext("Application_fine", ""),
                application_group=header.findtext("Application_Group", ""),
                type_of_service=header.findtext("Type_Of_Service", ""),
                product_category=header.findtext("Product_Category", ""),
                propulsion_type=header.findtext("Propulsion_Type", ""),
                propulsion_sup_key=header.findtext("Propulsion", ""),
                business_type=header.findtext("Business_Type", ""),
                ipas_object_type=header.findtext("IPAS_Object_Type", ""),
                project_type=header.findtext("Project_Type", ""),
            )

            # Section 4: Commercial Terms
            billing_plan_rel = header.findtext("Billing_Plan_Rel", "") == "X"
            order.commercial = MS5CommercialTerms(
                incoterms_1=header.findtext("Incoterms_1", ""),
                incoterms_2=header.findtext("Incoterms_2", ""),
                payment_terms=header.findtext("Terms_Of_Payment", ""),
                currency_code=header.findtext("Currency_Code", ""),
                invoice_language=header.findtext("Invoice_Language", "EN"),
                delivery_note_language=header.findtext("Delivery_Note_Language", "EN"),
                billing_plan_relevant=billing_plan_rel,
            )

            # Section 5: Delivery Data
            direct_ship = header.findtext("Direct_Ship", "0") == "1"
            order.delivery = MS5DeliveryData(
                delivery_location=header.findtext("Delivery_Location", ""),
                direct_ship=direct_ship,
                initiator_region=header.findtext("Initiator_Region", ""),
                target_region=header.findtext("Target_Region", ""),
                purchased_from_region=header.findtext("Purchased_From_Region", ""),
                producing_factory=header.findtext("Producing_Factory", ""),
                ordering_location=header.findtext("Ordering_Location", ""),
            )

            # Section 6: Classification Data
            order.classification = MS5ClassificationData(
                classification_society=header.findtext("Classification_Society", ""),
                emission_cert_authority=header.findtext("Emission_Cert_Authority", ""),
                flag_state=header.findtext("Flag_State", ""),
                construction_no_vessel=header.findtext("Construction_No_Vessel", ""),
                shipbuilder_yard=header.findtext("Shipbuilder_Yard", ""),
            )

            # Section 7: Others (miscellaneous fields)
            order.others = MS5OthersData(
                ipas_distribution_channel=header.findtext("Distr_Channel", ""),
                penalty=header.findtext("Penalty", ""),
                scope_of_supply_complete=header.findtext(
                    "Scope_Of_Supply_Complete", ""
                ),
                demagnesation=header.findtext("Demagnesation", ""),
                delivery_language=header.findtext("Delivery_Note_Language", ""),
            )

        # Parse Engines and Items
        engines_elem = root.find("Engines")
        if engines_elem is not None:
            for engine_elem in engines_elem.findall("Engine"):
                engine = MS5Engine(
                    engine_number=engine_elem.findtext("Engine_Number", ""),
                    engine_type=engine_elem.findtext("Engine_Type", ""),
                    quantity=int(engine_elem.findtext("Quantity", "1")),
                    delivery_date=engine_elem.findtext("Delivery_Date", ""),
                    ship_to_party=engine_elem.findtext("Ship_To_Party", ""),
                    shipping_type=engine_elem.findtext("Shipping_Type", ""),
                    packaging_group=engine_elem.findtext("Packaging_Group", ""),
                    gross_price=float(
                        engine_elem.findtext("Gross_Price", "0").strip() or "0"
                    ),
                    absolute_discount=float(
                        engine_elem.findtext("Absolute_Discount", "0").strip() or "0"
                    ),
                    exhaust_regulation=engine_elem.findtext("Exhaust_Regulation", ""),
                )

                # Parse line items for this engine
                for item_elem in engine_elem.findall("Item"):
                    item = MS5OrderItem(
                        item_number=item_elem.findtext("Item_Number", ""),
                        engine_number=item_elem.findtext("Engine_Number", ""),
                        material=item_elem.findtext("Material", ""),
                        material_description=item_elem.findtext("Material_Desc", ""),
                        quantity=int(item_elem.findtext("Quantity", "1")),
                        delivery_date=item_elem.findtext("Delivery_Date", ""),
                        assembly_note=item_elem.findtext("Assembly_Note", ""),
                        packaging_group=item_elem.findtext("Packaging_Group", ""),
                        item_type=item_elem.get("Type", "M"),
                    )
                    engine.items.append(item)
                    order.total_items += 1

                order.engines.append(engine)
                order.total_engines += 1
                order.total_value += engine.gross_price

        # Update classification with first engine's exhaust regulation if header empty
        if not order.classification.exhaust_regulation and order.engines:
            order.classification.exhaust_regulation = order.engines[
                0
            ].exhaust_regulation

        logger.info(
            f"Parsed IPAS order {order.order_id}: "
            f"{order.total_engines} engines, {order.total_items} items, "
            f"value {order.commercial.currency_code} {order.total_value:,.2f}"
        )

        return order


# =============================================================================
# IPAS Order Service
# =============================================================================


class IPASOrderService:
    """Service for managing IPAS orders and SFTP folder monitoring."""

    def __init__(self, ipas_folder: Optional[Path] = None):
        """Initialize service.

        Args:
            ipas_folder: Folder to monitor for IPAS XML files
        """
        self.ipas_folder = ipas_folder or IPAS_FOLDER
        self._orders_cache: dict[str, IPASOrder] = {}
        self._last_scan: Optional[datetime] = None
        self._sftp_client = None

    def _get_sftp_client(self):
        """Lazy-initialize SFTP client."""
        if self._sftp_client is None:
            try:
                from lead_to_cash.integrations.ipas_sftp_client import (
                    IPASSFTPClient,
                )

                self._sftp_client = IPASSFTPClient(local_folder=self.ipas_folder)
            except ImportError:
                logger.debug("IPAS SFTP client not available")
        return self._sftp_client

    def sync_from_sftp(self) -> dict:
        """Sync new IPAS XML files from SFTP server to local folder.

        Returns:
            Summary dict with sync results
        """
        sftp = self._get_sftp_client()
        if sftp and sftp.is_configured:
            result = sftp.sync()
            if result.get("downloaded", 0) > 0:
                # Clear cache so new files get parsed
                self._orders_cache.clear()
            return result
        return {"connected": False, "error": "SFTP not configured", "downloaded": 0}

    def scan_folder(self) -> list[IPASOrder]:
        """Scan IPAS folder for XML files and parse them.

        Automatically syncs from SFTP first if configured.

        Returns:
            List of parsed IPAS orders
        """
        # Try SFTP sync first (no-op if not configured)
        sftp = self._get_sftp_client()
        if sftp and sftp.is_configured:
            try:
                sync_result = sftp.sync()
                if sync_result.get("downloaded", 0) > 0:
                    self._orders_cache.clear()
                    logger.info(
                        f"SFTP: Downloaded {sync_result['downloaded']} new files"
                    )
            except Exception as e:
                logger.warning(f"SFTP sync failed, using local files: {e}")

        orders = []

        if not self.ipas_folder.exists():
            logger.warning(f"IPAS folder not found: {self.ipas_folder}")
            return orders

        # Find all XML files
        for xml_file in self.ipas_folder.glob("*.XML"):
            try:
                # Skip if already cached
                file_key = str(xml_file)

                if file_key in self._orders_cache:
                    cached = self._orders_cache[file_key]
                    # Simple cache check - could be improved
                    orders.append(cached)
                    continue

                # Parse new/updated file
                order = IPASOrderParser.parse_file(xml_file)
                self._orders_cache[file_key] = order
                orders.append(order)

            except ET.ParseError as e:
                logger.error(f"Failed to parse {xml_file.name}: {e}")
            except Exception as e:
                logger.error(f"Error processing {xml_file.name}: {e}")

        # Also check lowercase .xml extension
        for xml_file in self.ipas_folder.glob("*.xml"):
            if str(xml_file) not in self._orders_cache:
                try:
                    order = IPASOrderParser.parse_file(xml_file)
                    self._orders_cache[str(xml_file)] = order
                    orders.append(order)
                except Exception as e:
                    logger.error(f"Error processing {xml_file.name}: {e}")

        self._last_scan = datetime.now()

        # Resolve cross-references: IPAS ↔ SAP Order ↔ Opportunity
        self._resolve_cross_references(orders)

        logger.info(f"Scanned IPAS folder: found {len(orders)} orders")

        return orders

    def _resolve_cross_references(self, orders: list[IPASOrder]) -> None:
        """Resolve IPAS ↔ SAP Order ↔ Opportunity links via PO number matching."""
        try:
            from lead_to_cash.integrations.cpi_simulator import (
                _get_dynamic_billing_docs,
                _get_simulated_sales_orders,
            )

            sap_orders = _get_simulated_sales_orders()
            billing_docs = _get_dynamic_billing_docs()

            # Build PO → SAP order index
            po_to_sap: dict[str, dict] = {}
            for order_num, order_data in sap_orders.items():
                po = order_data.get("header", {}).get("BSTNK", "")
                if po:
                    po_to_sap[po] = {
                        "order_number": order_num,
                        "linked_opportunity": order_data.get("linked_opportunity"),
                        "ipas_order_number": order_data.get("ipas_order_number"),
                    }

            for ipas_order in orders:
                po = ipas_order.header.purchase_order_number
                if po and po in po_to_sap:
                    sap_ref = po_to_sap[po]
                    ipas_order.linked_sap_order = sap_ref["order_number"]
                    ipas_order.linked_opportunity = sap_ref.get("linked_opportunity")
                    # Resolve payment terms text from billing docs
                    order_num = sap_ref["order_number"]
                    order_data = sap_orders.get(order_num, {})
                    bp_dates = order_data.get("billing_plan", {}).get("dates", [])
                    for date_item in bp_dates:
                        vbeln = date_item.get("VBELN", "")
                        if vbeln and date_item.get("FKSAF") == "B":
                            doc = billing_docs.get(vbeln, {})
                            pt_text = doc.get("payment_terms_text", "")
                            if pt_text:
                                ipas_order.commercial.payment_terms_text = pt_text
                            break
        except Exception as e:
            logger.debug(f"Could not resolve IPAS cross-references: {e}")

    def get_pending_orders(self) -> list[IPASOrder]:
        """Get all pending orders from the IPAS folder.

        Returns:
            List of IPAS orders ready for MS5 entry
        """
        return self.scan_folder()

    def get_pending_count(self) -> int:
        """Get count of pending IPAS orders.

        Returns:
            Number of XML files in IPAS folder
        """
        if not self.ipas_folder.exists():
            return 0

        count = len(list(self.ipas_folder.glob("*.XML")))
        count += len(list(self.ipas_folder.glob("*.xml")))
        return count

    def get_order(self, order_id: str) -> Optional[IPASOrder]:
        """Get a specific order by ID.

        Args:
            order_id: IPAS order number

        Returns:
            IPASOrder if found, None otherwise
        """
        # Scan if cache empty
        if not self._orders_cache:
            self.scan_folder()

        # Search cache
        for order in self._orders_cache.values():
            if order.order_id == order_id or order.message_id == order_id:
                return order

        return None

    def get_order_by_file(self, file_name: str) -> Optional[IPASOrder]:
        """Get order by file name.

        Args:
            file_name: XML file name (must be a simple filename, no path separators)

        Returns:
            IPASOrder if found, None if not found or invalid name
        """
        # Reject path separators and traversal attempts
        if "/" in file_name or "\\" in file_name or ".." in file_name:
            logger.warning(f"Rejected file name with path traversal: {file_name!r}")
            return None

        file_path = (self.ipas_folder / file_name).resolve()
        # Verify resolved path is still within the IPAS folder
        if not str(file_path).startswith(str(self.ipas_folder.resolve())):
            logger.warning(f"Rejected file outside IPAS folder: {file_path}")
            return None

        if file_path.exists():
            return IPASOrderParser.parse_file(file_path)
        return None

    def get_summary(self) -> dict[str, Any]:
        """Get summary of pending orders.

        Returns:
            Summary with counts and totals
        """
        orders = self.get_pending_orders()

        total_value = sum(o.total_value for o in orders)
        total_engines = sum(o.total_engines for o in orders)
        total_items = sum(o.total_items for o in orders)

        # Group by currency
        by_currency: dict[str, float] = {}
        for order in orders:
            curr = order.commercial.currency_code or "EUR"
            by_currency[curr] = by_currency.get(curr, 0) + order.total_value

        # SFTP status
        sftp = self._get_sftp_client()
        sftp_configured = sftp.is_configured if sftp else False

        return {
            "pending_count": len(orders),
            "total_engines": total_engines,
            "total_items": total_items,
            "total_value": total_value,
            "value_by_currency": by_currency,
            "last_scan": self._last_scan.isoformat() if self._last_scan else None,
            "folder": str(self.ipas_folder),
            "sftp_configured": sftp_configured,
            "sftp_host": sftp.host if sftp else None,
        }


# =============================================================================
# Module-level instance
# =============================================================================

# Singleton service instance
_service_instance: Optional[IPASOrderService] = None


def get_ipas_order_service() -> IPASOrderService:
    """Get the singleton IPAS order service instance."""
    global _service_instance
    if _service_instance is None:
        _service_instance = IPASOrderService()
    return _service_instance
