"""Filter engine for the screener.

Two-phase filtering:
  1. CHEAP filters operate on raw universe rows (no network) — sector, country,
     region, listing_type, exchange, currency, industry.
  2. EXPENSIVE filters operate on enriched StockMetrics — price, mcap, P/E,
     RSI, perf, MA, etc.

A `Filter` is a typed dict-like spec that the engine compiles into a callable.
Stack any number of filters; results are AND-combined.

Supported `kind` values:
  Cheap (operate on raw row dicts):
    sector_in, country_in, region_in, exchange_in, currency_in, industry_in,
    listing_type_in
  Expensive (operate on enriched StockMetrics):
    price_min, price_max, mcap_usd_min, mcap_usd_max,
    pe_min, pe_max, pb_min, pb_max,
    dividend_min, dividend_max,
    volume_min, volume_max,
    rsi_min, rsi_max,
    perf5d_min, perf5d_max,
    roc14_min, roc14_max, roc21_min, roc21_max,
    pct_from_low_min, pct_from_low_max,
    pct_from_high_max,    # near 52W high (max distance below 0)
    above_ma20, above_ma50, above_ma200,
    min_data_confidence,   # uses computed score (0..100)
    exclude_unavailable_pe, exclude_unavailable_mcap, exclude_stale,
    require_history,
"""
from __future__ import annotations
from dataclasses import dataclass, field
from typing import Any, List, Optional

from models import StockMetrics


@dataclass
class Filter:
    kind: str
    value: Any
    label: Optional[str] = None

    CHEAP_KINDS = {
        "sector_in", "country_in", "region_in", "exchange_in",
        "currency_in", "industry_in", "listing_type_in",
    }

    def is_cheap(self) -> bool:
        return self.kind in Filter.CHEAP_KINDS


# ---------- helpers -----------------------------------------------------------

def _v(sv) -> Optional[float]:
    if sv is None:
        return None
    val = getattr(sv, "value", None)
    return val if isinstance(val, (int, float)) else None


def _check_row(row: dict, f: Filter) -> bool:
    """Cheap filter check on raw universe-row dict."""
    if f.kind == "sector_in":
        return (row.get("sector") or "").lower() in {s.lower() for s in f.value}
    if f.kind == "country_in":
        return (row.get("country") or "").lower() in {s.lower() for s in f.value}
    if f.kind == "region_in":
        return (row.get("region") or "").lower() in {s.lower() for s in f.value}
    if f.kind == "exchange_in":
        return (row.get("exchange") or "").lower() in {s.lower() for s in f.value}
    if f.kind == "currency_in":
        return (row.get("currency") or "").lower() in {s.lower() for s in f.value}
    if f.kind == "industry_in":
        return (row.get("industry") or "").lower() in {s.lower() for s in f.value}
    if f.kind == "listing_type_in":
        # universe rows don't carry listing_type; default to common-stock
        listing = (row.get("listing_type") or "common-stock").lower()
        return listing in {s.lower() for s in f.value}
    return True


def _check_metric(m: StockMetrics, f: Filter, scores: Optional[dict] = None) -> bool:
    """Expensive filter check on enriched StockMetrics. `scores` is an
    optional dict {value_score, momentum_score, ...} when filtering by score."""
    # Cheap filters can also re-run here for safety (after security inferred).
    if f.kind in Filter.CHEAP_KINDS:
        sec = m.security
        haystack = {
            "sector_in": (sec.sector or "").lower(),
            "country_in": (sec.country or "").lower(),
            "region_in": (sec.region or "").lower(),
            "exchange_in": (sec.exchange or "").lower(),
            "currency_in": (sec.currency or "").lower(),
            "industry_in": (sec.industry or "").lower(),
            "listing_type_in": (sec.listing_type or "common-stock").lower(),
        }[f.kind]
        return haystack in {str(s).lower() for s in f.value}

    price = _v(m.price)
    if f.kind == "price_min":
        return price is not None and price >= f.value
    if f.kind == "price_max":
        return price is not None and price <= f.value

    mcap = _v(m.market_cap_usd)
    if f.kind == "mcap_usd_min":
        return mcap is not None and mcap >= f.value
    if f.kind == "mcap_usd_max":
        return mcap is not None and mcap <= f.value

    pe = _v(m.trailing_pe)
    if f.kind == "pe_min":
        return pe is not None and pe > 0 and pe >= f.value
    if f.kind == "pe_max":
        return pe is not None and pe > 0 and pe <= f.value

    pb = _v(m.price_to_book) if m.price_to_book else None
    if f.kind == "pb_min":
        return pb is not None and pb >= f.value
    if f.kind == "pb_max":
        return pb is not None and pb <= f.value

    dy = _v(m.dividend_yield) if m.dividend_yield else None
    if f.kind == "dividend_min":
        return dy is not None and dy >= f.value
    if f.kind == "dividend_max":
        return dy is not None and dy <= f.value

    vol = _v(m.avg_daily_volume)
    if f.kind == "volume_min":
        return vol is not None and vol >= f.value
    if f.kind == "volume_max":
        return vol is not None and vol <= f.value

    rsi = _v(m.rsi14)
    if f.kind == "rsi_min":
        return rsi is not None and rsi >= f.value
    if f.kind == "rsi_max":
        return rsi is not None and rsi <= f.value

    p5 = _v(m.five_day_performance)
    if f.kind == "perf5d_min":
        return p5 is not None and p5 >= f.value
    if f.kind == "perf5d_max":
        return p5 is not None and p5 <= f.value

    r14 = _v(m.roc14)
    if f.kind == "roc14_min":
        return r14 is not None and r14 >= f.value
    if f.kind == "roc14_max":
        return r14 is not None and r14 <= f.value

    r21 = _v(m.roc21)
    if f.kind == "roc21_min":
        return r21 is not None and r21 >= f.value
    if f.kind == "roc21_max":
        return r21 is not None and r21 <= f.value

    pct_low = _v(m.percent_from_low)
    if f.kind == "pct_from_low_min":
        return pct_low is not None and pct_low >= f.value
    if f.kind == "pct_from_low_max":
        return pct_low is not None and pct_low <= f.value

    if f.kind == "pct_from_high_max":
        # "near 52W high" — within X% below the high
        high = _v(m.fifty_two_week_high)
        if price is None or high is None or high <= 0:
            return False
        distance_pct = (high - price) / high * 100.0
        return distance_pct <= f.value

    if f.kind == "above_ma20":
        ma20 = _v(m.ma20)
        return price is not None and ma20 is not None and ((price > ma20) is bool(f.value))
    if f.kind == "above_ma50":
        ma50 = _v(m.ma50)
        return price is not None and ma50 is not None and ((price > ma50) is bool(f.value))
    if f.kind == "above_ma200":
        ma200 = _v(m.ma200)
        return price is not None and ma200 is not None and ((price > ma200) is bool(f.value))

    if f.kind == "min_data_confidence":
        if scores is None:
            return True  # pass-through when scores not computed yet
        s = getattr(scores, "data_confidence_score", None)
        return s is not None and s.value >= f.value

    if f.kind == "exclude_unavailable_pe":
        return _v(m.trailing_pe) is not None
    if f.kind == "exclude_unavailable_mcap":
        return _v(m.market_cap_usd) is not None
    if f.kind == "exclude_stale":
        # Drop rows whose price freshness is "historical-only" or "unavailable".
        f_freshness = getattr(m.price, "freshness", "unavailable")
        return f_freshness not in ("historical-only", "unavailable")
    if f.kind == "require_history":
        return _v(m.ma200) is not None

    return True


# ---------- result + engine ---------------------------------------------------

@dataclass
class ScreenerResult:
    matches: List[StockMetrics]
    total_universe: int
    after_cheap_filters: int
    enriched_count: int
    failed_enrichment: int = 0
    warnings: List[str] = field(default_factory=list)
    score_cache: dict = field(default_factory=dict)  # ticker -> StockScores

    def to_dict(self) -> dict:
        return {
            "matches": [m.to_dict() for m in self.matches],
            "total_universe": self.total_universe,
            "after_cheap_filters": self.after_cheap_filters,
            "enriched_count": self.enriched_count,
            "failed_enrichment": self.failed_enrichment,
            "warnings": self.warnings,
        }


class ScreenerEngine:
    def __init__(self, universe_service):
        self.universe = universe_service

    def screen(
        self,
        filters: List[Filter],
        max_results: int = 200,
        max_enrich: int = 80,
        score_fn=None,
    ) -> ScreenerResult:
        """Apply CHEAP filters → enrich survivors → score → apply EXPENSIVE
        filters (some of which depend on scores)."""
        rows = self.universe.rows()
        cheap = [f for f in filters if f.is_cheap()]
        expensive = [f for f in filters if not f.is_cheap()]

        survivors = [r for r in rows if all(_check_row(r, f) for f in cheap)]
        warnings: list = []
        if len(survivors) > max_enrich:
            warnings.append(
                f"Filter matched {len(survivors)} candidates; enriching first {max_enrich} "
                f"to keep latency reasonable. Add more filters to narrow."
            )
        to_enrich = survivors[:max_enrich]

        enriched = self.universe.enrich_many(to_enrich, max_workers=8)
        failed = len(to_enrich) - len(enriched)

        # Compute scores for each enriched metric so score-based filters work.
        score_cache: dict = {}
        if score_fn is not None:
            for m in enriched:
                try:
                    score_cache[m.security.ticker] = score_fn(m)
                except Exception:
                    pass

        matches = [
            m for m in enriched
            if all(_check_metric(m, f, score_cache.get(m.security.ticker)) for f in expensive)
        ]
        matches = matches[:max_results]

        return ScreenerResult(
            matches=matches,
            total_universe=len(rows),
            after_cheap_filters=len(survivors),
            enriched_count=len(enriched),
            failed_enrichment=failed,
            warnings=warnings,
            score_cache=score_cache,
        )
