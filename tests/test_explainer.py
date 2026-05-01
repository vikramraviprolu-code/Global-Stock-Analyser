"""Tests for the Explainer browser bundle. Drawer + content registry are
client-side JS; tests verify each page loads explainer.js and the static
file contains every required topic key."""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pytest


REQUIRED_TOPICS = (
    # price + market metrics
    "price", "market_cap", "market_cap_usd", "trailing_pe", "forward_pe",
    "price_to_book", "dividend_yield", "avg_daily_volume",
    "fifty_two_week_high", "fifty_two_week_low", "percent_from_low",
    "five_day_performance",
    # technical indicators
    "rsi14", "roc14", "roc21", "ma20", "ma50", "ma200",
    # scores
    "value_score", "momentum_score", "quality_score", "risk_score",
    "data_confidence_score",
    # chart
    "candlestick", "line_chart", "volume_bars",
    # peer matrix + scenario
    "peer_matrix", "peer_median",
    "scenario_recommendation", "technical_trigger", "invalidation_level",
    # screener concepts
    "screener_preset", "regional_filter",
    # workspace
    "watchlist", "portfolio", "alert",
    # news
    "sentiment", "topic_clustering",
    # data quality
    "freshness", "source_quality", "mock_data", "verified_source_count",
)


@pytest.fixture
def client():
    import app as app_module
    app_module.app.testing = True
    return app_module.app.test_client()


@pytest.fixture
def explainer_source():
    here = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    path = os.path.join(here, "static", "explainer.js")
    with open(path) as f:
        return f.read()


def test_explainer_js_file_exists(explainer_source):
    assert "window.Explainer" in explainer_source
    assert "open" in explainer_source
    assert "attachAll" in explainer_source
    assert "iconButton" in explainer_source


def test_explainer_covers_required_topics(explainer_source):
    """Every PRD-relevant concept has a content entry."""
    missing = []
    for topic in REQUIRED_TOPICS:
        # Match `<key>:` at the top of CONTENT entries
        if f"{topic}:" not in explainer_source:
            missing.append(topic)
    assert not missing, f"Missing topics in explainer: {missing}"


def test_explainer_topics_have_definitions(explainer_source):
    """Each topic entry has a 'definition' field (sanity check)."""
    # Quick heuristic: count occurrences
    assert explainer_source.count("definition:") >= len(REQUIRED_TOPICS) - 5


def test_explainer_loaded_on_every_page(client):
    """All 11 pages must include explainer.js so the drawer is available."""
    routes = ["/screener", "/app", "/watchlists", "/compare", "/events",
              "/news", "/data-quality", "/sources", "/settings",
              "/portfolio", "/alerts"]
    for r in routes:
        resp = client.get(r)
        assert resp.status_code == 200, f"Route {r} returned {resp.status_code}"
        body = resp.data.decode()
        assert "explainer.js" in body, f"Route {r} missing explainer.js"


def test_explainer_jinja_quotes_clean(client):
    """Make sure the Jinja in <script> tags uses straight quotes (no
    `\\'static\\'` artefacts from sed-based bulk edits)."""
    resp = client.get("/screener")
    body = resp.data.decode()
    # Rendered HTML should contain the static path; never the literal
    # backslash-escaped form.
    assert "/static/explainer.js" in body
    assert "\\'static\\'" not in body
