"""Pure-math unit tests for calc.indicators."""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from calc.indicators import (
    simple_ma, rsi, roc, perf, fifty_two_week_high, fifty_two_week_low,
    compute_indicators,
)


def test_simple_ma_basic():
    assert simple_ma([1, 2, 3, 4, 5], 5) == 3.0
    assert simple_ma([1, 2, 3, 4, 5], 3) == 4.0  # last 3: 3,4,5 → 4
    assert simple_ma([1, 2], 5) is None  # not enough data


def test_simple_ma_invalid():
    assert simple_ma([], 1) is None
    assert simple_ma([1, 2, 3], 0) is None


def test_rsi_uptrend_high():
    closes = list(range(1, 30))  # monotonic up → all gains, no losses
    val = rsi(closes, 14)
    assert val == 100.0


def test_rsi_downtrend_low():
    closes = list(range(30, 1, -1))  # monotonic down
    val = rsi(closes, 14)
    assert val is not None
    assert val < 5  # near 0


def test_rsi_insufficient():
    assert rsi([1, 2, 3], 14) is None


def test_roc_basic():
    closes = [100, 110]
    assert abs(roc(closes, 1) - 10.0) < 1e-9


def test_roc_negative():
    closes = [100, 50]
    assert abs(roc(closes, 1) - (-50.0)) < 1e-9


def test_perf_5d():
    closes = [100, 101, 102, 103, 104, 110]
    assert abs(perf(closes, 5) - 10.0) < 1e-9


def test_perf_insufficient():
    assert perf([100, 101], 5) is None


def test_52w_window_capped():
    # 300 bars; only last 252 should be considered
    closes = [1.0] * 252 + [9999.0] * 48
    assert fifty_two_week_high(closes) == 9999.0  # included in tail
    assert fifty_two_week_low(closes) == 1.0


def test_52w_short_history_uses_all():
    closes = [1.0, 2.0, 3.0]
    assert fifty_two_week_high(closes) == 3.0
    assert fifty_two_week_low(closes) == 1.0


def test_compute_indicators_full_bundle():
    closes = list(range(1, 251))  # 250 bars
    volumes = [1000.0] * 250
    bundle = compute_indicators(closes, volumes)
    assert bundle["price"] == 250.0
    assert bundle["bars"] == 250
    assert bundle["ma_20"] is not None
    assert bundle["ma_50"] is not None
    assert bundle["ma_200"] is not None
    assert bundle["rsi_14"] is not None
    assert bundle["avg_volume"] == 1000.0
    # uptrend → RSI very high, all positive ROC
    assert bundle["rsi_14"] > 90
    assert bundle["perf_5d"] > 0
    assert bundle["roc_14"] > 0


def test_compute_indicators_empty():
    assert compute_indicators([], []) == {}
    assert compute_indicators([100], []) == {}


def test_compute_indicators_pct_from_low():
    closes = [50.0] * 200 + [60.0]  # low=50, last=60 → +20% from low
    bundle = compute_indicators(closes)
    assert abs(bundle["pct_from_low"] - 20.0) < 1e-9
