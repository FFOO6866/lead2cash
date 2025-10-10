# GitHub Project Setup Guide - RRPS Lead-to-Cash POV

This document describes the complete GitHub project structure for the 8-week RRPS Lead-to-Cash POV based on requirements.md v5.0.

## Quick Start

### Prerequisites

1. **Install GitHub CLI:** https://cli.github.com/
2. **Authenticate:** `gh auth login`
3. **Update repository owner:** Edit `scripts/setup-github-project.ps1` and change `$REPO_OWNER = "fujif"` to your GitHub username

### Run Setup Script

```powershell
# Windows (PowerShell)
cd C:\Users\fujif\OneDrive\Documents\GitHub\lead2cash
.\scripts\setup-github-project.ps1
```

```bash
# Linux/Mac (Bash)
cd /path/to/lead2cash
bash scripts/setup-github-project.sh
```

The script will:
- Create GitHub repository (if needed)
- Create 17 labels
- Create 5 milestones
- Create 19 issues (Sprint 0, Technical Enablers, User Stories, UAT)

---

## Project Structure Overview

### Labels (17 total)

**Epic Labels:**
- `epic-1-qualification` (Green) - Epic 1: Opportunity Qualification
- `epic-2-order-creation` (Blue) - Epic 2: Fast Order Creation

**Size Labels:**
- `size/S` (Yellow) - Small (1-2 days)
- `size/M` (Orange) - Medium (3-5 days)
- `size/L` (Red-Orange) - Large (1-2 weeks)
- `size/XL` (Red) - Extra Large (2-4 weeks)

**Type Labels:**
- `user-story` (Purple) - User story
- `technical-enabler` (Blue) - Technical enabler/infrastructure
- `infrastructure` (Light Blue) - Infrastructure setup
- `bug` (Red) - Something isn't working
- `uat` (Gray) - UAT testing and feedback

**Priority Labels:**
- `priority/critical` (Red)
- `priority/high` (Red-Orange)
- `priority/medium` (Yellow)
- `priority/low` (Green)

**Status Labels:**
- `blocked` (Red-Orange) - Blocked by dependency
- `in-progress` (Blue) - Currently in progress
- `review` (Yellow) - In review
- `done` (Green) - Completed

---

### Milestones (5 total)

| Milestone | Duration | Focus | Due Date |
|-----------|----------|-------|----------|
| Sprint 0 - Infrastructure (Week 0-2) | 2 weeks | Infrastructure setup, CPI validation, DataFlow alpha testing | +2 weeks from today |
| Sprint 1 - Epic 1 (Week 1-2) | 2 weeks | Opportunity Qualification - 3 stories | +2 weeks from today |
| Sprint 2 - Epic 2 Part 1 (Week 3-4) | 2 weeks | Order Creation - Stories 2.1-2.2 | +4 weeks from today |
| Sprint 3 - Epic 2 Part 2 (Week 5-6) | 2 weeks | Order Creation - Stories 2.3-2.4 | +6 weeks from today |
| Sprint 4 - UAT (Week 7-8) | 2 weeks | User Acceptance Testing with 10 test orders | +8 weeks from today |

---

### Issues (19 total)

#### Sprint 0: Infrastructure (1 issue)
- **Sprint 0: Infrastructure Setup Checklist**
  - Labels: infrastructure, priority/critical
  - Milestone: Sprint 0 - Infrastructure (Week 0-2)
  - Blocks: All Epic 1 and Epic 2 stories
  - Full DoD checklist with 60-80 hour estimate

#### Technical Enablers (10 issues)

| Issue | Labels | Milestone | Priority | Required By |
|-------|--------|-----------|----------|-------------|
| TE-2: CEC OData Client | technical-enabler, infrastructure, priority/critical | Sprint 0 | Critical | Story 1.1, 1.2, 1.3, 2.1 |
| TE-3: IPAS Client | technical-enabler, infrastructure, priority/high | Sprint 0 | High | Story 2.1 |
| TE-4: Opportunity Readiness Agent (Kaizen) | technical-enabler, priority/high, epic-1-qualification | Sprint 1 | High | Story 1.2, 1.3 |
| TE-5: MS5 BAPI Client (BAPI_SALESORDER_SIMULATE) | technical-enabler, infrastructure, priority/critical | Sprint 0 | Critical | Story 2.2 |
| TE-6: MS5 IDoc Client (ORDERS05 Submission) | technical-enabler, infrastructure, priority/critical | Sprint 0 | Critical | Story 2.3 |
| TE-8: Order Orchestration Agent (Kaizen) | technical-enabler, priority/critical, epic-2-order-creation | Sprint 2 | Critical | Story 2.2 |
| TE-10: Idempotency Layer | technical-enabler, infrastructure, priority/high | Sprint 3 | High | Story 2.3 |
| TE-12: SAP Customer Master Client | technical-enabler, infrastructure, priority/medium | Sprint 0 | Medium | Story 2.1 |
| TE-14: Audit Store (DataFlow + PostgreSQL) | technical-enabler, infrastructure, priority/critical | Sprint 0 | Critical | Story 1.3, 2.3, 2.4 |
| TE-15: Provenance Tracking | technical-enabler, infrastructure, priority/medium | Sprint 4 | Medium | Story 2.4 |

#### Epic 1: Opportunity Qualification (3 stories)

| Story | Title | Size | Labels | Milestone | Priority |
|-------|-------|------|--------|-----------|----------|
| 1.1 | Search Opportunities by Customer/Product | S | user-story, epic-1-qualification, size/S, priority/high | Sprint 1 | High |
| 1.2 | Filter Opportunities by Readiness Criteria | M | user-story, epic-1-qualification, size/M, priority/high | Sprint 1 | High |
| 1.3 | View AI Confidence Reasoning | S | user-story, epic-1-qualification, size/S, priority/medium | Sprint 1 | Medium |

#### Epic 2: Fast Order Creation (4 stories)

| Story | Title | Size | Labels | Milestone | Priority |
|-------|-------|------|--------|-----------|----------|
| 2.1 | Auto-Retrieve Order Data from Multiple Systems | L | user-story, epic-2-order-creation, size/L, priority/critical | Sprint 2 | Critical |
| 2.2 | AI Agent Validates & Populates IDoc Fields | XL | user-story, epic-2-order-creation, size/XL, priority/critical | Sprint 2 | Critical |
| 2.3 | Submit Order to SAP & Receive Confirmation | M | user-story, epic-2-order-creation, size/M, priority/critical | Sprint 3 | Critical |
| 2.4 | View Order Status & Audit Trail | S | user-story, epic-2-order-creation, size/S, priority/medium | Sprint 3 | Medium |

#### UAT Sprint (1 issue)
- **UAT Sprint: Week 7-8 Testing & Metrics**
  - Labels: uat, priority/critical, size/L
  - Milestone: Sprint 4 - UAT (Week 7-8)
  - Success criteria: 5+ orders, 30%+ acceptance, 0 critical bugs

---

## Issue Templates

Four issue templates are provided in `.github/ISSUE_TEMPLATE/`:

1. **user-story.md** - User story template with acceptance criteria, technical implementation, edge cases
2. **technical-enabler.md** - Technical enabler template with requirements, testing checklist
3. **bug.md** - Bug report template with reproduction steps, environment info
4. **uat-feedback.md** - UAT feedback template for capturing user testing results

---

## Dependency Mapping

### Sprint 0 Blocks Everything
Sprint 0 must complete before any user stories can begin. This is the CRITICAL PATH.

### Epic 1 Dependencies

```
Sprint 0 Complete
    ↓
TE-2 (CEC OData Client)
    ↓
Story 1.1: Search Opportunities
    ↓
TE-4 (Opportunity Readiness Agent)
    ↓
Story 1.2: Filter by Readiness ──→ Story 1.3: View AI Reasoning
                                        ↓
                                    TE-14 (Audit Store)
```

### Epic 2 Dependencies

```
Sprint 0 Complete
    ↓
TE-2, TE-3, TE-12 (Multi-System Clients)
    ↓
Story 2.1: Auto-Retrieve Order Data
    ↓
TE-5, TE-8 (BAPI + Order Orchestration Agent)
    ↓
Story 2.2: AI Populates IDoc Fields
    ↓
TE-6, TE-10, TE-14 (IDoc Client + Idempotency + Audit Store)
    ↓
Story 2.3: Submit Order to SAP
    ↓
TE-15 (Provenance Tracking)
    ↓
Story 2.4: View Order Status & Audit Trail
    ↓
UAT Sprint: Week 7-8
```

---

## GitHub Project Setup (Manual Steps)

After running the script, you'll need to manually create the GitHub Project:

### 1. Create Project

1. Go to: `https://github.com/{your-username}?tab=projects`
2. Click **"New Project"**
3. Select **"Board"** view
4. Name: **"RRPS Lead-to-Cash POV (8-Week MVP)"**
5. Description: **"Prove AI agents can deliver opportunity qualification + fast order creation"**

### 2. Add Custom Fields

Add these custom fields to the project:

| Field Name | Type | Options |
|------------|------|---------|
| Epic | Text | - |
| Size | Single Select | S, M, L, XL |
| Sprint | Text | - |
| Status | Single Select | Backlog, Ready, In Progress, Review, Done |
| Dependencies | Text | - |

### 3. Create Views

Create these project views:

**Sprint Board (Kanban):**
- Group by: Status
- Filter: Current sprint only
- Sort: Priority (critical → low)

**Epic View:**
- Group by: Epic
- Filter: All open issues
- Sort: Milestone, then priority

**Timeline View:**
- Layout: Timeline/Gantt
- Group by: Milestone
- Show: All issues with due dates

### 4. Add Issues to Project

Run this command to add all issues to your project:

```bash
# Get project ID first
gh project list --owner {your-username}

# Add all issues to project (replace PROJECT_NUMBER)
gh issue list --repo {your-username}/lead2cash --limit 100 --json number \
  --jq '.[].number' | \
  xargs -I {} gh project item-add PROJECT_NUMBER \
    --owner {your-username} \
    --url https://github.com/{your-username}/lead2cash/issues/{}
```

### 5. Configure Dependencies

In the GitHub Project UI, set these dependencies (use the Dependencies field):

- **All Epic 1 & 2 stories → Blocked by: Sprint 0**
- **Story 1.2 → Blocked by: Story 1.1, TE-4**
- **Story 1.3 → Blocked by: Story 1.2, TE-14**
- **Story 2.1 → Blocked by: TE-2, TE-3, TE-12**
- **Story 2.2 → Blocked by: Story 2.1, TE-5, TE-8**
- **Story 2.3 → Blocked by: Story 2.2, TE-6, TE-10, TE-14**
- **Story 2.4 → Blocked by: Story 2.3, TE-15**
- **UAT Sprint → Blocked by: All Epic 1 & 2 stories**

---

## POV Timeline Visualization

```
Week 0-2: Sprint 0 (Infrastructure Setup)
├── TE-2: CEC OData Client
├── TE-3: IPAS Client
├── TE-5: MS5 BAPI Client
├── TE-6: MS5 IDoc Client
├── TE-12: SAP Customer Master Client
└── TE-14: Audit Store (DataFlow validation)

Week 1-2: Sprint 1 (Epic 1: Opportunity Qualification)
├── TE-4: Opportunity Readiness Agent
├── Story 1.1: Search Opportunities
├── Story 1.2: Filter by Readiness
└── Story 1.3: View AI Reasoning

Week 3-4: Sprint 2 (Epic 2: Order Creation Part 1)
├── TE-8: Order Orchestration Agent
├── Story 2.1: Auto-Retrieve Order Data
└── Story 2.2: AI Populates IDoc Fields ← CORE POV FEATURE

Week 5-6: Sprint 3 (Epic 2: Order Creation Part 2)
├── TE-10: Idempotency Layer
├── Story 2.3: Submit Order to SAP
└── Story 2.4: View Order Status & Audit Trail

Week 7-8: Sprint 4 (UAT & Metrics)
├── TE-15: Provenance Tracking
└── UAT: 10 test orders, 3-5 pilot users
    ├── Target: 30-40% acceptance rate
    ├── Target: 5+ successful orders
    └── Decision: SCALE / ITERATE / STOP
```

---

## Success Metrics & KPIs

### POV Decision Criteria (Week 8)

**✅ PROCEED TO PRODUCTION (12-week rollout):**
- 5+ orders created successfully end-to-end
- 30%+ acceptance rate (auto-filled fields unchanged)
- Users report "much faster" than manual
- 0 critical bugs
- Users eager to continue

**⚠️ ITERATE (Extend POV by 4 weeks):**
- 2-4 orders successful
- 20-29% acceptance rate
- Mixed user feedback
- 1-2 fixable critical bugs

**❌ STOP POV:**
- <2 orders successful
- <20% acceptance rate
- No cycle time improvement
- 3+ critical bugs or CPI unstable

### Tracked Metrics

| Metric | Target | Measurement |
|--------|--------|-------------|
| Acceptance Rate | 30-40% | (Unchanged AI fields / Total AI fields) × 100 |
| Successful Orders | 5-10 | Count of VBELNs received in UAT |
| Cycle Time | Qualitative improvement | Users report "faster" than 45-min manual process |
| First-Time-Right | Baseline only | (Success on 1st attempt / Total attempts) × 100 |
| User Satisfaction | ≥3.5/5 | 5-question survey average |

---

## Troubleshooting

### Issue Creation Fails

**Error:** "Label not found"
- **Solution:** Run labels creation section of script again, or create labels manually via GitHub UI

**Error:** "Milestone not found"
- **Solution:** Create milestones manually via GitHub UI (Settings → Milestones)

### GitHub CLI Not Authenticated

**Error:** "gh: command not found"
- **Solution:** Install GitHub CLI: https://cli.github.com/

**Error:** "authentication required"
- **Solution:** Run `gh auth login` and follow prompts

### Repository Not Connected

**Error:** "remote origin already exists"
- **Solution:** Run `git remote set-url origin https://github.com/{your-username}/lead2cash.git`

---

## Next Steps After Setup

1. **Review all issues:** `gh issue list --repo {your-username}/lead2cash`
2. **Create GitHub Project** using manual steps above
3. **Add all issues to project**
4. **Configure dependencies** in project board
5. **Assign Sprint 0 to team** and begin infrastructure setup
6. **Push repository to GitHub:** `git push -u origin master`

---

## Contact & Support

- **Requirements Document:** `docs/requirements.md` (v5.0)
- **Issue Templates:** `.github/ISSUE_TEMPLATE/`
- **Setup Scripts:** `scripts/setup-github-project.ps1` (Windows) or `scripts/setup-github-project.sh` (Linux/Mac)

For questions about specific stories or technical enablers, refer to `docs/requirements.md` which contains full acceptance criteria, technical implementation details, and edge cases.

---

**Document Version:** 1.0
**Last Updated:** 2025-10-10
**Based On:** requirements.md v5.0 (Realistic 8-Week POV Scope)
