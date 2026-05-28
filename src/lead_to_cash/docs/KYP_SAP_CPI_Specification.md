# KYP SAP CPI Specification

> **Version:** 1.0
> **Last Updated:** 2026-01-21
> **Purpose:** Technical specification for Know Your Partner (KYP) data retrieval from SAP via CPI

---

## 1. Overview

This specification defines the SAP CPI integration requirements for KYP (Know Your Partner) due diligence assessments. The integration retrieves customer identity and credit information from SAP S/4HANA.

### KYP Workflow

```
Step 1: Customer Search
  User provides customer name
  System calls BAPI_CUSTOMER_GETLIST
  Returns list of matching customers with ID, Name, UEN

Step 2: User Confirmation
  User selects correct customer from search results

Step 3: KYP Assessment
  System calls BAPI_CUSTOMER_GETDETAIL2 for customer details
  System calls BAPI_CR_ACC_GETDETAIL for credit information
  Returns combined KYP assessment
```

---

## 2. Data Elements

### Summary Table

| Category | Data Element | SAP Field | SAP Table | BAPI |
|----------|--------------|-----------|-----------|------|
| Customer Details | Customer Name | NAME1 | KNA1 | BAPI_CUSTOMER_GETDETAIL2 |
| Customer Details | Customer ID | KUNNR | KNA1 | BAPI_CUSTOMER_GETDETAIL2 |
| Customer Details | UEN / Tax ID 1 | STCD1 | KNA1 | BAPI_CUSTOMER_GETDETAIL2 |
| Customer Details | Tax ID 2 | STCD2 | KNA1 | BAPI_CUSTOMER_GETDETAIL2 |
| Credit Information | Approved Credit Limit | KLIMK | KNKK | BAPI_CR_ACC_GETDETAIL |
| Credit Information | Credit Exposure | SKFOR | KNKK | BAPI_CR_ACC_GETDETAIL |
| Credit Information | Available Credit | Calculated | - | KLIMK - SKFOR |
| Credit Information | Credit Utilization % | Calculated | - | (SKFOR / KLIMK) * 100 |

---

## 3. BAPI Specifications

### 3.1 BAPI_CUSTOMER_GETLIST (Customer Search)

**Purpose:** Search customers by name for KYP lookup

**CPI iFlow:** CustomerGetList

**Input Parameters:**

| Parameter | Type | Description | Example |
|-----------|------|-------------|---------|
| MAXROWS | Integer | Maximum results to return | 50 |
| NAMERANGE | Table | Name search pattern | See below |
| COUNTRYRANGE | Table | Country filter (optional) | See below |

**NAMERANGE Structure:**

| Field | Value | Description |
|-------|-------|-------------|
| SIGN | I | Include |
| OPTION | CP | Contains Pattern |
| LOW | *BATAM* | Search pattern with wildcards |

**COUNTRYRANGE Structure:**

| Field | Value | Description |
|-------|-------|-------------|
| SIGN | I | Include |
| OPTION | EQ | Equals |
| LOW | SG | Country code |

**Output:**

| Structure | Field | Description |
|-----------|-------|-------------|
| ADDRESSDATA | CUSTOMER | Customer ID (KUNNR) |
| ADDRESSDATA | NAME | Customer name (NAME1) |
| ADDRESSDATA | STCD1 | Tax number 1 (UEN) |
| ADDRESSDATA | STCD2 | Tax number 2 |
| ADDRESSDATA | COUNTRY | Country code |
| ADDRESSDATA | CITY | City |

---

### 3.2 BAPI_CUSTOMER_GETDETAIL2 (Customer Details)

**Purpose:** Get customer master data including UEN/Tax ID

**CPI iFlow:** CustomerGetDetail

**Input Parameters:**

| Parameter | Type | Description | Example |
|-----------|------|-------------|---------|
| CUSTOMERNO | CHAR(10) | Customer number, zero-padded | 0000100001 |

**Output:**

| Structure | Field | Description |
|-----------|-------|-------------|
| CUSTOMERADDRESS | NAME1 | Customer name |
| CUSTOMERADDRESS | STREET | Street address |
| CUSTOMERADDRESS | CITY1 | City |
| CUSTOMERADDRESS | POST_CODE1 | Postal code |
| CUSTOMERADDRESS | COUNTRY | Country code |
| CUSTOMERADDRESS | STCD1 | Tax number 1 (UEN for Singapore) |
| CUSTOMERADDRESS | STCD2 | Tax number 2 |
| CUSTOMERADDRESS | TEL1_NUMBR | Telephone |
| CUSTOMERADDRESS | E_MAIL | Email |
| CUSTOMERGENERALDETAIL | CUSTOMER | Customer ID |

---

### 3.3 BAPI_CR_ACC_GETDETAIL (Credit Information)

**Purpose:** Get credit limit and exposure for risk assessment

**CPI iFlow:** CreditGetAccount

**Input Parameters:**

| Parameter | Type | Description | Example |
|-----------|------|-------------|---------|
| CUSTOMER | CHAR(10) | Customer number, zero-padded | 0000100001 |
| CREDITCONTROLAREA | CHAR(4) | Credit control area | 1000 |

**Output:**

| Field | Type | Description |
|-------|------|-------------|
| CREDIT_LIMIT | Currency | Approved credit limit (KLIMK) |
| CREDIT_EXPOSURE | Currency | Current exposure (SKFOR + SAUFT) |

---

## 4. MCP Tools

### 4.1 sap_search_customers

**Purpose:** Search customers by name for KYP lookup

**Parameters:**

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| name | string | Yes | Customer name to search (supports wildcards) |
| max_results | integer | No | Maximum results (default: 50) |
| country | string | No | Country code filter |

**Response:**

```json
{
  "success": true,
  "count": 2,
  "customers": [
    {
      "customer_id": "100001",
      "name": "Batam Fast Ferry Pte. Ltd.",
      "tax_number_1": "199901234A",
      "tax_number_2": "",
      "country": "SG",
      "city": "Singapore"
    }
  ]
}
```

---

### 4.2 sap_get_customer

**Purpose:** Get customer details including UEN/Tax ID

**Parameters:**

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| customer_id | string | Yes | SAP customer number |

**Response:**

```json
{
  "success": true,
  "customer_id": "100001",
  "name": "Batam Fast Ferry Pte. Ltd.",
  "tax_number_1": "199901234A",
  "tax_number_2": "",
  "address": {
    "street": "1 Harbour Front Place",
    "city": "Singapore",
    "postal_code": "098633",
    "country": "SG"
  },
  "contact": {
    "telephone": "+65 6270 2228",
    "email": "operations@batamfast.com.sg"
  }
}
```

---

### 4.3 sap_check_credit

**Purpose:** Get credit limit and exposure

**Parameters:**

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| customer_id | string | Yes | SAP customer number |
| credit_control_area | string | No | Credit control area |

**Response:**

```json
{
  "success": true,
  "customer_id": "100001",
  "credit_control_area": "1000",
  "credit_limit": 500000.00,
  "credit_exposure": 395000.00,
  "available_credit": 105000.00,
  "credit_check_passed": true,
  "utilization_percent": 79.0
}
```

---

### 4.4 sap_get_kyp_assessment

**Purpose:** Combined KYP assessment (customer details + credit)

**Parameters:**

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| customer_id | string | Yes | SAP customer number |
| credit_control_area | string | No | Credit control area |

**Response:**

```json
{
  "success": true,
  "customer_id": "100001",
  "customer_name": "Batam Fast Ferry Pte. Ltd.",
  "tax_number_1": "199901234A",
  "tax_number_2": "",
  "credit_limit": 500000.00,
  "credit_exposure": 395000.00,
  "available_credit": 105000.00,
  "utilization_percent": 79.0,
  "currency": "SGD",
  "country": "SG",
  "city": "Singapore"
}
```

---

## 5. CPI iFlow Requirements

### Existing iFlows (No Changes Required)

| iFlow | BAPI | Status |
|-------|------|--------|
| CreditGetAccount | BAPI_CR_ACC_GETDETAIL | Ready |

### iFlows Requiring Update

| iFlow | BAPI | Change Required |
|-------|------|-----------------|
| CustomerGetDetail | BAPI_CUSTOMER_GETDETAIL2 | Add STCD1, STCD2 to response |

### New iFlow Required

| iFlow | BAPI | Description |
|-------|------|-------------|
| CustomerGetList | BAPI_CUSTOMER_GETLIST | Customer search for KYP |

---

## 6. Implementation Status

| Component | Status |
|-----------|--------|
| MS5Client.search_customers() | Implemented |
| MS5Client.get_customer() with UEN | Implemented |
| MS5Client.get_kyp_assessment() | Implemented |
| sap_search_customers MCP tool | Implemented |
| sap_get_customer MCP tool (with UEN) | Implemented |
| sap_get_kyp_assessment MCP tool | Implemented |
| CPI Simulator support | Implemented |
| CustomerGetList CPI iFlow | Pending RRPS |
| STCD1/STCD2 in CustomerGetDetail | Pending RRPS |

---

## 7. Request to RRPS

Please provide or confirm the following:

1. **New iFlow: CustomerGetList**
   - Implement BAPI_CUSTOMER_GETLIST
   - Return ADDRESSDATA with CUSTOMER, NAME, STCD1, STCD2, COUNTRY, CITY

2. **Update iFlow: CustomerGetDetail**
   - Confirm STCD1 and STCD2 fields are included in response
   - These are in CUSTOMERADDRESS structure from BAPI_CUSTOMER_GETDETAIL2

---

## 8. Testing

The CPI Simulator (`cpi_simulator.py`) supports all KYP operations for testing without SAP connectivity:

```python
from lead_to_cash.integrations.cpi_simulator import CPISimulator
from lead_to_cash.integrations.ms5_client import MS5Client

# Use simulator instead of real CPI
simulator = CPISimulator()
ms5 = MS5Client(cpi_client=simulator)

async with ms5:
    # Search customers
    results = await ms5.search_customers("Batam")

    # Get KYP assessment
    kyp = await ms5.get_kyp_assessment("100001")
```

Test customers available in simulator:
- 0000100001: Batam Fast Ferry Pte. Ltd. (Singapore, UEN: 199901234A)
- 0000100002: A.P. Moller - Maersk A/S (Denmark, CVR: 25505933)
- 0022005992: ST Engineering Ltd (Singapore, UEN: 199706231H) - Credit: 100k, 0% utilization
