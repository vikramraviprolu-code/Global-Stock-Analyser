"""Render smoke for every user-facing route.

Substitutes for a full browser-driven Playwright suite — the app is a
server-rendered Flask app with progressive JS enhancement, so the high-
value gap left by pytest is "does every template render without raising
a Jinja / TypeError, and does it carry the expected landmark structure?"

This file hits every non-API route via Flask's test_client, asserts:
  1. HTTP 200 (template doesn't 500 on render)
  2. Content-Type starts with text/html (not an error JSON)
  3. Body contains the per-route landmark string we expect a human to see
  4. The global script tags wired up in v0.22.0 (alerts.js + APP_BASE)
     are present where they should be

If you add a new route or rename a template, update USER_ROUTES.
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pytest


@pytest.fixture
def client():
    import app as app_module
    app_module.app.testing = True
    return app_module.app.test_client()


# (path, expected_status, must_contain_substring, expects_alerts_js)
USER_ROUTES = [
    ("/",              200, "EquityScope",          False),  # landing
    ("/welcome",       200, "EquityScope",          False),
    ("/screener",      200, "Screener",             True),
    ("/app",           200, "Snapshot",             True),
    ("/sources",       200, "Sources",              True),
    ("/watchlists",    200, "Watchlist",            True),
    ("/compare",       200, "Compare",              True),
    ("/data-quality",  200, "Data",                 True),
    ("/events",        200, "Events",               True),
    ("/settings",      200, "Settings",             True),
    ("/portfolio",     200, "Portfolio",            True),
    ("/alerts",        200, "Alerts",               True),
    ("/news",          200, "News",                 True),
    ("/risk-profile",  200, "Risk",                 True),
    ("/privacy",       200, "Privacy",              True),
]


@pytest.mark.parametrize("path,status,landmark,expects_alerts", USER_ROUTES)
def test_user_route_renders(client, path, status, landmark, expects_alerts):
    resp = client.get(path)
    assert resp.status_code == status, f"{path} returned {resp.status_code}"
    ctype = resp.headers.get("Content-Type", "")
    assert ctype.startswith("text/html"), f"{path} returned {ctype}"
    body = resp.data.decode()
    assert landmark in body, f"{path} missing landmark '{landmark}'"
    if expects_alerts:
        assert "alerts.js" in body, f"{path} missing alerts.js (v0.22.0 wire-up)"


def test_security_txt_route_serves_rfc9116(client):
    resp = client.get("/.well-known/security.txt")
    assert resp.status_code == 200
    body = resp.data.decode()
    # RFC 9116 required fields
    for field in ("Contact:", "Expires:", "Canonical:", "Policy:"):
        assert field in body, f"security.txt missing {field}"


def test_security_txt_expires_not_in_past(client):
    """RFC 9116: Expires must be in the future. CI failsafe."""
    from datetime import datetime, timezone
    resp = client.get("/.well-known/security.txt")
    body = resp.data.decode()
    for line in body.splitlines():
        if line.startswith("Expires:"):
            iso = line.split(":", 1)[1].strip()
            # Normalise to RFC 3339 form fromisoformat understands on 3.9+.
            iso_norm = iso.replace(".000Z", "+00:00").replace("Z", "+00:00")
            dt = datetime.fromisoformat(iso_norm)
            assert dt > datetime.now(timezone.utc), \
                f"security.txt Expires has lapsed: {iso}"
            return
    pytest.fail("Expires line not found in security.txt")


def test_favicon_serves(client):
    resp = client.get("/favicon.ico")
    assert resp.status_code == 200
    ctype = resp.headers.get("Content-Type", "")
    assert "svg" in ctype or "icon" in ctype


def test_csp_header_present_on_html_routes(client):
    """All HTML routes must carry the strict CSP installed in v0.3.0."""
    for path in ("/screener", "/app", "/watchlists", "/risk-profile"):
        resp = client.get(path)
        csp = resp.headers.get("Content-Security-Policy", "")
        assert "script-src 'self'" in csp, f"{path} CSP missing script-src 'self'"
        assert "frame-ancestors 'none'" in csp, f"{path} CSP missing frame-ancestors 'none'"


def test_x_frame_options_on_html_routes(client):
    resp = client.get("/screener")
    assert resp.headers.get("X-Frame-Options", "") == "DENY"


def test_server_timing_header_present(client):
    """v0.21.0 commitment: every response carries Server-Timing."""
    resp = client.get("/screener")
    assert "Server-Timing" in resp.headers
    assert "app;dur=" in resp.headers["Server-Timing"]
