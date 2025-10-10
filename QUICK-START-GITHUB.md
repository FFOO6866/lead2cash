# Quick Start: GitHub Project Setup

**Time Required:** 10-15 minutes
**Prerequisites:** GitHub account, GitHub CLI installed ✅

---

## Step-by-Step Guide

### 1. Authenticate with GitHub (2 min)

```powershell
# Open PowerShell and run:
gh auth login
```

**Follow the prompts:**
1. Select: **GitHub.com**
2. Select: **HTTPS**
3. Authenticate with: **Login with a web browser** (recommended)
4. Copy the one-time code shown
5. Press Enter to open browser
6. Paste code and authorize GitHub CLI

**Verify authentication:**
```powershell
gh auth status
```

You should see: ✓ Logged in to github.com as {your-username}

---

### 2. Edit Repository Owner (1 min)

Open `scripts\setup-github-project.ps1` and change line 14:

```powershell
# BEFORE:
$REPO_OWNER = "fujif"

# AFTER:
$REPO_OWNER = "your-github-username"  # ← Replace with your actual username
```

Save the file.

---

### 3. Run the Setup Script (5 min)

```powershell
cd C:\Users\fujif\OneDrive\Documents\GitHub\lead2cash
.\scripts\setup-github-project.ps1
```

**The script will:**
1. Ask if you want to create the repository (select **Y** if it doesn't exist)
2. Create 17 labels (you'll see "✓ Created" or "- Exists" for each)
3. Create 5 milestones
4. Create 19 issues with full descriptions

**If you see errors about existing labels/milestones:** This is normal if you run the script multiple times. It will skip existing items.

---

### 4. View Created Issues (1 min)

```powershell
gh issue list --repo {your-username}/lead2cash
```

You should see 19 issues listed.

**View a specific issue:**
```powershell
gh issue view 1 --repo {your-username}/lead2cash
```

---

### 5. Create GitHub Project - MANUAL STEP (5 min)

GitHub Projects v2 must be created manually. Follow these steps:

1. **Go to your projects page:**
   - Open browser: `https://github.com/{your-username}?tab=projects`

2. **Create new project:**
   - Click **"New Project"**
   - Select **"Board"** template
   - Name: `RRPS Lead-to-Cash POV (8-Week MVP)`
   - Click **"Create"**

3. **Add custom fields:**
   - Click **"+ New field"** in the top-right
   - Add these fields:
     - **Epic** (Text)
     - **Size** (Single select: S, M, L, XL)
     - **Sprint** (Text)

4. **Add all issues to project:**
   - Click **"Add item"** at bottom of board
   - Type `#` and you'll see your issues
   - Add issues one by one, OR use this command:

   ```powershell
   # First, get your project number (look at URL: projects/{NUMBER})
   # Then run:
   gh issue list --repo {your-username}/lead2cash --limit 100 --json number --jq '.[].number' | ForEach-Object {
       gh project item-add {PROJECT_NUMBER} --owner {your-username} --url "https://github.com/{your-username}/lead2cash/issues/$_"
   }
   ```

5. **Create views:**
   - Click **"+ New view"**
   - Create:
     - **Sprint Board:** Group by "Status", filter current sprint
     - **Epic View:** Group by "Epic"
     - **Timeline:** Layout = Timeline, group by Milestone

---

### 6. Push Repository to GitHub (1 min)

```powershell
cd C:\Users\fujif\OneDrive\Documents\GitHub\lead2cash

# Add all files
git add .

# Commit
git commit -m "Initial commit: RRPS Lead-to-Cash POV with GitHub project structure"

# Push to GitHub
git push -u origin master
```

**If you see "remote: Repository not found":**
```powershell
# Set the correct remote URL
git remote set-url origin https://github.com/{your-username}/lead2cash.git

# Try push again
git push -u origin master
```

---

## Done! 🎉

You now have:
- ✅ GitHub repository created
- ✅ 17 labels configured
- ✅ 5 milestones with due dates
- ✅ 19 issues created and categorized
- ✅ GitHub Project board (if you completed step 5)
- ✅ Repository pushed to GitHub

---

## Next Steps

### For You (Project Owner)

1. **Review all issues:**
   - Visit: `https://github.com/{your-username}/lead2cash/issues`
   - Check that all 19 issues are there

2. **Review GitHub Project:**
   - Visit: `https://github.com/{your-username}?tab=projects`
   - Verify all issues are in the project board

3. **Assign Sprint 0:**
   - Assign Sprint 0 issues to your backend engineer
   - Schedule Sprint 0 kickoff meeting

### For Your Team

1. **Share the repository:**
   ```powershell
   # Invite collaborators via GitHub UI:
   # Settings → Collaborators → Add people
   ```

2. **Share documentation:**
   - Send team: `docs/requirements.md` (full requirements)
   - Send team: `docs/github-project-setup.md` (setup guide)
   - Send team: `GITHUB-PROJECT-SUMMARY.md` (quick reference)

3. **Schedule meetings:**
   - Sprint 0 kickoff (2 hours) - walkthrough infrastructure setup
   - Daily standups starting Week 1 (15 min)
   - Sprint planning for Sprint 1 (1 hour)

---

## Troubleshooting

### Issue: "gh: command not found"
**Solution:** GitHub CLI is installed but not in PATH. Restart PowerShell.

### Issue: "authentication required"
**Solution:** Run `gh auth login` again.

### Issue: "repository not found"
**Solution:** The script will ask if you want to create it. Select **Y**.

### Issue: Script execution blocked
**Solution:** Run PowerShell as Administrator:
```powershell
Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope CurrentUser
```

### Issue: Labels/milestones already exist
**Solution:** This is normal if you run the script multiple times. It will skip existing items.

### Issue: Can't add issues to project
**Solution:** Make sure you have the correct project number (from the URL).

---

## Verification Checklist

After completing all steps, verify:

- [ ] `gh auth status` shows you're logged in
- [ ] Repository exists: `https://github.com/{your-username}/lead2cash`
- [ ] 19 issues visible in Issues tab
- [ ] 17 labels visible in Labels tab
- [ ] 5 milestones visible in Milestones tab
- [ ] GitHub Project created with all issues
- [ ] Repository pushed (commits visible on GitHub)

If all checkboxes are checked, you're ready to start Sprint 0! 🚀

---

## Quick Commands Reference

```powershell
# Authenticate
gh auth login

# View issues
gh issue list --repo {your-username}/lead2cash

# View specific issue
gh issue view {NUMBER} --repo {your-username}/lead2cash

# View project
gh project list --owner {your-username}

# Check git status
git status

# Push changes
git add .
git commit -m "Your message"
git push
```

---

**Need Help?**
- Full setup guide: `docs/github-project-setup.md`
- Full requirements: `docs/requirements.md`
- Quick reference: `GITHUB-PROJECT-SUMMARY.md`

**Ready to Start?**
Begin with Step 1 above! ☝️
