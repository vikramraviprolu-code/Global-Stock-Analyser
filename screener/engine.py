"""Filter engine for the screener.

Two-phase filtering:
  1. CHEAP filters operate on raw universe rows (no network) — sector, country,
     region, listing_type, exchange.
  2. EXPENSIVE filters operate on enriched StockMetrics — price, mcap, P/E,
     RSI, perf, MA, etc.

A `Filter` is a typed dict-like spec that the engine compiles into a callable.
Stack any number of filters; results are AND-combined.
"""
from __future__ import annotations
from dataclasses import dataclass, field
from typing import Any, Callable, List, Optional

from models import StockMetrics


# ---------- Filter spec -------------------------------------------------------

@dataclass
class Filter:
    """A typed predicate. `kind` decides how `value` is interpreted.

    Kinds:
      - sector_in       value: List[str]
      - country_in      value: List[str]
      - region_in       value: List[str]
      - exchange_in     value: List[str]
      - price_min       value: float (in metric's local currency)
      - price_max       value: float
      - mcap_usd_min    value: float
      - mcap_usd_max    value: float
      - pe_min          value: float
      - pe_max          value: float
      - rsi_min         value: float
      - rsi_max         value: float
      - perf5d_min      value: float (percent)
      - perf5d_max      value: float
      - pct_from_low_max value: float (percent — within N% of 52W low)
      - above_ma200     value: bool
      - dividend_min    value: float
    """
    kind: str
    value: Any
    label: Optional[str] = None  # for UI display

    def is_cheap(self) -> bool:
        return self.kind in {"sector_in", "country_in", "region_in", "exchange_in"}


# ---------- Compilation -------------------------------------------------------

def _v(sv) -> Optional[float]:
    if sv is None:
        return None
    val = getattr(sv, "value", None)
    return val if isinstance(val, (int, float)) else None


def _check_row(row: dict, f: Filter) -> bool:
    """For cheap filters (raw universe row dict)."""
    if f.kind == "sector_in":
        return (row.get("sector") or "").lower() in {s.lower() for s in f.value}
    if f.kind == "country_in":
        return (row.get("country") or "").lower() in {s.lower() for s in f.value}
    if f.kind == "region_in":
        return (row.get("region") or "").lower() in {s.lower() for s in f.value}
    if f.kind == "exchange_in":
        return (row.get("exchange") or "").lower() in {s.lower() for s in f.value}
    return True


def _check_metric(m: StockMetrics, f: Filter) -> bool:
    """For expensive filters (enriched StockMetrics)."""
    if f.kind in {"sector_in", "country_in", "region_in", "exchange_in"}:
        sec = m.security
        haystack = {
            "sector_in": (sec.sector or "").lower(),
            "country_in": (sec.country or "").lower(),
            "region_in": (sec.region or "").lower(),
            "exchange_in": (sec.exchange or "").lower(),
        }[f.kind]
        return haystack in {s.lower() for s in f.value}

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

    pct_low = _v(m.percent_from_low)
    if f.kind == "pct_from_low_max":
        return pct_low is not None and pct_low <= f.value

    if f.kind == "above_ma200":
        ma200 = _v(m.ma200)
        if price is None or ma200 is None:
            return False
        return (price > ma200) is bool(f.value)

    if f.kind == "dividend_min":
        dy = _v(m.dividend_yield) if m.dividend_yield else None
        return dy is not None and dy >= f.value

    return True


# ---------- Engine ------------------------------------------------------------

@dataclass
class ScreenerResult:
    matches: List[StockMetrics]
    total_universe: int
    after_cheap_filters: int
    enriched_count: int
    failed_enrichment: int = 0
    warnings: List[str] = field(default_factory=list)

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
        max_enrich: int = 60,
    ) -> ScreenerResult:
        """Apply CHEAP filters → enrich survivors → apply EXPENSIVE filters.

        max_enrich caps the number of network round-trips so a wide screen
        doesn't try to enrich the whole universe at once.
        """
        rows = self.universe.rows()
        cheap = [f for f in filters if f.is_cheap()]
        expensive = [f for f in filters if not f.is_cheap()]

        # Phase 1: cheap filters, no network
        survivors = [r for r in rows if all(_check_row(r, f) for f in cheap)]
        warnings: List[str] = []
        if len(survivors) > max_enrich:
            warnings.append(
                f"Filter matched {len(survivors)} candidates; enriching first {max_enrich} "
                f"to keep latency reasonable. Add more filters to narrow."
            )
        to_enrich = survivors[:max_enrich]

        # Phase 2: enrich (network) in parallel
        enriched = self.universe.enrich_many(to_enrich, max_workers=8)
        failed = len(to_enrich) - len(enriched)

        # Phase 3: expensive filters
        matches = [m for m in enriched if all(_check_metric(m, f) for f in expensive)]
        matches = matches[:max_results]

        return ScreenerResult(
            matches=matches,
            total_universe=len(rows),
            after_cheap_filters=len(survivors),
            enriched_count=len(enriched),
            failed_enrichment=failed,
            warnings=warnings,
        )
