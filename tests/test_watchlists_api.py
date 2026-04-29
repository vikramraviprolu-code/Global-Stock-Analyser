"""Tests for the new v0.9.0 endpoints: /api/metrics, /api/sparkline,
/watchlists, /compare. Network calls are mocked at the UniverseService
level so tests run offline."""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pytest

from providers.mock import MockProvider


@pytest.fixture
def client(monkeypatch):
    """Patch UniverseService.enrich_ticker to use MockProvider so /api/metrics
    works without network. Patch fetch_history_for to return synthetic data."""
    import app as app_module
    mock = MockProvider()

    def mock_enrich_ticker(self, ticker, allow_mock_fallback=True):
        return mock.metrics_for(ticker)

    def mock_fetch_history(self, ticker):
        import pandas as pd
        from datetime import datetime, timedelta
        # 90 deterministic synthetic closes
        base = sum(ord(c) for c in ticker) % 50 + 50
        rows = []
        for i in range(90):
            d = datetime.now() - timedelta(days=89 - i)
            close = base + (i % 7) * 1.5 + (i * 0.1)
            rows.append({"Date": d, "Open": close, "High": close * 1.01,
                         "Low": close * 0.99, "Close": close, "Volume": 1_000_000})
        return pd.DataFrame(rows)

    monkeypatch.setattr(
        "providers.universe.UniverseService.enrich_ticker",
        mock_enrich_ticker,
    )
    monkeypatch.setattr(
        "providers.universe.UniverseService.fetch_history_for",
        mock_fetch_history,
    )

    app_module.app.testing = True
    return app_module.app.test_client()


def test_watchlists_route_renders(client):
    resp = client.get("/watchlists")
    assert resp.status_code == 200
    assert b"Watchlists" in resp.data


def test_compare_route_renders(client):
    resp = client.get("/compare")
    assert resp.status_code == 200
    assert b"Compare" in resp.data


def test_api_metrics_rejects_empty(client):
    resp = client.post(
        "/api/metrics",
        json={"tickers": []},
        headers={"Origin": "https://global-stock-analyser"},
    )
    assert resp.status_code == 400


def test_api_metrics_rejects_too_many(client):
    resp = client.post(
        "/api/metrics",
        json={"tickers": ["A"] * 50},
        headers={"Origin": "https://global-stock-analyser"},
    )
    assert resp.status_code == 400


def test_api_metrics_accepts_valid_batch(client):
    resp = client.post(
        "/api/metrics",
        json={"tickers": ["AAPL", "MSFT", "TCS.NS"]},
        headers={"Origin": "https://global-stock-analyser"},
    )
    assert resp.status_code == 200
    data = resp.get_json()
    assert "metrics" in data
    assert len(data["metrics"]) == 3
    tickers = [m["security"]["ticker"] for m in data["metrics"]]
    assert tickers == ["AAPL", "MSFT", "TCS.NS"]  # order preserved
    # Each metric carries scores
    for m in data["metrics"]:
        assert "scores" in m
        assert "value_score" in m["scores"]
        assert "momentum_score" in m["scores"]


def test_api_metrics_filters_invalid_tickers(client):
    resp = client.post(
        "/api/metrics",
        json={"tickers": ["AAPL", "<script>", ""]},
        headers={"Origin": "https://global-stock-analyser"},
    )
    assert resp.status_code == 200
    data = resp.get_json()
    assert len(data["metrics"]) == 1
    assert data["metrics"][0]["security"]["ticker"] == "AAPL"


def test_api_sparkline_rejects_invalid(client):
    resp = client.get("/api/sparkline?ticker=<script>")
    assert resp.status_code == 400


def test_api_sparkline_returns_closes(client):
    resp = client.get("/api/sparkline?ticker=AAPL&days=30")
    assert resp.status_code == 200
    data = resp.get_json()
    assert data["ticker"] == "AAPL"
    assert isinstance(data["closes"], list)
    assert len(data["closes"]) > 0
    assert data["min"] is not None
    assert data["max"] is not None
    assert data["first"] is not None
    assert data["last"] is not None


def test_api_sparkline_clamps_days(client):
    """days < 20 should be clamped to 20."""
    resp = client.get("/api/sparkline?ticker=MSFT&days=5")
    assert resp.status_code == 200
    data = resp.get_json()
    assert len(data["closes"]) >= 20  # at least 20 even though we asked for 5


def test_api_metrics_rejects_unknown_origin(client):
    """CSRF: cross-origin POST should be allowed for /api/metrics — it's
    read-only — but ensure no Origin doesn't 403 either (this is a metrics
    fetch, not a state-change like /api/shutdown)."""
    resp = client.post(
        "/api/metrics",
        json={"tickers": ["AAPL"]},
    )
    # No CSRF check on /api/metrics (read-only endpoint), so 200 expected
    assert resp.status_code == 200
