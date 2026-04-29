"""UniverseService: lazily enriches the curated universe.csv into a list of
StockMetrics. Each metric is a SourcedValue with provenance.

Strategy:
  - On first request, read universe_global.csv into memory (no network).
  - For a screener call, the engine asks for a `sector_country_filter` first
    (cheap), then enrichment is performed on the surviving subset (network).
  - Per-ticker enrichment caches for 30 min. Failed live fetches fall back
    to MockProvider entries clearly labelled freshness="mock".
"""
from __future__ import annotations
import os
import csv
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Callable, List, Optional

from models import Security, SourcedValue, StockMetrics
from markets import listing_meta, to_usd
from calc import compute_indicators
from providers.cache import TTLCache
from providers.historical import (
    StooqYFinanceProvider, closes_from_df, volumes_from_df,
    last_date_iso, freshness_from_last_date,
)
from providers.fundamentals import YFinanceFundamentals
from providers.mock import MockProvider
from providers.events import EventsProvider

UNIVERSE_PATH = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "data", "universe_global.csv",
)


class UniverseService:
    def __init__(
        self,
        historical: Optional[StooqYFinanceProvider] = None,
        fundamentals: Optional[YFinanceFundamentals] = None,
        mock: Optional[MockProvider] = None,
        events: Optional[EventsProvider] = None,
        ttl_seconds: int = 1800,
    ):
        cache = TTLCache(default_ttl=ttl_seconds)
        self.historical = historical or StooqYFinanceProvider(cache=cache)
        self.fundamentals = fundamentals or YFinanceFundamentals(cache=cache)
        self.mock = mock or MockProvider()
        self.events = events or EventsProvider()
        self._enriched_cache = TTLCache(default_ttl=ttl_seconds)
        self._rows: Optional[List[dict]] = None
        self._row_lock = threading.Lock()

    # ----- universe rows ------------------------------------------------------

    def rows(self) -> List[dict]:
        with self._row_lock:
            if self._rows is None:
                self._rows = self._load_rows()
            return self._rows

    def _load_rows(self) -> List[dict]:
        rows: List[dict] = []
        if not os.path.exists(UNIVERSE_PATH):
            return rows
        with open(UNIVERSE_PATH) as f:
            for r in csv.DictReader(f):
                rows.append(r)
        return rows

    # ----- enrichment ---------------------------------------------------------

    def enrich_ticker(self, ticker: str, allow_mock_fallback: bool = True) -> StockMetrics:
        """Enrich a single ticker. If it's in the curated universe, use that
        row's metadata; otherwise synthesize a row from suffix-based meta so
        the watchlist / compare pages can take any resolvable ticker."""
        ticker = ticker.upper().strip()
        existing = next((r for r in self.rows() if r["ticker"].upper() == ticker), None)
        if existing:
            return self.enrich(existing, allow_mock_fallback=allow_mock_fallback)
        meta = listing_meta(ticker)
        synthetic = {
            "ticker": ticker,
            "company": ticker,
            "sector": None,
            "industry": None,
            "country": meta.get("country"),
            "region": meta.get("region"),
            "exchange": meta.get("exchange"),
            "currency": meta.get("currency"),
        }
        return self.enrich(synthetic, allow_mock_fallback=allow_mock_fallback)

    def fetch_history_for(self, ticker: str):
        """Expose raw OHLC for sparkline / chart endpoints."""
        return self.historical.fetch(ticker)

    def enrich(self, row: dict, allow_mock_fallback: bool = True) -> StockMetrics:
        ticker = row["ticker"].upper()
        cached = self._enriched_cache.get(ticker)
        if cached is not None:
            return cached

        meta = listing_meta(ticker)
        currency = row.get("currency") or meta["currency"]
        country = row.get("country") or meta["country"]
        region = row.get("region") or meta["region"]
        exchange = row.get("exchange") or meta["exchange"]
        sector = row.get("sector")
        industry = row.get("industry")

        df = self.historical.fetch(ticker)
        fund = self.fundamentals.fetch(ticker)

        if df is None or df.empty:
            if not allow_mock_fallback:
                # Build an "all unavailable" metrics record
                return self._unavailable_metrics(
                    ticker, row.get("company") or ticker,
                    sector, industry, country, region, exchange, currency,
                )
            metrics = self.mock.metrics_for(
                ticker, sector or "Technology", industry or "—",
                country, region, exchange, currency,
            )
            self._enriched_cache.set(ticker, metrics)
            return metrics

        closes = closes_from_df(df)
        volumes = volumes_from_df(df)
        ind = compute_indicators(closes, volumes)
        last_date = last_date_iso(df)
        freshness = freshness_from_last_date(last_date)
        confidence = "high" if freshness in ("real-time", "delayed", "previous-close") else "medium"

        hist_source, hist_url = self.historical.source_for(ticker)
        retrieved_at = ""  # default to now via SourcedValue.__post_init__

        def sv_price(value):
            return SourcedValue(
                value=value, source_name=hist_source, source_url=hist_url,
                retrieved_at=retrieved_at, freshness=freshness, confidence=confidence,
                verified_source_count=1,
            )

        def sv_fund(value, source_url=None):
            if value is None:
                return SourcedValue.unavailable(fund.get("source_name", "Yahoo Finance"))
            return SourcedValue(
                value=value,
                source_name=fund.get("source_name", "Yahoo Finance"),
                source_url=source_url or fund.get("source_url"),
                retrieved_at=retrieved_at, freshness="cached", confidence="medium",
                verified_source_count=1,
            )

        market_cap_local = fund.get("market_cap")
        market_cap_usd = to_usd(market_cap_local, currency) if market_cap_local else None

        sec = Security(
            company_name=fund.get("company") or row.get("company") or ticker,
            ticker=ticker, exchange=exchange, country=country, region=region,
            currency=currency, sector=fund.get("sector") or sector,
            industry=fund.get("industry") or industry, listing_type="common-stock",
        )

        metrics = StockMetrics(
            security=sec,
            price=sv_price(ind.get("price")),
            market_cap_local=sv_fund(market_cap_local),
            market_cap_usd=sv_fund(market_cap_usd),
            trailing_pe=sv_fund(fund.get("trailing_pe")),
            forward_pe=sv_fund(fund.get("forward_pe")),
            price_to_book=sv_fund(fund.get("price_to_book")),
            dividend_yield=sv_fund(fund.get("dividend_yield")),
            avg_daily_volume=sv_price(ind.get("avg_volume")),
            fifty_two_week_low=sv_price(ind.get("low_52w")),
            fifty_two_week_high=sv_price(ind.get("high_52w")),
            percent_from_low=sv_price(ind.get("pct_from_low")),
            five_day_performance=sv_price(ind.get("perf_5d")),
            rsi14=sv_price(ind.get("rsi_14")),
            roc14=sv_price(ind.get("roc_14")),
            roc21=sv_price(ind.get("roc_21")),
            ma20=sv_price(ind.get("ma_20")),
            ma50=sv_price(ind.get("ma_50")),
            ma200=sv_price(ind.get("ma_200")),
        )
        self._enriched_cache.set(ticker, metrics)
        return metrics

    def enrich_many(self, rows: List[dict], max_workers: int = 8,
                    progress: Optional[Callable[[int, int], None]] = None) -> List[StockMetrics]:
        out: List[StockMetrics] = []
        total = len(rows)
        done = 0
        with ThreadPoolExecutor(max_workers=max_workers) as ex:
            futures = {ex.submit(self.enrich, r): r for r in rows}
            for fut in as_completed(futures):
                done += 1
                try:
                    res = fut.result()
                    if res:
                        out.append(res)
                except Exception:
                    continue
                if progress:
                    progress(done, total)
        return out

    def _unavailable_metrics(self, ticker, company, sector, industry,
                             country, region, exchange, currency) -> StockMetrics:
        sec = Security(
            company_name=company, ticker=ticker, exchange=exchange,
            country=country, region=region, currency=currency,
            sector=sector, industry=industry, listing_type="common-stock",
        )
        un = SourcedValue.unavailable(source_name="all sources")
        return StockMetrics(
            security=sec,
            price=un, market_cap_local=un, market_cap_usd=un,
            trailing_pe=un, avg_daily_volume=un,
            fifty_two_week_low=un, fifty_two_week_high=un,
            percent_from_low=un, five_day_performance=un,
            rsi14=un, roc14=un, roc21=un, ma20=un, ma50=un, ma200=un,
        )

    def stats(self) -> dict:
        return {
            "universe_size": len(self.rows()),
            "enriched_cache": self._enriched_cache.stats(),
            "last_loaded": time.time(),
        }
