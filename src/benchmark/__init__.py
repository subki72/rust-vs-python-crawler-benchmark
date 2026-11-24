"""Benchmark orchestration, telemetry, and comparison package."""

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
from src.benchmark.schemas import (
    ComparisonReport,
    ComparisonRequest,
    ComparisonSummary,
    EngineMetrics,
    HealthResponse,
)

__version__ = "1.0.0"

__all__ = [
    "ALLOWED_ORIGINS",
    "BenchmarkSettings",
    "ComparisonReport",
    "ComparisonRequest",
    "ComparisonSummary",
    "DEFAULT_CONCURRENCY",
    "DEFAULT_PAGES",
    "DEFAULT_TOPICS",
    "EngineMetrics",
    "HealthResponse",
    "LOG_LEVEL",
    "REQUEST_TIMEOUT_SECONDS",
    "__version__",
    "configure_logging",
]
