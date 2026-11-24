"""Integration tests for the FastAPI benchmark telemetry and comparison service."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from src.benchmark.api import create_app
from src.benchmark.config import BenchmarkSettings


def _seed_datasets(data_dir: Path) -> None:
    """Create deterministic Python and Rust JSONL datasets in a temporary directory."""
    py_rows = [
        {"id": "1", "category": "rust", "score": 100},
        {"id": "2", "category": "python", "score": 50},
    ]
    rs_rows = [
        {"id": "1", "category": "rust", "score": 100},
        {"id": "2", "category": "python", "score": 50},
    ]
    (data_dir / "social_python.jsonl").write_text(
        "\n".join(json.dumps(r) for r in py_rows) + "\n",
        encoding="utf-8",
    )
    (data_dir / "social_rust.jsonl").write_text(
        "\n".join(json.dumps(r) for r in rs_rows) + "\n",
        encoding="utf-8",
    )


def test_health_endpoint_ok_and_degraded(tmp_path: Path) -> None:
    # Arrange
    _seed_datasets(tmp_path)
    app_ok = create_app(BenchmarkSettings(data_dir=tmp_path))
    client_ok = TestClient(app_ok)

    missing_dir = tmp_path / "missing"
    app_degraded = create_app(BenchmarkSettings(data_dir=missing_dir))
    client_degraded = TestClient(app_degraded)

    # Act
    res_ok = client_ok.get("/health")
    res_deg = client_degraded.get("/health")

    # Assert
    assert res_ok.status_code == 200
    assert res_ok.json()["status"] == "ok"
    assert res_ok.json()["available_datasets"] == ["social_python.jsonl", "social_rust.jsonl"]
    assert res_ok.headers["X-Content-Type-Options"] == "nosniff"
    assert res_ok.headers["X-Frame-Options"] == "DENY"

    assert res_deg.status_code == 200
    assert res_deg.json()["status"] == "degraded"


def test_results_endpoint_caches_snapshots_and_serves_cors(tmp_path: Path) -> None:
    # Arrange
    _seed_datasets(tmp_path)
    settings = BenchmarkSettings(
        data_dir=tmp_path,
        allowed_origins=("http://localhost:3000",),
        cache_ttl_seconds=30.0,
    )
    client = TestClient(create_app(settings))

    # Act
    first = client.get("/api/v1/results", headers={"Origin": "http://localhost:3000"})
    second = client.get("/api/v1/results")

    # Assert
    assert first.status_code == 200
    assert first.headers["X-Cache"] == "MISS"
    assert first.headers["access-control-allow-origin"] == "http://localhost:3000"
    assert first.json()["summary"]["record_parity"] is True

    assert second.status_code == 200
    assert second.headers["X-Cache"] == "HIT"


def test_compare_endpoint_inline_and_file_modes(tmp_path: Path) -> None:
    # Arrange
    _seed_datasets(tmp_path)
    (tmp_path / "broken.jsonl").write_text("{corrupt\n", encoding="utf-8")
    client = TestClient(create_app(BenchmarkSettings(data_dir=tmp_path)))

    # Act
    inline_res = client.post(
        "/api/v1/compare",
        json={
            "python_metrics": {
                "name": "Python",
                "elapsed_sec": 12.0,
                "peak_ram_mb": 60.0,
                "total_records": 750,
                "throughput": 62.5,
            },
            "rust_metrics": {
                "name": "Rust",
                "elapsed_sec": 6.0,
                "peak_ram_mb": 15.0,
                "total_records": 750,
                "throughput": 125.0,
            },
        },
    )
    file_res = client.post(
        "/api/v1/compare",
        json={"python_file": "social_python.jsonl", "rust_file": "social_rust.jsonl"},
    )
    missing_res = client.post("/api/v1/compare", json={"python_file": "nope.jsonl"})
    bad_file_res = client.post("/api/v1/compare", json={"python_file": "broken.jsonl"})

    # Assert
    assert inline_res.status_code == 200
    assert inline_res.json()["summary"]["memory_efficiency_ratio"] == 4.0
    assert inline_res.json()["summary"]["faster_engine"] == "rust"

    assert file_res.status_code == 200
    assert file_res.json()["summary"]["record_parity"] is True

    assert missing_res.status_code == 404
    assert bad_file_res.status_code == 422


def test_rate_limiter_blocks_excess_requests(tmp_path: Path) -> None:
    # Arrange
    _seed_datasets(tmp_path)
    settings = BenchmarkSettings(
        data_dir=tmp_path,
        rate_limit_requests=2,
        rate_limit_window_seconds=60,
    )
    client = TestClient(create_app(settings))

    # Act
    r1 = client.get("/health")
    r2 = client.get("/health")
    r3 = client.get("/health")

    # Assert
    assert r1.status_code == 200
    assert r2.status_code == 200
    assert r3.status_code == 429
    assert "Retry-After" in r3.headers


def test_global_exception_handler_masks_internal_errors(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    # Arrange
    _seed_datasets(tmp_path)
    app = create_app(BenchmarkSettings(data_dir=tmp_path, cache_ttl_seconds=0.0))

    def _boom(_data_dir: Path) -> list[object]:
        raise RuntimeError("sensitive internal stack message")

    monkeypatch.setattr("src.benchmark.api.load_datasets", _boom)
    client = TestClient(app, raise_server_exceptions=False)

    # Act
    res = client.get("/api/v1/results")

    # Assert
    assert res.status_code == 500
    assert res.json() == {"detail": "Internal server error."}
