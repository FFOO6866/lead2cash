# RRPS Lead-to-Cash POV - GitHub Setup Script
# Run this in PowerShell after authenticating with: gh auth login

$REPO_OWNER = "fujif"  # Change this to your GitHub username
$REPO_NAME = "lead2cash"
$REPO = "$REPO_OWNER/$REPO_NAME"

Write-Host "=== RRPS Lead-to-Cash POV - GitHub Setup ===" -ForegroundColor Cyan
Write-Host ""

# Check authentication
Write-Host "Checking GitHub authentication..." -ForegroundColor Yellow
gh auth status
if ($LASTEXITCODE -ne 0) {
    Write-Host "ERROR: Not authenticated. Please run: gh auth login" -ForegroundColor Red
    exit 1
}

# Create repository if it doesn't exist
Write-Host ""
Write-Host "Checking if repository exists..." -ForegroundColor Yellow
gh repo view $REPO 2>$null
if ($LASTEXITCODE -ne 0) {
    Write-Host "Creating repository: $REPO" -ForegroundColor Green
    gh repo create $REPO --public --description "RRPS Lead-to-Cash POV: AI-Powered Order Creation & Opportunity Qualification (8-Week MVP)" --confirm

    # Add remote and push
    git remote add origin "https://github.com/$REPO.git"
    git branch -M master
    git push -u origin master
} else {
    Write-Host "Repository already exists: $REPO" -ForegroundColor Green
}

# Create labels
Write-Host ""
Write-Host "Creating labels..." -ForegroundColor Yellow

$labels = @(
    @{name="epic-1-qualification"; color="0E8A16"; description="Epic 1: Opportunity Qualification"},
    @{name="epic-2-order-creation"; color="1D76DB"; description="Epic 2: Fast Order Creation"},
    @{name="size/S"; color="FBCA04"; description="Small effort"},
    @{name="size/M"; color="FFA500"; description="Medium effort"},
    @{name="size/L"; color="FF6B6B"; description="Large effort"},
    @{name="size/XL"; color="D73A4A"; description="Extra Large effort"},
    @{name="user-story"; color="5319E7"; description="User-facing feature story"},
    @{name="technical-enabler"; color="006B75"; description="Technical infrastructure"},
    @{name="infrastructure"; color="7057FF"; description="Infrastructure setup"},
    @{name="bug"; color="D93F0B"; description="Bug report"},
    @{name="uat"; color="FBCA04"; description="UAT testing"},
    @{name="priority/critical"; color="B60205"; description="Critical priority"},
    @{name="priority/high"; color="D93F0B"; description="High priority"},
    @{name="priority/medium"; color="FBCA04"; description="Medium priority"},
    @{name="priority/low"; color="0E8A16"; description="Low priority"},
    @{name="blocked"; color="D73A4A"; description="Blocked by dependency"},
    @{name="in-progress"; color="FFA500"; description="Currently in progress"},
    @{name="review"; color="FBCA04"; description="In review"},
    @{name="done"; color="0E8A16"; description="Completed"}
)

foreach ($label in $labels) {
    gh label create $label.name --color $label.color --description $label.description --repo $REPO --force 2>$null
    if ($LASTEXITCODE -eq 0) {
        Write-Host "  ✓ Created label: $($label.name)" -ForegroundColor Green
    }
}

# Create milestones
Write-Host ""
Write-Host "Creating milestones..." -ForegroundColor Yellow

$milestones = @(
    @{title="Sprint 0 - Infrastructure"; due="2025-10-24"; description="Week 0-2: Infrastructure setup, DataFlow validation, CPI integration testing"},
    @{title="Sprint 1 - Epic 1"; due="2025-10-24"; description="Week 1-2: Opportunity Qualification (Stories 1.1-1.3)"},
    @{title="Sprint 2 - Epic 2 Part 1"; due="2025-11-07"; description="Week 3-4: Order Creation - Data Retrieval and AI Validation (Stories 2.1-2.2)"},
    @{title="Sprint 3 - Epic 2 Part 2"; due="2025-11-21"; description="Week 5-6: Order Creation - SAP Submission and Audit Trail (Stories 2.3-2.4)"},
    @{title="Sprint 4 - UAT"; due="2025-12-05"; description="Week 7-8: UAT with 3-5 pilot users, 10 test orders"}
)

foreach ($milestone in $milestones) {
    gh api repos/$REPO/milestones -f title="$($milestone.title)" -f due_on="$($milestone.due)T23:59:59Z" -f description="$($milestone.description)" 2>$null
    if ($LASTEXITCODE -eq 0) {
        Write-Host "  ✓ Created milestone: $($milestone.title)" -ForegroundColor Green
    }
}

Write-Host ""
Write-Host "=== Setup Complete! ===" -ForegroundColor Green
Write-Host ""
Write-Host "Next steps:" -ForegroundColor Cyan
Write-Host "1. Go to: https://github.com/$REPO/issues" -ForegroundColor White
Write-Host "2. Create issues using the templates in .github/ISSUE_TEMPLATE/" -ForegroundColor White
Write-Host "3. Create a new Project at: https://github.com/$REPO_OWNER?tab=projects" -ForegroundColor White
Write-Host "4. Add all issues to the project board" -ForegroundColor White
Write-Host ""
Write-Host "Repository URL: https://github.com/$REPO" -ForegroundColor Yellow
