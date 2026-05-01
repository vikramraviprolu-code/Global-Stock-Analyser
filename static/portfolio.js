// EquityScope portfolio storage layer (no login, all localStorage).
//
// Schema (JSON in localStorage["equityscope.portfolio"]):
//   {
//     version: 1,
//     baseCurrency: string,    // e.g. "USD"
//     holdings: [
//       {
//         id: string,           // crypto random uuid
//         ticker: string,
//         shares: number,
//         costPerShare: number, // in costCurrency
//         costCurrency: string, // ISO 4217 code
//         purchaseDate: string, // YYYY-MM-DD
//         notes: string,
//         createdAt: string,    // ISO timestamp
//       }
//     ]
//   }

(function () {
  const KEY = "equityscope.portfolio";
  const DEFAULT_BASE = "USD";

  function load() {
    try {
      const raw = localStorage.getItem(KEY);
      if (!raw) return seed();
      const parsed = JSON.parse(raw);
      if (!parsed || !Array.isArray(parsed.holdings)) return seed();
      return parsed;
    } catch (e) { return seed(); }
  }

  function save(state) {
    localStorage.setItem(KEY, JSON.stringify(state));
  }

  function seed() {
    const state = {
      version: 1,
      baseCurrency: DEFAULT_BASE,
      holdings: [],
    };
    save(state);
    return state;
  }

  function uuid() {
    if (window.crypto && crypto.randomUUID) return crypto.randomUUID();
    // Fallback (older browsers): timestamp + random
    return Date.now().toString(36) + Math.random().toString(36).slice(2, 10);
  }

  const Portfolio = {
    all() { return load(); },
    list() { return [...load().holdings]; },
    baseCurrency() { return load().baseCurrency || DEFAULT_BASE; },

    setBaseCurrency(ccy) {
      const s = load();
      s.baseCurrency = (ccy || DEFAULT_BASE).toUpperCase();
      save(s);
    },

    /** Add a holding. Required: ticker, shares, costPerShare, costCurrency. */
    add({ ticker, shares, costPerShare, costCurrency = "USD",
          purchaseDate = "", notes = "" }) {
      const s = load();
      const t = (ticker || "").toUpperCase().trim();
      const sh = parseFloat(shares);
      const cps = parseFloat(costPerShare);
      if (!t || !(sh > 0) || !(cps >= 0)) return null;
      const h = {
        id: uuid(),
        ticker: t,
        shares: sh,
        costPerShare: cps,
        costCurrency: (costCurrency || "USD").toUpperCase(),
        purchaseDate: purchaseDate || "",
        notes: (notes || "").substring(0, 200),
        createdAt: new Date().toISOString(),
      };
      s.holdings.push(h);
      save(s);
      return h;
    },

    update(id, fields) {
      const s = load();
      const idx = s.holdings.findIndex((h) => h.id === id);
      if (idx < 0) return false;
      const allowed = ["shares","costPerShare","costCurrency","purchaseDate","notes","ticker"];
      allowed.forEach((k) => {
        if (k in fields) {
          let v = fields[k];
          if (k === "shares" || k === "costPerShare") v = parseFloat(v);
          if (k === "ticker") v = String(v).toUpperCase().trim();
          if (k === "costCurrency") v = String(v).toUpperCase().trim();
          s.holdings[idx][k] = v;
        }
      });
      save(s);
      return true;
    },

    remove(id) {
      const s = load();
      const before = s.holdings.length;
      s.holdings = s.holdings.filter((h) => h.id !== id);
      save(s);
      return s.holdings.length < before;
    },

    clear() {
      save({ version: 1, baseCurrency: DEFAULT_BASE, holdings: [] });
    },

    /** Distinct tickers (for batch /api/metrics fetch). */
    tickers() {
      const set = new Set();
      load().holdings.forEach((h) => set.add(h.ticker));
      return [...set];
    },

    /** Distinct cost currencies + holding-local currencies (need FX rates). */
    currencies(extra = []) {
      const set = new Set([this.baseCurrency()]);
      load().holdings.forEach((h) => set.add(h.costCurrency));
      extra.forEach((c) => c && set.add(c));
      return [...set];
    },

    /**
     * Compute valuation rollup. Caller passes:
     *   metricsByTicker — { TICKER: stockMetrics }
     *   fxByPair        — { "INR_USD": 0.012, ... }  (from→to)
     * Returns array of holdings + per-row + grand totals in baseCurrency.
     */
    valuate(metricsByTicker, fxByPair) {
      const base = this.baseCurrency();
      const fx = (from, to) => {
        if (!from || !to) return null;
        if (from === to) return 1;
        const k = `${from}_${to}`;
        return fxByPair[k] != null ? fxByPair[k] : null;
      };

      let totalCostBase = 0, totalValueBase = 0;
      const rows = this.list().map((h) => {
        const m = metricsByTicker[h.ticker] || null;
        const livePrice = m?.price?.value ?? null;
        const liveCcy = m?.security?.currency || h.costCurrency;
        const sector = m?.security?.sector || null;
        const country = m?.security?.country || null;
        const valueLocal = livePrice != null ? h.shares * livePrice : null;
        const costLocal = h.shares * h.costPerShare;
        // FX both sides into base
        const fxValue = fx(liveCcy, base);
        const fxCost  = fx(h.costCurrency, base);
        const valueBase = (valueLocal != null && fxValue != null) ? valueLocal * fxValue : null;
        const costBase  = (fxCost != null) ? costLocal * fxCost : null;
        const plLocal = (valueLocal != null && liveCcy === h.costCurrency)
          ? valueLocal - costLocal : null;
        const plPct = (plLocal != null && costLocal > 0) ? (plLocal / costLocal) * 100 : null;
        const plBase = (valueBase != null && costBase != null) ? valueBase - costBase : null;
        const plBasePct = (plBase != null && costBase > 0) ? (plBase / costBase) * 100 : null;
        if (valueBase != null) totalValueBase += valueBase;
        if (costBase != null) totalCostBase += costBase;
        return {
          holding: h, metrics: m,
          livePrice, liveCcy, sector, country,
          valueLocal, costLocal, plLocal, plPct,
          valueBase, costBase, plBase, plBasePct,
        };
      });
      // Weights
      rows.forEach((r) => {
        r.weightPct = (totalValueBase > 0 && r.valueBase != null)
          ? (r.valueBase / totalValueBase) * 100 : null;
      });
      const totalPlBase = totalValueBase - totalCostBase;
      const totalPlBasePct = totalCostBase > 0 ? (totalPlBase / totalCostBase) * 100 : null;
      return {
        rows,
        baseCurrency: base,
        totalValueBase,
        totalCostBase,
        totalPlBase,
        totalPlBasePct,
      };
    },
  };

  window.Portfolio = Portfolio;
})();
