# ADR-006: CEC Opportunity Fields Enhancement

**Status:** Accepted
**Date:** 2026-02-02
**Deciders:** Integrum Architecture Team, RRPS Integration Team
**Consulted:** Sandra, Sharon (RRPS), Priya (RRPS)
**Informed:** Development Team, SAP Integration Team

## Context

During the design phase, the RRPS team identified the need to send Sales Order Number and IPAS Quote Number from two different systems for milestone payments and order completeness tracking.

Instead of building two new interfaces, we propose pulling this information from CEC (Customer Engagement Center) while extracting customer opportunities, by reusing the existing CECGetOpportunitiesByAccount interface.

This decision optimizes the number of interfaces by adding two additional fields to the existing CEC opportunity data structure.

## Decision Drivers

* **Interface Optimization**: Avoid building 2 new interfaces for Sales Order and IPAS Quote retrieval
* **Data Consistency**: Single source of truth for opportunity-related data
* **Maintenance Reduction**: Fewer interfaces = less maintenance overhead
* **Existing Infrastructure**: CEC already routes through CPI gateway (per ADR-002)
* **Milestone Payments**: Sales Order Number required for payment tracking
* **Order Completeness**: IPAS Quote Number required for configuration traceability

## Considered Options

* **Option 1**: Build separate interfaces for Sales Order and IPAS Quote retrieval
* **Option 2**: Add fields to existing CEC opportunity interface (Selected)
* **Option 3**: Retrieve from MS5/IPAS directly with separate calls

## Decision Outcome

Chosen option: **"Option 2: Add fields to existing CEC opportunity interface"**, because:

- Reuses existing CECGetOpportunitiesByAccount interface
- No new CPI iFlows required
- Single round-trip retrieves all opportunity data
- Maintains architectural consistency with ADR-002

## CEC Field Specification

### Standard Opportunity Fields (9 Fields)

| CEC UI Label | CEC Field | Integrum Mapping | Data Type | Description |
|--------------|-----------|------------------|-----------|-------------|
| Account ID | `account_id` | `account_id` | String | SAP Customer ID (10-digit) |
| Status | `status` | `status` | Enum | Won, Lost, Open, Qualified |
| Expected Revenue | `expected_revenue` | `expected_revenue` | Decimal | Expected value |
| Currency | `currency` | `currency` | ISO 4217 | EUR, USD, SGD, etc. |
| Estimated Award Date | `close_date` | `close_date` | Date | Expected close date |
| Opportunity Chance | `win_probability` | `win_probability` | Integer | 10, 35, 65, 90 |
| Opportunity Title | `title` | `title` | String | Opportunity name/subject |
| Start Date | `start_date` | `start_date` | Date | Creation date |
| Sales Type | `sales_type` | `sales_type` | Enum | OE_SALES, SERVICE_SALES |

### New Milestone Payment Fields (2 Fields)

| CEC UI Label | CEC Field | Integrum Mapping | Data Type | Description |
|--------------|-----------|------------------|-----------|-------------|
| Sales Order Number | `sap_order_id` | `sap_order_id` | String | SAP S/4HANA Sales Order (10-digit) |
| IPAS Quote Number | `ipas_quote_id` | `ipas_quote_id` | String | IPAS configuration quote reference |

### Win Probability Mapping

| CEC Display | Value | Description |
|-------------|-------|-------------|
| 10 Little chances | 10 | Low probability |
| 35 Limited chances | 35 | Below average |
| 65 Good chances | 65 | Above average |
| 90 Very good chances | 90 | High probability |

### Sales Type Mapping

| CEC Display | Value | SAP Mapping |
|-------------|-------|-------------|
| OE Sales | `OE_SALES` | Original Equipment |
| Service Sales | `SERVICE_SALES` | Aftermarket/MRO |

## Implementation Details

### Updated Opportunity Dataclass

```python
@dataclass
class Opportunity:
    """CEC Opportunity data with milestone payment fields."""

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

    # Classification
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

    # NEW: Milestone Payment Fields (ADR-006)
    sap_order_id: Optional[str] = None  # SAP Sales Order Number
    ipas_quote_id: Optional[str] = None  # IPAS Quote Number
```

### SAP Field Mapping Update

The `to_sap_mapping()` method is updated to include milestone payment references:

```python
def to_sap_mapping(self) -> dict[str, Any]:
    return {
        "BSTKD": self.opportunity_id,  # Customer PO reference
        "KUNNR": self.account_id.zfill(10),  # Sold-to party
        "WAERK": self.currency,
        "VKORG": self.sales_org or "",
        "VTWEG": self.distribution_channel or "",
        "SPART": self.division or "",
        # Milestone payment references
        "VBELN_REF": self.sap_order_id or "",  # Sales Order reference
        "IPAS_QUOTE": self.ipas_quote_id or "",  # IPAS Quote reference
        "items": [...],
    }
```

### CPI Response Structure

The CECGetOpportunitiesByAccount response includes the new fields:

```json
{
  "items": [
    {
      "id": "OPP-2026-001",
      "account_id": "0022005992",
      "account_name": "ST Engineering",
      "status": "Won",
      "expected_revenue": 450000.00,
      "currency": "SGD",
      "close_date": "2026-01-15",
      "start_date": "2025-09-01",
      "title": "MTU 16V4000 M65L Marine Propulsion",
      "win_probability": 90,
      "sales_type": "OE_SALES",
      "sap_order_id": "1000012345",
      "ipas_quote_id": "IPAS-2025-0892"
    }
  ]
}
```

## Positive Consequences

* No new CPI iFlows required
* Single API call retrieves complete opportunity data
* Enables milestone payment tracking without additional integration
* Maintains consistency with CPI Gateway Architecture (ADR-002)
* Reduces total number of interfaces by 2

## Negative Consequences

* CEC must be updated to expose these fields (requires SAP configuration)
* Slightly larger response payload (negligible impact)

## Related Documents

* [ADR-002: CPI Gateway Architecture](./002-cpi-gateway-architecture.md)
* [CEC Integration Client](../integrations/cec_client.py)
* [CPI Simulator](../integrations/cpi_simulator.py)
* [SAP CPI Configuration](../docs/SAP_CPI_Configuration.md)

## Approval

This enhancement was requested and approved by:
- Sandra (RRPS) - Confirmed fields available in CEC
- Sharon (RRPS) - Approved reuse of existing interface
- Priya (RRPS) - Confirmed milestone payment requirements

---

*This ADR documents the CEC opportunity fields enhancement for the Lead-to-Cash application.*
