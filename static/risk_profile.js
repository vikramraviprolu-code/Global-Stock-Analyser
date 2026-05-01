// Risk profiler — 10-question questionnaire scored to a bucket.
// Persisted in localStorage["equityscope.riskProfile"]. Used to tune
// Recommendation thresholds + screener defaults.
//
// Schema:
//   { version: 1, answers: { q1..q10 }, score, bucket, completedAt }

(function () {
  const KEY = "equityscope.riskProfile";

  const QUESTIONS = [
    {
      id: "q1", text: "Investment time horizon",
      options: [
        { label: "< 1 year",  score: 1 },
        { label: "1–3 years", score: 4 },
        { label: "3–5 years", score: 7 },
        { label: "5+ years",  score: 10 },
      ],
    },
    {
      id: "q2", text: "Maximum drawdown you could stomach without panic-selling",
      options: [
        { label: "-5% or less",  score: 1 },
        { label: "-15%",         score: 4 },
        { label: "-30%",         score: 7 },
        { label: "-50% or more", score: 10 },
      ],
    },
    {
      id: "q3", text: "Primary investment goal",
      options: [
        { label: "Capital preservation", score: 1 },
        { label: "Income",               score: 4 },
        { label: "Long-term growth",     score: 7 },
        { label: "Aggressive growth",    score: 10 },
      ],
    },
    {
      id: "q4", text: "Investing experience",
      options: [
        { label: "None — first portfolio", score: 1 },
        { label: "Beginner (< 2 yrs)",     score: 4 },
        { label: "Intermediate (2–5 yrs)", score: 7 },
        { label: "Advanced (5+ yrs)",      score: 10 },
      ],
    },
    {
      id: "q5", text: "% of total net worth allocated to equities",
      options: [
        { label: "0–25%",   score: 10 },
        { label: "25–50%",  score: 7 },
        { label: "50–75%",  score: 4 },
        { label: "75–100%", score: 1 },
      ],
    },
    {
      id: "q6", text: "If your portfolio fell 20% in a month, you would…",
      options: [
        { label: "Sell everything",  score: 1 },
        { label: "Sell some + cut risk", score: 4 },
        { label: "Hold and wait",    score: 7 },
        { label: "Buy more",         score: 10 },
      ],
    },
    {
      id: "q7", text: "Income stability",
      options: [
        { label: "Highly variable / freelance", score: 1 },
        { label: "Mostly stable salary",        score: 4 },
        { label: "Very stable + benefits",      score: 7 },
        { label: "Diversified income streams",  score: 10 },
      ],
    },
    {
      id: "q8", text: "Liquid net worth tier",
      options: [
        { label: "< $50K",      score: 1 },
        { label: "$50K – $250K", score: 4 },
        { label: "$250K – $1M",  score: 7 },
        { label: "$1M+",         score: 10 },
      ],
    },
    {
      id: "q9", text: "Emergency fund (months of expenses covered)",
      options: [
        { label: "None / less than 1 month", score: 1 },
        { label: "1–3 months",               score: 4 },
        { label: "3–6 months",               score: 7 },
        { label: "6+ months",                score: 10 },
      ],
    },
    {
      id: "q10", text: "Maximum % of portfolio in a single stock",
      options: [
        { label: "≤ 5%",   score: 1 },
        { label: "5–10%",  score: 4 },
        { label: "10–25%", score: 7 },
        { label: "25%+",   score: 10 },
      ],
    },
  ];

  // Bucket from total score (max 100)
  const BUCKETS = [
    { min: 0,  max: 30, key: "conservative", label: "Conservative",
      desc: "Capital preservation focus. Equities should be a small slice; consider bonds + cash + dividend payers." },
    { min: 30, max: 50, key: "moderate", label: "Moderate",
      desc: "Balanced — growth + income mix. Limit single-stock concentration; use diversification." },
    { min: 50, max: 70, key: "balanced", label: "Balanced Growth",
      desc: "Comfortable with normal market drawdowns. Suitable for diversified equity exposure with measured risk." },
    { min: 70, max: 90, key: "growth", label: "Growth",
      desc: "Long-horizon growth tolerant. Can ride momentum names but should still cap single-stock weight." },
    { min: 90, max: 101, key: "aggressive", label: "Aggressive",
      desc: "High risk tolerance + experience. Comfortable with concentration + drawdown — but still avoid leverage you can't size." },
  ];

  function load() {
    try { return JSON.parse(localStorage.getItem(KEY) || "null"); }
    catch (e) { return null; }
  }
  function save(state) { localStorage.setItem(KEY, JSON.stringify(state)); }

  function bucketFor(score) {
    return BUCKETS.find((b) => score >= b.min && score < b.max) || BUCKETS[2];
  }

  function calculate(answers) {
    let score = 0;
    let answered = 0;
    QUESTIONS.forEach((q) => {
      const a = answers[q.id];
      if (a == null) return;
      const opt = q.options[a];
      if (opt) { score += opt.score; answered++; }
    });
    if (answered === 0) return { score: 0, bucket: null, answered: 0 };
    return { score, bucket: bucketFor(score), answered };
  }

  const RiskProfile = {
    QUESTIONS, BUCKETS,
    get() { return load(); },
    save(answers) {
      const calc = calculate(answers);
      const state = {
        version: 1, answers, score: calc.score,
        bucket: calc.bucket, completedAt: new Date().toISOString(),
      };
      save(state);
      return state;
    },
    clear() { localStorage.removeItem(KEY); },
    bucketFor,
    /** Quick-access: current bucket key, or null if not set. */
    currentBucket() {
      const p = load();
      return p?.bucket?.key || null;
    },
  };

  window.RiskProfile = RiskProfile;
})();
