# Engine Data from Secondary Sources

**Collection Date**: 2026-01-22
**Status**: UNVERIFIED - Secondary aggregator sources only

## CRITICAL SOURCE QUALITY WARNING

**All data in this document is from SECONDARY SOURCES, not official OEM datasheets.**

| Source Used | Type | Authoritative? |
|-------------|------|----------------|
| maritimepropulsion.com | Industry directory/aggregator | **NO** - Secondary |
| yachtbuyer.com | Yacht sales platform | **NO** - Not authoritative |
| mtu-allison.com.ar | MTU distributor | **PARTIAL** - Distributor, not OEM |
| lectura-specs.com | Equipment database | **NO** - Secondary |
| nauticexpo.com | Trade directory | **NO** - Secondary |

### What "Verified" Actually Requires

True verification requires:
1. Official OEM datasheet PDF with document number
2. Page number and figure reference
3. Revision date
4. Direct download from manufacturer website

**This data does NOT meet these criteria.**

---

## Data Collected (UNVERIFIED - USE WITH CAUTION)

### MTU 12V 2000 M93
| Specification | Value | Source | Status |
|--------------|-------|--------|--------|
| Power | 1,340 kW @ 2,450 RPM | [Maritime Propulsion](https://www.maritimepropulsion.com/directory/product/mtu-12v2000m93-1797-hp-131940) | UNVERIFIED |
| Weight (dry) | 6,240 kg | Maritime Propulsion | UNVERIFIED |
| Dimensions L×W×H | 2,265 × 1,360 × 1,450 mm | Maritime Propulsion | UNVERIFIED |
| SFOC | NOT AVAILABLE | - | - |

### MTU 16V 2000 M93
| Specification | Value | Source | Status |
|--------------|-------|--------|--------|
| Power | 1,790 kW @ 2,450 RPM | [Maritime Propulsion](https://www.maritimepropulsion.com/directory/product/mtu-16v2000m93-2400-hp-131931) | UNVERIFIED |
| Weight (dry) | 4,570 kg | Maritime Propulsion | UNVERIFIED |
| Dimensions L×W×H | 2,330 × 1,290 × 1,420 mm | Maritime Propulsion | UNVERIFIED |
| SFOC | ~~209 g/kWh~~ | ~~YachtBuyer~~ | **REMOVED** - Not authoritative |

### MTU 12V 4000 M93
| Specification | Value | Source | Status |
|--------------|-------|--------|--------|
| Power | 2,340 kW @ 2,100 RPM | [Maritime Propulsion](https://www.maritimepropulsion.com/directory/product/mtu-12v4000m93-3138-hp-132010) | UNVERIFIED |
| Weight (dry) | 7,800-8,410 kg | Maritime Propulsion, MTU-Allison | DISCREPANCY |
| Dimensions L×W×H | 2,840 × 1,465 × 2,450 mm | MTU-Allison distributor | UNVERIFIED |
| Displacement | 51.7L or 76.3L | **CONFLICTING** | UNVERIFIED |
| SFOC | ~~216 g/kWh~~ | ~~MTU-Allison~~ | **REMOVED** - Distributor, not OEM |

### MAN D2862 LE463
| Specification | Value | Source | Status |
|--------------|-------|--------|--------|
| Power | 1,029 kW @ 2,100 RPM | [Maritime Propulsion](https://www.maritimepropulsion.com/directory/product/man--d-2862-le-463--1400-hp-132836) | UNVERIFIED |
| Weight (dry) | 2,270 kg | Maritime Propulsion | UNVERIFIED |
| Dimensions L×W×H | 1,631 × 1,153 × 1,289 mm | Maritime Propulsion | UNVERIFIED |
| SFOC | ~~210 g/kWh~~ | ~~Maritime Propulsion~~ | **REMOVED** - Aggregator, not authoritative |

### Wartsila 6L20
| Specification | Value | Source | Status |
|--------------|-------|--------|--------|
| Power | 1,200 kW @ 1,000 RPM | [Maritime Propulsion](https://www.maritimepropulsion.com/directory/product/wrtsil-6l20-16092hp-130167) | UNVERIFIED |
| Weight (dry) | 18,000 kg | Maritime Propulsion | UNVERIFIED |
| Dimensions L×W×H | 3,845 × 1,450 × 2,375 mm | Maritime Propulsion | UNVERIFIED |
| SFOC | NOT AVAILABLE | - | - |

### Cummins QSK60
| Specification | Value | Source | Status |
|--------------|-------|--------|--------|
| Power | 1,641-2,125 kW | [LECTURA](https://www.lectura-specs.com/en/model/components/engines-cummins/qsk60-2850-11688974) | UNVERIFIED |
| Weight (dry) | 8,754 kg | LECTURA (equipment database) | UNVERIFIED |
| Dimensions L×W×H | 3,290 × 1,757 × 2,415 mm | LECTURA | UNVERIFIED |
| SFOC | NOT AVAILABLE | - | - |

---

## Data Quality Summary (CORRECTED)

| Engine | Dimensions | Weight | SFOC | Status |
|--------|------------|--------|------|--------|
| MTU 12V 2000 M93 | Collected | Collected | None | UNVERIFIED |
| MTU 16V 2000 M93 | Collected | Collected | **REMOVED** | UNVERIFIED |
| MTU 12V 4000 M93 | Collected | Collected | **REMOVED** | UNVERIFIED |
| MAN D2862 LE463 | Collected | Collected | **REMOVED** | UNVERIFIED |
| Wartsila 6L20 | Collected | Collected | None | UNVERIFIED |
| Cummins QSK60 | Collected | Collected | None | UNVERIFIED |

**Total SFOC values from legitimate OEM sources: 0**

---

## Known Discrepancies (Require Resolution)

| Engine | Field | Value 1 | Value 2 | Resolution |
|--------|-------|---------|---------|------------|
| MTU 12V 4000 M93 | Displacement | 51.7L (MTU-Allison) | 76.3L (Maritime Propulsion) | **UNKNOWN** |
| MTU 16V 2000 M93 | Weight | 4,570 kg (website) | "under 3.4 tons" (search) | **UNKNOWN** |

---

## Legitimate Sources (To Be Contacted)

For verified data, contact:
- **MTU**: Internal RR systems (mtu-solutions.com portal access)
- **Cummins**: marine.sales@cummins.com
- **Caterpillar**: marine@cat.com
- **MAN Engines**: engines@man.eu
- **Wartsila**: marine.sales@wartsila.com
- **Volvo Penta**: commercial.marine@volvo.com

### Classification Society Databases
- [DNV ApprovalFinder](https://approvalfinder.dnv.com/) - Free registration required
- [Lloyd's Register](https://www.lr.org/en/type-approval/)
- [ClassNK](https://www.classnk.or.jp/hp/en/type_approval/)

---

## engine_master_data.py Status

All 6 engines with collected data now have:
- `verified=False` - Secondary sources only
- `data_source="secondary_aggregator:..."` - Clearly marked
- `sfoc_rated_g_kwh=None` - All SFOC removed (non-authoritative)
- Warning comments on each dimension field

**Example of corrected entry:**
```python
"MTU 16V 2000 M93": EngineSpecification(
    model_name="MTU 16V 2000 M93",
    duty_class=DutyClass.HEAVY_DUTY,
    rating_designation="M93",
    # WARNING: Secondary aggregator source, not official MTU datasheet
    # SFOC REMOVED: Was 209 g/kWh from YachtBuyer (yacht sales site, not authoritative)
    dry_weight_kg=4570,  # UNVERIFIED - from industry aggregator
    length_mm=2330,      # UNVERIFIED - from industry aggregator
    width_mm=1290,       # UNVERIFIED - from industry aggregator
    height_mm=1420,      # UNVERIFIED - from industry aggregator
    sfoc_rated_g_kwh=None,  # REMOVED - YachtBuyer is not authoritative source
    primary_applications=["fast_ferry", "coast_guard", "yacht"],
    data_source="secondary_aggregator:maritimepropulsion.com 2026-01-22",
    verified=False,  # Secondary source, not OEM datasheet
    notes="1790kW@2450RPM. Dimensions from aggregator site, needs OEM verification",
),
```
