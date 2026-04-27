# Changelog

All notable changes to this project will be documented in this file.
Format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/) and the
project adheres to [SemVer](https://semver.org/).

## [0.3.0] - 2026-04-27

### Security
- HTML-escape all user-data fields (`company`, `sector`, `industry`, `exchange`,
  `country`, signal/outlook labels) before injection into `innerHTML`. Defends
  against reflected XSS via third-party API fields.
- Replace JSON-in-HTML-attribute encoding for candidate listings with index-based
  lookups against module-scoped arrays (eliminates the attribute-escape vector).
- Strict regex validation on `/api/analyze` (ticker pattern) and `/api/search`
  (length + control-char filter).
- Sanitize all caller-provided listing metadata; fields that fail the safe-string
  regex are dropped and re-derived from suffix inference.
- Send hardening response headers on every request:
  `X-Content-Type-Options: nosniff`, `X-Frame-Options: DENY`,
  `Referrer-Policy: no-referrer`, `Permissions-Policy`, and a tight
  `Content-Security-Policy` on HTML routes (`frame-ancestors 'none'`).
- Suppress internal exception details on the API; log server-side instead.
- Sanitize the `?ticker=` URL parameter on the dashboard before auto-running.

### Container & runtime
- `Dockerfile` now creates an unprivileged `app` user and runs the container as
  non-root.
- Container CMD now uses `gunicorn` (2 workers, 4 threads, 60s timeout) with
  access + error logging.
- Added a `HEALTHCHECK` curl probe.

### Dependencies
- Pinned major version ranges in `requirements.txt` and `pyproject.toml`
  (flask `<4`, pandas `<3`, requests `<3`, yfinance `<0.3`).

### Documentation
- Added [SECURITY.md](SECURITY.md) detailing applied mitigations and reporting
  flow.

## [0.2.0] - 2026-04-26

### Added
- Global ticker resolver with disambiguation modal across 23+ exchanges.
- Region-aware filter thresholds (USA, India, UK, EU, Japan, HK, Korea, Taiwan,
  Singapore, Australia, China A-shares, Canada).
- Tiered peer matching (industry+country → industry+region → sector+country →
  sector+region → global industry → global sector).
- Local-currency price display with USD-normalized market cap and live FX rates.
- 175-ticker curated global universe (`data/universe_global.csv`).
- Marketing landing page at `/`; dashboard moved to `/app` with `?ticker=` deeplink.

### Changed
- yfinance fallback for OHLCV when Stooq CSV is gated.

## [0.1.0] - 2026-04-26

### Added
- Initial Flask app with value screen, momentum scan, cross-analysis, and
  Buy/Watch/Avoid recommendation for US tickers.
