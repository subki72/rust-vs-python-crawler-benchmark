# Stage 1: Build optimized Rust crawler binary
FROM rust:1-slim AS rust-builder

RUN apt-get update \
    && apt-get install -y --no-install-recommends pkg-config libssl-dev \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /build/crawler-rust
COPY crawler-rust/Cargo.toml crawler-rust/Cargo.lock ./
COPY crawler-rust/src ./src
RUN cargo build --release

# Stage 2: Build isolated Python dependency virtualenv
FROM python:3.11-slim AS python-builder

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /build
COPY requirements.txt ./
RUN python -m venv /opt/venv \
    && /opt/venv/bin/pip install --no-cache-dir --upgrade pip \
    && /opt/venv/bin/pip install --no-cache-dir -r requirements.txt

# Stage 3: Hardened non-root runtime serving FastAPI telemetry + crawlers
FROM python:3.11-slim AS runtime

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PATH="/opt/venv/bin:$PATH"

RUN apt-get update \
    && apt-get install -y --no-install-recommends ca-certificates libssl3 \
    && rm -rf /var/lib/apt/lists/* \
    && groupadd --gid 10001 appgroup \
    && useradd --uid 10001 --gid appgroup --shell /sbin/nologin --create-home appuser

WORKDIR /app

COPY --from=python-builder /opt/venv /opt/venv
COPY --from=rust-builder /build/crawler-rust/target/release/crawler-rust /usr/local/bin/crawler-rust
COPY --chown=appuser:appgroup src/ ./src/
COPY --chown=appuser:appgroup crawler-python/ ./crawler-python/
COPY --chown=appuser:appgroup benchmark_runner.py ./
COPY --chown=appuser:appgroup data/ ./data/

USER appuser

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD ["python", "-c", "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/health', timeout=3)"]

CMD ["uvicorn", "src.benchmark.api:app", "--host", "0.0.0.0", "--port", "8000"]
