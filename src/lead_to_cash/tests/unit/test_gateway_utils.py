"""
Unit Tests for Gateway Utility Functions

Tests for IP validation, rate limiting helpers, and other gateway utilities.
"""


class TestIsValidIP:
    """Tests for _is_valid_ip function."""

    def test_valid_ipv4_addresses(self):
        """Test valid IPv4 addresses are accepted."""
        from lead_to_cash.core.gateway import _is_valid_ip

        valid_ips = [
            "192.168.1.1",
            "10.0.0.1",
            "172.16.0.1",
            "127.0.0.1",
            "0.0.0.0",
            "255.255.255.255",
            "8.8.8.8",
        ]

        for ip in valid_ips:
            assert _is_valid_ip(ip) is True, f"Expected {ip} to be valid"

    def test_valid_ipv6_addresses(self):
        """Test valid IPv6 addresses are accepted."""
        from lead_to_cash.core.gateway import _is_valid_ip

        valid_ips = [
            "::1",  # Loopback
            "2001:db8::1",  # Documentation address
            "fe80::1",  # Link-local
            "::ffff:192.168.1.1",  # IPv4-mapped
            "2001:0db8:0000:0000:0000:0000:0000:0001",  # Full form
        ]

        for ip in valid_ips:
            assert _is_valid_ip(ip) is True, f"Expected {ip} to be valid"

    def test_invalid_ipv4_with_leading_zeros_rejected(self):
        """Test IPv4 with leading zeros is rejected (security - octal interpretation)."""
        from lead_to_cash.core.gateway import _is_valid_ip

        # Leading zeros can be interpreted as octal in some contexts
        # Python's ipaddress module strictly rejects them
        invalid_ips = [
            "192.168.001.001",
            "010.0.0.1",  # Could be interpreted as octal 8.0.0.1
            "127.000.000.001",
        ]

        for ip in invalid_ips:
            assert (
                _is_valid_ip(ip) is False
            ), f"Expected {ip} to be rejected (leading zeros)"

    def test_invalid_ipv4_addresses(self):
        """Test invalid IPv4 addresses are rejected."""
        from lead_to_cash.core.gateway import _is_valid_ip

        invalid_ips = [
            "256.1.1.1",  # Octet > 255
            "192.168.1",  # Missing octet
            "192.168.1.1.1",  # Extra octet
            "192.168.1.a",  # Non-numeric
            "192.168.-1.1",  # Negative
            "192.168.1.1/24",  # CIDR notation (network, not host)
            "192.168.1.1:8080",  # With port
        ]

        for ip in invalid_ips:
            assert _is_valid_ip(ip) is False, f"Expected {ip} to be invalid"

    def test_invalid_ipv6_addresses(self):
        """Test invalid IPv6 addresses are rejected."""
        from lead_to_cash.core.gateway import _is_valid_ip

        invalid_ips = [
            "2001:db8::g",  # Invalid hex character
            "2001:db8",  # Incomplete
            "2001:db8::1/64",  # CIDR notation
            "[::1]",  # Bracketed (URL format)
        ]

        for ip in invalid_ips:
            assert _is_valid_ip(ip) is False, f"Expected {ip} to be invalid"

    def test_none_rejected(self):
        """Test None input is rejected."""
        from lead_to_cash.core.gateway import _is_valid_ip

        # None should return False, not raise an exception
        assert _is_valid_ip(None) is False  # type: ignore

    def test_empty_and_edge_cases_rejected(self):
        """Test empty string and edge cases are rejected."""
        from lead_to_cash.core.gateway import _is_valid_ip

        assert _is_valid_ip("") is False
        assert _is_valid_ip("   ") is False
        assert _is_valid_ip("localhost") is False
        assert _is_valid_ip("example.com") is False

    def test_injection_attempts_rejected(self):
        """Test potential injection attempts are rejected."""
        from lead_to_cash.core.gateway import _is_valid_ip

        injection_attempts = [
            "127.0.0.1; DROP TABLE users",
            "192.168.1.1\n192.168.1.2",
            "192.168.1.1\x00malicious",
            "<script>alert(1)</script>",
            "192.168.1.1' OR '1'='1",
        ]

        for ip in injection_attempts:
            assert (
                _is_valid_ip(ip) is False
            ), f"Expected injection attempt to be rejected: {ip}"


class TestGetClientIP:
    """Tests for _get_client_ip function."""

    def test_direct_ip_when_no_proxy(self):
        """Test returns direct IP when not from trusted proxy."""
        from unittest.mock import MagicMock

        from lead_to_cash.core.gateway import _get_client_ip

        request = MagicMock()
        request.client.host = "203.0.113.50"
        request.headers = {}

        # When direct IP is not in trusted proxies, return it directly
        ip = _get_client_ip(request)
        assert ip == "203.0.113.50"

    def test_returns_unknown_when_no_client(self):
        """Test returns 'unknown' when request has no client."""
        from unittest.mock import MagicMock

        from lead_to_cash.core.gateway import _get_client_ip

        request = MagicMock()
        request.client = None

        ip = _get_client_ip(request)
        assert ip == "unknown"

    def test_trusts_x_real_ip_from_trusted_proxy(self):
        """Test X-Real-IP is trusted when request comes from trusted proxy."""
        from unittest.mock import MagicMock, patch

        from lead_to_cash.core.gateway import _get_client_ip

        request = MagicMock()
        request.client.host = "127.0.0.1"  # Trusted proxy (localhost)
        request.headers = {"X-Real-IP": "203.0.113.100"}

        # Patch config to ensure 127.0.0.1 is in trusted_proxies
        with patch("lead_to_cash.core.gateway.config") as mock_config:
            mock_config.trusted_proxies = ["127.0.0.1"]
            ip = _get_client_ip(request)

        assert ip == "203.0.113.100"

    def test_trusts_x_forwarded_for_from_trusted_proxy(self):
        """Test X-Forwarded-For is trusted when request comes from trusted proxy."""
        from unittest.mock import MagicMock, patch

        from lead_to_cash.core.gateway import _get_client_ip

        request = MagicMock()
        request.client.host = "127.0.0.1"  # Trusted proxy
        request.headers = {"X-Forwarded-For": "203.0.113.50, 10.0.0.1, 127.0.0.1"}

        with patch("lead_to_cash.core.gateway.config") as mock_config:
            mock_config.trusted_proxies = ["127.0.0.1"]
            ip = _get_client_ip(request)

        # Should return first IP in chain (original client)
        assert ip == "203.0.113.50"

    def test_ignores_proxy_headers_from_untrusted_source(self):
        """Test proxy headers are ignored when not from trusted proxy."""
        from unittest.mock import MagicMock, patch

        from lead_to_cash.core.gateway import _get_client_ip

        request = MagicMock()
        request.client.host = "203.0.113.50"  # Not a trusted proxy
        request.headers = {"X-Real-IP": "10.0.0.1"}  # Spoofed header

        with patch("lead_to_cash.core.gateway.config") as mock_config:
            mock_config.trusted_proxies = ["127.0.0.1"]
            ip = _get_client_ip(request)

        # Should return direct IP, ignoring spoofed header
        assert ip == "203.0.113.50"

    def test_rejects_invalid_x_real_ip(self):
        """Test invalid X-Real-IP is rejected even from trusted proxy."""
        from unittest.mock import MagicMock, patch

        from lead_to_cash.core.gateway import _get_client_ip

        request = MagicMock()
        request.client.host = "127.0.0.1"  # Trusted proxy
        request.headers = {"X-Real-IP": "not-an-ip"}

        with patch("lead_to_cash.core.gateway.config") as mock_config:
            mock_config.trusted_proxies = ["127.0.0.1"]
            ip = _get_client_ip(request)

        # Should fall back to direct IP since X-Real-IP is invalid
        assert ip == "127.0.0.1"
