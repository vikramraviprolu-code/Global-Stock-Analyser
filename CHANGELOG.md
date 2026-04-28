# Changelog

All notable changes to this project will be documented in this file.
Format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/) and the
project adheres to [SemVer](https://semver.org/).

## [0.8.0] - 2026-04-28

### Added — v2 Screener (first deliverable)

The app pivots from "analyze one stock" to "discover stocks". The Screener
is now the default landing page (was: marketing page → moved to `/welcome`).

**Provider abstraction** (`providers/`)
- `HistoricalPriceProvider` — Stooq CSV → yfinance fallback, with an
  in-memory TTL cache. Source name + URL bubbled up via `source_for()`.
- `FundamentalsProvider` — yfinance `.info` best-effort, deps coerced
  through `_to_float()` to handle string-typed numbers.
- `SymbolResolver` — wraps the existing `resolver.search()`.
- `MockProvider` — deterministic synthetic data labelled
  `freshness="mock"` and never silently mixed with real data.
- `UniverseService` — orchestrator: loads `universe_global.csv`, enriches
  rows in parallel, falls back to mock per-row only when both Stooq and
  yfinance return nothing.

**Calc layer** (`calc/`)
- `calc.indicators` — pure-math `simple_ma`, `rsi`, `roc`, `perf`,
  `fifty_two_week_*`, `compute_indicators` (no DataFrames in the public
  API → trivially unit-testable).
- `calc.scoring` — `value_score` (max 4), `momentum_score` (max 7),
  `quality_score` (max 4), `risk_score` (5 - penalties),
  `data_confidence_score`. Each `Score` carries reasons + warnings +
  `source_urls`. `score_all()` returns the full bundle.

**Screener engine** (`screener/`)
- Two-phase filter engine: cheap filters (sector / country / region /
  exchange — no network) run first, then enrichment, then expensive
  filters (price / mcap / P/E / RSI / perf / MA). Caps enrichment to 60
  per request to bound latency; emits warning if more candidates exist.
- 9 built-in presets covering value, momentum, trend-following,
  mega-caps, regional cuts (Indian banks, Japan industrials, European
  tech), oversold-bounce, dividend payers.

**Typed data models** (`models.py`)
- Python dataclasses 1:1 with the spec's TypeScript types. `SourcedValue`
  carries provenance (source, retrieved-at, freshness, confidence,
  warning) for every metric.

**Routes / templates**
- `/` (default) → Screener
- `/screener` → Screener (alias)
- `/sources` → Provider health page
- `/welcome` → former marketing landing
- `/app` → existing single-stock dashboard (unchanged)
- `templates/_nav.html` — shared v2 nav bar
- `templates/screener.html` + `static/screener.css` — sortable table,
  card view toggle, source-quality badges, value/momentum score bars,
  preset sidebar, custom filter builder
- `templates/sources.html` — provider summary

**API**
- `GET /api/screener/presets` — list of built-in presets
- `POST /api/screener/run` — `{preset}` or `{filters}` payload
- `GET /api/sources/health` — provider + universe stats

### Tests
- `tests/test_indicators.py` — 14 cases covering MA / RSI / ROC / perf /
  52-week / full bundle.
- `tests/test_scoring.py` — 9 cases for all five score functions and
  `score_all()`.
- `tests/test_screener_engine.py` — 9 cases using a `StubUniverse` so
  filter/preset logic is verified without network.

All 55 tests pass.

### Hardening
- Flask configured `allow_nan_values=False`; results recursively scrubbed
  via `_scrub_nan()` so NaN closes from Stooq holidays don't leak into
  JSON.
- `_filters_from_payload` validates filter `kind` against an allow-list
  and caps payload to 32 filters.

## [0.7.0] - 2026-04-27

### Security
- **LAN exposure removed.** Daemon now binds `127.0.0.1` instead of
  `0.0.0.0`. The hostname `Global-Stock-Analyser` resolves locally via
  `/etc/hosts`, so the URL still works for the user — but no other
  device on the Wi-Fi can reach the server. Closes a DoS vector where
  any LAN attacker could have hammered `/api/shutdown`.
- **CSRF defense on `/api/shutdown`.** Endpoint now requires both a
  loopback peer (`request.remote_addr` is 127.0.0.0/8 or ::1) AND an
  `Origin` / `Referer` header whose host is in `TRUSTED_HOSTS`. A
  malicious cross-origin site (or curl without proper headers) gets
  HTTP 403. Browser `beforeunload` beacons still work — they include
  `Origin` automatically.
- **Server header sanitised.** Replaces Werkzeug's
  `Werkzeug/X.Y Python/Z.Z` banner with `Server: EquityScope`,
  reducing fingerprinting surface for scanners.
- New tests cover CSRF block, untrusted-Origin block, server-header
  strip, and host-header allow-list.

### Notes
- The Werkzeug dev server still emits its own `Server` header before
  ours; production (gunicorn) doesn't, so the dual header is a dev-mode
  quirk only. Browsers use the last one (`EquityScope`).

## [0.6.7] - 2026-04-27

### Fixed
- **mkcert failed with `permission denied` on `rootCA-key.pem`.** A prior
  install ran mkcert under sudo, which wrote
  `~/Library/Application Support/mkcert/` as root. Subsequent user-level
  runs couldn't read the CA key. Installer now detects an orphaned
  root-owned CAROOT and removes it via a single admin prompt before
  running mkcert again as the user.

## [0.6.6] - 2026-04-27

### Fixed
- **`mkcert -install` failed under sudo** with
  `SecTrustSettingsSetTrustSettings: The authorization was denied since
  no user interaction was possible`. macOS blocks trust-store changes
  from non-interactive elevated processes (like osascript-with-admin).
- New install split: the user-level `Install-Browser-Mode.command`
  downloads mkcert and runs `mkcert -install` (login keychain) +
  `mkcert -cert-file ...` BEFORE asking for sudo. Cert files land in
  `/tmp/equityscope_certs_$$/`.
- The sudo-elevated `install_daemon.sh` now reads pre-issued certs from
  `USER_CERTS` env var; it no longer attempts mkcert-install itself.
- Falls back to `openssl` self-signed + System-keychain trust if mkcert
  certs aren't provided (e.g. download failed).
- `Uninstall-Browser-Mode.command` runs `mkcert -uninstall` as the user
  (correct context for login-keychain changes) before invoking sudo.

### Changed
- mkcert binary now caches in the project's own `bin/` (gitignored)
  rather than `/usr/local/.../bin/`, since it's needed in the user
  context, not the daemon's.

## [0.6.5] - 2026-04-27

### Added
- **mkcert integration** — installer now downloads the
  [mkcert](https://github.com/FiloSottile/mkcert) standalone binary and uses
  it to install a local Certificate Authority into the macOS System
  keychain, then issue a leaf cert signed by that CA. Result: browsers
  show a green padlock with no warnings, no bypass needed. mkcert binary
  is cached at `/usr/local/global-stock-analyser/bin/mkcert`.
- Falls back to `openssl` self-signed + `security add-trusted-cert` if
  the mkcert download fails (no network / GitHub down).
- Uninstaller now runs `mkcert -uninstall` to remove the local CA from
  the trust store before deleting the project tree.

### Why mkcert vs raw self-signed
- Self-signed certs added to System keychain trust still trip browser
  policy in many Chrome configurations. mkcert generates a real CA,
  which is the canonical way to get a trusted cert for a local
  hostname without a public DNS / ACME path.

## [0.6.4] - 2026-04-27

### Fixed
- **HSTS made cert errors unbypassable.** v0.4.0 added
  `Strict-Transport-Security: max-age=31536000` on TLS responses.
  Combined with a self-signed cert, Chrome refused any "Advanced →
  Proceed" path on `global-stock-analyser`, showing only the dead-end
  warning page. Removed HSTS — TLS still on, but the browser now
  accepts the trusted self-signed cert (or allows bypass).
- HSTS is anti-pattern for self-signed local hostnames; will not be
  re-added until the project supports a properly issued cert.

## [0.6.3] - 2026-04-27

### Fixed
- **Browser blocked URL with `NET::ERR_CERT_AUTHORITY_INVALID`.** Self-signed
  cert wasn't in the macOS trust store. Installer now runs:
  `security add-trusted-cert -d -r trustRoot -k /Library/Keychains/System.keychain`
  on the generated cert, so Chrome / Safari / Firefox accept it without
  warnings. Uninstaller removes it.
- New double-click helper `Trust-Certificate.command` for users who already
  installed but still see the warning — adds the existing cert to System
  trust without reinstalling the daemon.

## [0.6.2] - 2026-04-27

### Fixed
- **Daemon crashed with `ModuleNotFoundError: No module named 'flask'`.**
  The plist pointed at `/usr/bin/python3` (system Python), whose user-site
  packages aren't visible to root. Daemon entered a KeepAlive crashloop.
- The installer now creates a self-contained virtualenv at
  `/usr/local/global-stock-analyser/venv` and installs project deps inside
  it. The plist's `ProgramArguments[0]` is rewritten to that venv's
  `python`, so the daemon no longer depends on user-site packages or
  system Python upgrades.
- `chown -R root:wheel` on `/usr/local/global-stock-analyser` after rsync
  so the install dir is fully root-owned (previous partial runs had left
  user-owned dirs behind).
- rsync now `--exclude venv` and `--exclude certs` so reinstall preserves
  these between runs.

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
