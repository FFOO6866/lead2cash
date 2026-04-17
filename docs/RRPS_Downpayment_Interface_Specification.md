# Downpayment & Payment Milestone Interface Specification

## Integrum Agentic System to SAP MS5

---

**RRPS Lead-to-Cash Agentic System**
**Document Date:** 2026-04-16
**Version:** 1.0
**Classification:** Confidential - RRPS Internal
**Author:** Integrum / Kailash AI

---

## Table of Contents

1. [Overview](#1-overview)
2. [Downpayment Scenario Taxonomy](#2-downpayment-scenario-taxonomy)
   - 2.1 Category A: Simple DP + Balance
   - 2.2 Category B: Multi-Milestone Payment Schedule
   - 2.3 Category C: Complex Progress Payments
   - 2.4 Category D: Multi-Instrument Payments (TT + LC + BG)
   - 2.5 Category E: Large-Scale Contract with Periodic DPs
   - 2.6 Category F: Mid-Order Payment Terms Change
3. [Trigger Event Derivation Logic](#3-trigger-event-derivation-logic)
4. [SAP Document Types & Posting Patterns](#4-sap-document-types--posting-patterns)
5. [BAPIs / Function Modules Required](#5-bapis--function-modules-required)
   - 5.1 Downpayment Request Retrieval
   - 5.2 Billing Plan Retrieval
   - 5.3 Billing Document Retrieval
   - 5.4 FI Clearing & Payment Status
   - 5.5 SoF / Order Confirmation Date Retrieval
   - 5.6 Purchase Order & Invoice Receipt
   - 5.7 Bank Guarantee Tracking
6. [Field Mapping: SAP to Agentic System](#6-field-mapping-sap-to-agentic-system)
   - 6.1 Billing Plan Header (FPLA)
   - 6.2 Billing Plan Date Lines (FPLT)
   - 6.3 Downpayment Request Document (VBRK/VBRP)
   - 6.4 FI Accounting Document (BKPF/BSEG)
   - 6.5 Sales Order Status (VBUK/VBUP)
   - 6.6 Document Flow (VBFA)
   - 6.7 Purchase Order Invoice Receipt (RSEG/RBKP)
7. [Agentic Scenarios: AI Agent Capabilities](#7-agentic-scenarios-ai-agent-capabilities)
   - 7.1 DP Invoice Trigger Detection
   - 7.2 Multi-Position DP Allocation Tracking
   - 7.3 Payment Terms Change Monitoring
   - 7.4 Bank Guarantee Lifecycle Tracking
   - 7.5 L/C Timing & Readiness Monitoring
   - 7.6 PSI Stage Payment Tracking
   - 7.7 Proforma vs Collection Invoice Differentiation
   - 7.8 Vendor PO Invoice Receipt Linkage
   - 7.9 Multi-SoF Version Handling
   - 7.10 DP Netting on Final Invoice
8. [CPI iFlow Specifications](#8-cpi-iflow-specifications)
9. [Data Model Extensions](#9-data-model-extensions)
10. [Agent-Derived vs SAP-Direct Fields](#10-agent-derived-vs-sap-direct-fields)
11. [Appendix: Case Reference Matrix](#11-appendix-case-reference-matrix)

---

## 1. Overview

This document defines the interface specifications for the Integrum Agentic System to read, track, and manage downpayment and payment milestone data from SAP MS5 (S/4HANA) for Rolls-Royce Power Systems (RRPS/MTU).

The source analysis is based on **15 real production sales orders** (Company Code 0011, Transaction Type ZE06, period 2025) covering the full spectrum of RRPS downpayment patterns. Downpayment tracking is a **capability** within the existing `BillingCollectionsAgent` (Kaizen BaseAgent, domain: `accounts_receivable`), consistent with the BAPI Field Mapping specification (Section 7.8). The agent consumes data retrieved by the BAPIs/FMs specified herein via the `FinOpsDataService`.

### Architecture

```
SAP MS5 (S/4HANA)
  |
  +-- VBAK/VBAP (Sales Order Header/Items)
  +-- FPLA (Billing Plan Header) / FPLT (Billing Plan Date Lines, keyed by FPLTR)
  +-- VBRK/VBRP (Billing Documents: DP Requests, Invoices, Proformas, Cancellations)
  +-- BKPF/BSEG (FI Accounting Documents & Clearing)
  +-- VBFA (Document Flow)
  +-- NAST/TNAPR (Output Records - ZEOR, ZSOV)
  +-- EBAN (Purchase Requisitions)
  +-- EKKO/EKPO (Purchase Orders)
  +-- RBKP/RSEG (Logistics Invoice Verification - MIRO)
  |
  v
SAP CPI (iFlows)  --->  Integrum Agentic System
  |                           |
  |                    BillingCollectionsAgent
  |                    (Kaizen BaseAgent, domain: accounts_receivable)
  |                      |
  |                      +-- billing_tracking (existing)
  |                      +-- collections_monitoring (existing)
  |                      +-- payment_terms_analysis (existing)
  |                      +-- downpayment_tracking (NEW - this spec)
  |                      +-- aging_analysis (existing)
  |                      |
  v                      v
               FinOpsDataService (unified data layer)
                       |
                       v
                  Dashboard / API
```

### Scope

The 15 analyzed cases reveal **6 distinct downpayment categories**, **15 trigger event types**, and **10 AI-agentic capabilities** required to fully automate downpayment monitoring. This specification covers:

- **READ operations only** -- the Agentic System is a read-only observer
- **All payment instruments** -- TT (Telegraphic Transfer), L/C (Letter of Credit), BG (Bank Guarantee)
- **All milestone types** -- Order placement, FAT, SAT, NOR, EXW, delivery, PSI stages
- **All document types** -- DP requests (FAZ), invoices (F2), proformas (ZF2P), credit memos (S1)
- **Cross-document linkage** -- Sales order -> Billing plan -> DP request -> FI clearing -> Vendor PO -> MIRO

---

## 2. Downpayment Scenario Taxonomy

Based on analysis of all 15 production cases, RRPS downpayment scenarios are classified into 6 categories.

### 2.1 Category A: Simple DP + Balance

**Pattern:** Single downpayment percentage triggered by order event, followed by balance payment before shipment/delivery.

| Reference Order | PO Reference | DP % | DP Trigger | Balance % | Balance Trigger | Payment Method |
|---|---|---|---|---|---|---|
| 3228005147 | 250303SG-R1 | 20% | SoF first approval | 80% | NOR (Notification of Readiness) | TT / TT |
| 3228005185 | PO-39.0525, PO-40.05 | 20% | Order placement | 80% | Before EXW | TT / TT + 5% BG |
| 3228005242 | 25-011/USF | 20% | 14 days upon PO receipt | 80% | LC at sight, 30 days before shipment | TT / LC |
| 3228005268 | PO-251210301 | 20% | Order placement (TT) | 80% | 45 days upon NOR (TT) | TT / TT + 10% BG |
| 3228005221 | MJ25MK-016 | 20% | 30 days upon invoice (TT) | 80% | Credit line / alt. payment terms | TT / TT or LC |

**SAP Posting Pattern:**
```
Sales Order (VBAK)
  --> Billing Plan (FPLA/FPLT): 2 date lines
       Line 1: FPFAR=FAZ, BETEFP=20, TETXT="Down Payment"
       Line 2: FPFAR=F2,  BETEFP=80, TETXT="Balance Payment"
  --> DP Request (VBRK-FKART=FAZ): 1 document per order
  --> Balance Invoice (VBRK-FKART=F2): 1 document, nets out DP
```

**Key Observations from SAP:**
- DP document flow: `E:SlsOrder` -> `E: Down Payment` (3851xxxxxx) -> `E: Invoice` (3818xxxxxx) -> `Accounting document` (5610xxxxxx, status=Cleared)
- In order 3228005147: Two DP documents created (3851802713 on 02.06.2025, 3851802753 on 16.07.2025), suggesting **split DP invoicing** even in "simple" cases
- In order 3228005185: Four DP documents across 2 line items (pos 10 and 20), each getting 2 DP docs (3851802749/3851802750 and 3851802879/3851802880)
- BG tracking is **not in SAP document flow** -- requires external tracking

**Agent Derivation Rules:**
- DP trigger date = First SoF release date (NAST output type ZSOV, first creation date)
- Alternative: Customer PO date (VBAK-BSTDK) when terms say "upon PO receipt"
- Balance trigger = Delivery schedule date (VBEP-EDATU) minus offset days

---

### 2.2 Category B: Multi-Milestone Payment Schedule

**Pattern:** 3+ payment milestones with different trigger events and percentages.

| Reference Order | PO Reference | Milestone 1 | Milestone 2 | Milestone 3 | Milestone 4 |
|---|---|---|---|---|---|
| 3228005113 | MU100628 | 10% on order confirmation (90d) | 10% 90d before FCA (30d) | 80% on FCA (90d from invoice) | -- |
| 3228005124 | M04.MTU.DP.2025 | 4.9% EUR 60,500 DP by TT on OC | 15.1% EUR 186,900 interim 60d after 1st payment | 80.2% EUR 1,001,900 by L/C 30d at sight | -- |
| 3228005168 | (no PO ref) | 10% on order placement (TT) | 10% on drawings list submission | 80% before ex-works | -- |
| 3228005230 | 4516421220 | 15% on PO receipt (30d) | 80% after FAT (30d) | 5% after customer receipt (30d) | -- |
| 3228005227 | FFX-III-MF-2 | 30% by TT within 30d from contract signing + counter guarantee | 70% by irrevocable L/C, 6 weeks before shipment | -- | -- |

**SAP Posting Pattern:**
```
Sales Order (VBAK)
  --> Billing Plan (FPLA/FPLT): 3-4 date lines
       Line 1: FPFAR=FAZ, BETEFP=10-30%, TETXT="Down Payment / Advance"
       Line 2: FPFAR=FAZ, BETEFP=10-15%, TETXT="Interim Payment / 2nd Milestone"
       Line 3: FPFAR=F2,  BETEFP=70-80%, TETXT="Balance / Final Payment"
       [Line 4: FPFAR=F2,  BETEFP=5%,    TETXT="Final Payment 2" (if applicable)]
  --> Multiple DP Requests: 1 FAZ document per milestone
  --> Final Invoice: Nets out all prior DP documents
```

**Key Observations from SAP:**
- Order 3228005113: Shows 4 line items (pos 10/20/30/40) with DP docs 3851802644 and 3851802645 against pos 10, and separate DPs against pos 30/40. Invoice 3818015313 is the final. Invoice receipt 1802074183 from vendor PO 2800009744.
- Order 3228005124: **Cryptic position management** -- pos 10/20 created first as backlog locks, then pos 30/40 created later with proper material numbers. AI must detect position replacement and redirect monitoring from pos 10/20 to pos 30/40.
- Order 3228005168: 3 identical positions (pos 10/20/30, material 16V2000M72, EUR 830,000 each). Each position has its own chain of 3 DP docs + 1 invoice + 1 accounting doc. Total 9 DP documents for the order.
- Order 3228005230: **2 SoF approvals** -- first version determines DP invoice date, not the second.

**Agent Derivation Rules:**
- Interim payment trigger = Detect clearing status of first DP document (BSEG-AUGDT populated) + add offset days
- Drawings submission = Manual/unknown trigger -- flag for human intervention
- Contract signing date = Not in SAP -- requires external input or manual override
- FAT date = From quality notification or milestone confirmation (custom Z-table or NAST)

---

### 2.3 Category C: Complex Progress Payments

**Pattern:** Multiple progress-based payments prorated across individual units/phases, with acceptance-based triggers.

| Reference Order | PO Reference | Structure |
|---|---|---|
| 3228005208 | 4500069874 | 15% advance (BG+TT) + 50% on equipment arrival (prorated per DUPS) + 25% on installation (or 9m after FAT) + 5% on SAT (or 12m after FAT) + 5% on Final Acceptance (or Feb 2027) |
| 3228005171 | PO 3450000475-480 | DP per PO amount (TT) + Balance (LC) + PSI stages 30%/40%/30% (TT, 15 days) |

**SAP Posting Pattern (3228005208):**
```
Sales Order (VBAK): Net value SGD 16,900,000.00
  Line Items:
    Pos 10: KP16V4000B2E (mtu KP7 630/2500 16V4) - 6.00 UNT - SGD 10,984,999.98
    Pos 20: SERV_V4000   (75% Progress Payment)  - 1 LOT   - SGD 4,225,000.02
    Pos 30: SERV_V4000   (5% LC 30 days)         - 1 LOT   -
    Pos 40: SERV_V4000   (5% LC 30 days)         - 1 LOT   -
  --> DP Request 3851802837: 15% advance (against pos 10)
  --> Proforma 3868003805: printed as proforma, NOT for collection
  --> Progress invoices: prorated per individual DUPS unit delivery
```

**SAP Posting Pattern (3228005171):**
```
Sales Order (VBAK): 6 engines with accessories + PSI phases
  16 Line Items (VBAP):
    Pos 10/20/30/40/50/60: 20V8000M71L (DIESEL ENGINE Y16401-Y16406) - 2 ST each
    Pos 11/21/31/41/51/61: ACCESSORIES (BINDING DRAWING Y16401-Y16406) - 1 SET each
    Pos 12/13/14: ACC_V8000_DIRECT (PSI Phase 1/2/3) - 1 LOT each
  --> 12 DP billing documents (3851802721-3851802742): one per engine + one per accessories
  --> DP invoices contain FRACTIONAL amounts of original line item values
  --> PSI payments: staged 30%/40%/30% against work completion certificates
```

**Key Observations from SAP:**
- VBRP (billing doc items) shows 12 entries for order 3228005171: each engine position (pos 10,20,30,40,50,60,62) gets a separate billing doc, and each ACCESSORIES position (pos 11,21,31,41,51,61) gets a separate billing doc
- Net values in VBRP are fractional: e.g., pos 10 engine = 485,158.88 ST (vs full order item value of 3,826,356.03), pos 11 accessories = 485,158.88 LOT
- PSI items (ACC_V8000_DIRECT, pos 12/13/14) have item category ZEX2, billed separately against work completion
- Purchase Order 2800009810 has 9 line items spanning delivery dates from 06.2026 to 11.2027

**Agent Derivation Rules:**
- Prorated amounts = Total milestone % x individual unit proportion
- "Or N months after FAT, whichever earlier" = Agent must track both dates and use minimum
- PSI stage completion = Requires external work completion certificate confirmation
- Proforma vs collection = Check VBRK-FKART (FAZ=collection, ZF2P/other=proforma only)

---

### 2.4 Category D: Multi-Instrument Payments (TT + LC + BG)

**Pattern:** Different payment instruments for different milestones, with Bank Guarantee requirements.

| Reference Order | PO Reference | TT Component | LC Component | BG Component |
|---|---|---|---|---|
| 3228005142 | BB0735-02 | EUR 548,000 DP + EUR 84,735 LOP + EUR 9,417 software + EUR 137,000 post-delivery | EUR 1,510,047 genset + EUR 450,801 SCR (prior shipment) | Waiting for BG caused DP delay |
| 3228005227 | FFX-III-MF-2 | 30% DP against counter guarantee | 70% irrevocable LC, 6 weeks before shipment | Counter guarantee required before DP |
| 3228005185 | PO-39.0525 | 20% DP + 80% before EXW | -- | 5% BG before 80% balance, valid 6 months or until commissioning |
| 3228005268 | PO-251210301 | 20% DP + 80% upon NOR | -- | 10% BG against 80% payment, valid until commissioning or 6 months after shipment |

**SAP Posting Pattern (3228005142 - Terms Changed):**
```
Original Terms: 20% DP (TT) + 75% LC (prior EXW) + 5% TT (18m after delivery or 45d after SAT)

CHANGED TO Fixed Amounts per Item Category:
  Pos 10: MG20V4000A5 (MARINE GENSET 20V4000M65L) - ZE2, rejected (typo)
  Pos 11: MG20V4000A5 (MARINE GENSET 20V4000M65L) - ZE3
  Pos 12: ACCESSORIES (mtu SCR) - ZEX2
  Pos 13: ACCESSORIES (mtu LOP) - ZEX2
  Pos 14: ACCESSORIES (Software for mtu LOP) - ZEX2
  Pos 20: ACC_V4000 (Final payment, 45 days after SAT) - ZEX2

  DP allocation:
    EUR 548,000 via TT (DP against engines)
    EUR 1,510,047 via LC (3 x genset, prior shipment)
    EUR 450,801 via LC (3 x SCR, prior shipment)
    EUR 84,735 via TT (3 x LOP, 30 days from invoice)
    EUR 9,417 via TT (3 x software, 30 days from invoice)
    EUR 137,000 via TT (18 months after delivery or 45 days after SAT)
```

**Key Observations from SAP:**
- SoF first approved in March, but DP invoice issued in May -- **BG receipt was the gate**
- Payment terms changed from percentage-based to fixed-amount per item category
- Pos 10 rejected (Data Entry Error, item category typo), pos 11 is the corrected replacement
- Multiple item categories in play: ZE2, ZE3, ZEX2

**Agent Derivation Rules:**
- BG receipt = External event, not in SAP standard -- requires manual confirmation or external system notification
- LC establishment timing = "N days/weeks before shipment" requires delivery schedule minus offset
- Payment instrument per line item = Must read VBKD-ZLSCH (payment method) at item level or from billing plan text
- Fixed-amount vs percentage-based = Check FPLTR: if FAKWR populated (absolute) vs BETEFP populated (percentage)

---

### 2.5 Category E: Large-Scale Contract with Periodic DPs

**Pattern:** Multi-shipset/multi-unit contracts spanning extended periods with periodic downpayments and vendor PO linkage.

| Reference Order | PO Reference | Structure |
|---|---|---|
| 3228004906 | Sales Contract | 5 shipsets x 20 units. 10% DP (TT, 12m before delivery) + 20% intermediate (LC at sight, 30d before delivery) + 65% final 1 (60d Usance LC, 30d before delivery) + 5% final 2 (TT, 60d after delivery). Rev.2 VO: 100% TT EUR 184,000 |

**SAP Posting Pattern:**
```
Sales Order (VBAK): Old order, NO Terms of Payment Text
  20+ Line Items: STANDARD MONITOR material across multiple positions

  Document Flow (massive):
    E:SlsOrder w/IO 3228004906 (26.07.2023)
      --> Purchase Order 2800009126 (27.07.2023)
      --> E: Down Payment 3851802127 (10.08.2023)
      --> E: Down Payment 3851802129 (10.08.2023)
      --> ... (many more DP docs over 2+ years)
      --> Manual E/O order 3398001945
      --> E: Invoice 3818014709 (14.11.2024)
      --> Accounting document 5610335673 (14.11.2024, Cleared)
      --> ... (multiple invoice + accounting cycles)
      --> E: Down Payment 3851802501 (02.02.2025)
      --> E: Down Payment 3851802557 (13.02.2025)
      --> E: Invoice 3818015446 (03.03.2025)
      --> Accounting document 5610396607 (03.03.2025, Cleared)

  Proforma Invoice 3868003712:
    - Covers 20%+65% combined billing
    - CIF Taiwan Seaport
    - References Packing List 3478003073

  Vendor PO & MIRO:
    - Purchase Order shown in EKKO/EKPO (ME23N)
    - Logistics Invoice Verification (MIRO): RBKP header + RSEG line items
    - Final customer invoice triggered by vendor PO invoice receipt date
```

**Key Observations from SAP:**
- VBAP table shows 20+ entries across multiple materials (STANDARD MONITOR variants + DIESEL ENGINE)
- VBFA document flow contains 30+ documents spanning 2023-2025
- DP invoice text specifies a **specific date** (not formula-based) -- "10% to be paid by T/T 12 months before engines delivery date" but in practice issued ASAP
- 20%+65% combined into single proforma invoice 3868003712
- MIRO (Logistics Invoice Verification) is the trigger for final customer invoice -- RBKP/RSEG tables show vendor invoice verification header and line items
- Accounting documents show "Cleared" status confirming payment receipt

**Agent Derivation Rules:**
- DP timing discrepancy = "12 months before delivery" stated but actually issued immediately -- agent should flag this gap
- Combined milestone invoicing = Multiple billing plan lines consolidated into single proforma
- Vendor PO linkage = VBFA document flow links Sales Order -> Purchase Order (2800xxxxxx) -> Invoice Receipt (MIRO)
- Final invoice trigger = Vendor invoice receipt date from RBKP-BLDAT or RBKP-BUDAT

---

### 2.6 Category F: Mid-Order Payment Terms Change

**Pattern:** Original payment terms amended during order lifecycle, requiring the agent to detect version changes and apply current terms.

| Reference Order | Original Terms | Changed Terms | Reason |
|---|---|---|---|
| 3228005142 | 20% DP + 75% LC + 5% post-delivery | Fixed amounts per item category (6 separate payment lines) | Bank Guarantee requirements; item category restructuring |

**SAP Indicators of Terms Change:**
- VBAK-ERDAT vs VBKD-AEDAT (creation vs last change date)
- Multiple NAST records for ZSOV (SoF versions)
- FPLA/FPLT changes reflected in billing plan version
- Billing block (FAKSP) removed/changed
- Item rejection status (VBUP-ABSTA) on original items

**Agent Derivation Rules:**
- Detect terms change = Compare current VBKD-ZTERM with billing plan text vs original
- Position replacement = When VBUP-ABSTA shows rejection on original pos, find replacement pos via material match
- Payment terms text parsing = VBKD-ZTERM free text field contains human-readable payment schedule

---

## 3. Trigger Event Derivation Logic

The Agentic System must derive the correct trigger date for each downpayment milestone. The following table maps each trigger event to its SAP data source and derivation method.

| # | Trigger Event | SAP Data Source | Derivation Method | Confidence | Applicable Cases |
|---|---|---|---|---|---|
| 1 | **Order Placement / PO Receipt** | VBAK-ERDAT (order creation date) or VBAK-BSTDK (customer PO date) | Direct read | HIGH | 3228005185, 3228005242, 3228005268 |
| 2 | **First SoF Release Date** | NAST: Output type ZSOV, first record's ERDAT/ERZET | Query NAST WHERE KAPPL='V1' AND KSCHL='ZSOV' AND OBJKY=VBELN, MIN(ERDAT) | HIGH | 3228005143, 3228005147, 3228005171 |
| 3 | **Order Confirmation Printed** | NAST: Output type ZEOR, first record with Process.status=1 | Query NAST WHERE KSCHL='ZEOR' AND OBJKY=VBELN AND VSTAT='1', first ERDAT | HIGH | 3228005113 (Power Gen) |
| 4 | **N Days After First Payment** | BSEG: Clearing date of first DP FI document | Find first FAZ billing doc -> FI doc (BKPF-BELNR) -> BSEG-AUGDT + N days | HIGH | 3228005124 (interim: 60d after 1st payment) |
| 5 | **N Days Before FCA/EXW/Shipment** | VBEP-EDATU (delivery schedule date) or LIKP-WADAT (planned goods issue) | VBEP-EDATU minus N days | MEDIUM | 3228005113, 3228005242 |
| 6 | **Contract Signing Date** | NOT in SAP | **Manual input required** -- flag to user | LOW | 3228005227 |
| 7 | **Drawings/Documentation Submission** | NOT in SAP (milestone confirmation required) | **Manual input required** -- flag to user | LOW | 3228005168 (2nd milestone) |
| 8 | **Vendor PO Invoice Receipt (MIRO)** | RBKP-BLDAT (invoice date) or RBKP-BUDAT (posting date) | Query RBKP/RSEG via PO number from EKKO linked through VBFA | HIGH | 3228005124 (final), 3228004906 |
| 9 | **FAT (Factory Acceptance Test)** | Quality Notification or custom milestone table | Check QMEL or Z-table for FAT confirmation date | MEDIUM | 3228005230 (80% after FAT) |
| 10 | **SAT (Site Acceptance Test)** | Quality Notification or custom milestone table | Check QMEL or Z-table for SAT confirmation date | MEDIUM | 3228005142, 3228005208 |
| 11 | **NOR (Notification of Readiness)** | LIKP-WADAT_IST (actual goods issue) or custom notification | Derive from delivery status or custom output type | MEDIUM | 3228005147, 3228005268 |
| 12 | **Equipment Arrival at Job Site** | Proof of delivery / custom tracking | Delivery confirmation + transport lead time | LOW | 3228005208 (50% progress) |
| 13 | **Installation Completion** | Custom milestone table or service confirmation | External confirmation required | LOW | 3228005208 (25% progress) |
| 14 | **Final Acceptance** | Custom milestone table | External confirmation required | LOW | 3228005208 (5% final) |
| 15 | **Bank Guarantee Receipt** | NOT in SAP standard | **External tracking required** | LOW | 3228005142, 3228005185, 3228005208, 3228005227, 3228005268 |
| 16 | **N Months After Delivery** | LIKP-WADAT_IST (actual goods issue date) + N months | Direct calculation from confirmed delivery | MEDIUM | 3228005142 (18m), 3228004906 (60d) |
| 17 | **Customer PO Date** | VBAK-BSTDK | Direct read | HIGH | 3228005242 (14 days upon PO) |

### Confidence Level Definition

| Level | Meaning | Agent Action |
|---|---|---|
| **HIGH** | Data available in SAP standard tables, deterministic derivation | Fully automated |
| **MEDIUM** | Data may be in SAP but requires custom table/config lookup or heuristic | Automated with human confirmation |
| **LOW** | Data NOT in SAP, requires external input | Flag to user, await manual confirmation |

---

## 4. SAP Document Types & Posting Patterns

### 4.1 Document Number Ranges Observed

| Document Type | Number Range | SAP Table | Example |
|---|---|---|---|
| Sales Order (E:SlsOrder) | 3228xxxxxx | VBAK | 3228005113 |
| Down Payment Request (E: Down Payment) | 3851xxxxxx | VBRK (FKART=FAZ) | 3851802644 |
| Invoice (E: Invoice) | 3818xxxxxx | VBRK (FKART=F2) | 3818015313 |
| Invoice Cancellation (E:Invoice Cancell.) | 3891xxxxxx | VBRK (FKART=S1/ZS1) | 3891800429 |
| Proforma Invoice (E:Proforma) | 3868xxxxxx | VBRK (FKART=ZF2P/F8) | 3868003805 |
| FI Accounting Document | 5610xxxxxx | BKPF | 5610371928 |
| Purchase Requisition (BANF) | 2480xxxxxx | EBAN | 2480034805 |
| Purchase Order | 2800xxxxxx | EKKO | 2800009786 |
| Invoice Receipt (MIRO) | 1802xxxxxx | RBKP | 1802074183 |
| Manual E/O Order | 3398xxxxxx | VBAK | 3398001945 |
| Packing List | 3478xxxxxx | LIKP | 3478003073 |

### 4.2 Item Categories Observed

| Item Category | Description | Usage | DP Applicability |
|---|---|---|---|
| ZE2 | Engine New Business (rejected/typo) | Main engine items -- sometimes used erroneously | DP created against these |
| ZE3 | Engine New Business (active) | Primary engine line items | DP + Invoice |
| ZEX2 | Accessories / Service | Accessories, SCR, LOP, Software, PSI phases, final payment items | DP or standalone invoice |
| ZED2 | (Observed in status) | Engineering/design items | Conditional |

### 4.3 Billing Block Codes

| Block Code | Description | Agent Behaviour |
|---|---|---|
| 01 | Block for billing | Item blocked for invoicing. NOTE: DP (FAZ) may already exist if created before block was set. Agent must NOT assume blocked items have no DP activity. |
| 02 | Block for delivery | Delivery blocked -- DP unaffected |
| (blank) | No block | Normal billing allowed |

**Critical:** Order 3228005142 demonstrates that a DP document (3851802696) can exist against a billing-blocked item (pos 20, "Final payment, 45 days after SAT", block 01). The agent must always check VBRK/VBRP for existing billing documents regardless of current block status.

### 4.3 Posting Flow per Category

**Category A (Simple DP + Balance):**
```
VBAK --> FPLA/FPLT (2 lines) --> VBRK[FAZ] --> BKPF/BSEG --> VBRK[F2] --> BKPF/BSEG[Cleared]
```

**Category B (Multi-Milestone):**
```
VBAK --> FPLA/FPLT (3-4 lines)
  --> VBRK[FAZ] #1 (1st DP)  --> BKPF/BSEG
  --> VBRK[FAZ] #2 (2nd DP)  --> BKPF/BSEG
  --> VBRK[F2] (final)        --> BKPF/BSEG[Cleared, nets out DPs]
```

**Category C (Progress):**
```
VBAK --> FPLA/FPLT (5+ lines)
  --> VBRK[FAZ] (advance DP)
  --> VBRK[ZF2P] (proforma, not for collection)
  --> VBRK[F2] #1..N (progress invoices, prorated per unit)
  --> VBRK[F2] (final, nets out all prior)
```

**Category E (Large Contract):**
```
VBAK --> EBAN (purchase requisition) --> EKKO (vendor PO)
  --> VBRK[FAZ] #1..N (periodic DPs over months/years)
  --> RBKP (vendor MIRO) --> triggers customer invoice
  --> VBRK[ZF2P] (combined proforma for 20%+65%)
  --> VBRK[F2] #1..N (invoices per shipset delivery)
  --> BKPF/BSEG[Cleared]
```

**Invoice Cancellation & Replacement (observed in Category B, order 3228005124):**
```
VBRK[F2] (original invoice 3818015386)
  --> VBRK[S1/ZS1] (cancellation 3891800429, same date, FKSTO='X')
  --> VBRK[F2] (replacement invoice 3818015387, same date)
Agent must: exclude cancelled docs, link cancellation to replacement, track NET amount only
```

---

## 5. BAPIs / Function Modules Required

### 5.1 Downpayment Request Retrieval

| BAPI / FM | Purpose | Key Input | Key Output |
|---|---|---|---|
| BAPI_BILLINGDOC_GETLIST | List all billing docs for a sales order, filter FKART=FAZ for DP requests | REF_DOC_RANGE (range table: SIGN='I', OPTION='EQ', LOW=sales_order). **Note:** This is a range table, not a scalar REFDOCNR parameter. | List of billing doc numbers, types (FAZ/F2/ZF2P), amounts, dates |
| BAPI_BILLINGDOC_GETDETAIL | Get DP request header + items with partner and pricing data | BILLINGDOCUMENT (3851xxxxxx) | BILLINGDOCUMENTHEADER (VBRK fields), BILLINGDOCUMENTITEM (VBRP fields), BILLINGDOCUMENTPARTNER |

### 5.2 Billing Plan Retrieval

| BAPI / FM | Purpose | Key Input | Key Output |
|---|---|---|---|
| BAPI_SALESORDER_GETDETAIL | Read full sales order header, items, and partners. **Note:** Billing plan data (FPLA/FPLT) is NOT included in the standard BAPI export -- use BILLING_SCHEDULE_READ or RFC_READ_TABLE on FPLA/FPLT for billing plan retrieval. | SALESDOCUMENT (order number) | ORDER_HEADER_IN, ORDER_ITEMS_IN, ORDER_PARTNERS (billing plan NOT in standard export) |
| BILLING_SCHEDULE_READ (FM) | Read billing plan dates/milestones from FPLA/FPLT tables directly | VBELN (sales order), FPLNR (billing plan number) | Billing plan dates, percentages, amounts, billing blocks, billing types per line |
| SD_SALES_DOCUMENT_READ (FM) | Alternative full sales document read | DOCUMENT_NUMBER | Complete order data including billing plan lines |

### 5.3 Billing Document Retrieval

| BAPI / FM | Purpose | Key Input | Key Output |
|---|---|---|---|
| BAPI_BILLINGDOC_GETLIST | List ALL billing documents (DP + Invoice + Proforma + Credit Memo) | REF_DOC_RANGE (range table) | Doc numbers, FKART (FAZ/F2/ZF2P/S1), amounts, dates |
| BAPI_BILLINGDOC_GETDETAIL | Read individual billing document with items and partners | BILLINGDOCUMENT | Header (VBRK), Items (VBRP with AUBEL/AUPOS linking back to sales order), Partners |

### 5.4 FI Clearing & Payment Status

| BAPI / FM | Purpose | Key Input | Key Output |
|---|---|---|---|
| BAPI_AR_ACC_GETOPENITEMS | Check if DP request is still open (unpaid) | COMPANYCODE (0011), CUSTOMER | Open items: BELNR (accounting doc), BUZEI (line), DMBTR (amount), AUGDT (clearing date) |
| BAPI_AR_ACC_GETSTATEMENT | Full customer account statement including DP clearing history | COMPANYCODE, CUSTOMER, DATE_FROM, DATE_TO | Statement with all postings, clearings, and balances |
| ~~BAPI_ACC_DOCUMENT_CHECK~~ | **REMOVED:** This BAPI is for pre-posting validation, not for reading clearing status. Use BAPI_AR_ACC_GETOPENITEMS or BAPI_AR_ACC_GETSTATEMENT instead. | -- | -- |

### 5.5 SoF / Order Confirmation Date Retrieval

| BAPI / FM | Purpose | Key Input | Key Output |
|---|---|---|---|
| **RFC_READ_TABLE** on table NAST | Read output records for SoF (ZSOV) and Order Confirmation (ZEOR). **Note:** NAST_SELECT is not a standard SAP FM; use RFC_READ_TABLE with QUERY_TABLE='NAST' and appropriate OPTIONS filters. **Security:** RFC_READ_TABLE exposes raw table access -- CPI iFlow must whitelist only NAST and enforce KAPPL='V1' filter server-side. | OPTIONS: OBJKY=VBELN, KAPPL='V1', KSCHL='ZSOV' or 'ZEOR' | ERDAT (creation date), ERZET (creation time), VSTAT (processing status) |
| READ_TEXT (FM) | Read SoF approval text/notes if stored as long text | OBJECT='VBBK', ID='Z...', NAME=VBELN | Text content of SoF/approval notes |

**Critical:** This is the primary mechanism for determining the **first SoF release date**, which is the DP invoice trigger for most Power Gen and Marine orders. The query must return the **earliest** ZSOV record with Process.status = 1 (successfully processed).

### 5.6 Purchase Order & Invoice Receipt

| BAPI / FM | Purpose | Key Input | Key Output |
|---|---|---|---|
| BAPI_PO_GETDETAIL1 | Read purchase order created from sales order (via VBFA linkage) | PURCHASEORDER (2800xxxxxx) | PO header (EKKO), items (EKPO), delivery schedules (EKET) |
| BAPI_INCOMINGINVOICE_GETLIST | List MIRO invoice receipts for a PO | PURCHASEORDER | Invoice receipt numbers (RBKP-BELNR), dates, amounts |
| BAPI_INCOMINGINVOICE_GETDETAIL | Read MIRO invoice verification header and line items | INVOICEDOCNUMBER (1802xxxxxx) | RBKP header (invoice date, posting date, amount), RSEG items (PO reference, quantity, amount) |

**Critical for Category E:** The final customer invoice date is derived from the vendor PO invoice receipt date (MIRO). The agent must traverse: Sales Order (VBAK) --> Document Flow (VBFA, VBTYP_N='F' for PO) --> Purchase Order (EKKO) --> Invoice Receipt (RBKP).

### 5.7 Bank Guarantee Tracking

| Data Source | Purpose | Availability |
|---|---|---|
| SAP Treasury (TRM) | BG master records, validity, amounts | **Not standard in SD** -- requires custom iFlow if available |
| Custom Z-table | RRPS-specific BG tracking | **To be confirmed** with client tech team |
| External system | BG issuance/receipt confirmation | Requires manual input or external API integration |

**Recommendation:** Create a new CPI iFlow (`MS5GetBankGuarantee`) if RRPS has BG data in SAP TRM, otherwise implement external tracking in the Agentic System with manual confirmation workflow.

---

## 6. Field Mapping: SAP to Agentic System

### 6.1 Billing Plan Header (FPLA)

**CORRECTED:** The billing plan header table is **FPLA** (not FPLT). FPLT contains the date lines/items. FPLTR is a **field within FPLT** (sequence number, part of the primary key MANDT + FPLNR + FPLTR), not a separate table.

| SAP Field | SAP Table.Field | Description | Agentic System Model | Agentic Field | Example |
|---|---|---|---|---|---|
| FPLNR | FPLA-FPLNR | Billing plan number | DownpaymentPlan | plan_number | 0000012345 |
| FPART | FPLA-FPART | Billing plan type (01=Periodic, 02=Milestone) | DownpaymentPlan | plan_type | 02 (Milestone) |
| BETEFV | FPLA-BETEFV | Percentage basis rule | DownpaymentPlan | percentage_basis | 01 (of net value) |
| WAESSION | FPLA-WAESSION | Billing plan currency | DownpaymentPlan | currency | EUR |
| FAKWR | FPLA-FAKWR | Total billing plan value | DownpaymentPlan | total_plan_value | 2,705,000.00 |
| FKDAT | FPLA-FKDAT | Start date of billing plan | DownpaymentPlan | plan_start_date | 2025-01-08 |

### 6.2 Billing Plan Date Lines (FPLT)

**CORRECTED:** The date lines table is **FPLT** (not a separate FPLTR table). The field FPLT-FPLTR is the sequence/item number within the billing plan.

| SAP Field | SAP Table.Field | Description | Agentic System Model | Agentic Field | Example |
|---|---|---|---|---|---|
| FPLNR | FPLT-FPLNR | Billing plan number | PaymentMilestone | plan_number | (links to FPLA) |
| FPLTR | FPLT-FPLTR | Sequence number (item within billing plan) | PaymentMilestone | milestone_index | 1, 2, 3... |
| FDATU | FPLT-FDATU | Billing/milestone date | PaymentMilestone | due_date | 2025-03-18 |
| NFDAT | FPLT-NFDAT | Next billing date | PaymentMilestone | next_check_date | 2025-06-15 |
| TETXT | FPLT-TETXT | Milestone description text | PaymentMilestone | description | "Down Payment" |
| FAKWR | FPLT-FAKWR | Absolute billing value | PaymentMilestone | amount | 270,500.00 |
| BETEFP | FPLT-BETEFP | Percentage of plan value | PaymentMilestone | percentage | 10.0 |
| FPFAR | FPLT-FPFAR | Billing type override | PaymentMilestone | billing_type | FAZ (DP), F2 (Invoice) |
| FAKSP | FPLT-FAKSP | Billing block | PaymentMilestone | is_blocked | true if populated |
| FKSAF | FPLT-FKSAF | Billing status | PaymentMilestone | status | A=OPEN, B=BILLED, C=CANCELLED |

### 6.3 Downpayment Request Document (VBRK/VBRP)

| SAP Field | SAP Table.Field | Description | Agentic System Model | Agentic Field | Example |
|---|---|---|---|---|---|
| VBELN | VBRK-VBELN | Billing document number | DownpaymentRequest | document_number | 3851802644 |
| FKART | VBRK-FKART | Billing type | DownpaymentRequest | document_type | FAZ (DP Request) |
| FKDAT | VBRK-FKDAT | Billing date | DownpaymentRequest | billing_date | 2025-03-18 |
| KUNAG | VBRK-KUNAG | Sold-to party | DownpaymentRequest | customer_id | 0022005992 |
| KUNRG | VBRK-KUNRG | Payer | DownpaymentRequest | payer_id | 0022005992 |
| NETWR | VBRK-NETWR | Net value | DownpaymentRequest | amount | 270,500.00 |
| WAERK | VBRK-WAERK | Currency | DownpaymentRequest | currency | EUR |
| ZTERM | VBRK-ZTERM | Payment terms key | DownpaymentRequest | payment_terms_key | A000 |
| ZLSCH | VBRK-ZLSCH | Payment method | DownpaymentRequest | payment_method | T (TT), L (LC) |
| FKSTO | VBRK-FKSTO | Cancelled flag | DownpaymentRequest | is_cancelled | false |
| AUBEL | VBRP-AUBEL | Originating sales order | DownpaymentRequest | sales_order | 3228005113 |
| AUPOS | VBRP-AUPOS | Originating item | DownpaymentRequest | sales_order_item | 000010 |
| FKIMG | VBRP-FKIMG | Billed quantity | DownpaymentRequest | billed_quantity | 5.000 |
| NETWR | VBRP-NETWR | Item net value | DownpaymentRequest | item_amount | 270,500.00 |
| MATNR | VBRP-MATNR | Material entered | DownpaymentRequest | material | 20V4000DS4000 |

### 6.4 FI Accounting Document (BKPF/BSEG)

| SAP Field | SAP Table.Field | Description | Agentic System Model | Agentic Field | Example |
|---|---|---|---|---|---|
| BELNR | BKPF-BELNR | Accounting document number | PaymentClearing | fi_document | 5130025522 |
| BUKRS | BKPF-BUKRS | Company code | PaymentClearing | company_code | 0011 |
| GJAHR | BKPF-GJAHR | Fiscal year | PaymentClearing | fiscal_year | 2025 |
| BUDAT | BKPF-BUDAT | Posting date | PaymentClearing | posting_date | 2025-03-18 |
| AUGDT | BSEG-AUGDT | Clearing date | PaymentClearing | clearing_date | 2025-07-30 |
| AUGBL | BSEG-AUGBL | Clearing document number | PaymentClearing | clearing_document | 5140059754 |
| DMBTR | BSEG-DMBTR | Amount in local currency | PaymentClearing | amount_local | 270,500.00 |
| WRBTR | BSEG-WRBTR | Amount in document currency | PaymentClearing | amount_doc | 270,500.00 |
| SHKZG | BSEG-SHKZG | Debit/Credit indicator | PaymentClearing | posting_type | S=Debit, H=Credit |

**Clearing Status Logic:**
| BSEG-AUGDT | BSEG-AUGBL | Status | Agentic Mapping |
|---|---|---|---|
| NULL | NULL | Open (unpaid) | `status = "REQUESTED"` |
| Populated | Populated | Cleared (paid) | `status = "PAID"` |
| NULL | Partial match | Partially cleared | `status = "PARTIALLY_PAID"` |

### 6.5 Sales Order Status (VBUK/VBUP)

| SAP Field | SAP Table.Field | Description | Agentic System Model | Agentic Field |
|---|---|---|---|---|
| GBSTK | VBUK-GBSTK | Overall status | OrderStatus | header_status |
| FKSAK | VBUK-FKSAK | Billing status (header) | OrderStatus | billing_status |
| ABSTK | VBUK-ABSTK | Rejection status (header) | OrderStatus | rejection_status |
| FKSTA | VBUP-FKSTA | Billing status (item) | ItemStatus | item_billing_status |
| ABSTA | VBUP-ABSTA | Rejection status (item) | ItemStatus | item_rejection_status |
| LFSTA | VBUP-LFSTA | Delivery status (item) | ItemStatus | item_delivery_status |

**Critical for position replacement detection:**
- When VBUP-ABSTA = 'C' (fully rejected), the item is inactive
- Agent must find replacement item: same material (VBAP-MATNR) with ABSTA != 'C'
- Example: Order 3228005124 -- pos 10 (rejected, ZEX2 typo) replaced by pos 30 (active, ZE3)

### 6.6 Document Flow (VBFA)

| SAP Field | SAP Table.Field | Description | Agentic System Model | Agentic Field |
|---|---|---|---|---|
| VBELV | VBFA-VBELV | Preceding document | DocumentFlowEntry | source_document |
| POSNV | VBFA-POSNV | Preceding item | DocumentFlowEntry | source_item |
| VBELN | VBFA-VBELN | Subsequent document | DocumentFlowEntry | target_document |
| POSNN | VBFA-POSNN | Subsequent item | DocumentFlowEntry | target_item |
| VBTYP_N | VBFA-VBTYP_N | Subsequent doc category | DocumentFlowEntry | target_type |
| ERDAT | VBFA-ERDAT | Creation date | DocumentFlowEntry | created_on |
| RFMNG | VBFA-RFMNG | Quantity | DocumentFlowEntry | quantity |
| RFWRT | VBFA-RFWRT | Value | DocumentFlowEntry | value |

**VBTYP_N Values for Downpayment Tracking:**
| Code | Document Category | Description |
|---|---|---|
| C | Order | Sales Order |
| B | Purchase Requisition | BANF (2480xxxxxx) |
| F | Purchase Order | Vendor PO (2800xxxxxx) |
| M | Invoice / DP Request | Customer Invoice (F2, 3818xxxxxx) AND DP Request (FAZ, 3851xxxxxx). **NOTE:** DP requests share VBTYP_N='M' with invoices. Differentiate by reading VBRK-FKART: FAZ=DP Request, F2=Invoice. |
| U | Pro Forma Invoice | Proforma Invoice (3868xxxxxx). **CORRECTED:** SAP standard VBTYP 'U' = Pro Forma, NOT Down Payment Request. |
| N | Invoice Cancellation | Cancelled Invoice (3891xxxxxx) |
| S | Credit Memo Cancellation | Cancellation of a credit memo |
| O | Credit Memo | Credit Memo (S1) |
| P | Debit Memo | **CORRECTED:** SAP standard VBTYP 'P' = Debit Memo, NOT Proforma. |
| J | Delivery | Outbound Delivery |
| H | Returns | Returns |

**IMPORTANT — DP Request Detection in Document Flow:**
Down payment requests (FKART=FAZ) appear in VBFA with `VBTYP_N='M'` (same code as regular invoices). The agent MUST read the billing document detail (`BAPI_BILLINGDOC_GETDETAIL`) and check `VBRK-FKART` to distinguish:
- `FKART = FAZ` → Down Payment Request (track for collection)
- `FKART = F2` → Invoice (track for collection)
- `FKART = ZF2P / F8` → Proforma (display only, NOT for collection)
- `FKART = S1 / ZS1` → Credit Memo / Cancellation

### 6.7 Purchase Order Invoice Receipt (RSEG/RBKP)

| SAP Field | SAP Table.Field | Description | Agentic System Model | Agentic Field | Example |
|---|---|---|---|---|---|
| BELNR | RBKP-BELNR | Invoice receipt number | VendorInvoiceReceipt | receipt_number | 1802074183 |
| GJAHR | RBKP-GJAHR | Fiscal year | VendorInvoiceReceipt | fiscal_year | 2025 |
| BLDAT | RBKP-BLDAT | Invoice date | VendorInvoiceReceipt | invoice_date | 2025-09-30 |
| BUDAT | RBKP-BUDAT | Posting date | VendorInvoiceReceipt | posting_date | 2025-09-30 |
| LIFNR | RBKP-LIFNR | Vendor number | VendorInvoiceReceipt | vendor_id | 0022xxxxxx |
| RMWWR | RBKP-RMWWR | Gross invoice amount | VendorInvoiceReceipt | gross_amount | 2,377,702.60 |
| WAERS | RBKP-WAERS | Currency | VendorInvoiceReceipt | currency | EUR |
| EBELN | RSEG-EBELN | PO number | VendorInvoiceReceipt | po_number | 2800009744 |
| EBELP | RSEG-EBELP | PO item | VendorInvoiceReceipt | po_item | 10 |
| WRBTR | RSEG-WRBTR | Item amount | VendorInvoiceReceipt | item_amount | varies |

---

## 7. Agentic Scenarios: AI Agent Capabilities

### 7.1 DP Invoice Trigger Detection

**Capability:** Automatically determine when a downpayment invoice should be issued based on the trigger event type.

| Trigger Type | Detection Method | SAP Data Required | Agent Action |
|---|---|---|---|
| SoF First Approval | NAST query for ZSOV, min(ERDAT) | NAST + VBAK | Calculate DP due date = SoF date + offset days |
| Order Confirmation (ZEOR) | NAST query for ZEOR with VSTAT=1 | NAST + VBAK | Calculate DP due date = ZEOR date + offset days |
| Customer PO Date | VBAK-BSTDK | VBAK | DP due date = PO date + offset days |
| Order Creation | VBAK-ERDAT | VBAK | DP due date = creation date (immediate) |

**Agent Logic (pseudocode):**
```
function derive_dp_trigger_date(sales_order, trigger_type):
    if trigger_type == "SOF_APPROVAL":
        sof_records = RFC_READ_TABLE('NAST', OBJKY=sales_order, KSCHL='ZSOV', VSTAT='1')
        return min(sof_records.ERDAT)
    elif trigger_type == "ORDER_CONFIRMATION":
        oc_records = RFC_READ_TABLE('NAST', OBJKY=sales_order, KSCHL='ZEOR', VSTAT='1')
        return min(oc_records.ERDAT)
    elif trigger_type == "PO_RECEIPT":
        return VBAK.BSTDK  -- customer PO date
    elif trigger_type == "ORDER_PLACEMENT":
        return VBAK.ERDAT  -- order creation date
    else:
        return FLAG_FOR_MANUAL_INPUT(trigger_type)
```

**Reference Cases:** All 15 cases use one of these triggers for the first milestone.

---

### 7.2 Multi-Position DP Allocation Tracking

**Capability:** Track downpayment allocation across multiple sales order line items, including position replacement scenarios.

**Scenario 1: DP against backlog positions replaced by actual positions**
- Order 3228005124: DP invoiced against pos 10/20 (backlog), but pos 30/40 created later with proper material. Agent must redirect monitoring from pos 10/20 to pos 30/40.

**Scenario 2: DP against one position, invoice against different position**
- Order 3228005143: DP collected against pos 10/20, but delivery/invoice against pos 30. Different material numbers (pos 10 = 20V4000G23F vs pos 30 = 20V4000G41F).

**Scenario 3: Multiple DPs per position**
- Order 3228005168: 3 positions (pos 10/20/30) each with 3 DP documents + 1 invoice. Total 9 DP docs for the order.
- Order 3228005185: 2 positions (pos 10/20) each with 2 DP documents. Total 4 DP docs.

**Agent Logic:**
```
function track_dp_allocation(sales_order):
    items = GET_ORDER_ITEMS(sales_order)  -- VBAP
    active_items = [i for i in items if i.ABSTA != 'C']  -- exclude rejected
    rejected_items = [i for i in items if i.ABSTA == 'C']

    for rejected in rejected_items:
        replacement = find_replacement(rejected, active_items)
        if replacement:
            link_dp_docs(rejected.POSNR, replacement.POSNR)
            alert("Position {rejected.POSNR} replaced by {replacement.POSNR}")

    dp_docs = BAPI_BILLINGDOC_GETLIST(REF_DOC_RANGE=sales_order, FKART='FAZ')
    for dp in dp_docs:
        detail = BAPI_BILLINGDOC_GETDETAIL(dp.VBELN)
        for item in detail.ITEMS:
            allocation[item.AUPOS].append({
                'dp_doc': dp.VBELN,
                'amount': item.NETWR,
                'date': dp.FKDAT,
                'status': get_clearing_status(dp.VBELN)
            })

    return allocation

function find_replacement(rejected_item, active_items):
    -- Match by material or material group
    for active in active_items:
        if active.MATNR == rejected_item.MATNR or \
           similar_material(active.MATNR, rejected_item.MATNR):
            return active
    return None
```

---

### 7.3 Payment Terms Change Monitoring

**Capability:** Detect when payment terms are modified mid-order and apply current terms.

**Reference Case:** Order 3228005142 -- original terms (20%/75%/5% percentage-based) changed to fixed amounts per item category with new line items added.

**Detection Indicators:**
| Indicator | SAP Source | What to Check |
|---|---|---|
| Terms text changed | VBKD-ZTERM + VBKD-AEDAT | Compare creation date vs last change date |
| New items added after order creation | VBAP-ERDAT per item | Items with ERDAT significantly after VBAK-ERDAT |
| Items rejected post-creation | VBUP-ABSTA = 'C' with rejection reason 03 (Data Entry Error) | Rejection after initial creation |
| Billing block changes | VBKD-FAKSP / VBUP-FKSAA | Block added/removed |
| Multiple SoF versions | NAST ZSOV record count > 1 | Multiple SoF approvals |
| Billing plan value changes | FPLT-FAKWR vs original | Plan value differs from order net value |

**Agent Logic:**
```
function detect_terms_change(sales_order):
    order = BAPI_SALESORDER_GETDETAIL(sales_order)
    items = order.ITEMS

    creation_date = order.HEADER.ERDAT
    latest_item_date = max(item.ERDAT for item in items)

    if (latest_item_date - creation_date) > 30 days:
        alert("New items added {latest_item_date - creation_date} days after order creation")

    rejected_count = count(item for item in items if item.ABSTA == 'C')
    if rejected_count > 0:
        alert(f"{rejected_count} items rejected -- possible terms restructuring")

    sof_versions = RFC_READ_TABLE('NAST', OBJKY=sales_order, KSCHL='ZSOV')
    if len(sof_versions) > 1:
        alert(f"Multiple SoF versions ({len(sof_versions)}) -- terms may have changed")

    -- Always use CURRENT billing plan, not historical
    current_plan = BILLING_SCHEDULE_READ(sales_order)
    return current_plan
```

---

### 7.4 Bank Guarantee Lifecycle Tracking

**Capability:** Track BG issuance, amount, validity, and link to payment conditions.

**Cases Requiring BG:**
| Order | BG Amount | BG Purpose | Validity |
|---|---|---|---|
| 3228005185 | 5% of contract | Before 80% balance payment | 6 months or until commissioning |
| 3228005268 | 10% of 80% payment | Against balance payment | Until commissioning or 6 months after shipment |
| 3228005208 | 15% advance amount | 15% advance BG letter | Until equipment arrival at INCOTERMS DDP job site |
| 3228005227 | Counter guarantee | Before 30% DP payment | Until DP settlement |
| 3228005142 | (unspecified) | Delayed DP due to BG wait | Until DP invoice cleared |

**Data Model Extension Required:**
```
BankGuarantee:
    bg_reference: str           -- BG reference number (external)
    sales_order: str            -- Linked sales order (VBELN)
    bg_type: str                -- ADVANCE_PAYMENT | PERFORMANCE | RETENTION
    amount: Decimal             -- BG amount
    currency: str               -- Currency
    percentage: Decimal         -- % of contract value
    issued_date: Optional[date] -- When BG was issued
    expiry_date: Optional[date] -- BG expiry
    expiry_condition: str       -- "6 months after shipment" / "until commissioning"
    status: str                 -- PENDING | ISSUED | ACTIVE | EXPIRED | RELEASED
    gates_milestone: str        -- Which milestone this BG gates (e.g., "80% balance")
    source: str                 -- "MANUAL" (until SAP TRM iFlow available)
```

---

### 7.5 L/C Timing & Readiness Monitoring

**Capability:** Monitor Letter of Credit establishment deadlines relative to shipment dates.

**Cases with L/C:**
| Order | L/C Requirement | Timing Rule |
|---|---|---|
| 3228005124 | 80.2% balance by L/C 30 days at sight | LC established 30 days before EXW |
| 3228005142 | EUR 1,510,047 + EUR 450,801 via L/C | Prior to shipment |
| 3228005227 | 70% by irrevocable L/C | 6 weeks before date of shipment |
| 3228005242 | 80% LC at sight | 30 days before engines shipped |
| 3228004906 | 20% LC at sight + 65% 60d Usance LC | 30 days before delivery date |

**Agent Logic:**
```
function monitor_lc_readiness(sales_order):
    plan = BILLING_SCHEDULE_READ(sales_order)
    delivery_dates = GET_DELIVERY_SCHEDULE(sales_order)  -- VBEP-EDATU

    for milestone in plan.lines:
        if milestone.payment_method == "LC":
            offset = parse_lc_timing(milestone.TETXT)  -- e.g., "30 days before"
            lc_deadline = earliest_delivery_date - offset

            days_remaining = lc_deadline - today()
            if days_remaining <= 14:
                alert(f"LC URGENT: {days_remaining} days to establish LC for {milestone.description}")
            elif days_remaining <= 30:
                alert(f"LC WARNING: {days_remaining} days to establish LC for {milestone.description}")
```

---

### 7.6 PSI Stage Payment Tracking

**Capability:** Track Pre-Shipment Inspection (PSI) stage payments against work completion certificates.

**Reference Case:** Order 3228005171 -- PSI in stages 30%/40%/30%, payment by TT within 15 days against work completion certificate + SAP Service Sheet.

**SAP Line Items for PSI:**
| Position | Material | Description | Item Category |
|---|---|---|---|
| 12 | ACC_V8000_DIRECT | PSI - PHASE_1 | ZEX2 |
| 13 | ACC_V8000_DIRECT | PSI - PHASE_2 | ZEX2 |
| 14 | ACC_V8000_DIRECT | PSI - PHASE_3 | ZEX2 |

**Agent Logic:**
```
function track_psi_stages(sales_order):
    items = GET_ORDER_ITEMS(sales_order)
    psi_items = [i for i in items if "PSI" in i.ARKTX or "PHASE" in i.ARKTX]

    for psi in psi_items:
        phase = extract_phase(psi.ARKTX)  -- "PHASE_1" -> 1
        percentage = PSI_STAGE_MAP[phase]  -- {1: 30%, 2: 40%, 3: 30%}

        billing_docs = GET_BILLING_FOR_ITEM(sales_order, psi.POSNR)
        if billing_docs:
            status = "BILLED"
            clearing = get_clearing_status(billing_docs[0])
        else:
            status = "AWAITING_COMPLETION_CERT"

        yield PSIStage(
            phase=phase,
            percentage=percentage,
            amount=psi.NETWR * percentage,
            status=status,
            requires="Work Completion Certificate + SAP Service Sheet"
        )
```

---

### 7.7 Proforma vs Collection Invoice Differentiation

**Capability:** Distinguish proforma invoices (informational only) from collection invoices (actual receivables).

**Reference Cases:**
- Order 3228005208: Document 3868003805 is proforma (not for collection); Document 3851802837 is the real DP request
- Order 3228005242: Proforma 3868003811 exists alongside DP 3851802840
- Order 3228004906: Proforma 3868003712 combines 20%+65% for informational purposes

**Differentiation Logic:**
| VBRK-FKART | Number Range | Type | Receivable? | Agent Action |
|---|---|---|---|---|
| FAZ | 3851xxxxxx | Down Payment Request | YES | Track for payment clearing |
| F2 | 3818xxxxxx | Invoice | YES | Track for payment clearing |
| ZF2P / F8 | 3868xxxxxx | Proforma Invoice | NO | Display only, do not track for collection |
| S1 | varies | Credit Memo | YES (negative) | Net against receivables |

---

### 7.8 Vendor PO Invoice Receipt Linkage

**Capability:** Link vendor PO invoice receipt (MIRO) to customer invoice trigger for orders where final payment depends on vendor supply chain.

**Reference Cases:**
- Order 3228005124: Final customer invoice based on vendor PO invoice receipt date
- Order 3228004906: Vendor PO 2800009126, MIRO triggers customer invoicing

**Document Flow Traversal:**
```
Sales Order (VBAK, 3228xxxxxx)
  --> VBFA (VBTYP_N='F') --> Purchase Order (EKKO, 2800xxxxxx)
    --> VBFA (VBTYP_N='Q') --> Invoice Receipt (RBKP, 1802xxxxxx)
      --> RBKP-BUDAT = Vendor invoice posting date
      --> This date triggers customer final invoice
```

**Agent Logic:**
```
function check_vendor_invoice_receipt(sales_order):
    doc_flow = GET_DOCUMENT_FLOW(sales_order)
    po_entries = [d for d in doc_flow if d.VBTYP_N == 'F']  -- Purchase Orders

    for po in po_entries:
        miro_entries = GET_MIRO_FOR_PO(po.VBELN)
        for miro in miro_entries:
            if miro.status == 'POSTED':
                return {
                    'po_number': po.VBELN,
                    'miro_number': miro.BELNR,
                    'invoice_date': miro.BLDAT,
                    'posting_date': miro.BUDAT,
                    'amount': miro.RMWWR,
                    'trigger_ready': True
                }

    return {'trigger_ready': False, 'reason': 'No MIRO posted yet'}
```

---

### 7.9 Multi-SoF Version Handling

**Capability:** When multiple SoF versions exist, correctly identify which version determines the DP trigger date.

**Reference Cases:**
- Order 3228005230: 2 SoF approvals -- **first version** determines DP invoice date
- Order 3228005242: Multiple SoF versions -- first version is authoritative

**Rule:** Always use the **earliest** SoF with successful processing status (NAST-VSTAT = '1').

**Agent Logic:**
```
function get_authoritative_sof_date(sales_order):
    sof_records = RFC_READ_TABLE('NAST',
        OBJKY=sales_order,
        KAPPL='V1',
        KSCHL='ZSOV',
        VSTAT='1'  -- successfully processed
    )

    if not sof_records:
        return None, "No SoF found"

    sof_records.sort(key=lambda r: (r.ERDAT, r.ERZET))
    first_sof = sof_records[0]

    if len(sof_records) > 1:
        log(f"Multiple SoF versions found ({len(sof_records)}). "
            f"Using first: {first_sof.ERDAT}")

    return first_sof.ERDAT, f"SoF v1 approved {first_sof.ERDAT}"
```

---

### 7.10 DP Netting on Final Invoice

**Capability:** Verify that the final invoice correctly nets out all prior downpayments and calculate the remaining balance.

**Netting Calculation:**
```
Original Order Value (VBAK-NETWR)
  - Sum of all cleared FAZ documents (sum VBRK-NETWR where FKART='FAZ' and cleared)
  = Expected Final Invoice Amount

Actual Final Invoice (VBRK-NETWR where FKART='F2', last in sequence)
  -- Should match Expected Final Invoice Amount

Discrepancy = Actual - Expected
  -- If |Discrepancy| > threshold: ALERT
```

**Reference Example (Order 3228005113):**
```
Order Value: EUR 2,705,000.00
DP 1 (3851802644): EUR 270,500.00 (10%) -- Cleared
DP 2 (3851802645): EUR 270,500.00 (10%) -- Cleared
Expected Final: EUR 2,164,000.00 (80%)
Actual Invoice (3818015313): EUR 2,705,000.00 (gross, before DP netting in FI)
```

---

## 8. CPI iFlow Specifications

The following SAP CPI iFlows must be developed/configured to expose the required BAPIs as REST endpoints for the Agentic System.

| # | iFlow Name | BAPI / FM Called | Direction | Purpose | Priority |
|---|---|---|---|---|---|
| 1 | **MS5GetBillingPlan** | BILLING_SCHEDULE_READ | MS5 -> Agent | Read billing plan milestones and dates | P0 (Critical) |
| 2 | **MS5GetBillingDocuments** | BAPI_BILLINGDOC_GETLIST + BAPI_BILLINGDOC_GETDETAIL | MS5 -> Agent | All billing docs for an order (DP + Invoice + Proforma) | P0 (Critical) |
| 3 | **MS5GetDocumentFlow** | SD_DOCUMENT_FLOW_GET or VBFA read | MS5 -> Agent | Complete document flow chain for a sales order | P0 (Critical) |
| 4 | **MS5GetOpenARItems** | BAPI_AR_ACC_GETOPENITEMS | MS5 -> Agent | Open receivables for payment clearing status | P0 (Critical) |
| 5 | **MS5GetOrderDetail** | BAPI_SALESORDER_GETDETAIL | MS5 -> Agent | Full sales order with billing plan + items + status | P0 (Critical) |
| 6 | **MS5GetOrderStatus** | BAPI_SALESORDER_GETSTATUS | MS5 -> Agent | Order + per-item billing/delivery/rejection status | P1 (High) |
| 7 | **MS5GetOutputRecords** | RFC_READ_TABLE(NAST) | MS5 -> Agent | SoF (ZSOV) and Order Confirmation (ZEOR) dates. **Security:** iFlow must whitelist NAST table only and enforce KAPPL='V1' server-side. | P1 (High) |
| 8 | **MS5GetCustomerStatement** | BAPI_AR_ACC_GETSTATEMENT | MS5 -> Agent | Full AR statement including DP clearing history | P1 (High) |
| 9 | **MS5GetPOInvoiceReceipt** | BAPI_INCOMINGINVOICE_GETLIST + BAPI_INCOMINGINVOICE_GETDETAIL | MS5 -> Agent | MIRO invoice receipt for vendor PO linkage | P2 (Medium) |
| 10 | **MS5GetPurchaseOrder** | BAPI_PO_GETDETAIL1 | MS5 -> Agent | Vendor PO details linked from sales order | P2 (Medium) |
| 11 | **MS5GetBankGuarantee** | Custom FM / Z-table read (TBD) | MS5 -> Agent | BG tracking data (if available in SAP TRM) | P3 (Low) |

### CPI iFlow Request/Response Formats

**MS5GetBillingPlan (Priority P0):**

Request (plain XML -- matches existing CPI pattern, no SOAP envelope):
```xml
<BILLING_SCHEDULE_READ>
  <VBELN>3228005113</VBELN>
</BILLING_SCHEDULE_READ>
```

Response (mapped to JSON by CPI):
```json
{
  "billing_plan": {
    "plan_number": "0000012345",
    "plan_type": "02",
    "currency": "EUR",
    "total_value": 2705000.00,
    "lines": [
      {
        "sequence": 1,
        "date": "2025-03-18",
        "description": "Down Payment 10%",
        "amount": 270500.00,
        "percentage": 10.0,
        "billing_type": "FAZ",
        "status": "B",
        "billing_block": ""
      },
      {
        "sequence": 2,
        "date": "2025-06-15",
        "description": "2nd Down Payment 10%",
        "amount": 270500.00,
        "percentage": 10.0,
        "billing_type": "FAZ",
        "status": "B",
        "billing_block": ""
      },
      {
        "sequence": 3,
        "date": "2025-09-30",
        "description": "Balance Payment 80%",
        "amount": 2164000.00,
        "percentage": 80.0,
        "billing_type": "F2",
        "status": "B",
        "billing_block": ""
      }
    ]
  }
}
```

**MS5GetDocumentFlow (Priority P0):**

Request (plain XML -- matches existing CPI pattern, no SOAP envelope):
```xml
<SD_DOCUMENT_FLOW_GET>
  <IV_DOCNUM>3228005113</IV_DOCNUM>
</SD_DOCUMENT_FLOW_GET>
```

**Note:** The input parameter name is `IV_DOCNUM`, not `DOCUMENT_NUMBER`.

Response (mapped to JSON by CPI):
```json
{
  "document_flow": [
    {
      "source_doc": "3228005113",
      "source_item": "000010",
      "target_doc": "3851802644",
      "target_item": "000010",
      "target_type": "M",
      "target_type_desc": "Invoice (FKART=FAZ, DP Request)",
      "created_on": "2025-03-18",
      "quantity": 5.0,
      "unit": "UNT",
      "value": 270500.00,
      "currency": "EUR",
      "status": "Completed"
    },
    {
      "source_doc": "3228005113",
      "source_item": "000010",
      "target_doc": "2800009744",
      "target_item": "000010",
      "target_type": "F",
      "target_type_desc": "Purchase Order",
      "created_on": "2025-01-22",
      "quantity": 5.0,
      "unit": "PC",
      "value": 2377702.60,
      "currency": "EUR",
      "status": ""
    }
  ]
}
```

**MS5GetOutputRecords (Priority P1):**

Request (plain XML -- matches existing CPI pattern, no SOAP envelope):
```xml
<RFC_READ_TABLE>
  <QUERY_TABLE>NAST</QUERY_TABLE>
  <DELIMITER>|</DELIMITER>
  <OPTIONS>
    <item><TEXT>OBJKY = '3228005113' AND KAPPL = 'V1' AND KSCHL IN ('ZSOV','ZEOR')</TEXT></item>
  </OPTIONS>
  <FIELDS>
    <item><FIELDNAME>KSCHL</FIELDNAME></item>
    <item><FIELDNAME>ERDAT</FIELDNAME></item>
    <item><FIELDNAME>ERZET</FIELDNAME></item>
    <item><FIELDNAME>VSTAT</FIELDNAME></item>
    <item><FIELDNAME>DAESSION</FIELDNAME></item>
  </FIELDS>
</RFC_READ_TABLE>
```

Response (mapped to JSON by CPI):
```json
{
  "output_records": [
    {
      "output_type": "ZSOV",
      "description": "ENG:SOF (Preview)",
      "created_date": "2025-01-08",
      "created_time": "11:09:43",
      "process_status": "0",
      "process_status_desc": "Not yet processed"
    },
    {
      "output_type": "ZEOR",
      "description": "ENG: Sales Order",
      "created_date": "2025-03-12",
      "created_time": "10:49:01",
      "process_status": "1",
      "process_status_desc": "Successfully processed"
    }
  ]
}
```

---

## 9. Data Model Extensions

The following data models must be added to `src/rrps_lead2cash/core/models.py` to support full downpayment tracking.

### 9.1 New Enums

```python
class DownpaymentCategory(str, Enum):
    """Downpayment scenario category based on RRPS taxonomy."""
    CAT_A_SIMPLE = "SIMPLE_DP_BALANCE"          # Simple % DP + balance
    CAT_B_MULTI_MILESTONE = "MULTI_MILESTONE"    # 3+ milestones
    CAT_C_PROGRESS = "PROGRESS_PAYMENT"          # Prorated progress payments
    CAT_D_MULTI_INSTRUMENT = "MULTI_INSTRUMENT"  # TT + LC + BG
    CAT_E_LARGE_CONTRACT = "LARGE_CONTRACT"      # Multi-shipset periodic
    CAT_F_TERMS_CHANGED = "TERMS_CHANGED"        # Mid-order terms change

class PaymentInstrument(str, Enum):
    """Payment method/instrument."""
    TT = "TT"           # Telegraphic Transfer
    LC_SIGHT = "LC_SIGHT"       # Letter of Credit at sight
    LC_USANCE = "LC_USANCE"     # Usance Letter of Credit (deferred)
    LC_IRREVOCABLE = "LC_IRREVOCABLE"  # Irrevocable LC
    BG = "BG"           # Bank Guarantee (not a payment, but gates payment)
    CREDIT_LINE = "CREDIT_LINE" # Credit line arrangement

class TriggerEventType(str, Enum):
    """Trigger event for downpayment milestone."""
    ORDER_PLACEMENT = "ORDER_PLACEMENT"
    SOF_APPROVAL = "SOF_APPROVAL"
    ORDER_CONFIRMATION = "ORDER_CONFIRMATION"
    PO_RECEIPT = "PO_RECEIPT"
    CONTRACT_SIGNING = "CONTRACT_SIGNING"
    DRAWINGS_SUBMISSION = "DRAWINGS_SUBMISSION"
    DAYS_AFTER_FIRST_PAYMENT = "DAYS_AFTER_FIRST_PAYMENT"
    BEFORE_FCA = "BEFORE_FCA"
    BEFORE_EXW = "BEFORE_EXW"
    BEFORE_SHIPMENT = "BEFORE_SHIPMENT"
    FAT = "FAT"
    SAT = "SAT"
    NOR = "NOR"
    DELIVERY = "DELIVERY"
    EQUIPMENT_ARRIVAL = "EQUIPMENT_ARRIVAL"
    INSTALLATION_COMPLETE = "INSTALLATION_COMPLETE"
    FINAL_ACCEPTANCE = "FINAL_ACCEPTANCE"
    COMMISSIONING = "COMMISSIONING"
    VENDOR_INVOICE_RECEIPT = "VENDOR_INVOICE_RECEIPT"
    BG_RECEIPT = "BG_RECEIPT"
    MONTHS_AFTER_DELIVERY = "MONTHS_AFTER_DELIVERY"
    SPECIFIC_DATE = "SPECIFIC_DATE"

class DPDocumentStatus(str, Enum):
    """Status of a downpayment document.

    MIGRATION NOTE -- Status Mapping from Production FinOps Simulator:
    ┌──────────────────────┬──────────────────────┬────────────────────────────────────┐
    │ Production (current) │ New (this spec)       │ Migration Rule                     │
    ├──────────────────────┼──────────────────────┼────────────────────────────────────┤
    │ OPEN                 │ REQUESTED            │ Rename: OPEN → REQUESTED           │
    │ CLEARED              │ PAID                 │ Rename: CLEARED → PAID             │
    │ OVERDUE              │ OVERDUE              │ No change                          │
    │ (n/a)                │ PARTIALLY_PAID       │ New: BSEG partial clearing         │
    │ (n/a)                │ CANCELLED            │ New: VBRK-FKSTO='X'               │
    │ (n/a)                │ BLOCKED              │ New: FAKSP populated               │
    └──────────────────────┴──────────────────────┴────────────────────────────────────┘

    Gateway API must accept BOTH old and new values during transition.
    Existing FinOpsSimulator (finops_simulator.py) returns CLEARED/OPEN/OVERDUE.
    The FinOpsDataService layer should translate old→new at the boundary.
    """
    REQUESTED = "REQUESTED"       # FAZ created, FI doc open (was: OPEN)
    PAID = "PAID"                 # FI doc cleared (was: CLEARED)
    PARTIALLY_PAID = "PARTIALLY_PAID"  # NEW: partial clearing
    OVERDUE = "OVERDUE"           # Past due date, not cleared
    CANCELLED = "CANCELLED"       # NEW: VBRK-FKSTO = 'X' or cancellation doc exists
    BLOCKED = "BLOCKED"           # NEW: Billing block active (FAKSP populated)

class BGStatus(str, Enum):
    """Bank Guarantee lifecycle status."""
    PENDING = "PENDING"
    ISSUED = "ISSUED"
    ACTIVE = "ACTIVE"
    EXPIRED = "EXPIRED"
    RELEASED = "RELEASED"
```

### 9.2 New Data Models

```python
class DownpaymentPlan(BaseModel):
    """Billing plan extracted from SAP FPLA/FPLT."""
    sales_order: str
    plan_number: str
    plan_type: str             # "01"=Periodic, "02"=Milestone
    currency: str
    total_plan_value: Decimal
    category: DownpaymentCategory
    milestones: List[PaymentMilestone]
    source: str = "SAP_MS5"

class PaymentMilestone(BaseModel):
    """Single milestone from billing plan date line (FPLT table, keyed by FPLTR sequence)."""
    milestone_index: int
    description: str           # FPLT-TETXT
    amount: Optional[Decimal]  # FPLT-FAKWR (absolute)
    percentage: Optional[Decimal]  # FPLT-BETEFP
    billing_type: str          # FAZ, F2, ZF2P
    due_date: Optional[date]   # FPLT-FDATU
    trigger_event: TriggerEventType
    trigger_offset_days: int = 0
    payment_instrument: PaymentInstrument
    status: DPDocumentStatus
    is_blocked: bool           # FPLT-FAKSP populated
    billing_documents: List[str] = []  # Linked VBRK-VBELN
    requires_bg: bool = False
    bg_reference: Optional[str] = None

class DownpaymentRequest(BaseModel):
    """Individual DP request document from SAP VBRK/VBRP."""
    document_number: str       # VBRK-VBELN (3851xxxxxx)
    document_type: str         # VBRK-FKART (FAZ)
    billing_date: date
    customer_id: str
    payer_id: str
    amount: Decimal
    currency: str
    payment_terms_key: str
    payment_method: Optional[str]
    is_cancelled: bool
    sales_order: str           # VBRP-AUBEL
    sales_order_item: str      # VBRP-AUPOS
    material: Optional[str]
    billed_quantity: Decimal
    fi_document: Optional[str]
    clearing_date: Optional[date]
    clearing_document: Optional[str]
    status: DPDocumentStatus
    is_proforma: bool = False  # True if FKART in (ZF2P, F8)

class DocumentFlowEntry(BaseModel):
    """Single entry in the SAP document flow (VBFA)."""
    source_document: str
    source_item: str
    target_document: str
    target_item: str
    target_type: str           # VBTYP_N code
    target_type_desc: str
    created_on: date
    quantity: Optional[Decimal]
    value: Optional[Decimal]
    currency: Optional[str]
    status: Optional[str]

class BankGuarantee(BaseModel):
    """Bank Guarantee tracking (external to SAP standard)."""
    bg_reference: Optional[str]
    sales_order: str
    bg_type: str               # ADVANCE_PAYMENT, PERFORMANCE, RETENTION
    amount: Decimal
    currency: str
    percentage: Optional[Decimal]
    issued_date: Optional[date]
    expiry_date: Optional[date]
    expiry_condition: str
    status: BGStatus
    gates_milestone: str       # Which milestone this BG gates
    source: str = "MANUAL"

class VendorInvoiceReceipt(BaseModel):
    """MIRO invoice receipt from RBKP/RSEG."""
    receipt_number: str        # RBKP-BELNR (1802xxxxxx)
    fiscal_year: str
    invoice_date: date         # RBKP-BLDAT
    posting_date: date         # RBKP-BUDAT
    vendor_id: str
    gross_amount: Decimal
    currency: str
    po_number: str             # RSEG-EBELN
    po_item: str               # RSEG-EBELP
    triggers_customer_invoice: bool = True

class DownpaymentSummary(BaseModel):
    """Comprehensive DP summary for a sales order."""
    sales_order: str
    customer_id: str
    customer_name: str
    order_value: Decimal
    currency: str
    category: DownpaymentCategory
    plan: DownpaymentPlan
    dp_requests: List[DownpaymentRequest]
    document_flow: List[DocumentFlowEntry]
    bank_guarantees: List[BankGuarantee]
    vendor_invoices: List[VendorInvoiceReceipt]
    total_dp_requested: Decimal
    total_dp_paid: Decimal
    total_dp_outstanding: Decimal
    remaining_balance: Decimal
    next_milestone: Optional[PaymentMilestone]
    alerts: List[str]          # Active alerts/flags
    terms_changed: bool
    has_rejected_items: bool
    has_position_replacement: bool
```

---

## 10. Agent-Derived vs SAP-Direct Fields

| Field Category | SAP-Direct (Read from CPI) | Agent-Derived (Mapping/Logic Required) |
|---|---|---|
| **DP Category** | -- | Derived from billing plan structure (line count, billing types, amounts vs percentages) |
| **Trigger Event Type** | FPLTR-TETXT (free text) | NLP parsing of milestone description text to TriggerEventType enum |
| **Trigger Date** | FPLTR-FDATU (if populated) | Calculated from SoF date / PO date / delivery date + offset |
| **Payment Instrument** | VBRK-ZLSCH, VBKD-ZLSCH | Parsed from payment terms text (VBKD-ZTERM free text) |
| **DP Status** | FPLTR-FKSAF (billing status) | Cross-referenced with BSEG clearing to determine PAID/OPEN/OVERDUE |
| **Position Replacement** | VBUP-ABSTA per item | Agent matches rejected items to replacement items by material |
| **Terms Changed** | VBKD-AEDAT vs VBAK-ERDAT | Agent compares dates + checks for rejected items + multiple SoF versions |
| **BG Status** | Not in SAP standard | External tracking, manual input |
| **Proforma Flag** | VBRK-FKART | Agent checks: FAZ/F2 = collection, ZF2P/F8 = proforma only |
| **Vendor Invoice Trigger** | RBKP-BUDAT | Agent traverses VBFA -> EKKO -> RBKP to find trigger date |
| **Netting Calculation** | VBAK-NETWR, VBRK-NETWR | Agent sums all cleared FAZ docs and subtracts from order value |
| **LC Deadline** | -- | Agent calculates delivery date minus offset from parsed terms text |
| **PSI Stage %** | VBAP-ARKTX | Agent parses "PSI - PHASE_1" and maps to 30%/40%/30% |
| **Combined Milestone** | -- | Agent detects when multiple billing plan lines are invoiced together |

---

## 11. Appendix: Case Reference Matrix

| # | Sales Order | PO Reference | Category | DP % | Milestones | Payment Method | Key Complexity | DP Docs | Invoice Docs |
|---|---|---|---|---|---|---|---|---|---|
| 1 | 3228005113 | MU100628 | B (Multi) | 10+10+80 | OC, 90d before FCA, FCA | TT/TT/TT | Multi-position (4 items), vendor PO linkage | 3851802644, 3851802645 | 3818015313 |
| 2 | 3228005124 | M04.MTU.DP.2025 | B (Multi) + F (Changed) | 4.9+15.1+80.2 | OC, 60d after 1st pmt, L/C 30d at sight | TT/TT/LC | Position replacement (pos 10/20 -> 30/40), MIRO trigger | Multiple | Multiple |
| 3 | 3228005142 | BB0735-02 | D (Multi-Instr) + F (Changed) | Fixed amounts | 6 payment lines | TT+LC+BG | Terms changed, BG gating, item category restructuring, pos 10 rejected | Multiple | Multiple |
| 4 | 3228005143 | PO2502044 | A (Simple) | 20+80 | PO receipt (SoF), before collection | TT/TT or LC | DP on pos 10/20 but invoice on pos 30, different materials | 3851802687, 3851802709 | via pos 30 delivery |
| 5 | 3228005147 | 250303SG-R1 | A (Simple) | 20+80 | SoF approval, NOR | TT/TT | Split DP (2 docs), PO linkage | 3851802713, 3851802753 | 3818015229 |
| 6 | 3228005168 | (none) | B (Multi) | 10+10+80 | Order placement, drawings, EXW | TT/TT/TT | Unknown trigger (drawings), 3 identical positions, 9 DP docs total | 9 docs (3 per position) | 3818015445 x3 |
| 7 | 3228005171 | PO 3450000475 | C (Progress) | DP + Balance + PSI 30/40/30 | PO, LC, work completion | TT/LC/TT | 16 line items, 12 DP billing docs, PSI phases, accessories | 3851802721-742 | Per engine |
| 8 | 3228005185 | PO-39.0525 | A (Simple) | 20+80 | Order placement, EXW | TT/TT + 5% BG | 2 POs consolidated, 4 DP docs, BG required | 3851802749/750/879/880 | Pending |
| 9 | 3228005208 | 4500069874 | C (Progress) | 15+50+25+5+5 | BG receipt, arrival, install, SAT, final | TT/LC/LC/LC | Progress payment prorated per DUPS, proforma, 15% BG, SGD currency | 3851802837 | 3868003805 (proforma) |
| 10 | 3228005221 | MJ25MK-016 | A (Simple) | 20+80 | 30d upon invoice, credit line/alt terms | TT/TT or LC | DP delay unexplained, alternative payment terms | 3851802864 | Pending |
| 11 | 3228005227 | FFX-III-MF-2 | D (Multi-Instr) | 30+70 | Contract signing + counter guarantee, 6w before shipment | TT/LC irrevocable | Contract signing date not in SAP, counter guarantee gate | 3851802901 | Pending |
| 12 | 3228005230 | 4516421220 | B (Multi) | 15+80+5 | PO receipt, FAT, customer receipt | TT/TT/TT | 2 SoF versions, first determines DP date | 3851802836 | Pending |
| 13 | 3228005242 | 25-011/USF | A (Simple) | 20+80 | 14d upon PO, LC 30d before shipment | TT/LC | Multiple SoF versions, proforma issued | 3851802840 | 3868003811 (proforma) |
| 14 | 3228005268 | PO-251210301 | A (Simple) | 20+80 | Order placement, 45d upon NOR | TT/TT + 10% BG | BG against 80% payment | 3851802842 | Pending |
| 15 | 3228004906 | Sales Contract | E (Large) | 10+20+65+5 + VO | 12m before delivery, 30d before delivery, 60d Usance, 60d after delivery | TT/LC sight/LC Usance/TT | 5 shipsets x 20 units, 30+ doc flow entries, MIRO linkage, VO, combined proforma | Many (periodic) | 3868003712 (combined proforma) |

---

## 12. Invoice Cancellation & Replacement Handling

**Source:** Order 3228005124 -- pos 30/40 each show: Proforma 3868003794 -> Invoice 3818015386 -> Invoice Cancell. 3891800429 -> Invoice 3818015387

### 12.1 Cancellation Detection

| SAP Indicator | Field | Meaning |
|---|---|---|
| VBRK-FKSTO = 'X' | Cancelled flag on original invoice | This billing doc is void |
| FKART = S1 or ZS1 | Billing type of cancellation document | This IS the cancellation document |
| Number range 3891xxxxxx | Cancellation doc number | Identifies cancellation vs invoice |
| Same date as original | VBRK-FKDAT | Cancellations typically posted same day |

### 12.2 Agent Logic

```
function reconcile_billing_documents(sales_order):
    all_docs = BAPI_BILLINGDOC_GETLIST(REF_DOC_RANGE=sales_order)

    active_docs = []
    cancelled_docs = []

    for doc in all_docs:
        detail = BAPI_BILLINGDOC_GETDETAIL(doc.VBELN)
        if detail.HEADER.FKSTO == 'X':
            cancelled_docs.append(doc)
        elif detail.HEADER.FKART in ('S1', 'ZS1'):
            -- This is the cancellation document itself
            cancelled_docs.append(doc)
        else:
            active_docs.append(doc)

    -- Link cancellations to their replacements
    for cancelled in cancelled_docs:
        replacement = find_replacement_invoice(cancelled, active_docs)
        if replacement:
            log(f"Invoice {cancelled.VBELN} cancelled, replaced by {replacement.VBELN}")

    -- Only track active (non-cancelled) documents for receivables
    return active_docs
```

### 12.3 Impact on Receivables

```
Correct Outstanding = Sum of active invoices - Sum of cleared payments
                    (EXCLUDE all cancelled docs from both sides)

Common Error: Double-counting original + replacement = 2x overstated receivables
```

---

## 13. DP Invoice Delay Analysis

**Source:** Orders 3228005142 (SoF March, DP May due to BG), 3228005221 (SoF 15.10.25, DP delayed)

### 13.1 Delay Calculation

```
function analyse_dp_delay(sales_order):
    -- Get expected trigger date
    trigger_date = derive_dp_trigger_date(sales_order, trigger_type)

    -- Get actual DP document date
    dp_docs = BAPI_BILLINGDOC_GETLIST(REF_DOC_RANGE=sales_order, FKART='FAZ')
    first_dp = min(dp_docs, key=lambda d: d.FKDAT)
    actual_dp_date = first_dp.FKDAT

    delay_days = (actual_dp_date - trigger_date).days

    if delay_days <= 7:
        return "ON_TIME"
    elif delay_days <= 30:
        root_cause = investigate_delay(sales_order, trigger_date, actual_dp_date)
        return f"MINOR_DELAY: {delay_days} days. Cause: {root_cause}"
    else:
        root_cause = investigate_delay(sales_order, trigger_date, actual_dp_date)
        return f"SIGNIFICANT_DELAY: {delay_days} days. Cause: {root_cause}"

function investigate_delay(sales_order, trigger_date, actual_date):
    -- Check for BG dependency
    if has_bg_requirement(sales_order):
        bg = get_bg_status(sales_order)
        if bg.issued_date and bg.issued_date > trigger_date:
            return f"BG_WAIT: BG issued {bg.issued_date}, {(bg.issued_date - trigger_date).days} days after trigger"

    -- Check for billing block
    items = GET_ORDER_ITEMS(sales_order)
    blocked = [i for i in items if i.FAKSP]
    if blocked:
        return f"BILLING_BLOCK: {len(blocked)} items had billing block"

    -- Check for SoF re-approval
    sof_records = RFC_READ_TABLE('NAST', OBJKY=sales_order, KSCHL='ZSOV')
    if len(sof_records) > 1:
        return f"SOF_REAPPROVAL: {len(sof_records)} SoF versions, latest {sof_records[-1].ERDAT}"

    return "UNKNOWN: Manual investigation required"
```

---

## 14. Known Limitations & Human-in-the-Loop Requirements

The following scenarios CANNOT be fully automated and require manual confirmation from the operations team:

| # | Scenario | Reason | Agent Action | Ref Case |
|---|---|---|---|---|
| 1 | Contract Signing Date | Date not recorded in SAP -- purely commercial event | Flag as `MANUAL_CONFIRMATION_REQUIRED`, prompt user to enter date | 3228005227 |
| 2 | Drawings/Documentation Submission | No SAP trigger for engineering document delivery | Flag as `MANUAL_CONFIRMATION_REQUIRED`, prompt user to confirm submission date | 3228005168 |
| 3 | Bank Guarantee Receipt | BG issuance is external to SAP SD -- may be in TRM module (TBD) | Track as external event, prompt user for BG reference + date when received | 3228005142, 5185, 5208, 5227, 5268 |
| 4 | Equipment Arrival at Job Site | Delivery confirmation may not reach SAP in real-time | Monitor delivery status (LIKP), but flag for manual confirmation of actual site arrival | 3228005208 |
| 5 | Installation Completion | Service confirmation required from field team | Flag as `MANUAL_CONFIRMATION_REQUIRED`, prompt for SAP service confirmation number | 3228005208 |
| 6 | Final Acceptance | Customer sign-off event, not in SAP standard | Flag as `MANUAL_CONFIRMATION_REQUIRED` | 3228005208 |
| 7 | Work Completion Certificate (PSI) | External document required for PSI stage billing | Prompt user to upload/confirm work completion cert + SAP Service Sheet | 3228005171 |
| 8 | "90 days before FCA within 30 days" | Client's own notes indicate ambiguity in this payment term interpretation | Flag for commercial team clarification | 3228005113 |

**Design Principle:** For all LOW-confidence triggers, the agent will:
1. Calculate the estimated date using best available data
2. Display the estimate with a `REQUIRES_CONFIRMATION` badge
3. Create a task for the responsible user to confirm or override
4. Only proceed with billing-related actions after human confirmation

---

## 15. Gateway API Endpoints (New)

The following endpoints must be added to `gateway.py` to expose downpayment tracking to the dashboard and agents:

```
GET  /api/v1/finops/downpayment/{sales_order}
     --> DownpaymentSummary (comprehensive DP overview for an order)

GET  /api/v1/finops/billing-plan/{sales_order}
     --> DownpaymentPlan (billing plan milestones and dates)

GET  /api/v1/finops/document-flow/{sales_order}
     --> List[DocumentFlowEntry] (complete document chain)

GET  /api/v1/finops/dp-status/{billing_doc}
     --> DownpaymentRequest + PaymentClearing (individual DP doc with clearing)

GET  /api/v1/finops/vendor-invoice/{sales_order}
     --> List[VendorInvoiceReceipt] (MIRO receipts linked to order)

GET  /api/v1/finops/dp-delay/{sales_order}
     --> DelayAnalysis (expected vs actual DP date with root-cause)
```

These endpoints follow the existing pattern of `/api/v1/finops/...` routes and use the same authentication (`X-API-Key` via `verify_api_key()` dependency).

---

## 16. CPI iFlow Consolidation Recommendation

The 11 iFlows in Section 8 can be consolidated to **5-7 production iFlows** by combining related BAPI calls within a single iFlow. This reduces CPI development effort and simplifies monitoring.

| Consolidated iFlow | Combines | BAPIs Called | Rationale |
|---|---|---|---|
| **MS5GetOrderComplete** | MS5GetOrderDetail + MS5GetOrderStatus | BAPI_SALESORDER_GETDETAIL + BAPI_SALESORDER_GETSTATUS | Both operate on same sales order; single round-trip returns header + items + status |
| **MS5GetBillingComplete** | MS5GetBillingDocuments + MS5GetBillingPlan | BAPI_BILLINGDOC_GETLIST + BAPI_BILLINGDOC_GETDETAIL + BILLING_SCHEDULE_READ | Billing plan + billing docs are always queried together for DP tracking |
| **MS5GetARStatus** | MS5GetOpenARItems + MS5GetCustomerStatement | BAPI_AR_ACC_GETOPENITEMS + BAPI_AR_ACC_GETSTATEMENT | Both are AR queries on same customer; consolidate to reduce calls |
| **MS5GetDocumentFlow** | Keep separate | SD_DOCUMENT_FLOW_GET | Standalone -- used broadly across all agents |
| **MS5GetOutputRecords** | Keep separate | RFC_READ_TABLE(NAST) | Standalone -- security-sensitive, keep isolated |
| **MS5GetProcurement** | MS5GetPOInvoiceReceipt + MS5GetPurchaseOrder | BAPI_PO_GETDETAIL1 + BAPI_INCOMINGINVOICE_GETLIST/GETDETAIL | Procurement chain is always traversed end-to-end |
| **MS5GetBankGuarantee** | Keep separate (P3) | Custom FM / Z-table (TBD) | Low priority; depends on TRM availability |

**Note:** This matches the existing CPI pattern where `Integrum/RequestTableData` consolidates multiple table reads into a single iFlow.

---

## 17. Rate Limiting & Batching Strategy

### 17.1 CPI Call Budgets

To prevent excessive SAP load, the Agentic System must enforce rate limits per iFlow:

| iFlow | Max Calls/Min | Max Calls/Hour | Batch Size | Notes |
|---|---|---|---|---|
| MS5GetOrderComplete | 30 | 500 | 10 orders/batch | Use batch mode for scheduled scans |
| MS5GetBillingComplete | 20 | 300 | 5 orders/batch | Billing doc detail is expensive |
| MS5GetDocumentFlow | 30 | 500 | 10 orders/batch | Lightweight read |
| MS5GetARStatus | 10 | 100 | 1 customer/call | Customer-level, not order-level |
| MS5GetOutputRecords | 20 | 300 | 10 orders/batch | RFC_READ_TABLE supports IN-list filters |
| MS5GetProcurement | 10 | 100 | 5 POs/batch | Lower priority, less frequent |

### 17.2 Batching Patterns

```
-- Scheduled scan (runs every 4 hours for active orders)
function scheduled_dp_scan():
    active_orders = get_orders_with_open_dp()  -- from local DB
    batches = chunk(active_orders, size=10)

    for batch in batches:
        billing_data = MS5GetBillingComplete(batch)
        ar_data = MS5GetARStatus(unique_customers(batch))
        process_dp_updates(billing_data, ar_data)
        rate_limit_pause(2 seconds)  -- prevent SAP overload

-- Event-driven (triggered by status change or user action)
function on_demand_dp_check(sales_order):
    -- Single order, no batching needed
    data = MS5GetBillingComplete([sales_order])
    flow = MS5GetDocumentFlow(sales_order)
    return merge(data, flow)
```

---

## 18. CPI Error Handling

### 18.1 Error Response Patterns

All CPI iFlows must return standardized error responses:

```json
{
  "error": {
    "code": "SAP_RFC_ERROR",
    "message": "BAPI returned errors",
    "details": [
      {"type": "E", "message": "No billing documents found", "id": "VF", "number": "042"}
    ],
    "sap_return": [...]
  }
}
```

### 18.2 Retry Strategy

| Error Type | HTTP Status | Retry | Max Retries | Backoff |
|---|---|---|---|---|
| SAP system unavailable | 503 | Yes | 3 | Exponential (2s, 4s, 8s) |
| RFC timeout | 504 | Yes | 2 | Linear (5s, 10s) |
| Authorization failure | 401/403 | No | 0 | Re-authenticate via OAuth |
| No data found | 200 (empty) | No | 0 | Expected state, not error |
| BAPI business error | 200 (with RETURN type='E') | No | 0 | Log and surface to agent |
| Rate limit exceeded | 429 | Yes | 5 | Exponential (1s, 2s, 4s, 8s, 16s) |

### 18.3 Circuit Breaker

If a CPI iFlow returns 3+ consecutive 5xx errors within 5 minutes:
1. Open circuit breaker for that iFlow
2. Return cached data (if available and < 4 hours old)
3. Alert ops team via existing notification channel
4. Half-open after 5 minutes (allow 1 test call)
5. Close circuit on successful test call

---

## 19. Items Requiring Client Tech Team Confirmation

| # | Question | Impact | Priority |
|---|---|---|---|
| 1 | What is the FKART code for proforma invoices? (F5, F8, ZF2P, or other?) | Correct proforma vs collection differentiation | P0 |
| 2 | What is the FKART code for invoice cancellation? (S1, ZS1, or other?) | Invoice cancellation handling logic | P0 |
| 3 | Is RFC_READ_TABLE permitted on production MS5, or must NAST be wrapped in a custom FM? | SoF/ZEOR date retrieval iFlow design | P1 |
| 4 | Does RRPS store Bank Guarantee data in SAP TRM module? | Determines if MS5GetBankGuarantee iFlow is feasible | P1 |
| 5 | Which Z-tables/custom structures hold FAT/SAT/NOR confirmation dates? | Milestone trigger date derivation | P1 |
| 6 | Can the client provide the full T052/T052U (ZTERM payment terms) table? | PaymentTermsHarmonizer reference data | P1 |
| 7 | Are there billing block codes beyond 01 used in RRPS? | Complete billing block interpretation | P2 |
| 8 | Is Purchase Requisition (BANF/EBAN) relevant for agent monitoring, or only Purchase Order? | Scope of procurement chain tracking | P2 |

---

## End of Document

**Next Steps for Client Tech Team:**
1. **Priority P0 iFlows** (MS5GetBillingPlan, MS5GetBillingDocuments, MS5GetDocumentFlow, MS5GetOpenARItems, MS5GetOrderDetail) must be developed first
2. **NAST access** (MS5GetOutputRecords) is critical for SoF/OC date derivation -- confirm if RFC_READ_TABLE is permitted or if a custom FM wrapper is needed
3. **Bank Guarantee tracking** -- confirm if BG data exists in SAP TRM module; if not, external tracking model will be used
4. **Milestone confirmation tables** -- confirm which Z-tables or custom structures hold FAT/SAT/NOR confirmation dates
5. **Payment terms text parsing** -- provide a sample set of VBKD-ZTERM free-text values for NLP training of the TriggerEvent classifier

---

*Document prepared by Integrum / Kailash AI for RRPS Lead-to-Cash POV*
*Based on analysis of 15 production sales orders, Company Code 0011, Transaction Type ZE06, Period 2025*
