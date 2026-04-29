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
from providers import UniverseService
from screener import Filter, ScreenerEngine, PRESETS, get_preset
from screener.presets import list_presets
from calc.scoring import score_all

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


def _filters_from_payload(payload: dict) -> list:
    """Convert JSON {kind, value} dicts into Filter dataclasses, with input
    validation. Reject anything that doesn't match the supported kinds."""
    if not isinstance(payload, list):
        return []
    valid_kinds = {
        "sector_in", "country_in", "region_in", "exchange_in",
        "price_min", "price_max", "mcap_usd_min", "mcap_usd_max",
        "pe_min", "pe_max", "rsi_min", "rsi_max",
        "perf5d_min", "perf5d_max", "pct_from_low_max",
        "above_ma200", "dividend_min",
    }
    out = []
    for item in payload[:32]:  # cap to prevent abuse
        if not isinstance(item, dict):
            continue
        kind = str(item.get("kind", ""))
        if kind not in valid_kinds:
            continue
        value = item.get("value")
        # Type-coerce safely
        if kind in ("sector_in", "country_in", "region_in", "exchange_in"):
            if not isinstance(value, list):
                continue
            value = [str(v)[:60] for v in value[:32]]
        elif kind == "above_ma200":
            value = bool(value)
        else:
            try:
                value = float(value)
            except (TypeError, ValueError):
                continue
        out.append(Filter(kind=kind, value=value, label=item.get("label")))
    return out


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

    # Throttle: max 30 filters
    if len(filters) > 30:
        return jsonify({"error": "Too many filters."}), 400

    try:
        result = _screener_engine.screen(filters)
    except Exception:
        app.logger.exception("Screener run failed")
        return jsonify({"error": "Screener failed. See server logs."}), 500

    # Attach scores for every match (computed cheaply on top of metrics)
    payload_matches = []
    for m in result.matches:
        m_dict = m.to_dict()
        # score_all expects a dict-shaped metrics; reuse the original SourcedValue-bearing object
        scores = score_all({
            "price": m.price, "market_cap_usd": m.market_cap_usd,
            "trailing_pe": m.trailing_pe, "rsi14": m.rsi14, "roc14": m.roc14,
            "roc21": m.roc21, "ma20": m.ma20, "ma50": m.ma50, "ma200": m.ma200,
            "five_day_performance": m.five_day_performance,
            "percent_from_low": m.percent_from_low,
            "fifty_two_week_high": m.fifty_two_week_high,
            "dividend_yield": m.dividend_yield,
            "price_to_book": m.price_to_book,
            "avg_daily_volume": m.avg_daily_volume,
            "fifty_two_week_low": m.fifty_two_week_low,
            "security": m.security.to_dict(),
        })
        m_dict["scores"] = scores.to_dict()
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
    """Batch-enrich a list of tickers for watchlists / compare. Up to 6 to
    keep response time bounded."""
    data = request.get_json(silent=True) or {}
    tickers = data.get("tickers") or []
    if not isinstance(tickers, list) or not tickers:
        return jsonify({"error": "tickers (list) required."}), 400
    if len(tickers) > 12:
        return jsonify({"error": "Max 12 tickers per request."}), 400

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
    # Preserve original order
    by_ticker = {m["security"]["ticker"]: m for m in out}
    ordered = [by_ticker[t] for t in cleaned if t in by_ticker]
    return jsonify(_scrub_nan({"metrics": ordered}))


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


@app.route("/api/sources/health")
def api_sources_health():
    return jsonify({
        "providers": {
            "historical": {
                "name": "Stooq CSV → yfinance fallback",
                "type": "free",
                "url": "https://stooq.com",
                "fallback_url": "https://finance.yahoo.com",
            },
            "fundamentals": {
                "name": "yfinance (.info)",
                "type": "free / best-effort",
                "url": "https://finance.yahoo.com",
            },
            "fx": {
                "name": "yfinance currency pairs",
                "type": "free",
            },
            "symbol_resolver": {
                "name": "Curated universe + yfinance Search",
                "type": "free",
            },
            "mock": {
                "name": "Synthetic fallback",
                "type": "mock — only when live source fails",
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
