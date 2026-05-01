"""Flask web app for global stock analysis.

Environment variables (all optional):
    HOST            bind interface, default 127.0.0.1
    PORT            bind port, default 5050
    URL_PREFIX      mount under prefix, e.g. "/Local"; empty = root
    SSL_CERT        path to PEM cert; if set with SSL_KEY, serves HTTPS
    SSL_KEY         path to PEM private key
    IDLE_TIMEOUT    seconds without a request before auto-shutdown (default 45)
    AUTO_SHUTDOWN   set to "0" to disable idle watcher (default enabled)
"""
import ipaddress
import os
import re
import ssl
import threading
import time
from urllib.parse import urlparse
from flask import Flask, render_template, request, jsonify
from werkzeug.middleware.dispatcher import DispatcherMiddleware
from werkzeug.exceptions import NotFound
from analyzer import run_analysis
from resolver import search, needs_disambiguation
from markets import listing_meta
from providers import UniverseService, EventsProvider
from screener import Filter, ScreenerEngine, PRESETS, get_preset
from screener.presets import list_presets
from calc.scoring import score_all
from calc.recommendation import build_scenario

URL_PREFIX = os.getenv("URL_PREFIX", "").rstrip("/")  # e.g. "/Local"

app = Flask(__name__)
app.json.allow_nan_values = False  # type: ignore[attr-defined]  # strict JSON
if URL_PREFIX:
    app.config["APPLICATION_ROOT"] = URL_PREFIX

# Allow the configured hostname to reach the app even when bound to 127.0.0.1.
# Werkzeug rejects unknown Host headers when SERVER_NAME is set, so leave it
# unset and instead validate via a list of trusted hosts.
TRUSTED_HOSTS = {h.strip().lower() for h in os.getenv(
    "TRUSTED_HOSTS",
    "127.0.0.1,localhost,global-stock-analyser",
).split(",") if h.strip()}

TICKER_RE = re.compile(r"^[A-Z0-9]{1,12}(?:-[A-Z0-9]{1,4})?(?:\.[A-Z]{1,4})?$")
SAFE_STR_RE = re.compile(r"^[A-Za-z0-9 .\-&,'/+()]{0,80}$")


def _sanitize_optional(value, max_len=80):
    if value is None:
        return None
    s = str(value).strip()
    if not s or len(s) > max_len:
        return None
    if not SAFE_STR_RE.match(s):
        return None
    return s


IDLE_TIMEOUT = int(os.getenv("IDLE_TIMEOUT", "45"))
AUTO_SHUTDOWN = os.getenv("AUTO_SHUTDOWN", "1") != "0"
_last_activity = time.time()
_idle_thread_started = False


def _idle_watcher():
    """Exit the process after IDLE_TIMEOUT seconds without any activity."""
    while True:
        time.sleep(5)
        if time.time() - _last_activity > IDLE_TIMEOUT:
            app.logger.info("Idle timeout reached. Shutting down.")
            os._exit(0)


def _bump_activity():
    global _last_activity
    _last_activity = time.time()


@app.before_request
def _track_activity():
    _bump_activity()
    global _idle_thread_started
    if AUTO_SHUTDOWN and not _idle_thread_started:
        _idle_thread_started = True
        threading.Thread(target=_idle_watcher, daemon=True).start()


@app.before_request
def _validate_host():
    """Reject Host header that isn't on the allow-list (defense vs Host-header attacks)."""
    host = (request.host or "").split(":")[0].lower()
    if host and host not in TRUSTED_HOSTS:
        return jsonify({"error": "Host not allowed."}), 400


def _is_loopback(addr: str) -> bool:
    """True if addr is a loopback IP (127.0.0.0/8 or ::1)."""
    if not addr:
        return False
    try:
        return ipaddress.ip_address(addr).is_loopback
    except ValueError:
        return False


def _origin_is_trusted() -> bool:
    """Check Origin or Referer against TRUSTED_HOSTS for CSRF protection."""
    for header in ("Origin", "Referer"):
        src = request.headers.get(header, "")
        if not src:
            continue
        try:
            host = urlparse(src).netloc.split(":")[0].lower()
        except Exception:
            continue
        if host and host in TRUSTED_HOSTS:
            return True
    return False


@app.after_request
def _security_headers(resp):
    resp.headers["X-Content-Type-Options"] = "nosniff"
    resp.headers["X-Frame-Options"] = "DENY"
    resp.headers["Referrer-Policy"] = "no-referrer"
    resp.headers["Permissions-Policy"] = "geolocation=(), microphone=(), camera=()"
    # Strip Werkzeug version banner from Server header (info-leak hardening).
    resp.headers["Server"] = "EquityScope"
    # HSTS intentionally NOT set: this app uses a self-signed cert for a local
    # hostname. HSTS would lock the browser into refusing the cert without any
    # bypass option (chrome://net-internals/#hsts to clear). Keep TLS, drop HSTS.
    if request.path.startswith("/static") or request.path in ("/", "/app"):
        resp.headers["Content-Security-Policy"] = (
            "default-src 'self'; "
            "script-src 'self' 'unsafe-inline'; "
            "style-src 'self' 'unsafe-inline'; "
            "img-src 'self' data:; "
            "connect-src 'self'; "
            "frame-ancestors 'none'; "
            "base-uri 'self'; "
            "form-action 'self'"
        )
    return resp


# ----- v2 services (singletons) ----------------------------------------------
_universe_service = UniverseService()
_screener_engine = ScreenerEngine(_universe_service)


def _scrub_nan(obj):
    """Recursively replace float NaN/Inf with None (valid JSON)."""
    import math
    if isinstance(obj, float):
        if math.isnan(obj) or math.isinf(obj):
            return None
        return obj
    if isinstance(obj, dict):
        return {k: _scrub_nan(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [_scrub_nan(v) for v in obj]
    return obj


VALID_FILTER_KINDS = {
    # cheap
    "sector_in", "country_in", "region_in", "exchange_in",
    "currency_in", "industry_in", "listing_type_in",
    # range / numeric
    "price_min", "price_max", "mcap_usd_min", "mcap_usd_max",
    "pe_min", "pe_max", "pb_min", "pb_max",
    "dividend_min", "dividend_max",
    "volume_min", "volume_max",
    "rsi_min", "rsi_max",
    "perf5d_min", "perf5d_max",
    "roc14_min", "roc14_max", "roc21_min", "roc21_max",
    "pct_from_low_min", "pct_from_low_max",
    "pct_from_high_max",
    "min_data_confidence",
    # boolean
    "above_ma20", "above_ma50", "above_ma200",
    "exclude_unavailable_pe", "exclude_unavailable_mcap",
    "exclude_stale", "require_history",
}
LIST_KINDS = {"sector_in", "country_in", "region_in", "exchange_in",
              "currency_in", "industry_in", "listing_type_in"}
BOOL_KINDS = {"above_ma20", "above_ma50", "above_ma200",
              "exclude_unavailable_pe", "exclude_unavailable_mcap",
              "exclude_stale", "require_history"}


def _filters_from_payload(payload) -> list:
    """Convert JSON [{kind, value}, ...] into Filter dataclasses with input
    validation. Drops any unknown kinds silently."""
    if not isinstance(payload, list):
        return []
    out = []
    for item in payload[:48]:
        if not isinstance(item, dict):
            continue
        kind = str(item.get("kind", ""))
        if kind not in VALID_FILTER_KINDS:
            continue
        value = item.get("value")
        if kind in LIST_KINDS:
            if not isinstance(value, list):
                continue
            value = [str(v)[:60] for v in value[:48] if v]
            if not value:
                continue
        elif kind in BOOL_KINDS:
            value = bool(value)
        else:
            try:
                value = float(value)
            except (TypeError, ValueError):
                continue
        out.append(Filter(kind=kind, value=value, label=item.get("label")))
    return out


def _scores_for_metric(m):
    """Compute StockScores from a StockMetrics object."""
    return score_all({
        "price": m.price, "market_cap_usd": m.market_cap_usd,
        "trailing_pe": m.trailing_pe, "rsi14": m.rsi14, "roc14": m.roc14,
        "roc21": m.roc21, "ma20": m.ma20, "ma50": m.ma50, "ma200": m.ma200,
        "five_day_performance": m.five_day_performance,
        "percent_from_low": m.percent_from_low,
        "fifty_two_week_high": m.fifty_two_week_high,
        "fifty_two_week_low": m.fifty_two_week_low,
        "dividend_yield": m.dividend_yield,
        "price_to_book": m.price_to_book,
        "avg_daily_volume": m.avg_daily_volume,
        "security": m.security.to_dict(),
    })


@app.route("/")
def home():
    """Default landing — Screener (per spec)."""
    return render_template("screener.html")


@app.route("/screener")
def screener_page():
    return render_template("screener.html")


@app.route("/welcome")
def landing():
    """Marketing landing page (was at / before v2)."""
    return render_template("landing.html")


@app.route("/app")
def dashboard():
    return render_template("index.html")


@app.route("/sources")
def sources_page():
    return render_template("sources.html")


@app.route("/watchlists")
def watchlists_page():
    return render_template("watchlists.html")


@app.route("/compare")
def compare_page():
    return render_template("compare.html")


@app.route("/data-quality")
def data_quality_page():
    return render_template("data_quality.html")


@app.route("/events")
def events_page():
    return render_template("events.html")


@app.route("/settings")
def settings_page():
    return render_template("settings.html")


@app.route("/portfolio")
def portfolio_page():
    return render_template("portfolio.html")


@app.route("/alerts")
def alerts_page():
    return render_template("alerts.html")


@app.route("/news")
def news_page():
    return render_template("news.html")


# ----- v2 API ----------------------------------------------------------------

@app.route("/api/screener/presets")
def api_screener_presets():
    return jsonify({"presets": list_presets()})


@app.route("/api/screener/run", methods=["POST"])
def api_screener_run():
    data = request.get_json(silent=True) or {}
    preset_key = data.get("preset")
    custom = data.get("filters") or []

    if preset_key:
        if preset_key not in PRESETS:
            return jsonify({"error": "Unknown preset."}), 400
        filters = get_preset(preset_key)
    else:
        filters = _filters_from_payload(custom)

    if not filters:
        return jsonify({"error": "No filters provided."}), 400
    if len(filters) > 48:
        return jsonify({"error": "Too many filters."}), 400

    include_sparkline = bool((data or {}).get("include_sparkline", False))
    sparkline_days = max(20, min(int((data or {}).get("sparkline_days") or 60), 250))

    try:
        # Pass score_fn so min_data_confidence and similar score-based filters
        # can fire during screening (engine computes scores once per ticker).
        result = _screener_engine.screen(filters, score_fn=_scores_for_metric)
    except Exception:
        app.logger.exception("Screener run failed")
        return jsonify({"error": "Screener failed. See server logs."}), 500

    payload_matches = []
    for m in result.matches:
        scores = result.score_cache.get(m.security.ticker) or _scores_for_metric(m)
        m_dict = m.to_dict()
        m_dict["scores"] = scores.to_dict()
        if include_sparkline:
            try:
                df = _universe_service.fetch_history_for(m.security.ticker)
                if df is not None and not df.empty:
                    closes = [float(x) for x in df["Close"].tolist() if x == x][-sparkline_days:]
                    m_dict["recent_closes"] = closes
                else:
                    m_dict["recent_closes"] = []
            except Exception:
                m_dict["recent_closes"] = []
        payload_matches.append(m_dict)

    return jsonify(_scrub_nan({
        "matches": payload_matches,
        "total_universe": result.total_universe,
        "after_cheap_filters": result.after_cheap_filters,
        "enriched_count": result.enriched_count,
        "failed_enrichment": result.failed_enrichment,
        "warnings": result.warnings,
    }))


TICKER_BATCH_RE = re.compile(r"^[A-Z0-9]{1,12}(?:-[A-Z0-9]{1,4})?(?:\.[A-Z]{1,4})?$")


def _enrich_ticker_with_scores(ticker: str):
    """Enrich + attach scores. Returns dict or None on failure."""
    try:
        m = _universe_service.enrich_ticker(ticker)
        m_dict = m.to_dict()
        scores = score_all({
            "price": m.price, "market_cap_usd": m.market_cap_usd,
            "trailing_pe": m.trailing_pe, "rsi14": m.rsi14, "roc14": m.roc14,
            "roc21": m.roc21, "ma20": m.ma20, "ma50": m.ma50, "ma200": m.ma200,
            "five_day_performance": m.five_day_performance,
            "percent_from_low": m.percent_from_low,
            "fifty_two_week_high": m.fifty_two_week_high,
            "fifty_two_week_low": m.fifty_two_week_low,
            "dividend_yield": m.dividend_yield,
            "price_to_book": m.price_to_book,
            "avg_daily_volume": m.avg_daily_volume,
            "security": m.security.to_dict(),
        })
        m_dict["scores"] = scores.to_dict()
        return m_dict
    except Exception:
        app.logger.exception("Enrich failed for %s", ticker)
        return None


@app.route("/api/metrics", methods=["POST"])
def api_metrics():
    """Batch-enrich a list of tickers for watchlists / compare. Up to 12.

    Optional payload fields:
      - include_sparkline: bool — attach `recent_closes` per match
      - sparkline_days: int (20–250, default 60)
    """
    data = request.get_json(silent=True) or {}
    tickers = data.get("tickers") or []
    if not isinstance(tickers, list) or not tickers:
        return jsonify({"error": "tickers (list) required."}), 400
    if len(tickers) > 12:
        return jsonify({"error": "Max 12 tickers per request."}), 400

    include_sparkline = bool(data.get("include_sparkline", False))
    try:
        sparkline_days = int(data.get("sparkline_days") or 60)
    except (TypeError, ValueError):
        sparkline_days = 60
    sparkline_days = max(20, min(sparkline_days, 250))

    cleaned = []
    for t in tickers:
        if not isinstance(t, str):
            continue
        t = t.upper().strip()
        if TICKER_BATCH_RE.match(t):
            cleaned.append(t)
    if not cleaned:
        return jsonify({"error": "No valid tickers."}), 400

    from concurrent.futures import ThreadPoolExecutor, as_completed
    out = []
    with ThreadPoolExecutor(max_workers=6) as ex:
        futures = {ex.submit(_enrich_ticker_with_scores, t): t for t in cleaned}
        for fut in as_completed(futures):
            res = fut.result()
            if res:
                out.append(res)

    if include_sparkline:
        for m in out:
            t = m["security"]["ticker"]
            try:
                df = _universe_service.fetch_history_for(t)
                if df is not None and not df.empty:
                    closes = [float(x) for x in df["Close"].tolist() if x == x][-sparkline_days:]
                    m["recent_closes"] = closes
                else:
                    m["recent_closes"] = []
            except Exception:
                m["recent_closes"] = []

    # Preserve original order
    by_ticker = {m["security"]["ticker"]: m for m in out}
    ordered = [by_ticker[t] for t in cleaned if t in by_ticker]
    return jsonify(_scrub_nan({"metrics": ordered}))


@app.route("/api/ohlcv")
def api_ohlcv():
    """Full OHLCV series for the Stock Analysis chart panel.

    Returns date / open / high / low / close / volume arrays plus a freshness
    badge so the chart can render candlesticks + volume + indicator overlays.
    """
    ticker = (request.args.get("ticker") or "").upper().strip()
    if not ticker or not TICKER_BATCH_RE.match(ticker):
        return jsonify({"error": "Invalid ticker."}), 400
    try:
        days = int(request.args.get("days", "365"))
    except ValueError:
        days = 365
    days = max(20, min(days, 2500))

    df = _universe_service.fetch_history_for(ticker)
    if df is None or df.empty:
        return jsonify({"error": "No history available."}), 404
    # Drop NaN closes
    df = df.dropna(subset=["Close"]).tail(days).reset_index(drop=True)
    if df.empty:
        return jsonify({"error": "No valid bars after cleaning."}), 404

    bars = []
    for _, row in df.iterrows():
        d = row["Date"]
        date_str = (d.date() if hasattr(d, "date") else d)
        try:
            date_str = str(date_str)[:10]
        except Exception:
            continue
        try:
            o = float(row.get("Open", row["Close"]))
            h = float(row.get("High", row["Close"]))
            lo = float(row.get("Low", row["Close"]))
            c = float(row["Close"])
            v = row.get("Volume", 0)
            v = float(v) if v == v else 0.0  # NaN guard
        except (TypeError, ValueError):
            continue
        bars.append({
            "time": date_str,
            "open": o, "high": h, "low": lo, "close": c, "volume": v,
        })

    if not bars:
        return jsonify({"error": "No usable OHLCV rows."}), 404

    last_date = bars[-1]["time"]
    has_ohlc = all(b["open"] != b["close"] or b["high"] != b["low"] for b in bars[:5])
    src_name, src_url = _universe_service.historical.source_for(ticker)

    return jsonify(_scrub_nan({
        "ticker": ticker,
        "bars": bars,
        "count": len(bars),
        "first_date": bars[0]["time"],
        "last_date": last_date,
        "has_ohlc": bool(has_ohlc),
        "source_name": src_name,
        "source_url": src_url,
    }))


@app.route("/api/sparkline")
def api_sparkline():
    """Lightweight closes-only series for the compare page mini charts."""
    ticker = (request.args.get("ticker") or "").upper().strip()
    if not ticker or not TICKER_BATCH_RE.match(ticker):
        return jsonify({"error": "Invalid ticker."}), 400
    try:
        days = int(request.args.get("days", "60"))
    except ValueError:
        days = 60
    days = max(20, min(days, 750))

    df = _universe_service.fetch_history_for(ticker)
    if df is None or df.empty:
        return jsonify({"error": "No history available."}), 404
    closes = [float(x) for x in df["Close"].tolist() if x == x][-days:]
    dates = [str(d.date() if hasattr(d, "date") else d)[:10] for d in df["Date"].tolist()][-len(closes):]
    return jsonify(_scrub_nan({
        "ticker": ticker,
        "days": len(closes),
        "closes": closes,
        "dates": dates,
        "min": min(closes) if closes else None,
        "max": max(closes) if closes else None,
        "first": closes[0] if closes else None,
        "last": closes[-1] if closes else None,
    }))


@app.route("/api/settings/server-info")
def api_server_info():
    """Server-side info for the Settings page."""
    import platform
    import sys
    cache_stats = _universe_service._enriched_cache.stats()
    return jsonify({
        "version": "0.18.0",
        "python": sys.version.split()[0],
        "platform": platform.platform(),
        "url_prefix": URL_PREFIX or "/",
        "trusted_hosts": sorted(TRUSTED_HOSTS),
        "tls_enabled": bool(os.getenv("SSL_CERT") and os.getenv("SSL_KEY")),
        "auto_shutdown": AUTO_SHUTDOWN,
        "idle_timeout": IDLE_TIMEOUT,
        "universe_size": len(_universe_service.rows()),
        "cache_stats": cache_stats,
    })


@app.route("/api/settings/clear-cache", methods=["POST"])
def api_clear_cache():
    """Drop the enrichment cache so the next request re-fetches live data.

    Same-origin only (POST + Origin allow-list)."""
    if not _is_loopback(request.remote_addr or ""):
        return jsonify({"error": "Forbidden."}), 403
    if not _origin_is_trusted():
        return jsonify({"error": "Cross-origin clear-cache blocked."}), 403
    _universe_service._enriched_cache.clear()
    return jsonify({"cleared": True})


@app.route("/api/news")
def api_news():
    """Headlines for a single ticker. Returns list + summary digest."""
    ticker = (request.args.get("ticker") or "").upper().strip()
    if not ticker or not TICKER_BATCH_RE.match(ticker):
        return jsonify({"error": "Invalid ticker."}), 400
    try:
        max_items = int(request.args.get("max", "15"))
    except ValueError:
        max_items = 15
    max_items = max(1, min(max_items, 30))

    items = _universe_service.news.fetch(ticker, max_items=max_items)
    digest = _universe_service.news.summarize(items)
    return jsonify(_scrub_nan({
        "ticker": ticker, "items": items, "digest": digest,
        "warning": ("No headlines available from free public sources for this ticker."
                    if not items else None),
    }))


@app.route("/api/news/digest", methods=["POST"])
def api_news_digest():
    """Batch headlines for a list of tickers (e.g. user's watchlist)."""
    data = request.get_json(silent=True) or {}
    tickers = data.get("tickers") or []
    if not isinstance(tickers, list) or not tickers:
        return jsonify({"error": "tickers (list) required."}), 400
    if len(tickers) > 30:
        return jsonify({"error": "Max 30 tickers per batch."}), 400
    try:
        max_items = int(data.get("max_per_ticker", 8))
    except (TypeError, ValueError):
        max_items = 8
    max_items = max(1, min(max_items, 20))

    cleaned = []
    for t in tickers:
        if not isinstance(t, str):
            continue
        t = t.upper().strip()
        if TICKER_BATCH_RE.match(t):
            cleaned.append(t)
    if not cleaned:
        return jsonify({"error": "No valid tickers."}), 400

    from concurrent.futures import ThreadPoolExecutor, as_completed
    results = {}
    with ThreadPoolExecutor(max_workers=6) as ex:
        futures = {
            ex.submit(_universe_service.news.fetch, t, max_items): t
            for t in cleaned
        }
        for fut in as_completed(futures):
            t = futures[fut]
            try:
                results[t] = fut.result() or []
            except Exception:
                results[t] = []
    return jsonify(_scrub_nan({"news": results}))


CCY_RE = re.compile(r"^[A-Z]{3}$")


@app.route("/api/fx")
def api_fx():
    """Single currency-pair rate. Used by Portfolio + Compare for base-ccy rollups."""
    fr = (request.args.get("from") or "USD").upper().strip()
    to = (request.args.get("to") or "USD").upper().strip()
    if not CCY_RE.match(fr) or not CCY_RE.match(to):
        return jsonify({"error": "Invalid currency code (3 letters required)."}), 400
    try:
        from markets import fx_rate
        rate = fx_rate(fr, to)
    except Exception:
        app.logger.exception("FX fetch failed for %s→%s", fr, to)
        return jsonify({"from": fr, "to": to, "rate": None,
                        "freshness": "unavailable",
                        "warning": "FX provider error."}), 200
    return jsonify(_scrub_nan({
        "from": fr, "to": to, "rate": rate,
        "freshness": "cached" if rate is not None else "unavailable",
        "source_name": "Yahoo Finance" if rate is not None else None,
        "source_url": f"https://finance.yahoo.com/quote/{fr}{to}=X" if rate is not None else None,
    }))


@app.route("/api/fx/batch", methods=["POST"])
def api_fx_batch():
    """Batch currency-pair rates. Payload: {pairs: [{from, to}, ...]}.
    Returns {rates: {"FROM_TO": rate}}. Up to 30 pairs."""
    data = request.get_json(silent=True) or {}
    pairs = data.get("pairs") or []
    if not isinstance(pairs, list) or not pairs:
        return jsonify({"error": "pairs (list) required."}), 400
    if len(pairs) > 30:
        return jsonify({"error": "Max 30 pairs per batch."}), 400
    cleaned = []
    for p in pairs:
        if not isinstance(p, dict):
            continue
        fr = str(p.get("from", "")).upper().strip()
        to = str(p.get("to", "")).upper().strip()
        if CCY_RE.match(fr) and CCY_RE.match(to):
            cleaned.append((fr, to))
    if not cleaned:
        return jsonify({"error": "No valid pairs."}), 400

    from markets import fx_rate
    rates = {}
    for fr, to in cleaned:
        try:
            rates[f"{fr}_{to}"] = fx_rate(fr, to)
        except Exception:
            rates[f"{fr}_{to}"] = None
    return jsonify(_scrub_nan({"rates": rates}))


@app.route("/api/sources/health")
def api_sources_health():
    return jsonify({
        "providers": {
            "historical": {
                "name": "Stooq CSV + yfinance (parallel + cross-validated)",
                "type": "free, no API key",
                "url": "https://stooq.com",
                "fallback_url": "https://finance.yahoo.com",
                "notes": "Both providers fetched concurrently; metrics earn verified_source_count=2 when last closes agree within 2%.",
            },
            "fundamentals": {
                "name": "yfinance (.info)",
                "type": "free / best-effort",
                "url": "https://finance.yahoo.com",
                "notes": "Market cap, P/E, P/B, dividend yield, sector, industry, currency.",
            },
            "events": {
                "name": "yfinance (.calendar / .actions)",
                "type": "free / best-effort",
                "url": "https://finance.yahoo.com",
                "notes": "Earnings, dividend, ex-dividend, split dates. Missing dates surface as freshness=unavailable; never fabricated.",
            },
            "news": {
                "name": "yfinance (.news)",
                "type": "free / best-effort",
                "url": "https://finance.yahoo.com",
                "notes": "Recent headlines per ticker. Sentiment + topic classification is rule-based (keyword matching) — not AI; clearly labelled as 'auto-extracted' in the UI.",
            },
            "fx": {
                "name": "yfinance currency pairs",
                "type": "free",
                "notes": "USDxxx=X used to normalise market caps to USD. 6-hour cache.",
            },
            "symbol_resolver": {
                "name": "Curated universe + yfinance Search",
                "type": "free",
                "notes": "Disambiguation modal when a query matches multiple listings.",
            },
            "mock": {
                "name": "Synthetic fallback",
                "type": "mock — engages only when live sources fail",
                "notes": "Every value badged freshness=mock and never silently mixed with live data.",
            },
        },
        "universe": _universe_service.stats(),
    })


@app.route("/api/search")
def api_search():
    q = (request.args.get("q") or "").strip()
    if not q:
        return jsonify({"error": "Empty query."}), 400
    if len(q) > 80:
        return jsonify({"error": "Query too long."}), 400
    if re.search(r"[\x00-\x1f<>]", q):
        return jsonify({"error": "Invalid characters in query."}), 400
    candidates = search(q, limit=10)
    if not candidates:
        return jsonify({"candidates": [], "needs_choice": False})
    return jsonify({
        "candidates": candidates,
        "needs_choice": needs_disambiguation(candidates, q),
    })


@app.route("/api/heartbeat", methods=["POST"])
def api_heartbeat():
    """Browser keep-alive ping. Activity is bumped in _track_activity."""
    return ("", 204)


@app.route("/api/shutdown", methods=["POST"])
def api_shutdown():
    """Browser-triggered graceful shutdown (sent on beforeunload).

    Security: requires loopback peer AND a trusted Origin/Referer to defend
    against CSRF — a malicious cross-origin site cannot kill the daemon.
    """
    if not _is_loopback(request.remote_addr or ""):
        return jsonify({"error": "Forbidden."}), 403
    if not _origin_is_trusted():
        return jsonify({"error": "Cross-origin shutdown blocked."}), 403
    threading.Timer(0.3, lambda: os._exit(0)).start()
    return ("", 204)


def _peer_matrix(input_metric, peer_metrics):
    """Build the v2 peer comparison matrix per PRD format:
    { metric: { input, peer_median, peer_rank, better_or_worse, source_quality } }

    Lower-is-better metrics (P/E, % from low, RSI distance from 50, risk_score)
    treat smaller as better. For others, larger is better.
    """
    LOWER_BETTER = {"trailing_pe", "percent_from_low", "risk_score"}
    METRIC_KEYS = [
        ("trailing_pe", "P/E", "trailing_pe"),
        ("market_cap_usd", "Market Cap (USD)", "market_cap_usd"),
        ("five_day_performance", "5D Performance", "five_day_performance"),
        ("rsi14", "RSI 14", "rsi14"),
        ("roc14", "ROC 14D", "roc14"),
        ("roc21", "ROC 21D", "roc21"),
        ("percent_from_low", "% from 52W low", "percent_from_low"),
        ("vs_ma200", "Price vs 200D MA", None),  # synthesized
        ("value_score", "Value Score", "scores.value_score"),
        ("momentum_score", "Momentum Score", "scores.momentum_score"),
        ("quality_score", "Quality Score", "scores.quality_score"),
        ("risk_score", "Risk Score", "scores.risk_score"),
        ("data_confidence_score", "Data Confidence", "scores.data_confidence_score"),
    ]

    def get_val(metric_obj, key):
        # metric_obj is StockMetrics + .scores attached on dict; we work with
        # the dict-shaped payload here.
        if key == "vs_ma200":
            price = (metric_obj.get("price") or {}).get("value")
            ma200 = (metric_obj.get("ma200") or {}).get("value")
            if price is None or ma200 is None or ma200 == 0:
                return None
            return (price / ma200 - 1.0) * 100.0
        if key.startswith("scores."):
            sk = key.split(".", 1)[1]
            return (metric_obj.get("scores") or {}).get(sk, {}).get("value")
        sv = metric_obj.get(key)
        if isinstance(sv, dict):
            return sv.get("value")
        return None

    rows = []
    for key, label, src_key in METRIC_KEYS:
        input_val = get_val(input_metric, key if key != "vs_ma200" else "vs_ma200")
        peer_vals = [get_val(p, key if key != "vs_ma200" else "vs_ma200") for p in peer_metrics]
        peer_vals_clean = sorted([v for v in peer_vals if v is not None])
        if not peer_vals_clean or input_val is None:
            rows.append({
                "metric": label, "input": input_val, "peer_median": None,
                "peer_rank": None, "peer_count": len(peer_vals_clean),
                "better_or_worse": "—", "source_quality": None,
            })
            continue
        n = len(peer_vals_clean)
        median = peer_vals_clean[n // 2] if n % 2 else (peer_vals_clean[n//2 - 1] + peer_vals_clean[n//2]) / 2
        # Rank: include input alongside peers, count position
        combined = sorted(peer_vals_clean + [input_val], reverse=(key not in LOWER_BETTER))
        try:
            rank = combined.index(input_val) + 1
        except ValueError:
            rank = None
        if key in LOWER_BETTER:
            better = input_val < median
        else:
            better = input_val > median
        # Source quality
        sq = None
        if src_key and not src_key.startswith("scores.") and src_key != "vs_ma200":
            sv = input_metric.get(src_key)
            if isinstance(sv, dict):
                sq = {
                    "source_name": sv.get("source_name"),
                    "freshness": sv.get("freshness"),
                    "confidence": sv.get("confidence"),
                }
        rows.append({
            "metric": label,
            "input": input_val,
            "peer_median": median,
            "peer_rank": rank,
            "peer_count": n + 1,
            "better_or_worse": "Better" if better else "Worse",
            "source_quality": sq,
        })

    # High-level summary booleans for the UI
    pe_row = next((r for r in rows if r["metric"] == "P/E"), None)
    mom_row = next((r for r in rows if r["metric"] == "Momentum Score"), None)
    dc_row = next((r for r in rows if r["metric"] == "Data Confidence"), None)
    risk_row = next((r for r in rows if r["metric"] == "Risk Score"), None)
    summary = {
        "cheaper_than_peers": pe_row and pe_row["better_or_worse"] == "Better",
        "stronger_momentum_than_peers": mom_row and mom_row["better_or_worse"] == "Better",
        "higher_data_confidence_than_peers": dc_row and dc_row["better_or_worse"] == "Better",
        "higher_risk_than_peers": risk_row and risk_row["better_or_worse"] == "Worse",
    }
    return {"rows": rows, "summary": summary}


@app.route("/api/analyze/v2", methods=["POST"])
def api_analyze_v2():
    """v2 analyze: returns enriched StockMetrics + scores + peer matrix.

    Payload: { ticker, peer_tickers? } — peer_tickers defaults to up to 8 same-
    sector picks from the curated universe.
    """
    data = request.get_json(silent=True) or {}
    ticker = (data.get("ticker") or "").upper().strip()
    if not ticker or not TICKER_BATCH_RE.match(ticker):
        return jsonify({"error": "Invalid ticker."}), 400

    try:
        m = _universe_service.enrich_ticker(ticker)
    except Exception:
        app.logger.exception("Enrich failed for %s", ticker)
        return jsonify({"error": "Enrichment failed."}), 500

    scores = _scores_for_metric(m)
    m_dict = m.to_dict()
    m_dict["scores"] = scores.to_dict()

    # Peer discovery: same sector + region, up to 8, exclude input ticker.
    peer_tickers = data.get("peer_tickers")
    if not peer_tickers:
        sec = m.security
        peer_rows = [
            r for r in _universe_service.rows()
            if (r.get("sector") or "").lower() == (sec.sector or "").lower()
            and r["ticker"].upper() != ticker
        ][:12]
        peer_tickers = [r["ticker"].upper() for r in peer_rows]
    else:
        peer_tickers = [str(t).upper() for t in peer_tickers if isinstance(t, str)][:12]

    from concurrent.futures import ThreadPoolExecutor, as_completed
    peer_dicts = []
    if peer_tickers:
        with ThreadPoolExecutor(max_workers=6) as ex:
            futures = {ex.submit(_enrich_ticker_with_scores, t): t for t in peer_tickers}
            for fut in as_completed(futures):
                res = fut.result()
                if res:
                    peer_dicts.append(res)

    matrix = _peer_matrix(m_dict, peer_dicts)
    src_name, src_url = _universe_service.historical.source_for(ticker)

    # Events (best effort)
    events_dict = {}
    try:
        ev = _universe_service.events.fetch(ticker)
        events_dict = {k: v.to_dict() for k, v in ev.items()}
    except Exception:
        events_dict = {}

    # Inject events into the input metrics dict so the Stock Analysis Events
    # tab + Sources audit can render them.
    for ev_key in ("earnings_date", "dividend_date", "ex_dividend_date", "split_date"):
        if ev_key in events_dict:
            m_dict[ev_key] = events_dict[ev_key]

    # Scenario recommendation (uses metrics + scores + events)
    metrics_for_scenario = {
        "price": m.price, "ma20": m.ma20, "ma50": m.ma50, "ma200": m.ma200,
        "fifty_two_week_high": m.fifty_two_week_high,
        "fifty_two_week_low": m.fifty_two_week_low,
        "rsi14": m.rsi14, "roc14": m.roc14, "roc21": m.roc21,
        "trailing_pe": m.trailing_pe, "percent_from_low": m.percent_from_low,
        "security": m.security.to_dict(),
    }
    try:
        scenario = build_scenario(metrics_for_scenario, scores, events_dict)
    except Exception:
        app.logger.exception("Scenario build failed for %s", ticker)
        scenario = None

    return jsonify(_scrub_nan({
        "input": m_dict,
        "peers": peer_dicts,
        "peer_matrix": matrix,
        "history_source": {"name": src_name, "url": src_url},
        "events": events_dict,
        "scenario": scenario,
    }))


@app.route("/api/events")
def api_events():
    """Events for a single ticker."""
    ticker = (request.args.get("ticker") or "").upper().strip()
    if not ticker or not TICKER_BATCH_RE.match(ticker):
        return jsonify({"error": "Invalid ticker."}), 400
    try:
        ev = _universe_service.events.fetch(ticker)
    except Exception:
        app.logger.exception("Events fetch failed for %s", ticker)
        return jsonify({"error": "Events fetch failed."}), 500
    return jsonify(_scrub_nan({
        "ticker": ticker,
        "events": {k: v.to_dict() for k, v in ev.items()},
    }))


@app.route("/api/events/calendar", methods=["POST"])
def api_events_calendar():
    """Events for a list of tickers (e.g. from a watchlist or screener result)."""
    data = request.get_json(silent=True) or {}
    tickers = data.get("tickers") or []
    if not isinstance(tickers, list) or not tickers:
        return jsonify({"error": "tickers (list) required."}), 400
    if len(tickers) > 30:
        return jsonify({"error": "Max 30 tickers per request."}), 400
    cleaned = []
    for t in tickers:
        if not isinstance(t, str):
            continue
        t = t.upper().strip()
        if TICKER_BATCH_RE.match(t):
            cleaned.append(t)
    if not cleaned:
        return jsonify({"error": "No valid tickers."}), 400

    from concurrent.futures import ThreadPoolExecutor, as_completed
    out = {}
    with ThreadPoolExecutor(max_workers=6) as ex:
        futures = {ex.submit(_universe_service.events.fetch, t): t for t in cleaned}
        for fut in as_completed(futures):
            t = futures[fut]
            try:
                ev = fut.result()
                out[t] = {k: v.to_dict() for k, v in ev.items()}
            except Exception:
                out[t] = {}
    return jsonify(_scrub_nan({"events": out}))


@app.route("/api/data-quality/audit")
def api_data_quality_audit():
    """Source-audit table over the curated universe (cached for 30 min).

    Returns rows of {ticker, metric, value, source, url, retrieved_at,
    freshness, confidence, warning} for every metric on every ticker we
    have in our enrichment cache.
    """
    rows = []
    counts = {"real-time": 0, "delayed": 0, "previous-close": 0,
              "historical-only": 0, "cached": 0, "unavailable": 0, "mock": 0}
    by_ticker_status = {}

    METRIC_KEYS = (
        "price", "market_cap_local", "market_cap_usd", "trailing_pe",
        "forward_pe", "price_to_book", "dividend_yield", "avg_daily_volume",
        "fifty_two_week_high", "fifty_two_week_low", "rsi14", "roc14", "roc21",
        "ma20", "ma50", "ma200",
    )

    # Walk the enriched cache (only stocks the user has seen / screened recently)
    for entry_ts, entry in list(_universe_service._enriched_cache._store.values()):
        if entry is None:
            continue
        sec = entry.security
        ticker = sec.ticker
        for key in METRIC_KEYS:
            sv = getattr(entry, key, None)
            if sv is None:
                continue
            f = getattr(sv, "freshness", "unavailable")
            counts[f] = counts.get(f, 0) + 1
            rows.append({
                "ticker": ticker,
                "metric": key,
                "value": sv.value,
                "source": sv.source_name,
                "url": sv.source_url,
                "retrieved_at": sv.retrieved_at,
                "freshness": f,
                "confidence": sv.confidence,
                "warning": sv.warning,
            })
            status = by_ticker_status.setdefault(ticker, {"available": 0, "missing": 0, "mock": 0})
            if sv.value is None:
                status["missing"] += 1
            elif f == "mock":
                status["mock"] += 1
            else:
                status["available"] += 1

    cache_stats = _universe_service._enriched_cache.stats()
    return jsonify(_scrub_nan({
        "audit_rows": rows,
        "row_count": len(rows),
        "freshness_counts": counts,
        "tickers_covered": list(by_ticker_status.keys()),
        "ticker_count": len(by_ticker_status),
        "ticker_status": by_ticker_status,
        "cache_stats": cache_stats,
        "next_refresh_seconds": cache_stats["ttl_seconds"],
    }))


@app.route("/api/data-quality/stats")
def api_data_quality_stats():
    """Lightweight summary used by the Data Quality dashboard hero."""
    audit = api_data_quality_audit().get_json()
    rows = audit["audit_rows"]
    total = len(rows)
    if total == 0:
        return jsonify({
            "total_metrics": 0,
            "tickers_covered": 0,
            "avg_confidence_pct": None,
            "freshness_counts": audit["freshness_counts"],
            "stale_pct": 0,
            "mock_pct": 0,
            "missing_pct": 0,
        })
    fc = audit["freshness_counts"]
    return jsonify({
        "total_metrics": total,
        "tickers_covered": audit["ticker_count"],
        "freshness_counts": fc,
        "stale_pct": round(100 * fc.get("historical-only", 0) / total, 1),
        "mock_pct": round(100 * fc.get("mock", 0) / total, 1),
        "missing_pct": round(100 * fc.get("unavailable", 0) / total, 1),
        "fresh_pct": round(100 * (fc.get("real-time", 0) + fc.get("delayed", 0) + fc.get("previous-close", 0) + fc.get("cached", 0)) / total, 1),
        "next_refresh_seconds": audit["next_refresh_seconds"],
    })


@app.route("/api/analyze", methods=["POST"])
def api_analyze():
    data = request.get_json(silent=True) or request.form
    ticker = (data.get("ticker") or "").strip().upper()
    if not ticker:
        return jsonify({"error": "Ticker required."}), 400
    if not TICKER_RE.match(ticker):
        return jsonify({"error": "Invalid ticker format."}), 400

    listing = {
        "ticker": ticker,
        "company": _sanitize_optional(data.get("company")),
        "exchange": _sanitize_optional(data.get("exchange"), max_len=40),
        "country": _sanitize_optional(data.get("country"), max_len=40),
        "region": _sanitize_optional(data.get("region"), max_len=40),
        "currency": _sanitize_optional(data.get("currency"), max_len=8),
        "sector": _sanitize_optional(data.get("sector")),
        "industry": _sanitize_optional(data.get("industry")),
    }
    if not listing.get("country"):
        meta = listing_meta(ticker)
        listing.update({k: meta[k] for k in ("exchange", "country", "region", "currency")})

    try:
        result = run_analysis(listing)
        if "error" in result:
            return jsonify(result), 400
        return jsonify(result)
    except Exception:
        app.logger.exception("Analysis failed for %s", ticker)
        return jsonify({"error": "Analysis failed. See server logs."}), 500


# Build the WSGI application that respects URL_PREFIX so internal `url_for`
# calls render the prefix automatically and requests outside the prefix 404.
if URL_PREFIX:
    application = DispatcherMiddleware(NotFound(), {URL_PREFIX: app})
else:
    application = app


def _build_ssl_context():
    cert = os.getenv("SSL_CERT")
    key = os.getenv("SSL_KEY")
    if not (cert and key):
        return None
    if not (os.path.exists(cert) and os.path.exists(key)):
        raise FileNotFoundError(f"SSL_CERT or SSL_KEY missing: {cert}, {key}")
    ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
    ctx.load_cert_chain(cert, key)
    return ctx


if __name__ == "__main__":
    host = os.getenv("HOST", "127.0.0.1")
    port = int(os.getenv("PORT", "5050"))
    ctx = _build_ssl_context()
    from werkzeug.serving import run_simple
    scheme = "https" if ctx else "http"
    print(f"Serving {scheme}://{host}:{port}{URL_PREFIX or '/'} ...")
    run_simple(host, port, application, ssl_context=ctx, use_reloader=False, threaded=True)
