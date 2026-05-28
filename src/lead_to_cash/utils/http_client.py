"""
Async HTTP Client Mixin for Lead-to-Cash services.

Provides a reusable pattern for HTTP client lifecycle management,
eliminating code duplication across ~15 service files.

Usage:
    class MyService(AsyncHTTPClientMixin):
        def __init__(self):
            super().__init__(timeout=30.0, headers={"X-Custom": "value"})

        async def fetch_data(self):
            client = await self._get_client()
            response = await client.get("https://api.example.com/data")
            return response.json()

    # Usage with context manager (recommended)
    async with MyService() as service:
        data = await service.fetch_data()

    # Manual usage (don't forget to close!)
    service = MyService()
    try:
        data = await service.fetch_data()
    finally:
        await service.close()
"""

import logging
from typing import Any, Optional

import httpx

logger = logging.getLogger(__name__)


class AsyncHTTPClientMixin:
    """Mixin providing async HTTP client lifecycle management.

    Features:
    - Lazy client initialization (created on first use)
    - Automatic reconnection if client is closed
    - Context manager support for automatic cleanup
    - Configurable timeout, headers, and follow_redirects
    - Type-safe client access

    Attributes:
        _http_client: The underlying httpx.AsyncClient instance
        _http_timeout: Request timeout in seconds
        _http_headers: Default headers for all requests
        _http_follow_redirects: Whether to follow redirects
    """

    _http_client: Optional[httpx.AsyncClient] = None
    _http_timeout: float = 60.0
    _http_headers: Optional[dict[str, str]] = None
    _http_follow_redirects: bool = False

    def __init__(
        self,
        timeout: float = 60.0,
        headers: Optional[dict[str, str]] = None,
        follow_redirects: bool = False,
        **kwargs: Any,
    ) -> None:
        """Initialize HTTP client configuration.

        Args:
            timeout: Request timeout in seconds (default: 60.0)
            headers: Default headers for all requests
            follow_redirects: Whether to follow redirects (default: False)
            **kwargs: Additional arguments passed to parent classes
        """
        # Support multiple inheritance by passing kwargs to parent
        super().__init__(**kwargs)

        self._http_client: Optional[httpx.AsyncClient] = None
        self._http_timeout = timeout
        self._http_headers = headers
        self._http_follow_redirects = follow_redirects

    def _create_http_client(self) -> httpx.AsyncClient:
        """Create a new HTTP client instance.

        Override this method in subclasses to customize client creation.
        For example, to add custom transport or event hooks.

        Returns:
            New httpx.AsyncClient instance
        """
        return httpx.AsyncClient(
            timeout=self._http_timeout,
            headers=self._http_headers,
            follow_redirects=self._http_follow_redirects,
        )

    async def _get_client(self) -> httpx.AsyncClient:
        """Get or create HTTP client.

        Creates a new client if none exists or if the existing client is closed.
        Thread-safe for asyncio (single-threaded event loop).

        Returns:
            Active httpx.AsyncClient instance
        """
        if self._http_client is None or self._http_client.is_closed:
            self._http_client = self._create_http_client()
        return self._http_client

    async def close(self) -> None:
        """Close HTTP client and release resources.

        Safe to call multiple times. Logs a debug message on cleanup.
        """
        if self._http_client is not None and not self._http_client.is_closed:
            await self._http_client.aclose()
            logger.debug(f"{self.__class__.__name__}: HTTP client closed")
        self._http_client = None

    async def __aenter__(self) -> "AsyncHTTPClientMixin":
        """Async context manager entry.

        Returns:
            Self for use in async with statement
        """
        return self

    async def __aexit__(
        self,
        exc_type: Optional[type],
        exc_val: Optional[BaseException],
        exc_tb: Optional[Any],
    ) -> None:
        """Async context manager exit - ensures client cleanup.

        Args:
            exc_type: Exception type if raised
            exc_val: Exception value if raised
            exc_tb: Exception traceback if raised
        """
        await self.close()

    @property
    def is_client_active(self) -> bool:
        """Check if HTTP client is currently active.

        Returns:
            True if client exists and is not closed
        """
        return self._http_client is not None and not self._http_client.is_closed
