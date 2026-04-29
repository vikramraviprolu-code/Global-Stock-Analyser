"""Tests for v2 analysis endpoints (/api/analyze/v2 + /api/ohlcv) and the
peer-matrix builder. Network calls are stubbed at the UniverseService level."""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pytest
import pandas as pd
from datetime import datetime, timedelta

from providers.mock import MockProvider


@pytest.fixture
def client(monkeypatch):
    import app as app_module
    mock = MockProvider()

    def mock_enrich_ticker(self, ticker, allow_mock_fallback=True):
        return mock.metrics_for(ticker)

    def mock_fetch_history(self, ticker):
        # 365 deterministic synthetic bars
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


# ---------- /api/ohlcv ----------

def test_ohlcv_invalid_ticker(client):
    resp = client.get("/api/ohlcv?ticker=<bad>")
    assert resp.status_code == 400


def test_ohlcv_default_returns_bars(client):
    resp = client.get("/api/ohlcv?ticker=AAPL")
    assert resp.status_code == 200
    data = resp.get_json()
    assert data["ticker"] == "AAPL"
    assert isinstance(data["bars"], list)
    assert len(data["bars"]) > 0
    bar = data["bars"][0]
    for key in ("time", "open", "high", "low", "close", "volume"):
        assert key in bar
    assert "has_ohlc" in data
    assert "first_date" in data
    assert "last_date" in data


def test_ohlcv_clamps_days(client):
    resp = client.get("/api/ohlcv?ticker=MSFT&days=5")
    data = resp.get_json()
    # min clamp 20 — but only have 365 bars total
    assert len(data["bars"]) >= 20


def test_ohlcv_max_days_capped(client):
    resp = client.get("/api/ohlcv?ticker=NVDA&days=99999")
    data = resp.get_json()
    # max_days clamp is 2500 in app.py — we only have 365 bars so should match
    assert len(data["bars"]) <= 2500


# ---------- /api/analyze/v2 ----------

def test_analyze_v2_invalid_ticker(client):
    resp = client.post("/api/analyze/v2", json={"ticker": "<bad>"})
    assert resp.status_code == 400


def test_analyze_v2_returns_full_payload(client):
    resp = client.post("/api/analyze/v2", json={"ticker": "AAPL"})
    assert resp.status_code == 200
    data = resp.get_json()
    assert "input" in data
    assert "peers" in data
    assert "peer_matrix" in data
    assert "history_source" in data
    # Input has scores + security
    assert "scores" in data["input"]
    assert "security" in data["input"]


def test_analyze_v2_peer_matrix_has_required_metrics(client):
    resp = client.post("/api/analyze/v2", json={"ticker": "AAPL"})
    data = resp.get_json()
    metrics = {r["metric"] for r in data["peer_matrix"]["rows"]}
    # PRD-required metrics
    for required in ["P/E", "Market Cap (USD)", "5D Performance",
                     "RSI 14", "ROC 14D", "ROC 21D", "% from 52W low",
                     "Price vs 200D MA", "Value Score", "Momentum Score",
                     "Quality Score", "Risk Score", "Data Confidence"]:
        assert required in metrics, f"missing metric: {required}"


def test_analyze_v2_peer_matrix_summary_keys(client):
    resp = client.post("/api/analyze/v2", json={"ticker": "AAPL"})
    data = resp.get_json()
    summary = data["peer_matrix"]["summary"]
    # PRD's four boolean comparisons
    for key in ["cheaper_than_peers", "stronger_momentum_than_peers",
                "higher_data_confidence_than_peers", "higher_risk_than_peers"]:
        assert key in summary


def test_analyze_v2_with_explicit_peers(client):
    resp = client.post("/api/analyze/v2",
                       json={"ticker": "AAPL", "peer_tickers": ["MSFT", "NVDA"]})
    data = resp.get_json()
    assert resp.status_code == 200
    peer_tickers = {p["security"]["ticker"] for p in data["peers"]}
    assert peer_tickers == {"MSFT", "NVDA"}


def test_analyze_v2_peer_rank_within_bounds(client):
    resp = client.post("/api/analyze/v2", json={"ticker": "AAPL"})
    data = resp.get_json()
    for r in data["peer_matrix"]["rows"]:
        if r["peer_rank"] is not None:
            assert 1 <= r["peer_rank"] <= r["peer_count"]


def test_index_route_renders(client):
    resp = client.get("/app")
    assert resp.status_code == 200
    # Check the v2 8-tab structure is present
    body = resp.data.decode()
    for tab in ("Snapshot", "Chart", "Value", "Momentum", "Peers", "Events", "Recommendation", "Sources"):
        assert tab in body
