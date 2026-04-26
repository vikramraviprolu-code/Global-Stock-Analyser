# EquityScope — Global Equity Research Dashboard

[![Python](https://img.shields.io/badge/python-3.9%2B-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/license-MIT-green.svg)](LICENSE)
[![Code style](https://img.shields.io/badge/code%20style-pep8-orange.svg)](https://peps.python.org/pep-0008/)
[![Status](https://img.shields.io/badge/status-beta-yellow.svg)]()

Free, no-API-key, open-source equity research dashboard. Type a ticker or company name,
get a structured investment analysis with value screening, momentum scan, peer
cross-analysis, and a transparent Buy / Watch / Avoid recommendation across **23+ global
exchanges** in **14 currencies**.

> **Disclaimer.** Informational and educational use only. Not financial advice. Data may
> be delayed, incomplete, or unavailable. See [LICENSE](LICENSE) for details.

---

## Features

- **Global ticker resolution** — type `AAPL`, `Reliance`, `Toyota`, `BMW.DE`, `7203.T`,
  or any supported listing. Ambiguous matches prompt a listing picker.
- **5 modules** — Overview, Value Screen, Momentum, Cross-Analysis, Recommendation.
- **14 indicators** — 52W high/low, 5D performance, MAs (20/50/200), RSI-14,
  ROC-14/21, average volume, % from low/high, currency, USD-normalized market cap.
- **Region-aware filters** — different price/volume thresholds per market (USA, India,
  Europe, Japan, HK, Korea, Taiwan, Singapore, Australia, China A-shares).
- **Tiered peer matching** — industry+country → industry+region → sector+country →
  sector+region → global industry → global sector.
- **Local + USD currency display** — prices in local currency; market caps shown in
  both with live FX overlay.
- **Transparent scoring** — every value/momentum/penalty rule is visible in the UI.
- **No fabricated data** — missing values render as "Data unavailable"; freshness
  labeled as Real-time / Delayed / Previous close / Historical only.

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
| China | Shanghai SE, Shenzhen SE | `.SS`, `.SZ` |
| Canada | TSX | `.TO` |

---

## Quick start

### Requirements

- Python 3.9+
- ~50 MB disk for dependencies

### Install & run

```bash
git clone https://github.com/vikramraviprolu-code/Global-Stock-Analyser.git
cd Global-Stock-Analyser
pip install -r requirements.txt
python app.py
```

Open http://127.0.0.1:5050 — landing page. Click **Launch App** or hit `/app` directly.

No API keys required. Data sourced from Stooq (CSV) with yfinance fallback.

### Docker (optional)

```bash
docker build -t global-stock-analyser .
docker run -p 5050:5050 global-stock-analyser
```

---

## Project layout

```
Global-Stock-Analyser/
├── app.py                 # Flask routes
├── analyzer.py            # Screening, scoring, peer discovery
├── market_data.py         # Stooq + yfinance OHLCV/fundamentals
├── markets.py             # Exchange suffix → region/currency, FX rates
├── resolver.py            # Ticker/name search + disambiguation
├── data/
│   ├── universe.csv       # Legacy US universe (120 tickers)
│   └── universe_global.csv  # Global multi-market universe (175 tickers)
├── templates/
│   ├── landing.html       # Marketing landing page
│   └── index.html         # Analysis dashboard
├── static/
│   ├── style.css          # Dashboard theme
│   └── landing.css        # Landing page theme
├── requirements.txt
├── LICENSE
└── README.md
```

---

## API reference

### `GET /api/search?q=<query>`

Resolve a ticker or company name to candidate listings.

```bash
curl "http://127.0.0.1:5050/api/search?q=Toyota"
```

```json
{
  "candidates": [
    {"ticker": "7203.T", "company": "Toyota Motor", "exchange": "TSE", "country": "Japan", "currency": "JPY", "industry": "Auto Manufacturers"},
    {"ticker": "TM", "company": "Toyota Motor Corporation", "exchange": "NYSE", "country": "USA", "currency": "USD"}
  ],
  "needs_choice": true
}
```

### `POST /api/analyze`

Run the full analysis pipeline on a resolved listing.

```bash
curl -X POST http://127.0.0.1:5050/api/analyze \
  -H "Content-Type: application/json" \
  -d '{"ticker": "RELIANCE.NS"}'
```

Response includes: `input` (snapshot + indicators), `value_hits`, `momentum_hits`, `cross`,
`score` (transparent breakdown), `narrative` (bull/bear/base/catalysts/risks),
`recommendation`, `freshness`, `peer_tier`, `fx_to_usd`, `regional_filter`.

---

## Scoring model

Fully transparent — every increment surfaces in the UI.

**Value (max 4)**
- `+1` price within 10% of 52-week low
- `+1` trailing P/E ≤ 10
- `+1` market cap ≥ regional minimum (USD-normalized)
- `+1` P/E below peer median

**Momentum (max 7)**
- `+1` 5D performance positive
- `+1` ROC 14D positive
- `+1` ROC 21D positive
- `+1` RSI between 40 and 70
- `+1` price above 20D MA
- `+1` price above 50D MA
- `+1` price above 200D MA

**Penalties**
- `-1` RSI > 70 (overbought)
- `-1` price below 200D MA
- `-1` ROC 14D and 21D both negative
- Confidence reduced when key data is missing

**Recommendation**
- **Buy** — strong value AND momentum, no penalties; OR moderate value with strong momentum
- **Watch** — mixed signals or attractive setup pending confirmation
- **Avoid** — weak fundamentals, poor momentum, ≥ 2 penalties, or fails regional filters

---

## Regional filters

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

ETFs, funds, warrants, preferred shares excluded by name keyword.

---

## Data sources

| Type | Source | Notes |
| --- | --- | --- |
| OHLCV history | Stooq CSV → yfinance fallback | 2 years daily, no API key |
| Fundamentals | yfinance (`.info`) | Best effort; may be missing or rate-limited |
| FX rates | yfinance currency pairs | Cached 6 hours |
| Peer universe | Local curated CSV | 175 tickers, sector + industry tagged |

All caching is in-memory (30-min TTL for prices/fundamentals, 6-hour for FX). No
persistence layer.

---

## Known limitations

- **yfinance rate limits** — heavy concurrent fetches may hit Yahoo throttling. Cache
  helps; consider a `requests-cache` layer for production.
- **Stooq coverage** — Stooq CSV is now gated for many tickers; yfinance fallback handles
  the gap but adds latency.
- **Universe is curated, not exhaustive** — peer matching is limited to the ~175 tickers
  in `data/universe_global.csv`. Extend via PR.
- **Real-time data not available** — all prices are end-of-day from free sources.

---

## Contributing

PRs welcome. Common improvements:

1. **Extend the universe** — add tickers to [data/universe_global.csv](data/universe_global.csv)
   with `ticker, company, sector, industry, country, region, exchange, currency`.
2. **Add an indicator** — extend `compute_indicators()` in [market_data.py](market_data.py).
3. **Add a market** — extend `SUFFIX_MAP` and `REGIONAL_FILTERS` in [markets.py](markets.py).
4. **Improve the resolver** — extend `search()` in [resolver.py](resolver.py) with
   additional providers (e.g. Finnhub, Polygon free tier).

Run locally with:

```bash
pip install -r requirements.txt
python app.py
```

---

## License

[MIT](LICENSE). See license file for full text including financial-advice disclaimer.

---

## Acknowledgements

- [yfinance](https://github.com/ranaroussi/yfinance) — Yahoo Finance Python wrapper
- [Stooq](https://stooq.com/) — free OHLCV CSV data
- [Flask](https://flask.palletsprojects.com/) — web framework
- [pandas](https://pandas.pydata.org/) — indicator math
