import json
from typing import Any, Dict, List, Tuple
from models import SocialPost


def parse_hn_json(payload: str, category: str) -> Tuple[List[SocialPost], int]:
    """
    Parses Hacker News Algolia JSON response payload into strongly-typed SocialPost instances.

    Args:
        payload: Raw JSON string from the endpoint.
        category: The topic category mapped to this batch of posts.

    Returns:
        A tuple containing:
            - list of parsed SocialPost objects
            - total number of pages available for pagination (nbPages)
    """
    try:
        data: Dict[str, Any] = json.loads(payload)
    except json.JSONDecodeError as exc:
        raise ValueError(f"Failed to decode JSON payload: {exc}") from exc

    hits: List[Dict[str, Any]] = data.get("hits", [])
    total_pages: int = int(data.get("nbPages", 0))

    posts: List[SocialPost] = []
    for item in hits:
        post = SocialPost(
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
        posts.append(post)

    return posts, total_pages