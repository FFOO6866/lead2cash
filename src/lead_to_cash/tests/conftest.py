"""
Pytest configuration and fixtures for Lead-to-Cash tests.
"""

import os
import sys

import pytest

# Ensure the src directory is in the path
src_path = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if src_path not in sys.path:
    sys.path.insert(0, src_path)

# Set test environment
os.environ.setdefault("ENVIRONMENT", "test")
os.environ.setdefault("DEBUG", "True")


@pytest.fixture
def test_config():
    """Provide test configuration."""
    from lead_to_cash.config import AppConfig

    return AppConfig()


@pytest.fixture
def mock_cpi_credentials():
    """Provide mock CPI credentials for testing."""
    return {
        "client_id": "test_client_id",
        "client_secret": "test_client_secret",
        "token_url": "https://test.auth.com/oauth/token",
    }


@pytest.fixture
def sample_order_data():
    """Provide sample order data for testing."""
    return {
        "header": {
            "order_type": "ZOR",
            "sales_org": "1000",
            "distribution_channel": "10",
            "division": "00",
            "customer": "1234567890",
            "currency": "EUR",
        },
        "items": [
            {
                "material": "MATERIAL001",
                "quantity": 10,
                "unit": "EA",
                "plant": "1000",
            }
        ],
        "partners": [
            {"function": "AG", "customer": "1234567890"},  # Sold-to
            {"function": "WE", "customer": "1234567890"},  # Ship-to
        ],
    }


@pytest.fixture
def sample_opportunity_data():
    """Provide sample opportunity data for testing."""
    return {
        "id": "OPP-12345",
        "account_id": "ACC-001",
        "account_name": "Test Customer Inc.",
        "status": "Open",
        "expected_revenue": 250000.0,
        "currency": "EUR",
        "close_date": "2026-02-15",
        "products": [
            {
                "product_id": "ENGINE-001",
                "quantity": 2,
                "requested_date": "2026-03-01",
            },
            {
                "product_id": "SERVICE-001",
                "quantity": 1,
                "requested_date": "2026-03-15",
            },
        ],
        "owner": "sales.rep@rrps.com",
    }
