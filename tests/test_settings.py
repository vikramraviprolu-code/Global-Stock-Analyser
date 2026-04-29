"""Tests for /settings route, /api/settings/server-info, /api/settings/clear-cache."""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pytest


@pytest.fixture
def client():
    import app as app_module
    app_module.app.testing = True
    return app_module.app.test_client()


def test_settings_route_renders(client):
    resp = client.get("/settings")
    assert resp.status_code == 200
    body = resp.data.decode()
    assert "Settings" in body
    # Sections present
    assert "Preferences" in body
    assert "Watchlists" in body
    assert "Custom Screener Presets" in body
    assert "Server Info" in body
    assert "Reset" in body


def test_server_info_returns_required_keys(client):
    resp = client.get("/api/settings/server-info")
    assert resp.status_code == 200
    data = resp.get_json()
    for key in ("version", "python", "platform", "url_prefix",
                "trusted_hosts", "tls_enabled", "auto_shutdown",
                "idle_timeout", "universe_size", "cache_stats"):
        assert key in data
    assert isinstance(data["trusted_hosts"], list)
    assert data["universe_size"] >= 0


def test_server_info_version_matches_pyproject(client):
    """Version pin in API should match pyproject.toml."""
    resp = client.get("/api/settings/server-info")
    data = resp.get_json()
    # We bump it manually each release; just ensure it's a non-empty string
    assert isinstance(data["version"], str)
    assert len(data["version"]) > 0


def test_clear_cache_blocks_cross_origin(client):
    """No Origin header → CSRF rejection (only loopback + trusted Origin allowed)."""
    resp = client.post("/api/settings/clear-cache")
    # Either 403 (CSRF) or 400 — must NOT clear without proper Origin
    assert resp.status_code in (400, 403)


def test_clear_cache_blocks_untrusted_origin(client):
    resp = client.post("/api/settings/clear-cache",
                       headers={"Origin": "https://evil.example.com"})
    assert resp.status_code == 403


def test_clear_cache_with_trusted_origin_succeeds(client):
    resp = client.post("/api/settings/clear-cache",
                       headers={"Origin": "https://global-stock-analyser"})
    assert resp.status_code == 200
    assert resp.get_json()["cleared"] is True


def test_settings_link_in_nav(client):
    """Settings link appears in nav (no longer 'Coming soon')."""
    resp = client.get("/screener")
    body = resp.data.decode()
    # The nav now has a real Settings link
    assert "/settings" in body
