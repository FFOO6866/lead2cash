"""
Payment Terms Harmonization Service

Parses complex SAP payment terms text into structured data.

Sample input formats:
- "90 days after date of invoice"
- "20% advance payment by TT within 30 days, 80% balance before shipment"
- "10% upon order, 10% 9mo before delivery, 80% balance at FCA"
- "30% DP by TT, 70% by L/C 6 weeks before shipment"
- "100% Irrevocable L/C at Sight"
"""

import logging
import re
from typing import Optional

from lead_to_cash.services.financeops.models import (
    HarmonizedPaymentTerm,
    PaymentMethod,
    PaymentMilestone,
    PaymentTermType,
    TriggerEvent,
)

logger = logging.getLogger(__name__)


class PaymentTermsHarmonizer:
    """
    Parse and standardize SAP payment terms text.

    Handles complex milestone-based payment terms from SAP free-text fields.
    """

    # Regex patterns for extraction
    PERCENTAGE_PATTERN = re.compile(r"(\d+(?:\.\d+)?)\s*%")
    DAYS_PATTERN = re.compile(r"(\d+)\s*days?", re.IGNORECASE)
    MONTHS_PATTERN = re.compile(r"(\d+)\s*(?:months?|mo)", re.IGNORECASE)
    WEEKS_PATTERN = re.compile(r"(\d+)\s*weeks?", re.IGNORECASE)
    AMOUNT_PATTERN = re.compile(
        r"(?:EUR|USD|SGD|AUD|GBP)\s*([\d,]+(?:\.\d+)?)", re.IGNORECASE
    )
    CURRENCY_PATTERN = re.compile(r"(EUR|USD|SGD|AUD|GBP)", re.IGNORECASE)

    # Payment method keywords
    TT_KEYWORDS = [
        "t/t",
        "tt",
        "telegraphic transfer",
        "wire transfer",
        "bank transfer",
    ]
    LC_KEYWORDS = ["l/c", "lc", "letter of credit", "documentary credit"]
    LC_SIGHT_KEYWORDS = ["at sight", "sight"]
    CREDIT_LINE_KEYWORDS = ["credit line", "credit facility", "utilise credit"]

    # Trigger event keywords
    TRIGGER_KEYWORDS = {
        TriggerEvent.ORDER_PLACEMENT: [
            "upon order",
            "order placement",
            "upon po",
            "receipt of po",
            "upon receiving",
            "order confirmation",
            "po confirmation",
        ],
        TriggerEvent.CONTRACT_SIGNING: [
            "contract signing",
            "signing of contract",
            "after contract",
        ],
        TriggerEvent.INVOICE: [
            "upon invoice",
            "receipt of invoice",
            "from invoice",
            "after invoice",
            "date of invoice",
        ],
        TriggerEvent.BEFORE_SHIPMENT: [
            "before shipment",
            "prior to shipment",
            "before dispatch",
            "before delivery",
            "prior to delivery",
            "before collection",
        ],
        TriggerEvent.BEFORE_EXW: ["before exw", "before ex-work", "ex-works", "exw"],
        TriggerEvent.FCA: ["fca", "free carrier"],
        TriggerEvent.FAT: ["fat", "factory acceptance", "after fat"],
        TriggerEvent.SAT: ["sat", "site acceptance", "after sat"],
        TriggerEvent.NOR: ["nor", "notification of readiness", "ready for shipment"],
        TriggerEvent.DELIVERY: ["upon delivery", "at delivery", "after delivery"],
        TriggerEvent.DRAWING_DELIVERY: ["drawing", "drawings"],
        TriggerEvent.COMMISSIONING: ["commissioning", "upon commissioning"],
    }

    # Milestone type keywords
    ADVANCE_KEYWORDS = [
        "advance",
        "down payment",
        "downpayment",
        "dp",
        "deposit",
        "down-payment",
        "1st payment",
        "first payment",
    ]
    BALANCE_KEYWORDS = ["balance", "final", "remaining", "rest", "last payment"]
    INTERIM_KEYWORDS = [
        "interim",
        "progress",
        "2nd payment",
        "second payment",
        "intermediate",
    ]

    def __init__(self):
        """Initialize the harmonizer."""
        pass

    def parse(self, raw_text: str) -> HarmonizedPaymentTerm:
        """
        Parse payment terms text into structured format.

        Args:
            raw_text: Raw payment terms text from SAP

        Returns:
            HarmonizedPaymentTerm with parsed milestones
        """
        if not raw_text or not raw_text.strip():
            return HarmonizedPaymentTerm(
                raw_text="",
                term_type=PaymentTermType.UNKNOWN,
                confidence=0.0,
                parsing_notes=["Empty input"],
            )

        # Normalize text
        text = raw_text.strip()
        text_lower = text.lower()

        # Initialize result
        result = HarmonizedPaymentTerm(raw_text=text)
        notes = []

        # Detect payment methods
        result.has_lc = self._contains_any(text_lower, self.LC_KEYWORDS)
        result.has_bank_guarantee = (
            "bank guarantee" in text_lower or "bg" in text_lower.split()
        )

        # Extract milestones
        milestones = self._extract_milestones(text)
        result.milestones = milestones

        if milestones:
            # Calculate totals
            result.total_advance_pct = sum(
                m.percentage for m in milestones if self._is_advance_milestone(m)
            )
            result.total_balance_pct = sum(
                m.percentage for m in milestones if not self._is_advance_milestone(m)
            )

            # Determine primary payment method
            methods = [
                m.payment_method
                for m in milestones
                if m.payment_method != PaymentMethod.UNKNOWN
            ]
            if methods:
                result.primary_method = methods[0]  # First method mentioned

            # Determine term type
            result.term_type = self._determine_term_type(milestones, text_lower)

            # Calculate confidence
            total_pct = sum(m.percentage for m in milestones)
            if 99.0 <= total_pct <= 101.0:  # Allow 1% rounding error
                result.confidence = 0.9
            elif 95.0 <= total_pct <= 105.0:
                result.confidence = 0.7
                notes.append(f"Percentages sum to {total_pct}%")
            else:
                result.confidence = 0.5
                notes.append(f"Percentages sum to {total_pct}% (expected ~100%)")
        else:
            # No milestones extracted - try simple patterns
            simple_result = self._parse_simple_terms(text, text_lower)
            if simple_result:
                result.milestones = [simple_result]
                result.term_type = PaymentTermType.NET
                result.total_balance_pct = 100.0
                result.confidence = 0.8
            else:
                notes.append("Could not extract payment milestones")
                result.confidence = 0.3

        result.parsing_notes = notes
        return result

    def _extract_milestones(self, text: str) -> list[PaymentMilestone]:
        """Extract payment milestones from text."""
        milestones = []

        # Split by common delimiters
        # Handle newlines, bullet points, numbered items
        segments = re.split(r"\n|(?<=[.)])\s*(?=\d+%)|(?<=\d%)\s*(?=[A-Z])", text)

        for segment in segments:
            segment = segment.strip()
            if not segment:
                continue

            # Try to extract a milestone from this segment
            milestone = self._parse_segment(segment)
            if milestone:
                milestones.append(milestone)

        # If no milestones found, try to extract from whole text
        if not milestones:
            percentages = self.PERCENTAGE_PATTERN.findall(text)
            if percentages:
                # Split text by percentages
                parts = re.split(r"\d+(?:\.\d+)?%", text)
                for i, pct in enumerate(percentages):
                    # Get context around this percentage
                    before = parts[i] if i < len(parts) else ""
                    after = parts[i + 1] if i + 1 < len(parts) else ""
                    context = f"{before} {pct}% {after}"

                    milestone = PaymentMilestone(
                        percentage=float(pct),
                        payment_method=self._detect_payment_method(context),
                        trigger=self._detect_trigger(context),
                        days_from_trigger=self._extract_days(context),
                        description=context.strip()[:200],
                        requires_bank_guarantee="bank guarantee" in context.lower(),
                    )
                    milestones.append(milestone)

        return milestones

    def _parse_segment(self, segment: str) -> Optional[PaymentMilestone]:
        """Parse a single segment into a milestone."""
        segment_lower = segment.lower()

        # Extract percentage
        pct_match = self.PERCENTAGE_PATTERN.search(segment)
        if not pct_match:
            return None

        percentage = float(pct_match.group(1))

        # Extract amount if present
        amount = None
        currency = None
        amount_match = self.AMOUNT_PATTERN.search(segment)
        if amount_match:
            amount = float(amount_match.group(1).replace(",", ""))
            curr_match = self.CURRENCY_PATTERN.search(segment)
            if curr_match:
                currency = curr_match.group(1).upper()

        # Detect payment method
        payment_method = self._detect_payment_method(segment_lower)

        # Detect trigger event
        trigger = self._detect_trigger(segment_lower)

        # Extract days
        days = self._extract_days(segment_lower)

        # Check for bank guarantee requirement
        requires_bg = "bank guarantee" in segment_lower or "bg" in segment_lower.split()

        return PaymentMilestone(
            percentage=percentage,
            amount=amount,
            currency=currency,
            trigger=trigger,
            days_from_trigger=days,
            payment_method=payment_method,
            terms_days=days,
            description=segment.strip()[:200],
            requires_bank_guarantee=requires_bg,
        )

    def _detect_payment_method(self, text: str) -> PaymentMethod:
        """Detect payment method from text."""
        text_lower = text.lower()

        # Check for LC with timing
        if self._contains_any(text_lower, self.LC_KEYWORDS):
            if self._contains_any(text_lower, self.LC_SIGHT_KEYWORDS):
                return PaymentMethod.LC_SIGHT
            # Check for LC with days
            days_match = self.DAYS_PATTERN.search(text_lower)
            if days_match:
                days = int(days_match.group(1))
                if days <= 30:
                    return PaymentMethod.LC_30
                elif days <= 60:
                    return PaymentMethod.LC_60
                else:
                    return PaymentMethod.LC_90
            return PaymentMethod.LC_SIGHT  # Default LC type

        # Check for TT
        if self._contains_any(text_lower, self.TT_KEYWORDS):
            return PaymentMethod.TT

        # Check for credit line
        if self._contains_any(text_lower, self.CREDIT_LINE_KEYWORDS):
            return PaymentMethod.CREDIT_LINE

        return PaymentMethod.UNKNOWN

    def _detect_trigger(self, text: str) -> TriggerEvent:
        """Detect trigger event from text."""
        text_lower = text.lower()

        for trigger, keywords in self.TRIGGER_KEYWORDS.items():
            if self._contains_any(text_lower, keywords):
                return trigger

        return TriggerEvent.UNKNOWN

    def _extract_days(self, text: str) -> int:
        """Extract days from text, converting weeks/months as needed."""
        text_lower = text.lower()

        # Try days first
        days_match = self.DAYS_PATTERN.search(text_lower)
        if days_match:
            return int(days_match.group(1))

        # Try weeks
        weeks_match = self.WEEKS_PATTERN.search(text_lower)
        if weeks_match:
            return int(weeks_match.group(1)) * 7

        # Try months
        months_match = self.MONTHS_PATTERN.search(text_lower)
        if months_match:
            return int(months_match.group(1)) * 30

        return 0

    def _is_advance_milestone(self, milestone: PaymentMilestone) -> bool:
        """Check if milestone is an advance/downpayment."""
        desc_lower = milestone.description.lower()
        return (
            self._contains_any(desc_lower, self.ADVANCE_KEYWORDS)
            or milestone.trigger == TriggerEvent.ORDER_PLACEMENT
            or milestone.trigger == TriggerEvent.CONTRACT_SIGNING
        )

    def _determine_term_type(
        self, milestones: list[PaymentMilestone], text_lower: str
    ) -> PaymentTermType:
        """Determine the overall payment term type."""
        if len(milestones) == 1:
            if milestones[0].trigger == TriggerEvent.ORDER_PLACEMENT:
                return PaymentTermType.PREPAY
            if "net" in text_lower or milestones[0].trigger == TriggerEvent.INVOICE:
                return PaymentTermType.NET

        if len(milestones) >= 3:
            return PaymentTermType.MILESTONE

        if self._contains_any(text_lower, self.LC_KEYWORDS):
            return PaymentTermType.LC

        if len(milestones) == 2:
            if self._contains_any(text_lower, self.ADVANCE_KEYWORDS):
                return PaymentTermType.ADVANCE

        return PaymentTermType.MILESTONE

    def _parse_simple_terms(
        self, text: str, text_lower: str
    ) -> Optional[PaymentMilestone]:
        """Parse simple payment terms like 'Net 30 days'."""
        # Pattern: "Net X days" or "X days from invoice"
        if "net" in text_lower or "days" in text_lower:
            days = self._extract_days(text_lower)
            if days > 0:
                return PaymentMilestone(
                    percentage=100.0,
                    trigger=TriggerEvent.INVOICE,
                    days_from_trigger=days,
                    payment_method=self._detect_payment_method(text_lower),
                    terms_days=days,
                    description=text[:200],
                )

        # Pattern: "100% upon X" or "100% before X"
        if "100%" in text:
            return PaymentMilestone(
                percentage=100.0,
                trigger=self._detect_trigger(text_lower),
                days_from_trigger=self._extract_days(text_lower),
                payment_method=self._detect_payment_method(text_lower),
                description=text[:200],
            )

        return None

    def _contains_any(self, text: str, keywords: list[str]) -> bool:
        """Check if text contains any of the keywords."""
        return any(kw in text for kw in keywords)
