# SAP CPI Configuration

**Version:** 2.0 | **Date:** January 2026 | **Classification:** Confidential

---

## 1. Architecture Overview

SAP CPI serves as the **single gateway** for all SAP system integrations per [ADR-002](../adr/002-cpi-gateway-architecture.md).

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

**Key Benefits:**
- Single OAuth 2.0 authentication
- Unified monitoring and logging
- Consistent error handling
- Built-in retry, caching, and transformation

---

## 2. CPI Environment URLs

| Environment | URL | Purpose |
|-------------|-----|---------|
| **DEV** | `https://rrps-dev.integrationsuite.cfapps.eu20.hana.ondemand.com` | Development & Testing |
| **QA** | `https://rrps-qa.it-cpi005.cfapps.eu20.hana.ondemand.com` | Quality Assurance |
| **PROD** | `https://rrps-prod.authentication.eu20.hana.ondemand.com` | Production |

**Promotion Path:** DEV → QA → PROD (Manual Upload/Download)

---

## 3. CPI iFlows by System

### 3.1 CEC (Customer Engagement Center) - Existing Interface

| iFlow Name | Method | Purpose | Cache TTL |
|------------|--------|---------|-----------|
| `CECGetOpportunity` | POST | Get opportunity by ID | 5 min |
| `CECSearchOpportunities` | POST | Search opportunities | 2 min |
| `CECGetOpportunitiesByAccount` | POST | Get opportunities for account | 3 min |
| `CECGetCommercialTerms` | POST | Get payment terms, Incoterms | 10 min |
| `CECGetPartners` | POST | Get partner data | 5 min |

### 3.2 IPAS (Intelligent Product Advisor System) - NEW Interface

| iFlow Name | Method | Purpose | Cache TTL |
|------------|--------|---------|-----------|
| `IPASGetConfiguration` | POST | Get product configuration | 5 min |
| `IPASGetByOpportunity` | POST | Get configs for opportunity | 5 min |
| `IPASGetProductCatalog` | POST | Get product catalog | 10 min |
| `IPASValidateConfiguration` | POST | Validate configuration | - |
| `IPASGetBOM` | POST | Get bill of materials | 5 min |

### 3.3 MS5 (SAP S/4HANA) - Existing Interface via Cloud Connector

| iFlow Name | Method | BAPI | Purpose |
|------------|--------|------|---------|
| `MS5CustomerGet` | POST | BAPI_CUSTOMER_GETDETAIL2 | Customer master data |
| `MS5CreditCheck` | POST | BAPI_CR_ACC_GETDETAIL | Credit limit check |
| `MS5OrderSimulate` | POST | BAPI_SALESORDER_SIMULATE | Order simulation |
| `MS5OrderCreate` | POST | BAPI_SALESORDER_CREATEFROMDAT2 | Order creation |
| `MS5OrderCommit` | POST | BAPI_TRANSACTION_COMMIT | Transaction commit |

---

## 4. MCP Server Tools

The `SAPIntegrationMCPServer` exposes 13 tools via MCP protocol:

### CEC Tools (4)
| Tool Name | Description |
|-----------|-------------|
| `cec_get_opportunity` | Get opportunity from SAP CEC via CPI |
| `cec_search_opportunities` | Search opportunities in SAP CEC |
| `cec_get_opportunities_by_account` | Get opportunities for an account |
| `cec_get_commercial_terms` | Get payment terms, Incoterms |

### IPAS Tools (4)
| Tool Name | Description |
|-----------|-------------|
| `ipas_get_configuration` | Get product configuration from IPAS (NEW) |
| `ipas_get_configurations_by_opportunity` | Get configs for opportunity |
| `ipas_get_product_catalog` | Get product catalog |
| `ipas_validate_configuration` | Validate configuration characteristics |

### MS5 Tools (5)
| Tool Name | Description |
|-----------|-------------|
| `sap_get_customer` | Customer master data from MS5 |
| `sap_check_credit` | Credit limit and exposure check |
| `sap_simulate_order` | Sales order simulation |
| `sap_create_order` | Sales order creation with commit |
| `sap_health_check` | Health check for all systems via CPI |

---

## 5. Naming Conventions

| Item | Convention | Example |
|------|------------|---------|
| **CPI Package** | `RRPS - {ProjectName}` | `RRPS - Integrum` |
| **iFlow** | `RRPS - {ProjectName} - {FlowName}` | `RRPS - Integrum - LeadToCash` |
| **Artifact** | `RRPS_{ProjectName}_{ArtifactType}` | `RRPS_Integrum_CustomerValidation` |

---

## 6. API Configuration

### 6.1 Allowed Methods
- GET
- POST
- PUT
- PATCH
- DELETE

### 6.2 Payload Limits
| Setting | Value | Notes |
|---------|-------|-------|
| Max Payload Size | 50 MB (standard) | Can be increased on request |
| Rate Limit | 100 req/min (MCP) | Configurable per tool |
| Compression | Not required | gzip optional |

### 6.3 Content Types
- `application/json` (preferred)
- `application/xml` (supported)

---

## 7. Error Handling

### 7.1 Error Response Format
```json
{
  "success": false,
  "error": {
    "code": "SAP_ERROR|CEC_ERROR|IPAS_ERROR|VALIDATION_ERROR|CONFIGURATION_ERROR",
    "message": "Human-readable error message",
    "field": "field_name (for validation errors)",
    "details": { "sap_messages": [...] }
  }
}
```

### 7.2 Retry Mechanism
| Strategy | Implementation |
|----------|----------------|
| CPI Level | Built-in retry for transient errors |
| MCP Level | Circuit breaker (5 failures threshold) |
| Application | Idempotency keys for order creation |

### 7.3 Idempotency
- Order creation uses request_id as idempotency key
- TTL: 1 hour
- Duplicate requests return cached result

---

## 8. Field Mappings (CEC → SAP)

| CEC Field | SAP Field | Description |
|-----------|-----------|-------------|
| AccountID | KUNNR | Sold-to party |
| OpportunityID | BSTKD | Customer PO reference |
| ProductID | MATNR | Material number |
| Quantity | KWMENG | Order quantity |
| RequestedDate | EDATU | Requested delivery date |
| Currency | WAERK | Document currency |
| SalesOrg | VKORG | Sales organization |
| DistributionChannel | VTWEG | Distribution channel |
| Division | SPART | Division |

---

## 9. Security & Compliance

| Requirement | Implementation | ISO Reference |
|-------------|----------------|---------------|
| Authentication | OAuth 2.0 (Production) | ISO 27001 A.14.1.2 |
| Transport | TLS 1.3 | ISO 27001 A.14.1.2 |
| Audit Logging | All requests logged | ISO 27001 A.12.4.1 |
| Change Management | Manual upload/download | ISO 27001 A.14.2.2 |
| API Key Auth | X-API-Key header (MCP) | ISO 27001 A.9.4.2 |

---

## 10. Environment Variables

```bash
# SAP CPI Configuration
SAP_CPI_DEV_URL=https://rrps-dev.integrationsuite.cfapps.eu20.hana.ondemand.com
SAP_CPI_QA_URL=https://rrps-qa.it-cpi005.cfapps.eu20.hana.ondemand.com
SAP_CPI_PROD_URL=https://rrps-prod.authentication.eu20.hana.ondemand.com

# CPI Authentication (OAuth 2.0)
SAP_CPI_CLIENT_ID=<client_id>
SAP_CPI_CLIENT_SECRET=<client_secret>
SAP_CPI_TOKEN_URL=<token_endpoint>

# SAP MS5 Configuration (via Cloud Connector)
SAP_MS5_DEFAULT_SALES_ORG=US10
SAP_MS5_DEFAULT_DIST_CHANNEL=10
SAP_MS5_DEFAULT_DIVISION=00
SAP_MS5_DEFAULT_ORDER_TYPE=ZOR
SAP_MS5_DEFAULT_CREDIT_CONTROL_AREA=US01

# MCP Server Configuration
MCP_SERVER_HOST=localhost
MCP_SERVER_PORT=8082
MCP_API_KEY=<api_key>
```

---

## 11. Usage Examples

### 11.1 Python Integration
```python
from lead_to_cash.mcp import SAPCPIMCPServer, get_sap_mcp_config

# Create and initialize server
async with SAPCPIMCPServer() as server:
    # Get opportunity from CEC
    opp = await server.call_tool("cec_get_opportunity", {
        "opportunity_id": "OPP-12345"
    })

    # Get product configuration from IPAS
    config = await server.call_tool("ipas_get_configuration", {
        "config_id": "CFG-001"
    })

    # Create order in MS5
    order = await server.call_tool("sap_create_order", {
        "customer_id": "1234",
        "sales_org": "US10",
        "items": [{"material": "MAT001", "quantity": 10}]
    })
```

### 11.2 Kaizen Agent Integration
```python
from kaizen.agents import BaseAgent
from lead_to_cash.mcp import get_sap_mcp_config

class SalesOpsAgent(BaseAgent):
    def __init__(self):
        super().__init__(
            mcp_servers=[get_sap_mcp_config()]
        )
```

---

## 12. Monitoring & Metrics

### 12.1 Prometheus Metrics
```python
# Get metrics from MCP server
server = SAPCPIMCPServer(enable_metrics=True)
metrics = server.get_prometheus_metrics()
```

### 12.2 Health Check
```python
# Check all systems via CPI
result = await server.call_tool("sap_health_check", {})
# Returns: {
#   "success": true,
#   "gateway": "SAP CPI",
#   "connected": true,
#   "systems": ["CEC", "IPAS", "MS5"]
# }
```

---

## 13. Related Documentation

- [ADR-002: CPI Gateway Architecture](../adr/002-cpi-gateway-architecture.md)
- [MCP Server Implementation](../mcp/sap_cpi_server.py)
- [CEC Client](../integrations/cec_client.py)
- [IPAS Client](../integrations/ipas_client.py)
- [MS5 Client](../integrations/ms5_client.py)
- [CPI Client](../integrations/cpi_client.py)
