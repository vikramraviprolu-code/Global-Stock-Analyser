# Security Policy

## Supported versions

Only the latest `main` branch receives security fixes. Pin a tagged release if you need stability.

## Reporting a vulnerability

**Please do not open a public issue for security problems.** Instead:

1. Email a detailed report to the repository owner via GitHub (use the "Report a vulnerability" tab on the Security page of this repo).
2. Include reproduction steps, affected version/commit, and suggested mitigation if known.
3. Allow up to 7 days for an initial response.

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
