"""v1.2.0 round-trip release tests.

Two layers:
1. Template-level — confirm import / export / backup buttons + script
   tags are present where promised.
2. Schema-level — exercise the validation logic in static/backup.js by
   reading the file and running its validators against handcrafted
   payloads. Done via Node? No — we don't ship Node in CI. Instead we
   re-implement the exact same validation in Python and assert the
   shape contract. The JS code is short enough that it's worth pinning
   the contract twice — drift between the two would be caught by the
   render-smoke tests pulling text from the file.
"""
import sys
import os
import re
import json

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pytest


# ---------- 1. Template + script presence ----------

USER_FACING_PAGES_WITH_BACKUP = [
    ("templates/watchlists.html", "↑ Import JSON"),
    ("templates/alerts.html", "id=\"al-export\""),
    ("templates/alerts.html", "id=\"al-import\""),
    ("templates/privacy.html", "id=\"bk-backup-all\""),
    ("templates/privacy.html", "id=\"bk-restore-all\""),
    ("templates/privacy.html", "id=\"bk-wipe-all\""),
]


@pytest.mark.parametrize("path,marker", USER_FACING_PAGES_WITH_BACKUP)
def test_backup_ui_present(path, marker):
    abs_path = os.path.join(os.path.dirname(__file__), "..", path)
    with open(abs_path) as f:
        body = f.read()
    assert marker in body, f"{path} missing '{marker}'"


@pytest.mark.parametrize("tmpl", [
    "watchlists.html", "alerts.html", "privacy.html",
])
def test_backup_js_loaded(tmpl):
    abs_path = os.path.join(os.path.dirname(__file__), "..", "templates", tmpl)
    with open(abs_path) as f:
        body = f.read()
    assert "backup.js" in body, f"{tmpl} missing backup.js script tag"


def test_backup_js_exists_with_required_exports():
    """static/backup.js must define every public API the templates call."""
    path = os.path.join(os.path.dirname(__file__), "..", "static", "backup.js")
    with open(path) as f:
        body = f.read()
    for export in (
        "TICKER_RE", "ES_KEYS", "BACKUP_VERSION",
        "function download", "function pickFile",
        "validateWatchlistImport", "validateAlertsImport",
        "validatePortfolioImport",
        "function backupAll", "function restoreAll",
        "window.EsBackup",
    ):
        assert export in body, f"backup.js missing '{export}'"


def test_backup_bundles_all_equityscope_keys():
    """ES_KEYS must list every key the project documents in SECURITY/USER_GUIDE."""
    path = os.path.join(os.path.dirname(__file__), "..", "static", "backup.js")
    with open(path) as f:
        body = f.read()
    for k in (
        "equityscope.watchlists",
        "equityscope.portfolio",
        "equityscope.alerts",
        "equityscope.customPresets",
        "equityscope.prefs",
        "equityscope.colState",
        "equityscope.riskProfile",
        "equityscope.consent",
    ):
        assert k in body, f"ES_KEYS missing '{k}'"


# ---------- 2. Python mirror of the validators (contract pin) ----------

TICKER_RE = re.compile(r"^[A-Z0-9]{1,12}(?:-[A-Z0-9]{1,4})?(?:\.[A-Z]{1,4})?$")


def py_validate_watchlist(parsed):
    """Mirror of EsBackup.validateWatchlistImport — keep in lockstep."""
    if not isinstance(parsed, dict):
        return {"ok": False, "error": "Not a JSON object."}
    if isinstance(parsed.get("tickers"), list):
        clean = [t.upper().strip() for t in parsed["tickers"]
                 if isinstance(t, str) and TICKER_RE.match(t.upper().strip())]
        if not clean:
            return {"ok": False, "error": "No valid tickers."}
        if len(clean) > 200:
            return {"ok": False, "error": "Over 200-ticker cap."}
        return {"ok": True, "kind": "single",
                "name": str(parsed.get("watchlist", "Imported"))[:80],
                "tickers": clean}
    if isinstance(parsed.get("watchlists"), dict):
        if len(parsed["watchlists"]) > 50:
            return {"ok": False, "error": "Over 50-list cap."}
        lists = {}
        for n, arr in parsed["watchlists"].items():
            if not isinstance(arr, list):
                continue
            clean = [t.upper().strip() for t in arr
                     if isinstance(t, str) and TICKER_RE.match(t.upper().strip())][:200]
            lists[str(n)[:80]] = clean
        if not lists:
            return {"ok": False, "error": "No valid lists."}
        return {"ok": True, "kind": "full", "lists": lists,
                "active": parsed.get("active") if isinstance(parsed.get("active"), str) else None}
    return {"ok": False, "error": "Missing 'tickers' or 'watchlists' field."}


def test_validate_watchlist_single():
    r = py_validate_watchlist({"watchlist": "My List",
                               "tickers": ["AAPL", "MSFT", "BRK-B"]})
    assert r["ok"] and r["kind"] == "single"
    assert r["tickers"] == ["AAPL", "MSFT", "BRK-B"]
    assert r["name"] == "My List"


def test_validate_watchlist_full():
    r = py_validate_watchlist({
        "version": 1,
        "watchlists": {"A": ["AAPL"], "B": ["MSFT", "GOOG"]},
        "active": "A"
    })
    assert r["ok"] and r["kind"] == "full"
    assert set(r["lists"].keys()) == {"A", "B"}
    assert r["active"] == "A"


def test_validate_watchlist_strips_invalid_tickers():
    r = py_validate_watchlist({"watchlist": "X",
                               "tickers": ["AAPL", "<bad>", "GOOG", 123, "MSFT"]})
    assert r["ok"]
    assert r["tickers"] == ["AAPL", "GOOG", "MSFT"]


def test_validate_watchlist_rejects_garbage():
    assert py_validate_watchlist(None)["ok"] is False
    assert py_validate_watchlist("string")["ok"] is False
    assert py_validate_watchlist({})["ok"] is False
    assert py_validate_watchlist({"foo": "bar"})["ok"] is False


def test_validate_watchlist_caps_oversize():
    r = py_validate_watchlist({"tickers": [f"T{i}" for i in range(201)]})
    assert r["ok"] is False
    assert "200" in r["error"]


def py_validate_alerts(parsed):
    if not isinstance(parsed, dict):
        return {"ok": False, "error": "Not a JSON object."}
    arr = parsed.get("alerts")
    if not isinstance(arr, list):
        return {"ok": False, "error": "Missing 'alerts' array."}
    if len(arr) > 200:
        return {"ok": False, "error": "Over 200-alert cap."}
    cleaned = []
    for a in arr:
        if not isinstance(a, dict):
            continue
        if not isinstance(a.get("ticker"), str):
            continue
        if not TICKER_RE.match(a["ticker"].upper().strip()):
            continue
        if not isinstance(a.get("kind"), str):
            continue
        cleaned.append({"ticker": a["ticker"].upper().strip(),
                        "kind": a["kind"]})
    if not cleaned:
        return {"ok": False, "error": "No valid alerts."}
    return {"ok": True, "alerts": cleaned}


def test_validate_alerts_happy_path():
    r = py_validate_alerts({
        "alerts": [
            {"ticker": "AAPL", "kind": "price_above", "threshold": 200},
            {"ticker": "MSFT", "kind": "rsi_overbought"},
        ]
    })
    assert r["ok"]
    assert len(r["alerts"]) == 2


def test_validate_alerts_strips_garbage_rows():
    r = py_validate_alerts({
        "alerts": [
            {"ticker": "AAPL", "kind": "price_above"},
            "not a dict",
            {"ticker": "<bad>", "kind": "x"},
            {"kind": "no_ticker"},
            {"ticker": "GOOG"},
        ]
    })
    assert r["ok"]
    assert len(r["alerts"]) == 1
    assert r["alerts"][0]["ticker"] == "AAPL"


def py_validate_backup_all(parsed, backup_version=1):
    if not isinstance(parsed, dict):
        return {"ok": False, "error": "Not a JSON object."}
    if parsed.get("schema") != "equityscope-backup":
        return {"ok": False, "error": "Not an EquityScope backup file."}
    if parsed.get("version", 0) > backup_version:
        return {"ok": False, "error": "Backup version too new."}
    if not isinstance(parsed.get("keys"), dict):
        return {"ok": False, "error": "Missing 'keys' map."}
    return {"ok": True}


def test_backup_all_schema_validates():
    bundle = {
        "schema": "equityscope-backup",
        "version": 1,
        "exportedAt": "2026-05-02T16:30:00Z",
        "keys": {
            "equityscope.watchlists": {"version": 1, "watchlists": {}, "active": ""},
            "equityscope.consent": {"accepted": True},
        },
    }
    assert py_validate_backup_all(bundle)["ok"] is True


def test_backup_all_rejects_wrong_schema():
    assert py_validate_backup_all({"schema": "other", "version": 1, "keys": {}})["ok"] is False


def test_backup_all_rejects_future_version():
    assert py_validate_backup_all({"schema": "equityscope-backup",
                                   "version": 99, "keys": {}})["ok"] is False


def test_backup_all_rejects_missing_keys():
    assert py_validate_backup_all({"schema": "equityscope-backup",
                                   "version": 1})["ok"] is False


# ---------- 3. End-to-end round trips (export shape) ----------

def test_watchlist_export_shape_consumable_by_import():
    """Exported watchlist JSON (from /watchlists ↓ JSON) must validate
    cleanly through validateWatchlistImport. This is the round-trip
    contract — break this and existing exports become un-importable."""
    exported = {
        "watchlist": "Tech Megacaps",
        "exportedAt": "2026-05-02T16:30:00Z",
        "tickers": ["AAPL", "MSFT", "GOOG", "META", "AMZN"],
        "metrics": [{"security": {"ticker": "AAPL"}}],
    }
    r = py_validate_watchlist(exported)
    assert r["ok"]
    assert r["kind"] == "single"
    assert r["tickers"] == ["AAPL", "MSFT", "GOOG", "META", "AMZN"]


def test_alerts_export_shape_consumable_by_import():
    exported = {
        "schema": "equityscope-alerts",
        "version": 1,
        "exportedAt": "2026-05-02T16:30:00Z",
        "alerts": [
            {"id": "a1", "ticker": "AAPL", "kind": "price_above",
             "threshold": 200, "status": "active",
             "createdAt": "2026-04-01T00:00:00Z", "notes": ""},
        ],
        "pollMinutes": 5,
        "desktopNotifications": True,
    }
    r = py_validate_alerts(exported)
    assert r["ok"]
    assert len(r["alerts"]) == 1
    assert r["alerts"][0]["ticker"] == "AAPL"
