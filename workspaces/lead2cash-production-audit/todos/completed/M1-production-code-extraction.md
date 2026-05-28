# M1: Production Code Extraction & Reconciliation — COMPLETED

**Completed**: 2026-05-28 (session 1)

## Summary

| Todo | Status | Details |
|------|--------|---------|
| M1-T01 | DONE | `docker cp` + SCP: 250 Python files + 88 non-Python files extracted |
| M1-T02 | DONE | Full inventory: 15 agents, 27 core modules, 8 integrations, 90+ services, 55+ tests |
| M1-T03 | DONE | Copied to `src/lead_to_cash/` (excluded `rr-kailash.pem`, `.env.production`) |
| M1-T04 | PENDING | Package name reconciliation — requires architectural decision |
| M1-T05 | DONE | `SAP_CPI_BASE_URL` fallback to `SAP_CPI_DEV_URL` in sap_cpi_client.py |

## Extraction Details

- **Source**: `lead-to-cash-app:/app/src/lead_to_cash/` on rr.kailash.ai
- **Container status**: Up 4 weeks (healthy) at time of extraction
- **Archive**: `extracted/extracted_lead_to_cash.tar.gz` (12MB)
- **Excluded from commit**: `rr-kailash.pem` (SSH key), `.env.production` (credentials), `._*` (macOS resource forks)

## Key Findings

- Production has 15 agents (not 8 as originally estimated in journal 0007)
- Production has full reasoning pipeline: detector, evaluator, executor, planner
- Production has 55+ tests (unit, integration, e2e) — these can bootstrap M8
- Production has its own knowledge base with 25+ files and SQL migrations
- Production has competitor intelligence scraping suite (16 files)
- Production has marine intelligence module with embeddings

## Verification

- `find src/lead_to_cash/ -type f | wc -l` = 338 files
- No `*.pem` files in committed code
- No `.env.production` in committed code
- `extracted/` added to `.gitignore`
