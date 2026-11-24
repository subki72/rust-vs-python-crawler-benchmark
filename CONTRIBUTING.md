# Contributing Guide

Thank you for contributing to `rust-vs-python-crawler-benchmark`.

## Local Development Setup

1. Copy `.env.example` to `.env` if custom runtime overrides are required:
   ```bash
   cp .env.example .env
   ```
2. Install Python dependencies:
   ```bash
   make install
   ```
3. Verify the Rust toolchain (`rustc >= 1.70`, `cargo`):
   ```bash
   cargo build --manifest-path crawler-rust/Cargo.toml
   ```

## Coding & Quality Standards

- **Python 3.11+**: Enforce full type annotations, functions under 50 lines, shallow nesting (`< 3`), structured logging via `logging.getLogger(__name__)`, and zero swallowed exceptions.
- **Rust 1.70+**: Use `Result<T, E>` propagation with `?`, avoid `.unwrap()`/`.expect()` in production paths, add `///` doc comments on public items, and satisfy `cargo fmt` and `cargo clippy --all-targets -- -D warnings`.
- **Tests**: Add offline unit or API integration tests in `tests/` and Rust `#[cfg(test)]` tests for all new features or bug fixes.

## Verification Checklist Before Opening a Pull Request

Run all quality gates locally before committing:

```bash
make lint
make test
make test-rust
```

All commits should follow [Conventional Commits](https://www.conventionalcommits.org/) (`feat:`, `fix:`, `refactor:`, `test:`, `ci:`, `docs:`, `chore:`).
