import asyncio
import logging
from typing import List, Optional
import httpx
from models import SocialPost
from parser import parse_hn_json

logging.basicConfig(level=logging.INFO, format="[%(levelname)s] %(message)s")
logger = logging.getLogger("crawler.python")

DEFAULT_HEADERS = {
    "User-Agent": "SocialBenchmarkCrawler/1.0 (Educational Ingestion Lab)",
    "Accept": "application/json",
}


class SocialCrawlerPython:
    """
    High-throughput asynchronous web crawler powered by httpx and asyncio.
    Features connection pooling, semaphore-governed rate limiting, and defensive error handling.
    """

    def __init__(
        self,
        max_concurrency: int = 3,
        timeout: float = 15.0,
        headers: Optional[dict] = None,
    ) -> None:
        self.semaphore = asyncio.Semaphore(max_concurrency)
        client_headers = headers or DEFAULT_HEADERS
        limits = httpx.Limits(max_keepalive_connections=20, max_connections=50)
        self.client = httpx.AsyncClient(
            headers=client_headers,
            timeout=timeout,
            limits=limits,
            follow_redirects=True,
        )

    async def __aenter__(self) -> "SocialCrawlerPython":
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb) -> None:
        await self.close()

    async def close(self) -> None:
        """Gracefully release HTTP connection pool."""
        await self.client.aclose()

    async def fetch_page(self, url: str) -> str:
        """
        Fetches response body text with concurrency governed by an internal semaphore.
        """
        async with self.semaphore:
            response = await self.client.get(url)
            response.raise_for_status()
            return response.text

    async def crawl_topic(
        self,
        topic: str,
        max_pages: int = 3,
        hits_per_page: int = 50,
        delay_seconds: float = 0.1,
    ) -> List[SocialPost]:
        """
        Ingests social media submissions across paginated search results for a given topic.

        Args:
            topic: Keyword or tag to search for.
            max_pages: Total number of pages to retrieve.
            hits_per_page: Number of posts per page request.
            delay_seconds: Polite inter-request delay to honor API conventions.

        Returns:
            Aggregated list of SocialPost items.
        """
        aggregated_posts: List[SocialPost] = []

        for page in range(max_pages):
            url = f"https://hn.algolia.com/api/v1/search?query={topic}&hitsPerPage={hits_per_page}&page={page}"
            try:
                payload = await self.fetch_page(url)
                posts, total_pages = parse_hn_json(payload, category=topic)
                aggregated_posts.extend(posts)

                if page + 1 >= total_pages:
                    break

                if delay_seconds > 0:
                    await asyncio.sleep(delay_seconds)
            except httpx.HTTPStatusError as exc:
                logger.error("HTTP error on topic '%s' (page %d): %s", topic, page + 1, exc)
                break
            except Exception as exc:
                logger.error("Unexpected error on topic '%s' (page %d): %s", topic, page + 1, exc)
                break

        return aggregated_posts
