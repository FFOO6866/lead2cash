# Task Tracking (Todos)

This folder contains task tracking specific to this app only.

## Purpose

App-specific task tracking helps you:
- Track development progress without conflicts
- Organize work by priority and status
- Maintain visibility into current tasks
- Plan upcoming development work
- Coordinate with team members working on this app

## Structure

```
todos/
├── README.md           # This file - todo guide
├── 000-master.md       # Current active tasks
├── template.md         # Template for new tasks
└── completed/          # Archive of completed tasks
    └── 001-initial.md
```

## Task Management Workflow

### 1. View Current Tasks
```bash
cat todos/000-master.md
```

### 2. Add New Tasks
```bash
echo "- [ ] Implement user authentication" >> todos/000-master.md
echo "- [ ] Add email validation" >> todos/000-master.md
echo "- [ ] Write API tests" >> todos/000-master.md
```

### 3. Update Task Status
```bash
# Mark tasks as completed
sed -i 's/- \[ \] Implement user authentication/- \[x\] Implement user authentication/' todos/000-master.md
```

### 4. Archive Completed Work
```bash
# When 000-master.md gets too long, archive completed items
grep "- \[x\]" todos/000-master.md > todos/completed/002-week-ending-$(date +%Y-%m-%d).md
grep "- \[ \]" todos/000-master.md > todos/000-master-new.md
mv todos/000-master-new.md todos/000-master.md
```

## Task Categories

### Development Tasks
- [ ] Core model implementation
- [ ] API endpoint development
- [ ] Workflow creation
- [ ] Database schema updates

### Testing Tasks
- [ ] Unit test coverage
- [ ] Integration test scenarios
- [ ] End-to-end test automation
- [ ] Performance testing

### Documentation Tasks
- [ ] API documentation
- [ ] User guide updates
- [ ] Architecture documentation
- [ ] Deployment instructions

### DevOps Tasks
- [ ] CI/CD pipeline setup
- [ ] Docker configuration
- [ ] Environment configuration
- [ ] Monitoring setup

## Priority Levels

Use labels to indicate priority:
- `🔥 HIGH`: - [ ] 🔥 Critical bug fix
- `⚡ MED`: - [ ] ⚡ Feature development  
- `📋 LOW`: - [ ] 📋 Documentation update

## Status Tracking

- `[ ]` - Not started
- `[~]` - In progress
- `[x]` - Completed
- `[!]` - Blocked
- `[?]` - Needs clarification

## Example Usage

```bash
# Daily standup - check current tasks
cat todos/000-master.md

# Planning session - add new tasks
echo "- [ ] 🔥 Fix authentication bug" >> todos/000-master.md
echo "- [ ] ⚡ Add user profile editing" >> todos/000-master.md
echo "- [ ] 📋 Update API documentation" >> todos/000-master.md

# During development - update status
# Change [ ] to [~] when starting work
# Change [~] to [x] when completed
```

## Team Coordination

### For Multi-Developer Teams:
1. **Assign tasks**: Add initials to tasks (e.g., "- [ ] Fix bug [JS]")
2. **Daily updates**: Update task status daily
3. **Weekly review**: Archive completed tasks weekly
4. **Sprint planning**: Add new tasks from backlog

### Avoiding Conflicts:
- Each app has its own todos/ folder
- No shared task files between apps
- Use solutions/todos/ for cross-app coordination

---

*These tasks are specific to this app and won't conflict with other teams' work!*