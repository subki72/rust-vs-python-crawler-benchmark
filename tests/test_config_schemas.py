"""Unit tests for configuration validation and Pydantic v2 telemetry schemas."""

from __future__ import annotations

import logging
from pathlib import Path

import pytest
from pydantic import ValidationError

from src.benchmark.config import (
    DEFAULT_CONCURRENCY,
    DEFAULT_PAGES,
    DEFAULT_TOPICS,
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


def test_settings_defaults_and_topic_list() -> None:
    # Arrange & Act
    settings = BenchmarkSettings()

    # Assert
    assert settings.topics == DEFAULT_TOPICS
    assert settings.pages == DEFAULT_PAGES
    assert settings.concurrency == DEFAULT_CONCURRENCY
    assert settings.topic_list == ["rust", "python", "technology", "ai", "datascience"]


def test_settings_from_env_overrides(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    # Arrange
    monkeypatch.setenv("BENCHMARK_TOPICS", "rust, go")
    monkeypatch.setenv("BENCHMARK_PAGES", "5")
    monkeypatch.setenv("BENCHMARK_CONCURRENCY", "4")
    monkeypatch.setenv("DATA_DIR", str(tmp_path))
    monkeypatch.setenv("LOG_LEVEL", "debug")
    monkeypatch.setenv("ALLOWED_ORIGINS", "https://example.org,http://localhost:5173")

    # Act
    settings = BenchmarkSettings.from_env(env_file=tmp_path / "missing.env")

    # Assert
    assert settings.topic_list == ["rust", "go"]
    assert settings.pages == 5
    assert settings.concurrency == 4
    assert settings.data_dir == tmp_path
    assert settings.log_level == "DEBUG"
    assert settings.allowed_origins == ("https://example.org", "http://localhost:5173")


def test_settings_rejects_invalid_log_level_and_bounds() -> None:
    # Arrange & Act & Assert
    with pytest.raises(ValidationError):
        BenchmarkSettings(log_level="VERBOSE")

    with pytest.raises(ValidationError):
        BenchmarkSettings(pages=0)


def test_configure_logging_valid_and_invalid() -> None:
    # Arrange & Act
    pkg_logger = configure_logging("WARNING")

    # Assert
    assert pkg_logger.level == logging.WARNING

    with pytest.raises(ValueError, match="Unsupported logging level"):
        configure_logging("TRACE")


def test_comparison_request_validation_and_traversal_guard() -> None:
    # Arrange
    metrics = EngineMetrics(
        name="Python",
        elapsed_sec=10.0,
        peak_ram_mb=50.0,
        total_records=100,
        throughput=10.0,
    )

    # Act
    valid = ComparisonRequest(python_metrics=metrics)

    # Assert
    assert valid.python_metrics == metrics

    with pytest.raises(ValidationError):
        ComparisonRequest()

    with pytest.raises(ValidationError):
        ComparisonRequest(python_file="../secrets.jsonl")


def test_health_and_report_schemas() -> None:
    # Arrange & Act
    health = HealthResponse(
        status="ok",
        service="benchmark-api",
        version="1.0.0",
        timestamp="2026-11-24T00:00:00+00:00",
        data_dir_exists=True,
        available_datasets=["social_python.jsonl"],
    )
    report = ComparisonReport(
        generated_at="2026-11-24T00:00:00+00:00",
        summary=ComparisonSummary(),
    )

    # Assert
    assert health.status == "ok"
    assert report.datasets == []
