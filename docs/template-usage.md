# Using the Kailash SDK Template

This guide explains how to create new repositories from this template and how the automatic setup process works.

## 🚀 Creating a New Repository

### Method 1: GitHub Web Interface (Recommended)

1. **Navigate to the template**: Go to [new_project_template](https://github.com/Integrum-Global/new_project_template)
2. **Use Template**: Click the green "Use this template" button
3. **Create Repository**:
   - Choose repository name (e.g., `customer-analytics`, `sales-automation`)
   - Select visibility (private recommended for business solutions)
   - Click "Create repository from template"
4. **Automatic Setup**: The repository will automatically configure itself (see below)

### Method 2: GitHub CLI

```bash
gh repo create my-solution --template Integrum-Global/new_project_template --private
cd my-solution
# Automatic setup will run via GitHub Actions
```

### Method 3: Manual Clone and Setup

```bash
git clone https://github.com/Integrum-Global/new_project_template.git my-solution
cd my-solution
rm -rf .git
git init
git add .
git commit -m "Initial commit from template"
git remote add origin https://github.com/your-org/my-solution.git
git push -u origin main
# Automatic setup will run via GitHub Actions
```

## 🤖 Automatic Setup Process

When you create a repository from this template, the following happens automatically:

### 1. Template Initialization (GitHub Actions)
- **Trigger**: Runs on first push or when repository is created
- **Workflow**: `.github/workflows/template-init.yml`
- **Duration**: ~30 seconds

### 2. Automatic Configuration
The setup script (`scripts/setup_new_repo.py`) automatically:

#### ✅ **Template Sync Setup**
- Adds `kailash-template` topic to enable automatic template updates
- Adds `kailash` and `business-solutions` topics for organization
- Repository will now automatically receive template updates via PR

#### ✅ **Development Environment**
- Creates `.env.example` with common environment variables
- Updates `.gitignore` for solution development patterns
- Ensures sensitive data and artifacts are properly ignored

#### ✅ **Project Structure**
```
src/solutions/[repo-name]/      # Main solution code
├── __init__.py                 # Package initialization
├── workflow.py                 # Main workflow logic
├── config.py                   # Configuration management
└── README.md                   # Solution documentation

data/
├── inputs/                     # Input data files
├── outputs/                    # Generated outputs
├── configs/                    # Configuration files
└── samples/                    # Sample data

examples/                       # Example implementations
docs/solution/                  # Solution-specific docs
tests/                         # Test files
```

#### ✅ **Issue Tracking**
- Creates labels: `template-sync`, `solution-development`, `kailash`
- Sets up standard labels for enhancement, documentation, etc.

### 3. Initial Solution Template
- Creates a working solution template based on repository name
- Includes example workflow, configuration, and documentation
- Ready to run with `python -m solutions.[repo-name]`

## 🔄 Automatic Template Updates

Once configured, your repository will automatically receive updates:

### When Updates Happen
- **Trigger**: When the template repository is updated
- **Frequency**: Immediately after template changes are pushed
- **Method**: Automatic PR creation in your repository

### What Gets Updated
- **Always Updated**: `sdk-users/`, `.github/`, `scripts/`
- **Merged**: `CLAUDE.md` (preserves project-specific instructions)
- **Preserved**: Your solution code, data, custom configurations

### Update Process
1. Template detects repositories with `kailash-template` topic
2. Creates sync branch in your repository
3. Updates template-managed files
4. Creates PR for review: "Sync template updates"
5. You review and merge the PR

### Handling Conflicts
- Most updates are safe and automatic
- Review PR for any conflicts with your customizations
- Template preserves your solution-specific code and data
- Project-specific instructions in `CLAUDE.md` are preserved

## 📋 Manual Setup (If Needed)

If automatic setup doesn't run or you need to reconfigure:

### Re-run Setup
```bash
# From your repository root
python scripts/setup_new_repo.py
```

### Manual Topic Addition
```bash
# Add template topic for sync discovery
gh api /repos/YOUR-ORG/YOUR-REPO/topics --method PUT --raw-field names='["kailash-template","kailash","business-solutions"]'
```

### Manual Workflow Trigger
```bash
# In your repository
gh workflow run template-init.yml --field force_setup=true
```

## 🎯 Development Workflow

After setup, follow the 5-phase development process:

### 1. **Planning** (`todos/000-master.md`)
- Add your solution requirements to the master todo list
- Use `reference/pattern-library/` for solution architecture
- Plan using established patterns and templates

### 2. **Implementation** (`src/solutions/`)
- Develop in your solution directory
- Use `reference/cheatsheet/` for quick code patterns
- Follow the examples in `reference/templates/`

### 3. **Testing** (`tests/`)
- Write tests for your solution
- Use validation tools in `reference/validation/`
- Follow testing patterns in cheatsheet

### 4. **Documentation**
- Update solution README and documentation
- Track learnings in `mistakes/`
- Use established documentation patterns

### 5. **Deployment**
- Follow deployment patterns in `reference/cheatsheet/006-deployment-patterns.md`
- Use environment configuration from `.env.example`
- Follow production readiness checklist

## 🔧 Customization

### Adding Project-Specific Instructions
Edit `CLAUDE.md` and add your instructions under:
```markdown
## Project-Specific Instructions

<!-- Your custom instructions here -->
```
These will be preserved during template updates.

### Custom Patterns and Templates
- Add project-specific patterns to `reference/pattern-library/`
- Add custom templates to `reference/templates/`
- Create solution-specific cheatsheets in `reference/cheatsheet/`

### Custom Workflows
- Add custom GitHub Actions with `*_custom.yml` suffix
- These won't be overwritten by template updates

## 🆘 Troubleshooting

### Setup Didn't Run
- Check GitHub Actions tab for workflow status
- Manually trigger: `gh workflow run template-init.yml`
- Run setup script manually: `python scripts/setup_new_repo.py`

### Missing Template Updates
- Verify `kailash-template` topic: `gh api /repos/YOUR-ORG/YOUR-REPO --jq '.topics'`
- Add topic if missing: See manual topic addition above
- Check template repository Actions for sync failures

### Sync Conflicts
- Review PR carefully for conflicts
- Template preserves your code in `src/solutions/`, `data/`, custom configs
- Merge manually if needed, preferring your customizations for solution-specific files

## 📞 Support

- **Documentation**: Check `reference/` directory for comprehensive guides
- **Examples**: Review `examples/` for working implementations
- **Issues**: Use repository issues with appropriate labels
- **Template Issues**: Report at [new_project_template](https://github.com/Integrum-Global/new_project_template/issues)

---

**Ready to build amazing solutions with Kailash SDK! 🚀**
