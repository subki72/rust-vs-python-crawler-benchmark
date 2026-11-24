"""Pydantic v2 contracts for benchmark telemetry, comparison payloads, and health responses."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator


class EngineMetrics(BaseModel):
    """Measured execution telemetry for a single crawler engine run."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    name: str = Field(min_length=1, max_length=64, description="Engine label (e.g. Python, Rust)")
    elapsed_sec: float = Field(ge=0.0, description="Total execution duration in seconds")
    peak_ram_mb: float = Field(ge=0.0, description="Peak Resident Set Size (RSS) in megabytes")
    total_records: int = Field(ge=0, description="Total validated records persisted to JSONL")
    throughput: float = Field(ge=0.0, description="Ingestion rate in records per second")
    return_code: int = Field(default=0, description="Subprocess exit status code")


class ComparisonRequest(BaseModel):
    """Request payload for comparing Python and Rust benchmark runs or JSONL artifacts."""

    model_config = ConfigDict(extra="forbid")

    python_metrics: EngineMetrics | None = Field(
        default=None,
        description="Inline telemetry metrics for the Python crawler",
    )
    rust_metrics: EngineMetrics | None = Field(
        default=None,
        description="Inline telemetry metrics for the Rust crawler",
    )
    python_file: str | None = Field(
        default=None,
        min_length=1,
        max_length=128,
        description="Relative JSONL filename inside data_dir for Python records",
    )
    rust_file: str | None = Field(
        default=None,
        min_length=1,
        max_length=128,
        description="Relative JSONL filename inside data_dir for Rust records",
    )

    @model_validator(mode="after")
    def validate_inputs(self) -> ComparisonRequest:
        """Ensure at least one comparison source (inline metrics or filenames) is provided."""
        has_inline = self.python_metrics is not None or self.rust_metrics is not None
        has_files = self.python_file is not None or self.rust_file is not None
        if not has_inline and not has_files:
            raise ValueError(
                "Provide inline metrics ('python_metrics'/'rust_metrics') or JSONL filenames."
            )
        for filename in (self.python_file, self.rust_file):
            if filename is not None and ("/" in filename or "\\" in filename or ".." in filename):
                raise ValueError("Filenames must be simple relative names without path traversal.")
        return self


class ComparisonSummary(BaseModel):
    """Derived comparative performance ratios between Python and Rust engines."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    memory_efficiency_ratio: float | None = Field(
        default=None,
        ge=0.0,
        description="Ratio of Python peak RAM to Rust peak RAM",
    )
    throughput_speedup: float | None = Field(
        default=None,
        ge=0.0,
        description="Ratio of Rust throughput (or inverse latency) vs Python",
    )
    record_parity: bool = Field(
        default=False,
        description="True when both engines produced an equal non-zero record count",
    )
    faster_engine: Literal["rust", "python", "tie", "unknown"] = Field(default="unknown")
    more_memory_efficient_engine: Literal["rust", "python", "tie", "unknown"] = Field(
        default="unknown"
    )


class DatasetSnapshot(BaseModel):
    """Summary of an ingested JSONL artifact stored on disk."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    filename: str = Field(min_length=1)
    record_count: int = Field(ge=0)
    size_bytes: int = Field(ge=0)
    categories: dict[str, int] = Field(default_factory=dict)
    avg_score: float = Field(ge=0.0)


class ComparisonReport(BaseModel):
    """Complete comparative benchmark report returned by CLI and API endpoints."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    generated_at: str = Field(description="ISO-8601 UTC generation timestamp")
    python: EngineMetrics | None = Field(default=None)
    rust: EngineMetrics | None = Field(default=None)
    summary: ComparisonSummary
    datasets: list[DatasetSnapshot] = Field(default_factory=list)


class HealthResponse(BaseModel):
    """Service liveness and readiness probe response."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    status: Literal["ok", "degraded"]
    service: str
    version: str
    timestamp: str
    data_dir_exists: bool
    available_datasets: list[str] = Field(default_factory=list)
