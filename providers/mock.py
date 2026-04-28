"""MockProvider — deterministic synthetic data when no live source is reachable.

Always labelled clearly: every SourcedValue carries freshness="mock" and a
warning. Used as a last-resort fallback so the screener still demonstrates UX
when offline / rate-limited / behind a corporate firewall.
"""
from __future__ import annotations
import hashlib
from typing import Optional

from models import SourcedValue, Security, StockMetrics


def _h(seed: str, lo: float, hi: float) -> float:
    """Deterministic float in [lo, hi] from a string seed."""
    digest = hashlib.sha256(seed.encode("utf-8")).digest()
    raw = int.from_bytes(digest[:8], "big") / 2**64
    return lo + (hi - lo) * raw


class MockProvider:
    """Generates plausible-looking data so the UI is never broken offline."""

    def metrics_for(self, ticker: str, sector: str = "Technology",
                    industry: str = "—", country: str = "USA",
                    region: str = "Americas", exchange: str = "Nasdaq",
                    currency: str = "USD") -> StockMetrics:
        sec = Security(
            company_name=f"{ticker} Mock Co.",
            ticker=ticker,
            exchange=exchange,
            country=country,
            region=region,
            currency=currency,
            sector=sector,
            industry=industry,
            listing_type="common-stock",
        )
        price = round(_h(ticker + "p", 10, 400), 2)
        low_52 = round(price * (1 - _h(ticker + "l", 0.05, 0.40)), 2)
        high_52 = round(price * (1 + _h(ticker + "h", 0.02, 0.35)), 2)
        ma20 = round(price * _h(ticker + "m20", 0.95, 1.05), 2)
        ma50 = round(price * _h(ticker + "m50", 0.92, 1.08), 2)
        ma200 = round(price * _h(ticker + "m200", 0.85, 1.15), 2)
        rsi = round(_h(ticker + "rsi", 30, 75), 1)
        roc14 = round(_h(ticker + "r14", -10, 12), 2)
        roc21 = round(_h(ticker + "r21", -12, 14), 2)
        p5 = round(_h(ticker + "p5", -6, 7), 2)
        avg_vol = round(_h(ticker + "v", 200_000, 5_000_000), 0)
        mcap_local = round(_h(ticker + "mc", 0.5e9, 200e9), 0)

        def mock(value):
            return SourcedValue.mock(value)

        return StockMetrics(
            security=sec,
            price=mock(price),
            market_cap_local=mock(mcap_local),
            market_cap_usd=mock(mcap_local),  # mock assumes USD
            trailing_pe=mock(round(_h(ticker + "pe", 5, 40), 2)),
            forward_pe=mock(round(_h(ticker + "fpe", 5, 35), 2)),
            price_to_book=mock(round(_h(ticker + "pb", 0.5, 8), 2)),
            dividend_yield=mock(round(_h(ticker + "dy", 0, 4), 2)),
            avg_daily_volume=mock(avg_vol),
            fifty_two_week_low=mock(low_52),
            fifty_two_week_high=mock(high_52),
            percent_from_low=mock(round((price - low_52) / low_52 * 100, 2)),
            five_day_performance=mock(p5),
            rsi14=mock(rsi),
            roc14=mock(roc14),
            roc21=mock(roc21),
            ma20=mock(ma20),
            ma50=mock(ma50),
            ma200=mock(ma200),
        )
