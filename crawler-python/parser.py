"""Defensive JSON payload parser for Hacker News Algolia responses."""

import json
import logging
from typing import Any

from models import SocialPost

logger = logging.getLogger(__name__)


def _coerce_post(item: dict[str, Any], category: str) -> SocialPost:
    """Map a single raw Algolia hit dictionary into a validated :class:`SocialPost`."""
    return SocialPost(
        id=str(item.get("objectID", "")),
        title=item.get("title") or item.get("story_title") or "No Title",
        author=item.get("author") or "[anonymous]",
        score=int(item.get("points") or 0),
        num_comments=int(item.get("num_comments") or 0),
        url=item.get("url") or item.get("story_url") or "",
        created_utc=float(item.get("created_at_i") or 0.0),
        selftext=item.get("story_text") or None,
        category=category,
    )


def parse_hn_json(payload: str, category: str) -> tuple[list[SocialPost], int]:
    """Parse a Hacker News Algolia JSON payload into :class:`SocialPost` records.

    Args:
        payload: Raw JSON string from the Algolia search endpoint.
        category: Topic category assigned to each parsed post.

    Returns:
        Tuple of ``(posts, total_pages)``.

    Raises:
        ValueError: If ``payload`` is empty, malformed JSON, or misses expected structure.
    """
    if not payload or not payload.strip():
        raise ValueError("Empty JSON payload received from upstream endpoint.")

    try:
        data: Any = json.loads(payload)
    except json.JSONDecodeError as exc:
        raise ValueError(f"Failed to decode JSON payload: {exc}") from exc

    if not isinstance(data, dict):
        raise TypeError("Expected top-level JSON object in upstream response.")

    hits = data.get("hits", [])
    if not isinstance(hits, list):
        raise TypeError("Expected 'hits' field to be a JSON array.")

    total_pages = int(data.get("nbPages", 0) or 0)
    posts = [_coerce_post(item, category) for item in hits if isinstance(item, dict)]
    logger.debug("Parsed %d posts for category '%s' (nbPages=%d)", len(posts), category, total_pages)
    return posts, total_pages
