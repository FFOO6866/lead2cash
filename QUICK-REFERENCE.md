# Kailash Sprint Template - Quick Reference

## 🚀 Quick Start (3 Steps)

### 1. Set GitHub Token
```bash
export GH_TOKEN="github_pat_11BI6KSTQ0..."
```

### 2. Customize Config
Edit `.github/project-template-config.yaml`:
```yaml
project:
  name: "Your Project"
  organization: "your-org"
  repository: "your-repo"

story_0:
  core_model_name: "YourModel"  # e.g., Lead, User, Product
```

### 3. Generate Project
```bash
python scripts/create-kailash-project.py \
  --org your-org \
  --repo your-repo \
  --name "Project Name" \
  --description "Description"
```

---

## 📁 What Was Created

```
lead2cash/
├── .github/
│   ├── ISSUE_TEMPLATE/
│   │   ├── story-0-infrastructure.md    ← Story 0 template
│   │   └── feature-story.md             ← Feature template
│   └── project-template-config.yaml     ← Configuration
│
├── scripts/
│   ├── create-kailash-project.py        ← Generator
│   ├── quick-start.sh                   ← Helper script
│   └── requirements.txt                 ← Dependencies
│
├── README-TEMPLATE.md                   ← Full docs
├── USAGE-EXAMPLE.md                     ← Examples
├── TEMPLATE-OVERVIEW.md                 ← Patterns
└── QUICK-REFERENCE.md                   ← This file
```

---

## 🎯 Key Patterns Extracted

### 1. Infrastructure-First
```
Story 0 (21 pts, 2 weeks)
    ↓ BLOCKS
All Features (Stories 1-N)
```

### 2. Quality Gates
```
Ready → Develop → DoD → Deploy
  ↓        ↓       ↓       ↓
Deps   Implement  Tests  Prod
```

### 3. DataFlow Pattern
```python
@db.model
class Model:
    field: type

# Auto-generates 9 nodes:
# query, filter, create, update, delete,
# batch, validate, transform, aggregate
```

### 4. Multi-Channel Deploy
```
DataFlow → Nexus → API/CLI/MCP
```

---

## 📊 Story Points Guide

| Points | Time | Example |
|--------|------|---------|
| 5 | 15-20h | Simple feature |
| 8 | 25-35h | Standard feature |
| 13 | 40-50h | Advanced feature |
| 21 | 60-80h | Infrastructure, CRUD |
| 36 | 120h+ | AI (break down!) |

**Sprint Target:** 40 points / 2 weeks

---

## ✅ Story 0 Checklist

### Must Validate
- [ ] Kailash SDK installed (dataflow, nexus, kaizen)
- [ ] PostgreSQL connected
- [ ] @db.model generates 9 nodes
- [ ] All nodes work in workflows
- [ ] Performance: queries < 200ms, filters < 500ms
- [ ] No blocking bugs

### Decision Point
- ✅ **SUCCESS** → Proceed with DataFlow
- ⚠️ **PARTIAL** → Document workarounds
- ❌ **FAILURE** → Fallback to Core SDK

---

## 📝 Creating Feature Stories

### Option 1: GitHub UI
1. Issues → New Issue
2. Choose "Feature Story Template"
3. Fill placeholders
4. Create

### Option 2: GitHub CLI
```bash
gh issue create \
  --repo org/repo \
  --template feature-story.md \
  --title "Story X: Title"
```

---

## 🔧 Customization Examples

### React Instead of Flutter
```yaml
technology:
  frontend:
    framework: "React"
```

### Stricter Performance
```yaml
story_0:
  performance_benchmarks:
    query_ms: 100  # vs 200
    filter_ms: 250 # vs 500
```

### Smaller Team
```yaml
story_0:
  story_points: 13  # vs 21
  effort:
    weeks: 1        # vs 2

sprint:
  story_points_per_sprint: 20  # vs 40
```

---

## 🎬 Usage Workflow

```
1. Configure
   ├── Edit config.yaml
   └── Set core_model_name

2. Generate
   ├── Run create-kailash-project.py
   ├── Project created
   └── Story 0 created

3. Execute Sprint 0
   ├── Complete Story 0
   ├── Validate DataFlow
   └── Make GO/NO-GO decision

4. Create Features
   ├── Use feature-story.md template
   ├── Fill all sections
   └── Add to project

5. Sprint Planning
   ├── Select 40 pts
   ├── Check dependencies
   └── Execute sprint
```

---

## 📋 Definition of Done (Standard)

### Backend
- [ ] DataFlow models with @db.model
- [ ] All 9 nodes validated
- [ ] Workflows tested
- [ ] Nexus deployed (API/CLI/MCP)
- [ ] Performance benchmarks met
- [ ] Tests ≥ 80% coverage

### Frontend
- [ ] Responsive (mobile/tablet/desktop)
- [ ] Adaptive widgets
- [ ] API integrated
- [ ] Loading/error states
- [ ] Tests passing

### Quality
- [ ] Code reviewed (2+ approvals)
- [ ] Performance tested
- [ ] Security reviewed
- [ ] Docs updated
- [ ] Deployed to staging

---

## 🐛 Troubleshooting

### GraphQL Returns Null
**Fix:** Token needs `project` scope
```bash
# Create new token at:
https://github.com/settings/tokens
# Select: repo, read:org, project
```

### DataFlow Validation Fails
**Fix:**
1. Check PostgreSQL connection
2. Review @db.model syntax
3. Consult sdk-navigator agent
4. Consider Core SDK fallback

### Script Fails
**Fix:**
```bash
# Check Python version
python --version  # Should be 3.8+

# Reinstall dependencies
pip install -r scripts/requirements.txt

# Check GH_TOKEN
echo $GH_TOKEN
```

---

## 📚 Documentation

- **Full Guide:** `README-TEMPLATE.md`
- **Examples:** `USAGE-EXAMPLE.md`
- **Patterns:** `TEMPLATE-OVERVIEW.md`
- **This Guide:** `QUICK-REFERENCE.md`

---

## 🎯 Success Checklist

### Template Setup
- [x] Templates created in `.github/ISSUE_TEMPLATE/`
- [x] Config file created
- [x] Generator script working
- [x] Dependencies installed
- [x] Documentation complete

### Ready to Use When:
- [ ] Configuration customized
- [ ] GitHub token set
- [ ] Test project created successfully
- [ ] Team trained on templates
- [ ] Ready to execute Story 0

---

## 💡 Pro Tips

1. **Always start with Story 0** - Don't skip validation
2. **Test with sandbox first** - Validate before production
3. **Document alpha issues** - Track DataFlow limitations
4. **Break down 36-point stories** - More manageable
5. **Use dependency graphs** - Visual story relationships
6. **Update config as you learn** - Continuous improvement

---

## 📞 Support

- **Template Issues:** This repo
- **Kailash SDK:** Official docs
- **DataFlow Alpha:** Kailash support

---

**Version:** 1.0
**Source:** Impact-Verse Project #64
**Date:** 2025-10-10
