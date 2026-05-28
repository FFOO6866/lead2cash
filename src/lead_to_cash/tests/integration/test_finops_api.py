"""
FinOps API Endpoint Integration Tests

Tests the HTTP endpoints for /api/v1/finops/* using FastAPI TestClient.
NO MOCKING - Tests use real FinOpsDataService with CPISimulator per 3-tier testing policy.

Tier 2 (Integration): Tests API endpoints with real data services.

Tests cover:
- GET /api/v1/finops/summary
- GET /api/v1/finops/billing
- GET /api/v1/finops/collections
- GET /api/v1/finops/aging
- POST /api/v1/finops/refresh
- RBAC enforcement
- Input validation

Note: The middleware validates JWT tokens BEFORE dependency injection runs.
We patch auth_manager.validate_jwt to return test user data, which sets request.state.user
in the middleware, allowing the endpoint to access the user via the get_current_user dependency.
"""

from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from lead_to_cash.core.auth import AuthManager, AuthUser
from lead_to_cash.core.gateway import app

# =============================================================================
# Test Fixtures
# =============================================================================


def create_finops_user_data():
    """Create financeops user data dict (as returned by JWT validation)."""
    return {
        "user_id": "sewsen.goh",
        "username": "sewsen.goh",
        "roles": ["financeops"],
        "tenant_id": "default",
        "first_name": "Sew Sen",
        "last_name": "Goh",
    }


def create_sales_user_data():
    """Create sales_ops user data dict (for RBAC denial tests)."""
    return {
        "user_id": "kianseng.tee",
        "username": "kianseng.tee",
        "roles": ["sales_ops"],
        "tenant_id": "default",
        "first_name": "Kian Seng",
        "last_name": "Tee",
    }


def create_finops_user():
    """Create a financeops AuthUser for testing."""
    return AuthUser(**create_finops_user_data())


def create_sales_user():
    """Create a sales_ops AuthUser for testing."""
    return AuthUser(**create_sales_user_data())


def create_mock_auth_manager_for_user(user_data):
    """Create mock auth manager that validates JWT and checks permissions."""
    manager = MagicMock(spec=AuthManager)

    # validate_jwt returns user data dict when JWT is provided
    manager.validate_jwt = MagicMock(return_value=user_data)

    def check_permission(user, resource, action):
        # financeops role has billing and collections permissions
        if "financeops" in user.roles:
            if resource in ["billing", "collections", "payments", "finops_dashboard"]:
                return True
        # sales_ops role does NOT have billing/collections permissions
        if "sales_ops" in user.roles:
            if resource in ["billing", "collections"]:
                return False
        return False

    manager.check_permission = check_permission
    return manager


@pytest.fixture
def finops_user():
    """Create a financeops user for testing."""
    return create_finops_user()


@pytest.fixture
def sales_user():
    """Create a sales_ops user for testing."""
    return create_sales_user()


@pytest.fixture
def client_with_finops_auth(finops_user):
    """Create TestClient with finops user authentication.

    The middleware validates JWT tokens before dependency injection runs.
    We patch auth_manager.validate_jwt to return finops user data,
    which sets request.state.user in the middleware.
    """
    user_data = create_finops_user_data()
    mock_auth_manager = create_mock_auth_manager_for_user(user_data)

    with patch("lead_to_cash.core.gateway.auth_manager", mock_auth_manager):
        # Create client with a dummy JWT cookie to trigger JWT validation path
        client = TestClient(app, cookies={"jwt_token": "test_jwt_token"})
        yield client


@pytest.fixture
def client_with_sales_auth(sales_user):
    """Create TestClient with sales user authentication (for RBAC denial tests)."""
    user_data = create_sales_user_data()
    mock_auth_manager = create_mock_auth_manager_for_user(user_data)

    with patch("lead_to_cash.core.gateway.auth_manager", mock_auth_manager):
        client = TestClient(app, cookies={"jwt_token": "test_jwt_token"})
        yield client


@pytest.fixture
def client_unauthenticated():
    """Create TestClient without authentication.

    Don't provide JWT token and mock validate_jwt to return None.
    """
    mock_auth_manager = MagicMock(spec=AuthManager)
    mock_auth_manager.validate_jwt = MagicMock(return_value=None)

    with patch("lead_to_cash.core.gateway.auth_manager", mock_auth_manager):
        client = TestClient(app, raise_server_exceptions=False)
        yield client


# =============================================================================
# GET /api/v1/finops/summary Tests
# =============================================================================


class TestFinopsSummaryEndpoint:
    """Tests for GET /api/v1/finops/summary."""

    def test_summary_returns_success_for_finops_user(self, client_with_finops_auth):
        """Test finops user can access summary endpoint."""
        response = client_with_finops_auth.get("/api/v1/finops/summary")

        assert response.status_code == 200
        data = response.json()

        assert data["success"] is True
        assert "billing_count" in data
        assert "collections_count" in data
        assert "overdue_count" in data
        assert "billing_amount" in data
        assert "collections_amount" in data
        assert "as_of_date" in data
        assert "timestamp" in data

    def test_summary_returns_correct_count_types(self, client_with_finops_auth):
        """Test summary returns numeric counts."""
        response = client_with_finops_auth.get("/api/v1/finops/summary")

        assert response.status_code == 200
        data = response.json()

        assert isinstance(data["billing_count"], int)
        assert isinstance(data["collections_count"], int)
        assert isinstance(data["overdue_count"], int)
        assert data["billing_count"] >= 0
        assert data["collections_count"] >= 0
        assert data["overdue_count"] >= 0

    def test_summary_denied_for_sales_user(self, client_with_sales_auth):
        """Test sales user is denied access to finops summary."""
        response = client_with_sales_auth.get("/api/v1/finops/summary")

        assert response.status_code == 403
        assert "billing permissions" in response.json()["detail"].lower()

    def test_summary_denied_for_unauthenticated(self, client_unauthenticated):
        """Test unauthenticated user is denied access."""
        response = client_unauthenticated.get("/api/v1/finops/summary")

        assert response.status_code == 401


# =============================================================================
# GET /api/v1/finops/billing Tests
# =============================================================================


class TestFinopsBillingEndpoint:
    """Tests for GET /api/v1/finops/billing."""

    def test_billing_returns_items_for_finops_user(self, client_with_finops_auth):
        """Test finops user can access billing items."""
        response = client_with_finops_auth.get("/api/v1/finops/billing")

        assert response.status_code == 200
        data = response.json()

        assert data["success"] is True
        assert "items" in data
        assert isinstance(data["items"], list)
        assert "count" in data
        assert "filters" in data
        assert "timestamp" in data

    def test_billing_items_have_required_fields(self, client_with_finops_auth):
        """Test billing items have all required fields."""
        response = client_with_finops_auth.get("/api/v1/finops/billing")

        assert response.status_code == 200
        data = response.json()

        if data["items"]:
            item = data["items"][0]
            assert "document_number" in item
            assert "customer_id" in item
            assert "customer_name" in item
            assert "total_amount" in item
            assert "currency" in item
            assert "status" in item

    def test_billing_filter_by_customer_id(self, client_with_finops_auth):
        """Test filtering billing items by customer_id."""
        response = client_with_finops_auth.get(
            "/api/v1/finops/billing",
            params={"customer_id": "0022005992"},  # ST Engineering
        )

        assert response.status_code == 200
        data = response.json()

        assert data["filters"]["customer_id"] == "0022005992"
        for item in data["items"]:
            assert item["customer_id"] == "0022005992"

    def test_billing_filter_by_status(self, client_with_finops_auth):
        """Test filtering billing items by status."""
        response = client_with_finops_auth.get(
            "/api/v1/finops/billing", params={"status": "PENDING_BILLING"}
        )

        assert response.status_code == 200
        data = response.json()

        assert data["filters"]["status"] == "PENDING_BILLING"
        for item in data["items"]:
            assert item["status"] == "PENDING_BILLING"

    def test_billing_rejects_invalid_customer_id(self, client_with_finops_auth):
        """Test invalid customer_id format is rejected."""
        response = client_with_finops_auth.get(
            "/api/v1/finops/billing",
            params={"customer_id": "ABC123"},  # Invalid format
        )

        assert response.status_code == 400
        assert "Invalid customer_id format" in response.json()["detail"]

    def test_billing_rejects_invalid_status(self, client_with_finops_auth):
        """Test invalid status value is rejected."""
        response = client_with_finops_auth.get(
            "/api/v1/finops/billing", params={"status": "INVALID_STATUS"}
        )

        assert response.status_code == 400
        assert "Invalid status" in response.json()["detail"]
        assert "Allowed values" in response.json()["detail"]

    def test_billing_denied_for_sales_user(self, client_with_sales_auth):
        """Test sales user is denied access to billing items."""
        response = client_with_sales_auth.get("/api/v1/finops/billing")

        assert response.status_code == 403


# =============================================================================
# GET /api/v1/finops/collections Tests
# =============================================================================


class TestFinopsCollectionsEndpoint:
    """Tests for GET /api/v1/finops/collections."""

    def test_collections_returns_items_for_finops_user(self, client_with_finops_auth):
        """Test finops user can access collections items."""
        response = client_with_finops_auth.get("/api/v1/finops/collections")

        assert response.status_code == 200
        data = response.json()

        assert data["success"] is True
        assert "items" in data
        assert isinstance(data["items"], list)
        assert "count" in data

    def test_collections_items_are_collection_relevant(self, client_with_finops_auth):
        """Test collections only returns collection-relevant statuses."""
        response = client_with_finops_auth.get("/api/v1/finops/collections")

        assert response.status_code == 200
        data = response.json()

        valid_statuses = {"PENDING_COLLECTION", "PARTIALLY_PAID", "OVERDUE"}
        for item in data["items"]:
            assert item["status"] in valid_statuses

    def test_collections_rejects_invalid_status(self, client_with_finops_auth):
        """Test invalid status value is rejected for collections."""
        # PENDING_BILLING is not valid for collections endpoint
        response = client_with_finops_auth.get(
            "/api/v1/finops/collections", params={"status": "PENDING_BILLING"}
        )

        assert response.status_code == 400
        assert "Invalid status" in response.json()["detail"]
        assert "collections" in response.json()["detail"].lower()

    def test_collections_denied_for_sales_user(self, client_with_sales_auth):
        """Test sales user is denied access to collections items."""
        response = client_with_sales_auth.get("/api/v1/finops/collections")

        assert response.status_code == 403


# =============================================================================
# GET /api/v1/finops/aging Tests
# =============================================================================


class TestFinopsAgingEndpoint:
    """Tests for GET /api/v1/finops/aging."""

    def test_aging_returns_buckets_for_finops_user(self, client_with_finops_auth):
        """Test finops user can access aging buckets."""
        response = client_with_finops_auth.get("/api/v1/finops/aging")

        assert response.status_code == 200
        data = response.json()

        assert data["success"] is True
        assert "buckets" in data
        assert "timestamp" in data

    def test_aging_buckets_have_expected_categories(self, client_with_finops_auth):
        """Test aging buckets have standard categories."""
        response = client_with_finops_auth.get("/api/v1/finops/aging")

        assert response.status_code == 200
        data = response.json()

        buckets = data["buckets"]
        # 4 aging buckets: CURRENT (green), 0-30 (amber), 30-45 (orange), 45+ (red)
        expected_buckets = ["CURRENT", "0-30", "30-45", "45+"]
        for bucket_name in expected_buckets:
            assert bucket_name in buckets
            assert "count" in buckets[bucket_name]
            assert "amount" in buckets[bucket_name]

    def test_aging_denied_for_sales_user(self, client_with_sales_auth):
        """Test sales user is denied access to aging buckets."""
        response = client_with_sales_auth.get("/api/v1/finops/aging")

        assert response.status_code == 403


# =============================================================================
# POST /api/v1/finops/refresh Tests
# =============================================================================


class TestFinopsRefreshEndpoint:
    """Tests for POST /api/v1/finops/refresh."""

    def test_refresh_succeeds_for_finops_user(self, client_with_finops_auth):
        """Test finops user can trigger data refresh."""
        response = client_with_finops_auth.post("/api/v1/finops/refresh")

        assert response.status_code == 200
        data = response.json()

        assert data["success"] is True
        assert "refreshed_at" in data

    def test_refresh_denied_for_sales_user(self, client_with_sales_auth):
        """Test sales user is denied access to refresh endpoint."""
        response = client_with_sales_auth.post("/api/v1/finops/refresh")

        assert response.status_code == 403


# =============================================================================
# Input Validation Tests
# =============================================================================


class TestFinopsInputValidation:
    """Tests for input validation on finops endpoints."""

    def test_customer_id_must_be_10_digits(self, client_with_finops_auth):
        """Test customer_id must be exactly 10 digits."""
        invalid_ids = [
            "123456789",  # 9 digits
            "12345678901",  # 11 digits
            "00001234AB",  # Contains letters
            "0000-1234-56",  # Contains hyphens
        ]

        for invalid_id in invalid_ids:
            response = client_with_finops_auth.get(
                "/api/v1/finops/billing", params={"customer_id": invalid_id}
            )
            assert response.status_code == 400, (
                f"Expected 400 for customer_id={invalid_id}"
            )

    def test_valid_statuses_for_billing(self, client_with_finops_auth):
        """Test all valid statuses are accepted for billing endpoint."""
        valid_statuses = [
            "PENDING_BILLING",
            "PENDING_COLLECTION",
            "PARTIALLY_PAID",
            "PAID",
            "OVERDUE",
        ]

        for status in valid_statuses:
            response = client_with_finops_auth.get(
                "/api/v1/finops/billing", params={"status": status}
            )
            assert response.status_code == 200, f"Expected 200 for status={status}"

    def test_valid_statuses_for_collections(self, client_with_finops_auth):
        """Test only collections-relevant statuses are accepted."""
        valid_statuses = ["PENDING_COLLECTION", "PARTIALLY_PAID", "OVERDUE"]

        for status in valid_statuses:
            response = client_with_finops_auth.get(
                "/api/v1/finops/collections", params={"status": status}
            )
            assert response.status_code == 200, f"Expected 200 for status={status}"


# =============================================================================
# RBAC Enforcement Tests
# =============================================================================


class TestFinopsRBACEnforcement:
    """Tests for RBAC enforcement across all finops endpoints."""

    def test_all_finops_endpoints_require_billing_permission(
        self, client_with_sales_auth
    ):
        """Test all finops endpoints enforce billing permission."""
        endpoints = [
            ("GET", "/api/v1/finops/summary"),
            ("GET", "/api/v1/finops/billing"),
            ("GET", "/api/v1/finops/collections"),
            ("GET", "/api/v1/finops/aging"),
            ("POST", "/api/v1/finops/refresh"),
        ]

        for method, path in endpoints:
            if method == "GET":
                response = client_with_sales_auth.get(path)
            else:
                response = client_with_sales_auth.post(path)

            assert response.status_code == 403, f"Expected 403 for {method} {path}"
            assert "billing permissions" in response.json()["detail"].lower()
