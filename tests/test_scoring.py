"""Tests for calc.scoring on the 0–100 scale (PRD weights)."""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from models import SourcedValue
from calc.scoring import (
    value_score, momentum_score, quality_score, risk_score,
    data_confidence_score, score_all,
)


def sv(value, freshness="cached"):
    return SourcedValue(
        value=value, source_name="test",
        freshness=freshness, confidence="high",
    )


# ---------- value_score ----------

def test_value_score_pegged_at_max_with_full_signals():
    """+20 P/E ≤ 10, +15 below peer median, +20 within 10% low,
    +10 mcap, +10 dividend > 2% → 75 / 100"""
    m = {
        "trailing_pe":      sv(8.0),
        "percent_from_low": sv(5.0),
        "market_cap_usd":   sv(5_000_000_000.0),
        "dividend_yield":   sv(3.5),
        "price":            sv(100.0),
    }
    s = value_score(m, peer_median_pe=15.0)
    assert s.value == 75.0
    assert s.label == "Good"


def test_value_score_zero_when_pe_missing_drains_points():
    """No positive triggers, P/E unavailable → -15 → clamped to 0."""
    m = {
        "trailing_pe":      sv(None),
        "percent_from_low": sv(50.0),
        "market_cap_usd":   sv(1_000_000_000.0),  # < $2B threshold
    }
    # _to_float-style: SourcedValue.value is None means "unavailable" → triggers -15
    s = value_score(m)
    assert s.value == 0.0
    assert s.label == "Poor"


# ---------- momentum_score ----------

def test_momentum_score_full_bull():
    """All 7 positive signals + RSI 40-70 = 15+15+15+15+10+10+10 = 90"""
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
    assert s.value == 90.0
    assert s.label == "Excellent"


def test_momentum_score_overbought_below_200_and_negative_roc():
    """No positives + RSI > 70 (-15) + below 200D MA (-20) + both ROC negative (-15) = clamped 0"""
    m = {
        "five_day_performance": sv(-2.0),
        "roc14":                sv(-3.0),
        "roc21":                sv(-5.0),
        "rsi14":                sv(80.0),
        "price":                sv(80.0),
        "ma20":                 sv(85.0),
        "ma50":                 sv(90.0),
        "ma200":                sv(100.0),
    }
    s = momentum_score(m)
    assert s.value == 0.0  # clamped
    assert s.label == "Poor"


# ---------- quality_score ----------

def test_quality_mega_cap_dividend_pb():
    m = {
        "market_cap_usd":  sv(60_000_000_000.0),  # +35
        "dividend_yield":  sv(2.5),                # +20
        "price_to_book":   sv(3.0),                # +15
        "avg_daily_volume":sv(2_000_000.0),       # +10
        "security": {"sector": "Healthcare"},      # +10
        "price":           sv(100.0),
        "trailing_pe":     sv(20.0),               # +10 (price + fund both resolved)
    }
    s = quality_score(m)
    # 35 + 20 + 15 + 10 + 10 + 10 = 100
    assert s.value == 100.0
    assert s.label == "Excellent"


def test_quality_zero_when_only_small_cap_no_extras():
    m = {
        "market_cap_usd":  sv(100_000_000.0),
        "dividend_yield":  sv(0),
        "price_to_book":   sv(None),
        "avg_daily_volume":sv(50_000.0),
        "security": {"sector": "Technology"},
        "price":           sv(100.0),
        "trailing_pe":     sv(None),  # both not resolved → no +10
    }
    s = quality_score(m)
    assert s.value == 0.0


# ---------- risk_score ----------

def test_risk_score_clean_bill_of_health():
    """No risk triggers → 0"""
    m = {
        "rsi14":              sv(50.0),
        "price":              sv(100.0),
        "ma200":              sv(80.0),
        "avg_daily_volume":   sv(2_000_000.0),
        "trailing_pe":        sv(15.0),
        "market_cap_usd":     sv(50_000_000_000.0),
        "fifty_two_week_high":sv(150.0),
        "roc14":              sv(2.0),
        "roc21":              sv(3.0),
    }
    s = risk_score(m)
    assert s.value == 0.0


def test_risk_score_max_signals():
    """RSI > 70 (+25), below 200D (+25), low vol (+15), no PE (+15),
    small cap (+10), both ROC neg (+10) → 100"""
    m = {
        "rsi14":              sv(85.0),
        "price":              sv(50.0),
        "ma200":              sv(100.0),
        "avg_daily_volume":   sv(100_000.0),
        "trailing_pe":        sv(None),
        "market_cap_usd":     sv(200_000_000.0),
        "fifty_two_week_high":sv(150.0),
        "roc14":              sv(-3.0),
        "roc21":              sv(-5.0),
    }
    s = risk_score(m)
    assert s.value == 100.0
    assert s.label == "Excellent"  # NB: label scale used regardless of "lower-is-better"


# ---------- data_confidence_score ----------

def test_data_confidence_full_high():
    m = {k: sv(1.0) for k in (
        "price", "market_cap_usd", "trailing_pe", "avg_daily_volume",
        "fifty_two_week_high", "fifty_two_week_low", "rsi14", "ma200",
    )}
    s = data_confidence_score(m)
    # 8/8 coverage = 60, 8/8 freshness = 30, +10 completeness = 100
    assert s.value == 100.0
    assert s.label == "Excellent"


def test_data_confidence_partial():
    m = {
        "price":               sv(1.0),
        "market_cap_usd":      SourcedValue.unavailable(),
        "trailing_pe":         SourcedValue.unavailable(),
        "avg_daily_volume":    sv(1.0),
        "fifty_two_week_high": sv(1.0),
        "fifty_two_week_low":  SourcedValue.unavailable(),
        "rsi14":               sv(1.0),
        "ma200":               sv(1.0),
    }
    s = data_confidence_score(m)
    # 5/8 coverage = 37.5, 5/8 freshness = 18.75, no bonus → ~56
    assert 50 <= s.value <= 60


def test_data_confidence_mock_penalty():
    m = {k: sv(1.0, freshness="mock") for k in (
        "price", "market_cap_usd", "trailing_pe", "avg_daily_volume",
        "fifty_two_week_high", "fifty_two_week_low", "rsi14", "ma200",
    )}
    s = data_confidence_score(m)
    # 8/8 coverage = 60, 0/8 fresh (mock != fresh), +10 completeness, -8*5 mock = 30
    assert s.value == 30.0
    assert any("mock" in w.lower() for w in s.warnings)


# ---------- score_all ----------

def test_score_all_returns_all_five():
    m = {
        "trailing_pe":      sv(8.0),
        "percent_from_low": sv(5.0),
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
    assert 0 <= s.value_score.value <= 100
    assert 0 <= s.momentum_score.value <= 100
    assert 0 <= s.quality_score.value <= 100
    assert 0 <= s.risk_score.value <= 100
    assert 0 <= s.data_confidence_score.value <= 100
