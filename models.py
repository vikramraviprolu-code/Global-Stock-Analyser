"""Typed data models for v2 — mirror the TypeScript types in the spec.

Each Python dataclass below maps 1:1 to a TypeScript type so the future
Next.js / React frontend can consume the same JSON shapes verbatim.

Mapping (Python → TS):
    SourcedValue   ↔ SourcedValue<T>
    Security       ↔ Security
    StockMetrics   ↔ StockMetrics
    Score          ↔ Score
    StockScores    ↔ StockScores
"""
from __future__ import annotations
from dataclasses import dataclass, field, asdict
from typing import Any, Generic, List, Optional, TypeVar
from datetime import datetime, timezone

# ---------- Literal-equivalent enums (kept as strings for JSON simplicity) -----

FRESHNESS = (
    "real-time", "delayed", "previous-close", "historical-only",
    "cached", "unavailable", "mock",
)
CONFIDENCE = ("high", "medium", "low")

LISTING_TYPES = (
    "common-stock", "adr", "gdr", "etf", "fund",
    "preferred", "warrant", "unknown",
)

SCORE_LABELS = ("Excellent", "Good", "Mixed", "Weak", "Poor")


# ---------- SourcedValue ------------------------------------------------------

T = TypeVar("T")


@dataclass
class SourcedValue(Generic[T]):
    """Every metric carries provenance: where it came from, when, how fresh."""

    value: Optional[T]
    source_name: str = "unknown"
    source_url: Optional[str] = None
    retrieved_at: str = ""
    freshness: str = "unavailable"
    confidence: str = "low"
    verified_source_count: int = 0
    warning: Optional[str] = None

    def __post_init__(self) -> None:
        if not self.retrieved_at:
            self.retrieved_at = datetime.now(timezone.utc).isoformat(timespec="seconds")
        if self.freshness not in FRESHNESS:
            raise ValueError(f"freshness must be one of {FRESHNESS}, got {self.freshness}")
        if self.confidence not in CONFIDENCE:
            raise ValueError(f"confidence must be one of {CONFIDENCE}, got {self.confidence}")

    @classmethod
    def unavailable(cls, source_name: str = "unknown", warning: Optional[str] = None) -> "SourcedValue":
        return cls(
            value=None, source_name=source_name, freshness="unavailable",
            confidence="low", warning=warning,
        )

    @classmethod
    def mock(cls, value: T, warning: str = "Mock demo data. Not live market data.") -> "SourcedValue[T]":
        return cls(
            value=value, source_name="mock", freshness="mock",
            confidence="low", warning=warning,
        )

    def to_dict(self) -> dict:
        return asdict(self)


# ---------- Security & metrics ------------------------------------------------

@dataclass
class Security:
    company_name: Optional[str]
    ticker: str
    exchange: Optional[str]
    country: Optional[str]
    region: Optional[str]
    currency: Optional[str]
    sector: Optional[str]
    industry: Optional[str]
    listing_type: str = "common-stock"

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class StockMetrics:
    security: Security
    price: SourcedValue
    market_cap_local: SourcedValue
    market_cap_usd: SourcedValue
    trailing_pe: SourcedValue
    avg_daily_volume: SourcedValue
    fifty_two_week_low: SourcedValue
    fifty_two_week_high: SourcedValue
    percent_from_low: SourcedValue
    five_day_performance: SourcedValue
    rsi14: SourcedValue
    roc14: SourcedValue
    roc21: SourcedValue
    ma20: SourcedValue
    ma50: SourcedValue
    ma200: SourcedValue
    forward_pe: Optional[SourcedValue] = None
    price_to_book: Optional[SourcedValue] = None
    dividend_yield: Optional[SourcedValue] = None
    earnings_date: Optional[SourcedValue] = None
    dividend_date: Optional[SourcedValue] = None
    split_date: Optional[SourcedValue] = None

    def to_dict(self) -> dict:
        out: dict[str, Any] = {"security": self.security.to_dict()}
        for k, v in self.__dict__.items():
            if k == "security":
                continue
            out[k] = v.to_dict() if isinstance(v, SourcedValue) else v
        return out


# ---------- Scores ------------------------------------------------------------

@dataclass
class Score:
    value: float
    label: str  # one of SCORE_LABELS
    reasons: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
    source_urls: List[str] = field(default_factory=list)

    def __post_init__(self) -> None:
        if self.label not in SCORE_LABELS:
            raise ValueError(f"label must be one of {SCORE_LABELS}, got {self.label}")

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class StockScores:
    value_score: Score
    momentum_score: Score
    quality_score: Score
    risk_score: Score
    data_confidence_score: Score

    def to_dict(self) -> dict:
        return {k: v.to_dict() for k, v in self.__dict__.items()}


def label_for(value: float, max_value: float) -> str:
    """Map normalised score [0..1] to a label."""
    if max_value <= 0:
        return "Poor"
    pct = max(0.0, min(1.0, value / max_value))
    if pct >= 0.85:
        return "Excellent"
    if pct >= 0.65:
        return "Good"
    if pct >= 0.40:
        return "Mixed"
    if pct >= 0.20:
        return "Weak"
    return "Poor"
