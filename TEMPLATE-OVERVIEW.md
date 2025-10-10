# Kailash Sprint Design Template - Overview

## What You Get

This template extracts the proven sprint design patterns from the Impact-Verse project and makes them reusable for any Kailash/DataFlow/Nexus project.

## File Structure

```
lead2cash/
├── .github/
│   ├── ISSUE_TEMPLATE/
│   │   ├── story-0-infrastructure.md    📋 Story 0 template
│   │   └── feature-story.md             📋 Feature story template
│   └── project-template-config.yaml     ⚙️  Configuration file
│
├── scripts/
│   ├── create-kailash-project.py        🚀 Main generator script
│   ├── quick-start.sh                   ▶️  Quick start helper
│   └── requirements.txt                 📦 Python dependencies
│
├── README-TEMPLATE.md                   📖 Full documentation
├── USAGE-EXAMPLE.md                     💡 Usage examples
└── TEMPLATE-OVERVIEW.md                 📊 This file
```

## Core Components

### 1. Story 0 Template (Infrastructure)

**Purpose:** Critical validation story that must pass before any feature work

**Key Features:**
- ✅ Validates Kailash SDK (DataFlow, Nexus, Kaizen)
- ✅ Tests PostgreSQL integration
- ✅ Confirms auto-generated nodes work (9 nodes from `@db.model`)
- ✅ Performance benchmarks (queries < 200ms)
- ✅ GO/NO-GO decision framework
- ✅ Fallback plan (Core SDK if DataFlow fails)

**Placeholders:** 22 customizable fields
- Project name, core model, performance benchmarks, etc.

**Output:** Fully configured GitHub issue ready to use

---

### 2. Feature Story Template

**Purpose:** Standardized structure for all feature development stories

**Key Features:**
- ✅ User story format (As a/I want/So that)
- ✅ Ready criteria (prerequisites before starting)
- ✅ Definition of Done (quality gates)
- ✅ Backend checklist (DataFlow models, workflows, Nexus)
- ✅ Frontend checklist (components, responsive design)
- ✅ Test requirements (80%+ coverage)
- ✅ Performance benchmarks
- ✅ Documentation requirements

**Placeholders:** 40+ customizable fields

**Output:** Complete user story with all sections

---

### 3. Configuration File

**Purpose:** Single source of truth for project settings

**Sections:**
```yaml
project:           # Name, org, repo
technology:        # Stack configuration
story_0:          # Infrastructure settings
feature_story:    # Default values
sprint:           # Sprint planning
quality_gates:    # Quality criteria
github_automation: # Project fields, labels
```

**Usage:**
- Customize once
- Reuse across all stories
- Easy to maintain

---

### 4. Project Generator Script

**Purpose:** Automate GitHub project creation

**What It Does:**
1. Creates GitHub Project (v2)
2. Adds custom fields:
   - Status (Backlog → Done)
   - Priority (Critical → Low)
   - Story Points (number)
   - Sprint (iteration)
   - Team (Backend, Frontend, etc.)
3. Creates Story 0 issue
4. Adds Story 0 to project
5. Applies labels

**Technologies:**
- Python 3.8+
- GitHub GraphQL API
- YAML configuration
- Template substitution

---

## Design Patterns Extracted

### Pattern 1: Infrastructure-First Approach

```
Story 0 (Infrastructure)
    ↓ BLOCKS
All Feature Stories (1-N)
```

**Why:** Validate alpha technology (DataFlow) before investing in features

**Implementation:**
- Story 0 has 21 story points (2 weeks)
- Decision gate: Success/Partial/Failure
- Documented fallback plan

---

### Pattern 2: Quality Gates

**Every Story Must Pass:**

```
Ready Criteria → Development → Definition of Done → Deployment
      ↓               ↓                ↓                ↓
Prerequisites    Implement      Quality Gates    Production
```

**Gates:**
1. **Ready:** Dependencies resolved, contracts defined
2. **DoD Backend:** Models, workflows, tests (80%+)
3. **DoD Frontend:** Components, responsive, integration
4. **DoD Quality:** Performance, security, accessibility
5. **DoD Deploy:** Code review, staging, smoke tests

---

### Pattern 3: DataFlow Workflow Pattern

**Standard Backend Implementation:**

```python
# 1. Define model
@db.model
class Lead:
    name: str
    email: str
    status: str

# 2. Auto-generated nodes (9 total)
# - query_lead
# - filter_lead
# - create_lead
# - update_lead
# - delete_lead
# - batch_lead
# - validate_lead
# - transform_lead
# - aggregate_lead

# 3. Build workflow
workflow = (
    runtime
    .add_node(query_lead)
    .add_node(filter_lead)
    .add_edge(query_lead, filter_lead)
    .build()
)

# 4. Execute
result = runtime.execute(workflow)
```

---

### Pattern 4: Multi-Channel Deployment

**Nexus Pattern:**

```
DataFlow Workflows
        ↓
   Nexus Deploy
        ↓
    ┌───┴───┬───────┐
    ↓       ↓       ↓
   API     CLI     MCP
```

**Implementation:**
- Same backend logic
- Three access methods
- Session management
- Unified error handling

---

### Pattern 5: Responsive-First Frontend

**Design System:**

```
Breakpoints:
  Mobile:  600px  → Vertical layout, simplified
  Tablet:  1024px → Adaptive grid
  Desktop: 1440px → Full features

Adaptive Widgets:
  - AdaptiveFilter
  - AdaptiveGrid
  - AdaptiveForm
```

---

## Story Point Distribution Model

| Complexity | Points | Time Estimate | Examples |
|------------|--------|---------------|----------|
| Infrastructure | 21 | 70-80h (2 weeks) | Story 0, Complex integrations |
| CRUD Features | 21 | 60-70h | Full entity management |
| Advanced | 13 | 40-50h | Analytics, reporting |
| Standard | 8 | 25-35h | Basic features |
| Simple | 5 | 15-20h | Minor additions |
| AI/ML | 36 | 120-140h | AI features (break down!) |

**Velocity Planning:**
- Sprint duration: 2 weeks
- Target: 40 story points per sprint
- Buffer: 20% for bugs/tech debt

---

## Sprint Planning Framework

### Sprint 0: Infrastructure (CRITICAL)

**Duration:** 2 weeks
**Stories:** Story 0 only
**Outcome:** GO/NO-GO decision

**Success Metrics:**
- ✅ All 9 DataFlow nodes working
- ✅ Performance < 200ms (queries)
- ✅ 10k+ records tested
- ✅ No blocking bugs

**Failure Plan:**
- Document issues
- Evaluate Core SDK fallback
- Re-plan architecture

---

### Sprint 1+: Feature Development

**Structure:**
```
Sprint Planning
    ↓
Select stories (40 pts target)
    ↓
Check dependencies
    ↓
Validate ready criteria
    ↓
Implement
    ↓
Quality gates
    ↓
Sprint review
```

---

## Customization Guide

### Scenario 1: Different Frontend (React)

**Change:**
```yaml
technology:
  frontend:
    framework: "React"
```

**Result:**
- Story 0 mentions React instead of Flutter
- Component examples use React patterns
- Testing utilities reference Jest

---

### Scenario 2: Stricter Performance

**Change:**
```yaml
story_0:
  performance_benchmarks:
    query_ms: 100  # Instead of 200
    filter_ms: 250 # Instead of 500
```

**Result:**
- Higher performance bar
- More aggressive optimization needed
- Better user experience

---

### Scenario 3: Smaller Team

**Change:**
```yaml
story_0:
  story_points: 13
  effort:
    weeks: 1
    hours: 40

sprint:
  story_points_per_sprint: 20
```

**Result:**
- Faster Story 0 validation
- Smaller sprint commitments
- More realistic for small teams

---

## Usage Workflow

### Step 1: Initial Setup (One-time)

```bash
# Clone template
git clone https://github.com/{{ORG}}/lead2cash.git
cd lead2cash

# Install dependencies
pip install -r scripts/requirements.txt

# Set GitHub token
export GH_TOKEN=your_token_here
```

---

### Step 2: Configure Project

Edit `.github/project-template-config.yaml`:

```yaml
project:
  name: "Your Project Name"
  organization: "your-org"
  repository: "your-repo"

story_0:
  core_model_name: "YourModel"  # e.g., Lead, User, Product
```

---

### Step 3: Generate Project

```bash
python3 scripts/create-kailash-project.py \
  --org your-org \
  --repo your-repo \
  --name "Your Project" \
  --description "Description"
```

**Output:**
- ✅ GitHub Project created
- ✅ Custom fields configured
- ✅ Story 0 issue created
- ✅ Project board ready

---

### Step 4: Create Feature Stories

**Option A: GitHub UI**
1. Go to Issues → New Issue
2. Choose "Feature Story Template"
3. Fill in placeholders
4. Create issue

**Option B: GitHub CLI**
```bash
gh issue create \
  --repo org/repo \
  --template feature-story.md \
  --title "Story 1: Feature Name"
```

---

### Step 5: Execute Sprints

```
Sprint 0:
  - Complete Story 0
  - Make GO/NO-GO decision
  - Document findings

Sprint 1+:
  - Select stories (40 pts)
  - Implement features
  - Pass quality gates
  - Deploy to staging
```

---

## Key Benefits

### 1. Consistency
Every project follows proven patterns

### 2. Risk Management
Story 0 validates alpha tech early

### 3. Quality Built-In
Definition of Done enforces standards

### 4. Easy Onboarding
Templates guide new team members

### 5. Scalability
Reuse across unlimited projects

### 6. Documentation
Self-documenting stories

---

## Comparison: Before vs After

### Before (Manual)

- ❌ Inconsistent story formats
- ❌ Forgot critical validation steps
- ❌ No performance benchmarks
- ❌ Unclear dependencies
- ❌ Missing quality gates
- ❌ Tribal knowledge
- ⏱️ Hours to set up each project

### After (Template)

- ✅ Standardized format
- ✅ Story 0 validates everything
- ✅ Performance benchmarks built-in
- ✅ Clear dependency management
- ✅ Quality gates enforced
- ✅ Documented patterns
- ⏱️ Minutes to set up new project

---

## Success Metrics

### Template Success

- [ ] Project created in < 5 minutes
- [ ] Story 0 comprehensive and complete
- [ ] Feature stories consistent
- [ ] Team understands patterns
- [ ] Quality gates followed

### Project Success

- [ ] Story 0 completed successfully
- [ ] DataFlow validation passed
- [ ] Performance benchmarks met
- [ ] All stories follow template
- [ ] Quality gates passed
- [ ] On-time delivery

---

## Next Steps

1. **Review templates** in `.github/ISSUE_TEMPLATE/`
2. **Customize config** in `.github/project-template-config.yaml`
3. **Test generator** with sandbox project
4. **Create real project** for production
5. **Share with team** for feedback
6. **Iterate** based on learnings

---

## Support Resources

- **Full docs:** `README-TEMPLATE.md`
- **Examples:** `USAGE-EXAMPLE.md`
- **Config:** `.github/project-template-config.yaml`
- **Script:** `scripts/create-kailash-project.py`

---

**Template Version:** 1.0
**Based on:** Impact-Verse sprint design (Project #64)
**Last Updated:** 2025-10-10
