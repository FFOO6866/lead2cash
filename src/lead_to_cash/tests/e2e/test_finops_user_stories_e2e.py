"""
End-to-End Tests for FinOps User Stories (Story 4.x).

Tests the complete FinOps user journey through the production API:
- GET https://rr.kailash.ai/api/v1/finops/summary
- GET https://rr.kailash.ai/api/v1/finops/billing
- GET https://rr.kailash.ai/api/v1/finops/collections
- POST https://rr.kailash.ai/api/v1/chat (as finops user)

NO MOCKING - Tests use real production infrastructure per 3-tier testing policy.

Tier 3 (E2E): Full system integration against production API.

Prerequisites:
- FinOps user JWT cookie in /tmp/finops_cookies.txt
- OR standard cookies.txt with financeops role user
- Production API available at https://rr.kailash.ai
- Network connectivity to production

Cookie File Formats:
1. Simple format: jwt_token=<token_value>
2. Netscape format (from browser export)
"""

import os
import uuid
from pathlib import Path
from typing import Optional

import httpx
import pytest

# Production API configuration
PROD_URL = os.getenv("E2E_API_URL", "https://rr.kailash.ai")
FINOPS_SUMMARY_ENDPOINT = f"{PROD_URL}/api/v1/finops/summary"
FINOPS_BILLING_ENDPOINT = f"{PROD_URL}/api/v1/finops/billing"
FINOPS_COLLECTIONS_ENDPOINT = f"{PROD_URL}/api/v1/finops/collections"
FINOPS_AGING_ENDPOINT = f"{PROD_URL}/api/v1/finops/aging"
CHAT_ENDPOINT = f"{PROD_URL}/api/v1/chat"

# Cookie file paths
FINOPS_COOKIES_FILE = Path("/tmp/finops_cookies.txt")
STANDARD_COOKIES_FILE = Path("/tmp/cookies.txt")

# Test timeout for E2E (production APIs may take longer)
E2E_TIMEOUT = 60.0


def load_finops_cookie() -> Optional[str]:
    """
    Load FinOps user JWT cookie from cookie files.

    Tries:
    1. /tmp/finops_cookies.txt (finops-specific)
    2. /tmp/cookies.txt (general, may have finops user)

    Returns:
        Cookie string for httpx headers or None if not found.
    """
    for cookies_file in [FINOPS_COOKIES_FILE, STANDARD_COOKIES_FILE]:
        if not cookies_file.exists():
            continue

        content = cookies_file.read_text().strip()

        # Try simple format first
        if content.startswith("jwt_token="):
            return content

        # Try extracting from Netscape format
        jwt_token = None
        session_token = None

        for line in content.split("\n"):
            line = line.strip()
            if not line or line.startswith("# "):
                continue
            if line.startswith("#HttpOnly_"):
                line = line[len("#HttpOnly_") :]
            parts = line.split("\t")
            if len(parts) >= 7:
                cookie_name = parts[5]
                cookie_value = parts[6]
                if cookie_name == "jwt_token":
                    jwt_token = cookie_value
                elif cookie_name == "session_token":
                    session_token = cookie_value

        cookies = []
        if jwt_token:
            cookies.append(f"jwt_token={jwt_token}")
        if session_token:
            cookies.append(f"session_token={session_token}")

        if cookies:
            return "; ".join(cookies)

        # Fallback: use entire content as cookie if it looks like a JWT
        if len(content) > 20 and content.count(".") == 2:
            return f"jwt_token={content}"

    return None


@pytest.fixture(scope="module")
def finops_auth_cookies() -> dict:
    """
    Load FinOps user JWT cookies for authenticated requests.

    Returns:
        Dict with cookie header for httpx.

    Raises:
        pytest.skip if cookies not available.
    """
    cookie_str = load_finops_cookie()

    if not cookie_str:
        pytest.skip(
            "FinOps JWT cookie not found in /tmp/finops_cookies.txt or /tmp/cookies.txt. "
            "Please authenticate as a financeops user first."
        )

    return {"Cookie": cookie_str}


@pytest.fixture
def unique_session_id() -> str:
    """Generate unique session ID for test isolation."""
    return f"finops-e2e-{uuid.uuid4().hex[:12]}"


# =============================================================================
# Story 4.1: FinOps Dashboard Access
# =============================================================================


class TestFinOpsDashboardAccess:
    """
    Story 4.1: As a FinanceOps user, I can access the billing/collections dashboard.

    Tests that finops users can:
    - Access /api/v1/finops/summary
    - Access /api/v1/finops/billing
    - Access /api/v1/finops/collections
    - Access /api/v1/finops/aging
    """

    @pytest.mark.e2e
    @pytest.mark.production
    @pytest.mark.asyncio
    @pytest.mark.timeout(E2E_TIMEOUT)
    async def test_e2e_finops_summary_access(self, finops_auth_cookies):
        """
        T4.1.1: FinOps user can access billing summary.

        Expected: Returns billing, collections, and overdue counts.

        Acceptance Criteria:
        - AC4.1.1: FinOps user can access summary endpoint
        - AC4.1.2: Summary includes billing_count, collections_count, overdue_count
        """
        async with httpx.AsyncClient(verify=True) as client:
            response = await client.get(
                FINOPS_SUMMARY_ENDPOINT,
                headers={
                    **finops_auth_cookies,
                    "Content-Type": "application/json",
                },
                timeout=E2E_TIMEOUT,
            )

        assert response.status_code == 200, (
            f"Expected 200, got {response.status_code}: {response.text}"
        )
        data = response.json()

        # Verify required fields
        assert data.get("success") is True
        assert "billing_count" in data
        assert "collections_count" in data
        assert "overdue_count" in data
        assert "billing_amount" in data
        assert "collections_amount" in data

        # Counts should be non-negative integers
        assert isinstance(data["billing_count"], int) and data["billing_count"] >= 0
        assert (
            isinstance(data["collections_count"], int)
            and data["collections_count"] >= 0
        )
        assert isinstance(data["overdue_count"], int) and data["overdue_count"] >= 0

        print(
            f"Summary: Billing={data['billing_count']}, Collections={data['collections_count']}, Overdue={data['overdue_count']}"
        )

    @pytest.mark.e2e
    @pytest.mark.production
    @pytest.mark.asyncio
    @pytest.mark.timeout(E2E_TIMEOUT)
    async def test_e2e_finops_billing_access(self, finops_auth_cookies):
        """
        T4.1.2: FinOps user can access billing items.

        Expected: Returns list of billing items with document details.

        Acceptance Criteria:
        - AC4.1.3: Billing items include document_number, customer_name, amount
        - AC4.1.4: Items have status and due date information
        """
        async with httpx.AsyncClient(verify=True) as client:
            response = await client.get(
                FINOPS_BILLING_ENDPOINT,
                headers={
                    **finops_auth_cookies,
                    "Content-Type": "application/json",
                },
                timeout=E2E_TIMEOUT,
            )

        assert response.status_code == 200, (
            f"Expected 200, got {response.status_code}: {response.text}"
        )
        data = response.json()

        assert data.get("success") is True
        assert "items" in data
        assert isinstance(data["items"], list)
        assert "count" in data

        if data["items"]:
            item = data["items"][0]
            # Verify item structure
            assert "document_number" in item
            assert "customer_id" in item
            assert "customer_name" in item
            assert "total_amount" in item
            assert "currency" in item
            assert "status" in item

        print(f"Billing Items: {data['count']} items returned")

    @pytest.mark.e2e
    @pytest.mark.production
    @pytest.mark.asyncio
    @pytest.mark.timeout(E2E_TIMEOUT)
    async def test_e2e_finops_collections_access(self, finops_auth_cookies):
        """
        T4.1.3: FinOps user can access collections items.

        Expected: Returns list of items requiring collection action.

        Acceptance Criteria:
        - AC4.1.5: Collections only shows collection-relevant statuses
        - AC4.1.6: Items show aging information
        """
        async with httpx.AsyncClient(verify=True) as client:
            response = await client.get(
                FINOPS_COLLECTIONS_ENDPOINT,
                headers={
                    **finops_auth_cookies,
                    "Content-Type": "application/json",
                },
                timeout=E2E_TIMEOUT,
            )

        assert response.status_code == 200, (
            f"Expected 200, got {response.status_code}: {response.text}"
        )
        data = response.json()

        assert data.get("success") is True
        assert "items" in data
        assert isinstance(data["items"], list)

        # Verify all items have collection-relevant status
        valid_statuses = {"PENDING_COLLECTION", "PARTIALLY_PAID", "OVERDUE"}
        for item in data["items"]:
            assert item["status"] in valid_statuses, (
                f"Unexpected status: {item['status']}"
            )

        print(f"Collections Items: {data['count']} items returned")

    @pytest.mark.e2e
    @pytest.mark.production
    @pytest.mark.asyncio
    @pytest.mark.timeout(E2E_TIMEOUT)
    async def test_e2e_finops_aging_access(self, finops_auth_cookies):
        """
        T4.1.4: FinOps user can access aging buckets.

        Expected: Returns aging bucket breakdown.

        Acceptance Criteria:
        - AC4.1.7: Aging includes 3 buckets: CURRENT (green), 1-30 (yellow), 30+ (red)
        - AC4.1.8: Each bucket shows count and amount
        """
        async with httpx.AsyncClient(verify=True) as client:
            response = await client.get(
                FINOPS_AGING_ENDPOINT,
                headers={
                    **finops_auth_cookies,
                    "Content-Type": "application/json",
                },
                timeout=E2E_TIMEOUT,
            )

        assert response.status_code == 200, (
            f"Expected 200, got {response.status_code}: {response.text}"
        )
        data = response.json()

        assert data.get("success") is True
        assert "buckets" in data

        buckets = data["buckets"]
        # 4 aging buckets: CURRENT (green), 0-30 (amber), 30-45 (orange), 45+ (red)
        expected_buckets = ["CURRENT", "0-30", "30-45", "45+"]
        for bucket_name in expected_buckets:
            assert bucket_name in buckets, f"Missing bucket: {bucket_name}"
            assert "count" in buckets[bucket_name]
            assert "amount" in buckets[bucket_name]

        print(f"Aging Buckets: {buckets}")


# =============================================================================
# Story 4.2: FinOps Chat Integration
# =============================================================================


class TestFinOpsChatIntegration:
    """
    Story 4.2: As a FinanceOps user, I can chat about billing and collections.

    Tests that finops users receive appropriate responses via chat:
    - Billing inquiries route to BillingCollectionsAgent
    - Collections inquiries work correctly
    - Role-based responses are tailored for finops
    """

    @pytest.mark.e2e
    @pytest.mark.production
    @pytest.mark.asyncio
    @pytest.mark.timeout(E2E_TIMEOUT)
    async def test_e2e_finops_chat_billing_query(
        self, finops_auth_cookies, unique_session_id
    ):
        """
        T4.2.1: FinOps user can ask about billing items via chat.

        Input: "Show me pending billing items"
        Expected: Response with billing information.

        Acceptance Criteria:
        - AC4.2.1: Chat routes to FinOpsOrchestratorAgent
        - AC4.2.2: Response contains billing-related information
        """
        async with httpx.AsyncClient(verify=True) as client:
            response = await client.post(
                CHAT_ENDPOINT,
                json={"message": "Show me pending billing items"},
                headers={
                    **finops_auth_cookies,
                    "Content-Type": "application/json",
                    "X-Session-ID": unique_session_id,
                },
                timeout=E2E_TIMEOUT,
            )

        assert response.status_code == 200, (
            f"Expected 200, got {response.status_code}: {response.text}"
        )
        data = response.json()

        # Should get an answer
        assert data.get("type") in ["answer", "clarification_needed"]

        # Answer should mention billing-related terms
        if data.get("type") == "answer":
            answer = data.get("answer", "").lower()
            billing_indicators = [
                "billing",
                "invoice",
                "pending",
                "document",
                "amount",
                "customer",
                "sgd",
                "eur",
                "usd",
                "payment",
            ]
            has_billing_content = any(term in answer for term in billing_indicators)
            assert has_billing_content, (
                f"Expected billing content in answer: {answer[:300]}"
            )

        print(f"Chat Response: {data.get('answer', '')[:500]}...")

    @pytest.mark.e2e
    @pytest.mark.production
    @pytest.mark.asyncio
    @pytest.mark.timeout(E2E_TIMEOUT)
    async def test_e2e_finops_chat_collections_query(
        self, finops_auth_cookies, unique_session_id
    ):
        """
        T4.2.2: FinOps user can ask about collections via chat.

        Input: "What invoices are overdue?"
        Expected: Response with collections/overdue information.

        Acceptance Criteria:
        - AC4.2.3: Query is classified as collections task
        - AC4.2.4: Response addresses overdue items
        """
        async with httpx.AsyncClient(verify=True) as client:
            response = await client.post(
                CHAT_ENDPOINT,
                json={"message": "What invoices are overdue?"},
                headers={
                    **finops_auth_cookies,
                    "Content-Type": "application/json",
                    "X-Session-ID": unique_session_id,
                },
                timeout=E2E_TIMEOUT,
            )

        assert response.status_code == 200, (
            f"Expected 200, got {response.status_code}: {response.text}"
        )
        data = response.json()

        assert data.get("type") in ["answer", "clarification_needed"]

        if data.get("type") == "answer":
            answer = data.get("answer", "").lower()
            collections_indicators = [
                "overdue",
                "collection",
                "past due",
                "outstanding",
                "payment",
                "aging",
                "days",
                "invoice",
            ]
            has_collections_content = any(
                term in answer for term in collections_indicators
            )
            assert has_collections_content, (
                f"Expected collections content in answer: {answer[:300]}"
            )

        print(f"Chat Response: {data.get('answer', '')[:500]}...")

    @pytest.mark.e2e
    @pytest.mark.production
    @pytest.mark.asyncio
    @pytest.mark.timeout(E2E_TIMEOUT)
    async def test_e2e_finops_chat_aging_query(
        self, finops_auth_cookies, unique_session_id
    ):
        """
        T4.2.3: FinOps user can ask about aging buckets via chat.

        Input: "Show me the aging bucket breakdown"
        Expected: Response with aging information.

        Acceptance Criteria:
        - AC4.2.5: Query is classified as aging task
        - AC4.2.6: Response includes bucket breakdown
        """
        async with httpx.AsyncClient(verify=True) as client:
            response = await client.post(
                CHAT_ENDPOINT,
                json={"message": "Show me the aging bucket breakdown"},
                headers={
                    **finops_auth_cookies,
                    "Content-Type": "application/json",
                    "X-Session-ID": unique_session_id,
                },
                timeout=E2E_TIMEOUT,
            )

        assert response.status_code == 200, (
            f"Expected 200, got {response.status_code}: {response.text}"
        )
        data = response.json()

        assert data.get("type") in ["answer", "clarification_needed"]

        if data.get("type") == "answer":
            answer = data.get("answer", "").lower()
            aging_indicators = [
                "aging",
                "bucket",
                "current",
                "30",
                "60",
                "90",
                "days",
                "overdue",
                "breakdown",
            ]
            has_aging_content = any(term in answer for term in aging_indicators)
            assert has_aging_content, (
                f"Expected aging content in answer: {answer[:300]}"
            )

        print(f"Chat Response: {data.get('answer', '')[:500]}...")


# =============================================================================
# Story 4.3: FinOps RBAC Enforcement
# =============================================================================


class TestFinOpsRBACEnforcement:
    """
    Story 4.3: FinOps endpoints enforce role-based access control.

    Note: These tests verify that finops endpoints return proper data for
    authorized users. Testing RBAC denial requires sales_ops user cookies.
    """

    @pytest.mark.e2e
    @pytest.mark.production
    @pytest.mark.asyncio
    @pytest.mark.timeout(E2E_TIMEOUT)
    async def test_e2e_finops_filter_by_customer(self, finops_auth_cookies):
        """
        T4.3.1: FinOps user can filter billing by customer.

        Expected: Filtering by customer_id returns only that customer's items.

        Acceptance Criteria:
        - AC4.3.1: Customer filter works correctly
        - AC4.3.2: All returned items belong to specified customer
        """
        # Use ST Engineering customer ID
        customer_id = "0022005992"

        async with httpx.AsyncClient(verify=True) as client:
            response = await client.get(
                FINOPS_BILLING_ENDPOINT,
                params={"customer_id": customer_id},
                headers={
                    **finops_auth_cookies,
                    "Content-Type": "application/json",
                },
                timeout=E2E_TIMEOUT,
            )

        assert response.status_code == 200
        data = response.json()

        assert data.get("success") is True
        assert data["filters"]["customer_id"] == customer_id

        # All items should be for the specified customer
        for item in data["items"]:
            assert item["customer_id"] == customer_id

        print(f"Filtered to customer {customer_id}: {data['count']} items")

    @pytest.mark.e2e
    @pytest.mark.production
    @pytest.mark.asyncio
    @pytest.mark.timeout(E2E_TIMEOUT)
    async def test_e2e_finops_filter_by_status(self, finops_auth_cookies):
        """
        T4.3.2: FinOps user can filter billing by status.

        Expected: Filtering by status returns only matching items.

        Acceptance Criteria:
        - AC4.3.3: Status filter works correctly
        - AC4.3.4: All returned items have specified status
        """
        status = "PENDING_BILLING"

        async with httpx.AsyncClient(verify=True) as client:
            response = await client.get(
                FINOPS_BILLING_ENDPOINT,
                params={"status": status},
                headers={
                    **finops_auth_cookies,
                    "Content-Type": "application/json",
                },
                timeout=E2E_TIMEOUT,
            )

        assert response.status_code == 200
        data = response.json()

        assert data.get("success") is True
        assert data["filters"]["status"] == status

        # All items should have the specified status
        for item in data["items"]:
            assert item["status"] == status

        print(f"Filtered to status {status}: {data['count']} items")

    @pytest.mark.e2e
    @pytest.mark.production
    @pytest.mark.asyncio
    @pytest.mark.timeout(E2E_TIMEOUT)
    async def test_e2e_finops_invalid_customer_id_rejected(self, finops_auth_cookies):
        """
        T4.3.3: Invalid customer_id is rejected.

        Expected: 400 error for invalid customer_id format.

        Acceptance Criteria:
        - AC4.3.5: Input validation is enforced
        - AC4.3.6: Clear error message returned
        """
        async with httpx.AsyncClient(verify=True) as client:
            response = await client.get(
                FINOPS_BILLING_ENDPOINT,
                params={"customer_id": "INVALID"},
                headers={
                    **finops_auth_cookies,
                    "Content-Type": "application/json",
                },
                timeout=E2E_TIMEOUT,
            )

        assert response.status_code == 400
        data = response.json()
        assert "invalid" in data.get("detail", "").lower()

        print(f"Validation error: {data.get('detail')}")


# =============================================================================
# Test Discovery Helper
# =============================================================================

if __name__ == "__main__":
    print("E2E Test File for FinOps User Stories (Story 4.x)")
    print(f"Production URL: {PROD_URL}")
    print(f"FinOps Summary: {FINOPS_SUMMARY_ENDPOINT}")
    print(f"FinOps Billing: {FINOPS_BILLING_ENDPOINT}")
    print(f"FinOps Collections: {FINOPS_COLLECTIONS_ENDPOINT}")
    print(f"Chat Endpoint: {CHAT_ENDPOINT}")
    print(f"FinOps Cookies File: {FINOPS_COOKIES_FILE}")
    print(f"Standard Cookies File: {STANDARD_COOKIES_FILE}")
    print(f"FinOps Cookies exist: {FINOPS_COOKIES_FILE.exists()}")
    print(f"Standard Cookies exist: {STANDARD_COOKIES_FILE.exists()}")
