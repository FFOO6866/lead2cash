# Known Issues and Quick Fixes - [App Name]

**Last Updated:** YYYY-MM-DD  
**Quick Search:** Use Ctrl+F to find errors quickly

## 🚨 Current Active Issues

### [Date] Error: [Issue currently being worked on]
**Problem:** [Description of current problem]  
**Status:** Investigating | Testing Fix | Blocked  
**Assigned:** [Team member working on it]  
**Workaround:** [Temporary solution if available]

---

## ✅ Resolved Issues (Quick Reference)

### [Date] Error: Template Setup Error
**Problem:** Copied template but imports failing  
**Solution:** Update all import paths from "new_project" to actual app name  
**Prevention:** Use search/replace for app name after copying template  
**Tags:** [setup, imports]

### [Date] Error: Database Connection Failed
**Problem:** Cannot connect to database on first run  
**Solution:** Run `python setup.py develop` and check .env file  
**Prevention:** Always check environment variables are set correctly  
**Tags:** [database, setup]

### [Date] Error: Workflow Node Not Found
**Problem:** Custom node not recognized by Kailash SDK  
**Solution:** Add proper __init__.py imports and check node registration  
**Prevention:** Follow SDK node creation patterns exactly  
**Tags:** [sdk, workflows]

### [Date] Error: Test Discovery Issues
**Problem:** pytest not finding tests  
**Solution:** Ensure all test directories have __init__.py files  
**Prevention:** Use template test structure without modifications  
**Tags:** [testing]

### [Date] Error: API Endpoint 404
**Problem:** FastAPI routes not loading  
**Solution:** Check route registration in api/main.py  
**Prevention:** Follow FastAPI app structure in template  
**Tags:** [api, routing]

---

## 📝 Mistake Patterns

### Most Common Issues:
1. **Import Path Errors** (40% of early issues)
   - Always update import paths after copying template
   - Use relative imports within app

2. **Environment Configuration** (30% of setup issues)
   - Check .env file exists and has correct values
   - Verify database connection strings

3. **SDK Node Registration** (20% of workflow issues)
   - Follow exact SDK patterns for custom nodes
   - Check imports and initialization

### Prevention Checklist:
- [ ] Updated all import paths from template
- [ ] Configured environment variables
- [ ] Registered custom nodes properly
- [ ] Added __init__.py to all Python directories
- [ ] Followed SDK workflow patterns

---

## 🔍 Search Tips

**Search by category:**
- `[setup]` - Initial app setup issues
- `[database]` - Database connection/operation issues
- `[sdk]` - Kailash SDK usage issues
- `[testing]` - Test-related problems
- `[api]` - API/endpoint issues
- `[deployment]` - Deployment and configuration

**Search by component:**
- `Database` - All database-related issues
- `Workflow` - SDK workflow issues
- `Authentication` - Auth-related problems
- `Import` - Import/module issues

---

**Template Instructions:**
1. Replace "[App Name]" with your actual app name
2. Document errors as they happen (don't wait!)
3. Update solutions when you find fixes
4. Use tags for easy searching
5. Archive to archived/ folder monthly to keep this file manageable
6. Remove this instruction section once you start using it