# Kailash Project Template - Usage Example

This document shows how to use the template to create a new project.

## Example: Creating "Lead2Cash CRM" Project

### Step 1: Customize Configuration

Edit `.github/project-template-config.yaml`:

```yaml
project:
  name: "Lead2Cash CRM"
  description: "Customer Relationship Management system for lead tracking and conversion"
  organization: "Integrum-Global"
  repository: "lead2cash"

story_0:
  core_model_name: "Lead"  # Changed from Contact to Lead
  # ... rest stays the same
```

### Step 2: Set GitHub Token

```bash
export GH_TOKEN="github_pat_11BI6KSTQ0..."
```

### Step 3: Run Generator

```bash
python3 scripts/create-kailash-project.py \
  --org Integrum-Global \
  --repo lead2cash \
  --name "Lead2Cash CRM" \
  --description "CRM for lead tracking and conversion"
```

### Step 4: Expected Output

```
=============================================================
Kailash Project Template Generator
=============================================================
Creating GitHub Project: Lead2Cash CRM
✓ Project created: https://github.com/orgs/Integrum-Global/projects/65

Creating project fields...
  - Creating field: Status (single_select)
  - Creating field: Priority (single_select)
  - Creating field: Story Points (number)
  - Creating field: Sprint (iteration)
  - Creating field: Team (single_select)

Creating Story 0 (Infrastructure) issue...
✓ Story 0 issue created: https://github.com/Integrum-Global/lead2cash/issues/1
✓ Issue added to project

=============================================================
✓ Project setup complete!
=============================================================
Project URL: https://github.com/orgs/Integrum-Global/projects/65
Story 0 Issue: https://github.com/Integrum-Global/lead2cash/issues/1

Next steps:
1. Review and customize Story 0 issue
2. Create feature stories using the feature-story.md template
3. Begin Story 0 validation sprint
=============================================================
```

### Step 5: Story 0 Will Look Like

```markdown
# Story 0: Project Setup & Foundations (Infrastructure)

**Story Points:** 21
**Estimated Effort:** 2 weeks (70-80 hours)
**Priority:** CRITICAL - Must complete BEFORE all other stories

## Description
Establish the foundational development environment, validate all
technology stack components, and create design system infrastructure
for Lead2Cash CRM development.

## Ready Criteria
- [ ] PostgreSQL database credentials confirmed in `.env`
- [ ] Kailash SDK installation access verified
- [ ] Flutter SDK installed on development machines
- [ ] Team available for 3-day setup sprint

## DataFlow Alpha Validation
**CRITICAL:** DataFlow is PostgreSQL-only alpha. This story validates
it works for our use case.

### Success Criteria
- [ ] Lead model auto-generates all 9 nodes successfully
- [ ] Query/filter/create nodes work in workflows
- [ ] PostgreSQL integration stable with 10k+ test records
- [ ] Performance acceptable:
  - Queries: < 200ms
  - Filters: < 500ms
...
```

### Step 6: Create Feature Stories

Navigate to `https://github.com/Integrum-Global/lead2cash/issues/new/choose`

Select "Feature Story Template" and fill in:

```markdown
# Story 1: Search & Filter Leads

**Story Points:** 8
**Estimated Effort:** 14 hours
**Priority:** High
**Sprint:** 1

## User Story
**As a** sales representative
**I want** to search and filter leads by various criteria
**So that** I can quickly find relevant prospects

## Description
Implement comprehensive search and filtering functionality for leads,
allowing users to find leads by name, company, status, industry, etc.

## Definition of Done

### Backend Implementation
- [ ] DataFlow models created using `@db.model` decorator
- [ ] Lead search workflow implemented
- [ ] Filter nodes configured (status, industry, date range)
- [ ] Performance: queries < 200ms
- [ ] Backend tests ≥ 80% coverage

### Frontend Implementation
- [ ] Flutter search interface with adaptive design
- [ ] Filter panel with multi-criteria selection
- [ ] Results grid with pagination
- [ ] Loading and error states
- [ ] Frontend tests passing

...
```

## Template Customization Examples

### Example 1: React Frontend Instead of Flutter

`.github/project-template-config.yaml`:

```yaml
technology:
  frontend:
    framework: "React"
    responsive_breakpoints:
      mobile: 640
      tablet: 1024
      desktop: 1280
```

Story 0 will automatically update:
- "React development environment configured"
- Different adaptive component examples
- React-specific testing utilities

### Example 2: Different Performance Benchmarks

```yaml
story_0:
  performance_benchmarks:
    query_ms: 150  # Stricter requirement
    filter_ms: 300

feature_story_defaults:
  performance:
    query_perf_ms: 150
    page_load_ms: 800
```

### Example 3: Shorter Setup Sprint

```yaml
story_0:
  story_points: 13
  effort:
    weeks: 1
    hours: 40
  setup_sprint_days: 2
```

## Creating Multiple Stories at Once

You can create a batch script:

```bash
# create-all-stories.sh

export GH_TOKEN="your_token"
ORG="Integrum-Global"
REPO="lead2cash"

# Story 1: Search & Filter
gh issue create \
  --repo "$ORG/$REPO" \
  --title "Story 1: Search & Filter Leads" \
  --label "feature,user-story" \
  --body-file stories/story-1.md

# Story 2: Add & Update Leads
gh issue create \
  --repo "$ORG/$REPO" \
  --title "Story 2: Add & Update Leads" \
  --label "feature,user-story" \
  --body-file stories/story-2.md

# ... etc
```

## Testing the Template

### Validation Checklist

Before using in production:

- [ ] Story 0 template renders correctly
- [ ] All placeholders replaced
- [ ] Feature story template works
- [ ] GitHub project created successfully
- [ ] Custom fields added
- [ ] Story 0 added to project
- [ ] Labels applied correctly
- [ ] Performance benchmarks appropriate
- [ ] Documentation complete

### Test Project Creation

```bash
# Test with a sandbox org/repo first
python3 scripts/create-kailash-project.py \
  --org your-test-org \
  --repo test-kailash-template \
  --name "Test Project" \
  --description "Testing the template"
```

## Common Issues

### Issue: GraphQL API Returns Null

**Cause:** Insufficient token permissions

**Solution:** Recreate token with `project` scope:
1. Go to https://github.com/settings/tokens
2. Generate new token (classic)
3. Select: `repo`, `read:org`, `project`

### Issue: Template Placeholders Not Replaced

**Cause:** Missing configuration value

**Solution:** Check `.github/project-template-config.yaml` for all required fields

### Issue: Story 0 Too Large for Team

**Cause:** Default 21 points may be too high

**Solution:** Adjust story points and break into smaller tasks

```yaml
story_0:
  story_points: 13  # Reduce
  # Remove some optional subtasks
```

## Advanced: Custom Story Types

Create new templates in `.github/ISSUE_TEMPLATE/`:

**integration-story.md:**
```markdown
---
name: Integration Story
about: Template for third-party integrations
title: 'Integration: {{SERVICE_NAME}}'
labels: integration, story
---

# Integration: {{SERVICE_NAME}}

## Description
Integrate with {{SERVICE_NAME}} API for {{PURPOSE}}

## Definition of Done
- [ ] API credentials configured
- [ ] Nexus connector implemented
- [ ] Error handling for rate limits
- [ ] Integration tests passing
...
```

## Summary

This template provides:
- ✅ Standardized story structure
- ✅ Automatic project setup
- ✅ Quality gates built-in
- ✅ Kailash/DataFlow patterns
- ✅ Easy customization
- ✅ Documentation generation

Start with Story 0, validate your stack, then scale feature development!
