"""Tests for calc.scoring — value/momentum/quality/risk/data-confidence."""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from models import SourcedValue
from calc.scoring import (
    value_score, momentum_score, quality_score, risk_score,
    data_confidence_score, score_all,
)


def sv(value, freshness="cached"):
    """Make a real SourcedValue. Constructor enforces freshness."""
    return SourcedValue(
        value=value, source_name="test",
        freshness=freshness, confidence="high",
    )


def test_value_score_max_with_all_signals():
    m = {
        "percent_from_low": sv(5.0),       # +1
        "trailing_pe":      sv(8.0),       # +1
        "market_cap_usd":   sv(5_000_000_000.0),  # +1
        "price":            sv(100.0),
    }
    s = value_score(m, peer_median_pe=15.0)  # +1 (peer compare)
    assert s.value == 4.0
    assert s.label == "Excellent"


def test_value_score_zero_when_nothing_matches():
    m = {
        "percent_from_low": sv(50.0),
        "trailing_pe":      sv(40.0),
        "market_cap_usd":   sv(100_000_000.0),
    }
    s = value_score(m)
    assert s.value == 0.0
    assert s.label == "Poor"


def test_momentum_score_full_bull():
    m = {
        "five_day_performance": sv(3.0),
        "roc14":                sv(5.0),
        "roc21":                sv(8.0),
        "rsi14":                sv(55.0),
        "price":                sv(100.0),
        "ma20":                 sv(95.0),
        "ma50":                 sv(90.0),
        "ma200":                sv(85.0),
    }
    s = momentum_score(m)
    assert s.value == 7.0
    assert s.label == "Excellent"


def test_momentum_score_no_signal():
    m = {
        "five_day_performance": sv(-3.0),
        "roc14":                sv(-2.0),
        "roc21":                sv(-5.0),
        "rsi14":                sv(25.0),  # below 40
        "price":                sv(80.0),
        "ma20":                 sv(85.0),
        "ma50":                 sv(90.0),
        "ma200":                sv(100.0),
    }
    s = momentum_score(m)
    assert s.value == 0.0


def test_risk_score_low_risk_when_clean():
    m = {
        "rsi14":              sv(50.0),
        "price":              sv(100.0),
        "ma200":              sv(80.0),
        "roc14":              sv(2.0),
        "roc21":              sv(3.0),
        "fifty_two_week_high": sv(120.0),
        "market_cap_usd":     sv(10_000_000_000.0),
    }
    s = risk_score(m)
    assert s.value == 5.0  # zero penalties → max
    assert s.label == "Excellent"


def test_risk_score_penalised_when_overbought_and_below_ma200():
    m = {
        "rsi14":              sv(85.0),  # overbought
        "price":              sv(80.0),
        "ma200":              sv(100.0),  # below
        "roc14":              sv(-1.0),
        "roc21":              sv(-2.0),
        "fifty_two_week_high": sv(120.0),
        "market_cap_usd":     sv(10_000_000_000.0),
    }
    s = risk_score(m)
    assert s.value == 2.0  # 3 penalties: rsi>70, below ma200, both negs


def test_data_confidence_full_high():
    m = {
        "price":              sv(100.0),
        "market_cap_usd":     sv(1e9),
        "trailing_pe":        sv(10.0),
        "avg_daily_volume":   sv(1e6),
        "fifty_two_week_high": sv(120.0),
        "fifty_two_week_low":  sv(80.0),
        "rsi14":              sv(50.0),
        "ma200":              sv(100.0),
    }
    s = data_confidence_score(m)
    assert s.value == 5.0
    assert s.label == "Excellent"


def test_data_confidence_partial():
    m = {
        "price": sv(100.0),
        "market_cap_usd": SourcedValue.unavailable(),
        "trailing_pe": SourcedValue.unavailable(),
        "avg_daily_volume": sv(1e6),
        "fifty_two_week_high": sv(120.0),
        "fifty_two_week_low": SourcedValue.unavailable(),
        "rsi14": sv(50.0),
        "ma200": sv(100.0),
    }
    s = data_confidence_score(m)
    # 5 of 8 available → 5/8 * 5 = 3.125
    assert abs(s.value - 3.13) < 0.05


def test_score_all_returns_all_five():
    m = {
        "percent_from_low": sv(5.0),
        "trailing_pe":      sv(8.0),
        "market_cap_usd":   sv(5_000_000_000.0),
        "price":            sv(100.0),
        "five_day_performance": sv(2.0),
        "roc14": sv(3.0), "roc21": sv(4.0),
        "rsi14": sv(55.0),
        "ma20": sv(95.0), "ma50": sv(90.0), "ma200": sv(85.0),
        "avg_daily_volume": sv(1e6),
        "fifty_two_week_high": sv(120.0), "fifty_two_week_low": sv(80.0),
        "security": {"sector": "Healthcare"},
        "dividend_yield": sv(2.5),
        "price_to_book": sv(3.0),
    }
    s = score_all(m, peer_median_pe=15.0)
    assert s.value_score.value > 0
    assert s.momentum_score.value > 0
    assert s.quality_score.value > 0
    assert s.risk_score.value > 0
    assert s.data_confidence_score.value > 0
