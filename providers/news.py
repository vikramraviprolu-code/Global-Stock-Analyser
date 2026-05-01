"""NewsProvider — recent headlines via yfinance .news (free, no API key).

Returns a list of headline dicts; never fabricates sentiment or content.
A lightweight rule-based digest (`summarize`) classifies headlines into
bullish / bearish / neutral buckets via keyword matching and groups them
by topic (earnings / product / m&a / regulation / executive / macro).
This is pure heuristic — explicitly **not** AI inference. The UI
labels output as "auto-extracted from headlines" so users know the
limit.
"""
from __future__ import annotations
from datetime import datetime, timezone
from typing import List, Optional

from providers.cache import TTLCache


def _ts_to_iso(ts) -> Optional[str]:
    if ts is None:
        return None
    try:
        return datetime.fromtimestamp(int(ts), tz=timezone.utc).isoformat(timespec="seconds")
    except (ValueError, TypeError):
        return None


def _safe_get(d, *keys):
    """Safely traverse a nested dict — yfinance schemas drift between versions."""
    cur = d
    for k in keys:
        if cur is None:
            return None
        if isinstance(cur, dict):
            cur = cur.get(k)
        else:
            return None
    return cur


# ---------- sentiment + topic dictionaries ---------------------------------

POSITIVE_TERMS = {
    "beat", "beats", "raise", "raises", "raised", "upgrade", "upgrades", "upgraded",
    "surge", "surges", "rally", "rallies", "jump", "jumps", "soar", "soars", "soared",
    "record", "records", "strong", "growth", "rise", "rises", "rose", "gain", "gains",
    "gained", "exceed", "exceeds", "top", "tops", "outperform", "bullish", "buy",
    "expansion", "milestone", "win", "wins", "approved", "breakthrough",
}
NEGATIVE_TERMS = {
    "miss", "misses", "missed", "downgrade", "downgrades", "downgraded",
    "plunge", "plunges", "drop", "drops", "dropped", "fall", "falls", "fell",
    "slump", "slumps", "slip", "slips", "slipped", "decline", "declines", "declined",
    "cut", "cuts", "weak", "weakness", "loss", "losses", "concern", "concerns",
    "warn", "warning", "lawsuit", "fine", "probe", "investigation", "recall",
    "bearish", "sell", "underperform", "fraud", "delay", "halt", "layoffs",
    "restructure", "restructuring",
}

# Order matters — first-match wins. Most specific topics come first so that a
# headline like "DOJ launches antitrust probe" classifies as `regulation`
# rather than `product`. Generic catch-all topics (`product`, `macro`) are
# scanned last.
TOPIC_KEYWORDS = {
    "regulation": [
        "regulator", "regulation", "antitrust", "fine", "lawsuit", "ruling",
        "sec ", "ftc", "doj", "probe", "investigation", "compliance",
        "subpoena", "settlement",
    ],
    "executive": [
        "ceo", "cfo", "cto", "coo", "chairman", "executive",
        "appoint", "appoints", "resign", "resigns", "step down", "steps down",
        "leadership",
    ],
    "m_and_a": [
        "acquire", "acquires", "acquisition", "merger", "merges", "buyout",
        "stake", "joint venture", "spinoff", "divest", "divestiture",
    ],
    "earnings": [
        "earnings", "q1", "q2", "q3", "q4", "quarter", "quarterly", "revenue",
        "guidance", "eps", "profit", "outlook", "beat", "miss",
    ],
    "macro": [
        "fed ", "rate hike", "rate cut", "inflation", "tariff", "tariffs",
        "recession", "macro", "treasury", "fiscal", "geopolitical", "war",
    ],
    "product": [
        "launch", "launches", "unveil", "unveiled", "release", "released",
        "rollout", "feature",
    ],
}


def _classify_sentiment(text: str) -> str:
    """Return bullish / bearish / neutral by keyword count."""
    if not text:
        return "neutral"
    tokens = set(t.strip(".,;:!?\"'()") for t in text.lower().split())
    pos = len(tokens & POSITIVE_TERMS)
    neg = len(tokens & NEGATIVE_TERMS)
    if pos > neg and pos > 0:
        return "bullish"
    if neg > pos and neg > 0:
        return "bearish"
    return "neutral"


def _classify_topic(text: str) -> str:
    if not text:
        return "general"
    lower = text.lower()
    for topic, kws in TOPIC_KEYWORDS.items():
        for kw in kws:
            if kw in lower:
                return topic
    return "general"


# ---------- provider --------------------------------------------------------

class NewsProvider:
    """Free / no-key news provider built on yfinance .news."""

    def __init__(self, cache: Optional[TTLCache] = None):
        # Shorter TTL than price/fundamentals — news goes stale fast.
        self._cache = cache or TTLCache(default_ttl=900)  # 15 min

    def fetch(self, ticker: str, max_items: int = 15) -> List[dict]:
        """Return list of {title, link, publisher, published_at, summary,
        thumbnail, sentiment, topic, ticker, source_name, source_url}."""
        key = f"news:{ticker.upper()}:{max_items}"
        cached = self._cache.get(key)
        if cached is not None:
            return cached

        items: List[dict] = []
        try:
            import yfinance as yf
            t = yf.Ticker(ticker.upper())
            news = []
            try:
                news = t.news or []
            except Exception:
                news = []
            for n in news[:max_items]:
                # Newer yfinance returns nested {content: {...}}; older flat.
                c = n.get("content") if isinstance(n, dict) else None
                title = (
                    _safe_get(c, "title")
                    or n.get("title")
                    or n.get("headline")
                )
                link = (
                    _safe_get(c, "clickThroughUrl", "url")
                    or _safe_get(c, "canonicalUrl", "url")
                    or n.get("link")
                )
                publisher = (
                    _safe_get(c, "provider", "displayName")
                    or n.get("publisher")
                    or "Yahoo Finance"
                )
                published_at = (
                    _safe_get(c, "pubDate")
                    or _ts_to_iso(n.get("providerPublishTime"))
                    or _ts_to_iso(n.get("pubDate"))
                )
                summary = _safe_get(c, "summary") or n.get("summary")
                thumbnail = (
                    _safe_get(c, "thumbnail", "resolutions", 0, "url")
                    if isinstance(_safe_get(c, "thumbnail", "resolutions"), list)
                    else None
                )
                if not title:
                    continue
                blob = " ".join([title or "", summary or ""])
                items.append({
                    "title": title,
                    "link": link,
                    "publisher": publisher,
                    "published_at": published_at,
                    "summary": summary,
                    "thumbnail": thumbnail,
                    "sentiment": _classify_sentiment(blob),
                    "topic": _classify_topic(blob),
                    "ticker": ticker.upper(),
                    "source_name": "Yahoo Finance",
                    "source_url": f"https://finance.yahoo.com/quote/{ticker.upper()}/news",
                })
        except Exception:
            pass

        self._cache.set(key, items)
        return items

    def summarize(self, items: List[dict]) -> dict:
        """Lightweight digest: counts by sentiment + topic, plus headline
        samples per bucket. Not AI — pure rule-based aggregation."""
        if not items:
            return {
                "total": 0,
                "by_sentiment": {"bullish": 0, "bearish": 0, "neutral": 0},
                "by_topic": {},
                "samples": {"bullish": [], "bearish": [], "neutral": []},
                "warning": "No headlines available for this ticker.",
            }
        by_sent = {"bullish": 0, "bearish": 0, "neutral": 0}
        by_topic: dict = {}
        samples: dict = {"bullish": [], "bearish": [], "neutral": []}
        for it in items:
            s = it.get("sentiment") or "neutral"
            by_sent[s] = by_sent.get(s, 0) + 1
            t = it.get("topic") or "general"
            by_topic[t] = by_topic.get(t, 0) + 1
            if len(samples[s]) < 3:
                samples[s].append({
                    "title": it["title"],
                    "publisher": it.get("publisher"),
                    "link": it.get("link"),
                    "published_at": it.get("published_at"),
                })
        return {
            "total": len(items),
            "by_sentiment": by_sent,
            "by_topic": dict(sorted(by_topic.items(), key=lambda kv: -kv[1])),
            "samples": samples,
            "warning": None,
        }
