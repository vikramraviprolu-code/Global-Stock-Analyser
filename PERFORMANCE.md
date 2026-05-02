# Performance Budgets

Authoritative budgets for EquityScope (PRD Build Step 13). All
measurements are taken on a local-loopback dev server unless noted.

## JavaScript bundle budgets

Measured at v0.23.0 with `wc -c static/*.js`. Budgets enforced as the
project's own commitment — drift is reviewed at every release.

| Bundle | Size budget | Actual (v0.23.0) | Notes |
| --- | ---: | ---: | --- |
| `static/ui.js` | ≤ 7 KB | 6.3 KB | Skeletons + toast + fetchWithRetry |
| `static/format.js` | ≤ 6 KB | 5.9 KB | Shared formatters (extracted v0.21.0) |
| `static/consent.js` | ≤ 4 KB | 3.8 KB | GDPR banner |
| `static/explainer.js` | ≤ 25 KB | 21.6 KB | 40+ topic content registry |
| `static/watchlist.js` | ≤ 4 KB | 3.7 KB | localStorage CRUD + CSV/JSON export (v0.22.0) |
| `static/portfolio.js` | ≤ 7 KB | 6.5 KB | localStorage CRUD + valuate() |
| `static/alerts.js` | ≤ 14 KB | 13.3 KB | Rule engine + visibility-aware poller (loads on every page from v0.22.0) |
| `static/risk_profile.js` | ≤ 6 KB | 5.6 KB | Questionnaire + bucket logic |
| `static/backup.js` | ≤ 10 KB | 8.4 KB | Shared import / export / backup helpers (added v1.2.0) |
| `static/vendor/lightweight-charts.standalone.production.js` | ≤ 200 KB | 160 KB | Self-hosted, SHA-384 SRI |

### Per-page weight (own JS only — excludes vendor + cached assets)

`alerts.js` is now injected on every user-facing template (v0.22.0
wire-up release) so the visibility-aware poller runs site-wide. The
per-page totals reflect this:

| Page | Own JS (sum) | Vendor JS | Notes |
| --- | ---: | ---: | --- |
| `/screener` | ~36 KB | — | ui + format + consent + explainer + watchlist + alerts |
| `/app` (Stock Analysis) | ~37 KB | 160 KB | Same as above + lightweight-charts |
| `/watchlists` | ~33 KB | — | + watchlist + portfolio + alerts |
| `/portfolio` | ~36 KB | — | + portfolio + alerts |
| `/alerts` | ~36 KB | — | + alerts + format + ui |
| `/risk-profile` | ~26 KB | — | risk_profile + alerts + consent + explainer |
| `/privacy`, `/sources`, `/data-quality`, `/news`, `/events`, `/compare`, `/settings` | ~26-32 KB | — | Each adds page-specific helpers + global alerts |

Browsers cache identical script tags after the first hit, so the
real network cost on second-page navigation is dominated by the HTML
template itself (typically 8-30 KB). `alerts.js` is fetched once,
served from cache on every subsequent page.

**Why minify is deferred:** the entire app's own JS sums to ~50 KB
unminified — gzip on the wire (next iteration) brings this under 15 KB.
Minification adds tooling without meaningful user-visible win at this
scale.

## CSS bundle budgets

| Bundle | Size budget | Actual (v0.23.0) | Notes |
| --- | ---: | ---: | --- |
| `style.css` | ≤ 8 KB | 7.0 KB | Base tokens + dark theme |
| `screener.css` | ≤ 26 KB | 24.5 KB | Screener + nav + skeletons + drawer |
| `analysis.css` | ≤ 18 KB | 15.9 KB | 8-tab analysis + scenario + portfolio + risk + bucket chip (v0.22.1) |
| `landing.css` | ≤ 10 KB | 9.7 KB | Marketing landing only |

## Server response-time budgets (loopback dev server)

| Endpoint | p50 budget | p95 budget | Notes |
| --- | ---: | ---: | --- |
| Static-rendered template (e.g. `/screener`, `/portfolio`) | ≤ 30 ms | ≤ 80 ms | No upstream calls |
| `/api/search?q=…` | ≤ 200 ms | ≤ 600 ms | yfinance Search API |
| `/api/sparkline?ticker=…` | ≤ 250 ms | ≤ 800 ms | Stooq + yfinance fallback |
| `/api/ohlcv?ticker=…&days=…` | ≤ 300 ms | ≤ 1000 ms | Daily bars; cached 30 min |
| `/api/metrics` (1 ticker) | ≤ 400 ms | ≤ 1500 ms | Stooq + yfinance + fundamentals + scoring |
| `/api/metrics` (12 tickers) | ≤ 1500 ms | ≤ 4000 ms | Parallel fan-out |
| `/api/screener/run` (preset) | ≤ 2000 ms | ≤ 8000 ms | Cheap-then-expensive filter, capped at 60 enrichments |
| `/api/analyze/v2` | ≤ 1500 ms | ≤ 5000 ms | + peer matrix (≤ 12 peers, parallel) |
| `/api/news?ticker=…` | ≤ 600 ms | ≤ 2000 ms | yfinance .news; 15-min cache |
| `/api/events?ticker=…` | ≤ 500 ms | ≤ 1500 ms | yfinance .calendar; 4-hour cache |
| `/api/fx?from=…&to=…` | ≤ 300 ms | ≤ 1000 ms | yfinance currency pair; 6-hour cache |

**Cache hit ratios** — measured indirectly. After the first request to a
ticker, every subsequent request within the TTL window resolves from the
in-memory `TTLCache` and returns within 5 ms (loopback). Cache invalidation
is event-driven: TTL expiry only.

## Cache TTL summary

| Layer | TTL | Reason |
| --- | --- | --- |
| Historical OHLCV (Stooq → yfinance) | 30 min | EOD data; refresh between trading sessions |
| Fundamentals (yfinance .info) | 30 min | Snapshot data |
| Events (yfinance .calendar) | 4 hours | Earnings dates change rarely |
| News (yfinance .news) | 15 min | Headlines turnover faster |
| FX (yfinance currency pairs) | 6 hours | Mid-day drift acceptable for screening |
| Enriched StockMetrics (per ticker) | 30 min | Composite of above |

## Network observability

Every JSON response carries a `Server-Timing: app;dur=<ms>` header so
clients (and DevTools → Network → Timing) can read server-side latency
without instrumentation. The `_emit_server_timing` after-request hook is
defined in `app.py`.

## Frontend rendering targets

EquityScope is local-served, so traditional Lighthouse FCP / LCP / TTI
metrics are dominated by JS evaluation — not the network. Practical
targets:

| Metric | Target |
| --- | --- |
| First Contentful Paint (no analyse running) | ≤ 200 ms |
| Largest Contentful Paint after `/api/analyze/v2` resolves | ≤ 2.5 s |
| Time to Interactive | ≤ 1.5 s |
| Cumulative Layout Shift | ≤ 0.05 |
| Total Blocking Time | ≤ 200 ms |

These are not enforced in CI — they're a maintainer-side checklist.
Run Chrome DevTools → Lighthouse occasionally and update this file if
regressions appear.

## Accessibility-aware perf

- `prefers-reduced-motion: reduce` disables shimmer / toast / drawer
  animations, dropping CPU usage on slow devices and respecting OS
  setting.
- All `<script src>` tags are `defer`-able (DOM parses without blocking).
- No images served — emoji + SVG only. Zero image-decoding cost.
- `loading="lazy"` not currently needed (no `<img>` tags); will adopt
  when adding any.

## Reduce-cost commitments

- **No analytics, no telemetry, no third-party scripts.** Zero out-of-app
  network calls per page load.
- **Vendor JS self-hosted.** No CDN dependency = no third-party DNS
  resolution + no privacy leak.
- **localStorage-only state.** No IndexedDB, no service worker (yet).
- **Server runs on a single thread + single process by default.**
  Sufficient for personal use; gunicorn config in the Dockerfile scales
  to 2 workers × 4 threads if needed.

## Measurement workflow

```bash
# Server response timing
curl -w "%{time_total}\n" -o /dev/null -s http://127.0.0.1:5050/api/screener/presets
# Bundle sizes
wc -c static/*.js static/*.css static/vendor/*.js
# Header check
curl -sI http://127.0.0.1:5050/api/screener/presets | grep Server-Timing
```

## Future perf work (post-v0.21.0)

- Optional gzip via `flask-compress` (only meaningful when not on loopback)
- Service worker for offline shell + cache-first static assets
- Code-splitting `lightweight-charts` so it loads only on the Chart tab
  click, not on every Stock Analysis open
- Move heavy enrichment work into a background `concurrent.futures` pool
  with a streaming response (Server-Sent Events) so screener results
  appear progressively
