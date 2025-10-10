# Two-Level Structure Guide

This guide explains the two-level organizational structure used in this project to support multi-developer collaboration.

## Overview

The project uses a two-level structure for four key directories:
- **Architecture Decision Records (adr/)**
- **Product Requirements Documents (prd/)**
- **Task Tracking (todos/)**
- **Mistakes & Learnings (mistakes/)**

Each exists at both:
1. **Root Level** (`/adr/`, `/prd/`, `/todos/`, `/mistakes/`)
2. **Module Level** (`/src/solutions/[module]/adr/`, etc.)

## When to Use Each Level

### 🌍 Root Level (Project-Wide)

Use root-level directories for:
- Cross-module concerns
- System-wide decisions
- Project coordination
- Shared patterns

| Directory | Root Level Use Cases |
|-----------|---------------------|
| `/adr/` | • System architecture<br>• Technology stack decisions<br>• API design standards<br>• Security policies |
| `/prd/` | • Overall product vision<br>• Cross-module features<br>• User journeys spanning modules<br>• System requirements |
| `/todos/` | • Release planning<br>• Multi-module integration<br>• Project milestones<br>• Team coordination |
| `/mistakes/` | • Framework issues<br>• Patterns to avoid project-wide<br>• Infrastructure problems<br>• Common pitfalls |

### 📦 Module Level (Module-Specific)

Use module-level directories for:
- Module implementation details
- Internal design decisions
- Module-specific tasks
- Isolated concerns

| Directory | Module Level Use Cases |
|-----------|----------------------|
| `adr/` | • Module algorithms<br>• Internal data structures<br>• Module-specific patterns<br>• Implementation choices |
| `prd/` | • Module features<br>• Module API specs<br>• Module-specific UI<br>• Internal requirements |
| `todos/` | • Implementation tasks<br>• Module bugs<br>• Module enhancements<br>• Developer assignments |
| `mistakes/` | • Module bugs<br>• Implementation errors<br>• Module-specific learnings<br>• Performance issues |

## Decision Tree

```
Is this about multiple modules or system-wide?
├─ YES → Use Root Level (/[directory]/)
└─ NO → Is this specific to one module?
    ├─ YES → Use Module Level (/src/solutions/[module]/[directory]/)
    └─ NO → Start at module level, elevate if needed
```

## Examples

### Architecture Decisions (ADR)

**Root ADR Example**: "Use PostgreSQL for all persistent storage"
- Affects: All modules
- Location: `/adr/0015-database-selection.md`

**Module ADR Example**: "Use B-tree index for user lookup"
- Affects: Only user_management module
- Location: `/src/solutions/user_management/adr/0003-user-index-structure.md`

### Product Requirements (PRD)

**Root PRD Example**: "Single Sign-On (SSO) Integration"
- Affects: Authentication across all modules
- Location: `/prd/0008-sso-integration.md`

**Module PRD Example**: "CSV Export Feature for Reports"
- Affects: Only reporting module
- Location: `/src/solutions/reporting/prd/0002-csv-export.md`

### Task Tracking (Todos)

**Root Todo Example**: "Prepare v2.0 release"
- Involves: Multiple modules, coordination needed
- Location: `/todos/000-master.md`

**Module Todo Example**: "Optimize query performance"
- Involves: Only analytics module
- Location: `/src/solutions/analytics/todos/000-master.md`

### Mistakes & Learnings

**Root Mistake Example**: "Circular dependency between shared utilities"
- Impact: Could affect any module using shared utilities
- Location: `/mistakes/000-master.md`

**Module Mistake Example**: "Memory leak in data processing loop"
- Impact: Only affects data_processor module
- Location: `/src/solutions/data_processor/mistakes/000-master.md`

## Benefits

### For Developers
- **Clear Ownership**: Know exactly where your work is tracked
- **Reduced Conflicts**: Work in isolation without merge conflicts
- **Better Focus**: Module-level tracking reduces noise

### For Team Leads
- **Visibility**: See both project and module progress
- **Coordination**: Root level for planning, module level for execution
- **Scalability**: Add modules without restructuring

### For Project
- **Modularity**: True module independence
- **Traceability**: Decisions stay with implementations
- **Flexibility**: Teams can work in parallel

## Best Practices

1. **Start Specific**: Begin at module level when unsure
2. **Elevate When Needed**: Move to root if multiple modules affected
3. **Cross-Reference**: Link between root and module docs when related
4. **Regular Review**: Periodically check if module items should be elevated
5. **Clear Naming**: Use consistent naming patterns across levels

## Migration Guide

If you're converting an existing project:

1. **Keep existing root-level** directories as-is
2. **Create module structure** using `create_module.py`
3. **Move module-specific items** from root to module directories
4. **Update references** to point to new locations
5. **Document the transition** in both root and module ADRs

## Quick Reference Card

```
📁 Project Root
├── 🌍 /adr/          → System architecture
├── 🌍 /prd/          → Product vision  
├── 🌍 /todos/        → Project coordination
├── 🌍 /mistakes/     → Common pitfalls
└── 📦 /src/solutions/
    └── [module]/
        ├── 📦 adr/      → Module design
        ├── 📦 prd/      → Module features
        ├── 📦 todos/    → Module tasks
        └── 📦 mistakes/ → Module learnings
```

## Creating New Modules

Use the provided script to ensure consistent structure:

```bash
python scripts/create_module.py my_new_module
```

This automatically creates all four directories with appropriate README files and templates.