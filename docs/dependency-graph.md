# RRPS Lead-to-Cash POV: Dependency Graph

**Visual representation of story dependencies across all 6 epics**
**Date:** 2025-10-10

---

## Legend

- **→** : Depends on (blocks until complete)
- **[X pts]** : Story points
- **Week N** : Target completion week
- **CRITICAL PATH** : Stories on longest dependency chain

---

## Epic 1: Foundation & Integration (Weeks 1-2)

```
┌─────────────────────────────────────────────────────────────┐
│                    EPIC 1: FOUNDATION                        │
└─────────────────────────────────────────────────────────────┘

Week 1:
  1.1 Canonical Data Models [5 pts] ✅ COMPLETE
      │
      ├──→ 1.2 CEC OData Client [8 pts]
      ├──→ 1.3 MS5 BAPI Client [8 pts]
      ├──→ 1.4 MS5 IDoc Client [13 pts] ⚠️ CRITICAL PATH
      ├──→ 1.5 ArchiveLink Client [5 pts]
      ├──→ 1.6 IPAS Client [5 pts]
      ├──→ 1.7 Policy Catalog [8 pts]
      └──→ 1.8 Database Schema [8 pts]

Week 2:
  1.3 MS5 BAPI Client [8 pts]
      │
      └──→ 1.4 MS5 IDoc Client [13 pts] ⚠️ CRITICAL PATH
              (Depends on BAPI for validation)
```

### Epic 1 Output Dependencies:
- **1.1** → ALL Epic 2 stories (agents need models)
- **1.2** → 2.1 (Opportunity Assessment needs CEC)
- **1.3 + 1.4** → 2.2 (Sales Ops needs BAPI + IDoc) ⚠️ CRITICAL
- **1.5** → 2.3 (Due Diligence needs ArchiveLink)
- **1.6** → 2.4 (Data Mgmt needs IPAS)
- **1.7** → ALL Epic 2 stories (agents need policies/mappings)
- **1.8** → ALL Epic 2, 3 stories (agents need database)

---

## Epic 2: Agent Workflows (Weeks 3-6)

```
┌─────────────────────────────────────────────────────────────┐
│                  EPIC 2: AGENT WORKFLOWS                     │
└─────────────────────────────────────────────────────────────┘

Week 3-4:
  [1.1, 1.2, 1.6, 1.7, 1.8] → 2.1 Opportunity Assessment [8 pts]
                                   (Independent - can start early)

  [1.1, 1.6, 1.7, 1.8] → 2.4 Data Management [8 pts]
                              │
                              └──→ 2.2 Sales Ops [21 pts] ⚠️ CRITICAL PATH
                                       (Needs BOM normalization)

  [1.1, 1.5, 1.7, 1.8] → 2.3 Due Diligence [13 pts]
                              │
                              └──→ 2.2 Sales Ops [21 pts] ⚠️ CRITICAL PATH
                              │    (Needs DD checks)
                              │
                              └──→ 2.5 Financial Ops [8 pts]
                                   (DD re-check at billing)

Week 4-5:
  [1.1, 1.2, 1.3, 1.4, 1.6, 1.7, 1.8, 2.3, 2.4]
      → 2.2 Sales Ops Agent [21 pts] ⚠️ CRITICAL PATH
            (Orchestrator - most complex, depends on everything)
            │
            └──→ 2.6 Nexus Platform [8 pts]
                     (Needs all agents to expose via API/MCP)

  [1.1, 1.8, 2.3] → 2.5 Financial Ops [8 pts]
                         (Monitors billing readiness)

Week 5-6:
  [2.1, 2.2, 2.3, 2.4, 2.5] → 2.6 Nexus Multi-Channel Platform [8 pts]
                                   (Exposes all agents via API + MCP)
                                   │
                                   └──→ 4.1 AKS Deployment
                                        (Needs platform to deploy)

  [2.1, 2.2, 2.3, 2.4, 2.5] → 2.7-2.10 Error Handling, Logging,
                                        Retry, Performance [13 pts]
                                        (Cross-cutting concerns)
                                        │
                                        └──→ 5.1, 5.2 (UAT needs stable agents)
```

### Epic 2 Output Dependencies:
- **2.2** → 5.1, 6.1 (Sales Ops is primary workflow for UAT/pilot)
- **2.5** → 6.1, 6.2 (Financial Ops metrics for pilot)
- **2.6** → 4.1, 4.2 (Nexus needed for deployment)
- **2.7-2.10** → 5.1, 5.2 (Stable agents needed for UAT)

---

## Epic 3: Observability & Metrics (Weeks 3-6)

```
┌─────────────────────────────────────────────────────────────┐
│              EPIC 3: OBSERVABILITY & METRICS                 │
└─────────────────────────────────────────────────────────────┘

Week 3:
  [1.1, 1.8] → 3.1 Correlation ID Tracking [5 pts]
                    │
                    ├──→ 3.2 POV Metrics Instrumentation [8 pts]
                    ├──→ 3.3 Audit Trail & Provenance [8 pts]
                    └──→ 3.5 CPI Integration Observability [5 pts]

Week 4:
  [3.1, 1.1, 1.8, 2.1-2.5] → 3.2 POV Metrics Instrumentation [8 pts]
                                  (Needs agents to instrument)
                                  │
                                  └──→ 6.1, 6.2 (Metrics for pilot)

  [3.1, 1.1, 1.8] → 3.3 Audit Trail & Provenance [8 pts]
                         │
                         └──→ 6.3 (Audit evidence for decision pack)

Week 5:
  [3.1, 3.2, 2.1-2.5] → 3.4 Dashboards & Monitoring [8 pts]
                             │
                             └──→ 4.5 (Observability platform integration)

  [1.2, 1.3, 1.4, 1.5, 3.1] → 3.5 CPI Integration Observability [5 pts]
                                   │
                                   └──→ 5.2 (UAT needs CPI visibility)
```

### Epic 3 Output Dependencies:
- **3.1** → 3.2, 3.5, 6.1 (Correlation enables metrics + traceability)
- **3.2** → 6.1, 6.2 (Metrics instrumentation for pilot)
- **3.3** → 6.3 (Audit trail for decision pack evidence)
- **3.4** → 4.5 (Dashboards for observability platform)
- **3.5** → 5.2 (CPI observability for UAT)

---

## Epic 4: Deployment & Platform (Weeks 3-6)

```
┌─────────────────────────────────────────────────────────────┐
│              EPIC 4: DEPLOYMENT & PLATFORM                   │
└─────────────────────────────────────────────────────────────┘

Week 4:
  [2.6] → 4.1 AKS Deployment Manifests [13 pts]
               │
               ├──→ 4.2 CI/CD Pipeline [8 pts]
               ├──→ 4.3 Environment Management [8 pts]
               ├──→ 4.4 Security Hardening [13 pts]
               ├──→ 4.5 Observability Integration [8 pts]
               └──→ 4.6 Disaster Recovery [5 pts]

Week 5:
  [4.1] → 4.2 CI/CD Pipeline [8 pts]
               │
               ├──→ 4.3 Environment Management [8 pts]
               │         │
               │         └──→ 5.1, 5.2 (UAT environment needed)
               │
               └──→ 4.4 Security Hardening [13 pts]

  [4.1, 4.2] → 4.3 Environment Management [8 pts]
                    (DEV, QA, UAT, PROD setup)
                    │
                    └──→ 5.1, 5.2 (UAT needs UAT environment)

Week 6:
  [4.1, 4.3] → 4.4 Security Hardening [13 pts]
                    (Network, identity, audit)
                    │
                    └──→ 5.3, 6.4 (Security review before pilot)

  [3.4, 4.1] → 4.5 Observability Platform Integration [8 pts]
                    (Metrics export, log aggregation)

  [1.8, 4.1] → 4.6 Disaster Recovery & Backup [5 pts]
                    (Database backups, DR plan)
```

### Epic 4 Output Dependencies:
- **4.1** → 4.2-4.6 (Deployment foundation)
- **4.2** → 4.3, 4.4 (CI/CD for environments and security)
- **4.3** → 5.1, 5.2 (UAT environment needed)
- **4.4** → 5.3, 6.4 (Security approval needed)

---

## Epic 5: UAT & Validation (Weeks 7-8)

```
┌─────────────────────────────────────────────────────────────┐
│                 EPIC 5: UAT & VALIDATION                     │
└─────────────────────────────────────────────────────────────┘

Week 7:
  [2.1-2.5, 4.3] → 5.1 UAT Scenario Definition [8 pts]
                        │
                        └──→ 5.2 UAT Execution [13 pts] ⚠️ DECISION GATE
                                 │
                                 └──→ 6.1 (UAT sign-off for pilot)

  [2.1-2.5, 4.1] → 5.3 Performance Testing [8 pts]
                        (Load testing, latency validation)

  [4.4] → 5.4 Security Review [5 pts]
               │
               └──→ 6.1 (Security approval for pilot)

Week 8:
  [5.1, 4.3] → 5.2 UAT Execution [13 pts] ⚠️ DECISION GATE
                    (Sales/FinOps user testing)
                    │
                    ├──→ 6.1 (User sign-off for pilot)
                    └──→ 5.5 Evidence Capture Runbooks [5 pts]

  [5.2, 3.1-3.5] → 5.5 Evidence Capture Runbooks [5 pts]
                        (Pilot execution, metrics collection)
                        │
                        └──→ 6.1, 6.2 (Runbooks for pilot)
```

### Epic 5 Output Dependencies:
- **5.2** → 6.1 (UAT sign-off required for pilot) ⚠️ GO/NO-GO GATE
- **5.4** → 6.1 (Security approval required for pilot)
- **5.5** → 6.1, 6.2 (Runbooks for consistent pilot execution)

---

## Epic 6: POV Evaluation (Weeks 9-10)

```
┌─────────────────────────────────────────────────────────────┐
│                 EPIC 6: POV EVALUATION                       │
└─────────────────────────────────────────────────────────────┘

Week 9:
  [5.5] → 6.1 Baseline Data Collection [8 pts]
               (Historical order analysis)
               │
               └──→ 6.3 Metrics Comparison & Scorecard [5 pts]

  [5.2, 5.5] → 6.2 Pilot Execution [8 pts] ⚠️ CRITICAL PATH
                    (Live/near-live order processing)
                    │
                    └──→ 6.3 Metrics Comparison & Scorecard [5 pts]

Week 10:
  [6.1, 6.2] → 6.3 Metrics Comparison & Scorecard [5 pts]
                    (Baseline vs Pilot, Green/Amber/Red status)
                    │
                    └──→ 6.4 Decision Pack Creation [8 pts] 🎯 FINAL

  [6.3, 3.3, 5.2, 5.4] → 6.4 Decision Pack Creation [8 pts] 🎯 FINAL
                              (Executive summary, recommendation)
```

### Epic 6 Final Deliverable:
- **6.4 Decision Pack** → Board-ready document with scale/iterate/stop recommendation

---

## Critical Path Analysis

### Longest Dependency Chain (52 days individual, 10 weeks parallel):

```
WEEK 1-2: FOUNDATION
  1.1 Models [5 pts] ✅ COMPLETE
    → 1.4 IDoc Client [13 pts] (Weeks 1-2)

WEEK 3-5: AGENT DEVELOPMENT
    → 2.4 Data Mgmt [8 pts] (Week 3)
    → 2.3 Due Diligence [13 pts] (Week 3-4)
    → 2.2 Sales Ops [21 pts] ⚠️ MOST COMPLEX (Week 4-5)

WEEK 5-6: PLATFORM & OBSERVABILITY
    → 2.6 Nexus [8 pts] (Week 5)
    → 4.1 AKS Deployment [13 pts] (Week 5)
    → 4.3 Environment Mgmt [8 pts] (Week 5-6)

WEEK 7-8: UAT
    → 5.1 UAT Scenarios [8 pts] (Week 7)
    → 5.2 UAT Execution [13 pts] ⚠️ DECISION GATE (Week 7-8)
    → 5.5 Runbooks [5 pts] (Week 8)

WEEK 9-10: PILOT & EVALUATION
    → 6.2 Pilot Execution [8 pts] ⚠️ CRITICAL (Week 9)
    → 6.3 Scorecard [5 pts] (Week 10)
    → 6.4 Decision Pack [8 pts] 🎯 FINAL (Week 10)

TOTAL CRITICAL PATH: 136 story points across 10 weeks
```

---

## Parallel Workstreams

### Week 3-6 (4 parallel streams):

**Stream 1: Core Agents (Backend Developer)**
- 2.1, 2.2, 2.3, 2.4, 2.5, 2.7-2.10

**Stream 2: Observability (POV Analyst + Backend)**
- 3.1, 3.2, 3.3, 3.4, 3.5

**Stream 3: Platform (Platform Engineer)**
- 2.6, 4.1, 4.2, 4.3, 4.5, 4.6

**Stream 4: Security (Security Engineer)**
- 4.4, 5.4 (starts Week 6)

---

## Decision Gates (Go/No-Go Points)

### Gate 1: Week 2 End
**Criteria:** Epic 1 complete (all integrations working)
- [ ] CPI sandbox accessible
- [ ] BAPI simulate working
- [ ] IDoc posting working
- [ ] IPAS accessible
- [ ] Policies and mappings populated
**If FAIL:** Extend Week 1-2 by 1 week; delay Epics 2-4 start

### Gate 2: Week 6 End
**Criteria:** All agents + platform ready for UAT
- [ ] 5 agents implemented and tested (integration tests pass)
- [ ] Nexus platform operational
- [ ] UAT environment deployed
- [ ] Metrics instrumentation working
**If FAIL:** Extend Week 3-6 by 1 week; delay UAT

### Gate 3: Week 8 End ⚠️ CRITICAL
**Criteria:** UAT sign-off for pilot
- [ ] UAT scenarios executed successfully
- [ ] User feedback positive
- [ ] Critical bugs fixed
- [ ] Security review approved
**If FAIL:** Iterate on feedback; delay pilot by 1 week OR stop POV

### Gate 4: Week 10 End 🎯
**Criteria:** Decision pack complete
- [ ] Pilot executed (20-30 orders)
- [ ] Metrics scorecard generated
- [ ] Recommendation clear (scale/iterate/stop)
**If FAIL:** Extend by 1 week for decision pack completion

---

## Bottleneck Analysis

### Top 3 Bottlenecks:

1. **Story 1.4 (IDoc Client) [13 pts]**
   - Blocks Sales Ops Agent (most critical workflow)
   - Requires BAPI client (1.3) first
   - Complex: async, idempotent, CPI integration
   - **Mitigation:** Start Week 1; allocate senior backend dev

2. **Story 2.2 (Sales Ops Agent) [21 pts]**
   - Most complex agent (orchestrator)
   - Depends on 1.1-1.8, 2.3, 2.4
   - Critical for UAT and pilot
   - **Mitigation:** Start immediately after Epic 1; incremental testing

3. **Story 5.2 (UAT Execution) [13 pts]**
   - Decision gate for pilot
   - Depends on user availability
   - Unpredictable feedback/issues
   - **Mitigation:** Schedule UAT participants early; buffer time for fixes

---

## Work Allocation by Week

| Week | Epic 1 | Epic 2 | Epic 3 | Epic 4 | Epic 5 | Epic 6 | Total SP |
|------|--------|--------|--------|--------|--------|--------|----------|
| 1    | 26     | 0      | 0      | 0      | 0      | 0      | 26       |
| 2    | 29     | 0      | 0      | 0      | 0      | 0      | 29       |
| 3    | 0      | 21     | 13     | 0      | 0      | 0      | 34       |
| 4    | 0      | 29     | 13     | 13     | 0      | 0      | 55       |
| 5    | 0      | 21     | 8      | 21     | 0      | 0      | 50       |
| 6    | 0      | 18     | 0      | 21     | 0      | 0      | 39       |
| 7    | 0      | 0      | 0      | 0      | 21     | 0      | 21       |
| 8    | 0      | 0      | 0      | 0      | 13     | 0      | 13       |
| 9    | 0      | 0      | 0      | 0      | 0      | 16     | 16       |
| 10   | 0      | 0      | 0      | 0      | 0      | 5      | 5        |
| **Total** | **55** | **89** | **34** | **55** | **34** | **21** | **288** |

**Average per week:** 28.8 story points (sustainable with 2-3 developers)

---

## Quick Reference: Story Dependencies

```
NO DEPENDENCIES (Can start immediately):
- 1.1 Canonical Data Models ✅ COMPLETE

DEPENDS ON 1.1 ONLY:
- 1.2, 1.3, 1.4, 1.5, 1.6, 1.7, 1.8

DEPENDS ON EPIC 1 COMPLETE:
- 2.1, 2.2, 2.3, 2.4, 2.5
- 3.1, 3.2, 3.3, 3.4, 3.5

DEPENDS ON EPIC 2 COMPLETE:
- 2.6, 4.1, 4.2
- 5.1, 5.3

DEPENDS ON EPIC 2+3+4 COMPLETE:
- 5.2 (UAT) ⚠️ GATE

DEPENDS ON EPIC 5 COMPLETE:
- 6.1, 6.2 ⚠️ GATE

DEPENDS ON EPIC 6 (6.1+6.2) COMPLETE:
- 6.3, 6.4 🎯 FINAL
```

---

**Document Status:** Ready for Planning
**Next Steps:** Use this graph for sprint planning and resource allocation
**Owner:** POV Lead
