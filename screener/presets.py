"""Built-in screener presets. Each is a curated list of Filters."""
from __future__ import annotations
from typing import Dict, List
from screener.engine import Filter


PRESETS: Dict[str, dict] = {
    "value_near_low": {
        "name": "Value: Within 10% of 52W Low + P/E ≤ 10",
        "description": "Classic deep-value screen — beaten-down names trading near support with single-digit earnings multiples.",
        "filters": [
            Filter(kind="pct_from_low_max", value=10.0, label="≤ 10% from 52W low"),
            Filter(kind="pe_max", value=10.0, label="P/E ≤ 10"),
            Filter(kind="mcap_usd_min", value=2_000_000_000, label="Market cap ≥ $2B"),
        ],
    },
    "momentum_top": {
        "name": "Momentum: 5D ≥ +5% with constructive RSI",
        "description": "Names with a 5-day surge but RSI still in the healthy 40–70 range — momentum without exhaustion.",
        "filters": [
            Filter(kind="perf5d_min", value=5.0, label="5D ≥ +5%"),
            Filter(kind="rsi_min", value=40.0, label="RSI ≥ 40"),
            Filter(kind="rsi_max", value=70.0, label="RSI ≤ 70"),
            Filter(kind="mcap_usd_min", value=2_000_000_000, label="Market cap ≥ $2B"),
        ],
    },
    "trend_followers": {
        "name": "Trend Followers: Above 200D MA + ROC positive",
        "description": "Long-term uptrend intact and recent momentum positive.",
        "filters": [
            Filter(kind="above_ma200", value=True, label="Price > 200D MA"),
            Filter(kind="perf5d_min", value=0.0, label="5D ≥ 0%"),
            Filter(kind="mcap_usd_min", value=5_000_000_000, label="Market cap ≥ $5B"),
        ],
    },
    "mega_caps": {
        "name": "Mega Caps Above 200D MA",
        "description": "$50B+ companies in long-term uptrends — institutional-grade momentum.",
        "filters": [
            Filter(kind="mcap_usd_min", value=50_000_000_000, label="Market cap ≥ $50B"),
            Filter(kind="above_ma200", value=True, label="Price > 200D MA"),
        ],
    },
    "indian_banks": {
        "name": "Indian Banks (NSE)",
        "description": "All Indian banks tracked in our universe — for deep-dive comparisons.",
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
        "description": "EU-listed tech / semiconductor names — ASML, SAP, etc.",
        "filters": [
            Filter(kind="region_in", value=["Europe"], label="Europe"),
            Filter(kind="sector_in", value=["Technology"], label="Technology"),
        ],
    },
    "oversold_bounce": {
        "name": "Oversold Bounce Candidates",
        "description": "RSI < 35 — potential mean-reversion setups.",
        "filters": [
            Filter(kind="rsi_max", value=35.0, label="RSI ≤ 35"),
            Filter(kind="mcap_usd_min", value=2_000_000_000, label="Market cap ≥ $2B"),
        ],
    },
    "dividend_payers": {
        "name": "Dividend Payers (≥ 2%)",
        "description": "Stable dividend-paying large caps.",
        "filters": [
            Filter(kind="dividend_min", value=2.0, label="Dividend ≥ 2%"),
            Filter(kind="mcap_usd_min", value=5_000_000_000, label="Market cap ≥ $5B"),
        ],
    },
}


def get_preset(key: str) -> List[Filter]:
    spec = PRESETS.get(key)
    if not spec:
        return []
    return list(spec["filters"])


def list_presets() -> List[dict]:
    """For the UI dropdown."""
    return [
        {
            "key": k, "name": v["name"], "description": v["description"],
            "filter_labels": [f.label or f.kind for f in v["filters"]],
        }
        for k, v in PRESETS.items()
    ]
