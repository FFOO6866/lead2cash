# RRPS Lead-to-Cash Demo Data Guide

## Demo Customer: ST Engineering Marine Ltd

| Field | Value |
|-------|-------|
| SAP Customer ID | 0022005992 |
| Sales Order | 3228005147 |
| IPAS Order | 1207814 |
| Opportunity | Testing 1 (3000072515) |
| Order Value | EUR 62,630.00 |
| Engine | 1x MTU 8V2000M72 (720 KW @ 2100 RPM) |

## Data Sources

### Real Integrations

| Module | Endpoint | Auth |
|--------|----------|------|
| Credit Check | SAP CPI `rrps-dev.it-cpi005-rt.cfapps.eu20.hana.ondemand.com/http/Integrum/RequestTableData` | OAuth2 client_credentials |
| Opportunities | SAP CPI `rrps-dev.it-cpi005-rt.cfapps.eu20.hana.ondemand.com/http/Integrum/GetOpportunity` | OAuth2 client_credentials |
| Aravo KYP | `prod.aravo.co.uk/aems/restservices/v5.0/reports/25942819` | HTTP Basic Auth (IP-restricted to production server) |

### Simulated Data (Real SAP Document Numbers)

**Source document**: `Agentic AI - Test Data.docx` (on desktop)

#### IPAS Order — `data/ipas_xml/STE_1207814.XML`

- 1x 8V2000M72 marine propulsion engine
- 3 BOM items: engine (XM820010.00012), gearbox adapter (XM824000.00038/S), monitoring system (XM830200.00007)
- FOB SINGAPORE, payment terms Z080, classification LR (Lloyd's Register)
- Delivery 2025-06-30 (completed)

#### FinOps — `src/rrps_lead2cash/services/finops_simulator.py`

| Down Payment | Billing Doc | Amount | Financial Doc | Clearing Doc | Clearing Date | Status |
|-------------|-------------|--------|---------------|-------------|--------------|--------|
| 20% | 3851802713 | 12,526.00 | 5130025522 | 5140059754 | 2025-06-20 | CLEARED |
| 80% | 3851802753 | 50,104.00 | 5130025815 | 5140060121 | 2025-07-30 | CLEARED |

Fully paid. Zero aging. Risk: LOW.

#### Entity Registry — `src/rrps_lead2cash/services/entity_registry.py`

Resolves "ST Engineering", "STE", "ST Eng", "ST Engineering Marine", or SAP ID to customer 0022005992.

## Other Demo Customers

| Customer | SAP ID | Order Value | Status | Demo Purpose |
|----------|--------|-------------|--------|-------------|
| CLLS Power System Ltd | 0021000090 | EUR 45,000 | ON_TRACK (31,500 outstanding) | Partial payment |
| Tianjin Dingsheng | 0022005601 | EUR 5,200,000 | OVERDUE (100% outstanding) | High-risk/blocked |

## Environment Variables

| Variable | Purpose | Where Set |
|----------|---------|-----------|
| SAP_CPI_BASE_URL | CPI runtime URL | GitHub Secrets |
| SAP_CPI_TOKEN_URL | OAuth2 token endpoint | GitHub Secrets |
| SAP_CPI_CLIENT_ID | OAuth2 client ID | GitHub Secrets |
| SAP_CPI_CLIENT_SECRET | OAuth2 client secret | GitHub Secrets (MISSING) |
| ARAVO_REPORT_ID | 25942819 | GitHub Secrets |
| ARAVO_AUTH_TOKEN | Base64-encoded Basic auth | GitHub Secrets |
| ARAVO_VERIFY_SSL | false (Windows cert issue) | GitHub Secrets |
| IPAS_XML_DIR | Path to IPAS XML files | .env / deployment config |

## Key Files

| File | What |
|------|------|
| `data/ipas_xml/STE_1207814.XML` | ST Engineering IPAS order |
| `data/ipas_xml/SSZ sample.XML` | SSZ (Suzhou) sample order |
| `src/rrps_lead2cash/services/finops_simulator.py` | Billing/aging simulator |
| `src/rrps_lead2cash/services/ipas_xml_parser.py` | IPAS XML parser |
| `src/rrps_lead2cash/services/sap_cpi_client.py` | SAP CPI client (real) |
| `src/rrps_lead2cash/services/aravo_kyp_client.py` | Aravo KYP client (real) |
| `src/rrps_lead2cash/services/entity_registry.py` | Customer name resolution |
| `src/rrps_lead2cash/core/gateway.py` | FastAPI routes (22 endpoints) |
| `src/rrps_lead2cash/core/models.py` | All data models |
