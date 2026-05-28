"""
PDF Scraper for Competitor Intelligence

Downloads and parses PDF documents (annual reports, technical specs)
from competitor websites using pypdf.

NO MOCKS, NO SIMULATIONS - real PDF downloads and parsing.
"""

import hashlib
import io
import logging
import re
from datetime import datetime, timezone
from typing import Any, Optional
from urllib.parse import urljoin

import httpx
from pypdf import PdfReader

from lead_to_cash.services.competitor_intel.models import (
    CompetitorDocument,
    ContentType,
    SourceType,
)

logger = logging.getLogger(__name__)


class PDFScraper:
    """
    Production PDF scraper for competitor annual reports and documents.

    Downloads PDFs from competitor investor relations pages and extracts text.
    """

    # Real PDF URLs for competitor annual reports
    # These URLs point to actual annual report PDF files
    ANNUAL_REPORT_URLS = {
        "caterpillar": {
            "annual_report_2023": "https://s7d2.scene7.com/is/content/Caterpillar/CM20240212-4e2b2-a3dc3",
            "investor_page": "https://www.caterpillar.com/en/investors/financials-results/annual-report.html",
            "name": "Caterpillar Inc.",
        },
        "cummins": {
            "annual_report_2023": "https://investor.cummins.com/static-files/c3d88e01-b45f-4a9a-9be3-5c0ab0e1f5fc",
            "investor_page": "https://investor.cummins.com/financials/annual-reports",
            "name": "Cummins Inc.",
        },
        "man_energy": {
            # MAN ES is part of Volkswagen group
            "annual_report_2023": "https://www.man-es.com/-/media/Files/man-es/company/annual-report/MAN-ES-Annual-Report-2023.pdf",
            "investor_page": "https://www.man-es.com/company/annual-report",
            "name": "MAN Energy Solutions",
        },
    }

    # HTTP headers for PDF downloads
    HEADERS = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Accept": "application/pdf,application/octet-stream,*/*",
    }

    def __init__(self):
        self._client: Optional[httpx.AsyncClient] = None

    async def _get_client(self) -> httpx.AsyncClient:
        """Get or create HTTP client for PDF downloads."""
        if self._client is None:
            self._client = httpx.AsyncClient(
                timeout=120.0,  # PDFs can be large
                follow_redirects=True,
                headers=self.HEADERS,
            )
        return self._client

    async def close(self):
        """Close HTTP client."""
        if self._client:
            await self._client.aclose()
            self._client = None

    # =========================================================================
    # PDF Download and Parsing
    # =========================================================================

    async def download_pdf(self, url: str) -> Optional[bytes]:
        """
        Download a PDF file from URL.

        Args:
            url: PDF file URL

        Returns:
            PDF content as bytes, or None if download failed
        """
        logger.info(f"Downloading PDF: {url}")

        try:
            client = await self._get_client()
            response = await client.get(url)
            response.raise_for_status()

            # Verify it's a PDF
            content_type = response.headers.get("content-type", "")
            if "pdf" not in content_type.lower() and not url.lower().endswith(".pdf"):
                # Try to detect PDF magic bytes
                if not response.content.startswith(b"%PDF"):
                    logger.warning(f"URL does not appear to be a PDF: {url}")
                    return None

            logger.info(f"Downloaded PDF: {len(response.content)} bytes")
            return response.content

        except httpx.HTTPError as e:
            logger.error(f"HTTP error downloading PDF {url}: {e}")
            return None
        except Exception as e:
            logger.error(f"Error downloading PDF {url}: {e}")
            return None

    def parse_pdf(self, pdf_content: bytes) -> dict[str, Any]:
        """
        Parse PDF content and extract text.

        Args:
            pdf_content: PDF file bytes

        Returns:
            Dictionary with extracted text and metadata
        """
        try:
            pdf_file = io.BytesIO(pdf_content)
            reader = PdfReader(pdf_file)

            # Extract metadata
            metadata = {}
            if reader.metadata:
                metadata = {
                    "title": reader.metadata.get("/Title", ""),
                    "author": reader.metadata.get("/Author", ""),
                    "subject": reader.metadata.get("/Subject", ""),
                    "creator": reader.metadata.get("/Creator", ""),
                    "producer": reader.metadata.get("/Producer", ""),
                }

            # Extract text from all pages
            text_parts = []
            for i, page in enumerate(reader.pages):
                try:
                    text = page.extract_text()
                    if text:
                        text_parts.append(f"--- Page {i + 1} ---\n{text}")
                except Exception as e:
                    logger.warning(f"Error extracting text from page {i + 1}: {e}")
                    continue

            full_text = "\n\n".join(text_parts)

            # Clean up text
            full_text = re.sub(r"\n\s*\n", "\n\n", full_text)
            full_text = re.sub(r" +", " ", full_text)

            return {
                "text": full_text,
                "page_count": len(reader.pages),
                "metadata": metadata,
            }

        except Exception as e:
            logger.error(f"Error parsing PDF: {e}")
            return {
                "text": "",
                "page_count": 0,
                "metadata": {},
                "error": str(e),
            }

    async def download_and_parse(self, url: str) -> dict[str, Any]:
        """
        Download and parse a PDF in one step.

        Args:
            url: PDF file URL

        Returns:
            Dictionary with extracted text, metadata, and URL
        """
        pdf_content = await self.download_pdf(url)
        if not pdf_content:
            return {
                "text": "",
                "url": url,
                "error": "Failed to download PDF",
            }

        result = self.parse_pdf(pdf_content)
        result["url"] = url
        result["file_size"] = len(pdf_content)

        return result

    # =========================================================================
    # Annual Report Scraping
    # =========================================================================

    async def scrape_annual_report(
        self, competitor: str
    ) -> Optional[CompetitorDocument]:
        """
        Scrape annual report for a competitor.

        Args:
            competitor: Competitor identifier

        Returns:
            CompetitorDocument with annual report content, or None if failed
        """
        if competitor not in self.ANNUAL_REPORT_URLS:
            logger.error(f"Unknown competitor: {competitor}")
            return None

        config = self.ANNUAL_REPORT_URLS[competitor]
        pdf_url = config.get("annual_report_2023")

        if not pdf_url:
            logger.warning(f"No annual report URL for {competitor}")
            return None

        logger.info(f"Scraping annual report for {competitor}")

        result = await self.download_and_parse(pdf_url)

        if result.get("error") or not result.get("text"):
            logger.error(
                f"Failed to scrape annual report for {competitor}: {result.get('error')}"
            )
            return None

        # Create document
        doc = CompetitorDocument(
            id=self._generate_doc_id(pdf_url),
            competitor=competitor,
            content_type=ContentType.ANNUAL_REPORT.value,
            source_type=SourceType.PDF.value,
            title=f"{config['name']} Annual Report 2023",
            content=result["text"],
            summary=f"Annual report for {config['name']} fiscal year 2023. Contains financial statements, business overview, and strategic outlook.",
            source_url=pdf_url,
            scraped_at=datetime.now(timezone.utc),
            metadata={
                "page_count": result.get("page_count", 0),
                "file_size": result.get("file_size", 0),
                "pdf_metadata": result.get("metadata", {}),
                "scrape_method": "pdf_scraper",
            },
        )

        logger.info(
            f"Scraped annual report for {competitor}: {result.get('page_count', 0)} pages"
        )
        return doc

    async def scrape_all_annual_reports(self) -> list[CompetitorDocument]:
        """Scrape annual reports for all competitors."""
        documents = []

        for competitor in self.ANNUAL_REPORT_URLS.keys():
            try:
                doc = await self.scrape_annual_report(competitor)
                if doc:
                    documents.append(doc)
            except Exception as e:
                logger.error(f"Error scraping annual report for {competitor}: {e}")

        return documents

    # =========================================================================
    # Technical Document Scraping
    # =========================================================================

    async def find_and_scrape_pdfs(
        self, page_url: str, competitor: str
    ) -> list[CompetitorDocument]:
        """
        Find PDF links on a page and scrape them.

        Args:
            page_url: Web page URL to scan for PDF links
            competitor: Competitor identifier

        Returns:
            List of CompetitorDocument objects for found PDFs
        """
        documents = []

        try:
            client = await self._get_client()
            response = await client.get(page_url)
            response.raise_for_status()

            # Find PDF links
            from bs4 import BeautifulSoup

            soup = BeautifulSoup(response.text, "lxml")

            pdf_links: list[str] = []
            for link in soup.find_all("a", href=True):
                href = str(link.get("href", ""))  # type: ignore[union-attr]
                if href.lower().endswith(".pdf"):
                    if href.startswith("/"):
                        href = urljoin(page_url, href)
                    pdf_links.append(href)

            # Deduplicate and limit
            pdf_links = list(dict.fromkeys(pdf_links))[:5]

            for pdf_url in pdf_links:
                result = await self.download_and_parse(pdf_url)

                if result.get("text") and not result.get("error"):
                    # Determine content type from URL/title
                    content_type = ContentType.TECHNICAL_SPEC.value
                    if "annual" in pdf_url.lower() or "report" in pdf_url.lower():
                        content_type = ContentType.ANNUAL_REPORT.value
                    elif "brochure" in pdf_url.lower() or "product" in pdf_url.lower():
                        content_type = ContentType.PRODUCT_PAGE.value

                    doc = CompetitorDocument(
                        id=self._generate_doc_id(pdf_url),
                        competitor=competitor,
                        content_type=content_type,
                        source_type=SourceType.PDF.value,
                        title=result.get("metadata", {}).get("title", "PDF Document")
                        or "PDF Document",
                        content=result["text"],
                        source_url=pdf_url,
                        scraped_at=datetime.now(timezone.utc),
                        metadata={
                            "page_count": result.get("page_count", 0),
                            "file_size": result.get("file_size", 0),
                            "scrape_method": "pdf_scraper",
                        },
                    )
                    documents.append(doc)

        except Exception as e:
            logger.error(f"Error finding PDFs on {page_url}: {e}")

        return documents

    # =========================================================================
    # Utilities
    # =========================================================================

    def _generate_doc_id(self, url: str) -> str:
        """Generate a deterministic document ID from URL."""
        url_hash = hashlib.md5(url.encode()).hexdigest()[:12]
        return f"pdf_{url_hash}"


# Singleton instance
_pdf_scraper: Optional[PDFScraper] = None


def get_pdf_scraper() -> PDFScraper:
    """Get or create the PDF scraper singleton."""
    global _pdf_scraper
    if _pdf_scraper is None:
        _pdf_scraper = PDFScraper()
    return _pdf_scraper
