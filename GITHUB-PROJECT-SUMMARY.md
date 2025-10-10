# GitHub Project Structure - RRPS Lead-to-Cash POV
## Complete Setup Summary

**Created:** 2025-10-10
**Status:** Ready for GitHub authentication and deployment
**Based On:** requirements.md v5.0 (8-Week MVP)

---

## What Has Been Created

### 1. Issue Templates (4 files)
Location: `.github/ISSUE_TEMPLATE/`

✅ **user-story.md** - User story template with:
- User story format (As a/I want/So that)
- Acceptance criteria checklist
- Technical implementation (workflow + nodes)
- Edge cases
- Dependencies section
- Definition of Done

✅ **technical-enabler.md** - Technical enabler template with:
- TE number and purpose
- Technical requirements
- Implementation details
- Acceptance criteria
- Testing checklist
- Risk register

✅ **bug.md** - Bug report template with:
- Reproduction steps
- Expected vs actual behavior
- Environment details
- Error logs
- Impact assessment

✅ **uat-feedback.md** - UAT feedback template with:
- Session details
- User quote capture
- Impact rating
- POV team response tracking

### 2. Setup Scripts (2 files)
Location: `scripts/`

✅ **setup-github-project.sh** (Linux/Mac)
- Bash script for Unix-based systems
- Creates labels, milestones, issues
- Color-coded output

✅ **setup-github-project.ps1** (Windows)
- PowerShell script for Windows
- Same functionality as bash version
- Windows-native date handling

### 3. Documentation
Location: `docs/`

✅ **github-project-setup.md** - Complete setup guide with:
- Quick start instructions
- Label/milestone/issue structure
- Dependency mapping
- Manual project setup steps
- POV timeline visualization
- Troubleshooting guide

---

## Project Structure Overview

### Labels (17 total)

| Category | Label | Color | Description |
|----------|-------|-------|-------------|
| **Epic** | epic-1-qualification | 0E8A16 (Green) | Epic 1: Opportunity Qualification |
| **Epic** | epic-2-order-creation | 1D76DB (Blue) | Epic 2: Fast Order Creation |
| **Size** | size/S | FBCA04 (Yellow) | Small (1-2 days) |
| **Size** | size/M | FFA500 (Orange) | Medium (3-5 days) |
| **Size** | size/L | D93F0B (Red-Orange) | Large (1-2 weeks) |
| **Size** | size/XL | B60205 (Red) | Extra Large (2-4 weeks) |
| **Type** | user-story | 5319E7 (Purple) | User story |
| **Type** | technical-enabler | 0052CC (Blue) | Technical enabler/infrastructure |
| **Type** | infrastructure | C5DEF5 (Light Blue) | Infrastructure setup |
| **Type** | bug | D73A4A (Red) | Something isn't working |
| **Type** | uat | EDEDED (Gray) | UAT testing and feedback |
| **Priority** | priority/critical | B60205 (Red) | Critical priority |
| **Priority** | priority/high | D93F0B (Red-Orange) | High priority |
| **Priority** | priority/medium | FBCA04 (Yellow) | Medium priority |
| **Priority** | priority/low | 0E8A16 (Green) | Low priority |
| **Status** | blocked | D93F0B (Red-Orange) | Blocked by dependency |
| **Status** | in-progress | 1D76DB (Blue) | Currently in progress |
| **Status** | review | FBCA04 (Yellow) | In review |
| **Status** | done | 0E8A16 (Green) | Completed |

### Milestones (5 total)

1. **Sprint 0 - Infrastructure (Week 0-2)**
   - Infrastructure setup, CPI validation, DataFlow alpha testing
   - Due: +2 weeks from script run date

2. **Sprint 1 - Epic 1 (Week 1-2)**
   - Opportunity Qualification - 3 stories
   - Due: +2 weeks from script run date

3. **Sprint 2 - Epic 2 Part 1 (Week 3-4)**
   - Order Creation - Stories 2.1-2.2
   - Due: +4 weeks from script run date

4. **Sprint 3 - Epic 2 Part 2 (Week 5-6)**
   - Order Creation - Stories 2.3-2.4
   - Due: +6 weeks from script run date

5. **Sprint 4 - UAT (Week 7-8)**
   - User Acceptance Testing with 10 test orders
   - Due: +8 weeks from script run date

### Issues (19 total)

#### Sprint 0 Infrastructure (1 issue)
- ✅ Sprint 0: Infrastructure Setup Checklist
  - **Labels:** infrastructure, priority/critical
  - **Milestone:** Sprint 0 - Infrastructure (Week 0-2)
  - **Blocks:** ALL Epic 1 and Epic 2 stories
  - **Effort:** 60-80 hours
  - **Full DoD:** Backend setup, CPI integration, audit store, DataFlow validation

#### Technical Enablers (10 issues)

1. ✅ **TE-2: CEC OData Client**
   - Labels: technical-enabler, infrastructure, priority/critical
   - Milestone: Sprint 0
   - Required By: Stories 1.1, 1.2, 1.3, 2.1

2. ✅ **TE-3: IPAS Client**
   - Labels: technical-enabler, infrastructure, priority/high
   - Milestone: Sprint 0
   - Required By: Story 2.1

3. ✅ **TE-4: Opportunity Readiness Agent (Kaizen)**
   - Labels: technical-enabler, priority/high, epic-1-qualification
   - Milestone: Sprint 1
   - Required By: Stories 1.2, 1.3

4. ✅ **TE-5: MS5 BAPI Client (BAPI_SALESORDER_SIMULATE)**
   - Labels: technical-enabler, infrastructure, priority/critical
   - Milestone: Sprint 0
   - Required By: Story 2.2

5. ✅ **TE-6: MS5 IDoc Client (ORDERS05 Submission)**
   - Labels: technical-enabler, infrastructure, priority/critical
   - Milestone: Sprint 0
   - Required By: Story 2.3

6. ✅ **TE-8: Order Orchestration Agent (Kaizen)**
   - Labels: technical-enabler, priority/critical, epic-2-order-creation
   - Milestone: Sprint 2
   - Required By: Story 2.2

7. ✅ **TE-10: Idempotency Layer**
   - Labels: technical-enabler, infrastructure, priority/high
   - Milestone: Sprint 3
   - Required By: Story 2.3

8. ✅ **TE-12: SAP Customer Master Client**
   - Labels: technical-enabler, infrastructure, priority/medium
   - Milestone: Sprint 0
   - Required By: Story 2.1

9. ✅ **TE-14: Audit Store (DataFlow + PostgreSQL)**
   - Labels: technical-enabler, infrastructure, priority/critical
   - Milestone: Sprint 0
   - Required By: Stories 1.3, 2.3, 2.4

10. ✅ **TE-15: Provenance Tracking**
    - Labels: technical-enabler, infrastructure, priority/medium
    - Milestone: Sprint 4
    - Required By: Story 2.4

#### Epic 1: Opportunity Qualification (3 stories)

11. ✅ **Story 1.1: Search Opportunities by Customer/Product**
    - Size: S | Labels: user-story, epic-1-qualification, priority/high
    - Milestone: Sprint 1
    - Dependencies: Sprint 0, TE-2

12. ✅ **Story 1.2: Filter Opportunities by Readiness Criteria**
    - Size: M | Labels: user-story, epic-1-qualification, priority/high
    - Milestone: Sprint 1
    - Dependencies: Story 1.1, TE-4

13. ✅ **Story 1.3: View AI Confidence Reasoning**
    - Size: S | Labels: user-story, epic-1-qualification, priority/medium
    - Milestone: Sprint 1
    - Dependencies: Story 1.2, TE-14

#### Epic 2: Fast Order Creation (4 stories)

14. ✅ **Story 2.1: Auto-Retrieve Order Data from Multiple Systems**
    - Size: L | Labels: user-story, epic-2-order-creation, priority/critical
    - Milestone: Sprint 2
    - Dependencies: Sprint 0, TE-2, TE-3, TE-12

15. ✅ **Story 2.2: AI Agent Validates & Populates IDoc Fields** ⭐ CORE POV FEATURE
    - Size: XL | Labels: user-story, epic-2-order-creation, priority/critical
    - Milestone: Sprint 2
    - Dependencies: Story 2.1, TE-5, TE-8
    - **POV Success Metric:** 30-40% field acceptance rate

16. ✅ **Story 2.3: Submit Order to SAP & Receive Confirmation**
    - Size: M | Labels: user-story, epic-2-order-creation, priority/critical
    - Milestone: Sprint 3
    - Dependencies: Story 2.2, TE-6, TE-10, TE-14

17. ✅ **Story 2.4: View Order Status & Audit Trail**
    - Size: S | Labels: user-story, epic-2-order-creation, priority/medium
    - Milestone: Sprint 3
    - Dependencies: Story 2.3, TE-15

#### UAT Sprint (1 issue)

18. ✅ **UAT Sprint: Week 7-8 Testing & Metrics**
    - Size: L | Labels: uat, priority/critical
    - Milestone: Sprint 4
    - Dependencies: All Epic 1 & 2 stories
    - **Scope:** 10 test orders, 3-5 pilot users
    - **Success:** 5+ orders, 30%+ acceptance, 0 critical bugs

---

## Critical Dependency Chain

```
Sprint 0 (BLOCKS EVERYTHING)
    ↓
┌───────────────────────────────────┬───────────────────────────────────┐
│ Epic 1 Path                       │ Epic 2 Path                       │
├───────────────────────────────────┼───────────────────────────────────┤
│ TE-2 (CEC OData)                  │ TE-2, TE-3, TE-12 (Multi-System)  │
│    ↓                              │    ↓                              │
│ Story 1.1: Search Opportunities   │ Story 2.1: Auto-Retrieve Data     │
│    ↓                              │    ↓                              │
│ TE-4 (Readiness Agent)            │ TE-5, TE-8 (BAPI + Orchestration) │
│    ↓                              │    ↓                              │
│ Story 1.2: Filter by Readiness    │ Story 2.2: AI Populates IDoc ⭐   │
│    ↓                              │    ↓                              │
│ TE-14 (Audit Store)               │ TE-6, TE-10, TE-14 (IDoc + Audit) │
│    ↓                              │    ↓                              │
│ Story 1.3: View AI Reasoning      │ Story 2.3: Submit to SAP          │
│                                   │    ↓                              │
│                                   │ TE-15 (Provenance)                │
│                                   │    ↓                              │
│                                   │ Story 2.4: View Audit Trail       │
└───────────────────────────────────┴───────────────────────────────────┘
                            ↓
                    UAT Sprint (Week 7-8)
                            ↓
            POV Decision: SCALE / ITERATE / STOP
```

---

## How to Deploy This Setup

### Step 1: Authenticate with GitHub

```bash
# Install GitHub CLI (if not installed)
# Windows: winget install GitHub.cli
# Mac: brew install gh
# Linux: see https://cli.github.com/

# Authenticate
gh auth login
```

### Step 2: Update Repository Owner

Edit the setup script and change the repository owner:

**Windows (PowerShell):**
```powershell
# Edit scripts/setup-github-project.ps1
# Change line 14:
$REPO_OWNER = "fujif"  # ← Change to your GitHub username
```

**Linux/Mac (Bash):**
```bash
# Edit scripts/setup-github-project.sh
# Change line 14:
REPO_OWNER="fujif"  # ← Change to your GitHub username
```

### Step 3: Run the Setup Script

**Windows (PowerShell):**
```powershell
cd C:\Users\fujif\OneDrive\Documents\GitHub\lead2cash
.\scripts\setup-github-project.ps1
```

**Linux/Mac (Bash):**
```bash
cd /path/to/lead2cash
bash scripts/setup-github-project.sh
```

The script will:
1. Create GitHub repository (if needed) - you'll be prompted
2. Create 17 labels with proper colors
3. Create 5 milestones with due dates
4. Create 19 issues with full descriptions
5. Assign labels and milestones to each issue

**Expected Runtime:** 2-5 minutes (depends on GitHub API rate limits)

### Step 4: Create GitHub Project (Manual)

The script cannot automate GitHub Projects v2 creation. Follow these steps:

1. Go to: `https://github.com/{your-username}?tab=projects`
2. Click **"New Project"**
3. Select **"Board"** view
4. Name: **"RRPS Lead-to-Cash POV (8-Week MVP)"**
5. Add custom fields:
   - **Epic** (Text)
   - **Size** (Single Select: S, M, L, XL)
   - **Sprint** (Text)
   - **Status** (Single Select: Backlog, Ready, In Progress, Review, Done)
6. Create views:
   - **Sprint Board:** Group by Status, filter by current sprint
   - **Epic View:** Group by Epic
   - **Timeline:** Gantt chart view by milestone

### Step 5: Add Issues to Project

```bash
# List your projects to get PROJECT_NUMBER
gh project list --owner {your-username}

# Add all issues to project (replace PROJECT_NUMBER)
gh issue list --repo {your-username}/lead2cash --limit 100 --json number \
  --jq '.[].number' | \
  xargs -I {} gh project item-add PROJECT_NUMBER \
    --owner {your-username} \
    --url https://github.com/{your-username}/lead2cash/issues/{}
```

### Step 6: Push Repository to GitHub

```bash
# If not already pushed
git add .
git commit -m "Initial commit: RRPS Lead-to-Cash POV setup with GitHub project structure"
git push -u origin master
```

---

## POV Success Metrics (Week 8 Decision)

### ✅ SCALE (Proceed to 12-Week Production)

**Criteria:**
- ✅ 5+ orders created successfully end-to-end (VBELN received)
- ✅ 30%+ acceptance rate (auto-filled fields unchanged by users)
- ✅ Qualitative cycle time improvement (users report "much faster")
- ✅ 0 critical bugs (no data loss, duplicates, corruption)
- ✅ Users eager to continue using the tool

**Next Steps:**
- Secure 12-week production budget
- Add Epics 3-6 to backlog (Compliance, Billing, Metrics, Full UAT)
- Hire 2nd backend engineer
- Plan 50-user rollout

### ⚠️ ITERATE (Extend POV by 4 Weeks)

**Criteria:**
- ⚠️ 2-4 orders successful
- ⚠️ 20-29% acceptance rate
- ⚠️ Mixed user feedback (some value, many issues)
- ⚠️ 1-2 fixable critical bugs

**Next Steps:**
- Analyze low acceptance: AI quality or user training?
- Fix critical bugs (2 weeks)
- Rerun UAT with 5 more orders (2 weeks)
- Reassess at Week 12

### ❌ STOP (Redesign or Abandon)

**Criteria:**
- ❌ <2 orders successful
- ❌ <20% acceptance rate (users reject AI suggestions)
- ❌ Cycle time no better than manual (or worse)
- ❌ 3+ critical bugs or CPI integration unstable

**Next Steps:**
- Root cause analysis: AI quality, CPI, or user resistance?
- If CPI: Redesign integration, retry in 8 weeks
- If AI: Pivot to simpler automation (RPA-style, no LLM)
- If users: Redesign UX with more human-in-the-loop controls

---

## Tracked KPIs

| KPI | POV Target | Measurement Method |
|-----|------------|--------------------|
| **Acceptance Rate** | 30-40% | (Unchanged AI fields / Total AI fields) × 100 |
| **Successful Orders** | 5-10 orders | Count of VBELNs received in UAT |
| **Cycle Time** | Qualitative improvement | Users report "faster" than 45-min manual |
| **First-Time-Right** | Baseline only | (Success on 1st attempt / Total attempts) × 100 |
| **User Satisfaction** | ≥3.5/5 | 5-question survey (1-5 scale) average |

---

## What You Need to Do Next

### Immediate Actions (Before Running Script)

1. ✅ Install GitHub CLI: https://cli.github.com/
2. ✅ Authenticate: `gh auth login`
3. ✅ Edit setup script: Change `REPO_OWNER = "fujif"` to your GitHub username
4. ✅ Review issue templates in `.github/ISSUE_TEMPLATE/` (optional)

### After Running Script

1. ✅ Verify all issues created: `gh issue list --repo {your-username}/lead2cash`
2. ✅ Create GitHub Project manually (see Step 4 above)
3. ✅ Add all issues to project (see Step 5 above)
4. ✅ Configure dependencies in project board UI
5. ✅ Assign Sprint 0 to team and begin infrastructure setup
6. ✅ Push repository to GitHub: `git push -u origin master`

### For Team Onboarding

1. Share `docs/github-project-setup.md` with team
2. Review `docs/requirements.md` (v5.0) for full acceptance criteria
3. Assign Sprint 0 issues to backend engineer + integration specialist
4. Schedule Sprint 0 kickoff meeting (2-hour setup walkthrough)
5. Set up daily standups starting Week 1

---

## File Locations Reference

| File | Path | Purpose |
|------|------|---------|
| **Requirements** | `docs/requirements.md` | Full v5.0 requirements (8-week MVP) |
| **Setup Guide** | `docs/github-project-setup.md` | Complete setup instructions |
| **This Summary** | `GITHUB-PROJECT-SUMMARY.md` | Quick reference (this file) |
| **Bash Script** | `scripts/setup-github-project.sh` | Linux/Mac setup automation |
| **PowerShell Script** | `scripts/setup-github-project.ps1` | Windows setup automation |
| **User Story Template** | `.github/ISSUE_TEMPLATE/user-story.md` | Template for new user stories |
| **TE Template** | `.github/ISSUE_TEMPLATE/technical-enabler.md` | Template for technical enablers |
| **Bug Template** | `.github/ISSUE_TEMPLATE/bug.md` | Template for bug reports |
| **UAT Template** | `.github/ISSUE_TEMPLATE/uat-feedback.md` | Template for UAT feedback |

---

## Troubleshooting

### "gh: command not found"
- **Solution:** Install GitHub CLI: https://cli.github.com/

### "authentication required"
- **Solution:** Run `gh auth login` and follow prompts

### "Label already exists"
- **Solution:** This is normal. Script ignores duplicate labels.

### "Milestone not found" when creating issues
- **Solution:** Milestones may have been created with slightly different names. Check `gh api repos/{owner}/{repo}/milestones` and update script if needed.

### PowerShell script fails on Windows
- **Solution:** Run `Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope CurrentUser` to allow local scripts.

### Issues created but with minimal descriptions
- **Solution:** The bash/PowerShell scripts create issues with basic descriptions. Full descriptions are in the requirements.md file. You can manually edit issues in GitHub UI to add full acceptance criteria from requirements.md.

---

## Support & Contact

- **Primary Reference:** `docs/requirements.md` (v5.0) - Contains full acceptance criteria, technical implementation, edge cases
- **Setup Instructions:** `docs/github-project-setup.md` - Step-by-step setup guide
- **Issue Templates:** `.github/ISSUE_TEMPLATE/` - Reusable templates for new issues

**For questions about:**
- Story acceptance criteria → See `docs/requirements.md`
- Technical implementation → See story sections in `docs/requirements.md`
- GitHub setup process → See `docs/github-project-setup.md`
- Script errors → See "Troubleshooting" section above

---

## Summary Statistics

✅ **4 Issue Templates** created
✅ **2 Setup Scripts** created (Bash + PowerShell)
✅ **1 Complete Documentation** guide created
✅ **17 Labels** configured
✅ **5 Milestones** configured
✅ **19 Issues** ready for creation:
  - 1 Sprint 0 checklist
  - 10 Technical Enablers
  - 7 User Stories (3 Epic 1, 4 Epic 2)
  - 1 UAT meta-issue

**Total Effort Estimate:** 8 weeks (realistic POV scope)
**POV Success Target:** 5+ orders, 30%+ acceptance, 0 critical bugs

---

**Document Status:** ✅ PRODUCTION-READY
**Last Updated:** 2025-10-10
**Based On:** requirements.md v5.0 (Realistic 8-Week POV Scope)

---

**You are ready to deploy! Run the setup script when you're ready to create the GitHub project structure.**
