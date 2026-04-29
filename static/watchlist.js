// EquityScope watchlist storage layer (no login, all localStorage).
//
// Schema (JSON in localStorage["equityscope.watchlists"]):
//   {
//     version: 1,
//     watchlists: { [name: string]: string[] /* tickers */ },
//     active: string  // currently selected list name
//   }

(function () {
  const KEY = "equityscope.watchlists";
  const DEFAULT_LISTS = ["My Watchlist", "Value Candidates", "Momentum Candidates"];

  function load() {
    try {
      const raw = localStorage.getItem(KEY);
      if (!raw) return seed();
      const parsed = JSON.parse(raw);
      if (!parsed || !parsed.watchlists) return seed();
      return parsed;
    } catch (e) {
      return seed();
    }
  }

  function save(state) {
    localStorage.setItem(KEY, JSON.stringify(state));
  }

  function seed() {
    const state = { version: 1, watchlists: {}, active: DEFAULT_LISTS[0] };
    DEFAULT_LISTS.forEach((n) => (state.watchlists[n] = []));
    save(state);
    return state;
  }

  const Watchlists = {
    all() {
      return load();
    },
    names() {
      return Object.keys(load().watchlists);
    },
    list(name) {
      const s = load();
      return [...(s.watchlists[name] || [])];
    },
    activeName() {
      return load().active;
    },
    setActive(name) {
      const s = load();
      if (s.watchlists[name]) {
        s.active = name;
        save(s);
      }
    },
    create(name) {
      const s = load();
      const trimmed = (name || "").trim();
      if (!trimmed || s.watchlists[trimmed]) return false;
      s.watchlists[trimmed] = [];
      s.active = trimmed;
      save(s);
      return true;
    },
    rename(oldName, newName) {
      const s = load();
      const trimmed = (newName || "").trim();
      if (!trimmed || !s.watchlists[oldName] || s.watchlists[trimmed]) return false;
      s.watchlists[trimmed] = s.watchlists[oldName];
      delete s.watchlists[oldName];
      if (s.active === oldName) s.active = trimmed;
      save(s);
      return true;
    },
    drop(name) {
      const s = load();
      if (!s.watchlists[name]) return false;
      if (Object.keys(s.watchlists).length <= 1) return false; // never delete last
      delete s.watchlists[name];
      if (s.active === name) s.active = Object.keys(s.watchlists)[0];
      save(s);
      return true;
    },
    add(ticker, listName) {
      const s = load();
      const t = (ticker || "").toUpperCase().trim();
      const list = listName || s.active;
      if (!t || !s.watchlists[list]) return false;
      if (!s.watchlists[list].includes(t)) {
        s.watchlists[list].push(t);
        save(s);
        return true;
      }
      return false;
    },
    remove(ticker, listName) {
      const s = load();
      const t = (ticker || "").toUpperCase().trim();
      const list = listName || s.active;
      if (!t || !s.watchlists[list]) return false;
      const idx = s.watchlists[list].indexOf(t);
      if (idx >= 0) {
        s.watchlists[list].splice(idx, 1);
        save(s);
        return true;
      }
      return false;
    },
    has(ticker, listName) {
      const s = load();
      const t = (ticker || "").toUpperCase().trim();
      const list = listName || s.active;
      return !!(s.watchlists[list] && s.watchlists[list].includes(t));
    },
    // Returns set of all tickers across every list — used by screener row to
    // decide if a row is "starred" anywhere.
    allTickers() {
      const s = load();
      const set = new Set();
      Object.values(s.watchlists).forEach((lst) => lst.forEach((t) => set.add(t)));
      return set;
    },
  };

  // Expose globally
  window.Watchlists = Watchlists;
})();
