// GDPR-aligned consent banner for localStorage usage.
//
// EquityScope uses NO cookies, NO server-side storage of user data, NO
// third-party trackers, NO analytics. Every piece of user state
// (watchlists, alerts, portfolio, prefs) lives in localStorage on this
// device only and never leaves the browser.
//
// Under GDPR / ePrivacy Directive guidance, localStorage that's strictly
// necessary for app function (e.g. "save my settings") falls under the
// "essential" category and does not require explicit opt-in. Even so we
// disclose it transparently and offer an opt-out which disables every
// localStorage feature.
//
// State stored in localStorage["equityscope.consent"]:
//   { version: 1, status: "accepted" | "declined", at: <iso> }

(function () {
  const KEY = "equityscope.consent";

  function load() {
    try { return JSON.parse(localStorage.getItem(KEY) || "null"); }
    catch (e) { return null; }
  }
  function save(state) {
    try { localStorage.setItem(KEY, JSON.stringify(state)); }
    catch (e) {/* user blocks storage entirely */}
  }

  const Consent = {
    status() { return load()?.status || null; },
    accept() {
      save({ version: 1, status: "accepted", at: new Date().toISOString() });
      hide();
      window.dispatchEvent(new CustomEvent("equityscope:consent", { detail: { status: "accepted" } }));
    },
    decline() {
      // Wipe any pre-existing storage to honour the decision.
      const keep = ["equityscope.consent"];
      for (let i = localStorage.length - 1; i >= 0; i--) {
        const k = localStorage.key(i);
        if (k && k.startsWith("equityscope.") && !keep.includes(k)) {
          localStorage.removeItem(k);
        }
      }
      save({ version: 1, status: "declined", at: new Date().toISOString() });
      hide();
      window.dispatchEvent(new CustomEvent("equityscope:consent", { detail: { status: "declined" } }));
    },
    isAccepted() { return load()?.status === "accepted"; },
    isDeclined() { return load()?.status === "declined"; },
    reset() { localStorage.removeItem(KEY); },
  };

  function show() {
    if (document.getElementById("consent-banner")) return;
    const root = document.createElement("div");
    root.id = "consent-banner";
    root.setAttribute("role", "dialog");
    root.setAttribute("aria-labelledby", "consent-title");
    root.setAttribute("aria-describedby", "consent-body");
    root.innerHTML = `
      <div class="consent-inner">
        <h2 id="consent-title">Local data storage notice</h2>
        <p id="consent-body">
          EquityScope stores your watchlists, portfolio, alerts, custom presets, and
          preferences in your browser's <strong>localStorage</strong> — on this device
          only. We use <strong>no cookies, no server-side storage of personal data,
          no analytics, no third-party trackers</strong>. Your data never leaves your
          browser.
          <a href="${(window.APP_BASE || "")}/privacy" class="consent-link">Read full privacy notice</a>.
        </p>
        <div class="consent-actions">
          <button class="btn-primary" id="consent-accept">Accept &amp; continue</button>
          <button class="btn-ghost" id="consent-decline">Decline (disable local features)</button>
        </div>
      </div>`;
    document.body.appendChild(root);
    root.querySelector("#consent-accept").addEventListener("click", () => Consent.accept());
    root.querySelector("#consent-decline").addEventListener("click", () => Consent.decline());
  }

  function hide() {
    const el = document.getElementById("consent-banner");
    if (el) el.remove();
  }

  document.addEventListener("DOMContentLoaded", () => {
    if (Consent.status()) return;  // already decided
    show();
  });

  window.Consent = Consent;
})();
