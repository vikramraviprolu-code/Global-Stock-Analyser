# Security Policy

## Supported versions

Only the latest `main` branch receives security fixes. Pin a tagged release if you need stability. Latest: **v0.17.0**.

## Reporting a vulnerability

**Please do not open a public issue for security problems.** Instead:

1. Email a detailed report to the repository owner via GitHub (use the "Report a vulnerability" tab on the Security page of this repo).
2. Include reproduction steps, affected version/commit, and suggested mitigation if known.
3. Allow up to 7 days for an initial response.

## Hardening applied in v0.13.0+

| Threat | Mitigation |
| --- | --- |
| **CSRF on cache-clear** | `POST /api/settings/clear-cache` requires loopback peer AND `Origin`/`Referer` whose host is in `TRUSTED_HOSTS`. Returns 403 otherwise. |
| **Single-source data risk** | `StooqYFinanceProvider.fetch()` runs both providers in parallel and cross-validates last close within 2%. When both succeed and agree, `verified_source_count = 2` and confidence is bumped to "high". A green ✓ surfaces in source badges across the UI. |

## Hardening applied in v0.7.0

| Threat | Mitigation |
| --- | --- |
| **LAN exposure / DoS via `/api/shutdown`** | Daemon now binds `127.0.0.1`, not `0.0.0.0`. The hostname resolves locally via `/etc/hosts`; no other device on the network can reach the server. |
| **Cross-site shutdown (CSRF)** | `/api/shutdown` requires loopback peer AND `Origin`/`Referer` whose host is in `TRUSTED_HOSTS`. Cross-origin POSTs return HTTP 403. |
| **Server fingerprinting** | `Server` header replaced with `EquityScope` (drops Werkzeug + Python version banner). |

## Hardening applied in v0.6.x

| Threat | Mitigation |
| --- | --- |
| **Self-signed cert warnings + bypass-able UX** | mkcert local CA installed into the user's login keychain; leaf cert signed by that CA. Browsers show a green padlock with no warnings and no "Advanced → Proceed" path. |
| **Plaintext HSTS pin trapping users** | HSTS removed (v0.6.4). Combined with a self-signed cert, HSTS produced a dead-end Chrome warning; with mkcert there's no warning, so HSTS isn't needed for local use. |
| **Daemon import-time secret leakage / crashloop** | Daemon now runs from a pinned virtualenv inside `/usr/local/global-stock-analyser/venv` rather than the system Python's user-site, isolating the runtime from user-mutable code paths. |
| **Idle resource consumption (manual mode)** | Heartbeat + `beforeunload` `sendBeacon` cause the manual-launch server to exit ~45 s after the last tab closes. Browser-only mode disables idle exit (LaunchDaemon's job). |
| **Privileged install reading iCloud Drive** | Installer stages project to `/tmp/equityscope_stage_*`, then runs the elevated step from `/tmp` — sidesteps macOS TCC restrictions on iCloud-resident scripts. |
| **Orphan trust dirs from prior installs** | Installer detects root-owned `~/Library/Application Support/mkcert` from earlier failed runs and removes it before re-running mkcert as the user. |

## Hardening applied in v0.4.0

| Threat | Mitigation |
| --- | --- |
| **Plaintext HTTP** | TLS via `SSL_CERT`/`SSL_KEY` env vars; HSTS header on TLS responses. |
| **Host-header injection / DNS rebinding** | `TRUSTED_HOSTS` allow-list rejects unknown `Host` headers (HTTP 400). |
| **Path collisions when reverse-proxied** | App mounts under `URL_PREFIX` via Werkzeug `DispatcherMiddleware`. |

## Hardening applied in v0.3.0

| Threat | Mitigation |
| --- | --- |
| **XSS via API-supplied fields** (yfinance company/sector/industry could carry HTML) | All values HTML-escaped through an `esc()` helper before injection into `innerHTML`. |
| **JSON-in-HTML attribute injection** | Eliminated. Candidate listings stored in module-scoped JS arrays; DOM elements reference them by index only. |
| **Untrusted URL query string** (`/app?ticker=...`) | Whitelist regex on client; same regex on server (`TICKER_RE`). |
| **Server-side input validation** | `/api/analyze` enforces strict ticker pattern. `/api/search` rejects oversize/control-char queries. All listing metadata (company/sector/industry/etc.) sanitized through a safe-string regex; failed fields fall back to suffix inference. |
| **Information disclosure on error** | Internal exception details no longer leaked to clients; logged server-side instead. |
| **Clickjacking** | `X-Frame-Options: DENY` + CSP `frame-ancestors 'none'`. |
| **MIME sniffing** | `X-Content-Type-Options: nosniff`. |
| **Content injection** | Strict Content-Security-Policy on HTML routes (default-src self, no remote scripts/styles, no framing). |
| **Referrer leak** | `Referrer-Policy: no-referrer`. |
| **Container running as root** | Dockerfile creates an unprivileged `app` user and switches before runtime. |
| **Dev server in production** | Container CMD now uses `gunicorn` with bounded workers/threads/timeout. |
| **Dependency drift** | Major versions pinned in `requirements.txt` and `pyproject.toml`. |

## Known limitations

- **No auth / rate limiting**. Intended for single-user local use. If you expose the app publicly, add a reverse proxy with rate limiting (nginx, Caddy, Cloudflare).
- **In-memory cache only**. State resets on restart. Not safe to share across users.
- **Third-party data**. yfinance and Stooq deliver data over HTTPS but we do not validate signatures. Display-only — never feed values directly into trading systems.

## Out of scope

- Vulnerabilities in upstream dependencies that we have already pinned to safe ranges.
- Issues caused by running with `debug=True` (the production path uses gunicorn).
- Self-XSS where the user pastes their own malicious payload into the search box.
