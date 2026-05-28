# AWS Setup Requirements for RRPS Integration

## Overview
This document captures our internal AWS setup requirements based on client responses. Update this as we receive answers from RRPS.

---

## 1. Network Configuration

| Requirement | Client Input | Our Setup |
|-------------|--------------|-----------|
| Whitelist CPI IPs | _Pending from RRPS_ | Security Group inbound rules |
| Connectivity | _Pending_ | Public Internet (default) / VPN / PrivateLink |
| Port | 443 | ALB listener on 443 |

**To Configure:**
- [ ] AWS Security Group: Allow inbound 443 from CPI IP range
- [ ] VPC: Private subnets for backend services
- [ ] ALB: HTTPS listener with TLS 1.3

---

## 2. Authentication

| Requirement | Client Input | Our Setup |
|-------------|--------------|-----------|
| Auth Method | _Pending_ | OAuth 2.0 / API Key / mTLS |
| Token Rotation | _Pending_ | AWS Secrets Manager rotation |

**To Configure:**
- [ ] API Gateway or ALB authentication
- [ ] Secrets Manager for credential storage
- [ ] Rotation lambda (if API Key)

---

## 3. TLS & Certificates

| Requirement | Client Input | Our Setup |
|-------------|--------------|-----------|
| TLS Version | TLS 1.3 (default) | ALB security policy |
| mTLS Required | _Pending_ | If yes: ACM Private CA |
| CA | _Pending_ | ACM (public) or Private CA |

**To Configure:**
- [ ] ACM certificate for our domain
- [ ] ALB TLS policy: ELBSecurityPolicy-TLS13-1-2-2021-06
- [ ] If mTLS: Configure client certificate validation

---

## 4. Data & Region

| Requirement | Client Input | Our Setup |
|-------------|--------------|-----------|
| AWS Region | _Pending (likely ap-southeast-1)_ | All resources in this region |
| LLM Provider | _Pending_ | Configure Kaizen accordingly |
| Log Retention | _Pending_ | CloudWatch log retention |

**To Configure:**
- [ ] Deploy all infra in specified region
- [ ] Configure LLM provider in Kaizen settings
- [ ] Set CloudWatch log retention period

---

## 5. Development Checklist

Once we have client responses, implement:

```python
# Example: Security configuration for Nexus API
# src/lead_to_cash/config.py

AWS_CONFIG = {
    "region": "ap-southeast-1",  # Update per client response
    "allowed_ips": [],  # Add CPI IP ranges
    "tls_version": "TLS1.3",
    "auth_method": "oauth2",  # or "api_key", "mtls"
}
```

---

## 6. Quick Reference - Kailash Security Patterns

Based on SDK capabilities, we'll use:

- **Authentication**: Nexus built-in OAuth2/JWT support
- **Encryption**: TLS 1.3 via AWS ALB
- **Audit Logging**: Kailash workflow execution logs + CloudWatch
- **Secrets**: AWS Secrets Manager integration

No custom security code needed - leverage Nexus framework defaults.
