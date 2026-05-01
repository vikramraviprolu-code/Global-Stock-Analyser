# EquityScope v2 — Global Stock Discovery & Analysis Platform

[![Python](https://img.shields.io/badge/python-3.9%2B-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/license-MIT-green.svg)](LICENSE)
[![Code style](https://img.shields.io/badge/code%20style-pep8-orange.svg)](https://peps.python.org/pep-0008/)
[![Tests](https://img.shields.io/badge/tests-134%20passing-brightgreen.svg)]()
[![Version](https://img.shields.io/badge/version-0.21.0-blue.svg)](CHANGELOG.md)

Free, no-API-key, open-source equity research platform. Discover stocks via a
filterable Screener, drill into a full 8-tab Stock Analysis page, manage local
Watchlists, run side-by-side Compares, monitor Events, audit Data Quality, and
get scenario-based Buy / Watch / Avoid recommendations across **23+ global
exchanges** in **14 currencies**.

> **Disclaimer.** Informational and educational use only. Not financial advice.
> Free-source market data may be delayed, incomplete, or unavailable. See
> [LICENSE](LICENSE) for details.

Inspired by TradingView, FINVIZ, Koyfin, Simply Wall St, and StockAnalysis.com
— but **free / no API keys / no scraping by default**.

---

## What's new in v0.21.0

**Polish + perf budget** — last PRD step.

- `static/format.js` — shared formatters (`Fmt.n / pct / mcap / vol /
  money / cls / flag / sourceBadge / scoreBar / sparkline / timeAgo /
  date`), eliminates ~500 lines of duplication across templates.
- `Server-Timing: app;dur=<ms>` header on every response so clients see
  server-side latency without instrumentation.
- `/favicon.ico` route serves inline SVG (no extra HTTP request).
- `prefers-reduced-motion: reduce` CSS guard disables animations when
  the OS requests reduced motion.
- New `PERFORMANCE.md` documenting every JS / CSS / API budget + cache
  TTLs + Server-Timing measurement workflow.

PRD Build Steps 1–13 are now complete.

## What's new in v0.20.0

**Risk profiler + GDPR + EU AI Act compliance + security hardening:**

- **`/risk-profile`** — 10-question self-assessment scored 0–100,
  bucketed Conservative → Aggressive. Persisted locally; tunes
  recommendation thresholds.
- **`/privacy`** — full GDPR + EU AI Act disclosure. Article 6 lawful
  basis, Articles 15–22 data subject rights, international transfers,
  voluntary AI Act Art. 50 transparency despite non-applicability.
- **Consent banner** — first-visit; Decline wipes every `equityscope.*`
  localStorage key (Art. 21 right to object).
- **Subresource Integrity** on the self-hosted Lightweight Charts vendor
  bundle (SHA-384 + `crossorigin="anonymous"`).
- **`/.well-known/security.txt`** (RFC 9116) for coordinated
  vulnerability disclosure.
- New SECURITY.md "Threat model" section.

## What's new in v0.19.0

**Education drawers** — every metric, score, chart element, and
workspace concept now has a "?" icon next to it. Click → slide-out
drawer with plain-English definition, exact formula, how-to-read-it
bullets, caveats / limitations, and a "Read more" link to
Wikipedia / Investopedia. 40+ topics covered. Pure rule-based content,
no LLM. Works on every page.

## What's new in v0.18.0

**News &amp; headline digest** (`/news`) — recent headlines per ticker via
yfinance `.news` (free, no key). Rule-based sentiment classification
(bullish / bearish / neutral via keyword counts) and topic clustering
(earnings / product / m&a / regulation / executive / macro). Two modes:
"My Watchlist" digest aggregates across all watchlist tickers, or query a
single ticker. Headlines are pure rule-based aggregation — explicitly
labelled as "auto-extracted, not AI" so users know the limit.

## What's new in v0.17.0

**Alerts** — browser-local rule engine with 11 condition kinds
(price ≥/≤, 5D move, RSI bands, MA crossovers, 52W extremes), auto-poll
(1–60 min), in-app toasts + opt-in desktop notifications, snooze /
reactivate / dismiss states, persistent trigger log. Zero server-side
state — alerts live in your browser only.

## What's new in v0.16.0

**Portfolio** — full holdings tracker. localStorage-backed, no login.
Multi-currency cost basis + live prices, P/L in both local and base
currencies, sortable holdings table, allocation breakdowns by Sector /
Country / Currency, CSV+JSON export, JSON import. Quick-add button on
the Stock Analysis page header.

New endpoints: `GET /api/fx?from=&to=` for single FX rate,
`POST /api/fx/batch` for up to 30 pairs in one round-trip.

## What's new in v0.15.0

UI Foundations — the app now matches the PRD's information architecture and
accessibility expectations:

- **Grouped navigation** — Research / Workspace / Market / System with
  active-group highlight. Mobile hamburger collapses groups under 720 px.
- **Reusable UI helpers** (`static/ui.js`) — `UI.tableSkeleton`,
  `UI.statGridSkeleton`, `UI.paragraphSkeleton`, `UI.cardGridSkeleton`,
  `UI.emptyState`, `UI.toast`. All carry `aria-busy` / `aria-live` per WCAG.
- **`fetchWithRetry`** — retry on 408/425/429/5xx + network errors;
  skips deterministic 4xx; exponential backoff; 12s default timeout
  (30s opt-in for AI/news per PRD). Wired across all 13 fetch call-sites.
- **A11y pass** — skip-link, `<main>` landmark, focus-visible rings,
  ARIA labels on icon-only controls.
- **Mobile 375 px audit** — every page renders cleanly at the smallest
  iPhone width.

Previous: see [CHANGELOG.md](CHANGELOG.md) for v0.14.0 multi-source
verification + watchlist sparklines.

Full version history: [CHANGELOG.md](CHANGELOG.md).

---

## Pages

| Page | URL | What it does |
| --- | --- | --- |
| Screener (default) | `/` | Sortable + filterable + card-toggle view of the full curated universe with 32 filter kinds, 12 built-in presets, custom presets, multi-select bulk actions, CSV/JSON export |
| Stock Analysis | `/app` | 8-tab deep-dive: Snapshot · Chart (candle/line, MA/RSI/ROC overlays, 1M–Max ranges) · Value · Momentum · Peers (matrix vs median + rank) · Events · Recommendation (Base/Upside/Downside/Trigger/Invalidation) · Sources |
| Watchlists | `/watchlists` | localStorage-backed lists with mini sparklines, sort by 8 dimensions, multi-select compare |
| Compare | `/compare` | 2–6 stocks side-by-side with full metric matrix + sparklines + relative highlights |
| Events | `/events` | Earnings / dividend / ex-dividend / split dates for your watchlist or custom tickers |
| Data Quality | `/data-quality` | Source-audit table over the live cache; freshness counts; CSV/JSON export |
| Sources | `/sources` | Provider health + universe stats |
| Settings | `/settings` | Default landing, sparkline range, compact mode, watchlist + preset management, server cache control, reset |

---

## Quick start

### Option A — One-click (recommended, macOS)

After cloning, double-click **`Install-Browser-Mode.command`** in Finder. It
will:

1. Download `mkcert` and install a local Certificate Authority into your login
   keychain (browsers trust it natively → green padlock).
2. Add `127.0.0.1 Global-Stock-Analyser` to `/etc/hosts`.
3. Mirror the project to `/usr/local/global-stock-analyser/` with a
   self-contained Python venv.
4. Install a macOS LaunchDaemon that runs the Flask server on port 443 with
   TLS, auto-starts at boot, and auto-restarts on crash.
5. Open https://Global-Stock-Analyser/Local in your browser.

From then on, just open https://Global-Stock-Analyser/Local from any browser —
no Terminal needed. To uninstall, double-click
`Uninstall-Browser-Mode.command`.

### Option B — Manual mode (server only when you want it)

Double-click **`Global-Stock-Analyser.command`**. Single password prompt,
server starts on demand, browser opens, **auto-shuts down ~45s after the last
tab closes** via heartbeat / `beforeunload` beacon.

### Option C — Dev mode (terminal-attached)

```bash
git clone https://github.com/vikramraviprolu-code/Global-Stock-Analyser.git
cd Global-Stock-Analyser
pip install -r requirements.txt
python app.py
```

Open http://127.0.0.1:5050.

### Option D — Docker

```bash
docker build -t global-stock-analyser .
docker run -p 5050:5050 global-stock-analyser
```

---

## Environment variables

All optional — sensible defaults baked in.

| Var | Default | Purpose |
| --- | --- | --- |
| `HOST` | `127.0.0.1` | Bind interface (LAN-exposed if changed to `0.0.0.0`) |
| `PORT` | `5050` | Bind port (use 443 + sudo for production) |
| `URL_PREFIX` | empty | Mount under prefix, e.g. `/Local`, via Werkzeug `DispatcherMiddleware` |
| `SSL_CERT` / `SSL_KEY` | unset | Path to PEM files; presence enables HTTPS |
| `TRUSTED_HOSTS` | `127.0.0.1,localhost,global-stock-analyser` | `Host`-header allow-list |
| `IDLE_TIMEOUT` | `45` | Seconds before idle auto-shutdown (manual mode) |
| `AUTO_SHUTDOWN` | `1` | Set `0` to disable idle exit (browser-only daemon mode) |

---

## Project layout

```
Global-Stock-Analyser/
├── app.py                          # Flask routes + endpoints
├── analyzer.py                     # Legacy v1 single-stock analyzer (kept for /api/analyze)
├── market_data.py                  # Legacy v1 OHLCV/fundamentals fetcher
├── markets.py                      # 23 exchange suffixes, regional filter thresholds, FX rates
├── resolver.py                     # Ticker / company-name search + disambiguation
├── models.py                       # SourcedValue, Security, StockMetrics, Score, StockScores
├── calc/
│   ├── indicators.py               # Pure-math RSI / MA / ROC / 52w / perf
│   ├── scoring.py                  # value/momentum/quality/risk/data-confidence (0–100, PRD weights)
│   └── recommendation.py           # Scenario engine: Base/Upside/Downside/Trigger/Invalidation
├── providers/
│   ├── historical.py               # StooqYFinanceProvider — parallel fetch + cross-validation
│   ├── fundamentals.py             # YFinanceFundamentals
│   ├── events.py                   # EventsProvider — earnings/dividend/split dates
│   ├── symbol.py                   # SymbolResolver
│   ├── universe.py                 # UniverseService — orchestrator
│   ├── mock.py                     # Synthetic fallback (clearly badged)
│   └── cache.py                    # Tiny TTL cache, thread-safe
├── screener/
│   ├── engine.py                   # Two-phase filter engine (cheap → enrich → expensive)
│   └── presets.py                  # 12 built-in presets incl. all 6 PRD-required
├── data/
│   └── universe_global.csv         # 175 curated tickers across 23 exchanges, 14 currencies
├── templates/                      # Jinja templates per page
│   ├── _nav.html                   # Shared top navigation
│   ├── screener.html
│   ├── index.html                  # Stock Analysis (8 tabs)
│   ├── watchlists.html
│   ├── compare.html
│   ├── events.html
│   ├── data_quality.html
│   ├── settings.html
│   ├── sources.html
│   └── landing.html                # Marketing landing (now at /welcome)
├── static/
│   ├── style.css                   # Base dark theme tokens
│   ├── screener.css                # Screener + shared components
│   ├── analysis.css                # 8-tab analysis + scenario + settings
│   ├── landing.css                 # Marketing landing
│   ├── watchlist.js                # localStorage helper (window.Watchlists)
│   └── vendor/
│       └── lightweight-charts.standalone.production.js   # 160 KB, self-hosted
├── scripts/
│   ├── install_daemon.sh           # Build LaunchDaemon (called via osascript)
│   ├── uninstall_daemon.sh
│   ├── gen_cert.sh                 # openssl fallback
│   ├── setup_hosts.sh              # /etc/hosts entry
│   └── run_secure.sh               # Manual-mode launcher
├── tests/                          # 134 tests, all passing
│   ├── test_smoke.py
│   ├── test_indicators.py
│   ├── test_scoring.py
│   ├── test_screener_engine.py
│   ├── test_analyze_v2.py
│   ├── test_recommendation.py
│   ├── test_events_and_dq.py
│   ├── test_settings.py
│   ├── test_cross_validation.py
│   ├── test_resolver_edges.py
│   └── test_watchlists_api.py
├── Global-Stock-Analyser.command   # Manual launcher
├── Install-Browser-Mode.command    # Always-on daemon installer
├── Uninstall-Browser-Mode.command
├── Trust-Certificate.command
├── Dockerfile
├── requirements.txt
├── pyproject.toml
├── CHANGELOG.md
├── CONTRIBUTING.md
├── SECURITY.md
└── LICENSE
```

---

## API reference

### `GET /api/search?q=<query>`

Resolve a ticker or company name to candidate listings.

### `GET /api/ohlcv?ticker=&days=`

Full OHLCV bars for the Stock Analysis chart panel. `days` clamped 20–2500.

### `GET /api/sparkline?ticker=&days=`

Closes-only series for compact mini charts. `days` clamped 20–750.

### `POST /api/analyze/v2`

```json
{ "ticker": "AAPL", "peer_tickers": ["MSFT", "NVDA"] }
```

Returns `{input, peers, peer_matrix, history_source, events, scenario}` —
fully populated v2 payload powering the 8-tab Stock Analysis page.

### `POST /api/metrics`

```json
{ "tickers": ["AAPL","MSFT"], "include_sparkline": true, "sparkline_days": 60 }
```

Batch enrichment up to 12 tickers — used by Watchlists + Compare.

### `POST /api/screener/run`

```json
{ "preset": "value_near_lows" }   // or { "filters": [{kind, value, label}, ...] }
```

Returns matches + scores + warnings. Optional `include_sparkline` for cards.

### `GET /api/screener/presets`

Lists the 12 built-in presets with descriptions and filter labels.

### `GET /api/events?ticker=` / `POST /api/events/calendar`

Earnings / dividend / ex-dividend / split dates from yfinance. Batch up to 30
tickers.

### `GET /api/data-quality/audit` / `GET /api/data-quality/stats`

Source-audit table + summary counts (fresh / stale / mock / missing).

### `GET /api/settings/server-info` / `POST /api/settings/clear-cache`

Server diagnostics. Cache-clear is loopback-only + Origin-allow-listed.

### `POST /api/heartbeat` / `POST /api/shutdown`

Browser-driven lifecycle. Heartbeat extends idle window; shutdown is
loopback + trusted-Origin only.

---

## Scoring model (0–100, PRD weights)

Every score appears with a labelled bar (Excellent ≥ 85, Good ≥ 65, Mixed ≥ 40,
Weak ≥ 20, Poor below). Click any score bar in any view to open a "Why this
score?" modal with reasons + warnings + source URLs.

**Value Score (0–100)** — `+20` P/E ≤ 10, `+15` P/E below peer median, `+20`
within 10% of 52W low, `+10` market cap ≥ regional threshold, `+10` dividend
yield > 2%, `-15` P/E unavailable.

**Momentum Score (0–100)** — `+15` 5D positive, `+15` ROC 14D positive, `+15`
ROC 21D positive, `+15` RSI 40–70, `+10` each above 20D / 50D / 200D MA,
`-15` RSI > 70, `-20` below 200D MA, `-15` ROC 14D + 21D both negative.

**Quality Score (0–100)** — `+35` mega-cap (≥ $50B), `+20` large-cap, `+20`
dividend payer, `+15` P/B ≤ 5, `+10` high liquidity, `+10` defensive sector,
`+10` price + fundamentals both resolved.

**Risk Score (0–100, higher = riskier)** — `+25` RSI overbought, `+25` below
200D MA, `+15` low liquidity, `+15` P/E unavailable, `+10` small cap, `+10`
stale data, `+10` near 52W high, `+10` ROC 14D + 21D both negative.

**Data Confidence Score (0–100)** — 60% coverage + 30% freshness + 10%
completeness bonus, minus 5 per mock-flagged metric.

---

## Scenario-based Recommendation

Every analysis returns a full scenario per PRD Build Step 7:

- **Base Case** — narrative anchored on price vs MAs + P/E zone
- **Upside Case** — natural targets (200D reclaim, 52W high re-test)
- **Downside Case** — failure points (50D loss, 200D break, 52W low fail)
- **Technical Trigger** — bullish / bearish / continuation / mixed
- **Invalidation Level** — closer of 200D MA / 52W low
- **Confidence Reason** — score-driven explanation
- **Final Rating** — Buy / Watch / Avoid
- **Time Horizon** — rating-aware (1–3 mo Buy, 2–6 wk Watch)
- **Catalysts** — pulled from EventsProvider when available

---

## Supported markets

| Region | Exchanges | Suffix |
| --- | --- | --- |
| USA | NYSE, Nasdaq, NYSE American | (none) |
| India | NSE, BSE | `.NS`, `.BO` |
| UK | London Stock Exchange | `.L` |
| Eurozone | Euronext (PA/AS/BR/LS), Xetra, Borsa Italiana, BME | `.PA`, `.AS`, `.DE`, `.MI`, `.MC` |
| Switzerland | SIX Swiss | `.SW` |
| Nordics | Nasdaq Stockholm/Helsinki/Copenhagen, Oslo Bors | `.ST`, `.HE`, `.CO`, `.OL` |
| Japan | Tokyo Stock Exchange | `.T` |
| Hong Kong | HKEX | `.HK` |
| South Korea | KOSPI, KOSDAQ | `.KS`, `.KQ` |
| Taiwan | TWSE, TPEx | `.TW`, `.TWO` |
| Singapore | SGX | `.SI` |
| Australia | ASX | `.AX` |
| China | Shanghai, Shenzhen | `.SS`, `.SZ` |
| Canada | TSX | `.TO` |

---

## Regional screening filters

| Country | Min price | Min volume | Min market cap (USD) |
| --- | ---: | ---: | ---: |
| USA | $5 | 500K | $2B |
| India | ₹100 | 500K | $2B |
| UK / EU | £/€/Fr 5 | 100K | $2B |
| Japan | ¥500 | 300K | $2B |
| Hong Kong | HK$5 | 500K | $2B |
| South Korea | ₩5,000 | 100K | $2B |
| Taiwan | NT$50 | 100K | $2B |
| Australia | A$2 | 100K | $2B |
| Singapore | S$1 | 100K | $1B |
| China A-shares | ¥5 | 500K | $2B |

ETFs, funds, warrants, and preferred shares are excluded by name keyword.

---

## Data sources

| Type | Source | Notes |
| --- | --- | --- |
| OHLCV history | **Stooq CSV + yfinance, parallel + cross-validated** | When both agree within 2%, `verified_source_count = 2` and confidence is bumped to "high" |
| Fundamentals | yfinance `.info` | Best effort — can be missing or rate-limited |
| Events | yfinance `.calendar` + `.actions` | Earnings, dividend, ex-dividend, split dates |
| FX rates | yfinance currency pairs | 6-hour cache for USD market-cap normalisation |
| Symbol resolver | Curated universe + yfinance `Search` | Disambiguation modal when ambiguous |
| Peer universe | `data/universe_global.csv` | 175 tickers across 23 exchanges, 14 currencies |
| Mock fallback | Synthetic, clearly badged `MOCK` | Engages only when both Stooq + yfinance return nothing |

All caching is in-memory: 30-min TTL for prices/fundamentals, 6-hour for FX,
4-hour for events. No persistence layer.

---

## Tests — 134 passing

Run with `pytest tests/ -q`.

| Suite | Cases | Coverage |
| --- | ---: | --- |
| `test_indicators.py` | 14 | MA, RSI, ROC, perf, 52w window, full bundle |
| `test_scoring.py` | 9 | All five 0–100 scores, mock penalty, partial-data |
| `test_screener_engine.py` | 17 | All filter kinds, presets, score-aware filters |
| `test_analyze_v2.py` | 11 | /api/ohlcv + /api/analyze/v2 shape + peer matrix |
| `test_recommendation.py` | 10 | Scenario shape, rating logic, trigger/invalidation phrasing |
| `test_events_and_dq.py` | 11 | EventsProvider, /api/events, /data-quality routes |
| `test_settings.py` | 7 | /settings render, server-info, clear-cache CSRF |
| `test_cross_validation.py` | 6 | Verified=2 on agreement, =1 on disagreement, cache hit |
| `test_resolver_edges.py` | 12 | Empty/whitespace, lowercase, ambiguous, special chars |
| `test_watchlists_api.py` | 10 | /api/metrics validation + /api/sparkline |
| `test_smoke.py` | 27 | CSRF, security headers, host-header guard, ticker parsing |

---

## Security

See [SECURITY.md](SECURITY.md). Highlights from v0.7.0+:

- TLS via mkcert local CA → green padlock, no warnings
- Bind `127.0.0.1` (not LAN) — daemon plist + manual mode default
- CSRF defense on `/api/shutdown` + `/api/settings/clear-cache`: loopback peer
  + trusted-Origin allow-list, returns 403 otherwise
- Host-header allow-list rejects unknown hosts (HTTP 400)
- Strict CSP, X-Frame-Options DENY, X-Content-Type-Options nosniff,
  no-referrer, restrictive Permissions-Policy
- Server header replaced with `EquityScope` (drops Werkzeug + Python banner)
- Strict JSON (`allow_nan_values=False`) + recursive NaN/Inf scrub on the
  boundary so Stooq holiday gaps never leak invalid JSON

---

## Known limitations

- **Stooq CSV gating** — Stooq now requires an API key for many tickers.
  yfinance fallback handles the gap; cross-validation only fires when Stooq
  succeeds.
- **yfinance rate limits** — heavy concurrent fetches may hit Yahoo throttling.
  Cache helps; consider a `requests-cache` layer for production.
- **Universe is curated, not exhaustive** — peer matching is bounded by the
  ~175 tickers in `data/universe_global.csv`. Extend via PR.
- **No real-time data** — all prices are end-of-day from free sources.
- **Investor-day events** — no free public source exists; field omitted.
- **No multi-source for fundamentals** — only yfinance currently. Adding a
  second free source (e.g. Wikipedia / Wikidata for sector metadata) would
  bring `verified_source_count = 2` to non-price fields.

---

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md). Common improvement paths:

1. **Extend the universe** — add tickers to `data/universe_global.csv`
2. **Add an indicator** — extend `calc/indicators.py`
3. **Add a market** — extend `markets.py` `SUFFIX_MAP` + `REGIONAL_FILTERS`
4. **Add a screener filter** — extend `screener/engine.py` `Filter` kinds + UI
5. **Add a free data source** — implement a provider in `providers/` and wire
   into `UniverseService`

---

## License

[MIT](LICENSE). See license file for full text including financial-advice disclaimer.

---

## Acknowledgements

- [yfinance](https://github.com/ranaroussi/yfinance) — Yahoo Finance Python wrapper
- [Stooq](https://stooq.com/) — free OHLCV CSV data
- [mkcert](https://github.com/FiloSottile/mkcert) — local CA + cert issuance
- [Lightweight Charts](https://github.com/tradingview/lightweight-charts) — TradingView's open-source charting (self-hosted)
- [Flask](https://flask.palletsprojects.com/) — web framework
- [pandas](https://pandas.pydata.org/) — indicator math
