"""
RRPS Lead-to-Cash Configuration

Centralized configuration management for the RRPS Lead-to-Cash POV.
Manages SAP CPI, MS5, CEC, IPAS integration settings.
"""

import os
from dataclasses import dataclass, field
from enum import Enum
from typing import Optional


class Environment(Enum):
    """Deployment environment."""

    DEVELOPMENT = "development"
    QA = "qa"
    PRODUCTION = "production"


@dataclass
class SAPCPIConfig:
    """SAP CPI Integration Configuration."""

    # CPI Endpoints by environment - MUST be configured via environment variables
    # No hardcoded defaults to prevent connecting to wrong tenant
    dev_url: Optional[str] = os.getenv("SAP_CPI_DEV_URL")
    qa_url: Optional[str] = os.getenv("SAP_CPI_QA_URL")
    prod_url: Optional[str] = os.getenv("SAP_CPI_PROD_URL")

    # OAuth 2.0 Authentication
    client_id: Optional[str] = os.getenv("SAP_CPI_CLIENT_ID")
    client_secret: Optional[str] = os.getenv("SAP_CPI_CLIENT_SECRET")
    token_url: Optional[str] = os.getenv("SAP_CPI_TOKEN_URL")

    # API Settings
    max_payload_mb: int = int(os.getenv("SAP_CPI_MAX_PAYLOAD_MB", "50"))
    timeout_seconds: int = int(os.getenv("SAP_CPI_TIMEOUT", "30"))
    retry_attempts: int = int(os.getenv("SAP_CPI_RETRY_ATTEMPTS", "3"))

    # Naming Convention
    package_prefix: str = "RRPS - Integrum"

    def get_url(self, environment: str) -> str:
        """Get CPI URL for environment.

        Returns:
            CPI URL for the specified environment, or empty string if not configured.
        """
        urls = {
            "development": self.dev_url,
            "qa": self.qa_url,
            "production": self.prod_url,
        }
        return urls.get(environment) or ""


@dataclass
class SAPMS5Config:
    """SAP MS5 (S/4HANA) Configuration."""

    host: Optional[str] = os.getenv("SAP_MS5_HOST")
    client: str = os.getenv("SAP_MS5_CLIENT", "100")
    sysnr: str = os.getenv("SAP_MS5_SYSNR", "00")
    user: Optional[str] = os.getenv("SAP_MS5_USER")
    password: Optional[str] = os.getenv("SAP_MS5_PASSWORD")

    # RFC Connection Pool
    pool_size: int = int(os.getenv("SAP_MS5_POOL_SIZE", "5"))

    # SAP Organizational Values - MUST be configured per customer
    default_sales_org: Optional[str] = os.getenv("SAP_MS5_SALES_ORG")
    default_credit_control_area: Optional[str] = os.getenv(
        "SAP_MS5_CREDIT_CONTROL_AREA"
    )

    # Key BAPIs (validated against SAP documentation)
    bapis: dict = field(
        default_factory=lambda: {
            "customer_detail": "BAPI_CUSTOMER_GETDETAIL2",
            "credit_check": "BAPI_CR_ACC_GETDETAIL",  # CORRECTED: was BAPI_CREDITMANAGEMENT_GETLIST
            "order_simulate": "BAPI_SALESORDER_SIMULATE",
            "order_create": "BAPI_SALESORDER_CREATEFROMDAT2",
            "transaction_commit": "BAPI_TRANSACTION_COMMIT",  # Required after order create
        }
    )


@dataclass
class SAPCECConfig:
    """SAP CEC (Customer Engagement Center) Configuration."""

    base_url: Optional[str] = os.getenv("SAP_CEC_URL")
    client_id: Optional[str] = os.getenv("SAP_CEC_CLIENT_ID")
    client_secret: Optional[str] = os.getenv("SAP_CEC_CLIENT_SECRET")

    # API Settings
    api_version: str = "v1"
    timeout_seconds: int = int(os.getenv("SAP_CEC_TIMEOUT", "30"))


@dataclass
class SAPIPASConfig:
    """SAP IPAS (Intelligent Product Advisor System) Configuration."""

    base_url: Optional[str] = os.getenv("SAP_IPAS_URL")
    api_key: Optional[str] = os.getenv("SAP_IPAS_API_KEY")

    # API Settings
    timeout_seconds: int = int(os.getenv("SAP_IPAS_TIMEOUT", "30"))


@dataclass
class AravoConfig:
    """Aravo Third-Party Risk Management (TPRM) Configuration.

    Aravo provides supplier due diligence, compliance, and governance capabilities.
    API: SOAP/XML based with REST endpoints for specific services.
    """

    # Base URL (e.g., https://yourcompany.aravo.com)
    base_url: Optional[str] = os.getenv("ARAVO_URL")

    # OAuth 2.0 Authentication (or Basic Auth)
    client_id: Optional[str] = os.getenv("ARAVO_CLIENT_ID")
    client_secret: Optional[str] = os.getenv("ARAVO_CLIENT_SECRET")
    token_url: Optional[str] = os.getenv("ARAVO_TOKEN_URL")

    # Basic Auth (alternative to OAuth)
    username: Optional[str] = os.getenv("ARAVO_USERNAME")
    password: Optional[str] = os.getenv("ARAVO_PASSWORD")

    # API Settings
    timeout_seconds: int = int(os.getenv("ARAVO_TIMEOUT", "30"))
    retry_attempts: int = int(os.getenv("ARAVO_RETRY_ATTEMPTS", "3"))

    # SOAP Service Endpoints (relative to base_url)
    supplier_service_path: str = "/aems/services/SupplierService4_2"
    contact_service_path: str = "/aems/services/SupplierContactService4_2"
    business_relationship_service_path: str = (
        "/aems/services/BusinessRelationshipService4_2"
    )
    business_process_service_path: str = "/aems/services/BusinessProcessService4_4"
    association_service_path: str = "/aems/services/AssociationService4_2"
    user_service_path: str = "/aems/services/UserService4_2"

    # REST Service Endpoints
    file_attributes_path: str = "/aems/rest/fileattributes/v1_0"
    business_process_rest_path: str = "/aems/rest/businessprocess/v1_0"
    reports_rest_path: str = "/aems/rest/reports/v1_0"
    reports_v5_path: str = "/aems/restservices/v5.0/reports"
    tprm_report_id: str = os.getenv("ARAVO_REPORT_ID", "25942819")

    # Default entity keys (customer-specific, from Aravo Data Dictionary)
    default_engagement_type: str = os.getenv("ARAVO_ENGAGEMENT_TYPE", "TPMEngagement")
    default_supplier_type: str = os.getenv("ARAVO_SUPPLIER_TYPE", "Supplier")

    def get_service_url(self, service: str) -> str:
        """Get full URL for a service endpoint."""
        if not self.base_url:
            return ""
        paths = {
            "supplier": self.supplier_service_path,
            "contact": self.contact_service_path,
            "business_relationship": self.business_relationship_service_path,
            "business_process": self.business_process_service_path,
            "association": self.association_service_path,
            "user": self.user_service_path,
            "file_attributes": self.file_attributes_path,
            "business_process_rest": self.business_process_rest_path,
            "reports": self.reports_rest_path,
        }
        path = paths.get(service, "")
        return f"{self.base_url.rstrip('/')}{path}" if path else ""

    def is_configured(self) -> bool:
        """Check if Aravo is minimally configured."""
        has_oauth = bool(self.client_id and self.client_secret)
        has_basic = bool(self.username and self.password)
        return bool(self.base_url) and (has_oauth or has_basic)


@dataclass
class KnowledgeBaseConfig:
    """Knowledge Base Service Configuration."""

    # Database
    database_url: Optional[str] = os.getenv("KB_DATABASE_URL") or os.getenv(
        "DATABASE_URL"
    )
    read_replica_url: Optional[str] = os.getenv("KB_READ_REPLICA_URL")
    pool_size: int = int(os.getenv("KB_POOL_SIZE", "10"))
    pool_max_overflow: int = int(os.getenv("KB_POOL_MAX_OVERFLOW", "20"))

    # OpenAI API
    openai_api_key: Optional[str] = os.getenv("OPENAI_API_KEY")
    openai_model: str = os.getenv("KB_OPENAI_MODEL", "gpt-4o")
    embedding_model: str = os.getenv("KB_EMBEDDING_MODEL", "text-embedding-3-small")
    embedding_dimensions: int = int(os.getenv("KB_EMBEDDING_DIMENSIONS", "1536"))

    # LLM Settings
    extraction_temperature: float = float(os.getenv("KB_EXTRACTION_TEMPERATURE", "0.1"))
    extraction_max_tokens: int = int(os.getenv("KB_EXTRACTION_MAX_TOKENS", "2000"))
    max_content_chars: int = int(os.getenv("KB_MAX_CONTENT_CHARS", "12000"))

    # Entity Resolution
    min_confidence_threshold: float = float(os.getenv("KB_MIN_CONFIDENCE", "0.5"))
    fuzzy_match_threshold: int = int(os.getenv("KB_FUZZY_THRESHOLD", "85"))
    semantic_similarity_threshold: float = float(
        os.getenv("KB_SEMANTIC_THRESHOLD", "0.7")
    )

    # Scoring Thresholds
    high_priority_threshold: int = int(os.getenv("KB_HIGH_PRIORITY_THRESHOLD", "70"))
    monitor_threshold: int = int(os.getenv("KB_MONITOR_THRESHOLD", "40"))

    # Circuit Breaker
    circuit_failure_threshold: int = int(os.getenv("KB_CIRCUIT_FAILURE_THRESHOLD", "5"))
    circuit_recovery_timeout: int = int(os.getenv("KB_CIRCUIT_RECOVERY_TIMEOUT", "60"))
    circuit_half_open_calls: int = int(os.getenv("KB_CIRCUIT_HALF_OPEN_CALLS", "3"))

    # Rate Limiting
    rate_limit_requests: int = int(os.getenv("KB_RATE_LIMIT_REQUESTS", "100"))
    rate_limit_window_seconds: int = int(os.getenv("KB_RATE_LIMIT_WINDOW", "60"))
    batch_delay_seconds: float = float(os.getenv("KB_BATCH_DELAY", "0.5"))
    batch_size: int = int(os.getenv("KB_BATCH_SIZE", "100"))

    # Redis (for distributed circuit breaker and rate limiting)
    redis_url: Optional[str] = os.getenv("REDIS_URL")

    # Timeouts (seconds)
    api_timeout: float = float(os.getenv("KB_API_TIMEOUT", "30.0"))
    enrichment_timeout: float = float(os.getenv("KB_ENRICHMENT_TIMEOUT", "10.0"))

    # Feature Flags
    enable_semantic_search: bool = (
        os.getenv("KB_ENABLE_SEMANTIC_SEARCH", "True").lower() == "true"
    )
    enable_fuzzy_matching: bool = (
        os.getenv("KB_ENABLE_FUZZY_MATCHING", "True").lower() == "true"
    )

    def is_configured(self) -> bool:
        """Check if KB is minimally configured."""
        return bool(self.database_url and self.openai_api_key)


@dataclass
class AppConfig:
    """Configuration settings for RRPS Lead-to-Cash."""

    # App Information
    app_name: str = "lead_to_cash"
    app_version: str = "1.0.0"
    app_description: str = (
        "RRPS Lead-to-Cash POV - Multi-Agent SAP Integration Platform"
    )

    # Environment
    environment: str = os.getenv("ENVIRONMENT", "development")
    debug: bool = os.getenv("DEBUG", "False").lower() == "true"

    # Database Configuration
    database_url: Optional[str] = os.getenv("DATABASE_URL")
    database_echo: bool = os.getenv("DATABASE_ECHO", "False").lower() == "true"

    # API Configuration
    api_host: str = os.getenv("API_HOST", "0.0.0.0")
    api_port: int = int(os.getenv("API_PORT", "8000"))
    api_prefix: str = "/api/v1"
    api_base_url: str = os.getenv("API_BASE_URL", "https://rr.kailash.ai")

    # Security
    secret_key: Optional[str] = os.getenv("SECRET_KEY")
    allowed_origins: list = field(
        default_factory=lambda: os.getenv(
            "ALLOWED_ORIGINS", "http://localhost:3000,https://rr.kailash.ai"
        ).split(",")
    )

    # Kailash SDK Configuration
    sdk_log_level: str = os.getenv("SDK_LOG_LEVEL", "INFO")
    sdk_enable_monitoring: bool = (
        os.getenv("SDK_ENABLE_MONITORING", "True").lower() == "true"
    )
    sdk_max_concurrency: int = int(os.getenv("SDK_MAX_CONCURRENCY", "10"))

    # SAP Integration Configurations
    sap_cpi: SAPCPIConfig = field(default_factory=SAPCPIConfig)
    sap_ms5: SAPMS5Config = field(default_factory=SAPMS5Config)
    sap_cec: SAPCECConfig = field(default_factory=SAPCECConfig)
    sap_ipas: SAPIPASConfig = field(default_factory=SAPIPASConfig)

    # Third-Party Risk Management (TPRM)
    aravo: AravoConfig = field(default_factory=AravoConfig)

    # Knowledge Base Configuration
    knowledge_base: KnowledgeBaseConfig = field(default_factory=KnowledgeBaseConfig)

    # MCP Configuration
    mcp_enabled: bool = os.getenv("MCP_ENABLED", "True").lower() == "true"
    mcp_server_name: str = os.getenv("MCP_SERVER_NAME", "rrps-lead-to-cash-mcp")

    # Authentication
    auth_strategy: str = os.getenv("AUTH_STRATEGY", "rbac")
    session_timeout: int = int(os.getenv("SESSION_TIMEOUT", "3600"))

    # KPI Targets (from POV Requirements)
    kpi_field_autofill_target: float = 0.80  # 80% acceptance rate
    kpi_first_time_right_target: float = 0.85  # 85% FTR rate
    kpi_cycle_time_reduction: float = 0.40  # 40% reduction
    kpi_billing_ready_target: float = 0.90  # 90% billing ready
    kpi_traceability_target: float = 1.00  # 100% traceability

    # API Key for authentication (required in production)
    api_key: Optional[str] = os.getenv("API_KEY")

    # Trusted proxies for rate limiting (comma-separated IPs)
    trusted_proxies: list = field(
        default_factory=lambda: [
            ip.strip()
            for ip in os.getenv("TRUSTED_PROXIES", "127.0.0.1,172.30.0.1").split(",")
            if ip.strip()
        ]
    )

    # Session store requirement (required in production by default)
    require_session_store: bool = (
        os.getenv("REQUIRE_SESSION_STORE", "True").lower() == "true"
    )

    def __post_init__(self):
        """Validate configuration after initialization."""
        if self.environment == "production":
            if not self.secret_key:
                raise ValueError("SECRET_KEY is required in production")
            if not self.database_url:
                raise ValueError("DATABASE_URL is required in production")
            if not self.api_key:
                raise ValueError(
                    "API_KEY is required in production. "
                    "Set the API_KEY environment variable to enable authentication."
                )

    @classmethod
    def load(cls) -> "AppConfig":
        """Load configuration from environment variables."""
        return cls()

    def get_database_url(self) -> str:
        """Get database URL with fallback for development."""
        if self.database_url:
            return self.database_url

        # Development fallback
        app_name_safe = self.app_name.replace("-", "_").replace(" ", "_")
        return f"sqlite:///data/outputs/{app_name_safe}.db"

    def get_api_url(self) -> str:
        """Get full API URL."""
        if self.environment == "production":
            return f"{self.api_base_url}{self.api_prefix}"
        return f"http://{self.api_host}:{self.api_port}{self.api_prefix}"

    def get_cpi_url(self) -> str:
        """Get SAP CPI URL for current environment."""
        return self.sap_cpi.get_url(self.environment)

    def is_sap_configured(self) -> dict:
        """Check which SAP systems are configured."""
        return {
            "cpi": bool(self.sap_cpi.client_id and self.sap_cpi.client_secret),
            "ms5": bool(self.sap_ms5.host and self.sap_ms5.user),
            "cec": bool(self.sap_cec.base_url and self.sap_cec.client_id),
            "ipas": bool(self.sap_ipas.base_url),
            "aravo": self.aravo.is_configured(),
        }


# Global configuration instance
config = AppConfig.load()


# Configuration validation
def validate_config() -> bool:
    """Validate current configuration."""
    try:
        config.__post_init__()
        return True
    except ValueError as e:
        print(f"Configuration error: {e}")
        return False


if __name__ == "__main__":
    # Test configuration loading
    print("=" * 60)
    print("RRPS Lead-to-Cash Configuration")
    print("=" * 60)
    print(f"\nApp: {config.app_name} v{config.app_version}")
    print(f"Description: {config.app_description}")
    print(f"\nEnvironment: {config.environment}")
    print(f"Debug: {config.debug}")
    print(f"\nAPI URL: {config.get_api_url()}")
    print(f"Database URL: {config.get_database_url()}")
    print(f"\nSAP CPI URL: {config.get_cpi_url()}")

    print("\nSAP Integration Status:")
    sap_status = config.is_sap_configured()
    for system, configured in sap_status.items():
        status = "Configured" if configured else "Not Configured"
        print(f"  {system.upper()}: {status}")

    print("\nKPI Targets:")
    print(f"  Field Auto-Fill: {config.kpi_field_autofill_target:.0%}")
    print(f"  First-Time-Right: {config.kpi_first_time_right_target:.0%}")
    print(f"  Cycle Time Reduction: {config.kpi_cycle_time_reduction:.0%}")
    print(f"  Billing Ready: {config.kpi_billing_ready_target:.0%}")
    print(f"  Traceability: {config.kpi_traceability_target:.0%}")

    print("\n" + "=" * 60)
    if validate_config():
        print("Configuration Status: VALID")
    else:
        print("Configuration Status: ERRORS FOUND")
    print("=" * 60)
