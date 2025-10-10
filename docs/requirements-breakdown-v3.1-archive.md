# RRPS Lead-to-Cash POV: Requirements Breakdown (v3.1 - Resilience & Edge Cases)

**Document Version:** 3.1
**Date:** 2025-10-10
**Status:** Critique-Driven Refinement
**POV Duration:** 10 Weeks
**Framework:** Core SDK + Nexus Multi-Channel Platform

---

## Document Change Log

| Version | Date | Changes | Author |
|---------|------|---------|--------|
| 1.0 | 2025-10-10 | Initial breakdown (developer-centric) | Requirements Analyst |
| 2.0 | 2025-10-10 | User stories rewritten from business user perspectives | Requirements Analyst |
| 3.0 | 2025-10-10 | **MAJOR RESTRUCTURE:** Epics reorganized by value chain; user stories focus on business outcomes; technical tasks moved to "Technical Enablers" | Product Manager |
| 3.1 | 2025-10-10 | **CRITIQUE-DRIVEN REFINEMENT:** Added 4 new TEs (23-26), expanded TE-5/TE-6 with timeout/idempotency/error handling, added edge case criteria to Stories 2.2/3.1/4.2, created KPI definition table, adjusted targets (POV vs. Production) | Claude Code + Specialized Agents |

### Critical Changes in v3.1 (Critique-Driven Refinement)

**Problem Addressed:**
Version 3.0 user stories lacked critical resilience, error handling, and edge case specifications identified through comprehensive multi-agent critique (requirements-analyst, ultrathink-analyst, testing-specialist, pattern-expert).

**v3.1 Improvements:**

1. **Missing Technical Enablers Added:**
   - **TE-23**: Notification Service (for Story 1.3 alerts, lock takeover notifications)
   - **TE-24**: Object Storage Setup (MinIO/Azure Blob for Story 3.2 document uploads)
   - **TE-25**: Disaster Recovery & Backup (PostgreSQL backups, RTO/RPO definitions)
   - **TE-26**: SAP FI BAPI Client (for Epic 4 invoice creation, billing block checks)

2. **Integration Resilience Enhancements (Technical Enablers):**
   - **TE-5 (MS5 BAPI Client)**: Added timeout/retry/circuit breaker strategy (10s timeout, 2 retries, circuit breaker opens after 5 failures)
   - **TE-6 (MS5 IDoc Client)**: Added CPI-layer idempotency enforcement (correlation_id uniqueness, PostgreSQL constraint, duplicate handling to prevent duplicate orders)

3. **Edge Case Acceptance Criteria Added to User Stories:**
   - **Story 2.2** (Pre-Post Validation): BAPI timeout handling, warning vs. error distinction, field mapping errors, stale data detection, partial validation success
   - **Story 3.1** (Policy Checks): Policy conflicts, policy versioning during pilot, retroactive policy changes, policy exception handling, missing policy definitions
   - **Story 4.2** (Invoice Triggers): Out-of-order events, duplicate event deduplication, malformed event handling, partial deliveries, billing block detection

4. **KPI Definition Table:**
   - Clarified cycle time measurement per epic (Proposal→Posted vs. Delivery→Invoice)
   - Separated POV vs. Production targets (realistic POV: 60% acceptance vs. ambitious Production: 70%)
   - Acknowledged system limits (Traceability: 98%+ vs. unrealistic 100%)

5. **Epic Summary Updates:**
   - Epic 2: Remains 4 stories (2.1-2.4); infrastructure resilience moved to Technical Enablers
   - Total: 19 stories, 28-34 days effort

**Rationale:**
- **Critical risks mitigated in Technical Enablers**: Duplicate orders (TE-6 idempotency), timeout cascades (TE-5 circuit breaker), error handling (TE-5/TE-6 enhanced specs)
- **Testability improved**: Edge cases now have specific, measurable acceptance criteria in user stories
- **Realistic targets**: POV targets account for learning curve, field mapping drift, error handling overhead
- **User stories remain business-focused**: Infrastructure concerns (locking, Saga pattern, offline mode) belong in Technical Enablers, not user stories

### Critical Changes in v3.0

**Problem Addressed:**
Version 2.0 user stories were still organized by **technical implementation layers** (Foundation, Agent Workflows, Deployment) rather than **business value chains** (Sales Manager journey, Finance Ops journey).

**v3.0 Improvements:**
- **6 Value Chain Epics** replacing technical layer epics
- **User stories written in business language** (NO "IDoc," "BAPI," "CPI," "OData" in story statements)
- **Technical implementation moved to "Technical Enablers"** section
- **Story mapping aligned to Sales/Finance journeys** (Lead → Order → Invoice → Payment)
- **Business acceptance criteria separated from technical acceptance**

---

## Executive Summary

This document restructures the RRPS Lead-to-Cash POV requirements from a **business value chain perspective** rather than a technical implementation perspective.

### POV Objective (Business Language)

**The POV will prove whether AI agents can:**
1. Help Sales Managers **identify which opportunities are ready to convert to orders** (no more wasted time on deals that aren't ready)
2. Help Sales Ops **create orders in 5 minutes instead of 45 minutes** (70%+ fields auto-filled accurately)
3. Ensure **orders are compliant before posting** (policies enforced automatically)
4. Help Finance Ops **trigger invoices when prerequisites are met** (no more billing delays due to missing FAT certificates)
5. Provide **full traceability from opportunity to invoice** (audit-ready evidence for every transaction)

### Value Chain Overview

**Sales Manager Journey (Customer Engagement):**
Lead → Opportunity → **[Readiness Assessment]** → Quote → **[Order Creation]** → Order

**Sales Operations Journey (Order Fulfillment):**
Qualified Opportunity → **[Auto-Fill Proposal]** → Validate → Approve → **[Post to SAP]** → Order Confirmation

**Finance Operations Journey (Post-Sales Follow-up):**
Order → Delivery → **[Billing Readiness Check]** → Invoice → Payment → Collections

### Epic Overview (Business-Focused)

| Epic | Business Outcome | User Stories | Effort (Days) | POV Phase |
|------|------------------|--------------|---------------|-----------|
| **Epic 1: Sales Manager - Opportunity Qualification** | Sales Managers prioritize ready-to-order deals; gaps fixed early | 3 | 4-5 | Weeks 3-4 |
| **Epic 2: Sales Operations - Fast Order Creation** | Orders created in 5 min vs. 45 min; 60%+ auto-fill (POV) | 4 | 6-7 | Weeks 3-6 |
| **Epic 3: Compliance - Policy Enforcement** | Orders compliant before posting; full audit trail | 3 | 4-5 | Weeks 3-6 |
| **Epic 4: Finance Operations - Billing Readiness** | Invoices triggered when prerequisites met; reduced DSO | 3 | 4-5 | Weeks 5-6 |
| **Epic 5: POV Success - Metrics & Decision** | Data-driven scale/iterate/stop recommendation | 3 | 4-5 | Weeks 9-10 |
| **Epic 6: User Validation - UAT & Pilot** | Users confirm solution works; feedback incorporated | 3 | 6-7 | Weeks 7-8 |
| **TOTAL** | **All business outcomes proven** | **19** | **28-34** | **10 Weeks** |

**Note:** Technical enablers (integration, platform, infrastructure) run in parallel and are tracked separately.

---

### KPI Definitions & Measurement

**Purpose:** This table defines how each KPI is measured to avoid ambiguity (e.g., "Cycle Time" means different stages in different epics).

| KPI | Epic(s) | Definition | Measurement | POV Target | Production Target |
|-----|---------|------------|-------------|------------|-------------------|
| **Acceptance Rate** | Epic 2 | % of auto-filled proposal fields accepted without manual edits | `(Fields unchanged by user / Total fields auto-filled) × 100` | ≥60% | ≥70% |
| **Cycle Time Reduction** (Opportunity → Order) | Epic 1 | Time from "opportunity marked ready" to "user starts order creation" | Baseline: Time from CEC status "Ready" to first order proposal generation. POV: Same measurement. | N/A (Epic 1 is readiness, not order creation) | N/A |
| **Cycle Time Reduction** (Proposal → Posted) | Epic 2 | Time from "start order proposal" to "SAP VBELN received" | Baseline: Manual process (30-45 min). POV: Measure from user clicks "Create Order Proposal" to SAP VBELN returned (target: 3-5 min). | 25-35% reduction | 35-45% reduction |
| **Cycle Time Reduction** (Delivery → Invoice) | Epic 4 | Time from "delivery milestone event" to "invoice triggered" | Baseline: Manual billing readiness check (2-3 days). POV: Measure from delivery event received to invoice trigger (target: <1 hour). | 30-40% reduction | 40-50% reduction |
| **First-Time-Right** | Epic 2 | % of orders that post successfully on first attempt (no validation/posting errors requiring rework) | `(Orders posted successfully on first attempt / Total orders attempted) × 100` | +10-15% vs. baseline | +15-20% vs. baseline |
| **Artefact Readiness** | Epic 3, 4 | % of orders with required compliance documents present before billing | `(Orders with all required docs / Total orders) × 100` | 70-85% | 85-95% |
| **Traceability** | Epic 3 | % of transactions with complete audit trail (correlation ID → CPI message ID → SAP VBELN) | `(Transactions with complete chain / Total transactions) × 100` | 98%+ | 99%+ (allow 1% edge cases) |

**Key Changes from Original Targets** (based on critique):
- **Acceptance Rate:** Reduced POV target from ≥70% to ≥60% to account for field mapping drift and learning curve
- **Cycle Time:** Reduced POV target from 30-40% to 25-35% to include error handling overhead
- **First-Time-Right:** Reduced POV target from +15-20% to +10-15% to allow for data synchronization issues
- **Artefact Readiness:** Reduced POV target from 80-90% to 70-85% to account for user adoption time
- **Traceability:** Reduced from 100% to 98%+ to acknowledge system limits (network loss, edge cases)

---

## Value Chain Overview

### Sales Manager Journey (Lead → Order)

```
┌─────────────┐     ┌──────────────┐     ┌─────────────┐     ┌──────────────┐     ┌─────────┐
│   Lead      │────▶│ Opportunity  │────▶│   Quote     │────▶│ Order Ready  │────▶│  Order  │
│ Identified  │     │  Qualified   │     │  Approved   │     │  (All Gaps   │     │ Posted  │
│             │     │              │     │             │     │   Fixed)     │     │ to SAP  │
└─────────────┘     └──────────────┘     └─────────────┘     └──────────────┘     └─────────┘
                           │                                         │
                           │                                         │
                    ┌──────▼──────────┐                      ┌──────▼─────────┐
                    │ Agent Value:    │                      │ Agent Value:   │
                    │ Readiness Score │                      │ One-Click      │
                    │ Gap Visibility  │                      │ Order Creation │
                    └─────────────────┘                      └────────────────┘
```

**Pain Points Addressed:**
- **Before:** Cannot tell which opportunities are ready; gaps discovered at order creation (2-day delays)
- **After:** Readiness score + gap visibility; gaps fixed same day

### Sales Operations Journey (Opportunity → Order)

```
┌──────────────┐     ┌───────────────┐     ┌──────────┐     ┌─────────┐     ┌──────────┐
│  Qualified   │────▶│ Auto-Generate │────▶│ Validate │────▶│ Approve │────▶│   Post   │
│ Opportunity  │     │   Proposal    │     │  (BAPI)  │     │  Edit   │     │ to SAP   │
│              │     │ (CEC + IPAS)  │     │          │     │         │     │ (IDoc)   │
└──────────────┘     └───────────────┘     └──────────┘     └─────────┘     └──────────┘
       │                     │                                                      │
       │                     │                                                      │
   ┌───▼──────────┐     ┌───▼─────────────┐                                  ┌────▼─────┐
   │ 30-45 min    │     │ Agent Value:    │                                  │ SAP Order│
   │ manual entry │────▶│ 3 sec auto-fill │                                  │ VBELN    │
   │ (BEFORE)     │     │ 70%+ accuracy   │                                  │ returned │
   └──────────────┘     └─────────────────┘                                  └──────────┘
```

**Pain Points Addressed:**
- **Before:** 30-45 min manual data entry from CEC + IPAS → SAP; errors discovered after posting
- **After:** 3-5 min auto-fill → validate → post; errors caught before posting

### Finance Operations Journey (Order → Invoice)

```
┌─────────┐     ┌──────────┐     ┌───────────────┐     ┌─────────┐     ┌─────────┐
│  Order  │────▶│ Delivery │────▶│ Billing Ready │────▶│ Invoice │────▶│ Payment │
│ Posted  │     │ Confirmed│     │ (FAT + Docs)  │     │ Triggered│    │ Received│
└─────────┘     └──────────┘     └───────────────┘     └─────────┘     └─────────┘
                       │                  │
                       │                  │
                  ┌────▼──────────┐  ┌───▼────────────────┐
                  │ Agent Value:  │  │ Agent Value:       │
                  │ Auto-detect   │  │ Trigger invoice    │
                  │ delivery      │  │ when ready         │
                  │ milestone     │  │ (not 5 days later) │
                  └───────────────┘  └────────────────────┘
```

**Pain Points Addressed:**
- **Before:** Finance Ops manually checks delivery status + docs; discovers FAT missing 5 days later
- **After:** Agent auto-detects delivery + checks prerequisites; invoice triggered in 4 hours

---

## Epic 1: Sales Manager - Opportunity Qualification & Prioritization

**Business Outcome:** Sales Managers can identify which opportunities are ready to convert to orders, reducing time wasted on deals that aren't ready.

**KPI Impact:**
- Cycle Time Reduction: 30-40% (primary)
- First-Time-Right: +15-20% (secondary—fewer gaps discovered late)

**POV Phase:** Weeks 3-4 (after integration layer complete)
**Estimated Effort:** 4-5 days
**Dependencies:** Technical Enablers 1-3 (CEC integration, canonical models, policy catalog)

---

### User Story 1.1: Opportunity Readiness Scoring

**As a** Sales Manager,
**I want** to see a readiness score for each late-stage opportunity,
**So that** I can prioritize my time on deals most likely to close this week.

#### Business Value
- **Time Saved:** 15-20 min/day no longer spent manually reviewing each opportunity in CEC
- **Focus:** Spend time on green deals (ready to order) vs. amber deals (1-2 gaps) vs. red deals (multiple blockers)
- **Faster Conversion:** Deals progress to orders 2 days faster (gaps fixed proactively)

#### User Experience (What the User Sees)

**Dashboard View:**
```
Opportunity Readiness Dashboard

┌─────────────────────────────────────────────────────────────┐
│ OPP-12345  │ Singapore Engine Sale   │ 🟢 READY (100%)    │
│ Account: CUST123 | Quote: Approved | Next: Create Order    │
└─────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────┐
│ OPP-12346  │ Malaysia Power System   │ 🟡 AMBER (87%)     │
│ Missing: Ship-To partner | IPAS config "In Progress"        │
│ Action: Assign Ship-To | Finalize config                    │
└─────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────┐
│ OPP-12347  │ Thailand Marine Engine  │ 🔴 RED (45%)       │
│ Missing: Payment terms | Bill-To partner | Delivery date    │
│ Action: Fix 3 critical gaps before order creation           │
└─────────────────────────────────────────────────────────────┘
```

**What the Score Means:**
- **🟢 Green (90-100%):** All prerequisites met—ready to create order immediately
- **🟡 Amber (70-89%):** 1-2 gaps remaining—actionable fixes identified
- **🔴 Red (<70%):** Multiple blockers—not ready for order creation

#### Business Acceptance Criteria
- [ ] I can see a readiness score (0-100%) for each opportunity in stages "Quote Approved" or later
- [ ] Score updates automatically when I fix gaps (e.g., add Ship-To partner in CEC)
- [ ] I can filter opportunities by readiness: "Show me all green deals" or "Show me amber deals"
- [ ] I can click on an opportunity to see detailed gap analysis
- [ ] Scoring criteria is transparent (I understand why OPP-12346 is 87% vs. 100%)

#### Technical Acceptance Criteria (What Must Be Implemented)
- [ ] Opportunity Assessment Agent workflow retrieves opportunities from CEC (via Technical Enabler 2)
- [ ] Scoring logic checks:
  - [ ] Account assigned (CEC.Account.Id present)
  - [ ] Sold-To, Ship-To, Bill-To partners assigned (CEC.Partners with roles SP/SH/RE)
  - [ ] Payment terms set (CEC.PaymentTerms present)
  - [ ] Requested delivery date set (CEC.RequestedDate present)
  - [ ] IPAS configuration finalized (IPAS.ConfigStatus = "Complete")
  - [ ] Quote approved (CEC.Stage = "Quote Approved")
- [ ] Score calculated: (met prerequisites / total prerequisites) × 100
- [ ] Dashboard API returns scored opportunities
- [ ] Score refreshed every 15 minutes (or on-demand trigger)

#### Technical Enablers Required
- **TE-1:** Canonical data models (`OpportunityData`, `AssessmentResult`)
- **TE-2:** CEC OData client (retrieve opportunities + partners + terms)
- **TE-3:** IPAS client (retrieve config status)
- **TE-10:** Opportunity Assessment Agent workflow (Kailash SDK)
- **TE-15:** Nexus API endpoint (`GET /opportunities/readiness`)

#### KPI Impact
- **Cycle Time Reduction:** 30-40% (gaps fixed proactively vs. discovered at order creation)
- **First-Time-Right:** +15-20% (fewer orders rejected due to missing data)

---

### User Story 1.2: Gap Identification & Remediation Guidance

**As a** Sales Manager,
**I want** to see exactly what's missing for each opportunity (partners, terms, config),
**So that** I can fix blockers before they delay the deal.

#### Business Value
- **Clarity:** Know exactly what to fix (no more guessing)
- **Delegation:** Assign specific gaps to team members (e.g., "Add Ship-To partner" → Sales Ops)
- **Speed:** Gaps fixed same day (vs. discovered 2 days later at order creation)

#### User Experience (What the User Sees)

**Gap Detail View:**
```
Opportunity: OPP-12346 | Readiness: 87% (AMBER)

Prerequisites:
✓ Account assigned (CUST123)
✓ Sold-To partner assigned (CUST123-SP)
✗ Ship-To partner NOT assigned
  └─ Action: Go to CEC → Partners → Add Ship-To role
✓ Bill-To partner assigned (CUST123-BP)
✓ Payment terms set (Z001)
✓ Requested delivery date set (2025-09-30)
✗ IPAS configuration "In Progress" (not finalized)
  └─ Action: Contact engineering to finalize Config ID 789
✓ Quote approved

Next Step: Fix 2 gaps → Readiness will update to 100% (GREEN)
```

**What the User Does:**
1. Sees exactly what's missing (Ship-To partner, IPAS config)
2. Knows how to fix it (add Ship-To in CEC, finalize config in IPAS)
3. Delegates tasks to team
4. Readiness score updates automatically when gaps fixed

#### Business Acceptance Criteria
- [ ] I can see a checklist of all prerequisites for each opportunity
- [ ] Each gap shows a clear action: "Add Ship-To partner in CEC" (not "Partner missing")
- [ ] I can delegate gap remediation tasks to team members
- [ ] Score updates automatically when I fix gaps (within 15 min)
- [ ] I can export gap reports for weekly pipeline reviews

#### Technical Acceptance Criteria (What Must Be Implemented)
- [ ] Opportunity Assessment Agent returns detailed `AssessmentResult`:
  - [ ] List of met prerequisites (green checkmarks)
  - [ ] List of missing prerequisites (red X's) with remediation guidance
  - [ ] Scoring breakdown
- [ ] Remediation guidance includes:
  - [ ] What's missing (e.g., "Ship-To partner")
  - [ ] Where to fix it (e.g., "CEC → Partners tab")
  - [ ] Who should fix it (e.g., "Sales Ops" or "Engineering")
- [ ] API endpoint: `GET /opportunities/{id}/gaps` returns structured gap list
- [ ] Dashboard renders gaps as actionable checklist

#### Technical Enablers Required
- **TE-1:** Canonical data models (`AssessmentResult` with `missing_prerequisites` list)
- **TE-2:** CEC OData client (retrieve detailed partner/term data)
- **TE-3:** IPAS client (retrieve config status with details)
- **TE-10:** Opportunity Assessment Agent workflow
- **TE-15:** Nexus API endpoint (`GET /opportunities/{id}/gaps`)

#### KPI Impact
- **Cycle Time Reduction:** 30-40% (gaps fixed same day vs. 2-day delays)
- **User Adoption:** High (clear actionable guidance vs. cryptic messages)

---

### User Story 1.3: Automated Readiness Alerts

**As a** Sales Manager,
**I want** automated alerts when opportunities become order-ready (all gaps fixed),
**So that** I can strike while the iron is hot and convert deals immediately.

#### Business Value
- **Speed:** Convert deals within hours of becoming ready (vs. days)
- **Proactive:** Agent tells me when deals are ready (I don't have to keep checking)
- **Competitive Advantage:** Faster quote-to-order conversion vs. competitors

#### User Experience (What the User Sees)

**Alert Email (or Dashboard Notification):**
```
Subject: Opportunity OPP-12346 is now ORDER-READY

Hello Sarah,

Opportunity OPP-12346 (Malaysia Power System) has been updated:

Status: 🟢 READY (100%)
All prerequisites met:
✓ Ship-To partner assigned (fixed today)
✓ IPAS config finalized (completed today)
✓ All other prerequisites met

Next Step: Create sales order

[View Opportunity] [Create Order]
```

**What the User Does:**
1. Receives alert when deal becomes ready
2. Clicks "Create Order" button
3. Handed off to Sales Ops for order creation

#### Business Acceptance Criteria
- [ ] I receive an alert (email or dashboard notification) when an opportunity transitions from amber/red → green
- [ ] Alert includes: opportunity ID, customer name, what changed (gaps fixed), next action
- [ ] I can configure alert preferences (email, dashboard, or both)
- [ ] Alerts sent within 15 minutes of status change
- [ ] I can snooze/dismiss alerts

#### Technical Acceptance Criteria (What Must Be Implemented)
- [ ] Opportunity Assessment Agent runs on schedule (every 15 min) or on-demand
- [ ] Agent compares current readiness score vs. previous score
- [ ] If transition from <90% → ≥90%, trigger alert
- [ ] Alert notification sent via:
  - [ ] Email (SMTP integration)
  - [ ] Dashboard notification (WebSocket or polling)
- [ ] Alert includes opportunity details + direct link to "Create Order" workflow

#### Technical Enablers Required
- **TE-1:** Canonical data models (`AssessmentResult` with state transition tracking)
- **TE-10:** Opportunity Assessment Agent workflow (scheduled execution)
- **TE-15:** Nexus API endpoint (trigger alerts)
- **TE-19:** Notification service (email + dashboard notifications)

#### KPI Impact
- **Cycle Time Reduction:** 30-40% (immediate action when ready vs. 1-2 day delays)
- **User Satisfaction:** High (proactive alerts vs. manual monitoring)

---

## Epic 2: Sales Operations - Fast, Accurate Order Creation

**Business Outcome:** Sales Ops creates orders in 5 minutes instead of 45 minutes, with 60%+ of fields auto-filled accurately.

**KPI Impact:**
- Acceptance Rate: ≥60% POV / ≥70% Production (primary—percentage of auto-filled fields accepted without edits)
- Cycle Time Reduction: 25-35% POV / 35-45% Production (primary—time from "order-ready" to "order posted")
- First-Time-Right: +10-15% POV / +15-20% Production (secondary—fewer posting errors)

**POV Phase:** Weeks 3-6 (core agent workflows)
**Estimated Effort:** 6-7 days
**Story Count:** 4 stories (2.1-2.4)
**Dependencies:** Epic 1, Technical Enablers 1-7, 14, 15

---

### User Story 2.1: One-Click Order Proposal Generation

**As a** Sales Operations Manager,
**I want** to create a complete sales order with one click from a qualified CEC opportunity,
**So that** I can avoid spending 30-45 minutes re-keying data from CEC and IPAS into SAP.

#### Business Value
- **Time Saved:** 30-45 min → 3-5 min per order (80-90% reduction)
- **Accuracy:** Fewer manual entry errors (70%+ auto-fill accuracy)
- **Confidence:** Clear provenance for every field (know where data came from)

#### User Experience (What the User Sees)

**Order Creation Workflow:**

**Step 1: Search for Opportunity**
```
Sales Ops Agent - Create Order

Search Opportunity: [OPP-12345________] [Search]

Results:
┌──────────────────────────────────────────────────────┐
│ OPP-12345 │ Singapore Engine Sale │ 🟢 READY (100%) │
│ Customer: Maritime Solutions Ltd (CUST123)           │
│ Quote: Approved | Value: $2.5M                       │
└──────────────────────────────────────────────────────┘

[Create Order Proposal]
```

**Step 2: View Auto-Generated Proposal (3 seconds later)**
```
Order Proposal for OPP-12345

Header:
┌───────────────────┬──────────────┬─────────────────────────────────┐
│ Field             │ Value        │ Source                          │
├───────────────────┼──────────────┼─────────────────────────────────┤
│ Sales Org         │ 1000         │ 🟢 Copied from CEC.SalesOrg     │
│ Distribution Ch   │ 10           │ 🟢 Copied from CEC.DistChannel  │
│ Division          │ 00           │ 🟢 Copied from CEC.Division     │
│ Sold-To Partner   │ CUST123      │ 🟢 Copied from CEC.Account.Id   │
│ Ship-To Partner   │ CUST123-SH   │ 🟢 Copied from CEC.Partners.SH  │
│ Bill-To Partner   │ CUST123-BP   │ 🟢 Copied from CEC.Partners.RE  │
│ Payment Terms     │ Z001         │ 🟢 Copied from CEC.PaymentTerms │
│ Incoterms         │ DAP          │ 🟢 Copied from CEC.Incoterms    │
│ Incoterms Loc     │ Singapore    │ 🟢 Copied from CEC.IncoLoc      │
│ Requested Date    │ 2025-09-30   │ 🟢 Copied from CEC.ReqDate      │
│ Plant             │ SG01         │ 🟡 Derived from Ship-To loc     │
└───────────────────┴──────────────┴─────────────────────────────────┘

Items: (10 lines from IPAS BOM)
┌──────┬────────────┬─────┬─────┬───────┬─────────────────────────┐
│ Line │ Material   │ Qty │ UoM │ Plant │ Source                  │
├──────┼────────────┼─────┼─────┼───────┼─────────────────────────┤
│ 10   │ MAT-001    │ 2   │ EA  │ SG01  │ 🔵 IPAS BOM Line 1      │
│ 20   │ MAT-002    │ 5   │ EA  │ SG01  │ 🔵 IPAS BOM Line 2      │
│ ...  │ ...        │ ... │ ... │ ...   │ ...                     │
└──────┴────────────┴─────┴─────┴───────┴─────────────────────────┘

Auto-Fill Summary:
✓ 42 of 45 fields auto-filled (93% acceptance rate)
✓ 3 fields require review (yellow highlighted)

[Edit Proposal] [Validate Order] [Cancel]
```

**What the User Does:**
1. Searches for opportunity (OPP-12345)
2. Clicks "Create Order Proposal"
3. Reviews auto-generated proposal in 30 seconds
4. Edits 1-3 fields if needed (yellow highlighted fields)
5. Clicks "Validate Order" (proceeds to User Story 2.2)

#### Business Acceptance Criteria
- [ ] I can search for opportunities by ID, customer name, or quote number
- [ ] I can select an opportunity and click "Create Order Proposal"
- [ ] Proposal generates in <5 seconds (excluding SAP validation)
- [ ] I can see where each field came from:
  - [ ] 🟢 Green = Copied directly from CEC or IPAS
  - [ ] 🔵 Blue = Looked up from master data
  - [ ] 🟡 Yellow = Derived from business rule (rule ID shown)
- [ ] ≥70% of fields are auto-filled correctly (acceptance rate KPI)
- [ ] I can edit any field if needed
- [ ] Proposal includes header fields + line items (BOM from IPAS)

#### Technical Acceptance Criteria (What Must Be Implemented)
- [ ] Sales Ops Agent workflow:
  - [ ] Retrieve opportunity data from CEC (via TE-2: CEC OData client)
  - [ ] Retrieve BOM from IPAS (via TE-3: IPAS client)
  - [ ] Map CEC + IPAS data to `SalesOrderProposal` canonical model
  - [ ] Apply field derivation rules (e.g., plant derived from Ship-To location)
  - [ ] Tag each field with provenance:
    - [ ] `source: "CEC.Account.Id"` (copy)
    - [ ] `source: "Master Data Lookup: Ship-To → Plant"` (lookup)
    - [ ] `source: "Business Rule R-042: Incoterms + Location → Plant"` (derivation)
- [ ] API endpoint: `POST /orders/propose` (input: opportunity ID) → returns `SalesOrderProposal`
- [ ] Response time: <5 seconds p95
- [ ] Frontend renders proposal with color-coded provenance

#### Technical Enablers Required
- **TE-1:** Canonical data models (`SalesOrderProposal` with `Provenance` field)
- **TE-2:** CEC OData client (retrieve opportunity, account, partners, terms, dates)
- **TE-3:** IPAS client (retrieve BOM)
- **TE-4:** Field mapping registry (CEC/IPAS → MS5 field mappings)
- **TE-11:** Sales Ops Agent workflow (orchestrator)
- **TE-15:** Nexus API endpoint (`POST /orders/propose`)

#### KPI Impact
- **Cycle Time Reduction:** 30-40% (30-45 min → 3-5 min)
- **Acceptance Rate:** ≥70% (primary KPI)

---

### User Story 2.2: Pre-Post Validation & Error Prevention

**As a** Sales Operations Manager,
**I want** to validate my order proposal against SAP before posting,
**So that** I can catch errors (missing partners, pricing issues, material availability) before the order is submitted, saving me from rework.

#### Business Value
- **First-Time-Right:** +15-20% improvement (errors caught before posting)
- **Time Saved:** Avoid 1-2 day rework cycles due to posting errors
- **Confidence:** Know the order will succeed before submitting

#### User Experience (What the User Sees)

**Validation Workflow (after User Story 2.1):**

**Step 1: User Clicks "Validate Order"**
```
Validating order proposal against SAP...
⏳ Checking partners, materials, pricing, availability...
```

**Step 2: Validation Results (3 seconds later)**

**Success Case:**
```
✓ Validation Successful

All checks passed:
✓ Sold-To partner CUST123 exists in SAP
✓ Ship-To partner CUST123-SH exists in SAP
✓ Bill-To partner CUST123-BP exists in SAP
✓ All materials available (MAT-001: qty 2, MAT-002: qty 5, ...)
✓ Pricing determined: Total value $2.5M
✓ Requested date 2025-09-30 is valid

[Approve & Post Order] [Edit Proposal] [Cancel]
```

**Error Case:**
```
⚠ Validation Failed (2 issues found)

Business Errors:
❌ Ship-To partner CUST123-SH not found in SAP
   └─ Action: Verify Ship-To partner in CEC or use alternative
   └─ Field: header.shipTo

❌ Material MAT-003 not available (insufficient stock at plant SG01)
   └─ Action: Change plant to SG02 or adjust requested date
   └─ Field: items[2].plant

[Fix Errors & Re-Validate] [Cancel]
```

**What the User Does:**
1. Reviews validation results
2. If errors: fixes highlighted fields, re-validates
3. If success: clicks "Approve & Post Order" (proceeds to User Story 2.3)

#### Business Acceptance Criteria
- [ ] I can click "Validate Order" to check proposal against SAP before posting
- [ ] Validation completes in <3 seconds p95
- [ ] Validation checks:
  - [ ] Partners exist in SAP (Sold-To, Ship-To, Bill-To)
  - [ ] Materials exist and are available
  - [ ] Pricing can be determined
  - [ ] Requested date is valid
- [ ] Errors are categorized clearly:
  - [ ] **Business Errors:** Missing partners, material availability, pricing issues (I can fix)
  - [ ] **Technical Errors:** SAP timeout, network issues (IT must fix)
- [ ] Each error shows:
  - [ ] What's wrong (e.g., "Ship-To partner not found")
  - [ ] Which field is affected (e.g., "header.shipTo")
  - [ ] How to fix it (e.g., "Verify Ship-To partner in CEC")
- [ ] I can fix errors and re-validate without starting over

**Edge Cases & Error Handling** (added from critique):
- [ ] **BAPI Timeout Handling**: If SAP takes >10 seconds, show clear timeout message with retry option
- [ ] **Warning vs. Error Distinction**: BAPI warnings (e.g., "Material availability delayed by 2 days") shown separately from blocking errors
- [ ] **Field Mapping Errors**: If CEC field value (e.g., "NET30") doesn't map to valid SAP value, show specific error: "Payment term NET30 not recognized. Expected: Z030, Z060, or Z090"
- [ ] **Partial Validation Success**: If header validates but line items fail, show which line items have issues (don't fail entire validation)
- [ ] **Stale Data Detection**: If CEC data retrieved >5 minutes ago, show warning: "CEC data may be outdated (retrieved 12 min ago). [Refresh Data]"

#### Technical Acceptance Criteria (What Must Be Implemented)
- [ ] Sales Ops Agent calls BAPI_SALESORDER_SIMULATE (via TE-5: MS5 BAPI client)
- [ ] BAPI input: `SalesOrderProposal` (dryRun = true)
- [ ] BAPI output: `SAPValidationResponse` with:
  - [ ] `status: "SUCCESS"` or `"BUSINESS_ERROR"` or `"TECHNICAL_ERROR"`
  - [ ] `issues: List[ValidationIssue]` (code, severity, field, message)
  - [ ] Pricing data (if success)
- [ ] Validation errors parsed into user-friendly messages:
  - [ ] BAPI code "E 001" → "Ship-To partner not found"
  - [ ] BAPI code "W 010" → "Material availability warning"
- [ ] API endpoint: `POST /orders/validate` (input: `SalesOrderProposal`) → returns `SAPValidationResponse`
- [ ] Response time: <3 seconds p95
- [ ] Frontend highlights error fields in red

#### Technical Enablers Required
- **TE-1:** Canonical data models (`SAPValidationResponse`, `ValidationIssue`)
- **TE-5:** MS5 BAPI client (BAPI_SALESORDER_SIMULATE)
- **TE-11:** Sales Ops Agent workflow (validate step)
- **TE-15:** Nexus API endpoint (`POST /orders/validate`)

#### KPI Impact
- **First-Time-Right:** +15-20% (errors caught before posting)
- **User Satisfaction:** High (clear error messages vs. cryptic SAP codes)

---

### User Story 2.3: One-Click Approve & Post to SAP

**As a** Sales Operations Manager,
**I want** to approve and post the order to SAP in one workflow (no switching to SAP GUI),
**So that** I can complete order creation without switching between systems.

#### Business Value
- **Seamless Experience:** One platform (no SAP GUI switching)
- **Approval Trail:** Approval linked to SAP order automatically
- **Speed:** Order posted in seconds (not minutes)

#### User Experience (What the User Sees)

**Post Order Workflow (after User Story 2.2 validation success):**

**Step 1: User Clicks "Approve & Post Order"**
```
Posting order to SAP...
⏳ Submitting order via SAP interface...
⏳ Awaiting SAP order number...
```

**Step 2: Success (5-10 seconds later)**
```
✓ Order Posted Successfully

SAP Order Number: 8000123456 (VBELN)

Order Details:
- Opportunity: OPP-12345
- Customer: Maritime Solutions Ltd (CUST123)
- Total Value: $2.5M
- Requested Date: 2025-09-30
- Status: Posted to SAP

Audit Trail:
- Correlation ID: POV-2025-000123
- SAP Message ID: CPI-MSG-456789
- SAP Order Number: 8000123456
- Posted by: joe.smith@rrps.com
- Posted at: 2025-09-15 10:45:32 UTC

[View Order in SAP] [Create Another Order] [Done]
```

**Error Case (rare—validation should catch most errors):**
```
⚠ Order Posting Failed

Technical Error:
❌ SAP connection timeout (will retry automatically)
   └─ Retry attempt 1 of 3 in 5 seconds...

Your order proposal is saved. The system will retry posting automatically.

Correlation ID: POV-2025-000123 (use this for troubleshooting)

[View Status] [Cancel Order]
```

**What the User Does:**
1. Reviews success message
2. Notes SAP order number (8000123456)
3. Clicks "Done" or "Create Another Order"

#### Business Acceptance Criteria
- [ ] I can click "Approve & Post Order" after successful validation
- [ ] Order posted to SAP in <10 seconds p95
- [ ] I receive SAP order number (VBELN) immediately
- [ ] I can see full audit trail:
  - [ ] Correlation ID
  - [ ] SAP Message ID (from integration layer)
  - [ ] SAP Order Number (VBELN)
  - [ ] Who posted (user email)
  - [ ] When posted (UTC timestamp)
- [ ] If posting fails (rare), I see clear error message and retry status
- [ ] I can create another order or return to dashboard

#### Technical Acceptance Criteria (What Must Be Implemented)
- [ ] Sales Ops Agent calls IDoc ORDERS05 create (via TE-6: MS5 IDoc client)
- [ ] IDoc input: `SalesOrderProposal` (dryRun = false)
- [ ] IDoc submission returns:
  - [ ] `cpi_message_id` (immediate)
  - [ ] `sap_order_number` (VBELN) after async processing
- [ ] Idempotent posting:
  - [ ] Correlation ID used to prevent duplicate posts
  - [ ] If same correlation ID submitted twice, return existing VBELN (no duplicate order)
- [ ] Retry logic:
  - [ ] On transient errors (timeout, network), retry up to 3 times with exponential backoff
  - [ ] On business errors (e.g., partner still missing despite validation), return error immediately
- [ ] API endpoint: `POST /orders/post` (input: `SalesOrderProposal`) → returns `SAPPostResponse` (VBELN + audit trail)
- [ ] Audit trail captured:
  - [ ] Correlation ID
  - [ ] CPI Message ID
  - [ ] SAP VBELN
  - [ ] User email
  - [ ] Timestamp (UTC)
  - [ ] Field-level provenance (every field tagged with source)
- [ ] Response time: <10 seconds p95

#### Technical Enablers Required
- **TE-1:** Canonical data models (`SAPPostResponse` with audit trail)
- **TE-6:** MS5 IDoc client (ORDERS05 create with idempotency)
- **TE-11:** Sales Ops Agent workflow (post step)
- **TE-14:** Audit store (PostgreSQL—capture correlation ID, CPI message ID, VBELN)
- **TE-15:** Nexus API endpoint (`POST /orders/post`)

#### KPI Impact
- **Cycle Time Reduction:** 30-40% (seamless workflow vs. system switching)
- **Traceability:** 100% (correlation ID → CPI message ID → SAP VBELN)

---

### User Story 2.4: Field Provenance & Trust

**As a** Sales Operations Manager,
**I want** to see where each order field came from (CEC copy, IPAS lookup, business rule),
**So that** I can trust auto-filled data and only fix what's wrong (not re-check everything).

#### Business Value
- **Trust:** Know exactly where each value came from
- **Efficiency:** Only review/edit fields that are derived (yellow) vs. direct copies (green)
- **Troubleshooting:** If a field is wrong, know what to fix (CEC data? IPAS data? Business rule?)

#### User Experience (What the User Sees)

**Provenance Display (in order proposal from User Story 2.1):**

**Tooltip on Hover:**
```
Field: soldTo
Value: CUST123
Source: Copied from CEC.Account.Id
Retrieved: 2025-09-15 10:23:15 UTC
Confidence: High (direct copy)
```

**Provenance Legend:**
```
🟢 Green = Direct copy from CEC or IPAS (high confidence—rarely needs editing)
🔵 Blue = Looked up from SAP master data (medium confidence—verify if unfamiliar)
🟡 Yellow = Derived from business rule (review recommended)
🔴 Red = Manual entry required (no source data available)

Acceptance Rate This Week: 72% (above target of 70%)
```

**Detailed Provenance Report (exportable):**
```
Order Proposal Provenance Report
Opportunity: OPP-12345 | Correlation ID: POV-2025-000123

Header Fields:
┌──────────────────┬───────────┬─────────────────────────────────────┬────────────┐
│ Field            │ Value     │ Source                              │ Confidence │
├──────────────────┼───────────┼─────────────────────────────────────┼────────────┤
│ salesOrg         │ 1000      │ CEC.SalesOrg (copied)               │ High       │
│ soldTo           │ CUST123   │ CEC.Account.Id (copied)             │ High       │
│ shipTo           │ CUST123-SH│ CEC.Partners.SH (copied)            │ High       │
│ plant            │ SG01      │ Rule R-042: Ship-To loc → Plant     │ Medium     │
│ requestedDate    │ 2025-09-30│ CEC.RequestedDate (copied)          │ High       │
└──────────────────┴───────────┴─────────────────────────────────────┴────────────┘

Items:
┌──────┬────────────┬─────────────────────────────────────────┬────────────┐
│ Line │ Material   │ Source                                  │ Confidence │
├──────┼────────────┼─────────────────────────────────────────┼────────────┤
│ 10   │ MAT-001    │ IPAS BOM Line 1 (Config ID 789)         │ High       │
│ 20   │ MAT-002    │ IPAS BOM Line 2 (Config ID 789)         │ High       │
└──────┴────────────┴─────────────────────────────────────────┴────────────┘

Auto-Fill Summary:
- Direct Copy (Green): 38 fields (84%)
- Master Data Lookup (Blue): 2 fields (4%)
- Business Rule (Yellow): 5 fields (11%)
- Manual Entry (Red): 0 fields (0%)
Total Acceptance Rate: 93%
```

**What the User Does:**
1. Hovers over any field to see provenance tooltip
2. Focuses on yellow/red fields (review recommended)
3. Trusts green/blue fields (rarely needs editing)
4. Exports provenance report for audit/training purposes

#### Business Acceptance Criteria
- [ ] Every field in the order proposal shows provenance (source + confidence)
- [ ] I can hover over any field to see detailed tooltip:
  - [ ] Source system (CEC, IPAS, SAP master data, business rule)
  - [ ] Retrieval timestamp
  - [ ] Confidence level (High, Medium, Low)
- [ ] Fields color-coded by provenance type (green/blue/yellow/red)
- [ ] I can export provenance report for audit or training
- [ ] Provenance report includes:
  - [ ] All fields (header + items)
  - [ ] Source for each field
  - [ ] Confidence level
  - [ ] Auto-fill acceptance rate summary

#### Technical Acceptance Criteria (What Must Be Implemented)
- [ ] `SalesOrderProposal` model includes `Provenance` object for each field:
  ```json
  {
    "field": "soldTo",
    "value": "CUST123",
    "source": "CEC.Account.Id",
    "source_type": "COPY",  // COPY, LOOKUP, DERIVATION, MANUAL
    "rule_id": null,  // or "R-042" for business rules
    "retrieved_at": "2025-09-15T10:23:15Z",
    "confidence": "HIGH"  // HIGH, MEDIUM, LOW
  }
  ```
- [ ] Sales Ops Agent tags every field during proposal assembly
- [ ] API endpoint: `GET /orders/{correlation_id}/provenance` → returns full provenance report
- [ ] Frontend renders color-coded fields + tooltips
- [ ] Provenance report exportable as JSON or PDF

#### Technical Enablers Required
- **TE-1:** Canonical data models (`Provenance` field in `SalesOrderProposal`)
- **TE-4:** Field mapping registry (defines source for each field)
- **TE-11:** Sales Ops Agent workflow (provenance tagging)
- **TE-15:** Nexus API endpoint (`GET /orders/{id}/provenance`)

#### KPI Impact
- **Acceptance Rate:** ≥70% (users trust high-confidence fields)
- **User Satisfaction:** High (transparency builds trust)

---

## Epic 3: Compliance - Policy Enforcement & Audit Trail

**Business Outcome:** Orders are compliant before posting; full audit trail for every transaction.

**KPI Impact:**
- Traceability: 100% (primary—correlation ID → CPI → SAP VBELN for every transaction)
- Artefact Readiness: 80-90% (secondary—required docs present before billing)

**POV Phase:** Weeks 3-6 (parallel with Epic 2)
**Estimated Effort:** 4-5 days
**Dependencies:** Technical Enablers 1, 4, 7, 12

---

### User Story 3.1: Automated Policy Checks Before Posting

**As a** Compliance Manager,
**I want** automatic policy checks (Incoterms, partners, payment terms) before orders are posted,
**So that** non-compliant orders are blocked before they enter SAP (not discovered during audits).

#### Business Value
- **Proactive Compliance:** Policy violations blocked at creation (not discovered in audits)
- **Audit Confidence:** 100% of posted orders are compliant
- **Reduced Risk:** No retroactive corrections or fines

#### User Experience (What the User Sees)

**Policy Check (automatic during order validation):**

**Compliant Case:**
```
✓ Policy Compliance Checks Passed

All policies satisfied:
✓ Incoterms DAP: Required artefacts defined (FAT certificate, proof of delivery)
✓ Payment Terms Z001: Allowed for customer CUST123
✓ Partner Roles: Sold-To, Ship-To, Bill-To all assigned
✓ Approval Requirements: Quote approved by authorized approver

Order is compliant. Proceed to post.
```

**Non-Compliant Case (order blocked):**
```
⚠ Policy Compliance Failed (2 violations)

Policy Violations:
❌ Incoterms EXW requires bank guarantee (Payment Terms Z001)
   └─ Policy: POL-027 (Incoterms EXW + Payment Term Z001 → Bank Guarantee Required)
   └─ Action: Upload bank guarantee to document repository before posting
   └─ Document type: Bank Guarantee (BGUARANTEE)
   └─ Upload link: [rrps://docs/BGUARANTEE/OPP-12345]

❌ Ship-To partner role not assigned
   └─ Policy: POL-003 (All orders require Sold-To, Ship-To, Bill-To partners)
   └─ Action: Add Ship-To partner in CEC

Order BLOCKED. Fix violations before posting.

[View Policy Catalog] [Fix Violations] [Cancel]
```

**What the User (Sales Ops or Compliance) Does:**
1. Reviews policy check results during validation
2. If violations: fixes issues (uploads docs, adds partners)
3. Re-validates until compliant
4. Order cannot be posted until all policies pass

#### Business Acceptance Criteria
- [ ] Every order automatically checked against policy catalog before posting
- [ ] Policy checks include:
  - [ ] Incoterms → required artefacts (e.g., DAP requires FAT, EXW requires bank guarantee)
  - [ ] Payment terms → allowed for customer type
  - [ ] Partner roles → Sold-To, Ship-To, Bill-To all assigned
  - [ ] Approval requirements → Quote approved by authorized approver
- [ ] Non-compliant orders are **blocked from posting** (cannot proceed)
- [ ] Each violation shows:
  - [ ] Policy rule ID (e.g., POL-027)
  - [ ] What's violated (e.g., "Bank guarantee required")
  - [ ] How to fix it (e.g., "Upload bank guarantee to [link]")
- [ ] I can view full policy catalog (versioned, auditable)

**Edge Cases & Error Handling** (added from critique):
- [ ] **Policy Conflicts**: If Incoterms DAP + Payment Z001 require both FAT AND bank guarantee (2 docs, not 1), show all required documents clearly
- [ ] **Policy Versioning During Pilot**: If policy changes mid-execution (e.g., POL-027 updated on 2025-09-15), orders created before change use old policy version (immutable at creation time)
- [ ] **Retroactive Policy Changes**: Orders already posted are NOT re-validated (policy changes apply only to new orders going forward)
- [ ] **Policy Exception Handling**: If authorized user (Compliance Manager) grants exception (e.g., "waive bank guarantee for CUST123"), exception logged with justification and approver ID
- [ ] **Missing Policy Definition**: If order has Incoterms "FOB" but no policy defined for FOB, show warning (not blocking error): "No policy found for Incoterms FOB. Proceed with caution."

#### Technical Acceptance Criteria (What Must Be Implemented)
- [ ] Due Diligence Agent workflow runs policy checks:
  - [ ] Load policy catalog (via TE-7: Policy catalog service)
  - [ ] Match order data to policies:
    - [ ] Incoterms + Payment Terms → required artefacts
    - [ ] Customer type → allowed payment terms
    - [ ] Partner roles → completeness check
    - [ ] Quote approval status
  - [ ] Return `DDSummary` with:
    - [ ] `policies_passed: List[PolicyCheck]`
    - [ ] `policies_failed: List[PolicyViolation]`
- [ ] Sales Ops Agent calls Due Diligence Agent during validation (before BAPI simulate)
- [ ] If `policies_failed` is non-empty, block posting (return `status: "POLICY_VIOLATION"`)
- [ ] API endpoint: `POST /orders/check-policies` → returns `DDSummary`
- [ ] Policy catalog stored in versioned database:
  - [ ] Policy ID, rule description, conditions, required artefacts
  - [ ] Version controlled (track policy changes over time)

#### Technical Enablers Required
- **TE-1:** Canonical data models (`DDSummary`, `PolicyCheck`, `PolicyViolation`)
- **TE-7:** Policy catalog service (versioned rules database)
- **TE-12:** Due Diligence Agent workflow
- **TE-15:** Nexus API endpoint (`POST /orders/check-policies`)

#### KPI Impact
- **Traceability:** 100% (every policy check logged with rule ID + timestamp)
- **Compliance Rate:** 100% of posted orders pass all policies

---

### User Story 3.2: Required Document Flagging & Just-In-Time Prompts

**As a** Compliance Manager,
**I want** required documents (FAT certificates, bank guarantees) flagged upfront when orders are created,
**So that** billing isn't delayed by missing documents discovered later.

#### Business Value
- **Proactive Document Collection:** Documents requested during order creation (not at billing time)
- **Reduced Billing Delays:** 80-90% of required docs present before billing events
- **Audit Readiness:** All docs linked to transactions with hash verification

#### User Experience (What the User Sees)

**Document Requirements (flagged during order creation):**

**Step 1: Policy Check Flags Required Documents**
```
Order Proposal for OPP-12345

✓ Validation Passed
⚠ Document Requirements (2 required before billing)

Required Documents:
📄 FAT Certificate (Factory Acceptance Test)
   └─ Policy: Incoterms DAP requires FAT before billing
   └─ Upload to: [rrps://docs/FAT/OPP-12345]
   └─ Status: ⚠ NOT YET UPLOADED

📄 Proof of Delivery to Singapore Port
   └─ Policy: Incoterms DAP requires delivery confirmation
   └─ Upload to: [rrps://docs/DELIVERY/OPP-12345]
   └─ Status: ⚠ NOT YET UPLOADED (will be available after delivery)

Action: Upload FAT certificate now. Delivery proof will be required later.

[Upload FAT Certificate] [Proceed to Post] [Cancel]
```

**Step 2: User Uploads FAT Certificate**
```
Upload FAT Certificate

Drag and drop file here, or click to browse.

Accepted formats: PDF, JPG, PNG
Max size: 10 MB

[Select File]

┌────────────────────────────────────────────────┐
│ File: FAT_OPP12345_v2.pdf (2.3 MB)            │
│ Hash: sha256:a1b2c3d4e5f6... (verified)       │
│ Uploaded: 2025-09-15 10:50:32 UTC             │
│ Status: ✓ Linked to Order (POV-2025-000123)   │
└────────────────────────────────────────────────┘

✓ FAT Certificate uploaded successfully

[Upload Another Document] [Done]
```

**Step 3: Document Status Updated**
```
Required Documents:
📄 FAT Certificate (Factory Acceptance Test)
   └─ Status: ✓ UPLOADED (2025-09-15 10:50:32 UTC)
   └─ File: FAT_OPP12345_v2.pdf (hash verified)

📄 Proof of Delivery to Singapore Port
   └─ Status: ⚠ PENDING (required after delivery milestone)

Billing Readiness: 50% (1 of 2 docs present)
```

**What the User (Sales Ops or Finance Ops) Does:**
1. Sees required documents flagged during order creation
2. Uploads FAT certificate immediately (or during fulfillment)
3. Delivery proof automatically captured after delivery milestone
4. Finance Ops can invoice when all docs present

#### Business Acceptance Criteria
- [ ] Required documents flagged during order creation (based on Incoterms + payment terms policies)
- [ ] Each document shows:
  - [ ] Document type (e.g., FAT Certificate, Bank Guarantee)
  - [ ] Why it's required (policy rule)
  - [ ] Upload link (direct to document repository)
  - [ ] Status (uploaded ✓, pending ⚠, missing ❌)
- [ ] I can upload documents directly from order creation workflow
- [ ] Uploaded documents:
  - [ ] Hash verified (SHA-256)
  - [ ] Linked to order (correlation ID + SAP VBELN)
  - [ ] Metadata captured (upload timestamp, user, file name, hash)
- [ ] Billing readiness % calculated based on document completeness

#### Technical Acceptance Criteria (What Must Be Implemented)
- [ ] Due Diligence Agent identifies required documents:
  - [ ] Query policy catalog for Incoterms + Payment Terms → required artefact types
  - [ ] Return list of required documents with:
    - [ ] Document type (e.g., "FAT Certificate")
    - [ ] Policy rule ID (e.g., POL-027)
    - [ ] Upload URI (e.g., `rrps://docs/FAT/OPP-12345`)
    - [ ] Status (uploaded, pending, missing)
- [ ] Document upload flow:
  - [ ] User uploads file via API or UI
  - [ ] File stored in object storage (Azure Blob or S3)
  - [ ] Hash calculated (SHA-256)
  - [ ] Metadata stored in PostgreSQL:
    - [ ] Correlation ID
    - [ ] Document type
    - [ ] File URI
    - [ ] Hash
    - [ ] Upload timestamp
    - [ ] User email
  - [ ] ArchiveLink client (TE-8) links document to SAP VBELN (after order posted)
- [ ] Billing readiness calculated:
  - [ ] `readiness = (uploaded_docs / total_required_docs) × 100`
- [ ] API endpoints:
  - [ ] `GET /orders/{id}/documents` → returns required documents + status
  - [ ] `POST /orders/{id}/documents/upload` → uploads document + returns hash
  - [ ] `GET /orders/{id}/billing-readiness` → returns readiness %

#### Technical Enablers Required
- **TE-1:** Canonical data models (`Attachment`, `DocumentRequirement`)
- **TE-7:** Policy catalog (Incoterms → required artefacts)
- **TE-8:** ArchiveLink client (link documents to SAP VBELN)
- **TE-12:** Due Diligence Agent workflow (flag required docs)
- **TE-14:** Audit store (PostgreSQL—document metadata)
- **TE-15:** Nexus API endpoints (document upload/retrieval)

#### KPI Impact
- **Artefact Readiness:** 80-90% (documents collected proactively)
- **Billing Cycle Time:** Reduced (no delays due to missing docs)

---

### User Story 3.3: Immutable Audit Trail & Traceability

**As a** Compliance Manager,
**I want** full traceability from opportunity to SAP order (correlation ID → CPI message ID → SAP VBELN),
**So that** I can prove compliance in audits without manual reconstruction.

#### Business Value
- **Audit Efficiency:** Export audit trail in minutes (vs. weeks of manual reconstruction)
- **Compliance Proof:** Immutable evidence for every transaction
- **Risk Reduction:** No "missing links" in audit trail

#### User Experience (What the User Sees)

**Audit Trail Export:**

**Step 1: Search for Transaction**
```
Audit Trail Query

Search by:
○ Opportunity ID: [OPP-12345____]
○ Correlation ID: [POV-2025-000123____]
○ SAP Order Number: [8000123456____]
○ Date Range: [2025-09-01] to [2025-09-30]

[Search]
```

**Step 2: View Audit Trail**
```
Audit Trail for Opportunity OPP-12345

Transaction Overview:
┌─────────────────────────────────────────────────────────────┐
│ Correlation ID:     POV-2025-000123                         │
│ Opportunity:        OPP-12345 (Singapore Engine Sale)       │
│ Customer:           Maritime Solutions Ltd (CUST123)        │
│ SAP Order Number:   8000123456 (VBELN)                      │
│ Status:             Posted to SAP                           │
│ Created by:         joe.smith@rrps.com                      │
│ Created at:         2025-09-15 10:45:32 UTC                 │
└─────────────────────────────────────────────────────────────┘

Transaction Lifecycle:
┌───────────────────┬──────────────────────┬─────────────────────┐
│ Event             │ Timestamp (UTC)      │ Details             │
├───────────────────┼──────────────────────┼─────────────────────┤
│ Opportunity       │ 2025-09-15 10:20:15  │ Retrieved from CEC  │
│ Retrieved         │                      │ OData API           │
├───────────────────┼──────────────────────┼─────────────────────┤
│ Proposal          │ 2025-09-15 10:20:18  │ Auto-filled 42/45   │
│ Generated         │                      │ fields (93%)        │
├───────────────────┼──────────────────────┼─────────────────────┤
│ Policy Check      │ 2025-09-15 10:23:10  │ All policies passed │
│ Passed            │                      │ (5 rules checked)   │
├───────────────────┼──────────────────────┼─────────────────────┤
│ BAPI Validation   │ 2025-09-15 10:23:12  │ Success             │
│ Success           │                      │ CPI-MSG-456789      │
├───────────────────┼──────────────────────┼─────────────────────┤
│ Order Approved    │ 2025-09-15 10:45:30  │ By joe.smith        │
├───────────────────┼──────────────────────┼─────────────────────┤
│ IDoc Submitted    │ 2025-09-15 10:45:32  │ CPI-MSG-456790      │
├───────────────────┼──────────────────────┼─────────────────────┤
│ SAP Order Created │ 2025-09-15 10:45:38  │ VBELN 8000123456    │
└───────────────────┴──────────────────────┴─────────────────────┘

Field-Level Provenance: (42 fields)
┌───────────────────┬───────────┬─────────────────────────────────┐
│ Field             │ Value     │ Source                          │
├───────────────────┼───────────┼─────────────────────────────────┤
│ soldTo            │ CUST123   │ CEC.Account.Id (copied)         │
│ shipTo            │ CUST123-SH│ CEC.Partners.SH (copied)        │
│ plant             │ SG01      │ Rule R-042 (Ship-To → Plant)    │
│ ...               │ ...       │ ...                             │
└───────────────────┴───────────┴─────────────────────────────────┘

Policy Checks: (5 rules)
┌────────────┬─────────────────────────────────────┬────────────┐
│ Policy ID  │ Description                         │ Result     │
├────────────┼─────────────────────────────────────┼────────────┤
│ POL-003    │ Partner roles complete              │ ✓ PASSED   │
│ POL-027    │ Incoterms DAP → FAT required        │ ✓ PASSED   │
│ ...        │ ...                                 │ ...        │
└────────────┴─────────────────────────────────────┴────────────┘

Documents: (2 artefacts)
┌──────────────────┬────────────────────────┬────────────────────┐
│ Document Type    │ File Name              │ Hash (SHA-256)     │
├──────────────────┼────────────────────────┼────────────────────┤
│ FAT Certificate  │ FAT_OPP12345_v2.pdf    │ a1b2c3d4e5f6...    │
│ Delivery Proof   │ DELIVERY_8000123456.pdf│ f6e5d4c3b2a1...    │
└──────────────────┴────────────────────────┴────────────────────┘

[Export as JSON] [Export as PDF] [Close]
```

**What the User (Compliance or Auditor) Does:**
1. Searches by opportunity ID, correlation ID, or SAP order number
2. Views complete audit trail (lifecycle events, field provenance, policy checks, documents)
3. Exports as JSON (machine-readable) or PDF (human-readable)
4. Hands report to auditors (zero manual reconstruction)

#### Business Acceptance Criteria
- [ ] I can search for transactions by opportunity ID, correlation ID, SAP order number, or date range
- [ ] Audit trail shows:
  - [ ] Transaction overview (correlation ID, opportunity ID, SAP VBELN, user, timestamp)
  - [ ] Lifecycle events (opportunity retrieved, proposal generated, validated, approved, posted)
  - [ ] Field-level provenance (every field tagged with source)
  - [ ] Policy checks (which rules checked, results, timestamps)
  - [ ] Documents (type, file name, hash, upload timestamp)
- [ ] Every event timestamped (UTC)
- [ ] Audit trail is **immutable** (cannot be edited after capture)
- [ ] I can export audit trail as JSON or PDF
- [ ] Export includes all transaction details + metadata

#### Technical Acceptance Criteria (What Must Be Implemented)
- [ ] Audit store (PostgreSQL) captures:
  - [ ] `transactions` table:
    - [ ] `correlation_id` (PK)
    - [ ] `opportunity_id`
    - [ ] `cpi_message_id`
    - [ ] `sap_order_number` (VBELN)
    - [ ] `status` (proposed, validated, posted, failed)
    - [ ] `created_by` (user email)
    - [ ] `created_at` (UTC timestamp)
  - [ ] `events` table:
    - [ ] `correlation_id` (FK)
    - [ ] `event_type` (opportunity_retrieved, proposal_generated, policy_check, bapi_validate, idoc_submit, sap_order_created)
    - [ ] `event_timestamp` (UTC)
    - [ ] `event_data` (JSON—details)
  - [ ] `field_provenance` table:
    - [ ] `correlation_id` (FK)
    - [ ] `field_name`
    - [ ] `field_value`
    - [ ] `source`
    - [ ] `source_type` (COPY, LOOKUP, DERIVATION)
    - [ ] `rule_id` (if derivation)
  - [ ] `policy_checks` table:
    - [ ] `correlation_id` (FK)
    - [ ] `policy_id`
    - [ ] `result` (PASSED, FAILED)
    - [ ] `checked_at` (UTC)
  - [ ] `documents` table:
    - [ ] `correlation_id` (FK)
    - [ ] `document_type`
    - [ ] `file_uri`
    - [ ] `hash` (SHA-256)
    - [ ] `uploaded_by`
    - [ ] `uploaded_at` (UTC)
- [ ] All agents write to audit store after each step (append-only, immutable)
- [ ] API endpoints:
  - [ ] `GET /audit/{correlation_id}` → returns complete audit trail
  - [ ] `GET /audit?opportunity_id={id}` → search by opportunity
  - [ ] `GET /audit?sap_order_number={vbeln}` → search by SAP order
  - [ ] `GET /audit?start_date={date}&end_date={date}` → search by date range
  - [ ] `GET /audit/{id}/export?format=json` → export as JSON
  - [ ] `GET /audit/{id}/export?format=pdf` → export as PDF
- [ ] Database constraints:
  - [ ] `correlation_id` is unique (PK)
  - [ ] All writes are append-only (no UPDATE or DELETE allowed)
  - [ ] Timestamps immutable (set on INSERT, cannot change)

#### Technical Enablers Required
- **TE-1:** Canonical data models (all models include `correlation_id`)
- **TE-14:** Audit store (PostgreSQL with append-only tables)
- **TE-15:** Nexus API endpoints (audit trail query/export)
- **TE-ALL:** All agents write events to audit store

#### KPI Impact
- **Traceability:** 100% (every transaction fully traceable)
- **Audit Efficiency:** 99% time reduction (3 weeks → 15 minutes)

---

## Epic 4: Finance Operations - Billing Readiness & Invoice Automation

**Business Outcome:** Invoices triggered on time with all prerequisites met; reduced DSO.

**KPI Impact:**
- Artefact Readiness: 80-90% (primary—required docs present before billing)
- Cycle Time Reduction: Invoice triggered within 24 hours of delivery (vs. 3-5 days)

**POV Phase:** Weeks 5-6 (after Epic 2 complete)
**Estimated Effort:** 4-5 days
**Dependencies:** Epic 2, Epic 3, Technical Enablers 1, 7, 8, 13

---

### User Story 4.1: Billing Readiness Dashboard

**As a** Finance Operations Manager,
**I want** automatic checks for billing readiness (delivery milestone + FAT + Incoterms docs),
**So that** invoices aren't delayed by missing prerequisites discovered at billing time.

#### Business Value
- **Visibility:** Know which orders are invoice-ready vs. blocked
- **Proactive:** Fix missing docs before billing window (not after)
- **Reduced DSO:** Invoice faster when prerequisites met

#### User Experience (What the User Sees)

**Billing Readiness Dashboard:**
```
Billing Readiness Monitor

┌─────────────────────────────────────────────────────────────┐
│ READY TO INVOICE (3 orders)                                 │
└─────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────┐
│ Order 8000123456 │ Singapore Engine Sale │ 🟢 READY (100%)  │
│ Delivery: ✓ Confirmed (2025-09-20)                          │
│ FAT: ✓ Present (hash verified)                              │
│ Incoterms DAP: ✓ All docs present                           │
│ Action: [Trigger Invoice]                                   │
└─────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────┐
│ BLOCKED (2 orders)                                          │
└─────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────┐
│ Order 8000123457 │ Malaysia Power System │ 🔴 BLOCKED (50%) │
│ Delivery: ✓ Confirmed (2025-09-21)                          │
│ FAT: ❌ MISSING                                              │
│ Incoterms EXW: ⚠ Bank guarantee pending                     │
│ Action: [Request FAT] [Follow Up on Bank Guarantee]         │
└─────────────────────────────────────────────────────────────┘

Filters: [All Orders] [Ready] [Blocked] [Date Range]
```

**What the User (Finance Ops) Does:**
1. Opens billing readiness dashboard
2. Sees which orders are ready (green) vs. blocked (red)
3. For ready orders: clicks "Trigger Invoice"
4. For blocked orders: clicks "Request FAT" or follows up on missing docs

#### Business Acceptance Criteria
- [ ] I can see all orders with billing readiness status:
  - [ ] 🟢 Ready (100%): All prerequisites met → can invoice
  - [ ] 🟡 Partial (50-99%): Some prerequisites met → action needed
  - [ ] 🔴 Blocked (<50%): Multiple missing prerequisites → urgent action
- [ ] Each order shows:
  - [ ] Delivery status (confirmed ✓, pending ⚠, not yet shipped ❌)
  - [ ] Document status (FAT present ✓, missing ❌)
  - [ ] Incoterms compliance (docs present ✓, pending ⚠)
  - [ ] Billing readiness % (0-100%)
- [ ] I can filter by status (ready, blocked, date range)
- [ ] Dashboard refreshes every 15 minutes (or on-demand)
- [ ] I can trigger invoice directly from dashboard (for ready orders)

#### Technical Acceptance Criteria (What Must Be Implemented)
- [ ] Financial Ops Agent workflow:
  - [ ] Query all orders with delivery status (from MS5 via CPI events or polling)
  - [ ] For each order, check billing prerequisites:
    - [ ] Delivery confirmed (MS5 delivery milestone reached)
    - [ ] Required documents present (query Due Diligence Agent)
    - [ ] Incoterms docs present (policy-specific checks)
  - [ ] Calculate billing readiness:
    - [ ] `readiness = (met_prerequisites / total_prerequisites) × 100`
  - [ ] Return list of orders with status
- [ ] API endpoint: `GET /billing/readiness` → returns orders with billing status
- [ ] Dashboard UI:
  - [ ] List orders grouped by status (ready, partial, blocked)
  - [ ] Show prerequisite checklist for each order
  - [ ] Provide "Trigger Invoice" button for ready orders
  - [ ] Provide "Request Missing Docs" buttons for blocked orders

#### Technical Enablers Required
- **TE-1:** Canonical data models (`BillingReadinessStatus`)
- **TE-7:** Policy catalog (Incoterms → required billing docs)
- **TE-9:** CPI event listener (delivery milestone events from MS5)
- **TE-13:** Financial Ops Agent workflow
- **TE-15:** Nexus API endpoint (`GET /billing/readiness`)

#### KPI Impact
- **Artefact Readiness:** 80-90% (proactive doc collection)
- **Cycle Time:** Invoice triggered within 24 hours (vs. 3-5 days)

---

### User Story 4.2: Event-Driven Invoice Triggers

**As a** Finance Operations Manager,
**I want** invoice triggers when delivery + prerequisites are confirmed,
**So that** I don't have to manually monitor orders for billing windows.

#### Business Value
- **Automation:** Invoices triggered automatically when ready
- **Speed:** Invoices created within hours of delivery (vs. days)
- **Consistency:** No missed billing windows

#### User Experience (What the User Sees)

**Automated Invoice Trigger:**

**Step 1: Delivery Event Received (Finance Ops notified)**
```
Invoice Trigger Alert

Order: 8000123456 (Singapore Engine Sale)
Customer: Maritime Solutions Ltd (CUST123)

Status: 🟢 READY TO INVOICE

Prerequisites Met:
✓ Delivery confirmed (2025-09-20 14:32 UTC)
✓ FAT certificate present (hash verified)
✓ Incoterms DAP docs present (proof of delivery to Singapore Port)

Recommended Action: Trigger invoice

[Trigger Invoice] [Review Prerequisites] [Snooze 24h]
```

**Step 2: User Clicks "Trigger Invoice"**
```
Invoice triggered successfully

Invoice Number: 9000567890 (SAP)
Order: 8000123456
Amount: $2.5M
Due Date: 2025-10-20 (30 days)

Control Evidence Captured:
- Delivery confirmed: 2025-09-20 14:32 UTC (CPI-MSG-789123)
- FAT certificate: a1b2c3d4e5f6... (verified)
- Incoterms DAP docs: f6e5d4c3b2a1... (verified)
- Invoice triggered by: jane.doe@rrps.com (2025-09-20 15:10 UTC)

[View Invoice] [Done]
```

**What the User (Finance Ops) Does:**
1. Receives alert when order becomes invoice-ready
2. Reviews prerequisites (delivery confirmed, docs present)
3. Clicks "Trigger Invoice"
4. Invoice created in SAP automatically

#### Business Acceptance Criteria
- [ ] I receive an alert when an order becomes invoice-ready (delivery confirmed + all docs present)
- [ ] Alert includes:
  - [ ] Order number
  - [ ] Customer
  - [ ] Prerequisites met (delivery, docs)
  - [ ] Recommended action (trigger invoice)
- [ ] I can click "Trigger Invoice" to create invoice in SAP
- [ ] Invoice created in SAP within 10 seconds
- [ ] Control evidence captured automatically:
  - [ ] Delivery confirmation (timestamp + CPI message ID)
  - [ ] Document hashes (FAT, Incoterms docs)
  - [ ] User who triggered invoice
  - [ ] Invoice trigger timestamp
- [ ] I can review control evidence for A/R audits

**Edge Cases & Error Handling** (added from critique):
- [ ] **Out-of-Order Events**: If invoice trigger event arrives before delivery event (rare CPI race condition), queue trigger until delivery confirmed
- [ ] **Duplicate Event Deduplication**: If same delivery event received twice (CPI retry), idempotency check prevents duplicate invoice triggers (correlation_id matching)
- [ ] **Malformed Event Handling**: If CPI delivery event missing required fields (e.g., no VBELN), log error and alert Finance Ops for manual intervention
- [ ] **Partial Deliveries**: If order has 3 line items but only 2 delivered, allow Finance Ops to choose: "Invoice delivered items now" or "Wait for complete delivery"
- [ ] **Billing Block Detection**: If SAP order has billing block (credit hold, compliance hold), detect and show blocker: "Invoice cannot be created: Billing block Z01 (Credit Hold). Contact A/R team."

#### Technical Acceptance Criteria (What Must Be Implemented)
- [ ] Financial Ops Agent workflow:
  - [ ] Listen for CPI events: "Delivery milestone reached for VBELN-XXX"
  - [ ] On delivery event, check billing prerequisites:
    - [ ] Query Due Diligence Agent: "Are all required docs present for VBELN-XXX?"
    - [ ] If yes: send alert to Finance Ops
  - [ ] On user "Trigger Invoice" action:
    - [ ] Call SAP invoice creation API (via CPI)
    - [ ] Capture invoice number
    - [ ] Write control evidence to audit store:
      - [ ] Delivery timestamp + CPI message ID
      - [ ] Document hashes
      - [ ] User email + invoice trigger timestamp
      - [ ] Invoice number
- [ ] CPI event listener (TE-9):
  - [ ] Subscribe to MS5 delivery milestone events
  - [ ] Forward events to Financial Ops Agent
- [ ] API endpoints:
  - [ ] `POST /billing/trigger-invoice` → creates invoice in SAP
  - [ ] `GET /billing/{order_id}/control-evidence` → returns audit trail

#### Technical Enablers Required
- **TE-1:** Canonical data models (`InvoiceTriggerEvent`, `ControlEvidence`)
- **TE-9:** CPI event listener (delivery milestone events)
- **TE-13:** Financial Ops Agent workflow
- **TE-14:** Audit store (control evidence)
- **TE-15:** Nexus API endpoint (`POST /billing/trigger-invoice`)

#### KPI Impact
- **Cycle Time:** Invoice triggered within 4 hours of delivery (vs. 3-5 days)
- **DSO Reduction:** 4 days faster cash collection

---

### User Story 4.3: Control Evidence for A/R Audits

**As a** Finance Operations Manager,
**I want** control evidence captured automatically (delivery confirmation + docs verified),
**So that** A/R has proof of compliance without manual documentation.

#### Business Value
- **Audit Readiness:** Control evidence available instantly (no manual reconstruction)
- **Compliance Proof:** Immutable evidence for every invoice
- **Efficiency:** A/R audits completed in hours (vs. weeks)

#### User Experience (What the User Sees)

**Control Evidence Report:**
```
Control Evidence Report
Invoice: 9000567890 | Order: 8000123456

Billing Prerequisites:
┌─────────────────────────┬────────────────────────┬──────────────────┐
│ Prerequisite            │ Status                 │ Verified At      │
├─────────────────────────┼────────────────────────┼──────────────────┤
│ Delivery Confirmed      │ ✓ VERIFIED             │ 2025-09-20 14:32 │
│   CPI Message ID        │ CPI-MSG-789123         │                  │
│   Delivery Note         │ DN-8000123456          │                  │
├─────────────────────────┼────────────────────────┼──────────────────┤
│ FAT Certificate         │ ✓ VERIFIED             │ 2025-09-15 10:50 │
│   File Name             │ FAT_OPP12345_v2.pdf    │                  │
│   Hash (SHA-256)        │ a1b2c3d4e5f6...        │                  │
│   Uploaded By           │ joe.smith@rrps.com     │                  │
├─────────────────────────┼────────────────────────┼──────────────────┤
│ Incoterms DAP Docs      │ ✓ VERIFIED             │ 2025-09-20 14:35 │
│   Delivery Proof        │ DELIVERY_8000123456.pdf│                  │
│   Hash (SHA-256)        │ f6e5d4c3b2a1...        │                  │
└─────────────────────────┴────────────────────────┴──────────────────┘

Policy Compliance:
┌────────────┬─────────────────────────────────────┬────────────┐
│ Policy ID  │ Description                         │ Result     │
├────────────┼─────────────────────────────────────┼────────────┤
│ POL-027    │ Incoterms DAP → FAT required        │ ✓ PASSED   │
│ POL-045    │ Delivery → Invoice within 30 days   │ ✓ PASSED   │
└────────────┴─────────────────────────────────────┴────────────┘

Invoice Details:
- Invoice Number: 9000567890
- Amount: $2.5M
- Due Date: 2025-10-20 (30 days)
- Triggered By: jane.doe@rrps.com
- Triggered At: 2025-09-20 15:10:32 UTC

[Export as PDF] [Export as JSON] [Close]
```

**What the User (Finance Ops or A/R Auditor) Does:**
1. Searches for invoice by invoice number or order number
2. Views control evidence report (delivery confirmation, docs, policy compliance)
3. Exports as PDF for audit submission
4. Hands to auditors (zero manual reconstruction)

#### Business Acceptance Criteria
- [ ] I can search for invoices by invoice number, order number, or date range
- [ ] Control evidence report shows:
  - [ ] Delivery confirmation (timestamp + CPI message ID + delivery note)
  - [ ] Documents verified (file name, hash, upload timestamp, user)
  - [ ] Policy compliance checks (rule IDs + results + timestamps)
  - [ ] Invoice details (number, amount, due date, triggered by, timestamp)
- [ ] Evidence is **immutable** (cannot be edited after capture)
- [ ] I can export as PDF (for audit submission) or JSON (for data analysis)
- [ ] Export includes all evidence + metadata

#### Technical Acceptance Criteria (What Must Be Implemented)
- [ ] Audit store (PostgreSQL) captures control evidence:
  - [ ] `control_evidence` table:
    - [ ] `invoice_number` (FK to invoices)
    - [ ] `order_number` (VBELN)
    - [ ] `delivery_confirmed_at` (UTC timestamp)
    - [ ] `delivery_cpi_message_id`
    - [ ] `delivery_note`
  - [ ] Link to `documents` table (FAT, Incoterms docs)
  - [ ] Link to `policy_checks` table (compliance results)
- [ ] Financial Ops Agent writes control evidence after invoice trigger:
  - [ ] Delivery confirmation details
  - [ ] Document verification (hashes)
  - [ ] Policy compliance results
  - [ ] Invoice metadata (number, amount, user, timestamp)
- [ ] API endpoints:
  - [ ] `GET /billing/{invoice_number}/control-evidence` → returns full evidence report
  - [ ] `GET /billing/{invoice_number}/export?format=pdf` → exports as PDF
  - [ ] `GET /billing/{invoice_number}/export?format=json` → exports as JSON

#### Technical Enablers Required
- **TE-1:** Canonical data models (`ControlEvidence`)
- **TE-13:** Financial Ops Agent workflow (capture evidence)
- **TE-14:** Audit store (immutable evidence tables)
- **TE-15:** Nexus API endpoint (evidence query/export)

#### KPI Impact
- **Traceability:** 100% (every invoice has control evidence)
- **Audit Efficiency:** 99% time reduction (3 weeks → 15 minutes)

---

## Epic 5: POV Success - Metrics & Decision Pack

**Business Outcome:** Data-driven recommendation (scale/iterate/stop) based on measurable KPIs.

**KPI Impact:**
- All 5 KPIs measured (baseline vs. pilot)
- Decision pack delivered with clear recommendation

**POV Phase:** Weeks 9-10 (POV evaluation)
**Estimated Effort:** 4-5 days
**Dependencies:** Epic 2, Epic 3, Epic 4 complete; pilot execution data

---

### User Story 5.1: Baseline Data Collection

**As a** POV Analyst,
**I want** baseline metrics from historical orders (last 3 months),
**So that** I can measure improvement accurately (baseline vs. pilot).

#### Business Value
- **Accurate Comparison:** Baseline vs. pilot using identical definitions
- **Data-Driven Decision:** Quantify improvement (not anecdotal)
- **Credibility:** ISO/IEC TR 24030 compliant metrics

#### User Experience (What the User Sees)

**Baseline Data Collection Report:**
```
Baseline Metrics Collection
Period: 2025-06-01 to 2025-08-31 (3 months)
Order Types: Same types used in pilot (Engine sales, Power systems)

Data Sources:
✓ CEC: Opportunity dates, account data
✓ IPAS: Configuration data
✓ MS5: Order creation timestamps, rework events, billing blocks
✓ Document Repository: Artefact upload timestamps

Cohort: 50 orders (matching pilot order types)

Baseline Results:
┌─────────────────────────────┬──────────┬────────────┬──────────┐
│ KPI                         │ Baseline │ Target     │ Status   │
├─────────────────────────────┼──────────┼────────────┼──────────┤
│ Acceptance Rate             │ 45%      │ ≥70%       │ ⚠ Below  │
│ Cycle Time Reduction        │ 0%       │ 30-40%     │ N/A      │
│ First-Time-Right            │ 62%      │ +15-20%    │ N/A      │
│ Artefact Readiness          │ 35%      │ 80-90%     │ ⚠ Below  │
│ Traceability                │ 20%      │ 100%       │ ⚠ Below  │
└─────────────────────────────┴──────────┴────────────┴──────────┘

Detailed Metrics:
- Average cycle time (order-ready → posted): 45 minutes
- Average rework cycles per order: 1.8
- Average time to invoice (delivery → invoice): 7 days
- Artefacts missing at billing: 65% of orders

[Export Baseline Report] [Proceed to Pilot]
```

**What the User (POV Analyst) Does:**
1. Defines baseline period (last 3 months)
2. Selects cohort (same order types as pilot)
3. Reviews baseline metrics
4. Exports baseline report for comparison

#### Business Acceptance Criteria
- [ ] I can define baseline period (start date, end date)
- [ ] I can select cohort (order types matching pilot)
- [ ] Baseline metrics calculated automatically:
  - [ ] Acceptance Rate: % of fields manually entered (no auto-fill in baseline)
  - [ ] Cycle Time: Average time from "order-ready" to "posted"
  - [ ] First-Time-Right: % of orders posted without rework
  - [ ] Artefact Readiness: % of required docs present before billing
  - [ ] Traceability: % of orders with full audit trail
- [ ] Data sourced from:
  - [ ] CEC (opportunity dates)
  - [ ] IPAS (config data)
  - [ ] MS5 (order timestamps, rework events)
  - [ ] Document repository (artefact timestamps)
- [ ] I can export baseline report (PDF or JSON)

#### Technical Acceptance Criteria (What Must Be Implemented)
- [ ] Baseline data collection script (Python):
  - [ ] Query CEC for historical opportunities
  - [ ] Query MS5 for historical orders (matching opportunities)
  - [ ] Calculate metrics:
    - [ ] `acceptance_rate = 0%` (no auto-fill in baseline)
    - [ ] `cycle_time = avg(order_posted_timestamp - opportunity_ready_timestamp)`
    - [ ] `first_time_right = (orders_without_rework / total_orders) × 100`
    - [ ] `artefact_readiness = (orders_with_docs_at_billing / total_orders) × 100`
    - [ ] `traceability = (orders_with_audit_trail / total_orders) × 100`
  - [ ] Store baseline metrics in PostgreSQL
- [ ] API endpoint: `GET /metrics/baseline` → returns baseline metrics
- [ ] Export: `GET /metrics/baseline/export?format=pdf`

#### Technical Enablers Required
- **TE-2:** CEC OData client (historical data query)
- **TE-14:** Audit store (baseline metrics table)
- **TE-15:** Nexus API endpoint (baseline metrics query)

#### KPI Impact
- **Decision Quality:** Accurate baseline enables credible comparison

---

### User Story 5.2: Pilot Execution & Metrics Capture

**As a** POV Analyst,
**I want** pilot metrics captured automatically during pilot execution,
**So that** I can compare baseline vs. pilot without manual data collection.

#### Business Value
- **Automated Measurement:** No manual metric collection
- **Real-Time Visibility:** See pilot performance during execution
- **Accurate Comparison:** Identical metric definitions (baseline vs. pilot)

#### User Experience (What the User Sees)

**Pilot Metrics Dashboard (live during pilot):**
```
Pilot Execution Metrics
Period: 2025-09-15 to 2025-09-30 (2 weeks)
Orders Processed: 25 of 50 (target)

Real-Time KPIs:
┌─────────────────────────────┬──────────┬──────────┬────────────┬──────────┐
│ KPI                         │ Baseline │ Pilot    │ Target     │ Status   │
├─────────────────────────────┼──────────┼──────────┼────────────┼──────────┤
│ Acceptance Rate             │ 45%      │ 78%      │ ≥70%       │ ✓ GREEN  │
│ Cycle Time Reduction        │ 0%       │ 35%      │ 30-40%     │ ✓ GREEN  │
│ First-Time-Right            │ 62%      │ 80%      │ +15-20%    │ ✓ GREEN  │
│ Artefact Readiness          │ 35%      │ 88%      │ 80-90%     │ ✓ GREEN  │
│ Traceability                │ 20%      │ 100%     │ 100%       │ ✓ GREEN  │
└─────────────────────────────┴──────────┴──────────┴────────────┴──────────┘

Detailed Pilot Metrics:
- Average cycle time (order-ready → posted): 29 minutes (was 45 min)
- Average rework cycles per order: 0.4 (was 1.8)
- Average time to invoice (delivery → invoice): 6 hours (was 7 days)
- Artefacts missing at billing: 12% of orders (was 65%)

User Feedback:
- Sales Ops: "Order creation is 10x faster. I can finally keep up with demand."
- Finance Ops: "Billing readiness dashboard is a game-changer."

[Refresh Metrics] [Export Pilot Report] [Compare Baseline vs Pilot]
```

**What the User (POV Analyst or Leadership) Does:**
1. Monitors pilot metrics in real-time during execution
2. Sees progress toward targets (green = on track, amber = needs attention, red = off track)
3. Reviews user feedback
4. Exports pilot report for decision pack

#### Business Acceptance Criteria
- [ ] Pilot metrics captured automatically during pilot execution (no manual data entry)
- [ ] Metrics calculated using identical definitions as baseline:
  - [ ] Acceptance Rate: % of auto-filled fields accepted without edits
  - [ ] Cycle Time Reduction: % reduction in "order-ready → posted" time
  - [ ] First-Time-Right: % of orders posted without rework
  - [ ] Artefact Readiness: % of required docs present before billing
  - [ ] Traceability: % of orders with full audit trail (correlation ID → SAP VBELN)
- [ ] Dashboard shows baseline vs. pilot vs. target for each KPI
- [ ] Status color-coded:
  - [ ] Green: At or above target
  - [ ] Amber: Near target (within 10%)
  - [ ] Red: Below target (>10% gap)
- [ ] I can export pilot report (PDF or JSON)

#### Technical Acceptance Criteria (What Must Be Implemented)
- [ ] Pilot metrics auto-captured during execution:
  - [ ] Sales Ops Agent logs:
    - [ ] Proposal generation (timestamp)
    - [ ] Fields auto-filled vs. manually edited
    - [ ] Validation results (pass/fail)
    - [ ] Order posted (timestamp)
  - [ ] Due Diligence Agent logs:
    - [ ] Policy checks (timestamp, results)
    - [ ] Document requirements (present/missing)
  - [ ] Financial Ops Agent logs:
    - [ ] Billing readiness checks (timestamp, results)
    - [ ] Invoice triggers (timestamp)
  - [ ] Audit store logs:
    - [ ] Correlation ID → CPI message ID → SAP VBELN linkage
- [ ] Metrics calculation (real-time):
  - [ ] `acceptance_rate = (auto_filled_fields_accepted / total_auto_filled_fields) × 100`
  - [ ] `cycle_time_reduction = ((baseline_avg_time - pilot_avg_time) / baseline_avg_time) × 100`
  - [ ] `first_time_right = (orders_without_rework / total_orders) × 100`
  - [ ] `artefact_readiness = (orders_with_docs_at_billing / total_orders) × 100`
  - [ ] `traceability = (orders_with_full_audit_trail / total_orders) × 100`
- [ ] API endpoint: `GET /metrics/pilot` → returns pilot metrics
- [ ] Dashboard refreshes every 5 minutes

#### Technical Enablers Required
- **TE-14:** Audit store (pilot metrics table)
- **TE-15:** Nexus API endpoint (pilot metrics query)
- **TE-ALL:** All agents log events for metrics capture

#### KPI Impact
- **Decision Quality:** Real-time visibility enables mid-pilot adjustments

---

### User Story 5.3: Metrics Comparison & Scorecard

**As a** POV Analyst,
**I want** a scorecard comparing baseline vs. pilot with clear status (Green/Amber/Red),
**So that** I can present results to leadership with a clear recommendation.

#### Business Value
- **Executive Summary:** One-page scorecard for leadership
- **Data-Driven Recommendation:** Clear scale/iterate/stop decision
- **Credibility:** ISO/IEC TR 24030 compliant comparison

#### User Experience (What the User Sees)

**POV Scorecard (final):**
```
RRPS Lead-to-Cash POV: Scorecard
Period: 2025-09-15 to 2025-09-30 (2 weeks pilot)
Cohort: 50 orders (Engine sales, Power systems)

┌─────────────────────────────┬──────────┬──────────┬────────────┬──────────┐
│ KPI                         │ Baseline │ Pilot    │ Target     │ Status   │
├─────────────────────────────┼──────────┼──────────┼────────────┼──────────┤
│ Acceptance Rate             │ 45%      │ 78%      │ ≥70%       │ 🟢 GREEN │
│ Cycle Time Reduction        │ 0%       │ 35%      │ 30-40%     │ 🟢 GREEN │
│ First-Time-Right            │ 62%      │ 80%      │ +15-20%    │ 🟢 GREEN │
│ Artefact Readiness          │ 35%      │ 88%      │ 80-90%     │ 🟢 GREEN │
│ Traceability                │ 20%      │ 100%     │ 100%       │ 🟢 GREEN │
└─────────────────────────────┴──────────┴──────────┴────────────┴──────────┘

Overall Status: 🟢 GREEN (5/5 KPIs at or above target)

Interpretation:
- All 5 KPIs achieved or exceeded targets
- Traceability at 100% (governance requirement met)
- User feedback overwhelmingly positive

Recommendation: SCALE
- Expand to additional order types (Marine engines, Industrial power systems)
- Onboard additional Sales Ops and Finance Ops users
- Plan 6-month rollout with quarterly reviews

Business Impact:
- Time Saved: 7.5 hours → 30 minutes per day per Sales Ops user (93% reduction)
- DSO Reduction: 7 days → 6 hours (invoice trigger time)
- Compliance: 100% audit-ready transactions (vs. 20% baseline)

[View Detailed Report] [Export Scorecard (PDF)] [Close]
```

**What the User (POV Analyst or Leadership) Does:**
1. Reviews scorecard (one-page summary)
2. Sees overall status (Green = recommend scale, Amber = iterate, Red = stop)
3. Reads recommendation
4. Exports scorecard for board presentation

#### Business Acceptance Criteria
- [ ] Scorecard shows baseline vs. pilot vs. target for all 5 KPIs
- [ ] Each KPI has status:
  - [ ] 🟢 Green: At or above target (and Traceability = 100%)
  - [ ] 🟡 Amber: Near target (within 10%) OR variable results
  - [ ] 🔴 Red: Below target (>10% gap) OR governance issues (Traceability <100%)
- [ ] Overall status calculated:
  - [ ] Green: All KPIs green
  - [ ] Amber: 1-2 KPIs amber
  - [ ] Red: Any KPI red OR Traceability <100%
- [ ] Recommendation provided:
  - [ ] Scale: Green overall + positive user feedback
  - [ ] Iterate: Amber overall + specific improvement areas
  - [ ] Stop: Red overall + governance issues unresolved
- [ ] Business impact summary (time saved, DSO reduction, compliance improvement)
- [ ] I can export scorecard as PDF (for presentations)

#### Technical Acceptance Criteria (What Must Be Implemented)
- [ ] Scorecard generation script:
  - [ ] Query baseline metrics (from User Story 5.1)
  - [ ] Query pilot metrics (from User Story 5.2)
  - [ ] Compare vs. targets
  - [ ] Calculate status (Green/Amber/Red) per KPI
  - [ ] Calculate overall status
  - [ ] Generate recommendation (Scale/Iterate/Stop)
  - [ ] Calculate business impact (time saved, DSO, compliance)
- [ ] API endpoint: `GET /metrics/scorecard` → returns scorecard
- [ ] Export: `GET /metrics/scorecard/export?format=pdf`

#### Technical Enablers Required
- **TE-14:** Audit store (baseline + pilot metrics)
- **TE-15:** Nexus API endpoint (scorecard generation)

#### KPI Impact
- **Decision Quality:** Clear recommendation based on data (not opinions)

---

## Epic 6: User Validation - UAT & Pilot

**Business Outcome:** Users confirm the solution works before live deployment; feedback incorporated.

**KPI Impact:**
- User Satisfaction: Positive feedback from Sales Ops, Finance Ops, Sales Manager
- Adoption Readiness: Users trained and confident

**POV Phase:** Weeks 7-8 (UAT) + Weeks 9-10 (Pilot execution)
**Estimated Effort:** 6-7 days
**Dependencies:** Epic 2, Epic 3, Epic 4 complete (all workflows functional)

---

### User Story 6.1: UAT Scenario Definition & Guided Walkthroughs

**As a** Sales Operations Manager,
**I want** guided UAT with realistic scenarios,
**So that** I can confirm the system works for my daily workflow before going live.

#### Business Value
- **Confidence:** Users validate solution works for their real workflows
- **Feedback:** Identify usability issues before pilot
- **Training:** Users learn system during UAT

#### User Experience (What the User Sees)

**UAT Scenario Walkthrough:**
```
UAT Scenario 1: Create Order from Qualified Opportunity

Objective: Validate that you can create a sales order from a CEC opportunity in <5 minutes.

Test Data:
- Opportunity: UAT-OPP-001 (Test Customer, Singapore Engine Sale)
- Expected Outcome: Order created in MS5 with VBELN returned

Steps:
1. Open Sales Ops Agent platform
2. Search for UAT-OPP-001
3. Click "Create Order Proposal"
4. Review auto-generated proposal (verify 70%+ fields auto-filled)
5. Edit 1-2 fields if needed
6. Click "Validate Order" (verify BAPI simulation passes)
7. Click "Approve & Post Order"
8. Verify SAP order number (VBELN) returned

Success Criteria:
✓ Order proposal generated in <5 seconds
✓ ≥70% of fields auto-filled correctly
✓ Validation passes (no business errors)
✓ Order posted successfully (VBELN returned)
✓ Total time <5 minutes

[Start Scenario] [Mark Complete] [Report Issue]
```

**UAT Feedback Form (after each scenario):**
```
Scenario 1 Feedback

How did it go?
○ Worked perfectly ✓ (selected)
○ Worked with minor issues
○ Did not work

What worked well?
[Auto-fill was accurate. Validation caught a missing partner before posting. Very fast!]

What could be improved?
[Plant field was yellow (derived) but I'm not sure what rule was used. Add tooltip?]

Would you use this in production?
○ Yes, definitely ✓ (selected)
○ Yes, with improvements
○ No, needs major changes

[Submit Feedback]
```

**What the User (Sales Ops, Finance Ops, Sales Manager) Does:**
1. Completes guided UAT scenarios (5-10 scenarios per role)
2. Validates system works for real workflows
3. Provides feedback (what worked, what needs improvement)
4. Confirms readiness for pilot

#### Business Acceptance Criteria
- [ ] I receive guided UAT scenarios for my role (Sales Ops, Finance Ops, Sales Manager)
- [ ] Each scenario includes:
  - [ ] Objective (what to validate)
  - [ ] Test data (realistic opportunity, order, invoice)
  - [ ] Step-by-step instructions
  - [ ] Success criteria (measurable outcomes)
- [ ] I can mark scenarios complete and provide feedback
- [ ] Feedback captured:
  - [ ] What worked well
  - [ ] What could be improved
  - [ ] Would I use this in production (Yes/No/With improvements)
- [ ] I can report issues (bugs, usability problems)

#### Technical Acceptance Criteria (What Must Be Implemented)
- [ ] UAT scenario library (5-10 scenarios per role):
  - [ ] Sales Manager: Opportunity readiness scoring, gap identification
  - [ ] Sales Ops: Order proposal, validation, posting
  - [ ] Finance Ops: Billing readiness, invoice trigger, control evidence
  - [ ] Compliance: Policy checks, audit trail export
- [ ] Test data setup:
  - [ ] Synthetic CEC opportunities
  - [ ] Synthetic IPAS configs
  - [ ] UAT environment (isolated from production)
- [ ] Feedback capture:
  - [ ] UAT feedback form (web UI or API)
  - [ ] Store feedback in PostgreSQL
  - [ ] Issue tracking (link to bugs/improvements)
- [ ] API endpoints:
  - [ ] `GET /uat/scenarios` → returns scenario list
  - [ ] `POST /uat/scenarios/{id}/complete` → mark scenario complete
  - [ ] `POST /uat/feedback` → submit feedback

#### Technical Enablers Required
- **TE-15:** Nexus API endpoints (UAT scenario delivery, feedback capture)
- **TE-16:** Test data generator (synthetic CEC/IPAS data)
- **TE-17:** UAT environment (isolated from production)

#### KPI Impact
- **User Satisfaction:** Positive feedback → high adoption readiness

---

### User Story 6.2: Pilot Execution with Real Orders

**As a** Sales Operations Manager,
**I want** to process real orders in a pilot (not just test data),
**So that** the POV proves value with my actual work.

#### Business Value
- **Real-World Validation:** Pilot uses actual opportunities, not synthetic data
- **Confidence:** Users trust solution works for real scenarios
- **Metrics Credibility:** Pilot results based on real workflows

#### User Experience (What the User Sees)

**Pilot Kickoff (Week 9):**
```
Pilot Execution - Week 1

Cohort: 25 real orders (selected by Sales Ops)
- 15 Engine sales (Singapore, Malaysia)
- 10 Power systems (Thailand, Indonesia)

Your Role: Process these orders using Sales Ops Agent (instead of SAP GUI)

Support:
- 24/7 support hotline: +65 8023 8808
- Issue tracking: pilot-support@integrum.global
- Daily standup: 9:00 AM SGT (review progress, address blockers)

[View Order Queue] [Start Processing] [Report Issue]
```

**Order Queue (pilot orders):**
```
Pilot Order Queue

┌──────────────────────────────────────────────────────────────┐
│ OPP-PILOT-001 │ Singapore Engine Sale │ 🟢 READY (100%)     │
│ Status: Not yet processed                                    │
│ Action: [Create Order]                                       │
└──────────────────────────────────────────────────────────────┘

┌──────────────────────────────────────────────────────────────┐
│ OPP-PILOT-002 │ Malaysia Power System │ 🟡 AMBER (87%)      │
│ Status: Not yet processed                                    │
│ Action: [Fix Gaps First] [Create Order]                     │
└──────────────────────────────────────────────────────────────┘

...

Progress: 12 of 25 orders processed (48%)
Average cycle time: 28 minutes (target: <30 min)
Acceptance rate: 76% (target: ≥70%)

[Refresh] [Export Progress Report]
```

**What the User (Sales Ops) Does:**
1. Receives pilot order queue (real opportunities)
2. Processes orders using Sales Ops Agent (same as UAT, but real data)
3. Tracks progress (orders completed, cycle time, acceptance rate)
4. Reports issues if encountered
5. Attends daily standup to review progress

#### Business Acceptance Criteria
- [ ] I receive a queue of real pilot orders (not synthetic test data)
- [ ] I can process orders using Sales Ops Agent (same workflow as UAT)
- [ ] I have support available (hotline, email, daily standup)
- [ ] I can track my progress (orders completed, cycle time, acceptance rate)
- [ ] I can report issues and see resolution status
- [ ] Pilot metrics captured automatically (no manual tracking)

#### Technical Acceptance Criteria (What Must Be Implemented)
- [ ] Pilot order selection:
  - [ ] Sales Ops selects 25-50 real opportunities from CEC
  - [ ] Opportunities marked as "pilot cohort" (tag in CEC or internal DB)
- [ ] Pilot execution:
  - [ ] Users process pilot orders using Sales Ops Agent
  - [ ] All metrics captured (same as User Story 5.2)
- [ ] Support infrastructure:
  - [ ] Issue tracking system (Jira, GitLab Issues, or similar)
  - [ ] Daily standup (review progress, address blockers)
  - [ ] Hotline staffed during pilot (9-5 SGT)
- [ ] Progress tracking:
  - [ ] Dashboard shows pilot progress (orders completed, cycle time, acceptance rate)
  - [ ] Refresh every 5 minutes

#### Technical Enablers Required
- **TE-15:** Nexus API endpoints (pilot order queue, progress tracking)
- **TE-18:** Support infrastructure (issue tracking, hotline)

#### KPI Impact
- **User Satisfaction:** Real-world validation → high confidence
- **Metrics Credibility:** Pilot results based on actual workflows

---

### User Story 6.3: Feedback Incorporation & Iteration

**As a** Sales Operations Manager,
**I want** feedback from UAT and pilot incorporated before go-live,
**So that** usability issues are fixed and the system is production-ready.

#### Business Value
- **Quality:** Usability issues fixed before go-live
- **Adoption:** Users confident in system (feedback addressed)
- **Continuous Improvement:** Iteration based on real user input

#### User Experience (What the User Sees)

**Feedback Review & Iteration:**
```
UAT & Pilot Feedback Summary

Total Feedback: 42 items
- 28 positive comments
- 10 improvement suggestions
- 4 bugs reported

Top Improvement Suggestions:
1. Add tooltip for derived fields (explain business rule used) - 7 users
2. Add "Save Draft" button (allow partial proposal save) - 5 users
3. Highlight edited fields in yellow (show what user changed) - 4 users

Status:
✓ Improvement 1: Implemented (2025-09-25)
✓ Improvement 2: Implemented (2025-09-26)
⏳ Improvement 3: In progress (ETA: 2025-09-28)

Bugs:
✓ Bug 1: Plant field incorrectly derived for Ship-To in Malaysia - FIXED
✓ Bug 2: BAPI validation timeout on large orders - FIXED
✓ Bug 3: FAT upload fails for files >5MB - FIXED
⏳ Bug 4: Dashboard refresh slow (>10 sec) - IN PROGRESS

[View Detailed Feedback] [Close]
```

**What the User (Sales Ops or POV Team) Does:**
1. Reviews aggregated feedback from UAT and pilot
2. Sees which improvements implemented vs. in progress
3. Confirms bugs fixed before go-live
4. Re-tests improvements during pilot Week 2

#### Business Acceptance Criteria
- [ ] All UAT and pilot feedback aggregated and reviewed
- [ ] Feedback categorized:
  - [ ] Positive comments (what worked well)
  - [ ] Improvement suggestions (usability enhancements)
  - [ ] Bugs (functional issues)
- [ ] Top improvements prioritized and implemented during pilot
- [ ] All critical bugs fixed before go-live
- [ ] I can see status of each feedback item (implemented, in progress, deferred)

#### Technical Acceptance Criteria (What Must Be Implemented)
- [ ] Feedback aggregation:
  - [ ] Query all UAT feedback (from User Story 6.1)
  - [ ] Query all pilot feedback (from User Story 6.2)
  - [ ] Categorize (positive, improvement, bug)
  - [ ] Prioritize by frequency (how many users reported)
- [ ] Iteration process:
  - [ ] Top 3-5 improvements implemented during pilot
  - [ ] Critical bugs fixed immediately
  - [ ] Non-critical improvements deferred to post-POV roadmap
- [ ] Status tracking:
  - [ ] Each feedback item has status (implemented, in progress, deferred)
  - [ ] Status visible to users (dashboard or report)
- [ ] API endpoint: `GET /uat/feedback-summary` → returns aggregated feedback

#### Technical Enablers Required
- **TE-15:** Nexus API endpoint (feedback aggregation)
- **TE-18:** Issue tracking (feedback status)

#### KPI Impact
- **User Satisfaction:** Feedback addressed → high adoption readiness

---

## Technical Enablers Section

**Purpose:** This section lists all technical implementation tasks that enable the business user stories above. These are NOT user stories—they are infrastructure, integration, and platform work required to deliver business value.

**Organization:** Technical enablers organized by layer (Integration, Data, Platform, Testing).

---

### Integration Layer

**TE-1: Canonical Data Models** (Story 1.1 in v2.0)
- Pydantic models for all payloads: `SalesOrderProposal`, `OpportunityData`, `BOMData`, `DDSummary`, `POVMetrics`
- Field-level provenance tracking
- JSON schema export for OpenAPI
- **Effort:** 1.5 days | **Blocks:** All other stories

**TE-2: CEC OData Client** (Story 1.2 in v2.0)
- OAuth2 authentication + token refresh
- Methods: `get_opportunity()`, `get_business_partner()`, `get_opportunities_by_stage()`
- Integration tests with CPI sandbox (NO MOCKS)
- **Effort:** 3 days | **Blocks:** Epic 1 (Opportunity Assessment)

**TE-3: IPAS Client** (Story 1.6 in v2.0)
- Methods: `get_configuration()`, `get_configuration_status()`
- BOM parsing to `SalesOrderItem` list
- Integration tests with IPAS proxy (NO MOCKS)
- **Effort:** 2 days | **Blocks:** Epic 2 (Sales Ops Agent)

**TE-4: Field Mapping Registry** (Story 1.7 in v2.0)
- CEC/IPAS → MS5 field mappings (versioned)
- Business rule catalog (e.g., Ship-To → Plant)
- **Effort:** 2 days | **Blocks:** Epic 2 (Sales Ops Agent)

**TE-5: MS5 BAPI Client** (Story 1.3 in v2.0)
- Method: `simulate_sales_order()` → `SAPValidationResponse`
- Parse BAPI return messages into `ValidationIssue` list
- **Timeout/Retry/Circuit Breaker Strategy** (CRITICAL - added from critique):
  - Timeout: 10 seconds for BAPI simulate, 30 seconds for BAPI create
  - Retry logic: 2 retries with 2-second exponential backoff for transient errors
  - Circuit breaker: Open circuit after 5 consecutive failures within 1 minute
  - Circuit breaker recovery: Auto-close after 2-minute cooldown
  - User feedback: Show timeout countdown (e.g., "Validating... (8 sec remaining)")
  - On timeout: "SAP is slow. Retrying... (Attempt 1 of 2)"
  - On circuit open: "SAP temporarily unavailable. Retry in 2 minutes."
- Integration tests with CPI sandbox (NO MOCKS)
- **Effort:** 4 days (increased from 3 for resilience logic) | **Blocks:** Epic 2 (Sales Ops Agent)

**TE-6: MS5 IDoc Client** (Story 1.4 in v2.0)
- Method: `create_sales_order()` → `SAPPostResponse` (VBELN)
- **Idempotency Enforcement at CPI Layer** (CRITICAL - added from critique):
  - **Client-side**: Agent includes correlation_id in IDoc header
  - **CPI-layer enforcement**: CPI checks if correlation_id already processed before posting to SAP
  - **Database constraint**: PostgreSQL UNIQUE constraint on correlation_id in transactions table
  - **Duplicate handling**: If correlation_id exists, return existing VBELN (HTTP 200, not error)
  - **Agent retry logic**: Before retry, check audit store for existing VBELN
  - **Testing requirement**: 100 concurrent posts with 10% network loss → 0 duplicate orders
- Retry logic with exponential backoff (3 retries, 2/4/8 second delays)
- Timeout: 30 seconds per IDoc post attempt
- Integration tests with CPI sandbox (NO MOCKS)
- **Effort:** 4.5 days (increased from 3.5 for CPI-layer idempotency) | **Blocks:** Epic 2 (Sales Ops Agent)

**TE-7: Policy Catalog Service** (Story 1.7 in v2.0)
- Versioned policy rules (Incoterms → artefacts, payment terms → approvals)
- API: `get_policies()`, `check_policy_compliance()`
- **Effort:** 2 days | **Blocks:** Epic 3 (Due Diligence Agent)

**TE-8: ArchiveLink Client** (Story 1.5 in v2.0)
- Method: `attach_document()` → link to SAP VBELN
- Document hash verification (SHA-256)
- Integration tests with CPI sandbox (NO MOCKS)
- **Effort:** 2 days | **Blocks:** Epic 3, Epic 4

**TE-9: CPI Event Listener** (Story 3.5 in v2.0)
- Subscribe to MS5 delivery milestone events
- Forward events to Financial Ops Agent
- **Effort:** 1.5 days | **Blocks:** Epic 4 (Financial Ops Agent)

---

### Agent Workflows (Kailash SDK Core)

**TE-10: Opportunity Assessment Agent** (Story 2.1 in v2.0)
- Workflow: Retrieve opportunity from CEC → Check prerequisites → Calculate readiness score → Flag gaps
- Output: `AssessmentResult` with score + gap list
- **Effort:** 3 days | **Blocks:** Epic 1

**TE-11: Sales Ops Agent (Orchestrator)** (Story 2.2 in v2.0)
- Workflow: Retrieve CEC + IPAS data → Assemble proposal → Call Due Diligence → BAPI validate → IDoc post
- Output: `SalesOrderProposal` with field provenance + `SAPPostResponse` (VBELN)
- **Effort:** 4 days | **Blocks:** Epic 2

**TE-12: Due Diligence Agent** (Story 2.3 in v2.0)
- Workflow: Check policies → Flag required artefacts → Return `DDSummary`
- Output: `DDSummary` with policy checks + artefact requirements
- **Effort:** 3.5 days | **Blocks:** Epic 3

**TE-13: Financial Ops Agent** (Story 2.5 in v2.0)
- Workflow: Listen for delivery events → Check billing prerequisites → Trigger invoice
- Output: Invoice trigger + control evidence
- **Effort:** 3 days | **Blocks:** Epic 4

---

### Data & Platform

**TE-14: Audit Store (PostgreSQL)** (Story 1.8 in v2.0)
- Tables: `transactions`, `events`, `field_provenance`, `policy_checks`, `documents`, `control_evidence`
- Append-only (immutable audit trail)
- **Effort:** 2 days | **Blocks:** Epic 3, Epic 4, Epic 5

**TE-15: Nexus Multi-Channel Platform** (Story 2.6 in v2.0)
- API endpoints for all user stories (15-20 endpoints)
- MCP server (optional—for AI agent integration)
- **Effort:** 4 days | **Blocks:** All epics

**TE-16: Test Data Generator** (Story 5.1 in v2.0)
- Synthetic CEC opportunities, IPAS configs, MS5 orders
- UAT test data setup
- **Effort:** 1.5 days | **Blocks:** Epic 6 (UAT)

**TE-17: UAT Environment** (Story 5.1 in v2.0)
- Isolated environment (DEV, UAT, PROD separation)
- **Effort:** 1 day | **Blocks:** Epic 6

**TE-18: Support Infrastructure** (Story 6.2 in v2.0)
- Issue tracking (Jira, GitLab Issues)
- Hotline setup
- **Effort:** 1 day | **Blocks:** Epic 6 (Pilot)

---

### Deployment & Infrastructure

**TE-19: AKS Deployment Manifests** (Story 4.1 in v2.0)
- Kubernetes manifests for all agents + platform services
- **Effort:** 2 days | **Blocks:** Epic 6 (Pilot)

**TE-20: CI/CD Pipeline** (Story 4.2 in v2.0)
- GitLab CI or GitHub Actions
- Automated testing (unit, integration, E2E)
- **Effort:** 2.5 days | **Blocks:** Epic 6 (Pilot)

**TE-21: Security Hardening** (Story 4.4 in v2.0)
- VNet isolation, Key Vault, TLS, IP allow-listing
- **Effort:** 3 days | **Blocks:** Epic 6 (Pilot)

**TE-22: Observability Platform** (Story 4.5 in v2.0)
- Prometheus + Grafana dashboards
- **Effort:** 2 days | **Blocks:** Epic 3 (Metrics)

**TE-23: Notification Service** (NEW - identified in critique)
- Email/Slack notifications for opportunity readiness alerts (Story 1.3)
- Methods: `send_notification()`, `subscribe_to_updates()`
- Integration with CEC opportunity updates
- **Effort:** 1.5 days | **Blocks:** Epic 1 (Story 1.3 - Automated Alerts)

**TE-24: Object Storage Setup** (NEW - identified in critique)
- MinIO or Azure Blob Storage for document uploads (Story 3.2)
- Document hash verification (SHA-256)
- Integration with ArchiveLink for SAP attachment
- **Effort:** 1 day | **Blocks:** Epic 3 (Story 3.2 - Document Flagging)

**TE-25: Disaster Recovery & Backup** (NEW - identified in critique)
- PostgreSQL daily backups with 7-day retention
- Backup restore testing and validation
- RTO/RPO definitions: RTO <4 hours, RPO <24 hours
- **Effort:** 2 days | **Blocks:** Epic 6 (Pilot - production readiness)

**TE-26: SAP FI BAPI Client** (NEW - identified in critique)
- Method: `create_invoice()` → Invoice number
- Method: `check_billing_blocks()` → Billing block status
- Integration with Epic 4 (Story 4.2 - Invoice Triggers)
- Integration tests with CPI sandbox (NO MOCKS)
- **Effort:** 2.5 days | **Blocks:** Epic 4 (Financial Ops Agent)

---

## Story Mapping (Value Chain)

See separate document: `docs/story-mapping.md`

---

## Validation Checklist

For each user story in Epics 1-6, verify:
- [x] Written from **business user** perspective (not developer/platform admin)
- [x] Describes **business capability**, not technical implementation
- [x] "So that" clause explains **business value** (time saved, fewer errors, visibility)
- [x] NO technical jargon in user story statement (CPI, IDoc, BAPI, OData, etc.)
- [x] Technical details in **Technical Acceptance Criteria** or **Technical Enablers**, not user story
- [x] Can be explained to a non-technical executive in 30 seconds

---

## Appendix: Mapping to v2.0 Stories

| v3.0 User Story | v2.0 Story ID | Change Summary |
|-----------------|---------------|----------------|
| 1.1 Opportunity Readiness Scoring | 2.1 | Reframed from technical (agent workflow) to business (readiness dashboard) |
| 1.2 Gap Identification | 2.1 | Extracted as separate story (clarity) |
| 1.3 Automated Alerts | 2.1 | Extracted as separate story (user value) |
| 2.1 One-Click Order Proposal | 2.2 | Reframed from technical (orchestrator) to business (one-click creation) |
| 2.2 Pre-Post Validation | 2.2 | Extracted as separate story (error prevention) |
| 2.3 Approve & Post | 2.2 | Extracted as separate story (seamless workflow) |
| 2.4 Field Provenance | 2.2 | Extracted as separate story (trust & transparency) |
| 3.1 Policy Checks | 2.3 | Reframed from technical (DD agent) to business (compliance enforcement) |
| 3.2 Document Flagging | 2.3 | Extracted as separate story (billing readiness) |
| 3.3 Audit Trail | 3.1, 3.3 | Combined correlation tracking + audit trail (traceability) |
| 4.1 Billing Readiness Dashboard | 2.5 | Reframed from technical (FinOps agent) to business (visibility) |
| 4.2 Invoice Triggers | 2.5 | Extracted as separate story (automation) |
| 4.3 Control Evidence | 2.5, 3.3 | Extracted as separate story (A/R audits) |
| 5.1 Baseline Collection | 6.1 | No change (already business-focused) |
| 5.2 Pilot Metrics | 6.2 | No change (already business-focused) |
| 5.3 Scorecard | 6.3 | No change (already business-focused) |
| 6.1 UAT Scenarios | 5.2 | No change (already business-focused) |
| 6.2 Pilot Execution | 6.2 | No change (already business-focused) |
| 6.3 Feedback Incorporation | NEW | Added to address iteration |

**Technical stories (1.1-1.8, 2.4, 2.6-2.10, 3.1-3.5, 4.1-4.6) → Moved to Technical Enablers section**

---

**Document End**
