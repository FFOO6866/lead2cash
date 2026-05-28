# Mistake Documentation Template

Use this template for detailed documentation of complex issues.

## Error: [Brief Error Title]

**Date Encountered:** YYYY-MM-DD  
**Reporter:** [Your name/initials]  
**Severity:** Critical | High | Medium | Low  
**Status:** Active | Investigating | Resolved  
**Tags:** [setup, database, sdk, testing, api, deployment]

## Error Description

### What Happened
[Detailed description of what went wrong]

### Expected Behavior
[What should have happened instead]

### Actual Behavior
[What actually happened, including error messages]

## Environment Details

**App Version:** [App version or commit hash]  
**SDK Version:** [Kailash SDK version]  
**Python Version:** [Python version]  
**OS:** [Operating system]  
**Environment:** [Development | Testing | Production]

### Configuration
```bash
# Relevant configuration that might affect the issue
DATABASE_URL=...
DEBUG=True
```

## Error Messages

```
[Paste full error messages, stack traces, logs]
```

## Steps to Reproduce

1. [Step 1]
2. [Step 2]
3. [Step 3]
4. [Error occurs]

## Investigation Process

### Initial Diagnosis
[What you first thought the problem was]

### Steps Taken
1. [Investigation step 1]
2. [Investigation step 2]
3. [What you tried that didn't work]

### Tools Used
- [Debugging tools used]
- [Log files examined]
- [Commands run]

## Root Cause Analysis

### Why It Happened
[The underlying cause of the problem]

### Contributing Factors
- [Factor 1 that made it worse]
- [Factor 2 that made it harder to diagnose]

## Solution

### The Fix
[Detailed description of how you solved it]

### Code Changes
```python
# Before (broken)
old_code_example()

# After (fixed)
new_code_example()
```

### Configuration Changes
```bash
# Changes to .env file
NEW_SETTING=value

# Changes to setup.py
new_dependency==1.2.3
```

### Commands Run
```bash
# Commands needed to implement the fix
pip install new_package
python migrate.py
```

## Prevention Strategy

### Code Changes
- [Code patterns to prevent recurrence]
- [Validation to add]
- [Error handling to improve]

### Process Changes
- [Development process improvements]
- [Testing additions]
- [Documentation updates needed]

### Monitoring/Alerts
- [Monitoring to add to catch early]
- [Health checks to implement]

## Testing the Fix

### Verification Steps
1. [How to verify the fix works]
2. [Test cases to run]
3. [Regression tests to add]

### Test Results
- [Results of verification]
- [Any remaining issues]

## Impact Assessment

### Affected Components
- [What parts of the app were affected]
- [Dependencies that might be impacted]

### User Impact
- [How this affected end users]
- [Downtime or degraded functionality]

## Lessons Learned

### What We Learned
- [Key insights from this experience]
- [Better practices to adopt]

### Knowledge Gaps Identified
- [Areas where team needs more knowledge]
- [Documentation that was missing]

## Related Issues

### Similar Past Issues
- [Link to mistakes/XXX-similar-issue.md]
- [Reference to related problems]

### Dependencies
- [External issues this depends on]
- [Upstream bugs or limitations]

## References

- [Documentation links]
- [Stack Overflow discussions]
- [GitHub issues]
- [Team discussion links]

---

**Follow-up Actions:**
- [ ] Update documentation to prevent recurrence
- [ ] Add tests to catch this type of error
- [ ] Share learnings with other app teams (if relevant)
- [ ] Schedule review to ensure fix is holding