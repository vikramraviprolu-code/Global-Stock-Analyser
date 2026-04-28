"""HistoricalPriceProvider: Stooq CSV first, yfinance fallback."""
from __future__ import annotations
import io
from datetime import datetime
from typing import List, Optional, Protocol
import pandas as pd
import requests

from providers.cache import TTLCache


class HistoricalPriceProvider(Protocol):
    def fetch(self, ticker: str) -> Optional[pd.DataFrame]: ...
    def source_for(self, ticker: str) -> tuple[str, Optional[str]]: ...


class StooqYFinanceProvider:
    """Tries Stooq CSV first (free, no key), falls back to yfinance."""
    STOOQ_URL = "https://stooq.com/q/d/l/?s={sym}.us&i=d"

    def __init__(self, cache: Optional[TTLCache] = None):
        self._cache = cache or TTLCache(default_ttl=1800)
        self._last_source: dict[str, tuple[str, Optional[str]]] = {}

    def fetch(self, ticker: str) -> Optional[pd.DataFrame]:
        sym = ticker.lower().strip()
        cache_key = f"hist:{sym}"
        cached = self._cache.get(cache_key)
        if cached is not None:
            return cached

        df = self._fetch_stooq(sym)
        if df is None or df.empty:
            df = self._fetch_yfinance(ticker)
        if df is not None and not df.empty:
            self._cache.set(cache_key, df)
        return df

    def source_for(self, ticker: str) -> tuple[str, Optional[str]]:
        return self._last_source.get(ticker.lower(), ("unknown", None))

    def _fetch_stooq(self, sym: str) -> Optional[pd.DataFrame]:
        try:
            url = self.STOOQ_URL.format(sym=sym)
            r = requests.get(url, timeout=10, headers={"User-Agent": "Mozilla/5.0"})
            if r.status_code != 200 or not r.text:
                return None
            text = r.text
            if "apikey" in text[:300].lower() or "Date" not in text[:50]:
                return None
            df = pd.read_csv(io.StringIO(text))
            if df.empty or "Close" not in df.columns:
                return None
            df["Date"] = pd.to_datetime(df["Date"])
            df = df.sort_values("Date").reset_index(drop=True)
            self._last_source[sym] = ("Stooq", url)
            return df
        except Exception:
            return None

    def _fetch_yfinance(self, ticker: str) -> Optional[pd.DataFrame]:
        try:
            import yfinance as yf
            t = yf.Ticker(ticker.upper())
            hist = t.history(period="2y", interval="1d", auto_adjust=False)
            if hist is None or hist.empty:
                return None
            df = hist.reset_index().rename(columns={
                "Date": "Date", "Open": "Open", "High": "High",
                "Low": "Low", "Close": "Close", "Volume": "Volume",
            })
            df["Date"] = pd.to_datetime(df["Date"]).dt.tz_localize(None)
            df = df[["Date", "Open", "High", "Low", "Close", "Volume"]].sort_values("Date").reset_index(drop=True)
            self._last_source[ticker.lower()] = (
                "Yahoo Finance",
                f"https://finance.yahoo.com/quote/{ticker.upper()}",
            )
            return df
        except Exception:
            return None


def closes_from_df(df: pd.DataFrame) -> List[float]:
    """Drop NaN closes (holidays, missing bars) so indicators don't see NaN."""
    return [float(x) for x in df["Close"].tolist() if x == x]  # x == x filters NaN


def volumes_from_df(df: pd.DataFrame) -> List[float]:
    if "Volume" not in df.columns:
        return []
    return [float(x) for x in df["Volume"].tolist() if x == x]


def last_date_iso(df: pd.DataFrame) -> Optional[str]:
    if df is None or df.empty:
        return None
    return df["Date"].iloc[-1].strftime("%Y-%m-%d")


def freshness_from_last_date(last_date: Optional[str]) -> str:
    if not last_date:
        return "unavailable"
    try:
        d = datetime.strptime(last_date, "%Y-%m-%d")
        days = (datetime.now() - d).days
        if days <= 1:
            return "previous-close"
        if days <= 5:
            return "delayed"
        return "historical-only"
    except Exception:
        return "historical-only"
