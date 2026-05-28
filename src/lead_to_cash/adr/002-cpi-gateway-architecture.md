# ADR-002: SAP CPI as Single Gateway Architecture

**Status:** Accepted
**Date:** 2026-01-18
**Deciders:** Architecture Team
**Consulted:** SAP Integration Team, Security Team
**Informed:** Development Team, Operations Team

## Context

The Lead-to-Cash system integrates with three SAP systems:
- **CEC (Customer Engagement Center)**: Opportunity management via Sales Cloud
- **IPAS (Intelligent Product Advisor System)**: Product configuration
- **MS5 (SAP S/4HANA)**: Master data and sales order processing

Initially, each client could potentially connect directly to its target system. However, this creates multiple connection paths, complicates security management, and makes monitoring difficult.

## Decision Drivers

* **Security**: Single point of authentication and authorization
* **Maintainability**: Centralized integration logic and error handling
* **Monitoring**: Unified logging and metrics across all SAP systems
* **Compliance**: Consistent audit trails (ISO 27001)
* **Scalability**: CPI provides built-in rate limiting and caching
* **Flexibility**: CPI allows transformation logic without code changes

## Considered Options

* **Option 1: Direct Connections** - Each client connects directly to its target system
* **Option 2: CPI as Single Gateway** - All requests route through SAP CPI
* **Option 3: Hybrid Approach** - CPI for MS5, direct for CEC/IPAS

## Decision Outcome

Chosen option: **"Option 2: CPI as Single Gateway"**, because it provides:
- Single point of authentication (OAuth 2.0 via CPI)
- Unified monitoring and logging
- Consistent error handling
- Simplified security posture
- Better alignment with SAP integration best practices

### Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│  SAPIntegrationMCPServer (13 MCP Tools)                        │
│    ├── CECClient  ─┐                                            │
│    ├── IPASClient ─┼─→ CPIClient ─→ SAP CPI ─→ Target Systems   │
│    └── MS5Client  ─┘                                            │
└─────────────────────────────────────────────────────────────────┘

SAP CPI Routes:
    - CPI → SAP CEC (existing interface)
    - CPI → IPAS (NEW interface)
    - CPI → Cloud Connector → MS5/ECC (existing interface)
```

### Positive Consequences

* Single OAuth token acquisition shared across all systems
* Unified error handling at the CPI level
* Consistent audit logging for compliance
* Simplified firewall and network configuration
* CPI provides retry logic, caching, and transformation
* Easier to add new SAP systems in the future

### Negative Consequences

* Additional latency through CPI gateway (mitigated by caching)
* CPI becomes single point of failure (mitigated by CPI high availability)
* Requires CPI iFlow development for each system

## Pros and Cons of the Options

### Option 1: Direct Connections

Each client (CECClient, IPASClient, MS5Client) connects directly to its target system.

* Good, because lower latency for direct calls
* Good, because simpler initial implementation
* Bad, because multiple authentication mechanisms to manage
* Bad, because no centralized logging
* Bad, because difficult to maintain consistent error handling
* Bad, because security vulnerabilities in each connection point

### Option 2: CPI as Single Gateway (Selected)

All requests route through SAP CPI, which forwards to target systems.

* Good, because single point of authentication
* Good, because unified monitoring and logging
* Good, because consistent error handling
* Good, because CPI provides built-in retry and caching
* Good, because easier to add transformation logic
* Bad, because additional network hop (mitigated by caching)
* Bad, because CPI must be highly available (CPI provides HA)

### Option 3: Hybrid Approach

CPI for MS5 (requires Cloud Connector), direct for CEC/IPAS.

* Good, because optimizes for different system characteristics
* Good, because reduces CPI load
* Bad, because inconsistent architecture
* Bad, because multiple security models to maintain
* Bad, because complicated monitoring setup

## Implementation Details

### Client Architecture

All clients accept an optional `cpi_client` parameter to share the same CPIClient instance:

```python
# Shared CPI client for all systems
cpi = CPIClient()

# System-specific clients (all route through CPI)
cec = CECClient(cpi_client=cpi)
ipas = IPASClient(cpi_client=cpi)
ms5 = MS5Client(cpi_client=cpi)
```

### CPI iFlow Names

| System | iFlow | Purpose |
|--------|-------|---------|
| CEC | CECGetOpportunity | Get opportunity by ID (see ADR-006 for fields) |
| CEC | CECSearchOpportunities | Search opportunities (see ADR-006 for fields) |
| CEC | CECGetOpportunitiesByAccount | Get opportunities for account (see ADR-006 for fields) |
| CEC | CECGetCommercialTerms | Get payment terms, Incoterms |
| IPAS | IPASGetConfiguration | Get product configuration (NEW) |
| IPAS | IPASGetByOpportunity | Get configs for opportunity (NEW) |
| IPAS | IPASGetProductCatalog | Get product catalog (NEW) |
| IPAS | IPASValidateConfiguration | Validate configuration (NEW) |
| MS5 | MS5CustomerGet | BAPI_CUSTOMER_GETDETAIL2 |
| MS5 | MS5CreditCheck | BAPI_CR_ACC_GETDETAIL |
| MS5 | MS5OrderSimulate | BAPI_SALESORDER_SIMULATE |
| MS5 | MS5OrderCreate | BAPI_SALESORDER_CREATEFROMDAT2 |

### MCP Tools (13 Total)

**CEC (4 tools):**
- `cec_get_opportunity`
- `cec_search_opportunities`
- `cec_get_opportunities_by_account`
- `cec_get_commercial_terms`

**IPAS (4 tools):**
- `ipas_get_configuration`
- `ipas_get_configurations_by_opportunity`
- `ipas_get_product_catalog`
- `ipas_validate_configuration`

**MS5 (5 tools):**
- `sap_get_customer`
- `sap_check_credit`
- `sap_simulate_order`
- `sap_create_order`
- `sap_health_check`

## Links

* [ADR-006: CEC Opportunity Fields Enhancement](./006-cec-opportunity-fields-enhancement.md)
* [SAP CPI Configuration](../docs/SAP_CPI_Configuration.md)
* [CEC Integration Guide](../docs/CEC_Integration_Guide.md)
* [Kailash Platform Deployment Architecture](../../../docs/architecture/)
* [MCP Server Implementation](../mcp/sap_cpi_server.py)

---

*This ADR is specific to the Lead-to-Cash application and its SAP integration architecture.*
