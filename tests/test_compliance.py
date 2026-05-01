"""Tests for v0.20.0 compliance + risk profile + security additions:
GDPR / EU AI Act privacy page, security.txt, SRI hash, consent banner,
risk profile bundle, route registrations."""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pytest


@pytest.fixture
def client():
    import app as app_module
    app_module.app.testing = True
    return app_module.app.test_client()


# ---------- routes ----------

def test_risk_profile_route_renders(client):
    resp = client.get("/risk-profile")
    assert resp.status_code == 200
    body = resp.data.decode()
    assert "Risk Profile" in body
    assert "Questionnaire" in body
    assert "risk_profile.js" in body


def test_privacy_route_renders(client):
    resp = client.get("/privacy")
    assert resp.status_code == 200
    body = resp.data.decode()
    # Required GDPR + AI Act sections
    assert "GDPR" in body
    assert "EU AI Act" in body
    assert "Article 6" in body or "Article 6(1)" in body  # lawful basis
    assert "Article 22" in body  # ADM
    assert "data subject rights" in body.lower() or "subject rights" in body.lower()
    assert "rule-based" in body.lower()
    # No-cookies declaration must appear verbatim
    assert "No cookies" in body


def test_security_txt_served(client):
    """RFC 9116 well-known location must serve text/plain."""
    resp = client.get("/.well-known/security.txt")
    assert resp.status_code == 200
    assert "text/plain" in resp.headers.get("Content-Type", "")
    body = resp.data.decode()
    assert "Contact:" in body
    assert "Expires:" in body
    assert "Policy:" in body
    assert "Canonical:" in body


def test_risk_profile_link_in_nav(client):
    resp = client.get("/screener")
    body = resp.data.decode()
    assert "/risk-profile" in body


# ---------- bundles ----------

@pytest.fixture
def risk_profile_source():
    here = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    with open(os.path.join(here, "static", "risk_profile.js")) as f:
        return f.read()


def test_risk_profile_js_has_10_questions(risk_profile_source):
    """PRD: 10-question profile."""
    qs = sum(1 for i in range(1, 11) if f'id: "q{i}"' in risk_profile_source)
    assert qs == 10, f"Expected 10 questions, found {qs}"


def test_risk_profile_js_has_5_buckets(risk_profile_source):
    """5 buckets: conservative / moderate / balanced / growth / aggressive."""
    for key in ("conservative", "moderate", "balanced", "growth", "aggressive"):
        assert key in risk_profile_source, f"Missing bucket: {key}"


def test_risk_profile_js_exports_api(risk_profile_source):
    assert "window.RiskProfile" in risk_profile_source
    for fn in ("save", "get", "clear", "bucketFor"):
        assert fn in risk_profile_source


@pytest.fixture
def consent_source():
    here = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    with open(os.path.join(here, "static", "consent.js")) as f:
        return f.read()


def test_consent_js_exposes_required_methods(consent_source):
    assert "window.Consent" in consent_source
    for fn in ("accept", "decline", "status", "isAccepted", "isDeclined", "reset"):
        assert fn in consent_source


def test_consent_decline_wipes_storage(consent_source):
    """Per GDPR Article 21 (right to object) — decline must purge stored data."""
    assert "removeItem" in consent_source
    assert "equityscope." in consent_source


def test_consent_loads_on_every_page(client):
    """consent.js should be loaded on every user-facing page."""
    routes = ["/screener", "/app", "/watchlists", "/compare", "/events",
              "/news", "/data-quality", "/sources", "/settings",
              "/portfolio", "/alerts", "/risk-profile", "/privacy"]
    for r in routes:
        resp = client.get(r)
        assert resp.status_code == 200, f"{r} returned {resp.status_code}"
        body = resp.data.decode()
        assert "consent.js" in body, f"{r} missing consent.js"


# ---------- SRI on vendor JS ----------

def test_lightweight_charts_has_sri_integrity(client):
    """Self-hosted vendor JS must carry an SRI integrity hash."""
    resp = client.get("/app")
    body = resp.data.decode()
    assert "vendor/lightweight-charts" in body
    assert 'integrity="sha384-' in body
    assert 'crossorigin="anonymous"' in body


def test_sri_hash_matches_actual_file():
    """Verify the hash in the template matches the served file."""
    import hashlib
    import base64
    import re
    here = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    js_path = os.path.join(here, "static", "vendor",
                           "lightweight-charts.standalone.production.js")
    with open(js_path, "rb") as f:
        digest = hashlib.sha384(f.read()).digest()
    expected = "sha384-" + base64.b64encode(digest).decode()

    with open(os.path.join(here, "templates", "index.html")) as f:
        html = f.read()
    m = re.search(r'integrity="(sha384-[^"]+)"', html)
    assert m, "SRI integrity attribute not found in index.html"
    actual = m.group(1)
    assert actual == expected, (
        f"SRI hash mismatch — vendor file has {expected}, template has {actual}. "
        "Re-run `openssl dgst -sha384 -binary <file> | openssl base64 -A` "
        "and update index.html."
    )


# ---------- AI Act key claims surface in privacy.html ----------

def test_privacy_states_no_ai(client):
    resp = client.get("/privacy")
    body = resp.data.decode().lower()
    # The page must explicitly declare no AI / no LLM / no ML
    assert "no machine-learning" in body or "no ml model" in body or "no machine learning" in body
    assert "no large language model" in body or "no llm" in body
    # Heuristic transparency
    assert "rule-based" in body
