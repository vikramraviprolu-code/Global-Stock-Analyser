"""Built-in screener presets — match the 6 PRD presets plus a few extras."""
from __future__ import annotations
from typing import Dict, List
from screener.engine import Filter


PRESETS: Dict[str, dict] = {
    # ---------------------------------------------------------------- PRD Required
    "value_near_lows": {
        "name": "Value Near Lows",
        "description": "Within 10% of 52-week low + P/E ≤ 10 + market cap ≥ regional threshold + medium+ data confidence.",
        "filters": [
            Filter(kind="pct_from_low_max", value=10.0, label="≤ 10% from 52W low"),
            Filter(kind="pe_max", value=10.0, label="P/E ≤ 10"),
            Filter(kind="mcap_usd_min", value=2_000_000_000, label="Market cap ≥ $2B"),
            Filter(kind="volume_min", value=250_000, label="Avg vol ≥ 250K"),
            Filter(kind="min_data_confidence", value=60.0, label="Data confidence ≥ Medium"),
        ],
    },
    "momentum_leaders": {
        "name": "Momentum Leaders",
        "description": "Strong 5D + ROC 14D & 21D positive + RSI 40–70 + price above 20D & 50D MAs.",
        "filters": [
            Filter(kind="perf5d_min", value=2.0, label="5D ≥ +2%"),
            Filter(kind="roc14_min", value=0.0, label="ROC 14D ≥ 0"),
            Filter(kind="roc21_min", value=0.0, label="ROC 21D ≥ 0"),
            Filter(kind="rsi_min", value=40.0, label="RSI ≥ 40"),
            Filter(kind="rsi_max", value=70.0, label="RSI ≤ 70"),
            Filter(kind="above_ma20", value=True, label="Price > 20D MA"),
            Filter(kind="above_ma50", value=True, label="Price > 50D MA"),
            Filter(kind="mcap_usd_min", value=2_000_000_000, label="Market cap ≥ $2B"),
        ],
    },
    "quality_large_caps": {
        "name": "Quality Large Caps",
        "description": "$10B+ market cap with healthy liquidity, available P/E, fresh data, medium+ confidence.",
        "filters": [
            Filter(kind="mcap_usd_min", value=10_000_000_000, label="Market cap ≥ $10B"),
            Filter(kind="volume_min", value=500_000, label="Avg vol ≥ 500K"),
            Filter(kind="exclude_unavailable_pe", value=True, label="P/E available"),
            Filter(kind="exclude_stale", value=True, label="Exclude stale data"),
            Filter(kind="min_data_confidence", value=60.0, label="Confidence ≥ Medium"),
        ],
    },
    "oversold_watchlist": {
        "name": "Oversold Watchlist",
        "description": "RSI < 35 + within 20% of 52-week low — potential mean-reversion setups.",
        "filters": [
            Filter(kind="rsi_max", value=35.0, label="RSI ≤ 35"),
            Filter(kind="pct_from_low_max", value=20.0, label="≤ 20% from 52W low"),
            Filter(kind="mcap_usd_min", value=2_000_000_000, label="Market cap ≥ $2B"),
            Filter(kind="volume_min", value=250_000, label="Avg vol ≥ 250K"),
        ],
    },
    "breakout_candidates": {
        "name": "Breakout Candidates",
        "description": "Above 20D + 50D MA, ROC 14D positive, 5D positive, near 52W high but not extremely overbought.",
        "filters": [
            Filter(kind="above_ma20", value=True, label="Price > 20D MA"),
            Filter(kind="above_ma50", value=True, label="Price > 50D MA"),
            Filter(kind="roc14_min", value=0.0, label="ROC 14D ≥ 0"),
            Filter(kind="perf5d_min", value=0.0, label="5D ≥ 0%"),
            Filter(kind="pct_from_high_max", value=10.0, label="Within 10% of 52W high"),
            Filter(kind="rsi_max", value=72.0, label="RSI ≤ 72 (not extreme)"),
            Filter(kind="mcap_usd_min", value=2_000_000_000, label="Market cap ≥ $2B"),
        ],
    },
    "data_reliable_only": {
        "name": "Data Reliable Only",
        "description": "High data confidence (≥ 85), price + market cap + P/E all available, no stale freshness.",
        "filters": [
            Filter(kind="min_data_confidence", value=85.0, label="Data confidence ≥ High"),
            Filter(kind="exclude_unavailable_pe", value=True, label="P/E available"),
            Filter(kind="exclude_unavailable_mcap", value=True, label="Mcap available"),
            Filter(kind="exclude_stale", value=True, label="Exclude stale"),
            Filter(kind="require_history", value=True, label="Has 200D MA"),
        ],
    },
    # ---------------------------------------------------------------- Extras
    "trend_followers": {
        "name": "Trend Followers (above 200D MA)",
        "description": "Long-term uptrend + recent positive 5D — institutional-style momentum.",
        "filters": [
            Filter(kind="above_ma200", value=True, label="Price > 200D MA"),
            Filter(kind="perf5d_min", value=0.0, label="5D ≥ 0%"),
            Filter(kind="mcap_usd_min", value=5_000_000_000, label="Market cap ≥ $5B"),
        ],
    },
    "mega_caps": {
        "name": "Mega Caps Above 200D MA",
        "description": "$50B+ companies in long-term uptrends — institutional momentum names.",
        "filters": [
            Filter(kind="mcap_usd_min", value=50_000_000_000, label="Market cap ≥ $50B"),
            Filter(kind="above_ma200", value=True, label="Price > 200D MA"),
        ],
    },
    "indian_banks": {
        "name": "Indian Banks (NSE)",
        "description": "All Indian financial-services tickers in our universe.",
        "filters": [
            Filter(kind="country_in", value=["India"], label="India"),
            Filter(kind="sector_in", value=["Financial Services"], label="Financial Services"),
        ],
    },
    "japan_industrials": {
        "name": "Japan Industrials",
        "description": "Tokyo-listed industrial conglomerates and machinery names.",
        "filters": [
            Filter(kind="country_in", value=["Japan"], label="Japan"),
            Filter(kind="sector_in", value=["Industrials"], label="Industrials"),
        ],
    },
    "europe_tech": {
        "name": "European Technology",
        "description": "EU-listed technology / semiconductors — ASML, SAP, etc.",
        "filters": [
            Filter(kind="region_in", value=["Europe"], label="Europe"),
            Filter(kind="sector_in", value=["Technology"], label="Technology"),
        ],
    },
    "dividend_payers": {
        "name": "Dividend Payers (≥ 2%)",
        "description": "Stable dividend-paying large caps for income.",
        "filters": [
            Filter(kind="dividend_min", value=2.0, label="Div ≥ 2%"),
            Filter(kind="mcap_usd_min", value=5_000_000_000, label="Mcap ≥ $5B"),
        ],
    },
}


def get_preset(key: str) -> List[Filter]:
    spec = PRESETS.get(key)
    if not spec:
        return []
    return list(spec["filters"])


def list_presets() -> List[dict]:
    return [
        {
            "key": k,
            "name": v["name"],
            "description": v["description"],
            "filter_labels": [f.label or f.kind for f in v["filters"]],
        }
        for k, v in PRESETS.items()
    ]
