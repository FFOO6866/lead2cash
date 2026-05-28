"""
IPAS XML Parser Service.

Parses IPAS SUN FORMAT v1.0 XML files into structured order data
for MS5 SAP order creation.

Each XML file represents one IPAS order containing:
- DocumentProperties: metadata (message ID, source, timestamps)
- Header: order-level commercial/technical data
- Engines: 1..N engines with nested BOM items
- Partner_Information: customer and employee contacts

Source XML files are read from a configurable directory (IPAS_XML_DIR env var).
"""

import logging
import math
import os
from pathlib import Path

import defusedxml.ElementTree as SafeET  # M0-T07: XXE protection for parsing
from typing import Dict, List, Optional
from xml.etree.ElementTree import (
    Element,
)  # stdlib type only (defusedxml has no Element)

from ..config import config
from ..core.models import (
    IPASBOMItem,
    IPASDocumentProperties,
    IPASEngine,
    IPASHeader,
    IPASOrder,
    IPASPartner,
    IPASSummary,
)

logger = logging.getLogger(__name__)


class IPASXMLParser:
    """
    Parser for IPAS SUN FORMAT v1.0 XML files.

    Reads XML files from IPAS_XML_DIR, parses them into IPASOrder models,
    and provides query methods matching the production API endpoints.
    """

    def __init__(self, xml_dir: Optional[str] = None) -> None:
        self._xml_dir = xml_dir or config.ipas_xml_dir
        self._orders: Dict[str, IPASOrder] = {}
        self._loaded = False

    def _ensure_loaded(self) -> None:
        """Load XML files on first access."""
        if not self._loaded:
            self.load_all()

    def load_all(self) -> int:
        """
        Load and parse all XML files from the configured directory.

        Returns:
            Number of orders successfully parsed.
        """
        self._orders.clear()

        if not self._xml_dir:
            logger.warning("IPAS_XML_DIR not configured — no IPAS orders available")
            self._loaded = True
            return 0

        xml_path = Path(self._xml_dir)
        if not xml_path.exists():
            logger.warning("IPAS_XML_DIR does not exist: %s", self._xml_dir)
            self._loaded = True
            return 0

        # Parse all .xml and .XML files
        xml_files = list(xml_path.glob("*.xml")) + list(xml_path.glob("*.XML"))
        # Deduplicate (on case-insensitive filesystems)
        seen = set()
        unique_files = []
        for f in xml_files:
            key = str(f).lower()
            if key not in seen:
                seen.add(key)
                unique_files.append(f)

        for xml_file in unique_files:
            try:
                order = self._parse_file(xml_file)
                if order:
                    self._orders[order.header.ipas_order_number] = order
                    logger.info(
                        "Parsed IPAS order %s: %d engines, %.2f total value from %s",
                        order.header.ipas_order_number,
                        order.total_engines,
                        order.total_value,
                        xml_file.name,
                    )
            except Exception:
                logger.exception("Failed to parse IPAS XML: %s", xml_file)

        self._loaded = True
        logger.info("Loaded %d IPAS orders from %s", len(self._orders), self._xml_dir)
        return len(self._orders)

    def get_summary(self) -> IPASSummary:
        """Get summary of all loaded IPAS orders."""
        self._ensure_loaded()

        order_summaries = []
        total_engines = 0
        total_value = 0.0

        for order_num, order in self._orders.items():
            total_engines += order.total_engines
            total_value += order.total_value
            order_summaries.append(
                {
                    "order_number": order_num,
                    "engine_type": order.header.engine_type,
                    "sold_to_party": order.header.sold_to_party,
                    "total_engines": order.total_engines,
                    "total_bom_items": order.total_bom_items,
                    "total_value": order.total_value,
                    "currency": order.header.currency_code,
                    "document_date": order.header.document_date,
                    "source_file": order.source_file,
                }
            )

        return IPASSummary(
            total_orders=len(self._orders),
            total_engines=total_engines,
            total_value=total_value,
            orders=order_summaries,
        )

    def get_all_orders(self) -> List[IPASOrder]:
        """Return all parsed IPAS orders."""
        self._ensure_loaded()
        return list(self._orders.values())

    def get_order(self, order_number: str) -> Optional[IPASOrder]:
        """Get a single IPAS order by order number."""
        self._ensure_loaded()
        return self._orders.get(order_number)

    def reload(self) -> int:
        """Force reload all XML files."""
        self._loaded = False
        return self.load_all()

    # ------------------------------------------------------------------
    # XML Parsing
    # ------------------------------------------------------------------

    def _parse_file(self, xml_file: Path) -> Optional[IPASOrder]:
        """Parse a single IPAS XML file into an IPASOrder."""
        tree = SafeET.parse(xml_file)
        root = tree.getroot()

        if root.tag != "IPAS_Order":
            logger.warning(
                "Skipping %s — root element is '%s', expected 'IPAS_Order'",
                xml_file,
                root.tag,
            )
            return None

        doc_props = self._parse_document_properties(root)
        header = self._parse_header(root)
        engines = self._parse_engines(root)
        partners = self._parse_partners(root)

        total_engines = len(engines)
        total_bom_items = sum(len(e.items) for e in engines)
        total_value = sum(e.gross_price * e.quantity for e in engines)

        return IPASOrder(
            document_properties=doc_props,
            header=header,
            engines=engines,
            partners=partners,
            total_engines=total_engines,
            total_bom_items=total_bom_items,
            total_value=total_value,
            source_file=xml_file.name,
        )

    def _parse_document_properties(self, root: Element) -> IPASDocumentProperties:
        """Parse DocumentProperties section."""
        dp = root.find("DocumentProperties")
        if dp is None:
            return IPASDocumentProperties(created="", message_id="unknown")

        return IPASDocumentProperties(
            created=self._text(dp, "Created"),
            type=self._text(dp, "Type", "IPAS"),
            format_version=self._text(dp, "Format_Version", "1.0"),
            source=self._text(dp, "Source", "IPAS7.1"),
            target_id=self._text(dp, "Target_ID"),
            target_desc=self._text(dp, "Target_Desc"),
            message_id=self._text(dp, "Message_ID", "unknown"),
            draft_version=self._text(dp, "Draft_Version", "0"),
        )

    def _parse_header(self, root: Element) -> IPASHeader:
        """Parse Header section."""
        h = root.find("Header")
        if h is None:
            return IPASHeader(ipas_order_number="unknown")

        return IPASHeader(
            ipas_order_status=self._text(h, "IPAS_Order_Status"),
            ipas_project_number=self._text(h, "IPAS_Project_Number"),
            ipas_order_number=self._text(h, "IPAS_Order_Number", "unknown"),
            ipas_order_version=self._text(h, "IPAS_Order_Version", "00"),
            document_date=self._text(h, "Document_Date"),
            engine_type=self._text(h, "Engine_Type"),
            series=self._text(h, "Series"),
            cylinder=self._text(h, "Cylinder"),
            power=self._text(h, "Power"),
            engine_speed=self._text(h, "Engine_Speed"),
            sold_to_party=self._text(h, "Sold_To_Party"),
            bill_to_party=self._text(h, "Bill_To_Party"),
            ship_to_party=self._text(h, "Ship_To_Party"),
            end_customer=self._text(h, "End_Customer"),
            end_customer_country=self._text(h, "End_Customer_Country"),
            purchase_order_number=self._text(h, "Purchase_Order_Number"),
            purchase_order_date=self._text(h, "Purchase_Order_Date"),
            incoterms_1=self._text(h, "Incoterms_1"),
            incoterms_2=self._text(h, "Incoterms_2"),
            currency_code=self._text(h, "Currency_Code"),
            terms_of_payment=self._text(h, "Terms_Of_Payment"),
            distribution_channel=self._text(h, "Distr_Channel"),
            application_coarse=self._text(h, "Application_coarse"),
            application_fine=self._text(h, "Application_fine"),
            business_type=self._text(h, "Business_Type"),
            classification_society=self._text(h, "Classification_Society"),
            emission_cert_authority=self._text(h, "Emission_Cert_Authority"),
            billing_plan_rel=self._text(h, "Billing_Plan_Rel"),
            product_category=self._text(h, "Product_Category"),
            power_unit=self._text(h, "Power_Unit", "KW"),
        )

    def _parse_engines(self, root: Element) -> List[IPASEngine]:
        """Parse Engines section with nested BOM Items."""
        engines_el = root.find("Engines")
        if engines_el is None:
            return []

        engines: List[IPASEngine] = []
        for eng_el in engines_el.findall("Engine"):
            items = self._parse_bom_items(eng_el)
            gross_price = self._safe_float(
                self._text(eng_el, "Gross_Price", "0").strip()
            )

            engine = IPASEngine(
                engine_number=self._text(eng_el, "Engine_Number"),
                engine_type=self._text(eng_el, "Engine_Type"),
                quantity=self._int(eng_el, "Quantity", 1),
                delivery_date=self._text(eng_el, "Delivery_Date"),
                ship_to_party=self._text(eng_el, "Ship_To_Party"),
                shipping_type=self._text(eng_el, "Shipping_Type"),
                packaging_group=self._text(eng_el, "Packaging_Group"),
                gross_price=gross_price,
                absolute_discount=self._safe_float(
                    self._text(eng_el, "Absolute_Discount", "0") or "0"
                ),
                acceptance_with_customer=self._text(
                    eng_el, "Acceptance_With_Customer", "0"
                ),
                exhaust_regulation=self._text(eng_el, "Exhaust_Regulation"),
                take_from_stock=self._text(eng_el, "Take_From_Stock", "0"),
                items=items,
            )
            engines.append(engine)

        return engines

    def _parse_bom_items(self, engine_el: Element) -> List[IPASBOMItem]:
        """Parse BOM Item elements within an Engine."""
        items: List[IPASBOMItem] = []
        for item_el in engine_el.findall("Item"):
            item_type = item_el.get("Type", "M")
            items.append(
                IPASBOMItem(
                    item_number=self._text(item_el, "Item_Number"),
                    engine_number=self._text(item_el, "Engine_Number"),
                    material=self._text(item_el, "Material"),
                    material_desc=self._text(item_el, "Material_Desc"),
                    quantity=self._int(item_el, "Quantity", 1),
                    item_type=item_type,
                    assembly_note=self._text(item_el, "Assembly_Note"),
                    delivery_date=self._text(item_el, "Delivery_Date"),
                    packaging_group=self._text(item_el, "Packaging_Group"),
                    ship_to_party=self._text(item_el, "Ship_To_Party"),
                    sub_object_number=self._text(item_el, "Sub_Object_Number"),
                )
            )
        return items

    def _parse_partners(self, root: Element) -> List[IPASPartner]:
        """Parse Partner_Information section."""
        pi = root.find("Partner_Information")
        if pi is None:
            return []

        partners: List[IPASPartner] = []

        for cust_el in pi.findall("Customer"):
            partners.append(
                IPASPartner(
                    type=cust_el.get("Type", "Unknown"),
                    customer_code=self._text(cust_el, "Customer_Code"),
                    name1=self._text(cust_el, "Name1"),
                    name2=self._text(cust_el, "Name2"),
                    country=self._text(cust_el, "Country"),
                    city=self._text(cust_el, "City"),
                )
            )

        for emp_el in pi.findall("Employee"):
            partners.append(
                IPASPartner(
                    type=emp_el.get("Type", "Unknown"),
                    partner_id=self._text(emp_el, "Partner_ID"),
                    first_name=self._text(emp_el, "First_Name"),
                    last_name=self._text(emp_el, "Last_Name"),
                    department=self._text(emp_el, "Department_Desc"),
                    phone=self._text(emp_el, "Phone"),
                    email=self._text(emp_el, "Mail"),
                )
            )

        return partners

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _text(parent: Element, tag: str, default: str = "") -> str:
        """Get text content of a child element, or default if missing/empty."""
        el = parent.find(tag)
        if el is None or el.text is None:
            return default
        return el.text.strip() if el.text.strip() else default

    @staticmethod
    def _safe_float(value: str) -> float:
        """Safely convert a string to float, rejecting NaN/Inf."""
        try:
            result = float(value)
            return result if math.isfinite(result) else 0.0
        except (ValueError, TypeError):
            return 0.0

    @staticmethod
    def _int(parent: Element, tag: str, default: int = 0) -> int:
        """Get integer content of a child element."""
        el = parent.find(tag)
        if el is None or el.text is None:
            return default
        try:
            return int(el.text.strip())
        except ValueError:
            return default


class IPASParseError(Exception):
    """Error parsing IPAS XML file."""

    pass
