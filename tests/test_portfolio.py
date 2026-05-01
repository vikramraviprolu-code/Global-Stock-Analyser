"""Tests for /portfolio route and /api/fx + /api/fx/batch endpoints."""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pytest


@pytest.fixture
def client(monkeypatch):
    """Stub markets.fx_rate so tests run offline."""
    import app as app_module
    import markets as markets_module

    def stub_fx(from_ccy, to_ccy="USD"):
        if from_ccy == to_ccy:
            return 1.0
        # deterministic table for known pairs
        rates = {
            ("INR", "USD"): 0.012,
            ("EUR", "USD"): 1.08,
            ("GBP", "USD"): 1.27,
            ("JPY", "USD"): 0.0067,
            ("USD", "EUR"): 0.93,
            ("USD", "INR"): 83.0,
        }
        return rates.get((from_ccy, to_ccy))
    monkeypatch.setattr(markets_module, "fx_rate", stub_fx)

    app_module.app.testing = True
    return app_module.app.test_client()


def test_portfolio_route_renders(client):
    resp = client.get("/portfolio")
    assert resp.status_code == 200
    body = resp.data.decode()
    # Page presence checks
    assert "Portfolio" in body
    assert "Add Holding" in body
    assert 'id="pf-table"' in body
    assert 'id="pf-totals"' in body
    # JS helpers loaded
    assert "portfolio.js" in body
    assert "ui.js" in body


def test_fx_invalid_codes(client):
    # 4-letter code rejected
    resp = client.get("/api/fx?from=USDX&to=EUR")
    assert resp.status_code == 400
    # contains digit
    resp = client.get("/api/fx?from=US1&to=EUR")
    assert resp.status_code == 400
    # too short
    resp = client.get("/api/fx?from=US&to=EUR")
    assert resp.status_code == 400


def test_fx_same_currency_returns_one(client):
    resp = client.get("/api/fx?from=USD&to=USD")
    assert resp.status_code == 200
    data = resp.get_json()
    assert data["rate"] == 1.0
    assert data["from"] == "USD"
    assert data["to"] == "USD"


def test_fx_known_pair(client):
    resp = client.get("/api/fx?from=INR&to=USD")
    assert resp.status_code == 200
    data = resp.get_json()
    assert data["rate"] == 0.012
    assert data["freshness"] == "cached"
    assert data["source_name"] == "Yahoo Finance"
    assert "INRUSD=X" in data["source_url"]


def test_fx_unknown_pair_returns_unavailable(client):
    """Unknown pair returns 200 with rate=null + warning, not 500."""
    resp = client.get("/api/fx?from=ZZZ&to=USD")
    # Format-valid 3-letter codes pass regex; rate may be None from provider
    assert resp.status_code == 200
    data = resp.get_json()
    assert data["rate"] is None
    assert data["freshness"] == "unavailable"


def test_fx_batch_rejects_empty(client):
    resp = client.post("/api/fx/batch", json={"pairs": []})
    assert resp.status_code == 400


def test_fx_batch_rejects_too_many(client):
    pairs = [{"from": "USD", "to": "EUR"}] * 50
    resp = client.post("/api/fx/batch", json={"pairs": pairs})
    assert resp.status_code == 400


def test_fx_batch_returns_rates(client):
    resp = client.post("/api/fx/batch", json={
        "pairs": [
            {"from": "INR", "to": "USD"},
            {"from": "EUR", "to": "USD"},
            {"from": "GBP", "to": "USD"},
        ],
    })
    assert resp.status_code == 200
    data = resp.get_json()
    assert "rates" in data
    assert data["rates"]["INR_USD"] == 0.012
    assert data["rates"]["EUR_USD"] == 1.08
    assert data["rates"]["GBP_USD"] == 1.27


def test_fx_batch_filters_invalid_pairs(client):
    """Invalid currency codes are dropped silently; valid pairs still resolve."""
    resp = client.post("/api/fx/batch", json={
        "pairs": [
            {"from": "INR", "to": "USD"},
            {"from": "BAD", "to": "USD2"},  # invalid 'to' length
            {"from": "EUR", "to": "USD"},
            {},  # malformed
        ],
    })
    assert resp.status_code == 200
    data = resp.get_json()
    assert "INR_USD" in data["rates"]
    assert "EUR_USD" in data["rates"]
    assert len(data["rates"]) == 2


def test_portfolio_link_in_nav(client):
    """Portfolio link appears in nav (no longer disabled placeholder)."""
    resp = client.get("/screener")
    body = resp.data.decode()
    assert "/portfolio" in body
    # Confirm it's not the disabled placeholder
    assert 'aria-disabled="true">Portfolio' not in body
