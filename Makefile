.PHONY: install lint format test test-rust run run-benchmark docker-build clean

PYTHON ?= python

install:
	$(PYTHON) -m pip install -r requirements.txt

lint:
	$(PYTHON) -m ruff check benchmark_runner.py src crawler-python tests
	$(PYTHON) -m flake8 --max-line-length=120 benchmark_runner.py src crawler-python tests
	cargo fmt --manifest-path crawler-rust/Cargo.toml --all -- --check
	cargo clippy --manifest-path crawler-rust/Cargo.toml --all-targets -- -D warnings

format:
	$(PYTHON) -m ruff format benchmark_runner.py src crawler-python tests
	cargo fmt --manifest-path crawler-rust/Cargo.toml --all

test:
	$(PYTHON) -m pytest tests/ -v --cov=src --cov-report=term-missing

test-rust:
	cargo test --manifest-path crawler-rust/Cargo.toml

run:
	$(PYTHON) -m uvicorn src.benchmark.api:app --host 0.0.0.0 --port 8000 --reload

run-benchmark:
	$(PYTHON) benchmark_runner.py

docker-build:
	docker build -t rust-vs-python-crawler-benchmark:latest .

clean:
	$(PYTHON) -c "import pathlib, shutil; [shutil.rmtree(p, ignore_errors=True) for p in pathlib.Path('.').rglob('__pycache__')]"
	$(PYTHON) -c "import pathlib, shutil; [shutil.rmtree(p, ignore_errors=True) for p in ['.pytest_cache', '.ruff_cache', '.mypy_cache', 'dist', 'build', 'htmlcov'] if pathlib.Path(p).exists()]"
