# RRPS Lead-to-Cash POV: Project Timeline

**Project Duration:** Mid-November 2025 → February 2026 Go-Live
**Total Duration:** 14 weeks (8 weeks POV + 6 weeks production prep)

---

## Sprint Schedule

| Sprint | Duration | Dates | Focus | Stories | Key Deliverables |
|--------|----------|-------|-------|---------|------------------|
| **Sprint 0** | 2 weeks | **Nov 11-22, 2025** | Infrastructure Setup | 1 | Kailash SDK validated, CPI integrations tested, DataFlow alpha validated, Audit store ready |
| **Sprint 1** | 2 weeks | **Nov 18-29, 2025** | Epic 1: Opportunity Qualification | 3 | Sales Managers can search & filter opportunities with AI confidence scoring |
| **Sprint 2** | 2 weeks | **Dec 2-13, 2025** | Epic 2: Order Creation (Part 1) | 2 | Auto-retrieve data from 3 systems, AI populates 30-40% of fields |
| **Sprint 3** | 2 weeks | **Dec 16-27, 2025** | Epic 2: Order Creation (Part 2) | 2 | Submit orders to SAP, receive VBELN, full audit trail |
| **Sprint 4** | 2 weeks | **Jan 6-17, 2026** | UAT & Iteration | 1 | 10 test orders with 3-5 pilot users, feedback captured |
| **Holiday Break** | 1 week | **Dec 30 - Jan 3** | - | - | Team休息 |
| **POV Decision** | - | **Jan 20, 2026** | Scale/Iterate/Stop | - | Decision based on KPIs (30%+ acceptance rate, 5+ orders) |
| **Production Prep** | 4-6 weeks | **Jan 20 - Feb 28** | Scale-up activities | - | Full rollout to 20+ users, compliance features, metrics dashboard |
| **Go-Live** | - | **February 2026** | Production Deployment | - | Full production rollout |

---

## Milestone Details

### Sprint 0: Infrastructure Setup (Nov 11-22)
**Milestone:** https://github.com/FFOO6866/lead2cash/milestone/1
**Due:** November 22, 2025

**Critical Prerequisites:**
- [ ] PostgreSQL environment ready (Nov 11)
- [ ] SAP CPI sandbox access granted (Nov 11)
- [ ] Team allocated full-time (Nov 11-22)

**Week 1 (Nov 11-15):**
- Day 1-2: Kailash SDK installation + DataFlow alpha validation
- Day 3-5: CEC OData + IPAS clients testing

**Week 2 (Nov 18-22):**
- Day 1-3: MS5 BAPI + IDoc clients testing
- Day 4-5: Audit store setup + team knowledge transfer

**Success Criteria:**
- ✅ All CPI integrations working (response time < 5 sec)
- ✅ DataFlow alpha stable with 1000+ test transactions
- ✅ Team trained on Kailash SDK patterns

---

### Sprint 1: Epic 1 - Opportunity Qualification (Nov 18-29)
**Milestone:** https://github.com/FFOO6866/lead2cash/milestone/2
**Due:** November 29, 2025

**Stories:**
1. **Story 1.1** (Size S, 2-3 days): Search Opportunities by Customer/Product
2. **Story 1.2** (Size M, 4-5 days): Filter Opportunities by Readiness Criteria (AI scoring)
3. **Story 1.3** (Size S, 2-3 days): View AI Confidence Reasoning

**Week 1 (Nov 18-22):**
- Story 1.1: Complete search functionality
- Story 1.2: Start AI readiness agent implementation

**Week 2 (Nov 25-29):**
- Story 1.2: Complete AI scoring + filtering
- Story 1.3: Add reasoning view + override capability

**Success Criteria:**
- ✅ Sales Managers can find opportunities in < 2 sec
- ✅ AI confidence scores show for all opportunities
- ✅ Reasoning is human-readable with next steps

---

### Sprint 2: Epic 2 Part 1 - Data Retrieval & AI Validation (Dec 2-13)
**Milestone:** https://github.com/FFOO6866/lead2cash/milestone/3
**Due:** December 13, 2025

**Stories:**
1. **Story 2.1** (Size L, 5-6 days): Auto-Retrieve Order Data from Multiple Systems
2. **Story 2.2** (Size XL, 7-8 days): AI Agent Validates & Populates IDoc Fields ⭐ **CORE POV FEATURE**

**Week 1 (Dec 2-6):**
- Story 2.1: Complete parallel data retrieval from C4C, IPAS, SAP
- Story 2.2: Start AI orchestration agent development

**Week 2 (Dec 9-13):**
- Story 2.2: Complete field population with confidence scoring
- Story 2.2: Color-coded field validation (Green/Yellow/Red)
- Story 2.2: BAPI pre-validation integration

**Success Criteria:**
- ✅ Data retrieved from 3 systems within 5 seconds
- ✅ 30-40% of fields auto-filled (Green)
- ✅ Users can edit any field before submission

---

### Sprint 3: Epic 2 Part 2 - SAP Submission & Audit Trail (Dec 16-27)
**Milestone:** https://github.com/FFOO6866/lead2cash/milestone/4
**Due:** December 27, 2025

**Stories:**
1. **Story 2.3** (Size M, 4-5 days): Submit Order to SAP & Receive Confirmation
2. **Story 2.4** (Size S, 2-3 days): View Order Status & Audit Trail

**Week 1 (Dec 16-20):**
- Story 2.3: IDoc submission + VBELN receipt
- Story 2.3: Idempotency layer (no duplicate orders)

**Week 2 (Dec 23-27):**
- Story 2.4: Audit trail query interface
- Story 2.4: Field provenance tracking (AI vs. manual)
- End-to-end testing: Opportunity → VBELN

**Success Criteria:**
- ✅ VBELN received within 30 seconds
- ✅ Retry with same correlation_id returns existing VBELN (0 duplicates)
- ✅ 100% audit trail completeness

---

### Holiday Break (Dec 30 - Jan 3, 2026)
**No development activities.** Team休息.

---

### Sprint 4: UAT & Iteration (Jan 6-17, 2026)
**Milestone:** https://github.com/FFOO6866/lead2cash/milestone/5
**Due:** January 17, 2026

**Focus:** Validate Epic 1 + Epic 2 with 3-5 pilot users

**Week 1 (Jan 6-10):**
- Day 1: UAT kickoff with pilot users (training)
- Day 2-5: Users create 5 test orders
- Daily 15-min feedback sessions

**Week 2 (Jan 13-17):**
- Day 1-3: Users create 5 more test orders (total 10)
- Day 4: Bug fixes based on feedback
- Day 5: Final metrics collection + user survey

**Success Criteria:**
- ✅ **SCALE**: 5+ orders successful, 30%+ acceptance rate, 0 critical bugs → Proceed to production
- ⚠️ **ITERATE**: 2-4 orders successful, 20-29% acceptance → Extend POV by 4 weeks
- ❌ **STOP**: <2 orders successful, <20% acceptance → Redesign approach

---

## POV Decision Point (Jan 20, 2026)

**Meeting:** Executive review with stakeholders

**Decision Criteria:**

### ✅ SCALE (Proceed to Production Rollout)
- 5+ orders created successfully end-to-end (VBELN received)
- 30%+ acceptance rate (auto-filled fields unchanged by users)
- Qualitative cycle time improvement (users report "much faster")
- 0 critical bugs (no data loss, duplicates, corruption)
- Users eager to continue using the tool

**Next Steps if SCALE:**
- Secure 12-week production budget
- Add Epics 3-6 (Compliance, Billing, Metrics, Full UAT)
- Hire 2nd backend engineer
- Plan 50-user rollout for February

---

### ⚠️ ITERATE (Extend POV by 4 Weeks)
- 2-4 orders successful
- 20-29% acceptance rate
- Mixed user feedback (some value, many issues)
- 1-2 fixable critical bugs

**Next Steps if ITERATE:**
- Analyze low acceptance: AI quality? User training?
- Fix critical bugs (2 weeks)
- Rerun UAT with 5 more orders (2 weeks)
- Reassess at Week 12

---

### ❌ STOP (Redesign or Abandon)
- <2 orders successful
- <20% acceptance rate (users reject most AI suggestions)
- Cycle time no better than manual
- 3+ critical bugs or CPI integration unstable

**Next Steps if STOP:**
- Root cause analysis: AI quality, CPI integration, or user resistance?
- If CPI integration: Redesign integration layer, retry in 8 weeks
- If AI quality: Pivot to simpler automation (RPA-style, no LLM)
- If user resistance: Redesign UX, add more human-in-the-loop

---

## Production Prep Phase (Jan 20 - Feb 28, 2026)
**Duration:** 4-6 weeks (only if POV decision = SCALE)

**Week 1-2 (Jan 20 - Jan 31):**
- Epic 3: Compliance & Policy Enforcement (Stories 3.1-3.3)
- Epic 4: Billing Readiness & Invoice Automation (Stories 4.1-4.3)

**Week 3-4 (Feb 3 - Feb 14):**
- Epic 5: Metrics Dashboard (Stories 5.1-5.3)
- Epic 6: Full UAT with 20+ users

**Week 5-6 (Feb 17 - Feb 28):**
- Performance optimization & load testing
- User training for 50+ user rollout
- Production deployment preparation

---

## Go-Live: February 2026
**Milestone:** https://github.com/FFOO6866/lead2cash/milestone/7
**Target:** End of February 2026

**Rollout Plan:**
- Week 1 (Feb 17-21): Pilot group (10 users) in production
- Week 2 (Feb 24-28): Full rollout (50+ users)

**Production Success Criteria:**
- 60%+ acceptance rate (vs. 30-40% in POV)
- 35-45% cycle time reduction (45 min → 5-10 min)
- 15-20% improvement in first-time-right orders
- 99%+ traceability (correlation_id → VBELN)

---

## Key Milestones at a Glance

| Date | Milestone | Decision Point |
|------|-----------|----------------|
| **Nov 11, 2025** | POV Kickoff | Sprint 0 starts |
| **Nov 22, 2025** | Infrastructure Ready | ✅ Sprint 0 complete |
| **Nov 29, 2025** | Epic 1 Complete | Sales Managers can qualify opportunities |
| **Dec 13, 2025** | Epic 2 Part 1 Complete | AI auto-fills 30-40% of order fields |
| **Dec 27, 2025** | Epic 2 Part 2 Complete | Orders can be submitted to SAP |
| **Dec 30 - Jan 3** | Holiday Break | No development |
| **Jan 17, 2026** | UAT Complete | 10 test orders with pilot users |
| **Jan 20, 2026** | **POV DECISION** | ✅ SCALE / ⚠️ ITERATE / ❌ STOP |
| **Feb 28, 2026** | **GO-LIVE** | Production rollout (if SCALE) |

---

## Risk Mitigation & Buffers

### High-Risk Periods:
1. **Nov 11-15**: CPI integration testing (30% probability of sandbox downtime)
   - **Mitigation**: Schedule around SAP maintenance windows
   - **Buffer**: 2 extra days in Sprint 0

2. **Dec 2-13**: AI orchestration agent (TE-8) development
   - **Mitigation**: Start with rule-based fallback if LLM fails
   - **Buffer**: Extend Sprint 2 by 2 days if needed

3. **Dec 23-27**: Holiday week overlap
   - **Mitigation**: Complete critical Story 2.3 by Dec 20
   - **Buffer**: Story 2.4 is low-risk, can slip to Jan 6 if needed

### Built-in Buffers:
- Sprint 0 → Sprint 1 overlap: 1 week (Nov 18-22)
- Holiday break: 1 week (Dec 30 - Jan 3)
- POV Decision → Production Prep: 4-6 weeks flexibility

---

## Dependencies & Blockers

### Sprint 0 BLOCKS Everything:
- Epic 1 cannot start until TE-2 (CEC OData Client) validated
- Epic 2 cannot start until all CPI integrations (TE-2, TE-3, TE-5, TE-6, TE-12) validated
- UAT cannot start until audit store (TE-14) ready

### Critical Path:
```
Sprint 0 (Nov 11-22)
  ↓
Sprint 1 (Nov 18-29) - Epic 1
  ↓
Sprint 2 (Dec 2-13) - Epic 2 Part 1 ⭐ CORE POV FEATURE
  ↓
Sprint 3 (Dec 16-27) - Epic 2 Part 2
  ↓
Sprint 4 (Jan 6-17) - UAT
  ↓
POV Decision (Jan 20)
  ↓ (if SCALE)
Production Prep (Jan 20 - Feb 28)
  ↓
Go-Live (Feb 28)
```

---

## Team Allocation

### Sprint 0 (Nov 11-22):
- 1 Backend Engineer (full-time)
- 0.5 Integration Specialist (SAP CPI focus)

### Sprint 1-3 (Nov 18 - Dec 27):
- 1-2 Backend Engineers (full-time)
- 0.5 Integration Specialist (on-call for CPI issues)

### Sprint 4 - UAT (Jan 6-17):
- 1 Backend Engineer (bug fixes)
- 3-5 Pilot Users (Sales Managers + Sales Ops)

### Production Prep (Jan 20 - Feb 28):
- 2 Backend Engineers (full-time)
- 1 Frontend Developer (if UI needed)
- Change Management lead (user training)

---

## Communication Plan

**Weekly Standups:** Every Monday 10 AM (15 min)
- Sprint progress update
- Blocker identification
- Risk escalation

**Sprint Reviews:** End of each sprint (Friday 2 PM, 30 min)
- Demo completed stories
- Stakeholder feedback
- Adjust next sprint plan

**POV Decision Meeting:** January 20, 2026 (90 min)
- Present UAT results
- KPI analysis
- Executive decision: SCALE / ITERATE / STOP

**Go-Live Readiness Review:** February 21, 2026 (60 min)
- Production checklist review
- Rollout plan confirmation
- Support team readiness check

---

## Success Metrics (8-Week POV)

| KPI | POV Target | Production Target |
|-----|------------|-------------------|
| **Acceptance Rate** | 30-40% | ≥60% |
| **Cycle Time Reduction** | Qualitative improvement | 35-45% reduction (45→5-10 min) |
| **First-Time-Right** | Baseline measurement | +15-20% vs. baseline |
| **Successful Orders** | 5-10 orders | 50+ orders/week |
| **User Satisfaction** | ≥3.5/5 | ≥4.0/5 |
| **Traceability** | 98%+ | 99%+ |

---

## Document Status

**Version:** 1.0
**Last Updated:** October 10, 2025
**Next Review:** November 11, 2025 (POV Kickoff)

**Project Links:**
- **GitHub Project:** https://github.com/users/FFOO6866/projects/1
- **Repository:** https://github.com/FFOO6866/lead2cash
- **Requirements:** docs/requirements.md (v5.0)
