# Legitimate Data Acquisition Tasks for Engine Knowledge Base

**Status**: ACTIVE - Data collection required before production use
**Created**: 2026-01-22
**Owner**: RR Engineering Team

---

## Executive Summary

The engine_master_data.py file contains **65 engines** with **VERIFIED duty class** information only.
All other technical specifications require legitimate sourcing before production use.

**Currently Verified** (from manufacturer rating systems):
- Duty class (e.g., MTU M72=Light, M93=Heavy)
- Rating designation
- Primary applications (from marketing materials)

**Requires Legitimate Sources**:
- Physical dimensions (weight, length, width, height)
- SFOC (Specific Fuel Oil Consumption) at 100%, 75%, 50% load
- TBO (Time Between Overhaul) intervals
- Type approvals (classification society certificates)

---

## Task 1: SFOC Data (Specific Fuel Oil Consumption)

### What's Needed
For each engine model, obtain:
- `sfoc_rated_g_kwh`: Fuel consumption at 100% MCR (g/kWh)
- `sfoc_75pct_g_kwh`: Fuel consumption at 75% load
- `sfoc_50pct_g_kwh`: Fuel consumption at 50% load

### Legitimate Sources

| Source | Access Level | Data Quality | Notes |
|--------|-------------|--------------|-------|
| **Manufacturer Datasheets** | OEM relationship | HIGH | Best source, may require NDA |
| **IMO EEDI Database** | Public | MEDIUM | Contains verified SFOC for certified vessels |
| **MAN PrimeServ TechDoc** | Customer portal | HIGH | Requires MAN account |
| **MTU MarineLink** | Customer portal | HIGH | Requires MTU account |
| **Cummins QuickServe** | Customer portal | HIGH | Requires Cummins account |

### How to Obtain

1. **OEM Sales Contact**: Request technical datasheets from manufacturer sales representatives
   - MTU: Contact RR Rolls-Royce internal (MTU is RR-owned)
   - Cummins: marine.sales@cummins.com
   - Cat: marine@cat.com
   - MAN: engines@man.eu

2. **IMO EEDI Database**: https://gisis.imo.org/EEDI
   - Contains SFOC data for vessels certified under MARPOL Annex VI
   - Free access for basic data, detailed reports may require subscription

3. **Industry Publications**:
   - Marine Technology News engine specifications
   - Diesel & Gas Turbine Worldwide buyer's guide
   - Significant Ships yearbook (IMarEST)

### Data Format Example
```python
# FROM: MTU Datasheet DS-2000-M93-EN Rev.4, Page 12, Figure 3.2
sfoc_rated_g_kwh=199,  # At 2100 RPM, 1432 kW
sfoc_75pct_g_kwh=192,  # At 75% load, ~1074 kW
sfoc_50pct_g_kwh=205,  # At 50% load, ~716 kW
data_source="MTU DS-2000-M93-EN Rev.4 p.12"
```

---

## Task 2: Physical Dimensions

### What's Needed
For each engine model:
- `dry_weight_kg`: Engine weight without fluids
- `length_mm`: Overall length
- `width_mm`: Overall width
- `height_mm`: Overall height

### Legitimate Sources

| Source | Access Level | Data Quality |
|--------|-------------|--------------|
| **Manufacturer Datasheets** | OEM relationship | HIGH |
| **Manufacturer Websites** | Public | HIGH (but incomplete) |
| **Marine Equipment Catalogs** | Industry | MEDIUM |

### How to Obtain

1. **MTU**: https://www.mtu-solutions.com/eu/en/applications/marine.html
   - Navigate to specific engine series
   - Download PDF datasheet (requires registration)
   - Look for "Dimensions and Weights" section

2. **Cummins**: https://www.cummins.com/engines/marine
   - Select engine family
   - "Specifications" tab contains dimensions

3. **Cat**: https://www.cat.com/en_US/products/new/power-systems/marine-power-systems.html
   - Download spec sheets by model

### Data Format Example
```python
# FROM: Cummins Marine Engine QSK60 Spec Sheet 2025, Page 3
dry_weight_kg=5533,
length_mm=2692,
width_mm=1814,
height_mm=1816,
data_source="Cummins QSK60-M Marine Spec Sheet 2025 p.3"
```

---

## Task 3: TBO (Time Between Overhaul)

### What's Needed
- `tbo_hours`: Major overhaul interval (hours)
- `minor_service_hours`: Minor service interval (hours)

### Legitimate Sources

| Source | Access Level | Data Quality | Notes |
|--------|-------------|--------------|-------|
| **Manufacturer Maintenance Manuals** | Customer only | HIGH | Often confidential |
| **OEM Service Agreements** | Contract required | HIGH | Specific to operating conditions |
| **Fleet Operator Data** | Industry contacts | MEDIUM | Actual operating experience |

### How to Obtain

1. **OEM Technical Support**: Request maintenance schedules
   - TBO varies by duty cycle, operating conditions, fuel quality
   - Request specific values for marine propulsion applications

2. **Industry Guidelines**:
   - ISO 8528-5: Reciprocating internal combustion engine driven alternating current generating sets
   - CIMAC (International Council on Combustion Engines) recommendations

3. **Fleet Operators**: Contact major operators for actual maintenance data
   - Maersk Supply Service (OSV fleet)
   - Edison Chouest (OSV/tugboat fleet)
   - Swire Pacific Offshore

### Important Note
TBO values are **duty-class dependent**:
- Light Duty: 8,000-12,000 hours typical
- Medium Duty: 12,000-18,000 hours typical
- Heavy Duty: 18,000-24,000 hours typical
- Continuous: 24,000-30,000 hours typical

These are GUIDELINES - actual values depend on specific engine and operating profile.

---

## Task 4: Type Approvals (Classification Society Certificates)

### What's Needed
For each engine, verified type approvals from:
- DNV (Det Norske Veritas)
- Lloyd's Register (LR)
- ABS (American Bureau of Shipping)
- Bureau Veritas (BV)
- ClassNK (Nippon Kaiji Kyokai)
- CCS (China Classification Society)
- Korean Register (KR)
- RINA (Italian Register)

### Legitimate Sources

| Source | Access Level | Data Quality |
|--------|-------------|--------------|
| **Classification Society Databases** | Public/Subscription | HIGH |
| **Manufacturer Type Approval Lists** | OEM | HIGH |
| **IMO GISIS** | Registered users | HIGH |

### How to Obtain

1. **DNV Approval Finder**: https://approvalfinder.dnv.com
   - Search by manufacturer and model
   - Returns certificate number and validity

2. **Lloyd's Register**: https://www.lr.org/en/type-approval/
   - Type approval database search
   - Certificate PDFs available

3. **ABS**: https://www.eagle.org/content/type-approvals
   - Requires ABS account
   - Returns certificate number

4. **ClassNK**: https://www.classnk.or.jp/hp/en/type_approval/
   - Search by manufacturer
   - Japanese and English interface

5. **Manufacturer Lists**: Contact OEM for their maintained approval list
   - MTU maintains a comprehensive type approval matrix

### Data Format Example
```python
# Verified from DNV ApprovalFinder, searched 2026-01-22
type_approvals=[
    {"society": "DNV", "cert": "TAA00001XY", "valid_until": "2027-06-30", "verified_date": "2026-01-22"},
    {"society": "LR", "cert": "MA123456", "valid_until": "2026-12-31", "verified_date": "2026-01-22"},
]
data_source="DNV ApprovalFinder, LR TypeApproval DB"
```

---

## Task 5: Performance Curves (Optional but Valuable)

### What's Needed
Power and torque curves at multiple RPM points:
- Power (kW) at 60%, 70%, 80%, 90%, 100% rated RPM
- Torque (Nm) at same points
- BSFC (Brake Specific Fuel Consumption) at each point

### Legitimate Sources
- **OEM Test Reports**: Gold standard, requires NDA
- **Marine survey reports**: May contain partial data
- **Academic papers**: Sometimes publish verified test data

### Priority
LOW - Nice to have but not critical for initial deployment

---

## Implementation Workflow

### Phase 1: Internal MTU Data (Weeks 1-2)
Since MTU is RR-owned, internal access should be straightforward:
1. Contact MTU Marine technical documentation team
2. Request datasheets for all Series 2000, 4000, 8000 engines
3. Populate: dimensions, SFOC, TBO for 17 MTU engines

### Phase 2: Competitor Public Data (Weeks 2-4)
Start with publicly available data:
1. Download Cat, Cummins, MAN datasheets from websites
2. Search classification society databases for type approvals
3. Populate: dimensions, partial SFOC for ~30 engines

### Phase 3: OEM Relationship Data (Weeks 4-8)
Leverage existing supplier relationships:
1. Contact Cummins marine sales for detailed specs
2. Request Cat marine power systems data
3. Populate: remaining SFOC, TBO, full type approvals

### Phase 4: Verification (Weeks 8-10)
Quality assurance:
1. Cross-reference SFOC values against IMO EEDI database
2. Verify type approvals are current (not expired)
3. Document all sources in data_source field

---

## Data Quality Tracking

Each EngineSpecification should track:

```python
@dataclass
class EngineSpecification:
    # ... fields ...

    # Data quality tracking
    data_source: str = "duty_class_only"  # e.g., "MTU DS-2000-M93-EN p.12"
    verified: bool = False  # True only when all critical fields have sources
    verified_date: Optional[str] = None  # ISO date of last verification
    data_completeness: float = 0.1  # 0.0-1.0 based on populated fields
```

### Completeness Calculation
- duty_class: 10% (verified from rating designation)
- dimensions (all 4): 30%
- SFOC (all 3): 30%
- TBO (both): 15%
- type_approvals: 15%

An engine with only duty_class has 10% completeness.
A fully populated engine has 100% completeness.

---

## Contacts for Data Acquisition

| Manufacturer | Contact Type | Email/Phone |
|-------------|--------------|-------------|
| MTU | Internal (RR) | TBD - internal contact |
| Cummins | Sales | marine.sales@cummins.com |
| Caterpillar | Marine Power | marine@cat.com |
| MAN Engines | Technical | engines@man.eu |
| Wartsila | Marine | marine.sales@wartsila.com |
| Volvo Penta | Commercial | commercial.marine@volvo.com |
| Yanmar | Marine | marine@yanmar.com |

---

## Success Criteria

**Minimum Viable Data** (for production deployment):
- 100% of engines have verified dimensions
- 80% of engines have SFOC at rated power
- 80% of engines have at least 3 type approvals verified

**Target Data Quality**:
- 100% of engines have complete SFOC curves (3 points)
- 100% of engines have verified type approvals
- All data sources documented with citations
