"""
EU MRV THETIS Data Ingestion for Marine Engine Knowledge Base

Ingests vessel data from the EU MRV (Monitoring, Reporting, Verification) system
to derive vessel type → engine requirements mappings.

Data Source: https://mrv.emsa.europa.eu/#public/emission-report
- Publicly available annual datasets (2018-2023+)
- ~12,000 vessels >5,000 GT calling at EU ports
- Includes: ship type, technical efficiency (EEDI/EEXI/EIV), fuel consumption, emissions

Usage:
    # Download data manually from THETIS portal, then:
    from lead_to_cash.services.knowledge_base.eu_mrv_ingestion import (
        EUMRVIngestion,
        analyze_vessel_requirements,
    )

    ingestion = EUMRVIngestion()
    vessels = ingestion.load_from_excel("path/to/eu_mrv_2023.xlsx")
    requirements = analyze_vessel_requirements(vessels)

References:
- EMSA THETIS-MRV: https://mrv.emsa.europa.eu/
- EU Open Data Portal: https://data.europa.eu/data/datasets/co2-emissions-data
- Regulation (EU) 2015/757
"""

import statistics
from collections import defaultdict
from dataclasses import dataclass, field
from typing import Any, Optional

from lead_to_cash.utils.logging import get_logger

logger = get_logger(__name__)


# =============================================================================
# EU MRV SHIP TYPE MAPPING
# =============================================================================

# Official EU MRV ship type codes mapped to our KB categories
EU_MRV_SHIP_TYPES = {
    # Cargo vessels
    "Bulk carrier": "bulk_carrier",
    "General cargo ship": "general_cargo",
    "Container ship": "container_ship",
    "Container/ro-ro cargo ship": "container_roro",
    "Refrigerated cargo carrier": "reefer",
    "Combination carrier": "combination_carrier",
    # Tankers
    "Oil tanker": "oil_tanker",
    "Chemical tanker": "chemical_tanker",
    "LNG carrier": "lng_carrier",
    "Gas carrier": "gas_carrier",
    # Passenger vessels
    "Passenger ship": "passenger_ship",
    "Ro-pax ship": "ro_pax",
    "Cruise passenger ship": "cruise_ship",
    # RoRo vessels
    "Ro-ro ship": "roro_cargo",
    "Vehicle carrier": "vehicle_carrier",
    # Offshore
    "Offshore ship": "offshore_vessel",
    # Other
    "Other ship types": "other",
}

# Reverse mapping for lookups
KB_TO_EU_MRV_TYPES = {v: k for k, v in EU_MRV_SHIP_TYPES.items()}


@dataclass
class EUMRVVessel:
    """Vessel record from EU MRV THETIS database."""

    # Identification
    imo_number: str
    ship_name: str
    ship_type: str  # EU MRV ship type
    flag_state: str

    # Physical characteristics
    gross_tonnage: float
    deadweight_tonnage: Optional[float] = None

    # Technical efficiency (one of these will be populated)
    eedi: Optional[float] = None  # Energy Efficiency Design Index (new ships)
    eexi: Optional[float] = None  # Energy Efficiency Existing Ship Index
    eiv: Optional[float] = None  # Estimated Index Value (fallback)

    # Operational data (annual)
    total_fuel_consumption_tonnes: Optional[float] = None
    total_co2_emissions_tonnes: Optional[float] = None
    total_distance_nm: Optional[float] = None
    total_time_at_sea_hours: Optional[float] = None

    # Cargo data
    total_cargo_carried_tonnes: Optional[float] = None
    total_passengers: Optional[int] = None

    # Derived metrics
    average_fuel_consumption_per_nm: Optional[float] = None
    co2_per_transport_work: Optional[float] = None  # g CO2 / tonne-nm

    # Metadata
    reporting_year: int = 2023
    data_source: str = "EU_MRV_THETIS"

    @property
    def technical_efficiency(self) -> Optional[float]:
        """Return the available technical efficiency index."""
        return self.eedi or self.eexi or self.eiv

    @property
    def kb_ship_type(self) -> str:
        """Map EU MRV ship type to KB category."""
        return EU_MRV_SHIP_TYPES.get(self.ship_type, "other")

    @property
    def estimated_installed_power_kw(self) -> Optional[float]:
        """
        Estimate installed power from technical efficiency and DWT.

        IMPORTANT: This is a ROUGH APPROXIMATION with significant limitations:

        1. The IMO EEDI formula is complex and ship-type specific:
           EEDI = (P_ME × C_F × SFC_ME + P_AE × C_F × SFC_AE) / (DWT × V_ref)

        2. This simplified estimation assumes:
           - No auxiliary power contribution
           - Constant SFC across all load conditions
           - No correction factors (weather, ice class, etc.)

        3. Accuracy is typically ±30-50% and should NOT be used for:
           - Engine sizing decisions
           - Commercial specifications
           - Contract documentation

        4. For reliable power data, use:
           - Classification society records (DNV, Lloyd's)
           - Ship registry databases (IHS Markit, Clarksons)
           - Manufacturer-confirmed vessel specifications

        Formula: P_ME ≈ (EEDI × DWT × V_ref) / (C_F × SFC_ME)
        """
        if not self.technical_efficiency or not self.deadweight_tonnage:
            return None

        # Reference speeds by ship type (knots) - IMO MEPC guidelines
        ref_speeds = {
            "bulk_carrier": 14.5,
            "oil_tanker": 14.5,
            "chemical_tanker": 14.5,
            "lng_carrier": 19.5,
            "gas_carrier": 19.5,
            "container_ship": 22.0,
            "general_cargo": 15.0,
            "reefer": 20.0,
            "roro_cargo": 17.0,
            "ro_pax": 18.0,
            "cruise_ship": 21.0,
            "passenger_ship": 18.0,
            "vehicle_carrier": 18.0,
            "offshore_vessel": 13.0,
        }

        v_ref = ref_speeds.get(self.kb_ship_type, 15.0)
        c_f = 3.206  # CO2 conversion factor for diesel (g CO2 / g fuel)
        sfc = 185.0  # Average SFOC g/kWh for medium-speed engines

        # P_ME ≈ (EEDI × DWT × V_ref) / (C_F × SFC)
        # Units: (g CO2/t-nm × t × nm/h) / (g CO2/g fuel × g fuel/kWh) = kW
        # Note: This gives very rough estimates due to formula simplifications
        power_kw = (self.technical_efficiency * self.deadweight_tonnage * v_ref) / (
            c_f * sfc
        )

        return round(power_kw, 0)


@dataclass
class VesselTypeRequirements:
    """Derived requirements for a vessel type from EU MRV analysis."""

    vessel_type: str
    vessel_type_eu_mrv: str

    # Power requirements (derived from analysis)
    power_range_min_kw: float
    power_range_max_kw: float
    power_median_kw: float
    power_percentile_25_kw: float
    power_percentile_75_kw: float

    # Size characteristics
    gt_range: tuple[float, float]
    dwt_range: tuple[float, float]

    # Efficiency characteristics
    avg_technical_efficiency: Optional[float] = None
    avg_co2_per_transport_work: Optional[float] = None

    # Fuel patterns observed
    primary_fuel_types: list[str] = field(default_factory=list)

    # Data quality
    sample_size: int = 0
    confidence: float = 0.0
    source: str = "EU_MRV_THETIS"
    reporting_years: list[int] = field(default_factory=list)


# =============================================================================
# EU MRV DATA INGESTION CLASS
# =============================================================================


class EUMRVIngestion:
    """
    Ingest and process EU MRV THETIS vessel data.

    The EU MRV data can be downloaded from:
    - THETIS Portal: https://mrv.emsa.europa.eu/#public/emission-report
    - EU Open Data: https://data.europa.eu/data/datasets/co2-emissions-data

    Data is available in Excel format with annual reporting from 2018 onwards.
    """

    # Expected column names in EU MRV Excel export
    # These may vary slightly between years - mapping handles variations
    COLUMN_MAPPINGS = {
        # Identification columns
        "IMO Number": "imo_number",
        "IMO number": "imo_number",
        "Ship IMO number": "imo_number",
        "Name": "ship_name",
        "Ship name": "ship_name",
        "Ship Name": "ship_name",
        "Ship type": "ship_type",
        "Ship Type": "ship_type",
        "Flag State": "flag_state",
        "Flag": "flag_state",
        # Physical characteristics
        "Gross tonnage": "gross_tonnage",
        "GT": "gross_tonnage",
        "Deadweight": "deadweight_tonnage",
        "DWT": "deadweight_tonnage",
        "Deadweight tonnage": "deadweight_tonnage",
        # Technical efficiency
        "EEDI": "eedi",
        "EEDI (Energy Efficiency Design Index)": "eedi",
        "Attained EEDI": "eedi",
        "EEXI": "eexi",
        "EEXI (Energy Efficiency Existing Ship Index)": "eexi",
        "EIV": "eiv",
        "EIV (Estimated Index Value)": "eiv",
        "Technical efficiency": "technical_efficiency",
        # Fuel and emissions
        "Total fuel consumption [m tonnes]": "total_fuel_consumption_tonnes",
        "Total fuel consumption": "total_fuel_consumption_tonnes",
        "Annual Total fuel consumption [m tonnes]": "total_fuel_consumption_tonnes",
        "Total CO₂ emissions [m tonnes]": "total_co2_emissions_tonnes",
        "Total CO2 emissions [m tonnes]": "total_co2_emissions_tonnes",
        "Annual Total CO₂ emissions [m tonnes]": "total_co2_emissions_tonnes",
        # Operational
        "Total distance travelled [n miles]": "total_distance_nm",
        "Distance travelled (nm)": "total_distance_nm",
        "Total time spent at sea [hours]": "total_time_at_sea_hours",
        "Time at sea (hours)": "total_time_at_sea_hours",
        # Cargo
        "Total cargo carried [m tonnes]": "total_cargo_carried_tonnes",
        "Cargo carried (tonnes)": "total_cargo_carried_tonnes",
        "Number of passengers": "total_passengers",
        # Derived efficiency metrics
        "Average CO₂ emissions per transport work [g / (m tonnes * n miles)]": "co2_per_transport_work",
        "Annual average CO₂ emissions per transport work": "co2_per_transport_work",
        "Average Fuel consumption per distance [kg / n mile]": "average_fuel_consumption_per_nm",
    }

    def __init__(self):
        self.vessels: list[EUMRVVessel] = []
        self._raw_data = None

    def load_from_excel(self, filepath: str, year: int = 2023) -> list[EUMRVVessel]:
        """
        Load EU MRV data from Excel file downloaded from THETIS portal.

        Args:
            filepath: Path to Excel file
            year: Reporting year for the data

        Returns:
            List of parsed EUMRVVessel objects
        """
        try:
            import pandas as pd
        except ImportError:
            raise ImportError(
                "pandas and openpyxl required: pip install pandas openpyxl"
            )

        logger.info(f"Loading EU MRV data from {filepath}")

        # Read Excel file
        df = pd.read_excel(filepath)
        self._raw_data = df

        # Normalize column names
        column_map = {}
        for col in df.columns:
            col_clean = col.strip()
            if col_clean in self.COLUMN_MAPPINGS:
                column_map[col] = self.COLUMN_MAPPINGS[col_clean]
            else:
                # Try partial matching
                for key, value in self.COLUMN_MAPPINGS.items():
                    if key.lower() in col_clean.lower():
                        column_map[col] = value
                        break

        df = df.rename(columns=column_map)

        # Parse vessels
        vessels = []
        for idx, row in df.iterrows():
            try:
                vessel = self._parse_vessel_row(row, year)
                if vessel:
                    vessels.append(vessel)
            except Exception as e:
                logger.debug(f"Failed to parse row {idx}: {e}")

        self.vessels = vessels
        logger.info(f"Loaded {len(vessels)} vessels from EU MRV data")

        return vessels

    def load_from_csv(self, filepath: str, year: int = 2023) -> list[EUMRVVessel]:
        """Load EU MRV data from CSV file."""
        try:
            import pandas as pd
        except ImportError:
            raise ImportError("pandas required: pip install pandas")

        logger.info(f"Loading EU MRV data from CSV {filepath}")

        df = pd.read_csv(filepath)
        self._raw_data = df

        # Same parsing logic as Excel
        column_map = {}
        for col in df.columns:
            col_clean = col.strip()
            if col_clean in self.COLUMN_MAPPINGS:
                column_map[col] = self.COLUMN_MAPPINGS[col_clean]

        df = df.rename(columns=column_map)

        vessels = []
        for idx, row in df.iterrows():
            try:
                vessel = self._parse_vessel_row(row, year)
                if vessel:
                    vessels.append(vessel)
            except Exception as e:
                logger.debug(f"Failed to parse row {idx}: {e}")

        self.vessels = vessels
        logger.info(f"Loaded {len(vessels)} vessels from CSV")

        return vessels

    def _parse_vessel_row(self, row, year: int) -> Optional[EUMRVVessel]:
        """Parse a single row into an EUMRVVessel object."""
        # Required fields
        imo = str(row.get("imo_number", "")).strip()
        if not imo or imo == "nan":
            return None

        ship_name = str(row.get("ship_name", "")).strip()
        ship_type = str(row.get("ship_type", "Other ship types")).strip()
        flag_state = str(row.get("flag_state", "")).strip()

        # Parse numeric fields safely
        def safe_float(value) -> Optional[float]:
            if value is None or str(value).strip() in ("", "nan", "None", "-"):
                return None
            try:
                return float(value)
            except (ValueError, TypeError):
                return None

        def safe_int(value) -> Optional[int]:
            if value is None or str(value).strip() in ("", "nan", "None", "-"):
                return None
            try:
                return int(float(value))
            except (ValueError, TypeError):
                return None

        gt = safe_float(row.get("gross_tonnage"))
        if not gt or gt < 100:
            return None  # Invalid vessel

        return EUMRVVessel(
            imo_number=imo,
            ship_name=ship_name,
            ship_type=ship_type,
            flag_state=flag_state,
            gross_tonnage=gt,
            deadweight_tonnage=safe_float(row.get("deadweight_tonnage")),
            eedi=safe_float(row.get("eedi")),
            eexi=safe_float(row.get("eexi")),
            eiv=safe_float(row.get("eiv"))
            or safe_float(row.get("technical_efficiency")),
            total_fuel_consumption_tonnes=safe_float(
                row.get("total_fuel_consumption_tonnes")
            ),
            total_co2_emissions_tonnes=safe_float(
                row.get("total_co2_emissions_tonnes")
            ),
            total_distance_nm=safe_float(row.get("total_distance_nm")),
            total_time_at_sea_hours=safe_float(row.get("total_time_at_sea_hours")),
            total_cargo_carried_tonnes=safe_float(
                row.get("total_cargo_carried_tonnes")
            ),
            total_passengers=safe_int(row.get("total_passengers")),
            average_fuel_consumption_per_nm=safe_float(
                row.get("average_fuel_consumption_per_nm")
            ),
            co2_per_transport_work=safe_float(row.get("co2_per_transport_work")),
            reporting_year=year,
        )

    def get_vessels_by_type(self, kb_ship_type: str) -> list[EUMRVVessel]:
        """Get all vessels of a specific KB ship type."""
        return [v for v in self.vessels if v.kb_ship_type == kb_ship_type]

    def get_ship_type_summary(self) -> dict:
        """Get summary statistics by ship type."""
        summary: dict[str, dict[str, Any]] = defaultdict(
            lambda: {
                "count": 0,
                "gt_values": [],
                "dwt_values": [],
                "efficiency_values": [],
                "estimated_power_values": [],
            }
        )

        for vessel in self.vessels:
            kb_type = vessel.kb_ship_type
            summary[kb_type]["count"] += 1
            summary[kb_type]["gt_values"].append(vessel.gross_tonnage)

            if vessel.deadweight_tonnage:
                summary[kb_type]["dwt_values"].append(vessel.deadweight_tonnage)

            if vessel.technical_efficiency:
                summary[kb_type]["efficiency_values"].append(
                    vessel.technical_efficiency
                )

            est_power = vessel.estimated_installed_power_kw
            if est_power and 500 < est_power < 100000:  # Reasonable range
                summary[kb_type]["estimated_power_values"].append(est_power)

        return dict(summary)


# =============================================================================
# ANALYSIS FUNCTIONS
# =============================================================================


def analyze_vessel_requirements(
    vessels: list[EUMRVVessel],
    min_sample_size: int = 10,
) -> dict[str, VesselTypeRequirements]:
    """
    Analyze EU MRV vessel data to derive vessel type requirements.

    Args:
        vessels: List of EUMRVVessel objects
        min_sample_size: Minimum vessels required for valid statistics

    Returns:
        Dictionary of vessel_type -> VesselTypeRequirements
    """
    # Group vessels by KB ship type
    by_type: dict[str, list[EUMRVVessel]] = defaultdict(list)
    for vessel in vessels:
        by_type[vessel.kb_ship_type].append(vessel)

    requirements = {}

    for kb_type, type_vessels in by_type.items():
        if len(type_vessels) < min_sample_size:
            logger.debug(
                f"Skipping {kb_type}: only {len(type_vessels)} vessels (min: {min_sample_size})"
            )
            continue

        # Collect metrics
        gt_values = [v.gross_tonnage for v in type_vessels if v.gross_tonnage]
        dwt_values = [
            v.deadweight_tonnage for v in type_vessels if v.deadweight_tonnage
        ]
        efficiency_values = [
            v.technical_efficiency for v in type_vessels if v.technical_efficiency
        ]
        co2_work_values = [
            v.co2_per_transport_work for v in type_vessels if v.co2_per_transport_work
        ]

        # Estimate power values
        power_values = []
        for v in type_vessels:
            est_power = v.estimated_installed_power_kw
            if est_power and 500 < est_power < 100000:  # Reasonable range filter
                power_values.append(est_power)

        if len(power_values) < min_sample_size:
            # Fall back to empirical power estimation from GT
            power_values = estimate_power_from_gt(kb_type, gt_values)

        if not power_values:
            logger.warning(f"No power data available for {kb_type}")
            continue

        # Calculate statistics
        power_values_sorted = sorted(power_values)
        n = len(power_values_sorted)

        req = VesselTypeRequirements(
            vessel_type=kb_type,
            vessel_type_eu_mrv=KB_TO_EU_MRV_TYPES.get(kb_type, "Other ship types"),
            power_range_min_kw=power_values_sorted[int(n * 0.05)],  # 5th percentile
            power_range_max_kw=power_values_sorted[int(n * 0.95)],  # 95th percentile
            power_median_kw=statistics.median(power_values),
            power_percentile_25_kw=power_values_sorted[int(n * 0.25)],
            power_percentile_75_kw=power_values_sorted[int(n * 0.75)],
            gt_range=(min(gt_values), max(gt_values)) if gt_values else (0, 0),
            dwt_range=(min(dwt_values), max(dwt_values)) if dwt_values else (0, 0),
            avg_technical_efficiency=(
                statistics.mean(efficiency_values) if efficiency_values else None
            ),
            avg_co2_per_transport_work=(
                statistics.mean(co2_work_values) if co2_work_values else None
            ),
            sample_size=len(type_vessels),
            confidence=min(
                1.0, len(power_values) / 100
            ),  # Higher confidence with more data
            reporting_years=list(set(v.reporting_year for v in type_vessels)),
        )

        requirements[kb_type] = req
        logger.info(
            f"{kb_type}: {req.sample_size} vessels, "
            f"power {req.power_range_min_kw/1000:.1f}-{req.power_range_max_kw/1000:.1f} MW"
        )

    return requirements


def estimate_power_from_gt(ship_type: str, gt_values: list[float]) -> list[float]:
    """
    Estimate installed power from gross tonnage using empirical relationships.

    Based on industry data and classification society guidelines:
    - Power roughly scales with GT^0.6 to GT^0.7 depending on vessel type

    Args:
        ship_type: KB ship type
        gt_values: List of gross tonnage values

    Returns:
        List of estimated power values in kW
    """
    # Empirical coefficients: power_kw = a * GT^b
    # Based on industry analysis and DNV/Lloyd's data
    POWER_COEFFICIENTS = {
        "bulk_carrier": (4.5, 0.65),
        "oil_tanker": (4.0, 0.65),
        "chemical_tanker": (5.0, 0.63),
        "lng_carrier": (8.0, 0.62),
        "gas_carrier": (7.0, 0.63),
        "container_ship": (12.0, 0.62),
        "general_cargo": (5.5, 0.60),
        "reefer": (8.0, 0.60),
        "roro_cargo": (6.0, 0.63),
        "ro_pax": (8.0, 0.62),
        "cruise_ship": (10.0, 0.65),
        "passenger_ship": (7.0, 0.63),
        "vehicle_carrier": (5.0, 0.62),
        "offshore_vessel": (8.0, 0.55),
        "other": (5.0, 0.60),
    }

    a, b = POWER_COEFFICIENTS.get(ship_type, (5.0, 0.60))

    return [a * (gt**b) for gt in gt_values if gt > 0]


def generate_application_requirements_update(
    requirements: dict[str, VesselTypeRequirements],
) -> str:
    """
    Generate Python code to update APPLICATION_REQUIREMENTS in product_data.py.

    Args:
        requirements: Analyzed vessel type requirements

    Returns:
        Python code string for updating APPLICATION_REQUIREMENTS
    """
    lines = [
        "# =============================================================================",
        "# VESSEL TYPE REQUIREMENTS (Derived from EU MRV THETIS Data)",
        "# =============================================================================",
        "",
        "EU_MRV_VESSEL_REQUIREMENTS = {",
    ]

    for kb_type, req in sorted(requirements.items()):
        lines.append(f'    "{kb_type}": {{')
        lines.append(f'        "eu_mrv_type": "{req.vessel_type_eu_mrv}",')
        lines.append(
            f'        "power_range_kw": ({req.power_range_min_kw:.0f}, {req.power_range_max_kw:.0f}),'
        )
        lines.append(f'        "power_median_kw": {req.power_median_kw:.0f},')
        lines.append(
            f'        "power_iqr_kw": ({req.power_percentile_25_kw:.0f}, {req.power_percentile_75_kw:.0f}),'
        )
        lines.append(
            f'        "gt_range": ({req.gt_range[0]:.0f}, {req.gt_range[1]:.0f}),'
        )
        lines.append(
            f'        "dwt_range": ({req.dwt_range[0]:.0f}, {req.dwt_range[1]:.0f}),'
        )

        if req.avg_technical_efficiency:
            lines.append(
                f'        "avg_eedi_eexi": {req.avg_technical_efficiency:.2f},'
            )
        if req.avg_co2_per_transport_work:
            lines.append(
                f'        "avg_co2_per_transport_work": {req.avg_co2_per_transport_work:.2f},'
            )

        lines.append(f'        "sample_size": {req.sample_size},')
        lines.append(f'        "confidence": {req.confidence:.2f},')
        lines.append(f'        "source": "{req.source}",')
        lines.append(f'        "reporting_years": {req.reporting_years},')
        lines.append("    },")

    lines.append("}")
    lines.append("")

    return "\n".join(lines)


# =============================================================================
# SAMPLE DATA FOR TESTING (When EU MRV data not available)
# =============================================================================

# Industry-standard vessel power ranges by type
# Based on DNV, Lloyd's Register, and industry publications
INDUSTRY_POWER_RANGES: dict[str, dict[str, Any]] = {
    "cruise_ship": {
        "power_range_kw": (20000, 80000),
        "typical_rpm": (400, 600),
        "notes": "Diesel-electric common, high hotel load",
    },
    "ro_pax": {
        "power_range_kw": (8000, 35000),
        "typical_rpm": (500, 750),
        "notes": "Fast ferries may have higher power",
    },
    "passenger_ship": {
        "power_range_kw": (4000, 20000),
        "typical_rpm": (600, 900),
        "notes": "Varies widely by size and route",
    },
    "container_ship": {
        "power_range_kw": (8000, 80000),
        "typical_rpm": (80, 120),  # Slow-speed for large, 400-600 for feeder
        "notes": "2-stroke slow-speed for large, 4-stroke medium for feeder",
    },
    "bulk_carrier": {
        "power_range_kw": (6000, 25000),
        "typical_rpm": (80, 120),
        "notes": "Mostly 2-stroke slow-speed propulsion",
    },
    "oil_tanker": {
        "power_range_kw": (8000, 35000),
        "typical_rpm": (80, 120),
        "notes": "Slow-speed for economy, some VLCC go higher",
    },
    "chemical_tanker": {
        "power_range_kw": (4000, 15000),
        "typical_rpm": (500, 750),
        "notes": "Medium-speed 4-stroke common",
    },
    "lng_carrier": {
        "power_range_kw": (25000, 45000),
        "typical_rpm": (80, 120),
        "notes": "Dual-fuel engines common, boil-off gas utilization",
    },
    "gas_carrier": {
        "power_range_kw": (8000, 25000),
        "typical_rpm": (500, 750),
        "notes": "LPG carriers, smaller than LNG",
    },
    "general_cargo": {
        "power_range_kw": (3000, 12000),
        "typical_rpm": (500, 750),
        "notes": "Medium-speed engines, versatile",
    },
    "reefer": {
        "power_range_kw": (8000, 18000),
        "typical_rpm": (500, 750),
        "notes": "High power for refrigeration + speed",
    },
    "roro_cargo": {
        "power_range_kw": (8000, 25000),
        "typical_rpm": (500, 750),
        "notes": "Often diesel-electric for maneuverability",
    },
    "vehicle_carrier": {
        "power_range_kw": (10000, 20000),
        "typical_rpm": (500, 750),
        "notes": "PCC/PCTC vessels",
    },
    "offshore_vessel": {
        "power_range_kw": (4000, 15000),
        "typical_rpm": (720, 1000),
        "notes": "OSV, PSV, AHTS - often diesel-electric with DP",
    },
    "tug": {
        "power_range_kw": (1500, 6000),
        "typical_rpm": (720, 1000),
        "notes": "High bollard pull focus, compact",
    },
    "dredger": {
        "power_range_kw": (5000, 25000),
        "typical_rpm": (600, 900),
        "notes": "Varies by dredger type (TSHD, CSD)",
    },
}


def get_industry_baseline_requirements() -> dict[str, VesselTypeRequirements]:
    """
    Get baseline vessel requirements from industry data.

    Use this when EU MRV data is not available.
    """
    requirements = {}

    for kb_type, data in INDUSTRY_POWER_RANGES.items():
        power_range: tuple[float, float] = data["power_range_kw"]
        min_kw, max_kw = power_range
        median_kw = (min_kw + max_kw) / 2

        requirements[kb_type] = VesselTypeRequirements(
            vessel_type=kb_type,
            vessel_type_eu_mrv=KB_TO_EU_MRV_TYPES.get(kb_type, "Other ship types"),
            power_range_min_kw=float(min_kw),
            power_range_max_kw=float(max_kw),
            power_median_kw=median_kw,
            power_percentile_25_kw=min_kw + (max_kw - min_kw) * 0.25,
            power_percentile_75_kw=min_kw + (max_kw - min_kw) * 0.75,
            gt_range=(0, 0),  # Not available without EU MRV
            dwt_range=(0, 0),
            sample_size=0,
            confidence=0.7,  # Industry baseline has good confidence
            source="INDUSTRY_BASELINE",
            reporting_years=[],
        )

    return requirements


# =============================================================================
# CLI ENTRY POINT
# =============================================================================


def main():
    """CLI entry point for EU MRV ingestion."""
    import argparse

    parser = argparse.ArgumentParser(
        description="Ingest EU MRV THETIS vessel data for KB"
    )
    parser.add_argument(
        "input_file",
        nargs="?",
        help="Path to EU MRV Excel/CSV file (optional, uses industry baseline if not provided)",
    )
    parser.add_argument(
        "--year",
        type=int,
        default=2023,
        help="Reporting year (default: 2023)",
    )
    parser.add_argument(
        "--output",
        "-o",
        help="Output Python file for requirements",
    )
    parser.add_argument(
        "--baseline",
        action="store_true",
        help="Generate from industry baseline (no EU MRV data needed)",
    )

    args = parser.parse_args()

    if args.baseline or not args.input_file:
        print("Using industry baseline data (EU MRV data not provided)")
        requirements = get_industry_baseline_requirements()
    else:
        ingestion = EUMRVIngestion()

        if args.input_file.endswith(".csv"):
            vessels = ingestion.load_from_csv(args.input_file, args.year)
        else:
            vessels = ingestion.load_from_excel(args.input_file, args.year)

        requirements = analyze_vessel_requirements(vessels)

    # Generate output
    output_code = generate_application_requirements_update(requirements)

    if args.output:
        with open(args.output, "w") as f:
            f.write(output_code)
        print(f"Requirements written to {args.output}")
    else:
        print(output_code)

    # Print summary
    print("\n=== Summary ===")
    for kb_type, req in sorted(requirements.items()):
        print(
            f"{kb_type:20s}: {req.power_range_min_kw/1000:6.1f} - {req.power_range_max_kw/1000:6.1f} MW "
            f"(n={req.sample_size}, conf={req.confidence:.0%})"
        )


if __name__ == "__main__":
    main()
