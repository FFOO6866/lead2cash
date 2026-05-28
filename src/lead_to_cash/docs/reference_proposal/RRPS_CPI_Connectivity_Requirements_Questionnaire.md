# RRPS CPI-to-AWS Connectivity Requirements Questionnaire

## Document Control
| Item | Value |
|------|-------|
| **Document Title** | CPI-to-AWS Connectivity Requirements Questionnaire |
| **Client** | Rolls-Royce Power Systems (RRPS) |
| **Prepared By** | Integrum Pte. Ltd. |
| **Date** | December 2025 |
| **Version** | 1.0 |
| **Classification** | Confidential |

---

## Purpose
This questionnaire collects information required to establish secure connectivity between RRPS SAP CPI and Integrum's AWS-hosted Kailash Platform. All requirements are designed to ensure compliance with:
- **ISO 42001:2023** - AI Management Systems
- **ISO 27001:2022** - Information Security Management Systems

---

## Section 1: Network Connectivity Requirements

### 1.1 Network Architecture

| # | Requirement | RRPS Response | ISO Reference |
|---|------------|---------------|---------------|
| 1.1.1 | What is the source IP range/CIDR for outbound CPI connections? | | ISO 27001 A.13.1.1 |
| 1.1.2 | Is IP whitelisting required? If yes, provide Integrum's AWS IP ranges to whitelist. | | ISO 27001 A.13.1.1 |
| 1.1.3 | What is the preferred network connectivity method? (Public Internet / AWS Direct Connect / VPN Site-to-Site / AWS PrivateLink) | | ISO 27001 A.13.1.2 |
| 1.1.4 | Are there firewall rules/ACLs that need to be configured? Please specify. | | ISO 27001 A.13.1.1 |
| 1.1.5 | What ports are required for outbound CPI traffic? (Standard: 443/HTTPS) | | ISO 27001 A.13.1.1 |
| 1.1.6 | Is NAT Gateway used for outbound traffic? Provide NAT IP if applicable. | | ISO 27001 A.13.1.1 |
| 1.1.7 | What is the expected network latency tolerance? (e.g., <100ms, <500ms) | | ISO 27001 A.17.2.1 |
| 1.1.8 | What is the required network bandwidth allocation? | | ISO 27001 A.17.2.1 |

### 1.2 DNS and Endpoint Resolution

| # | Requirement | RRPS Response | ISO Reference |
|---|------------|---------------|---------------|
| 1.2.1 | Can RRPS CPI resolve external DNS? Or is internal DNS proxy required? | | ISO 27001 A.13.1.1 |
| 1.2.2 | Is custom domain/CNAME required for Integrum endpoints? | | ISO 27001 A.13.1.1 |
| 1.2.3 | Are there DNS filtering/blocking policies we need to be aware of? | | ISO 27001 A.13.1.1 |

---

## Section 2: Transport Layer Security (TLS)

### 2.1 Encryption Requirements

| # | Requirement | RRPS Response | ISO Reference |
|---|------------|---------------|---------------|
| 2.1.1 | What is the minimum TLS version required? (Integrum supports TLS 1.3) | | ISO 27001 A.10.1.1 |
| 2.1.2 | Are specific cipher suites required/blocked? | | ISO 27001 A.10.1.1 |
| 2.1.3 | Is mutual TLS (mTLS) required for CPI-to-AWS communication? | | ISO 27001 A.10.1.1 |
| 2.1.4 | What is the certificate authority (CA) policy? (Public CA / Private CA / Both) | | ISO 27001 A.10.1.2 |
| 2.1.5 | What is the certificate validity period requirement? | | ISO 27001 A.10.1.2 |
| 2.1.6 | Is certificate pinning required? | | ISO 27001 A.10.1.2 |

### 2.2 Certificate Management

| # | Requirement | RRPS Response | ISO Reference |
|---|------------|---------------|---------------|
| 2.2.1 | Who manages certificate rotation? (RRPS / Integrum / Shared) | | ISO 27001 A.10.1.2 |
| 2.2.2 | What is the certificate rotation frequency requirement? | | ISO 27001 A.10.1.2 |
| 2.2.3 | How should certificate expiry notifications be handled? | | ISO 27001 A.10.1.2 |
| 2.2.4 | Is there a certificate revocation checking requirement? (CRL / OCSP) | | ISO 27001 A.10.1.2 |

---

## Section 3: Authentication & Authorization

### 3.1 API Authentication

| # | Requirement | RRPS Response | ISO Reference |
|---|------------|---------------|---------------|
| 3.1.1 | What authentication method is preferred? (OAuth 2.0 / API Key / JWT / Client Certificates) | | ISO 27001 A.9.4.2 |
| 3.1.2 | If OAuth 2.0: What is the Authorization Server URL? | | ISO 27001 A.9.4.2 |
| 3.1.3 | If OAuth 2.0: What grant type is required? (Client Credentials / Authorization Code) | | ISO 27001 A.9.4.2 |
| 3.1.4 | If OAuth 2.0: What scopes are required for CPI integration? | | ISO 27001 A.9.4.2 |
| 3.1.5 | If API Key: What is the key rotation policy? | | ISO 27001 A.9.4.3 |
| 3.1.6 | If JWT: What signing algorithm is required? (RS256 / ES256) | | ISO 27001 A.9.4.2 |
| 3.1.7 | What is the token expiry/refresh policy? | | ISO 27001 A.9.4.2 |

### 3.2 Service Account Management

| # | Requirement | RRPS Response | ISO Reference |
|---|------------|---------------|---------------|
| 3.2.1 | Will RRPS provide a dedicated service account for integration? | | ISO 27001 A.9.2.1 |
| 3.2.2 | What is the naming convention for service accounts? | | ISO 27001 A.9.2.1 |
| 3.2.3 | What is the credential rotation policy for service accounts? | | ISO 27001 A.9.2.4 |
| 3.2.4 | How are service account credentials securely shared? | | ISO 27001 A.9.2.4 |
| 3.2.5 | Is MFA required for service account access? | | ISO 27001 A.9.4.2 |

### 3.3 Authorization & Access Control

| # | Requirement | RRPS Response | ISO Reference |
|---|------------|---------------|---------------|
| 3.3.1 | What RBAC roles need to be mapped for Integrum platform? | | ISO 27001 A.9.1.2 |
| 3.3.2 | Is attribute-based access control (ABAC) required? | | ISO 27001 A.9.1.2 |
| 3.3.3 | What is the principle of least privilege policy? | | ISO 27001 A.9.1.2 |
| 3.3.4 | Are there IP-based access restrictions for API calls? | | ISO 27001 A.9.4.1 |

---

## Section 4: Data Protection & Privacy

### 4.1 Data Classification

| # | Requirement | RRPS Response | ISO Reference |
|---|------------|---------------|---------------|
| 4.1.1 | What data classification levels are used? (e.g., Public, Internal, Confidential, Restricted) | | ISO 27001 A.8.2.1 |
| 4.1.2 | What classification applies to order/opportunity data? | | ISO 27001 A.8.2.1 |
| 4.1.3 | What classification applies to customer/partner data? | | ISO 27001 A.8.2.1 |
| 4.1.4 | What classification applies to financial/billing data? | | ISO 27001 A.8.2.1 |
| 4.1.5 | Are there specific fields requiring encryption at rest? | | ISO 27001 A.8.2.3 |

### 4.2 Data Handling Requirements

| # | Requirement | RRPS Response | ISO Reference |
|---|------------|---------------|---------------|
| 4.2.1 | What is the data retention policy for transactional data? | | ISO 27001 A.8.3.2 |
| 4.2.2 | What is the data retention policy for audit logs? | | ISO 27001 A.8.3.2 |
| 4.2.3 | Is data anonymization/pseudonymization required? For which fields? | | ISO 27001 A.8.2.3 |
| 4.2.4 | What are the data deletion requirements? (Hard delete / Soft delete / Anonymization) | | ISO 27001 A.8.3.2 |
| 4.2.5 | Is there a legal hold policy that may override retention? | | ISO 27001 A.18.1.3 |

### 4.3 Cross-Border Data Transfer

| # | Requirement | RRPS Response | ISO Reference |
|---|------------|---------------|---------------|
| 4.3.1 | What data residency requirements exist? (e.g., data must stay in APAC) | | ISO 27001 A.18.1.4 |
| 4.3.2 | Are there restrictions on data transfer to specific countries? | | ISO 27001 A.18.1.4 |
| 4.3.3 | Is Standard Contractual Clauses (SCC) required for data transfer? | | ISO 27001 A.18.1.4 |
| 4.3.4 | What AWS region should Integrum host the platform? | | ISO 27001 A.18.1.4 |

---

## Section 5: Audit Logging & Monitoring

### 5.1 Audit Requirements

| # | Requirement | RRPS Response | ISO Reference |
|---|------------|---------------|---------------|
| 5.1.1 | What audit events must be logged? (All API calls / Specific actions) | | ISO 27001 A.12.4.1 |
| 5.1.2 | What is the required audit log format? (JSON / CEF / Syslog) | | ISO 27001 A.12.4.1 |
| 5.1.3 | How long must audit logs be retained? | | ISO 27001 A.12.4.1 |
| 5.1.4 | Is real-time audit log streaming required to RRPS SIEM? | | ISO 27001 A.12.4.1 |
| 5.1.5 | What SIEM platform does RRPS use? (Splunk / Azure Sentinel / etc.) | | ISO 27001 A.12.4.1 |

### 5.2 Monitoring & Alerting

| # | Requirement | RRPS Response | ISO Reference |
|---|------------|---------------|---------------|
| 5.2.1 | What metrics must be exposed? (Latency / Error rates / Throughput) | | ISO 27001 A.12.4.3 |
| 5.2.2 | Is integration with RRPS monitoring tools required? | | ISO 27001 A.12.4.3 |
| 5.2.3 | What are the alerting thresholds for security events? | | ISO 27001 A.12.4.3 |
| 5.2.4 | Who should receive security alerts? (Email / PagerDuty / Webhook) | | ISO 27001 A.16.1.2 |

### 5.3 Traceability Requirements

| # | Requirement | RRPS Response | ISO Reference |
|---|------------|---------------|---------------|
| 5.3.1 | What correlation ID format should be used for end-to-end tracing? | | ISO 27001 A.12.4.1 |
| 5.3.2 | Should CPI Message IDs be logged in Integrum platform? | | ISO 27001 A.12.4.1 |
| 5.3.3 | Is distributed tracing required? (OpenTelemetry / Jaeger / X-Ray) | | ISO 27001 A.12.4.1 |

---

## Section 6: SAP CPI Integration Specifics

### 6.1 CPI Configuration

| # | Requirement | RRPS Response | ISO Reference |
|---|------------|---------------|---------------|
| 6.1.1 | What CPI tenant/instance will be used for integration? | | ISO 27001 A.14.1.2 |
| 6.1.2 | What CPI package/iFlow naming convention should be followed? | | ISO 27001 A.14.1.2 |
| 6.1.3 | What is the CPI change management process? | | ISO 27001 A.14.2.2 |
| 6.1.4 | Are there existing iFlows that can be reused? Please list. | | ISO 27001 A.14.2.1 |
| 6.1.5 | What is the CPI environment promotion path? (DEV → QA → PROD) | | ISO 27001 A.14.2.1 |

### 6.2 API Patterns

| # | Requirement | RRPS Response | ISO Reference |
|---|------------|---------------|---------------|
| 6.2.1 | What HTTP methods are allowed? (GET / POST / PUT / PATCH / DELETE) | | ISO 27001 A.14.1.2 |
| 6.2.2 | What is the maximum payload size allowed? | | ISO 27001 A.14.1.2 |
| 6.2.3 | What is the API rate limit from CPI? (requests/minute) | | ISO 27001 A.14.1.2 |
| 6.2.4 | Is request/response compression required? (gzip) | | ISO 27001 A.14.1.2 |
| 6.2.5 | What content types are supported? (application/json / application/xml) | | ISO 27001 A.14.1.2 |

### 6.3 Error Handling

| # | Requirement | RRPS Response | ISO Reference |
|---|------------|---------------|---------------|
| 6.3.1 | What is the retry policy for failed requests? | | ISO 27001 A.17.1.1 |
| 6.3.2 | What HTTP status codes should trigger retry? | | ISO 27001 A.17.1.1 |
| 6.3.3 | What is the dead letter queue policy for failed messages? | | ISO 27001 A.17.1.1 |
| 6.3.4 | How should idempotency be handled? (Idempotency Key header?) | | ISO 27001 A.14.1.2 |

---

## Section 7: ISO 42001 - AI Management System Requirements

### 7.1 AI Governance

| # | Requirement | RRPS Response | ISO Reference |
|---|------------|---------------|---------------|
| 7.1.1 | Is there an AI ethics policy that Integrum must comply with? | | ISO 42001 6.1.1 |
| 7.1.2 | What AI risk assessment framework is used? | | ISO 42001 6.1.2 |
| 7.1.3 | Is there an AI governance committee/board for approval? | | ISO 42001 5.1 |
| 7.1.4 | What documentation is required for AI model deployment? | | ISO 42001 7.5 |

### 7.2 AI Transparency & Explainability

| # | Requirement | RRPS Response | ISO Reference |
|---|------------|---------------|---------------|
| 7.2.1 | What level of AI decision explainability is required? | | ISO 42001 9.1.2 |
| 7.2.2 | Must AI-generated proposals include reasoning/rationale? | | ISO 42001 9.1.2 |
| 7.2.3 | Is human-in-the-loop approval required for all AI decisions? | | ISO 42001 8.4 |
| 7.2.4 | What AI model versioning and lineage tracking is required? | | ISO 42001 7.5.3 |

### 7.3 AI Data Requirements

| # | Requirement | RRPS Response | ISO Reference |
|---|------------|---------------|---------------|
| 7.3.1 | Is there a policy on LLM data retention? (No long-term retention expected) | | ISO 42001 8.2 |
| 7.3.2 | Can operational data be used for AI model training? | | ISO 42001 8.2 |
| 7.3.3 | What data quality requirements exist for AI inputs? | | ISO 42001 8.2 |
| 7.3.4 | Is synthetic data generation allowed for testing? | | ISO 42001 8.2 |

### 7.4 AI Model Management

| # | Requirement | RRPS Response | ISO Reference |
|---|------------|---------------|---------------|
| 7.4.1 | What LLM providers are approved for use? (OpenAI / Anthropic / Azure OpenAI / Mistral) | | ISO 42001 8.3 |
| 7.4.2 | Is on-premises/private LLM deployment required? | | ISO 42001 8.3 |
| 7.4.3 | What AI model performance monitoring is required? | | ISO 42001 9.1 |
| 7.4.4 | Is AI bias detection/mitigation required? | | ISO 42001 9.1.3 |

### 7.5 AI Incident Management

| # | Requirement | RRPS Response | ISO Reference |
|---|------------|---------------|---------------|
| 7.5.1 | What is the process for reporting AI-related incidents? | | ISO 42001 10.1 |
| 7.5.2 | What is the escalation path for AI decision errors? | | ISO 42001 10.1 |
| 7.5.3 | Is there an AI model rollback procedure requirement? | | ISO 42001 10.1 |

---

## Section 8: ISO 27001 - Information Security Controls

### 8.1 Access Control (A.9)

| # | Requirement | RRPS Response | ISO Reference |
|---|------------|---------------|---------------|
| 8.1.1 | What is the access request/approval process for Integrum team? | | ISO 27001 A.9.2.1 |
| 8.1.2 | What is the access review frequency? (Quarterly / Annual) | | ISO 27001 A.9.2.5 |
| 8.1.3 | What is the access revocation process upon project completion? | | ISO 27001 A.9.2.6 |
| 8.1.4 | Is privileged access management (PAM) required? | | ISO 27001 A.9.2.3 |

### 8.2 Cryptography (A.10)

| # | Requirement | RRPS Response | ISO Reference |
|---|------------|---------------|---------------|
| 8.2.1 | What encryption algorithm is required for data at rest? (Integrum uses AES-256-GCM) | | ISO 27001 A.10.1.1 |
| 8.2.2 | What key management solution should be used? (AWS KMS / HashiCorp Vault) | | ISO 27001 A.10.1.2 |
| 8.2.3 | What is the encryption key rotation frequency? | | ISO 27001 A.10.1.2 |
| 8.2.4 | Who owns/controls encryption keys? (RRPS / Integrum / Shared) | | ISO 27001 A.10.1.2 |

### 8.3 Operations Security (A.12)

| # | Requirement | RRPS Response | ISO Reference |
|---|------------|---------------|---------------|
| 8.3.1 | What change management process must Integrum follow? | | ISO 27001 A.12.1.2 |
| 8.3.2 | Is separation of development/test/production environments required? | | ISO 27001 A.12.1.4 |
| 8.3.3 | What malware protection requirements exist? | | ISO 27001 A.12.2.1 |
| 8.3.4 | What backup and recovery requirements apply? | | ISO 27001 A.12.3.1 |

### 8.4 Communications Security (A.13)

| # | Requirement | RRPS Response | ISO Reference |
|---|------------|---------------|---------------|
| 8.4.1 | Is network segmentation required for the integration? | | ISO 27001 A.13.1.3 |
| 8.4.2 | Are there DDoS protection requirements? | | ISO 27001 A.13.1.1 |
| 8.4.3 | Is Web Application Firewall (WAF) required? | | ISO 27001 A.13.1.1 |
| 8.4.4 | What intrusion detection/prevention requirements exist? | | ISO 27001 A.13.1.1 |

### 8.5 Supplier Relationships (A.15)

| # | Requirement | RRPS Response | ISO Reference |
|---|------------|---------------|---------------|
| 8.5.1 | What security requirements apply to Integrum as a supplier? | | ISO 27001 A.15.1.1 |
| 8.5.2 | Is a security assessment/audit of Integrum required? | | ISO 27001 A.15.1.1 |
| 8.5.3 | What SLA requirements apply to security incident response? | | ISO 27001 A.15.1.2 |
| 8.5.4 | Is SOC 2 Type II certification required from Integrum? | | ISO 27001 A.15.1.1 |

### 8.6 Incident Management (A.16)

| # | Requirement | RRPS Response | ISO Reference |
|---|------------|---------------|---------------|
| 8.6.1 | What is the security incident notification timeline? | | ISO 27001 A.16.1.2 |
| 8.6.2 | Who are the security incident contacts at RRPS? | | ISO 27001 A.16.1.1 |
| 8.6.3 | What incident severity classification is used? | | ISO 27001 A.16.1.4 |
| 8.6.4 | Is there a joint incident response procedure required? | | ISO 27001 A.16.1.5 |

### 8.7 Business Continuity (A.17)

| # | Requirement | RRPS Response | ISO Reference |
|---|------------|---------------|---------------|
| 8.7.1 | What is the required RTO (Recovery Time Objective)? | | ISO 27001 A.17.1.1 |
| 8.7.2 | What is the required RPO (Recovery Point Objective)? | | ISO 27001 A.17.1.1 |
| 8.7.3 | Is multi-region deployment required for high availability? | | ISO 27001 A.17.2.1 |
| 8.7.4 | What disaster recovery testing frequency is required? | | ISO 27001 A.17.1.3 |

### 8.8 Compliance (A.18)

| # | Requirement | RRPS Response | ISO Reference |
|---|------------|---------------|---------------|
| 8.8.1 | What regulatory frameworks must be complied with? (GDPR / SOX / etc.) | | ISO 27001 A.18.1.1 |
| 8.8.2 | Is there a right to audit clause required in the contract? | | ISO 27001 A.18.2.1 |
| 8.8.3 | What penetration testing requirements exist? (Frequency / Scope) | | ISO 27001 A.18.2.3 |
| 8.8.4 | Is vulnerability scanning required? What frequency? | | ISO 27001 A.18.2.3 |

---

## Section 9: Operational Requirements

### 9.1 Service Level Agreements

| # | Requirement | RRPS Response | ISO Reference |
|---|------------|---------------|---------------|
| 9.1.1 | What is the required service availability? (e.g., 99.9%) | | ISO 27001 A.17.2.1 |
| 9.1.2 | What are the scheduled maintenance windows? | | ISO 27001 A.17.2.1 |
| 9.1.3 | What is the maximum allowed response time for API calls? | | ISO 27001 A.17.2.1 |
| 9.1.4 | What is the incident resolution SLA by severity? | | ISO 27001 A.16.1.5 |

### 9.2 Support & Escalation

| # | Requirement | RRPS Response | ISO Reference |
|---|------------|---------------|---------------|
| 9.2.1 | What support hours are required? (Business hours / 24x7) | | ISO 27001 A.16.1.1 |
| 9.2.2 | What is the escalation matrix for critical issues? | | ISO 27001 A.16.1.1 |
| 9.2.3 | What communication channels are preferred? (Email / Phone / Teams) | | ISO 27001 A.16.1.1 |

### 9.3 Testing & Validation

| # | Requirement | RRPS Response | ISO Reference |
|---|------------|---------------|---------------|
| 9.3.1 | Is end-to-end testing in a non-production environment required before go-live? | | ISO 27001 A.14.2.8 |
| 9.3.2 | What test data requirements exist? (Masked / Synthetic / Production copy) | | ISO 27001 A.14.3.1 |
| 9.3.3 | Is User Acceptance Testing (UAT) sign-off required? | | ISO 27001 A.14.2.9 |

---

## Section 10: Integrum AWS Configuration (For RRPS Review)

The following configurations will be implemented on Integrum's AWS infrastructure. Please review and confirm compliance with RRPS security standards.

### 10.1 Network Security

| Configuration | Integrum Implementation | RRPS Approval |
|--------------|------------------------|---------------|
| VPC with private subnets | Yes - isolated VPC with no public subnets for backend | |
| Network ACLs | Restrictive ACLs - only allow CPI IP ranges | |
| Security Groups | Least privilege - only port 443 inbound from CPI | |
| AWS WAF | Enabled with OWASP Top 10 rule set | |
| AWS Shield | Standard DDoS protection enabled | |
| VPC Flow Logs | Enabled - logs retained for 90 days | |

### 10.2 Data Security

| Configuration | Integrum Implementation | RRPS Approval |
|--------------|------------------------|---------------|
| Encryption at Rest | AES-256-GCM via AWS KMS | |
| Encryption in Transit | TLS 1.3 with strong cipher suites | |
| Key Management | AWS KMS with automatic rotation (90 days) | |
| Database Encryption | RDS encryption enabled | |
| S3 Bucket Encryption | SSE-KMS with bucket policies | |
| Secrets Management | AWS Secrets Manager with rotation | |

### 10.3 Access Control

| Configuration | Integrum Implementation | RRPS Approval |
|--------------|------------------------|---------------|
| IAM Policies | Least privilege, role-based | |
| MFA Enforcement | Required for all console access | |
| Service Accounts | Dedicated IAM roles for CPI integration | |
| Cross-Account Access | Not enabled unless explicitly required | |
| Session Duration | Maximum 8 hours | |

### 10.4 Logging & Monitoring

| Configuration | Integrum Implementation | RRPS Approval |
|--------------|------------------------|---------------|
| CloudTrail | Enabled for all API calls | |
| CloudWatch Logs | Application and access logs | |
| Log Retention | 2555 days (7 years) for audit logs | |
| GuardDuty | Enabled for threat detection | |
| Security Hub | Enabled with CIS benchmarks | |
| SIEM Integration | Available via S3/CloudWatch Logs export | |

### 10.5 Compliance

| Configuration | Integrum Implementation | RRPS Approval |
|--------------|------------------------|---------------|
| AWS Region | ap-southeast-1 (Singapore) - confirm requirement | |
| Compliance Programs | SOC 2 Type II in progress | |
| Penetration Testing | Annual third-party assessment | |
| Vulnerability Scanning | Weekly automated scans | |
| Patch Management | Critical: 24hrs, High: 7 days, Medium: 30 days | |

---

## Section 11: Action Items & Sign-Off

### 11.1 RRPS Action Items

| # | Action Item | Owner | Due Date | Status |
|---|-------------|-------|----------|--------|
| 1 | Complete all sections of this questionnaire | | | |
| 2 | Provide CPI tenant details and credentials | | | |
| 3 | Confirm AWS region for data residency | | | |
| 4 | Provide IP ranges for whitelisting | | | |
| 5 | Confirm authentication method (OAuth/API Key/mTLS) | | | |
| 6 | Provide security incident contact details | | | |
| 7 | Review and approve Integrum AWS configuration | | | |

### 11.2 Integrum Action Items

| # | Action Item | Owner | Due Date | Status |
|---|-------------|-------|----------|--------|
| 1 | Configure AWS VPC and security groups | | | |
| 2 | Set up TLS certificates | | | |
| 3 | Configure authentication endpoint | | | |
| 4 | Enable audit logging | | | |
| 5 | Configure SIEM integration (if required) | | | |
| 6 | Prepare security documentation | | | |
| 7 | Schedule penetration test | | | |

---

## Approval

| Role | Name | Signature | Date |
|------|------|-----------|------|
| RRPS IT Security | | | |
| RRPS CPI Owner | | | |
| RRPS Project Sponsor | | | |
| Integrum Solution Architect | | | |
| Integrum Security Officer | | | |

---

## Document History

| Version | Date | Author | Changes |
|---------|------|--------|---------|
| 1.0 | Dec 2025 | Integrum | Initial version |

