# Changelog

All notable changes to this project will be documented in this file.
Format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/) and the
project adheres to [SemVer](https://semver.org/).

## [0.6.1] - 2026-04-27

### Fixed
- **iCloud TCC blocked daemon install.** macOS rejects elevated processes
  (osascript-with-admin / sudo) that read scripts from
  `~/Library/Mobile Documents/com~apple~CloudDocs/...`. Symptom:
  `Operation not permitted (126)` when double-clicking
  `Install-Browser-Mode.command`.
- New install flow:
  1. User-level `Install-Browser-Mode.command` rsyncs the project to
     `/tmp/equityscope_stage_$$/` (no privilege issue with iCloud).
  2. Copies `install_daemon.sh` to `/tmp` too.
  3. osascript runs the `/tmp` install script with admin rights.
  4. The install script copies the staged tree to
     `/usr/local/global-stock-analyser/` and bootstraps the LaunchDaemon
     pointing at that path — completely outside iCloud.
- Uninstaller mirrors the staging flow and also removes
  `/usr/local/global-stock-analyser`.

## [0.6.0] - 2026-04-27

### Added — Terminal-independent "browser-only" mode
- `Install-Browser-Mode.command` — double-click in Finder. macOS native
  password dialog (osascript), then installs a system LaunchDaemon that
  runs the HTTPS server on port 443 always-on. After install, opening
  https://Global-Stock-Analyser/Local in any browser just works — no
  Terminal, no relaunching.
- `Uninstall-Browser-Mode.command` — companion uninstaller; bootouts
  the daemon and removes the plist.
- `scripts/install_daemon.sh` — renders plist template, installs deps
  if missing, ensures /etc/hosts entry, generates cert, bootstraps
  LaunchDaemon, waits for HTTPS readiness.
- `scripts/uninstall_daemon.sh` — companion script.
- `scripts/com.equityscope.global.plist.template` — plist template with
  `__PYTHON__` and `__PROJECT_ROOT__` placeholders. Daemon runs with
  `AUTO_SHUTDOWN=0` (always-on); manual mode via `.command` keeps the
  idle-shutdown behaviour.

### Modes summary
- **Browser-only** (Install-Browser-Mode.command): always-on system daemon.
- **Manual** (Global-Stock-Analyser.command): on-demand, idle auto-exit.
- **Dev** (`python app.py` or `scripts/run_secure.sh`): same as manual.

## [0.5.0] - 2026-04-27

### Added
- **Browser-driven lifecycle.** Server starts on demand via the Finder
  launcher and shuts down when the last tab closes — no manual stop.
- `Global-Stock-Analyser.command` — double-click launcher that triggers
  a native macOS admin password dialog (osascript), starts the HTTPS
  server detached, waits for readiness, and opens the browser.
- `/api/heartbeat` endpoint — frontend pings every 10s while the page is
  open; server tracks last-activity timestamp.
- `/api/shutdown` endpoint — frontend fires `navigator.sendBeacon` on
  `beforeunload` for prompt graceful exit.
- Background idle watcher — exits the process if no request seen for
  `IDLE_TIMEOUT` seconds (default 45). Disable with `AUTO_SHUTDOWN=0`.

### Notes
- The launcher reuses an already-running server: clicking it a second
  time just opens the browser without re-prompting for sudo.
- If beacon delivery fails (network drop, force-quit), the idle watcher
  ensures the server still exits within the timeout.

## [0.4.0] - 2026-04-27

### Added
- **HTTPS support** — app now serves TLS when `SSL_CERT` and `SSL_KEY` env
  vars point to PEM files. HSTS header sent on TLS responses.
- **URL prefix mount** — `URL_PREFIX=/Local` env var mounts the entire app
  under that prefix via Werkzeug `DispatcherMiddleware`. All `url_for()`
  links and template-injected JS API base URLs respect the prefix.
- **Host-header allow-list** — `TRUSTED_HOSTS` env var rejects requests
  whose `Host` header isn't on the list (defense vs. Host-header injection
  / DNS rebinding).
- **`scripts/gen_cert.sh`** — generates self-signed TLS cert with SAN for
  `Global-Stock-Analyser`, `localhost`, and `127.0.0.1`.
- **`scripts/setup_hosts.sh`** — adds `127.0.0.1 Global-Stock-Analyser` to
  `/etc/hosts` (idempotent, sudo-aware).
- **`scripts/run_secure.sh`** — orchestrates cert/hosts checks then
  launches HTTPS on the configured port and prefix.
- README section documenting the secure launch flow.

### Changed
- Hardcoded `/api/...` and `/app` paths in templates now resolve via
  `url_for()` and `request.script_root` so prefix mounting works end-to-end.

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
