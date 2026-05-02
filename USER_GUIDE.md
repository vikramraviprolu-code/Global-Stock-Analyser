# EquityScope — User Guide

Comprehensive walkthrough of every feature in EquityScope v1.1.0+.
Pair this with `INSTALL.md` (install) and `SECURITY.md` (privacy +
threat model).

> **First time?** Run through [Quick start](#quick-start) for a 5-minute
> tour. Then come back for the deep dives.

---

## Table of contents

1. [Quick start](#quick-start)
2. [Concepts: data sources, scores, providers](#concepts)
3. [Page-by-page reference](#page-by-page)
   - [Landing](#landing-)
   - [Screener](#screener-screener) `/screener`
   - [Stock Analysis (8-tab)](#stock-analysis-app) `/app`
   - [Watchlists](#watchlists-watchlists) `/watchlists`
   - [Portfolio](#portfolio-portfolio) `/portfolio`
   - [Compare](#compare-compare) `/compare`
   - [Events](#events-events) `/events`
   - [News](#news-news) `/news`
   - [Alerts](#alerts-alerts) `/alerts`
   - [Risk Profile](#risk-profile-risk-profile) `/risk-profile`
   - [Data Quality](#data-quality-data-quality) `/data-quality`
   - [Sources](#sources-sources) `/sources`
   - [Settings](#settings-settings) `/settings`
   - [Privacy](#privacy-privacy) `/privacy`
4. [Daily workflows](#daily-workflows)
5. [Keyboard shortcuts](#keyboard-shortcuts)
6. [Data freshness, caches, retries](#data-freshness)
7. [Privacy, GDPR, and the EU AI Act](#privacy--compliance)
8. [Troubleshooting](#troubleshooting)
9. [Glossary](#glossary)

---

## Quick start

Once installed (see `INSTALL.md`):

1. **Open the app** in your browser.
2. The **consent banner** appears on first visit. Click **Accept** to
   enable browser-local persistence (watchlists, portfolio, alerts,
   risk profile). Click **Decline** and EquityScope still works as a
   read-only research tool — it just won't remember anything between
   page reloads.
3. **Take the Risk Profile questionnaire** at `/risk-profile` (10
   questions, 2 minutes). Your bucket — Conservative, Moderate,
   Balanced, Growth, or Aggressive — tunes Buy/Watch/Avoid thresholds
   on every Recommendation.
4. **Search a ticker** in the top-bar search (e.g. `AAPL`,
   `MSFT.NASDAQ`, `RIO.LSE`). EquityScope auto-resolves global tickers
   across 23 exchanges + 14 currencies.
5. **Read the 8 tabs**:
   - **Snapshot** — price, MA, technicals, peer ranks
   - **Chart** — interactive candlesticks with overlays
   - **Value** — P/E, P/B, dividend yield with sector context
   - **Momentum** — RSI, ROC, MA cross signals
   - **Peers** — side-by-side metric matrix
   - **Events** — earnings dates, dividends, splits
   - **Recommendation** — scenario-based Buy/Watch/Avoid + bucket chip
   - **Sources** — every metric's provider URL + freshness
6. **Add to a watchlist.** Click the ⭐ icon next to the ticker.
7. **Set an alert** at `/alerts` (e.g. "AAPL crosses below 50D MA").

Done. Each subsequent ticker is a 30-second deep dive.

---

## Concepts

### Data sources

EquityScope uses **only free public providers**. No API keys. No
scraping. No paid feeds.

| Provider | Used for | Latency | Notes |
| --- | --- | --- | --- |
| **Stooq** | Daily OHLCV bars | EOD | Primary historical source. Free, redistributable. |
| **yfinance** | OHLCV (fallback), fundamentals, news, events, FX | Real-time-ish (15-min delay typical) | Wraps Yahoo Finance public endpoints. |

The `StooqYFinanceProvider` runs **both providers in parallel** and
**cross-validates** the last close within 2%. When both agree,
the result is marked `verified_source_count = 2` and confidence
upgrades to "high". A green ✓ surfaces in the UI.

### Scores (0–100)

Every analysed ticker gets five scores computed in pure Python by
`calc/scoring.py`. Weights are documented inline in the file and
explained in the `?` drawers next to each score:

| Score | Inputs | Higher = |
| --- | --- | --- |
| **Value** | P/E, P/B, dividend yield vs sector benchmarks | Cheaper relative to peers |
| **Momentum** | RSI 14, ROC 14D / 21D, 5D performance | Stronger near-term trend |
| **Quality** | Market cap, avg daily volume, price/book sanity | More liquid, more "real" |
| **Risk** | Distance from 52W high/low, volatility proxies | Higher number = MORE risk |
| **Data Confidence** | Field coverage + freshness + cross-validation | More fields fresh + verified |

### Recommendations

`calc/recommendation.py` runs a scenario-based engine that emits
**Buy / Watch / Avoid** plus base/upside/downside cases, technical
trigger, invalidation level, and time horizon. Thresholds tune per
**risk bucket** — see [Risk Profile](#risk-profile-risk-profile).

> **Important.** Every recommendation is rule-based and deterministic.
> No ML, no LLM, no neural net. The full threshold table lives in
> `calc/recommendation.py::RISK_THRESHOLDS` and is cited in
> SECURITY.md under the EU AI Act non-applicability declaration.

---

## Page-by-page

### Landing — `/`

Marketing page with feature highlights. Click "Open the app" to land
in the Screener.

### Screener — `/screener`

The top of the funnel. Discover tickers via filters, presets, and
saved custom queries.

**What you can do:**

- Pick a **preset**: "Cheap large-cap value", "High momentum mid-caps",
  "Quality dividend payers", etc. Each preset is a JSON filter spec
  in `screener/presets.py` — open the explainer drawer to see the
  exact criteria.
- Build a **custom screen** with any combination of: country, sector,
  industry, market-cap range, P/E range, dividend-yield floor, RSI
  band, ROC threshold, score floors. Save it via "Save current as
  preset" → it persists in `equityscope.customPresets` localStorage.
- **Sort** any column (price, MCap-USD, P/E, perf 5D, RSI, ROC, scores).
- **Toggle columns** via the ⚙️ menu. Choices persist in
  `equityscope.colState`.
- Click any row to drill into the **Stock Analysis** for that ticker.
- ⭐ icon next to any row adds the ticker to a watchlist.

**Performance.** Every preset run is capped at 60 enrichments to keep
latency bounded. The screener uses a "cheap-then-expensive" filter
strategy — country / sector / industry / market-cap pre-filter all
the cheap fields before any provider call fires. See PERFORMANCE.md
for response-time budgets.

### Stock Analysis — `/app`

The 8-tab deep dive. Mount with `?ticker=AAPL` or use the top-bar
search.

#### Tab 1 — Snapshot

Headline price card + 5 score bars + a peer-rank chip ("AAPL ranks 3
of 12 in Consumer Electronics on Momentum"). Source badges next to
every metric show provider + freshness.

#### Tab 2 — Chart

Interactive candlesticks via the self-hosted **Lightweight Charts**
library (no CDN, SHA-384 SRI checked at load). Overlays: 20D / 50D /
200D moving averages. Volume histogram below. Pinch-zoom + scroll-pan
on touch devices.

#### Tab 3 — Value

P/E (trailing + forward), Price-to-Book, Dividend Yield. Each metric
plotted against the sector mean + a peer scatter. The `?` drawer
explains the formula and cites the source.

#### Tab 4 — Momentum

RSI 14, ROC 14D, ROC 21D, 5D performance. Color-coded bands
(over-bought / over-sold). Cross-with-MA signals annotated.

#### Tab 5 — Peers

Side-by-side metric matrix vs ≤ 12 peers (auto-selected by sector +
industry, or override with `?peers=MSFT,NVDA,AMD`). Includes:

- P/E, Market Cap (USD), 5D Performance, RSI 14, ROC 14D / 21D
- % from 52W low, Price vs 200D MA
- All four scores + Data Confidence
- Peer rank for every metric (1 = best, N = worst)
- Four boolean summaries: cheaper / stronger momentum / higher data
  confidence / higher risk than peers

#### Tab 6 — Events

Earnings date, ex-dividend date, dividend pay date, splits — all from
yfinance's `.calendar` endpoint. Cached 4 hours.

#### Tab 7 — Recommendation

The scenario engine output:

- **Buy / Watch / Avoid** banner — color-coded
- **Bucket chip**: "Tuned for Conservative · Buy ≥ M75/V50/R≤30 ·
  change". Hover for the full threshold dict; click "change" to jump
  to `/risk-profile` and retake the questionnaire.
- **Confidence reason** — plain-English why this rating fired
- **Time horizon** — "1-3 months on momentum + technical
  confirmation; reassess at next earnings"
- **Base / Upside / Downside cases** — three side-by-side cards
- **Technical trigger** — what would shift the view bullish or
  bearish
- **Invalidation level** — the price that ends this thesis
- **Catalysts** — upcoming events + sector flows

> **The Recommendation is not financial advice.** It's a rule-based
> heuristic over public data. Read SECURITY.md for the full
> compliance disclosure.

#### Tab 8 — Sources

Every metric on the page with: value, provider name, source URL,
freshness chip ("real-time", "EOD", "cached 12 min"). Audit trail for
the entire analysis. Cross-validation status (Stooq+yfinance agree
within 2% → green ✓).

### Watchlists — `/watchlists`

Browser-local watchlist CRUD. Stored in `equityscope.watchlists`.

**Actions:**

- **Create** a named watchlist (default + as many custom as you want).
- **Add tickers** via the search box or the ⭐ icon on Screener /
  Analysis pages.
- **Remove** tickers via the row's ✖.
- **Live metrics**: every row refreshes price, perf 5D, RSI, ROC, %
  from low, and four scores when you visit the page.
- **Sort** any column.
- **Export ↓ CSV** — 20-column CSV with quoted strings + numeric
  coercion (added v0.22.0). Filename:
  `watchlist-<safeName>-<timestamp>.csv`.
- **Export ↓ JSON** — structured dump:
  `{watchlist, exportedAt, tickers, metrics}`. Filename:
  `watchlist-<safeName>-<timestamp>.json`.

### Portfolio — `/portfolio`

Browser-local portfolio with cost-basis P/L. Stored in
`equityscope.portfolio`.

**Actions:**

- **Add** a position: ticker, quantity, average cost, currency.
- **Live valuation**: pulls current price, computes unrealized P/L in
  the position's currency AND in your reporting currency (FX
  conversion via yfinance currency pairs, 6-hour cache).
- **Total**: sum of all positions in the reporting currency.
- **Sort** any column.
- **Edit / delete** individual positions.

### Compare — `/compare`

Side-by-side compare of up to 4 tickers across all metrics. Useful
for "should I buy AAPL or MSFT?" decisions.

**What you see:**

- Score grid for all 4 tickers stacked.
- Metric-by-metric table (price, MCap-USD, P/E, RSI, ROC, %from low,
  etc.).
- Best-in-row highlight (green) + worst-in-row (red).

### Events — `/events`

Calendar view of upcoming earnings, dividend, and ex-dividend dates
across either: a single ticker, a watchlist, or a screener result.

POST `/api/events/calendar` accepts up to 30 tickers per request to
keep latency bounded.

### News — `/news`

Headlines digest with rule-based sentiment. Pulls from yfinance's
`.news` endpoint, scored by a deterministic sentiment dictionary
(positive words: "beat", "raises", "outperform", etc.; negative
words: "missed", "downgrade", etc.). 15-minute cache.

> Sentiment is **NOT** an LLM or ML output. It's a rule-based
> heuristic — the dictionary lives in `providers/news.py`.

### Alerts — `/alerts`

Browser-local alerts engine with **11 alert kinds**:

1. Price crosses above N
2. Price crosses below N
3. Price crosses MA50 (above / below)
4. Price crosses MA200 (above / below)
5. RSI 14 crosses 70 (overbought)
6. RSI 14 crosses 30 (oversold)
7. ROC 14D crosses positive / negative
8. % move ≥ N% intraday
9. New 52W high
10. New 52W low
11. Volume spike ≥ N× 30D average

**How it works:**

- Stored in `equityscope.alerts` localStorage.
- **`alerts.js` runs a visibility-aware background poller on every
  user-facing page** (added v0.22.0) — switching tabs doesn't stop
  alerts from firing.
- When an alert triggers, you get an in-page toast + (with permission)
  an OS-level notification. Permission is requested only when you
  create your first alert.
- Per-alert cooldown to prevent spam.
- View / edit / delete alerts on the `/alerts` page.

### Risk Profile — `/risk-profile`

10-question questionnaire scored 0–100, mapped to one of five buckets:

- **Conservative** (0–20): Buy needs M ≥ 75, V ≥ 50, R ≤ 30, DC ≥ 70
- **Moderate** (21–40): Buy needs M ≥ 70, V ≥ 45, R ≤ 40, DC ≥ 55
- **Balanced** (41–60): Buy needs M ≥ 65, V ≥ 40, R ≤ 50, DC ≥ 40
- **Growth** (61–80): Buy needs M ≥ 55, V ≥ 30, R ≤ 65, DC ≥ 40
- **Aggressive** (81–100): Buy needs M ≥ 45, V ≥ 25, R ≤ 75, DC ≥ 35

Stored in `equityscope.riskProfile` localStorage. The active bucket
flows into every `/api/analyze/v2` POST and tunes Recommendation
thresholds. Retake the questionnaire any time — next analysis picks
up the new bucket immediately.

### Data Quality — `/data-quality`

Every metric on every analysis comes with a quality chip:

- **Source name** (Stooq / yfinance)
- **Freshness** ("real-time", "EOD", "cached 30 min", "stale > 1h")
- **Confidence** ("high" — cross-validated, "medium" — single source,
  "low" — fallback)

This page is the audit-mode view: shows quality across your most
recently analysed tickers + flags missing fields.

### Sources — `/sources`

Companion to Data Quality. Lists every metric → provider URL → click
to open the provider's page in a new tab. Useful for "wait, where
did that P/E number come from?" verification.

### Settings — `/settings`

- **Server info**: version, Python version, platform, URL prefix,
  trusted hosts, TLS state, auto-shutdown setting.
- **Cache stats**: live hit ratio + entry count.
- **Clear cache**: forces every TTLCache to drop all entries. Useful
  when troubleshooting stale data.
- **Reporting currency**: change the currency used to value your
  portfolio in the global P/L total.

### Privacy — `/privacy`

Plain-English privacy policy:

- Article 6 lawful basis (consent + legitimate interest)
- Articles 15-22 data subject rights (access, rectification, erasure,
  data portability, object, automated decision-making)
- International transfers (none — data stays on your browser)
- **EU AI Act Article 3 declaration**: EquityScope contains no AI
  system. All "AI-like" features (sentiment, scoring, recommendation)
  are deterministic rule-based heuristics. Voluntary
  Article-50-style transparency despite non-applicability.
- **Wipe all data** button — deletes every `equityscope.*`
  localStorage key in one click.

---

## Daily workflows

### "What should I look at this morning?"

1. `/screener` → run preset "High momentum mid-caps".
2. ⭐ the top 5 unfamiliar names into a watchlist called "morning
   ideas".
3. `/watchlists/morning-ideas` → click the first row.
4. Read the **Recommendation** tab → if Buy/Watch, drill into
   Snapshot → Chart → Peers.
5. Set an alert: "price crosses below 50D MA" as a stop-out.

### "Is my portfolio overweight any sector?"

1. `/portfolio` → note the largest-weighted positions.
2. `/compare` → load all five into the compare grid.
3. Look at the Sector row. If they're all the same sector, you're
   concentrated.

### "Did anything happen overnight?"

1. `/news` → top 20 headlines for your watchlist tickers, sentiment-
   tagged.
2. `/events` → any earnings or ex-div dates today?
3. `/alerts` → any alerts triggered since you last checked?

### "Should I buy AAPL today?"

1. `/app?ticker=AAPL`
2. **Recommendation** tab → read the rating + bucket chip.
3. If Watch / Avoid → read the **Confidence reason** to learn what's
   missing.
4. **Peers** tab → is AAPL cheap vs. its peers? Stronger momentum?
5. **Events** tab → earnings within 2 weeks? Wait.
6. **Sources** tab → cross-validation green ✓? If not, the data is
   single-source and your confidence should be lower.

---

## Keyboard shortcuts

| Key | Action |
| --- | --- |
| `/` | Focus the top-bar search |
| `Esc` | Close any open drawer / modal |
| `?` | Open the explainer drawer for the current page |
| `1`–`8` | Switch tabs on the Stock Analysis page |
| `↑` / `↓` | Move row selection on Screener / Watchlists |
| `Enter` | Open the selected ticker in Stock Analysis |

---

## Data freshness

| Layer | TTL | Why |
| --- | --- | --- |
| Historical OHLCV | 30 min | EOD data — refresh between sessions |
| Fundamentals | 30 min | yfinance `.info` snapshot |
| Events | 4 hours | Earnings dates change rarely |
| News | 15 min | Headlines turn over fast |
| FX rates | 6 hours | Mid-day drift acceptable for screening |
| Enriched StockMetrics (composite) | 30 min | Sum of the above |

The cache is **in-memory only**. Server restart = empty cache. This
is intentional — see SECURITY.md threat model.

---

## Privacy + compliance

- **No login**, no auth, no SaaS backend.
- **No telemetry**, no analytics, no third-party scripts.
- **All state lives in your browser's localStorage** under the
  `equityscope.*` namespace.
- **Wipe with one click** at `/privacy`.
- **GDPR-compliant** — Article 6 lawful basis (consent), Articles
  15-22 data subject rights documented.
- **EU AI Act Article 3**: EquityScope contains no AI system. All
  scoring / sentiment / recommendation logic is deterministic and
  documented in source.
- **RFC 9116 security.txt** at `/.well-known/security.txt` for
  coordinated disclosure.

Full threat model in SECURITY.md.

---

## Troubleshooting

| Symptom | Fix |
| --- | --- |
| "Invalid ticker" on a known symbol | Try the exchange suffix: `AAPL.US`, `RIO.LSE`, `7203.JP`. |
| Data Confidence stuck at "low" | Provider returned a sparse `.info` payload. Try again in 5 minutes — yfinance occasionally throttles. |
| Recommendation banner says "Watch — data confidence too low" | Same as above. Quality is a function of field coverage; missing fields drop DC. |
| Watchlist doesn't persist after browser restart | Consent banner declined? Re-visit `/privacy` and accept. |
| Alerts don't fire | Browser tab fully closed = no poller. Keep at least one EquityScope tab open in the background. Check OS notification permission. |
| Charts blank on `/app` | Check browser console for SRI mismatch. Vendor JS is integrity-locked at SHA-384 — a stale browser cache can break the load. Hard reload: Cmd+Shift+R / Ctrl+Shift+F5. |
| `/api/analyze/v2` returns 500 | Provider rate-limited. Wait 60 seconds. If persistent, drop into Settings → Clear cache. |

---

## Glossary

- **Cross-validation** — Two providers (Stooq + yfinance) deliver the
  same metric and agree within 2%. Result marked
  `verified_source_count = 2`.
- **Data Confidence** — A 0–100 score combining field coverage +
  freshness + cross-validation. Below 40 forces Recommendation to
  "Watch" regardless of other scores.
- **Freshness** — How recently a value was fetched. "real-time" =
  this request, "EOD" = previous close, "cached" = served from
  TTLCache.
- **Risk Bucket** — One of Conservative / Moderate / Balanced /
  Growth / Aggressive. Tunes Recommendation thresholds.
- **TTLCache** — In-memory cache with per-entry time-to-live. Resets
  on server restart. No disk persistence.
- **Universe** — The full set of tickers EquityScope can resolve. ~5K
  rows across `data/universe.csv` and `data/universe_global.csv`.
