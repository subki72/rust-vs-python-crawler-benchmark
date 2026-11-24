"""Offline unit tests for SocialCrawlerPython using mocked async HTTP transport."""

from __future__ import annotations

import asyncio
import json
import sys
from pathlib import Path

import httpx
import pytest

CRAWLER_PYTHON_DIR = str(Path(__file__).resolve().parent.parent / "crawler-python")
if CRAWLER_PYTHON_DIR not in sys.path:
    sys.path.insert(0, CRAWLER_PYTHON_DIR)

from crawler import SocialCrawlerPython  # noqa: E402


def test_crawler_constructor_rejects_invalid_parameters() -> None:
    # Arrange & Act & Assert
    with pytest.raises(ValueError, match="max_concurrency"):
        SocialCrawlerPython(max_concurrency=0)

    with pytest.raises(ValueError, match="timeout"):
        SocialCrawlerPython(timeout=0.0)

    with pytest.raises(ValueError, match="max_retries"):
        SocialCrawlerPython(max_retries=-1)


def test_fetch_page_retries_transient_503_and_succeeds() -> None:
    # Arrange
    attempts = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal attempts
        attempts += 1
        if attempts < 3:
            return httpx.Response(503, text="upstream busy", request=request)
        return httpx.Response(200, text='{"hits":[],"nbPages":0}', request=request)

    async def _run() -> str:
        transport = httpx.MockTransport(handler)
        async with SocialCrawlerPython(
            max_retries=3,
            backoff_seconds=0.0,
            transport=transport,
        ) as crawler:
            return await crawler.fetch_page("https://example.test/api")

    # Act
    body = asyncio.run(_run())

    # Assert
    assert attempts == 3
    assert '"nbPages":0' in body


def test_fetch_page_does_not_retry_permanent_404() -> None:
    # Arrange
    attempts = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal attempts
        attempts += 1
        return httpx.Response(404, text="not found", request=request)

    async def _run() -> None:
        transport = httpx.MockTransport(handler)
        async with SocialCrawlerPython(
            max_retries=3,
            backoff_seconds=0.0,
            transport=transport,
        ) as crawler:
            await crawler.fetch_page("https://example.test/missing")

    # Act & Assert
    with pytest.raises(httpx.HTTPStatusError):
        asyncio.run(_run())
    assert attempts == 1


def test_crawl_topic_paginates_and_stops_at_nb_pages() -> None:
    # Arrange
    requested_pages: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        page = request.url.params.get("page", "0")
        requested_pages.append(page)
        payload = {
            "nbPages": 2,
            "hits": [
                {
                    "objectID": f"id-{page}",
                    "title": f"Post page {page}",
                    "author": "tester",
                    "points": 10,
                    "num_comments": 2,
                }
            ],
        }
        return httpx.Response(200, text=json.dumps(payload), request=request)

    async def _run() -> list[object]:
        transport = httpx.MockTransport(handler)
        async with SocialCrawlerPython(
            max_retries=1,
            backoff_seconds=0.0,
            transport=transport,
        ) as crawler:
            empty = await crawler.crawl_topic("  ", max_pages=3)
            assert empty == []
            return await crawler.crawl_topic("rust lang", max_pages=5, delay_seconds=0.0)

    # Act
    posts = asyncio.run(_run())

    # Assert
    assert requested_pages == ["0", "1"]
    assert len(posts) == 2
    assert posts[0].category == "rust lang"


def test_crawl_topic_returns_partial_results_on_failure() -> None:
    # Arrange
    def handler(request: httpx.Request) -> httpx.Response:
        page = request.url.params.get("page", "0")
        if page == "0":
            payload = {"nbPages": 3, "hits": [{"objectID": "1", "title": "First"}]}
            return httpx.Response(200, text=json.dumps(payload), request=request)
        return httpx.Response(500, text="server error", request=request)

    async def _run() -> list[object]:
        transport = httpx.MockTransport(handler)
        async with SocialCrawlerPython(
            max_retries=0,
            backoff_seconds=0.0,
            transport=transport,
        ) as crawler:
            return await crawler.crawl_topic("python", max_pages=3, delay_seconds=0.0)

    # Act
    posts = asyncio.run(_run())

    # Assert
    assert len(posts) == 1
    assert posts[0].id == "1"
