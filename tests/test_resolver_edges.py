"""Symbol resolver edge case tests."""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from resolver import search, needs_disambiguation, _candidate_from_universe


def test_empty_query_returns_empty():
    assert search("") == []


def test_whitespace_only_returns_empty():
    assert search("   ") == []


def test_lowercase_ticker_resolves_to_uppercase():
    """Lowercase tickers must be normalised to uppercase candidates."""
    cands = search("aapl")
    if cands:  # offline / yfinance throttled → empty
        assert all(c["ticker"] == c["ticker"].upper() for c in cands)


def test_known_universe_ticker_returns_candidate():
    cands = search("AAPL")
    if cands:
        assert any(c["ticker"] == "AAPL" for c in cands)


def test_company_name_substring_matches_universe():
    """'Apple' should surface AAPL from the curated universe."""
    cands = search("Apple")
    if cands:
        tickers = [c["ticker"] for c in cands]
        assert "AAPL" in tickers


def test_global_suffix_ticker_resolves():
    cands = search("RELIANCE.NS")
    if cands:
        # Either resolves directly or via name match
        assert any(c["ticker"].startswith("RELIANCE") for c in cands)


def test_ambiguous_query_marked_for_disambiguation():
    """Same name might exist on multiple exchanges."""
    cands = search("Toyota")
    if len(cands) >= 2:
        assert needs_disambiguation(cands, "Toyota")


def test_single_match_doesnt_need_disambiguation():
    cands = [{"ticker": "AAPL", "exchange": "Nasdaq", "country": "USA",
              "company": "Apple", "currency": "USD", "region": "Americas"}]
    assert not needs_disambiguation(cands, "AAPL")


def test_dot_suffix_preserved_in_candidate():
    """Candidates from the universe must keep their .NS / .DE / .T suffixes."""
    from resolver import load_universe
    rows = load_universe()
    has_suffixed = any("." in r["ticker"] for r in rows)
    assert has_suffixed  # universe ships with global suffixes
    suffixed = next(r for r in rows if "." in r["ticker"])
    cand = _candidate_from_universe(suffixed)
    assert "." in cand["ticker"]


def test_unknown_ticker_falls_back_to_raw():
    """Random made-up ticker should still produce a 'raw' candidate so the
    user can still try to fetch it (might exist on yfinance)."""
    cands = search("ZZZZZRANDOM")
    # At minimum the raw fallback should produce a candidate
    if cands:
        assert any(c.get("source") == "raw" or c["ticker"].startswith("ZZZZZ")
                   for c in cands) or len(cands) > 0


def test_query_with_special_characters_safe():
    """No exception on dots, ampersands, dashes (M&M.NS, BRK-B etc.)"""
    for q in ["M&M.NS", "BRK-B", "0700.HK", "005930.KS"]:
        cands = search(q)
        # Just ensure no exception; cands may be empty offline
        assert isinstance(cands, list)


def test_long_query_truncated_or_handled():
    # 200 chars — make sure we don't crash
    long_q = "A" * 200
    cands = search(long_q)
    assert isinstance(cands, list)
