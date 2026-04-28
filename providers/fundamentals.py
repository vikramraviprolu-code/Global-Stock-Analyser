"""FundamentalsProvider: yfinance .info best-effort."""
from __future__ import annotations
from typing import Optional, Protocol
from providers.cache import TTLCache


class FundamentalsProvider(Protocol):
    def fetch(self, ticker: str) -> dict: ...


def _to_float(x) -> Optional[float]:
    if x is None:
        return None
    if isinstance(x, (int, float)):
        return float(x)
    try:
        return float(str(x).replace(",", ""))
    except (ValueError, TypeError):
        return None


class YFinanceFundamentals:
    def __init__(self, cache: Optional[TTLCache] = None):
        self._cache = cache or TTLCache(default_ttl=1800)

    def fetch(self, ticker: str) -> dict:
        key = f"fund:{ticker.upper()}"
        cached = self._cache.get(key)
        if cached is not None:
            return cached

        out = {
            "source_name": "Yahoo Finance",
            "source_url": f"https://finance.yahoo.com/quote/{ticker.upper()}/key-statistics",
            "raw": {},
        }
        try:
            import yfinance as yf
            t = yf.Ticker(ticker.upper())
            info = {}
            try:
                info = t.info or {}
            except Exception:
                info = {}
            if info:
                out["raw"] = info
                out.update({
                    "company": info.get("longName") or info.get("shortName"),
                    "sector": info.get("sector"),
                    "industry": info.get("industry"),
                    "currency": info.get("currency"),
                    "country": info.get("country"),
                    "exchange": info.get("exchange") or info.get("fullExchangeName"),
                    "market_cap": _to_float(info.get("marketCap")),
                    "trailing_pe": _to_float(info.get("trailingPE")),
                    "forward_pe": _to_float(info.get("forwardPE")),
                    "price_to_book": _to_float(info.get("priceToBook")),
                    "dividend_yield": _to_float(info.get("dividendYield")),
                })
        except Exception:
            pass

        self._cache.set(key, out)
        return out
