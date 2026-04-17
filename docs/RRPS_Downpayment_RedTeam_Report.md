# Red Team Report: Downpayment Interface Specification v1.0

**Date:** 2026-04-16
**Subject:** RRPS_Downpayment_Interface_Specification.md
**Scope:** Scenario coverage, production codebase alignment, data model consistency, gap analysis

---

## Executive Summary

The specification covers all 15 client-provided sales orders and correctly categorises them into 6 scenario types. However, the red team review identified **7 critical gaps**, **5 consistency issues** with the existing production codebase, and **4 enhancement opportunities**. Each is detailed below with remediation.

**Verdict:** Specification is **85% complete**. The gaps below must be addressed before client handover.

---

## 1. SCENARIO COVERAGE AUDIT

### 1.1 All 15 Cases Accounted For -- PASS

| # | Sales Order | Category in Spec | Verified |
|---|---|---|---|
| 1 | 3228005113 | B (Multi-Milestone) | YES |
| 2 | 3228005124 | B + F (Multi-Milestone + Terms Changed) | YES |
| 3 | 3228005142 | D + F (Multi-Instrument + Terms Changed) | YES |
| 4 | 3228005143 | A (Simple DP + Balance) | YES |
| 5 | 3228005147 | A (Simple DP + Balance) | YES |
| 6 | 3228005168 | B (Multi-Milestone) | YES |
| 7 | 3228005171 | C (Complex Progress) | YES |
| 8 | 3228005185 | A (Simple DP + Balance) | YES |
| 9 | 3228005208 | C (Complex Progress) | YES |
| 10 | 3228005221 | A (Simple DP + Balance) | YES |
| 11 | 3228005227 | D (Multi-Instrument) | YES |
| 12 | 3228005230 | B (Multi-Milestone) | YES |
| 13 | 3228005242 | A (Simple DP + Balance) | YES |
| 14 | 3228005268 | A (Simple DP + Balance) | YES |
| 15 | 3228004906 | E (Large Contract) | YES |

### 1.2 Missing Sub-Scenarios -- CRITICAL GAPS FOUND

#### GAP-01: Invoice Cancellation & Replacement (CRITICAL)

**Source:** Order 3228005124 (screenshots image10.png, image11.png)

**What was missed:** The document flow for pos 30 and pos 40 shows:
```
E:Proforma     3868003794  30  25.09.2025
E: Invoice     3818015386  30  26.11.2025
E:Invoice Cancell.  3891800429  30  26.11.2025   <-- MISSED
E: Invoice     3818015387  30  26.11.2025   <-- replacement
```

The spec mentions credit memos (S1) but does NOT cover **invoice cancellation** (document type 3891xxxxxx, likely FKART=S1 or ZS1). This is a distinct document in the flow where an invoice is cancelled on the same day and a replacement is issued. The agent must:
- Detect cancelled invoices (VBRK-FKSTO = 'X' or FKART = cancellation type)
- Exclude cancelled invoices from receivables tracking
- Link cancelled invoices to their replacements
- Track the NET of cancellation + replacement for correct outstanding calculation

**Impact:** Without this, the agent would double-count invoices (original + replacement) and show incorrect receivables.

**Remediation:** Add Section 7.11 "Invoice Cancellation & Replacement Handling" and add number range 3891xxxxxx to Section 4.1.

---

#### GAP-02: Purchase Requisition in Document Flow (CRITICAL)

**Source:** Order 3228005124 (screenshots image10.png, image11.png)

**What was missed:** The document flow shows:
```
Purch. requisition  2480034805  20  03.09.2025   <-- MISSED
Purchase Order      2800009761  20  24.09.2025
Invoice receipt     1802096434  1   25.11.2025
```

The spec covers Purchase Order (EKKO) and Invoice Receipt (RBKP) but completely omits the **Purchase Requisition** (BANF, table EBAN, number range 2480xxxxxx). The full procurement chain is:

```
Sales Order (VBAK) --> Purchase Requisition (EBAN) --> Purchase Order (EKKO) --> Invoice Receipt (RBKP)
```

**Impact:** The agent cannot trace the full procurement lifecycle. For orders where the customer invoice is triggered by vendor supply chain events, missing the purchase requisition means the agent cannot provide early warning of procurement delays.

**Remediation:**
- Add EBAN/BANF to Section 4.1 document number ranges
- Add VBTYP_N code for purchase requisition to Section 6.6
- Consider new iFlow `MS5GetPurchaseRequisition` (Priority P3)

---

#### GAP-03: Billing Block Codes Not Specified (HIGH)

**Source:** Order 3228005142 (screenshot image15.png)

**What was missed:** The screenshots show explicit billing block codes:
```
Pos 12: mtu SCR       -- Billing block: 01 Block for billing
Pos 13: mtu LOP       -- Billing block: 01 Block for billing
Pos 14: Software       -- Billing block: 01 Block for billing
Pos 20: Final payment  -- Billing block: 01 Block for billing (but DP 3851802696 created against this!)
```

The spec mentions `FAKSP` (billing block) at the billing plan level but does NOT specify:
- The actual block code values used by RRPS (01 = "Block for billing")
- That a DP can be created **even when the billing block is active** on the line item (as shown by pos 20 having both a block AND a DP document)
- That the billing block is at the **item level** (VBUP-FKSAA), not just the billing plan level

**Impact:** The agent may incorrectly assume a billing-blocked item has no DP activity.

**Remediation:** Add billing block code table:
| Code | Description | Agent Behaviour |
|---|---|---|
| 01 | Block for billing | Item blocked -- but DP may still exist if created before block |
| 02 | Block for delivery | Delivery blocked -- DP unaffected |
| (blank) | No block | Normal billing |

---

#### GAP-04: DP Against "Final Payment" Line Items (HIGH)

**Source:** Order 3228005142 (screenshot image15.png)

**What was missed:** Pos 20 is described as "Final payment, 45 days after SAT" (material ACC_V4000, item category ZEX2), and it has a billing block AND a DP document (3851802696). This means:
- A DP can be created against a line item that represents the FINAL payment, not just engine items
- The DP is essentially a partial advance against a future milestone payment
- The DP amount is a fraction of the final payment amount, not a percentage of the order

This is a **semantically different** DP pattern: the DP is not "advance against order" but "advance against specific future milestone". The spec's categories don't cleanly capture this.

**Remediation:** Add a note to Category D clarifying that DPs can be raised against ANY line item including service/final-payment items, and that the billing type (FAZ) determines DP status regardless of what the line item represents.

---

#### GAP-05: SoF Validity Period and DMS Attachments (MEDIUM)

**Source:** Orders 3228005124 and 3228005143 (screenshots image7.png, image17.png)

**What was missed:** The SoF documents show:
- **Validity period**: "13.02.2025-11.03.2025" (order 3228005124), "30.04.2025-25.05.2025" (order 3228005143)
- **DMS attachments**: SOF PDF, PO.pdf, OrderConfirmation.pdf, costing sheet (stored in Z_S1DMS and DMS_C1_ST storage categories)

The spec captures the first SoF date but not the validity end date. An expired SoF may need re-approval before the DP can be issued.

**Remediation:**
- Add SoF validity end date to the NAST/DMS data retrieval
- Add note that if SoF is expired (current date > validity end), the agent should flag "SoF expired -- re-approval may be required"
- Consider iFlow for DMS document retrieval (lower priority)

---

#### GAP-06: Variation Order (VO) Handling (MEDIUM)

**Source:** Order 3228004906

**What was missed:** The order has "Rev.2, 1st VO: 100% T/T of Eur 184,000". A Variation Order changes the contract value and may add entirely new payment terms for the variation scope. The spec mentions this in the case table but does not define:
- How to detect a VO (order version change, new items added mid-lifecycle)
- How the VO amount integrates with existing billing plan
- Whether the VO gets its own DP or is billed separately

**Remediation:** Add Section 7.12 "Variation Order Detection" covering VBAK version tracking and additional billing plan lines created for VO scope.

---

#### GAP-07: DP Invoice Delay Root-Cause Analysis (MEDIUM)

**Source:** Orders 3228005142 and 3228005221

**What was missed:** The client explicitly flagged:
- Order 3228005142: "SOF was first approved in March, but DP invoice issued in May. Why? There is a Bank guarantee behind this."
- Order 3228005221: "Why did this one take so long until the first DP invoice as first SoF approval is 15.10.25?"

The spec captures BG gating as a concept but does NOT define an explicit **delay analysis** capability. The agent should be able to:
- Calculate expected DP date (trigger event date + offset)
- Compare with actual DP document date (VBRK-FKDAT)
- Compute delay = actual - expected
- If delay > threshold: flag and attempt root-cause (BG pending? billing block? SoF expired?)

**Remediation:** Add Section 7.13 "DP Invoice Delay Analysis" with delay calculation logic and root-cause decision tree.

---

## 2. PRODUCTION CODEBASE ALIGNMENT

### 2.1 FinOps Model Status Enum Mismatch -- CRITICAL

**Current production** (`finops_simulator.py` line 39):
```python
status: str = Field(default="OPEN", description="CLEARED, OPEN, or OVERDUE")
```

**Spec proposes** (Section 9.1):
```python
class DPDocumentStatus(str, Enum):
    REQUESTED = "REQUESTED"
    PAID = "PAID"
    PARTIALLY_PAID = "PARTIALLY_PAID"
    OVERDUE = "OVERDUE"
    CANCELLED = "CANCELLED"
    BLOCKED = "BLOCKED"
```

**Problem:** The status values don't match. `CLEARED` (production) maps to `PAID` (spec). `OPEN` (production) maps to `REQUESTED` (spec). Any new code using the spec's enum will be inconsistent with existing demo data.

**Remediation:** Define explicit mapping in the spec:
| Production (Current) | Spec (New) | Meaning |
|---|---|---|
| OPEN | REQUESTED | DP created, not yet paid |
| CLEARED | PAID | FI document cleared |
| OVERDUE | OVERDUE | Past due, not cleared |
| -- | PARTIALLY_PAID | New: partial clearing |
| -- | CANCELLED | New: VBRK-FKSTO = 'X' |
| -- | BLOCKED | New: billing block active |

Implement backwards-compatible mapping in `FinOpsDataService` that translates between old and new enum values.

---

### 2.2 Agent Naming Inconsistency -- HIGH

**BAPI template document** (Section 7.8): Defines a single `BillingCollectionsAgent` with capabilities including `downpayment_tracking`.

**Spec** (Section 1): Introduces a SEPARATE `DownpaymentTrackingAgent` alongside `BillingCollectionsAgent`.

**Problem:** The BAPI template doc treats downpayment tracking as a CAPABILITY of BillingCollectionsAgent. The spec introduces it as a separate agent. This creates confusion about which agent owns the downpayment domain.

**Remediation:** Align with the BAPI template. Downpayment tracking should be a **capability** within `BillingCollectionsAgent`, NOT a separate agent. Update Section 1 architecture diagram:
```
BillingCollectionsAgent (Kaizen BaseAgent, domain: accounts_receivable)
  ├── billing_tracking (existing)
  ├── collections_monitoring (existing)
  ├── payment_terms_analysis (existing)
  ├── aging_analysis (existing)
  └── downpayment_tracking (NEW - from this spec)
```

---

### 2.3 Missing Gateway API Endpoints -- HIGH

**Current production** (`gateway.py`): Has routes for `/api/v1/finops/billing/{sales_order}`, `/api/v1/finops/aging/{customer_id}`, `/api/v1/finops/summary/{customer_id}`.

**Spec**: Defines 11 CPI iFlows but does NOT define corresponding new API endpoints in the gateway.

**Problem:** The spec stops at "CPI gives us data" but doesn't show how the gateway exposes this to the dashboard/agents.

**Remediation:** Add new gateway endpoints:
```
GET  /api/v1/finops/downpayment/{sales_order}        --> DownpaymentSummary
GET  /api/v1/finops/billing-plan/{sales_order}        --> DownpaymentPlan
GET  /api/v1/finops/document-flow/{sales_order}       --> List[DocumentFlowEntry]
GET  /api/v1/finops/dp-status/{billing_doc}           --> DownpaymentRequest + clearing
GET  /api/v1/finops/vendor-invoice/{sales_order}      --> List[VendorInvoiceReceipt]
```

---

### 2.4 IPAS billing_plan_rel Not Connected -- MEDIUM

**Current production** (`models.py` line 207):
```python
billing_plan_rel: str = Field(default="", description="Billing plan relevance (X=yes)")
```

**Problem:** The IPAS model already has a `billing_plan_rel` flag that indicates whether an order requires a billing plan. The spec's trigger logic does not reference this field. When `billing_plan_rel == "X"`, the agent should automatically expect billing plan data and begin DP tracking.

**Remediation:** Add to Section 3 trigger logic:
```
Pre-condition check: IPAS Header.billing_plan_rel == "X"
  If YES --> Order has billing plan --> activate DP tracking
  If NO  --> No billing plan --> skip DP monitoring
```

---

### 2.5 Existing FinOps Demo Data Uses Real Case (3228005147) -- MEDIUM

**Current production** (`finops_simulator.py` lines 97-138): Uses sales order 3228005147 (ST Engineering) as demo data with DP docs 3851802713 and 3851802753.

**The spec** also references this exact order as a Category A case.

**Good news:** The data is CONSISTENT -- the spec's analysis matches the demo data.

**Issue:** The spec shows the order value as "1.000 UNT" in the status overview, but the simulator has `order_value=62630.00`. The screenshots from the SAP document flow show the DP amounts as EUR 12,526 (20%) and EUR 50,104 (80%), which matches the simulator but NOT the billing plan total shown in the SAP screenshots (DIESEL ENGINE, 1.000 UNT). This suggests the demo data is for a SUBSET of the order (single engine), not the full order. This is fine for demo purposes but should be noted.

**Remediation:** No action needed -- just acknowledge that simulator represents a single-item subset.

---

## 3. MISSING FROM THE SPEC

### 3.1 ZTERM Payment Terms Code Lookup Table -- HIGH

The spec references payment terms codes (A000, ZR11) but does NOT provide a lookup table mapping ZTERM codes to their text descriptions. This is CRITICAL for the `PaymentTermsHarmonizer` referenced in the BAPI template.

**Known codes from the 15 cases:**
| ZTERM | Description | Source Order |
|---|---|---|
| A000 | As per contract | 3228005143, 3228005147, 3228005185, 3228005242 |
| ZR11 | 30% adv. TT, 70% by LC at sight | 3228005227 |
| Z030 | Net 30 days | (from BAPI template) |

**Remediation:** Request full ZTERM table from client (T052 / T052U tables in SAP) and add as appendix.

---

### 3.2 Client's Explicit "Unknown" Questions Not Captured -- HIGH

The client document contains explicit uncertainty markers that the spec should capture as **known limitations requiring human-in-the-loop**:

| Order | Client Question | Spec Coverage | Gap |
|---|---|---|---|
| 3228005113 | "10% 90 days before FCA within 30days -- ???" | Trigger #5 (N days before FCA) at MEDIUM confidence | OK but should acknowledge the client's own confusion about this rule |
| 3228005168 | "how would I know this is when?" (drawings submission) | Trigger #7 at LOW confidence | OK but should add explicit "MANUAL_CONFIRMATION_REQUIRED" flag |
| 3228005227 | "How do I know when is contract signed? This must be managed manually outside the system no?" | Trigger #6 at LOW confidence | OK but should explicitly confirm the client's assumption -- YES, this is manual |
| 3228005221 | "Why did this one take so long until the first DP invoice as first SoF approval is 15.10.25?" | NOT covered | GAP -- need delay analysis (see GAP-07) |
| 3228005208 | "I think the document 3868003805 is printed really as proforma and not for collection purposes" | Section 7.7 covers proforma differentiation | OK |

**Remediation:** Add a "Known Limitations & Human-in-the-Loop" section explicitly confirming which triggers CANNOT be automated and require manual confirmation from the operations team.

---

### 3.3 Multi-Currency Handling -- MEDIUM

**Observed currencies:**
- EUR: 13 of 15 orders
- SGD: 1 order (3228005208, SGD 16,900,000.00)
- CNY: potential (from IPAS XML currency code)

The spec captures currency as a field but does not address:
- FX conversion for aging analysis when mixing EUR/SGD/CNY
- Document currency vs local currency (BSEG-WRBTR vs BSEG-DMBTR)
- Whether the agent should convert to a common reporting currency

**Remediation:** Add note to Section 6.4 clarifying that the agent should track both document currency (WAERK/WRBTR) and local currency (DMBTR), and flag multi-currency orders in the DownpaymentSummary.

---

### 3.4 Proforma Billing Type Verification -- LOW

The spec assumes proforma FKART = `ZF2P`. The screenshots show proformas in the 3868xxxxxx range with document flow label "E:Proforma". The actual FKART may be `F5`, `F8`, or a Z-custom type.

**Remediation:** Request FKART mapping table from client (TVFK table in SAP). For now, detect proforma by number range (3868xxxxxx) as fallback.

---

## 4. CONSISTENCY WITH BAPI TEMPLATE DOCUMENT

### 4.1 Section 7 Alignment Check

| BAPI Template Section | Spec Coverage | Status |
|---|---|---|
| 7.1 Post-Order Payment Flow Overview | Section 1 Architecture + Section 4 Posting Patterns | ALIGNED |
| 7.2 BAPIs for SO Status & Billing Plan | Section 5.2 | ALIGNED |
| 7.3 BAPIs for Billing Doc & DP Retrieval | Section 5.1, 5.3 | ALIGNED |
| 7.4 Billing Plan Fields (FPLT/FPLTR) | Section 6.1, 6.2 | ALIGNED -- spec adds more fields |
| 7.5 Billing Document Fields | Section 6.3 | ALIGNED |
| 7.6 Downpayment Request Tracking | Section 6.3, 6.4 | ALIGNED -- spec adds clearing logic |
| 7.7 Payment Milestone Mapping | Section 6.2, Section 10 | ALIGNED |
| 7.8 Integration with BillingCollectionsAgent | **MISALIGNED** -- spec creates separate agent | **FIX NEEDED** (see 2.2) |
| CPI iFlow Configuration | Section 8 | ALIGNED -- spec adds 6 more iFlows |

### 4.2 Trigger Event Mapping Consistency

| BAPI Template (Section 7.7) | Spec Trigger Event | Status |
|---|---|---|
| ORDER_PLACEMENT | ORDER_PLACEMENT | ALIGNED |
| BEFORE_SHIPMENT | BEFORE_SHIPMENT, BEFORE_EXW | ALIGNED (spec splits EXW out) |
| FAT | FAT | ALIGNED |
| SAT | SAT | ALIGNED |
| NOR | NOR | ALIGNED |
| DELIVERY | DELIVERY | ALIGNED |
| COMMISSIONING | COMMISSIONING | ALIGNED |
| DRAWING_DELIVERY | DRAWINGS_SUBMISSION | ALIGNED (renamed) |
| CONTRACT_SIGNING | CONTRACT_SIGNING | ALIGNED |
| -- | SOF_APPROVAL | **NEW** -- not in BAPI template |
| -- | ORDER_CONFIRMATION | **NEW** -- not in BAPI template |
| -- | DAYS_AFTER_FIRST_PAYMENT | **NEW** -- not in BAPI template |
| -- | VENDOR_INVOICE_RECEIPT | **NEW** -- not in BAPI template |
| -- | BG_RECEIPT | **NEW** -- not in BAPI template |
| -- | MONTHS_AFTER_DELIVERY | **NEW** -- not in BAPI template |
| -- | SPECIFIC_DATE | **NEW** -- not in BAPI template |
| -- | PO_RECEIPT | **NEW** -- not in BAPI template |
| -- | BEFORE_FCA | **NEW** -- not in BAPI template |
| -- | EQUIPMENT_ARRIVAL | **NEW** -- not in BAPI template |
| -- | INSTALLATION_COMPLETE | **NEW** -- not in BAPI template |
| -- | FINAL_ACCEPTANCE | **NEW** -- not in BAPI template |

The spec correctly **extends** the BAPI template's 9 trigger events to 17. The new triggers are all derived from the 15 production cases. This is the right approach -- the BAPI template had a generic set; the spec is RRPS-specific.

---

## 5. REMEDIATION PRIORITY MATRIX

| # | Gap | Severity | Effort | Priority |
|---|---|---|---|---|
| GAP-01 | Invoice Cancellation handling | CRITICAL | Medium | P0 |
| GAP-02 | Purchase Requisition in flow | CRITICAL | Low | P0 |
| 2.1 | Status enum mismatch | CRITICAL | Low | P0 |
| 2.2 | Agent naming (separate vs capability) | HIGH | Low | P0 |
| 2.3 | Missing gateway endpoints | HIGH | Medium | P1 |
| 3.1 | ZTERM lookup table | HIGH | Low (client provides) | P1 |
| 3.2 | Known limitations section | HIGH | Low | P1 |
| GAP-03 | Billing block codes | HIGH | Low | P1 |
| GAP-04 | DP against final-payment items | HIGH | Low | P1 |
| GAP-05 | SoF validity period | MEDIUM | Low | P2 |
| GAP-06 | Variation Order handling | MEDIUM | Medium | P2 |
| GAP-07 | DP delay analysis | MEDIUM | Medium | P2 |
| 2.4 | IPAS billing_plan_rel linkage | MEDIUM | Low | P2 |
| 3.3 | Multi-currency handling | MEDIUM | Low | P2 |
| 3.4 | Proforma FKART verification | LOW | Low (client confirms) | P3 |

---

## 6. POSITIVE FINDINGS

Things the spec got RIGHT:

1. **All 15 cases categorised correctly** -- no mis-classification
2. **6 categories are comprehensive** -- every observed pattern fits into one (or combination) of the categories
3. **17 trigger events cover all observed patterns** -- including edge cases like "N days after first payment" and "vendor invoice receipt"
4. **Confidence levels (HIGH/MEDIUM/LOW)** correctly reflect SAP data availability
5. **Field mappings are accurate** -- SAP table/field references match actual SAP screenshot data (VBAP entries, VBRP entries, VBFA flows)
6. **Real document numbers used as examples** -- all examples (3851xxxxxx, 3818xxxxxx, etc.) come from actual screenshots
7. **Position replacement logic** correctly identifies the material-change scenario
8. **Proforma differentiation** correctly distinguishes 3868xxxxxx from 3851xxxxxx
9. **CPI iFlow priority ranking** is sensible -- billing plan and document flow are P0
10. **Data model extensions** are compatible with existing Pydantic patterns in `models.py`
11. **Agent pseudocode** is implementable and references correct SAP objects
12. **The spec correctly identifies BG tracking as external** -- SAP standard SD does not store BG data

---

## 7. ITEMS REQUIRING CLIENT CONFIRMATION

Before finalising the spec, the following must be confirmed with the RRPS client tech team:

| # | Question | Why It Matters |
|---|---|---|
| 1 | What is the FKART code for proforma invoices? (F5, F8, ZF2P, or other?) | Correct differentiation of proforma vs collection |
| 2 | What is the FKART code for invoice cancellation? (S1, ZS1, or other?) | Invoice cancellation handling |
| 3 | Is RFC_READ_TABLE permitted on production MS5, or must NAST be wrapped in a custom FM? | SoF/ZEOR date retrieval iFlow design |
| 4 | Does RRPS store Bank Guarantee data in SAP TRM module? | Determines if BG iFlow is feasible or manual-only |
| 5 | Which Z-tables/custom structures hold FAT/SAT/NOR confirmation dates? | Milestone trigger date derivation |
| 6 | Can the client provide the full T052/T052U (ZTERM) table dump? | PaymentTermsHarmonizer training data |
| 7 | What are all billing block codes used? (01 confirmed, any others?) | Billing block status interpretation |
| 8 | Is Purchase Requisition (BANF) relevant for agent monitoring, or only Purchase Order? | Scope of procurement tracking |

---

*End of Red Team Report*
