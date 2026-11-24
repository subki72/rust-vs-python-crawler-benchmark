# Changelog

All notable changes to this project are documented in this file.

The format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [1.0.0] - 2026-11-24

### Added
- Modular root benchmark package `src/benchmark/` (`config.py`, `schemas.py`, `runner.py`, `analyzer.py`, `api.py`).
- FastAPI telemetry and benchmark comparison API (`GET /health`, `GET /api/v1/results`, `POST /api/v1/compare`) with CORS allowlist, security response headers, sliding-window rate limiter, TTL snapshot caching, and centralized exception boundary.
- Environment configuration template (`.env.example`) and pinned dependency manifests (`requirements.txt`, `requirements-lock.txt`, `uv.lock`).
- Offline unit and API integration test suites in `tests/` (6 test modules) plus Rust unit tests in `crawler-rust/src/models.rs`, `crawler-rust/src/parser.rs`, and `crawler-rust/src/crawler.rs`.
- Multi-stage non-root `Dockerfile`, `docker-compose.yml`, `Makefile`, `.pre-commit-config.yaml`, `pyproject.toml`, `.flake8`, `crawler-rust/rustfmt.toml`, and `crawler-rust/clippy.toml`.
- GitHub Actions CI workflow (`.github/workflows/ci.yml`) covering Ruff/Flake8, Pytest with coverage, Rust fmt/clippy/test, Docker build, Semgrep SAST, and Trivy scanning, plus Dependabot automation (`.github/dependabot.yml`).
- Governance and operational documentation (`LICENSE`, `SECURITY.md`, `CONTRIBUTING.md`, `docs/RUNBOOK.md`).

### Changed
- Refactored `benchmark_runner.py` into a thin backward-compatible wrapper delegating to `src.benchmark`.
- Hardened `crawler-python/` with bounded exponential-backoff retries, explicit connect/read timeouts, URL query encoding, and leveled logging.
- Hardened `crawler-rust/` with modular CLI parsing, `try_new` error propagation, bounded retry backoff, and full `rustfmt`/`clippy` compliance.

### Fixed
- Excluded `.env`, `.env.*`, `*.pem`, `*.key`, and build artifacts in `.gitignore`.
- Eliminated swallowed exceptions (`except ...: pass`) in benchmark orchestration and RSS monitoring.
