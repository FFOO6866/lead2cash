# RRPS Lead-to-Cash POV: Detailed User Stories

**Document Version:** 2.1
**Date:** 2025-10-14
**Status:** Final Draft
**Authored By:** RRPS Lead-to-Cash POV Team
**Reviewed By:** [Pending Review]
**Approved By:** [Pending Approval]

**Total Story Points:** 42 pts across 4 sprints
**Total Estimated Effort:** 130-160 hours (backend engineering)
**POV Duration:** 8 weeks (Nov 2025 - Jan 2026)
**Go-Live Target:** February 2026 (if successful)

---

## Executive Overview: POV Purpose & Design Intent

This Proof of Value (POV) validates the feasibility of multi-agent enquiry and notification workflows across RRPS's C4C (Customer Engagement Center), IPAS (Intelligent Product Administration System), and MS5 (SAP ERP) systems. **Agents act strictly as observers**—enabling visibility, readiness insights, and automated notifications—while maintaining RRPS' no-write data policy. Users retain full manual control over order creation in MS5 and billing in SAP. The POV aims to demonstrate value through improved decision support, reduced information retrieval time, and proactive notifications, without compromising existing business processes or introducing automation risk. Success metrics focus on enquiry accuracy (≥80%), notification timeliness (≤5 minutes), and zero agent boundary violations.

---

## Story Point Summary by Sprint

| Sprint | Duration | Stories | Effort (hrs) | Story Points | Key Deliverables |
|--------|----------|---------|--------------|--------------|------------------|
| **Sprint 0** | 2 weeks (Nov 11-22) | Infrastructure Setup | 47-58 | N/A | Kailash SDK validated, CPI read-only integrations, notification infrastructure |
| **Sprint 1** | 2 weeks (Nov 18-29) | Stories 1.1-1.3 | 32-43 | **11 pts** | Opportunity enquiry, AI readiness assessment, reasoning views |
| **Sprint 2** | 2 weeks (Dec 2-13) | Stories 2.1-2.2 | 35-47 | **13 pts** | Order data retrieval, MS5 monitoring & notifications |
| **Sprint 3** | 2 weeks (Dec 16-27) | Stories 2.3-2.4 | 20-27 | **8 pts** | Sales Manager notifications, order status enquiry |
| **Sprint 4** | 2 weeks (Jan 6-17) | Story 3.1, UAT | 47-52 | **10 pts** | FinOps billing notifications, UAT with 3-5 pilot users |
| **Total** | **8 weeks** | **10 items** | **181-227 hrs** | **42 pts** | POV Decision: Jan 20, 2026 |

**Average Sprint Velocity:** 10.5 story points/sprint
**Sprint 0 Note:** Infrastructure setup has no story points but blocks all user stories.

---

# Sprint 0: Infrastructure Setup (2 weeks)

## Critical Prerequisite

**CRITICAL PREREQUISITE**: This must be completed BEFORE all other user stories.

## Description

Establish foundational development environment, validate Kailash SDK components (DataFlow alpha, Nexus multi-channel), test SAP CPI integration for **read-only** enquiry access, and create notification infrastructure for RRPS Lead-to-Cash POV.

**KEY CONSTRAINT**: Agents will NOT create, modify, or submit orders. Users manually create orders in MS5. Agents observe, notify, and answer questions.

---

## Ready Criteria

### Backend Setup & Validation
- [ ] PostgreSQL credentials confirmed in `.env`
- [ ] SAP CPI sandbox **read-only** access granted (OData queries for C4C, IPAS, SAP)
- [ ] Kailash SDK installation access verified
- [ ] Notification channels configured (email, Slack, or internal messaging)

### Frontend Setup & Design System
- [ ] N/A (API-first POV, no frontend in 8-week scope)

### Development Infrastructure
- [ ] Python 3.11+ environment ready
- [ ] Git repository cloned
- [ ] CI/CD pipeline configured (basic)

### Documentation & Team Knowledge
- [ ] Team available for 2-week setup sprint
- [ ] SDK documentation access confirmed
- [ ] Agent roles clearly documented: **Enquiry & Notification ONLY**

---

## Definition of Done

### 1. Backend Setup & DataFlow Alpha Validation
- [ ] Kailash SDK installed: `pip install kailash[dataflow,nexus,kaizen]`
- [ ] PostgreSQL connection verified using `.env` credentials
- [ ] **DataFlow Alpha Validation**:
  - [ ] @db.model generates 9 nodes for test `Notification` model
  - [ ] All auto-generated nodes work in workflows
  - [ ] PostgreSQL integration stable with 1000+ test notifications
  - [ ] Performance acceptable: queries < 200ms, filters < 500ms
- [ ] Nexus multi-channel deployment tested (API, CLI)
- [ ] Essential SDK patterns validated: `runtime.execute(workflow.build())`

### 2. SAP CPI Read-Only Integration Testing (CRITICAL PATH)
- [ ] **CEC OData Client** (TE-2):
  - [ ] OAuth2 authentication successful
  - [ ] **READ-ONLY**: Retrieve 10 test opportunities (no write operations)
  - [ ] Response time < 2 seconds
- [ ] **IPAS Client** (TE-3):
  - [ ] **READ-ONLY**: Retrieve 5 test BOM configurations
  - [ ] Parse BOM to SalesOrderItem list
  - [ ] Response time < 3 seconds
- [ ] **MS5 Order Query Client**:
  - [ ] **READ-ONLY**: Query existing orders by VBELN
  - [ ] Retrieve order status (Created, In Process, Delivered, Blocked)
  - [ ] Response time < 2 seconds
- [ ] **SAP Customer Master Client** (TE-12):
  - [ ] **READ-ONLY**: Retrieve customer master data
  - [ ] Response time < 2 seconds

### 3. Notification Infrastructure
- [ ] PostgreSQL notification tables created: `notifications`, `events`, `subscriptions`
- [ ] Append-only enforcement tested (no UPDATEs, only INSERTs)
- [ ] Test data: 20 sample notifications
- [ ] Email/Slack notification delivery tested

### 4. Documentation & Knowledge Transfer
- [ ] DataFlow alpha limitations documented
- [ ] CPI read-only endpoints documented
- [ ] Agent role boundaries documented: **NO order creation, NO order submission**
- [ ] Common issues and solutions logged
- [ ] Team walkthrough session completed (2 hours)

---

## DataFlow Alpha Validation

**Context:** DataFlow is PostgreSQL-only alpha. Sprint 0 validates it works for notification store use case.

### Success Criteria
- [ ] `Notification` model auto-generates all 9 nodes successfully
- [ ] Query/filter/create nodes work in workflows
- [ ] PostgreSQL integration stable with 1000+ test notifications
- [ ] Performance acceptable: queries < 200ms, filters < 500ms

### Decision Point

✅ **SUCCESS**: Proceed with DataFlow for notification store
⚠️ **PARTIAL**: Document workarounds, continue with caution, monitor for blockers
❌ **FAILURE**: Fallback to Core SDK AsyncSQLDatabaseNode, update notification store implementation (adds 1 week)

---

## Technical Subtasks

### 1. Kailash SDK Installation & Validation (4-6h)
- Install SDK with all frameworks
- Verify imports: `from kailash.workflow.builder import WorkflowBuilder`
- Test essential patterns: `runtime.execute(workflow.build())`
- Consult `sdk-navigator`, `framework-advisor`, `pattern-expert` agents if issues arise

### 2. DataFlow Alpha Validation (6-8h)
- Connect to PostgreSQL
- Create test `Notification` model with @db.model decorator
- Verify all 9 auto-generated nodes
- Load 1000 test notifications
- Measure query/filter performance

### 3. Nexus Multi-Channel Test (3-4h)
- Deploy hello-world workflow
- Test API endpoint (REST)
- Test CLI command
- Verify session management

### 4. CPI Read-Only Integration Testing (16-20h) - **CRITICAL PATH**
- **CEC OData** (4h): OAuth2 + 10 opportunity retrieval (READ-ONLY)
- **IPAS Client** (4h): 5 BOM retrievals + parsing (READ-ONLY)
- **MS5 Order Query** (6h): Order status queries by VBELN (READ-ONLY)
- **SAP Customer Master** (4h): Customer master data retrieval (READ-ONLY)

### 5. Notification Store Setup (8-12h)
- Create PostgreSQL tables (2h)
- Define Pydantic models (3h)
- Test DataFlow node generation (3h)
- Populate test data (2h)
- Test email/Slack delivery (2h)

### 6. Documentation (6-8h)
- CPI read-only endpoint documentation (3h)
- Agent role boundaries documentation (2h)
- Common issues log (2h)
- Team walkthrough session (2h)

---

## Estimated Effort

**Total:** 47-58 hours (1.5-2 weeks with 1 backend engineer + 0.5 integration specialist)

---

## Story Points

N/A (Infrastructure checklist, not a user story)

---

## Story Dependencies

**Blocks:**
- **ALL** Epic 1 stories (1.1, 1.2, 1.3)
- **ALL** Epic 2 stories (2.1, 2.2, 2.3, 2.4)
- **ALL** Epic 3 stories (3.1)
- UAT Sprint

**Dependencies:**
- **None** - This is the starting point

---

## Risks / Mitigation

### High-Risk Areas
1. **CPI Sandbox Downtime** (30% probability during Nov 11-15)
   - **Mitigation**: Schedule around SAP maintenance windows, maintain 2-day buffer
   - **Impact**: Could delay Sprint 1 start by 2-3 days

2. **DataFlow Alpha Stability** (20% probability of issues)
   - **Mitigation**: Fallback to Core SDK AsyncSQLDatabaseNode if unstable
   - **Impact**: Adds 1 week to Sprint 0 if fallback required

3. **OAuth2 CPI Authentication Complexity** (15% probability of delays)
   - **Mitigation**: Allocate 2 extra hours for troubleshooting, consult SAP CPI expert
   - **Impact**: Could extend TE-2 by 1 day

---

## Metadata

**Priority:** Critical
**Size:** N/A (Infrastructure)
**Estimate:** 47-58 hours
**Duration:** 2 weeks (Nov 11-22, 2025)
**Team:** 1 backend engineer + 0.5 integration specialist
**Audit Trail Reference:** Notification infrastructure established here (referenced in Stories 2.2, 2.3, 3.1)

---
---

# Sprint 1: Opportunity Enquiry Agent (2 weeks)

**Duration:** Nov 18-29, 2025
**Story Points:** 11 pts (3 + 5 + 3)
**Sprint Goal:** Enable Sales Managers to enquire about opportunity readiness via AI agents

---

# Story 1.1: Sales Manager Enquiry - Search Opportunities (3 pts)

## Critical Prerequisite

Sprint 0 must be complete with CEC OData Client (TE-2) validated for **read-only** access.

## Description

**As a** Sales Manager
**I want** to ask an AI agent to search opportunities by customer name or product family
**So that** I can quickly find deals without manually navigating C4C

**Agent Role:** **Enquiry ONLY** - Agent searches C4C and returns results. Agent does NOT create or modify opportunities.

---

## Ready Criteria

### Backend Setup & Validation
- [ ] Sprint 0 complete
- [ ] CEC OData Client (TE-2) tested and working (READ-ONLY)
- [ ] OAuth2 authentication to CPI verified
- [ ] Test opportunities available in C4C sandbox

### Frontend Setup & Design System
- [ ] N/A (API-first POV)

### Development Infrastructure
- [ ] Kailash SDK installed
- [ ] LocalRuntime configured
- [ ] Development environment ready

### Documentation & Team Knowledge
- [ ] OData query syntax documented
- [ ] CEC opportunity schema understood
- [ ] Team trained on WorkflowBuilder patterns

---

## Acceptance Criteria

- [ ] User asks agent: "Show me opportunities for Acme Corp" → Agent returns matching opportunities
- [ ] User asks agent: "Find opportunities for Power Systems product" → Agent returns matching opportunities
- [ ] Search supports partial matching (e.g., "Acme" matches "Acme Corp" and "Acme Industries")
- [ ] Results returned within 2 seconds
- [ ] Empty result set shows clear message: "No opportunities found for [search term]"
- [ ] Results include: Opportunity ID, Customer, Product, Amount, Close Date
- [ ] **Agent does NOT create or modify opportunities**

---

## Technical Implementation

**Workflow:** `SearchOpportunitiesEnquiryWorkflow`

**Nodes:**
1. `TextInputNode` → Capture user query (e.g., "Show opportunities for Acme Corp")
2. `CustomNode<QueryParserAgent>` → Parse query to extract search terms (customer or product)
3. `CustomNode<CECODataClient>` → **READ-ONLY** Query C4C opportunities via CPI
   - OData filter: `$filter=contains(AccountName, '{term}') or contains(ProductFamily, '{term}')`
   - OAuth2 authentication via CPI
4. `FilterOpportunitiesNode` → Filter results by status (Open, In Progress)
5. `FormatResultsNode` → Format as list
6. `TextOutputNode` → Return results or "No opportunities found"

**Edge Cases:**
- Search term with special characters → URL-encode before OData query
- CPI timeout (>5 sec) → Return error: "CEC system unavailable, try again later"
- OAuth2 token expired → Refresh token automatically, retry once
- User asks to create opportunity → Agent responds: "I can only search opportunities. Please create opportunities in C4C."

---

## Technical Subtasks

### 1. Create QueryParserAgent (Kaizen) (2-3h)
- Define LLM signature: `"user_query -> search_term, search_type"`
- Extract customer name or product family from natural language query
- Test with 10 sample queries

### 2. Create CECODataClient wrapper (3-4h)
- Implement OAuth2 authentication
- Build OData query construction logic (READ-ONLY)
- Add error handling and retries
- Test with 10 sample opportunities

### 3. Build SearchOpportunitiesEnquiryWorkflow (2-3h)
- Add TextInputNode for user query
- Configure QueryParserAgent node
- Configure `CustomNode<CECODataClient>` with client
- Add FilterOpportunitiesNode for status filtering
- Add FormatResultsNode for output
- Test end-to-end workflow

### 4. Handle edge cases (1-2h)
- URL encoding for special characters
- Timeout handling
- Token refresh logic
- Empty result handling
- Reject write requests

### 5. Testing & validation (2h)
- Test with 5 customer searches
- Test with 5 product searches
- Test partial matching
- Test error scenarios (timeout, auth failure)
- Test write rejection (user asks to create opportunity)
- Performance testing (< 2 sec response time)

---

## Estimated Effort

**Total:** 10-14 hours (1.5-2 days)

---

## Story Points

**3 pts** (Small)

---

## Story Dependencies

**Blocks:** None

**Dependencies:**
- Sprint 0 complete
- TE-2 (CEC OData Client) validated for READ-ONLY access

---

## Risks / Mitigation

### Medium-Risk Areas
1. **LLM Query Parser Accuracy** (15% probability of low accuracy)
   - **Mitigation**: Fallback to keyword-based parsing if LLM accuracy < 70%
   - **Impact**: May require additional refinement in Sprint 2

---

## Metadata

**Priority:** High
**Size:** Small (S)
**Estimate:** 10-14 hours
**Sprint:** Sprint 1 (Nov 18-29, 2025)
**Epic:** Epic 1 - Opportunity Enquiry

---
---

# Story 1.2: Sales Manager Enquiry - Filter by AI Readiness Assessment (5 pts)

## Critical Prerequisite

Story 1.1 must be complete. TE-4 (Opportunity Readiness Agent) must be implemented. TE-16 (Aravo KYP Client) must be validated.

## Description

**As a** Sales Manager
**I want** to ask an AI agent to filter opportunities by readiness criteria
**So that** I can prioritize deals most likely to convert to orders

**Agent Role:** **Enquiry ONLY** - Agent assesses readiness and returns filtered list. Agent does NOT modify opportunities or create orders.

---

## Ready Criteria

### Backend Setup & Validation
- [ ] Story 1.1 complete (search functionality working)
- [ ] Kaizen framework installed and configured
- [ ] LLM API access verified (OpenAI/Anthropic/local)
- [ ] Test data: 20 opportunities with varying completeness

### Frontend Setup & Design System
- [ ] N/A (API-first POV)

### Development Infrastructure
- [ ] Kaizen BaseAgent patterns understood
- [ ] LLM prompt templates documented
- [ ] Confidence scoring logic defined

### Documentation & Team Knowledge
- [ ] Team trained on Kaizen signature-based programming
- [ ] Readiness criteria documented (customer confirmed, product configured, pricing approved, delivery date, payment terms)
- [ ] Fallback rule-based scoring logic documented

---

## Acceptance Criteria

- [ ] User asks agent: "Show me opportunities ready to order" → Agent returns opportunities with ≥70% AI confidence score
- [ ] User asks agent: "Which opportunities need follow-up?" → Agent returns opportunities with 40-69% AI confidence score
- [ ] User asks agent: "Show me not-ready opportunities" → Agent returns opportunities with <40% AI confidence score
- [ ] Each opportunity shows AI confidence score (e.g., "85% Ready") with human-readable reasoning
- [ ] Reasoning includes missing prerequisites (e.g., "Missing: Delivery date, Payment terms")
- [ ] **KYP compliance status** is included in readiness assessment:
  - [ ] KYP APPROVED → Green indicator, no impact on score
  - [ ] KYP CONDITIONAL → Amber indicator, score reduced by 10 points, shows conditions (e.g., "High risk rating — additional review may be required")
  - [ ] KYP BLOCKED → Red indicator, opportunity flagged as "Not Ready" regardless of other criteria (e.g., "Third party REJECTED in Aravo")
  - [ ] KYP PENDING → Amber indicator, shows "KYP review in progress" (e.g., "TP Completing DDQ")
  - [ ] KYP NOT_FOUND → Red indicator, shows "Partner not registered in Aravo — registration required"
- [ ] Results sorted by confidence score (highest first)
- [ ] **Agent does NOT create or modify opportunities**

---

## Technical Implementation

**Workflow:** `AssessOpportunityReadinessEnquiryWorkflow`

**Nodes:**
1. `TextInputNode` → Capture user query (e.g., "Show me ready opportunities")
2. `CustomNode<QueryParserAgent>` → Parse query to extract readiness filter (ready/needs-follow-up/not-ready)
3. `CustomNode<CECODataClient>` → **READ-ONLY** Retrieve opportunities from Story 1.1 results
4. `CustomNode<AravoKYPClient>` → **READ-ONLY** Query Aravo KYP status for opportunity's customer
   - Direct REST API call to Aravo (not via CPI)
   - Fuzzy matches customer name against Aravo third-party records
   - Returns: KYPAssessment (kyp_status, risk_rating, onboarding_status, issues, blocking)
5. **Kaizen Agent: OpportunityReadinessAgent**
   - Input: Opportunity data + KYP assessment
   - LLM Signature: `"opportunity, kyp_assessment -> readiness_score, missing_fields, reasoning"`
   - Prompt: "Assess if this opportunity is ready to convert to SAP order. Check for: customer confirmed, product configured, pricing approved, delivery date set, payment terms agreed, KYP compliance status (APPROVED/CONDITIONAL/BLOCKED/PENDING)."
   - Output: `{score: 0.85, missing: ["delivery_date"], kyp_status: "APPROVED", reasoning: "Customer and pricing confirmed. KYP approved. Need delivery date."}`
6. `FilterByScoreNode` → Apply user-selected filter (≥70%, 40-69%, <40%)
7. `SortByScoreNode` → Sort by score descending
8. `TextOutputNode` → Format results with confidence score + KYP status + reasoning

**Edge Cases:**
- Opportunity with incomplete data → Score as <40%, list all missing fields
- LLM API timeout → Fallback to rule-based scoring (check for null fields)
- Aravo API unavailable → Log error, assess without KYP (flag as "KYP check unavailable")
- Customer name not found in Aravo → Flag as KYP NOT_FOUND, score as <40%
- User asks to update opportunity → Agent responds: "I can only assess readiness. Please update opportunities in C4C."

---

## Technical Subtasks

### 1. Implement OpportunityReadinessAgent (Kaizen) (8-10h)
- Define LLM signature for readiness assessment
- Create prompt template with readiness criteria
- Implement confidence scoring algorithm
- Build fallback rule-based logic for LLM failures
- Test with 20 sample opportunities

### 2. Integrate Aravo KYP Client (3-4h) — TE-16
- Add `CustomNode<AravoKYPClient>` node to workflow
- Map customer name from CEC opportunity to Aravo query
- Handle KYP status in readiness scoring (APPROVED/CONDITIONAL/BLOCKED/PENDING/NOT_FOUND)
- Handle Aravo API unavailability (degrade gracefully)
- Test with known Aravo customers

### 3. Build AssessOpportunityReadinessEnquiryWorkflow (3-4h)
- Integrate `CustomNode<CECODataClient>` from Story 1.1
- Integrate `CustomNode<AravoKYPClient>` for KYP assessment
- Add `CustomNode<OpportunityReadinessAgent>` node (with KYP input)
- Add FilterByScoreNode for user filter selection
- Add SortByScoreNode for ranking
- Test end-to-end workflow

### 4. Handle edge cases (2-3h)
- Incomplete opportunity data handling
- LLM timeout and fallback logic
- Aravo API timeout / unavailability handling
- Customer name mismatch in Aravo (fuzzy match threshold)
- Empty result handling
- Reject write requests

### 4. Testing & validation (3-4h)
- Test with 20 opportunities (10 ready, 5 partial, 5 not ready)
- Validate confidence scores align with expectations
- Test LLM fallback when API down
- Test write rejection (user asks to update opportunity)
- Performance testing (< 5 sec for 20 opportunities)

---

## Estimated Effort

**Total:** 16-21 hours (2-2.5 days)

---

## Story Points

**5 pts** (Medium)

---

## Story Dependencies

**Blocks:** None

**Dependencies:**
- Story 1.1 complete
- TE-4 (Opportunity Readiness Agent) implemented
- TE-16 (Aravo KYP Client) validated in Sprint 0

---

## Risks / Mitigation

### High-Risk Areas
1. **LLM Hallucination in Readiness Assessment** (25% probability)
   - **Mitigation**: Rule-based validation catches hallucinations, limits to null-field checks
   - **Impact**: May reduce confidence score accuracy to 70-80% vs. target 85%+

2. **Aravo Data Staleness** (15% probability)
   - **Mitigation**: Check ETL timestamp in report metadata; warn if >48h old
   - **Impact**: KYP status may be outdated for recently onboarded partners

3. **Customer Name Mismatch in Aravo** (20% probability)
   - **Mitigation**: Fuzzy matching with threshold 0.6; flag low-confidence matches
   - **Impact**: May miss valid partners or match wrong entity

---

## Metadata

**Priority:** High
**Size:** Medium (M)
**Estimate:** 16-21 hours
**Sprint:** Sprint 1 (Nov 18-29, 2025)
**Epic:** Epic 1 - Opportunity Enquiry

---
---

# Story 1.3: Sales Manager Enquiry - View AI Reasoning (3 pts)

## Critical Prerequisite

Story 1.2 must be complete.

## Description

**As a** Sales Manager
**I want** to ask the AI agent why it assessed an opportunity as ready/not ready
**So that** I can understand the assessment and take corrective action

**Agent Role:** **Enquiry ONLY** - Agent explains reasoning. Agent does NOT modify opportunities.

---

## Ready Criteria

### Backend Setup & Validation
- [ ] Story 1.2 complete (AI confidence scoring working)
- [ ] Test audit trail data available

### Frontend Setup & Design System
- [ ] N/A (API-first POV)

### Development Infrastructure
- [ ] Reasoning formatter patterns documented

### Documentation & Team Knowledge
- [ ] Reasoning display format documented
- [ ] Team trained on reasoning querying

---

## Acceptance Criteria

- [ ] User asks agent: "Why is opportunity X ready/not ready?" → Agent shows detailed AI reasoning
- [ ] Reasoning includes:
  - [ ] Confidence score (e.g., "85% Ready")
  - [ ] Checklist: Customer confirmed (✅), Product configured (✅), Pricing approved (✅), Delivery date (❌), Payment terms (✅)
  - [ ] Next steps: "Contact customer for delivery date confirmation"
- [ ] **Agent does NOT modify opportunities**

---

## Technical Implementation

**Workflow:** `ViewOpportunityReasoningEnquiryWorkflow`

**Nodes:**
1. `TextInputNode` → Capture user query (e.g., "Why is opportunity 12345 ready?")
2. `CustomNode<QueryParserAgent>` → Extract opportunity ID from query
3. `CustomNode<CECODataClient>` → **READ-ONLY** Retrieve full opportunity details
4. **Kaizen Agent: OpportunityReadinessAgent** (same as 1.2)
   - Return detailed checklist + next steps
5. `FormatReasoningNode` → Format as structured output (confidence, checklist, next steps)
6. `TextOutputNode` → Display reasoning

**Edge Cases:**
- Opportunity not found → Return "Invalid Opportunity ID"
- LLM reasoning too verbose → Truncate to 500 characters, add "See full reasoning..." link
- User asks to update opportunity → Agent responds: "I can only explain reasoning. Please update opportunities in C4C."

---

## Technical Subtasks

### 1. Build ViewOpportunityReasoningEnquiryWorkflow (3-4h)
- Integrate `CustomNode<CECODataClient>` and `CustomNode<OpportunityReadinessAgent>` from Story 1.2
- Add FormatReasoningNode for checklist display
- Add TextOutputNode for reasoning output
- Test with 10 sample opportunities

### 2. Handle edge cases (1-2h)
- Invalid opportunity ID handling
- Verbose reasoning truncation
- Reject write requests

### 3. Testing & validation (2h)
- Test reasoning display for 10 opportunities
- Test write rejection (user asks to update opportunity)

---

## Estimated Effort

**Total:** 6-8 hours (1 day)

---

## Story Points

**3 pts** (Small)

---

## Story Dependencies

**Blocks:** None

**Dependencies:**
- Story 1.2 complete

---

## Risks / Mitigation

**Low-Risk**: No significant risks identified.

---

## Metadata

**Priority:** Medium
**Size:** Small (S)
**Estimate:** 6-8 hours
**Sprint:** Sprint 1 (Nov 18-29, 2025)
**Epic:** Epic 1 - Opportunity Enquiry

---
---

# Sprint 2: Order Data Enquiry & Sales Operations Notification (2 weeks)

**Duration:** Dec 2-13, 2025
**Story Points:** 13 pts (5 + 8)
**Sprint Goal:** Enable Sales Operations to enquire about order data and automate MS5 order monitoring with notifications

---

# Story 2.1: Sales Operations Enquiry - Retrieve Order Data from Multiple Systems (5 pts)

## Critical Prerequisite

Sprint 0 must be complete with all CPI clients validated (TE-2, TE-3, TE-12) for **read-only** access.

## Description

**As a** Sales Operations Specialist
**I want** to ask an AI agent to retrieve order data from C4C, IPAS, and SAP when I'm preparing to create an order
**So that** I have all information ready before I manually create the order in MS5

**Agent Role:** **Enquiry ONLY** - Agent retrieves and displays data. User still **manually creates order in MS5**.

---

## Ready Criteria

### Backend Setup & Validation
- [ ] Sprint 0 complete
- [ ] CEC OData Client (TE-2) working (READ-ONLY)
- [ ] IPAS Client (TE-3) working (READ-ONLY)
- [ ] SAP Customer Master Client (TE-12) working (READ-ONLY)
- [ ] Test data available in all 3 systems

### Frontend Setup & Design System
- [ ] N/A (API-first POV)

### Development Infrastructure
- [ ] Parallel execution patterns documented
- [ ] Error handling for partial failures understood
- [ ] Merge logic for multi-system data defined

### Documentation & Team Knowledge
- [ ] Data mapping documented (C4C → Order, IPAS → Items, SAP → Customer Master)
- [ ] Timeout and retry policies defined
- [ ] Team trained on parallel workflow execution

---

## Acceptance Criteria

- [ ] User asks agent: "Get order data for opportunity 12345" → Agent retrieves data from C4C, IPAS, SAP in parallel
- [ ] **C4C Data Retrieved:** Customer name, Sold-to party, Ship-to party, Opportunity amount, Close date
- [ ] **IPAS Data Retrieved:** BOM (Bill of Materials) for product configuration → Parsed to SalesOrderItem list
- [ ] **SAP Data Retrieved:** Customer master data (payment terms, incoterms, sales org)
- [ ] All data retrieved within 5 seconds total (parallel execution)
- [ ] If any system unavailable → Shows which data is missing
- [ ] Merged order object includes data from all 3 sources
- [ ] **Agent does NOT create order in MS5** - User reviews data and manually creates order

---

## Technical Implementation

**Workflow:** `RetrieveOrderDataEnquiryWorkflow`

**Nodes:**
1. `TextInputNode` → Capture user query (e.g., "Get order data for opportunity 12345")
2. `CustomNode<QueryParserAgent>` → Extract opportunity ID from query
3. **Parallel Execution Block:**
   - `CustomNode<CECODataClient>` → **READ-ONLY** Retrieve C4C opportunity data (2 sec)
   - `CustomNode<IPASClient>` → **READ-ONLY** Retrieve BOM configuration (3 sec)
   - `CustomNode<SAPCustomerMasterClient>` → **READ-ONLY** Retrieve customer master data via CPI (2 sec)
4. `MergeDataNode` → Combine all data sources into unified order object
5. `ValidateCompletenessNode` → Check for missing required fields
6. `TextOutputNode` → Display merged data or list missing fields
7. **Reminder:** "Please review this data and manually create the order in MS5."

**Edge Cases:**
- IPAS timeout → Mark BOM as "unavailable", note manual entry needed
- C4C returns partial data → Mark missing fields
- SAP customer not found → Return error: "Customer [ID] not found in SAP, contact master data team"
- All 3 systems timeout → Return error: "All systems unavailable, try again later"
- User asks agent to create order → Agent responds: "I can only retrieve data. Please manually create the order in MS5."

---

## Technical Subtasks

### 1. Build parallel execution block (4-6h)
- Configure 3 CustomNodes for parallel execution (READ-ONLY)
- Implement timeout handling (5 sec max)
- Build retry logic (1 retry per system)
- Test parallel execution with mock data

### 2. Implement MergeDataNode (3-4h)
- Define unified order object schema
- Map C4C fields → Order header
- Map IPAS BOM → SalesOrderItem list
- Map SAP customer master → Payment terms, incoterms
- Test merge logic with 10 test cases

### 3. Build ValidateCompletenessNode (2-3h)
- Define required fields checklist
- Check for missing fields in merged object
- Flag partial data
- Test with complete and incomplete data

### 4. Handle edge cases (2-3h)
- System timeout handling
- Partial data handling
- Customer not found in SAP
- All systems down scenario
- Reject write requests (no order creation)

### 5. Testing & validation (3-4h)
- Test with 10 complete opportunities
- Test with missing data in each system
- Test with 1 system down, 2 systems down, all down
- Test write rejection (user asks to create order)
- Performance testing (< 5 sec total)

---

## Estimated Effort

**Total:** 14-20 hours (2-2.5 days)

---

## Story Points

**5 pts** (Medium)

---

## Story Dependencies

**Blocks:** None

**Dependencies:**
- Sprint 0 complete
- TE-2 (CEC OData Client) validated (READ-ONLY)
- TE-3 (IPAS Client) validated (READ-ONLY)
- TE-12 (SAP Customer Master Client) validated (READ-ONLY)

---

## Risks / Mitigation

### High-Risk Areas
1. **Parallel Execution Complexity** (20% probability of issues)
   - **Mitigation**: Sequential fallback if parallel execution unstable
   - **Impact**: Response time may increase to 7-8 seconds vs. target 5 seconds

2. **IPAS BOM Parsing Variability** (15% probability of parsing errors)
   - **Mitigation**: Robust error handling with "BOM unavailable" fallback
   - **Impact**: Users may need manual BOM entry for complex products

---

## Metadata

**Priority:** High
**Size:** Medium (M)
**Estimate:** 14-20 hours
**Sprint:** Sprint 2 (Dec 2-13, 2025)
**Epic:** Epic 2 - Order Data Enquiry

---
---

# Story 2.2: Data Management Agent - Auto-Copy Order Details & Notify Sales Operations (8 pts)

## Critical Prerequisite

Story 2.1 must be complete. MS5 Order Query Client must be implemented for **read-only** access.

## Description

**As a** Sales Operations Specialist
**I want** the Data Management Agent to automatically detect when I create an order in MS5, copy the details, and notify the Sales Operations Agent
**So that** Sales Operations Agent can notify Sales Manager without manual intervention

**Agent Role:** **Notification ONLY** - Data Management Agent monitors MS5 for new orders (READ-ONLY), copies details to internal store, and notifies Sales Operations Agent. Agent does NOT create or modify orders in MS5.

---

## Ready Criteria

### Backend Setup & Validation
- [ ] Story 2.1 complete (data retrieval working)
- [ ] MS5 Order Query Client implemented for **READ-ONLY** access
- [ ] Polling or webhook mechanism configured for MS5 order events
- [ ] Notification infrastructure ready (from Sprint 0)
- [ ] Sales Operations Agent notification endpoint ready

### Frontend Setup & Design System
- [ ] N/A (API-first POV)

### Development Infrastructure
- [ ] Polling interval configured (e.g., every 5 minutes)
- [ ] Webhook authentication configured (if using webhooks)
- [ ] Internal order store schema defined (PostgreSQL)

### Documentation & Team Knowledge
- [ ] MS5 order query API documented
- [ ] Polling vs. webhook approach documented
- [ ] Notification delivery mechanisms documented
- [ ] Team trained on monitoring patterns

---

## Acceptance Criteria

- [ ] User manually creates order in MS5 → Data Management Agent detects new order within 5 minutes (polling) or immediately (webhook)
- [ ] Data Management Agent **reads** order details from MS5 (VBELN, customer, items, amounts, status)
- [ ] Data Management Agent copies order details to internal PostgreSQL store
- [ ] Data Management Agent sends notification to Sales Operations Agent: "New order [VBELN] created by [user] for [customer]"
- [ ] Sales Operations Agent receives notification and can query order details
- [ ] **Agent does NOT create or modify orders in MS5**

---

## Technical Implementation

**Workflow:** `MonitorMS5OrdersWorkflow` (runs continuously via polling or webhook)

**Nodes:**
1. **Polling Approach:**
   - `SchedulerNode` → Trigger every 5 minutes
   - `CustomNode<MS5OrderQueryClient>` → **READ-ONLY** Query MS5 for orders created in last 5 minutes
   - `FilterNewOrdersNode` → Filter out orders already in internal store
2. **Webhook Approach (alternative):**
   - `WebhookReceiverNode` → Receive MS5 order creation event
   - `ValidateWebhookNode` → Validate webhook signature
3. `CustomNode<MS5OrderQueryClient>` → **READ-ONLY** Retrieve full order details by VBELN
4. `CustomNode<InternalOrderStoreWriterNode>` → Copy order details to PostgreSQL
5. `CustomNode<NotificationSenderNode>` → Send notification to Sales Operations Agent
   - Notification: "New order [VBELN] created by [user] for [customer]"
6. `LogEventNode` → Log monitoring event to audit trail

**Edge Cases:**
- MS5 API timeout → Log error, retry on next poll
- Duplicate detection → Skip orders already in internal store
- Webhook signature invalid → Reject webhook, log security event
- Sales Operations Agent offline → Queue notification for later delivery

**Audit Trail Linkage:** References notification infrastructure from Sprint 0 (TE-14).

---

## Technical Subtasks

### 1. Implement MS5OrderQueryClient (READ-ONLY) (4-5h)
- Build MS5 order query API wrapper
- Implement authentication
- Parse order details from MS5 response
- Test with 10 sample orders

### 2. Build MonitorMS5OrdersWorkflow (polling approach) (5-6h)
- Configure SchedulerNode for 5-minute polling
- Build FilterNewOrdersNode to avoid duplicates
- Test polling with mock MS5 data
- Measure latency (should detect orders within 5 min)

### 3. Implement InternalOrderStoreWriterNode (3-4h)
- Define internal order schema in PostgreSQL
- Build DataFlow nodes for order storage
- Test writes with 10 sample orders

### 4. Build NotificationSenderNode (3-4h)
- Configure notification delivery (email, Slack, API)
- Format notification message
- Test delivery to Sales Operations Agent endpoint

### 5. Handle edge cases (2-3h)
- MS5 API timeout handling
- Duplicate detection logic
- Webhook validation (if using webhooks)
- Notification queueing for offline agents

### 6. Testing & validation (4-5h)
- Test with 20 manual order creations in MS5
- Verify agent detects all 20 within 5 minutes
- Verify notifications delivered to Sales Operations Agent
- Test duplicate detection (create same order twice)
- Test MS5 downtime scenario

---

## Estimated Effort

**Total:** 21-27 hours (3-3.5 days)

---

## Story Points

**8 pts** (Large)

---

## Story Dependencies

**Blocks:** None

**Dependencies:**
- Story 2.1 complete
- MS5 Order Query Client implemented (READ-ONLY)
- Notification infrastructure ready (Sprint 0)

---

## Risks / Mitigation

### High-Risk Areas
1. **MS5 API Rate Limiting** (25% probability)
   - **Mitigation**: Implement exponential backoff, increase polling interval to 10 minutes if rate-limited
   - **Impact**: May increase detection latency to 10 minutes vs. target 5 minutes

2. **Webhook Reliability** (20% probability if using webhooks)
   - **Mitigation**: Fallback to polling if webhook failures exceed 5%
   - **Impact**: Reduces real-time notifications, falls back to 5-10 minute polling

---

## Metadata

**Priority:** Critical
**Size:** Large (L)
**Estimate:** 21-27 hours
**Sprint:** Sprint 2 (Dec 2-13, 2025)
**Epic:** Epic 2 - Order Notification
**Audit Trail Reference:** Notification store from Sprint 0

---
---

# Sprint 3: Sales Operations & Sales Manager Notifications (2 weeks)

**Duration:** Dec 16-27, 2025
**Story Points:** 8 pts (5 + 3)
**Sprint Goal:** Route order notifications to Sales Managers and enable order status enquiry

---

# Story 2.3: Sales Operations Agent - Notify Sales Manager of Order Updates (5 pts)

## Critical Prerequisite

Story 2.2 must be complete (Data Management Agent sending notifications).

## Description

**As a** Sales Manager
**I want** the Sales Operations Agent to automatically notify me when new orders are created or updated
**So that** I'm always aware of my team's order activity without checking MS5 manually

**Agent Role:** **Notification ONLY** - Sales Operations Agent receives notifications from Data Management Agent and forwards to Sales Manager. Agent does NOT create or modify orders.

---

## Ready Criteria

### Backend Setup & Validation
- [ ] Story 2.2 complete (Data Management Agent notifications working)
- [ ] Sales Operations Agent notification endpoint implemented
- [ ] Sales Manager notification channels configured (email, Slack, etc.)
- [ ] Subscription/preference system ready (Sales Managers can subscribe to specific customers/products)

### Frontend Setup & Design System
- [ ] N/A (API-first POV)

### Development Infrastructure
- [ ] Notification routing logic defined
- [ ] Subscription management patterns documented

### Documentation & Team Knowledge
- [ ] Notification preferences documented
- [ ] Escalation rules documented (e.g., high-value orders)
- [ ] Team trained on subscription management

---

## Acceptance Criteria

- [ ] Data Management Agent sends notification "New order [VBELN] created" → Sales Operations Agent receives it
- [ ] Sales Operations Agent checks Sales Manager subscriptions:
  - [ ] If Sales Manager subscribed to customer/product → Forward notification
  - [ ] If high-value order (>$100K) → Forward to all Sales Managers with "High-Value Order Alert"
- [ ] Sales Manager receives notification: "New order [VBELN] created by [user] for [customer] - [amount]"
- [ ] Sales Manager can click notification to view order details (from Story 2.4)
- [ ] **Agent does NOT create or modify orders**

---

## Technical Implementation

**Workflow:** `SalesOpsNotificationRoutingWorkflow`

**Nodes:**
1. `InputNode<NotificationObject>` → Receive notification from Data Management Agent
2. `CustomNode<InternalOrderStoreReaderNode>` → **READ-ONLY** Retrieve full order details from internal store
3. `CheckSubscriptionsNode` → Query subscription table for Sales Managers interested in this customer/product
4. `CheckHighValueNode` → If order amount > $100K, flag as high-value
5. `RouteNotificationsNode` → Determine recipients (subscribed managers + all managers if high-value)
6. `CustomNode<NotificationSenderNode>` → Send notifications to Sales Managers
   - Notification: "New order [VBELN] created by [user] for [customer] - [amount]"
7. `LogEventNode` → Log notification delivery to audit trail

**Edge Cases:**
- No subscribed Sales Managers → Send to default manager
- Sales Manager notification delivery fails → Queue for retry, send backup email
- Order details incomplete → Send basic notification with "Details unavailable"

**Audit Trail Linkage:** References notification infrastructure from Sprint 0 (TE-14) and internal order store from Story 2.2.

---

## Technical Subtasks

### 1. Build SalesOpsNotificationRoutingWorkflow (4-5h)
- Integrate with Data Management Agent notifications
- Build CheckSubscriptionsNode for routing logic
- Build CheckHighValueNode for escalation
- Test with 10 sample notifications

### 2. Implement subscription management (3-4h)
- Create PostgreSQL subscription table
- Build subscription query logic
- Test with 5 Sales Managers, various subscription rules

### 3. Build NotificationSenderNode for Sales Managers (2-3h)
- Format notification message for Sales Managers
- Test delivery via email/Slack
- Test with 10 notifications

### 4. Handle edge cases (2-3h)
- No subscriptions → Default manager routing
- Delivery failure → Retry and backup email
- Incomplete order details handling

### 5. Testing & validation (3-4h)
- Test with 20 order notifications
- Verify correct routing based on subscriptions
- Verify high-value escalation
- Test delivery failure scenarios

---

## Estimated Effort

**Total:** 14-19 hours (2-2.5 days)

---

## Story Points

**5 pts** (Medium)

---

## Story Dependencies

**Blocks:** None

**Dependencies:**
- Story 2.2 complete (Data Management Agent notifications)
- Notification infrastructure (Sprint 0)
- Internal order store (Story 2.2)

---

## Risks / Mitigation

**Low-Risk**: No significant risks identified.

---

## Metadata

**Priority:** High
**Size:** Medium (M)
**Estimate:** 14-19 hours
**Sprint:** Sprint 3 (Dec 16-27, 2025)
**Epic:** Epic 2 - Order Notification
**Audit Trail Reference:** Notification store from Sprint 0, internal order store from Story 2.2

---
---

# Story 2.4: Sales Manager Enquiry - View Order Status & History (3 pts)

## Critical Prerequisite

Story 2.3 must be complete (Sales Operations Agent notifications working).

## Description

**As a** Sales Manager
**I want** to ask the agent for order status and history
**So that** I can track my team's orders without logging into MS5

**Agent Role:** **Enquiry ONLY** - Agent queries internal store and MS5 for order status. Agent does NOT create or modify orders.

---

## Ready Criteria

### Backend Setup & Validation
- [ ] Story 2.3 complete (notifications working)
- [ ] Internal order store populated with order history
- [ ] MS5 Order Query Client working (READ-ONLY)

### Frontend Setup & Design System
- [ ] N/A (API-first POV)

### Development Infrastructure
- [ ] Order status query patterns documented

### Documentation & Team Knowledge
- [ ] Order status codes documented
- [ ] History display format documented

---

## Acceptance Criteria

- [ ] User asks agent: "What's the status of order 12345?" → Agent returns current MS5 status (Created, In Process, Delivered, Blocked)
- [ ] User asks agent: "Show me order history for 12345" → Agent returns timeline:
  - [ ] Order created (user, timestamp)
  - [ ] Notifications sent (Sales Manager notified, timestamp)
  - [ ] Current status in MS5
- [ ] **Agent does NOT create or modify orders**

---

## Technical Implementation

**Workflow:** `ViewOrderStatusEnquiryWorkflow`

**Nodes:**
1. `TextInputNode` → Capture user query (e.g., "What's the status of order 12345?")
2. `CustomNode<QueryParserAgent>` → Extract VBELN from query
3. `CustomNode<MS5OrderQueryClient>` → **READ-ONLY** Query MS5 for current order status
4. `CustomNode<InternalOrderStoreReaderNode>` → **READ-ONLY** Retrieve order history from internal store
5. `FormatOrderHistoryNode` → Format as timeline: Created → Notified → Current Status
6. `TextOutputNode` → Display status + history

**Edge Cases:**
- VBELN not found in MS5 → Return "Order not found, check VBELN"
- History incomplete → Display warning: "Partial history, contact support"
- User asks to modify order → Agent responds: "I can only query orders. Please modify orders in MS5."

**Audit Trail Linkage:** References internal order store from Story 2.2.

---

## Technical Subtasks

### 1. Build ViewOrderStatusEnquiryWorkflow (3-4h)
- Integrate `CustomNode<MS5OrderQueryClient>` (READ-ONLY)
- Integrate `CustomNode<InternalOrderStoreReaderNode>`
- Build FormatOrderHistoryNode
- Test with 10 sample VBELNs

### 2. Handle edge cases (1-2h)
- VBELN not found handling
- Incomplete history handling
- Reject write requests

### 3. Testing & validation (2h)
- Test with 10 valid VBELNs
- Test with invalid VBELN
- Test with incomplete history
- Test write rejection (user asks to modify order)

---

## Estimated Effort

**Total:** 6-8 hours (1 day)

---

## Story Points

**3 pts** (Small)

---

## Story Dependencies

**Blocks:** None

**Dependencies:**
- Story 2.3 complete (notifications)
- Internal order store (Story 2.2)

---

## Risks / Mitigation

**Low-Risk**: No significant risks identified.

---

## Metadata

**Priority:** Medium
**Size:** Small (S)
**Estimate:** 6-8 hours
**Sprint:** Sprint 3 (Dec 16-27, 2025)
**Epic:** Epic 2 - Order Notification
**Audit Trail Reference:** Internal order store from Story 2.2

---
---

# Sprint 4: Finance Operations Agent - Billing Checks & Notifications (2 weeks)

**Duration:** Jan 6-17, 2026
**Story Points:** 10 pts (5 + 5)
**Sprint Goal:** Automate billing status checks and complete UAT with pilot users

---

# Story 3.1: Finance Operations Agent - Check Billing Status & Notify (5 pts)

## Critical Prerequisite

Story 2.4 must be complete. SAP Billing Query Client must be implemented for **read-only** access.

## Description

**As a** Finance Operations Specialist
**I want** the Finance Operations Agent to automatically check billing status for delivered orders and notify me of billing issues
**So that** I can follow up on unbilled orders without manually checking SAP

**Agent Role:** **Enquiry & Notification ONLY** - Finance Operations Agent checks billing status (READ-ONLY) and sends notifications. Agent does NOT create or trigger billing.

---

## Ready Criteria

### Backend Setup & Validation
- [ ] Story 2.4 complete (order status queries working)
- [ ] SAP Billing Query Client implemented for **READ-ONLY** access
- [ ] Finance Operations notification channels configured (email, Slack, etc.)
- [ ] Polling interval configured (e.g., daily)

### Frontend Setup & Design System
- [ ] N/A (API-first POV)

### Development Infrastructure
- [ ] Billing status codes documented
- [ ] Notification templates created

### Documentation & Team Knowledge
- [ ] Billing query patterns documented
- [ ] Escalation rules documented (e.g., unbilled >7 days)

---

## Acceptance Criteria

- [ ] Finance Operations Agent checks SAP daily for delivered orders (status = "Delivered")
- [ ] For each delivered order → Agent **reads** billing status from SAP (Billed, Not Billed, Blocked)
- [ ] If order unbilled >7 days → Agent sends notification to Finance Operations: "Order [VBELN] delivered on [date] but not yet billed"
- [ ] If billing blocked → Agent sends urgent notification: "Order [VBELN] billing blocked: [reason]"
- [ ] **Agent does NOT create or trigger billing** - Finance Operations user manually creates billing in SAP

---

## Technical Implementation

**Workflow:** `MonitorBillingStatusWorkflow` (runs daily via scheduler)

**Nodes:**
1. `SchedulerNode` → Trigger daily at 9 AM
2. `CustomNode<InternalOrderStoreReaderNode>` → **READ-ONLY** Query delivered orders from internal store
3. `CustomNode<SAPBillingQueryClient>` → **READ-ONLY** Query billing status for each delivered order
4. `FilterUnbilledOrdersNode` → Filter orders unbilled >7 days
5. `FilterBlockedBillingNode` → Filter orders with billing blocked
6. `CustomNode<NotificationSenderNode>` → Send notifications to Finance Operations
   - Notification: "Order [VBELN] delivered on [date] but not yet billed"
   - Urgent: "Order [VBELN] billing blocked: [reason]"
7. `LogEventNode` → Log monitoring event to audit trail

**Edge Cases:**
- SAP billing API timeout → Log error, retry next day
- Order billed between checks → Remove from unbilled list
- Finance Operations user offline → Queue notification for later delivery
- User asks agent to create billing → Agent responds: "I can only check billing status. Please manually create billing in SAP."

**Audit Trail Linkage:** References notification infrastructure from Sprint 0 (TE-14) and internal order store from Story 2.2.

---

## Technical Subtasks

### 1. Implement SAPBillingQueryClient (READ-ONLY) (4-5h)
- Build SAP billing status query API wrapper
- Implement authentication
- Parse billing status from SAP response
- Test with 10 sample orders

### 2. Build MonitorBillingStatusWorkflow (4-5h)
- Configure SchedulerNode for daily runs
- Build FilterUnbilledOrdersNode (>7 days logic)
- Build FilterBlockedBillingNode
- Test with mock data

### 3. Build NotificationSenderNode for Finance Operations (2-3h)
- Format notification messages
- Test delivery via email/Slack
- Test with 10 notifications

### 4. Handle edge cases (2-3h)
- SAP API timeout handling
- Order state changes between checks
- Notification queueing for offline users
- Reject write requests (no billing creation)

### 5. Testing & validation (3-4h)
- Test with 20 delivered orders (10 billed, 10 unbilled)
- Verify unbilled >7 days detection
- Verify blocked billing detection
- Test SAP downtime scenario
- Test write rejection (user asks to create billing)

---

## Estimated Effort

**Total:** 15-20 hours (2-2.5 days)

---

## Story Points

**5 pts** (Medium)

---

## Story Dependencies

**Blocks:** None

**Dependencies:**
- Story 2.4 complete
- SAP Billing Query Client implemented (READ-ONLY)
- Notification infrastructure (Sprint 0)
- Internal order store (Story 2.2)

---

## Risks / Mitigation

### Medium-Risk Areas
1. **SAP Billing API Complexity** (20% probability of parsing issues)
   - **Mitigation**: Fallback to manual billing checks if API unreliable
   - **Impact**: May reduce automation value for Finance Operations users

---

## Metadata

**Priority:** High
**Size:** Medium (M)
**Estimate:** 15-20 hours
**Sprint:** Sprint 4 (Jan 6-17, 2026)
**Epic:** Epic 3 - Billing Notification
**Audit Trail Reference:** Notification store from Sprint 0, internal order store from Story 2.2

---
---

# Sprint 4: UAT & Iteration (1 week)

**Duration:** Jan 13-17, 2026
**Story Points:** 5 pts

---

# UAT Sprint: Week 8 Testing & Metrics (5 pts)

## Critical Prerequisite

ALL Epic 1, Epic 2, and Epic 3 stories must be complete (Stories 1.1-1.3, 2.1-2.4, 3.1).

## Description

Validate Epic 1-3 with 3-5 pilot users, test agent enquiry/notification workflows end-to-end, capture metrics, and iterate based on feedback.

**KEY CONSTRAINT**: Validate that agents are **enquiry/notification only** - users still manually create orders in MS5.

---

## Ready Criteria

### Backend Setup & Validation
- [ ] All Epic 1-3 stories complete and tested
- [ ] End-to-end workflow tested (Enquiry → Manual Order Creation → Notification)
- [ ] SAP sandbox stable and available
- [ ] Notification delivery working for all channels

### Frontend Setup & Design System
- [ ] N/A (API-first POV)

### Development Infrastructure
- [ ] Metrics collection framework ready (spreadsheet or simple dashboard)
- [ ] Test data generator ready (20 sample opportunities)
- [ ] Bug tracking system ready
- [ ] Daily feedback session schedule created

### Documentation & Team Knowledge
- [ ] User training materials prepared (1-hour walkthrough)
- [ ] Agent role boundaries clearly communicated: **Enquiry & Notification ONLY**
- [ ] Bug report template created
- [ ] Feedback survey prepared (5 questions, 1-5 scale)

---

## Scope

- [ ] **3-5 pilot users** (1-2 Sales Managers, 1-2 Sales Operations Specialists, 1 Finance Operations Specialist)
- [ ] **10 test scenarios** covering enquiry and notification workflows
- [ ] **Daily 15-minute feedback sessions** (4 sessions total over 1 week)
- [ ] **Bug fixes and tweaks** (max 1 day per fix)

---

## Metrics to Capture

### 1. Agent Enquiry Accuracy (PRIMARY POV METRIC)
- **Definition:** % of agent enquiry responses that are correct and helpful
- **Measurement:** User rates each enquiry response (Correct/Incorrect/Partially Correct)
- **Target:** ≥80% correct responses
- **Data Collection:** Track each enquiry and user rating

### 2. Notification Timeliness
- **Definition:** Time from order creation in MS5 to Sales Manager notification
- **Target:** ≤5 minutes (polling approach) or immediate (webhook approach)
- **Data Collection:** Timestamp MS5 order creation → Timestamp Sales Manager notification

### 3. User Satisfaction
- **Definition:** User survey score (5 questions, 1-5 scale, average)
- **Target:** ≥3.5/5 (acceptable for POV)
- **Survey Questions:**
  1. How helpful were agent enquiry responses? (Stories 1.1-1.3, 2.1, 2.4)
  2. How timely were order notifications? (Stories 2.2-2.3)
  3. Did the agent correctly understand its role (no order creation)? (Agent boundaries)
  4. How helpful were billing notifications? (Story 3.1)
  5. Would you continue using this tool in production? (Overall)

### 4. Agent Role Boundary Violations
- **Definition:** # of times agent attempted to create/modify orders (should be 0)
- **Target:** 0 violations
- **Data Collection:** Track all write requests rejected by agents

---

## Success Criteria

### ✅ SCALE (Proceed to Production Rollout)
- [ ] **Enquiry accuracy ≥80%** (agent responses correct and helpful)
- [ ] **Notifications delivered within 5 minutes** (or immediately if webhook)
- [ ] **0 agent role boundary violations** (agent never attempted to create/modify orders)
- [ ] **Users satisfied** (survey ≥3.5/5, willing to use in production)
- [ ] **0 critical bugs** (no notification loss, data corruption)

**Next Steps if SCALE:**
- Secure 6-week production prep budget
- Add Epic 4 (Full UAT with 20+ users)
- Plan 50-user rollout for February 2026

**Future Scalability Note:** If successful, agents may be extended to perform workflow recommendations (not actions) under a controlled approval framework, maintaining the no-write policy while adding decision support value.

---

### ⚠️ ITERATE (Extend POV by 2 Weeks)
- [ ] **Enquiry accuracy 60-79%** (some helpful responses, some errors)
- [ ] **Notifications delayed 5-15 minutes** (polling interval too long)
- [ ] **Mixed user feedback** (some value, many issues)
- [ ] **1-2 fixable critical bugs** (can be resolved in 1 week)

**Next Steps if ITERATE:**
- Analyze low accuracy: AI quality issue? Data quality issue?
- Fix critical bugs (1 week)
- Rerun UAT with 5 more scenarios (1 week)
- Reassess at Week 10

---

### ❌ STOP (Redesign or Abandon)
- [ ] **Enquiry accuracy <60%** (agent responses mostly incorrect)
- [ ] **Notifications not delivered or delayed >15 minutes**
- [ ] **1+ agent role boundary violations** (agent attempted to create/modify orders)
- [ ] **Users refuse to continue** testing
- [ ] **3+ critical bugs** or CPI integration unstable

**Next Steps if STOP:**
- Root cause analysis: AI quality? CPI integration? Agent design?
- If CPI integration: Redesign integration layer, retry in 8 weeks
- If AI quality: Pivot to simpler rule-based enquiry (no LLM)
- If agent design: Redesign agent boundaries, add more guardrails

---

## Technical Subtasks

### Day 1: UAT Kickoff (4h)
- 1-hour user training session (system walkthrough)
- Emphasize agent role: **Enquiry & Notification ONLY**
- Distribute test credentials and sandbox access
- Review test scenarios (10 test workflows)
- Answer questions and clarify POV goals

### Day 2-4: Execute 10 test scenarios (24h)
- Users execute 10 scenarios end-to-end
- Capture metrics per scenario (enquiry accuracy, notification timeliness)
- Daily 15-minute feedback session (identify blockers)
- Document bugs and issues in real-time
- Backend team on standby for urgent fixes

### Day 5: Final metrics collection + user survey (4h)
- Compile all metrics (enquiry accuracy, notification timeliness, boundary violations)
- Distribute user satisfaction survey
- Analyze results and prepare POV decision report
- Schedule POV Decision Meeting (Jan 20, 2026)

---

## Estimated Effort

**Total:** 32 hours (Backend: 12h for bug fixes, Users: 24h for testing)

---

## Story Points

**5 pts** (Medium) - Reflects 1-week effort with multiple users

---

## Story Dependencies

**Blocks:** POV Decision (Jan 20, 2026)

**Dependencies:**
- Story 1.1 complete
- Story 1.2 complete
- Story 1.3 complete
- Story 2.1 complete
- Story 2.2 complete
- Story 2.3 complete
- Story 2.4 complete
- Story 3.1 complete

---

## Risks / Mitigation

### High-Risk Areas
1. **User Adoption Resistance** (25% probability)
   - **Mitigation**: Extra training session, clear communication of agent value proposition
   - **Impact**: May reduce user satisfaction scores below 3.5/5 target

2. **Pilot User Availability During Holiday Week** (20% probability)
   - **Mitigation**: Schedule UAT after Jan 6 to avoid holiday conflicts
   - **Impact**: May delay UAT start by 1 week

---

## Metadata

**Priority:** Critical
**Size:** Medium (M)
**Estimate:** 32 hours (12h backend + 24h user testing)
**Sprint:** Sprint 4 (Jan 13-17, 2026)
**POV Decision Date:** January 20, 2026
**Go-Live Target:** February 2026 (if SCALE decision)

---

# End of Document

**Total Story Points:** 42 pts across 4 sprints (Sprint 0 N/A + Sprint 1 11 pts + Sprint 2 13 pts + Sprint 3 8 pts + Sprint 4 10 pts)
**Total Estimated Effort:** 181-227 hours (backend engineering)
**POV Duration:** 8 weeks (Nov 2025 - Jan 2026)
**Go-Live:** February 2026 (if successful)

---

## Summary of Agent Roles

| Agent | Role | Can Do | Cannot Do |
|-------|------|--------|-----------|
| **Opportunity Enquiry Agent** | Enquiry | Search opportunities, assess readiness, explain reasoning | Create/modify opportunities, create orders |
| **Order Data Enquiry Agent** | Enquiry | Retrieve data from C4C/IPAS/SAP, display merged data | Create/modify orders in MS5 |
| **Data Management Agent** | Notification | Monitor MS5 for new orders (READ-ONLY), copy details to internal store, notify Sales Operations Agent | Create/modify orders in MS5 |
| **Sales Operations Agent** | Notification | Receive notifications from Data Management Agent, route to Sales Managers | Create/modify orders |
| **Finance Operations Agent** | Enquiry & Notification | Check billing status (READ-ONLY), send notifications | Create/trigger billing in SAP |

**KEY PRINCIPLE**: All agents are **passive observers**. Users manually create orders in MS5 and billing in SAP. Agents only enquire, notify, and support.

---

## Document Change History

| Version | Date | Changes | Author |
|---------|------|---------|--------|
| 1.0 | 2025-10-14 | Initial draft with order creation automation (incorrect) | RRPS Team |
| 2.0 | 2025-10-14 | Major revision: Agents changed to enquiry/notification only (correct) | RRPS Team |
| 2.1 | 2025-10-14 | Applied editorial critiques: Added executive overview, story point summary table, standardized terminology, improved formatting, added risks/mitigation sections, audit trail linkage, future scalability note | RRPS Team |

---

**Document Status:** Final Draft - Ready for Review
