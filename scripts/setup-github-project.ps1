###############################################################################
# RRPS Lead-to-Cash POV - GitHub Project Setup Script (PowerShell)
#
# This script creates:
# - GitHub repository (if needed)
# - Labels, milestones, and project
# - All issues for Sprint 0, Epic 1, Epic 2, Technical Enablers, and UAT
#
# Prerequisites:
# 1. GitHub CLI installed: https://cli.github.com/
# 2. Authenticated: gh auth login
# 3. Repository created or script will create it
#
# Usage:
#   .\scripts\setup-github-project.ps1
###############################################################################

$ErrorActionPreference = "Stop"

# Configuration
$REPO_OWNER = "fujif"  # Change this to your GitHub username or org
$REPO_NAME = "lead2cash"
$REPO_FULL = "$REPO_OWNER/$REPO_NAME"

Write-Host "========================================" -ForegroundColor Cyan
Write-Host "RRPS Lead-to-Cash POV - GitHub Setup" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""
Write-Host "Repository: $REPO_FULL" -ForegroundColor Yellow
Write-Host ""

# Check if gh CLI is authenticated
try {
    gh auth status 2>&1 | Out-Null
} catch {
    Write-Host "ERROR: GitHub CLI not authenticated." -ForegroundColor Red
    Write-Host "Please run: gh auth login" -ForegroundColor Yellow
    exit 1
}

# Check if repository exists, create if needed
try {
    gh repo view "$REPO_FULL" 2>&1 | Out-Null
} catch {
    Write-Host "Repository $REPO_FULL does not exist." -ForegroundColor Yellow
    $response = Read-Host "Create it now? (y/n)"
    if ($response -eq 'y' -or $response -eq 'Y') {
        gh repo create "$REPO_FULL" --private --description "RRPS Lead-to-Cash POV - 8-Week MVP using Kailash SDK"
        git remote add origin "https://github.com/$REPO_FULL.git"
        Write-Host "Repository created successfully." -ForegroundColor Green
    } else {
        Write-Host "Exiting. Please create the repository manually." -ForegroundColor Yellow
        exit 1
    }
}

Write-Host ""
Write-Host "Step 1: Creating Labels..." -ForegroundColor Cyan
Write-Host "----------------------------"

# Function to create label (ignores if exists)
function Create-Label {
    param($Name, $Color, $Description)
    try {
        gh label create $Name --color $Color --description $Description --repo $REPO_FULL 2>&1 | Out-Null
        Write-Host "  ✓ Created: $Name" -ForegroundColor Green
    } catch {
        Write-Host "  - Exists: $Name" -ForegroundColor Gray
    }
}

# Epic labels
Create-Label "epic-1-qualification" "0E8A16" "Epic 1: Opportunity Qualification"
Create-Label "epic-2-order-creation" "1D76DB" "Epic 2: Fast Order Creation"

# Size labels
Create-Label "size/S" "FBCA04" "Small (1-2 days)"
Create-Label "size/M" "FFA500" "Medium (3-5 days)"
Create-Label "size/L" "D93F0B" "Large (1-2 weeks)"
Create-Label "size/XL" "B60205" "Extra Large (2-4 weeks)"

# Type labels
Create-Label "user-story" "5319E7" "User story"
Create-Label "technical-enabler" "0052CC" "Technical enabler/infrastructure"
Create-Label "infrastructure" "C5DEF5" "Infrastructure setup"
Create-Label "bug" "D73A4A" "Something isn't working"
Create-Label "uat" "EDEDED" "UAT testing and feedback"

# Priority labels
Create-Label "priority/critical" "B60205" "Critical priority"
Create-Label "priority/high" "D93F0B" "High priority"
Create-Label "priority/medium" "FBCA04" "Medium priority"
Create-Label "priority/low" "0E8A16" "Low priority"

# Status labels
Create-Label "blocked" "D93F0B" "Blocked by dependency"
Create-Label "in-progress" "1D76DB" "Currently in progress"
Create-Label "review" "FBCA04" "In review"
Create-Label "done" "0E8A16" "Completed"

Write-Host "Labels created successfully." -ForegroundColor Green

Write-Host ""
Write-Host "Step 2: Creating Milestones..." -ForegroundColor Cyan
Write-Host "--------------------------------"

# Function to create milestone (ignores if exists)
function Create-Milestone {
    param($Title, $Description, $WeeksOffset)
    try {
        $dueDate = (Get-Date).AddDays($WeeksOffset * 7).ToString("yyyy-MM-ddT23:59:59Z")
        $body = @{
            title = $Title
            description = $Description
            due_on = $dueDate
        } | ConvertTo-Json

        gh api "repos/$REPO_FULL/milestones" -X POST --input - <<< $body 2>&1 | Out-Null
        Write-Host "  ✓ Created: $Title" -ForegroundColor Green
    } catch {
        Write-Host "  - Exists: $Title" -ForegroundColor Gray
    }
}

# Note: PowerShell date calculation
Create-Milestone "Sprint 0 - Infrastructure (Week 0-2)" "Infrastructure setup, CPI validation, DataFlow alpha testing" 2
Create-Milestone "Sprint 1 - Epic 1 (Week 1-2)" "Opportunity Qualification - 3 stories" 2
Create-Milestone "Sprint 2 - Epic 2 Part 1 (Week 3-4)" "Order Creation - Stories 2.1-2.2" 4
Create-Milestone "Sprint 3 - Epic 2 Part 2 (Week 5-6)" "Order Creation - Stories 2.3-2.4" 6
Create-Milestone "Sprint 4 - UAT (Week 7-8)" "User Acceptance Testing with 10 test orders" 8

Write-Host "Milestones created successfully." -ForegroundColor Green

Write-Host ""
Write-Host "Step 3: Creating Project..." -ForegroundColor Cyan
Write-Host "----------------------------"

Write-Host "Creating GitHub Project (you may need to do this manually)..." -ForegroundColor Yellow
Write-Host "Project Name: RRPS Lead-to-Cash POV (8-Week MVP)" -ForegroundColor White
Write-Host "Description: Prove AI agents can deliver opportunity qualification + fast order creation" -ForegroundColor White
Write-Host ""
Write-Host "Manual steps (if automated creation fails):" -ForegroundColor Yellow
Write-Host "1. Go to: https://github.com/$REPO_OWNER?tab=projects"
Write-Host "2. Click 'New Project'"
Write-Host "3. Name: RRPS Lead-to-Cash POV (8-Week MVP)"
Write-Host "4. Add custom fields: Epic (text), Size (single-select: S/M/L/XL), Sprint (text)"
Write-Host "5. Create views: Sprint Board, Epic View, Timeline"
Write-Host ""

Write-Host ""
Write-Host "Step 4: Creating Issues..." -ForegroundColor Cyan
Write-Host "----------------------------"
Write-Host ""

# Function to create issue
function Create-Issue {
    param($Title, $Body, $Labels, $Milestone)

    Write-Host "Creating: $Title" -ForegroundColor White
    try {
        # Create issue body file temporarily
        $tempFile = [System.IO.Path]::GetTempFileName()
        $Body | Out-File -FilePath $tempFile -Encoding UTF8

        gh issue create `
            --repo $REPO_FULL `
            --title $Title `
            --body-file $tempFile `
            --label $Labels `
            --milestone $Milestone 2>&1 | Out-Null

        Remove-Item $tempFile
        Write-Host "  ✓ Created successfully" -ForegroundColor Green
    } catch {
        Write-Host "  - Issue may already exist or error occurred" -ForegroundColor Gray
    }
}

# Due to PowerShell here-string limitations, issue bodies are stored in separate files
# This script will read from the templates directory
# For simplicity, we'll create a condensed version here

Write-Host "Creating Sprint 0 checklist..." -ForegroundColor Yellow
Create-Issue `
    "Sprint 0: Infrastructure Setup Checklist" `
    "See docs/requirements.md Sprint 0 section for full checklist. This is the CRITICAL PATH for the POV." `
    "infrastructure,priority/critical" `
    "Sprint 0 - Infrastructure (Week 0-2)"

Write-Host ""
Write-Host "Creating Technical Enabler issues..." -ForegroundColor Yellow

$TEs = @(
    @{Title="TE-2: CEC OData Client"; Labels="technical-enabler,infrastructure,priority/critical"; Milestone="Sprint 0 - Infrastructure (Week 0-2)"},
    @{Title="TE-3: IPAS Client"; Labels="technical-enabler,infrastructure,priority/high"; Milestone="Sprint 0 - Infrastructure (Week 0-2)"},
    @{Title="TE-4: Opportunity Readiness Agent (Kaizen)"; Labels="technical-enabler,priority/high,epic-1-qualification"; Milestone="Sprint 1 - Epic 1 (Week 1-2)"},
    @{Title="TE-5: MS5 BAPI Client (BAPI_SALESORDER_SIMULATE)"; Labels="technical-enabler,infrastructure,priority/critical"; Milestone="Sprint 0 - Infrastructure (Week 0-2)"},
    @{Title="TE-6: MS5 IDoc Client (ORDERS05 Submission)"; Labels="technical-enabler,infrastructure,priority/critical"; Milestone="Sprint 0 - Infrastructure (Week 0-2)"},
    @{Title="TE-8: Order Orchestration Agent (Kaizen)"; Labels="technical-enabler,priority/critical,epic-2-order-creation"; Milestone="Sprint 2 - Epic 2 Part 1 (Week 3-4)"},
    @{Title="TE-10: Idempotency Layer"; Labels="technical-enabler,infrastructure,priority/high"; Milestone="Sprint 3 - Epic 2 Part 2 (Week 5-6)"},
    @{Title="TE-12: SAP Customer Master Client"; Labels="technical-enabler,infrastructure,priority/medium"; Milestone="Sprint 0 - Infrastructure (Week 0-2)"},
    @{Title="TE-14: Audit Store (DataFlow + PostgreSQL)"; Labels="technical-enabler,infrastructure,priority/critical"; Milestone="Sprint 0 - Infrastructure (Week 0-2)"},
    @{Title="TE-15: Provenance Tracking"; Labels="technical-enabler,infrastructure,priority/medium"; Milestone="Sprint 4 - UAT (Week 7-8)"}
)

foreach ($TE in $TEs) {
    Create-Issue $TE.Title "See issue template and docs/requirements.md for details." $TE.Labels $TE.Milestone
}

Write-Host ""
Write-Host "Creating Epic 1 user stories..." -ForegroundColor Yellow

$Epic1Stories = @(
    @{Title="Story 1.1: Search Opportunities by Customer/Product"; Labels="user-story,epic-1-qualification,size/S,priority/high"; Milestone="Sprint 1 - Epic 1 (Week 1-2)"},
    @{Title="Story 1.2: Filter Opportunities by Readiness Criteria"; Labels="user-story,epic-1-qualification,size/M,priority/high"; Milestone="Sprint 1 - Epic 1 (Week 1-2)"},
    @{Title="Story 1.3: View AI Confidence Reasoning"; Labels="user-story,epic-1-qualification,size/S,priority/medium"; Milestone="Sprint 1 - Epic 1 (Week 1-2)"}
)

foreach ($story in $Epic1Stories) {
    Create-Issue $story.Title "See issue template and docs/requirements.md for full acceptance criteria and technical implementation." $story.Labels $story.Milestone
}

Write-Host ""
Write-Host "Creating Epic 2 user stories..." -ForegroundColor Yellow

$Epic2Stories = @(
    @{Title="Story 2.1: Auto-Retrieve Order Data from Multiple Systems"; Labels="user-story,epic-2-order-creation,size/L,priority/critical"; Milestone="Sprint 2 - Epic 2 Part 1 (Week 3-4)"},
    @{Title="Story 2.2: AI Agent Validates & Populates IDoc Fields"; Labels="user-story,epic-2-order-creation,size/XL,priority/critical"; Milestone="Sprint 2 - Epic 2 Part 1 (Week 3-4)"},
    @{Title="Story 2.3: Submit Order to SAP & Receive Confirmation"; Labels="user-story,epic-2-order-creation,size/M,priority/critical"; Milestone="Sprint 3 - Epic 2 Part 2 (Week 5-6)"},
    @{Title="Story 2.4: View Order Status & Audit Trail"; Labels="user-story,epic-2-order-creation,size/S,priority/medium"; Milestone="Sprint 3 - Epic 2 Part 2 (Week 5-6)"}
)

foreach ($story in $Epic2Stories) {
    Create-Issue $story.Title "See issue template and docs/requirements.md for full acceptance criteria and technical implementation." $story.Labels $story.Milestone
}

Write-Host ""
Write-Host "Creating UAT Sprint meta-issue..." -ForegroundColor Yellow
Create-Issue `
    "UAT Sprint: Week 7-8 Testing & Metrics" `
    "See docs/requirements.md UAT section for full scope, success criteria, and metrics collection." `
    "uat,priority/critical,size/L" `
    "Sprint 4 - UAT (Week 7-8)"

Write-Host ""
Write-Host "========================================" -ForegroundColor Cyan
Write-Host "GitHub Project Setup Complete!" -ForegroundColor Green
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""
Write-Host "Summary:" -ForegroundColor Cyan
Write-Host "--------"
Write-Host "✅ Labels created (17 labels)" -ForegroundColor Green
Write-Host "✅ Milestones created (5 milestones)" -ForegroundColor Green
Write-Host "✅ Issues created:" -ForegroundColor Green
Write-Host "   - 1 Sprint 0 checklist"
Write-Host "   - 10 Technical Enablers (TE-2, TE-3, TE-4, TE-5, TE-6, TE-8, TE-10, TE-12, TE-14, TE-15)"
Write-Host "   - 7 User Stories (3 in Epic 1, 4 in Epic 2)"
Write-Host "   - 1 UAT Sprint meta-issue"
Write-Host "   Total: 19 issues"
Write-Host ""
Write-Host "Next Steps:" -ForegroundColor Cyan
Write-Host "-----------"
Write-Host "1. View all issues: gh issue list --repo $REPO_FULL"
Write-Host "2. Create GitHub Project manually:"
Write-Host "   - Go to: https://github.com/$REPO_OWNER?tab=projects"
Write-Host "   - Click 'New Project' → 'Board' view"
Write-Host "   - Name: RRPS Lead-to-Cash POV (8-Week MVP)"
Write-Host "   - Add custom fields: Epic (text), Size (select: S/M/L/XL), Sprint (text)"
Write-Host "   - Add all issues to project"
Write-Host "3. Configure issue dependencies in project board"
Write-Host "4. Push this repo to GitHub: git push -u origin master"
Write-Host ""
Write-Host "Repository URL: https://github.com/$REPO_FULL" -ForegroundColor Yellow
Write-Host ""
