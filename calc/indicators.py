"""Pure technical-indicator math. No DataFrames in the public API — accept
plain sequences so this module is trivially unit-testable."""
from __future__ import annotations
from typing import Optional, Sequence


def simple_ma(closes: Sequence[float], period: int) -> Optional[float]:
    if len(closes) < period or period <= 0:
        return None
    window = closes[-period:]
    return float(sum(window) / period)


def rsi(closes: Sequence[float], period: int = 14) -> Optional[float]:
    """Wilder-style RSI using simple averages of gains/losses over `period`."""
    if len(closes) <= period:
        return None
    gains = 0.0
    losses = 0.0
    # Use the most recent `period` deltas for a stable last-bar value
    for i in range(-period, 0):
        delta = closes[i] - closes[i - 1]
        if delta > 0:
            gains += delta
        else:
            losses += -delta
    if losses == 0:
        return 100.0 if gains > 0 else 50.0
    rs = (gains / period) / (losses / period)
    return float(100 - (100 / (1 + rs)))


def roc(closes: Sequence[float], period: int) -> Optional[float]:
    """Rate of Change as a percentage."""
    if len(closes) <= period or period <= 0:
        return None
    prev = closes[-(period + 1)]
    if prev == 0:
        return None
    return float((closes[-1] / prev - 1.0) * 100.0)


def perf(closes: Sequence[float], n: int) -> Optional[float]:
    """N-bar percentage performance."""
    if len(closes) <= n or n <= 0:
        return None
    prev = closes[-(n + 1)]
    if prev == 0:
        return None
    return float((closes[-1] / prev - 1.0) * 100.0)


def fifty_two_week_high(closes: Sequence[float]) -> Optional[float]:
    if not closes:
        return None
    window = closes[-252:] if len(closes) >= 252 else closes
    return float(max(window))


def fifty_two_week_low(closes: Sequence[float]) -> Optional[float]:
    if not closes:
        return None
    window = closes[-252:] if len(closes) >= 252 else closes
    return float(min(window))


def compute_indicators(closes: Sequence[float], volumes: Optional[Sequence[float]] = None) -> dict:
    """Full bundle used by the analyzer + screener. Returns floats or None."""
    if not closes or len(closes) < 2:
        return {}
    last = float(closes[-1])
    high_52 = fifty_two_week_high(closes)
    low_52 = fifty_two_week_low(closes)
    avg_vol_20 = None
    if volumes:
        tail = volumes[-20:] if len(volumes) >= 20 else volumes
        avg_vol_20 = float(sum(tail) / len(tail))
    return {
        "price": last,
        "high_52w": high_52,
        "low_52w": low_52,
        "pct_from_low": ((last - low_52) / low_52 * 100.0) if low_52 else None,
        "pct_from_high": ((last - high_52) / high_52 * 100.0) if high_52 else None,
        "perf_5d": perf(closes, 5),
        "ma_20": simple_ma(closes, 20),
        "ma_50": simple_ma(closes, 50),
        "ma_200": simple_ma(closes, 200),
        "rsi_14": rsi(closes, 14),
        "roc_14": roc(closes, 14),
        "roc_21": roc(closes, 21),
        "avg_volume": avg_vol_20,
        "bars": len(closes),
    }
