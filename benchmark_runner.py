"""Backward-compatible CLI entrypoint delegating to ``src.benchmark``."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

from src.benchmark.config import (
    DEFAULT_PAGES,
    DEFAULT_TOPICS,
    BenchmarkSettings,
    configure_logging,
)
from src.benchmark.runner import (
    execute_benchmark as _execute_benchmark,
)
from src.benchmark.runner import (
    run_full_benchmark,
    sample_peak_memory,
)

TOPICS = DEFAULT_TOPICS
PAGES = DEFAULT_PAGES

logger = logging.getLogger(__name__)


def execute_benchmark(
    name: str,
    command: list[str],
    working_dir: Path,
    output_file: Path | None = None,
) -> dict[str, Any]:
    """Execute a crawler subprocess and return serialized benchmark telemetry."""
    metrics = _execute_benchmark(
        name=name,
        command=command,
        working_dir=working_dir,
        output_file=output_file,
    )
    return metrics.model_dump()


def main() -> None:
    """Run the head-to-head Rust vs. Python benchmark suite from configuration."""
    settings = BenchmarkSettings.from_env()
    configure_logging(settings.log_level)
    root_dir = Path(__file__).resolve().parent
    logger.info(
        "Starting benchmark: topics=%s, pages=%d, concurrency=%d",
        settings.topics,
        settings.pages,
        settings.concurrency,
    )
    run_full_benchmark(root_dir=root_dir, settings=settings)


__all__ = [
    "PAGES",
    "TOPICS",
    "execute_benchmark",
    "main",
    "sample_peak_memory",
]


if __name__ == "__main__":
    main()
