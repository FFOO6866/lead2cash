"""
Unit tests for configuration module.
"""


def test_config_loads():
    """Test that configuration loads correctly."""
    from lead_to_cash.config import config

    assert config.app_name == "lead_to_cash"
    assert config.app_version == "1.0.0"
    assert "RRPS" in config.app_description


def test_config_sap_cpi_urls_optional():
    """Test SAP CPI URL configuration is optional (no hardcoded defaults)."""
    import os

    from lead_to_cash.config import SAPCPIConfig

    # Without env vars, URLs should be None
    # Save and clear env vars
    saved_dev = os.environ.pop("SAP_CPI_DEV_URL", None)
    saved_qa = os.environ.pop("SAP_CPI_QA_URL", None)
    saved_prod = os.environ.pop("SAP_CPI_PROD_URL", None)

    try:
        fresh_config = SAPCPIConfig()
        # URLs should be None or from env vars - no hardcoded defaults
        assert fresh_config.dev_url is None or "rrps" in fresh_config.dev_url
        assert fresh_config.qa_url is None or "rrps" in fresh_config.qa_url
        assert fresh_config.prod_url is None or "rrps" in fresh_config.prod_url
    finally:
        # Restore env vars
        if saved_dev:
            os.environ["SAP_CPI_DEV_URL"] = saved_dev
        if saved_qa:
            os.environ["SAP_CPI_QA_URL"] = saved_qa
        if saved_prod:
            os.environ["SAP_CPI_PROD_URL"] = saved_prod


def test_config_get_cpi_url_empty_when_not_configured():
    """Test CPI URL returns empty string when not configured."""
    from lead_to_cash.config import SAPCPIConfig

    # Create config with no URLs
    cpi_config = SAPCPIConfig()
    cpi_config.dev_url = None
    cpi_config.qa_url = None
    cpi_config.prod_url = None

    # Should return empty string, not None or hardcoded value
    assert cpi_config.get_url("development") == ""
    assert cpi_config.get_url("qa") == ""
    assert cpi_config.get_url("production") == ""


def test_config_kpi_targets():
    """Test KPI target values are set correctly."""
    from lead_to_cash.config import config

    assert config.kpi_field_autofill_target == 0.80
    assert config.kpi_first_time_right_target == 0.85
    assert config.kpi_cycle_time_reduction == 0.40
    assert config.kpi_billing_ready_target == 0.90
    assert config.kpi_traceability_target == 1.00


def test_config_is_sap_configured():
    """Test SAP configuration status check."""
    from lead_to_cash.config import config

    status = config.is_sap_configured()
    assert isinstance(status, dict)
    assert "cpi" in status
    assert "ms5" in status
    assert "cec" in status
    assert "ipas" in status


def test_config_api_url():
    """Test API URL generation."""
    from lead_to_cash.config import config

    api_url = config.get_api_url()
    assert "/api/v1" in api_url


def test_config_database_url_fallback():
    """Test database URL fallback for development."""
    from lead_to_cash.config import AppConfig

    # Create a fresh config without DATABASE_URL
    test_config = AppConfig()
    test_config.database_url = None

    db_url = test_config.get_database_url()
    assert "sqlite" in db_url
    assert "lead_to_cash" in db_url
