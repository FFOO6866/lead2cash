# ADR-002: Aravo KYP Direct REST Integration

**Date:** 2026-03-03
**Status:** Accepted
**Deciders:** RRPS Lead-to-Cash POV Team
**Context:** Epic 1 — Opportunity Qualification, Due Diligence Tier 1

---

## Context

The RRPS lead-to-cash process requires Know Your Partner (KYP) compliance verification before opportunities can be qualified and orders created. RRPS uses **Aravo** (a third-party risk management platform) to track partner onboarding, risk ratings, and review statuses.

Currently, there is an existing KYP implementation at `rr.kailash.ai` that exposes:
- `GET /api/v1/validation/kyp/{customer_name}` — Tier 1 KYP assessment
- `POST /api/v1/validation/validate` — Two-tier validation (KYP + SAP)
- `GET /api/v1/validation/customers` — List available customers
- `POST /api/v1/agents/due-diligence/validate` — DD agent validation
- `GET /api/v1/debug/cpi-kyp` — Debug endpoint

However, the Aravo integration was **returning errors because the integration was not completed**. This ADR documents the architecture for the proper implementation.

## Decision

### 1. Direct REST API (NOT via CPI)

Aravo is accessed via **direct HTTPS REST calls** from the agent platform, NOT through SAP CPI.

**Rationale:**
- Aravo is a standalone third-party SaaS platform, not part of the SAP landscape
- CPI is the mandated route for SAP systems only (CEC, MS5/ECC, IPAS)
- Direct calls reduce latency and dependency on CPI availability
- Aravo has its own REST API with Basic Auth — no need for CPI mediation

### 2. Two-Tier Validation Pattern

Customer validation follows a **two-tier architecture**:

| Tier | Source | Scope | Route |
|------|--------|-------|-------|
| **Tier 1: KYP** | Aravo REST API | Partner compliance, risk rating, onboarding status, E&C/S&EC reviews | Direct HTTPS |
| **Tier 2: SAP** | MS5/ECC via CPI | Master data completeness, credit limit, payment terms, sales area | Via CPI (TE-12) |

### 3. Integration Point: Epic 1 (Opportunity Qualification)

KYP assessment is performed during **opportunity qualification** (Story 1.2: Filter by Readiness), NOT during order creation.

**Flow:**
```
Opportunity Assessment Agent
    → Query CEC for opportunity data
    → Query Aravo for KYP assessment (Tier 1)
    → Evaluate readiness score (including KYP status)
    → Flag if BLOCKED/PENDING/CONDITIONAL
```

### 4. Aravo API Specifics

- **Endpoint:** `GET /aems/restservices/v5.0/reports/{report_id}`
- **Auth:** HTTP Basic Authentication (pre-encoded token from `ARAVO_AUTH_TOKEN` env var)
- **Response:** JSON report with 12-column schema (see below)
- **Matching:** Fuzzy name matching (exact → substring → SequenceMatcher)

**Column Schema:**
| Column | Field |
|--------|-------|
| c1 | Active? (boolean) |
| c2 | Third Party Identifier |
| c3 | Third Party Name |
| c4 | Proposer |
| c5 | Third Party Onboarding Status |
| c6 | Third Party Status |
| c7 | E&C Review Status |
| c8 | S&EC Review Status |
| c9 | Engagement Risk Rating |
| c10 | Engagement ID |
| c11 | Engagement Name |
| c12 | Partner Type |

### 5. KYP Decision Rules

| Condition | KYP Status | Blocking? |
|-----------|-----------|-----------|
| Onboarding = Rejected | BLOCKED | Yes |
| Third Party Status = Denied | BLOCKED | Yes |
| Risk Rating = Very High | BLOCKED | Yes |
| Onboarding ≠ Approved | PENDING | No |
| Third Party Status ≠ Approved | PENDING | No |
| Risk Rating = High | CONDITIONAL | No |
| E&C Review = Pending | CONDITIONAL | No |
| S&EC Review = Pending | CONDITIONAL | No |
| All checks pass | APPROVED | No |

## Consequences

### Positive
- Clear separation: Aravo (direct) vs. SAP (via CPI)
- Early warning: KYP issues surface during qualification, not at order time
- Matches production API pattern already deployed at rr.kailash.ai
- No dependency on CPI for compliance checks
- TTL-based report caching avoids redundant HTTP calls (default 5 min)
- Nearest-match suggestions returned on fuzzy match miss ("Did you mean...")
- Inactive records filtered out at parse time
- API key authentication on all validation endpoints (X-API-Key header)

### Negative
- Requires Aravo API credentials managed separately from SAP credentials
- Fuzzy name matching may produce false positives/negatives
- Report-based API fetches all rows — no server-side filtering by customer
- Two-tier validation returns CONDITIONAL (not APPROVED) until Tier 2 (TE-12) is wired

### Risks
- Aravo report may be stale (depends on ETL schedule; last ETL: 2025-10-28)
- SSL certificate issues may require `ARAVO_VERIFY_SSL=false` in some environments

## Configuration

Environment variables required:
```
ARAVO_BASE_URL=https://prod.aravo.co.uk
ARAVO_API_VERSION=v5.0
ARAVO_REPORT_ID=<report_id>
ARAVO_AUTH_TOKEN=<pre-encoded_basic_auth_token>
ARAVO_TIMEOUT=30
ARAVO_VERIFY_SSL=true
```

## Files Changed

| File | Change |
|------|--------|
| `src/rrps_lead2cash/core/models.py` | Added AravoEngagement, KYPAssessment, TwoTierValidation models, TwoTierValidationStatus enum |
| `src/rrps_lead2cash/config.py` | Added Aravo configuration (auth token, report ID, SSL, timeout) |
| `src/rrps_lead2cash/services/aravo_kyp_client.py` | New — Aravo REST client with TTL cache, fuzzy match, suggestions |
| `src/rrps_lead2cash/services/validation_service.py` | New — Two-tier validation orchestrator (CONDITIONAL when Tier 2 absent) |
| `src/rrps_lead2cash/core/gateway.py` | Added validation API routes with X-API-Key auth |
| `docs/requirements.md` | Added TE-16, updated Epic 1 stories |
