"""Asynchronous HTTP crawler with bounded concurrency, explicit timeouts, and retries."""

import asyncio
import logging
from typing import Self
from urllib.parse import quote_plus

import httpx
from models import SocialPost
from parser import parse_hn_json

logger = logging.getLogger(__name__)

DEFAULT_HEADERS: dict[str, str] = {
    "User-Agent": "SocialBenchmarkCrawler/1.0 (Educational Ingestion Lab)",
    "Accept": "application/json",
}
RETRYABLE_STATUS_CODES: frozenset[int] = frozenset({429, 500, 502, 503, 504})
BASE_HN_SEARCH_URL = "https://hn.algolia.com/api/v1/search"


def _compute_backoff(attempt: int, base_backoff: float) -> float:
    """Calculate exponential retry delay for zero-indexed retry ``attempt``."""
    return base_backoff * (2**attempt)


class SocialCrawlerPython:
    """High-throughput asynchronous web crawler powered by ``httpx`` and ``asyncio``.

    Features connection pooling, semaphore-governed concurrency, explicit connect/read
    timeouts, and bounded exponential-backoff retries on transient upstream failures.
    """

    def __init__(
        self,
        max_concurrency: int = 3,
        timeout: float = 15.0,
        headers: dict[str, str] | None = None,
        max_retries: int = 3,
        backoff_seconds: float = 0.5,
        transport: httpx.AsyncBaseTransport | None = None,
    ) -> None:
        if max_concurrency < 1:
            raise ValueError("max_concurrency must be at least 1.")
        if timeout <= 0:
            raise ValueError("timeout must be strictly positive.")
        if max_retries < 0:
            raise ValueError("max_retries must be non-negative.")

        self.semaphore = asyncio.Semaphore(max_concurrency)
        self.max_retries = max_retries
        self.backoff_seconds = backoff_seconds
        client_headers = headers or DEFAULT_HEADERS
        limits = httpx.Limits(max_keepalive_connections=20, max_connections=50)
        client_timeout = httpx.Timeout(timeout, connect=min(timeout, 5.0))
        self.client = httpx.AsyncClient(
            headers=client_headers,
            timeout=client_timeout,
            limits=limits,
            follow_redirects=True,
            transport=transport,
        )

    async def __aenter__(self) -> Self:
        return self

    async def __aexit__(self, exc_type: object, exc_val: object, exc_tb: object) -> None:
        await self.close()

    async def close(self) -> None:
        """Gracefully release the underlying HTTP connection pool."""
        await self.client.aclose()

    async def _request_once(self, url: str) -> str:
        """Perform a single semaphore-guarded HTTP GET request."""
        async with self.semaphore:
            response = await self.client.get(url)
            response.raise_for_status()
            return response.text

    async def fetch_page(self, url: str) -> str:
        """Fetch response text with bounded exponential-backoff retries on transient errors.

        Args:
            url: Target HTTP endpoint URL.

        Returns:
            Raw response body string.

        Raises:
            httpx.HTTPError: When all retry attempts fail or a non-retryable 4xx occurs.
        """
        for attempt in range(self.max_retries + 1):
            try:
                return await self._request_once(url)
            except httpx.HTTPStatusError as exc:
                status = exc.response.status_code
                if status not in RETRYABLE_STATUS_CODES or attempt >= self.max_retries:
                    raise
                delay = _compute_backoff(attempt, self.backoff_seconds)
                logger.warning("Transient HTTP %d for %s; retrying in %.2fs", status, url, delay)
                await asyncio.sleep(delay)
            except (httpx.TimeoutException, httpx.TransportError) as exc:
                if attempt >= self.max_retries:
                    raise
                delay = _compute_backoff(attempt, self.backoff_seconds)
                logger.warning("Network error for %s (%s); retrying in %.2fs", url, exc, delay)
                await asyncio.sleep(delay)

        raise RuntimeError(f"Unreachable retry exhaustion state for {url}")

    async def crawl_topic(
        self,
        topic: str,
        max_pages: int = 3,
        hits_per_page: int = 50,
        delay_seconds: float = 0.1,
    ) -> list[SocialPost]:
        """Ingest social submissions across paginated search results for ``topic``.

        Args:
            topic: Keyword or tag to search for.
            max_pages: Maximum number of pages to retrieve.
            hits_per_page: Number of posts requested per page.
            delay_seconds: Polite inter-request pause between pages.

        Returns:
            Aggregated list of validated :class:`SocialPost` records.
        """
        if not topic.strip() or max_pages < 1:
            return []

        encoded_topic = quote_plus(topic.strip())
        aggregated_posts: list[SocialPost] = []

        for page in range(max_pages):
            url = (
                f"{BASE_HN_SEARCH_URL}?query={encoded_topic}"
                f"&hitsPerPage={hits_per_page}&page={page}"
            )
            try:
                payload = await self.fetch_page(url)
                posts, total_pages = parse_hn_json(payload, category=topic)
                aggregated_posts.extend(posts)
                if page + 1 >= total_pages:
                    break
                if delay_seconds > 0:
                    await asyncio.sleep(delay_seconds)
            except (httpx.HTTPError, TypeError, ValueError) as exc:
                logger.error("Failed crawling topic '%s' (page %d): %s", topic, page + 1, exc)
                break

        return aggregated_posts
