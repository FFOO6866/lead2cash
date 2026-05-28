# Active Tasks - RRPS Lead-to-Cash

**Last Updated:** 2026-03-09
**Sprint/Milestone:** Sprint 3 (KYP Quality + Agent Hardening)
**Overall Progress:** ~85% of MVP scope

## 🔥 High Priority — KYP Data Quality (Current Sprint)

- [x] 🔥 Fix Aravo TPRMAssessment attribute errors (flat attrs, not nested)
- [x] 🔥 Fix SAP discovery/credit 3-tier fallback chain (CPISimulator → real CPI → force simulator)
- [x] 🔥 Fix CSS class mismatch (status-no_adverse_findings vs .passed)
- [x] 🔥 Fix triple-redundant status display → paragraph field type
- [x] 🔥 Fix Perplexity citation/source URL leak into display text
- [x] 🔥 Fix text overflow in KYP sections (overflow-wrap: break-word)
- [x] 🔥 Add sentence-aware truncation for assessment notes
- [x] 🔥 Fix status badge visibility (green/red/amber on dark bg)
- [x] 🔥 Fix Perplexity NO_ADVERSE_FINDINGS → UNABLE_TO_VERIFY for unknown companies (prompt + parser guard)
- [x] 🔥 Strip "Sources: None relevant/specific" artifacts from section text
- [ ] 🔥 Red team test KYP quality fixes (deploy + run R3/R5 subset)
- [ ] 🔥 Follow up on SAP CPI credentials with RRPS

## ⚡ Medium Priority

- [ ] ⚡ Create OpportunityAgent (Story 2b) - CEC & IPAS integration
- [ ] ⚡ Create DataManagementAgent (Story 3) - SAP field auto-population
- [ ] ⚡ Create FinancialOpsAgent (Story 4) - Order simulation
- [ ] ⚡ Enhance web chat UI features (https://rr.kailash.ai/chat)
- [ ] ⚡ Expand unit test coverage to 80%+
- [ ] ⚡ Sync GitHub issues with actual implementation status
- [ ] ⚡ Expand integration tests for implemented agents

## 📋 Low Priority

- [ ] 📋 End-to-end test implementation (depends on SAP credentials)
- [ ] 📋 KPI validation dashboard
- [ ] 📋 User acceptance testing preparation
- [ ] 📋 Documentation for all agents
- [ ] 📋 Performance benchmarking

## 🚫 Blocked (External Dependencies)

- [ ] 🚫 SAP CPI connectivity testing - Awaiting credentials from RRPS
- [ ] 🚫 Live BAPI/RFC testing against MS5 - Awaiting credentials
- [ ] 🚫 CEC/IPAS OData integration - Awaiting credentials
- [ ] 🚫 IDoc ORDERS05 posting - Awaiting credentials

## 📝 Notes

- **Web Chat Interface** is live at https://rr.kailash.ai/chat
- **Competitor Intelligence RAG system** is fully implemented (bonus feature)
- **Agent Registry** with graceful degradation is production-ready
- **FastAPI Gateway** with async runtime is deployed at rr.kailash.ai
- **KYP Report** fully functional with 3-phase structured output (SAP + Aravo + Perplexity)
- **Red Team R3-R5** all passing (100%, 78%, 100%) — see docs/ for results
- All SAP clients (CPI, MS5, CEC, IPAS) have structure but need credentials to test

## Implementation Summary

| Agent | Status | LOC | Notes |
|-------|--------|-----|-------|
| SalesOpsAgent | ✅ 100% | 832 | Web chat integrated |
| DueDiligenceAgent | ✅ 95% | 726 | KYP quality hardened |
| CompetitorIntelAgent | ✅ 100% | 508 | Bonus - fully working |
| MarineIntelAgent | ✅ 100% | ~400 | Marine news & opportunities |
| KnowledgeBaseAgent | ✅ 100% | ~350 | Product/engine KB |
| WebSearchAgent | ✅ 100% | ~300 | Perplexity-powered |
| AgentRegistry | ✅ 100% | 773 | Production-ready |
| OpportunityAgent | ⏳ 30% | - | Framework only |
| DataManagementAgent | ⏳ 10% | - | Not started |
| FinancialOpsAgent | ⏳ 10% | - | Not started |

## Recent Completions

- [x] ✅ KYP UNABLE_TO_VERIFY relevance guard + prompt fix — 2026-03-09
- [x] ✅ KYP paragraph field type + CSS visibility fix — 2026-03-09
- [x] ✅ KYP Aravo/SAP fallback chain + Perplexity text cleanup — 2026-03-09
- [x] ✅ Red Team R5 — 51/51 (100%) market/customer/product/competitor — 2026-02
- [x] ✅ Red Team R4 — KB enrichment, competitor intel fixes — 2026-02
- [x] ✅ Red Team R3 — 73/73 (100%) RBAC, session, security — 2026-01
- [x] ✅ Production deployment with API key injection — 2026-01-18
- [x] ✅ Web chat interface deployed (https://rr.kailash.ai/chat) — 2026-01-15
- [x] ✅ Competitor Intelligence RAG system — 2026-01-15
- [x] ✅ Agent registry resilience improvements — 2026-01-15
- [x] ✅ Docker deployment optimization — 2026-01-08
- [x] ✅ GitHub Actions CI/CD pipeline — 2025-12
- [x] ✅ FastAPI gateway implementation — 2025-12

## Sprint Metrics

| Metric | Value |
|--------|-------|
| Total Story Points | 99 pts |
| Completed Points | ~72 pts |
| Velocity | 73% |
| Blocked Points | ~20 pts (SAP) |

---

**Next Review:** After red team validation of KYP fixes
