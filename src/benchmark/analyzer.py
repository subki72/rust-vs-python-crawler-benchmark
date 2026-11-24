"""Pure analyzer for ingested JSONL datasets and Rust vs. Python benchmark metrics."""

from __future__ import annotations

import json
import logging
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from src.benchmark.schemas import (
    ComparisonReport,
    ComparisonSummary,
    DatasetSnapshot,
    EngineMetrics,
)

logger = logging.getLogger(__name__)


def parse_jsonl_dataset(file_path: Path) -> DatasetSnapshot:
    """Stream-parse a JSONL dataset file into aggregate counts and category breakdowns.

    Args:
        file_path: Path to a ``.jsonl`` file containing serialized social posts.

    Returns:
        Aggregated :class:`DatasetSnapshot` metrics.

    Raises:
        FileNotFoundError: If ``file_path`` does not exist.
        ValueError: If any non-empty line contains invalid JSON or a non-object payload.
    """
    if not file_path.exists():
        raise FileNotFoundError(f"Dataset file not found: {file_path}")

    categories: dict[str, int] = {}
    record_count = 0
    score_sum = 0.0

    with file_path.open("r", encoding="utf-8") as handle:
        for line_num, raw_line in enumerate(handle, start=1):
            stripped = raw_line.strip()
            if not stripped:
                continue
            try:
                record: Any = json.loads(stripped)
            except json.JSONDecodeError as exc:
                raise ValueError(
                    f"Malformed JSON in '{file_path.name}' at line {line_num}: {exc}"
                ) from exc
            if not isinstance(record, dict):
                raise TypeError(
                    f"Expected JSON object in '{file_path.name}' at line {line_num}."
                )
            record_count += 1
            category = str(record.get("category") or "uncategorized")
            categories[category] = categories.get(category, 0) + 1
            score_sum += float(record.get("score") or 0.0)

    avg_score = round(score_sum / record_count, 2) if record_count > 0 else 0.0
    size_bytes = file_path.stat().st_size
    return DatasetSnapshot(
        filename=file_path.name,
        record_count=record_count,
        size_bytes=size_bytes,
        categories=categories,
        avg_score=avg_score,
    )


def load_datasets(data_dir: Path, *, skip_invalid: bool = False) -> list[DatasetSnapshot]:
    """Load all ``*.jsonl`` snapshots from ``data_dir`` sorted by filename."""
    if not data_dir.exists() or not data_dir.is_dir():
        return []
    snapshots: list[DatasetSnapshot] = []
    for file_path in sorted(data_dir.glob("*.jsonl")):
        try:
            snapshots.append(parse_jsonl_dataset(file_path))
        except (OSError, TypeError, ValueError) as exc:
            if not skip_invalid:
                raise
            logger.warning("Skipping invalid JSONL dataset '%s': %s", file_path.name, exc)
    return snapshots


def _resolve_speedup(
    python_metrics: EngineMetrics,
    rust_metrics: EngineMetrics,
) -> tuple[float | None, str]:
    """Compute throughput/latency speedup ratio and faster engine label."""
    if python_metrics.throughput > 0 and rust_metrics.throughput > 0:
        ratio = round(rust_metrics.throughput / python_metrics.throughput, 3)
    elif python_metrics.elapsed_sec > 0 and rust_metrics.elapsed_sec > 0:
        ratio = round(python_metrics.elapsed_sec / rust_metrics.elapsed_sec, 3)
    else:
        return None, "unknown"

    if ratio > 1.0:
        return ratio, "rust"
    if ratio < 1.0:
        return ratio, "python"
    return ratio, "tie"


def _resolve_memory_efficiency(
    python_metrics: EngineMetrics,
    rust_metrics: EngineMetrics,
) -> tuple[float | None, str]:
    """Compute Python-to-Rust peak RSS ratio and more memory-efficient engine."""
    if python_metrics.peak_ram_mb <= 0 or rust_metrics.peak_ram_mb <= 0:
        return None, "unknown"
    ratio = round(python_metrics.peak_ram_mb / rust_metrics.peak_ram_mb, 3)
    if ratio > 1.0:
        return ratio, "rust"
    if ratio < 1.0:
        return ratio, "python"
    return ratio, "tie"


def compute_comparison_summary(
    python_metrics: EngineMetrics | None,
    rust_metrics: EngineMetrics | None,
) -> ComparisonSummary:
    """Compare Python and Rust telemetry metrics into comparative ratios."""
    if python_metrics is None or rust_metrics is None:
        return ComparisonSummary()

    speedup, faster_engine = _resolve_speedup(python_metrics, rust_metrics)
    mem_ratio, mem_winner = _resolve_memory_efficiency(python_metrics, rust_metrics)
    record_parity = (
        python_metrics.total_records > 0
        and python_metrics.total_records == rust_metrics.total_records
    )

    return ComparisonSummary(
        memory_efficiency_ratio=mem_ratio,
        throughput_speedup=speedup,
        record_parity=record_parity,
        faster_engine=faster_engine,
        more_memory_efficient_engine=mem_winner,
    )


def metrics_from_dataset(
    engine_name: str,
    snapshot: DatasetSnapshot,
    elapsed_sec: float = 0.0,
    peak_ram_mb: float = 0.0,
) -> EngineMetrics:
    """Create an :class:`EngineMetrics` object derived from a persisted dataset snapshot."""
    throughput = round(snapshot.record_count / elapsed_sec, 4) if elapsed_sec > 0 else 0.0
    return EngineMetrics(
        name=engine_name,
        elapsed_sec=elapsed_sec,
        peak_ram_mb=peak_ram_mb,
        total_records=snapshot.record_count,
        throughput=throughput,
        return_code=0,
    )


def build_comparison_report(
    python_metrics: EngineMetrics | None = None,
    rust_metrics: EngineMetrics | None = None,
    datasets: list[DatasetSnapshot] | None = None,
) -> ComparisonReport:
    """Assemble a complete timestamped comparison report."""
    summary = compute_comparison_summary(python_metrics, rust_metrics)
    return ComparisonReport(
        generated_at=datetime.now(UTC).isoformat(),
        python=python_metrics,
        rust=rust_metrics,
        summary=summary,
        datasets=datasets or [],
    )


def format_report_json(report: ComparisonReport) -> str:
    """Serialize a :class:`ComparisonReport` to formatted JSON."""
    return report.model_dump_json(indent=2)
