"""Market metadata: exchange suffixes, regions, currencies, regional filter thresholds, FX."""
from __future__ import annotations
import time
from typing import Optional, Dict, Tuple

# Yahoo Finance suffix → (exchange, country, region, currency, currency_symbol)
SUFFIX_MAP: Dict[str, Dict[str, str]] = {
    "":     {"exchange": "NYSE/Nasdaq", "country": "USA",         "region": "Americas", "currency": "USD", "symbol": "$"},
    "NS":   {"exchange": "NSE",         "country": "India",       "region": "Asia",     "currency": "INR", "symbol": "₹"},
    "BO":   {"exchange": "BSE",         "country": "India",       "region": "Asia",     "currency": "INR", "symbol": "₹"},
    "L":    {"exchange": "LSE",         "country": "UK",          "region": "Europe",   "currency": "GBP", "symbol": "£"},
    "PA":   {"exchange": "Euronext Paris",     "country": "France",       "region": "Europe", "currency": "EUR", "symbol": "€"},
    "AS":   {"exchange": "Euronext Amsterdam", "country": "Netherlands",  "region": "Europe", "currency": "EUR", "symbol": "€"},
    "BR":   {"exchange": "Euronext Brussels",  "country": "Belgium",      "region": "Europe", "currency": "EUR", "symbol": "€"},
    "LS":   {"exchange": "Euronext Lisbon",    "country": "Portugal",     "region": "Europe", "currency": "EUR", "symbol": "€"},
    "DE":   {"exchange": "Xetra",       "country": "Germany",     "region": "Europe",   "currency": "EUR", "symbol": "€"},
    "F":    {"exchange": "Frankfurt",   "country": "Germany",     "region": "Europe",   "currency": "EUR", "symbol": "€"},
    "SW":   {"exchange": "SIX Swiss",   "country": "Switzerland", "region": "Europe",   "currency": "CHF", "symbol": "Fr."},
    "MI":   {"exchange": "Borsa Italiana", "country": "Italy",    "region": "Europe",   "currency": "EUR", "symbol": "€"},
    "MC":   {"exchange": "Bolsa de Madrid", "country": "Spain",   "region": "Europe",   "currency": "EUR", "symbol": "€"},
    "ST":   {"exchange": "Nasdaq Stockholm", "country": "Sweden", "region": "Europe",   "currency": "SEK", "symbol": "kr"},
    "HE":   {"exchange": "Nasdaq Helsinki",  "country": "Finland", "region": "Europe",  "currency": "EUR", "symbol": "€"},
    "CO":   {"exchange": "Nasdaq Copenhagen", "country": "Denmark", "region": "Europe", "currency": "DKK", "symbol": "kr"},
    "OL":   {"exchange": "Oslo Bors",   "country": "Norway",      "region": "Europe",   "currency": "NOK", "symbol": "kr"},
    "T":    {"exchange": "TSE",         "country": "Japan",       "region": "Asia",     "currency": "JPY", "symbol": "¥"},
    "HK":   {"exchange": "HKEX",        "country": "Hong Kong",   "region": "Asia",     "currency": "HKD", "symbol": "HK$"},
    "KS":   {"exchange": "KOSPI",       "country": "South Korea", "region": "Asia",     "currency": "KRW", "symbol": "₩"},
    "KQ":   {"exchange": "KOSDAQ",      "country": "South Korea", "region": "Asia",     "currency": "KRW", "symbol": "₩"},
    "TW":   {"exchange": "TWSE",        "country": "Taiwan",      "region": "Asia",     "currency": "TWD", "symbol": "NT$"},
    "TWO":  {"exchange": "TPEx",        "country": "Taiwan",      "region": "Asia",     "currency": "TWD", "symbol": "NT$"},
    "SI":   {"exchange": "SGX",         "country": "Singapore",   "region": "Asia",     "currency": "SGD", "symbol": "S$"},
    "AX":   {"exchange": "ASX",         "country": "Australia",   "region": "Asia-Pacific", "currency": "AUD", "symbol": "A$"},
    "SS":   {"exchange": "Shanghai SE", "country": "China",       "region": "Asia",     "currency": "CNY", "symbol": "¥"},
    "SZ":   {"exchange": "Shenzhen SE", "country": "China",       "region": "Asia",     "currency": "CNY", "symbol": "¥"},
    "TO":   {"exchange": "TSX",         "country": "Canada",      "region": "Americas", "currency": "CAD", "symbol": "C$"},
}

# Regional filter thresholds (local currency for price/volume; market cap in USD across the board)
REGIONAL_FILTERS: Dict[str, Dict[str, float]] = {
    "USA":         {"min_price": 5.0,    "min_volume": 500_000, "min_mcap_usd": 2_000_000_000},
    "India":       {"min_price": 100.0,  "min_volume": 500_000, "min_mcap_usd": 2_000_000_000},
    "UK":          {"min_price": 5.0,    "min_volume": 100_000, "min_mcap_usd": 2_000_000_000},
    "France":      {"min_price": 5.0,    "min_volume": 100_000, "min_mcap_usd": 2_000_000_000},
    "Germany":     {"min_price": 5.0,    "min_volume": 100_000, "min_mcap_usd": 2_000_000_000},
    "Netherlands": {"min_price": 5.0,    "min_volume": 100_000, "min_mcap_usd": 2_000_000_000},
    "Belgium":     {"min_price": 5.0,    "min_volume": 100_000, "min_mcap_usd": 2_000_000_000},
    "Portugal":    {"min_price": 5.0,    "min_volume": 100_000, "min_mcap_usd": 2_000_000_000},
    "Switzerland": {"min_price": 5.0,    "min_volume": 100_000, "min_mcap_usd": 2_000_000_000},
    "Italy":       {"min_price": 5.0,    "min_volume": 100_000, "min_mcap_usd": 2_000_000_000},
    "Spain":       {"min_price": 5.0,    "min_volume": 100_000, "min_mcap_usd": 2_000_000_000},
    "Sweden":      {"min_price": 50.0,   "min_volume": 100_000, "min_mcap_usd": 2_000_000_000},
    "Finland":     {"min_price": 5.0,    "min_volume": 100_000, "min_mcap_usd": 2_000_000_000},
    "Denmark":     {"min_price": 50.0,   "min_volume": 100_000, "min_mcap_usd": 2_000_000_000},
    "Norway":      {"min_price": 50.0,   "min_volume": 100_000, "min_mcap_usd": 2_000_000_000},
    "Japan":       {"min_price": 500.0,  "min_volume": 300_000, "min_mcap_usd": 2_000_000_000},
    "Hong Kong":   {"min_price": 5.0,    "min_volume": 500_000, "min_mcap_usd": 2_000_000_000},
    "South Korea": {"min_price": 5_000.0, "min_volume": 100_000, "min_mcap_usd": 2_000_000_000},
    "Taiwan":      {"min_price": 50.0,   "min_volume": 100_000, "min_mcap_usd": 2_000_000_000},
    "Singapore":   {"min_price": 1.0,    "min_volume": 100_000, "min_mcap_usd": 1_000_000_000},
    "Australia":   {"min_price": 2.0,    "min_volume": 100_000, "min_mcap_usd": 2_000_000_000},
    "China":       {"min_price": 5.0,    "min_volume": 500_000, "min_mcap_usd": 2_000_000_000},
    "Canada":      {"min_price": 5.0,    "min_volume": 100_000, "min_mcap_usd": 2_000_000_000},
}

DEFAULT_FILTER = {"min_price": 5.0, "min_volume": 100_000, "min_mcap_usd": 2_000_000_000}

_fx_cache: Dict[str, Tuple[float, float]] = {}
_FX_TTL = 60 * 60 * 6  # 6 hours


def parse_ticker(ticker: str) -> Tuple[str, str]:
    """Split AAPL → ('AAPL', '') or RELIANCE.NS → ('RELIANCE', 'NS')."""
    t = ticker.upper().strip()
    if "." in t:
        base, suf = t.rsplit(".", 1)
        return base, suf
    return t, ""


def listing_meta(ticker: str) -> Dict[str, str]:
    """Return market metadata for a ticker based on its suffix."""
    _, suf = parse_ticker(ticker)
    meta = SUFFIX_MAP.get(suf, SUFFIX_MAP[""])
    return dict(meta)


def regional_filter(country: str) -> Dict[str, float]:
    return REGIONAL_FILTERS.get(country, DEFAULT_FILTER)


def fx_rate(from_ccy: str, to_ccy: str = "USD") -> Optional[float]:
    """Return 1 unit of from_ccy in to_ccy. Cached. None if fetch fails."""
    if from_ccy == to_ccy:
        return 1.0
    key = f"{from_ccy}{to_ccy}"
    cached = _fx_cache.get(key)
    if cached and time.time() - cached[0] < _FX_TTL:
        return cached[1]
    try:
        import yfinance as yf
        pair = f"{from_ccy}{to_ccy}=X"
        t = yf.Ticker(pair)
        hist = t.history(period="5d", interval="1d", auto_adjust=False)
        if hist is None or hist.empty:
            return None
        rate = float(hist["Close"].iloc[-1])
        _fx_cache[key] = (time.time(), rate)
        return rate
    except Exception:
        return None


def to_usd(amount: Optional[float], from_ccy: str) -> Optional[float]:
    """Convert local-currency amount to USD."""
    if amount is None:
        return None
    rate = fx_rate(from_ccy, "USD")
    if rate is None:
        return None
    return amount * rate


def fmt_currency(amount: Optional[float], currency: str, symbol: str) -> str:
    if amount is None:
        return "—"
    if currency in ("JPY", "KRW", "TWD", "INR", "HKD"):
        return f"{symbol}{amount:,.0f}"
    return f"{symbol}{amount:,.2f}"


def fmt_mcap(amount: Optional[float], currency: str, symbol: str) -> str:
    if amount is None:
        return "—"
    if amount >= 1e12:
        return f"{symbol}{amount/1e12:.2f}T"
    if amount >= 1e9:
        return f"{symbol}{amount/1e9:.2f}B"
    if amount >= 1e6:
        return f"{symbol}{amount/1e6:.1f}M"
    return f"{symbol}{amount:,.0f}"
