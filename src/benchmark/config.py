"""Validated environment configuration and structured logging helpers."""

from __future__ import annotations

import logging
import os
from pathlib import Path
import sys
from typing import TextIO

from dotenv import load_dotenv
from pydantic import BaseModel, ConfigDict, Field, field_validator

DEFAULT_TOPICS = "rust,python,technology,ai,datascience"
DEFAULT_PAGES = 3
DEFAULT_CONCURRENCY = 3
REQUEST_TIMEOUT_SECONDS = 15.0
DEFAULT_MAX_RETRIES = 3
DEFAULT_RETRY_BACKOFF_SECONDS = 0.5
DATA_DIR = Path("data")
ALLOWED_ORIGINS: tuple[str, ...] = (
    "http://localhost:3000",
    "http://127.0.0.1:8000",
)
LOG_LEVEL = "INFO"
DEFAULT_RATE_LIMIT_REQUESTS = 60
DEFAULT_RATE_LIMIT_WINDOW_SECONDS = 60
DEFAULT_CACHE_TTL_SECONDS = 15.0

_VALID_LOG_LEVELS = {"DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"}


def _parse_origins(raw_value: str | None) -> tuple[str, ...]:
    """Parse a comma-separated CORS origins string into a clean tuple."""
    if not raw_value:
        return ALLOWED_ORIGINS
    origins = tuple(item.strip() for item in raw_value.split(",") if item.strip())
    return origins or ALLOWED_ORIGINS


class BenchmarkSettings(BaseModel):
    """Validated runtime settings for benchmark orchestration and the telemetry API."""

    model_config = ConfigDict(frozen=True)

    topics: str = Field(default=DEFAULT_TOPICS, min_length=1)
    pages: int = Field(default=DEFAULT_PAGES, ge=1, le=50)
    concurrency: int = Field(default=DEFAULT_CONCURRENCY, ge=1, le=32)
    request_timeout_seconds: float = Field(default=REQUEST_TIMEOUT_SECONDS, gt=0.0, le=120.0)
    max_retries: int = Field(default=DEFAULT_MAX_RETRIES, ge=0, le=10)
    retry_backoff_seconds: float = Field(default=DEFAULT_RETRY_BACKOFF_SECONDS, ge=0.0, le=30.0)
    data_dir: Path = Field(default=DATA_DIR)
    allowed_origins: tuple[str, ...] = Field(default=ALLOWED_ORIGINS)
    log_level: str = Field(default=LOG_LEVEL)
    rate_limit_requests: int = Field(default=DEFAULT_RATE_LIMIT_REQUESTS, ge=1, le=10000)
    rate_limit_window_seconds: int = Field(default=DEFAULT_RATE_LIMIT_WINDOW_SECONDS, ge=1, le=3600)
    cache_ttl_seconds: float = Field(default=DEFAULT_CACHE_TTL_SECONDS, ge=0.0, le=3600.0)

    @field_validator("log_level")
    @classmethod
    def validate_log_level(cls, value: str) -> str:
        """Normalize and validate standard Python logging level names."""
        normalized = value.strip().upper()
        if normalized not in _VALID_LOG_LEVELS:
            raise ValueError(f"Unsupported LOG_LEVEL '{value}'. Expected one of {sorted(_VALID_LOG_LEVELS)}.")
        return normalized

    @property
    def topic_list(self) -> list[str]:
        """Return parsed, non-empty topic keywords."""
        return [item.strip() for item in self.topics.split(",") if item.strip()]

    @classmethod
    def from_env(cls, env_file: Path | None = None) -> BenchmarkSettings:
        """Load settings from environment variables and an optional .env file."""
        if env_file is not None:
            load_dotenv(dotenv_path=env_file, override=False)
        else:
            load_dotenv(override=False)

        raw_data_dir = os.getenv("DATA_DIR", str(DATA_DIR)).strip() or str(DATA_DIR)
        return cls(
            topics=os.getenv("BENCHMARK_TOPICS", DEFAULT_TOPICS),
            pages=int(os.getenv("BENCHMARK_PAGES", str(DEFAULT_PAGES))),
            concurrency=int(os.getenv("BENCHMARK_CONCURRENCY", str(DEFAULT_CONCURRENCY))),
            request_timeout_seconds=float(
                os.getenv("REQUEST_TIMEOUT_SECONDS", str(REQUEST_TIMEOUT_SECONDS))
            ),
            max_retries=int(os.getenv("MAX_RETRIES", str(DEFAULT_MAX_RETRIES))),
            retry_backoff_seconds=float(
                os.getenv("RETRY_BACKOFF_SECONDS", str(DEFAULT_RETRY_BACKOFF_SECONDS))
            ),
            data_dir=Path(raw_data_dir),
            allowed_origins=_parse_origins(os.getenv("ALLOWED_ORIGINS")),
            log_level=os.getenv("LOG_LEVEL", LOG_LEVEL),
            rate_limit_requests=int(
                os.getenv("RATE_LIMIT_REQUESTS", str(DEFAULT_RATE_LIMIT_REQUESTS))
            ),
            rate_limit_window_seconds=int(
                os.getenv("RATE_LIMIT_WINDOW_SECONDS", str(DEFAULT_RATE_LIMIT_WINDOW_SECONDS))
            ),
            cache_ttl_seconds=float(
                os.getenv("CACHE_TTL_SECONDS", str(DEFAULT_CACHE_TTL_SECONDS))
            ),
        )


def configure_logging(level: str = LOG_LEVEL, stream: TextIO | None = None) -> logging.Logger:
    """Configure leveled structured logging without clobbering test capture handlers.

    Args:
        level: Target logging level name (e.g. ``INFO``, ``DEBUG``).
        stream: Optional output stream; defaults to ``sys.stdout``.

    Returns:
        Configured ``benchmark`` package logger.
    """
    normalized = level.strip().upper()
    if normalized not in _VALID_LOG_LEVELS:
        raise ValueError(f"Unsupported logging level: {level}")

    numeric_level = getattr(logging, normalized)
    logging.basicConfig(
        level=numeric_level,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%Y-%m-%dT%H:%M:%S",
        stream=stream or sys.stdout,
    )
    pkg_logger = logging.getLogger("benchmark")
    pkg_logger.setLevel(numeric_level)
    return pkg_logger
