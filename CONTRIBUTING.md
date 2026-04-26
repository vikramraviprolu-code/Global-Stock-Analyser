# Contributing to EquityScope

Thanks for your interest. This project welcomes contributions of all sizes — from typo
fixes to new market integrations.

## Development setup

```bash
git clone https://github.com/vikramraviprolu-code/equityscope.git
cd equityscope
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
pip install ruff pytest  # dev tools
python app.py            # http://127.0.0.1:5050
```

## Where to contribute

| Want to... | Edit |
| --- | --- |
| Add a ticker | [data/universe_global.csv](data/universe_global.csv) |
| Add a market / exchange suffix | [markets.py](markets.py) — `SUFFIX_MAP` + `REGIONAL_FILTERS` |
| Add an indicator | [market_data.py](market_data.py) — `compute_indicators()` |
| Tune scoring rules | [analyzer.py](analyzer.py) — `score_input_stock()` |
| Improve resolver / search | [resolver.py](resolver.py) — `search()` |
| Improve UI | [templates/](templates/) + [static/](static/) |

## Coding standards

- **Python**: PEP 8, 4-space indent. Run `ruff check .` before pushing.
- **No fabricated data**. If a value is missing, return `None` and let the UI render
  "Data unavailable". Never guess or interpolate fundamentals.
- **No hard-coded secrets / API keys**. The project must remain free-to-run.
- **Backward compatibility**. The `/api/analyze` and `/api/search` response shapes are
  consumed by the frontend — coordinate via PR if you change them.

## Pull request checklist

1. Branch from `main`. Use a descriptive name: `feat/<thing>` or `fix/<thing>`.
2. Run the app locally and verify at least one ticker per affected market.
3. Update [README.md](README.md) if user-facing behavior changes.
4. Open a PR using the template; link any related issue.

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
