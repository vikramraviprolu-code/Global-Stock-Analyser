"""Resolve user input (ticker or company name) → list of candidate listings."""
from __future__ import annotations
import os
import csv
import time
from typing import List, Dict, Optional
from markets import SUFFIX_MAP, parse_ticker, listing_meta

UNIVERSE_PATH = os.path.join(os.path.dirname(__file__), "data", "universe_global.csv")

_universe_cache: Optional[List[Dict]] = None
_search_cache: Dict[str, tuple] = {}
_SEARCH_TTL = 60 * 60  # 1 hour


def load_universe() -> List[Dict]:
    global _universe_cache
    if _universe_cache is not None:
        return _universe_cache
    rows = []
    if os.path.exists(UNIVERSE_PATH):
        with open(UNIVERSE_PATH) as f:
            for r in csv.DictReader(f):
                rows.append(r)
    _universe_cache = rows
    return rows


def _candidate_from_universe(row: Dict) -> Dict:
    meta = listing_meta(row["ticker"])
    return {
        "ticker": row["ticker"].upper(),
        "company": row.get("company") or row["ticker"],
        "exchange": row.get("exchange") or meta["exchange"],
        "country": row.get("country") or meta["country"],
        "region": row.get("region") or meta["region"],
        "currency": row.get("currency") or meta["currency"],
        "sector": row.get("sector"),
        "industry": row.get("industry"),
        "source": "universe",
    }


def _candidate_from_yf_quote(q: Dict) -> Optional[Dict]:
    """Convert yfinance Search quote dict → candidate dict."""
    sym = (q.get("symbol") or "").upper().strip()
    if not sym:
        return None
    quote_type = (q.get("quoteType") or "").upper()
    if quote_type and quote_type != "EQUITY":
        return None
    meta = listing_meta(sym)
    return {
        "ticker": sym,
        "company": q.get("longname") or q.get("shortname") or sym,
        "exchange": q.get("exchDisp") or meta["exchange"],
        "country": meta["country"],
        "region": meta["region"],
        "currency": meta["currency"],
        "sector": q.get("sector"),
        "industry": q.get("industry"),
        "source": "yfinance",
    }


def _yfinance_search(query: str, limit: int = 8) -> List[Dict]:
    """Use yfinance Search if available."""
    out = []
    try:
        import yfinance as yf
        if hasattr(yf, "Search"):
            res = yf.Search(query, max_results=limit, news_count=0).quotes or []
            for q in res:
                c = _candidate_from_yf_quote(q)
                if c:
                    out.append(c)
    except Exception:
        pass
    return out


def search(query: str, limit: int = 10) -> List[Dict]:
    """Resolve ticker or company name to candidate listings, sorted by relevance."""
    q = (query or "").strip()
    if not q:
        return []
    key = q.lower()
    cached = _search_cache.get(key)
    if cached and time.time() - cached[0] < _SEARCH_TTL:
        return cached[1]

    universe = load_universe()
    q_upper = q.upper()
    q_lower = q.lower()
    candidates: List[Dict] = []
    seen_tickers = set()

    # 1) Exact ticker match in universe (with or without suffix)
    for row in universe:
        t = row["ticker"].upper()
        base, _ = parse_ticker(t)
        if t == q_upper or base == q_upper:
            cand = _candidate_from_universe(row)
            if cand["ticker"] not in seen_tickers:
                candidates.append(cand)
                seen_tickers.add(cand["ticker"])

    # 2) Company-name substring in universe
    for row in universe:
        company = (row.get("company") or "").lower()
        if q_lower in company and row["ticker"].upper() not in seen_tickers:
            cand = _candidate_from_universe(row)
            candidates.append(cand)
            seen_tickers.add(cand["ticker"])

    # 3) yfinance Search to extend coverage beyond curated universe
    for cand in _yfinance_search(q, limit=limit):
        if cand["ticker"] not in seen_tickers:
            candidates.append(cand)
            seen_tickers.add(cand["ticker"])

    # 4) If still empty and looks like a ticker, accept as-is (yfinance may resolve)
    if not candidates and q_upper.replace(".", "").replace("-", "").replace("&", "").isalnum():
        meta = listing_meta(q_upper)
        candidates.append({
            "ticker": q_upper,
            "company": q_upper,
            "exchange": meta["exchange"],
            "country": meta["country"],
            "region": meta["region"],
            "currency": meta["currency"],
            "sector": None,
            "industry": None,
            "source": "raw",
        })

    candidates = candidates[:limit]
    _search_cache[key] = (time.time(), candidates)
    return candidates


def needs_disambiguation(candidates: List[Dict], original_query: str) -> bool:
    """If ≥ 2 candidates from different exchanges/countries, ask user to pick."""
    if len(candidates) < 2:
        return False
    countries = {c["country"] for c in candidates}
    exchanges = {c["exchange"] for c in candidates}
    return len(countries) > 1 or len(exchanges) > 1
