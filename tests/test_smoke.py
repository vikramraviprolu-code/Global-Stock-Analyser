"""Smoke tests — pure-logic checks that run without network access."""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from markets import parse_ticker, listing_meta, regional_filter, SUFFIX_MAP
from analyzer import _to_float, passes_global_filters, score_input_stock


def test_parse_ticker_us():
    assert parse_ticker("AAPL") == ("AAPL", "")
    assert parse_ticker("aapl") == ("AAPL", "")


def test_parse_ticker_global():
    assert parse_ticker("RELIANCE.NS") == ("RELIANCE", "NS")
    assert parse_ticker("7203.T") == ("7203", "T")
    assert parse_ticker("BMW.DE") == ("BMW", "DE")
    assert parse_ticker("0700.HK") == ("0700", "HK")


def test_listing_meta_us():
    m = listing_meta("AAPL")
    assert m["country"] == "USA"
    assert m["currency"] == "USD"


def test_listing_meta_india():
    m = listing_meta("RELIANCE.NS")
    assert m["country"] == "India"
    assert m["currency"] == "INR"
    assert m["exchange"] == "NSE"


def test_listing_meta_japan():
    m = listing_meta("7203.T")
    assert m["country"] == "Japan"
    assert m["currency"] == "JPY"


def test_regional_filter_usa():
    f = regional_filter("USA")
    assert f["min_price"] == 5.0
    assert f["min_volume"] == 500_000


def test_regional_filter_singapore_lower_mcap():
    f = regional_filter("Singapore")
    assert f["min_mcap_usd"] == 1_000_000_000


def test_to_float_handles_str():
    assert _to_float("12.5") == 12.5
    assert _to_float("1,234.56") == 1234.56
    assert _to_float(None) is None
    assert _to_float("nan") != _to_float("nan")  # NaN != NaN


def test_passes_global_filters_us_pass():
    d = {"price": 100.0, "avg_volume": 1_000_000, "market_cap_usd": 5e9, "country": "USA", "currency_symbol": "$"}
    ok, fails = passes_global_filters(d)
    assert ok is True
    assert fails == []


def test_passes_global_filters_us_fail_price():
    d = {"price": 1.0, "avg_volume": 1_000_000, "market_cap_usd": 5e9, "country": "USA", "currency_symbol": "$"}
    ok, fails = passes_global_filters(d)
    assert ok is False
    assert any("Price" in f for f in fails)


def test_score_buy_signal():
    d = {
        "pct_from_low": 5.0, "trailing_pe": 8.0, "market_cap_usd": 5e9, "country": "USA",
        "perf_5d": 2.0, "roc_14": 5.0, "roc_21": 8.0, "rsi_14": 55.0,
        "price": 100, "ma_20": 95, "ma_50": 92, "ma_200": 85,
        "attractive_vs_peers": True,
    }
    s = score_input_stock(d)
    assert s["recommendation"] == "Buy"
    assert s["value_score"] == 4
    assert s["momentum_score"] == 7
    assert s["penalties"] == 0


def test_score_avoid_signal():
    d = {
        "pct_from_low": 60.0, "trailing_pe": 50.0, "market_cap_usd": 1e9, "country": "USA",
        "perf_5d": -3.0, "roc_14": -8.0, "roc_21": -12.0, "rsi_14": 80.0,
        "price": 80, "ma_20": 90, "ma_50": 95, "ma_200": 100,
    }
    s = score_input_stock(d)
    assert s["recommendation"] == "Avoid"
    assert s["penalties"] >= 2


def test_suffix_map_completeness():
    expected_suffixes = {"NS", "BO", "L", "DE", "PA", "SW", "T", "HK", "KS", "TW", "SI", "AX", "SS"}
    assert expected_suffixes.issubset(SUFFIX_MAP.keys())


# Security tests

from app import TICKER_RE, _sanitize_optional, app as flask_app


def test_ticker_regex_accepts_valid():
    valid = ["AAPL", "MSFT", "BRK-B", "RELIANCE.NS", "0700.HK", "VOLV-B.ST", "005930.KS", "7203.T", "BMW.DE"]
    for t in valid:
        assert TICKER_RE.match(t), f"should accept {t}"


def test_ticker_regex_rejects_malicious():
    bad = [
        "<script>alert(1)</script>",
        "AAPL'; DROP TABLE users--",
        "AAPL\x00",
        "AAPL/../../etc/passwd",
        "AAPL OR 1=1",
        "AAPL\nMSFT",
        "javascript:alert(1)",
        "",
        "A" * 50,
    ]
    for t in bad:
        assert not TICKER_RE.match(t), f"should reject {t!r}"


def test_sanitize_optional_drops_unsafe():
    assert _sanitize_optional(None) is None
    assert _sanitize_optional("") is None
    assert _sanitize_optional("<script>") is None
    assert _sanitize_optional("Apple Inc.") == "Apple Inc."
    assert _sanitize_optional("a" * 200) is None


def test_security_headers_present():
    client = flask_app.test_client()
    resp = client.get("/")
    assert resp.headers.get("X-Content-Type-Options") == "nosniff"
    assert resp.headers.get("X-Frame-Options") == "DENY"
    assert "frame-ancestors 'none'" in resp.headers.get("Content-Security-Policy", "")


def test_analyze_rejects_invalid_ticker():
    client = flask_app.test_client()
    resp = client.post("/api/analyze", json={"ticker": "<script>"})
    assert resp.status_code == 400
    assert "Invalid" in resp.get_json()["error"]


def test_search_rejects_control_chars():
    client = flask_app.test_client()
    resp = client.get("/api/search?q=foo%00bar")
    assert resp.status_code == 400
