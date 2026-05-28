# Comprehensive Test Plan: RRPS Lead-to-Cash User Stories

> **Version:** 1.0
> **Date:** 2026-02-04
> **Testing Strategy:** Kailash SDK 3-Tier Testing
> **System Under Test:** https://rr.kailash.ai (Chat API: /api/v1/chat)

---

## Test Plan Overview

This document defines the comprehensive test plan for the completed RRPS Lead-to-Cash user stories, following the Kailash SDK 3-tier testing strategy:

| Tier | Scope | Mocking Policy | Timeout | Location |
|------|-------|----------------|---------|----------|
| **Tier 1** | Unit Tests | Allowed for external services | <1s | `tests/unit/` |
| **Tier 2** | Integration Tests | **NO MOCKING** - real infrastructure | <5s | `tests/integration/` |
| **Tier 3** | E2E Tests | **NO MOCKING** - full system | <10s | `tests/e2e/` |

---

## Story 1.1: Enquire on Customer Profile

### User Story
> As a **Sales Rep**, I want to **enquire on a customer profile** so that I can **understand who they are, their fleet, our history with them, and current opportunities**.

### Acceptance Criteria

- **AC1.1.1**: System returns customer profile with company overview when queried by name
- **AC1.1.2**: System returns SAP customer data (ID, credit status) via MCP integration
- **AC1.1.3**: System shows installed base of MTU/Bergen equipment
- **AC1.1.4**: System displays open opportunities from CRM
- **AC1.1.5**: System identifies key contacts when available
- **AC1.1.6**: System shows relationship status (ACTIVE/INACTIVE/PROSPECT)
- **AC1.1.7**: Customer matching provides confidence score with match reasons

### Test Cases

| ID | Tier | Test Name | Input | Expected Output | Status |
|----|------|-----------|-------|-----------------|--------|
| **T1.1.01** | 1 | test_customer_profile_data_class | CustomerProfile object | Valid serialization to dict | PENDING |
| **T1.1.02** | 1 | test_customer_match_candidate_ranking | Multiple candidates | Correct confidence ordering | PENDING |
| **T1.1.03** | 1 | test_customer_match_confidence_levels | Various scores | Correct HIGH/MEDIUM/LOW/UNCERTAIN | PENDING |
| **T1.1.04** | 1 | test_customer_matcher_config_defaults | Config object | Valid default thresholds | PENDING |
| **T1.1.05** | 1 | test_customer_matcher_empty_candidates | Empty lists | Graceful handling, requires_confirmation=True | PENDING |
| **T1.1.06** | 1 | test_normalize_company_name | "PT Company Pte Ltd" | Normalized form without suffixes | PENDING |
| **T1.1.07** | 1 | test_customer_matcher_llm_response_parsing | JSON response | Parsed candidates list | PENDING |
| **T1.1.08** | 2 | test_customer_lookup_sap_integration | "Batam Fast Ferry" | Real SAP data via CPISimulator | PENDING |
| **T1.1.09** | 2 | test_customer_lookup_cross_reference_kyp | Company name | KYP + SAP cross-reference | PENDING |
| **T1.1.10** | 2 | test_customer_credit_status_retrieval | Customer ID | Real credit limit/exposure data | PENDING |
| **T1.1.11** | 2 | test_customer_matcher_with_real_sap_data | "Maersk" | High confidence match with SAP ID | PENDING |
| **T1.1.12** | 2 | test_installed_base_query | Customer ID | Engine list from SAP PM | PENDING |
| **T1.1.13** | 3 | test_e2e_customer_profile_full_query | "Tell me about Batam Fast Ferry" | Complete profile with all fields | PENDING |
| **T1.1.14** | 3 | test_e2e_customer_profile_via_chat_api | POST /api/v1/chat | Valid response with profile | PENDING |
| **T1.1.15** | 3 | test_e2e_customer_not_found | "Unknown XYZ Corp" | "Not found in SAP" message | PENDING |
| **T1.1.16** | 3 | test_e2e_customer_multiple_matches | "Fast Ferry" | Disambiguation prompt | PENDING |

### Test Implementation Notes

**Tier 1 (Unit):**
```python
# File: tests/unit/test_customer_matcher_agent.py
# Uses mocked CPI client and KYP processor
# Tests data classes, confidence calculation, name normalization
```

**Tier 2 (Integration):**
```python
# File: tests/integration/test_customer_profile_integration.py
# Requires: CPISimulator running (tests/utils/test-env up)
# NO MOCKING - uses real simulator connections
```

**Tier 3 (E2E):**
```python
# File: tests/e2e/test_customer_profile_e2e.py
# Tests via production API: https://rr.kailash.ai/api/v1/chat
# NO MOCKING - full system end-to-end
```

---

## Story 1.2: Review Purchase History & Projects

### User Story
> As a **Sales Rep**, I want to **review a customer's purchase history and past projects** so that I can **understand their buying patterns and identify upsell/cross-sell opportunities**.

### Acceptance Criteria

- **AC1.2.1**: System returns purchase history from SAP FI
- **AC1.2.2**: System shows revenue for last 12 months vs prior year
- **AC1.2.3**: System lists active contracts with values and expiry dates
- **AC1.2.4**: System identifies purchasing frequency trends (GROWING/STABLE/DECLINING)
- **AC1.2.5**: System suggests renewal/replacement opportunities based on contract expiry
- **AC1.2.6**: System shows open pipeline with expected close dates

### Test Cases

| ID | Tier | Test Name | Input | Expected Output | Status |
|----|------|-----------|-------|-----------------|--------|
| **T1.2.01** | 1 | test_purchase_history_data_model | History object | Valid fields with dates/amounts | PENDING |
| **T1.2.02** | 1 | test_trend_calculation_growing | Increasing revenue | GROWING status | PENDING |
| **T1.2.03** | 1 | test_trend_calculation_declining | Decreasing revenue | DECLINING status | PENDING |
| **T1.2.04** | 1 | test_contract_expiry_detection | Contract list | Sorted by expiry proximity | PENDING |
| **T1.2.05** | 1 | test_revenue_comparison_yoy | Two period data | Correct delta and percentage | PENDING |
| **T1.2.06** | 2 | test_purchase_history_sap_integration | Customer ID | Real transaction data | PENDING |
| **T1.2.07** | 2 | test_contract_data_retrieval | Customer ID | Real contract list from SAP SD | PENDING |
| **T1.2.08** | 2 | test_revenue_aggregation | Customer ID | Aggregated by time period | PENDING |
| **T1.2.09** | 2 | test_pipeline_opportunity_fetch | Customer ID | CEC opportunity data | PENDING |
| **T1.2.10** | 3 | test_e2e_purchase_history_query | "What has Penguin purchased?" | Full history with trends | PENDING |
| **T1.2.11** | 3 | test_e2e_contract_renewal_alert | Contract near expiry | Renewal suggestion | PENDING |
| **T1.2.12** | 3 | test_e2e_cross_sell_opportunity | Purchase pattern | Cross-sell recommendation | PENDING |

### Test Implementation Notes

**Tier 1 (Unit):**
```python
# Tests trend calculation algorithms
# Tests data model serialization
# Tests contract expiry sorting logic
```

**Tier 2 (Integration):**
```python
# Requires: SAP CPI Simulator, CEC Client
# Tests actual data retrieval and aggregation
```

**Tier 3 (E2E):**
```python
# Tests natural language queries about purchase history
# Validates AI synthesis of transaction data
```

---

## Story 1.3: Access Product Information & Insights

### User Story
> As a **Sales Rep**, I want to **access product information and competitive insights** so that I can **recommend the right MTU/Bergen engine for customer requirements**.

### Acceptance Criteria

- **AC1.3.1**: System provides MTU engine specifications (power, RPM, fuel options)
- **AC1.3.2**: System matches requirements to suitable engine series
- **AC1.3.3**: Product fit scoring uses deterministic rules (not ML)
- **AC1.3.4**: System compares at rating-level (apple-to-apple)
- **AC1.3.5**: System shows competitor alternatives when relevant
- **AC1.3.6**: System respects duty class requirements (ISO 8528)
- **AC1.3.7**: System filters by emission tier (IMO Tier II/III)

### Test Cases

| ID | Tier | Test Name | Input | Expected Output | Status |
|----|------|-----------|-------|-----------------|--------|
| **T1.3.01** | 1 | test_product_fit_scoring_power_match | 1200kW requirement | Power score >= 80 for matching engine | PENDING |
| **T1.3.02** | 1 | test_product_fit_scoring_duty_class | Medium-duty + 3000hrs | Correct duty class matching | PENDING |
| **T1.3.03** | 1 | test_product_fit_score_breakdown | Full requirements | All component scores present | PENDING |
| **T1.3.04** | 1 | test_customer_requirement_model | Requirement object | Valid field constraints | PENDING |
| **T1.3.05** | 1 | test_duty_class_inference_from_hours | 4000 hrs/year | HEAVY_DUTY inferred | PENDING |
| **T1.3.06** | 1 | test_emission_tier_filtering | IMO Tier III | Only compliant engines | PENDING |
| **T1.3.07** | 1 | test_recommendation_threshold_strong_fit | Score 92 | STRONG_FIT recommendation | PENDING |
| **T1.3.08** | 1 | test_recommendation_threshold_marginal | Score 45 | MARGINAL recommendation | PENDING |
| **T1.3.09** | 2 | test_kb_engine_lookup | "MTU 12V2000" | Real spec data from KB | PENDING |
| **T1.3.10** | 2 | test_kb_semantic_search | "ferry engine 1200kW" | Relevant engine matches | PENDING |
| **T1.3.11** | 2 | test_kb_competitor_mapping | MTU model | Mapped competitor ratings | PENDING |
| **T1.3.12** | 2 | test_rating_level_comparison | Two ratings | Apple-to-apple comparison | PENDING |
| **T1.3.13** | 3 | test_e2e_product_recommendation | "Which engine fits 1200kW ferry?" | MTU 12V2000 M96 recommendation | PENDING |
| **T1.3.14** | 3 | test_e2e_product_comparison | "Compare MTU 4000 vs Cummins QSK60" | Rating-level comparison table | PENDING |
| **T1.3.15** | 3 | test_e2e_product_specification | "What are MTU 8000 specs?" | Complete specification output | PENDING |
| **T1.3.16** | 3 | test_e2e_fuel_compatibility_query | "Dual fuel options for OSV" | Filtered engine list | PENDING |

### Test Implementation Notes

**Tier 1 (Unit):**
```python
# File: tests/unit/test_kb_product_fit_scoring.py
# Tests deterministic scoring algorithm
# NO ML - rule-based calculations
# Tests threshold classifications
```

**Tier 2 (Integration):**
```python
# File: tests/integration/test_kb_integration.py
# Requires: PostgreSQL with KB tables populated
# Tests real database queries and semantic search
```

**Tier 3 (E2E):**
```python
# File: tests/e2e/test_product_intel_e2e.py
# Tests ProductIntelAgent through chat API
# Natural language product queries
```

---

## Story 2.1: Receive Product & Configuration Suggestions

### User Story
> As a **Sales Rep**, I want to **receive product and configuration suggestions** so that I can **propose optimal solutions to customers based on their requirements**.

### Acceptance Criteria

- **AC2.1.1**: System accepts structured customer requirements
- **AC2.1.2**: System ranks engines by fit score
- **AC2.1.3**: System provides top N recommendations with rationale
- **AC2.1.4**: System identifies configuration options (twin/quad)
- **AC2.1.5**: System highlights positive factors and gaps
- **AC2.1.6**: System suggests alternatives if primary not available
- **AC2.1.7**: System considers physical constraints (weight/size) when provided

### Test Cases

| ID | Tier | Test Name | Input | Expected Output | Status |
|----|------|-----------|-------|-----------------|--------|
| **T2.1.01** | 1 | test_requirement_structuring | Natural language | CustomerRequirement object | PENDING |
| **T2.1.02** | 1 | test_rank_ratings_ordering | Multiple engines | Descending fit score order | PENDING |
| **T2.1.03** | 1 | test_find_best_fit_with_min_score | Requirements | Best engine above threshold | PENDING |
| **T2.1.04** | 1 | test_configuration_twin_recommendation | High power need | Twin engine suggestion | PENDING |
| **T2.1.05** | 1 | test_positive_factors_extraction | Good fit result | List of positive reasons | PENDING |
| **T2.1.06** | 1 | test_gap_factors_extraction | Marginal fit | List of deficiencies | PENDING |
| **T2.1.07** | 1 | test_alternative_suggestions | Primary unavailable | Alternative engine list | PENDING |
| **T2.1.08** | 2 | test_fit_scoring_with_real_kb | Full requirements | Scores from real KB data | PENDING |
| **T2.1.09** | 2 | test_recommendation_persistence | Fit result | Saved to kb_product_fit_results | PENDING |
| **T2.1.10** | 2 | test_multi_engine_ranking_integration | Ferry requirements | Top 5 MTU engines ranked | PENDING |
| **T2.1.11** | 3 | test_e2e_suggestion_request | "Suggest engine for 2400kW ferry" | Ranked recommendations | PENDING |
| **T2.1.12** | 3 | test_e2e_configuration_advice | "Best setup for 4800kW total" | Twin configuration suggestion | PENDING |
| **T2.1.13** | 3 | test_e2e_constraint_handling | "Max 3500kg engine" | Filtered by weight | PENDING |
| **T2.1.14** | 3 | test_e2e_follow_up_alternatives | "What if that's not available?" | Alternative recommendations | PENDING |

### Test Implementation Notes

**Tier 1 (Unit):**
```python
# Tests ProductFitScoringService methods
# Tests ranking algorithm
# Tests configuration logic
```

**Tier 2 (Integration):**
```python
# Tests against real KB data
# Tests database persistence of results
# Tests multi-engine queries
```

**Tier 3 (E2E):**
```python
# Tests conversational product suggestion
# Tests follow-up clarifications
# Tests constraint application
```

---

## Story 2.2: Consolidate Order Details

### User Story
> As a **Sales Rep**, I want to **consolidate order details from various sources** so that I can **prepare accurate quotes and orders for customers**.

### Acceptance Criteria

- **AC2.2.1**: System retrieves opportunity data from CEC
- **AC2.2.2**: System fetches product configuration from IPAS
- **AC2.2.3**: System combines customer data from SAP with opportunity data
- **AC2.2.4**: System validates customer credit status before order
- **AC2.2.5**: System identifies missing information for order completion
- **AC2.2.6**: System supports draft order creation workflow
- **AC2.2.7**: System displays consolidated view with all relevant fields

### Test Cases

| ID | Tier | Test Name | Input | Expected Output | Status |
|----|------|-----------|-------|-----------------|--------|
| **T2.2.01** | 1 | test_order_consolidation_model | Order data | Valid OrderConsolidation object | PENDING |
| **T2.2.02** | 1 | test_missing_field_detection | Incomplete order | List of missing fields | PENDING |
| **T2.2.03** | 1 | test_credit_validation_logic | Credit data | APPROVED/BLOCKED status | PENDING |
| **T2.2.04** | 1 | test_order_field_mapping | Source fields | Correct target mapping | PENDING |
| **T2.2.05** | 1 | test_data_merge_priority | Conflicting sources | Correct priority resolution | PENDING |
| **T2.2.06** | 2 | test_cec_opportunity_fetch | Opportunity ID | Real CEC data | PENDING |
| **T2.2.07** | 2 | test_ipas_product_config_fetch | Config ID | Real IPAS XML data | PENDING |
| **T2.2.08** | 2 | test_sap_customer_credit_check | Customer ID | Real credit status | PENDING |
| **T2.2.09** | 2 | test_multi_source_consolidation | Opp + Customer + Product | Merged result | PENDING |
| **T2.2.10** | 2 | test_order_draft_creation | Consolidated data | Draft order in MS5 | PENDING |
| **T2.2.11** | 3 | test_e2e_order_consolidation_query | "Consolidate order for OPP-123" | Full order details | PENDING |
| **T2.2.12** | 3 | test_e2e_credit_block_warning | Blocked customer | Credit warning displayed | PENDING |
| **T2.2.13** | 3 | test_e2e_missing_info_prompt | Incomplete data | List of required fields | PENDING |
| **T2.2.14** | 3 | test_e2e_draft_order_workflow | Complete data | Draft order confirmation | PENDING |

### Test Implementation Notes

**Tier 1 (Unit):**
```python
# Tests data consolidation logic
# Tests field mapping and validation
# Tests merge priority rules
```

**Tier 2 (Integration):**
```python
# Requires: CEC Client, IPAS Client, MS5 Client, CPISimulator
# Tests real API integrations
# Tests cross-system data retrieval
```

**Tier 3 (E2E):**
```python
# Tests full order consolidation workflow
# Tests credit validation flow
# Tests draft order creation
```

---

## Cross-Story Test Cases

### Multi-Agent Coordination Tests

| ID | Tier | Test Name | Description | Status |
|----|------|-----------|-------------|--------|
| **TX.01** | 2 | test_agent_registry_routing | Query routes to correct agent | PENDING |
| **TX.02** | 2 | test_multi_agent_orchestration | SalesOpsAgent coordinates multiple agents | PENDING |
| **TX.03** | 2 | test_knowledge_base_shared_tool | All agents access shared KB | PENDING |
| **TX.04** | 3 | test_e2e_multi_intent_query | "Tell me about customer and recommend product" | PENDING |
| **TX.05** | 3 | test_e2e_session_context_preservation | Multi-turn conversation maintains context | PENDING |

### API Contract Tests

| ID | Tier | Test Name | Description | Status |
|----|------|-----------|-------------|--------|
| **TA.01** | 2 | test_chat_api_request_format | POST /api/v1/chat accepts valid request | PENDING |
| **TA.02** | 2 | test_chat_api_response_format | Response matches orchestration_guide.md spec | PENDING |
| **TA.03** | 2 | test_chat_api_session_header | X-Session-ID header preserved | PENDING |
| **TA.04** | 2 | test_chat_api_clarification_response | Clarification response structure valid | PENDING |
| **TA.05** | 3 | test_e2e_streaming_endpoint | POST /api/v1/chat/stream SSE events | PENDING |

### Error Handling Tests

| ID | Tier | Test Name | Description | Status |
|----|------|-----------|-------------|--------|
| **TE.01** | 1 | test_empty_query_handling | Empty message returns error type | PENDING |
| **TE.02** | 1 | test_malformed_response_handling | Invalid LLM response handled gracefully | PENDING |
| **TE.03** | 2 | test_service_unavailable_fallback | Service down triggers fallback | PENDING |
| **TE.04** | 2 | test_timeout_handling | Slow response handled | PENDING |
| **TE.05** | 3 | test_e2e_graceful_degradation | Partial system failure returns partial results | PENDING |

---

## Test Infrastructure Requirements

### Tier 2 Integration Test Setup

```bash
# Start test infrastructure
cd tests/utils
./test-env up

# Verify services
./test-env status

# Expected services:
# - PostgreSQL (KB tables, marine intel)
# - CPISimulator (SAP CPI mock)
# - CEC Client (opportunity data)
# - IPAS Client (product config)
```

### Environment Variables Required

```bash
# Required for all tests
OPENAI_API_KEY=xxx

# Required for Tier 2/3 integration tests
DATABASE_URL=postgresql://...
PERPLEXITY_API_KEY=xxx
CPI_SIMULATOR_URL=http://localhost:8001

# Optional (for full E2E)
EODHD_API_KEY=xxx
NEWSAPI_KEY=xxx
```

### Test Execution Commands

```bash
# Tier 1: Unit tests only (fast)
pytest tests/unit/ -v --timeout=1

# Tier 2: Integration tests (requires infrastructure)
./tests/utils/test-env up
pytest tests/integration/ -v --timeout=5

# Tier 3: E2E tests (requires production-like environment)
pytest tests/e2e/ -v --timeout=10

# Full suite
pytest tests/ --timeout=10 -v
```

---

## Test Data Requirements

### Simulated Customers (CPISimulator)

| SAP ID | Company | Currency | Credit Limit | Utilization | UEN |
|--------|---------|----------|--------------|-------------|-----|
| 0000100001 | Batam Fast Ferry | SGD | 500K | 79% | 199901234A |
| 0000100002 | Maersk A/S | EUR | 10M | 30% | 25505933 |
| 0000100003 | Neptune Energy | EUR | 2M | 50% | - |
| 0000100004 | Blocked Marine | USD | 100K | 150% | BLOCKED |
| 0000100005 | Pacific Maritime | AUD | 50K | 0% | - |

### Knowledge Base Seed Data

- 43 high-speed engine models (MTU, Cummins, CAT, MAN, etc.)
- 18 engine series
- 9 manufacturers (1 RRPS, 8 competitors)
- Duty class ratings per ISO 8528

---

## Test Naming Conventions

```
test_<tier>_<story>_<component>_<scenario>

Examples:
- test_unit_customer_matcher_confidence_high
- test_integration_sap_customer_lookup_success
- test_e2e_chat_api_product_recommendation
```

---

## Acceptance Criteria Traceability Matrix

| AC ID | Test IDs | Coverage |
|-------|----------|----------|
| AC1.1.1 | T1.1.01, T1.1.08, T1.1.13 | Tier 1, 2, 3 |
| AC1.1.2 | T1.1.08, T1.1.10, T1.1.14 | Tier 2, 3 |
| AC1.1.3 | T1.1.12, T1.1.13 | Tier 2, 3 |
| AC1.1.4 | T1.1.13, T1.1.14 | Tier 3 |
| AC1.1.5 | T1.1.13 | Tier 3 |
| AC1.1.6 | T1.1.01, T1.1.11, T1.1.13 | Tier 1, 2, 3 |
| AC1.1.7 | T1.1.02, T1.1.03, T1.1.11 | Tier 1, 2 |
| AC1.2.1 | T1.2.01, T1.2.06, T1.2.10 | Tier 1, 2, 3 |
| AC1.2.2 | T1.2.05, T1.2.08, T1.2.10 | Tier 1, 2, 3 |
| AC1.2.3 | T1.2.04, T1.2.07, T1.2.10 | Tier 1, 2, 3 |
| AC1.2.4 | T1.2.02, T1.2.03, T1.2.10 | Tier 1, 3 |
| AC1.2.5 | T1.2.04, T1.2.11 | Tier 1, 3 |
| AC1.2.6 | T1.2.09, T1.2.10 | Tier 2, 3 |
| AC1.3.1 | T1.3.09, T1.3.15 | Tier 2, 3 |
| AC1.3.2 | T1.3.01, T1.3.10, T1.3.13 | Tier 1, 2, 3 |
| AC1.3.3 | T1.3.01-T1.3.08 | Tier 1 |
| AC1.3.4 | T1.3.11, T1.3.12, T1.3.14 | Tier 2, 3 |
| AC1.3.5 | T1.3.11, T1.3.14 | Tier 2, 3 |
| AC1.3.6 | T1.3.02, T1.3.05 | Tier 1 |
| AC1.3.7 | T1.3.06, T1.3.16 | Tier 1, 3 |
| AC2.1.1 | T2.1.01, T2.1.08 | Tier 1, 2 |
| AC2.1.2 | T2.1.02, T2.1.10 | Tier 1, 2 |
| AC2.1.3 | T2.1.03, T2.1.11 | Tier 1, 3 |
| AC2.1.4 | T2.1.04, T2.1.12 | Tier 1, 3 |
| AC2.1.5 | T2.1.05, T2.1.06, T2.1.11 | Tier 1, 3 |
| AC2.1.6 | T2.1.07, T2.1.14 | Tier 1, 3 |
| AC2.1.7 | T2.1.13 | Tier 3 |
| AC2.2.1 | T2.2.06, T2.2.11 | Tier 2, 3 |
| AC2.2.2 | T2.2.07, T2.2.11 | Tier 2, 3 |
| AC2.2.3 | T2.2.09, T2.2.11 | Tier 2, 3 |
| AC2.2.4 | T2.2.03, T2.2.08, T2.2.12 | Tier 1, 2, 3 |
| AC2.2.5 | T2.2.02, T2.2.13 | Tier 1, 3 |
| AC2.2.6 | T2.2.10, T2.2.14 | Tier 2, 3 |
| AC2.2.7 | T2.2.01, T2.2.11 | Tier 1, 3 |

---

## Revision History

| Version | Date | Author | Changes |
|---------|------|--------|---------|
| 1.0 | 2026-02-04 | Testing Specialist | Initial test plan creation |

---

## Related Documents

- **User Stories**: RRPS Lead-to-Cash GitHub Project
- **Architecture**: `docs/adr/ADR-002-autonomous-agent-redesign.md`
- **Testing Strategy**: Kailash SDK 3-Tier Testing Strategy
- **Output Formats**: `docs/guides/orchestration_guide.md`
- **Agent Guide**: `docs/guides/sales_intelligence_agent_guide.md`
- **Product Fit Guide**: `docs/guides/product_fit_guide.md`
- **Customer Intel Guide**: `docs/guides/customer_intel_guide.md`
