"""FastAPI telemetry and comparative benchmark REST service."""

from __future__ import annotations

import logging
import threading
import time
from collections import defaultdict, deque
from collections.abc import Awaitable, Callable
from datetime import UTC, datetime
from pathlib import Path

from fastapi import FastAPI, HTTPException, Request, Response, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from src.benchmark.analyzer import (
    build_comparison_report,
    load_datasets,
    metrics_from_dataset,
    parse_jsonl_dataset,
)
from src.benchmark.config import BenchmarkSettings, configure_logging
from src.benchmark.schemas import (
    ComparisonReport,
    ComparisonRequest,
    DatasetSnapshot,
    EngineMetrics,
    HealthResponse,
)

logger = logging.getLogger(__name__)

SERVICE_NAME = "rust-vs-python-crawler-benchmark-api"
SERVICE_VERSION = "1.0.0"

SECURITY_HEADERS: dict[str, str] = {
    "X-Content-Type-Options": "nosniff",
    "X-Frame-Options": "DENY",
    "Referrer-Policy": "strict-origin-when-cross-origin",
    "Content-Security-Policy": "default-src 'none'",
}


class SlidingWindowRateLimiter:
    """Thread-safe in-memory sliding-window rate limiter keyed by client IP."""

    def __init__(self, max_requests: int, window_seconds: int) -> None:
        if max_requests <= 0 or window_seconds <= 0:
            raise ValueError("Rate limiter bounds must be positive integers.")
        self._max_requests = max_requests
        self._window_seconds = window_seconds
        self._buckets: dict[str, deque[float]] = defaultdict(deque)
        self._lock = threading.Lock()

    def is_allowed(self, client_key: str, now: float | None = None) -> tuple[bool, int]:
        """Evaluate whether a request from ``client_key`` fits inside the rate window."""
        current = time.monotonic() if now is None else now
        cutoff = current - self._window_seconds

        with self._lock:
            bucket = self._buckets[client_key]
            while bucket and bucket[0] <= cutoff:
                bucket.popleft()
            if len(bucket) >= self._max_requests:
                retry_after = max(1, int(bucket[0] + self._window_seconds - current) + 1)
                return False, retry_after
            bucket.append(current)
            return True, 0


class ResultCache:
    """Thread-safe TTL cache invalidated when JSONL dataset file signatures change."""

    def __init__(self, ttl_seconds: float) -> None:
        self._ttl_seconds = ttl_seconds
        self._lock = threading.Lock()
        self._cached_at = 0.0
        self._cached_signature: tuple[tuple[str, int, int], ...] = ()
        self._cached_report: ComparisonReport | None = None

    @staticmethod
    def _directory_signature(data_dir: Path) -> tuple[tuple[str, int, int], ...]:
        if not data_dir.exists() or not data_dir.is_dir():
            return ()
        entries: list[tuple[str, int, int]] = []
        for item in sorted(data_dir.glob("*.jsonl")):
            stat = item.stat()
            entries.append((item.name, stat.st_mtime_ns, stat.st_size))
        return tuple(entries)

    def get_or_build(
        self,
        data_dir: Path,
        builder: Callable[[], ComparisonReport],
    ) -> tuple[ComparisonReport, bool]:
        """Return cached report when TTL and dataset signatures match, else rebuild."""
        if self._ttl_seconds <= 0:
            return builder(), False

        signature = self._directory_signature(data_dir)
        now = time.monotonic()
        with self._lock:
            valid_ttl = (now - self._cached_at) < self._ttl_seconds
            if self._cached_report is not None and valid_ttl and signature == self._cached_signature:
                return self._cached_report, True

        fresh = builder()
        with self._lock:
            self._cached_report = fresh
            self._cached_signature = signature
            self._cached_at = time.monotonic()
        return fresh, False


def _resolve_safe_data_file(data_dir: Path, filename: str) -> Path:
    """Resolve ``filename`` inside ``data_dir`` while preventing path traversal."""
    root = data_dir.resolve()
    candidate = (root / filename).resolve()
    if candidate.parent != root:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Dataset filename must reside directly in data_dir.",
        )
    if not candidate.exists():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Dataset '{filename}' not found.",
        )
    return candidate


def _build_snapshot_report(data_dir: Path) -> ComparisonReport:
    """Build a comparative report from persisted ``data/*.jsonl`` snapshots."""
    snapshots = load_datasets(data_dir, skip_invalid=True)
    by_name: dict[str, DatasetSnapshot] = {snap.filename: snap for snap in snapshots}
    py_snap = by_name.get("social_python.jsonl")
    rs_snap = by_name.get("social_rust.jsonl")
    py_metrics = metrics_from_dataset("Python", py_snap) if py_snap else None
    rs_metrics = metrics_from_dataset("Rust", rs_snap) if rs_snap else None
    return build_comparison_report(
        python_metrics=py_metrics,
        rust_metrics=rs_metrics,
        datasets=snapshots,
    )


def _resolve_engine_input(
    engine_name: str,
    inline_metrics: EngineMetrics | None,
    filename: str | None,
    data_dir: Path,
) -> EngineMetrics | None:
    """Resolve metrics either from inline payload or from a persisted JSONL dataset."""
    if inline_metrics is not None:
        return inline_metrics
    if filename is None:
        return None
    target_path = _resolve_safe_data_file(data_dir, filename)
    try:
        snapshot = parse_jsonl_dataset(target_path)
    except (ValueError, TypeError) as exc:
        raise HTTPException(
            status_code=422,
            detail=f"Invalid JSONL dataset '{filename}': {exc}",
        ) from exc
    return metrics_from_dataset(engine_name, snapshot)


def _register_middlewares(
    app: FastAPI,
    settings: BenchmarkSettings,
    limiter: SlidingWindowRateLimiter,
) -> None:
    """Attach CORS, rate-limiting, and security header middlewares."""
    app.add_middleware(
        CORSMiddleware,
        allow_origins=list(settings.allowed_origins),
        allow_credentials=False,
        allow_methods=["GET", "POST"],
        allow_headers=["Content-Type", "Authorization"],
    )

    @app.middleware("http")
    async def rate_limit_and_security_headers(
        request: Request,
        call_next: Callable[[Request], Awaitable[Response]],
    ) -> Response:
        client_ip = request.client.host if request.client else "unknown"
        allowed, retry_after = limiter.is_allowed(client_ip)
        if not allowed:
            logger.warning("Rate limit exceeded for client %s on %s", client_ip, request.url.path)
            return JSONResponse(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                content={"detail": "Rate limit exceeded. Retry later."},
                headers={"Retry-After": str(retry_after), **SECURITY_HEADERS},
            )

        response = await call_next(request)
        for header_name, header_value in SECURITY_HEADERS.items():
            response.headers.setdefault(header_name, header_value)
        return response


def _register_routes(
    app: FastAPI,
    settings: BenchmarkSettings,
    cache: ResultCache,
) -> None:
    """Register REST endpoints and the centralized exception boundary."""

    @app.exception_handler(Exception)
    async def global_exception_handler(request: Request, exc: Exception) -> JSONResponse:
        logger.exception("Unhandled error handling %s %s: %s", request.method, request.url.path, exc)
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={"detail": "Internal server error."},
            headers=SECURITY_HEADERS,
        )

    @app.get("/health", response_model=HealthResponse, tags=["health"])
    def health_check() -> HealthResponse:
        data_dir = settings.data_dir
        exists = data_dir.exists() and data_dir.is_dir()
        datasets = sorted(p.name for p in data_dir.glob("*.jsonl")) if exists else []
        return HealthResponse(
            status="ok" if exists else "degraded",
            service=SERVICE_NAME,
            version=SERVICE_VERSION,
            timestamp=datetime.now(UTC).isoformat(),
            data_dir_exists=exists,
            available_datasets=datasets,
        )

    @app.get("/api/v1/results", response_model=ComparisonReport, tags=["benchmark"])
    def get_benchmark_results(response: Response) -> ComparisonReport:
        report, cache_hit = cache.get_or_build(
            settings.data_dir,
            lambda: _build_snapshot_report(settings.data_dir),
        )
        response.headers["X-Cache"] = "HIT" if cache_hit else "MISS"
        logger.info(
            "Served /api/v1/results (datasets=%d, cache_hit=%s)",
            len(report.datasets),
            cache_hit,
        )
        return report

    @app.post("/api/v1/compare", response_model=ComparisonReport, tags=["benchmark"])
    def compare_engines(payload: ComparisonRequest) -> ComparisonReport:
        py_metrics = _resolve_engine_input(
            "Python", payload.python_metrics, payload.python_file, settings.data_dir
        )
        rs_metrics = _resolve_engine_input(
            "Rust", payload.rust_metrics, payload.rust_file, settings.data_dir
        )
        report = build_comparison_report(
            python_metrics=py_metrics,
            rust_metrics=rs_metrics,
            datasets=load_datasets(settings.data_dir, skip_invalid=True),
        )
        logger.info("Computed engine comparison (record_parity=%s)", report.summary.record_parity)
        return report


def create_app(settings: BenchmarkSettings | None = None) -> FastAPI:
    """Create and configure a hardened FastAPI benchmark telemetry application."""
    active_settings = settings or BenchmarkSettings.from_env()
    configure_logging(active_settings.log_level)

    app = FastAPI(
        title="Rust vs. Python Crawler Benchmark API",
        description="Telemetry, dataset inspection, and comparative benchmark reporting service.",
        version=SERVICE_VERSION,
    )
    limiter = SlidingWindowRateLimiter(
        max_requests=active_settings.rate_limit_requests,
        window_seconds=active_settings.rate_limit_window_seconds,
    )
    cache = ResultCache(ttl_seconds=active_settings.cache_ttl_seconds)

    _register_middlewares(app, active_settings, limiter)
    _register_routes(app, active_settings, cache)
    return app


app = create_app()
