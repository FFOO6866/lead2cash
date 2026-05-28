"""
FinanceOps Data Service

Aggregates billing and collections data from SAP CPI/MS5.
"""

import logging
from datetime import date
from typing import Optional

from lead_to_cash.integrations.ms5_client import MS5Client
from lead_to_cash.services.financeops.models import (
    BillingItem,
    BillingStatus,
    BillingSummary,
)
from lead_to_cash.services.financeops.payment_terms import PaymentTermsHarmonizer

logger = logging.getLogger(__name__)


class FinOpsDataService:
    """
    Service for aggregating billing and collections data.

    Retrieves data from SAP CPI/MS5 simulator and provides
    aggregated views for the FinanceOps dashboard.
    """

    def __init__(self, cpi_client=None):
        """
        Initialize the data service.

        Args:
            cpi_client: CPI client instance (real SAP CPI required)
        """
        self._cpi_client = cpi_client
        self._ms5_client: Optional[MS5Client] = None
        self._harmonizer = PaymentTermsHarmonizer()
        self._connected = False

    async def connect(self) -> None:
        """Establish connection to SAP systems."""
        if self._connected:
            return

        if self._cpi_client is None:
            from lead_to_cash.integrations.client_factory import get_cpi_client

            self._cpi_client, _ = await get_cpi_client(use_case="FinOps")
            if not self._cpi_client:
                logger.warning("FinOpsDataService: SAP CPI not available")
                return

        await self._cpi_client.connect()
        self._ms5_client = MS5Client(cpi_client=self._cpi_client)
        await self._ms5_client.connect()
        self._connected = True
        logger.info("FinOpsDataService connected")

    async def disconnect(self) -> None:
        """Close connections."""
        if self._ms5_client:
            await self._ms5_client.disconnect()
        if self._cpi_client:
            await self._cpi_client.disconnect()
        self._connected = False

    async def __aenter__(self) -> "FinOpsDataService":
        """Async context manager entry."""
        await self.connect()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb) -> None:
        """Async context manager exit."""
        await self.disconnect()

    def _ensure_connected(self) -> None:
        """Ensure service is connected."""
        if not self._connected:
            raise RuntimeError("FinOpsDataService not connected")

    async def get_summary_counts(self) -> BillingSummary:
        """
        Get summary counts for dashboard badges.

        Badge logic:
        - Billing: Items pending invoice creation (PENDING_BILLING)
        - Collections: Items awaiting payment (PENDING_COLLECTION, PARTIALLY_PAID, OVERDUE)
        - Overdue: Subset of collections that are past due (included in collections count)

        Returns:
            BillingSummary with billing, collections, and overdue counts
        """
        self._ensure_connected()

        # Get billing documents from simulator
        billing_docs = await self._get_billing_documents()

        summary = BillingSummary(as_of_date=date.today())

        for doc in billing_docs:
            if doc.status == BillingStatus.PENDING_BILLING:
                # Billing = items needing invoice
                summary.billing_count += 1
                summary.billing_amount += doc.total_amount
            elif doc.status in (
                BillingStatus.PENDING_COLLECTION,
                BillingStatus.PARTIALLY_PAID,
                BillingStatus.OVERDUE,  # OVERDUE is part of collections
            ):
                # Collections = items awaiting payment (includes overdue)
                summary.collections_count += 1
                summary.collections_amount += doc.total_amount

                # Track overdue separately (subset of collections)
                if doc.status == BillingStatus.OVERDUE:
                    summary.overdue_count += 1
                    summary.overdue_amount += doc.total_amount

            # Track downpayments needing action (across all actionable statuses)
            if doc.is_downpayment and doc.status in (
                BillingStatus.PENDING_BILLING,
                BillingStatus.PENDING_COLLECTION,
                BillingStatus.OVERDUE,
            ):
                summary.downpayment_count += 1
                summary.downpayment_amount += doc.total_amount

        # Set primary currency (use the most common)
        if billing_docs:
            currencies = [doc.currency for doc in billing_docs]
            summary.currency = max(set(currencies), key=currencies.count)

        return summary

    async def get_billing_items(
        self,
        customer_id: Optional[str] = None,
        status: Optional[str] = None,
    ) -> list[BillingItem]:
        """
        Get billing items, optionally filtered.

        Filtering happens at the CPI/MCP source for efficiency (A2A pattern).

        Args:
            customer_id: Filter by customer ID
            status: Filter by status (PENDING_BILLING, PENDING_COLLECTION, etc.)

        Returns:
            List of BillingItem objects
        """
        self._ensure_connected()

        # Pass filters to source (CPI simulator) - A2A pattern
        billing_docs = await self._get_billing_documents(
            customer_id=customer_id,
            status=status,
        )

        return billing_docs

    async def get_collections_items(
        self,
        customer_id: Optional[str] = None,
        status: Optional[str] = None,
    ) -> list[BillingItem]:
        """
        Get items requiring collection action.

        Customer filter is passed to CPI source (A2A pattern).
        Status filter for collection types applied locally since CPI
        only supports single status filter.

        Args:
            customer_id: Filter by customer ID (passed to CPI source)
            status: Filter by specific status

        Returns:
            List of BillingItem objects in collection status
        """
        self._ensure_connected()

        # Pass customer filter to source (A2A pattern)
        # Don't pass status - we need to filter for multiple collection statuses
        billing_docs = await self._get_billing_documents(
            customer_id=customer_id,
            status=status,  # If specific status requested, pass it
        )

        # If no specific status requested, filter to collection-relevant statuses
        if not status:
            collection_statuses = {
                BillingStatus.PENDING_COLLECTION,
                BillingStatus.PARTIALLY_PAID,
                BillingStatus.OVERDUE,
            }
            billing_docs = [d for d in billing_docs if d.status in collection_statuses]

        return billing_docs

    async def get_aging_buckets(self, customer_id: Optional[str] = None) -> dict:
        """
        Get aging bucket breakdown.

        Four buckets:
        - CURRENT (green): Not overdue
        - 0-30 (amber): 1-30 days overdue
        - 30-45 (orange): 31-45 days overdue
        - 45+ (red): 46+ days overdue

        Args:
            customer_id: Optional SAP customer ID to filter by

        Returns:
            Dict with aging buckets and their counts/amounts
        """
        self._ensure_connected()

        billing_docs = await self._get_billing_documents()

        # Filter by customer if specified
        if customer_id:
            billing_docs = [d for d in billing_docs if d.customer_id == customer_id]

        buckets = {
            "CURRENT": {"count": 0, "amount": 0.0},
            "0-30": {"count": 0, "amount": 0.0},
            "30-45": {"count": 0, "amount": 0.0},
            "45+": {"count": 0, "amount": 0.0},
        }

        for doc in billing_docs:
            bucket = doc.aging_bucket
            if bucket == "CURRENT":
                buckets["CURRENT"]["count"] += 1
                buckets["CURRENT"]["amount"] += doc.total_amount
            elif bucket == "0-30":
                buckets["0-30"]["count"] += 1
                buckets["0-30"]["amount"] += doc.total_amount
            elif bucket == "30-45":
                buckets["30-45"]["count"] += 1
                buckets["30-45"]["amount"] += doc.total_amount
            else:
                # 45+ and any legacy bucket values
                buckets["45+"]["count"] += 1
                buckets["45+"]["amount"] += doc.total_amount

        return buckets

    async def get_payment_terms(self, customer_id: str) -> Optional[dict]:
        """
        Get harmonized payment terms for a customer.

        Args:
            customer_id: SAP customer ID

        Returns:
            Dict with harmonized payment terms or None
        """
        self._ensure_connected()

        try:
            # Get customer commercial terms from MS5
            customer = await self._ms5_client.get_customer(customer_id)
            if not customer:
                return None

            # Get payment terms text (ZTERM)
            zterm = getattr(customer, "zterm", "")
            if not zterm:
                return None

            # Harmonize the payment terms
            harmonized = self._harmonizer.parse(zterm)
            return harmonized.to_dict()

        except Exception as e:
            logger.error(f"Error getting payment terms for {customer_id}: {e}")
            return None

    async def get_payment_terms_text(self, document_number: str) -> str:
        """Get payment terms full text for a billing document via RFC_READ_TEXT.

        Args:
            document_number: SAP billing document number

        Returns:
            Formatted payment terms text string
        """
        self._ensure_connected()
        try:
            return await self._ms5_client.get_payment_terms_text(document_number)
        except Exception as e:
            logger.warning(
                f"Failed to get payment terms text for {document_number}: {e}"
            )
            return ""

    async def get_downpayment_alerts(
        self,
        customer_id: Optional[str] = None,
    ) -> list[BillingItem]:
        """
        Get downpayment requests that need attention.

        Returns FAZ (downpayment) documents that are:
        - PENDING_BILLING: DP request needs to be created/sent
        - PENDING_COLLECTION: DP request sent, awaiting payment
        - OVERDUE: DP request past due

        Args:
            customer_id: Optional SAP customer ID to filter by

        Returns:
            List of BillingItem objects for downpayment requests needing action
        """
        self._ensure_connected()

        billing_docs = await self._get_billing_documents(customer_id=customer_id)

        # Filter to FAZ (downpayment) docs that need action
        actionable_statuses = {
            BillingStatus.PENDING_BILLING,
            BillingStatus.PENDING_COLLECTION,
            BillingStatus.OVERDUE,
        }
        return [
            doc
            for doc in billing_docs
            if doc.is_downpayment and doc.status in actionable_statuses
        ]

    async def get_overdue_downpayments(
        self,
        customer_id: Optional[str] = None,
    ) -> list[BillingItem]:
        """
        Get overdue downpayment requests requiring collection action.

        Returns FAZ documents that are past their due date.

        Args:
            customer_id: Optional SAP customer ID to filter by

        Returns:
            List of overdue downpayment BillingItem objects
        """
        self._ensure_connected()

        billing_docs = await self._get_billing_documents(customer_id=customer_id)

        return [
            doc
            for doc in billing_docs
            if doc.is_downpayment and doc.status == BillingStatus.OVERDUE
        ]

    async def get_payment_status(
        self,
        customer_id: Optional[str] = None,
        sales_order: Optional[str] = None,
    ) -> dict:
        """
        Get comprehensive payment status combining billing docs and milestones.

        Provides a unified view of:
        - Downpayment requests (FAZ) with clearing status
        - Milestone invoices (F2) with payment status
        - Billing plan milestones from sales orders

        Args:
            customer_id: Optional SAP customer ID to filter by
            sales_order: Optional sales order number to filter by

        Returns:
            Dict with downpayments, invoices, and summary statistics
        """
        self._ensure_connected()

        billing_docs = await self._get_billing_documents(customer_id=customer_id)

        # Filter by sales order if specified
        if sales_order:
            billing_docs = [d for d in billing_docs if d.sales_order == sales_order]

        # Separate downpayments from invoices
        downpayments = [d for d in billing_docs if d.is_downpayment]
        invoices = [d for d in billing_docs if not d.is_downpayment]

        # Calculate summary
        total_dp_amount = sum(d.total_amount for d in downpayments)
        paid_dp_amount = sum(
            d.total_amount for d in downpayments if d.status == BillingStatus.PAID
        )
        pending_dp_amount = sum(
            d.total_amount
            for d in downpayments
            if d.status
            in (
                BillingStatus.PENDING_BILLING,
                BillingStatus.PENDING_COLLECTION,
                BillingStatus.OVERDUE,
            )
        )
        overdue_dp_amount = sum(
            d.total_amount for d in downpayments if d.status == BillingStatus.OVERDUE
        )

        total_inv_amount = sum(d.total_amount for d in invoices)
        paid_inv_amount = sum(
            d.total_amount for d in invoices if d.status == BillingStatus.PAID
        )
        pending_inv_amount = sum(
            d.total_amount
            for d in invoices
            if d.status
            in (
                BillingStatus.PENDING_BILLING,
                BillingStatus.PENDING_COLLECTION,
                BillingStatus.OVERDUE,
                BillingStatus.PARTIALLY_PAID,
            )
        )
        overdue_inv_amount = sum(
            d.total_amount for d in invoices if d.status == BillingStatus.OVERDUE
        )

        # Determine primary currency
        all_currencies = [d.currency for d in billing_docs]
        currency = (
            max(set(all_currencies), key=all_currencies.count)
            if all_currencies
            else "USD"
        )

        return {
            "downpayments": [d.to_dict() for d in downpayments],
            "invoices": [d.to_dict() for d in invoices],
            "summary": {
                "total_documents": len(billing_docs),
                "downpayment_count": len(downpayments),
                "invoice_count": len(invoices),
                "currency": currency,
                "downpayment_total": total_dp_amount,
                "downpayment_paid": paid_dp_amount,
                "downpayment_pending": pending_dp_amount,
                "downpayment_overdue": overdue_dp_amount,
                "invoice_total": total_inv_amount,
                "invoice_paid": paid_inv_amount,
                "invoice_pending": pending_inv_amount,
                "invoice_overdue": overdue_inv_amount,
            },
            "customer_id": customer_id,
            "sales_order": sales_order,
        }

    async def _get_billing_documents(
        self,
        customer_id: Optional[str] = None,
        status: Optional[str] = None,
    ) -> list[BillingItem]:
        """
        Get billing documents from SAP via MCP/CPI.

        Args:
            customer_id: Optional SAP customer ID to filter by
            status: Optional status filter (PENDING_BILLING, PENDING_COLLECTION, etc.)

        Returns:
            List of BillingItem objects
        """
        # Call the simulator's billing documents handler with filters
        # This follows A2A pattern - filter at source, not in Python
        try:
            payload = {}
            if customer_id:
                payload["customer_id"] = customer_id
            if status:
                payload["status"] = status

            response = await self._cpi_client.send_request(
                iflow_name="MS5GetBillingDocuments",
                payload=payload,
            )

            if not response.get("success"):
                logger.warning("Failed to get billing documents from simulator")
                return []

            documents = response.get("documents", [])
            billing_items = []

            today = date.today()

            for doc in documents:
                # Parse payment terms
                payment_text = doc.get("payment_terms_text", "")
                harmonized_terms = self._harmonizer.parse(payment_text)

                # Parse dates
                doc_date = self._parse_date(doc.get("document_date"))
                due_date = self._parse_date(doc.get("due_date"))

                # Calculate days and status
                days_to_action = 0
                status = BillingStatus(doc.get("status", "PENDING_BILLING"))
                aging_bucket = "CURRENT"

                if due_date:
                    days_to_action = (due_date - today).days

                    # Only override to OVERDUE if status is not already terminal/special
                    # PAID: already settled, past due date is expected
                    # DISPUTED: under dispute, should not trigger escalation
                    if days_to_action < 0 and status not in (
                        BillingStatus.PAID,
                        BillingStatus.DISPUTED,
                    ):
                        status = BillingStatus.OVERDUE
                        overdue_days = abs(days_to_action)
                        # 4-bucket aging: CURRENT, 0-30 (amber), 30-45 (orange), 45+ (red)
                        if overdue_days > 45:
                            aging_bucket = "45+"
                        elif overdue_days > 30:
                            aging_bucket = "30-45"
                        else:
                            aging_bucket = "0-30"

                # Parse clearing fields (for downpayment requests)
                clearing_date = self._parse_date(doc.get("clearing_date"))

                billing_item = BillingItem(
                    document_number=doc.get("document_number", ""),
                    customer_id=doc.get("customer_id", ""),
                    customer_name=doc.get("customer_name", ""),
                    document_date=doc_date or today,
                    total_amount=doc.get("amount", 0.0),
                    currency=doc.get("currency", "USD"),
                    payment_term=harmonized_terms,
                    status=status,
                    next_action_date=due_date,
                    days_to_action=days_to_action,
                    aging_bucket=aging_bucket,
                    billing_type=doc.get("billing_type", "F2"),
                    sales_order=doc.get("sales_order", ""),
                    clearing_date=clearing_date,
                    clearing_doc=doc.get("clearing_doc", "") or "",
                )
                billing_items.append(billing_item)

            return billing_items

        except Exception as e:
            logger.error(f"Error getting billing documents: {e}")
            return []

    def _parse_date(self, date_str: Optional[str]) -> Optional[date]:
        """Parse date string to date object."""
        if not date_str:
            return None
        try:
            return date.fromisoformat(date_str)
        except (ValueError, TypeError):
            return None
