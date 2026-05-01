// EquityScope education drawer — slide-out explainer for every metric / score
// / chart concept the app surfaces. Content is hand-curated; no LLM calls.
//
// Usage:
//   <button data-explain="rsi14" aria-label="What is RSI?">?</button>
//   Or call Explainer.open("rsi14") programmatically.
//
// Auto-attach: any element with data-explain="<key>" gets click-to-open
// behaviour wired on DOMContentLoaded.

(function () {
  // ---------- content registry ------------------------------------------

  const CONTENT = {
    // ---- price & market metrics ----
    price: {
      title: "Price",
      definition: "Last available trade or close for the security in its local currency.",
      formula: "Reported as the latest available bar's close. We pull from Stooq + yfinance and cross-validate when both succeed.",
      interpretation: [
        "Free-source data is end-of-day or delayed — not for execution decisions.",
        "Source-quality badge tells you the freshness (live / delayed / cached / historical).",
      ],
      caveats: ["Verify against a broker before placing orders."],
      learn_more: "https://www.investopedia.com/terms/c/closingprice.asp",
    },
    market_cap: {
      title: "Market Capitalization",
      definition: "Total dollar value of all outstanding shares — a quick measure of company size.",
      formula: "Market cap = share price × shares outstanding",
      interpretation: [
        "≥ $200B = mega-cap (Apple, Microsoft)",
        "$10B – $200B = large-cap",
        "$2B – $10B = mid-cap",
        "< $2B = small-cap (more risk + more upside)",
      ],
      caveats: ["Excludes preferred shares + debt. Enterprise value (EV) is a more complete size proxy."],
      learn_more: "https://www.investopedia.com/terms/m/marketcapitalization.asp",
    },
    market_cap_usd: {
      title: "Market Cap (USD-normalized)",
      definition: "Market cap converted to USD using yfinance FX rates so global stocks can be compared on equal footing.",
      formula: "Market cap (local) × FX(local → USD)",
      interpretation: ["Used by all regional filters so a $2B-equivalent threshold applies the same way globally."],
      caveats: ["FX rates are 6-hour cached and can drift intraday."],
    },
    trailing_pe: {
      title: "Trailing P/E (Price / Earnings)",
      definition: "Stock price divided by trailing-12-month earnings per share. Tells you how many years of current earnings the price represents.",
      formula: "Trailing P/E = price / TTM EPS",
      interpretation: [
        "≤ 10 = potential value (or distressed)",
        "10–20 = fair range for many sectors",
        "≥ 30 = priced for growth — investors expect earnings to rise sharply",
      ],
      caveats: [
        "Negative or zero earnings → P/E is meaningless or undefined.",
        "Sector matters: software typically commands higher multiples than utilities.",
        "Best compared against peer-group median (the Peer Matrix shows this).",
      ],
      learn_more: "https://www.investopedia.com/terms/p/price-earningsratio.asp",
    },
    forward_pe: {
      title: "Forward P/E",
      definition: "Stock price divided by *projected* next-12-month EPS — analyst-consensus driven.",
      interpretation: ["A forward P/E meaningfully below trailing P/E suggests analysts expect earnings to grow."],
      caveats: ["Forward EPS is a forecast; analyst optimism / pessimism can skew the number."],
    },
    price_to_book: {
      title: "Price / Book (P/B)",
      definition: "Price relative to net assets per share. Useful for asset-heavy sectors (banks, insurance, REITs).",
      formula: "P/B = price / book value per share",
      interpretation: [
        "P/B < 1 = trading below stated book value (deep value or distressed)",
        "P/B ≤ 5 is considered reasonable in our Quality score",
      ],
      caveats: ["Less meaningful for asset-light companies (software, advertising) where intangibles dominate."],
      learn_more: "https://www.investopedia.com/terms/p/price-to-bookratio.asp",
    },
    dividend_yield: {
      title: "Dividend Yield",
      definition: "Annual dividend per share as a percentage of price. Shows the income component of return.",
      formula: "Dividend yield = (annual dividend / price) × 100",
      interpretation: [
        "0% = no dividend (often growth companies)",
        "2-5% = typical for mature dividend-paying large caps",
        "≥ 6% = unusually high — verify dividend isn't about to be cut",
      ],
      caveats: ["A spiking yield often means the price has fallen sharply, not that the company raised the dividend."],
    },
    avg_daily_volume: {
      title: "Average Daily Volume",
      definition: "Mean number of shares traded per day over the last 20 sessions. Measures liquidity.",
      interpretation: [
        "≥ 1M = highly liquid",
        "< 250K = thin trading — bid/ask spreads widen, slippage rises",
      ],
      caveats: ["Free data may report unadjusted volume. Stocks halted for events show artificial spikes."],
    },
    fifty_two_week_high: {
      title: "52-Week High",
      definition: "Highest closing price over the trailing 252 trading days.",
      interpretation: ["Often acts as resistance — break-outs above can trigger momentum buying."],
    },
    fifty_two_week_low: {
      title: "52-Week Low",
      definition: "Lowest closing price over the trailing 252 trading days.",
      interpretation: ["Often acts as support — failure of the low signals trend invalidation."],
    },
    percent_from_low: {
      title: "% from 52-Week Low",
      definition: "How far above the trailing 252-day low the current price sits.",
      formula: "(price − 52W low) / 52W low × 100",
      interpretation: [
        "< 10% = near support — potential value entry",
        "> 50% = stock has rallied substantially off the low",
      ],
    },
    five_day_performance: {
      title: "5-Day Performance",
      definition: "Percent change in price over the last 5 trading sessions.",
      formula: "5D % = (price_today / price_5_days_ago − 1) × 100",
      interpretation: ["A simple short-term momentum gauge — not a trend signal on its own."],
    },

    // ---- technical indicators ----
    rsi14: {
      title: "RSI 14 (Relative Strength Index)",
      definition: "Momentum oscillator measuring speed + magnitude of recent price changes on a 0–100 scale.",
      formula: "RSI = 100 − (100 / (1 + RS)) where RS = average gain / average loss over 14 periods",
      interpretation: [
        "RSI > 70 → overbought (recent rally has been sharp)",
        "RSI < 30 → oversold (recent decline has been sharp)",
        "40–70 = healthy uptrend zone (our Momentum score awards +15 here)",
      ],
      caveats: [
        "RSI can stay overbought for weeks in strong trends — don't auto-sell at 70.",
        "Best paired with a trend filter (e.g. 200D MA) to avoid fighting the trend.",
      ],
      learn_more: "https://en.wikipedia.org/wiki/Relative_strength_index",
    },
    roc14: {
      title: "ROC 14 (Rate of Change, 14-day)",
      definition: "Percent change in price compared to 14 trading days ago. Pure momentum measure.",
      formula: "ROC = (price_today / price_14_days_ago − 1) × 100",
      interpretation: ["Positive → upward momentum. Cross from negative to positive often precedes trend reversal."],
    },
    roc21: {
      title: "ROC 21 (Rate of Change, 21-day)",
      definition: "Same as ROC 14 but over a 21-day (≈ 1 calendar month) window — slower, less noisy signal.",
      interpretation: ["Used together with ROC 14 to detect momentum confirmation across timeframes."],
    },
    ma20: {
      title: "20-Day Moving Average",
      definition: "Simple average of the last 20 closing prices. Short-term trend baseline.",
      formula: "20D MA = sum(last 20 closes) / 20",
      interpretation: [
        "Price above 20D MA → short-term uptrend intact",
        "Steep slope = strong trend; flat = consolidation",
      ],
    },
    ma50: {
      title: "50-Day Moving Average",
      definition: "Simple average of the last 50 closing prices. Medium-term trend baseline used by many institutional traders.",
      interpretation: ["Crossing above the 50D MA from below is a common bullish trigger; the inverse is bearish."],
    },
    ma200: {
      title: "200-Day Moving Average",
      definition: "Simple average of the last 200 closing prices. Long-term trend baseline — the institutional 'bull / bear' line.",
      interpretation: [
        "Price above 200D MA = long-term uptrend (our Momentum score awards +10).",
        "Price below 200D MA = long-term downtrend (our Risk score adds +25 penalty).",
      ],
      caveats: ["Lagging indicator — by definition the 200D MA reacts slowly to fresh moves."],
      learn_more: "https://www.investopedia.com/terms/s/sma.asp",
    },

    // ---- scores ----
    value_score: {
      title: "Value Score (0–100)",
      definition: "Aggregate score of value signals: low P/E, P/E below peer median, near 52W low, market cap threshold, dividend.",
      formula: "+20 P/E ≤ 10 · +15 P/E < peer median · +20 within 10% of 52W low · +10 mcap ≥ regional threshold · +10 dividend > 2% · −15 P/E unavailable.",
      interpretation: [
        "85+ = Excellent · 65+ = Good · 40+ = Mixed · 20+ = Weak · below = Poor",
      ],
      caveats: ["Value alone doesn't time entries. Pair with the Momentum score for stronger setups."],
    },
    momentum_score: {
      title: "Momentum Score (0–100)",
      definition: "Aggregate score of momentum signals across short, medium, and long timeframes.",
      formula: "+15 each: 5D positive · ROC 14D positive · ROC 21D positive · RSI 40-70. +10 each: above 20D / 50D / 200D MA. −15 RSI > 70 · −20 below 200D MA · −15 ROC 14D + 21D both negative.",
      interpretation: ["A high momentum + reasonable Risk score is the classic 'trend-following' setup."],
      caveats: ["Momentum can reverse violently — combine with technical trigger + invalidation level (Recommendation tab)."],
    },
    quality_score: {
      title: "Quality Score (0–100)",
      definition: "Lightweight quality proxy from publicly verifiable signals only — never fabricated from missing data.",
      formula: "+35 mega-cap (≥ $50B) · +20 large-cap (≥ $10B) · +20 dividend payer · +15 P/B ≤ 5 · +10 high liquidity · +10 defensive sector · +10 price + fundamentals both resolved.",
      caveats: ["No ROE / ROIC / debt metrics — those would require paid data. Treat as a starting filter, not a deep quality verdict."],
    },
    risk_score: {
      title: "Risk Score (0–100; higher = riskier)",
      definition: "Sum of risk-flag penalties.",
      formula: "+25 RSI > 70 · +25 below 200D MA · +15 low liquidity · +15 P/E unavailable · +10 small cap · +10 stale data · +10 within 5% of 52W high · +10 ROC 14D + 21D both negative.",
      interpretation: ["Note: opposite direction from Value/Momentum — a high Risk score is a warning, not a virtue."],
    },
    data_confidence_score: {
      title: "Data Confidence Score (0–100)",
      definition: "How complete + fresh + multi-source-verified the metrics are for this stock.",
      formula: "60% × coverage (8 key metrics) + 30% × freshness + 10% completeness bonus − 5 per mock-flagged metric.",
      interpretation: [
        "≥ 85 = High — stable inputs",
        "< 60 = Low — Recommendation forces 'Watch' regardless of other scores",
      ],
    },

    // ---- chart concepts ----
    candlestick: {
      title: "Candlestick Chart",
      definition: "Each bar shows open / high / low / close for a session. Body colour = direction (green up, red down). Wicks = extremes.",
      interpretation: [
        "Long lower wicks = buyers stepped in below — potential support",
        "Long upper wicks = sellers rejected the high — potential resistance",
      ],
      learn_more: "https://www.investopedia.com/trading/candlestick-charting-what-is-it/",
    },
    line_chart: {
      title: "Line Chart",
      definition: "Connects close prices only. Cleaner than candlesticks for spotting long-term trends or comparing tickers.",
    },
    volume_bars: {
      title: "Volume Bars",
      definition: "Number of shares traded per session. Confirms (or rejects) price moves.",
      interpretation: [
        "Big up day on heavy volume = institutional buying",
        "Big up day on thin volume = less conviction; risk of fade",
      ],
    },

    // ---- peer matrix ----
    peer_matrix: {
      title: "Peer Comparison Matrix",
      definition: "Table comparing the input stock to ~12 same-sector peers across 13 metrics, with peer median + rank.",
      interpretation: [
        "'Better' = stock outperforms peer median for that metric (or has lower P/E for valuation rows).",
        "Peer rank shows position out of total peers; lower is better when 'lower-is-better' for that metric.",
      ],
    },
    peer_median: {
      title: "Peer Median",
      definition: "Median value across same-sector peers. Used as a fairer comparison baseline than the mean (less skewed by outliers).",
    },

    // ---- scenario recommendation ----
    scenario_recommendation: {
      title: "Scenario-Based Recommendation",
      definition: "PRD Build Step 7 output: Base / Upside / Downside cases + Technical Trigger + Invalidation Level + Final Rating.",
      interpretation: [
        "Final rating logic: low data confidence → Watch. Strong momentum + reasonable value + acceptable risk → Buy. Weak momentum or high risk → Avoid.",
      ],
      caveats: ["Anchored on moving averages and 52W extremes when no real S/R can be derived. Not financial advice."],
    },
    technical_trigger: {
      title: "Technical Trigger",
      definition: "The condition that would confirm the bullish or bearish thesis — e.g. 'close above 50D MA with positive ROC'.",
    },
    invalidation_level: {
      title: "Invalidation Level",
      definition: "Price below which the thesis breaks. Anchored on 200D MA or 52W low.",
      interpretation: ["Treat as a soft stop: if price closes below this, the original setup is no longer valid."],
    },

    // ---- screener / filters ----
    screener_preset: {
      title: "Screener Preset",
      definition: "Pre-built filter combination (e.g. 'Value Near Lows', 'Momentum Leaders'). 6 PRD-required + 6 extras.",
      interpretation: ["Click any preset chip in the Screener sidebar to run it. Save your own custom filter combos via 'Save current filters'."],
    },
    regional_filter: {
      title: "Regional Filters",
      definition: "Per-country thresholds for price + volume + market cap, baked into every screen so cross-region comparisons stay sane.",
    },

    // ---- workspace concepts ----
    watchlist: {
      title: "Watchlist",
      definition: "Local list of tickers stored in this browser only — no login, no server sync.",
      interpretation: ["Add via the ⭐ button on any Screener row, the header on Stock Analysis, or the Watchlists page."],
    },
    portfolio: {
      title: "Portfolio",
      definition: "Local holdings tracker with cost basis + live P/L + multi-currency rollup. Stored in this browser only.",
      caveats: ["Single weighted-average cost per ticker — not a tax-lot-level system."],
    },
    alert: {
      title: "Alerts",
      definition: "Browser-local rule engine that polls /api/metrics every N minutes and fires toast + (opt-in) desktop notifications when conditions trigger.",
      caveats: ["Polling is best-effort while the browser tab is open. Not for time-critical decisions."],
    },

    // ---- news ----
    sentiment: {
      title: "Headline Sentiment",
      definition: "Bullish / Bearish / Neutral classification per headline.",
      formula: "Counts positive vs negative keyword hits in the title + summary. First wins.",
      caveats: ["Pure rule-based heuristic — NOT AI inference. Read the actual headlines for context. Sarcasm + nuance won't classify."],
    },
    topic_clustering: {
      title: "Topic Clustering",
      definition: "Headlines bucket into Earnings / Product / M&A / Regulation / Executive / Macro / General via keyword matching.",
      caveats: ["Same as sentiment — heuristic, not ML."],
    },

    // ---- data quality ----
    freshness: {
      title: "Source Freshness",
      definition: "How recent the data is. Categories: real-time / delayed / previous-close / cached / historical-only / unavailable / mock.",
      interpretation: [
        "live / delayed / prev / cached → green tier",
        "historical-only → yellow (data is days old)",
        "mock → red (synthetic fallback only fires when both Stooq + yfinance fail)",
      ],
    },
    source_quality: {
      title: "Source Quality Badge",
      definition: "Combines source name + freshness + confidence + verified-source-count into a single chip.",
    },
    mock_data: {
      title: "Mock Data",
      definition: "Synthetic fallback used when both live providers fail. ALWAYS clearly labelled 'MOCK' (red badge) and never silently mixed with live data.",
      caveats: ["Treat any MOCK badge as 'no real data available' — values are deterministic placeholders for UI continuity, not real prices."],
    },
    verified_source_count: {
      title: "Verified by N Sources",
      definition: "Count of providers that returned the same value within tolerance. ≥ 2 earns a green ✓ on the source badge.",
      interpretation: ["For prices: Stooq + yfinance fetched in parallel; if last closes agree within 2%, count = 2."],
    },
  };

  // ---------- drawer DOM ------------------------------------------------

  let drawer, backdrop, lastTrigger;

  function ensureDrawer() {
    if (drawer) return;
    backdrop = document.createElement("div");
    backdrop.className = "explainer-backdrop";
    backdrop.addEventListener("click", close);
    drawer = document.createElement("aside");
    drawer.className = "explainer-drawer";
    drawer.setAttribute("role", "dialog");
    drawer.setAttribute("aria-modal", "true");
    drawer.setAttribute("aria-labelledby", "explainer-title");
    drawer.tabIndex = -1;
    drawer.innerHTML = `
      <header>
        <h2 id="explainer-title"></h2>
        <button class="explainer-close" aria-label="Close explainer">✕</button>
      </header>
      <div class="explainer-body"></div>
    `;
    drawer.querySelector(".explainer-close").addEventListener("click", close);
    document.addEventListener("keydown", (e) => {
      if (e.key === "Escape" && drawer.classList.contains("open")) close();
    });
    document.body.appendChild(backdrop);
    document.body.appendChild(drawer);
  }

  function open(key, trigger) {
    ensureDrawer();
    const c = CONTENT[key];
    if (!c) {
      console.warn("Explainer: unknown topic", key);
      return;
    }
    lastTrigger = trigger || document.activeElement;
    drawer.querySelector("#explainer-title").textContent = c.title;
    const body = drawer.querySelector(".explainer-body");
    const sections = [];
    if (c.definition) {
      sections.push(`<div class="exp-section"><div class="exp-label">What it is</div><p>${c.definition}</p></div>`);
    }
    if (c.formula) {
      sections.push(`<div class="exp-section"><div class="exp-label">How it's computed</div><p class="exp-formula">${c.formula}</p></div>`);
    }
    if (c.interpretation && c.interpretation.length) {
      sections.push(`<div class="exp-section"><div class="exp-label">How to read it</div><ul>${c.interpretation.map((x) => `<li>${x}</li>`).join("")}</ul></div>`);
    }
    if (c.caveats && c.caveats.length) {
      sections.push(`<div class="exp-section exp-caveats"><div class="exp-label">⚠ Caveats</div><ul>${c.caveats.map((x) => `<li>${x}</li>`).join("")}</ul></div>`);
    }
    if (c.learn_more) {
      sections.push(`<div class="exp-section"><a href="${c.learn_more}" target="_blank" rel="noopener" class="exp-link">Read more →</a></div>`);
    }
    body.innerHTML = sections.join("");
    backdrop.classList.add("open");
    drawer.classList.add("open");
    drawer.focus();
  }

  function close() {
    if (!drawer || !drawer.classList.contains("open")) return;
    drawer.classList.remove("open");
    backdrop.classList.remove("open");
    if (lastTrigger && lastTrigger.focus) {
      lastTrigger.focus();
    }
  }

  function attachAll(scope = document) {
    scope.querySelectorAll("[data-explain]").forEach((el) => {
      if (el.dataset.explainWired) return;
      el.dataset.explainWired = "1";
      el.style.cursor = "help";
      const key = el.dataset.explain;
      el.addEventListener("click", (e) => {
        // If element is also a link / button with its own action, only open
        // the drawer when the user clicks an explain icon explicitly.
        if (el.matches(".explainer-icon") || !el.matches("a, button")) {
          e.preventDefault();
          e.stopPropagation();
          open(key, el);
        }
      });
    });
  }

  /** Append a "?" icon button next to a label that opens the drawer. */
  function iconButton(key, label) {
    return `<button type="button" class="explainer-icon" data-explain="${key}" aria-label="Learn about ${label || key}" tabindex="0">?</button>`;
  }

  document.addEventListener("DOMContentLoaded", () => attachAll(document));

  window.Explainer = { open, close, attachAll, iconButton, CONTENT };
})();
