"""
Output Generator for Competitor Intelligence

Generates output files:
- competitors_items.jsonl: All extracted signals
- competitors_opportunities.jsonl: High-impact items (score >= 60)
- competitors_weekly_digest.md: Formatted weekly report
"""

import json
import logging
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Optional

from lead_to_cash.services.competitor_intel.signal_models import (
    CompetitorFinancials,
    CompetitorSignal,
)

logger = logging.getLogger(__name__)


class OutputGenerator:
    """
    Output file generator for competitor intelligence.

    Output Files:
    - data/competitor_intel/competitors_items.jsonl (all items)
    - data/competitor_intel/competitors_opportunities.jsonl (score >= 60)
    - data/competitor_intel/competitors_weekly_digest.md (formatted report)
    """

    DEFAULT_OUTPUT_DIR = "data/competitor_intel"
    HIGH_IMPACT_THRESHOLD = 60

    def __init__(self, output_dir: Optional[str] = None):
        """
        Initialize output generator.

        Args:
            output_dir: Output directory path. Defaults to data/competitor_intel/
        """
        self.output_dir = Path(output_dir or self.DEFAULT_OUTPUT_DIR)
        self._ensure_output_dir()

    def _ensure_output_dir(self):
        """Ensure output directory exists."""
        self.output_dir.mkdir(parents=True, exist_ok=True)

    def write_all_items(
        self, signals: list[CompetitorSignal], filename: str = "competitors_items.jsonl"
    ) -> str:
        """
        Write all signals to JSONL file.

        Args:
            signals: List of CompetitorSignal objects
            filename: Output filename

        Returns:
            Path to output file
        """
        output_path = self.output_dir / filename

        with open(output_path, "w") as f:
            for signal in signals:
                f.write(json.dumps(signal.to_dict(), default=str) + "\n")

        logger.info(f"Wrote {len(signals)} signals to {output_path}")
        return str(output_path)

    def write_opportunities(
        self,
        signals: list[CompetitorSignal],
        filename: str = "competitors_opportunities.jsonl",
    ) -> str:
        """
        Write high-impact signals (score >= 60) to JSONL file.

        Args:
            signals: List of CompetitorSignal objects
            filename: Output filename

        Returns:
            Path to output file
        """
        output_path = self.output_dir / filename
        high_impact = [s for s in signals if s.score >= self.HIGH_IMPACT_THRESHOLD]

        with open(output_path, "w") as f:
            for signal in high_impact:
                f.write(json.dumps(signal.to_dict(), default=str) + "\n")

        logger.info(f"Wrote {len(high_impact)} high-impact signals to {output_path}")
        return str(output_path)

    def generate_weekly_digest(
        self,
        signals: list[CompetitorSignal],
        financials: Optional[dict[str, CompetitorFinancials]] = None,
        filename: str = "competitors_weekly_digest.md",
    ) -> str:
        """
        Generate formatted weekly digest in Markdown.

        Args:
            signals: List of CompetitorSignal objects
            financials: Optional dict of competitor -> CompetitorFinancials
            filename: Output filename

        Returns:
            Path to output file
        """
        output_path = self.output_dir / filename

        # Group signals by type
        contract_wins = []
        product_launches = []
        fuel_transition = []
        offshore_marine = []
        events = []
        partnerships = []
        thought_leadership = []

        for signal in signals:
            if signal.signal_type == "CONTRACT_WIN":
                contract_wins.append(signal)
            elif signal.signal_type == "PRODUCT_LAUNCH":
                product_launches.append(signal)
            elif signal.signal_type == "TECHNOLOGY_POV":
                if signal.fuel_type or any(
                    k in signal.keywords_matched
                    for k in ["dual fuel", "methanol", "ammonia", "hydrogen", "lng"]
                ):
                    fuel_transition.append(signal)
                else:
                    thought_leadership.append(signal)
            elif signal.signal_type == "EVENT_MARKETING":
                events.append(signal)
            elif signal.signal_type == "PARTNERSHIP":
                partnerships.append(signal)
            else:
                # Check for offshore/marine relevance
                if signal.vessel_type or any(
                    k in signal.keywords_matched
                    for k in ["offshore", "marine", "vessel", "ship", "osv", "fpso"]
                ):
                    offshore_marine.append(signal)
                else:
                    thought_leadership.append(signal)

        # Generate markdown
        now = datetime.now(timezone.utc)
        week_start = now - timedelta(days=7)

        md_content = f"""# Competitor Intelligence Weekly Digest

**Generated:** {now.strftime("%Y-%m-%d %H:%M UTC")}
**Period:** {week_start.strftime("%Y-%m-%d")} to {now.strftime("%Y-%m-%d")}

---

## Executive Summary

| Competitor | Signals | High-Impact | Top Signal Type |
|------------|---------|-------------|-----------------|
"""

        # Summary by competitor
        competitors = ["caterpillar", "cummins", "man_energy"]
        competitor_names = {
            "caterpillar": "Caterpillar",
            "cummins": "Cummins",
            "man_energy": "MAN Energy Solutions",
        }

        for comp in competitors:
            comp_signals = [s for s in signals if s.competitor == comp]
            high_impact = [s for s in comp_signals if s.score >= 60]
            top_type = self._get_top_signal_type(comp_signals)
            md_content += f"| {competitor_names.get(comp, comp)} | {len(comp_signals)} | {len(high_impact)} | {top_type} |\n"

        md_content += "\n---\n\n"

        # Contract Wins Section
        md_content += self._format_section(
            "Contract Wins",
            contract_wins,
            "Key contract wins and customer selections involving marine engines.",
        )

        # Product Launches Section
        md_content += self._format_section(
            "Product Launches",
            product_launches,
            "New engine platforms, models, and product announcements.",
        )

        # Fuel Transition Strategy Section
        md_content += self._format_section(
            "Fuel Transition Strategy",
            fuel_transition,
            "Dual-fuel, methanol, ammonia, hydrogen, and decarbonization initiatives.",
        )

        # Offshore & Marine Projects Section
        md_content += self._format_section(
            "Offshore & Marine Project Involvement",
            offshore_marine,
            "OSV, FPSO, ferry, and other marine project activity.",
        )

        # Financial Signals Section
        if financials:
            md_content += self._format_financials_section(financials)

        # Events & Marketing Section
        md_content += self._format_section(
            "Events & Marketing",
            events,
            "Trade show participation and marketing activity.",
        )

        # Partnerships Section
        md_content += self._format_section(
            "Partnerships & Collaborations",
            partnerships,
            "Strategic partnerships and joint ventures.",
        )

        # Strategic Messaging Section
        md_content += self._format_section(
            "Strategic Messaging & Thought Leadership",
            thought_leadership,
            "Positioning, strategy direction, and thought leadership content.",
        )

        # Appendix: Top Opportunities
        md_content += self._format_top_opportunities(signals)

        # Write file
        with open(output_path, "w") as f:
            f.write(md_content)

        logger.info(f"Generated weekly digest at {output_path}")
        return str(output_path)

    def _format_section(
        self, title: str, signals: list[CompetitorSignal], description: str
    ) -> str:
        """Format a section of the digest."""
        if not signals:
            return (
                f"## {title}\n\n*No significant activity in this category.*\n\n---\n\n"
            )

        # Sort by score (highest first)
        sorted_signals = sorted(signals, key=lambda s: s.score, reverse=True)

        md = f"## {title}\n\n{description}\n\n"

        for signal in sorted_signals[:10]:  # Top 10 per section
            competitor_name = {
                "caterpillar": "CAT",
                "cummins": "CMI",
                "man_energy": "MAN",
            }.get(signal.competitor, signal.competitor.upper())

            score_badge = (
                f"[{signal.score}]" if signal.score >= 60 else f"({signal.score})"
            )

            md += f"### {score_badge} {competitor_name}: {signal.headline}\n\n"
            md += f"{signal.description}\n\n"

            # Metadata
            metadata_parts = []
            if signal.customer_mentioned:
                metadata_parts.append(f"**Customer:** {signal.customer_mentioned}")
            if signal.vessel_type:
                metadata_parts.append(f"**Vessel:** {signal.vessel_type}")
            if signal.fuel_type:
                metadata_parts.append(f"**Fuel:** {signal.fuel_type}")
            if signal.region or signal.country:
                location = signal.country or signal.region
                metadata_parts.append(f"**Location:** {location}")
            if signal.source_url:
                metadata_parts.append(f"[Source]({signal.source_url})")

            if metadata_parts:
                md += " | ".join(metadata_parts) + "\n\n"

        md += "---\n\n"
        return md

    def _format_financials_section(
        self, financials: dict[str, CompetitorFinancials]
    ) -> str:
        """Format financial signals section."""
        md = "## Financial Signals\n\nQuarterly financial data from EODHD.\n\n"

        md += "| Competitor | Period | Revenue | YoY Growth | Operating Margin |\n"
        md += "|------------|--------|---------|------------|------------------|\n"

        for comp, fin in financials.items():
            comp_name = {
                "caterpillar": "Caterpillar",
                "cummins": "Cummins",
                "man_energy": "MAN Energy",
            }.get(comp, comp)

            revenue = f"${fin.revenue_usd/1e9:.1f}B" if fin.revenue_usd else "N/A"
            yoy = (
                f"{fin.revenue_growth_yoy_pct:+.1f}%"
                if fin.revenue_growth_yoy_pct
                else "N/A"
            )
            margin = (
                f"{fin.operating_margin_pct:.1f}%"
                if fin.operating_margin_pct
                else "N/A"
            )

            md += f"| {comp_name} | {fin.fiscal_period} | {revenue} | {yoy} | {margin} |\n"

        md += "\n---\n\n"
        return md

    def _format_top_opportunities(self, signals: list[CompetitorSignal]) -> str:
        """Format appendix with top opportunities."""
        high_impact = [s for s in signals if s.score >= 60]
        sorted_signals = sorted(high_impact, key=lambda s: s.score, reverse=True)[:20]

        if not sorted_signals:
            return "## Appendix: Top Opportunities\n\n*No high-impact opportunities this week.*\n"

        md = "## Appendix: Top Opportunities\n\nHighest-scoring signals requiring attention.\n\n"
        md += "| Score | Competitor | Type | Headline |\n"
        md += "|-------|------------|------|----------|\n"

        for signal in sorted_signals:
            comp = signal.competitor[:3].upper()
            signal_type = signal.signal_type.replace("_", " ").title()[:15]
            headline = (
                signal.headline[:50] + "..."
                if len(signal.headline) > 50
                else signal.headline
            )
            md += f"| {signal.score} | {comp} | {signal_type} | {headline} |\n"

        return md

    def _get_top_signal_type(self, signals: list[CompetitorSignal]) -> str:
        """Get the most common signal type for a list of signals."""
        if not signals:
            return "N/A"

        type_counts: dict[str, int] = {}
        for signal in signals:
            type_counts[signal.signal_type] = type_counts.get(signal.signal_type, 0) + 1

        top_type = max(type_counts, key=lambda k: type_counts.get(k, 0))
        return top_type.replace("_", " ").title()

    def generate_daily_summary(
        self, signals: list[CompetitorSignal], filename: Optional[str] = None
    ) -> str:
        """
        Generate a brief daily summary.

        Args:
            signals: List of signals from today
            filename: Optional filename (defaults to daily_summary_YYYYMMDD.md)

        Returns:
            Path to output file
        """
        now = datetime.now(timezone.utc)
        if filename is None:
            filename = f"daily_summary_{now.strftime('%Y%m%d')}.md"

        output_path = self.output_dir / filename

        # Filter to high-impact only for daily summary
        high_impact = [s for s in signals if s.score >= 50]  # Lower threshold for daily

        md = f"""# Competitor Intelligence Daily Summary

**Date:** {now.strftime("%Y-%m-%d")}
**Signals Collected:** {len(signals)}
**High-Impact:** {len(high_impact)}

---

## Today's Highlights

"""

        if not high_impact:
            md += "*No significant competitor activity detected today.*\n"
        else:
            for signal in sorted(high_impact, key=lambda s: s.score, reverse=True)[:5]:
                comp = {
                    "caterpillar": "Caterpillar",
                    "cummins": "Cummins",
                    "man_energy": "MAN Energy",
                }.get(signal.competitor, signal.competitor)

                md += f"- **[{signal.score}] {comp}:** {signal.headline}\n"

        with open(output_path, "w") as f:
            f.write(md)

        logger.info(f"Generated daily summary at {output_path}")
        return str(output_path)


# Singleton instance
_generator: Optional[OutputGenerator] = None


def get_output_generator() -> OutputGenerator:
    """Get or create the output generator singleton."""
    global _generator
    if _generator is None:
        _generator = OutputGenerator()
    return _generator
