# ADR-003: Billing Plan Integration via SAP CPI

**Status:** ANSWERED — Simulator data is the correct approach for POV scope
**Date:** 2026-04-23 (updated 2026-05-28)
**Author:** Integrum / Kailash AI
**Deciders:** Shyy San, Srinivas Nelacuditi (RRPS CPI)

---

## Context

The billing & collections dashboard requires milestone-level billing plan data from SAP sales orders. The UI shows a "To Bill" / "To Collect" view with per-milestone due dates, amounts, descriptions, billing blocks, and overdue status.

### Current State
- `finops_simulator.py` has hardcoded static billing data for 3 demo customers
- No real SAP billing plan data is consumed
- The simulator models post-billing-document state only (DownPayment records with clearing dates)
- It does not model the pre-billing phase (billing plan milestones that have not yet been invoiced)

### Available CPI iFlows (transported to QA 2026-04-23)
| iFlow | Integrated? | Purpose |
|-------|-------------|---------|
| `Integrum/RequestTableData` | YES | Credit + customer master |
| `Integrum/GetOpportunity` | YES | CEC opportunities |
| `Integrum/GetSOPaymentTerms` | TESTED | Returns `RFC_READ_TEXT.Response` with empty `TEXT_LINES` — NOT billing plan data |
| `Integrum/GetProduct` | **NO** | Product data (TBC — not yet integrated into rrps_lead2cash) |

### The Problem (Resolved 2026-05-28)
The iFlow is named `GetSOPaymentTerms`. Investigation confirmed it returns **neither Option A nor Option B**:

- **Option A:** Payment terms only (VBKD-ZTERM) — a single code + text — **NOT returned**
- **Option B:** Billing plan milestones (FPLA/FPLT) — multi-row schedule with dates, amounts, status — **NOT returned**
- **Actual:** `RFC_READ_TEXT.Response` with empty `TEXT_LINES` — the iFlow wraps an RFC_READ_TEXT call that reads sales order header text, but returns no parseable billing plan data or structured payment terms

### What GetSOPaymentTerms Actually Returns
The iFlow calls `RFC_READ_TEXT` (not `BILLING_SCHEDULE_READ` or a VBKD read). The response contains:
- `RFC_READ_TEXT.Response` envelope
- `TEXT_LINES` element — **empty** (no text content for tested orders)
- No billing plan structure (FPLA/FPLT tables)
- No payment terms code (VBKD-ZTERM)
- No milestone dates, amounts, or statuses

This means billing plan milestones are **NOT available** via any current CPI iFlow.

---

## Decision

**ANSWERED** — The simulator approach (`finops_simulator.py`) is correct for the POV scope.

### Rationale
1. `GetSOPaymentTerms` returns `RFC_READ_TEXT` with empty text lines — not billing plan data
2. Billing plan milestones require `BILLING_SCHEDULE_READ` (FPLA/FPLT) — no iFlow exists for this
3. Structured payment terms require VBKD-ZTERM — not exposed by this iFlow
4. The CPI_SIMULATOR provides realistic billing/payment data derived from actual SAP reference orders
5. All simulator responses are clearly labeled with `"source": "CPI_SIMULATOR"` to distinguish from real CPI data
6. A future iFlow (`MS5GetBillingPlan` per interface spec) would be needed to replace the simulator

### Preliminary Design (contingent on Option B confirmation)

#### Storage: PostgreSQL (not SQLite)
- PostgreSQL is already in the production docker-compose stack (pgvector/pgvector:pg15)
- SQLite is unsuitable because the Dockerfile runs `--workers 4` (4 uvicorn processes), and SQLite does not support concurrent writes from multiple processes
- Redis is also available for caching/locking if needed

#### Scheduling: External cron (not APScheduler)
- APScheduler in a multi-worker uvicorn process creates N schedulers (one per worker), causing duplicate CPI calls and write contention
- A simple cron job (`curl -X POST .../billing-plans/sync`) avoids this entirely
- Manual trigger endpoint also provided for demos

#### Data Sources Required (TWO, not one)
The dashboard requires data from two distinct sources:

| Dashboard Category | Data Source | SAP BAPI/FM |
|--------------------|-------------|-------------|
| **To Bill** (unbilled milestones) | Billing plan lines | `BILLING_SCHEDULE_READ` (FPLA/FPLT) |
| **To Collect** (billed, unpaid) | AR open items | `BAPI_AR_ACC_GETOPENITEMS` (BSEG clearing status) |

Using billing plan status (FPLT-FKSAF) alone is insufficient:
- FKSAF='A' → no billing document → **To Bill**
- FKSAF='B'/'C' → billing document exists → but is it paid?
  - BSEG-AUGDT blank → **To Collect**
  - BSEG-AUGDT populated → **Collected** (done)

An additional iFlow for AR open items (`MS5GetOpenARItems` in the interface spec) is needed.

#### Milestone Due Date Derivation (Confirmed by RRPS Business)
The milestone due date (FPLT-FDATU) is NOT an arbitrary date — it is derived from specific SAP events:

| Milestone Type | FDATU Source | SAP Object |
|---|---|---|
| **Downpayment (FAZ)** | Sales Order Form (SoF/ZSF) release date | ZSF document status date via `NAST-ERDAT` WHERE KSCHL='ZSOV' |
| **Progress/Balance (F2)** | Sales Order Item First Delivery Date | `VBAP-EDATU` or `VBEP-EDATU` |

This was confirmed with reference to order 3228005147 (ST Engineering) where:
- SoF released 29 May 2025 → DP milestone FDATU = 2025-05-29
- Item delivery date 23 May 2026 → Balance milestone FDATU = 2026-05-23

#### Order Discovery: Explicit registry (POV limitation)
- CPI does not support "give me all open orders"
- For the POV, we maintain a configured list of sales orders to track
- Initial list: 3228005147, 3228006201, 3228007450
- Configurable via environment variable `BILLING_SYNC_ORDERS`

#### Migration: Replace finops simulator (not parallel)
- New billing plan data replaces the finops simulator for orders with real CPI data
- Simulator becomes fallback-only for orders not yet synced
- Single API path with `source` field indicating data origin ("SAP_CPI" vs "CPI_SIMULATOR")

---

## Red Team Findings (2026-04-23)

| ID | Severity | Finding | Mitigation |
|----|----------|---------|------------|
| CRITICAL-01 | CRITICAL | iFlow name suggests payment terms (ZTERM), not billing plan (FPLA/FPLT) | **RESOLVED**: Confirmed — returns RFC_READ_TEXT, not FPLA/FPLT or ZTERM |
| CRITICAL-02 | CRITICAL | to_bill vs to_collect needs BSEG clearing data, not just FPLT-FKSAF | Deferred to post-POV (requires MS5GetOpenARItems iFlow) |
| CRITICAL-03 | CRITICAL | No mechanism to discover which orders to poll | N/A for POV (simulator uses known order list) |
| CRITICAL-04 | CRITICAL | SQLite + 4 uvicorn workers = write contention | N/A for POV (simulator uses in-memory data, no DB) |
| CRITICAL-05 | CRITICAL | APScheduler + 4 workers = 4 concurrent schedulers | N/A for POV (no scheduler needed with simulator) |
| CRITICAL-06 | CRITICAL | Response format is completely unverified | **RESOLVED**: QA tested — RFC_READ_TEXT with empty TEXT_LINES |
| HIGH-01 | HIGH | Interface spec already defines MS5GetBillingPlan, not GetSOPaymentTerms | **RESOLVED**: GetSOPaymentTerms is not a billing plan iFlow; MS5GetBillingPlan needed post-POV |
| HIGH-02 | HIGH | Overdue calculation differs for to_bill vs to_collect | Separate overdue logic per category |
| HIGH-03 | HIGH | Two conflicting data sources (new + finops simulator) | Replace, don't parallel |
| HIGH-04 | HIGH | No CPI downtime handling | Add staleness indicator, retry logic |
| MEDIUM-01 | MEDIUM | SHA-256 change detection is fragile | Compare individual business fields |
| MEDIUM-02 | MEDIUM | Financial data in local storage needs encryption | Use PostgreSQL with proper access control |
| MEDIUM-03 | MEDIUM | APScheduler is over-engineering for a single daily job | Cron + manual endpoint is simpler |

---

## Resolution History

1. **QA endpoint tested** (2026-04-23): `GetSOPaymentTerms` called with order 3228005147 — returned `RFC_READ_TEXT.Response` with empty `TEXT_LINES`
2. **Response format confirmed**: Neither Option A (VBKD-ZTERM) nor Option B (FPLA/FPLT) — the iFlow reads order header text via RFC_READ_TEXT
3. **Decision**: Simulator data is the correct approach for POV scope. All responses labeled `"source": "CPI_SIMULATOR"`

## Future Steps (Post-POV)

1. **Request `MS5GetBillingPlan` iFlow** from CPI team for real billing plan milestones (FPLA/FPLT)
2. **Request AR open items iFlow** (`MS5GetOpenARItems`) for "To Collect" logic (BSEG clearing status)
3. **When available**: Replace `finops_simulator.py` with real CPI data, maintaining `source` field as `"SAP_CPI"`

---

## GetProduct iFlow Status (2026-05-28)

The `Integrum/GetProduct` iFlow was transported to QA on 2026-04-23 alongside GetSOPaymentTerms.

### Current State
- **QA testing**: Attempted via `scripts/test_qa_cpi.py` and `scripts/test_qa_cpi_v2.py` with MATNR and ProductID input formats
- **SAPCPIClient**: No `get_product` method exists — the iFlow is not integrated into the rrps_lead2cash application
- **Input format**: Unknown — tested with `<MATNR>MTU</MATNR>` and `<ProductID>MTU</ProductID>`, response format TBC
- **Usage**: Product data is not currently required by any POV endpoint. IPAS XML files already contain product/engine data for order entry

### Decision
Not integrated for POV scope. Product data from IPAS XML is sufficient. If product catalog lookup is needed post-POV, implement a `get_product()` method in `SAPCPIClient` following the same pattern as `get_credit_check()` and `get_opportunities()`.

---

## References

- Interface Specification: `docs/RRPS_Downpayment_Interface_Specification.md` (Sections 5-8)
- Red Team Report: `docs/RRPS_Downpayment_RedTeam_Report.md`
- Shortlist Cases: `C:\Users\fujif\OneDrive\Desktop\0011-20250101-20251231-TXID-ZE06 - shortlist cases.docx`
- CPI QA Endpoints: `https://rrps-qa.it-cpi005-rt.cfapps.eu20.hana.ondemand.com/http/Integrum/GetSOPaymentTerms`
