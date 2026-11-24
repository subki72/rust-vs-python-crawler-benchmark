"""Benchmark orchestration, telemetry, and comparison package."""

from src.benchmark.analyzer import (
    build_comparison_report,
    compute_comparison_summary,
    format_report_json,
    load_datasets,
    metrics_from_dataset,
    parse_jsonl_dataset,
)
from src.benchmark.config import (
    ALLOWED_ORIGINS,
    DEFAULT_CONCURRENCY,
    DEFAULT_PAGES,
    DEFAULT_TOPICS,
    LOG_LEVEL,
    REQUEST_TIMEOUT_SECONDS,
    BenchmarkSettings,
    configure_logging,
)
from src.benchmark.runner import (
    build_rust_release,
    configure_console_utf8,
    execute_benchmark,
    run_full_benchmark,
    sample_peak_memory,
)
from src.benchmark.schemas import (
    ComparisonReport,
    ComparisonRequest,
    ComparisonSummary,
    DatasetSnapshot,
    EngineMetrics,
    HealthResponse,
)

__version__ = "1.0.0"

__all__ = [
    "ALLOWED_ORIGINS",
    "DEFAULT_CONCURRENCY",
    "DEFAULT_PAGES",
    "DEFAULT_TOPICS",
    "LOG_LEVEL",
    "REQUEST_TIMEOUT_SECONDS",
    "BenchmarkSettings",
    "ComparisonReport",
    "ComparisonRequest",
    "ComparisonSummary",
    "DatasetSnapshot",
    "EngineMetrics",
    "HealthResponse",
    "__version__",
    "build_comparison_report",
    "build_rust_release",
    "compute_comparison_summary",
    "configure_console_utf8",
    "configure_logging",
    "execute_benchmark",
    "format_report_json",
    "load_datasets",
    "metrics_from_dataset",
    "parse_jsonl_dataset",
    "run_full_benchmark",
    "sample_peak_memory",
]
