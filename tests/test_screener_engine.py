"""Screener engine tests using a stub UniverseService backed by MockProvider."""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from screener.engine import Filter, ScreenerEngine
from screener.presets import PRESETS, get_preset, list_presets
from providers.mock import MockProvider
from models import StockMetrics


class StubUniverse:
    """A tiny in-memory universe that bypasses the network. Returns mock
    metrics for the few rows we declare here."""

    def __init__(self):
        self.mock = MockProvider()
        self._rows = [
            {"ticker": "AAPL",  "company": "Apple",      "sector": "Technology",         "industry": "Consumer Electronics", "country": "USA",   "region": "Americas", "exchange": "Nasdaq", "currency": "USD"},
            {"ticker": "MSFT",  "company": "Microsoft",  "sector": "Technology",         "industry": "Software",             "country": "USA",   "region": "Americas", "exchange": "Nasdaq", "currency": "USD"},
            {"ticker": "JPM",   "company": "JPMorgan",   "sector": "Financial Services", "industry": "Banks",                "country": "USA",   "region": "Americas", "exchange": "NYSE",   "currency": "USD"},
            {"ticker": "TCS.NS","company": "TCS",        "sector": "Technology",         "industry": "IT Services",          "country": "India", "region": "Asia",     "exchange": "NSE",    "currency": "INR"},
            {"ticker": "7203.T","company": "Toyota",     "sector": "Consumer Cyclical",  "industry": "Auto Manufacturers",   "country": "Japan", "region": "Asia",     "exchange": "TSE",    "currency": "JPY"},
        ]

    def rows(self):
        return self._rows

    def enrich_many(self, rows, max_workers=8):
        # Bypass network entirely — return deterministic mock metrics
        out = []
        for r in rows:
            out.append(self.mock.metrics_for(
                r["ticker"], r["sector"], r["industry"],
                r["country"], r["region"], r["exchange"], r["currency"],
            ))
        return out

    def enrich(self, row, allow_mock_fallback=True):
        return self.mock.metrics_for(
            row["ticker"], row["sector"], row["industry"],
            row["country"], row["region"], row["exchange"], row["currency"],
        )


def test_screener_country_filter():
    eng = ScreenerEngine(StubUniverse())
    res = eng.screen([Filter(kind="country_in", value=["USA"])])
    countries = {m.security.country for m in res.matches}
    assert countries == {"USA"}
    assert res.total_universe == 5
    assert res.after_cheap_filters == 3  # AAPL, MSFT, JPM


def test_screener_sector_filter():
    eng = ScreenerEngine(StubUniverse())
    res = eng.screen([Filter(kind="sector_in", value=["Technology"])])
    sectors = {m.security.sector for m in res.matches}
    assert sectors == {"Technology"}


def test_screener_combined_filters():
    eng = ScreenerEngine(StubUniverse())
    res = eng.screen([
        Filter(kind="region_in", value=["Asia"]),
        Filter(kind="sector_in", value=["Technology"]),
    ])
    tickers = {m.security.ticker for m in res.matches}
    assert "TCS.NS" in tickers
    assert "AAPL" not in tickers
    assert "7203.T" not in tickers


def test_screener_expensive_filter_pe_max():
    """All mock-generated PEs are between 5 and 40 — filter to ≤ 10."""
    eng = ScreenerEngine(StubUniverse())
    res = eng.screen([Filter(kind="pe_max", value=10.0)])
    for m in res.matches:
        assert m.trailing_pe.value <= 10.0
        assert m.trailing_pe.value > 0


def test_screener_no_filters_returns_error_path():
    """Engine with empty filter list → enriches all, no exclusions."""
    eng = ScreenerEngine(StubUniverse())
    res = eng.screen([])
    assert len(res.matches) == 5  # all pass


def test_preset_returns_filters():
    filters = get_preset("value_near_lows")
    assert len(filters) >= 2
    kinds = [f.kind for f in filters]
    assert "pct_from_low_max" in kinds
    assert "pe_max" in kinds


def test_preset_unknown_returns_empty():
    assert get_preset("does_not_exist") == []


def test_list_presets_includes_built_ins():
    presets = list_presets()
    keys = {p["key"] for p in presets}
    # PRD-required preset keys
    assert "value_near_lows" in keys
    assert "momentum_leaders" in keys
    assert "quality_large_caps" in keys
    assert "oversold_watchlist" in keys
    assert "breakout_candidates" in keys
    assert "data_reliable_only" in keys
    assert "indian_banks" in keys


def test_screener_currency_filter():
    eng = ScreenerEngine(StubUniverse())
    res = eng.screen([Filter(kind="currency_in", value=["USD"])])
    for m in res.matches:
        assert m.security.currency == "USD"


def test_screener_industry_filter():
    eng = ScreenerEngine(StubUniverse())
    res = eng.screen([Filter(kind="industry_in", value=["Banks"])])
    for m in res.matches:
        assert (m.security.industry or "").lower() == "banks"


def test_screener_above_ma20_filter():
    eng = ScreenerEngine(StubUniverse())
    res = eng.screen([Filter(kind="above_ma20", value=True)])
    for m in res.matches:
        assert m.price.value > m.ma20.value


def test_screener_pct_from_high_filter():
    eng = ScreenerEngine(StubUniverse())
    # "Within X% of 52W high" — every match must satisfy distance <= X
    res = eng.screen([Filter(kind="pct_from_high_max", value=20.0)])
    for m in res.matches:
        high = m.fifty_two_week_high.value
        price = m.price.value
        if high is not None and price is not None and high > 0:
            assert (high - price) / high * 100.0 <= 20.0


def test_screener_exclude_unavailable_pe():
    eng = ScreenerEngine(StubUniverse())
    res = eng.screen([Filter(kind="exclude_unavailable_pe", value=True)])
    for m in res.matches:
        assert m.trailing_pe.value is not None


def test_screener_score_aware_filter():
    """min_data_confidence requires the engine to have a score_fn."""
    from calc.scoring import score_all
    eng = ScreenerEngine(StubUniverse())
    # All mock metrics have freshness="mock" → confidence ~30. Filtering for >=80
    # should yield zero matches.
    res = eng.screen(
        [Filter(kind="min_data_confidence", value=80.0)],
        score_fn=lambda m: score_all({
            "price": m.price, "market_cap_usd": m.market_cap_usd,
            "trailing_pe": m.trailing_pe, "rsi14": m.rsi14, "roc14": m.roc14,
            "roc21": m.roc21, "ma20": m.ma20, "ma50": m.ma50, "ma200": m.ma200,
            "five_day_performance": m.five_day_performance,
            "percent_from_low": m.percent_from_low,
            "fifty_two_week_high": m.fifty_two_week_high,
            "fifty_two_week_low": m.fifty_two_week_low,
            "dividend_yield": m.dividend_yield, "price_to_book": m.price_to_book,
            "avg_daily_volume": m.avg_daily_volume,
            "security": m.security.to_dict(),
        }),
    )
    assert len(res.matches) == 0


def test_breakout_preset_uses_new_filter_kinds():
    filters = get_preset("breakout_candidates")
    kinds = {f.kind for f in filters}
    assert "above_ma20" in kinds
    assert "above_ma50" in kinds
    assert "pct_from_high_max" in kinds


def test_data_reliable_preset():
    filters = get_preset("data_reliable_only")
    kinds = {f.kind for f in filters}
    assert "min_data_confidence" in kinds
    assert "exclude_unavailable_pe" in kinds
    assert "exclude_stale" in kinds


def test_screener_result_to_dict_serialisable():
    eng = ScreenerEngine(StubUniverse())
    res = eng.screen([Filter(kind="country_in", value=["USA"])])
    d = res.to_dict()
    assert "matches" in d
    assert isinstance(d["matches"], list)
    if d["matches"]:
        first = d["matches"][0]
        assert "security" in first
        assert "price" in first
        assert "freshness" in first["price"]
