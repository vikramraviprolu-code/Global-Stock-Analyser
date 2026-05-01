"""Scenario-based recommendation engine (PRD Build Step 7).

Returns a dict with:
  base_case, upside_case, downside_case,
  technical_trigger, invalidation_level,
  confidence_reason, final_rating, time_horizon,
  catalysts (list).

Uses moving averages and 52-week high/low as the support/resistance proxy
when no real S/R levels are available — explicit per PRD.
"""
from __future__ import annotations
from typing import Optional


def _v(sv) -> Optional[float]:
    if sv is None:
        return None
    val = getattr(sv, "value", None) if hasattr(sv, "value") else (sv.get("value") if isinstance(sv, dict) else None)
    return val if isinstance(val, (int, float)) else None


def _txt_value(sv) -> Optional[str]:
    if sv is None:
        return None
    val = sv.value if hasattr(sv, "value") else (sv.get("value") if isinstance(sv, dict) else None)
    return val if isinstance(val, str) else None


# Risk-profile-aware Buy thresholds. Each bucket sets the minimum scores
# (and maximum risk) before "Buy" can fire. None of these are advice — they
# adjust how aggressive the recommender is for the same input data.
RISK_THRESHOLDS = {
    "conservative": {"buy_value": 50, "buy_momentum": 75, "buy_risk_max": 30,
                     "buy_dc_min": 70, "avoid_momentum": 35, "avoid_risk": 60},
    "moderate":     {"buy_value": 45, "buy_momentum": 70, "buy_risk_max": 40,
                     "buy_dc_min": 55, "avoid_momentum": 30, "avoid_risk": 65},
    "balanced":     {"buy_value": 40, "buy_momentum": 65, "buy_risk_max": 50,
                     "buy_dc_min": 40, "avoid_momentum": 25, "avoid_risk": 70},
    "growth":       {"buy_value": 30, "buy_momentum": 55, "buy_risk_max": 65,
                     "buy_dc_min": 40, "avoid_momentum": 20, "avoid_risk": 80},
    "aggressive":   {"buy_value": 25, "buy_momentum": 45, "buy_risk_max": 75,
                     "buy_dc_min": 35, "avoid_momentum": 15, "avoid_risk": 90},
}
DEFAULT_BUCKET = "balanced"


def _thresholds_for(bucket: Optional[str]) -> dict:
    return RISK_THRESHOLDS.get(bucket or DEFAULT_BUCKET, RISK_THRESHOLDS[DEFAULT_BUCKET])


def build_scenario(
    metrics: dict,
    scores: dict,
    events: Optional[dict] = None,
    risk_bucket: Optional[str] = None,
) -> dict:
    """metrics: dict-shape with SourcedValue or {value: ...} entries.
    scores: StockScores dataclass OR dict from .to_dict().
    events: optional dict of SourcedValue events (earnings_date etc.)
    risk_bucket: optional one of conservative / moderate / balanced /
                 growth / aggressive — tunes Buy / Avoid thresholds.
                 Falls back to "balanced" defaults.
    """
    # Normalise scores to dict of {key: value (float)}
    score_vals = {}
    if hasattr(scores, "value_score"):
        for key in ("value_score", "momentum_score", "quality_score",
                    "risk_score", "data_confidence_score"):
            s = getattr(scores, key, None)
            score_vals[key] = s.value if s else None
    elif isinstance(scores, dict):
        for key in ("value_score", "momentum_score", "quality_score",
                    "risk_score", "data_confidence_score"):
            s = scores.get(key) or {}
            score_vals[key] = s.get("value")

    v = score_vals.get("value_score") or 0
    m = score_vals.get("momentum_score") or 0
    q = score_vals.get("quality_score") or 0
    r = score_vals.get("risk_score") or 0
    dc = score_vals.get("data_confidence_score") or 0

    price = _v(metrics.get("price"))
    ma20 = _v(metrics.get("ma20"))
    ma50 = _v(metrics.get("ma50"))
    ma200 = _v(metrics.get("ma200"))
    high52 = _v(metrics.get("fifty_two_week_high"))
    low52 = _v(metrics.get("fifty_two_week_low"))
    rsi = _v(metrics.get("rsi14"))
    roc14 = _v(metrics.get("roc14"))
    roc21 = _v(metrics.get("roc21"))
    pe = _v(metrics.get("trailing_pe"))
    pct_low = _v(metrics.get("percent_from_low"))

    sym = ""
    sec = metrics.get("security")
    if isinstance(sec, dict):
        sym = sec.get("currency") or ""

    def fmt(x):
        return f"{sym} {x:.2f}" if x is not None else "—"

    # --- Base Case --------------------------------------------------------
    base_lines = []
    if price is not None and ma50 is not None:
        if price > ma50:
            base_lines.append(f"Price ({fmt(price)}) above 50D MA ({fmt(ma50)}) — recent trend constructive.")
        else:
            base_lines.append(f"Price ({fmt(price)}) below 50D MA ({fmt(ma50)}) — short-term trend weak.")
    if pct_low is not None:
        base_lines.append(f"Sitting {pct_low:.1f}% above the 52-week low.")
    if pe is not None:
        if pe <= 10:
            base_lines.append(f"Trailing P/E {pe:.1f}x — clear value zone.")
        elif pe <= 20:
            base_lines.append(f"Trailing P/E {pe:.1f}x — fair valuation range.")
        else:
            base_lines.append(f"Trailing P/E {pe:.1f}x — premium multiple.")
    if not base_lines:
        base_lines.append("Insufficient data to characterize base case beyond raw scores.")

    # --- Upside Case ------------------------------------------------------
    upside_lines = []
    if ma200 is not None and price is not None and price < ma200:
        upside_lines.append(
            f"If price reclaims 200D MA at {fmt(ma200)} on positive ROC, "
            f"long-term trend flips bullish."
        )
    if high52 is not None and price is not None:
        target = high52
        upside_lines.append(
            f"Re-test of 52-week high at {fmt(target)} "
            f"({((target/price - 1)*100):+.1f}% from here) is the natural upside marker."
        )
    if (roc14 or 0) > 0 and (roc21 or 0) > 0:
        upside_lines.append(
            "Both ROC 14D and 21D are positive — momentum behind the move."
        )
    if not upside_lines:
        upside_lines.append("No clear technical upside catalyst from current setup.")

    # --- Downside Case ----------------------------------------------------
    downside_lines = []
    if ma50 is not None and price is not None and price > ma50:
        downside_lines.append(
            f"Loss of 50D MA at {fmt(ma50)} would weaken the short-term thesis."
        )
    if ma200 is not None and price is not None:
        downside_lines.append(
            f"Break below 200D MA at {fmt(ma200)} signals a long-term downtrend."
        )
    if low52 is not None:
        downside_lines.append(
            f"Failure of 52-week low at {fmt(low52)} = full thesis invalidation."
        )
    if rsi is not None and rsi > 70:
        downside_lines.append(
            f"RSI {rsi:.0f} (overbought) — mean reversion risk in the near term."
        )
    if not downside_lines:
        downside_lines.append("No imminent technical downside trigger from current setup.")

    # --- Technical Trigger ------------------------------------------------
    if ma50 is not None and ma200 is not None and price is not None:
        if price > ma50 and price < ma200:
            trigger = (f"Bullish trigger: a daily close above 200D MA ({fmt(ma200)}) "
                       f"with ROC 14D continuing positive would flip the long-term trend.")
        elif price > ma50 and price > ma200 and (roc14 or 0) > 0:
            trigger = (f"Continuation trigger: holding above 50D MA ({fmt(ma50)}) "
                       f"and 200D MA ({fmt(ma200)}) keeps the uptrend intact.")
        elif price < ma50 and price < ma200:
            trigger = (f"Bearish trigger: rejection at 50D MA ({fmt(ma50)}) "
                       f"with negative ROC accelerates the downtrend.")
        else:
            trigger = (f"Mixed: watch 50D MA ({fmt(ma50)}) and 200D MA ({fmt(ma200)}) "
                       f"as the next decision points.")
    else:
        trigger = "Moving averages unavailable — cannot derive a clean technical trigger."

    # --- Invalidation Level ----------------------------------------------
    if low52 is not None and ma200 is not None and price is not None:
        # Choose the closer of 200D MA (below price) or 52W low
        if price > ma200:
            invalidation = f"Close below 200D MA ({fmt(ma200)}) invalidates the bullish view."
        else:
            invalidation = f"Close below 52-week low ({fmt(low52)}) invalidates any reversal thesis."
    elif low52 is not None:
        invalidation = f"Close below 52-week low ({fmt(low52)}) invalidates the thesis."
    else:
        invalidation = "Insufficient data to set a precise invalidation level — use stop based on personal risk."

    # --- Final Rating + Confidence Reason ---------------------------------
    th = _thresholds_for(risk_bucket)
    bucket_label = (risk_bucket or DEFAULT_BUCKET).replace("_", " ").title()
    if dc < th["buy_dc_min"]:
        rating = "Watch"
        reason = (f"Data confidence is low ({dc:.0f}/100, needs ≥ {th['buy_dc_min']} "
                  f"for {bucket_label} profile) — too many key metrics missing "
                  f"or stale to commit to a directional call.")
    elif m >= th["buy_momentum"] and v >= th["buy_value"] and r <= th["buy_risk_max"]:
        rating = "Buy"
        reason = (f"Strong momentum ({m:.0f}/100, ≥ {th['buy_momentum']}) backed "
                  f"by reasonable value ({v:.0f}/100, ≥ {th['buy_value']}) and "
                  f"acceptable risk ({r:.0f}/100, ≤ {th['buy_risk_max']}). "
                  f"[{bucket_label} profile]")
    elif m <= th["avoid_momentum"] or r >= th["avoid_risk"]:
        rating = "Avoid"
        reason = (f"Weak momentum ({m:.0f}/100, ≤ {th['avoid_momentum']}) or "
                  f"elevated risk ({r:.0f}/100, ≥ {th['avoid_risk']}). "
                  f"Wait for technical reset. [{bucket_label} profile]")
    elif v >= 65 and m >= 40:
        rating = "Buy"
        reason = (f"Compelling value ({v:.0f}/100) with improving momentum "
                  f"({m:.0f}/100) — classic value-with-momentum setup. "
                  f"[{bucket_label} profile]")
    else:
        rating = "Watch"
        reason = (f"Mixed signals — value {v:.0f}, momentum {m:.0f}, "
                  f"risk {r:.0f}, data confidence {dc:.0f}. Wait for "
                  f"confirmation. [{bucket_label} profile]")

    # --- Time horizon -----------------------------------------------------
    if rating == "Buy":
        horizon = "1–3 months on momentum + technical confirmation; reassess at next earnings."
    elif rating == "Watch":
        horizon = "2–6 weeks watching for setup confirmation."
    else:
        horizon = "Avoid initiating — re-evaluate in 4–8 weeks."

    # --- Catalysts from events ------------------------------------------
    catalysts = []
    if events:
        ed = events.get("earnings_date")
        if ed and (hasattr(ed, "value") and ed.value or isinstance(ed, dict) and ed.get("value")):
            val = ed.value if hasattr(ed, "value") else ed.get("value")
            catalysts.append(f"Upcoming earnings: {val} — guidance + margin trajectory.")
        ex = events.get("ex_dividend_date")
        if ex and (hasattr(ex, "value") and ex.value or isinstance(ex, dict) and ex.get("value")):
            val = ex.value if hasattr(ex, "value") else ex.get("value")
            catalysts.append(f"Ex-dividend date: {val}.")
        dd = events.get("dividend_date")
        if dd and (hasattr(dd, "value") and dd.value or isinstance(dd, dict) and dd.get("value")):
            val = dd.value if hasattr(dd, "value") else dd.get("value")
            catalysts.append(f"Dividend pay date: {val}.")
    if not catalysts:
        catalysts.append("No event-driven catalysts on the calendar from free public sources.")
    catalysts.append("Sector rotation flows + macro rate path.")
    catalysts.append("Peer earnings reactions setting comp expectations.")

    return {
        "base_case": base_lines,
        "upside_case": upside_lines,
        "downside_case": downside_lines,
        "technical_trigger": trigger,
        "invalidation_level": invalidation,
        "confidence_reason": reason,
        "final_rating": rating,
        "time_horizon": horizon,
        "catalysts": catalysts,
        "risk_bucket": risk_bucket or DEFAULT_BUCKET,
        "thresholds_used": th,
    }
