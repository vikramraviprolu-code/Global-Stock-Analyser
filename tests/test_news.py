"""Tests for NewsProvider + /api/news + /api/news/digest + /news route."""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pytest

from providers.news import (
    NewsProvider, _classify_sentiment, _classify_topic, _ts_to_iso,
)


# ---------- pure-Python helpers ----------

def test_classify_sentiment_bullish():
    assert _classify_sentiment("Apple stock surges on record earnings beat") == "bullish"
    assert _classify_sentiment("Microsoft upgrades guidance, raises outlook") == "bullish"


def test_classify_sentiment_bearish():
    assert _classify_sentiment("Tesla plunges after weak quarter and downgrade") == "bearish"
    assert _classify_sentiment("Lawsuit filed; SEC probe widens, layoffs ahead") == "bearish"


def test_classify_sentiment_neutral():
    assert _classify_sentiment("Apple announces new chip architecture") == "neutral"
    assert _classify_sentiment("") == "neutral"
    assert _classify_sentiment(None) == "neutral"


def test_classify_topic_earnings():
    assert _classify_topic("Q3 earnings beat consensus") == "earnings"
    assert _classify_topic("Quarterly revenue rises 12%") == "earnings"


def test_classify_topic_m_and_a():
    assert _classify_topic("Apple acquires AI startup") == "m_and_a"


def test_classify_topic_regulation():
    assert _classify_topic("DOJ launches antitrust probe") == "regulation"


def test_classify_topic_executive():
    assert _classify_topic("CEO steps down after board review") == "executive"


def test_classify_topic_general_fallback():
    assert _classify_topic("Stock analysis report") == "general"


def test_ts_to_iso_handles_unix_epoch():
    iso = _ts_to_iso(1714521600)  # 2024-05-01
    assert iso is not None
    assert "2024" in iso


def test_ts_to_iso_handles_none():
    assert _ts_to_iso(None) is None


def test_ts_to_iso_handles_garbage():
    assert _ts_to_iso("not-a-number") is None


# ---------- summarize ----------

def test_news_provider_summarize_empty():
    p = NewsProvider()
    s = p.summarize([])
    assert s["total"] == 0
    assert s["by_sentiment"]["bullish"] == 0
    assert "warning" in s


def test_news_provider_summarize_aggregates_buckets():
    p = NewsProvider()
    items = [
        {"title": "Apple beats earnings", "sentiment": "bullish", "topic": "earnings"},
        {"title": "Apple plunges on miss", "sentiment": "bearish", "topic": "earnings"},
        {"title": "Apple unveils new product", "sentiment": "neutral", "topic": "product"},
        {"title": "Apple acquires AI company", "sentiment": "bullish", "topic": "m_and_a"},
    ]
    s = p.summarize(items)
    assert s["total"] == 4
    assert s["by_sentiment"]["bullish"] == 2
    assert s["by_sentiment"]["bearish"] == 1
    assert s["by_sentiment"]["neutral"] == 1
    assert s["by_topic"]["earnings"] == 2
    assert s["by_topic"]["product"] == 1
    assert s["by_topic"]["m_and_a"] == 1
    # Samples capped at 3 per bucket
    assert len(s["samples"]["bullish"]) <= 3


def test_news_provider_fetch_returns_empty_on_yfinance_failure(monkeypatch):
    """Force yfinance import path to fail; provider still returns []."""
    import builtins
    real_import = builtins.__import__

    def boom(name, *a, **kw):
        if name == "yfinance":
            raise ImportError("simulated")
        return real_import(name, *a, **kw)
    monkeypatch.setattr(builtins, "__import__", boom)

    p = NewsProvider()
    items = p.fetch("AAPL")
    assert items == []


# ---------- API integration ----------

@pytest.fixture
def client(monkeypatch):
    import app as app_module

    def stub_fetch(self, ticker, max_items=15):
        return [
            {
                "title": f"{ticker} beats Q3 earnings expectations",
                "link": "https://example.com/1",
                "publisher": "Reuters",
                "published_at": "2026-04-30T12:00:00+00:00",
                "summary": "Strong revenue growth.",
                "sentiment": "bullish",
                "topic": "earnings",
                "ticker": ticker.upper(),
                "source_name": "Yahoo Finance",
                "source_url": "https://finance.yahoo.com",
            },
            {
                "title": f"Lawsuit filed against {ticker}",
                "link": "https://example.com/2",
                "publisher": "Bloomberg",
                "published_at": "2026-04-29T08:00:00+00:00",
                "summary": None,
                "sentiment": "bearish",
                "topic": "regulation",
                "ticker": ticker.upper(),
                "source_name": "Yahoo Finance",
                "source_url": "https://finance.yahoo.com",
            },
        ]
    monkeypatch.setattr("providers.news.NewsProvider.fetch", stub_fetch)

    app_module.app.testing = True
    return app_module.app.test_client()


def test_news_route_renders(client):
    resp = client.get("/news")
    assert resp.status_code == 200
    body = resp.data.decode()
    assert "Headline Digest" in body
    assert "news.js" not in body  # we didn't extract a separate JS bundle
    assert "ui.js" in body


def test_api_news_invalid_ticker(client):
    resp = client.get("/api/news?ticker=<bad>")
    assert resp.status_code == 400


def test_api_news_returns_items_and_digest(client):
    resp = client.get("/api/news?ticker=AAPL")
    assert resp.status_code == 200
    data = resp.get_json()
    assert data["ticker"] == "AAPL"
    assert isinstance(data["items"], list)
    assert len(data["items"]) == 2
    assert "digest" in data
    assert data["digest"]["total"] == 2
    assert data["digest"]["by_sentiment"]["bullish"] == 1
    assert data["digest"]["by_sentiment"]["bearish"] == 1


def test_api_news_max_clamps(client):
    """max param clamped to 1..30"""
    resp = client.get("/api/news?ticker=AAPL&max=999")
    assert resp.status_code == 200


def test_api_news_digest_rejects_empty(client):
    resp = client.post("/api/news/digest", json={"tickers": []})
    assert resp.status_code == 400


def test_api_news_digest_rejects_too_many(client):
    resp = client.post("/api/news/digest",
                       json={"tickers": ["A"] * 50})
    assert resp.status_code == 400


def test_api_news_digest_returns_per_ticker(client):
    resp = client.post("/api/news/digest",
                       json={"tickers": ["AAPL", "MSFT"], "max_per_ticker": 5})
    assert resp.status_code == 200
    data = resp.get_json()
    assert "news" in data
    assert "AAPL" in data["news"]
    assert "MSFT" in data["news"]
    assert len(data["news"]["AAPL"]) == 2


def test_news_link_in_nav(client):
    resp = client.get("/screener")
    body = resp.data.decode()
    assert "/news" in body


def test_sources_health_includes_news_provider(client):
    resp = client.get("/api/sources/health")
    data = resp.get_json()
    assert "news" in data["providers"]
    assert "yfinance" in data["providers"]["news"]["name"].lower()
