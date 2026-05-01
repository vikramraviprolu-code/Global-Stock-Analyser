// EquityScope alerts — browser-local rule engine. No server state.
//
// Schema (JSON in localStorage["equityscope.alerts"]):
//   {
//     version: 1,
//     pollMinutes: 5,         // polling interval
//     desktopNotifications: false,
//     alerts: [
//       {
//         id, ticker, kind, threshold, status,
//         createdAt, triggeredAt?, dismissedAt?, notes?
//       }
//     ],
//     log: [
//       { ts, alertId, ticker, kind, threshold, value, message }
//     ]
//   }

(function () {
  const KEY = "equityscope.alerts";
  const LOG_CAP = 200;

  /** Available alert kinds + display labels + threshold semantics. */
  const KINDS = {
    price_above:    { label: "Price ≥",        threshold: "number", needs: ["price"], unit: "(currency)" },
    price_below:    { label: "Price ≤",        threshold: "number", needs: ["price"], unit: "(currency)" },
    pct_change_5d:  { label: "5D move ≥",      threshold: "number", needs: ["five_day_performance"], unit: "%" },
    rsi_above:      { label: "RSI ≥",          threshold: "number", needs: ["rsi14"], unit: "(0-100)" },
    rsi_below:      { label: "RSI ≤",          threshold: "number", needs: ["rsi14"], unit: "(0-100)" },
    cross_ma200_up: { label: "Price ≥ 200D MA",threshold: null,     needs: ["price","ma200"], unit: "" },
    cross_ma200_down:{label: "Price ≤ 200D MA",threshold: null,     needs: ["price","ma200"], unit: "" },
    cross_ma50_up:  { label: "Price ≥ 50D MA", threshold: null,     needs: ["price","ma50"], unit: "" },
    cross_ma50_down:{ label: "Price ≤ 50D MA", threshold: null,     needs: ["price","ma50"], unit: "" },
    near_52w_low:   { label: "Within X% of 52W low", threshold: "number", needs: ["percent_from_low"], unit: "%" },
    near_52w_high:  { label: "Within X% of 52W high",threshold: "number", needs: ["price","fifty_two_week_high"], unit: "%" },
  };

  function load() {
    try {
      const raw = localStorage.getItem(KEY);
      if (!raw) return seed();
      const parsed = JSON.parse(raw);
      if (!parsed || !Array.isArray(parsed.alerts)) return seed();
      return parsed;
    } catch (e) { return seed(); }
  }

  function save(state) {
    // Cap log size to avoid runaway storage
    if (Array.isArray(state.log) && state.log.length > LOG_CAP) {
      state.log = state.log.slice(-LOG_CAP);
    }
    localStorage.setItem(KEY, JSON.stringify(state));
  }

  function seed() {
    const state = {
      version: 1, pollMinutes: 5, desktopNotifications: false,
      alerts: [], log: [],
    };
    save(state);
    return state;
  }

  function uuid() {
    if (window.crypto && crypto.randomUUID) return crypto.randomUUID();
    return Date.now().toString(36) + Math.random().toString(36).slice(2, 10);
  }

  // ---------- evaluator ----------

  /** Returns { triggered, value, message } given alert + current metric dict. */
  function evaluate(alert, m) {
    if (!m) return { triggered: false };
    const price = m.price?.value;
    const rsi = m.rsi14?.value;
    const ma50 = m.ma50?.value;
    const ma200 = m.ma200?.value;
    const ccy = m.security?.currency || "";
    let value, message;
    switch (alert.kind) {
      case "price_above":
        if (price == null) return { triggered: false };
        value = price;
        return {
          triggered: price >= alert.threshold,
          value,
          message: `${alert.ticker} ${ccy} ${price.toFixed(2)} ≥ ${alert.threshold}`,
        };
      case "price_below":
        if (price == null) return { triggered: false };
        value = price;
        return {
          triggered: price <= alert.threshold,
          value,
          message: `${alert.ticker} ${ccy} ${price.toFixed(2)} ≤ ${alert.threshold}`,
        };
      case "pct_change_5d":
        const p5 = m.five_day_performance?.value;
        if (p5 == null) return { triggered: false };
        return {
          triggered: Math.abs(p5) >= alert.threshold,
          value: p5,
          message: `${alert.ticker} 5D move ${p5.toFixed(2)}% (≥ ${alert.threshold}%)`,
        };
      case "rsi_above":
        if (rsi == null) return { triggered: false };
        return {
          triggered: rsi >= alert.threshold,
          value: rsi,
          message: `${alert.ticker} RSI ${rsi.toFixed(1)} ≥ ${alert.threshold}`,
        };
      case "rsi_below":
        if (rsi == null) return { triggered: false };
        return {
          triggered: rsi <= alert.threshold,
          value: rsi,
          message: `${alert.ticker} RSI ${rsi.toFixed(1)} ≤ ${alert.threshold}`,
        };
      case "cross_ma200_up":
        if (price == null || ma200 == null) return { triggered: false };
        return {
          triggered: price >= ma200,
          value: price,
          message: `${alert.ticker} price ${price.toFixed(2)} ≥ 200D MA ${ma200.toFixed(2)}`,
        };
      case "cross_ma200_down":
        if (price == null || ma200 == null) return { triggered: false };
        return {
          triggered: price <= ma200,
          value: price,
          message: `${alert.ticker} price ${price.toFixed(2)} ≤ 200D MA ${ma200.toFixed(2)}`,
        };
      case "cross_ma50_up":
        if (price == null || ma50 == null) return { triggered: false };
        return {
          triggered: price >= ma50,
          value: price,
          message: `${alert.ticker} price ${price.toFixed(2)} ≥ 50D MA ${ma50.toFixed(2)}`,
        };
      case "cross_ma50_down":
        if (price == null || ma50 == null) return { triggered: false };
        return {
          triggered: price <= ma50,
          value: price,
          message: `${alert.ticker} price ${price.toFixed(2)} ≤ 50D MA ${ma50.toFixed(2)}`,
        };
      case "near_52w_low":
        const pctLow = m.percent_from_low?.value;
        if (pctLow == null) return { triggered: false };
        return {
          triggered: pctLow <= alert.threshold,
          value: pctLow,
          message: `${alert.ticker} ${pctLow.toFixed(1)}% above 52W low (≤ ${alert.threshold}%)`,
        };
      case "near_52w_high":
        const high = m.fifty_two_week_high?.value;
        if (price == null || high == null || high <= 0) return { triggered: false };
        const dist = (high - price) / high * 100;
        return {
          triggered: dist <= alert.threshold,
          value: dist,
          message: `${alert.ticker} ${dist.toFixed(1)}% below 52W high (≤ ${alert.threshold}%)`,
        };
    }
    return { triggered: false };
  }

  // ---------- API ----------

  const Alerts = {
    KINDS,
    all() { return load(); },
    list() { return [...load().alerts]; },
    log() { return [...(load().log || [])].reverse(); }, // newest first
    pollMinutes() { return load().pollMinutes || 5; },
    setPollMinutes(n) {
      const s = load();
      s.pollMinutes = Math.max(1, Math.min(60, parseInt(n) || 5));
      save(s);
    },
    desktopEnabled() { return !!load().desktopNotifications; },
    setDesktopEnabled(on) {
      const s = load();
      s.desktopNotifications = !!on;
      save(s);
    },

    add({ ticker, kind, threshold, notes }) {
      if (!ticker || !KINDS[kind]) return null;
      const t = ticker.toUpperCase().trim();
      const def = KINDS[kind];
      let th = null;
      if (def.threshold === "number") {
        th = parseFloat(threshold);
        if (!isFinite(th)) return null;
      }
      const s = load();
      const a = {
        id: uuid(),
        ticker: t,
        kind,
        threshold: th,
        status: "active",
        createdAt: new Date().toISOString(),
        notes: (notes || "").substring(0, 200),
      };
      s.alerts.push(a);
      save(s);
      return a;
    },

    update(id, fields) {
      const s = load();
      const idx = s.alerts.findIndex((a) => a.id === id);
      if (idx < 0) return false;
      Object.assign(s.alerts[idx], fields);
      save(s);
      return true;
    },

    remove(id) {
      const s = load();
      const before = s.alerts.length;
      s.alerts = s.alerts.filter((a) => a.id !== id);
      save(s);
      return s.alerts.length < before;
    },

    snooze(id, minutes = 60) {
      return Alerts.update(id, {
        status: "snoozed",
        snoozedUntil: new Date(Date.now() + minutes * 60_000).toISOString(),
      });
    },

    dismiss(id) {
      return Alerts.update(id, { status: "dismissed", dismissedAt: new Date().toISOString() });
    },

    reactivate(id) {
      return Alerts.update(id, {
        status: "active",
        triggeredAt: null,
        snoozedUntil: null,
        dismissedAt: null,
      });
    },

    /** Distinct tickers across ACTIVE alerts (for batch /api/metrics fetch). */
    activeTickers() {
      const set = new Set();
      const now = Date.now();
      load().alerts.forEach((a) => {
        if (a.status === "dismissed") return;
        if (a.status === "snoozed" && a.snoozedUntil && new Date(a.snoozedUntil).getTime() > now) return;
        set.add(a.ticker);
      });
      return [...set];
    },

    /**
     * Evaluate all active alerts against a metricsByTicker map.
     * Marks triggered alerts, appends log entries, and returns the list of
     * fresh fires (so the caller can show toasts / OS notifications).
     */
    evaluateAll(metricsByTicker) {
      const s = load();
      const now = Date.now();
      const fires = [];
      s.alerts.forEach((a) => {
        if (a.status === "dismissed") return;
        if (a.status === "snoozed" && a.snoozedUntil && new Date(a.snoozedUntil).getTime() > now) return;
        if (a.status === "triggered") return;  // already fired; user must reactivate
        const m = metricsByTicker[a.ticker];
        const r = evaluate(a, m);
        if (r.triggered) {
          a.status = "triggered";
          a.triggeredAt = new Date().toISOString();
          a.lastValue = r.value;
          fires.push({ alert: a, message: r.message, value: r.value });
          s.log = s.log || [];
          s.log.push({
            ts: a.triggeredAt, alertId: a.id, ticker: a.ticker,
            kind: a.kind, threshold: a.threshold, value: r.value, message: r.message,
          });
        }
      });
      if (fires.length) save(s);
      return fires;
    },

    /** Fire OS notification + in-app toast for an alert hit. */
    notifyFire(fire) {
      try {
        if (window.UI && UI.toast) {
          UI.toast(`🔔 ${fire.message}`, { type: "warning", duration: 6000 });
        }
        if (Alerts.desktopEnabled() && "Notification" in window
            && Notification.permission === "granted") {
          new Notification("EquityScope alert", {
            body: fire.message,
            tag: fire.alert.id,
          });
        }
      } catch (e) {/* ignore */}
    },

    requestDesktopPermission() {
      if (!("Notification" in window)) return Promise.resolve("unsupported");
      if (Notification.permission === "granted") return Promise.resolve("granted");
      if (Notification.permission === "denied") return Promise.resolve("denied");
      return Notification.requestPermission();
    },
  };

  // ---------- background poller ----------
  // Runs in any page that loads alerts.js (i.e. all pages — see _nav include).
  // Pauses while the document is hidden to avoid wasted requests.

  let pollTimer = null;
  async function pollOnce() {
    if (document.hidden) return;
    const tickers = Alerts.activeTickers();
    if (!tickers.length) return;
    try {
      const APP_BASE = window.APP_BASE_FOR_ALERTS || "";
      // Chunk 12 per batch
      const metricsByTicker = {};
      for (let i = 0; i < tickers.length; i += 12) {
        const chunk = tickers.slice(i, i + 12);
        const f = window.fetchWithRetry || window.fetch;
        const r = await f(APP_BASE + "/api/metrics", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ tickers: chunk }),
        });
        const d = await r.json();
        if (d.metrics) d.metrics.forEach((m) => (metricsByTicker[m.security.ticker] = m));
      }
      const fires = Alerts.evaluateAll(metricsByTicker);
      fires.forEach((f) => Alerts.notifyFire(f));
      // Notify open Alerts page (if any) so it can re-render without reload
      if (fires.length && window.dispatchEvent) {
        window.dispatchEvent(new CustomEvent("equityscope:alerts-fired", { detail: { fires } }));
      }
    } catch (e) {/* swallow — poll runs in background */}
  }

  function startPolling() {
    if (pollTimer) return;
    const minutes = Alerts.pollMinutes();
    pollOnce();  // first run on tab focus
    pollTimer = setInterval(pollOnce, minutes * 60_000);
  }

  // Visibility-aware: re-arm when tab becomes visible
  document.addEventListener("visibilitychange", () => {
    if (!document.hidden) pollOnce();
  });

  // Auto-start once DOM is ready (so APP_BASE injected by templates is set)
  document.addEventListener("DOMContentLoaded", () => {
    if (typeof window.APP_BASE !== "undefined" && window.APP_BASE_FOR_ALERTS == null) {
      window.APP_BASE_FOR_ALERTS = window.APP_BASE;
    }
    startPolling();
  });

  Alerts.pollOnce = pollOnce;
  Alerts.startPolling = startPolling;
  Alerts._evaluate = evaluate;  // exposed for tests

  window.Alerts = Alerts;
})();
