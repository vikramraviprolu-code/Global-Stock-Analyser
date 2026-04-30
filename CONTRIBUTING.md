# Contributing to EquityScope

Thanks for your interest. This project welcomes contributions of all sizes — from typo
fixes to new market integrations.

## Development setup

```bash
git clone https://github.com/vikramraviprolu-code/Global-Stock-Analyser.git
cd Global-Stock-Analyser
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
pip install ruff pytest  # dev tools
python app.py            # http://127.0.0.1:5050
```

## Where to contribute

| Want to... | Edit |
| --- | --- |
| Add a ticker | [data/universe_global.csv](data/universe_global.csv) — keep the `ticker, company, sector, industry, country, region, exchange, currency` shape |
| Add a market / exchange suffix | [markets.py](markets.py) — `SUFFIX_MAP` + `REGIONAL_FILTERS` |
| Add an indicator | [calc/indicators.py](calc/indicators.py) — pure-math, no DataFrame in the public API so it stays unit-testable |
| Tune scoring rules | [calc/scoring.py](calc/scoring.py) — every score is 0–100 with explicit `+/-` point deltas surfaced in `reasons` |
| Tune scenario recommendation | [calc/recommendation.py](calc/recommendation.py) — Base/Upside/Downside cases + Trigger/Invalidation |
| Add a screener filter kind | [screener/engine.py](screener/engine.py) — extend `Filter.CHEAP_KINDS` or `_check_metric()`, then expose in `templates/screener.html` and `app.py` `VALID_FILTER_KINDS` |
| Add a screener preset | [screener/presets.py](screener/presets.py) |
| Add a free data source | New file in `providers/`; wire into `UniverseService.__init__` |
| Improve resolver / search | [resolver.py](resolver.py) — `search()` |
| Add a page / API | New `templates/*.html` + new route in [app.py](app.py); add a nav link in [templates/_nav.html](templates/_nav.html) |
| Improve UI | [templates/](templates/) + [static/](static/). New per-page CSS file pattern is `static/<page>.css` |

## Coding standards

- **Python**: PEP 8, 4-space indent. Run `ruff check .` before pushing.
- **No fabricated data**. If a value is missing, return `None` (or
  `SourcedValue.unavailable(...)` with a clear `warning`) and let the UI render
  "Data unavailable". Never guess or interpolate fundamentals.
- **Always wrap fetched values in `SourcedValue`** so provenance (source name,
  URL, retrieved-at, freshness, confidence, verified count, warning) flows
  through to the UI badges and the Data Quality audit table.
- **No hard-coded secrets / API keys**. The project must remain free-to-run.
- **Backward compatibility**. The `/api/screener/run`, `/api/analyze/v2`,
  `/api/metrics`, `/api/ohlcv`, and `/api/events` response shapes are
  consumed by templates and tests — coordinate via PR if you change them.
- **Tests required** for any new calc / scoring / filter / endpoint. The
  suite (`pytest tests/ -q`) ships at 134 cases; aim to keep it green.

## Pull request checklist

1. Branch from `main`. Use a descriptive name: `feat/<thing>` or `fix/<thing>`.
2. Run the app locally and verify at least one ticker per affected market.
3. Update [README.md](README.md) if user-facing behavior changes.
4. Open a PR using the template; link any related issue.

## Releasing a new version

**Strict rule:** every version bump must update all docs in lock-step. See
[RELEASING.md](RELEASING.md) for the full checklist. The release script
won't push until every doc / version pin matches.

```bash
bash scripts/check_version_sync.sh
```

Required parity across:

- `pyproject.toml` — `version = "X.Y.Z"`
- `app.py` — `/api/settings/server-info` returns `"version": "X.Y.Z"`
- `README.md` — version badge + "What's new in vX.Y.Z" header
- `SECURITY.md` — "Latest: **vX.Y.Z**" line
- `CHANGELOG.md` — top entry `## [X.Y.Z] - YYYY-MM-DD`

## Commit style

Imperative mood, short subject (≤ 70 chars), optional body for context:

```
feat(markets): add Brazil B3 exchange (.SA suffix)

Adds B3 to SUFFIX_MAP with BRL currency and REGIONAL_FILTERS thresholds.
Tested with PETR4.SA, VALE3.SA, ITUB4.SA.
```

## Reporting bugs

Open an issue using the bug-report template. Include the ticker, market, browser, and
server logs so it's reproducible.

## Code of conduct

Be respectful. Assume good faith. No harassment.
