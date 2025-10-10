# Testing Analysis: RRPS Lead-to-Cash POV Requirements (v3.0)

**Document Version:** 1.0
**Date:** 2025-10-10
**Analyzed Requirements:** requirements-breakdown-v3-value-chain.md
**Testing Framework:** Kailash SDK 3-Tier Testing Strategy (NO MOCKING in Tiers 2-3)

---

## Executive Summary

This document analyzes the testability of all user stories in the RRPS Lead-to-Cash POV from a rigorous testing perspective, following the Kailash SDK's 3-tier testing strategy with **NO MOCKING** policy for integration and end-to-end tests.

### Key Findings

**Overall Testability:** MODERATE (60-70%)

**Critical Gaps Identified:**
1. **Acceptance criteria lack specific test metrics** (e.g., "≥70% auto-fill" is testable, but "clear error message" is subjective)
2. **Missing error scenario coverage** (happy path well-defined, but edge cases need expansion)
3. **Real infrastructure requirements underspecified** (CEC, IPAS, MS5 sandbox environments assumed but not detailed)
4. **Test data generation complexity high** (realistic CEC opportunities + IPAS BOMs + SAP master data required)
5. **Timing/performance assertions missing** (except for explicit KPIs like "≥70% acceptance rate")

**Test Infrastructure Required:**
- **External Systems (NO MOCKING):** CEC OData sandbox, IPAS sandbox, MS5 BAPI/IDoc sandbox (via CPI), ArchiveLink sandbox
- **Internal Services:** PostgreSQL (audit store), Redis (session/cache), MinIO (document storage), Elasticsearch (search)
- **Message Brokers:** Kafka/RabbitMQ (for CPI event delivery)
- **Test Data:** Synthetic CEC opportunities, IPAS configurations, SAP master data (partners, materials, pricing)

**Recommendation:**
Expand acceptance criteria with:
1. Explicit test scenarios (happy path, error cases, edge cases)
2. Quantifiable success metrics for all subjective criteria
3. Performance benchmarks for all timed operations
4. Test data requirements per user story

---

## 1. Testability Analysis by Epic

### Epic 1: Sales Manager - Opportunity Qualification & Prioritization

#### User Story 1.1: Opportunity Readiness Scoring

**Testability Score:** 75% (GOOD)

**What's Testable:**
- ✅ Readiness score calculation (0-100%) is quantifiable
- ✅ Score updates automatically (observable state change)
- ✅ Filtering by readiness (green/amber/red) is verifiable
- ✅ Scoring criteria is transparent (can verify logic)
- ✅ Specific prerequisites listed (account, partners, terms, dates, IPAS config, quote status)

**What's NOT Testable (Ambiguous):**
- ⚠️ "Scoring criteria is transparent (I understand why OPP-12346 is 87% vs. 100%)" — subjective; needs UX test
- ⚠️ "Score updates automatically when I fix gaps" — timing not specified (within 15 min mentioned in technical criteria, but not in business criteria)

**Test Coverage Required:**

**Tier 1: Unit Tests** (<1 sec)
- Scoring logic: `(met_prerequisites / total_prerequisites) × 100`
- Threshold classification: 90-100% → Green, 70-89% → Amber, <70% → Red
- Edge cases: Empty prerequisites, all met, all missing, partial
- Invalid input handling: Null opportunity, missing fields

**Tier 2: Integration Tests** (<5 sec, NO MOCKING)
- Real CEC OData query for opportunities with actual partner/term data
- Real IPAS query for config status
- Scoring based on real data (not mocked responses)
- Score persistence in real PostgreSQL database
- Dashboard API returns accurate scores from database

**Tier 3: End-to-End Tests** (<10 sec, NO MOCKING)
- Complete flow: CEC opportunity → IPAS config check → scoring → dashboard display
- State transition: Fix gap in CEC → observe score update within 15 min
- Multi-opportunity scenarios: Verify filtering by readiness
- Refresh workflow: On-demand trigger vs. 15-min schedule

**Missing Test Scenarios (NOT in acceptance criteria):**
1. **Concurrency:** What if two users update the same opportunity simultaneously?
2. **Stale data:** What if CEC data changes but IPAS data is cached?
3. **Partial failures:** What if CEC query succeeds but IPAS query fails?
4. **Large datasets:** What if 1000+ opportunities need scoring (performance degradation?)
5. **Invalid states:** What if opportunity stage is "Quote Approved" but account is null?

**Test Data Requirements:**
- Minimum 10 synthetic CEC opportunities with varying completeness:
  - 3 green (100% complete)
  - 4 amber (70-89% complete with 1-2 missing prerequisites)
  - 3 red (<70% complete with 3+ missing prerequisites)
- IPAS configurations: 5 "Complete", 3 "In Progress", 2 "Not Started"
- Partner data: Valid Sold-To, Ship-To, Bill-To for test customers
- Payment terms: Valid Z001, Z002, Z003 terms
- Dates: Valid requested dates (future dates, not past)

---

#### User Story 1.2: Gap Identification & Remediation Guidance

**Testability Score:** 70% (GOOD)

**What's Testable:**
- ✅ Checklist of prerequisites (observable output)
- ✅ Score updates automatically when gaps fixed (state change verification)
- ✅ Export gap reports (file output verification)

**What's NOT Testable (Ambiguous):**
- ⚠️ "Each gap shows a clear action" — subjective; needs content verification (is "Add Ship-To partner in CEC" clearer than "Partner missing"?)
- ⚠️ "I can delegate gap remediation tasks" — no specification of delegation mechanism (email? task assignment system?)

**Test Coverage Required:**

**Tier 1: Unit Tests** (<1 sec)
- Gap identification logic: Detect missing prerequisites
- Remediation guidance generation: Rule-based mapping (gap type → action + location + owner)
- Edge cases: No gaps, all gaps, partial gaps

**Tier 2: Integration Tests** (<5 sec, NO MOCKING)
- Real CEC query to detect missing partners/terms
- Real IPAS query to detect incomplete configs
- Gap list persisted to real PostgreSQL
- API returns structured gap data with remediation guidance

**Tier 3: End-to-End Tests** (<10 sec, NO MOCKING)
- Complete gap remediation flow: Identify gaps → fix in CEC → verify gap removed
- Export gap report: Generate PDF/JSON → verify contents
- Delegation workflow (if implemented): Assign gap → verify assignment

**Missing Test Scenarios:**
1. **Gap priority:** Which gaps should be fixed first? (No prioritization in requirements)
2. **Invalid remediation actions:** What if user follows action but gap persists? (e.g., adds Ship-To but still shows as missing)
3. **Permission errors:** What if user lacks permission to fix gap in CEC?
4. **Export format validation:** Is exported report human-readable? Machine-parsable?

**Test Data Requirements:**
- Same as User Story 1.1, plus:
  - Test cases for each gap type (missing account, missing Sold-To, missing Ship-To, missing Bill-To, missing payment terms, missing requested date, incomplete IPAS config, unapproved quote)
  - Valid remediation paths for each gap type

---

#### User Story 1.3: Automated Readiness Alerts

**Testability Score:** 80% (VERY GOOD)

**What's Testable:**
- ✅ Alert triggered on status transition (<90% → ≥90%)
- ✅ Alert content (opportunity ID, customer name, changes, next action)
- ✅ Alert delivery method (email, dashboard notification)
- ✅ Alert timing (within 15 minutes)
- ✅ Snooze/dismiss alerts

**What's NOT Testable (Ambiguous):**
- ⚠️ "I can configure alert preferences" — no specification of configuration options (frequency? channels?)

**Test Coverage Required:**

**Tier 1: Unit Tests** (<1 sec)
- Alert trigger logic: Detect state transition (previous score < 90%, current score ≥ 90%)
- Alert payload generation: Verify structure (opportunity ID, customer, changes, next action)
- Edge cases: Multiple transitions in short time, transition from 100% → 89% (should NOT alert)

**Tier 2: Integration Tests** (<5 sec, NO MOCKING)
- Real PostgreSQL query for previous vs. current scores
- Real email sending (SMTP) or dashboard notification (WebSocket/polling)
- Alert persistence in database (idempotent—no duplicate alerts)
- Scheduled execution (cron/timer-based agent run every 15 min)

**Tier 3: End-to-End Tests** (<10 sec, NO MOCKING)
- Complete alert flow: Fix gap → score transitions → alert sent → user receives alert
- On-demand trigger: Manual "Refresh" button → immediate alert check
- Snooze/dismiss: User dismisses alert → verify not shown again (or snoozed for 24h)
- Multi-channel delivery: Verify alert sent via email AND dashboard notification

**Missing Test Scenarios:**
1. **Alert flood prevention:** What if 50 opportunities become ready simultaneously? (Rate limiting?)
2. **Alert ordering:** If multiple alerts, which is shown first?
3. **Duplicate prevention:** If score transitions from 85% → 95% → 100% within 15 min, should user receive 1 alert or 2?
4. **Email delivery failures:** What if SMTP server is down? (Retry? Log error?)
5. **User notification preferences:** What if user is on vacation? (Auto-snooze?)

**Test Data Requirements:**
- Same as User Story 1.1, plus:
  - Test opportunities with transitions: Amber → Green (trigger alert), Red → Amber (no alert), Green → Amber (no alert)
  - Test email accounts for alert delivery verification
  - WebSocket/polling infrastructure for dashboard notification testing

---

### Epic 2: Sales Operations - Fast, Accurate Order Creation

#### User Story 2.1: One-Click Order Proposal Generation

**Testability Score:** 85% (VERY GOOD)

**What's Testable:**
- ✅ Proposal generation time (<5 seconds p95) — quantifiable performance metric
- ✅ Auto-fill accuracy (≥70% acceptance rate) — quantifiable KPI
- ✅ Field provenance (green/blue/yellow color coding) — observable output
- ✅ Editable fields — interaction verification
- ✅ Header + line items structure — data validation

**What's NOT Testable (Ambiguous):**
- ⚠️ "I can search for opportunities by ID, customer name, or quote number" — search quality not specified (exact match? fuzzy? substring?)

**Test Coverage Required:**

**Tier 1: Unit Tests** (<1 sec)
- Field mapping logic: CEC → `SalesOrderProposal`, IPAS → `SalesOrderItem[]`
- Provenance tagging: Each field tagged with source (CEC, IPAS, lookup, rule)
- Derivation rules: Ship-To location → Plant (rule R-042)
- Edge cases: Missing CEC data, missing IPAS BOM, empty fields

**Tier 2: Integration Tests** (<5 sec, NO MOCKING)
- Real CEC OData query for opportunity + account + partners + terms
- Real IPAS query for BOM (Config ID)
- Real field mapping registry query (versioned rules)
- Proposal assembly with real data (no mocked responses)
- API response time measurement (<5 sec p95)

**Tier 3: End-to-End Tests** (<10 sec, NO MOCKING)
- Complete proposal flow: Search opportunity → generate proposal → verify auto-fill accuracy
- Multi-line item scenarios: IPAS BOM with 10, 50, 100 line items (performance validation)
- Edit workflow: User edits 1-3 fields → verify changes persisted → validate edited proposal
- Provenance verification: Hover over field → verify tooltip shows source + timestamp

**Missing Test Scenarios:**
1. **Search edge cases:** What if multiple opportunities match search term? (Ordering? Pagination?)
2. **BOM size limits:** What if IPAS BOM has 500 line items? (Performance? UI rendering?)
3. **Conflicting data:** What if CEC shows Sold-To = CUST123 but IPAS shows CUST124? (Which wins?)
4. **Incomplete BOMs:** What if IPAS BOM has material MAT-001 but no quantity? (Error? Default?)
5. **Concurrent edits:** What if two users generate proposals for the same opportunity simultaneously?

**Test Data Requirements:**
- 10 synthetic CEC opportunities with complete data (account, partners, terms, dates)
- 10 IPAS configurations with BOMs:
  - 5 small BOMs (5-10 line items)
  - 3 medium BOMs (20-50 line items)
  - 2 large BOMs (100+ line items)
- SAP master data: Materials (MAT-001 to MAT-100), Plants (SG01, SG02, MY01), UoMs (EA, KG, M)
- Field mapping registry: 50+ CEC/IPAS → MS5 mappings
- Business rules: 10+ derivation rules (e.g., Ship-To → Plant, Incoterms + Location → Plant)

---

#### User Story 2.2: Pre-Post Validation & Error Prevention

**Testability Score:** 90% (EXCELLENT)

**What's Testable:**
- ✅ Validation time (<3 seconds p95) — quantifiable performance metric
- ✅ Validation checks (partners, materials, pricing, dates) — verifiable outcomes
- ✅ Error categorization (business vs. technical) — observable output
- ✅ Error details (field affected, fix guidance) — data validation
- ✅ Re-validation workflow — state transition verification

**What's NOT Testable (Ambiguous):**
- (None — this story is very well-defined for testing!)

**Test Coverage Required:**

**Tier 1: Unit Tests** (<1 sec)
- BAPI response parsing: Convert BAPI return codes to `ValidationIssue[]`
- Error categorization: BAPI code "E 001" → "Ship-To partner not found" (business error)
- Edge cases: Empty BAPI response, all errors, all warnings, success with warnings

**Tier 2: Integration Tests** (<5 sec, NO MOCKING)
- Real BAPI_SALESORDER_SIMULATE call to MS5 sandbox (via CPI)
- Real validation scenarios:
  - Valid proposal → BAPI success
  - Missing partner → BAPI error E 001
  - Insufficient material → BAPI warning W 010
  - Invalid date → BAPI error E 015
- Response time measurement (<3 sec p95)

**Tier 3: End-to-End Tests** (<10 sec, NO MOCKING)
- Complete validation flow: Generate proposal → validate → fix errors → re-validate → success
- Multi-error scenarios: Proposal with 3+ validation errors → verify all displayed
- Pricing validation: Proposal with valid materials → verify pricing determined
- Material availability: Proposal with unavailable material → verify stock warning

**Missing Test Scenarios:**
1. **BAPI timeout handling:** What if BAPI call takes >10 seconds? (Timeout? Retry?)
2. **Transient errors:** What if BAPI returns "System temporarily unavailable"? (User messaging?)
3. **Warning vs. error:** Can user proceed despite warnings? (Block or allow with confirmation?)
4. **Error field highlighting:** Are all affected fields highlighted in UI? (Multi-field errors?)
5. **Validation result caching:** If user re-validates without changes, is BAPI called again or cached?

**Test Data Requirements:**
- Same as User Story 2.1, plus:
- Test proposals for each validation error type:
  - Missing Sold-To partner (E 001)
  - Missing Ship-To partner (E 002)
  - Missing Bill-To partner (E 003)
  - Material not found (E 010)
  - Material unavailable (W 010)
  - Invalid requested date (E 015)
  - Pricing determination failure (E 020)
- MS5 sandbox with test master data (partners, materials, pricing conditions)

---

#### User Story 2.3: One-Click Approve & Post to SAP

**Testability Score:** 85% (VERY GOOD)

**What's Testable:**
- ✅ Posting time (<10 seconds p95) — quantifiable performance metric
- ✅ SAP order number (VBELN) returned — observable output
- ✅ Audit trail captured (correlation ID, CPI message ID, VBELN, user, timestamp) — data validation
- ✅ Retry logic (up to 3 times) — error handling verification
- ✅ Idempotent posting (same correlation ID → same VBELN) — state consistency

**What's NOT Testable (Ambiguous):**
- ⚠️ "If posting fails (rare), I see clear error message" — subjective; needs content validation

**Test Coverage Required:**

**Tier 1: Unit Tests** (<1 sec)
- IDoc payload assembly: `SalesOrderProposal` → ORDERS05 IDoc XML
- Correlation ID generation: Unique ID per proposal
- Idempotency check: Same correlation ID → return existing VBELN (no duplicate order)
- Edge cases: Missing required fields, null correlation ID

**Tier 2: Integration Tests** (<5 sec, NO MOCKING)
- Real IDoc ORDERS05 submission to MS5 sandbox (via CPI)
- Real CPI message ID returned (immediate)
- Real VBELN returned (after async processing—poll for result)
- Audit trail persisted to real PostgreSQL (correlation ID, CPI message ID, VBELN, user, timestamp)
- Response time measurement (<10 sec p95)

**Tier 3: End-to-End Tests** (<10 sec, NO MOCKING)
- Complete posting flow: Validate → approve → post → receive VBELN → verify in SAP
- Idempotency test: Post same proposal twice → verify same VBELN returned, no duplicate order
- Retry test: Simulate transient error → verify retry (up to 3 times)
- Audit trail verification: Query audit store → verify full linkage (correlation ID → CPI message ID → VBELN)

**Missing Test Scenarios:**
1. **Async VBELN retrieval:** If VBELN takes >10 seconds to return, what happens? (Polling? Webhook?)
2. **Posting failures after retry exhaustion:** If all 3 retries fail, how is user notified? (Error message? Email?)
3. **Concurrent posting:** What if two users post the same proposal simultaneously? (Race condition?)
4. **SAP order cancellation:** If order posted but user wants to cancel, is there a workflow?
5. **Partial success:** What if order posted to SAP but audit trail write fails? (Orphaned order?)

**Test Data Requirements:**
- Same as User Story 2.2, plus:
- Valid proposals that pass BAPI validation
- MS5 sandbox with IDoc processing enabled
- CPI sandbox with async VBELN return (webhook or polling endpoint)
- Test correlation IDs for idempotency testing

---

#### User Story 2.4: Field Provenance & Trust

**Testability Score:** 75% (GOOD)

**What's Testable:**
- ✅ Provenance data structure (source, source_type, rule_id, retrieved_at, confidence) — data validation
- ✅ Color coding (green/blue/yellow/red) — observable output
- ✅ Export provenance report (JSON/PDF) — file validation
- ✅ Auto-fill acceptance rate summary — quantifiable metric

**What's NOT Testable (Ambiguous):**
- ⚠️ "Hover over any field to see detailed tooltip" — UI interaction test (not API-level testable)
- ⚠️ "Provenance report is human-readable" — subjective; needs UX validation

**Test Coverage Required:**

**Tier 1: Unit Tests** (<1 sec)
- Provenance tagging logic: Each field tagged during proposal assembly
- Confidence calculation: COPY → HIGH, LOOKUP → MEDIUM, DERIVATION → MEDIUM, MANUAL → LOW
- Edge cases: Missing source, null rule_id, invalid source_type

**Tier 2: Integration Tests** (<5 sec, NO MOCKING)
- Real field mapping registry query for provenance tagging
- Real proposal assembly with provenance for all fields
- Provenance persisted to real PostgreSQL
- API returns full provenance report (header + items)

**Tier 3: End-to-End Tests** (<10 sec, NO MOCKING)
- Complete provenance flow: Generate proposal → verify provenance for all fields → export report
- Tooltip verification: Verify API returns provenance data for frontend tooltips
- Export validation: Generate PDF → verify contents (all fields, sources, confidence levels)

**Missing Test Scenarios:**
1. **Provenance for edited fields:** If user edits a field, is provenance updated to "MANUAL"?
2. **Provenance versioning:** If field mapping rules change, how is provenance updated?
3. **Provenance for derived fields:** If rule R-042 changes, are existing proposals re-tagged?
4. **Export format consistency:** Are JSON and PDF exports structurally consistent?

**Test Data Requirements:**
- Same as User Story 2.1, plus:
- Test proposals with all provenance types: COPY (green), LOOKUP (blue), DERIVATION (yellow), MANUAL (red)
- Field mapping registry with versioning
- Business rules with rule IDs (R-001 to R-050)

---

### Epic 3: Compliance - Policy Enforcement & Audit Trail

#### User Story 3.1: Automated Policy Checks Before Posting

**Testability Score:** 80% (VERY GOOD)

**What's Testable:**
- ✅ Policy catalog structure (policy ID, rule, conditions, required artefacts) — data validation
- ✅ Policy checks (Incoterms → artefacts, payment terms → approvals, partner roles → completeness) — verifiable logic
- ✅ Non-compliant orders blocked from posting — state transition verification
- ✅ Violation details (policy ID, what's violated, how to fix) — observable output
- ✅ Policy catalog versioning — data integrity

**What's NOT Testable (Ambiguous):**
- ⚠️ "I can view full policy catalog" — UI feature, not API-level testable (unless there's an API endpoint)

**Test Coverage Required:**

**Tier 1: Unit Tests** (<1 sec)
- Policy matching logic: Order data (Incoterms, payment terms, partners) → applicable policies
- Compliance evaluation: Check order against policy conditions → pass/fail
- Edge cases: No policies match, all policies pass, all policies fail, partial compliance

**Tier 2: Integration Tests** (<5 sec, NO MOCKING)
- Real policy catalog query from PostgreSQL (versioned rules)
- Real Due Diligence Agent workflow: Load policies → check order → return `DDSummary`
- Policy check persistence in real PostgreSQL (policy ID, result, timestamp)

**Tier 3: End-to-End Tests** (<10 sec, NO MOCKING)
- Complete policy enforcement flow: Generate proposal → policy check → violation found → order blocked → fix → re-check → pass
- Multi-policy scenarios: Order violates 3 policies → verify all violations displayed
- Policy versioning: Policy rule updated → verify new orders checked against new rule, old orders against old rule

**Missing Test Scenarios:**
1. **Policy conflicts:** What if two policies contradict each other? (e.g., POL-027 requires doc A, POL-028 forbids doc A)
2. **Policy exceptions:** Can authorized users override policy violations? (Approval workflow?)
3. **Policy audit trail:** Are policy check results logged with policy version used?
4. **Policy rule syntax errors:** What if policy rule has syntax error? (Fail-safe? Alert admin?)
5. **Policy updates mid-validation:** If policy updated while order is being validated, which version applies?

**Test Data Requirements:**
- Policy catalog with 20+ policies:
  - Incoterms-based policies (POL-001 to POL-010): DAP → FAT required, EXW → bank guarantee required
  - Payment terms policies (POL-011 to POL-020): Z001 allowed for customer type A, Z002 requires approval
  - Partner policies (POL-021 to POL-030): Sold-To/Ship-To/Bill-To required, Ship-To must have delivery address
- Test orders for each policy violation type
- Policy versioning: 3 versions of each policy (to test versioning logic)

---

#### User Story 3.2: Required Document Flagging & Just-In-Time Prompts

**Testability Score:** 85% (VERY GOOD)

**What's Testable:**
- ✅ Document requirements flagged (policy-driven) — observable output
- ✅ Document upload (file, hash, timestamp, user) — data validation
- ✅ Document status updated (NOT YET UPLOADED → PRESENT) — state transition
- ✅ Document hash verification (SHA-256) — integrity check
- ✅ Document linkage to order (correlation ID) — data integrity

**What's NOT Testable (Ambiguous):**
- ⚠️ "Upload link: [rrps://docs/FAT/OPP-12345]" — custom URI scheme; needs specification

**Test Coverage Required:**

**Tier 1: Unit Tests** (<1 sec)
- Document requirement extraction: Policy → required doc types (FAT, delivery proof, bank guarantee)
- Hash calculation: File content → SHA-256 hash
- Edge cases: Empty file, large file (>10MB), unsupported format

**Tier 2: Integration Tests** (<5 sec, NO MOCKING)
- Real document upload to MinIO (object storage)
- Real hash verification: Upload file → calculate hash → verify match
- Real document metadata stored in PostgreSQL (file name, hash, upload timestamp, user, correlation ID)
- Real ArchiveLink linkage (if applicable): Document → SAP VBELN

**Tier 3: End-to-End Tests** (<10 sec, NO MOCKING)
- Complete document flow: Order created → required docs flagged → upload FAT → status updated → verify linked to order
- Multi-document scenarios: Order requires 3 docs (FAT, delivery proof, bank guarantee) → upload all → verify all linked
- Hash integrity: Upload doc → retrieve doc → verify hash matches

**Missing Test Scenarios:**
1. **Document versioning:** If user uploads FAT_v1.pdf, then uploads FAT_v2.pdf, which is used? (Replace? Both?)
2. **Document access control:** Can any user view uploaded docs? (Permission-based?)
3. **Document retention:** How long are docs stored? (Compliance requirement?)
4. **Document deletion:** Can user delete uploaded doc? (Audit trail preserved?)
5. **Large file uploads:** What if file is 100MB? (Chunked upload? Timeout?)

**Test Data Requirements:**
- Test documents: FAT certificates (PDF, 1-5 MB), delivery proofs (PDF, <1 MB), bank guarantees (PDF, <1 MB)
- MinIO object storage (real or Docker-based)
- Test correlation IDs for document linkage
- Test user accounts for upload tracking

---

#### User Story 3.3: Immutable Audit Trail & Traceability

**Testability Score:** 90% (EXCELLENT)

**What's Testable:**
- ✅ Audit trail structure (correlation ID → CPI message ID → SAP VBELN) — data validation
- ✅ Immutability (cannot edit after capture) — database constraint verification
- ✅ Full linkage (opportunity → proposal → validation → posting → audit trail) — data integrity
- ✅ 100% traceability KPI — quantifiable metric
- ✅ Export audit trail (JSON, PDF) — file validation

**What's NOT Testable (Ambiguous):**
- (None — this story is very well-defined for testing!)

**Test Coverage Required:**

**Tier 1: Unit Tests** (<1 sec)
- Audit trail payload generation: All required fields (correlation ID, CPI message ID, VBELN, user, timestamp)
- Edge cases: Missing VBELN, null user, invalid timestamp

**Tier 2: Integration Tests** (<5 sec, NO MOCKING)
- Real audit trail write to PostgreSQL (append-only table)
- Real immutability check: Attempt UPDATE → verify rejected (append-only constraint)
- Real linkage verification: Query audit trail by correlation ID → verify full chain

**Tier 3: End-to-End Tests** (<10 sec, NO MOCKING)
- Complete traceability flow: Opportunity (CEC) → Proposal (agent) → Validation (BAPI) → Posting (IDoc) → Audit trail → Export
- Multi-order audit trail: 50 orders → verify 100% have complete audit trail (correlation ID → VBELN)
- Export validation: Generate PDF → verify all audit data present

**Missing Test Scenarios:**
1. **Audit trail query performance:** What if 10,000+ orders in audit trail? (Indexing? Query optimization?)
2. **Audit trail retention:** How long is audit trail kept? (Compliance requirement?)
3. **Audit trail export for auditors:** Can auditors export audit trail for date range? (Batch export?)
4. **Audit trail anonymization:** Are user emails stored or hashed? (Privacy?)
5. **Audit trail for failed orders:** If order posting fails, is audit trail still created?

**Test Data Requirements:**
- 50+ synthetic orders with complete audit trail (correlation ID → CPI message ID → VBELN)
- PostgreSQL with append-only audit table (immutability constraint)
- Test user accounts for audit tracking
- Export templates (PDF, JSON)

---

### Epic 4: Finance Operations - Billing Readiness

#### User Story 4.1: Billing Readiness Dashboard

**Testability Score:** 75% (GOOD)

**What's Testable:**
- ✅ Billing readiness calculation: `(met_prerequisites / total_prerequisites) × 100`
- ✅ Readiness status (ready/partial/blocked) — observable output
- ✅ Prerequisites checked (delivery, docs, Incoterms compliance) — verifiable logic
- ✅ Dashboard refresh (every 15 min or on-demand) — timing verification
- ✅ Filter by status (ready, blocked, date range) — query validation

**What's NOT Testable (Ambiguous):**
- ⚠️ "I can trigger invoice directly from dashboard" — interaction test, not acceptance criteria detail

**Test Coverage Required:**

**Tier 1: Unit Tests** (<1 sec)
- Billing readiness calculation: Delivery + docs + Incoterms → readiness %
- Threshold classification: 100% → Ready, 50-99% → Partial, <50% → Blocked
- Edge cases: No delivery, no docs, all prerequisites met

**Tier 2: Integration Tests** (<5 sec, NO MOCKING)
- Real MS5 query for delivery status (via CPI events or polling)
- Real Due Diligence Agent query for document status
- Real billing readiness persisted to PostgreSQL
- Dashboard API returns accurate readiness data

**Tier 3: End-to-End Tests** (<10 sec, NO MOCKING)
- Complete billing readiness flow: Order posted → delivery confirmed → docs uploaded → readiness updated → dashboard shows ready
- Multi-order scenarios: 10 orders with varying readiness → verify dashboard shows correct status
- Filtering: Filter by ready → verify only ready orders shown

**Missing Test Scenarios:**
1. **Delivery milestone detection:** How is delivery milestone detected? (CPI event? Manual update?)
2. **Missing delivery data:** What if delivery confirmed in SAP but event not received? (Polling fallback?)
3. **Document verification:** Are document hashes re-verified before billing? (Integrity check?)
4. **Stale readiness data:** If delivery confirmed but dashboard not refreshed, is data stale? (Cache invalidation?)
5. **Large order volumes:** What if 500+ orders need billing readiness checks? (Performance?)

**Test Data Requirements:**
- 20 synthetic orders with varying billing readiness:
  - 5 ready (delivery confirmed, all docs present)
  - 8 partial (delivery confirmed, some docs missing)
  - 7 blocked (no delivery or no docs)
- CPI event listener (real or Docker-based Kafka/RabbitMQ)
- Test delivery events (VBELN-XXX delivery confirmed)
- Test documents uploaded to MinIO

---

#### User Story 4.2: Event-Driven Invoice Triggers

**Testability Score:** 85% (VERY GOOD)

**What's Testable:**
- ✅ Alert triggered on delivery event — event-driven verification
- ✅ Prerequisites checked before alert — verifiable logic
- ✅ Invoice creation (<10 seconds) — quantifiable performance metric
- ✅ Control evidence captured (delivery timestamp, CPI message ID, doc hashes, user, timestamp) — data validation
- ✅ Invoice number returned — observable output

**What's NOT Testable (Ambiguous):**
- ⚠️ "I can review prerequisites" — UI feature, not acceptance criteria detail

**Test Coverage Required:**

**Tier 1: Unit Tests** (<1 sec)
- Event handler logic: Delivery event → check prerequisites → trigger alert
- Invoice payload generation: Order data → invoice creation request
- Edge cases: Missing delivery data, missing docs, invalid order number

**Tier 2: Integration Tests** (<5 sec, NO MOCKING)
- Real CPI event listener receives delivery event
- Real Financial Ops Agent checks prerequisites
- Real invoice creation API call to SAP (via CPI)
- Real control evidence written to PostgreSQL

**Tier 3: End-to-End Tests** (<10 sec, NO MOCKING)
- Complete invoice flow: Order posted → delivery confirmed (event) → prerequisites checked → alert sent → user triggers invoice → invoice created in SAP
- Control evidence verification: Query audit store → verify all control evidence captured
- Multi-invoice scenarios: 5 delivery events in short time → verify all invoices created

**Missing Test Scenarios:**
1. **Event ordering:** What if delivery event received before order posting event? (Out-of-order handling?)
2. **Duplicate events:** What if delivery event received twice? (Idempotency?)
3. **Event processing failures:** What if event listener crashes mid-processing? (Retry? Dead letter queue?)
4. **Invoice creation failures:** What if SAP invoice API fails? (Retry? User notification?)
5. **Control evidence for failed invoices:** If invoice creation fails, is control evidence still captured?

**Test Data Requirements:**
- Same as User Story 4.1, plus:
- Test CPI delivery events (JSON or XML payloads)
- SAP invoice creation sandbox API
- Test invoice numbers for verification

---

#### User Story 4.3: Control Evidence for A/R Audits

**Testability Score:** 90% (EXCELLENT)

**What's Testable:**
- ✅ Control evidence structure (delivery confirmation, docs, policy checks, invoice details) — data validation
- ✅ Immutability (cannot edit after capture) — database constraint verification
- ✅ Export formats (PDF, JSON) — file validation
- ✅ 100% traceability KPI — quantifiable metric

**What's NOT Testable (Ambiguous):**
- (None — this story is very well-defined for testing!)

**Test Coverage Required:**

**Tier 1: Unit Tests** (<1 sec)
- Control evidence payload generation: All required fields
- Edge cases: Missing delivery timestamp, null CPI message ID, no docs

**Tier 2: Integration Tests** (<5 sec, NO MOCKING)
- Real control evidence write to PostgreSQL (append-only table)
- Real immutability check: Attempt UPDATE → verify rejected
- Real linkage: Invoice → control evidence → delivery → docs → policy checks

**Tier 3: End-to-End Tests** (<10 sec, NO MOCKING)
- Complete control evidence flow: Invoice created → control evidence captured → export report → verify all data present
- Multi-invoice audit: 20 invoices → verify all have control evidence
- Export validation: PDF export → verify human-readable, JSON export → verify machine-parsable

**Missing Test Scenarios:**
1. **Control evidence retention:** How long is control evidence kept?
2. **Control evidence search:** Can auditors search by invoice number, order number, date range?
3. **Control evidence for partial invoices:** If order has multiple invoices, is control evidence linked correctly?
4. **Control evidence for credit memos:** If invoice corrected, is control evidence updated or new record created?

**Test Data Requirements:**
- Same as User Story 4.2, plus:
- Test invoices with complete control evidence
- Export templates (PDF, JSON)

---

### Epic 5: POV Success - Metrics & Decision Pack

#### User Story 5.1: Baseline Data Collection

**Testability Score:** 70% (GOOD)

**What's Testable:**
- ✅ Baseline metrics calculation (acceptance rate, cycle time, first-time-right, artefact readiness, traceability) — quantifiable metrics
- ✅ Data sources (CEC, IPAS, MS5, document repository) — verifiable queries
- ✅ Cohort selection (matching pilot order types) — data validation
- ✅ Export baseline report (PDF, JSON) — file validation

**What's NOT Testable (Ambiguous):**
- ⚠️ "Cohort: 50 orders (matching pilot order types)" — how is "matching" defined? (Same customer? Same product type? Same region?)

**Test Coverage Required:**

**Tier 1: Unit Tests** (<1 sec)
- Metrics calculation formulas: acceptance_rate, cycle_time, first_time_right, artefact_readiness, traceability
- Edge cases: No historical data, incomplete data, zero orders

**Tier 2: Integration Tests** (<5 sec, NO MOCKING)
- Real CEC query for historical opportunities (last 3 months)
- Real MS5 query for historical orders
- Real metrics calculation based on real data
- Metrics persisted to PostgreSQL

**Tier 3: End-to-End Tests** (<10 sec, NO MOCKING)
- Complete baseline collection flow: Define period → select cohort → calculate metrics → export report
- Cohort validation: Verify cohort matches pilot order types
- Export validation: PDF export → verify all metrics present

**Missing Test Scenarios:**
1. **Data quality:** What if historical data has gaps? (Incomplete orders, missing timestamps?)
2. **Cohort size:** What if fewer than 50 matching orders exist? (Accept smaller cohort? Expand date range?)
3. **Metrics recalculation:** If baseline period changes, are metrics recalculated?
4. **Historical data access:** What if CEC API doesn't support historical queries? (Manual data entry?)

**Test Data Requirements:**
- Historical CEC opportunities (last 3 months): 100+ opportunities
- Historical MS5 orders: 50+ orders matching pilot types
- Historical document uploads (if tracked)
- Historical rework events (if tracked in SAP)

---

#### User Story 5.2: Pilot Execution & Metrics Capture

**Testability Score:** 85% (VERY GOOD)

**What's Testable:**
- ✅ Pilot metrics auto-captured (no manual entry) — automation verification
- ✅ Identical metric definitions as baseline — formula consistency
- ✅ Dashboard shows baseline vs. pilot vs. target — observable output
- ✅ Status color-coded (green/amber/red) — classification logic
- ✅ Real-time dashboard refresh (every 5 min) — timing verification

**What's NOT Testable (Ambiguous):**
- ⚠️ "User feedback: Sales Ops: 'Order creation is 10x faster...'" — qualitative feedback, not testable (unless there's a feedback form)

**Test Coverage Required:**

**Tier 1: Unit Tests** (<1 sec)
- Metrics calculation (same formulas as baseline)
- Status classification: Green (at/above target), Amber (within 10%), Red (>10% gap)
- Edge cases: No pilot data, incomplete pilot data

**Tier 2: Integration Tests** (<5 sec, NO MOCKING)
- Real pilot metrics auto-captured from agent logs (Sales Ops Agent, Due Diligence Agent, Financial Ops Agent)
- Real metrics persisted to PostgreSQL
- Dashboard API returns baseline vs. pilot comparison

**Tier 3: End-to-End Tests** (<10 sec, NO MOCKING)
- Complete pilot metrics flow: Process pilot order → metrics auto-captured → dashboard updated → verify metrics
- Multi-order pilot: 25 pilot orders → verify metrics calculated correctly
- Dashboard refresh: Wait 5 min → verify dashboard auto-refreshed

**Missing Test Scenarios:**
1. **Metrics consistency:** Are pilot metrics calculated using same code as baseline? (Code reuse?)
2. **Metrics lag:** If order processed but metrics not yet updated, is there a lag indicator?
3. **User feedback capture:** How is qualitative feedback captured? (Form? Manual entry?)
4. **Metrics export during pilot:** Can user export mid-pilot metrics for stakeholder updates?

**Test Data Requirements:**
- 25 pilot orders (real CEC opportunities selected by Sales Ops)
- Pilot execution logs (Sales Ops Agent, Due Diligence Agent, Financial Ops Agent)
- Baseline metrics (from User Story 5.1) for comparison

---

#### User Story 5.3: Metrics Comparison & Scorecard

**Testability Score:** 90% (EXCELLENT)

**What's Testable:**
- ✅ Scorecard structure (baseline, pilot, target, status) — data validation
- ✅ Overall status calculation: Green (all KPIs green), Amber (1-2 amber), Red (any red or Traceability <100%)
- ✅ Recommendation logic: Green → Scale, Amber → Iterate, Red → Stop
- ✅ Business impact calculation (time saved, DSO reduction, compliance improvement) — quantifiable metrics
- ✅ Export scorecard (PDF) — file validation

**What's NOT Testable (Ambiguous):**
- (None — this story is very well-defined for testing!)

**Test Coverage Required:**

**Tier 1: Unit Tests** (<1 sec)
- Overall status calculation: KPI statuses → overall status
- Recommendation logic: Overall status + user feedback → recommendation
- Business impact calculation: Baseline vs. pilot → time saved, DSO reduction
- Edge cases: All green, all red, mixed, Traceability <100% (force Red)

**Tier 2: Integration Tests** (<5 sec, NO MOCKING)
- Real scorecard generation: Query baseline + pilot metrics → calculate status → generate recommendation
- Scorecard persisted to PostgreSQL
- API returns scorecard data

**Tier 3: End-to-End Tests** (<10 sec, NO MOCKING)
- Complete scorecard flow: Baseline collected → pilot executed → scorecard generated → export PDF
- Recommendation validation: Green overall → verify "SCALE" recommendation
- Export validation: PDF export → verify all sections (KPIs, status, recommendation, business impact)

**Missing Test Scenarios:**
1. **Scorecard versioning:** If pilot extended, is scorecard recalculated with updated data?
2. **Scorecard access control:** Who can view scorecard? (Executives only? All users?)
3. **Scorecard archival:** Are historical scorecards preserved? (POV 1, POV 2, etc.?)

**Test Data Requirements:**
- Baseline metrics (from User Story 5.1)
- Pilot metrics (from User Story 5.2)
- Target values for all KPIs
- Scorecard export template (PDF)

---

### Epic 6: User Validation - UAT & Pilot

#### User Story 6.1: UAT Scenario Definition & Guided Walkthroughs

**Testability Score:** 65% (MODERATE)

**What's Testable:**
- ✅ UAT scenario structure (objective, test data, steps, success criteria) — data validation
- ✅ Feedback capture (worked well, could be improved, would use in production) — observable output
- ✅ Issue tracking (bugs, usability problems) — data validation

**What's NOT Testable (Ambiguous):**
- ⚠️ "I receive guided UAT scenarios" — delivery mechanism not specified (email? dashboard? PDF?)
- ⚠️ "Step-by-step instructions" — instruction quality not quantifiable
- ⚠️ "Success criteria (measurable outcomes)" — some success criteria are subjective (e.g., "user feels confident")

**Test Coverage Required:**

**Tier 1: Unit Tests** (<1 sec)
- UAT scenario data structure validation
- Feedback payload validation
- Edge cases: Empty feedback, missing fields

**Tier 2: Integration Tests** (<5 sec, NO MOCKING)
- Real UAT scenario query from PostgreSQL or file system
- Real feedback submission to PostgreSQL
- Real issue tracking integration (Jira, GitLab Issues)

**Tier 3: End-to-End Tests** (<10 sec, NO MOCKING)
- Complete UAT flow: User receives scenario → completes steps → submits feedback → feedback captured
- Multi-scenario UAT: 5-10 scenarios per role → verify all feedback captured
- Issue tracking: Report bug → verify issue created in tracking system

**Missing Test Scenarios:**
1. **UAT scenario versioning:** If scenario updated, do users re-test?
2. **UAT scenario assignment:** How are scenarios assigned to users? (Role-based? Manual?)
3. **UAT progress tracking:** Can admin see which users completed which scenarios?
4. **UAT feedback aggregation:** How is feedback from 10+ users aggregated?
5. **UAT test data isolation:** Are UAT test data isolated from production data?

**Test Data Requirements:**
- 5-10 UAT scenarios per role (Sales Manager, Sales Ops, Finance Ops, Compliance)
- Synthetic test data (CEC opportunities, IPAS configs, MS5 orders)
- UAT environment (isolated from production)
- Test user accounts for UAT

---

#### User Story 6.2: Pilot Execution with Real Orders

**Testability Score:** 75% (GOOD)

**What's Testable:**
- ✅ Pilot order queue (real opportunities) — data validation
- ✅ Support infrastructure (hotline, email, daily standup) — process verification
- ✅ Progress tracking (orders completed, cycle time, acceptance rate) — quantifiable metrics
- ✅ Issue reporting and resolution status — data validation

**What's NOT Testable (Ambiguous):**
- ⚠️ "I have support available" — support quality not quantifiable
- ⚠️ "Daily standup: 9:00 AM SGT" — attendance and effectiveness not testable

**Test Coverage Required:**

**Tier 1: Unit Tests** (<1 sec)
- Pilot order selection logic
- Progress calculation: (orders_completed / total_orders) × 100
- Edge cases: No orders completed, all orders completed

**Tier 2: Integration Tests** (<5 sec, NO MOCKING)
- Real pilot order query from CEC
- Real progress tracking persisted to PostgreSQL
- Real issue tracking integration

**Tier 3: End-to-End Tests** (<10 sec, NO MOCKING)
- Complete pilot flow: Pilot cohort selected → orders processed → progress tracked → metrics calculated
- Multi-user pilot: 3 users process orders concurrently → verify progress aggregated correctly
- Issue resolution: Report issue → verify status updated → verify resolution

**Missing Test Scenarios:**
1. **Pilot order selection criteria:** How are pilot orders selected? (Random? Manual?)
2. **Pilot order reassignment:** If user on leave, can order be reassigned to another user?
3. **Pilot data contamination:** Are pilot orders clearly marked to avoid confusion with production orders?
4. **Pilot rollback:** If pilot fails, can orders be rolled back?

**Test Data Requirements:**
- 25-50 real CEC opportunities (pilot cohort)
- Real IPAS configurations for pilot orders
- Real MS5 sandbox for order posting
- Test user accounts for pilot execution
- Support infrastructure (issue tracking, hotline)

---

#### User Story 6.3: Feedback Incorporation & Iteration

**Testability Score:** 70% (GOOD)

**What's Testable:**
- ✅ Feedback aggregation (positive, improvement, bug) — data validation
- ✅ Prioritization by frequency — quantifiable ranking
- ✅ Status tracking (implemented, in progress, deferred) — state management
- ✅ Critical bugs fixed before go-live — verification checklist

**What's NOT Testable (Ambiguous):**
- ⚠️ "Top improvements prioritized" — prioritization criteria not specified
- ⚠️ "I can see status of each feedback item" — UI feature, not API-level testable

**Test Coverage Required:**

**Tier 1: Unit Tests** (<1 sec)
- Feedback categorization logic: Text → positive/improvement/bug
- Prioritization logic: Frequency-based ranking
- Edge cases: No feedback, all positive, all bugs

**Tier 2: Integration Tests** (<5 sec, NO MOCKING)
- Real feedback aggregation from PostgreSQL (UAT + pilot feedback)
- Real status tracking in PostgreSQL or issue tracking system
- Real feedback query API

**Tier 3: End-to-End Tests** (<10 sec, NO MOCKING)
- Complete feedback flow: Feedback submitted → aggregated → prioritized → status tracked → improvements implemented → re-tested
- Multi-feedback scenarios: 42 feedback items → verify top 3-5 prioritized
- Status verification: Check implemented improvements → verify status "implemented"

**Missing Test Scenarios:**
1. **Feedback approval:** Who approves which improvements to implement?
2. **Feedback rejection:** Can feedback be rejected? (With reason?)
3. **Feedback duplicates:** How are duplicate feedback items merged?
4. **Feedback follow-up:** Are users notified when their feedback is implemented?

**Test Data Requirements:**
- 42 synthetic feedback items (28 positive, 10 improvement, 4 bugs)
- Issue tracking system for status management
- Test improvements to implement during pilot

---

## 2. Test Coverage Summary

### Test Coverage by Tier

| Epic | User Story | Tier 1 (Unit) | Tier 2 (Integration) | Tier 3 (E2E) | Coverage Gap |
|------|------------|---------------|----------------------|--------------|--------------|
| 1.1 | Opportunity Readiness Scoring | High | Medium | Medium | Missing concurrency, stale data, large dataset tests |
| 1.2 | Gap Identification | High | Medium | Low | Missing gap priority, invalid remediation, export format tests |
| 1.3 | Automated Alerts | High | High | Medium | Missing alert flood, duplicate prevention tests |
| 2.1 | Order Proposal Generation | High | High | High | Missing BOM size limits, conflicting data tests |
| 2.2 | Pre-Post Validation | High | High | High | Missing BAPI timeout, warning vs. error tests |
| 2.3 | Approve & Post to SAP | High | High | High | Missing async VBELN retrieval, partial success tests |
| 2.4 | Field Provenance | High | Medium | Low | Missing provenance versioning, edited field tests |
| 3.1 | Policy Checks | High | High | High | Missing policy conflicts, exceptions, audit trail tests |
| 3.2 | Document Flagging | High | High | High | Missing document versioning, access control tests |
| 3.3 | Audit Trail | High | High | High | Missing query performance, retention tests |
| 4.1 | Billing Readiness | High | Medium | Medium | Missing delivery detection, stale data tests |
| 4.2 | Invoice Triggers | High | High | High | Missing event ordering, duplicate events tests |
| 4.3 | Control Evidence | High | High | High | Missing retention, partial invoice tests |
| 5.1 | Baseline Collection | High | Medium | Low | Missing data quality, cohort size tests |
| 5.2 | Pilot Metrics Capture | High | High | Medium | Missing metrics consistency, lag indicator tests |
| 5.3 | Scorecard Generation | High | High | High | Missing scorecard versioning, access control tests |
| 6.1 | UAT Scenarios | Medium | Medium | Low | Missing scenario versioning, progress tracking tests |
| 6.2 | Pilot Execution | High | Medium | Medium | Missing order selection, reassignment tests |
| 6.3 | Feedback Incorporation | Medium | Medium | Low | Missing approval, duplicates, follow-up tests |

**Overall Coverage:**
- **Tier 1 (Unit):** 90% coverage (excellent)
- **Tier 2 (Integration):** 75% coverage (good)
- **Tier 3 (E2E):** 60% coverage (moderate)

**Coverage Gaps:** E2E tests underspecified; many user stories lack complete end-to-end scenarios.

---

## 3. Test Infrastructure Requirements (NO MOCKING for Tiers 2-3)

### External Systems (Real Infrastructure Required)

**SAP Landscape (via CPI Sandbox):**
- **CEC OData API:** Authentication, opportunity queries, partner queries, term queries
- **IPAS Client API:** Configuration queries, BOM retrieval
- **MS5 BAPI API:** BAPI_SALESORDER_SIMULATE (validation)
- **MS5 IDoc API:** ORDERS05 (order creation)
- **MS5 Invoice API:** Invoice creation
- **ArchiveLink API:** Document attachment to VBELN

**Critical:** All SAP integrations must use **real CPI sandbox** (NO MOCKING). Mock responses hide integration failures (field mapping errors, authentication issues, timeout handling).

**CPI Event Listener:**
- Real Kafka or RabbitMQ broker for delivery milestone events
- Event schema validation (JSON or XML)
- Idempotency and retry testing

### Internal Services (Dockerized for Tests)

**PostgreSQL:**
- Schema: `transactions`, `events`, `field_provenance`, `policy_checks`, `documents`, `control_evidence`, `baseline_metrics`, `pilot_metrics`
- Constraints: Append-only audit tables (immutability)
- Test data seeding scripts

**MinIO (Object Storage):**
- Document upload/download
- Hash verification (SHA-256)
- Access control testing

**Redis (Optional):**
- Session management
- Cache invalidation testing
- Distributed locks (for concurrent operations)

**Elasticsearch (Optional):**
- Full-text search for opportunities, orders, documents
- Query performance testing

### Test Environment Setup

**Docker Compose Stack:**
```yaml
services:
  postgres:
    image: postgres:15
    environment:
      POSTGRES_DB: test_db
      POSTGRES_USER: test
      POSTGRES_PASSWORD: test
    ports:
      - "5433:5432"

  minio:
    image: minio/minio
    command: server /data
    environment:
      MINIO_ROOT_USER: testuser
      MINIO_ROOT_PASSWORD: testpass
    ports:
      - "9001:9000"

  redis:
    image: redis:7
    ports:
      - "6380:6379"

  kafka:
    image: confluentinc/cp-kafka:7.5.0
    environment:
      KAFKA_ZOOKEEPER_CONNECT: zookeeper:2181
      KAFKA_ADVERTISED_LISTENERS: PLAINTEXT://localhost:9092
    ports:
      - "9092:9092"
```

**Test Utility Scripts:**
- `tests/utils/test-env up` → Start all services
- `tests/utils/test-env down` → Stop all services
- `tests/utils/test-env status` → Check service health
- `tests/utils/test-env seed` → Load test data (CEC opportunities, IPAS configs, SAP master data)

### Test Data Requirements

**CEC Synthetic Data:**
- 100+ opportunities with varying completeness (green, amber, red)
- 50+ accounts with Sold-To, Ship-To, Bill-To partners
- 20+ payment terms (Z001, Z002, Z003, etc.)
- 10+ sales orgs, distribution channels, divisions

**IPAS Synthetic Data:**
- 50+ configurations with BOMs (5-100 line items)
- Config statuses: Complete, In Progress, Not Started
- Material master data: MAT-001 to MAT-100

**SAP Master Data (in MS5 Sandbox):**
- Partners: CUST123, CUST124, CUST125 with Sold-To/Ship-To/Bill-To roles
- Materials: MAT-001 to MAT-100 with stock levels
- Plants: SG01, SG02, MY01 with delivery addresses
- Pricing conditions for test materials

**Policy Catalog Data:**
- 20+ policies (Incoterms → artefacts, payment terms → approvals, partner roles)
- Policy versions (3 versions per policy for versioning tests)

**Document Test Files:**
- FAT certificates (PDF, 1-5 MB): 10 files
- Delivery proofs (PDF, <1 MB): 10 files
- Bank guarantees (PDF, <1 MB): 5 files

---

## 4. Data Requirements & Generation Needs

### Data Generation Strategy

**Approach:** Synthetic data generation with realistic constraints (no PII, compliance-friendly).

**Tools:**
- **Faker:** Generate realistic customer names, addresses, emails
- **Custom generators:** CEC opportunities, IPAS BOMs, SAP master data
- **Database seeding:** SQL scripts to populate PostgreSQL with test data

**Data Consistency:**
- **Referential integrity:** Opportunities reference valid accounts, accounts reference valid partners
- **State consistency:** Opportunity stage "Quote Approved" implies quote exists
- **Temporal consistency:** Requested dates in future, order posted after proposal created

**Data Volume:**
- **Small datasets (unit tests):** 10-50 records
- **Medium datasets (integration tests):** 50-500 records
- **Large datasets (performance tests):** 1000+ records

### Test Data Lifecycle

**Setup (Before Test):**
1. Start Docker services (`test-env up`)
2. Seed database with synthetic data (`test-env seed`)
3. Verify CPI sandbox connectivity
4. Verify MinIO object storage ready

**Execution (During Test):**
1. Read test data from database or file
2. Execute workflow with real infrastructure (NO MOCKING)
3. Capture results (outputs, logs, metrics)

**Teardown (After Test):**
1. Clean up test data (truncate tables, delete files)
2. Verify no test data leaked to production
3. Stop Docker services (optional—keep running for speed)

**Data Isolation:**
- **UAT environment:** Separate database, separate CPI tenant, separate MinIO bucket
- **Pilot environment:** Separate database (shared CPI tenant with tagging)
- **Production environment:** NEVER use test data

---

## 5. Test Complexity Analysis

### Most Challenging Stories to Test

#### 1. User Story 2.3: One-Click Approve & Post to SAP (HIGH COMPLEXITY)

**Why Complex:**
- **Async VBELN retrieval:** IDoc submission returns CPI message ID immediately, but VBELN available only after async processing (polling or webhook required)
- **Idempotency:** Same correlation ID must return same VBELN (requires persistent state in CPI sandbox)
- **Retry logic:** Transient errors must retry up to 3 times with exponential backoff (requires simulating CPI failures)
- **Audit trail linkage:** Correlation ID → CPI message ID → VBELN must be verified across systems

**Test Approach:**
- Mock CPI async behavior in Tier 1 (unit tests)
- Use real CPI sandbox in Tier 2/3 (integration/E2E tests)
- Simulate transient errors with CPI sandbox chaos engineering (random failures)
- Verify audit trail linkage with database queries (correlation ID → VBELN)

**Estimated Test Time:** 2-3 days (including CPI sandbox setup)

---

#### 2. User Story 4.2: Event-Driven Invoice Triggers (HIGH COMPLEXITY)

**Why Complex:**
- **Event-driven architecture:** Requires real Kafka/RabbitMQ broker for CPI delivery events
- **Event ordering:** Delivery event may arrive before order posting event (out-of-order handling)
- **Event idempotency:** Duplicate delivery events must not trigger duplicate invoices
- **Event processing failures:** Event listener crash mid-processing requires dead letter queue

**Test Approach:**
- Use real Kafka/RabbitMQ in Tier 2/3 (Docker-based)
- Simulate out-of-order events with manual event publishing
- Simulate duplicate events with event replay
- Simulate event listener crash with container kill (`docker kill`)

**Estimated Test Time:** 2-3 days (including Kafka setup and chaos engineering)

---

#### 3. User Story 3.1: Automated Policy Checks (MEDIUM-HIGH COMPLEXITY)

**Why Complex:**
- **Policy rule versioning:** Policies may change over time; orders checked against policy version at time of creation
- **Policy conflicts:** Two policies may contradict each other (requires conflict resolution logic)
- **Policy exceptions:** Authorized users may override policy violations (requires approval workflow)

**Test Approach:**
- Store policies with version numbers in PostgreSQL
- Test policy versioning: Create order with policy v1, update policy to v2, create another order, verify both orders checked against correct version
- Test policy conflicts: Define conflicting policies, verify error or resolution logic
- Test policy exceptions (if implemented): Authorized user overrides violation, verify override captured in audit trail

**Estimated Test Time:** 1.5-2 days (including policy versioning tests)

---

#### 4. User Story 5.2: Pilot Execution & Metrics Capture (MEDIUM COMPLEXITY)

**Why Complex:**
- **Real-time metrics calculation:** Metrics calculated from live agent logs (requires log aggregation)
- **Metrics consistency:** Pilot metrics must use identical formulas as baseline metrics (code reuse verification)
- **Dashboard refresh timing:** Dashboard refreshes every 5 min (requires timing tests with sleep)

**Test Approach:**
- Capture agent logs in real PostgreSQL (all agents write logs to database)
- Verify metrics calculation code shared between baseline and pilot (unit test code reuse)
- Test dashboard refresh: Process order, wait 5 min, verify dashboard auto-refreshed

**Estimated Test Time:** 1.5 days (including log aggregation setup)

---

### Least Complex Stories to Test

#### 1. User Story 1.1: Opportunity Readiness Scoring (LOW-MEDIUM COMPLEXITY)

**Why Simple:**
- Deterministic scoring logic: `(met / total) × 100`
- Clear prerequisites (6 checks: account, partners, terms, date, IPAS config, quote)
- No async operations, no event-driven logic

**Test Approach:**
- Unit tests: Scoring logic with varied inputs (all met, all missing, partial)
- Integration tests: Real CEC/IPAS queries, verify score accuracy
- E2E tests: Fix gap, verify score update

**Estimated Test Time:** 0.5 days

---

#### 2. User Story 2.4: Field Provenance & Trust (LOW-MEDIUM COMPLEXITY)

**Why Simple:**
- Static provenance tagging during proposal assembly (no dynamic updates)
- Export as JSON/PDF (straightforward file generation)

**Test Approach:**
- Unit tests: Provenance tagging logic
- Integration tests: Verify provenance persisted to database
- E2E tests: Export report, verify contents

**Estimated Test Time:** 0.5 days

---

#### 3. User Story 5.3: Metrics Comparison & Scorecard (LOW-MEDIUM COMPLEXITY)

**Why Simple:**
- Deterministic scorecard logic: Baseline vs. pilot vs. target → status → recommendation
- No external system dependencies (all data in PostgreSQL)

**Test Approach:**
- Unit tests: Scorecard calculation with varied metrics (all green, all red, mixed)
- Integration tests: Query baseline + pilot metrics, generate scorecard
- E2E tests: Export PDF, verify contents

**Estimated Test Time:** 0.5 days

---

## 6. Missing Test Scenarios (Not in Acceptance Criteria)

### Cross-Cutting Scenarios

**Security:**
- [ ] **Authentication:** Can unauthenticated users access APIs? (401 Unauthorized expected)
- [ ] **Authorization:** Can Sales Ops user access Finance Ops endpoints? (403 Forbidden expected)
- [ ] **Input validation:** Are malicious inputs sanitized? (SQL injection, XSS prevention)
- [ ] **Rate limiting:** Can user flood API with 1000 requests/sec? (Rate limit enforcement)

**Performance:**
- [ ] **Load testing:** Can system handle 100 concurrent users?
- [ ] **Large datasets:** Can system handle 10,000+ opportunities? (Query optimization)
- [ ] **API response times:** Are all APIs <5 sec p95? (Performance benchmarks missing)

**Error Handling:**
- [ ] **Network failures:** What if CEC API unreachable? (User-friendly error message?)
- [ ] **Partial failures:** What if CEC query succeeds but IPAS query fails? (Degrade gracefully?)
- [ ] **Data corruption:** What if database contains null values in required fields? (Validation?)

**Concurrency:**
- [ ] **Concurrent updates:** What if two users update the same opportunity simultaneously? (Optimistic locking?)
- [ ] **Race conditions:** What if two users post the same order simultaneously? (Idempotency?)

**Data Integrity:**
- [ ] **Referential integrity:** What if opportunity references non-existent account? (Foreign key constraint?)
- [ ] **State consistency:** What if order posted but audit trail write fails? (Transaction rollback?)

**Compliance:**
- [ ] **Data retention:** How long is audit trail kept? (Compliance requirement?)
- [ ] **Data anonymization:** Are user emails stored or hashed? (Privacy?)
- [ ] **Audit trail immutability:** Can admin edit audit trail? (Append-only enforcement?)

---

### Epic-Specific Scenarios

**Epic 1 (Opportunity Readiness):**
- [ ] **Stale data:** What if CEC data cached but outdated? (Cache invalidation?)
- [ ] **Large opportunity volumes:** What if 1000+ opportunities need scoring? (Pagination?)
- [ ] **Partial CEC data:** What if opportunity missing payment terms? (Default value? Error?)

**Epic 2 (Order Creation):**
- [ ] **BOM size limits:** What if IPAS BOM has 500 line items? (UI rendering? Performance?)
- [ ] **Conflicting data:** What if CEC shows Sold-To = CUST123 but IPAS shows CUST124? (Conflict resolution?)
- [ ] **BAPI timeout:** What if BAPI call takes >10 seconds? (Timeout? Retry?)
- [ ] **Async VBELN retrieval:** If VBELN takes >10 seconds to return, what happens? (Polling? Webhook?)

**Epic 3 (Compliance):**
- [ ] **Policy conflicts:** What if two policies contradict each other? (Error? Manual resolution?)
- [ ] **Policy exceptions:** Can authorized users override policy violations? (Approval workflow?)
- [ ] **Document versioning:** If user uploads FAT_v1.pdf, then FAT_v2.pdf, which is used? (Replace? Both?)

**Epic 4 (Billing Readiness):**
- [ ] **Delivery milestone detection:** How is delivery milestone detected? (CPI event? Polling?)
- [ ] **Missing delivery data:** What if delivery confirmed in SAP but event not received? (Polling fallback?)
- [ ] **Event ordering:** What if delivery event received before order posting event? (Out-of-order handling?)

**Epic 5 (Metrics):**
- [ ] **Data quality:** What if historical data has gaps? (Incomplete orders, missing timestamps?)
- [ ] **Cohort size:** What if fewer than 50 matching orders exist? (Accept smaller cohort? Expand date range?)
- [ ] **Metrics lag:** If order processed but metrics not yet updated, is there a lag indicator?

**Epic 6 (UAT/Pilot):**
- [ ] **UAT scenario versioning:** If scenario updated, do users re-test?
- [ ] **UAT test data isolation:** Are UAT test data isolated from production data?
- [ ] **Pilot order selection criteria:** How are pilot orders selected? (Random? Manual?)
- [ ] **Pilot data contamination:** Are pilot orders clearly marked to avoid confusion with production orders?

---

## 7. Recommendations for Improving Testability

### 1. Expand Acceptance Criteria with Explicit Test Scenarios

**Current Issue:** Acceptance criteria often describe "what" (e.g., "I can see a readiness score") but not "how to verify" (e.g., "Score = 87% when 6 of 7 prerequisites met").

**Recommendation:**
For each acceptance criterion, add:
- **Given:** Initial state (e.g., "Given opportunity OPP-12345 has 6 of 7 prerequisites met")
- **When:** Action (e.g., "When I query the readiness API")
- **Then:** Expected outcome (e.g., "Then readiness score = 85.7% (6/7 × 100)")

**Example (User Story 1.1):**
```
Business Acceptance Criteria:
- [ ] I can see a readiness score (0-100%) for each opportunity in stages "Quote Approved" or later

↓ EXPAND TO ↓

Business Acceptance Criteria:
- [ ] **Given** opportunity OPP-12345 has 6 of 7 prerequisites met (missing Ship-To partner)
      **When** I query GET /opportunities/OPP-12345/readiness
      **Then** response contains {"score": 85.7, "status": "AMBER"}
- [ ] **Given** opportunity OPP-12346 has all 7 prerequisites met
      **When** I query GET /opportunities/OPP-12346/readiness
      **Then** response contains {"score": 100, "status": "GREEN"}
```

**Impact:** Transforms subjective criteria into testable specifications.

---

### 2. Quantify Subjective Criteria

**Current Issue:** Criteria like "clear error message" or "user-friendly" are not testable.

**Recommendation:**
Replace subjective terms with quantifiable metrics:
- "Clear error message" → "Error message includes: field affected, what's wrong, how to fix it"
- "User-friendly" → "90% of UAT users rate UI as 'easy to use' (survey)"
- "Fast" → "Response time <5 seconds p95"

**Example (User Story 2.2):**
```
Business Acceptance Criteria:
- [ ] Each error shows: What's wrong, which field is affected, how to fix it

↓ EXPAND TO ↓

- [ ] **Given** validation error "Ship-To partner not found"
      **When** I view the error details
      **Then** error message contains:
        - **Field:** header.shipTo
        - **What's wrong:** "Ship-To partner CUST123-SH not found in SAP"
        - **How to fix:** "Verify Ship-To partner in CEC or use alternative"
```

**Impact:** Enables objective pass/fail verification.

---

### 3. Add Performance Benchmarks for All Timed Operations

**Current Issue:** Many operations are described as "fast" or "immediate" without explicit timing.

**Recommendation:**
Add explicit timing for all operations:
- Proposal generation: <5 seconds p95
- Validation: <3 seconds p95
- Order posting: <10 seconds p95
- Dashboard refresh: <2 seconds p95
- Alert delivery: Within 15 minutes

**Example (User Story 2.1):**
```
Business Acceptance Criteria:
- [ ] Proposal generates quickly

↓ REPLACE WITH ↓

- [ ] Proposal generation completes in <5 seconds p95 (measured from API request to response)
- [ ] For large BOMs (100+ line items), proposal generation completes in <10 seconds p95
```

**Impact:** Enables performance regression testing.

---

### 4. Specify Error Handling for All External Dependencies

**Current Issue:** Error handling for CEC, IPAS, MS5, CPI failures is underspecified.

**Recommendation:**
For each external dependency, specify:
- **Happy path:** External system responds successfully
- **Timeout:** External system takes >X seconds
- **Network error:** External system unreachable
- **Business error:** External system returns error (e.g., partner not found)
- **Partial failure:** External system returns partial data

**Example (User Story 2.1):**
```
Technical Acceptance Criteria:
- [ ] Sales Ops Agent calls CEC OData API to retrieve opportunity data

↓ EXPAND TO ↓

- [ ] **Happy path:** CEC API returns opportunity data within 2 seconds → proposal generated
- [ ] **Timeout:** CEC API takes >5 seconds → return error "CEC API timeout, please retry"
- [ ] **Network error:** CEC API unreachable → return error "CEC API unavailable, contact support"
- [ ] **Business error:** CEC API returns 404 (opportunity not found) → return error "Opportunity OPP-12345 not found in CEC"
- [ ] **Partial data:** CEC API returns opportunity but missing partners → flag missing data, continue with partial proposal
```

**Impact:** Ensures robust error handling and clear user messaging.

---

### 5. Add Test Data Requirements Per User Story

**Current Issue:** Test data requirements are implicit (not specified in user stories).

**Recommendation:**
For each user story, add section:
```
#### Test Data Requirements
- **CEC:** 10 opportunities (3 green, 4 amber, 3 red)
- **IPAS:** 10 configurations (5 complete, 3 in progress, 2 not started)
- **SAP:** 5 test customers with Sold-To/Ship-To/Bill-To partners
- **Documents:** 5 FAT certificates (PDF, 1-5 MB)
```

**Impact:** Simplifies test setup and ensures consistent test data across teams.

---

### 6. Add Concurrency and Race Condition Tests

**Current Issue:** Concurrent user scenarios not covered.

**Recommendation:**
For stories with state changes (e.g., order posting, gap fixing), add:
```
#### Concurrency Test Scenarios
- [ ] **Given** two users generate proposals for the same opportunity simultaneously
      **When** both users post the order
      **Then** only one order created (idempotent posting via correlation ID)
- [ ] **Given** User A fixes gap (adds Ship-To) while User B views readiness score
      **When** User A commits change and User B refreshes
      **Then** User B sees updated score within 15 minutes
```

**Impact:** Prevents race conditions and ensures data consistency.

---

### 7. Add Data Integrity and Audit Trail Tests

**Current Issue:** Audit trail immutability and data integrity tests underspecified.

**Recommendation:**
For Epic 3 and Epic 4, add:
```
#### Data Integrity Test Scenarios
- [ ] **Given** audit trail entry exists for order VBELN-8000123456
      **When** admin attempts UPDATE audit_trail SET vbeln = '9999999999'
      **Then** database rejects update (append-only constraint enforced)
- [ ] **Given** order posted but audit trail write fails (database unavailable)
      **When** system recovers
      **Then** audit trail write retried OR order posting rolled back (transaction consistency)
```

**Impact:** Ensures compliance and audit readiness.

---

### 8. Add Load and Stress Tests for Pilot Scale

**Current Issue:** No load testing scenarios for 100+ concurrent users or 1000+ opportunities.

**Recommendation:**
For Epic 6 (Pilot), add:
```
#### Load Test Scenarios
- [ ] **Given** 100 users simultaneously create order proposals
      **When** all users submit proposals within 1 minute
      **Then** all proposals generated within <10 seconds each (no degradation)
- [ ] **Given** 1000 opportunities need readiness scoring
      **When** scoring job runs
      **Then** all 1000 opportunities scored within <5 minutes (pagination + parallel processing)
```

**Impact:** Validates system readiness for production scale.

---

### 9. Add UAT and Pilot Test Data Isolation

**Current Issue:** UAT and pilot test data isolation not specified.

**Recommendation:**
For Epic 6, add:
```
#### Test Data Isolation
- [ ] UAT environment uses separate PostgreSQL database (uat_db)
- [ ] UAT environment uses separate CPI tenant (uat.cpi.domain.com)
- [ ] UAT test data tagged with `environment: 'UAT'` (prevent production contamination)
- [ ] Pilot orders tagged with `pilot_cohort: true` (clearly marked for visibility)
```

**Impact:** Prevents production data contamination and compliance violations.

---

### 10. Add Regression Test Suite for Each Sprint

**Current Issue:** No regression test strategy specified.

**Recommendation:**
Add:
```
#### Regression Test Strategy
- [ ] **Tier 1 (Unit):** Run on every commit (CI pipeline, <1 min)
- [ ] **Tier 2 (Integration):** Run nightly (Docker services up, <10 min)
- [ ] **Tier 3 (E2E):** Run weekly (full UAT scenarios, <1 hour)
- [ ] **Load Tests:** Run before pilot (100 concurrent users, <30 min)
```

**Impact:** Catches regressions early and ensures continuous quality.

---

## 8. Final Recommendations Summary

### Immediate Actions (Before Development Starts)

1. **Expand acceptance criteria** with Given/When/Then test scenarios (BDD format)
2. **Quantify subjective criteria** ("clear" → "includes field, issue, fix")
3. **Add performance benchmarks** for all timed operations (<5 sec, <10 sec)
4. **Specify error handling** for all external dependencies (CEC, IPAS, MS5, CPI)
5. **Document test data requirements** per user story (CEC, IPAS, SAP, documents)

### Before Integration Testing (Tier 2)

6. **Set up test infrastructure**:
   - Docker Compose stack (PostgreSQL, MinIO, Redis, Kafka)
   - CPI sandbox connectivity (CEC, IPAS, MS5, ArchiveLink)
   - Test data seeding scripts

7. **Verify NO MOCKING policy**:
   - All Tier 2/3 tests use real CPI sandbox (NO MOCKED responses)
   - All Tier 2/3 tests use real Docker services (PostgreSQL, MinIO, Kafka)

### Before End-to-End Testing (Tier 3)

8. **Add missing test scenarios**:
   - Concurrency and race conditions
   - Error handling (timeouts, network errors, partial failures)
   - Load and stress tests (100 users, 1000+ opportunities)
   - Data integrity and audit trail immutability

9. **Add UAT/Pilot test data isolation**:
   - Separate environments (UAT, Pilot, Production)
   - Test data tagging (environment, pilot_cohort)

### Before Pilot Execution (Epic 6)

10. **Execute regression test suite**:
    - Tier 1 (Unit): <1 min on CI
    - Tier 2 (Integration): <10 min nightly
    - Tier 3 (E2E): <1 hour weekly
    - Load tests: <30 min before pilot

---

## Conclusion

The RRPS Lead-to-Cash POV requirements (v3.0) are **moderately testable (60-70%)** with significant room for improvement. The business acceptance criteria are well-written from a user perspective, but lack the specificity required for rigorous testing.

**Key Strengths:**
- Quantifiable KPIs (≥70% acceptance rate, <5 sec response time)
- Clear business value per story
- Technical acceptance criteria separate from business criteria

**Key Weaknesses:**
- Subjective criteria ("clear error message", "user-friendly") not quantified
- Error handling underspecified (timeouts, network errors, partial failures)
- Concurrency and race conditions not covered
- Load and stress test scenarios missing
- Test data requirements implicit (not documented per story)

**Recommendation:**
Before development starts, expand acceptance criteria with explicit test scenarios (Given/When/Then), quantify subjective criteria, add performance benchmarks, and document test data requirements per user story. This will increase testability to **85-90%** and enable rigorous 3-tier testing with NO MOCKING in Tiers 2-3.

---

**Next Steps:**
1. Review this analysis with requirements analyst and product owner
2. Update requirements-breakdown-v3-value-chain.md with expanded acceptance criteria
3. Create test data generation scripts (CEC, IPAS, SAP master data)
4. Set up Docker Compose test infrastructure (`tests/utils/test-env`)
5. Begin Tier 1 (unit) test development with TDD approach

---

**Document Author:** Testing Specialist (Kailash SDK)
**Review Status:** DRAFT - Awaiting stakeholder review
**File Location:** C:\Users\fujif\OneDrive\Documents\GitHub\lead2cash\docs\testing-analysis-v3.md
