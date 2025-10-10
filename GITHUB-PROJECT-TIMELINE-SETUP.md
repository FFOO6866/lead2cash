# GitHub Project Timeline Setup Guide

This guide shows you how to add timeline/roadmap view to your GitHub Project.

**Project URL:** https://github.com/users/FFOO6866/projects/1

---

## Current Status

✅ **Complete:**
- 9 user stories created (Sprint 0, Stories 1.1-1.3, 2.1-2.4, UAT)
- 5 sprint milestones with dates (Nov 2025 - Jan 2026)
- 1 go-live milestone (Feb 2026)
- All stories added to project board
- Technical Enablers separated (not in project)

⚠️ **Need Manual Setup:**
- Timeline fields (Start Date, End Date)
- Roadmap view
- Sprint field (custom field)

---

## Step-by-Step Timeline Setup

### Step 1: Add Custom Fields

1. Go to your project: https://github.com/users/FFOO6866/projects/1
2. Click the **"+"** button next to the existing fields (top right)
3. Add these fields:

   **Field 1: Sprint**
   - Name: `Sprint`
   - Type: `Single select`
   - Options:
     - Sprint 0 (Nov 11-22)
     - Sprint 1 (Nov 18-29)
     - Sprint 2 (Dec 2-13)
     - Sprint 3 (Dec 16-27)
     - Sprint 4 (Jan 6-17)
     - Go-Live (Feb 2026)

   **Field 2: Start Date**
   - Name: `Start Date`
   - Type: `Date`

   **Field 3: End Date**
   - Name: `End Date`
   - Type: `Date`

   **Field 4: Size**
   - Name: `Size`
   - Type: `Single select`
   - Options:
     - S (Small)
     - M (Medium)
     - L (Large)
     - XL (Extra Large)

### Step 2: Populate Dates for Each Story

Click on each story and add dates:

| Story | Sprint | Start Date | End Date | Size |
|-------|--------|------------|----------|------|
| Sprint 0: Infrastructure Setup | Sprint 0 | Nov 11, 2025 | Nov 22, 2025 | - |
| Story 1.1: Search Opportunities | Sprint 1 | Nov 18, 2025 | Nov 20, 2025 | S |
| Story 1.2: Filter by Readiness | Sprint 1 | Nov 21, 2025 | Nov 26, 2025 | M |
| Story 1.3: View AI Reasoning | Sprint 1 | Nov 27, 2025 | Nov 29, 2025 | S |
| Story 2.1: Auto-Retrieve Data | Sprint 2 | Dec 2, 2025 | Dec 6, 2025 | L |
| Story 2.2: AI Populates Fields ⭐ | Sprint 2 | Dec 7, 2025 | Dec 13, 2025 | XL |
| Story 2.3: Submit to SAP | Sprint 3 | Dec 16, 2025 | Dec 20, 2025 | M |
| Story 2.4: View Audit Trail | Sprint 3 | Dec 23, 2025 | Dec 27, 2025 | S |
| Sprint 4: UAT | Sprint 4 | Jan 6, 2026 | Jan 17, 2026 | L |

### Step 3: Create Roadmap View

1. Click **"New view"** (top right, next to current table view)
2. Select **"Roadmap"**
3. Name it: `Timeline - Nov 2025 to Feb 2026`
4. Configure:
   - Group by: `Sprint`
   - Date field: Use `Start Date` and `End Date`
   - Zoom level: Weekly
5. Save view

### Step 4: Create Sprint Board View

1. Click **"New view"**
2. Select **"Board"**
3. Name it: `Sprint Board`
4. Configure:
   - Group by: `Status` (Todo, In Progress, Done)
   - Filter by: Current sprint (e.g., `Sprint = Sprint 1`)
5. Save view

---

## Recommended Project Views

Once setup is complete, you'll have:

1. **Table View (Default)**
   - Shows all stories with all fields
   - Best for: Planning and overview

2. **Roadmap View**
   - Shows timeline with bars for each story
   - Best for: Visualizing sprint schedule and dependencies

3. **Sprint Board View**
   - Kanban board filtered to current sprint
   - Best for: Daily standup and sprint execution

4. **Milestone View** (Optional)
   - Group by: `Milestone`
   - Best for: Tracking sprint completion

---

## Sample Roadmap Visualization

After setup, your roadmap will look like:

```
Nov 2025                  Dec 2025                  Jan 2026      Feb 2026
|------Sprint 0------|
          |------Sprint 1------|
                          |------Sprint 2------|
                                          |------Sprint 3------|
                                                          |---Sprint 4---|
                                                                      Go-Live
```

With individual stories shown as bars within each sprint.

---

## Tips for Using Timeline View

### 1. Color Code by Epic
- Edit each story
- Add label color:
  - Epic 1 (Green): Stories 1.1-1.3
  - Epic 2 (Blue): Stories 2.1-2.4
  - Infrastructure (Purple): Sprint 0
  - UAT (Yellow): Sprint 4

### 2. Track Dependencies
- Use GitHub's task lists within story descriptions
- Example in Story 2.2:
  ```markdown
  ## Dependencies
  - [ ] #15 (Story 2.1) must be complete
  - [ ] #7 (TE-8) must be validated
  ```

### 3. Filter by Current Sprint
- Create saved filter: `Sprint = Sprint 1`
- Switch filter weekly to focus on current work

### 4. Mark Blockers
- Add custom field: `Blocked` (checkbox)
- Filter: `Blocked = true` to see all blockers

---

## Automation (Optional)

GitHub Projects supports automation:

1. **Auto-assign to Sprint:**
   - When issue is assigned to milestone "Sprint 1"
   - Set field `Sprint` = "Sprint 1"

2. **Auto-update Status:**
   - When PR is merged
   - Move story to "Done"

To set up:
1. Click **"⋯"** (three dots) → **"Workflows"**
2. Enable built-in workflows or create custom ones

---

## Weekly Sprint Tracking

Use this checklist weekly:

**Monday (Sprint Start):**
- [ ] Move current sprint stories to "In Progress"
- [ ] Verify all dependencies are met
- [ ] Update roadmap view to focus on current sprint

**Friday (Sprint End):**
- [ ] Move completed stories to "Done"
- [ ] Update story dates if slipped
- [ ] Review next sprint stories
- [ ] Update risk register if blockers found

---

## Critical Dates to Track

Add these as manual items to your calendar:

- **Nov 11, 2025**: POV Kickoff
- **Nov 22, 2025**: Sprint 0 Due (Infrastructure ready)
- **Dec 27, 2025**: Epic 2 Complete (Orders can be submitted)
- **Jan 17, 2026**: UAT Complete
- **Jan 20, 2026**: **POV DECISION MEETING** (Scale/Iterate/Stop)
- **Feb 28, 2026**: Go-Live Target

---

## Troubleshooting

**Q: I don't see "Roadmap" option when creating new view**
- A: Roadmap requires `Start Date` and `End Date` fields to be created first

**Q: Stories don't show up in roadmap**
- A: Make sure each story has both `Start Date` and `End Date` populated

**Q: Can I see Technical Enablers in the roadmap?**
- A: No, TEs were intentionally removed from project. They're tracked in "Technical Enablers" milestone but referenced as dependencies in user stories.

**Q: How do I add Sprint 0 back if I deleted it?**
- A: Run: `gh project item-add 1 --owner FFOO6866 --url "https://github.com/FFOO6866/lead2cash/issues/1"`

---

## Next Steps

1. ✅ Complete Step 1-4 above to set up timeline
2. 📅 Schedule POV Kickoff meeting for Nov 11, 2025
3. 👥 Invite pilot users (3-5 people) for Sprint 4 UAT
4. 📊 Set up weekly sprint review meetings (Fridays 2 PM)
5. 🔔 Enable GitHub notifications for project updates

---

## Resources

- **Project Board:** https://github.com/users/FFOO6866/projects/1
- **Repository:** https://github.com/FFOO6866/lead2cash
- **Full Timeline:** `PROJECT-TIMELINE.md`
- **Requirements:** `docs/requirements.md`
- **GitHub Projects Docs:** https://docs.github.com/en/issues/planning-and-tracking-with-projects

---

**Last Updated:** October 10, 2025
**Next Review:** November 11, 2025 (POV Kickoff)
