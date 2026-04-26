"""Free market data: Stooq CSV for OHLCV, yfinance fallback for fundamentals."""
from __future__ import annotations
import io
import time
import pandas as pd
import requests
from datetime import datetime, timezone
from typing import Optional

STOOQ_URL = "https://stooq.com/q/d/l/?s={sym}.us&i=d"
_cache = {}
_CACHE_TTL = 60 * 30  # 30 min


def _now():
    return time.time()


def _fetch_stooq_csv(ticker: str) -> Optional[pd.DataFrame]:
    """Try Stooq CSV (free, no key — but Stooq now gates many tickers)."""
    sym = ticker.lower().strip()
    url = STOOQ_URL.format(sym=sym)
    try:
        r = requests.get(url, timeout=10, headers={"User-Agent": "Mozilla/5.0"})
        if r.status_code != 200:
            return None
        text = r.text
        # Stooq returns plain-text "error.txt" / apikey nag when gated
        if not text or "apikey" in text[:300].lower() or "Date" not in text[:50]:
            return None
        df = pd.read_csv(io.StringIO(text))
        if df.empty or "Close" not in df.columns:
            return None
        df["Date"] = pd.to_datetime(df["Date"])
        df = df.sort_values("Date").reset_index(drop=True)
        return df
    except Exception:
        return None


def _fetch_yfinance_history(ticker: str) -> Optional[pd.DataFrame]:
    """yfinance daily OHLCV (free, no key). Normalize to Stooq-like columns."""
    try:
        import yfinance as yf
        t = yf.Ticker(ticker.upper())
        hist = t.history(period="2y", interval="1d", auto_adjust=False)
        if hist is None or hist.empty:
            return None
        df = hist.reset_index().rename(
            columns={"Date": "Date", "Open": "Open", "High": "High",
                     "Low": "Low", "Close": "Close", "Volume": "Volume"}
        )
        df["Date"] = pd.to_datetime(df["Date"]).dt.tz_localize(None)
        return df[["Date", "Open", "High", "Low", "Close", "Volume"]].sort_values("Date").reset_index(drop=True)
    except Exception:
        return None


def fetch_stooq_history(ticker: str) -> Optional[pd.DataFrame]:
    """Try Stooq CSV first, fall back to yfinance. Cached. Name kept for compat."""
    sym = ticker.lower().strip()
    key = f"hist:{sym}"
    cached = _cache.get(key)
    if cached and _now() - cached[0] < _CACHE_TTL:
        return cached[1]
    df = _fetch_stooq_csv(ticker)
    if df is None or df.empty:
        df = _fetch_yfinance_history(ticker)
    _cache[key] = (_now(), df)
    return df


def compute_indicators(df: pd.DataFrame) -> dict:
    """Compute technical indicators from OHLCV DataFrame."""
    if df is None or df.empty or len(df) < 20:
        return {}
    close = df["Close"].astype(float)
    vol = df["Volume"].astype(float) if "Volume" in df.columns else pd.Series([0] * len(df))
    last_close = float(close.iloc[-1])
    # 52-week window = 252 trading days
    window_252 = close.iloc[-252:] if len(close) >= 252 else close
    high_52w = float(window_252.max())
    low_52w = float(window_252.min())

    def perf(n):
        if len(close) <= n:
            return None
        prev = float(close.iloc[-(n + 1)])
        if prev == 0:
            return None
        return (last_close / prev - 1.0) * 100

    def ma(n):
        if len(close) < n:
            return None
        return float(close.iloc[-n:].mean())

    def roc(n):
        if len(close) <= n:
            return None
        prev = float(close.iloc[-(n + 1)])
        if prev == 0:
            return None
        return (last_close / prev - 1.0) * 100

    def rsi(n=14):
        if len(close) <= n:
            return None
        delta = close.diff().dropna()
        gain = delta.clip(lower=0)
        loss = -delta.clip(upper=0)
        avg_gain = gain.rolling(n).mean().iloc[-1]
        avg_loss = loss.rolling(n).mean().iloc[-1]
        if avg_loss == 0:
            return 100.0
        rs = avg_gain / avg_loss
        return float(100 - (100 / (1 + rs)))

    avg_vol_20 = float(vol.iloc[-20:].mean()) if len(vol) >= 20 else float(vol.mean())

    return {
        "price": last_close,
        "high_52w": high_52w,
        "low_52w": low_52w,
        "pct_from_low": ((last_close - low_52w) / low_52w * 100) if low_52w else None,
        "pct_from_high": ((last_close - high_52w) / high_52w * 100) if high_52w else None,
        "perf_5d": perf(5),
        "ma_20": ma(20),
        "ma_50": ma(50),
        "ma_200": ma(200),
        "rsi_14": rsi(14),
        "roc_14": roc(14),
        "roc_21": roc(21),
        "avg_volume": avg_vol_20,
        "last_date": df["Date"].iloc[-1].strftime("%Y-%m-%d"),
        "bars": len(df),
    }


def fetch_fundamentals(ticker: str) -> dict:
    """yfinance fallback for market cap, P/E, sector, industry. Best effort."""
    key = f"fund:{ticker.upper()}"
    cached = _cache.get(key)
    if cached and _now() - cached[0] < _CACHE_TTL:
        return cached[1]
    out = {"source": "unavailable"}
    try:
        import yfinance as yf
        t = yf.Ticker(ticker.upper())
        info = {}
        try:
            info = t.info or {}
        except Exception:
            info = {}
        if info:
            out = {
                "market_cap": info.get("marketCap"),
                "trailing_pe": info.get("trailingPE"),
                "sector": info.get("sector"),
                "industry": info.get("industry"),
                "company": info.get("longName") or info.get("shortName"),
                "currency": info.get("currency"),
                "country": info.get("country"),
                "exchange": info.get("exchange") or info.get("fullExchangeName"),
                "source": "yfinance",
            }
    except Exception:
        pass
    _cache[key] = (_now(), out)
    return out


def freshness_label(last_date_str: Optional[str]) -> str:
    if not last_date_str:
        return "Unavailable"
    try:
        last = datetime.strptime(last_date_str, "%Y-%m-%d")
        today = datetime.now()
        days = (today - last).days
        if days <= 1:
            return "Previous close"
        if days <= 5:
            return "Delayed"
        return "Historical only"
    except Exception:
        return "Historical only"
