# Kailash Sprint Design Template

This repository contains a reusable sprint design template for Kailash/DataFlow/Nexus projects, based on the Impact-Verse project structure.

## Overview

The template provides:
- **Story 0 (Infrastructure)**: Critical prerequisite validation story
- **Feature Story Template**: Standardized structure for all feature development
- **GitHub Project Automation**: Scripts to create projects with proper structure
- **Sprint Planning Framework**: Proven patterns for Kailash-based projects

## Quick Start

### 1. Prerequisites

- GitHub Personal Access Token with `project`, `repo`, and `read:org` scopes
- Python 3.8+ installed
- Access to Kailash SDK

### 2. Installation

```bash
# Clone this repository
git clone https://github.com/{{ORG}}/{{REPO}}.git
cd {{REPO}}

# Install Python dependencies
pip install -r scripts/requirements.txt

# Set your GitHub token
export GH_TOKEN=your_github_token_here
```

### 3. Configure Your Project

Edit `.github/project-template-config.yaml`:

```yaml
project:
  name: "My New Project"
  description: "Project description"
  organization: "my-github-org"
  repository: "my-repo-name"

story_0:
  core_model_name: "YourCoreModel"  # e.g., Contact, User, Product
  # ... other configurations
```

### 4. Generate GitHub Project

```bash
python scripts/create-kailash-project.py \
  --org your-github-org \
  --repo your-repo-name \
  --name "My New Kailash Project" \
  --description "Project description"
```

This will:
1. Create a GitHub Project (v2) in your organization
2. Set up custom fields (Status, Priority, Story Points, Sprint, Team)
3. Create Story 0 (Infrastructure) issue with all validation criteria
4. Add Story 0 to the project board

## Template Structure

### Story 0: Infrastructure (CRITICAL)

**Must be completed BEFORE all feature development**

Story 0 validates:
- ✅ Kailash SDK installation (DataFlow, Nexus, Kaizen)
- ✅ PostgreSQL connection and DataFlow alpha validation
- ✅ Auto-generated nodes (9 nodes from `@db.model`)
- ✅ Multi-channel deployment (API, CLI, MCP)
- ✅ Frontend framework setup (Flutter/React/Vue)
- ✅ Performance benchmarks (queries < 200ms, filters < 500ms)

**Decision Gate:**
- ✅ SUCCESS → Proceed with DataFlow
- ⚠️ PARTIAL → Document workarounds
- ❌ FAILURE → Fallback to Core SDK

### Feature Stories

Each feature story includes:

**Ready Criteria:**
- Story 0 completed
- Dependencies resolved
- API contracts defined
- Test data available

**Definition of Done:**
- Backend: DataFlow models, workflows, Nexus deployment
- Frontend: Responsive components, API integration
- Testing: Unit (80%+), integration, E2E tests
- Documentation: API docs, component docs, user guides
- Deployment: Code reviewed, deployed to staging

## Sprint Planning Framework

### Recommended Sprint Structure

**Sprint 0 (Weeks 1-2): Infrastructure**
- Story 0 validation
- GO/NO-GO decision
- Story Points: 21

**Sprint 1 (Weeks 3-4): Core Features**
- Foundation functionality
- Target: ~40 story points

**Sprint 2+ (Ongoing): Feature Development**
- Advanced features
- Integrations
- AI capabilities

### Story Point Guidelines

| Complexity | Points | Examples |
|------------|--------|----------|
| Infrastructure | 21 | Story 0, Complex integrations |
| CRUD Operations | 21 | Full entity management |
| Advanced Features | 13 | Analytics, reporting |
| Basic Features | 8 | Standard features |
| Simple Features | 5 | Minor additions |
| AI Features | 36 | AI-driven (consider breaking down) |

## Technology Stack

### Backend
- **Kailash SDK**
  - DataFlow: ORM with auto-generated nodes (PostgreSQL-only alpha)
  - Nexus: Multi-channel deployment (API/CLI/MCP)
  - Kaizen: AI agent framework
- **PostgreSQL**: Primary database

### Frontend
- **Flutter** (default) or React/Vue
- Responsive design system
- Adaptive widgets

### Development Tools
- OpenAPI/Swagger for API contracts
- Prism for mock servers
- pytest for backend testing
- Flutter test / Jest for frontend

## File Structure

```
.
├── .github/
│   ├── ISSUE_TEMPLATE/
│   │   ├── story-0-infrastructure.md      # Story 0 template
│   │   └── feature-story.md               # Feature story template
│   └── project-template-config.yaml       # Project configuration
├── scripts/
│   ├── create-kailash-project.py          # Project generator
│   └── requirements.txt                   # Python dependencies
└── README-TEMPLATE.md                     # This file
```

## Usage Guide

### Creating Story 0

```bash
# Automatically created by create-kailash-project.py
# Or manually create using GitHub UI with story-0-infrastructure.md template
```

### Creating Feature Stories

1. Go to your repository → Issues → New Issue
2. Select "Feature Story Template"
3. Fill in the placeholders:
   - `{{STORY_NUMBER}}`: Story number (1, 2, 3...)
   - `{{STORY_TITLE}}`: Descriptive title
   - `{{STORY_POINTS}}`: Points (5, 8, 13, 21, 36)
   - `{{USER_ROLE}}`: User persona
   - `{{USER_GOAL}}`: What they want
   - `{{USER_BENEFIT}}`: Why they want it
4. Complete all sections
5. Add to project board

### Quality Gates

Every story must pass:

1. **Code Review**: 2+ approvals
2. **Testing**: 80%+ coverage, all tests passing
3. **Performance**: Meets benchmarks
4. **Documentation**: Complete and updated

## Best Practices

### 1. Always Start with Story 0
Never skip infrastructure validation. It's the foundation for everything.

### 2. Validate DataFlow Early
DataFlow is in alpha. Run comprehensive validation before committing to architecture.

### 3. Use Dependency Graphs
Story 0 blocks all features. Map dependencies clearly.

### 4. Break Down Large Stories
Stories > 21 points should be split into smaller increments.

### 5. Document Alpha Limitations
Track any DataFlow limitations discovered during Story 0.

### 6. Performance Testing
Test with realistic data volumes (10k+ records) early.

## Customization

### Adjust Story Points

Edit `.github/project-template-config.yaml`:

```yaml
story_0:
  story_points: 21  # Adjust based on team capacity

feature_story_defaults:
  performance:
    query_perf_ms: 200  # Adjust benchmarks
```

### Change Frontend Framework

```yaml
technology:
  frontend:
    framework: "React"  # or Vue, Svelte, etc.
```

### Add Custom Fields

```yaml
github_automation:
  project_fields:
    - name: "Custom Field"
      type: "single_select"
      options: ["Option1", "Option2"]
```

## Troubleshooting

### Issue: DataFlow Alpha Validation Fails

**Solution:**
1. Document specific failures
2. Consult Kailash SDK documentation
3. Use specialized agents (sdk-navigator, framework-advisor)
4. Consider Core SDK fallback

### Issue: Performance Benchmarks Not Met

**Solution:**
1. Review database indexes
2. Optimize DataFlow queries
3. Check PostgreSQL configuration
4. Consider caching strategies

### Issue: GitHub API Rate Limiting

**Solution:**
1. Use authenticated requests (GH_TOKEN)
2. Implement exponential backoff
3. Batch API calls

## Contributing

When improving this template:

1. Test changes with a new project creation
2. Update documentation
3. Maintain backward compatibility
4. Add examples for new patterns

## References

- [Kailash SDK Documentation](https://docs.kailash.ai)
- [DataFlow Guide](https://docs.kailash.ai/dataflow)
- [Nexus Multi-Channel Deployment](https://docs.kailash.ai/nexus)
- [GitHub Projects V2 API](https://docs.github.com/en/graphql/reference/objects#projectv2)

## Support

For issues with:
- **Template**: Open issue in this repository
- **Kailash SDK**: Consult Kailash documentation
- **DataFlow Alpha**: Contact Kailash support team

## License

{{LICENSE_INFO}}

---

**Generated from Impact-Verse sprint design pattern**
