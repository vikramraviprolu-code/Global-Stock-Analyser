"""Tests for v0.22.0 wire-up release:
1. Risk-bucket-aware Recommendation thresholds
2. /api/analyze/v2 risk_bucket payload validation
3. Watchlist export buttons present in template
4. alerts.js loaded on every user-facing template
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pytest
import pandas as pd
from datetime import datetime, timedelta

from models import SourcedValue
from calc.recommendation import (
    build_scenario,
    RISK_THRESHOLDS,
    DEFAULT_BUCKET,
    _thresholds_for,
)
from calc.scoring import score_all
from providers.mock import MockProvider


# ---------- helpers ----------

def sv(value, freshness="cached"):
    return SourcedValue(value=value, source_name="test",
                       freshness=freshness, confidence="high")


def make_metrics(price=110, ma20=100, ma50=95, ma200=85, high52=115, low52=70,
                 rsi=55, roc14=5, roc21=7, pe=8, pct_low=5):
    return {
        "price": sv(price), "ma20": sv(ma20), "ma50": sv(ma50), "ma200": sv(ma200),
        "fifty_two_week_high": sv(high52), "fifty_two_week_low": sv(low52),
        "rsi14": sv(rsi), "roc14": sv(roc14), "roc21": sv(roc21),
        "trailing_pe": sv(pe), "percent_from_low": sv(pct_low),
        "five_day_performance": sv(2.0),
        "market_cap_usd": sv(50_000_000_000),
        "avg_daily_volume": sv(2_000_000),
        "dividend_yield": sv(2.0),
        "price_to_book": sv(3.0),
        "security": {"sector": "Technology", "currency": "USD"},
    }


# ---------- 1. Risk-bucket thresholds ----------

def test_risk_thresholds_has_all_five_buckets():
    for bucket in ("conservative", "moderate", "balanced", "growth", "aggressive"):
        assert bucket in RISK_THRESHOLDS
        th = RISK_THRESHOLDS[bucket]
        for key in ("buy_value", "buy_momentum", "buy_risk_max",
                    "buy_dc_min", "avoid_momentum", "avoid_risk"):
            assert key in th, f"{bucket} missing {key}"


def test_thresholds_for_unknown_bucket_falls_back_to_default():
    assert _thresholds_for(None) == RISK_THRESHOLDS[DEFAULT_BUCKET]
    assert _thresholds_for("not_a_bucket") == RISK_THRESHOLDS[DEFAULT_BUCKET]
    assert _thresholds_for("balanced") == RISK_THRESHOLDS["balanced"]


def test_conservative_stricter_than_aggressive():
    """Conservative bucket should require higher value/momentum and lower risk than aggressive."""
    cons = RISK_THRESHOLDS["conservative"]
    aggr = RISK_THRESHOLDS["aggressive"]
    assert cons["buy_value"] > aggr["buy_value"]
    assert cons["buy_momentum"] > aggr["buy_momentum"]
    assert cons["buy_risk_max"] < aggr["buy_risk_max"]
    assert cons["buy_dc_min"] > aggr["buy_dc_min"]


def test_scenario_returns_risk_bucket_metadata():
    m = make_metrics()
    scores = score_all(m)
    sc = build_scenario(m, scores, risk_bucket="growth")
    assert sc["risk_bucket"] == "growth"
    assert sc["thresholds_used"] == RISK_THRESHOLDS["growth"]


def test_scenario_default_bucket_when_none_passed():
    m = make_metrics()
    scores = score_all(m)
    sc = build_scenario(m, scores)
    assert sc["risk_bucket"] == DEFAULT_BUCKET


def test_scenario_aggressive_more_likely_buy_than_conservative():
    """Same mediocre setup → aggressive may Buy where conservative says Watch."""
    m = make_metrics(price=105, ma50=100, ma200=95, rsi=60, roc14=2, roc21=3,
                     pe=18, pct_low=20)
    scores = score_all(m)
    sc_cons = build_scenario(m, scores, risk_bucket="conservative")
    sc_aggr = build_scenario(m, scores, risk_bucket="aggressive")
    # Aggressive rating should be at least as bullish as conservative.
    rank = {"Avoid": 0, "Watch": 1, "Buy": 2}
    assert rank[sc_aggr["final_rating"]] >= rank[sc_cons["final_rating"]]


def test_scenario_reason_includes_bucket_label():
    m = make_metrics()
    scores = score_all(m)
    sc = build_scenario(m, scores, risk_bucket="conservative")
    assert "Conservative" in sc["confidence_reason"] or sc["final_rating"] == "Watch"


# ---------- 2. /api/analyze/v2 risk_bucket payload ----------

@pytest.fixture
def client(monkeypatch):
    import app as app_module
    mock = MockProvider()

    def mock_enrich_ticker(self, ticker, allow_mock_fallback=True):
        return mock.metrics_for(ticker)

    def mock_fetch_history(self, ticker):
        base = sum(ord(c) for c in ticker) % 50 + 50
        rows = []
        for i in range(365):
            d = datetime.now() - timedelta(days=364 - i)
            close = base + (i % 7) * 1.5 + (i * 0.1)
            rows.append({
                "Date": d, "Open": close * 0.99, "High": close * 1.02,
                "Low": close * 0.98, "Close": close, "Volume": 1_000_000,
            })
        return pd.DataFrame(rows)

    def mock_rows(self):
        return [
            {"ticker": "AAPL", "company": "Apple", "sector": "Technology",
             "industry": "Consumer Electronics", "country": "USA",
             "region": "Americas", "exchange": "Nasdaq", "currency": "USD"},
            {"ticker": "MSFT", "company": "Microsoft", "sector": "Technology",
             "industry": "Software", "country": "USA",
             "region": "Americas", "exchange": "Nasdaq", "currency": "USD"},
            {"ticker": "NVDA", "company": "NVIDIA", "sector": "Technology",
             "industry": "Semiconductors", "country": "USA",
             "region": "Americas", "exchange": "Nasdaq", "currency": "USD"},
        ]

    monkeypatch.setattr("providers.universe.UniverseService.enrich_ticker", mock_enrich_ticker)
    monkeypatch.setattr("providers.universe.UniverseService.fetch_history_for", mock_fetch_history)
    monkeypatch.setattr("providers.universe.UniverseService.rows", mock_rows)

    app_module.app.testing = True
    return app_module.app.test_client()


def test_analyze_v2_accepts_valid_risk_bucket(client):
    resp = client.post("/api/analyze/v2",
                       json={"ticker": "AAPL", "risk_bucket": "growth"})
    assert resp.status_code == 200
    data = resp.get_json()
    sc = data.get("scenario") or {}
    # Bucket should round-trip into the scenario dict
    assert sc.get("risk_bucket") == "growth"


def test_analyze_v2_ignores_unknown_risk_bucket(client):
    """Unknown bucket must fall back to default — never 500."""
    resp = client.post("/api/analyze/v2",
                       json={"ticker": "AAPL", "risk_bucket": "yolo_mode"})
    assert resp.status_code == 200
    data = resp.get_json()
    sc = data.get("scenario") or {}
    assert sc.get("risk_bucket") == DEFAULT_BUCKET


def test_analyze_v2_no_risk_bucket_uses_default(client):
    resp = client.post("/api/analyze/v2", json={"ticker": "AAPL"})
    assert resp.status_code == 200
    data = resp.get_json()
    sc = data.get("scenario") or {}
    assert sc.get("risk_bucket") == DEFAULT_BUCKET


# ---------- 3. Watchlist export buttons ----------

def test_watchlists_template_has_export_buttons():
    path = os.path.join(os.path.dirname(__file__), "..",
                        "templates", "watchlists.html")
    with open(path, "r") as f:
        body = f.read()
    assert 'id="export-csv"' in body, "missing CSV export button"
    assert 'id="export-json"' in body, "missing JSON export button"
    assert "exportWatchlist" in body, "missing exportWatchlist function"


def test_recommendation_renders_bucket_chip():
    """Index.html must show a chip with the active bucket label + thresholds."""
    path = os.path.join(os.path.dirname(__file__), "..",
                        "templates", "index.html")
    with open(path, "r") as f:
        body = f.read()
    assert "rec-bucket-chip" in body, "missing bucket chip class"
    assert "Tuned for" in body, "missing 'Tuned for' chip text"
    assert "thresholds_used" in body, "chip must read thresholds_used"


def test_analysis_css_has_bucket_chip_style():
    path = os.path.join(os.path.dirname(__file__), "..",
                        "static", "analysis.css")
    with open(path, "r") as f:
        body = f.read()
    assert ".rec-bucket-chip" in body, "missing .rec-bucket-chip CSS rule"


# ---------- 4. alerts.js loaded on every user-facing template ----------

USER_TEMPLATES = [
    "index.html", "watchlists.html", "screener.html", "compare.html",
    "events.html", "news.html", "data_quality.html", "sources.html",
    "settings.html", "portfolio.html", "risk_profile.html", "privacy.html",
]


@pytest.mark.parametrize("tmpl", USER_TEMPLATES)
def test_alerts_js_injected_in_template(tmpl):
    path = os.path.join(os.path.dirname(__file__), "..", "templates", tmpl)
    if not os.path.exists(path):
        pytest.skip(f"{tmpl} not present")
    with open(path, "r") as f:
        body = f.read()
    assert "alerts.js" in body, f"{tmpl} missing alerts.js script tag"
