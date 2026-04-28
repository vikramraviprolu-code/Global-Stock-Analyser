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
    filters = get_preset("value_near_low")
    assert len(filters) >= 2
    kinds = [f.kind for f in filters]
    assert "pct_from_low_max" in kinds
    assert "pe_max" in kinds


def test_preset_unknown_returns_empty():
    assert get_preset("does_not_exist") == []


def test_list_presets_includes_built_ins():
    presets = list_presets()
    keys = {p["key"] for p in presets}
    assert "value_near_low" in keys
    assert "momentum_top" in keys
    assert "indian_banks" in keys


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
