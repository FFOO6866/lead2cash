#!/bin/bash

###############################################################################
# RRPS Lead-to-Cash POV - GitHub Project Setup Script
#
# This script creates:
# - GitHub repository (if needed)
# - Labels, milestones, and project
# - All issues for Sprint 0, Epic 1, Epic 2, Technical Enablers, and UAT
#
# Prerequisites:
# 1. GitHub CLI installed: https://cli.github.com/
# 2. Authenticated: gh auth login
# 3. Repository created or script will create it
#
# Usage:
#   bash scripts/setup-github-project.sh
###############################################################################

set -e  # Exit on error

# Configuration
REPO_OWNER="fujif"  # Change this to your GitHub username or org
REPO_NAME="lead2cash"
REPO_FULL="$REPO_OWNER/$REPO_NAME"

echo "========================================"
echo "RRPS Lead-to-Cash POV - GitHub Setup"
echo "========================================"
echo ""
echo "Repository: $REPO_FULL"
echo ""

# Check if gh CLI is authenticated
if ! gh auth status &>/dev/null; then
    echo "ERROR: GitHub CLI not authenticated."
    echo "Please run: gh auth login"
    exit 1
fi

# Check if repository exists, create if needed
if ! gh repo view "$REPO_FULL" &>/dev/null; then
    echo "Repository $REPO_FULL does not exist."
    read -p "Create it now? (y/n) " -n 1 -r
    echo
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        gh repo create "$REPO_FULL" --private --description "RRPS Lead-to-Cash POV - 8-Week MVP using Kailash SDK"
        git remote add origin "https://github.com/$REPO_FULL.git"
        echo "Repository created successfully."
    else
        echo "Exiting. Please create the repository manually."
        exit 1
    fi
fi

echo ""
echo "Step 1: Creating Labels..."
echo "----------------------------"

# Epic labels
gh label create "epic-1-qualification" --color "0E8A16" --description "Epic 1: Opportunity Qualification" --repo "$REPO_FULL" || true
gh label create "epic-2-order-creation" --color "1D76DB" --description "Epic 2: Fast Order Creation" --repo "$REPO_FULL" || true

# Size labels
gh label create "size/S" --color "FBCA04" --description "Small (1-2 days)" --repo "$REPO_FULL" || true
gh label create "size/M" --color "FFA500" --description "Medium (3-5 days)" --repo "$REPO_FULL" || true
gh label create "size/L" --color "D93F0B" --description "Large (1-2 weeks)" --repo "$REPO_FULL" || true
gh label create "size/XL" --color "B60205" --description "Extra Large (2-4 weeks)" --repo "$REPO_FULL" || true

# Type labels
gh label create "user-story" --color "5319E7" --description "User story" --repo "$REPO_FULL" || true
gh label create "technical-enabler" --color "0052CC" --description "Technical enabler/infrastructure" --repo "$REPO_FULL" || true
gh label create "infrastructure" --color "C5DEF5" --description "Infrastructure setup" --repo "$REPO_FULL" || true
gh label create "bug" --color "D73A4A" --description "Something isn't working" --repo "$REPO_FULL" || true
gh label create "uat" --color "EDEDED" --description "UAT testing and feedback" --repo "$REPO_FULL" || true

# Priority labels
gh label create "priority/critical" --color "B60205" --description "Critical priority" --repo "$REPO_FULL" || true
gh label create "priority/high" --color "D93F0B" --description "High priority" --repo "$REPO_FULL" || true
gh label create "priority/medium" --color "FBCA04" --description "Medium priority" --repo "$REPO_FULL" || true
gh label create "priority/low" --color "0E8A16" --description "Low priority" --repo "$REPO_FULL" || true

# Status labels
gh label create "blocked" --color "D93F0B" --description "Blocked by dependency" --repo "$REPO_FULL" || true
gh label create "in-progress" --color "1D76DB" --description "Currently in progress" --repo "$REPO_FULL" || true
gh label create "review" --color "FBCA04" --description "In review" --repo "$REPO_FULL" || true
gh label create "done" --color "0E8A16" --description "Completed" --repo "$REPO_FULL" || true

echo "Labels created successfully."

echo ""
echo "Step 2: Creating Milestones..."
echo "--------------------------------"

# Calculate dates (approximate - adjust as needed)
TODAY=$(date +%Y-%m-%d)

gh api repos/"$REPO_FULL"/milestones -X POST \
  -f title="Sprint 0 - Infrastructure (Week 0-2)" \
  -f description="Infrastructure setup, CPI validation, DataFlow alpha testing" \
  -f due_on="$(date -d '+2 weeks' +%Y-%m-%dT23:59:59Z 2>/dev/null || date -v+2w +%Y-%m-%dT23:59:59Z 2>/dev/null || echo '')" \
  || true

gh api repos/"$REPO_FULL"/milestones -X POST \
  -f title="Sprint 1 - Epic 1 (Week 1-2)" \
  -f description="Opportunity Qualification - 3 stories" \
  -f due_on="$(date -d '+2 weeks' +%Y-%m-%dT23:59:59Z 2>/dev/null || date -v+2w +%Y-%m-%dT23:59:59Z 2>/dev/null || echo '')" \
  || true

gh api repos/"$REPO_FULL"/milestones -X POST \
  -f title="Sprint 2 - Epic 2 Part 1 (Week 3-4)" \
  -f description="Order Creation - Stories 2.1-2.2" \
  -f due_on="$(date -d '+4 weeks' +%Y-%m-%dT23:59:59Z 2>/dev/null || date -v+4w +%Y-%m-%dT23:59:59Z 2>/dev/null || echo '')" \
  || true

gh api repos/"$REPO_FULL"/milestones -X POST \
  -f title="Sprint 3 - Epic 2 Part 2 (Week 5-6)" \
  -f description="Order Creation - Stories 2.3-2.4" \
  -f due_on="$(date -d '+6 weeks' +%Y-%m-%dT23:59:59Z 2>/dev/null || date -v+6w +%Y-%m-%dT23:59:59Z 2>/dev/null || echo '')" \
  || true

gh api repos/"$REPO_FULL"/milestones -X POST \
  -f title="Sprint 4 - UAT (Week 7-8)" \
  -f description="User Acceptance Testing with 10 test orders" \
  -f due_on="$(date -d '+8 weeks' +%Y-%m-%dT23:59:59Z 2>/dev/null || date -v+8w +%Y-%m-%dT23:59:59Z 2>/dev/null || echo '')" \
  || true

echo "Milestones created successfully."

echo ""
echo "Step 3: Creating Project..."
echo "----------------------------"

# Note: GitHub Projects v2 (beta) requires different API
# Using gh CLI project commands (requires gh extension)
# If not available, create project manually via GitHub UI

echo "Creating GitHub Project (you may need to do this manually)..."
echo "Project Name: RRPS Lead-to-Cash POV (8-Week MVP)"
echo "Description: Prove AI agents can deliver opportunity qualification + fast order creation"
echo ""
echo "Manual steps (if automated creation fails):"
echo "1. Go to: https://github.com/$REPO_OWNER?tab=projects"
echo "2. Click 'New Project'"
echo "3. Name: RRPS Lead-to-Cash POV (8-Week MVP)"
echo "4. Add custom fields: Epic (text), Size (single-select: S/M/L/XL), Sprint (text)"
echo "5. Create views: Sprint Board, Epic View, Timeline"
echo ""

echo ""
echo "Step 4: Creating Issues..."
echo "----------------------------"
echo ""

# Function to create issue and capture issue number
create_issue() {
    local title="$1"
    local body="$2"
    local labels="$3"
    local milestone="$4"

    echo "Creating: $title"
    gh issue create \
        --repo "$REPO_FULL" \
        --title "$title" \
        --body "$body" \
        --label "$labels" \
        --milestone "$milestone" 2>/dev/null || echo "  (Issue may already exist)"
}

###############################################################################
# Sprint 0: Infrastructure Checklist
###############################################################################

SPRINT0_BODY=$(cat <<'EOF'
## Sprint 0: Infrastructure Setup Checklist

**NOT A USER STORY** - This is prerequisite work before Sprint 1 starts.

**Duration:** 0-2 weeks (depending on CPI access readiness)
**Team:** 1 backend engineer + 0.5 integration specialist
**Estimated Effort:** 60-80 hours

---

## Ready Criteria

- [ ] PostgreSQL credentials confirmed in .env
- [ ] SAP CPI sandbox access granted (OData, BAPI, IDoc endpoints)
- [ ] Kailash SDK installation access verified
- [ ] Team available for Sprint 0 setup

---

## Definition of Done

### 1. Backend Setup & DataFlow Alpha Validation

- [ ] Kailash SDK installed: pip install kailash[dataflow,nexus,kaizen]
- [ ] PostgreSQL connection verified using .env credentials
- [ ] DataFlow Alpha Validation:
  - [ ] @db.model generates 9 nodes for test Transaction model
  - [ ] All auto-generated nodes work in workflows
  - [ ] PostgreSQL integration stable with 1000+ test transactions
  - [ ] Performance acceptable: queries < 200ms, filters < 500ms
- [ ] Nexus multi-channel deployment tested (API, CLI)
- [ ] Essential SDK patterns validated: runtime.execute(workflow.build())

### 2. SAP CPI Integration Testing (CRITICAL PATH)

- [ ] CEC OData Client (TE-2):
  - [ ] OAuth2 authentication successful
  - [ ] Retrieve 10 test opportunities
  - [ ] Response time < 2 seconds
- [ ] IPAS Client (TE-3):
  - [ ] Retrieve 5 test BOM configurations
  - [ ] Parse BOM to SalesOrderItem list
  - [ ] Response time < 3 seconds
- [ ] MS5 BAPI Client (TE-5):
  - [ ] BAPI_SALESORDER_SIMULATE test successful (1 order)
  - [ ] Parse BAPI return messages correctly
  - [ ] Circuit breaker activates after 3 failures
- [ ] MS5 IDoc Client (TE-6):
  - [ ] Submit 1 test IDoc ORDERS05
  - [ ] Receive test VBELN from SAP
  - [ ] Idempotency test: retry with same correlation_id returns existing VBELN

### 3. Audit Store Infrastructure

- [ ] PostgreSQL audit tables created:
  - [ ] transactions (correlation_id UNIQUE constraint)
  - [ ] events (basic event log)
  - [ ] field_provenance (AI agent decisions)
- [ ] Append-only enforcement tested
- [ ] Test data: 20 sample transactions with provenance

### 4. Documentation & Knowledge Transfer

- [ ] DataFlow alpha limitations documented
- [ ] CPI integration endpoints documented
- [ ] Common issues and solutions logged
- [ ] Team walkthrough session completed

---

## DataFlow Alpha Validation (DECISION POINT)

Success Criteria:
- [ ] Transaction model auto-generates all 9 nodes successfully
- [ ] Query/filter/create nodes work in workflows
- [ ] PostgreSQL integration stable with 1000+ test transactions
- [ ] Performance acceptable: queries < 200ms, filters < 500ms

Decision Point:
- ✅ SUCCESS: Proceed with DataFlow for audit store
- ⚠️ PARTIAL: Document workarounds, continue with caution
- ❌ FAILURE: Fallback to Core SDK AsyncSQLDatabaseNode

---

## Dependencies

**Blocks:** All Epic 1 and Epic 2 stories
**Required Technical Enablers:** TE-2, TE-3, TE-5, TE-6, TE-12, TE-14

---

## Notes

This is the CRITICAL PATH for the POV. CPI integration delays will block all user stories.
Allocate 20% time buffer for inevitable delays.
EOF
)

create_issue "Sprint 0: Infrastructure Setup Checklist" "$SPRINT0_BODY" "infrastructure,priority/critical" "Sprint 0 - Infrastructure (Week 0-2)"

###############################################################################
# Technical Enablers
###############################################################################

TE2_BODY=$(cat <<'EOF'
## TE-2: CEC OData Client

**Purpose:** Retrieve C4C opportunities via SAP CPI
**Technology:** Custom OData client + CPI middleware
**Validated In:** Sprint 0

---

## Technical Requirements

- [ ] OAuth2 authentication via CPI
- [ ] OData v2/v4 query support
- [ ] Filter by customer name, product family, status
- [ ] Response time < 2 seconds
- [ ] Error handling: timeout, auth failure, malformed response

---

## Implementation Details

**Endpoint:** https://{cpi-host}/http/cec/opportunities
**Authentication:** OAuth2 Client Credentials
**Query Parameters:**
- $filter: OData filter expression
- $select: Fields to retrieve
- $top: Limit results

---

## Acceptance Criteria

- [ ] OAuth2 authentication successful
- [ ] Retrieve 10 test opportunities from C4C sandbox
- [ ] Response time < 2 seconds (measured over 10 requests)
- [ ] Proper error handling: timeout → return error, token expired → refresh + retry
- [ ] Integration test passing with real CPI sandbox

---

## Dependencies

**Required By Stories:** Story 1.1, Story 1.2, Story 1.3, Story 2.1
**External Dependencies:** CPI sandbox access, C4C test data
EOF
)

create_issue "TE-2: CEC OData Client" "$TE2_BODY" "technical-enabler,infrastructure,priority/critical" "Sprint 0 - Infrastructure (Week 0-2)"

TE3_BODY=$(cat <<'EOF'
## TE-3: IPAS Client

**Purpose:** Retrieve BOM configurations from IPAS
**Technology:** Custom REST client + CPI middleware
**Validated In:** Sprint 0

---

## Technical Requirements

- [ ] Retrieve BOM by product ID
- [ ] Parse BOM to SalesOrderItem list (material, quantity, unit)
- [ ] Response time < 3 seconds
- [ ] Error handling: timeout, product not found, invalid BOM

---

## Acceptance Criteria

- [ ] Retrieve 5 test BOM configurations from IPAS sandbox
- [ ] Parse BOM correctly to SalesOrderItem list
- [ ] Response time < 3 seconds (measured over 5 requests)
- [ ] Proper error handling: product not found → return empty BOM, timeout → retry once
- [ ] Integration test passing with real IPAS sandbox

---

## Dependencies

**Required By Stories:** Story 2.1
**External Dependencies:** IPAS sandbox access, test product IDs
EOF
)

create_issue "TE-3: IPAS Client" "$TE3_BODY" "technical-enabler,infrastructure,priority/high" "Sprint 0 - Infrastructure (Week 0-2)"

TE4_BODY=$(cat <<'EOF'
## TE-4: Opportunity Readiness Agent (Kaizen)

**Purpose:** AI-driven confidence scoring for opportunity readiness
**Technology:** Kailash Kaizen + LLM (GPT-4/Claude)
**Validated In:** Sprint 1

---

## Technical Requirements

- [ ] LLM Signature: "opportunity -> readiness_score, missing_fields, reasoning"
- [ ] Prompt: Assess if opportunity is ready to convert to SAP order
- [ ] Check: customer confirmed, product configured, pricing approved, delivery date, payment terms
- [ ] Output: {score: 0-1, missing: [fields], reasoning: "explanation"}
- [ ] Fallback: Rule-based scoring if LLM API timeout

---

## Acceptance Criteria

- [ ] Agent assesses 10 test opportunities with correct scores (validated manually)
- [ ] Reasoning is human-readable and actionable
- [ ] Missing fields list is accurate
- [ ] Response time < 3 seconds per opportunity
- [ ] Fallback to rule-based scoring if LLM timeout
- [ ] Integration test with Kaizen framework passing

---

## Dependencies

**Required By Stories:** Story 1.2, Story 1.3
**External Dependencies:** LLM API access (OpenAI/Anthropic), Kaizen framework
EOF
)

create_issue "TE-4: Opportunity Readiness Agent (Kaizen)" "$TE4_BODY" "technical-enabler,priority/high,epic-1-qualification" "Sprint 1 - Epic 1 (Week 1-2)"

TE5_BODY=$(cat <<'EOF'
## TE-5: MS5 BAPI Client (BAPI_SALESORDER_SIMULATE)

**Purpose:** Pre-validate orders against SAP business logic before submission
**Technology:** Custom BAPI client + CPI + circuit breaker
**Validated In:** Sprint 0

---

## Technical Requirements

- [ ] Call BAPI_SALESORDER_SIMULATE with IDoc data
- [ ] Parse return messages (errors, warnings, info)
- [ ] Circuit breaker: 3 consecutive failures → open circuit for 60s
- [ ] Response time < 5 seconds
- [ ] Error handling: timeout, BAPI error, connection loss

---

## Acceptance Criteria

- [ ] BAPI_SALESORDER_SIMULATE test successful with 1 valid order
- [ ] Parse BAPI return messages correctly (errors, warnings)
- [ ] Circuit breaker activates after 3 failures, recovers after 60s
- [ ] Response time < 5 seconds (measured over 10 requests)
- [ ] Integration test passing with real SAP sandbox

---

## Dependencies

**Required By Stories:** Story 2.2
**External Dependencies:** SAP CPI sandbox access, test order data
EOF
)

create_issue "TE-5: MS5 BAPI Client (BAPI_SALESORDER_SIMULATE)" "$TE5_BODY" "technical-enabler,infrastructure,priority/critical" "Sprint 0 - Infrastructure (Week 0-2)"

TE6_BODY=$(cat <<'EOF'
## TE-6: MS5 IDoc Client (ORDERS05 Submission)

**Purpose:** Submit orders to SAP via IDoc and receive VBELN confirmation
**Technology:** Custom IDoc client + CPI + idempotency layer
**Validated In:** Sprint 0

---

## Technical Requirements

- [ ] Submit IDoc ORDERS05 to SAP via CPI
- [ ] Receive VBELN (SAP Sales Order Number) in response
- [ ] Idempotency: Same correlation_id returns existing VBELN (no duplicate orders)
- [ ] Response time < 30 seconds
- [ ] Retry logic: 1 automatic retry on timeout
- [ ] Error handling: SAP error, timeout, connection loss

---

## Acceptance Criteria

- [ ] Submit 1 test IDoc ORDERS05 successfully
- [ ] Receive test VBELN from SAP sandbox
- [ ] Idempotency test: Retry with same correlation_id returns existing VBELN
- [ ] Response time < 30 seconds (measured over 5 submissions)
- [ ] Automatic retry on timeout works correctly
- [ ] Integration test passing with real SAP sandbox

---

## Dependencies

**Required By Stories:** Story 2.3
**External Dependencies:** SAP CPI sandbox access, IDoc configuration, TE-10 (Idempotency)
EOF
)

create_issue "TE-6: MS5 IDoc Client (ORDERS05 Submission)" "$TE6_BODY" "technical-enabler,infrastructure,priority/critical" "Sprint 0 - Infrastructure (Week 0-2)"

TE8_BODY=$(cat <<'EOF'
## TE-8: Order Orchestration Agent (Kaizen)

**Purpose:** Auto-populate IDoc fields from multi-system data with confidence scoring
**Technology:** Kailash Kaizen + LLM (GPT-4/Claude)
**Validated In:** Sprint 2

---

## Technical Requirements

- [ ] LLM Signature: "order_data -> idoc_fields, confidence_scores, review_flags"
- [ ] Input: Merged data from C4C, IPAS, SAP customer master
- [ ] Prompt: Populate ORDERS05 IDoc fields following RRPS business rules
- [ ] Output: {idoc: {...}, confidence: {...}, review_flags: [...]}
- [ ] Color-coding: Green (≥0.8), Yellow (0.5-0.79), Red (<0.5)
- [ ] Integration with TE-5 (BAPI validation)

---

## Acceptance Criteria

- [ ] Agent populates 30-40% of IDoc fields with high confidence (≥0.8)
- [ ] Confidence scores are accurate (validated manually on 10 test orders)
- [ ] Review flags correctly identify uncertain fields
- [ ] BAPI validation catches hallucinations before submission
- [ ] Response time < 5 seconds per order
- [ ] Integration test with Kaizen framework passing

---

## POV Success Metric

30-40% of fields auto-filled and accepted by user without edits (measured in UAT)

---

## Dependencies

**Required By Stories:** Story 2.2
**External Dependencies:** LLM API access, Kaizen framework, TE-5 (BAPI validation), TE-2/3/12 (data sources)
EOF
)

create_issue "TE-8: Order Orchestration Agent (Kaizen)" "$TE8_BODY" "technical-enabler,priority/critical,epic-2-order-creation" "Sprint 2 - Epic 2 Part 1 (Week 3-4)"

TE10_BODY=$(cat <<'EOF'
## TE-10: Idempotency Layer

**Purpose:** Prevent duplicate order submissions with correlation_id tracking
**Technology:** PostgreSQL + correlation_id (UUID)
**Validated In:** Sprint 3

---

## Technical Requirements

- [ ] Generate unique correlation_id (UUID) for each order submission
- [ ] Query PostgreSQL audit store before submission
- [ ] If correlation_id exists → Return existing VBELN (no resubmission)
- [ ] If new → Proceed with IDoc submission
- [ ] Store correlation_id + VBELN mapping in audit store

---

## Implementation Details

**Database Table:** transactions
**Unique Constraint:** correlation_id (prevents duplicates)
**Query Logic:**
```sql
SELECT vbeln FROM transactions WHERE correlation_id = ?
```

---

## Acceptance Criteria

- [ ] Generate unique correlation_id for new order
- [ ] Query audit store correctly
- [ ] Return existing VBELN if correlation_id found
- [ ] Submit to SAP only if correlation_id not found
- [ ] Store correlation_id + VBELN mapping after successful submission
- [ ] Unit test: Retry with same correlation_id returns cached VBELN
- [ ] Integration test: Real SAP submission + idempotency check

---

## Dependencies

**Required By Stories:** Story 2.3
**External Dependencies:** TE-14 (Audit Store), TE-6 (IDoc Client)
EOF
)

create_issue "TE-10: Idempotency Layer" "$TE10_BODY" "technical-enabler,infrastructure,priority/high" "Sprint 3 - Epic 2 Part 2 (Week 5-6)"

TE12_BODY=$(cat <<'EOF'
## TE-12: SAP Customer Master Client

**Purpose:** Retrieve customer master data from SAP (payment terms, incoterms, sales org)
**Technology:** Custom BAPI/OData client + CPI
**Validated In:** Sprint 0

---

## Technical Requirements

- [ ] Retrieve customer master data by customer ID
- [ ] Fields: Payment terms, Incoterms, Sales Org, Distribution Channel, Division
- [ ] Response time < 2 seconds
- [ ] Error handling: customer not found, timeout

---

## Acceptance Criteria

- [ ] Retrieve customer master data for 5 test customers
- [ ] All required fields returned correctly
- [ ] Response time < 2 seconds (measured over 5 requests)
- [ ] Proper error handling: customer not found → return error message
- [ ] Integration test passing with real SAP sandbox

---

## Dependencies

**Required By Stories:** Story 2.1
**External Dependencies:** SAP CPI sandbox access, test customer IDs
EOF
)

create_issue "TE-12: SAP Customer Master Client" "$TE12_BODY" "technical-enabler,infrastructure,priority/medium" "Sprint 0 - Infrastructure (Week 0-2)"

TE14_BODY=$(cat <<'EOF'
## TE-14: Audit Store (DataFlow + PostgreSQL)

**Purpose:** Immutable event log for order submissions and AI decisions
**Technology:** Kailash DataFlow + PostgreSQL
**Validated In:** Sprint 0, used in Sprint 3-4

---

## Technical Requirements

- [ ] PostgreSQL tables: transactions, events, field_provenance
- [ ] Append-only enforcement (no UPDATEs, only INSERTs)
- [ ] DataFlow @db.model auto-generates 9 nodes per model
- [ ] Unique constraint: correlation_id (prevents duplicates)
- [ ] Performance: Queries < 200ms, filters < 500ms

---

## Database Schema

**Table: transactions**
- correlation_id (UUID, UNIQUE)
- vbeln (VARCHAR)
- idoc_data (JSONB)
- user_id (VARCHAR)
- timestamp (TIMESTAMP)

**Table: events**
- event_id (UUID)
- correlation_id (UUID, FK)
- event_type (VARCHAR)
- event_data (JSONB)
- timestamp (TIMESTAMP)

**Table: field_provenance**
- field_id (UUID)
- correlation_id (UUID, FK)
- field_name (VARCHAR)
- source (VARCHAR: "ai" or "manual")
- confidence (DECIMAL)
- timestamp (TIMESTAMP)

---

## Acceptance Criteria

- [ ] PostgreSQL audit tables created with correct schema
- [ ] DataFlow @db.model generates 9 nodes for Transaction model
- [ ] Append-only enforcement tested (UPDATE blocked, only INSERT allowed)
- [ ] Populate 20 test transactions with provenance data
- [ ] Performance: Queries < 200ms, filters < 500ms (measured with 1000+ records)
- [ ] Integration test with DataFlow passing

---

## DataFlow Alpha Validation

This is a DECISION POINT in Sprint 0. If DataFlow alpha has blocking bugs:
- Fallback to Core SDK AsyncSQLDatabaseNode
- Update audit store implementation (adds 3-5 days)

---

## Dependencies

**Required By Stories:** Story 1.3, Story 2.3, Story 2.4
**External Dependencies:** PostgreSQL 14+, DataFlow alpha (v0.4.6+)
EOF
)

create_issue "TE-14: Audit Store (DataFlow + PostgreSQL)" "$TE14_BODY" "technical-enabler,infrastructure,priority/critical" "Sprint 0 - Infrastructure (Week 0-2)"

TE15_BODY=$(cat <<'EOF'
## TE-15: Provenance Tracking

**Purpose:** Track which fields were auto-filled by AI vs. manually edited by users
**Technology:** PostgreSQL field_provenance table
**Validated In:** Sprint 4

---

## Technical Requirements

- [ ] Log every field in IDoc with source (ai/manual) and confidence
- [ ] Store in field_provenance table
- [ ] Query provenance data for audit trail
- [ ] Calculate acceptance rate: % of AI fields unchanged by user

---

## Implementation Details

**Field Provenance Record:**
```json
{
  "field_name": "delivery_plant",
  "source": "ai",
  "confidence": 0.85,
  "original_value": "1000",
  "final_value": "1000",
  "user_edited": false
}
```

---

## Acceptance Criteria

- [ ] Log provenance for all IDoc fields (30-50 fields per order)
- [ ] Track AI vs. manual source correctly
- [ ] Track user edits (original_value vs. final_value)
- [ ] Query provenance data for audit trail
- [ ] Calculate acceptance rate: (Unchanged AI fields / Total AI fields) × 100
- [ ] Integration test: Create order → Log provenance → Query provenance

---

## POV Success Metric

Acceptance rate ≥30% (realistic target for first POV iteration)

---

## Dependencies

**Required By Stories:** Story 2.4
**External Dependencies:** TE-14 (Audit Store), TE-8 (Order Orchestration Agent)
EOF
)

create_issue "TE-15: Provenance Tracking" "$TE15_BODY" "technical-enabler,infrastructure,priority/medium" "Sprint 4 - UAT (Week 7-8)"

###############################################################################
# Epic 1 Stories
###############################################################################

STORY11_BODY=$(cat <<'EOF'
## User Story

**As a** Sales Manager
**I want** to search opportunities by customer name or product family
**So that** I can quickly find deals related to specific accounts or product lines

**Size:** S (Small)
**Epic:** epic-1-qualification
**Sprint:** Sprint 1

---

## Acceptance Criteria

- [ ] User enters customer name (e.g., "Acme Corp") → Returns all opportunities for that customer
- [ ] User enters product family (e.g., "Power Systems") → Returns all opportunities with matching products
- [ ] Search supports partial matching (e.g., "Acme" matches "Acme Corp" and "Acme Industries")
- [ ] Results returned within 2 seconds
- [ ] Empty result set shows clear message: "No opportunities found for [search term]"

---

## Technical Implementation

**Workflow:** SearchOpportunitiesWorkflow

**Nodes:**
1. TextInputNode → Capture search term (customer or product)
2. CustomNode<CECODataClient> → Query C4C opportunities via CPI
   - OData filter: $filter=contains(AccountName, '{term}') or contains(ProductFamily, '{term}')
   - OAuth2 authentication via CPI
3. FilterOpportunitiesNode → Filter results by status (Open, In Progress)
4. FormatResultsNode → Format as list: Opportunity ID, Customer, Product, Amount, Close Date
5. TextOutputNode → Return results or "No opportunities found"

**Technical Enablers Required:**
- [x] TE-2: CEC OData Client

---

## Edge Cases

- **Search term with special characters** → URL-encode before OData query
- **CPI timeout (>5 sec)** → Return error: "CEC system unavailable, try again later"
- **OAuth2 token expired** → Refresh token automatically, retry once

---

## Dependencies

**Blocked By:** Sprint 0 complete, TE-2 validated
**Blocks:** Story 1.2, Story 1.3

---

## Definition of Done

- [ ] All acceptance criteria met
- [ ] Unit tests for search logic
- [ ] Integration test with CPI sandbox
- [ ] Response time < 2 seconds validated
- [ ] Code reviewed and approved
- [ ] Documentation updated
EOF
)

create_issue "Story 1.1: Search Opportunities by Customer/Product" "$STORY11_BODY" "user-story,epic-1-qualification,size/S,priority/high" "Sprint 1 - Epic 1 (Week 1-2)"

STORY12_BODY=$(cat <<'EOF'
## User Story

**As a** Sales Manager
**I want** to filter opportunities by AI-assessed readiness criteria
**So that** I can prioritize deals most likely to convert to orders

**Size:** M (Medium)
**Epic:** epic-1-qualification
**Sprint:** Sprint 1

---

## Acceptance Criteria

- [ ] User selects readiness filter: "Ready to Order" → Shows opportunities with ≥70% AI confidence score
- [ ] User selects readiness filter: "Needs Follow-up" → Shows opportunities with 40-69% AI confidence score
- [ ] User selects readiness filter: "Not Ready" → Shows opportunities with <40% AI confidence score
- [ ] Each opportunity shows AI confidence score (e.g., "85% Ready") with human-readable reasoning
- [ ] Reasoning includes missing prerequisites (e.g., "Missing: Delivery date, Payment terms")
- [ ] Results sorted by confidence score (highest first)

---

## Technical Implementation

**Workflow:** AssessOpportunityReadinessWorkflow

**Nodes:**
1. CustomNode<CECODataClient> → Retrieve opportunities from Story 1.1 results
2. Kaizen Agent: OpportunityReadinessAgent
   - Input: Opportunity data (customer, product, amount, close date, notes)
   - LLM Signature: "opportunity -> readiness_score, missing_fields, reasoning"
   - Prompt: "Assess if this opportunity is ready to convert to SAP order. Check for: customer confirmed, product configured, pricing approved, delivery date set, payment terms agreed."
   - Output: {score: 0.85, missing: ["delivery_date"], reasoning: "Customer and pricing confirmed. Need delivery date."}
3. FilterByScoreNode → Apply user-selected filter (≥70%, 40-69%, <40%)
4. SortByScoreNode → Sort by score descending
5. TextOutputNode → Format results with confidence score + reasoning

**Technical Enablers Required:**
- [x] TE-4: Opportunity Readiness Agent (Kaizen)
- [x] TE-2: CEC OData Client

---

## Edge Cases

- **Opportunity with incomplete data** → Score as <40%, list all missing fields
- **LLM API timeout** → Fallback to rule-based scoring (check for null fields)
- **User selects no filter** → Show all opportunities sorted by score

---

## Dependencies

**Blocked By:** Sprint 0 complete, TE-2 validated, TE-4 implemented, Story 1.1 complete
**Blocks:** Story 1.3

---

## Definition of Done

- [ ] All acceptance criteria met
- [ ] Kaizen agent tested with 10 test opportunities
- [ ] Unit tests for filtering and sorting logic
- [ ] Integration test with LLM API
- [ ] Fallback to rule-based scoring tested
- [ ] Code reviewed and approved
- [ ] Documentation updated
EOF
)

create_issue "Story 1.2: Filter Opportunities by Readiness Criteria" "$STORY12_BODY" "user-story,epic-1-qualification,size/M,priority/high" "Sprint 1 - Epic 1 (Week 1-2)"

STORY13_BODY=$(cat <<'EOF'
## User Story

**As a** Sales Manager
**I want** to see why the AI assessed an opportunity as ready/not ready
**So that** I can validate the assessment and take corrective action

**Size:** S (Small)
**Epic:** epic-1-qualification
**Sprint:** Sprint 1

---

## Acceptance Criteria

- [ ] User clicks on opportunity → Shows detailed AI reasoning
- [ ] Reasoning includes:
  - [ ] Confidence score (e.g., "85% Ready")
  - [ ] Checklist: Customer confirmed (✅), Product configured (✅), Pricing approved (✅), Delivery date (❌), Payment terms (✅)
  - [ ] Next steps: "Contact customer for delivery date confirmation"
- [ ] User can override AI assessment (mark as "Ready to Order" even if AI says 60%)
- [ ] Override is logged in audit trail with reason

---

## Technical Implementation

**Workflow:** ViewOpportunityReasoningWorkflow

**Nodes:**
1. TextInputNode → Capture opportunity ID
2. CustomNode<CECODataClient> → Retrieve full opportunity details
3. Kaizen Agent: OpportunityReadinessAgent (same as Story 1.2)
   - Return detailed checklist + next steps
4. FormatReasoningNode → Format as structured output (confidence, checklist, next steps)
5. TextOutputNode → Display reasoning
6. Optional Override Path:
   - BooleanInputNode → User wants to override? (Yes/No)
   - TextInputNode → Override reason
   - CustomNode<AuditStoreWriter> → Log override event to PostgreSQL
     - Event type: "opportunity_assessment_override"
     - Data: {opportunity_id, ai_score, user_override, reason}

**Technical Enablers Required:**
- [x] TE-4: Opportunity Readiness Agent (Kaizen)
- [x] TE-2: CEC OData Client
- [x] TE-14: Audit Store

---

## Edge Cases

- **Opportunity not found** → Return "Invalid Opportunity ID"
- **LLM reasoning too verbose** → Truncate to 500 characters, add "See full reasoning..." link
- **User overrides without reason** → Require reason (validation error)

---

## Dependencies

**Blocked By:** Sprint 0 complete, TE-2 validated, TE-4 implemented, TE-14 validated, Story 1.2 complete
**Blocks:** None

---

## Definition of Done

- [ ] All acceptance criteria met
- [ ] Audit store logging tested
- [ ] Unit tests for reasoning display and override logic
- [ ] Integration test with Kaizen agent
- [ ] Code reviewed and approved
- [ ] Documentation updated
EOF
)

create_issue "Story 1.3: View AI Confidence Reasoning" "$STORY13_BODY" "user-story,epic-1-qualification,size/S,priority/medium" "Sprint 1 - Epic 1 (Week 1-2)"

###############################################################################
# Epic 2 Stories
###############################################################################

STORY21_BODY=$(cat <<'EOF'
## User Story

**As a** Sales Operations Specialist
**I want** the system to automatically retrieve order data from C4C, IPAS, and SAP when I select an opportunity
**So that** I don't waste 15-20 minutes manually gathering information from 3 systems

**Size:** L (Large)
**Epic:** epic-2-order-creation
**Sprint:** Sprint 2

---

## Acceptance Criteria

- [ ] User selects opportunity (from Epic 1) → System retrieves data from C4C, IPAS, SAP in parallel
- [ ] C4C Data Retrieved: Customer name, Sold-to party, Ship-to party, Opportunity amount, Close date
- [ ] IPAS Data Retrieved: BOM (Bill of Materials) for product configuration → Parsed to SalesOrderItem list
- [ ] SAP Data Retrieved: Customer master data (payment terms, incoterms, sales org)
- [ ] All data retrieved within 5 seconds total (parallel execution)
- [ ] If any system unavailable → Shows which data is missing, allows manual entry

---

## Technical Implementation

**Workflow:** RetrieveOrderDataWorkflow

**Nodes:**
1. TextInputNode → Capture opportunity ID (from Epic 1)
2. Parallel Execution Block:
   - CustomNode<CECODataClient> → Retrieve C4C opportunity data (2 sec)
   - CustomNode<IPASClient> → Retrieve BOM configuration (3 sec)
   - CustomNode<SAPCustomerMasterClient> → Retrieve customer master data via CPI (2 sec)
3. MergeDataNode → Combine all data sources into unified order object
4. ValidateCompletenessNode → Check for missing required fields
5. TextOutputNode → Display merged data or list missing fields

**Technical Enablers Required:**
- [x] TE-2: CEC OData Client
- [x] TE-3: IPAS Client
- [x] TE-12: SAP Customer Master Client

---

## Edge Cases

- **IPAS timeout** → Mark BOM as "unavailable", allow manual item entry
- **C4C returns partial data** → Mark missing fields, continue
- **SAP customer not found** → Return error: "Customer [ID] not found in SAP, contact master data team"
- **All 3 systems timeout** → Return error: "All systems unavailable, try again later or enter manually"

---

## Dependencies

**Blocked By:** Sprint 0 complete, TE-2/3/12 validated, Epic 1 complete
**Blocks:** Story 2.2

---

## Definition of Done

- [ ] All acceptance criteria met
- [ ] Parallel execution tested (response time < 5 sec)
- [ ] Unit tests for data merging and validation
- [ ] Integration tests with all 3 systems
- [ ] Error handling for partial/missing data
- [ ] Code reviewed and approved
- [ ] Documentation updated
EOF
)

create_issue "Story 2.1: Auto-Retrieve Order Data from Multiple Systems" "$STORY21_BODY" "user-story,epic-2-order-creation,size/L,priority/critical" "Sprint 2 - Epic 2 Part 1 (Week 3-4)"

STORY22_BODY=$(cat <<'EOF'
## User Story

**As a** Sales Operations Specialist
**I want** the AI agent to validate data completeness and intelligently populate IDoc fields
**So that** I can review a pre-filled order form instead of manually filling 50+ fields

**Size:** XL (Extra Large) - CORE POV FEATURE
**Epic:** epic-2-order-creation
**Sprint:** Sprint 2

---

## Acceptance Criteria

- [ ] System auto-populates 30-40% of IDoc fields from retrieved data (realistic POV target, not 60%+)
- [ ] Auto-Filled Fields (High Confidence):
  - [ ] Customer (Sold-to, Ship-to)
  - [ ] Sales Org, Distribution Channel, Division (from SAP master data)
  - [ ] Order Date (today), Requested Delivery Date (from C4C close date + 14 days)
  - [ ] Payment Terms, Incoterms (from SAP customer master)
  - [ ] Line Items (from IPAS BOM)
- [ ] Flagged for Review (Medium Confidence):
  - [ ] Pricing (AI suggests price from opportunity, flags for approval)
  - [ ] Delivery Plant (AI suggests based on Ship-to location, flags for confirmation)
  - [ ] Special Instructions (AI extracts from C4C notes, flags for review)
- [ ] Left Blank (Low Confidence):
  - [ ] Purchase Order Number (manual entry required)
  - [ ] Custom fields specific to deal
- [ ] User sees color-coded fields: Green (auto-filled, high confidence), Yellow (review required), Red (manual entry required)
- [ ] User can edit any field before submission

---

## Technical Implementation

**Workflow:** PopulateIDoCFieldsWorkflow

**Nodes:**
1. InputNode<OrderDataObject> → Receives merged data from Story 2.1
2. Kaizen Agent: OrderOrchestrationAgent
   - Input: Order data from 3 systems
   - LLM Signature: "order_data -> idoc_fields, confidence_scores, review_flags"
   - Prompt: "Populate ORDERS05 IDoc fields from C4C, IPAS, SAP data. Mark high-confidence fields as auto-filled, flag uncertain fields for review. Follow RRPS business rules: [pricing policy, delivery plant logic, etc.]"
   - Output: {idoc: {...}, confidence: {customer: 0.95, pricing: 0.60, plant: 0.70}, review_flags: ["pricing", "plant"]}
3. CustomNode<BAPI_SALESORDER_SIMULATE> → Pre-validate IDoc against SAP business logic
   - If BAPI returns errors → Add to review_flags
4. FormatOrderFormNode → Color-code fields (Green/Yellow/Red) based on confidence + BAPI validation
5. TextOutputNode → Display pre-filled order form for user review

**Technical Enablers Required:**
- [x] TE-8: Order Orchestration Agent (Kaizen)
- [x] TE-5: BAPI_SALESORDER_SIMULATE
- [x] TE-2/3/12: Data retrieval from Story 2.1

---

## Edge Cases

- **BAPI validation fails** → Show SAP error messages, highlight problematic fields in red
- **LLM hallucinates field value** → BAPI validation catches it, flags for review
- **Pricing outside policy limits** → Flag as red, require manager approval
- **Missing required field** → Block submission until filled

---

## POV Success Metric

30-40% of fields auto-filled and accepted by user without edits (measured in UAT, Week 7-8)

---

## Dependencies

**Blocked By:** Story 2.1 complete, TE-8 implemented, TE-5 validated
**Blocks:** Story 2.3

---

## Definition of Done

- [ ] All acceptance criteria met
- [ ] Kaizen agent populates 30-40% of fields correctly (tested with 10 orders)
- [ ] BAPI pre-validation catches errors
- [ ] Color-coding logic tested
- [ ] Unit tests for field population and validation
- [ ] Integration tests with Kaizen + BAPI
- [ ] Code reviewed and approved
- [ ] Documentation updated
EOF
)

create_issue "Story 2.2: AI Agent Validates & Populates IDoc Fields" "$STORY22_BODY" "user-story,epic-2-order-creation,size/XL,priority/critical" "Sprint 2 - Epic 2 Part 1 (Week 3-4)"

STORY23_BODY=$(cat <<'EOF'
## User Story

**As a** Sales Operations Specialist
**I want** to submit the validated order to SAP with one click and receive immediate confirmation
**So that** I don't wait 2-3 hours for batch processing or wonder if the order was created

**Size:** M (Medium)
**Epic:** epic-2-order-creation
**Sprint:** Sprint 3

---

## Acceptance Criteria

- [ ] User reviews order form (from Story 2.2) → Clicks "Submit to SAP"
- [ ] System submits IDoc ORDERS05 to SAP via CPI
- [ ] System receives VBELN (SAP Sales Order Number) within 30 seconds
- [ ] Success message: "Order [VBELN] created successfully in SAP"
- [ ] If submission fails → Shows SAP error message, allows retry
- [ ] Idempotency: Retry with same correlation_id returns existing VBELN (no duplicate orders)

---

## Technical Implementation

**Workflow:** SubmitOrderToSAPWorkflow

**Nodes:**
1. InputNode<IDoCObject> → Receives validated IDoc from Story 2.2
2. GenerateCorrelationIDNode → Create unique correlation_id (UUID)
3. CheckIdempotencyNode → Query PostgreSQL audit store for existing submission with same correlation_id
   - If found → Return existing VBELN, skip submission
4. CustomNode<MS5IDoCClient> → Submit IDoc ORDERS05 to SAP via CPI
   - Timeout: 30 seconds
   - Retry: 1 automatic retry if timeout
5. ReceiveVBELNNode → Parse SAP response for VBELN
6. CustomNode<AuditStoreWriter> → Log submission event to PostgreSQL
   - Event type: "order_submitted"
   - Data: {correlation_id, vbeln, idoc, timestamp, user_id}
7. TextOutputNode → Display "Order [VBELN] created successfully"

**Technical Enablers Required:**
- [x] TE-6: MS5 IDoc Client
- [x] TE-10: Idempotency Layer
- [x] TE-14: Audit Store

---

## Edge Cases

- **SAP returns error (e.g., "Customer blocked")** → Display error, do NOT create audit record, allow user to fix and retry
- **CPI timeout** → Display "SAP unavailable, order saved as draft, will auto-submit when SAP available"
- **Network loss during submission** → Idempotency check prevents duplicate on retry
- **User clicks "Submit" twice rapidly** → Idempotency check catches duplicate, returns existing VBELN

---

## POV Success Metric

1 order submitted successfully end-to-end (VBELN received)

---

## Dependencies

**Blocked By:** Story 2.2 complete, TE-6 validated, TE-10 implemented, TE-14 validated
**Blocks:** Story 2.4

---

## Definition of Done

- [ ] All acceptance criteria met
- [ ] Idempotency tested (duplicate submission returns cached VBELN)
- [ ] Audit store logging tested
- [ ] Unit tests for submission logic
- [ ] Integration test with SAP sandbox (VBELN received)
- [ ] Error handling tested (SAP error, timeout, network loss)
- [ ] Code reviewed and approved
- [ ] Documentation updated
EOF
)

create_issue "Story 2.3: Submit Order to SAP & Receive Confirmation" "$STORY23_BODY" "user-story,epic-2-order-creation,size/M,priority/critical" "Sprint 3 - Epic 2 Part 2 (Week 5-6)"

STORY24_BODY=$(cat <<'EOF'
## User Story

**As a** Sales Operations Specialist
**I want** to view the status of my submitted order and full audit trail
**So that** I can confirm it's in SAP and troubleshoot any issues

**Size:** S (Small)
**Epic:** epic-2-order-creation
**Sprint:** Sprint 3

---

## Acceptance Criteria

- [ ] User enters VBELN → Shows order status in SAP (Created, In Process, Delivered, Blocked)
- [ ] User sees full audit trail:
  - [ ] Who created the order (user ID, timestamp)
  - [ ] Which fields were auto-filled by AI vs. manually edited
  - [ ] SAP submission timestamp, received VBELN, CPI correlation_id
  - [ ] Any errors or retries during submission
- [ ] Audit trail is immutable (append-only, no edits)
- [ ] User can export audit trail as PDF for compliance

---

## Technical Implementation

**Workflow:** ViewOrderStatusWorkflow

**Nodes:**
1. TextInputNode → Capture VBELN
2. CustomNode<SAPOrderStatusClient> → Query SAP for current order status via CPI
3. CustomNode<AuditStoreReader> → Query PostgreSQL for audit trail:
   - Query: SELECT * FROM transactions WHERE vbeln = ? ORDER BY timestamp ASC
   - Joins with field_provenance table to show AI vs. manual fields
4. FormatAuditTrailNode → Format as timeline: Created → Validated → Submitted → Confirmed
5. TextOutputNode → Display status + audit trail
6. Optional PDF Export:
   - CustomNode<PDFGeneratorNode> → Convert audit trail to PDF
   - FileOutputNode → Return PDF file

**Technical Enablers Required:**
- [x] TE-14: Audit Store
- [x] TE-15: Provenance Tracking
- [x] TE-6: SAP Order Status query

---

## Edge Cases

- **VBELN not found in SAP** → Return "Order not found, check VBELN"
- **Audit trail incomplete (system error during logging)** → Display warning: "Partial audit trail, contact support"
- **PDF export fails** → Return error: "PDF generation failed, try again or contact support"

---

## POV Success Metric

100% of test orders have complete audit trail (correlation_id → VBELN)

---

## Dependencies

**Blocked By:** Story 2.3 complete, TE-14 validated, TE-15 implemented
**Blocks:** None

---

## Definition of Done

- [ ] All acceptance criteria met
- [ ] Audit trail query tested with 10 test orders
- [ ] Provenance tracking shows AI vs. manual fields correctly
- [ ] PDF export tested
- [ ] Unit tests for audit trail formatting
- [ ] Integration test with audit store
- [ ] Code reviewed and approved
- [ ] Documentation updated
EOF
)

create_issue "Story 2.4: View Order Status & Audit Trail" "$STORY24_BODY" "user-story,epic-2-order-creation,size/S,priority/medium" "Sprint 3 - Epic 2 Part 2 (Week 5-6)"

###############################################################################
# UAT Sprint
###############################################################################

UAT_BODY=$(cat <<'EOF'
## UAT Sprint: Week 7-8

**Focus:** Validate Epic 1 + Epic 2 with 3-5 pilot users, capture feedback, iterate

**Size:** L (Large)

---

## UAT Scope (Realistic POV)

- [ ] 3-5 pilot users (1-2 Sales Managers, 2-3 Sales Ops Specialists)
- [ ] 10 test orders created end-to-end with real SAP sandbox data
- [ ] Capture metrics:
  - [ ] Acceptance rate: % of auto-filled fields accepted without edits
  - [ ] Cycle time: Baseline (manual) vs. AI-assisted order creation
  - [ ] First-time-right: % of orders posted successfully on 1st attempt
  - [ ] User satisfaction: Survey with 5 questions (1-5 scale)
- [ ] Daily feedback sessions (15 min) to capture issues and iterate
- [ ] Bug fixes and tweaks based on feedback (max 2 days per fix)

---

## UAT Success Criteria (Honest POV Targets)

### ✅ PROCEED TO PRODUCTION ROLLOUT (12-week plan)

- [ ] 5+ orders created successfully end-to-end (VBELN received)
- [ ] 30%+ acceptance rate (auto-filled fields unchanged by users)
- [ ] Qualitative cycle time improvement (users report "much faster" than manual)
- [ ] 0 critical bugs (order loss, duplicate orders, data corruption)
- [ ] Users want to continue using the tool

### ⚠️ ITERATE (Extend POV by 4 weeks)

- [ ] 2-4 orders successful
- [ ] 20-29% acceptance rate
- [ ] Users report "slightly faster" but many manual corrections needed
- [ ] 1-2 critical bugs identified, fixable in 2 weeks
- [ ] Users willing to continue testing with improvements

### ❌ STOP POV

- [ ] <2 orders successful
- [ ] <20% acceptance rate (users reject most AI suggestions)
- [ ] Cycle time no better than manual (or worse due to tool overhead)
- [ ] 3+ critical bugs or CPI integration unstable
- [ ] Users refuse to continue testing

---

## UAT Activities

1. **Week 7: Initial Testing**
   - [ ] Day 1: User training session (2 hours)
   - [ ] Day 2-3: Users create 5 test orders
   - [ ] Day 4-5: Daily feedback sessions, fix critical bugs

2. **Week 8: Iteration & Final Testing**
   - [ ] Day 1-2: Deploy bug fixes from Week 7
   - [ ] Day 3-4: Users create 5 more test orders
   - [ ] Day 5: Final feedback session, capture metrics, POV decision

---

## Metrics Collection

**Acceptance Rate:**
- Track every IDoc field: AI-filled value vs. user final value
- Calculate: (Fields unchanged / Total AI fields) × 100
- Target: 30-40%

**Cycle Time:**
- Baseline: Time existing manual process (estimate: 45 min)
- AI-Assisted: Time from "Create Order" click to VBELN received
- Qualitative: User survey question: "Was this faster than manual?"

**First-Time-Right:**
- Count: Orders posted successfully on 1st BAPI/IDoc attempt
- Calculate: (Success on 1st attempt / Total attempts) × 100
- Baseline measurement (no target yet)

**User Satisfaction:**
- 5-question survey (1-5 scale):
  1. How easy was it to use the AI agent?
  2. How much time did it save you?
  3. How much do you trust the AI suggestions?
  4. How likely are you to use this in production?
  5. Overall satisfaction with the POV?
- Target: Average ≥3.5/5

---

## Dependencies

**Blocked By:** All Epic 1 and Epic 2 stories complete
**Blocks:** POV Decision (SCALE / ITERATE / STOP)

---

## Notes

This is the FINAL VALIDATION before POV decision. Honest metrics are critical.
If acceptance rate is 25%, don't round up to 30% - report 25% and decide based on reality.
EOF
)

create_issue "UAT Sprint: Week 7-8 Testing & Metrics" "$UAT_BODY" "uat,priority/critical,size/L" "Sprint 4 - UAT (Week 7-8)"

echo ""
echo "========================================"
echo "GitHub Project Setup Complete!"
echo "========================================"
echo ""
echo "Summary:"
echo "--------"
echo "✅ Labels created (17 labels)"
echo "✅ Milestones created (5 milestones)"
echo "✅ Issues created:"
echo "   - 1 Sprint 0 checklist"
echo "   - 10 Technical Enablers (TE-2, TE-3, TE-4, TE-5, TE-6, TE-8, TE-10, TE-12, TE-14, TE-15)"
echo "   - 7 User Stories (3 in Epic 1, 4 in Epic 2)"
echo "   - 1 UAT Sprint meta-issue"
echo "   Total: 19 issues"
echo ""
echo "Next Steps:"
echo "-----------"
echo "1. View all issues: gh issue list --repo $REPO_FULL"
echo "2. Create GitHub Project manually:"
echo "   - Go to: https://github.com/$REPO_OWNER?tab=projects"
echo "   - Click 'New Project' → 'Board' view"
echo "   - Name: RRPS Lead-to-Cash POV (8-Week MVP)"
echo "   - Add custom fields: Epic (text), Size (select: S/M/L/XL), Sprint (text)"
echo "   - Add all issues to project"
echo "3. Configure issue dependencies in project board"
echo "4. Push this repo to GitHub: git push -u origin master"
echo ""
echo "Repository URL: https://github.com/$REPO_FULL"
echo ""
