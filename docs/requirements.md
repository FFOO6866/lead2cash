# RRPS Lead-to-Cash POV: Requirements (8-Week MVP)

**Document Version:** 5.0 (Realistic POV Scope)
**Date:** 2025-10-10
**Status:** Production-Ready
**POV Duration:** 8 Weeks
**Framework:** Kailash SDK (Core + DataFlow + Nexus)
**Scope:** MVP - Epic 1 + Epic 2 Only

---

## Document Change Log

| Version | Date | Changes | Author |
|---------|------|---------|--------|
| 1.0-3.1 | 2025-10-10 | Initial iterations (19 stories, 6 epics) | Requirements Analyst |
| 4.0 | 2025-10-10 | Impact-Verse integration (190 points, unrealistic) | Claude Code |
| 5.0 | 2025-10-10 | **REALISTIC 8-WEEK POV**: Cut to 7 stories (Epic 1+2 only), Sprint 0 checklist, T-shirt sizing, honest KPIs, risk register | Enterprise Agile PM |

---

## Critical Changes in v5.0 (Realistic POV Scope)

**Problem in v4.0:**
- 190 story points across 8 weeks = unrealistic (requires velocity of 24 points/week with no established baseline)
- 19 user stories across 6 epics = scope too large for POV
- "Story 0" as backlog item = anti-pattern (infrastructure is not user-facing value)
- KPIs like "60% acceptance rate" = fantasy for first POV iteration (30-40% more realistic)
- No buffer for SAP CPI sandbox downtime, DataFlow alpha bugs, user resistance

**v5.0 Solutions:**

1. **Aggressive Scope Reduction**
   - Focus: Epic 1 (Opportunity Qualification) + Epic 2 (Order Creation) ONLY
   - 7 user stories total (3 in Epic 1, 4 in Epic 2)
   - Epics 3-6 moved to "Future Phase" (Compliance, Billing, Metrics, UAT)

2. **Story 0 → Sprint 0 Conversion**
   - Removed from backlog entirely
   - Converted to prerequisite checklist (0-2 weeks before user stories start)
   - Infrastructure setup is continuous activity, not a "story"

3. **Story Points → T-Shirt Sizing**
   - Epic 1: M (Medium) - 2 weeks with 1 backend engineer
   - Epic 2: XL (Extra Large) - 4 weeks with 1-2 engineers
   - Week 7-8: UAT buffer (L) - 10 test orders with real users

4. **Honest POV Success Criteria**
   - KPI: "5-10 orders created successfully end-to-end" (not 50 orders with 60% acceptance)
   - Target: 30-40% acceptance rate (realistic for first iteration, not 60%)
   - Cycle time: Measure 1 baseline, then test with AI agent (qualitative improvement acceptable)

5. **Risk Register Added**
   - Mitigation plans for CPI sandbox downtime, DataFlow alpha bugs, user resistance
   - 20% time buffer for inevitable delays

---

## POV Objective (Focused MVP)

**Prove whether AI agents can deliver TWO killer features:**

1. **Epic 1: Opportunity Qualification** → Sales Managers see "ready-to-order" opportunities ranked by confidence
2. **Epic 2: Fast Order Creation** → Orders created in 5 min vs. 45 min with 30-40% auto-fill acceptance

**Out of Scope for 8-Week POV:**
- Epic 3: Compliance & Audit Trail → Future Phase
- Epic 4: Billing Automation → Future Phase
- Epic 5: Metrics Dashboard → Future Phase
- Epic 6: Full UAT with 50+ users → Reduced to 10 test orders with 3-5 pilot users

**Decision Criteria at Week 8:**
- ✅ **SCALE**: 5+ orders created successfully, 30%+ acceptance rate → Proceed to 12-week production rollout
- ⚠️ **ITERATE**: 2-4 orders successful, learnings captured → Extend POV by 4 weeks with scope adjustments
- ❌ **STOP**: <2 orders successful, or CPI integration unstable → Redesign approach or abandon

---

## 8-Week Timeline (Sprint Structure)

| Sprint | Duration | Focus | Deliverables | Size |
|--------|----------|-------|--------------|------|
| **Sprint 0** | Week 0-2 (Pre-POV) | Infrastructure setup (NOT a user story) | All TEs validated, CPI integrations tested, audit store ready | - |
| **Sprint 1** | Week 1-2 | Epic 1: Opportunity Qualification | 3 stories complete, Sales Managers can see ranked opportunities | M (Medium) |
| **Sprint 2** | Week 3-4 | Epic 2: Order Creation (Stories 2.1-2.2) | Order agent retrieves data, validates, populates IDoc | L (Large) |
| **Sprint 3** | Week 5-6 | Epic 2: Order Creation (Stories 2.3-2.4) | IDoc submission, confirmation, audit trail | L (Large) |
| **Sprint 4** | Week 7-8 | UAT + Iteration | 10 test orders with 3-5 pilot users, capture feedback | L (Large) |

**Total Effort:** 8 weeks (MVP only)

---

## Technology Stack (Same as Impact-Verse)

### Backend
- **Kailash SDK Core**: Workflow orchestration, runtime execution
- **Kailash DataFlow (v0.4.6+ alpha)**: Database operations with @db.model auto-node generation
  - ⚠️ **ALPHA STATUS**: PostgreSQL-only, validation required in Sprint 0
- **Kailash Nexus**: Multi-channel deployment (API + CLI + MCP)
- **Kailash Kaizen**: AI agent coordination (optional for POV)

### Database
- **PostgreSQL 14+**: DataFlow backend, audit store, policy catalog

### Integration
- **SAP CPI**: Middleware for MS5 (C4C, IPAS, S/4HANA MS5)
- **Custom Clients**: CEC OData, IPAS, MS5 BAPI, MS5 IDoc, ArchiveLink

### Frontend (Out of scope for POV)
- API-first design; UI can be Nexus CLI or third-party tool

---

## Sprint 0: Infrastructure Setup (Prerequisite Checklist)

**NOT A USER STORY** - This is prerequisite work before Sprint 1 starts.

**Duration:** 0-2 weeks (depending on CPI access readiness)
**Team:** 1 backend engineer + 0.5 integration specialist
**Estimated Effort:** 60-80 hours

---

### Ready Criteria

- [ ] PostgreSQL credentials confirmed in `.env`
- [ ] SAP CPI sandbox access granted (OData, BAPI, IDoc endpoints)
- [ ] Kailash SDK installation access verified
- [ ] Team available for Sprint 0 setup

---

### Definition of Done (Sprint 0)

#### 1. Backend Setup & DataFlow Alpha Validation

- [ ] Kailash SDK installed: `pip install kailash[dataflow,nexus,kaizen]`
- [ ] PostgreSQL connection verified using `.env` credentials
- [ ] **DataFlow Alpha Validation**:
  - [ ] @db.model generates 9 nodes for test `Transaction` model
  - [ ] All auto-generated nodes work in workflows (create, read, update, delete, query, filter, count, exists, bulk_create)
  - [ ] PostgreSQL integration stable with 1000+ test transactions
  - [ ] Performance acceptable: queries < 200ms, filters < 500ms
- [ ] Nexus multi-channel deployment tested (API, CLI)
- [ ] Essential SDK patterns validated: `runtime.execute(workflow.build())`

#### 2. SAP CPI Integration Testing (CRITICAL PATH)

- [ ] **CEC OData Client** (TE-2):
  - [ ] OAuth2 authentication successful
  - [ ] Retrieve 10 test opportunities
  - [ ] Response time < 2 seconds
- [ ] **IPAS Client** (TE-3):
  - [ ] Retrieve 5 test BOM configurations
  - [ ] Parse BOM to SalesOrderItem list
  - [ ] Response time < 3 seconds
- [ ] **MS5 BAPI Client** (TE-5):
  - [ ] BAPI_SALESORDER_SIMULATE test successful (1 order)
  - [ ] Parse BAPI return messages correctly
  - [ ] Circuit breaker activates after 3 failures (reduced for POV)
- [ ] **MS5 IDoc Client** (TE-6):
  - [ ] Submit 1 test IDoc ORDERS05
  - [ ] Receive test VBELN from SAP
  - [ ] Idempotency test: retry with same correlation_id returns existing VBELN

#### 3. Audit Store Infrastructure (Minimal for POV)

- [ ] PostgreSQL audit tables created:
  - [ ] `transactions` (correlation_id UNIQUE constraint)
  - [ ] `events` (basic event log)
  - [ ] `field_provenance` (AI agent decisions)
- [ ] Append-only enforcement tested (no UPDATEs, only INSERTs)
- [ ] Test data: 20 sample transactions with provenance

#### 4. Documentation & Knowledge Transfer

- [ ] DataFlow alpha limitations documented (if any discovered)
- [ ] CPI integration endpoints documented
- [ ] Common issues and solutions logged
- [ ] Team walkthrough session completed

---

### DataFlow Alpha Validation (DECISION POINT)

**Context:** DataFlow is PostgreSQL-only alpha. Sprint 0 validates it works for audit store use case.

**Success Criteria:**

- [ ] `Transaction` model auto-generates all 9 nodes successfully
- [ ] Query/filter/create nodes work in workflows
- [ ] PostgreSQL integration stable with 1000+ test transactions
- [ ] Performance acceptable: queries < 200ms, filters < 500ms

**Decision Point:**

✅ **SUCCESS**: Proceed with DataFlow for audit store (Stories 2.3, 2.4)
⚠️ **PARTIAL**: Document workarounds, continue with caution, monitor for blockers
❌ **FAILURE**: Fallback to Core SDK AsyncSQLDatabaseNode, update audit store implementation

---

### Technical Subtasks (Sprint 0)

#### 1. Kailash SDK Installation & Validation (4-6h)
- Install SDK with all frameworks
- Verify imports: `from kailash.workflow.builder import WorkflowBuilder`
- Test essential patterns: `runtime.execute(workflow.build())`
- Consult `sdk-navigator`, `framework-advisor`, `pattern-expert` agents if issues arise

#### 2. DataFlow Alpha Validation (6-8h)
- Connect to PostgreSQL
- Create test `Transaction` model with @db.model decorator
- Verify all 9 auto-generated nodes
- Load 1000 test transactions
- Measure query/filter performance

#### 3. Nexus Multi-Channel Test (3-4h)
- Deploy hello-world workflow
- Test API endpoint (REST)
- Test CLI command
- Verify session management

#### 4. CPI Integration Testing (24-30h) - **CRITICAL PATH**
- **CEC OData** (6h): OAuth2 + 10 opportunity retrieval
- **IPAS Client** (6h): 5 BOM retrievals + parsing
- **MS5 BAPI** (8h): BAPI_SALESORDER_SIMULATE + error parsing + circuit breaker
- **MS5 IDoc** (8h): ORDERS05 submission + idempotency test

#### 5. Audit Store Setup (8-12h)
- Create PostgreSQL tables (2h)
- Define Pydantic models (3h)
- Test DataFlow node generation (3h)
- Populate test data (2h)

#### 6. Documentation (6-8h)
- CPI endpoint documentation (3h)
- Common issues log (2h)
- Team walkthrough session (2h)

**Total Estimated Effort:** 60-80 hours

---

### Sprint 0 Validation Criteria

**✅ PROCEED TO SPRINT 1:**
- All CPI integrations tested successfully
- DataFlow alpha works for audit store use case
- Performance benchmarks met (queries < 200ms)
- Team trained on SDK patterns

**⚠️ PROCEED WITH CAUTION:**
- DataFlow has minor issues but workarounds exist
- 1 CPI endpoint slow but acceptable (< 5 sec)
- Document workarounds clearly

**❌ STOP POV / ESCALATE:**
- DataFlow alpha has blocking bugs → Fallback to Core SDK (adds 1 week)
- CPI access denied or unstable → Escalate to SAP team (blocks POV)
- PostgreSQL connection issues → Review infrastructure
- Team cannot grasp SDK patterns → Additional training required (adds 1 week)

---

## Epic 1: Sales Manager - Opportunity Qualification (Sprint 1, Week 1-2)

**Business Outcome:** Sales Managers prioritize "ready-to-order" opportunities with AI-driven confidence scoring

**Stories:** 3
**Size:** M (Medium) - 2 weeks
**Dependencies:** Sprint 0 complete (CEC OData client validated)

---

### Story 1.1: Search Opportunities by Customer/Product

**As a** Sales Manager
**I want** to search opportunities by customer name or product family
**So that** I can quickly find deals related to specific accounts or product lines

**Size:** S (Small)

#### Acceptance Criteria

- [ ] User enters customer name (e.g., "Acme Corp") → Returns all opportunities for that customer
- [ ] User enters product family (e.g., "Power Systems") → Returns all opportunities with matching products
- [ ] Search supports partial matching (e.g., "Acme" matches "Acme Corp" and "Acme Industries")
- [ ] Results returned within 2 seconds
- [ ] Empty result set shows clear message: "No opportunities found for [search term]"

#### Technical Implementation (TE-2: CEC OData Client)

**Workflow:** `SearchOpportunitiesWorkflow`

**Nodes:**
1. `TextInputNode` → Capture search term (customer or product)
2. `CustomNode<CECODataClient>` → Query C4C opportunities via CPI
   - OData filter: `$filter=contains(AccountName, '{term}') or contains(ProductFamily, '{term}')`
   - OAuth2 authentication via CPI
3. `FilterOpportunitiesNode` → Filter results by status (Open, In Progress)
4. `FormatResultsNode` → Format as list: Opportunity ID, Customer, Product, Amount, Close Date
5. `TextOutputNode` → Return results or "No opportunities found"

**Edge Cases:**
- Search term with special characters → URL-encode before OData query
- CPI timeout (>5 sec) → Return error: "CEC system unavailable, try again later"
- OAuth2 token expired → Refresh token automatically, retry once

**Dependencies:** TE-2 (CEC OData Client validated in Sprint 0)

---

### Story 1.2: Filter Opportunities by Readiness Criteria

**As a** Sales Manager
**I want** to filter opportunities by AI-assessed readiness criteria
**So that** I can prioritize deals most likely to convert to orders

**Size:** M (Medium)

#### Acceptance Criteria

- [ ] User selects readiness filter: "Ready to Order" → Shows opportunities with ≥70% AI confidence score
- [ ] User selects readiness filter: "Needs Follow-up" → Shows opportunities with 40-69% AI confidence score
- [ ] User selects readiness filter: "Not Ready" → Shows opportunities with <40% AI confidence score
- [ ] Each opportunity shows AI confidence score (e.g., "85% Ready") with human-readable reasoning
- [ ] Reasoning includes missing prerequisites (e.g., "Missing: Delivery date, Payment terms")
- [ ] Results sorted by confidence score (highest first)

#### Technical Implementation (TE-4: Opportunity Readiness Agent)

**Workflow:** `AssessOpportunityReadinessWorkflow`

**Nodes:**
1. `CustomNode<CECODataClient>` → Retrieve opportunities from Story 1.1 results
2. **Kaizen Agent: OpportunityReadinessAgent**
   - Input: Opportunity data (customer, product, amount, close date, notes)
   - LLM Signature: `"opportunity -> readiness_score, missing_fields, reasoning"`
   - Prompt: "Assess if this opportunity is ready to convert to SAP order. Check for: customer confirmed, product configured, pricing approved, delivery date set, payment terms agreed."
   - Output: `{score: 0.85, missing: ["delivery_date"], reasoning: "Customer and pricing confirmed. Need delivery date."}`
3. `FilterByScoreNode` → Apply user-selected filter (≥70%, 40-69%, <40%)
4. `SortByScoreNode` → Sort by score descending
5. `TextOutputNode` → Format results with confidence score + reasoning

**Edge Cases:**
- Opportunity with incomplete data → Score as <40%, list all missing fields
- LLM API timeout → Fallback to rule-based scoring (check for null fields)
- User selects no filter → Show all opportunities sorted by score

**Dependencies:** TE-4 (Kaizen OpportunityReadinessAgent), TE-2 (CEC OData Client)

---

### Story 1.3: View AI Confidence Reasoning

**As a** Sales Manager
**I want** to see why the AI assessed an opportunity as ready/not ready
**So that** I can validate the assessment and take corrective action

**Size:** S (Small)

#### Acceptance Criteria

- [ ] User clicks on opportunity → Shows detailed AI reasoning
- [ ] Reasoning includes:
  - [ ] Confidence score (e.g., "85% Ready")
  - [ ] Checklist: Customer confirmed (✅), Product configured (✅), Pricing approved (✅), Delivery date (❌), Payment terms (✅)
  - [ ] Next steps: "Contact customer for delivery date confirmation"
- [ ] User can override AI assessment (mark as "Ready to Order" even if AI says 60%)
- [ ] Override is logged in audit trail with reason

#### Technical Implementation (TE-4: Opportunity Readiness Agent + TE-14: Audit Store)

**Workflow:** `ViewOpportunityReasoningWorkflow`

**Nodes:**
1. `TextInputNode` → Capture opportunity ID
2. `CustomNode<CECODataClient>` → Retrieve full opportunity details
3. **Kaizen Agent: OpportunityReadinessAgent** (same as 1.2)
   - Return detailed checklist + next steps
4. `FormatReasoningNode` → Format as structured output (confidence, checklist, next steps)
5. `TextOutputNode` → Display reasoning
6. **Optional Override Path:**
   - `BooleanInputNode` → User wants to override? (Yes/No)
   - `TextInputNode` → Override reason
   - `CustomNode<AuditStoreWriter>` → Log override event to PostgreSQL
     - Event type: "opportunity_assessment_override"
     - Data: {opportunity_id, ai_score, user_override, reason}

**Edge Cases:**
- Opportunity not found → Return "Invalid Opportunity ID"
- LLM reasoning too verbose → Truncate to 500 characters, add "See full reasoning..." link
- User overrides without reason → Require reason (validation error)

**Dependencies:** TE-4 (Kaizen OpportunityReadinessAgent), TE-2 (CEC OData Client), TE-14 (Audit Store)

---

## Epic 2: Sales Operations - Fast Order Creation (Sprint 2-3, Week 3-6)

**Business Outcome:** Orders created in 5 min vs. 45 min with 30-40% auto-fill acceptance (realistic POV target)

**Stories:** 4
**Size:** XL (Extra Large) - 4 weeks
**Dependencies:** Sprint 0 complete (all CPI clients validated), Epic 1 complete (opportunity data retrieval)

---

### Story 2.1: Auto-Retrieve Order Data from Multiple Systems

**As a** Sales Operations Specialist
**I want** the system to automatically retrieve order data from C4C, IPAS, and SAP when I select an opportunity
**So that** I don't waste 15-20 minutes manually gathering information from 3 systems

**Size:** L (Large)

#### Acceptance Criteria

- [ ] User selects opportunity (from Epic 1) → System retrieves data from C4C, IPAS, SAP in parallel
- [ ] **C4C Data Retrieved:** Customer name, Sold-to party, Ship-to party, Opportunity amount, Close date
- [ ] **IPAS Data Retrieved:** BOM (Bill of Materials) for product configuration → Parsed to SalesOrderItem list
- [ ] **SAP Data Retrieved:** Customer master data (payment terms, incoterms, sales org)
- [ ] All data retrieved within 5 seconds total (parallel execution)
- [ ] If any system unavailable → Shows which data is missing, allows manual entry

#### Technical Implementation (TE-2, TE-3, TE-12: Multi-System Integration)

**Workflow:** `RetrieveOrderDataWorkflow`

**Nodes:**
1. `TextInputNode` → Capture opportunity ID (from Epic 1)
2. **Parallel Execution Block:**
   - `CustomNode<CECODataClient>` → Retrieve C4C opportunity data (2 sec)
   - `CustomNode<IPASClient>` → Retrieve BOM configuration (3 sec)
   - `CustomNode<SAPCustomerMasterClient>` → Retrieve customer master data via CPI (2 sec)
3. `MergeDataNode` → Combine all data sources into unified order object
4. `ValidateCompletenessNode` → Check for missing required fields
5. `TextOutputNode` → Display merged data or list missing fields

**Edge Cases:**
- IPAS timeout → Mark BOM as "unavailable", allow manual item entry
- C4C returns partial data → Mark missing fields, continue
- SAP customer not found → Return error: "Customer [ID] not found in SAP, contact master data team"
- All 3 systems timeout → Return error: "All systems unavailable, try again later or enter manually"

**Dependencies:** TE-2 (CEC OData), TE-3 (IPAS Client), TE-12 (SAP Customer Master via CPI)

---

### Story 2.2: AI Agent Validates & Populates IDoc Fields

**As a** Sales Operations Specialist
**I want** the AI agent to validate data completeness and intelligently populate IDoc fields
**So that** I can review a pre-filled order form instead of manually filling 50+ fields

**Size:** XL (Extra Large) - **CORE POV FEATURE**

#### Acceptance Criteria

- [ ] System auto-populates 30-40% of IDoc fields from retrieved data (realistic POV target, not 60%+)
- [ ] **Auto-Filled Fields (High Confidence):**
  - [ ] Customer (Sold-to, Ship-to)
  - [ ] Sales Org, Distribution Channel, Division (from SAP master data)
  - [ ] Order Date (today), Requested Delivery Date (from C4C close date + 14 days)
  - [ ] Payment Terms, Incoterms (from SAP customer master)
  - [ ] Line Items (from IPAS BOM)
- [ ] **Flagged for Review (Medium Confidence):**
  - [ ] Pricing (AI suggests price from opportunity, flags for approval)
  - [ ] Delivery Plant (AI suggests based on Ship-to location, flags for confirmation)
  - [ ] Special Instructions (AI extracts from C4C notes, flags for review)
- [ ] **Left Blank (Low Confidence):**
  - [ ] Purchase Order Number (manual entry required)
  - [ ] Custom fields specific to deal
- [ ] User sees color-coded fields: Green (auto-filled, high confidence), Yellow (review required), Red (manual entry required)
- [ ] User can edit any field before submission

#### Technical Implementation (TE-8: Order Orchestration Agent + TE-5: BAPI Validation)

**Workflow:** `PopulateIDoCFieldsWorkflow`

**Nodes:**
1. `InputNode<OrderDataObject>` → Receives merged data from Story 2.1
2. **Kaizen Agent: OrderOrchestrationAgent**
   - Input: Order data from 3 systems
   - LLM Signature: `"order_data -> idoc_fields, confidence_scores, review_flags"`
   - Prompt: "Populate ORDERS05 IDoc fields from C4C, IPAS, SAP data. Mark high-confidence fields as auto-filled, flag uncertain fields for review. Follow RRPS business rules: [pricing policy, delivery plant logic, etc.]"
   - Output: `{idoc: {...}, confidence: {customer: 0.95, pricing: 0.60, plant: 0.70}, review_flags: ["pricing", "plant"]}`
3. `CustomNode<BAPI_SALESORDER_SIMULATE>` → Pre-validate IDoc against SAP business logic
   - If BAPI returns errors → Add to review_flags
4. `FormatOrderFormNode` → Color-code fields (Green/Yellow/Red) based on confidence + BAPI validation
5. `TextOutputNode` → Display pre-filled order form for user review

**Edge Cases:**
- BAPI validation fails → Show SAP error messages, highlight problematic fields in red
- LLM hallucinates field value → BAPI validation catches it, flags for review
- Pricing outside policy limits → Flag as red, require manager approval
- Missing required field → Block submission until filled

**POV Success Metric:** 30-40% of fields auto-filled and accepted by user without edits (measured in UAT, Week 7-8)

**Dependencies:** TE-8 (Kaizen OrderOrchestrationAgent), TE-5 (BAPI_SALESORDER_SIMULATE), TE-2/3/12 (Data retrieval from Story 2.1)

---

### Story 2.3: Submit Order to SAP & Receive Confirmation

**As a** Sales Operations Specialist
**I want** to submit the validated order to SAP with one click and receive immediate confirmation
**So that** I don't wait 2-3 hours for batch processing or wonder if the order was created

**Size:** M (Medium)

#### Acceptance Criteria

- [ ] User reviews order form (from Story 2.2) → Clicks "Submit to SAP"
- [ ] System submits IDoc ORDERS05 to SAP via CPI
- [ ] System receives VBELN (SAP Sales Order Number) within 30 seconds
- [ ] Success message: "Order [VBELN] created successfully in SAP"
- [ ] If submission fails → Shows SAP error message, allows retry
- [ ] Idempotency: Retry with same correlation_id returns existing VBELN (no duplicate orders)

#### Technical Implementation (TE-6: IDoc Submission + TE-10: Idempotency)

**Workflow:** `SubmitOrderToSAPWorkflow`

**Nodes:**
1. `InputNode<IDoCObject>` → Receives validated IDoc from Story 2.2
2. `GenerateCorrelationIDNode` → Create unique correlation_id (UUID)
3. `CheckIdempotencyNode` → Query PostgreSQL audit store for existing submission with same correlation_id
   - If found → Return existing VBELN, skip submission
4. `CustomNode<MS5IDoCClient>` → Submit IDoc ORDERS05 to SAP via CPI
   - Timeout: 30 seconds
   - Retry: 1 automatic retry if timeout
5. `ReceiveVBELNNode` → Parse SAP response for VBELN
6. `CustomNode<AuditStoreWriter>` → Log submission event to PostgreSQL
   - Event type: "order_submitted"
   - Data: {correlation_id, vbeln, idoc, timestamp, user_id}
7. `TextOutputNode` → Display "Order [VBELN] created successfully"

**Edge Cases:**
- SAP returns error (e.g., "Customer blocked") → Display error, do NOT create audit record, allow user to fix and retry
- CPI timeout → Display "SAP unavailable, order saved as draft, will auto-submit when SAP available"
- Network loss during submission → Idempotency check prevents duplicate on retry
- User clicks "Submit" twice rapidly → Idempotency check catches duplicate, returns existing VBELN

**POV Success Metric:** 1 order submitted successfully end-to-end (VBELN received)

**Dependencies:** TE-6 (IDoc Client), TE-10 (Idempotency), TE-14 (Audit Store)

---

### Story 2.4: View Order Status & Audit Trail

**As a** Sales Operations Specialist
**I want** to view the status of my submitted order and full audit trail
**So that** I can confirm it's in SAP and troubleshoot any issues

**Size:** S (Small)

#### Acceptance Criteria

- [ ] User enters VBELN → Shows order status in SAP (Created, In Process, Delivered, Blocked)
- [ ] User sees full audit trail:
  - [ ] Who created the order (user ID, timestamp)
  - [ ] Which fields were auto-filled by AI vs. manually edited
  - [ ] SAP submission timestamp, received VBELN, CPI correlation_id
  - [ ] Any errors or retries during submission
- [ ] Audit trail is immutable (append-only, no edits)
- [ ] User can export audit trail as PDF for compliance

#### Technical Implementation (TE-14: Audit Store + TE-15: Provenance Tracking)

**Workflow:** `ViewOrderStatusWorkflow`

**Nodes:**
1. `TextInputNode` → Capture VBELN
2. `CustomNode<SAPOrderStatusClient>` → Query SAP for current order status via CPI
3. `CustomNode<AuditStoreReader>` → Query PostgreSQL for audit trail:
   - Query: `SELECT * FROM transactions WHERE vbeln = ? ORDER BY timestamp ASC`
   - Joins with `field_provenance` table to show AI vs. manual fields
4. `FormatAuditTrailNode` → Format as timeline: Created → Validated → Submitted → Confirmed
5. `TextOutputNode` → Display status + audit trail
6. **Optional PDF Export:**
   - `CustomNode<PDFGeneratorNode>` → Convert audit trail to PDF
   - `FileOutputNode` → Return PDF file

**Edge Cases:**
- VBELN not found in SAP → Return "Order not found, check VBELN"
- Audit trail incomplete (system error during logging) → Display warning: "Partial audit trail, contact support"
- PDF export fails → Return error: "PDF generation failed, try again or contact support"

**POV Success Metric:** 100% of test orders have complete audit trail (correlation_id → VBELN)

**Dependencies:** TE-14 (Audit Store), TE-15 (Provenance Tracking), TE-6 (SAP Order Status query)

---

## UAT & Iteration (Sprint 4, Week 7-8)

**Focus:** Validate Epic 1 + Epic 2 with 3-5 pilot users, capture feedback, iterate

**Size:** L (Large)

---

### UAT Scope (Realistic POV)

- [ ] **3-5 pilot users** (1-2 Sales Managers, 2-3 Sales Ops Specialists)
- [ ] **10 test orders** created end-to-end with real SAP sandbox data
- [ ] **Capture metrics:**
  - [ ] Acceptance rate: % of auto-filled fields accepted without edits
  - [ ] Cycle time: Baseline (manual) vs. AI-assisted order creation
  - [ ] First-time-right: % of orders posted successfully on 1st attempt
  - [ ] User satisfaction: Survey with 5 questions (1-5 scale)
- [ ] **Daily feedback sessions** (15 min) to capture issues and iterate
- [ ] **Bug fixes and tweaks** based on feedback (max 2 days per fix)

---

### UAT Success Criteria (Honest POV Targets)

**✅ PROCEED TO PRODUCTION ROLLOUT (12-week plan):**
- [ ] 5+ orders created successfully end-to-end (VBELN received)
- [ ] 30%+ acceptance rate (auto-filled fields unchanged by users)
- [ ] Qualitative cycle time improvement (users report "much faster" than manual)
- [ ] 0 critical bugs (order loss, duplicate orders, data corruption)
- [ ] Users want to continue using the tool

**⚠️ ITERATE (Extend POV by 4 weeks):**
- [ ] 2-4 orders successful
- [ ] 20-29% acceptance rate
- [ ] Users report "slightly faster" but many manual corrections needed
- [ ] 1-2 critical bugs identified, fixable in 2 weeks
- [ ] Users willing to continue testing with improvements

**❌ STOP POV:**
- [ ] <2 orders successful
- [ ] <20% acceptance rate (users reject most AI suggestions)
- [ ] Cycle time no better than manual (or worse due to tool overhead)
- [ ] 3+ critical bugs or CPI integration unstable
- [ ] Users refuse to continue testing

---

## KPI Definitions (Honest POV Targets)

| KPI | Definition | Measurement | POV Target (Realistic) | Production Target (Future) |
|-----|------------|-------------|------------------------|----------------------------|
| **Acceptance Rate** | % of auto-filled fields accepted | `(Fields unchanged / Total fields) × 100` | **30-40%** (first iteration) | ≥60% (after 3 months learning) |
| **Cycle Time** (Proposal→Posted) | Order creation time | From "Create Order" click to VBELN received | **Qualitative improvement** (users report "faster") | 25-35% reduction (45 min → 5-10 min) |
| **First-Time-Right** | % orders posted successfully (1st attempt) | `(Success on 1st attempt / Total attempts) × 100` | **Baseline measurement** (no target yet) | +10-15% vs. baseline |
| **Successful Orders** | # orders created end-to-end | Count of VBELNs received | **5-10 orders** in UAT | 50+ orders/week in production |
| **User Satisfaction** | User survey score | 5-question survey (1-5 scale, average) | **≥3.5/5** (acceptable for POV) | ≥4.0/5 (production) |

**Key Insight:** First POV iterations typically achieve 30-40% acceptance, not 60%+. Setting honest targets prevents declaring failure prematurely.

---

## Risk Register & Mitigation Plans

| Risk | Probability | Impact | Mitigation | Contingency |
|------|-------------|--------|------------|-------------|
| **CPI sandbox downtime** | High (30%) | High | Schedule UAT around known SAP maintenance windows | Keep 2-day buffer in Week 7-8 for rescheduling |
| **DataFlow alpha bugs** | Medium (20%) | High | Validate thoroughly in Sprint 0; have Core SDK fallback ready | If blocking bug found, switch to AsyncSQLDatabaseNode (adds 3-5 days) |
| **Users resist AI suggestions** | Medium (25%) | Medium | Involve users in Epic 1 design review; show confidence scores + reasoning | If <20% acceptance, pivot to "AI assistant" mode (suggests, doesn't auto-fill) |
| **LLM hallucinations in order data** | Low (10%) | High | BAPI_SALESORDER_SIMULATE pre-validation catches errors before submission | Add explicit validation rules for critical fields (pricing, plant) |
| **SAP integration changes** | Low (5%) | High | Lock CPI endpoint versions during POV; coordinate with SAP team | If breaking change occurs, pause POV, update integration (1 week) |
| **Scope creep** | High (40%) | Medium | **Hard stop at Epic 1 + Epic 2 only**; defer all other requests to Future Phase | Stakeholder communication: "POV proves 2 features, production adds rest" |
| **Key engineer unavailable** | Low (10%) | High | Cross-train 2nd engineer in Sprint 0; document all CPI integrations | If primary engineer leaves, 2nd engineer continues (1-week ramp) |

---

## Out of Scope (Future Phase)

The following epics from v3.1 are **deferred to 12-week production rollout** after POV success:

### Epic 3: Compliance - Policy Enforcement & Audit Trail
- Story 3.1: Pre-Submission Policy Checks
- Story 3.2: Compliance Dashboard
- Story 3.3: Audit Trail Query Interface

**Rationale:** Compliance is critical for production but not needed to prove core POV hypothesis (AI can create orders faster). Audit trail from Story 2.4 provides basic traceability for POV.

### Epic 4: Finance Operations - Billing Readiness & Invoice Automation
- Story 4.1: Billing Block Agent
- Story 4.2: Invoice Trigger Automation
- Story 4.3: Billing Readiness Dashboard

**Rationale:** Billing automation is valuable but downstream of order creation. POV focuses on order creation bottleneck first.

### Epic 5: POV Success - Metrics & Decision Pack
- Story 5.1: Acceptance Rate Metrics
- Story 5.2: Cycle Time Analysis
- Story 5.3: Traceability Metrics

**Rationale:** Basic metrics captured manually in UAT (Week 7-8) using spreadsheets. Full dashboard deferred to production.

### Epic 6: User Validation - UAT & Pilot (Reduced Scope)
- Story 6.1: Reduced to 10 test orders (not 50+)
- Story 6.2: Simplified test data generator (20 samples, not 200)
- Story 6.3: Feedback portal deferred (use email/spreadsheet)

**Rationale:** Full UAT infrastructure overkill for 10-order POV. Manual tracking sufficient.

---

## Decision Framework (End of Week 8)

### ✅ SCALE (Proceed to 12-Week Production Rollout)

**Criteria:**
- 5+ orders created successfully end-to-end
- 30%+ acceptance rate
- Users report qualitative cycle time improvement
- 0 critical bugs
- Users eager to continue

**Next Steps:**
- Secure 12-week production budget
- Add Epics 3-6 to backlog
- Hire 2nd backend engineer
- Plan 50-user rollout

---

### ⚠️ ITERATE (Extend POV by 4 Weeks)

**Criteria:**
- 2-4 orders successful
- 20-29% acceptance rate
- Mixed user feedback (some value, many issues)
- 1-2 fixable critical bugs

**Next Steps:**
- Analyze low acceptance: Is AI bad, or users unfamiliar?
- Fix critical bugs (2 weeks)
- Rerun UAT with 5 more orders (2 weeks)
- Reassess at Week 12

---

### ❌ STOP (Redesign or Abandon)

**Criteria:**
- <2 orders successful
- <20% acceptance rate
- Users report "slower than manual"
- 3+ critical bugs or CPI unstable

**Next Steps:**
- Root cause analysis: Was it AI quality, CPI integration, or user training?
- If CPI integration: Redesign integration layer, retry in 8 weeks
- If AI quality: Pivot to simpler automation (RPA-style data copy, no LLM)
- If user resistance: Redesign UX, add more human-in-the-loop controls

---

## Technical Enablers (Referenced in Stories)

**Note:** These are NOT user stories. They are technical capabilities required by user stories.

| TE# | Name | Purpose | Technology | Validated In |
|-----|------|---------|------------|--------------|
| TE-2 | CEC OData Client | Retrieve C4C opportunities | Custom client + CPI | Sprint 0 |
| TE-3 | IPAS Client | Retrieve BOM configurations | Custom client + CPI | Sprint 0 |
| TE-4 | Opportunity Readiness Agent | AI confidence scoring | Kaizen + LLM | Sprint 1 |
| TE-5 | MS5 BAPI Client | BAPI_SALESORDER_SIMULATE validation | Custom client + CPI + circuit breaker | Sprint 0 |
| TE-6 | MS5 IDoc Client | Submit ORDERS05, receive VBELN | Custom client + CPI | Sprint 0 |
| TE-8 | Order Orchestration Agent | Auto-fill IDoc fields | Kaizen + LLM | Sprint 2 |
| TE-10 | Idempotency Layer | Prevent duplicate orders | PostgreSQL + correlation_id | Sprint 3 |
| TE-12 | SAP Customer Master Client | Retrieve payment terms, incoterms | Custom client + CPI | Sprint 0 |
| TE-14 | Audit Store | Immutable event log | DataFlow + PostgreSQL | Sprint 0, 3, 4 |
| TE-15 | Provenance Tracking | Track AI vs. manual field edits | PostgreSQL + field_provenance table | Sprint 4 |

---

## Summary: 8-Week POV Scope

### What's IN Scope (MVP)

1. **Sprint 0 (Week 0-2):** Infrastructure setup, CPI validation, DataFlow alpha testing
2. **Epic 1 (Week 1-2):** Opportunity qualification with AI confidence scoring (3 stories)
3. **Epic 2 (Week 3-6):** Fast order creation with 30-40% auto-fill acceptance (4 stories)
4. **UAT (Week 7-8):** 10 test orders with 3-5 pilot users, capture metrics, iterate

**Total:** 7 user stories focused on 2 killer features

### What's OUT of Scope (Future Phase)

- Epic 3: Compliance & Policy Enforcement
- Epic 4: Billing Automation
- Epic 5: Metrics Dashboard
- Epic 6: Full UAT (50+ orders, 20+ users)

### Success Metrics (Honest POV Targets)

- **5-10 orders** created successfully end-to-end
- **30-40% acceptance rate** (realistic for first iteration)
- **Qualitative cycle time improvement** (users report "faster")
- **0 critical bugs** (no data loss, duplicates, corruption)
- **Users want to continue** (survey ≥3.5/5)

---

## Next Steps

1. **Secure stakeholder approval** for reduced scope (Epic 1 + Epic 2 only)
2. **Assign Sprint 0** to backend engineer + integration specialist
3. **Schedule 8-week sprint calendar** with pilot users
4. **Set expectations:** POV proves 2 features work; production rollout adds rest
5. **Begin Sprint 0** infrastructure setup (Week 0-2)

---

**Document Status:** ✅ PRODUCTION-READY (Realistic 8-Week POV Scope)
**Primary Reference:** This file (requirements.md v5.0)
**Detailed Story Archive:** docs/requirements-breakdown-v3.1-archive.md (for Epics 3-6 specifications)
**Last Updated:** 2025-10-10 (v5.0 - Realistic POV Scope)
