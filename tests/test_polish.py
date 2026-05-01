"""Tests for v0.21.0 polish + perf budget items: Server-Timing header,
favicon, format.js bundle, prefers-reduced-motion CSS guard, JS bundle
budgets, PERFORMANCE.md presence."""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pytest


@pytest.fixture
def client():
    import app as app_module
    app_module.app.testing = True
    return app_module.app.test_client()


# ---------- Server-Timing ----------

def test_server_timing_header_on_every_response(client):
    """Every response should expose `Server-Timing: app;dur=<ms>`."""
    routes = ["/screener", "/api/screener/presets", "/api/sources/health"]
    for r in routes:
        resp = client.get(r)
        assert resp.status_code in (200, 204), f"{r} returned {resp.status_code}"
        st = resp.headers.get("Server-Timing", "")
        assert "app" in st, f"{r} missing Server-Timing app metric: {st!r}"
        assert "dur=" in st


# ---------- favicon ----------

def test_favicon_route_returns_svg(client):
    resp = client.get("/favicon.ico")
    assert resp.status_code == 200
    assert "image/svg+xml" in resp.headers.get("Content-Type", "")
    body = resp.data.decode()
    assert "<svg" in body
    # Cache-Control set
    assert "max-age" in resp.headers.get("Cache-Control", "")


def test_favicon_link_in_every_template(client):
    routes = ["/screener", "/app", "/watchlists", "/compare", "/events",
              "/news", "/data-quality", "/sources", "/settings",
              "/portfolio", "/alerts", "/risk-profile", "/privacy"]
    for r in routes:
        resp = client.get(r)
        body = resp.data.decode()
        assert 'rel="icon"' in body, f"{r} missing favicon link"


# ---------- format.js ----------

@pytest.fixture
def format_source():
    here = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    with open(os.path.join(here, "static", "format.js")) as f:
        return f.read()


def test_format_js_exposes_required_helpers(format_source):
    assert "window.Fmt" in format_source
    for fn in ("n", "pct", "mcap", "vol", "money", "cls",
               "flag", "sourceBadge", "scoreBar", "sparkline",
               "timeAgo", "date"):
        assert f"{fn}(" in format_source or f"{fn}:" in format_source, f"Fmt.{fn} missing"


def test_format_js_loaded_on_every_template(client):
    routes = ["/screener", "/app", "/watchlists", "/compare", "/events",
              "/news", "/data-quality", "/sources", "/settings",
              "/portfolio", "/alerts", "/risk-profile", "/privacy"]
    for r in routes:
        resp = client.get(r)
        body = resp.data.decode()
        assert "format.js" in body, f"{r} missing format.js"


# ---------- prefers-reduced-motion ----------

def test_screener_css_has_reduced_motion_guard():
    here = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    with open(os.path.join(here, "static", "screener.css")) as f:
        css = f.read()
    assert "prefers-reduced-motion" in css
    assert "animation-duration: 0.01ms" in css
    assert "transition-duration: 0.01ms" in css


# ---------- bundle size budgets ----------

BUDGETS_BYTES = {
    "ui.js": 7 * 1024,
    "format.js": 6 * 1024,
    "consent.js": 4 * 1024,
    "explainer.js": 30 * 1024,
    "watchlist.js": 6 * 1024,
    "portfolio.js": 8 * 1024,
    "alerts.js": 14 * 1024,
    "risk_profile.js": 6 * 1024,
}


def test_js_bundle_sizes_within_budget():
    here = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    for fname, max_bytes in BUDGETS_BYTES.items():
        path = os.path.join(here, "static", fname)
        size = os.path.getsize(path)
        assert size <= max_bytes, (
            f"{fname} is {size} bytes — exceeds budget of {max_bytes} bytes."
            " Update PERFORMANCE.md or trim the bundle."
        )


def test_lightweight_charts_size_within_budget():
    here = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    path = os.path.join(here, "static", "vendor",
                        "lightweight-charts.standalone.production.js")
    size = os.path.getsize(path)
    assert size <= 200 * 1024, f"vendor JS too big: {size} bytes"


# ---------- PERFORMANCE.md ----------

def test_performance_md_exists():
    here = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    path = os.path.join(here, "PERFORMANCE.md")
    assert os.path.exists(path)
    with open(path) as f:
        body = f.read()
    # Required sections
    assert "JavaScript bundle budgets" in body
    assert "Server response-time budgets" in body
    assert "Cache TTL summary" in body
    assert "Server-Timing" in body
