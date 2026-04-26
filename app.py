"""Flask web app for global stock analysis."""
from flask import Flask, render_template, request, jsonify
from analyzer import run_analysis
from resolver import search, needs_disambiguation
from markets import listing_meta

app = Flask(__name__)


@app.route("/")
def landing():
    return render_template("landing.html")


@app.route("/app")
def dashboard():
    return render_template("index.html")


@app.route("/api/search")
def api_search():
    q = (request.args.get("q") or "").strip()
    if not q or len(q) > 80:
        return jsonify({"error": "Empty or too-long query."}), 400
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
    if not ticker.replace(".", "").replace("-", "").replace("&", "").isalnum():
        return jsonify({"error": "Invalid ticker characters."}), 400
    if len(ticker) > 16:
        return jsonify({"error": "Ticker too long."}), 400

    # Caller may pass pre-resolved listing fields (from /api/search choice)
    listing = {
        "ticker": ticker,
        "company": data.get("company"),
        "exchange": data.get("exchange"),
        "country": data.get("country"),
        "region": data.get("region"),
        "currency": data.get("currency"),
        "sector": data.get("sector"),
        "industry": data.get("industry"),
    }
    # If caller didn't provide metadata, fall back to suffix-based inference.
    if not listing.get("country"):
        meta = listing_meta(ticker)
        listing.update({k: meta[k] for k in ("exchange", "country", "region", "currency")})

    try:
        result = run_analysis(listing)
        if "error" in result:
            return jsonify(result), 400
        return jsonify(result)
    except Exception as e:
        return jsonify({"error": f"Analysis failed: {e}"}), 500


if __name__ == "__main__":
    app.run(host="127.0.0.1", port=5050, debug=False)
