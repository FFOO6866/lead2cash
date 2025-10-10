---
name: Feature Story Template
about: Standard template for feature user stories
title: 'Story {{STORY_NUMBER}}: {{STORY_TITLE}}'
labels: feature, user-story
assignees: ''
---

# Story {{STORY_NUMBER}}: {{STORY_TITLE}}

**Story Points:** {{STORY_POINTS}}
**Estimated Effort:** {{EFFORT_ESTIMATE}} hours
**Priority:** {{PRIORITY}}
**Sprint:** {{SPRINT_NUMBER}}

---

## User Story

**As a** {{USER_ROLE}}
**I want** {{USER_GOAL}}
**So that** {{USER_BENEFIT}}

---

## Description

{{DETAILED_DESCRIPTION}}

---

## Ready Criteria

- [ ] Story 0 (Infrastructure) completed successfully
- [ ] Dependencies completed (see below)
- [ ] {{BACKEND_FRAMEWORK}} backend environment validated
- [ ] {{FRONTEND_FRAMEWORK}} frontend environment ready
- [ ] API contracts defined for this story
- [ ] Acceptance criteria reviewed and agreed upon
- [ ] Test data available

---

## Definition of Done

### Backend Implementation

- [ ] DataFlow models created using `@db.model` decorator
- [ ] All 9 auto-generated nodes validated:
  - [ ] Query node
  - [ ] Filter node
  - [ ] Create node
  - [ ] Update node
  - [ ] Delete node
  - [ ] Batch operations (if applicable)
  - [ ] Validation node
  - [ ] Transform node
  - [ ] Aggregate node (if applicable)
- [ ] Workflows built and tested: `runtime.execute(workflow.build())`
- [ ] Nexus deployment configured (API/CLI/MCP channels)
- [ ] Performance benchmarks met:
  - [ ] Queries: < {{QUERY_PERF_MS}}ms
  - [ ] Mutations: < {{MUTATION_PERF_MS}}ms
- [ ] Error handling implemented
- [ ] Backend tests written and passing (unit + integration)

### Frontend Implementation

- [ ] {{FRONTEND_FRAMEWORK}} components created
- [ ] Responsive design implemented (mobile/tablet/desktop)
- [ ] Adaptive widgets used where appropriate
- [ ] API integration complete
- [ ] Loading states handled
- [ ] Error states handled
- [ ] Empty states handled
- [ ] Frontend tests written and passing

### API Contract

- [ ] OpenAPI specification updated
- [ ] Contract tests passing
- [ ] Mock server updated
- [ ] API documentation generated

### Quality & Testing

- [ ] Unit tests: {{UNIT_TEST_COVERAGE}}% coverage minimum
- [ ] Integration tests written
- [ ] E2E tests for critical paths
- [ ] Performance tested with realistic data volumes
- [ ] Security review completed (if applicable)
- [ ] Accessibility standards met (WCAG 2.1 AA)

### Documentation

- [ ] API endpoints documented
- [ ] Component documentation updated
- [ ] User guide updated (if user-facing)
- [ ] Technical decisions logged
- [ ] Known limitations documented

### Deployment

- [ ] Code reviewed and approved
- [ ] Merged to main branch
- [ ] Deployed to staging environment
- [ ] Smoke tests passing in staging
- [ ] Ready for production deployment

---

## Technical Subtasks

### Backend ({{BACKEND_HOURS}}h)

1. **Data Models** ({{DATA_MODEL_HOURS}}h)
   - [ ] Define `@db.model` schemas
   - [ ] Add field validations
   - [ ] Create database migrations (if needed)

2. **Workflows** ({{WORKFLOW_HOURS}}h)
   - [ ] Build core workflows
   - [ ] Implement business logic
   - [ ] Add error handling

3. **Nexus Deployment** ({{NEXUS_DEPLOY_HOURS}}h)
   - [ ] Configure API endpoints
   - [ ] Set up CLI commands (if applicable)
   - [ ] Configure MCP integration (if applicable)

### Frontend ({{FRONTEND_HOURS}}h)

1. **UI Components** ({{UI_COMPONENT_HOURS}}h)
   - [ ] Create base components
   - [ ] Implement adaptive layouts
   - [ ] Add animations/transitions

2. **State Management** ({{STATE_MGMT_HOURS}}h)
   - [ ] Set up state containers
   - [ ] Implement data fetching
   - [ ] Add caching strategy

3. **Integration** ({{INTEGRATION_HOURS}}h)
   - [ ] Connect to API
   - [ ] Handle loading/error states
   - [ ] Add offline support (if applicable)

---

## Acceptance Criteria

- [ ] {{ACCEPTANCE_CRITERION_1}}
- [ ] {{ACCEPTANCE_CRITERION_2}}
- [ ] {{ACCEPTANCE_CRITERION_3}}
- [ ] {{ACCEPTANCE_CRITERION_4}}
- [ ] {{ACCEPTANCE_CRITERION_5}}

---

## Performance Requirements

- [ ] Page load time: < {{PAGE_LOAD_MS}}ms
- [ ] API response time: < {{API_RESPONSE_MS}}ms
- [ ] Supports {{CONCURRENT_USERS}} concurrent users
- [ ] Works with {{DATA_VOLUME}} records

---

## Dependencies

**Blocks:** Story {{BLOCKS_STORY_NUMBERS}}
**Blocked By:** Story {{BLOCKED_BY_STORY_NUMBERS}}
**Related:** Story {{RELATED_STORY_NUMBERS}}

---

## Test Scenarios

### Happy Path
1. {{HAPPY_PATH_SCENARIO_1}}
2. {{HAPPY_PATH_SCENARIO_2}}
3. {{HAPPY_PATH_SCENARIO_3}}

### Edge Cases
1. {{EDGE_CASE_1}}
2. {{EDGE_CASE_2}}
3. {{EDGE_CASE_3}}

### Error Handling
1. {{ERROR_SCENARIO_1}}
2. {{ERROR_SCENARIO_2}}
3. {{ERROR_SCENARIO_3}}

---

## UI/UX Mockups

{{MOCKUP_LINKS_OR_DESCRIPTIONS}}

---

## API Endpoints

### {{ENDPOINT_1_METHOD}} {{ENDPOINT_1_PATH}}
**Description:** {{ENDPOINT_1_DESCRIPTION}}
**Request:**
```json
{{ENDPOINT_1_REQUEST_EXAMPLE}}
```
**Response:**
```json
{{ENDPOINT_1_RESPONSE_EXAMPLE}}
```

### {{ENDPOINT_2_METHOD}} {{ENDPOINT_2_PATH}}
**Description:** {{ENDPOINT_2_DESCRIPTION}}
**Request:**
```json
{{ENDPOINT_2_REQUEST_EXAMPLE}}
```
**Response:**
```json
{{ENDPOINT_2_RESPONSE_EXAMPLE}}
```

---

## Notes & Decisions

_Use this section to track important decisions, blockers, and notes during implementation._

---

## References

- [Related Documentation]({{DOCS_URL}})
- [Design Specifications]({{DESIGN_URL}})
- [Technical Specifications]({{TECH_SPEC_URL}})
