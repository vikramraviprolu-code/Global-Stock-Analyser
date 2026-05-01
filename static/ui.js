// EquityScope shared UI helpers — loading skeletons, empty states, and a
// retry-aware fetch wrapper. All factories return HTML strings so callers can
// inject directly via `el.innerHTML = UI.tableSkeleton()`.

(function () {
  // ---------- skeleton factories ----------

  /** Fixed-shimmer table skeleton. Carries aria-busy=true. */
  function tableSkeleton(rows = 6, cols = 8) {
    const cells = [];
    for (let r = 0; r < rows; r++) {
      const row = [];
      for (let c = 0; c < cols; c++) {
        const w = 40 + Math.floor(Math.random() * 60);
        row.push(`<td><span class="sk-bar" style="width:${w}%"></span></td>`);
      }
      cells.push(`<tr>${row.join("")}</tr>`);
    }
    return `<div class="sk-table-wrap" aria-busy="true" aria-live="polite">
      <table class="results-table sk-table"><tbody>${cells.join("")}</tbody></table>
    </div>`;
  }

  /** Grid of stat cards (e.g. for Snapshot tab). */
  function statGridSkeleton(count = 8) {
    const cells = [];
    for (let i = 0; i < count; i++) {
      cells.push(`<div class="metric sk-stat" aria-busy="true">
        <span class="sk-bar" style="width:50%; height:10px;"></span>
        <span class="sk-bar" style="width:80%; height:18px; margin-top:6px;"></span>
      </div>`);
    }
    return `<div class="grid sk-stat-grid">${cells.join("")}</div>`;
  }

  /** Multi-line paragraph block. */
  function paragraphSkeleton(lines = 3) {
    const out = [];
    for (let i = 0; i < lines; i++) {
      out.push(`<span class="sk-bar" style="width:${85 - i * 8}%"></span>`);
    }
    return `<div class="sk-paragraph" aria-busy="true">${out.join("")}</div>`;
  }

  /** Card grid (used in Watchlists / Compare / Screener cards). */
  function cardGridSkeleton(count = 6) {
    const cards = [];
    for (let i = 0; i < count; i++) {
      cards.push(`<div class="result-card sk-card" aria-busy="true">
        <span class="sk-bar" style="width:40%"></span>
        <span class="sk-bar" style="width:75%; margin-top:6px;"></span>
        <span class="sk-bar" style="width:55%; margin-top:6px;"></span>
        <span class="sk-bar sk-spark" style="margin-top:10px;"></span>
        <div class="sk-grid">
          <span class="sk-bar"></span><span class="sk-bar"></span>
          <span class="sk-bar"></span><span class="sk-bar"></span>
        </div>
      </div>`);
    }
    return `<div class="results-cards">${cards.join("")}</div>`;
  }

  // ---------- empty-state factory ----------

  /**
   * @param {Object} opts
   * @param {string} opts.title
   * @param {string} opts.description
   * @param {string} [opts.icon]      e.g. "🔍" or "📭"
   * @param {string} [opts.linkText]  Optional CTA text
   * @param {string} [opts.linkHref]  Optional CTA href
   */
  function emptyState({ title, description, icon = "📭", linkText, linkHref } = {}) {
    const cta = (linkText && linkHref)
      ? `<a class="empty-state-link" href="${linkHref}">${linkText}</a>`
      : "";
    return `<div class="empty-state" role="status">
      <div class="empty-state-icon" aria-hidden="true">${icon}</div>
      <div class="empty-state-title">${title || ""}</div>
      ${description ? `<div class="empty-state-desc">${description}</div>` : ""}
      ${cta}
    </div>`;
  }

  // ---------- fetchWithRetry ----------

  /**
   * Wraps fetch with timeout + retry on transient failures (408, 425, 429,
   * 500, 502, 503, 504, network errors). Deterministic 4xx (400/401/403/404
   * /422) are NOT retried.
   *
   * Default timeout 12s; pass {timeout: 30000} for AI/news endpoints per PRD.
   */
  async function fetchWithRetry(url, options = {}) {
    const {
      retries = 3,
      timeout = 12000,
      backoffMs = 250,
      retryStatuses = [408, 425, 429, 500, 502, 503, 504],
      ...fetchOpts
    } = options;

    let lastErr;
    for (let attempt = 0; attempt <= retries; attempt++) {
      const ctrl = new AbortController();
      const timer = setTimeout(() => ctrl.abort(), timeout);
      try {
        const res = await fetch(url, { ...fetchOpts, signal: ctrl.signal });
        clearTimeout(timer);
        // Successful or non-retryable status — return immediately
        if (res.ok || !retryStatuses.includes(res.status)) {
          return res;
        }
        // Retryable status & attempts left → loop
        if (attempt === retries) return res;
      } catch (e) {
        clearTimeout(timer);
        lastErr = e;
        // Only retry network-level / abort errors; abort the loop on fatal others
        const isTransient = e.name === "AbortError"
          || e.name === "TypeError"  // fetch network failures
          || /network|failed|connection/i.test(e.message || "");
        if (!isTransient || attempt === retries) throw e;
      }
      // Exponential backoff: 250ms, 500ms, 1000ms by default
      await new Promise((r) => setTimeout(r, backoffMs * Math.pow(2, attempt)));
    }
    if (lastErr) throw lastErr;
    throw new Error("fetchWithRetry: unreachable");
  }

  // ---------- toast (lightweight) ----------

  function toast(msg, { type = "info", duration = 3500 } = {}) {
    let host = document.getElementById("toast-host");
    if (!host) {
      host = document.createElement("div");
      host.id = "toast-host";
      host.setAttribute("role", "status");
      host.setAttribute("aria-live", "polite");
      document.body.appendChild(host);
    }
    const el = document.createElement("div");
    el.className = `toast toast-${type}`;
    el.textContent = msg;
    host.appendChild(el);
    setTimeout(() => el.classList.add("toast-leaving"), duration);
    setTimeout(() => el.remove(), duration + 250);
  }

  // ---------- expose ----------

  window.UI = {
    tableSkeleton,
    statGridSkeleton,
    paragraphSkeleton,
    cardGridSkeleton,
    emptyState,
    toast,
  };
  window.fetchWithRetry = fetchWithRetry;
})();

// Mobile nav toggle wired globally (idempotent)
document.addEventListener("DOMContentLoaded", () => {
  const toggle = document.querySelector(".v2-mobile-toggle");
  const groups = document.querySelector(".v2-nav-groups");
  if (!toggle || !groups) return;
  toggle.addEventListener("click", () => {
    const open = groups.classList.toggle("open");
    toggle.setAttribute("aria-expanded", open ? "true" : "false");
  });
});
