# SAP CEC (Customer Engagement Center) Integration Guide

**Version:** 1.0
**Date:** 2026-02-02
**Status:** Production
**Related ADRs:** ADR-002 (CPI Gateway), ADR-006 (CEC Opportunity Fields)

## 1. Overview

The CEC (Customer Engagement Center) integration provides access to SAP Sales Cloud opportunity management via the CPI gateway architecture. All CEC requests route through SAP CPI as the single gateway per ADR-002.

```
CECClient → CPIClient → SAP CPI → SAP CEC (Sales Cloud)
```

## 2. Architecture

### 2.1 Gateway Pattern

```
┌─────────────────────────────────────────────────────────────────┐
│  SAPIntegrationMCPServer                                        │
│    └── CECClient ─→ CPIClient ─→ SAP CPI ─→ SAP CEC             │
└─────────────────────────────────────────────────────────────────┘
```

### 2.2 CPI iFlows

| iFlow Name | Purpose | Description |
|------------|---------|-------------|
| CECGetOpportunity | Single opportunity | Retrieve by opportunity ID |
| CECSearchOpportunities | Search | Search by query string |
| CECGetOpportunitiesByAccount | Account opportunities | All opportunities for a customer |
| CECGetCommercialTerms | Payment terms | Incoterms, pricing, payment terms |

## 3. Opportunity Fields (ADR-006)

### 3.1 Standard Fields (9 Fields)

| CEC UI Label | Field Name | Type | Description |
|--------------|------------|------|-------------|
| Account ID | `account_id` | String | SAP Customer ID (10-digit padded) |
| Status | `status` | Enum | Won, Lost, Open, Qualified |
| Expected Revenue | `expected_revenue` | Decimal | Expected opportunity value |
| Currency | `currency` | String | ISO 4217 (EUR, USD, SGD) |
| Estimated Award Date | `close_date` | Date | Expected close/award date |
| Opportunity Chance | `win_probability` | Integer | 10, 35, 65, 90 |
| Opportunity Title | `title` | String | Opportunity name/subject |
| Start Date | `start_date` | Date | Creation date |
| Sales Type | `sales_type` | Enum | OE_SALES, SERVICE_SALES |

### 3.2 Milestone Payment Fields (ADR-006)

| CEC UI Label | Field Name | Type | Description |
|--------------|------------|------|-------------|
| Sales Order Number | `sap_order_id` | String | SAP S/4HANA Sales Order (10-digit) |
| IPAS Quote Number | `ipas_quote_id` | String | IPAS configuration quote reference |

### 3.3 Win Probability Mapping

| CEC Display | Value | Description |
|-------------|-------|-------------|
| 10 Little chances | 10 | Low probability (10%) |
| 35 Limited chances | 35 | Below average (35%) |
| 65 Good chances | 65 | Above average (65%) |
| 90 Very good chances | 90 | High probability (90%) |

### 3.4 Sales Type Mapping

| CEC Display | Value | SAP Mapping |
|-------------|-------|-------------|
| OE Sales | `OE_SALES` | Original Equipment |
| Service Sales | `SERVICE_SALES` | Aftermarket/MRO |

## 4. Usage

### 4.1 Basic Usage

```python
from lead_to_cash.integrations.cec_client import CECClient

# Using async context manager (recommended)
async with CECClient() as client:
    # Get single opportunity
    opp = await client.get_opportunity("OPP-2026-001")
    print(f"Title: {opp.title}")
    print(f"Value: {opp.currency} {opp.expected_revenue:,.2f}")
    print(f"SAP Order: {opp.sap_order_id}")
    print(f"IPAS Quote: {opp.ipas_quote_id}")

    # Get all opportunities for an account
    opps = await client.get_opportunities_by_account("0022005992")
    for o in opps:
        print(f"{o.opportunity_id}: {o.title} - {o.status}")
```

### 4.2 Shared CPI Client

```python
from lead_to_cash.integrations.cpi_client import CPIClient
from lead_to_cash.integrations.cec_client import CECClient
from lead_to_cash.integrations.ms5_client import MS5Client

# Share single CPI client across multiple integrations
cpi = CPIClient()
await cpi.connect()

cec = CECClient(cpi_client=cpi)
ms5 = MS5Client(cpi_client=cpi)

await cec.connect()
await ms5.connect()

# All requests route through shared CPI connection
opp = await cec.get_opportunity("OPP-2026-001")
customer = await ms5.get_customer(opp.account_id)
```

### 4.3 SAP Field Mapping

```python
# Convert opportunity to SAP Sales Order format
opp = await client.get_opportunity("OPP-2026-001")
sap_data = opp.to_sap_mapping()

# Returns:
# {
#     "BSTKD": "OPP-2026-001",       # Customer PO reference
#     "KUNNR": "0022005992",          # Sold-to party (10-digit)
#     "WAERK": "SGD",                 # Currency
#     "VKORG": "1000",                # Sales organization
#     "VTWEG": "10",                  # Distribution channel
#     "SPART": "10",                  # Division
#     "VBELN_REF": "1000025001",      # Sales Order reference (ADR-006)
#     "IPAS_QUOTE": "IPAS-2025-0001", # IPAS Quote reference (ADR-006)
#     "items": [...]
# }
```

### 4.4 Serialization

```python
# Convert to dictionary for JSON serialization
opp = await client.get_opportunity("OPP-2026-001")
opp_dict = opp.to_dict()

# Returns all fields including milestone payment fields
import json
print(json.dumps(opp_dict, indent=2))
```

## 5. KYP Report Integration

The CEC client provides opportunity data for KYP (Know Your Partner) reports:

### 5.1 Business Context Section

```python
# Fetch opportunities for KYP business context
opps = await cec.get_opportunities_by_account(sap_customer_id)

# Calculate metrics
won_deals = [o for o in opps if o.status == "Won"]
lost_deals = [o for o in opps if o.status == "Lost"]
open_deals = [o for o in opps if o.status == "Open"]

lifetime_value = sum(o.expected_revenue for o in won_deals)
open_pipeline_value = sum(o.expected_revenue for o in open_deals)

# These metrics feed into KYP Business Context section
# Source attribution: "CEC" or "CEC, Records from {first_order_date}"
```

### 5.2 Source Attribution

In KYP reports, CEC-derived data is attributed with source "CEC":

```
┌─────────────────────────┬─────────────────────────────┬─────────┐
│ Field                   │ Value                       │ Source  │
├─────────────────────────┼─────────────────────────────┼─────────┤
│ Lifetime Value          │ SGD 2,500,000.00            │ CEC     │
├─────────────────────────┼─────────────────────────────┼─────────┤
│ Won Deals               │ 12                          │ CEC     │
├─────────────────────────┼─────────────────────────────┼─────────┤
│ Open Pipeline           │ SGD 650,000.00              │ CEC     │
└─────────────────────────┴─────────────────────────────┴─────────┘
```

## 6. MCP Tools

The CEC integration is exposed via 4 MCP tools:

| Tool Name | Description |
|-----------|-------------|
| `cec_get_opportunity` | Get single opportunity by ID |
| `cec_search_opportunities` | Search opportunities |
| `cec_get_opportunities_by_account` | Get opportunities for account |
| `cec_get_commercial_terms` | Get payment/commercial terms |

### 6.1 MCP Tool Usage

```python
# Via MCP server
result = await mcp_server.call_tool(
    "cec_get_opportunity",
    {"opportunity_id": "OPP-2026-001"}
)
```

## 7. Development & Testing

### 7.1 CPI Simulator

For development without SAP access, use the CPI Simulator:

```python
from lead_to_cash.integrations.cpi_simulator import CPISimulator
from lead_to_cash.integrations.cec_client import CECClient

# Use simulator as drop-in replacement for CPIClient
simulator = CPISimulator()
await simulator.connect()

cec = CECClient(cpi_client=simulator)
await cec.connect()

# All CEC operations work with simulated data
opps = await cec.get_opportunities_by_account("0022005992")
# Returns simulated ST Engineering opportunities
```

### 7.2 Simulated Customers

| Customer ID | Name | Opportunities | LTV |
|-------------|------|---------------|-----|
| 0022005992 | ST Engineering | 17 (12W/3L/2O) | SGD 2.5M |
| 0000100001 | Batam Fast Ferry | 8 (5W/1L/2O) | SGD 1.2M |
| 0000100002 | Maersk A/S | 13 (8W/2L/3O) | EUR 4.5M |
| 0021000090 | CLLS Power System | 5 (3W/1L/1O) | EUR 380K |

## 8. Configuration

### 8.1 Environment Variables

```bash
# .env
SAP_CEC_URL=https://tenant.c4c.ibmcloud.com
SAP_CEC_CLIENT_ID=your_client_id
SAP_CEC_CLIENT_SECRET=your_client_secret
SAP_CEC_TIMEOUT=30
```

### 8.2 Config Class

```python
from lead_to_cash.config import config

# Access CEC configuration
cec_config = config.sap_cec
print(f"URL: {cec_config.base_url}")
print(f"Timeout: {cec_config.timeout_seconds}s")
```

## 9. Error Handling

### 9.1 Connection Errors

```python
try:
    await cec.connect()
except ValueError as e:
    # CPI not configured
    logger.error(f"CEC connection failed: {e}")
```

### 9.2 Operation Errors

```python
try:
    opp = await cec.get_opportunity("INVALID-ID")
except RuntimeError as e:
    # Client not connected
    logger.error(f"Operation failed: {e}")
```

## 10. Health Checks

```python
# Check CEC connectivity
health = await cec.health_check()
# Returns:
# {
#     "status": "connected",
#     "cpi_status": {...},
#     "iflows": {
#         "get_opportunity": "CECGetOpportunity",
#         "search": "CECSearchOpportunities",
#         "by_account": "CECGetOpportunitiesByAccount"
#     }
# }
```

## 11. Related Documentation

- [ADR-002: CPI Gateway Architecture](../adr/002-cpi-gateway-architecture.md)
- [ADR-006: CEC Opportunity Fields Enhancement](../adr/006-cec-opportunity-fields-enhancement.md)
- [SAP CPI Configuration](./SAP_CPI_Configuration.md)
- [KYP Guide](./guides/KYP_guide.md)

## 12. Changelog

| Version | Date | Changes |
|---------|------|---------|
| 1.0 | 2026-02-02 | Initial release with ADR-006 milestone payment fields |
