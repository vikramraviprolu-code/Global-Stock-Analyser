"""Global screening, scoring, peer discovery."""
from __future__ import annotations
import os
from typing import Optional, List, Tuple, Dict
from concurrent.futures import ThreadPoolExecutor, as_completed
from market_data import fetch_stooq_history, compute_indicators, fetch_fundamentals, freshness_label
from markets import (
    listing_meta, regional_filter, fx_rate, to_usd, fmt_currency, fmt_mcap,
)
from resolver import load_universe

EXCLUDE_KEYWORDS = ("ETF", "Fund", "Trust", "Warrant", "Preferred", "REIT - Mortgage")


def _to_float(x):
    """Coerce to float; return None on failure."""
    if x is None:
        return None
    if isinstance(x, (int, float)):
        return float(x)
    try:
        return float(str(x).replace(",", ""))
    except (ValueError, TypeError):
        return None


def find_peers(listing: Dict, universe: List[dict]) -> List[dict]:
    """Tiered peer search: same industry+country, then industry+region, sector+country,
    sector+region, finally global same-industry."""
    t_up = listing["ticker"].upper()
    sector = (listing.get("sector") or "").strip().lower()
    industry = (listing.get("industry") or "").strip().lower()
    country = (listing.get("country") or "").strip().lower()
    region = (listing.get("region") or "").strip().lower()

    def collect(predicate) -> List[dict]:
        out = []
        seen = set()
        for r in universe:
            rt = r["ticker"].upper()
            if rt == t_up or rt in seen:
                continue
            if any(k.lower() in (r.get("company") or "").lower() for k in EXCLUDE_KEYWORDS):
                continue
            if predicate(r):
                out.append(r)
                seen.add(rt)
        return out

    tiers = [
        ("industry+country", lambda r: industry and r.get("industry", "").lower() == industry
         and country and r.get("country", "").lower() == country),
        ("industry+region", lambda r: industry and r.get("industry", "").lower() == industry
         and region and r.get("region", "").lower() == region),
        ("sector+country", lambda r: sector and r.get("sector", "").lower() == sector
         and country and r.get("country", "").lower() == country),
        ("sector+region", lambda r: sector and r.get("sector", "").lower() == sector
         and region and r.get("region", "").lower() == region),
        ("global industry", lambda r: industry and r.get("industry", "").lower() == industry),
        ("global sector", lambda r: sector and r.get("sector", "").lower() == sector),
    ]
    best_name, best_peers = tiers[-1][0], []
    for tier_name, pred in tiers:
        peers = collect(pred)
        if len(peers) >= 3:
            return peers, tier_name
        if peers and not best_peers:
            best_name, best_peers = tier_name, peers
    return best_peers, best_name


def enrich_ticker(row: dict) -> Optional[dict]:
    """Fetch history + fundamentals for a universe row."""
    sym = row["ticker"].upper()
    df = fetch_stooq_history(sym)
    ind = compute_indicators(df) if df is not None else {}
    if not ind:
        return None
    fund = fetch_fundamentals(sym)
    meta = listing_meta(sym)
    currency = fund.get("currency") or row.get("currency") or meta["currency"]
    market_cap_local = _to_float(fund.get("market_cap"))
    market_cap_usd = to_usd(market_cap_local, currency) if currency else None
    return {
        "ticker": sym,
        "company": fund.get("company") or row.get("company") or sym,
        "sector": fund.get("sector") or row.get("sector"),
        "industry": fund.get("industry") or row.get("industry"),
        "country": row.get("country") or meta["country"],
        "region": row.get("region") or meta["region"],
        "exchange": row.get("exchange") or meta["exchange"],
        "currency": currency,
        "currency_symbol": meta["symbol"],
        "market_cap": market_cap_local,
        "market_cap_usd": market_cap_usd,
        "trailing_pe": _to_float(fund.get("trailing_pe")),
        "fund_source": fund.get("source", "unavailable"),
        **ind,
    }


def passes_global_filters(d: dict) -> Tuple[bool, List[str]]:
    """Apply regional filter thresholds based on country."""
    country = d.get("country") or "USA"
    flt = regional_filter(country)
    fails = []
    price = d.get("price")
    if price is None or price < flt["min_price"]:
        sym = d.get("currency_symbol", "")
        fails.append(f"Price < {sym}{flt['min_price']:g} ({country})")
    vol = d.get("avg_volume")
    if vol is None or vol < flt["min_volume"]:
        fails.append(f"Avg vol < {flt['min_volume']:,.0f}")
    mcap_usd = d.get("market_cap_usd")
    if mcap_usd is not None and mcap_usd < flt["min_mcap_usd"]:
        fails.append(f"Market cap < ${flt['min_mcap_usd']/1e9:.0f}B USD")
    return (len(fails) == 0, fails)


def value_screen(peers: List[dict]) -> List[dict]:
    out = []
    for p in peers:
        passes, _ = passes_global_filters(p)
        if not passes:
            continue
        if p.get("pct_from_low") is None or p["pct_from_low"] > 10:
            continue
        pe = p.get("trailing_pe")
        if pe is None or pe <= 0 or pe > 10:
            continue
        out.append(p)
    return sorted(out, key=lambda x: x.get("pct_from_low", 999))


def momentum_screen(peers: List[dict], top_n: int = 10) -> List[dict]:
    qualified = []
    for p in peers:
        passes, _ = passes_global_filters(p)
        if not passes:
            continue
        if p.get("perf_5d") is None:
            continue
        qualified.append(p)
    qualified.sort(key=lambda x: x.get("perf_5d", -999), reverse=True)
    top = qualified[:top_n]
    for p in top:
        rsi = p.get("rsi_14")
        p["rsi_label"] = "Overbought" if rsi and rsi > 70 else "Oversold" if rsi and rsi < 30 else "Neutral"
        price = p.get("price")
        for n in (20, 50, 200):
            ma = p.get(f"ma_{n}")
            if ma and price:
                pct = (price / ma - 1) * 100
                p[f"vs_ma_{n}"] = pct
                p[f"vs_ma_{n}_label"] = f"↑ {pct:+.1f}%" if pct > 0 else f"↓ {pct:+.1f}%"
            else:
                p[f"vs_ma_{n}"] = None
                p[f"vs_ma_{n}_label"] = "—"
        roc14 = p.get("roc_14") or 0
        roc21 = p.get("roc_21") or 0
        above_50 = p.get("vs_ma_50") and p["vs_ma_50"] > 0
        above_200 = p.get("vs_ma_200") and p["vs_ma_200"] > 0
        if rsi and rsi > 70:
            p["signal"], p["outlook"], p["confidence"] = "Potential reversal", "Neutral", "Medium"
        elif roc14 > 0 and roc21 > 0 and above_50 and above_200:
            p["signal"], p["outlook"] = "Momentum continuation", "Bullish"
            p["confidence"] = "High" if rsi and 40 <= rsi <= 70 else "Medium"
        elif roc14 < 0 and roc21 < 0:
            p["signal"], p["outlook"], p["confidence"] = "Potential reversal", "Bearish", "Medium"
        else:
            p["signal"], p["outlook"], p["confidence"] = "Mixed signal", "Neutral", "Low"
    return top


def score_input_stock(d: dict) -> dict:
    value_score = 0
    value_breakdown = []
    if d.get("pct_from_low") is not None and d["pct_from_low"] <= 10:
        value_score += 1
        value_breakdown.append("+1 within 10% of 52W low")
    pe = d.get("trailing_pe")
    if pe and 0 < pe <= 10:
        value_score += 1
        value_breakdown.append("+1 trailing P/E ≤ 10")
    flt = regional_filter(d.get("country") or "USA")
    if d.get("market_cap_usd") and d["market_cap_usd"] >= flt["min_mcap_usd"]:
        value_score += 1
        value_breakdown.append(f"+1 market cap ≥ ${flt['min_mcap_usd']/1e9:.0f}B USD")
    if d.get("attractive_vs_peers"):
        value_score += 1
        value_breakdown.append("+1 attractive vs peers")

    mom = 0
    mom_breakdown = []
    if (d.get("perf_5d") or 0) > 0:
        mom += 1; mom_breakdown.append("+1 5D positive")
    if (d.get("roc_14") or 0) > 0:
        mom += 1; mom_breakdown.append("+1 ROC 14D positive")
    if (d.get("roc_21") or 0) > 0:
        mom += 1; mom_breakdown.append("+1 ROC 21D positive")
    rsi = d.get("rsi_14")
    if rsi and 40 <= rsi <= 70:
        mom += 1; mom_breakdown.append("+1 RSI 40–70")
    price = d.get("price")
    for n in (20, 50, 200):
        ma = d.get(f"ma_{n}")
        if price and ma and price > ma:
            mom += 1
            mom_breakdown.append(f"+1 above {n}D MA")

    penalties = 0
    pen_breakdown = []
    if rsi and rsi > 70:
        penalties += 1; pen_breakdown.append("-1 RSI > 70")
    if price and d.get("ma_200") and price < d["ma_200"]:
        penalties += 1; pen_breakdown.append("-1 below 200D MA")
    if (d.get("roc_14") or 0) < 0 and (d.get("roc_21") or 0) < 0:
        penalties += 1; pen_breakdown.append("-1 ROC 14D & 21D both negative")

    total = value_score + mom - penalties

    if value_score >= 3 and mom >= 4 and penalties == 0:
        rec = "Buy"
    elif value_score >= 2 and mom >= 5:
        rec = "Buy"
    elif penalties >= 2 or (value_score <= 1 and mom <= 2):
        rec = "Avoid"
    elif total >= 4:
        rec = "Watch"
    else:
        rec = "Watch"

    missing = [k for k in ("trailing_pe", "market_cap", "rsi_14", "ma_200") if d.get(k) is None]
    if len(missing) >= 2:
        confidence = "Low"
    elif total >= 6 and not missing:
        confidence = "High"
    elif total >= 3:
        confidence = "Medium"
    else:
        confidence = "Low"

    return {
        "value_score": value_score, "momentum_score": mom, "penalties": penalties,
        "total_score": total, "value_breakdown": value_breakdown,
        "momentum_breakdown": mom_breakdown, "penalty_breakdown": pen_breakdown,
        "recommendation": rec, "confidence": confidence, "missing_data": missing,
    }


def build_narrative(d: dict, score: dict, value_hits: List[dict], mom_hits: List[dict]) -> dict:
    bull, bear, base, catalysts, fund_risks, tech_risks = [], [], [], [], [], []
    sym = d.get("currency_symbol", "")
    rsi = d.get("rsi_14"); pe = d.get("trailing_pe")
    pct_low = d.get("pct_from_low"); pct_high = d.get("pct_from_high")
    p5 = d.get("perf_5d"); roc14 = d.get("roc_14"); roc21 = d.get("roc_21")
    price = d.get("price")

    if pct_low is not None and pct_low <= 10:
        bull.append(f"Trading {pct_low:.1f}% above 52-week low — attractive entry zone.")
    if pe and 0 < pe <= 10:
        bull.append(f"Trailing P/E of {pe:.1f}x suggests valuation discount.")
    if (p5 or 0) > 0 and (roc14 or 0) > 0:
        bull.append("Positive 5D and ROC 14D point to building momentum.")
    if price and d.get("ma_200") and price > d["ma_200"]:
        bull.append("Price holds above 200-day MA — long-term uptrend intact.")

    if pct_high is not None and pct_high < -25:
        bear.append(f"Down {abs(pct_high):.1f}% from 52-week high — sustained weakness.")
    if rsi and rsi > 70:
        bear.append(f"RSI {rsi:.0f} signals overbought, near-term pullback risk.")
    if (roc14 or 0) < 0 and (roc21 or 0) < 0:
        bear.append("Negative ROC 14D and 21D — momentum deteriorating.")
    if price and d.get("ma_200") and price < d["ma_200"]:
        bear.append("Price below 200-day MA — long-term downtrend pressure.")

    base.append(f"Stock at {sym}{price:,.2f} ({d.get('currency')}), score {score['total_score']}, recommendation {score['recommendation']}.")
    if value_hits:
        base.append(f"{len(value_hits)} qualifying value peers in screen.")
    if mom_hits:
        base.append(f"Top momentum peers showing {mom_hits[0]['perf_5d']:+.1f}% 5D performance.")

    catalysts.extend([
        "Upcoming earnings release — guidance and margin trajectory.",
        "Sector rotation flows and macro rate path.",
        "Local-market FX moves (relevant for ADR / cross-listed exposure).",
        "Peer earnings reactions setting comp expectations.",
    ])

    if pe and pe > 30:
        fund_risks.append(f"Premium P/E of {pe:.1f}x — execution risk if growth disappoints.")
    if not d.get("market_cap"):
        fund_risks.append("Market cap data unavailable — fundamental sizing uncertain.")
    if pe is None:
        fund_risks.append("Trailing P/E unavailable — earnings quality unverified.")
    if d.get("country") not in ("USA",):
        fund_risks.append(f"Cross-border risks: FX, regulation, accounting standards differ in {d.get('country')}.")

    if rsi and rsi > 70:
        tech_risks.append("Overbought RSI raises probability of mean reversion.")
    if rsi and rsi < 30:
        tech_risks.append("Oversold RSI — selling pressure may persist before reversal.")
    if score["penalties"] >= 2:
        tech_risks.append("Multiple penalty triggers — wait for confirmation.")
    if pct_high is not None and pct_high < -30:
        tech_risks.append("Distance from 52W high indicates broken trend.")

    horizon = "1–3 months" if score["recommendation"] == "Buy" else (
        "2–4 weeks" if score["recommendation"] == "Watch" else "Avoid initiating")

    return {
        "bull_case": bull or ["No standout bullish triggers identified."],
        "bear_case": bear or ["No standout bearish triggers identified."],
        "base_case": base, "catalysts": catalysts,
        "fundamental_risks": fund_risks or ["No flagged fundamental risks."],
        "technical_risks": tech_risks or ["No flagged technical risks."],
        "horizon": horizon,
    }


def run_analysis(listing: Dict) -> dict:
    """Top-level: listing must have ticker (and optionally exchange/country/etc.)."""
    ticker = listing["ticker"].upper().strip()
    universe = load_universe()
    df = fetch_stooq_history(ticker)
    if df is None or df.empty:
        return {"error": f"No price history found for {ticker}. Verify ticker + exchange suffix."}
    indicators = compute_indicators(df)
    if not indicators:
        return {"error": f"Insufficient price history for {ticker} (need ≥ 20 bars)."}
    fund = fetch_fundamentals(ticker)
    meta = listing_meta(ticker)
    universe_row = next((r for r in universe if r["ticker"].upper() == ticker), {})

    currency = fund.get("currency") or listing.get("currency") or universe_row.get("currency") or meta["currency"]
    sector = fund.get("sector") or listing.get("sector") or universe_row.get("sector")
    industry = fund.get("industry") or listing.get("industry") or universe_row.get("industry")
    country = listing.get("country") or universe_row.get("country") or meta["country"]
    region = listing.get("region") or universe_row.get("region") or meta["region"]
    exchange = listing.get("exchange") or universe_row.get("exchange") or meta["exchange"]
    market_cap_local = _to_float(fund.get("market_cap"))
    market_cap_usd = to_usd(market_cap_local, currency)

    input_d = {
        "ticker": ticker,
        "company": fund.get("company") or listing.get("company") or universe_row.get("company") or ticker,
        "sector": sector, "industry": industry,
        "country": country, "region": region, "exchange": exchange,
        "currency": currency, "currency_symbol": meta["symbol"],
        "market_cap": market_cap_local, "market_cap_usd": market_cap_usd,
        "trailing_pe": _to_float(fund.get("trailing_pe")),
        "fund_source": fund.get("source"),
        **indicators,
    }

    peers_raw, peer_tier = find_peers(input_d, universe)
    peers_enriched = []
    if peers_raw:
        with ThreadPoolExecutor(max_workers=8) as ex:
            futures = {ex.submit(enrich_ticker, p): p for p in peers_raw[:40]}
            for fut in as_completed(futures):
                try:
                    res = fut.result()
                    if res:
                        peers_enriched.append(res)
                except Exception:
                    continue

    value_hits = value_screen(peers_enriched)
    momentum_hits = momentum_screen(peers_enriched, top_n=10)
    cross = [v for v in value_hits if any(m["ticker"] == v["ticker"] for m in momentum_hits)]

    peer_pes = [p["trailing_pe"] for p in peers_enriched if p.get("trailing_pe") and p["trailing_pe"] > 0]
    if peer_pes and input_d.get("trailing_pe") and input_d["trailing_pe"] > 0:
        median_pe = sorted(peer_pes)[len(peer_pes) // 2]
        input_d["attractive_vs_peers"] = input_d["trailing_pe"] < median_pe
        input_d["peer_median_pe"] = median_pe
    else:
        input_d["attractive_vs_peers"] = False

    input_passes_global, input_fails = passes_global_filters(input_d)
    input_value_qualifies = (
        input_passes_global
        and input_d.get("pct_from_low") is not None and input_d["pct_from_low"] <= 10
        and input_d.get("trailing_pe") and 0 < input_d["trailing_pe"] <= 10
    )

    score = score_input_stock(input_d)
    narrative = build_narrative(input_d, score, value_hits, momentum_hits)
    freshness = freshness_label(input_d.get("last_date"))

    # FX rate snapshot for UI
    fx_to_usd = fx_rate(currency, "USD") if currency != "USD" else 1.0

    return {
        "input": input_d,
        "value_hits": value_hits,
        "momentum_hits": momentum_hits,
        "cross": cross,
        "score": score,
        "narrative": narrative,
        "freshness": freshness,
        "input_passes_global": input_passes_global,
        "input_global_fails": input_fails,
        "input_value_qualifies": input_value_qualifies,
        "peer_count": len(peers_enriched),
        "peer_total_in_universe": len(peers_raw),
        "peer_tier": peer_tier,
        "fx_to_usd": fx_to_usd,
        "regional_filter": regional_filter(country),
    }
