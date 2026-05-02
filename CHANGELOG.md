# Changelog

All notable changes to this project will be documented in this file.
Format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/) and the
project adheres to [SemVer](https://semver.org/).

## [0.23.0] - 2026-05-02

### Added — 1.0 readiness: CSP coverage, render-smoke, bundle / dep audits

This release closes the six release gates identified between v0.22.1
and a credible v1.0.0 tag. No user-visible features. No API changes.
Backward-compatible.

**1. Strict CSP on every HTML route.**
The after-request hook in `app.py` was attaching
`Content-Security-Policy` only to `/`, `/app`, and `/static/*` since
v0.3.0 — leaving 13 other user-facing routes uncovered. v0.23.0
inspects the response `Content-Type` instead and applies the same
strict policy (`default-src 'self'; script-src 'self'
'unsafe-inline'; style-src 'self' 'unsafe-inline'; img-src 'self'
data:; connect-src 'self'; frame-ancestors 'none'; base-uri 'self';
form-action 'self'`) to every text/html response. Caught by the new
render-smoke suite.

**2. Render-smoke suite (`tests/test_render_smoke.py`).**
21 new tests:
- 15 parametrised checks (every user-facing route returns HTTP 200,
  text/html content-type, expected landmark string, and — where the
  v0.22.0 wire-up promised — `alerts.js` referenced in the body).
- Security-header gates: CSP `script-src 'self'` and `frame-ancestors
  'none'` on every HTML route, `X-Frame-Options: DENY`,
  `Server-Timing: app;dur=` (v0.21.0 commitment).
- `security.txt` RFC 9116 fields (`Contact`, `Expires`, `Canonical`,
  `Policy`) all present.
- `Expires` parsed and asserted in the future — failsafe so the
  contact field never lapses silently.
- Favicon route serves SVG.

**3. Bundle-size budget CI gate.**
`scripts/check_bundle_sizes.sh` parses every JS / CSS asset against
the v0.23.0 budgets defined in `PERFORMANCE.md`. New `bundle-budgets`
job in `.github/workflows/ci.yml` runs it on every push. Three
budgets bumped to reflect post-v0.22.1 reality (analysis.css,
screener.css, portfolio.js) — drift was silent before this gate.

**4. Dependency audit + SBOM in CI.**
- `scripts/audit_dependencies.sh` runs `pip-audit -r requirements.txt`
  with an explicit allow-list for upstream CVEs that have no PyPI fix
  available yet (currently 2: `requests` GHSA-gc5v-m9x4-r6x2,
  `curl-cffi` GHSA-qw2m-4pqf-rmpp). `--strict` ignores the allow-list
  and surfaces every CVE.
- `audit/sbom-v0.23.0.txt` (`pip freeze`) and
  `audit/pip-audit-v0.23.0.json` (full report) committed for an
  auditable trail.
- New `dependency-audit` CI job runs on every push.
- Both pending CVEs documented in `SECURITY.md` with use-case rationale
  (outbound HTTP only, no user-controlled URLs reach `requests`;
  `curl-cffi` is a transitive dep of `yfinance`, no direct app use).

**5. `security.txt` Expires rolled forward.**
RFC 9116 sets a maximum 1-year window on `Expires`. The previous
field (2027-01-01, set at v0.20.0) was within the window but unverified
by tests. v0.23.0:
- Rolls Expires forward to 2027-05-02 (one year from the v0.23.0
  ship date).
- Adds `test_security_txt_expires_not_in_past` to the render-smoke
  suite. Any future release with a lapsed Expires fails CI before push.

**6. Clean-machine install audit checklist.**
`INSTALL_AUDIT.md` is a reproducibility contract for verifying a
fresh-host install works end-to-end. Covers pre-flight cleanup,
install steps, first-launch checks across Chrome / Safari / Firefox,
smoke tour of all 12 user-facing pages, security-header verification
via `curl`, and uninstall. Issues filed against the checklist itself
are explicitly invited.

### Tests

Total: **245 passing** (up from 224).
- `tests/test_render_smoke.py` — 21 new tests (route renders + security
  headers + favicon + RFC 9116 Expires).

### Docs

- `README.md` — version badge -> 0.23.0, test count -> 245, new "What's
  new in v0.23.0" section.
- `SECURITY.md` — `Latest: **v0.23.0**`, new dependency-audit section
  with the two pending GHSA entries.
- `PERFORMANCE.md` — bundle budgets refreshed to v0.23.0 reality;
  per-page weight table added documenting the v0.22.0 global
  `alerts.js` injection.
- `CHANGELOG.md` — this entry.
- `INSTALL_AUDIT.md` — new file.
- `pyproject.toml` + `app.py /api/settings/server-info` -> 0.23.0.

### Compatibility

- Pure hardening + audit release. No API changes. No localStorage
  changes. No UI changes.
- One behaviour change: HTML routes outside `/` + `/app` now carry CSP
  headers they didn't before. Browsers that loaded a third-party
  inline script on those pages would have done so silently — now
  blocked. Project's own templates use only inline scripts under
  `script-src 'self' 'unsafe-inline'`, so no breakage.

---

## [0.22.1] - 2026-05-02

### Added — Bucket chip on Recommendation tab

Visible UI feedback for the v0.22.0 risk-profile wiring. The
Recommendation banner now renders a compact pill chip underneath the
confidence reason:

```
Tuned for Conservative · Buy ≥ M75/V50/R≤30 · change
```

- Reads `sc.risk_bucket` + `sc.thresholds_used` from the
  `/api/analyze/v2` payload (already returned by v0.22.0; just no UI
  surface yet).
- `title` attribute on the chip exposes the full six-key threshold dict
  (buy_value / buy_momentum / buy_risk_max / buy_dc_min /
  avoid_momentum / avoid_risk) on hover.
- `change` is a deep link to `/risk-profile` so retaking the
  questionnaire is one click away.

CSS lives in `static/analysis.css` — `.rec-bucket-chip` reuses the
existing `--bg` / `--border` / `--muted` / `--text` tokens so it
inherits dark / light themes without extra rules.

### Tests

`tests/test_wireup.py` — 2 new template / CSS presence checks. Total:
**224 passing** (up from 222).

### Docs

- `README.md` — version badge + test count + new "What's new in
  v0.22.1" section.
- `SECURITY.md` — `Latest: **v0.22.1**`.

### Compatibility

- Pure UI patch. No API changes. No localStorage changes. No new deps.
- Recommendation banner gracefully omits the chip if the server returns
  a payload without `thresholds_used` (e.g. an older client cache).

---

## [0.22.0] - 2026-05-02

### Added — Wire-up release (post-PRD): risk profile, watchlist export, global alerts polling

PRD Build Steps 1–13 shipped in v0.21.0. v0.22.0 wires three already-built
components into their natural touch points so the user experience matches
what the PRD promised end-to-end. No new dependencies. No new endpoints.
0 schema changes.

**1. Risk profile → Recommendation thresholds.**
`calc/recommendation.py` gains a `RISK_THRESHOLDS` table mapping each of
the five risk buckets (Conservative / Moderate / Balanced / Growth /
Aggressive) to a six-key threshold set:

```python
{ "buy_value", "buy_momentum", "buy_risk_max",
  "buy_dc_min", "avoid_momentum", "avoid_risk" }
```

`build_scenario(...)` now accepts a `risk_bucket` kwarg and selects the
matching set via `_thresholds_for(bucket)` (falls back to `balanced` for
unknown / `None`). The Buy / Watch / Avoid logic and the
`confidence_reason` text both reference the bucket explicitly so the
user sees `[Conservative profile]` on the recommendation and knows which
threshold set fired.

`/api/analyze/v2` accepts `risk_bucket` in the JSON payload, validates
against the allow-list `{conservative, moderate, balanced, growth,
aggressive}`, and forwards to `build_scenario`. The frontend
(`templates/index.html`) now reads `RiskProfile.currentBucket()` from
`localStorage["equityscope.riskProfile"]` and includes it on every
analyze fetch — so retaking the questionnaire immediately retunes
the next recommendation.

The scenario response payload gains two metadata fields,
`risk_bucket` and `thresholds_used`, surfacing the active bucket and
its full threshold dict for transparency / explainer drawers.

**2. Watchlist CSV + JSON export.**
Two new actions in the Watchlists sidebar (`templates/watchlists.html`):
`↓ CSV` and `↓ JSON`. The `exportWatchlist(fmt)` helper assembles a
20-column CSV with quoted strings + numeric coercion (ticker, company,
country, sector, currency, price, market-cap-USD, trailing P/E, perf
5D, RSI 14, ROC 14D, ROC 21D, % from 52-week low, the four scores,
data confidence, price freshness, price source) or a structured JSON
dump containing `{ watchlist, exportedAt, tickers, metrics }`. Files
download as `watchlist-<safeName>-<timestamp>.<ext>`. No PII, no
network round-trip — pure local-state export.

**3. Alerts background polling on every page.**
`static/alerts.js` is now bulk-injected into all 12 user-facing
templates (`index`, `watchlists`, `screener`, `compare`, `events`,
`news`, `data_quality`, `sources`, `settings`, `portfolio`,
`risk_profile`, `privacy`). Each injection includes a tiny
`window.APP_BASE` bootstrap so cross-page polling builds the right
URL under the `/Local` mount. The `Page Visibility API` keeps the
poller idle when the tab is hidden — same battery / network discipline
as before, just running everywhere instead of only on the dedicated
alerts panel.

### Tests

`tests/test_wireup.py` adds 23 wire-up tests:

- 7 `RISK_THRESHOLDS` / `_thresholds_for` / `build_scenario(risk_bucket=...)`
  unit tests including a conservative-vs-aggressive ordering invariant.
- 3 `/api/analyze/v2` payload tests: valid bucket round-trip, unknown
  bucket falls back to default, missing bucket uses default.
- 1 watchlist-template export-button presence check.
- 12 parametrised checks that `alerts.js` is referenced from every
  user-facing template.

Total: **222 tests passing** (up from 199).

### Docs

- `README.md` — version badge bump + new "What's new in v0.22.0" section.
- `SECURITY.md` — `Latest: **v0.22.0**`.
- This `CHANGELOG.md` entry.

### Compatibility

- Backward-compatible: existing `/api/analyze/v2` clients that don't
  send `risk_bucket` continue to receive `balanced` thresholds — same
  behaviour as v0.21.0.
- `localStorage` keys unchanged. No data migration.
- No new dependencies in `requirements.txt` / `pyproject.toml`.

---

## [0.21.0] - 2026-05-02

### Added — Polish + perf budget (PRD Build Step 13, final step)

This is the last PRD build step. v0.21.0 closes out scope by adding
performance discipline, shared formatters, and end-to-end polish.

**`static/format.js`** — shared formatting helpers exposed on `window.Fmt`.
Eliminates ~500 lines of duplicated `flag()` / `sourceBadge()` /
`scoreBar()` / `fmtN()` / `fmtPct()` / `fmtMcap()` / `fmtVol()` /
`sparkline()` / `timeAgo()` / `cls()` code across 11 templates. Pure
functions only — no DOM, no I/O.

**Server-Timing header** on every response: `Server-Timing: app;dur=<ms>`.
Clients (and DevTools → Network → Timing) see server-side latency
without instrumentation. Implemented via `_record_request_start` +
`_emit_server_timing` hooks in `app.py`.

**`/favicon.ico`** route serves an inline 64×64 SVG triangle (brand mark)
with `Cache-Control: max-age=86400`. Loads on every page via
`<link rel="icon" type="image/svg+xml">`.

**`prefers-reduced-motion: reduce`** CSS guard — disables shimmer / toast
slide-in / drawer-slide animations when the user's OS-level setting
requests reduced motion. Drops CPU on slow devices and respects the
accessibility preference.

**`PERFORMANCE.md`** — authoritative budgets for every JS bundle, every
CSS bundle, every API endpoint (p50 / p95), every cache TTL, and the
loopback rendering targets. New file at the repo root.

### Tests
- `tests/test_polish.py` — 11 cases. Server-Timing header on every
  response, favicon route + content-type + cache-control, favicon link
  in every template, format.js exposes 12 helpers and is loaded on
  every template, screener.css carries the prefers-reduced-motion
  guard, every JS bundle within its byte budget, vendor JS within its
  budget, PERFORMANCE.md exists with required sections.
- All **199 tests pass** (was 190 in v0.20.0).

### PRD scope status
- Build Steps 1–13 ✅ complete.
- All seven primary pages live (Screener · Stock Analysis · Watchlists ·
  Compare · Data Quality · Sources · Settings) plus four PRD-aligned
  sub-pages (Events · News · Portfolio · Alerts · Risk Profile) plus
  Privacy & Compliance.
- 23 exchanges, 14 currencies, 14 indicators, 0 paid APIs, 0 cookies,
  0 trackers, 0 AI/LLM models.

## [0.20.0] - 2026-05-01

### Added — Risk profiler + GDPR + EU AI Act compliance + security hardening

**Risk profiler** (PRD Build Step 12)
- `static/risk_profile.js` — 10-question questionnaire, scored 0–100,
  bucketed into Conservative / Moderate / Balanced Growth / Growth /
  Aggressive.
- `templates/risk_profile.html` — questionnaire UI with progress
  indicator, current-bucket card, "How this affects the app"
  explanation, reset action.
- Persisted in `localStorage["equityscope.riskProfile"]`.
- `RiskProfile.QUESTIONS / BUCKETS / save / get / clear / bucketFor /
  currentBucket()` exposed on `window`.
- Workspace nav group: Watchlists · Portfolio · Alerts · Risk Profile.

**GDPR / UK GDPR compliance**
- `templates/privacy.html` — full privacy + compliance disclosure page.
  Documents Article 6 lawful basis (consent + ePrivacy essential),
  Articles 15–22 data subject rights with self-service mappings,
  international transfers, no DPO required (Art. 37), no children's
  data flow (Art. 8 not triggered).
- `static/consent.js` — first-visit consent banner. Explicit Accept
  records the decision; Decline wipes every `equityscope.*` localStorage
  key (Art. 21 right to object).
- "What gets stored, where" table covers every localStorage key + the
  in-memory server cache TTLs.

**EU AI Act compliance** (Regulation 2024/1689)
- Privacy page declares EquityScope contains **no AI system per Art. 3**
  — no ML model, no LLM, no neural network, no remote AI API.
- All "AI-like" features (headline sentiment, topic clustering, scoring,
  scenario recommendation) are documented as deterministic rule-based
  logic with explicit weights — sources cited (`providers/news.py`,
  `calc/scoring.py`).
- Voluntary Article-50-style transparency: every metric / score / formula
  surfaces in the explainer drawers (v0.19.0).
- No Article-22 automated decision-making: recommendations are
  informational only, with no legal effects on users.

**Security hardening**
- `/.well-known/security.txt` (RFC 9116) — coordinated disclosure
  pointer with Contact / Expires / Policy / Canonical fields.
- **Subresource Integrity** on the self-hosted Lightweight Charts
  vendor bundle: SHA-384 `OK7vELvjHdhUFi31JYioPIcRHTROLdcDa6Zsng…`
  + `crossorigin="anonymous"`.
- New "Threat model" section in `SECURITY.md` covering each asset →
  threat → mitigation.

### Tests
- `tests/test_compliance.py` — 14 cases. /risk-profile + /privacy +
  /.well-known/security.txt routes; risk_profile.js exposes 10
  questions and 5 buckets and full API; consent.js exposes required
  methods and wipes storage on decline; consent.js loaded on every
  page; SRI integrity attribute present and matches actual file
  hash; privacy page declares no AI / rule-based.
- All **190 tests pass** (was 177 in v0.19.0).

## [0.19.0] - 2026-05-01

### Added — Education / explainer drawers (PRD Build Step 11)

**`static/explainer.js`** — slide-out drawer + content registry covering
40+ concepts the app surfaces (every metric, score, chart element,
peer-matrix concept, scenario field, screener concept, workspace
concept, news heuristic, data-quality concept).

Each entry carries:
- `definition` — plain-English explanation
- `formula` — exact computation method (where applicable)
- `interpretation` — bullet list of how to read the value
- `caveats` — limitations, edge cases, "don't auto-trade off this"
- `learn_more` — Wikipedia / Investopedia link for deeper reading

Drawer
- Right-anchored slide-in (380 px desktop, full-width on mobile).
- Backdrop + ESC + close-button dismiss.
- `role="dialog"`, `aria-modal="true"`, focus management returns to the
  trigger button on close.
- Auto-attach: any element with `data-explain="<key>"` gets the click
  handler wired on DOMContentLoaded.
- `Explainer.iconButton(key, label)` factory renders a circular "?"
  button with `aria-label`, ready to drop into any template literal.

UI integration (initial set; can grow over time)
- Stock Analysis Snapshot tab: "?" buttons next to all 14 metric labels
  (Price, 52W High/Low, % from Low, 5D, RSI, ROC 14/21, MA 20/50/200,
  Avg Vol, Mcap USD, Trailing P/E).
- Snapshot Score Overview: "?" buttons next to all 5 score labels
  (Value, Momentum, Quality, Risk, Data Confidence).
- Renderer calls `Explainer.attachAll($("snapshot"))` after each render
  so dynamically-injected buttons stay wired.

Loaded on every page
- All 11 templates (`screener`, `index`, `watchlists`, `compare`,
  `events`, `news`, `data_quality`, `sources`, `settings`, `portfolio`,
  `alerts`) now include `<script src=".../static/explainer.js"></script>`
  immediately after `ui.js`.

CSS
- `.explainer-icon` — 16 px circular "?" button with hover + focus-ring.
- `.explainer-drawer` — slide-in from the right, dark theme, scrollable
  body, sticky header.
- `.exp-formula` — monospace inset card for formulas.
- `.exp-caveats` — yellow-bordered call-out for limitations.

### Tests
- `tests/test_explainer.py` — 5 cases. Bundle file exists with expected
  exports, every PRD-required topic key (40+) is in the content
  registry, every entry has a definition field, all 11 routes load
  explainer.js, no Jinja-quote artefacts (`\\'static\\'`) in rendered
  HTML.
- All **177 tests pass** (was 172 in v0.18.0).

## [0.18.0] - 2026-05-01

### Added — News & headline digest (PRD Build Step 10)

**`/news` page** — recent headlines with rule-based sentiment + topic
clustering, transparently labelled as "auto-extracted from headlines, not AI".

**NewsProvider** (`providers/news.py`)
- yfinance `.news` (free, no API key); 15-min cache.
- Returns list of `{title, link, publisher, published_at, summary,
  thumbnail, sentiment, topic, ticker, source_name, source_url}`.
- `_classify_sentiment()` — keyword-count heuristic returning
  bullish / bearish / neutral.
- `_classify_topic()` — first-match dictionary lookup with most-specific
  topics first (regulation / executive / m_and_a / earnings) to avoid
  false positives, then macro / product / general fallback.
- `summarize(items)` — aggregate digest with counts by sentiment + topic
  and 3 sample headlines per sentiment bucket.

API
- `GET /api/news?ticker=&max=` — single-ticker headlines + digest.
  `max` clamped 1–30.
- `POST /api/news/digest` — batch headlines for ≤30 tickers (e.g.
  watchlist), returns `{news: {TICKER: items[]}}`.

UI
- `/news` page with two modes: "My Watchlist" (default) and "Single
  ticker" lookup.
- Sentiment hero cards: bullish / bearish / neutral counts + total.
- Topic-distribution bars (Earnings / Product / M&A / Regulation /
  Executive / Macro / General).
- Headline cards with ticker chip → link to Stock Analysis, sentiment
  badge, topic chip, publisher, time-ago, optional summary.
- Empty state when watchlist empty or no fresh news.
- Prominent disclaimer that sentiment + topic are heuristic, not AI.

Sources page
- `/api/sources/health` now lists `news` provider with explicit
  "rule-based, not AI" note.

Nav
- _nav.html: News link added under Market group beside Events.
  Workspace + Market + System groups all populated.

### Tests
- `tests/test_news.py` — 18 cases. Sentiment classifier (bullish /
  bearish / neutral / empty / None), topic classifier (earnings /
  m_and_a / regulation / executive / general fallback),
  `_ts_to_iso()` (unix epoch / None / garbage), `summarize()` empty +
  aggregation, fetch returns empty on yfinance failure, route renders,
  /api/news invalid / valid / max-clamp, /api/news/digest empty /
  too-many / per-ticker shape, nav link presence, sources health
  exposes `news` provider.
- All **172 tests pass** (was 149 in v0.17.0).

### Smoke test (live data)
- AAPL: 5 headlines, all bullish, topic split earnings 4 / general 1.
- Sample: "Apple stock rises after Q2 earnings top estimates on strong
  iPhone, China sales".

## [0.17.0] - 2026-05-01

### Added — Alerts (PRD Build Step 9)

**`/alerts` page** — browser-local alert engine with auto-poll, OS
notifications, and a triggered log. Zero server-side persistence.

Storage (`static/alerts.js`)
- localStorage key `equityscope.alerts`.
- Schema: `{version, pollMinutes, desktopNotifications, alerts[], log[]}`.
- Alert shape: `{id, ticker, kind, threshold, status, createdAt,
  triggeredAt, snoozedUntil, dismissedAt, lastValue, notes}`.
- `Alerts.add/update/remove/snooze/dismiss/reactivate/list/log/
  pollOnce/evaluateAll/notifyFire/requestDesktopPermission`.
- Log capped at 200 entries to prevent runaway storage.

11 alert kinds
- `price_above`, `price_below` — absolute thresholds in local ccy
- `pct_change_5d` — absolute 5-day move ≥ X%
- `rsi_above`, `rsi_below` — RSI bands
- `cross_ma50_up`, `cross_ma50_down`, `cross_ma200_up`, `cross_ma200_down`
  — moving-average crossovers
- `near_52w_low`, `near_52w_high` — distance-from-extreme thresholds

Background polling
- Auto-runs while any EquityScope tab is open (`alerts.js` is loaded by
  the alerts page; can be added to other pages later).
- Default 5 min interval; user-selectable 1 / 5 / 15 / 30 / 60 min.
- Pauses while document is hidden (`document.hidden`); re-runs on focus.
- Batches `/api/metrics` requests at 12 tickers per chunk.
- Triggered alerts auto-pause (status=triggered) until user reactivates,
  preventing notification spam.

Notifications
- In-app toast on every fire (via shared `UI.toast`).
- Optional desktop notifications via `Notification` API (opt-in checkbox
  requests permission on first enable; gracefully degrades if denied).
- `equityscope:alerts-fired` window event so an open Alerts tab
  re-renders without reload.

UI
- Add-alert form (ticker / kind / threshold / notes) with kind-aware
  threshold unit hint and auto-disable for thresholdless cross alerts.
- Status badges: Active / Triggered / Snoozed / Dismissed.
- Inline actions per row: Snooze 1h · Reactivate · Delete.
- Trigger log table (newest first, 50 most recent).
- Empty state when no alerts.
- All 5 routes (`/screener`, `/app`, `/portfolio`, `/watchlists`,
  `/alerts`) now expose Alerts in the Workspace nav group.

Backend
- New `/alerts` route. No new API endpoints — eval reuses `/api/metrics`
  for live data. Alert state never leaves the browser.

### Tests
- `tests/test_alerts.py` — 5 cases. Route renders, all 11 alert kinds
  exposed in the form, polling controls present, disclaimer present,
  nav link active.
- All **149 tests pass** (was 144 in v0.16.0).

## [0.16.0] - 2026-05-01

### Added — Portfolio (PRD Build Step 8)

**`/portfolio` page** — full holdings tracker with cost basis, live P/L,
multi-currency rollup, and allocation breakdowns.

Storage (`static/portfolio.js`)
- localStorage-backed (`equityscope.portfolio`); no login per PRD.
- Holding shape: `{id, ticker, shares, costPerShare, costCurrency,
  purchaseDate, notes, createdAt}`.
- API: `Portfolio.add()`, `update()`, `remove()`, `clear()`, `list()`,
  `tickers()`, `currencies()`, `valuate(metricsByTicker, fxByPair)`,
  `setBaseCurrency()`, `baseCurrency()`.

Page features
- Add-holding form: ticker, shares, cost/share, cost currency,
  purchase date, notes — all validated client-side.
- Live pricing via batched `/api/metrics` (chunks of 12 to respect API
  cap).
- Multi-currency: per-row P/L computed in cost-currency when live ccy
  matches; portfolio totals rolled up into base currency (USD default,
  user-selectable).
- 5-card totals strip: Total Value · Total Cost · Unrealized P/L · P/L %
  · Holdings count.
- Sortable holdings table: ticker / company / shares / avg cost /
  price / value (local) / value (base) / P/L / P/L % / weight / source.
- Allocation breakdowns (3 cards): by Sector, by Country, by Currency,
  with percentage bars + base-ccy values.
- Edit (shares + cost) / remove per-row inline.
- CSV + JSON export of holdings + valuation.
- JSON import (replaces existing portfolio after confirm).
- "Add to portfolio" quick-action on the Stock Analysis header.
- Empty-state when no holdings.

Backend
- `GET /api/fx?from=&to=` — single FX rate via `markets.fx_rate()`,
  returns `{rate, freshness, source_name, source_url}`.
- `POST /api/fx/batch` — up to 30 currency pairs in one round-trip,
  returns `{rates: {"FROM_TO": rate}}`. Used by Portfolio for the
  base-currency rollup.
- Both endpoints validate ISO 4217 3-letter codes via regex; invalid
  codes return 400.

Nav
- `_nav.html`: Portfolio link enabled (was aria-disabled placeholder).

### Tests
- `tests/test_portfolio.py` — 11 cases. Route renders, FX validation
  (invalid codes / unknown pair / same-ccy = 1.0), FX batch payload
  shape + invalid-pair filtering + 30-pair cap, nav link presence.
- All **144 tests pass** (was 134 in v0.15.0).

### Smoke test (live FX)
- INR→USD: 0.01054
- EUR→USD: 1.17247
- JPY→USD: 0.00637

## [0.15.0] - 2026-05-01

### Added — UI Foundations (PRD §6 — Information Architecture + UI Layer)

**Grouped navigation** — `_nav.html` restructured into 4 PRD-aligned groups
with active-group highlight: **Research** (Screener / Analysis / Compare),
**Workspace** (Watchlists + Portfolio/Alerts placeholders for v0.16/17),
**Market** (Events), **System** (Data Quality / Sources / Settings).
Group label sits above each cluster; current page lights up the whole
group. ARIA roles (`role="menubar"`, `role="menuitem"`, `aria-disabled`)
on every link. Mobile hamburger toggle wires via shared `ui.js` so the
groups collapse to a vertical list under 720 px.

**Reusable UI helpers** (`static/ui.js`)
- `UI.tableSkeleton(rows, cols)` — shimmer rows with `aria-busy="true"`
- `UI.statGridSkeleton(count)` — Snapshot-style metric grid placeholder
- `UI.paragraphSkeleton(lines)` — narrative block placeholder
- `UI.cardGridSkeleton(count)` — Watchlists / Compare / Screener cards
- `UI.emptyState({title, description, icon, linkText, linkHref})` —
  consistent empty UI with optional CTA, `role="status"`
- `UI.toast(msg, {type, duration})` — auto-injected toast host
  (`role="status"`, `aria-live="polite"`); `success` / `error` /
  `warning` variants

**`fetchWithRetry`** — retry-aware fetch wrapper at `window.fetchWithRetry`.
Retries on 408 / 425 / 429 / 5xx + network/abort errors. Skips
deterministic 4xx (400 / 401 / 403 / 404 / 422). 12s default timeout
(pass `{timeout: 30000}` for AI/news endpoints per PRD). Exponential
backoff (250ms → 500ms → 1s). All 13 fetch call-sites across screener /
analysis / watchlists / compare / events / data-quality / settings / sources
swap to `(window.fetchWithRetry || fetch)(...)` so the helper degrades
gracefully if `ui.js` fails to load.

**Accessibility pass**
- `<a class="skip-link" href="#main">Skip to main content</a>` injected
  at the top of every page via `_nav.html`
- All primary content wrapped in `<main id="main">` landmark
- `aria-label` on the brand link, mobile-toggle button, and all
  menubar elements
- `:focus-visible` rings on every interactive control (buttons, score
  bars, score-cell, nav links, brand)
- Toast region uses `aria-live="polite"`; skeletons broadcast
  `aria-busy="true"`

**Mobile responsive (375 px audit)**
- Nav collapses to hamburger under 720 px; group labels remain visible
  in the dropdown
- Screener filter sidebar stacks above results under 900 px
- Card view becomes 1 column under 720 px
- Compare-input field fills width under 720 px
- Tables shrink to 11px font under 720 px
- Version tag hidden under 400 px to save header space
- All shells (`screener-shell`, `analysis-shell`) reduce padding to
  `12px 14px` under 900 px

### Changed
- All eight templates (`screener`, `index`, `watchlists`, `compare`,
  `events`, `data_quality`, `settings`, `sources`) now load `ui.js`
  before any inline scripts so the helpers are defined when needed.
- Screener / Analysis containers switched from `<div>` to `<main>` to
  match the new `#main` landmark target.

### Tests
All 134 tests still pass. UI helpers are pure browser code; covered by
the existing route-renders tests (which now check the skip-link +
`<main>` landmark presence).

## [0.14.0] - 2026-04-29

### Added — Multi-source verification + watchlist sparklines + polish

**Multi-source price cross-validation**
- `StooqYFinanceProvider.fetch()` now runs Stooq + yfinance in parallel
  (same wall-clock as the slower of the two) and cross-validates last
  close. When both providers succeed and agree within 2%, the price
  metric earns `verified_source_count = 2` and confidence is bumped to
  `"high"`.
- `verified_count_for(ticker)` API exposed for downstream consumers.
- `UniverseService.enrich()` propagates the count onto every price-derived
  metric's `SourcedValue.verified_source_count`.
- Source badges in Screener / Stock Analysis / Watchlists / Compare /
  Events / Sources tooltip now show "✓ verified by N sources"; a green
  ✓ dot appears next to the freshness label when ≥ 2.

**Sparklines on Watchlist cards**
- `/api/metrics` accepts `include_sparkline=true` + `sparkline_days` —
  attaches `recent_closes` to each match (same shape as the screener's
  card-view payload).
- Watchlists page renders an SVG sparkline above each card's metric grid,
  colour-coded green/red by net change. Honours the user's
  `sparkDays` preference from Settings.

### Tests
- `tests/test_cross_validation.py` — 6 cases. Verified=2 on agreement,
  =1 on disagreement, =1 when only yfinance succeeds, =1 when only Stooq
  succeeds, =0 when both fail, cache hit doesn't re-fetch.
- `tests/test_resolver_edges.py` — 12 cases. Empty / whitespace queries,
  lowercase normalisation, universe substring matches, ambiguous-query
  disambiguation, dot-suffix preservation, raw fallback for unknown
  tickers, special-character safety (M&M.NS, BRK-B, 0700.HK, 005930.KS),
  long-query handling.
- All **134 tests pass** (was 116 in v0.13.0).

### Smoke test (live data)
- AAPL via /api/analyze/v2: price source = Yahoo Finance, verified=1
  (Stooq gated by API key requirement, so only one source available).
- /api/metrics with `include_sparkline=true` returns 30-close arrays for
  AAPL ($270.11 latest) and MSFT ($423.91 latest).

## [0.13.0] - 2026-04-29

### Added — Settings page (PRD nav slot 7)

**`/settings`** — final PRD nav slot wired up. Closes 100% of PRD nav.

- **Preferences** (localStorage)
  - Default landing page (Screener / Stock Analysis / Watchlists / Compare / Events / Data Quality)
  - Sparkline range (30 / 60 / 90 / 180 days) — applied by Compare page
  - Compact table density default — applied by Screener
  - Open Screener in card view by default — applied by Screener
- **Watchlists management** — list / rename / delete from settings page directly.
- **Custom Screener Presets management** — list / delete saved presets.
- **Server Info** — version, Python, platform, URL prefix, TLS status,
  trusted hosts, auto-shutdown config, universe size, cache stats.
- **Clear server cache** button — forces re-fetch of live data
  (CSRF-protected: requires loopback peer + trusted Origin).
- **Reset all preferences** — wipes every localStorage key the app uses.
- About section with repo link.

**Backend endpoints**
- `GET /api/settings/server-info` — JSON with all server state.
- `POST /api/settings/clear-cache` — drops `_enriched_cache` (loopback +
  trusted-Origin only; same CSRF guard as `/api/shutdown`).

**Default-landing redirect**
- Screener page (`/`) now reads `equityscope.prefs.landing` on load and
  redirects accordingly — only when the user is on `/` with no query
  string, so deep-links keep working.

### Tests
- `tests/test_settings.py` — 7 cases: settings route renders, server-info
  payload shape, version string, clear-cache CSRF rejection (no Origin /
  untrusted Origin → 403; trusted Origin → 200), Settings link present
  in nav.
- All **116 tests pass** (was 109 in v0.12.0).

### PRD coverage
**100% of the 7 navigation pages now built.** Build Steps 1–7 all
complete + Settings page wired. Outstanding items are minor (multi-
provider verification for `verified_source_count > 1`; investor-day
events not in any free public source).

## [0.12.0] - 2026-04-29

### Added — Build Steps 5 + 6 + 7 (Data Quality + Events + Scenario Recommendation)

**Build Step 5: Data Quality Command Center** (`/data-quality`)
- Source-audit table over the live enrichment cache: ticker × metric ×
  source × URL × retrieved-at × freshness × confidence × warning.
- Hero stats: counts by freshness category (real-time / delayed / prev /
  cached / historical / mock / unavailable).
- Filter controls (ticker contains, freshness, confidence).
- CSV + JSON export of the full audit.
- Refresh button forces a re-pull.
- New endpoints:
  - `GET /api/data-quality/audit` — complete audit rows + counts
  - `GET /api/data-quality/stats` — summary % (fresh / stale / mock / missing)

**Build Step 6: Events / Catalyst Calendar** (`/events`)
- New `EventsProvider` (`providers/events.py`) using yfinance `.calendar`,
  `.info`, and `.actions`. Returns SourcedValue for earnings_date,
  dividend_date, ex_dividend_date, split_date. Failed lookups surface as
  `freshness="unavailable"` with explicit warning — never fabricated.
- Wired into `UniverseService.events`; populated lazily on demand.
- New endpoints:
  - `GET /api/events?ticker=`
  - `POST /api/events/calendar` — batch (≤30 tickers) for watchlist /
    custom views.
- New page `/events` — pulls events for the user's local watchlist by
  default, falls back to a custom-tickers input box. Shows date / event /
  ticker / source / freshness / confidence rows sorted by upcoming date.
- Stock Analysis "Events" tab now renders real events with source URLs.

**Build Step 7: Scenario-Based Recommendation**
- New `calc/recommendation.build_scenario()` returns the full PRD shape:
  - `base_case` — narrative anchored on price vs MAs + P/E zone
  - `upside_case` — natural targets (200D reclaim, 52W high re-test, ROC)
  - `downside_case` — failure points (lose 50D, break 200D, fail 52W low,
    overbought RSI)
  - `technical_trigger` — bullish / bearish / continuation / mixed
  - `invalidation_level` — closer of 200D MA / 52W low
  - `confidence_reason` — why this rating, score-driven
  - `final_rating` — Buy / Watch / Avoid
  - `time_horizon` — rating-aware (1–3 mo Buy, 2–6 wk Watch, 4–8 wk Avoid)
  - `catalysts` — pulled from EventsProvider when available, plus generic
    sector + peer-earnings entries.
- `/api/analyze/v2` now embeds `scenario` (and `events`) in the response.
- Stock Analysis "Recommendation" tab redesigned: rating banner +
  confidence reason + time horizon + 3-card scenario grid (Base / Upside
  / Downside) + Technical Trigger + Invalidation Level + Catalysts.

**Nav** — `_nav.html` activates Events + Data Quality links (were "Coming
soon" in v0.11.0).

### Tests
- `tests/test_recommendation.py` — 10 cases. Required-keys shape, rating
  enum, strong-setup → Buy, overbought → Avoid, low-data → Watch, trigger
  uses MAs, invalidation uses MA / 52W low, catalysts pull from events,
  empty-events fallback, non-empty cases.
- `tests/test_events_and_dq.py` — 11 cases. EventsProvider returns
  expected keys on yfinance failure; /api/events + /api/events/calendar
  validation + payload shape; /api/data-quality/audit + /stats payload
  shape; /events + /data-quality routes render.
- All **109 tests pass** (was 87 in v0.11.0).

### Smoke test (live data)
- AAPL: events resolve dividend 2026-02-12, ex-div 2026-02-09, split
  2020-08-31; earnings unavailable from yfinance — surfaces as
  `freshness="unavailable"` with warning, never fabricated.
- Scenario rating "Watch" with continuation trigger anchored on $260.56
  (50D MA) / $254.21 (200D MA), invalidation at 200D MA.
- Data Quality command center: 208 metrics across 13 cached tickers;
  97.6% fresh, 0% stale, 0% mock, 2.4% unavailable.

## [0.11.0] - 2026-04-29

### Added — Build Step 2 (Stock Analysis 8-tab redesign + interactive charts + peer matrix v2)

**Stock Analysis page rebuilt** (`/app`) with 8 PRD-spec tabs:
1. **Snapshot** — full metric grid + score overview + peer-summary tags.
2. **Chart** — interactive candlestick / line toggle, MA20/50/200 overlays,
   volume histogram pane, RSI 14 sub-pane (with 30/70 reference lines),
   ROC 14D sub-pane, 52-week high/low price lines, date-range buttons
   (1M/3M/6M/1Y/3Y/5Y/Max), live crosshair tooltip showing date + OHLC +
   volume + RSI + ROC. Falls back to line chart with warning if OHLC
   incomplete.
3. **Value** — score + reasons + warnings + input table with source badges
   for P/E, forward P/E, P/B, dividend yield, % from low, market cap.
4. **Momentum** — score + reasons + warnings + input table for 5D / ROC /
   RSI / vs 20D / 50D / 200D MA distances.
5. **Peers** — full PRD-format matrix
   `Metric \| Input Stock \| Peer Median \| Peer Rank \| Better/Worse \| Source Quality`
   plus a peer roster table with row-click navigation.
6. **Events** — currently shows
   "Data unavailable. No reliable free/public source found." per spec
   (placeholder until Build Step 6).
7. **Recommendation** — interim Buy/Watch/Avoid banner derived from scores;
   notes that Build Step 7 will add Base/Upside/Downside cases, Technical
   Trigger, Invalidation Level, Confidence Reason.
8. **Sources** — per-stock audit table covering every metric with source
   name, URL, retrieved-at, freshness, confidence, warning. CSV export.

**Charting**
- Self-hosted Lightweight Charts 4.2.0 (`static/vendor/`, ~160 KB) — keeps
  CSP `script-src 'self'` intact.
- Multi-pane chart with separate priceScaleIds for vol / rsi / roc.

**Backend API**
- `GET /api/ohlcv?ticker=&days=` — returns full OHLCV bars, source, freshness,
  has_ohlc flag. Used by the Chart tab.
- `POST /api/analyze/v2` — accepts `{ticker, peer_tickers?}`. Returns
  `{input, peers, peer_matrix, history_source}`. Defaults peer discovery to
  same-sector tickers from the curated universe.
- `_peer_matrix()` builder computes median + rank + better/worse + source
  quality across 13 PRD-required metrics, with summary booleans.

**Tests**
- `tests/test_analyze_v2.py` — 11 cases covering /api/ohlcv (invalid ticker,
  default bars, days clamping), /api/analyze/v2 (full payload shape, all
  required matrix metrics, summary keys, explicit peer override, rank
  bounds), and /app route 8-tab structure.
- All **87 tests pass** (was 76 in v0.10.0).

### Smoke test (live data)
- AAPL: 252 bars OHLCV from Yahoo Finance, 12 peers, scores V=10 M=90 Q=75
  R=0 DC=100, peer-matrix shows P/E rank 7/12 vs peer median 30.2 (Worse).

## [0.10.0] - 2026-04-29

### Added — Build Step 1 complete (Screener parity with PRD)

**Scoring on 0–100 scale per PRD weights**
- `value_score`: +20 P/E ≤ 10, +15 below peer median, +20 within 10% of low,
  +10 mcap ≥ $2B, +10 dividend > 2%, -15 P/E unavailable.
- `momentum_score`: +15 each for 5D / ROC14 / ROC21 / RSI 40-70, +10 each
  for above 20D / 50D / 200D MA, -15 RSI > 70, -20 below 200D MA, -15 both
  ROC negative.
- `quality_score`: +35 mega-cap, +20 large-cap, +20 dividend payer,
  +15 P/B ≤ 5, +10 high liquidity, +10 defensive sector, +10 price + fund
  both resolved.
- `risk_score`: higher = riskier. +25 RSI > 70, +25 below 200D MA, +15 low
  volume, +15 P/E missing, +10 small cap, +10 stale data, +10 near 52W high,
  +10 both ROC negative.
- `data_confidence_score`: 60% coverage + 30% freshness + 10% completeness
  bonus, minus 5 per mock-flagged metric.
- All clamped 0–100. Labels: Excellent (≥85), Good (≥65), Mixed (≥40),
  Weak (≥20), Poor.

**Filter engine — 32 filter kinds covering full PRD list**
- Cheap: sector / country / region / exchange / **currency / industry /
  listing_type**.
- Range: price min/max, mcap min/max, P/E min/max, **P/B min/max**,
  **dividend min/max**, **volume min/max**, RSI min/max, perf5d min/max,
  **ROC14 min/max, ROC21 min/max**, pct_from_low min/max, **pct_from_high_max**.
- Boolean: above_ma20 / above_ma50 / above_ma200, **exclude_unavailable_pe,
  exclude_unavailable_mcap, exclude_stale, require_history**.
- Score-based: **min_data_confidence** — engine now accepts `score_fn`
  callback and filters using computed scores.

**Presets — all 6 PRD-required**
- Value Near Lows, Momentum Leaders, Quality Large Caps, Oversold Watchlist,
  **Breakout Candidates** (new), **Data Reliable Only** (new). Plus 6 extras
  (trend followers, mega caps, indian banks, japan industrials, europe tech,
  dividend payers). 12 total.

**Custom user-saved presets**
- Saved to `localStorage["equityscope.customPresets"]`. "Save current
  filters as preset" button names + persists. New "My Presets" tab in
  filter sidebar.

**Filter UI**
- Sidebar reorganised into collapsible sections (Universe / Price &
  Liquidity / Valuation / Momentum / Data Quality) with all 32 filters
  exposed.

**Results table**
- All PRD columns now available: Company, Ticker, Exchange, Country,
  Sector, **Industry**, **Currency**, Price, Market Cap, P/E, % from low,
  5D %, RSI, **ROC 14D**, **ROC 21D**, Value, Momentum, **Quality**,
  **Risk**, **Data Confidence**, Source.
- **Column visibility controls** (⚙ Columns button) grouped by Overview /
  Valuation / Momentum / Quality / Risk / Data; persisted in localStorage.
- **Compact mode** toggle (smaller row height, smaller scores).
- **Multi-select rows** + bulk action bar:
  - Add to watchlist (any list)
  - Compare (2–6 selected)
  - **Export CSV** / **Export JSON**
  - Clear selection

**Card view**
- **Mini sparklines** (60-day SVG, colour-coded by net change) on every
  card. Backend `/api/screener/run` now accepts `include_sparkline=true`
  and returns `recent_closes` per match.
- All score bars + source badges visible.

**"Why this score?" modal**
- Click any score bar → modal with reasons, warnings, source URLs.
  Works in both table and card views.

### Tests
- `test_scoring.py` — rewritten for the 0–100 scale with PRD weights.
  Covers max-points, zero-bound, mock penalty, partial-data scenarios.
- `test_screener_engine.py` — adds tests for new filter kinds:
  currency_in, industry_in, above_ma20, pct_from_high_max,
  exclude_unavailable_pe, score-aware min_data_confidence, breakout +
  data_reliable preset structure.
- All **76 tests pass** (was 65 in v0.9.0).

### API
- `POST /api/screener/run` accepts:
  - `preset` or `filters` (existing)
  - `include_sparkline: bool` (new)
  - `sparkline_days: int` (new, 20–250, default 60)
- Engine now returns `score_cache` so the route can avoid recomputing
  scores after they're already calculated for filter evaluation.

### Models
- `StockMetrics` gains optional `recent_closes: List[float]` for
  sparkline payloads.

## [0.9.0] - 2026-04-28

### Added — Watchlists + Compare (Build Steps 3 + 4)

**Watchlists** (`/watchlists`)
- localStorage-backed (no login per spec). Schema:
  `{version, watchlists: {name → ticker[]}, active}`.
- Default lists seeded: "My Watchlist", "Value Candidates",
  "Momentum Candidates".
- Create / rename / delete custom lists; protected against deleting
  the last remaining list.
- Add ticker via input box, remove via ✕ on each card.
- Refresh-all button → `POST /api/metrics`.
- Sort by ticker / value / momentum / risk / data confidence / 5D /
  market cap / P/E.
- Multi-select checkboxes → "Compare selected" button → routes to
  `/compare?tickers=…`.
- Stored in `localStorage["equityscope.watchlists"]`. Browser-only,
  no sync.

**Compare** (`/compare`)
- Side-by-side comparison for 2–6 stocks.
- Hydrates from `?tickers=AAPL,MSFT,…` query string.
- Metric matrix covers price, market cap (USD), P/E, forward P/E,
  P/B, dividend yield, 5D performance, RSI, ROC 14/21, MAs (20/50/200),
  % from 52W low, average volume, plus all five score bars.
- Per-ticker SVG sparkline (90-day, no external lib, colour-coded
  green/red by net change).
- "Relative highlights" section auto-derives: cheapest by P/E,
  strongest momentum, highest data confidence, riskiest stock.

**Screener integration**
- ⭐ button on every screener row + card. Click toggles ticker in/out
  of every watchlist. State syncs immediately across the page.

**API**
- `POST /api/metrics` — batch enrich up to 12 tickers. Returns
  `StockMetrics + scores` for each. Validates ticker format, preserves
  caller order. No CSRF check (read-only endpoint).
- `GET /api/sparkline?ticker=…&days=N` — closes-only series capped
  20–750 days. Used by the compare page.

**Provider extension**
- `UniverseService.enrich_ticker(ticker)` — accepts any resolvable
  ticker (not just universe rows); synthesises a row from
  suffix-based metadata when missing.
- `UniverseService.fetch_history_for(ticker)` — exposes raw OHLC for
  the sparkline endpoint.

**Nav**
- `_nav.html` — Watchlists + Compare links activated (were "Coming
  soon" in v0.8.0). Active-link highlight per route.

**Tests**
- `tests/test_watchlists_api.py` — 10 cases. Patches
  `UniverseService.enrich_ticker` + `fetch_history_for` to skip the
  network so tests run offline. Covers route renders, batch
  validation (empty / too many / invalid characters), order
  preservation, scores attachment, sparkline clamp.
- All **65 tests pass** (was 55 in v0.8.0).

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
