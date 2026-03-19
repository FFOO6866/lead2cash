"""
App Configuration

Centralized configuration management for the app.
Update these settings for your specific app.
"""

import os
from typing import Optional
from dataclasses import dataclass, field


@dataclass
class AppConfig:
    """Configuration settings for the app."""
    
    # App Information
    app_name: str = "rrps_lead2cash"
    app_version: str = "0.1.0"
    app_description: str = "Agentic AI Lead-to-Cash Management for Rolls-Royce Power Systems POV"
    
    # Environment
    environment: str = os.getenv("ENVIRONMENT", "development")
    debug: bool = os.getenv("DEBUG", "True").lower() == "true"
    
    # Database Configuration
    database_url: Optional[str] = os.getenv("DATABASE_URL")
    database_echo: bool = os.getenv("DATABASE_ECHO", "False").lower() == "true"
    
    # API Configuration
    api_host: str = os.getenv("API_HOST", "0.0.0.0")
    api_port: int = int(os.getenv("API_PORT", "8000"))
    api_prefix: str = "/api/v1"
    
    # Security
    secret_key: Optional[str] = os.getenv("SECRET_KEY")
    allowed_origins: list = field(default_factory=lambda: os.getenv("ALLOWED_ORIGINS", "http://localhost:3000").split(","))
    
    # Kailash SDK Configuration
    sdk_log_level: str = os.getenv("SDK_LOG_LEVEL", "INFO")
    sdk_enable_monitoring: bool = os.getenv("SDK_ENABLE_MONITORING", "True").lower() == "true"
    sdk_max_concurrency: int = int(os.getenv("SDK_MAX_CONCURRENCY", "10"))
    
    # Service Configuration
    rag_enabled: bool = os.getenv("RAG_ENABLED", "True").lower() == "true"
    rag_embedding_model: str = os.getenv("RAG_EMBEDDING_MODEL", "ollama")
    rag_vector_db: str = os.getenv("RAG_VECTOR_DB", "chroma")
    
    sharepoint_enabled: bool = os.getenv("SHAREPOINT_ENABLED", "False").lower() == "true"
    sharepoint_site_url: Optional[str] = os.getenv("SHAREPOINT_SITE_URL")
    sharepoint_client_id: Optional[str] = os.getenv("SHAREPOINT_CLIENT_ID")
    sharepoint_client_secret: Optional[str] = os.getenv("SHAREPOINT_CLIENT_SECRET")
    
    mcp_enabled: bool = os.getenv("MCP_ENABLED", "True").lower() == "true"
    mcp_server_name: str = os.getenv("MCP_SERVER_NAME", "project-mcp-server")
    
    # Authentication
    auth_strategy: str = os.getenv("AUTH_STRATEGY", "rbac")  # rbac, abac, or hybrid
    session_timeout: int = int(os.getenv("SESSION_TIMEOUT", "3600"))  # seconds
    
    # RRPS-Specific Settings
    # SAP CPI Integration
    sap_cpi_base_url: str = os.getenv("SAP_CPI_BASE_URL", "https://cpi.rrps.com")
    sap_cpi_client_id: Optional[str] = os.getenv("SAP_CPI_CLIENT_ID")
    sap_cpi_client_secret: Optional[str] = os.getenv("SAP_CPI_CLIENT_SECRET")

    # CEC (SAP Sales Cloud) Configuration
    cec_odata_url: str = os.getenv("CEC_ODATA_URL", "https://cpi.rrps.com/odata")
    cec_oauth_token_url: str = os.getenv("CEC_OAUTH_TOKEN_URL")

    # IPAS Configuration
    ipas_proxy_url: str = os.getenv("IPAS_PROXY_URL")
    ipas_timeout: int = int(os.getenv("IPAS_TIMEOUT", "30"))
    ipas_xml_dir: str = os.getenv("IPAS_XML_DIR", "")

    # MS5/ECC Configuration
    ms5_sales_org: str = os.getenv("MS5_SALES_ORG", "1000")
    ms5_dist_channel: str = os.getenv("MS5_DIST_CHANNEL", "10")
    ms5_division: str = os.getenv("MS5_DIVISION", "00")

    # Aravo KYP Configuration (Direct REST API — NOT via CPI)
    aravo_base_url: str = os.getenv("ARAVO_BASE_URL", "https://prod.aravo.co.uk")
    aravo_api_version: str = os.getenv("ARAVO_API_VERSION", "v5.0")
    aravo_report_id: str = os.getenv("ARAVO_REPORT_ID", "")
    aravo_auth_token: str = os.getenv("ARAVO_AUTH_TOKEN", "")  # Pre-encoded Basic Auth token
    aravo_timeout: int = int(os.getenv("ARAVO_TIMEOUT", "30"))
    aravo_verify_ssl: bool = os.getenv("ARAVO_VERIFY_SSL", "True").lower() == "true"

    # POV Configuration
    pov_pilot_mode: bool = os.getenv("POV_PILOT_MODE", "True").lower() == "true"
    pov_baseline_cohort: str = os.getenv("POV_BASELINE_COHORT", "2025-Q1")
    pov_pilot_cohort: str = os.getenv("POV_PILOT_COHORT", "2025-Q2")
    pov_metrics_enabled: bool = os.getenv("POV_METRICS_ENABLED", "True").lower() == "true"
    
    def __post_init__(self):
        """Validate configuration after initialization."""
        if self.environment == "production":
            if not self.secret_key:
                raise ValueError("SECRET_KEY is required in production")
            if not self.database_url:
                raise ValueError("DATABASE_URL is required in production")
    
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
        return f"http://{self.api_host}:{self.api_port}{self.api_prefix}"

    def get_aravo_report_url(self) -> str:
        """Get Aravo KYP report endpoint URL."""
        return f"{self.aravo_base_url}/aems/restservices/{self.aravo_api_version}/reports/{self.aravo_report_id}"


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
    print("App Configuration:")
    print(f"  Name: {config.app_name}")
    print(f"  Version: {config.app_version}")
    print(f"  Environment: {config.environment}")
    print(f"  Database URL: {config.get_database_url()}")
    print(f"  API URL: {config.get_api_url()}")
    print(f"  Debug: {config.debug}")
    
    if validate_config():
        print("✅ Configuration is valid")
    else:
        print("❌ Configuration has errors")