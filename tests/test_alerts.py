"""Tests for /alerts route. Alert engine itself is browser-side JS — covered
manually via DevTools and the existing /api/metrics tests."""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pytest


@pytest.fixture
def client():
    import app as app_module
    app_module.app.testing = True
    return app_module.app.test_client()


def test_alerts_route_renders(client):
    resp = client.get("/alerts")
    assert resp.status_code == 200
    body = resp.data.decode()
    # Page presence
    assert "Alerts" in body
    assert "Add Alert" in body
    assert 'id="al-tbody"' in body
    assert 'id="al-log-tbody"' in body
    # JS bundle loaded
    assert "alerts.js" in body
    assert "ui.js" in body


def test_alerts_link_in_nav(client):
    resp = client.get("/screener")
    body = resp.data.decode()
    assert "/alerts" in body
    # Must NOT be aria-disabled placeholder
    assert 'aria-disabled="true">Alerts' not in body


def test_alerts_route_has_add_form_kinds(client):
    """Verify all 11 alert kinds surface in the page select."""
    resp = client.get("/alerts")
    body = resp.data.decode()
    for kind in ("price_above", "price_below", "pct_change_5d",
                 "rsi_above", "rsi_below",
                 "cross_ma200_up", "cross_ma200_down",
                 "cross_ma50_up", "cross_ma50_down",
                 "near_52w_low", "near_52w_high"):
        assert f'value="{kind}"' in body


def test_alerts_route_has_polling_controls(client):
    resp = client.get("/alerts")
    body = resp.data.decode()
    assert 'id="al-poll-min"' in body
    assert 'id="al-desktop"' in body
    assert 'id="al-test-poll"' in body


def test_alerts_route_disclaimer_present(client):
    resp = client.get("/alerts")
    body = resp.data.decode()
    assert "Not financial advice" in body
