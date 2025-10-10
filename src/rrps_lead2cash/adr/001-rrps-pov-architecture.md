# ADR-001: RRPS POV Architecture & Integration Strategy

**Status:** Accepted
**Date:** 2025-10-10
**Context:** POV Proposal for Rolls-Royce Power Systems Lead-to-Cash Automation
**Deciders:** Integrum + RRPS Stakeholders

## Context and Problem Statement

RRPS operates an end-to-end lead-to-cash process spanning CEC (commercial opportunities), IPAS (configuration/BOM), and MS5/SAP ECC (order management/invoicing). The current state involves:

- Manual re-keying of data from CEC/IPAS into MS5
- Limited visibility into billing readiness prerequisites
- Lengthy cycle times from "order-ready" to "order posted"
- Risk of inconsistency and rework

A 10-week POV will evaluate whether agentic automation can reduce effort, improve first-time-right posting, and make billing readiness observable—without re-platforming existing systems.

## Decision Drivers

1. **Security & Compliance:** All workloads must run in RRPS Azure tenant; SAP access only via CPI
2. **Non-Disruptive:** No changes to master data, pricing models, or core business flows
3. **Auditability:** Full traceability required (correlation IDs → CPI → SAP documents)
4. **Measurable Value:** POV must produce baseline vs. pilot KPIs for scale/stop decision
5. **Existing Infrastructure:** Reuse CPI iFlows wherever possible; minimize new integration surfaces

## Considered Options

### Option 1: Direct SAP Integration (Rejected)
- **Pros:** Simpler integration, fewer hops
- **Cons:** Violates RRPS security posture (CPI is mandated route), breaks governance

### Option 2: Custom Orchestration Platform (Rejected)
- **Pros:** Full control over workflow logic
- **Cons:** High build effort, long-term maintenance burden, not aligned with Kailash SDK patterns

### Option 3: Kailash SDK + Nexus + CPI Mediation (SELECTED)
- **Pros:**
  - Complies with RRPS guardrails (AKS in tenant, CPI-only SAP access)
  - Multi-channel deployment (API for users, MCP for agent orchestration)
  - Workflow-based agent design using Core SDK patterns
  - Reuses proven Kailash SDK components (WorkflowBuilder, LocalRuntime)
- **Cons:** Requires careful mapping of CPI contracts to canonical models

## Decision Outcome

**Chosen Option:** Kailash SDK Core + Nexus multi-channel deployment with SAP CPI mediation

### Architecture Components

#### 1. Runtime Placement
- **Platform:** AKS (Azure Kubernetes Service) in RRPS tenant
- **Ingress:** API Gateway with TLS, OAuth2, rate limiting
- **State Services:** PostgreSQL (operational), Redis (cache), Object Storage (artefacts)

#### 2. Integration Model
All SAP access mediated through CPI with these patterns:

| System | Direction | Protocol | Use Case |
|--------|-----------|----------|----------|
| CEC | Read | OData via CPI | Opportunities, partners, terms, activities |
| MS5/ECC | Validate | BAPI via CPI | BAPI_SALESORDER_SIMULATE (sync) |
| MS5/ECC | Create | IDoc via CPI | ORDERS05 (async, durable) |
| MS5/ECC | Attach | Content Adapter | ArchiveLink/GOS for FAT/evidence |
| MS5/ECC | Events | Webhooks from CPI | Delivery/invoice milestones |
| IPAS | Read | Existing Proxy | Configuration/BOM (no new inbound) |

#### 3. Agentic Architecture (5 Agents as Kailash Workflows)

Each agent is a **Kailash Workflow** using `WorkflowBuilder`:

1. **Opportunity Assessment Agent**
   - Scores late-stage opportunities for "order-ready"
   - Flags gaps (partners, terms, dates, config health)
   - Data: CEC + IPAS status

2. **Sales Ops Agent (Orchestrator)**
   - Assembles order dossier (CEC + IPAS)
   - Calls Due Diligence + Data Mgmt
   - Proposes MS5 order with field-level provenance
   - Posts via CPI after user approval

3. **Due Diligence Agent**
   - Applies commercial/policy checks (Incoterms, partners, approvals)
   - Validates required artefacts (FAT, approvals)
   - Raises just-in-time tasks
   - Re-checks at billing milestones

4. **Data Management Agent**
   - Normalizes IPAS BOM → MS5 itemization
   - Maps material/UoM/plant codes
   - Flags mismatches, provides lookups

5. **Financial Ops Agent**
   - Monitors MS5 milestones/payment status
   - Triggers compliant invoice steps when prerequisites met
   - Records control evidence for A/R

#### 4. Canonical Data Contracts

**SalesOrderProposal** (agents → CPI):
```json
{
  "header": {
    "salesOrg": "1000", "distChannel": "10", "division": "00",
    "soldTo": "CUST123", "shipTo": "CUST123-S", "billTo": "CUST123-B",
    "incoterms": {"code": "DAP", "location": "Singapore"},
    "paymentTerms": "0001", "requestedDate": "2025-09-30"
  },
  "items": [{"line": 10, "material": "MAT-001", "qty": 2, "uom": "EA", "plant": "SG01"}],
  "attachments": [{"type": "FAT", "uri": "rrps://docs/abc123", "hash": "sha256:…"}],
  "provenance": [{"field": "soldTo", "source": "CEC.Account.Id"}],
  "meta": {"correlationId": "klx-2025-000123", "dryRun": true}
}
```

**OpportunityData** (CEC → agents):
- Account, partners (sold-to, ship-to, bill-to), terms, dates, stage, activities

**BOMData** (IPAS → agents):
- Configuration ID, line items (material, qty, UoM), config health, mismatches

**DDSummary** (Due Diligence → audit):
- Check results, required artefacts status, policy violations, tasks created

#### 5. Security & Traceability

**Network:**
- VNet isolation; IP allow-listing to CPI
- No inbound SAP exposure

**Identity:**
- OAuth2 for CEC OData
- CPI service accounts for ECC
- Secrets in Azure Key Vault

**Audit Trail:**
- Every transaction: `correlationId` → CPI `MessageId` → SAP `VBELN`
- Field-level provenance (copy/lookup/derivation per field)
- Immutable audit log for POV window

#### 6. Deployment Strategy (Nexus Multi-Channel)

**API Channel:**
- FastAPI endpoints for user-facing operations
- `/api/v1/opportunities/assess`
- `/api/v1/orders/propose`
- `/api/v1/orders/create`
- `/api/v1/due-diligence/validate`

**MCP Channel:**
- MCP server for agent-to-agent orchestration
- Tools: `assess_opportunity`, `create_order`, `validate_due_diligence`, `normalize_bom`, `trigger_invoice`

**Unified Session Management:**
- Nexus handles session/correlation across channels
- Single audit trail regardless of access method

### Consequences

#### Positive
- **Compliant:** Runs within RRPS security/integration posture
- **Observable:** End-to-end traceability via correlation IDs
- **Reusable:** CPI contracts can be versioned and reused
- **Flexible:** Nexus enables API (users) + MCP (agents) from single codebase
- **Proven Patterns:** Leverages Kailash SDK workflow patterns

#### Negative
- **CPI Dependency:** All SAP access routes through CPI (potential bottleneck)
- **Mapping Complexity:** Requires careful canonical model ↔ CPI contract mapping
- **Initial Setup:** Policy catalog, field mappings, test data preparation

#### Risks & Mitigations

| Risk | Mitigation |
|------|------------|
| CPI latency impacts UX | Async IDoc creates; simulate is sync but cached |
| CPI iFlow changes | Version contracts; change control for new iFlows |
| Test data quality | Use masked CEC/ECC records; synthetic FAT artefacts |
| Policy drift | Versioned policy pack; change audit trail |

## POV Success Criteria (from Proposal Chapter 3)

1. **Cycle Time:** Order-ready → posted reduces by 30–40%
2. **Acceptance Rate:** ≥70% of auto-filled fields accepted without edit
3. **First-Time-Right:** 15–20% improvement in posting success
4. **Artefact Readiness:** 80–90% of required docs present before billing
5. **Traceability:** 100% of transactions linked to CPI calls + SAP docs

## Implementation Plan (10 Weeks)

**Weeks 1-2:** Discover & Confirm
- Validate as-is flow, interfaces, KPI definitions
- Lock pilot order types, policy catalog

**Weeks 3-6:** Configure & Connect
- Build 5 agent workflows (Kailash SDK)
- Implement CPI integration clients
- Instrument metrics/audit

**Weeks 7-8:** UAT & Refine
- User testing with Sales/FinOps
- Evidence capture runbooks

**Weeks 9-10:** Pilot & Evidence Pack
- Collect baseline vs. pilot metrics
- Compile decision pack (scale/iterate/stop)

## References

- POV Proposal for Rolls-Royce Power Systems (Oct 2025)
- CLAUDE.md (Kailash SDK guidance)
- CPI Integration Suite documentation (RRPS internal)
- ISO/IEC TR 24030 (POV metrics framework)

## Notes

- All agent implementations must follow Kailash SDK patterns: `runtime.execute(workflow.build())`
- NO mocking in Tier 2-3 tests (real CPI sandbox/test system required)
- Policy pack to be versioned in `src/rrps_lead2cash/services/policy/`
- Field mappings documented in `docs/integration/field_mappings.md`
