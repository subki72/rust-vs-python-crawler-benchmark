"""Unit tests for benchmark runner orchestration, RSS polling, and CLI wrapper."""

from __future__ import annotations

import logging
import subprocess
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock

import psutil
import pytest

import benchmark_runner
from src.benchmark.runner import (
    configure_console_utf8,
    execute_benchmark,
    sample_peak_memory,
)


def test_sample_peak_memory_aggregates_children_rss(monkeypatch: pytest.MonkeyPatch) -> None:
    # Arrange
    fake_proc = MagicMock(spec=subprocess.Popen)
    fake_proc.pid = 4242
    fake_proc.poll.side_effect = [None, None, 0]

    child = MagicMock()
    child.pid = 4243
    child.memory_info.return_value = SimpleNamespace(rss=5 * 1024 * 1024)

    parent = MagicMock()
    parent.memory_info.side_effect = [
        SimpleNamespace(rss=10 * 1024 * 1024),
        SimpleNamespace(rss=20 * 1024 * 1024),
    ]
    parent.children.return_value = [child]

    monkeypatch.setattr(psutil, "Process", lambda pid: parent)
    monkeypatch.setattr("src.benchmark.runner.time.sleep", lambda _: None)

    # Act
    peak_mb = sample_peak_memory(fake_proc, interval=0.01)

    # Assert
    assert peak_mb == pytest.approx(25.0)


def test_sample_peak_memory_rejects_non_positive_interval() -> None:
    # Arrange
    fake_proc = MagicMock(spec=subprocess.Popen)

    # Act & Assert
    with pytest.raises(ValueError, match="strictly positive"):
        sample_peak_memory(fake_proc, interval=0.0)


def test_sample_peak_memory_handles_missing_process_gracefully(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # Arrange
    fake_proc = MagicMock(spec=subprocess.Popen)
    fake_proc.pid = 999999

    def _raise_no_proc(_pid: int) -> None:
        raise psutil.NoSuchProcess(pid=999999)

    monkeypatch.setattr(psutil, "Process", _raise_no_proc)

    # Act
    peak_mb = sample_peak_memory(fake_proc, interval=0.01)

    # Assert
    assert peak_mb == 0.0


def test_execute_benchmark_collects_metrics_and_records(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    # Arrange
    working_dir = tmp_path / "crawler-python"
    data_dir = tmp_path / "data"
    working_dir.mkdir()
    data_dir.mkdir()
    output_file = data_dir / "social_python.jsonl"
    output_file.write_text('{"id":"1"}\n{"id":"2"}\n\n', encoding="utf-8")

    fake_proc = MagicMock()
    fake_proc.pid = 1001
    fake_proc.returncode = 0
    fake_proc.communicate.return_value = ("completed run", "")

    monkeypatch.setattr("src.benchmark.runner.subprocess.Popen", lambda *args, **kwargs: fake_proc)
    monkeypatch.setattr("src.benchmark.runner.sample_peak_memory", lambda proc, interval: 42.5)

    # Act
    metrics = execute_benchmark(
        name="Python",
        command=["python", "main.py"],
        working_dir=working_dir,
    )

    # Assert
    assert metrics.name == "Python"
    assert metrics.peak_ram_mb == 42.5
    assert metrics.total_records == 2
    assert metrics.return_code == 0


def test_execute_benchmark_rejects_empty_command(tmp_path: Path) -> None:
    # Arrange & Act & Assert
    with pytest.raises(ValueError, match="must not be empty"):
        execute_benchmark(name="Python", command=[], working_dir=tmp_path)


def test_backward_compatible_wrapper_returns_dict(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    # Arrange
    output_file = tmp_path / "custom.jsonl"
    output_file.write_text('{"id":"99"}\n', encoding="utf-8")
    fake_proc = MagicMock()
    fake_proc.pid = 2002
    fake_proc.returncode = 0
    fake_proc.communicate.return_value = ("ok", "")

    monkeypatch.setattr("src.benchmark.runner.subprocess.Popen", lambda *args, **kwargs: fake_proc)
    monkeypatch.setattr("src.benchmark.runner.sample_peak_memory", lambda proc, interval: 12.0)

    # Act
    result = benchmark_runner.execute_benchmark(
        name="Rust",
        command=["crawler-rust"],
        working_dir=tmp_path,
        output_file=output_file,
    )

    # Assert
    assert isinstance(result, dict)
    assert result["name"] == "Rust"
    assert result["total_records"] == 1
    assert result["peak_ram_mb"] == 12.0
    assert benchmark_runner.PAGES == 3
    assert "rust" in benchmark_runner.TOPICS


def test_configure_console_utf8_logs_error_without_raising(
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    # Arrange
    class BrokenStdout:
        def reconfigure(self, **_kwargs: object) -> None:
            raise OSError("broken pipe")

    monkeypatch.setattr("src.benchmark.runner.sys.platform", "win32")
    monkeypatch.setattr("src.benchmark.runner.sys.stdout", BrokenStdout())

    # Act
    with caplog.at_level(logging.DEBUG):
        configure_console_utf8()

    # Assert
    assert any("reconfigure stdout" in rec.message for rec in caplog.records)
