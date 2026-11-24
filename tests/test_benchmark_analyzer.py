"""Unit tests for JSONL dataset analysis and comparative report computation."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from src.benchmark.analyzer import (
    build_comparison_report,
    compute_comparison_summary,
    format_report_json,
    load_datasets,
    metrics_from_dataset,
    parse_jsonl_dataset,
)
from src.benchmark.schemas import EngineMetrics


def test_parse_jsonl_dataset_aggregates_counts_and_scores(tmp_path: Path) -> None:
    # Arrange
    dataset_path = tmp_path / "sample.jsonl"
    rows = [
        {"id": "1", "category": "rust", "score": 100},
        {"id": "2", "category": "rust", "score": 50},
        {"id": "3", "category": "python", "score": 150},
    ]
    dataset_path.write_text("\n".join(json.dumps(r) for r in rows) + "\n", encoding="utf-8")

    # Act
    snapshot = parse_jsonl_dataset(dataset_path)

    # Assert
    assert snapshot.filename == "sample.jsonl"
    assert snapshot.record_count == 3
    assert snapshot.categories == {"rust": 2, "python": 1}
    assert snapshot.avg_score == 100.0


def test_parse_jsonl_dataset_handles_empty_and_errors(tmp_path: Path) -> None:
    # Arrange
    empty_file = tmp_path / "empty.jsonl"
    empty_file.write_text("\n\n", encoding="utf-8")

    malformed_file = tmp_path / "bad.jsonl"
    malformed_file.write_text("{not-valid-json\n", encoding="utf-8")

    non_object_file = tmp_path / "list.jsonl"
    non_object_file.write_text("[1, 2, 3]\n", encoding="utf-8")

    # Act & Assert
    empty_snap = parse_jsonl_dataset(empty_file)
    assert empty_snap.record_count == 0
    assert empty_snap.avg_score == 0.0

    with pytest.raises(FileNotFoundError):
        parse_jsonl_dataset(tmp_path / "missing.jsonl")

    with pytest.raises(ValueError, match="Malformed JSON"):
        parse_jsonl_dataset(malformed_file)

    with pytest.raises(TypeError, match="Expected JSON object"):
        parse_jsonl_dataset(non_object_file)


def test_load_datasets_scans_sorted_jsonl_files(tmp_path: Path) -> None:
    # Arrange
    (tmp_path / "b.jsonl").write_text('{"id":"2","category":"ai","score":10}\n', encoding="utf-8")
    (tmp_path / "a.jsonl").write_text('{"id":"1","category":"rust","score":20}\n', encoding="utf-8")
    (tmp_path / "ignore.txt").write_text("ignored", encoding="utf-8")

    # Act
    snapshots = load_datasets(tmp_path)

    # Assert
    assert [snap.filename for snap in snapshots] == ["a.jsonl", "b.jsonl"]
    assert load_datasets(tmp_path / "nonexistent") == []

    # Arrange: invalid dataset skipped only when skip_invalid=True
    (tmp_path / "c_broken.jsonl").write_text("{broken\n", encoding="utf-8")
    assert [snap.filename for snap in load_datasets(tmp_path, skip_invalid=True)] == ["a.jsonl", "b.jsonl"]
    with pytest.raises(ValueError, match="Malformed JSON"):
        load_datasets(tmp_path, skip_invalid=False)


def test_compute_comparison_summary_and_report_serialization(tmp_path: Path) -> None:
    # Arrange
    py = EngineMetrics(
        name="Python",
        elapsed_sec=12.0,
        peak_ram_mb=60.0,
        total_records=750,
        throughput=62.5,
    )
    rs = EngineMetrics(
        name="Rust",
        elapsed_sec=6.0,
        peak_ram_mb=15.0,
        total_records=750,
        throughput=125.0,
    )
    snap = parse_jsonl_dataset(_write_temp_jsonl(tmp_path / "social_rust.jsonl"))

    # Act
    summary = compute_comparison_summary(py, rs)
    report = build_comparison_report(python_metrics=py, rust_metrics=rs, datasets=[snap])
    rendered = json.loads(format_report_json(report))

    # Assert
    assert summary.memory_efficiency_ratio == 4.0
    assert summary.throughput_speedup == 2.0
    assert summary.record_parity is True
    assert summary.faster_engine == "rust"
    assert summary.more_memory_efficient_engine == "rust"
    assert rendered["summary"]["record_parity"] is True
    assert metrics_from_dataset("Rust", snap, elapsed_sec=2.0, peak_ram_mb=10.0).throughput == 0.5

    # Edge cases: python faster, tie, and missing engine
    py_fast = EngineMetrics(name="Python", elapsed_sec=2.0, peak_ram_mb=10.0, total_records=10, throughput=0.0)
    rs_slow = EngineMetrics(name="Rust", elapsed_sec=4.0, peak_ram_mb=20.0, total_records=10, throughput=0.0)
    py_win = compute_comparison_summary(py_fast, rs_slow)
    assert py_win.faster_engine == "python"
    assert py_win.more_memory_efficient_engine == "python"

    tie_summary = compute_comparison_summary(py_fast, py_fast)
    assert tie_summary.faster_engine == "tie"
    assert tie_summary.more_memory_efficient_engine == "tie"
    assert compute_comparison_summary(py_fast, None).faster_engine == "unknown"


def _write_temp_jsonl(path: Path) -> Path:
    path.write_text('{"id":"1","category":"rust","score":42}\n', encoding="utf-8")
    return path
