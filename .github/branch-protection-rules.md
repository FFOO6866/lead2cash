# Branch Protection Rules for `main`

## Recommended Settings

### 1. **Require a pull request before merging**
- ✅ **Enable this rule**
- Required approvals: **1** (or 2 for critical projects)
- ✅ Dismiss stale pull request approvals when new commits are pushed
- ✅ Require review from CODEOWNERS (if you have a CODEOWNERS file)
- ❌ Restrict who can dismiss pull request reviews (optional, for larger teams)
- ✅ Require approval of the most recent reviewable push

### 2. **Require status checks to pass before merging**
- ✅ **Enable this rule**
- ✅ Require branches to be up to date before merging

#### Required Status Checks:
Select these specific checks from the PR Checks workflow:
- `Lint and Format Check`
- `Test Python 3.11`
- `Test Python 3.12`
- `Validate Examples`
- `PR Summary`

#### Optional Status Checks (if security is critical):
- `Security Scan`

### 3. **Require conversation resolution before merging**
- ✅ **Enable this rule**
- Ensures all PR comments are addressed

### 4. **Require signed commits** (Optional)
- ⚠️ Enable if your team uses commit signing
- Adds extra security but requires GPG setup

### 5. **Require linear history** (Optional)
- ⚠️ Enable if you prefer a clean git history
- Prevents merge commits, only allows rebase/squash

### 6. **Include administrators**
- ❌ Generally disabled for flexibility
- ✅ Enable for maximum protection (even admins must follow rules)

### 7. **Restrict who can push to matching branches**
- ⚠️ Optional - only if you want to limit direct pushes
- Suggested: Allow repository admins and specific team members

### 8. **Rules for force pushes and deletions**
- ✅ Block force pushes
- ✅ Block deletions

## Setting Up in GitHub

### Via GitHub UI:
1. Go to Settings → Branches
2. Add rule → Branch name pattern: `main`
3. Configure the protection rules above
4. Create

### Via GitHub CLI:
```bash
# Create branch protection rule
gh api repos/:owner/:repo/branches/main/protection \
  --method PUT \
  --field required_status_checks='{"strict":true,"contexts":["Lint and Format Check","Test Python 3.11","Test Python 3.12","Validate Examples","PR Summary"]}' \
  --field enforce_admins=false \
  --field required_pull_request_reviews='{"required_approving_review_count":1,"dismiss_stale_reviews":true}' \
  --field restrictions=null \
  --field allow_force_pushes=false \
  --field allow_deletions=false \
  --field required_conversation_resolution=true
```

## Why These Rules?

### Critical Checks Only
We only require the PR Checks workflow statuses because:
- **CI (Quick Tests)** runs on feature branches for feedback
- **Full Test Suite** runs AFTER merge to main
- **PR Checks** validates everything needed before merge

### No Duplicate Requirements
We don't require:
- `basic-test` from ci.yml (already covered by PR checks)
- `full-test` from full-test.yml (runs after merge)
- Individual CI jobs (PR checks are comprehensive)

### Flexibility vs Protection Balance
- Allows admins to bypass in emergencies (disable if not needed)
- Requires reviews but not excessive approvals
- Focuses on automated quality gates

## Additional Recommendations

### 1. **CODEOWNERS File**
Create `.github/CODEOWNERS`:
```
# Global owners
* @your-username @team-lead

# Python code
*.py @python-team
/src/ @python-team
/tests/ @python-team @qa-team

# Documentation
/docs/ @docs-team @python-team
*.md @docs-team

# GitHub Actions
/.github/workflows/ @devops-team @python-team
```

### 2. **Auto-merge for Dependabot**
If using Dependabot:
```yaml
# .github/auto-merge.yml
- match:
    dependency_type: "development"
    update_type: "semver:patch"
```

### 3. **Branch Naming Enforcement**
Consider enforcing branch naming patterns:
- `feat/*` - New features
- `fix/*` - Bug fixes
- `docs/*` - Documentation only
- `refactor/*` - Code refactoring
- `test/*` - Test additions/fixes
- `chore/*` - Maintenance tasks

## Monitoring and Adjustments

### Review Weekly:
- Check if required checks are too strict/lenient
- Monitor PR merge times
- Adjust based on team feedback

### Signs to Adjust:
- **Too Strict**: PRs taking too long, blocking valid changes
- **Too Lenient**: Quality issues in main branch
- **Missing Checks**: Add new required status checks as needed
