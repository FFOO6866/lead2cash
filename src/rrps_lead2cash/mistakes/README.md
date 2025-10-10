# Mistake Tracking and Learning

This folder contains mistake tracking and learnings specific to this app only.

## Purpose

App-specific mistake tracking helps you:
- Learn from errors without repeating them
- Share knowledge with team members
- Build institutional knowledge
- Debug issues faster
- Improve development practices

## Structure

```
mistakes/
├── README.md           # This file - mistakes guide
├── 000-master.md       # Current known issues and quick fixes
├── template.md         # Template for documenting mistakes
└── archived/           # Historical mistakes and solutions
    └── 001-resolved.md
```

## Mistake Documentation Workflow

### 1. Encountered an Error?
```bash
# Immediately document it while fresh
echo "## [Date] Error: Brief description" >> mistakes/000-master.md
echo "**Problem:** What went wrong" >> mistakes/000-master.md
echo "**Solution:** How you fixed it" >> mistakes/000-master.md
echo "**Prevention:** How to avoid in future" >> mistakes/000-master.md
echo "" >> mistakes/000-master.md
```

### 2. Detailed Documentation
```bash
# For complex issues, create detailed documentation
cp mistakes/template.md mistakes/002-database-connection-issue.md
# Fill in all details about the problem and solution
```

### 3. Share Knowledge
- Update mistakes/000-master.md with quick fixes
- Create detailed docs for complex issues
- Review during team meetings
- Archive resolved issues periodically

## Common Mistake Categories

### Development Errors
- Import/dependency issues
- Configuration problems
- Database connection failures
- Authentication/authorization bugs

### SDK Usage Mistakes
- Incorrect node configurations
- Workflow connection errors
- Parameter mapping issues
- Runtime configuration problems

### Testing Issues
- Test setup failures
- Mock configuration problems
- Test data management
- CI/CD pipeline issues

### Deployment Problems
- Environment configuration
- Docker/container issues
- Database migration failures
- Service discovery problems

## Quick Reference Format

Use this format in 000-master.md:

```markdown
## [Date] Error: Brief Description
**Problem:** One-line description of what went wrong
**Solution:** One-line description of the fix
**Prevention:** How to avoid this in the future
**Tags:** [development, testing, deployment, sdk]
```

## Detailed Documentation Format

For complex issues, use template.md structure:
- **Error Description:** Full details
- **Environment:** When/where it occurred
- **Investigation:** Steps taken to diagnose
- **Root Cause:** Why it happened
- **Solution:** Complete fix with code examples
- **Prevention:** Process/code changes to prevent recurrence

## Team Learning Practices

### Daily Practices:
1. **Document immediately** when you hit an error
2. **Update quickly** when you find a solution
3. **Check first** before asking for help (search mistakes/)

### Weekly Practices:
1. **Review mistakes** during team meetings
2. **Archive resolved** issues to keep 000-master.md clean
3. **Identify patterns** in recurring mistakes

### Monthly Practices:
1. **Process improvements** based on mistake patterns
2. **Tool/configuration updates** to prevent common errors
3. **Knowledge sharing** with other app teams (optional)

## Search and Reference

```bash
# Find similar issues
grep -r "database connection" mistakes/
grep -r "authentication" mistakes/

# Quick lookup for common problems
cat mistakes/000-master.md | grep -A 3 "Error: Database"
```

## Integration with Development

### Code Comments:
```python
# See mistakes/003-async-deadlock.md for why we use this pattern
async def safe_database_operation():
    # Implementation based on lessons learned
```

### Documentation Links:
```markdown
## Common Issues
- Database setup: See [mistakes/002-db-setup.md](mistakes/002-db-setup.md)
- Authentication: See [mistakes/004-auth-config.md](mistakes/004-auth-config.md)
```

---

*These mistakes are specific to this app and help your team learn faster without conflicting with other teams' learning!*