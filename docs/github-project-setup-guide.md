# GitHub Project Setup Guide

**Creating the RRPS Lead-to-Cash POV Project Board**
**Date:** 2025-10-10

---

## Overview

This guide provides step-by-step instructions for creating a GitHub Project board with all 38 user stories from the requirements breakdown.

---

## Project Setup

### Step 1: Create GitHub Project

1. Navigate to repository: `https://github.com/[org]/lead2cash`
2. Click **Projects** tab
3. Click **New Project**
4. Select **Board** view
5. Name: **RRPS Lead-to-Cash POV**
6. Description: **10-week POV for agentic lead-to-cash automation (Oct-Dec 2025)**

### Step 2: Configure Project Views

**View 1: By Epic (Default)**
- Group by: Epic (custom field)
- Sort by: Story ID

**View 2: By Week**
- Group by: Target Week (custom field)
- Sort by: Priority

**View 3: By Owner**
- Group by: Assignee
- Sort by: Story Points

**View 4: Critical Path**
- Filter: `is:critical-path`
- Sort by: Dependencies

---

## Custom Fields to Add

| Field Name | Type | Values |
|------------|------|--------|
| Story Points | Number | 1, 2, 3, 5, 8, 13, 21 |
| Epic | Select | Epic 1, Epic 2, Epic 3, Epic 4, Epic 5, Epic 6 |
| Target Week | Select | Week 1, Week 2, ..., Week 10 |
| Priority | Select | Critical, High, Medium, Low |
| Status | Select | Not Started, In Progress, Blocked, In Review, Done |
| Effort (Days) | Number | 0.5-5 |
| Critical Path | Checkbox | True/False |
| Decision Gate | Checkbox | True/False |

---

## Labels to Create

### Epic Labels:
- `epic-1-foundation` (Purple)
- `epic-2-agents` (Blue)
- `epic-3-observability` (Green)
- `epic-4-platform` (Orange)
- `epic-5-uat` (Yellow)
- `epic-6-evaluation` (Red)

### Type Labels:
- `type-integration` (Gray)
- `type-workflow` (Cyan)
- `type-platform` (Navy)
- `type-testing` (Lime)
- `type-documentation` (Pink)

### Priority Labels:
- `priority-critical` (Red)
- `priority-high` (Orange)
- `priority-medium` (Yellow)
- `priority-low` (Green)

### Status Labels:
- `blocked` (Red)
- `decision-gate` (Purple)
- `ready-for-review` (Blue)

---

## Issue Templates

### User Story Template

```markdown
## User Story

**As a** [role], **I want** [capability] **so that** [business value].

## Critical Prerequisites

- [ ] Prerequisite 1
- [ ] Prerequisite 2

## Ready Criteria

- [ ] Criterion 1
- [ ] Criterion 2

## Definition of Done

### Backend Setup & Validation
- [ ] Implementation task 1
- [ ] Implementation task 2
- [ ] Unit tests passing
- [ ] Integration tests passing

### Frontend Setup & Design System
- [ ] API endpoint documented
- [ ] Error responses standardized

### Development Infrastructure
- [ ] Environment configured
- [ ] Logging instrumented

## Success Criteria

- Success metric 1
- Success metric 2

## Decision Point

What question does completing this story answer?

## Technical Subtasks

- [ ] Subtask 1
- [ ] Subtask 2

## Metadata

- **Story Points:** X
- **Estimated Effort:** X days
- **Epic:** Epic N
- **Target Week:** Week N
- **Priority:** [Critical/High/Medium/Low]
- **Critical Path:** [Yes/No]
- **Decision Gate:** [Yes/No]

## Dependencies

**Blocks:**
- #XX (Story N.M)

**Blocked By:**
- #XX (Story N.M)

## References

- Requirements Breakdown: `docs/requirements-breakdown.md`
- ADR-NNN: `src/rrps_lead2cash/adr/NNN-title.md`
```

---

## All 38 Issues to Create

### Epic 1: Foundation & Integration (8 issues)

#### Issue #1: Story 1.1 - Canonical Data Models ✅
```yaml
Title: "[Epic 1.1] Canonical Data Models Implementation"
Labels: epic-1-foundation, type-integration, priority-critical
Story Points: 5
Effort: 1.5 days
Target Week: Week 1
Critical Path: Yes
Status: Done (models already exist)
```

#### Issue #2: Story 1.2 - CEC OData Client
```yaml
Title: "[Epic 1.2] SAP CPI Client - CEC OData Integration"
Labels: epic-1-foundation, type-integration, priority-critical
Story Points: 8
Effort: 3 days
Target Week: Week 1-2
Depends On: #1
Blocks: #9 (Story 2.1)
```

#### Issue #3: Story 1.3 - MS5 BAPI Client
```yaml
Title: "[Epic 1.3] SAP CPI Client - MS5 BAPI Integration"
Labels: epic-1-foundation, type-integration, priority-critical
Story Points: 8
Effort: 3 days
Target Week: Week 1-2
Depends On: #1
Blocks: #4, #10
```

#### Issue #4: Story 1.4 - MS5 IDoc Client ⚠️
```yaml
Title: "[Epic 1.4] SAP CPI Client - MS5 IDoc Integration"
Labels: epic-1-foundation, type-integration, priority-critical
Story Points: 13
Effort: 3.5 days
Target Week: Week 2
Critical Path: Yes
Depends On: #1, #3
Blocks: #10 (Story 2.2 - Sales Ops Agent)
```

#### Issue #5: Story 1.5 - ArchiveLink Client
```yaml
Title: "[Epic 1.5] SAP CPI Client - ArchiveLink Integration"
Labels: epic-1-foundation, type-integration, priority-high
Story Points: 5
Effort: 2 days
Target Week: Week 2
Depends On: #1
Blocks: #11 (Story 2.3)
```

#### Issue #6: Story 1.6 - IPAS Client
```yaml
Title: "[Epic 1.6] IPAS Configuration/BOM Client"
Labels: epic-1-foundation, type-integration, priority-critical
Story Points: 5
Effort: 2 days
Target Week: Week 2
Depends On: #1
Blocks: #9, #12
```

#### Issue #7: Story 1.7 - Policy Catalog
```yaml
Title: "[Epic 1.7] Policy Catalog & Field Mapping Registry"
Labels: epic-1-foundation, type-integration, priority-critical
Story Points: 8
Effort: 2.5 days
Target Week: Week 2
Depends On: #1
Blocks: #9-#13 (All agents)
ADR Required: ADR-002, ADR-003
```

#### Issue #8: Story 1.8 - Database Schema
```yaml
Title: "[Epic 1.8] Database Schema & Audit Store"
Labels: epic-1-foundation, type-integration, priority-critical
Story Points: 8
Effort: 2.5 days
Target Week: Week 2
Depends On: #1
Blocks: #9-#13, #19-#23
```

---

### Epic 2: Agent Workflows (10 issues)

#### Issue #9: Story 2.1 - Opportunity Assessment Agent
```yaml
Title: "[Epic 2.1] Opportunity Assessment Agent Workflow"
Labels: epic-2-agents, type-workflow, priority-high
Story Points: 8
Effort: 3 days
Target Week: Week 3
Depends On: #1, #2, #6, #7, #8
```

#### Issue #10: Story 2.2 - Sales Ops Agent ⚠️
```yaml
Title: "[Epic 2.2] Sales Ops Agent Workflow (Orchestrator)"
Labels: epic-2-agents, type-workflow, priority-critical
Story Points: 21
Effort: 5 days
Target Week: Week 4-5
Critical Path: Yes
Depends On: #1, #2, #3, #4, #6, #7, #8, #11, #12
Blocks: #29, #34
```

#### Issue #11: Story 2.3 - Due Diligence Agent
```yaml
Title: "[Epic 2.3] Due Diligence Agent Workflow"
Labels: epic-2-agents, type-workflow, priority-critical
Story Points: 13
Effort: 3.5 days
Target Week: Week 3-4
Depends On: #1, #5, #7, #8
Blocks: #10, #13
```

#### Issue #12: Story 2.4 - Data Management Agent
```yaml
Title: "[Epic 2.4] Data Management Agent Workflow"
Labels: epic-2-agents, type-workflow, priority-critical
Story Points: 8
Effort: 3 days
Target Week: Week 3
Depends On: #1, #6, #7, #8
Blocks: #10
```

#### Issue #13: Story 2.5 - Financial Ops Agent
```yaml
Title: "[Epic 2.5] Financial Ops Agent Workflow"
Labels: epic-2-agents, type-workflow, priority-high
Story Points: 8
Effort: 3 days
Target Week: Week 4
Depends On: #1, #8, #11
Blocks: #34, #35
```

#### Issue #14: Story 2.6 - Nexus Platform
```yaml
Title: "[Epic 2.6] Nexus Multi-Channel Platform Setup"
Labels: epic-2-agents, type-platform, priority-critical
Story Points: 8
Effort: 2.5 days
Target Week: Week 5
Depends On: #9-#13
Blocks: #24, #25
```

#### Issue #15-18: Stories 2.7-2.10 - Error Handling, Logging, Retry, Performance
```yaml
Title: "[Epic 2.7-2.10] Agent Error Handling, Logging, Retry, Performance"
Labels: epic-2-agents, type-workflow, priority-high
Story Points: 13
Effort: 4 days
Target Week: Week 5-6
Depends On: #9-#13
Blocks: #29, #30
ADR Required: ADR-004
```

---

### Epic 3: Observability & Metrics (5 issues)

#### Issue #19: Story 3.1 - Correlation ID Tracking
```yaml
Title: "[Epic 3.1] Correlation ID Tracking"
Labels: epic-3-observability, type-platform, priority-critical
Story Points: 5
Effort: 1.5 days
Target Week: Week 3
Depends On: #1, #8
Blocks: #20, #23, #34
```

#### Issue #20: Story 3.2 - POV Metrics Instrumentation
```yaml
Title: "[Epic 3.2] POV Metrics Instrumentation"
Labels: epic-3-observability, type-platform, priority-critical
Story Points: 8
Effort: 2.5 days
Target Week: Week 4
Depends On: #1, #8, #19, #9-#13
Blocks: #34, #35
ADR Required: ADR-005
```

#### Issue #21: Story 3.3 - Audit Trail & Provenance
```yaml
Title: "[Epic 3.3] Audit Trail & Provenance Capture"
Labels: epic-3-observability, type-platform, priority-critical
Story Points: 8
Effort: 2 days
Target Week: Week 4
Depends On: #1, #8, #19
Blocks: #36
ADR Required: ADR-006
```

#### Issue #22: Story 3.4 - Dashboards & Monitoring
```yaml
Title: "[Epic 3.4] Dashboards & Monitoring"
Labels: epic-3-observability, type-platform, priority-medium
Story Points: 8
Effort: 2 days
Target Week: Week 5
Depends On: #19, #20, #9-#13
```

#### Issue #23: Story 3.5 - CPI Integration Observability
```yaml
Title: "[Epic 3.5] CPI Integration Observability"
Labels: epic-3-observability, type-integration, priority-high
Story Points: 5
Effort: 1.5 days
Target Week: Week 5
Depends On: #2-#5, #19
Blocks: #30
```

---

### Epic 4: Deployment & Platform (6 issues)

#### Issue #24: Story 4.1 - AKS Deployment
```yaml
Title: "[Epic 4.1] AKS Deployment Manifests"
Labels: epic-4-platform, type-platform, priority-critical
Story Points: 13
Effort: 3 days
Target Week: Week 5
Depends On: #14
Blocks: #25-#28
```

#### Issue #25: Story 4.2 - CI/CD Pipeline
```yaml
Title: "[Epic 4.2] CI/CD Pipeline"
Labels: epic-4-platform, type-platform, priority-critical
Story Points: 8
Effort: 2.5 days
Target Week: Week 5
Depends On: #24
Blocks: #26, #27
```

#### Issue #26: Story 4.3 - Environment Management
```yaml
Title: "[Epic 4.3] Environment Management (DEV, QA, UAT, PROD)"
Labels: epic-4-platform, type-platform, priority-critical
Story Points: 8
Effort: 2 days
Target Week: Week 5-6
Depends On: #24, #25
Blocks: #29, #30
ADR Required: ADR-007
```

#### Issue #27: Story 4.4 - Security Hardening
```yaml
Title: "[Epic 4.4] Security Hardening"
Labels: epic-4-platform, type-platform, priority-critical
Story Points: 13
Effort: 3 days
Target Week: Week 6
Depends On: #24, #26
Blocks: #31, #37
```

#### Issue #28: Story 4.5 - Observability Integration
```yaml
Title: "[Epic 4.5] Observability Platform Integration"
Labels: epic-4-platform, type-platform, priority-medium
Story Points: 8
Effort: 2 days
Target Week: Week 6
Depends On: #22, #24
```

#### Issue #29: Story 4.6 - Disaster Recovery
```yaml
Title: "[Epic 4.6] Disaster Recovery & Backup"
Labels: epic-4-platform, type-platform, priority-medium
Story Points: 5
Effort: 1.5 days
Target Week: Week 6
Depends On: #8, #24
ADR Required: ADR-008
```

---

### Epic 5: UAT & Validation (5 issues)

#### Issue #30: Story 5.1 - UAT Scenarios
```yaml
Title: "[Epic 5.1] UAT Scenario Definition & Test Data"
Labels: epic-5-uat, type-testing, priority-critical
Story Points: 8
Effort: 2 days
Target Week: Week 7
Depends On: #9-#13, #26
Blocks: #31, #32
```

#### Issue #31: Story 5.2 - UAT Execution ⚠️
```yaml
Title: "[Epic 5.2] UAT Execution with Sales/FinOps"
Labels: epic-5-uat, type-testing, priority-critical, decision-gate
Story Points: 13
Effort: 3 days
Target Week: Week 7-8
Critical Path: Yes
Decision Gate: Yes
Depends On: #30, #26
Blocks: #34
```

#### Issue #32: Story 5.3 - Performance Testing
```yaml
Title: "[Epic 5.3] Performance & Load Testing"
Labels: epic-5-uat, type-testing, priority-high
Story Points: 8
Effort: 2.5 days
Target Week: Week 7
Depends On: #9-#13, #24
```

#### Issue #33: Story 5.4 - Security Review
```yaml
Title: "[Epic 5.4] Security Review & Penetration Testing"
Labels: epic-5-uat, type-testing, priority-critical
Story Points: 5
Effort: 2 days
Target Week: Week 7-8
Depends On: #27
Blocks: #34
```

#### Issue #34: Story 5.5 - Evidence Capture Runbooks
```yaml
Title: "[Epic 5.5] Evidence Capture & Runbook Creation"
Labels: epic-5-uat, type-documentation, priority-high
Story Points: 5
Effort: 1.5 days
Target Week: Week 8
Depends On: #31, #19-#23
Blocks: #35, #36
```

---

### Epic 6: POV Evaluation (4 issues)

#### Issue #35: Story 6.1 - Baseline Data Collection
```yaml
Title: "[Epic 6.1] Baseline Data Collection"
Labels: epic-6-evaluation, type-documentation, priority-critical
Story Points: 8
Effort: 2 days
Target Week: Week 9
Depends On: #34
Blocks: #37
```

#### Issue #36: Story 6.2 - Pilot Execution ⚠️
```yaml
Title: "[Epic 6.2] Pilot Execution"
Labels: epic-6-evaluation, type-testing, priority-critical, decision-gate
Story Points: 8
Effort: 2 days
Target Week: Week 9
Critical Path: Yes
Depends On: #31, #34
Blocks: #37
```

#### Issue #37: Story 6.3 - Metrics Scorecard
```yaml
Title: "[Epic 6.3] Metrics Comparison & Scorecard"
Labels: epic-6-evaluation, type-documentation, priority-critical
Story Points: 5
Effort: 1.5 days
Target Week: Week 10
Depends On: #35, #36
Blocks: #38
```

#### Issue #38: Story 6.4 - Decision Pack 🎯
```yaml
Title: "[Epic 6.4] Decision Pack Creation"
Labels: epic-6-evaluation, type-documentation, priority-critical, decision-gate
Story Points: 8
Effort: 2 days
Target Week: Week 10
Decision Gate: Yes
Depends On: #37, #21, #31, #33
```

---

## Milestones

### Milestone 1: Foundation Complete
- **Due:** End of Week 2
- **Issues:** #1-#8
- **Story Points:** 55
- **Criteria:** All integrations working, policies/mappings complete

### Milestone 2: Agents & Platform Complete
- **Due:** End of Week 6
- **Issues:** #9-#28
- **Story Points:** 178
- **Criteria:** All agents deployed to AKS, metrics instrumented

### Milestone 3: UAT Complete ⚠️
- **Due:** End of Week 8
- **Issues:** #29-#34
- **Story Points:** 39
- **Criteria:** UAT sign-off, security approval, runbooks ready

### Milestone 4: POV Complete 🎯
- **Due:** End of Week 10
- **Issues:** #35-#38
- **Story Points:** 21
- **Criteria:** Decision pack delivered with recommendation

---

## Project Automation Rules

### Rule 1: Auto-move to "In Progress"
- **Trigger:** Issue assigned
- **Action:** Move to "In Progress" column

### Rule 2: Auto-move to "Blocked"
- **Trigger:** Label `blocked` added
- **Action:** Move to "Blocked" column

### Rule 3: Auto-move to "In Review"
- **Trigger:** PR linked and ready for review
- **Action:** Move to "In Review" column

### Rule 4: Auto-move to "Done"
- **Trigger:** Issue closed and all checkboxes checked
- **Action:** Move to "Done" column

### Rule 5: Dependency Alert
- **Trigger:** Issue moved to "In Progress" but dependencies not "Done"
- **Action:** Add comment warning about dependencies

---

## Sprint Planning (2-week sprints)

### Sprint 1 (Weeks 1-2): Foundation
- **Goal:** Complete Epic 1 (all integrations)
- **Issues:** #1-#8
- **Story Points:** 55
- **Team:** Backend Developer (primary), Integration Lead

### Sprint 2 (Weeks 3-4): Core Agents
- **Goal:** Complete 4/5 agents, start observability
- **Issues:** #9-#13, #19-#21
- **Story Points:** 58
- **Team:** Backend Developer (primary), POV Analyst

### Sprint 3 (Weeks 5-6): Platform & Polish
- **Goal:** Deploy to AKS, complete all agents
- **Issues:** #14-#18, #22-#28
- **Story Points:** 77
- **Team:** Platform Engineer (primary), Backend Developer

### Sprint 4 (Weeks 7-8): UAT
- **Goal:** Complete UAT with user sign-off
- **Issues:** #29-#34
- **Story Points:** 39
- **Team:** QA Lead (primary), Security Engineer, Backend Developer

### Sprint 5 (Weeks 9-10): Pilot & Evaluation
- **Goal:** Execute pilot, deliver decision pack
- **Issues:** #35-#38
- **Story Points:** 21
- **Team:** POV Analyst (primary), POV Lead

---

## Dashboard Queries

### Critical Path View
```
is:open label:priority-critical
```

### Blocked Issues
```
is:open label:blocked
```

### Ready to Start (no blockers)
```
is:open -linked:issue
```

### This Week (Week N)
```
is:open "Target Week:Week N"
```

### By Epic
```
is:open label:epic-1-foundation
is:open label:epic-2-agents
is:open label:epic-3-observability
is:open label:epic-4-platform
is:open label:epic-5-uat
is:open label:epic-6-evaluation
```

---

## Velocity Tracking

### Story Points per Week (Target):
- **Weeks 1-2:** 27.5 SP/week (Epic 1)
- **Weeks 3-6:** 35 SP/week (Epics 2-4 parallel)
- **Weeks 7-8:** 20 SP/week (UAT)
- **Weeks 9-10:** 10.5 SP/week (Pilot)

### Team Velocity Assumptions:
- **1 Backend Developer:** 15-20 SP/week
- **1 Platform Engineer:** 10-15 SP/week
- **1 Integration Lead:** 8-10 SP/week
- **Team Total:** 33-45 SP/week

---

## Communication Plan

### Daily Standups:
- **Time:** 9:00 AM daily
- **Format:** What I did, what I'm doing, blockers
- **Duration:** 15 minutes

### Weekly Sprint Planning:
- **Time:** Monday 10:00 AM
- **Format:** Review backlog, assign issues, commit to sprint
- **Duration:** 1 hour

### Bi-Weekly Sprint Review/Retro:
- **Time:** Friday 2:00 PM (end of 2-week sprint)
- **Format:** Demo completed stories, retrospective
- **Duration:** 1.5 hours

### Decision Gate Reviews:
- **Gate 1 (Week 2):** Epic 1 complete - go/no-go for Epics 2-4
- **Gate 2 (Week 6):** Agents complete - go/no-go for UAT
- **Gate 3 (Week 8):** UAT complete - go/no-go for pilot
- **Gate 4 (Week 10):** Decision pack - scale/iterate/stop

---

## Next Steps

1. **Create GitHub Project** using this guide
2. **Create all 38 issues** with metadata
3. **Set up milestones** with due dates
4. **Configure automation rules**
5. **Assign initial issues** to Sprint 1
6. **Schedule Sprint 1 kickoff** (Week 1 start)

---

**Document Status:** Ready for Project Creation
**Owner:** POV Lead
**Tools Needed:** GitHub Project, Issue Templates
