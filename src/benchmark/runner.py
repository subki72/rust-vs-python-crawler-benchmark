"""Modular benchmark execution, subprocess RSS profiling, and reporting helpers."""

from __future__ import annotations

import logging
import os
import subprocess
import sys
import time
from pathlib import Path

import psutil

from src.benchmark.analyzer import build_comparison_report, load_datasets
from src.benchmark.config import BenchmarkSettings
from src.benchmark.schemas import ComparisonReport, EngineMetrics

logger = logging.getLogger(__name__)

DEFAULT_SAMPLE_INTERVAL_SECONDS = 0.05
BYTES_PER_MIB = 1024 * 1024


def configure_console_utf8() -> None:
    """Attempt to configure UTF-8 stdout encoding on Windows consoles safely."""
    if sys.platform != "win32":
        return
    reconfigure = getattr(sys.stdout, "reconfigure", None)
    if reconfigure is None:
        return
    try:
        reconfigure(encoding="utf-8")
    except (AttributeError, OSError, ValueError) as exc:
        logger.debug("Could not reconfigure stdout to UTF-8: %s", exc)


def _read_process_rss_bytes(process: psutil.Process) -> int:
    """Sum RSS memory in bytes for ``process`` and any recursive child processes."""
    total_bytes = int(process.memory_info().rss)
    for child in process.children(recursive=True):
        try:
            total_bytes += int(child.memory_info().rss)
        except (psutil.NoSuchProcess, psutil.AccessDenied) as exc:
            logger.debug("Skipping child process RSS read for pid %s: %s", child.pid, exc)
    return total_bytes


def sample_peak_memory(
    proc: subprocess.Popen[str],
    interval: float = DEFAULT_SAMPLE_INTERVAL_SECONDS,
) -> float:
    """Poll a running subprocess and track peak Resident Set Size (RSS) in megabytes.

    Args:
        proc: Active subprocess handle returned by ``subprocess.Popen``.
        interval: Polling sleep interval in seconds.

    Returns:
        Peak observed memory footprint in MiB.

    Raises:
        ValueError: If ``interval`` is not positive.
    """
    if interval <= 0:
        raise ValueError("Sample interval must be strictly positive.")

    peak_mb = 0.0
    try:
        process = psutil.Process(proc.pid)
        while proc.poll() is None:
            try:
                current_mb = _read_process_rss_bytes(process) / BYTES_PER_MIB
                peak_mb = max(peak_mb, current_mb)
            except (psutil.NoSuchProcess, psutil.AccessDenied) as exc:
                logger.debug("Process %s exited during RSS polling: %s", proc.pid, exc)
                break
            time.sleep(interval)
    except (psutil.NoSuchProcess, psutil.AccessDenied) as exc:
        logger.debug("Unable to attach psutil monitor to pid %s: %s", proc.pid, exc)
    return round(peak_mb, 4)


def _count_non_empty_lines(file_path: Path) -> int:
    """Count non-empty lines inside a persisted JSONL file."""
    if not file_path.exists():
        return 0
    with file_path.open("r", encoding="utf-8") as handle:
        return sum(1 for line in handle if line.strip())


def execute_benchmark(
    name: str,
    command: list[str],
    working_dir: Path,
    output_file: Path | None = None,
    sample_interval: float = DEFAULT_SAMPLE_INTERVAL_SECONDS,
) -> EngineMetrics:
    """Execute a crawler command, profile peak RSS, measure latency, and count records.

    Args:
        name: Human-readable engine name (e.g. ``Python``, ``Rust``).
        command: Subprocess argument vector.
        working_dir: Working directory where the command executes.
        output_file: Expected JSONL output artifact path.
        sample_interval: RSS sampling interval in seconds.

    Returns:
        Structured :class:`EngineMetrics` telemetry.

    Raises:
        ValueError: If ``command`` is empty or ``sample_interval`` is invalid.
    """
    if not command:
        raise ValueError("Benchmark command must not be empty.")

    logger.info("Executing %s engine in %s", name, working_dir)
    start_time = time.perf_counter()

    proc = subprocess.Popen(
        command,
        cwd=str(working_dir),
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
    )
    peak_ram_mb = sample_peak_memory(proc, interval=sample_interval)
    stdout, _ = proc.communicate()
    elapsed_sec = max(time.perf_counter() - start_time, 0.0)

    if stdout:
        logger.info("[%s output]\n%s", name, stdout.strip())

    resolved_output = output_file or (working_dir.parent / "data" / f"social_{name.lower()}.jsonl")
    total_records = _count_non_empty_lines(resolved_output)
    throughput = round(total_records / elapsed_sec, 4) if elapsed_sec > 0 else 0.0

    return EngineMetrics(
        name=name,
        elapsed_sec=round(elapsed_sec, 4),
        peak_ram_mb=peak_ram_mb,
        total_records=total_records,
        throughput=throughput,
        return_code=proc.returncode or 0,
    )


def build_rust_release(rust_dir: Path) -> Path:
    """Compile the Rust crawler in release mode and return the binary path."""
    logger.info("Building optimized release binary for Rust in %s", rust_dir)
    subprocess.run(["cargo", "build", "--release"], cwd=str(rust_dir), check=True)
    binary_name = "crawler-rust.exe" if os.name == "nt" else "crawler-rust"
    return rust_dir / "target" / "release" / binary_name


def log_comparison_report(report: ComparisonReport) -> None:
    """Emit a concise structured comparison summary via leveled logging."""
    py = report.python
    rs = report.rust
    if py is None or rs is None:
        logger.warning("Incomplete comparison report; skipping summary table.")
        return

    logger.info("=" * 65)
    logger.info("FINAL BENCHMARK COMPARISON REPORT")
    logger.info(
        "Records: Python=%d, Rust=%d (parity=%s)",
        py.total_records,
        rs.total_records,
        report.summary.record_parity,
    )
    logger.info(
        "Latency: Python=%.2fs, Rust=%.2fs | Speedup=%.2fx (%s)",
        py.elapsed_sec,
        rs.elapsed_sec,
        report.summary.throughput_speedup or 0.0,
        report.summary.faster_engine,
    )
    logger.info(
        "Peak RSS: Python=%.2fMB, Rust=%.2fMB | Efficiency=%.2fx (%s)",
        py.peak_ram_mb,
        rs.peak_ram_mb,
        report.summary.memory_efficiency_ratio or 0.0,
        report.summary.more_memory_efficient_engine,
    )
    logger.info("=" * 65)


def run_full_benchmark(root_dir: Path, settings: BenchmarkSettings) -> ComparisonReport:
    """Build Rust release binary and execute end-to-end Python vs. Rust benchmarks."""
    configure_console_utf8()
    data_dir = settings.data_dir if settings.data_dir.is_absolute() else root_dir / settings.data_dir
    python_dir = root_dir / "crawler-python"
    rust_dir = root_dir / "crawler-rust"

    rust_bin = build_rust_release(rust_dir)
    py_output = data_dir / "social_python.jsonl"
    rs_output = data_dir / "social_rust.jsonl"

    py_metrics = execute_benchmark(
        name="Python",
        command=[
            sys.executable,
            "main.py",
            "--topics",
            settings.topics,
            "--pages",
            str(settings.pages),
            "--concurrency",
            str(settings.concurrency),
            "--output",
            str(py_output),
        ],
        working_dir=python_dir,
        output_file=py_output,
    )
    rs_metrics = execute_benchmark(
        name="Rust",
        command=[
            str(rust_bin),
            "--topics",
            settings.topics,
            "--pages",
            str(settings.pages),
            "--concurrency",
            str(settings.concurrency),
            "--output",
            str(rs_output),
        ],
        working_dir=rust_dir,
        output_file=rs_output,
    )

    datasets = load_datasets(data_dir)
    report = build_comparison_report(
        python_metrics=py_metrics,
        rust_metrics=rs_metrics,
        datasets=datasets,
    )
    log_comparison_report(report)
    return report
