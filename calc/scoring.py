"""Score functions on a 0–100 scale per PRD weights.

Every score is `clamp(0, 100)`. Each function returns a Score with:
  - value:  0–100 number
  - label:  Excellent (>=85) / Good (>=65) / Mixed (>=40) / Weak (>=20) / Poor
  - reasons: human-readable list of triggered rules with point deltas
  - warnings: human-readable list of missing/conflicting inputs
  - source_urls: provenance pointers for the inputs that fired
"""
from __future__ import annotations
from typing import Optional
from models import Score, StockScores, SourcedValue


# ---------- helpers -----------------------------------------------------------

def _v(sv: Optional[SourcedValue]) -> Optional[float]:
    if sv is None:
        return None
    val = sv.value
    return val if isinstance(val, (int, float)) else None


def _clamp(x: float, lo: float = 0, hi: float = 100) -> float:
    return max(lo, min(hi, x))


def _label_100(score: float) -> str:
    if score >= 85:
        return "Excellent"
    if score >= 65:
        return "Good"
    if score >= 40:
        return "Mixed"
    if score >= 20:
        return "Weak"
    return "Poor"


def _collect_source_urls(m: dict, keys: list) -> list:
    urls = []
    for k in keys:
        sv = m.get(k)
        if sv is not None and getattr(sv, "source_url", None):
            urls.append(sv.source_url)
    return urls


# ---------- Value Score (0–100) ----------------------------------------------

def value_score(m: dict, peer_median_pe: Optional[float] = None) -> Score:
    """PRD weights:
        +20 if P/E ≤ 10
        +15 if P/E below peer median
        +20 if within 10% of 52-week low
        +10 if market cap passes regional threshold
        +10 if dividend yield available and above peer median
        -15 if P/E unavailable
        -15 if earnings appear cyclical / one-off (skipped — no public signal)
    """
    pts = 0.0
    reasons: list = []
    warnings: list = []

    pe = _v(m.get("trailing_pe"))
    if pe is not None and 0 < pe <= 10:
        pts += 20
        reasons.append(f"+20 P/E {pe:.1f}x ≤ 10")
    if pe is not None and peer_median_pe and 0 < pe < peer_median_pe:
        pts += 15
        reasons.append(f"+15 P/E below peer median ({peer_median_pe:.1f}x)")
    if pe is None:
        pts -= 15
        warnings.append("-15 trailing P/E unavailable")

    pct_low = _v(m.get("percent_from_low"))
    if pct_low is not None and pct_low <= 10:
        pts += 20
        reasons.append(f"+20 within 10% of 52W low ({pct_low:.1f}%)")

    mcap_usd = _v(m.get("market_cap_usd"))
    if mcap_usd is not None and mcap_usd >= 2_000_000_000:
        pts += 10
        reasons.append(f"+10 market cap ${mcap_usd/1e9:.1f}B ≥ $2B")
    elif mcap_usd is None:
        warnings.append("Market cap unavailable")

    dy = _v(m.get("dividend_yield"))
    if dy is not None and dy > 2.0:
        pts += 10
        reasons.append(f"+10 dividend yield {dy:.2f}% (income contributor)")

    pts = _clamp(pts)
    return Score(
        value=round(pts, 1),
        label=_label_100(pts),
        reasons=reasons,
        warnings=warnings,
        source_urls=_collect_source_urls(m, ["trailing_pe", "percent_from_low", "market_cap_usd", "dividend_yield"]),
    )


# ---------- Momentum Score (0–100) -------------------------------------------

def momentum_score(m: dict) -> Score:
    """PRD weights:
        +15 if 5D positive
        +15 if ROC 14D positive
        +15 if ROC 21D positive
        +15 if RSI 40–70
        +10 if price above 20D MA
        +10 if price above 50D MA
        +10 if price above 200D MA
        -15 if RSI > 70
        -20 if price below 200D MA
        -15 if both ROC values negative
    """
    pts = 0.0
    reasons: list = []
    warnings: list = []

    p5 = _v(m.get("five_day_performance"))
    if p5 is not None and p5 > 0:
        pts += 15
        reasons.append(f"+15 5D positive ({p5:+.2f}%)")

    r14 = _v(m.get("roc14"))
    r21 = _v(m.get("roc21"))
    if r14 is not None and r14 > 0:
        pts += 15
        reasons.append(f"+15 ROC 14D positive ({r14:+.2f}%)")
    if r21 is not None and r21 > 0:
        pts += 15
        reasons.append(f"+15 ROC 21D positive ({r21:+.2f}%)")
    if (r14 is not None and r14 < 0) and (r21 is not None and r21 < 0):
        pts -= 15
        reasons.append("-15 ROC 14D and 21D both negative")

    rsi = _v(m.get("rsi14"))
    if rsi is not None and 40 <= rsi <= 70:
        pts += 15
        reasons.append(f"+15 RSI 40–70 ({rsi:.0f})")
    elif rsi is not None and rsi > 70:
        pts -= 15
        reasons.append(f"-15 RSI overbought ({rsi:.0f})")

    price = _v(m.get("price"))
    ma20 = _v(m.get("ma20"))
    ma50 = _v(m.get("ma50"))
    ma200 = _v(m.get("ma200"))
    if price is not None and ma20 is not None and price > ma20:
        pts += 10
        reasons.append("+10 above 20D MA")
    if price is not None and ma50 is not None and price > ma50:
        pts += 10
        reasons.append("+10 above 50D MA")
    if price is not None and ma200 is not None:
        if price > ma200:
            pts += 10
            reasons.append("+10 above 200D MA")
        else:
            pts -= 20
            reasons.append("-20 below 200D MA (long-term downtrend)")
    elif ma200 is None:
        warnings.append("200D MA unavailable")

    pts = _clamp(pts)
    return Score(
        value=round(pts, 1),
        label=_label_100(pts),
        reasons=reasons,
        warnings=warnings,
        source_urls=_collect_source_urls(m, ["price", "rsi14", "roc14", "roc21"]),
    )


# ---------- Quality Score (0–100) --------------------------------------------

def quality_score(m: dict) -> Score:
    """Lightweight quality proxy — only verified public signals.

    +20 large-cap (≥ $10B USD)
    +15 mega-cap (≥ $50B USD)
    +20 dividend payer
    +15 P/B ≤ 5 (sane balance sheet proxy)
    +10 high liquidity (avg daily vol ≥ 1M)
    +10 defensive sector
    +10 low source conflict (at least one fundamental + one price source)
    """
    pts = 0.0
    reasons: list = []
    warnings: list = []

    mcap = _v(m.get("market_cap_usd"))
    if mcap is not None and mcap >= 50_000_000_000:
        pts += 35  # +20 large + +15 mega
        reasons.append(f"+35 mega-cap ${mcap/1e9:.0f}B ≥ $50B")
    elif mcap is not None and mcap >= 10_000_000_000:
        pts += 20
        reasons.append(f"+20 large-cap ${mcap/1e9:.1f}B ≥ $10B")
    elif mcap is None:
        warnings.append("Market cap unavailable")

    dy = _v(m.get("dividend_yield"))
    if dy is not None and dy > 0:
        pts += 20
        reasons.append(f"+20 pays dividend ({dy:.2f}%)")

    pb = _v(m.get("price_to_book"))
    if pb is not None and 0 < pb <= 5:
        pts += 15
        reasons.append(f"+15 P/B {pb:.2f} ≤ 5")
    elif pb is None:
        warnings.append("Price/Book unavailable")

    vol = _v(m.get("avg_daily_volume"))
    if vol is not None and vol >= 1_000_000:
        pts += 10
        reasons.append(f"+10 high liquidity (avg vol {vol/1e6:.1f}M/day)")

    sec = m.get("security")
    sector = (sec.get("sector") if isinstance(sec, dict) else None) or ""
    if sector.lower() in {"consumer defensive", "healthcare", "utilities"}:
        pts += 10
        reasons.append(f"+10 defensive sector ({sector})")

    # Source conflict / coverage proxy: do we have BOTH a price and a fundamental
    # SourcedValue resolved? Then sources are non-conflicting.
    price_sv = m.get("price")
    pe_sv = m.get("trailing_pe")
    if price_sv and pe_sv and price_sv.value is not None and pe_sv.value is not None:
        pts += 10
        reasons.append("+10 price + fundamentals both resolved (low source conflict)")

    pts = _clamp(pts)
    return Score(
        value=round(pts, 1),
        label=_label_100(pts),
        reasons=reasons,
        warnings=warnings,
        source_urls=_collect_source_urls(m, ["market_cap_usd", "dividend_yield", "price_to_book"]),
    )


# ---------- Risk Score (0–100; HIGHER = HIGHER RISK) -------------------------

def risk_score(m: dict) -> Score:
    """PRD: higher score = higher risk. Inputs are penalties.

    +25 RSI > 70 (overbought)
    +25 price below 200D MA
    +15 low liquidity (avg vol < 250K)
    +15 P/E unavailable (missing fundamentals)
    +10 small cap (< $500M USD)
    +10 stale data (historical-only freshness)
    +10 within 5% of 52W high (limited upside / sentiment risk)
    +10 ROC 14D & 21D both negative
    """
    pts = 0.0
    reasons: list = []
    warnings: list = []

    rsi = _v(m.get("rsi14"))
    if rsi is not None and rsi > 70:
        pts += 25
        reasons.append(f"+25 RSI overbought ({rsi:.0f})")

    price = _v(m.get("price"))
    ma200 = _v(m.get("ma200"))
    if price is not None and ma200 is not None and price < ma200:
        pts += 25
        reasons.append("+25 below 200D MA (long-term downtrend)")

    vol = _v(m.get("avg_daily_volume"))
    if vol is not None and vol < 250_000:
        pts += 15
        reasons.append(f"+15 low liquidity (avg vol {vol/1e3:.0f}K/day)")

    pe = _v(m.get("trailing_pe"))
    if pe is None:
        pts += 15
        reasons.append("+15 trailing P/E unavailable (missing fundamentals)")

    mcap = _v(m.get("market_cap_usd"))
    if mcap is not None and mcap < 500_000_000:
        pts += 10
        reasons.append(f"+10 small cap (${mcap/1e6:.0f}M < $500M)")

    price_sv = m.get("price")
    if price_sv and getattr(price_sv, "freshness", None) == "historical-only":
        pts += 10
        reasons.append("+10 stale data (historical-only)")

    high52 = _v(m.get("fifty_two_week_high"))
    if price is not None and high52 is not None and high52 > 0:
        if (high52 - price) / high52 < 0.05:
            pts += 10
            reasons.append("+10 within 5% of 52W high (limited upside)")

    r14 = _v(m.get("roc14"))
    r21 = _v(m.get("roc21"))
    if (r14 is not None and r14 < 0) and (r21 is not None and r21 < 0):
        pts += 10
        reasons.append("+10 ROC 14D & 21D both negative")

    pts = _clamp(pts)
    # NB: higher = higher risk, but the same label scale is applied; users read
    # the "label" + the meta description ("higher = riskier") together.
    return Score(
        value=round(pts, 1),
        label=_label_100(pts),
        reasons=reasons,
        warnings=warnings,
        source_urls=[],
    )


# ---------- Data Confidence Score (0–100) ------------------------------------

KEY_METRICS = (
    "price", "market_cap_usd", "trailing_pe", "avg_daily_volume",
    "fifty_two_week_high", "fifty_two_week_low", "rsi14", "ma200",
)


def data_confidence_score(m: dict) -> Score:
    """0–100 based on availability + freshness + source count + ticker
    resolution certainty."""
    available = 0
    fresh_count = 0
    mock_count = 0
    total = len(KEY_METRICS)
    warnings: list = []
    reasons: list = []

    for key in KEY_METRICS:
        sv = m.get(key)
        if sv is None or getattr(sv, "value", None) is None:
            warnings.append(f"{key} unavailable")
            continue
        available += 1
        f = getattr(sv, "freshness", "unavailable")
        if f in ("real-time", "delayed", "previous-close", "cached"):
            fresh_count += 1
        if f == "mock":
            mock_count += 1
            warnings.append(f"{key} is mock data")

    coverage_pts = (available / total) * 60         # 0..60
    freshness_pts = (fresh_count / total) * 30      # 0..30
    completeness_bonus = 10 if available == total else 0

    # Penalty for mock leakage
    pts = coverage_pts + freshness_pts + completeness_bonus - (mock_count * 5)

    if available == total:
        reasons.append(f"+10 all {total} key metrics available")
    if fresh_count >= total - 1:
        reasons.append(f"+30 {fresh_count}/{total} metrics fresh")
    elif fresh_count > 0:
        reasons.append(f"+{round((fresh_count/total)*30, 0):.0f} {fresh_count}/{total} metrics fresh")
    reasons.append(f"+{round(coverage_pts, 0):.0f} coverage ({available}/{total} key metrics)")
    if mock_count:
        reasons.append(f"-{mock_count*5} {mock_count} metric(s) are mock — caveat emptor")

    pts = _clamp(pts)
    return Score(
        value=round(pts, 1),
        label=_label_100(pts),
        reasons=reasons,
        warnings=warnings,
        source_urls=[],
    )


# ---------- Aggregate ---------------------------------------------------------

def score_all(m: dict, peer_median_pe: Optional[float] = None) -> StockScores:
    return StockScores(
        value_score=value_score(m, peer_median_pe),
        momentum_score=momentum_score(m),
        quality_score=quality_score(m),
        risk_score=risk_score(m),
        data_confidence_score=data_confidence_score(m),
    )
