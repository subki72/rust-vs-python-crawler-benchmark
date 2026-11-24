"""Unit tests for the Python crawler parser and SocialPost Pydantic model."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest
from pydantic import ValidationError

CRAWLER_PYTHON_DIR = str(Path(__file__).resolve().parent.parent / "crawler-python")
if CRAWLER_PYTHON_DIR not in sys.path:
    sys.path.insert(0, CRAWLER_PYTHON_DIR)

from models import SocialPost  # noqa: E402
from parser import parse_hn_json  # noqa: E402


def test_parse_hn_json_happy_path_and_fallbacks() -> None:
    # Arrange
    payload = json.dumps(
        {
            "nbPages": 4,
            "hits": [
                {
                    "objectID": "101",
                    "title": "Rust 1.80 Released",
                    "author": "alice",
                    "points": 320,
                    "num_comments": 55,
                    "url": "https://example.org/rust",
                    "created_at_i": 1700000000,
                    "story_text": "Release notes",
                },
                {
                    "objectID": "102",
                    "story_title": "Ask HN: Async I/O",
                    "story_url": "https://news.ycombinator.com/item?id=102",
                    "author": None,
                    "points": None,
                    "num_comments": None,
                },
            ],
        }
    )

    # Act
    posts, nb_pages = parse_hn_json(payload, category="rust")

    # Assert
    assert nb_pages == 4
    assert len(posts) == 2
    assert posts[0].id == "101"
    assert posts[0].score == 320
    assert posts[0].selftext == "Release notes"
    assert posts[1].title == "Ask HN: Async I/O"
    assert posts[1].author == "[anonymous]"
    assert posts[1].score == 0
    assert posts[1].category == "rust"


def test_parse_hn_json_rejects_invalid_inputs() -> None:
    # Arrange & Act & Assert
    with pytest.raises(ValueError, match="Empty JSON payload"):
        parse_hn_json("   ", category="python")

    with pytest.raises(ValueError, match="Failed to decode JSON"):
        parse_hn_json("{bad-json", category="python")

    with pytest.raises(TypeError, match="top-level JSON object"):
        parse_hn_json("[1, 2]", category="python")

    with pytest.raises(TypeError, match="'hits' field"):
        parse_hn_json('{"hits": "invalid"}', category="python")


def test_social_post_model_is_frozen_and_ignores_extra() -> None:
    # Arrange
    post = SocialPost(id="1", title="Demo", category="ai", extra_field="ignored")  # type: ignore[call-arg]

    # Act & Assert
    assert post.id == "1"
    with pytest.raises(ValidationError):
        post.title = "Mutated"  # type: ignore[misc]
