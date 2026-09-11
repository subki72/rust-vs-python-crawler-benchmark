"""
Benchmark Orchestrator: Rust vs Python Social Ingestion Engine
Measures end-to-end execution latency, ingestion throughput, and peak memory utilization (RSS).
"""

import os
import subprocess
import sys
import time
from pathlib import Path
from typing import Any, Dict, List
import psutil

TOPICS = "rust,python,technology,ai,datascience"
PAGES = 3  # 3 pages * 50 posts = 150 posts/topic * 5 topics = 750 posts total


def sample_peak_memory(proc: subprocess.Popen, interval: float = 0.05) -> float:
    """
    Monitors a running subprocess and tracks its peak Resident Set Size (RSS) in Megabytes.
    Aggregates memory across child processes recursively.
    """
    peak_mb = 0.0
    try:
        process = psutil.Process(proc.pid)
        while proc.poll() is None:
            try:
                total_bytes = process.memory_info().rss
                for child in process.children(recursive=True):
                    total_bytes += child.memory_info().rss
                current_mb = total_bytes / (1024 * 1024)
                if current_mb > peak_mb:
                    peak_mb = current_mb
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                pass
            time.sleep(interval)
    except (psutil.NoSuchProcess, psutil.AccessDenied):
        pass
    return peak_mb


def execute_benchmark(name: str, command: List[str], working_dir: Path) -> Dict[str, Any]:
    """
    Executes a crawler subprocess, samples peak RAM, measures execution time, and counts output records.
    """
    print(f"\n{'=' * 20} Executing {name} Engine {'=' * 20}")
    start_time = time.perf_counter()

    proc = subprocess.Popen(
        command,
        cwd=str(working_dir),
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
    )

    peak_ram_mb = sample_peak_memory(proc)
    stdout, _ = proc.communicate()
    elapsed_sec = time.perf_counter() - start_time

    print(stdout)

    output_file = working_dir.parent / "data" / f"social_{name.lower()}.jsonl"
    total_records = 0
    if output_file.exists():
        with output_file.open("r", encoding="utf-8") as handle:
            total_records = sum(1 for line in handle if line.strip())

    throughput = total_records / elapsed_sec if elapsed_sec > 0 else 0.0

    return {
        "name": name,
        "elapsed_sec": elapsed_sec,
        "peak_ram_mb": peak_ram_mb,
        "total_records": total_records,
        "throughput": throughput,
    }


def main() -> None:
    try:
        if sys.platform == "win32":
            sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass

    root_dir = Path(__file__).resolve().parent
    python_dir = root_dir / "crawler-python"
    rust_dir = root_dir / "crawler-rust"

    print("\n" + "=" * 65)
    print("  HEAD-TO-HEAD BENCHMARK: RUST VS PYTHON DATA INGESTION")
    print("=" * 65)
    print(f"Target Source   : Hacker News Social Discussions (Algolia API)")
    print(f"Topic Categories: {TOPICS}")
    print(f"Pages per Topic : {PAGES} (50 posts/page)")
    print(f"Target Volume   : ~750 social posts")

    # 1. Compile Rust release binary
    print("\n[Build] Building optimized release binary for Rust...")
    subprocess.run(["cargo", "build", "--release"], cwd=str(rust_dir), check=True)
    binary_name = "crawler-rust.exe" if os.name == "nt" else "crawler-rust"
    rust_bin = rust_dir / "target" / "release" / binary_name

    # 2. Run Python Crawler Benchmark
    py_command = [
        sys.executable,
        "main.py",
        "--topics", TOPICS,
        "--pages", str(PAGES),
        "--output", str(root_dir / "data" / "social_python.jsonl"),
    ]
    py_metrics = execute_benchmark("Python", py_command, python_dir)

    # 3. Run Rust Crawler Benchmark
    rust_command = [
        str(rust_bin),
        "--topics", TOPICS,
        "--pages", str(PAGES),
        "--output", str(root_dir / "data" / "social_rust.jsonl"),
    ]
    rust_metrics = execute_benchmark("Rust", rust_command, rust_dir)

    # 4. Display Comparison Report
    print("\n" + "=" * 65)
    print("               FINAL BENCHMARK COMPARISON REPORT")
    print("=" * 65)
    print(f"{'Metric':<25} | {'Python':<15} | {'Rust':<15}")
    print("-" * 65)
    print(f"{'Total Posts Ingested':<25} | {py_metrics['total_records']:<15} | {rust_metrics['total_records']:<15}")
    print(f"{'Elapsed Time (sec)':<25} | {py_metrics['elapsed_sec']:<15.2f} | {rust_metrics['elapsed_sec']:<15.2f}")
    print(f"{'Throughput (posts/sec)':<25} | {py_metrics['throughput']:<15.2f} | {rust_metrics['throughput']:<15.2f}")
    print(f"{'Peak RAM (MB)':<25} | {py_metrics['peak_ram_mb']:<15.2f} | {rust_metrics['peak_ram_mb']:<15.2f}")
    print("=" * 65)

    if rust_metrics["peak_ram_mb"] > 0 and py_metrics["peak_ram_mb"] > 0:
        ram_ratio = py_metrics["peak_ram_mb"] / rust_metrics["peak_ram_mb"]
        print(f"[*] Memory Efficiency: Rust uses {ram_ratio:.1f}x less RAM than Python!")

    if py_metrics["elapsed_sec"] > 0 and rust_metrics["elapsed_sec"] > 0:
        speed_ratio = py_metrics["elapsed_sec"] / rust_metrics["elapsed_sec"]
        if speed_ratio > 1.0:
            print(f"[+] Throughput Speed  : Rust is {speed_ratio:.2f}x faster than Python!")


if __name__ == "__main__":
    main()
