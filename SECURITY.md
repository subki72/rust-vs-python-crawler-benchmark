# Security Policy

## Supported Versions

| Version | Supported          |
| ------- | ------------------ |
| 1.0.x   | :white_check_mark: |
| < 1.0   | :x:                |

## Reporting a Vulnerability

If you discover a security vulnerability in this repository:

1. **Do NOT open a public GitHub issue** for undisclosed vulnerabilities.
2. Submit a private report via GitHub Security Advisories (`Security -> Advisories -> Report a vulnerability`).
3. Include affected file paths, line numbers, reproduction steps, and estimated severity.
4. Initial acknowledgement will be provided within **48 hours**.

## Security Controls

- **Secret Hygiene**: `.env`, `.env.*`, `*.pem`, and `*.key` files are excluded via `.gitignore`; `.env.example` provides non-sensitive templates only.
- **Input & Path Safety**: Pydantic v2 schemas enforce strict field bounds and block path traversal on JSONL dataset lookups.
- **API Hardening**: CORS allowlists (`ALLOWED_ORIGINS`), security response headers (`X-Content-Type-Options`, `X-Frame-Options`, `Content-Security-Policy`), sliding-window rate limiting, and sanitized global exception handling.
- **Automated Scanning**: Weekly Dependabot updates (major bumps ignored), Semgrep SAST (`p/python`), and Trivy container vulnerability scanning in CI.
- **Container Hardening**: Multi-stage non-root Docker builds running as UID `10001` (`appuser`).
