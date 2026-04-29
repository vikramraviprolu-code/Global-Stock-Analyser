"""Tests for parallel Stooq+yfinance cross-validation."""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pandas as pd
from datetime import datetime, timedelta

from providers.historical import StooqYFinanceProvider
from providers.cache import TTLCache


def _make_df(closes):
    rows = []
    for i, c in enumerate(closes):
        d = datetime.now() - timedelta(days=len(closes) - 1 - i)
        rows.append({"Date": d, "Open": c, "High": c * 1.01,
                     "Low": c * 0.99, "Close": c, "Volume": 1_000_000})
    return pd.DataFrame(rows)


def test_verified_count_2_when_both_sources_agree(monkeypatch):
    """When Stooq + yfinance return matching last closes → verified=2."""
    cache = TTLCache(default_ttl=60)
    p = StooqYFinanceProvider(cache=cache)

    monkeypatch.setattr(p, "_fetch_stooq",
                        lambda sym: _make_df([100.0, 101.0, 102.0]))
    monkeypatch.setattr(p, "_fetch_yfinance",
                        lambda ticker: _make_df([100.0, 101.0, 102.10]))  # 0.1% diff
    df = p.fetch("AAPL")
    assert df is not None
    assert p.verified_count_for("AAPL") == 2


def test_verified_count_1_when_sources_disagree(monkeypatch):
    """Last close diff > 2% → verified=1 (still trust the chosen primary)."""
    cache = TTLCache(default_ttl=60)
    p = StooqYFinanceProvider(cache=cache)

    monkeypatch.setattr(p, "_fetch_stooq",
                        lambda sym: _make_df([100.0, 101.0, 80.0]))   # very different
    monkeypatch.setattr(p, "_fetch_yfinance",
                        lambda ticker: _make_df([100.0, 101.0, 102.0]))
    df = p.fetch("AAPL")
    assert df is not None
    assert p.verified_count_for("AAPL") == 1


def test_verified_count_1_when_only_yfinance(monkeypatch):
    cache = TTLCache(default_ttl=60)
    p = StooqYFinanceProvider(cache=cache)

    monkeypatch.setattr(p, "_fetch_stooq", lambda sym: None)  # Stooq gated
    monkeypatch.setattr(p, "_fetch_yfinance",
                        lambda ticker: _make_df([100.0, 101.0, 102.0]))
    df = p.fetch("AAPL")
    assert df is not None
    assert p.verified_count_for("AAPL") == 1


def test_verified_count_0_when_both_fail(monkeypatch):
    cache = TTLCache(default_ttl=60)
    p = StooqYFinanceProvider(cache=cache)

    monkeypatch.setattr(p, "_fetch_stooq", lambda sym: None)
    monkeypatch.setattr(p, "_fetch_yfinance", lambda ticker: None)
    df = p.fetch("AAPL")
    assert df is None
    assert p.verified_count_for("AAPL") == 0


def test_verified_count_2_with_stooq_only_falls_back_to_1(monkeypatch):
    """If only Stooq returns data, can't cross-validate → verified=1."""
    cache = TTLCache(default_ttl=60)
    p = StooqYFinanceProvider(cache=cache)

    monkeypatch.setattr(p, "_fetch_stooq",
                        lambda sym: _make_df([100.0, 101.0, 102.0]))
    monkeypatch.setattr(p, "_fetch_yfinance", lambda ticker: None)
    df = p.fetch("AAPL")
    assert df is not None
    assert p.verified_count_for("AAPL") == 1


def test_cache_hit_does_not_re_fetch(monkeypatch):
    """Second fetch should hit cache, no re-fetching."""
    cache = TTLCache(default_ttl=60)
    p = StooqYFinanceProvider(cache=cache)

    fetch_count = {"stooq": 0, "yf": 0}
    def stooq_fn(sym):
        fetch_count["stooq"] += 1
        return _make_df([100.0, 101.0, 102.0])
    def yf_fn(ticker):
        fetch_count["yf"] += 1
        return _make_df([100.0, 101.0, 102.0])
    monkeypatch.setattr(p, "_fetch_stooq", stooq_fn)
    monkeypatch.setattr(p, "_fetch_yfinance", yf_fn)
    p.fetch("AAPL")
    p.fetch("AAPL")
    assert fetch_count["stooq"] == 1  # only first call
    assert fetch_count["yf"] == 1
