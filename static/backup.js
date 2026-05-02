// EquityScope shared import / export / backup helpers (v1.2.0).
//
// Centralises file-picker plumbing, ticker validation, and full-state
// backup/restore. Every page that exports or imports localStorage data
// goes through this module so the schema versioning, ticker regex, and
// download discipline stay consistent.
//
// Schema versioning:
//   v1  — watchlist + portfolio + alerts (per-collection)
//   v1  — backup-all bundle (this whole file)
//
// Public API:
//   EsBackup.TICKER_RE
//   EsBackup.download(content, filename, mime)
//   EsBackup.pickFile(accept) -> Promise<{name, text}>
//   EsBackup.validateWatchlistImport(parsed)
//   EsBackup.validateAlertsImport(parsed)
//   EsBackup.validatePortfolioImport(parsed)
//   EsBackup.backupAll()    -> JSON string of every equityscope.* key
//   EsBackup.restoreAll(parsed, {mode}) -> {ok, restored: [...keys], error}

(function () {
  const TICKER_RE = /^[A-Z0-9]{1,12}(?:-[A-Z0-9]{1,4})?(?:\.[A-Z]{1,4})?$/;
  const ES_KEYS = [
    "equityscope.watchlists",
    "equityscope.portfolio",
    "equityscope.alerts",
    "equityscope.customPresets",
    "equityscope.prefs",
    "equityscope.colState",
    "equityscope.riskProfile",
    "equityscope.consent",
  ];
  const BACKUP_VERSION = 1;
  const MAX_TICKERS_PER_LIST = 200;
  const MAX_LISTS = 50;
  const MAX_HOLDINGS = 500;
  const MAX_ALERTS = 200;

  function download(content, filename, mime) {
    const blob = new Blob([content], { type: mime });
    const a = document.createElement("a");
    a.href = URL.createObjectURL(blob);
    a.download = filename;
    a.click();
    URL.revokeObjectURL(a.href);
  }

  function pickFile(accept) {
    return new Promise((resolve, reject) => {
      const input = document.createElement("input");
      input.type = "file";
      if (accept) input.accept = accept;
      input.onchange = (e) => {
        const f = e.target.files && e.target.files[0];
        if (!f) return reject(new Error("No file selected"));
        const reader = new FileReader();
        reader.onload = () => resolve({ name: f.name, text: reader.result });
        reader.onerror = () => reject(reader.error);
        reader.readAsText(f);
      };
      input.click();
    });
  }

  function _validTicker(t) {
    return typeof t === "string" && TICKER_RE.test(t.toUpperCase().trim());
  }

  function validateWatchlistImport(parsed) {
    // Accepts both: a single watchlist export {watchlist, tickers, ...}
    // and the full Watchlists state {version, watchlists, active}.
    if (!parsed || typeof parsed !== "object") {
      return { ok: false, error: "Not a JSON object." };
    }
    if (parsed.tickers && Array.isArray(parsed.tickers)) {
      // Single-list export shape (from /watchlists ↓ JSON button).
      const name = (parsed.watchlist || "Imported").toString().slice(0, 80);
      const clean = parsed.tickers
        .map((t) => (typeof t === "string" ? t.toUpperCase().trim() : ""))
        .filter(_validTicker);
      if (!clean.length) return { ok: false, error: "No valid tickers." };
      if (clean.length > MAX_TICKERS_PER_LIST) {
        return { ok: false, error: `Over ${MAX_TICKERS_PER_LIST}-ticker cap.` };
      }
      return { ok: true, kind: "single", name, tickers: clean };
    }
    if (parsed.watchlists && typeof parsed.watchlists === "object") {
      // Full state shape.
      const lists = {};
      const names = Object.keys(parsed.watchlists);
      if (names.length > MAX_LISTS) {
        return { ok: false, error: `Over ${MAX_LISTS}-list cap.` };
      }
      for (const n of names) {
        const arr = parsed.watchlists[n];
        if (!Array.isArray(arr)) continue;
        const clean = arr
          .map((t) => (typeof t === "string" ? t.toUpperCase().trim() : ""))
          .filter(_validTicker)
          .slice(0, MAX_TICKERS_PER_LIST);
        lists[n.toString().slice(0, 80)] = clean;
      }
      if (!Object.keys(lists).length) {
        return { ok: false, error: "No valid lists." };
      }
      return { ok: true, kind: "full", lists,
               active: typeof parsed.active === "string" ? parsed.active : null };
    }
    return { ok: false, error: "Missing 'tickers' or 'watchlists' field." };
  }

  function validateAlertsImport(parsed) {
    if (!parsed || typeof parsed !== "object") {
      return { ok: false, error: "Not a JSON object." };
    }
    const arr = Array.isArray(parsed.alerts) ? parsed.alerts : null;
    if (!arr) return { ok: false, error: "Missing 'alerts' array." };
    if (arr.length > MAX_ALERTS) {
      return { ok: false, error: `Over ${MAX_ALERTS}-alert cap.` };
    }
    const cleaned = [];
    for (const a of arr) {
      if (!a || typeof a !== "object") continue;
      if (!_validTicker(a.ticker)) continue;
      if (typeof a.kind !== "string") continue;
      cleaned.push({
        id: a.id || ("imp_" + Math.random().toString(36).slice(2, 10)),
        ticker: a.ticker.toUpperCase().trim(),
        kind: a.kind,
        threshold: typeof a.threshold === "number" ? a.threshold : null,
        cooldownMins: typeof a.cooldownMins === "number" ? a.cooldownMins : 60,
        lastFired: typeof a.lastFired === "number" ? a.lastFired : null,
        active: a.active !== false,
        notes: typeof a.notes === "string" ? a.notes.slice(0, 200) : "",
      });
    }
    if (!cleaned.length) return { ok: false, error: "No valid alerts." };
    return { ok: true, alerts: cleaned };
  }

  function validatePortfolioImport(parsed) {
    if (!parsed || typeof parsed !== "object") {
      return { ok: false, error: "Not a JSON object." };
    }
    const arr = Array.isArray(parsed.holdings) ? parsed.holdings : null;
    if (!arr) return { ok: false, error: "Missing 'holdings' array." };
    if (arr.length > MAX_HOLDINGS) {
      return { ok: false, error: `Over ${MAX_HOLDINGS}-holding cap.` };
    }
    const cleaned = [];
    for (const h of arr) {
      if (!h || typeof h !== "object") continue;
      if (!_validTicker(h.ticker)) continue;
      if (!(typeof h.shares === "number" && h.shares > 0)) continue;
      if (!(typeof h.cost === "number" && h.cost >= 0)) continue;
      cleaned.push({
        id: h.id || ("imp_" + Math.random().toString(36).slice(2, 10)),
        ticker: h.ticker.toUpperCase().trim(),
        shares: h.shares,
        cost: h.cost,
        costCcy: (typeof h.costCcy === "string" ? h.costCcy : "USD").toUpperCase().slice(0, 3),
        date: typeof h.date === "string" ? h.date.slice(0, 10) : "",
        notes: typeof h.notes === "string" ? h.notes.slice(0, 200) : "",
      });
    }
    if (!cleaned.length) return { ok: false, error: "No valid holdings." };
    return { ok: true, holdings: cleaned };
  }

  function backupAll() {
    const bundle = {
      schema: "equityscope-backup",
      version: BACKUP_VERSION,
      exportedAt: new Date().toISOString(),
      keys: {},
    };
    for (const k of ES_KEYS) {
      const raw = localStorage.getItem(k);
      if (raw == null) continue;
      try {
        bundle.keys[k] = JSON.parse(raw);
      } catch (e) {
        bundle.keys[k] = raw;  // fall back to raw string
      }
    }
    return JSON.stringify(bundle, null, 2);
  }

  function restoreAll(parsed, opts) {
    opts = opts || {};
    if (!parsed || parsed.schema !== "equityscope-backup") {
      return { ok: false, error: "Not an EquityScope backup file." };
    }
    if (parsed.version > BACKUP_VERSION) {
      return { ok: false,
               error: `Backup is version ${parsed.version}; this app understands up to ${BACKUP_VERSION}.` };
    }
    if (!parsed.keys || typeof parsed.keys !== "object") {
      return { ok: false, error: "Missing 'keys' map." };
    }
    const restored = [];
    const skipped = [];
    for (const [k, v] of Object.entries(parsed.keys)) {
      if (!ES_KEYS.includes(k)) {
        skipped.push(k);
        continue;
      }
      try {
        const payload = typeof v === "string" ? v : JSON.stringify(v);
        localStorage.setItem(k, payload);
        restored.push(k);
      } catch (e) {
        skipped.push(k);
      }
    }
    return { ok: true, restored, skipped };
  }

  window.EsBackup = {
    TICKER_RE,
    ES_KEYS,
    BACKUP_VERSION,
    download,
    pickFile,
    validateWatchlistImport,
    validateAlertsImport,
    validatePortfolioImport,
    backupAll,
    restoreAll,
  };
})();
