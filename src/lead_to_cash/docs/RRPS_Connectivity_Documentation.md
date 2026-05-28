# Integrum API Connectivity Documentation

**Version:** 1.0 | **Date:** December 2025 | **Classification:** Confidential

---

## 1. Endpoint Details

| Parameter | Value |
|-----------|-------|
| **Base URL** | `https://rr.kailash.ai` |
| **Protocol** | HTTPS |
| **TLS Version** | 1.3 |
| **Port** | 443 |
| **Certificate** | Let's Encrypt (auto-renewal enabled) |

---

## 2. Authentication

### Testing (Current)

| Field | Value |
|-------|-------|
| Type | API Key Authentication |
| Header | `X-API-Key` |
| Key | *Contact administrator for test credentials* |

> **Note:** Credentials should be stored in environment variables, never in documentation.

### Production (Planned)

OAuth 2.0 Client Credentials flow will be provisioned for production use.

---

## 3. Available Endpoints

| Endpoint | Method | Auth | Description |
|----------|--------|------|-------------|
| `/health` | GET | No | Service health check |
| `/api/v1/test` | GET | Yes | Validate authentication |
| `/api/v1/echo` | POST | Yes | Test bidirectional communication |

---

## 4. Request & Response Examples

### 4.1 Health Check (No Auth)

**Request:**
```http
GET https://rr.kailash.ai/health
```

**Response (200 OK):**
```json
{
  "status": "ok",
  "timestamp": "2025-12-04T07:44:49Z",
  "message": "Service healthy"
}
```

### 4.2 Authentication Test

**Request:**
```http
GET https://rr.kailash.ai/api/v1/test
Authorization: Basic cnJwc19jcGlfdGVzdDpLYWlsYXNoMjAyNENQSQ==
```

**Response (200 OK):**
```json
{
  "status": "ok",
  "timestamp": "2025-12-04T07:44:50Z",
  "message": "Authentication successful for user: rrps_cpi_test"
}
```

### 4.3 Echo Test (POST with Payload)

**Request:**
```http
POST https://rr.kailash.ai/api/v1/echo
Authorization: Basic cnJwc19jcGlfdGVzdDpLYWlsYXNoMjAyNENQSQ==
Content-Type: application/json

{
  "message": "Hello from Kailash",
  "test_id": "RRPS-001"
}
```

**Response (200 OK):**
```json
{
  "status": "ok",
  "timestamp": "2025-12-04T07:44:50Z",
  "received_message": "Hello from Kailash",
  "test_id": "RRPS-001",
  "echo_hash": "127e1d79f8015388"
}
```

---

## 5. Error Handling

| HTTP Code | Meaning | Recommended Action |
|-----------|---------|-------------------|
| 200 | Success | Process response |
| 401 | Unauthorized | Verify credentials |
| 400 | Bad Request | Check payload format |
| 500 | Server Error | Retry with backoff |
| 503 | Service Unavailable | Retry after 30s |

**Suggested Retry Policy:** 3 attempts with exponential backoff (1s, 2s, 4s)

---

## 6. Security Summary

| Control | Implementation |
|---------|----------------|
| Encryption | TLS 1.3 (CHACHA20-POLY1305, AES-256-GCM) |
| Authentication | Basic Auth (test) / OAuth 2.0 (production) |
| Audit Logging | All requests logged with timestamp and correlation ID |
| Availability | Auto-restart on failure, health monitoring enabled |

---

## 7. Testing Checklist

| # | Test | Expected Result |
|---|------|-----------------|
| 1 | GET `/health` | 200 OK, status: "ok" |
| 2 | GET `/api/v1/test` with valid credentials | 200 OK, authentication successful |
| 3 | GET `/api/v1/test` with invalid credentials | 401 Unauthorized |
| 4 | POST `/api/v1/echo` with JSON payload | 200 OK, message echoed back |

---

## 8. Next Steps

| Party | Action |
|-------|--------|
| **RRPS** | Provide OAuth credentials for Integrum to connect to CPI |
| **Integrum** | Configure CPI connection once credentials received |
| **Integrum** | Provision OAuth 2.0 endpoint for production |

---

## 9. Contact

For connectivity issues or questions, please contact the Integrum project team.
