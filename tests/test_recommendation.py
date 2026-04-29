"""Tests for calc.recommendation.build_scenario."""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from models import SourcedValue
from calc.recommendation import build_scenario
from calc.scoring import score_all


def sv(value, freshness="cached"):
    return SourcedValue(value=value, source_name="test",
                       freshness=freshness, confidence="high")


def make_metrics(price=100, ma20=98, ma50=95, ma200=85, high52=120, low52=70,
                 rsi=55, roc14=3, roc21=5, pe=15, pct_low=42):
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


def test_scenario_returns_required_keys():
    m = make_metrics()
    scores = score_all(m)
    sc = build_scenario(m, scores)
    for key in ("base_case", "upside_case", "downside_case",
                "technical_trigger", "invalidation_level",
                "confidence_reason", "final_rating",
                "time_horizon", "catalysts"):
        assert key in sc, f"missing key: {key}"


def test_scenario_rating_is_buy_watch_or_avoid():
    m = make_metrics()
    scores = score_all(m)
    sc = build_scenario(m, scores)
    assert sc["final_rating"] in ("Buy", "Watch", "Avoid")


def test_scenario_strong_setup_buy():
    m = make_metrics(price=110, ma20=100, ma50=95, ma200=85,
                     high52=115, rsi=55, roc14=5, roc21=7, pe=8, pct_low=5)
    scores = score_all(m)
    sc = build_scenario(m, scores)
    assert sc["final_rating"] == "Buy"


def test_scenario_overbought_high_risk_avoid():
    m = make_metrics(price=80, ma20=85, ma50=90, ma200=100,
                     high52=110, rsi=85, roc14=-5, roc21=-7, pe=40, pct_low=10)
    scores = score_all(m)
    sc = build_scenario(m, scores)
    assert sc["final_rating"] == "Avoid"


def test_scenario_low_data_confidence_falls_back_watch():
    """Make most fields None so dc score < 40 → forced Watch."""
    m = {
        "price": sv(100), "ma20": SourcedValue.unavailable(),
        "ma50": SourcedValue.unavailable(), "ma200": SourcedValue.unavailable(),
        "fifty_two_week_high": SourcedValue.unavailable(),
        "fifty_two_week_low": SourcedValue.unavailable(),
        "rsi14": SourcedValue.unavailable(),
        "roc14": SourcedValue.unavailable(),
        "roc21": SourcedValue.unavailable(),
        "trailing_pe": SourcedValue.unavailable(),
        "percent_from_low": SourcedValue.unavailable(),
        "five_day_performance": SourcedValue.unavailable(),
        "market_cap_usd": SourcedValue.unavailable(),
        "avg_daily_volume": SourcedValue.unavailable(),
        "dividend_yield": SourcedValue.unavailable(),
        "price_to_book": SourcedValue.unavailable(),
        "security": {"sector": "Technology", "currency": "USD"},
    }
    scores = score_all(m)
    sc = build_scenario(m, scores)
    assert sc["final_rating"] == "Watch"
    assert "Data confidence" in sc["confidence_reason"]


def test_scenario_uses_50d_ma_in_trigger():
    m = make_metrics(price=110, ma50=100, ma200=90)
    scores = score_all(m)
    sc = build_scenario(m, scores)
    # Above 50D + above 200D → continuation phrasing
    assert "50D MA" in sc["technical_trigger"] or "200D MA" in sc["technical_trigger"]


def test_scenario_invalidation_uses_52w_low_or_ma200():
    m = make_metrics(price=110, ma200=90, low52=70)
    scores = score_all(m)
    sc = build_scenario(m, scores)
    assert "200D MA" in sc["invalidation_level"] or "52-week low" in sc["invalidation_level"]


def test_scenario_catalysts_includes_events_when_provided():
    m = make_metrics()
    scores = score_all(m)
    events = {
        "earnings_date": sv("2026-05-15"),
        "ex_dividend_date": sv("2026-05-20"),
    }
    sc = build_scenario(m, scores, events)
    assert any("earnings" in c.lower() for c in sc["catalysts"])
    assert any("ex-dividend" in c.lower() for c in sc["catalysts"])


def test_scenario_handles_empty_events():
    m = make_metrics()
    scores = score_all(m)
    sc = build_scenario(m, scores, events=None)
    assert sc["catalysts"]  # non-empty (generic catalysts)


def test_scenario_base_case_non_empty():
    m = make_metrics()
    scores = score_all(m)
    sc = build_scenario(m, scores)
    assert len(sc["base_case"]) > 0
    assert len(sc["upside_case"]) > 0
    assert len(sc["downside_case"]) > 0
