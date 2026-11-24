"""CLI entrypoint for the Python asynchronous social data ingestion engine."""

import argparse
import asyncio
import logging
import sys
import time
from pathlib import Path

from crawler import SocialCrawlerPython
from models import SocialPost

logger = logging.getLogger("crawler.python.main")


def parse_arguments(argv: list[str] | None = None) -> argparse.Namespace:
    """Parse and validate CLI flags for the Python ingestion runner."""
    parser = argparse.ArgumentParser(
        description="High-throughput Async Social Data Ingestion Engine (Python)",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser.add_argument(
        "--topics",
        type=str,
        default="rust,python,technology,ai,datascience",
        help="Comma-delimited topic keywords to crawl",
    )
    parser.add_argument(
        "--pages",
        type=int,
        default=3,
        help="Number of paginated requests per topic (50 posts/page)",
    )
    parser.add_argument(
        "--output",
        type=str,
        default="../data/social_python.jsonl",
        help="Destination path for the output JSON Lines file",
    )
    parser.add_argument(
        "--concurrency",
        type=int,
        default=3,
        help="Maximum concurrent network requests",
    )
    args = parser.parse_args(argv)
    if args.pages < 1 or args.concurrency < 1:
        parser.error("--pages and --concurrency must be positive integers.")
    return args


def _configure_cli_logging() -> None:
    """Configure leveled logging emitting cleanly to standard output."""
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%Y-%m-%dT%H:%M:%S",
        stream=sys.stdout,
    )


def _write_jsonl(output_path: Path, posts: list[SocialPost]) -> Path:
    """Persist validated posts as line-delimited JSON."""
    resolved = output_path.resolve()
    resolved.parent.mkdir(parents=True, exist_ok=True)
    with resolved.open("w", encoding="utf-8") as file_handle:
        for post in posts:
            file_handle.write(post.model_dump_json() + "\n")
    return resolved


async def run(argv: list[str] | None = None) -> int:
    """Execute the asynchronous crawl pipeline and persist output records."""
    _configure_cli_logging()
    args = parse_arguments(argv)
    topics = [item.strip() for item in args.topics.split(",") if item.strip()]
    if not topics:
        logger.error("No valid topics provided.")
        return 1

    logger.info("[Python] Starting ingestion pipeline: topics=%s, pages=%d", topics, args.pages)
    start_time = time.perf_counter()

    all_posts: list[SocialPost] = []
    async with SocialCrawlerPython(max_concurrency=args.concurrency) as crawler:
        for topic in topics:
            batch = await crawler.crawl_topic(topic=topic, max_pages=args.pages, hits_per_page=50)
            logger.info("[Python] Finished topic '%s': ingested %d posts", topic, len(batch))
            all_posts.extend(batch)

    elapsed = max(time.perf_counter() - start_time, 0.0)
    resolved = _write_jsonl(Path(args.output), all_posts)
    throughput = len(all_posts) / elapsed if elapsed > 0 else 0.0

    logger.info(
        "[Python] Summary: posts=%d, elapsed=%.2fs, throughput=%.2f posts/sec, dest=%s",
        len(all_posts),
        elapsed,
        throughput,
        resolved,
    )
    return 0


if __name__ == "__main__":
    try:
        sys.exit(asyncio.run(run()))
    except KeyboardInterrupt:
        logger.warning("[Python] Ingestion interrupted by user.")
        sys.exit(130)
