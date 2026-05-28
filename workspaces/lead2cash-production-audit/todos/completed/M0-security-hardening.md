# M0: Security Hardening — COMPLETED

**Completed**: 2026-05-28 (session 1)

## Summary

All 10 of 11 security todos implemented. M0-T11 (rate limiting) deferred to Wave 2.

| Todo | Status | File(s) Changed |
|------|--------|-----------------|
| M0-T01 | DONE | gateway.py — `hmac.compare_digest()` |
| M0-T02 | DONE | gateway.py — deny-by-default when key unset |
| M0-T03 | DONE | gateway.py — auth on 3 endpoints, PythonCodeNode blocked, Pydantic model |
| M0-T04 | DONE | sap_cpi_client.py — `verify=self._verify` (True default), `SAP_CPI_CA_BUNDLE` env |
| M0-T05 | DONE | sap_cpi_client.py — ET.Element builder + regex validation |
| M0-T06 | DONE | gateway.py — CORS restricted in prod, all `str(e)` replaced |
| M0-T07 | DONE | ipas_xml_parser.py + sap_cpi_client.py — defusedxml for external input |
| M0-T08 | DONE | .gitignore + `git rm --cached sdk-users/.env.sdk-dev` |
| M0-T09 | DONE | chat.html — verified `escapeHtml()` covers all server data paths |
| M0-T10 | DONE | aravo_kyp_client.py — SSL override requires `ARAVO_SSL_OVERRIDE_ACKNOWLEDGED` |
| M0-T11 | DEFERRED | Rate limiting — requires `slowapi` dependency + middleware (Wave 2) |

## Verification

- All modified files pass `ast.parse()` syntax validation
- Security reviewer agent ran full audit (background)
- No `detail=str(e)` remaining in any error response
- No `verify=False` remaining in any HTTP call
- No f-string XML construction remaining
- `defusedxml` added to pyproject.toml dependencies
