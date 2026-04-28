"""Score functions. Each returns a Score with reasons + warnings + value [0..max]."""
from __future__ import annotations
from typing import Optional
from models import Score, StockScores, label_for, SourcedValue


def _v(sv: Optional[SourcedValue]) -> Optional[float]:
    """Unwrap SourcedValue.value, or None."""
    if sv is None:
        return None
    val = sv.value
    return val if isinstance(val, (int, float)) else None


# ---------- Value (max 4) -----------------------------------------------------

def value_score(m: dict, peer_median_pe: Optional[float] = None) -> Score:
    """m is a dict with SourcedValue entries. Spec rules: +1 within 10% of 52W
    low; +1 trailing P/E ≤ 10; +1 mcap_usd ≥ $2B; +1 cheaper than peer median P/E."""
    score = 0
    reasons: list[str] = []
    warnings: list[str] = []

    pct_low = _v(m.get("percent_from_low"))
    pe = _v(m.get("trailing_pe"))
    mcap_usd = _v(m.get("market_cap_usd"))

    if pct_low is not None and pct_low <= 10:
        score += 1
        reasons.append(f"Within 10% of 52W low ({pct_low:.1f}%)")
    if pe is not None and 0 < pe <= 10:
        score += 1
        reasons.append(f"Trailing P/E {pe:.1f}x ≤ 10")
    elif pe is None:
        warnings.append("Trailing P/E unavailable")
    if mcap_usd is not None and mcap_usd >= 2_000_000_000:
        score += 1
        reasons.append(f"Market cap ${mcap_usd/1e9:.1f}B ≥ $2B")
    elif mcap_usd is None:
        warnings.append("Market cap unavailable")
    if peer_median_pe and pe and 0 < pe < peer_median_pe:
        score += 1
        reasons.append(f"Cheaper than peer median P/E ({peer_median_pe:.1f}x)")

    return Score(
        value=float(score),
        label=label_for(score, 4.0),
        reasons=reasons,
        warnings=warnings,
        source_urls=_collect_source_urls(m, ["price", "trailing_pe", "market_cap_usd", "fifty_two_week_low"]),
    )


# ---------- Momentum (max 7) --------------------------------------------------

def momentum_score(m: dict) -> Score:
    score = 0
    reasons: list[str] = []
    warnings: list[str] = []

    p5 = _v(m.get("five_day_performance"))
    r14 = _v(m.get("roc14"))
    r21 = _v(m.get("roc21"))
    rsi = _v(m.get("rsi14"))
    price = _v(m.get("price"))

    if (p5 or 0) > 0:
        score += 1; reasons.append(f"5D performance positive ({p5:+.2f}%)")
    if (r14 or 0) > 0:
        score += 1; reasons.append(f"ROC 14D positive ({r14:+.2f}%)")
    if (r21 or 0) > 0:
        score += 1; reasons.append(f"ROC 21D positive ({r21:+.2f}%)")
    if rsi is not None and 40 <= rsi <= 70:
        score += 1; reasons.append(f"RSI in 40–70 range ({rsi:.0f})")
    if price is not None:
        for n in (20, 50, 200):
            ma = _v(m.get(f"ma{n}"))
            if ma is not None and price > ma:
                score += 1; reasons.append(f"Price above {n}D MA")
            elif ma is None:
                warnings.append(f"{n}D MA unavailable")
    return Score(
        value=float(score),
        label=label_for(score, 7.0),
        reasons=reasons,
        warnings=warnings,
        source_urls=_collect_source_urls(m, ["price", "rsi14", "roc14", "roc21"]),
    )


# ---------- Quality (max 4) ---------------------------------------------------

def quality_score(m: dict) -> Score:
    """Lightweight quality proxy from free data: large-cap + non-cyclical sector
    + dividend present + price/book ≤ 5."""
    score = 0
    reasons: list[str] = []
    warnings: list[str] = []

    mcap_usd = _v(m.get("market_cap_usd"))
    if mcap_usd and mcap_usd >= 10_000_000_000:
        score += 1; reasons.append(f"Large-cap ≥ $10B (${mcap_usd/1e9:.1f}B)")
    elif mcap_usd is None:
        warnings.append("Market cap unavailable for quality check")

    sector = (m.get("security") or {}).get("sector") if isinstance(m.get("security"), dict) else None
    if sector and sector.lower() in {"consumer defensive", "healthcare", "utilities"}:
        score += 1; reasons.append(f"Defensive sector ({sector})")

    div = _v(m.get("dividend_yield"))
    if div is not None and div > 0:
        score += 1; reasons.append(f"Pays dividend ({div:.2f}%)")
    elif div is None:
        warnings.append("Dividend yield unavailable")

    pb = _v(m.get("price_to_book"))
    if pb is not None and 0 < pb <= 5:
        score += 1; reasons.append(f"Price/Book {pb:.2f} ≤ 5")
    elif pb is None:
        warnings.append("Price/Book unavailable")

    return Score(
        value=float(score),
        label=label_for(score, 4.0),
        reasons=reasons,
        warnings=warnings,
        source_urls=_collect_source_urls(m, ["dividend_yield", "price_to_book"]),
    )


# ---------- Risk (penalties; lower is better, score reported as inverse) ------

def risk_score(m: dict) -> Score:
    """Higher Score.value = lower risk. Penalties: RSI>70, below 200D MA,
    ROC14+ROC21 both negative, near 52W high (<5%), tiny mcap (<$500M)."""
    penalties = 0
    reasons: list[str] = []
    warnings: list[str] = []

    rsi = _v(m.get("rsi14"))
    if rsi is not None and rsi > 70:
        penalties += 1; reasons.append(f"RSI overbought ({rsi:.0f})")

    price = _v(m.get("price"))
    ma200 = _v(m.get("ma200"))
    if price and ma200 and price < ma200:
        penalties += 1; reasons.append("Price below 200D MA")

    r14 = _v(m.get("roc14"))
    r21 = _v(m.get("roc21"))
    if (r14 or 0) < 0 and (r21 or 0) < 0:
        penalties += 1; reasons.append("ROC 14D + 21D both negative")

    high52 = _v(m.get("fifty_two_week_high"))
    if price and high52 and (high52 - price) / high52 < 0.05:
        penalties += 1; reasons.append("Within 5% of 52W high — limited upside")

    mcap_usd = _v(m.get("market_cap_usd"))
    if mcap_usd is not None and mcap_usd < 500_000_000:
        penalties += 1; reasons.append(f"Small cap (<$500M) — liquidity / volatility risk")

    # Inverse: 5 penalties slots → score = 5 - penalties
    inv = 5 - penalties
    return Score(
        value=float(inv),
        label=label_for(inv, 5.0),
        reasons=reasons,
        warnings=warnings,
        source_urls=[],
    )


# ---------- Data confidence ---------------------------------------------------

KEY_METRICS = (
    "price", "market_cap_usd", "trailing_pe", "avg_daily_volume",
    "fifty_two_week_high", "fifty_two_week_low", "rsi14", "ma200",
)


def data_confidence_score(m: dict) -> Score:
    """How many of KEY_METRICS resolved + how fresh."""
    available = 0
    high_freshness = 0
    warnings: list[str] = []
    reasons: list[str] = []
    for key in KEY_METRICS:
        sv = m.get(key)
        if sv is not None and getattr(sv, "value", None) is not None:
            available += 1
            if sv.freshness in ("real-time", "delayed", "previous-close", "cached"):
                high_freshness += 1
            if sv.freshness == "mock":
                warnings.append(f"{key} is mock data")
        else:
            warnings.append(f"{key} unavailable")

    pct = available / len(KEY_METRICS)
    score = round(pct * 5.0, 2)
    if available == len(KEY_METRICS):
        reasons.append("All key metrics available")
    if high_freshness >= len(KEY_METRICS) - 1:
        reasons.append("All metrics fresh")

    return Score(
        value=score,
        label=label_for(score, 5.0),
        reasons=reasons,
        warnings=warnings,
        source_urls=[],
    )


def score_all(m: dict, peer_median_pe: Optional[float] = None) -> StockScores:
    return StockScores(
        value_score=value_score(m, peer_median_pe),
        momentum_score=momentum_score(m),
        quality_score=quality_score(m),
        risk_score=risk_score(m),
        data_confidence_score=data_confidence_score(m),
    )


# ---------- helpers -----------------------------------------------------------

def _collect_source_urls(m: dict, keys: list[str]) -> list[str]:
    urls: list[str] = []
    for k in keys:
        sv = m.get(k)
        if sv is not None and getattr(sv, "source_url", None):
            urls.append(sv.source_url)
    return urls
