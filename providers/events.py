"""EventsProvider — earnings, dividend, ex-dividend, split dates from yfinance.

Free-source only. If a date can't be verified, the SourcedValue carries
freshness="unavailable" and a clear warning rather than a fabricated value.
"""
from __future__ import annotations
from datetime import datetime
from typing import Optional

import pandas as pd

from models import SourcedValue
from providers.cache import TTLCache


def _date_str(x) -> Optional[str]:
    """Coerce a yfinance date / pandas Timestamp / string to YYYY-MM-DD."""
    if x is None:
        return None
    try:
        if isinstance(x, str):
            # already a string — accept ISO-ish formats
            return x[:10]
        if isinstance(x, (pd.Timestamp, datetime)):
            return x.strftime("%Y-%m-%d")
    except Exception:
        return None
    return None


class EventsProvider:
    """Fetches calendar / earnings / dividend events via yfinance."""

    def __init__(self, cache: Optional[TTLCache] = None):
        self._cache = cache or TTLCache(default_ttl=3600 * 4)  # 4 hours

    def fetch(self, ticker: str) -> dict:
        """Return dict of {earnings_date, dividend_date, ex_dividend_date,
        split_date} — each is a SourcedValue. Missing dates surface as
        SourcedValue.unavailable with a warning."""
        key = f"events:{ticker.upper()}"
        cached = self._cache.get(key)
        if cached is not None:
            return cached

        out = {
            "earnings_date": SourcedValue.unavailable("Yahoo Finance",
                "Earnings date not available from free public source."),
            "dividend_date": SourcedValue.unavailable("Yahoo Finance",
                "Dividend date not available."),
            "ex_dividend_date": SourcedValue.unavailable("Yahoo Finance",
                "Ex-dividend date not available."),
            "split_date": SourcedValue.unavailable("Yahoo Finance",
                "Split date not available."),
        }

        try:
            import yfinance as yf
            t = yf.Ticker(ticker.upper())
            url = f"https://finance.yahoo.com/quote/{ticker.upper()}/calendar"

            # yfinance .calendar returns a dict (newer yf) or DataFrame (older)
            cal = None
            try:
                cal = t.calendar
            except Exception:
                cal = None

            earnings_date = None
            div_date = None
            ex_div_date = None

            if isinstance(cal, dict):
                # New yfinance: dict with possibly 'Earnings Date' (list)
                ed = cal.get("Earnings Date")
                if isinstance(ed, list) and ed:
                    earnings_date = _date_str(ed[0])
                elif ed:
                    earnings_date = _date_str(ed)
                div_date = _date_str(cal.get("Dividend Date"))
                ex_div_date = _date_str(cal.get("Ex-Dividend Date"))
            elif isinstance(cal, pd.DataFrame) and not cal.empty:
                row = cal.iloc[:, 0]
                earnings_date = _date_str(row.get("Earnings Date"))
                div_date = _date_str(row.get("Dividend Date"))
                ex_div_date = _date_str(row.get("Ex-Dividend Date"))

            # Try .info for ex-dividend / dividend dates as fallback
            try:
                info = t.info or {}
                if not ex_div_date:
                    edt = info.get("exDividendDate")
                    if edt:
                        ex_div_date = _date_str(datetime.fromtimestamp(edt)) if isinstance(edt, (int, float)) else _date_str(edt)
                if not div_date:
                    ddt = info.get("dividendDate")
                    if ddt:
                        div_date = _date_str(datetime.fromtimestamp(ddt)) if isinstance(ddt, (int, float)) else _date_str(ddt)
            except Exception:
                pass

            now = datetime.now().isoformat(timespec="seconds")

            if earnings_date:
                out["earnings_date"] = SourcedValue(
                    value=earnings_date, source_name="Yahoo Finance",
                    source_url=url, retrieved_at=now, freshness="cached",
                    confidence="medium", verified_source_count=1,
                )
            if div_date:
                out["dividend_date"] = SourcedValue(
                    value=div_date, source_name="Yahoo Finance",
                    source_url=url, retrieved_at=now, freshness="cached",
                    confidence="medium", verified_source_count=1,
                )
            if ex_div_date:
                out["ex_dividend_date"] = SourcedValue(
                    value=ex_div_date, source_name="Yahoo Finance",
                    source_url=url, retrieved_at=now, freshness="cached",
                    confidence="medium", verified_source_count=1,
                )

            # Splits: from history actions if available
            try:
                actions = t.actions
                if isinstance(actions, pd.DataFrame) and not actions.empty and "Stock Splits" in actions.columns:
                    splits = actions[actions["Stock Splits"] > 0]
                    if not splits.empty:
                        last = splits.index[-1]
                        out["split_date"] = SourcedValue(
                            value=_date_str(last), source_name="Yahoo Finance",
                            source_url=url, retrieved_at=now,
                            freshness="historical-only", confidence="medium",
                            verified_source_count=1,
                            warning="Most recent past split — not necessarily upcoming.",
                        )
            except Exception:
                pass
        except Exception:
            pass

        self._cache.set(key, out)
        return out
