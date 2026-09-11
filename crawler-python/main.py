import argparse
import asyncio
import os
import sys
import time
from pathlib import Path
from crawler import SocialCrawlerPython


def parse_arguments() -> argparse.Namespace:
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
    return parser.parse_args()


async def run() -> None:
    args = parse_arguments()
    topics = [t.strip() for t in args.topics.split(",") if t.strip()]

    print(f"[Python] Starting ingestion pipeline: topics={topics}, pages={args.pages} (50 posts/page)")
    start_time = time.perf_counter()

    all_posts = []
    async with SocialCrawlerPython(max_concurrency=args.concurrency) as crawler:
        for topic in topics:
            batch = await crawler.crawl_topic(topic=topic, max_pages=args.pages, hits_per_page=50)
            print(f"[Python] Finished topic '{topic}': ingested {len(batch)} posts")
            all_posts.extend(batch)

    elapsed = time.perf_counter() - start_time

    # Persist records as atomic JSON Lines
    output_path = Path(args.output).resolve()
    output_path.parent.mkdir(parents=True, exist_ok=True)

    with output_path.open("w", encoding="utf-8") as file_handle:
        for post in all_posts:
            file_handle.write(post.model_dump_json() + "\n")

    throughput = len(all_posts) / elapsed if elapsed > 0 else 0.0

    print("\n" + "-" * 50)
    print("[Python] Ingestion Summary")
    print("-" * 50)
    print(f"Total Posts Ingested : {len(all_posts)}")
    print(f"Elapsed Time         : {elapsed:.2f} seconds")
    print(f"Throughput           : {throughput:.2f} posts/second")
    print(f"Destination          : {output_path}")


if __name__ == "__main__":
    try:
        asyncio.run(run())
    except KeyboardInterrupt:
        print("\n[Python] Ingestion interrupted by user.")
        sys.exit(130)
