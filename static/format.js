// Shared formatting helpers, exposed on window.Fmt. Eliminates ~500 lines
// of duplication across templates. Pure functions only — no DOM, no I/O.

(function () {
  const FLAGS = {
    "USA":"🇺🇸","India":"🇮🇳","UK":"🇬🇧","Germany":"🇩🇪","France":"🇫🇷",
    "Netherlands":"🇳🇱","Switzerland":"🇨🇭","Italy":"🇮🇹","Spain":"🇪🇸",
    "Sweden":"🇸🇪","Finland":"🇫🇮","Denmark":"🇩🇰","Norway":"🇳🇴",
    "Japan":"🇯🇵","Hong Kong":"🇭🇰","South Korea":"🇰🇷","Taiwan":"🇹🇼",
    "Singapore":"🇸🇬","Australia":"🇦🇺","China":"🇨🇳","Canada":"🇨🇦",
  };

  const FRESHNESS_LABEL = {
    "real-time": "live",
    "delayed": "delayed",
    "previous-close": "prev",
    "historical-only": "historical",
    "cached": "cached",
    "unavailable": "—",
    "mock": "MOCK",
  };

  const Fmt = {
    /** Number formatter, "—" for null. */
    n(value, decimals = 2) {
      return (value == null) ? "—" : Number(value).toFixed(decimals);
    },

    /** Percentage with + prefix on positives. */
    pct(value, decimals = 2) {
      if (value == null) return "—";
      const n = Number(value);
      return (n >= 0 ? "+" : "") + n.toFixed(decimals) + "%";
    },

    /** Market-cap human formatter (T / B / M). */
    mcap(value, sym = "$") {
      if (value == null) return "—";
      const v = Number(value);
      if (Math.abs(v) >= 1e12) return sym + (v / 1e12).toFixed(2) + "T";
      if (Math.abs(v) >= 1e9)  return sym + (v / 1e9).toFixed(2) + "B";
      if (Math.abs(v) >= 1e6)  return sym + (v / 1e6).toFixed(1) + "M";
      return sym + v.toFixed(0);
    },

    /** Volume formatter (M / K). */
    vol(value) {
      if (value == null) return "—";
      const v = Number(value);
      if (v >= 1e6) return (v / 1e6).toFixed(2) + "M";
      if (v >= 1e3) return (v / 1e3).toFixed(0) + "K";
      return Math.round(v).toString();
    },

    /** Money with currency code prefix + magnitude suffix. */
    money(value, ccy = "USD") {
      if (value == null) return "—";
      const v = Number(value);
      if (Math.abs(v) >= 1e9) return `${ccy} ${(v/1e9).toFixed(2)}B`;
      if (Math.abs(v) >= 1e6) return `${ccy} ${(v/1e6).toFixed(2)}M`;
      if (Math.abs(v) >= 1e3) return `${ccy} ${(v/1e3).toFixed(2)}K`;
      return `${ccy} ${v.toFixed(2)}`;
    },

    /** CSS class for sign — green / red / muted. */
    cls(value) {
      if (value == null) return "muted";
      return value > 0 ? "green" : value < 0 ? "red" : "muted";
    },

    /** Country flag emoji. */
    flag(country) {
      return FLAGS[country] || "🌐";
    },

    /** Source-quality badge HTML from a SourcedValue. */
    sourceBadge(sv) {
      if (!sv) return '<span class="src-badge unavailable">—</span>';
      const f = sv.freshness || "unavailable";
      const cssCls = "src-badge " + f.replace(/[^a-z]/g, "-");
      const verified = sv.verified_source_count || 0;
      const verifiedTxt = verified >= 2 ? ` • ✓ verified by ${verified} sources` : "";
      const tip = `${sv.source_name || "?"} • ${sv.confidence || "?"} confidence${verifiedTxt}`;
      const label = FRESHNESS_LABEL[f] || f;
      const verifiedDot = verified >= 2
        ? ' <span class="verified-dot" title="Verified by 2+ sources">✓</span>'
        : '';
      return `<span class="${cssCls}" title="${tip}">${label}${verifiedDot}</span>`;
    },

    /** Score bar HTML for a 0–100 score with optional risk-inverse class. */
    scoreBar(score, scoreKey = null) {
      if (!score) return "—";
      const pct = Math.max(0, Math.min(100, score.value));
      const labelCls = (score.label || "Mixed").toLowerCase();
      const visualCls = (scoreKey === "risk_score")
        ? (score.value > 65 ? "poor" : score.value > 40 ? "mixed" : "excellent")
        : labelCls;
      const reasons = (score.reasons || []).join("; ");
      return `<div class="score-bar ${visualCls}" title="${reasons}">
        <div class="score-fill" style="width:${pct}%"></div>
        <span class="score-text">${score.value.toFixed(0)} · ${score.label}</span>
      </div>`;
    },

    /** Tiny SVG sparkline from a closes array. Returns empty placeholder if too short. */
    sparkline(closes, w = 220, h = 50) {
      if (!closes || closes.length < 2) {
        return "<div class='spark-empty'>No history</div>";
      }
      const min = Math.min(...closes);
      const max = Math.max(...closes);
      const range = (max - min) || 1;
      const stepX = w / (closes.length - 1);
      const pts = closes.map((c, i) =>
        `${(i * stepX).toFixed(2)},${(h - ((c - min) / range) * h).toFixed(2)}`
      ).join(" ");
      const colour = closes[closes.length - 1] >= closes[0] ? "#3fb950" : "#f85149";
      const area = `M0,${h} L${pts.replace(/ /g, " L")} L${w},${h} Z`;
      return `<svg class="spark" viewBox="0 0 ${w} ${h}" width="${w}" height="${h}" preserveAspectRatio="none">
        <path d="${area}" fill="${colour}" fill-opacity="0.12"/>
        <polyline points="${pts}" fill="none" stroke="${colour}" stroke-width="1.5"/>
      </svg>`;
    },

    /** Relative time-ago formatter ("3h ago", "2d ago", date for older). */
    timeAgo(ts) {
      if (!ts) return "—";
      try {
        const d = new Date(ts);
        if (isNaN(d.getTime())) return ts;
        const diff = (Date.now() - d.getTime()) / 1000;
        if (diff < 60) return "just now";
        if (diff < 3600) return Math.floor(diff / 60) + "m ago";
        if (diff < 86400) return Math.floor(diff / 3600) + "h ago";
        if (diff < 604800) return Math.floor(diff / 86400) + "d ago";
        return d.toLocaleDateString();
      } catch (e) { return ts; }
    },

    /** ISO yyyy-mm-dd substring. */
    date(ts) {
      return ts ? String(ts).substring(0, 10) : "—";
    },
  };

  window.Fmt = Fmt;
})();
