"""Flask web app for global stock analysis."""
import re
from flask import Flask, render_template, request, jsonify
from analyzer import run_analysis
from resolver import search, needs_disambiguation
from markets import listing_meta

app = Flask(__name__)

# Strict ticker pattern: letters, digits, optional dot suffix, optional dash/ampersand.
# Examples that match: AAPL, BRK-B, M&M.NS, 0700.HK, RELIANCE.NS, 005930.KS, VOLV-B.ST
TICKER_RE = re.compile(r"^[A-Z0-9]{1,12}(?:-[A-Z0-9]{1,4})?(?:\.[A-Z]{1,4})?$")
SAFE_STR_RE = re.compile(r"^[A-Za-z0-9 .\-&,'/+()]{0,80}$")


def _sanitize_optional(value, max_len=80):
    """Return string if it's a safe, short identifier; None otherwise."""
    if value is None:
        return None
    s = str(value).strip()
    if not s or len(s) > max_len:
        return None
    if not SAFE_STR_RE.match(s):
        return None
    return s


@app.after_request
def _security_headers(resp):
    """Defense-in-depth: prevent clickjacking, MIME sniffing, content injection."""
    resp.headers["X-Content-Type-Options"] = "nosniff"
    resp.headers["X-Frame-Options"] = "DENY"
    resp.headers["Referrer-Policy"] = "no-referrer"
    resp.headers["Permissions-Policy"] = "geolocation=(), microphone=(), camera=()"
    if request.path.startswith("/static") or request.path in ("/", "/app"):
        # CSP locks scripts/styles to same origin; inline allowed for current templates.
        # Move to nonces if you externalize the app.js.
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
    # Disallow control chars and angle brackets to defang downstream consumers
    if re.search(r"[\x00-\x1f<>]", q):
        return jsonify({"error": "Invalid characters in query."}), 400
    candidates = search(q, limit=10)
    if not candidates:
        return jsonify({"candidates": [], "needs_choice": False})
    return jsonify({
        "candidates": candidates,
        "needs_choice": needs_disambiguation(candidates, q),
    })


@app.route("/api/analyze", methods=["POST"])
def api_analyze():
    data = request.get_json(silent=True) or request.form
    ticker = (data.get("ticker") or "").strip().upper()
    if not ticker:
        return jsonify({"error": "Ticker required."}), 400
    if not TICKER_RE.match(ticker):
        return jsonify({"error": "Invalid ticker format."}), 400

    # Sanitize all caller-provided metadata. Anything that fails the pattern is dropped
    # (we'll fall back to suffix-based inference instead of trusting the field).
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
    except Exception as e:
        # Avoid leaking internal exception details to clients
        app.logger.exception("Analysis failed for %s", ticker)
        return jsonify({"error": "Analysis failed. See server logs."}), 500


if __name__ == "__main__":
    app.run(host="127.0.0.1", port=5050, debug=False)
