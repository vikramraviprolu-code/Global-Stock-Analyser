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
import os
import re
import ssl
import threading
import time
from flask import Flask, render_template, request, jsonify
from werkzeug.middleware.dispatcher import DispatcherMiddleware
from werkzeug.exceptions import NotFound
from analyzer import run_analysis
from resolver import search, needs_disambiguation
from markets import listing_meta

URL_PREFIX = os.getenv("URL_PREFIX", "").rstrip("/")  # e.g. "/Local"

app = Flask(__name__)
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


@app.after_request
def _security_headers(resp):
    resp.headers["X-Content-Type-Options"] = "nosniff"
    resp.headers["X-Frame-Options"] = "DENY"
    resp.headers["Referrer-Policy"] = "no-referrer"
    resp.headers["Permissions-Policy"] = "geolocation=(), microphone=(), camera=()"
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


@app.route("/")
def landing():
    return render_template("landing.html")


@app.route("/app")
def dashboard():
    return render_template("index.html")


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
    """Browser-triggered graceful shutdown (sent on beforeunload)."""
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
