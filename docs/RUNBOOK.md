# Operational Runbook

## 1. Service Overview

This repository provides two complementary runtimes:
1. **Batch Benchmark CLI (`benchmark_runner.py` / `src/benchmark/runner.py`)**: Compiles `crawler-rust`, executes head-to-head Python and Rust crawling against Hacker News Algolia search, profiles peak RSS memory, and writes JSONL output artifacts to `data/`.
2. **Telemetry & Comparison API (`src/benchmark/api.py`)**: Serves liveness probes (`/health`), cached dataset analytics (`/api/v1/results`), and engine comparison (`/api/v1/compare`) over FastAPI/Uvicorn.

---

## 2. Health Checks & Verification

### API Liveness & Readiness
```bash
curl -f http://127.0.0.1:8000/health
```
Expected `status`:
- `"ok"`: `data/` directory is mounted and readable.
- `"degraded"`: `data/` directory is missing; mount or create `DATA_DIR` before serving dataset comparisons.

### Benchmark Results & Comparison
```bash
curl -s http://127.0.0.1:8000/api/v1/results
```
Verify `X-Cache: MISS` on first request and `X-Cache: HIT` on subsequent requests within `CACHE_TTL_SECONDS`.

---

## 3. Common Failure Scenarios & Remediation

| Symptom | Likely Cause | Diagnostic Action | Resolution |
|---|---|---|---|
| `HTTP 429 Too Many Requests` | Client exceeded `RATE_LIMIT_REQUESTS` within `RATE_LIMIT_WINDOW_SECONDS` | Inspect `Retry-After` response header and API warning logs | Throttle client polling or raise `RATE_LIMIT_REQUESTS` in `.env` |
| `GET /health` returns `"degraded"` | `DATA_DIR` path missing or unmounted in container | Check `DATA_DIR` env var and Docker volume mount | Ensure `./data:/app/data` is mounted or run `mkdir -p data` |
| Upstream `429` / `5xx` during crawl | Hacker News Algolia rate limit or transient outage | Review `crawler.python` / `crawler-rust` retry logs | Reduce `BENCHMARK_CONCURRENCY` (e.g. `2`) or increase `RETRY_BACKOFF_SECONDS` |
| `POST /api/v1/compare` returns `422` | Corrupted or non-object JSON line in `data/*.jsonl` | Inspect line number reported in error detail | Re-run crawler or remove truncated trailing line from dataset |
| `POST /api/v1/compare` returns `400` | Path traversal characters (`..`, `/`, `\`) in filename | Verify `python_file` / `rust_file` fields | Pass basename only (e.g. `social_python.jsonl`) |

---

## 4. Container & Release Operations

### Local Container Lifecycle
```bash
make docker-build
docker compose up -d
docker compose logs -f benchmark-api
docker compose down
```

### CI/CD Verification Parity
Before tagging a release (`git tag -a vX.Y.Z -m "Release vX.Y.Z"`):
1. `make lint` passes with exit code `0` (Ruff + Flake8 + Clippy).
2. `make test` and `make test-rust` pass `100%` offline.
3. `docker build` succeeds as non-root `appuser` (UID `10001`).
