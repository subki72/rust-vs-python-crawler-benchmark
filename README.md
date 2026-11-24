# Social Crawler & Ingestion Benchmark: Rust vs. Python

[![CI Pipeline](https://github.com/subki72/rust-vs-python-crawler-benchmark/actions/workflows/ci.yml/badge.svg)](https://github.com/subki72/rust-vs-python-crawler-benchmark/actions/workflows/ci.yml)
[![Python 3.11+](https://img.shields.io/badge/python-3.11%2B-blue.svg)](https://www.python.org/downloads/)
[![Rust 1.70+](https://img.shields.io/badge/rust-1.70%2B-orange.svg)](https://www.rust-lang.org/)
[![License: MIT](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)

An end-to-end polyglot data engineering benchmark and FastAPI telemetry service comparing **Rust** (`tokio` + `reqwest` + `serde`) and **Python** (`asyncio` + `httpx` + `Pydantic v2`) for concurrent social data crawling, schema validation, and JSON Lines persistence.

---

## Architecture Overview

```mermaid
flowchart TD
    subgraph Data_Source ["External Target"]
        API["Hacker News Public API (Algolia)\nhttps://hn.algolia.com/api/v1/search"]
    end

    subgraph Python_Engine ["Python Ingestion Engine"]
        P_CLI["CLI Entrypoint\n(crawler-python/main.py)"]
        P_HTTP["Async HTTP Client\n(httpx + Bounded Retries)"]
        P_MODEL["Validation & Serialization\n(Pydantic v2 SocialPost)"]
        P_OUT[("data/social_python.jsonl")]
        P_CLI --> P_HTTP --> API
        P_HTTP --> P_MODEL --> P_OUT
    end

    subgraph Rust_Engine ["Rust Ingestion Engine"]
        R_CLI["CLI Entrypoint\n(crawler-rust/src/main.rs)"]
        R_HTTP["Async HTTP Client\n(reqwest + tokio Semaphore)"]
        R_MODEL["Zero-copy Deserialization\n(serde_json + SocialPost)"]
        R_OUT[("data/social_rust.jsonl")]
        R_CLI --> R_HTTP --> API
        R_HTTP --> R_MODEL --> R_OUT
    end

    subgraph Orchestration_And_API ["Benchmark Orchestrator & Telemetry Service"]
        Runner["benchmark_runner.py -> src/benchmark/runner.py\n(Subprocess Lifecycle + psutil RSS Sampler)"]
        Analyzer["src/benchmark/analyzer.py\n(JSONL Parser & Comparison Ratios)"]
        API_SVC["src/benchmark/api.py\n(FastAPI /health, /api/v1/results, /api/v1/compare)"]
        Runner -.-> Python_Engine
        Runner -.-> Rust_Engine
        Analyzer --> API_SVC
        P_OUT --> Analyzer
        R_OUT --> Analyzer
    end
```

---

## Baseline Benchmark Results

Tested across **5 technical topics** (`rust`, `python`, `technology`, `ai`, `datascience`) with 3 paginated batches per topic (50 records/batch), yielding **750 social media submissions** in `data/social_python.jsonl` and `data/social_rust.jsonl`:

| Metric | Python Engine (`httpx` + `pydantic`) | Rust Engine (`reqwest` + `tokio` + `serde`) | Variance / Winner |
| :--- | :--- | :--- | :--- |
| **Total Ingested Records** | **750 posts** | **750 posts** | **100% Identical Parity** |
| **Elapsed Execution Time** | **12.73 seconds** | **12.38 seconds** | **Rust ~1.03x faster** |
| **Ingestion Throughput** | **58.89 posts/sec** | **60.59 posts/sec** | **Rust +1.70 posts/sec** |
| **Peak Memory Usage (RSS)** | **59.05 MB** | **13.30 MB** | **Rust is 4.4x more memory efficient** |

---

## Project Directory Structure

```text
rust-vs-python-crawler-benchmark/
├── .env.example                   # Environment configuration template
├── .flake8                        # Flake8 linting settings
├── .gitignore                     # Secret, cache, and build artifact exclusions
├── .pre-commit-config.yaml        # Local pre-commit validation hooks
├── CHANGELOG.md                   # Semantic release history
├── CONTRIBUTING.md                # Contributor standards and checklist
├── Dockerfile                     # Multi-stage non-root image (Rust + Python API)
├── LICENSE                        # MIT License
├── Makefile                       # Single-command lint, test, build, and run targets
├── README.md                      # Project documentation
├── SECURITY.md                    # Vulnerability reporting and security controls
├── benchmark_runner.py            # Backward-compatible CLI wrapper for src.benchmark
├── docker-compose.yml             # Local container stack definition
├── pyproject.toml                 # Project metadata, Ruff, and Pytest settings
├── requirements-lock.txt          # Locked Python dependency snapshot
├── requirements.txt               # Exact-pinned Python dependencies
├── uv.lock                        # Cross-platform uv dependency lockfile
├── crawler-python/                # Python asynchronous ingestion engine
├── crawler-rust/                  # Rust Tokio asynchronous ingestion engine
├── data/                          # Persisted JSONL ingestion datasets
├── docs/
│   └── RUNBOOK.md                 # Operations & incident response runbook
├── src/
│   └── benchmark/
│       ├── analyzer.py            # JSONL parser & comparative metrics calculator
│       ├── api.py                 # Hardened FastAPI telemetry & comparison service
│       ├── config.py              # Validated BenchmarkSettings & structured logging
│       ├── runner.py              # Subprocess execution & psutil peak RSS sampler
│       └── schemas.py             # Pydantic v2 contracts & traversal guards
└── tests/                         # Offline unit & FastAPI integration test suites
```

---

## Quickstart & Local Usage

### Prerequisites

- **Python**: `3.11+` (`pip` or `uv`)
- **Rust**: `1.70+` (`cargo`, `rustfmt`, `clippy`)
- **Docker** (optional, for containerized deployment)

### Setup & Verification via Makefile

```bash
# 1. Configure environment (optional overrides)
cp .env.example .env

# 2. Install Python dependencies
make install

# 3. Run Python and Rust linters
make lint

# 4. Run offline test suites (Python Pytest + Rust cargo test)
make test
make test-rust
```

### Run the Telemetry API Service

```bash
make run
# or via Docker Compose:
docker compose up --build
```

Available HTTP endpoints:
- `GET /health` — Readiness and liveness probe reporting dataset availability.
- `GET /api/v1/results` — Cached comparative report computed from `data/*.jsonl`.
- `POST /api/v1/compare` — Compare inline engine telemetry or persisted JSONL filenames.

### Run the Head-to-Head Crawler Benchmark

```bash
make run-benchmark
# or directly:
python benchmark_runner.py
```

---

## Data Contract & Governance

Both engines emit line-delimited JSON (`.jsonl`) conforming to the canonical `SocialPost` contract (`id`, `title`, `author`, `score`, `num_comments`, `url`, `created_utc`, `selftext`, `category`).
See [SECURITY.md](SECURITY.md) for vulnerability reporting, [CONTRIBUTING.md](CONTRIBUTING.md) for PR requirements, and [docs/RUNBOOK.md](docs/RUNBOOK.md) for operational diagnostics.
