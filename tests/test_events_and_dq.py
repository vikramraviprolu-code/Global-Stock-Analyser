"""Tests for EventsProvider, /api/events, /api/events/calendar,
/api/data-quality/audit, /api/data-quality/stats, /events, /data-quality routes."""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pytest

from models import SourcedValue
from providers.events import EventsProvider, _date_str
from providers.cache import TTLCache


# ---------- EventsProvider unit ----------

def test_date_str_handles_iso_string():
    assert _date_str("2026-05-01T00:00:00Z") == "2026-05-01"


def test_date_str_handles_none():
    assert _date_str(None) is None


def test_date_str_handles_datetime():
    from datetime import datetime
    assert _date_str(datetime(2026, 5, 1)) == "2026-05-01"


def test_events_provider_returns_unavailable_keys_when_yfinance_missing(monkeypatch):
    """Ensure all expected keys exist even on a yfinance failure."""
    cache = TTLCache(default_ttl=60)
    p = EventsProvider(cache=cache)

    # Force yfinance import to raise inside fetch
    import builtins
    real_import = builtins.__import__
    def boom(name, *a, **kw):
        if name == "yfinance":
            raise ImportError("simulated")
        return real_import(name, *a, **kw)
    monkeypatch.setattr(builtins, "__import__", boom)

    out = p.fetch("AAPL")
    for key in ("earnings_date", "dividend_date",
                "ex_dividend_date", "split_date"):
        assert key in out
        sv = out[key]
        assert isinstance(sv, SourcedValue)
        assert sv.value is None or isinstance(sv.value, str)


# ---------- API integration ----------

@pytest.fixture
def client(monkeypatch):
    import app as app_module

    def stub_events_fetch(self, ticker):
        return {
            "earnings_date": SourcedValue(
                value="2026-05-15", source_name="Yahoo Finance",
                source_url="https://finance.yahoo.com/quote/" + ticker + "/calendar",
                freshness="cached", confidence="medium", verified_source_count=1,
            ),
            "dividend_date": SourcedValue.unavailable("Yahoo Finance",
                "Dividend date not available."),
            "ex_dividend_date": SourcedValue(
                value="2026-05-20", source_name="Yahoo Finance",
                freshness="cached", confidence="medium", verified_source_count=1,
            ),
            "split_date": SourcedValue.unavailable("Yahoo Finance",
                "Split date not available."),
        }
    monkeypatch.setattr(
        "providers.events.EventsProvider.fetch", stub_events_fetch)

    app_module.app.testing = True
    return app_module.app.test_client()


def test_api_events_invalid_ticker(client):
    resp = client.get("/api/events?ticker=<bad>")
    assert resp.status_code == 400


def test_api_events_returns_payload(client):
    resp = client.get("/api/events?ticker=AAPL")
    assert resp.status_code == 200
    data = resp.get_json()
    assert data["ticker"] == "AAPL"
    assert "events" in data
    assert "earnings_date" in data["events"]
    assert data["events"]["earnings_date"]["value"] == "2026-05-15"


def test_api_events_calendar_rejects_empty(client):
    resp = client.post("/api/events/calendar", json={"tickers": []})
    assert resp.status_code == 400


def test_api_events_calendar_accepts_batch(client):
    resp = client.post("/api/events/calendar",
                       json={"tickers": ["AAPL", "MSFT"]})
    assert resp.status_code == 200
    data = resp.get_json()
    assert "events" in data
    assert "AAPL" in data["events"]
    assert "MSFT" in data["events"]


def test_api_data_quality_audit_returns_shape(client):
    resp = client.get("/api/data-quality/audit")
    assert resp.status_code == 200
    data = resp.get_json()
    for key in ("audit_rows", "row_count", "freshness_counts",
                "tickers_covered", "ticker_count", "ticker_status",
                "cache_stats", "next_refresh_seconds"):
        assert key in data


def test_api_data_quality_stats_returns_shape(client):
    resp = client.get("/api/data-quality/stats")
    assert resp.status_code == 200
    data = resp.get_json()
    for key in ("total_metrics", "tickers_covered", "freshness_counts"):
        assert key in data


def test_data_quality_route_renders(client):
    resp = client.get("/data-quality")
    assert resp.status_code == 200
    assert b"Data Quality Command Center" in resp.data


def test_events_route_renders(client):
    resp = client.get("/events")
    assert resp.status_code == 200
    assert b"Events" in resp.data
