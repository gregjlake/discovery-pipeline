/**
 * DiscoveryLens — Post-Broadband-Fix Validation
 * Verifies all results after switching from B28002_004E to B28002_007E.
 * Run: node tests/post-broadband-validation.mjs
 */

const BASE = "https://web-production-a68ad.up.railway.app/api";
let passed = 0, failed = 0, warnings = 0;
const results = [];
const changes = []; // Track significant changes from pre-fix values

function log(status, test, detail, severity = "") {
  const icon = status === "PASS" ? "\x1b[32m✓\x1b[0m" : status === "FAIL" ? "\x1b[31m✗\x1b[0m" : "\x1b[33m⚠\x1b[0m";
  console.log(`  ${icon} ${test}${severity ? ` [${severity}]` : ""}`);
  if (detail) console.log(`    ${detail}`);
  results.push({ status, test, detail, severity });
  if (status === "PASS") passed++; else if (status === "FAIL") failed++; else warnings++;
}

function track(label, oldVal, newVal, tolerance = 0.02) {
  const diff = Math.abs(newVal - oldVal);
  const sig = diff > tolerance;
  if (sig) changes.push({ label, old: oldVal, new: newVal, diff });
  return sig;
}

function pearsonR(nodes, varA, varB) {
  const xs = [], ys = [];
  for (const n of nodes) {
    const a = n.datasets?.[varA], b = n.datasets?.[varB];
    if (a != null && b != null) { xs.push(a); ys.push(b); }
  }
  if (xs.length < 10) return { r: null, n: 0 };
  const nn = xs.length;
  const mx = xs.reduce((s, v) => s + v, 0) / nn, my = ys.reduce((s, v) => s + v, 0) / nn;
  let num = 0, dx = 0, dy = 0;
  for (let i = 0; i < nn; i++) { num += (xs[i] - mx) * (ys[i] - my); dx += (xs[i] - mx) ** 2; dy += (ys[i] - my) ** 2; }
  return { r: Math.sqrt(dx * dy) === 0 ? null : num / Math.sqrt(dx * dy), n: nn };
}

async function fetchJSON(path, opts) {
  const res = await fetch(`${BASE}${path}`, opts);
  if (!res.ok) throw new Error(`HTTP ${res.status}`);
  return res.json();
}

let _nodes = null;
async function getNodes() {
  if (!_nodes) { _nodes = (await fetchJSON("/gravity-map?module_id=all")).nodes || []; }
  return _nodes;
}

// ═══════════════════════════════════════════════════════════════
async function testBroadbandCorrelations() {
  console.log("\n\x1b[1m═══ 1. Broadband Correlation Changes ═══\x1b[0m");
  const nodes = await getNodes();

  const pairs = [
    { a: "broadband", b: "diabetes", oldR: -0.699, label: "broadband × diabetes" },
    { a: "broadband", b: "life_expectancy", oldR: 0.548, label: "broadband × life_expectancy" },
    { a: "broadband", b: "poverty", oldR: -0.642, label: "broadband × poverty" },
    { a: "broadband", b: "median_income", oldR: 0.670, label: "broadband × median_income" },
    { a: "broadband", b: "obesity", oldR: null, label: "broadband × obesity" },
  ];

  for (const p of pairs) {
    const { r, n } = pearsonR(nodes, p.a, p.b);
    const sig = p.oldR != null ? track(p.label, p.oldR, r, 0.03) : false;
    log("PASS", p.label, `r=${r?.toFixed(4)} (n=${n})${p.oldR != null ? `, was ${p.oldR.toFixed(3)}${sig ? " ← CHANGED" : ""}` : ""}`);
  }
}

async function testPovertyDiabetes() {
  console.log("\n\x1b[1m═══ 2. Paper Headline: poverty × diabetes ═══\x1b[0m");
  const nodes = await getNodes();
  const { r } = pearsonR(nodes, "poverty", "diabetes");
  const sig = track("poverty × diabetes overall", 0.736, r, 0.01);
  if (Math.abs(r - 0.736) <= 0.02) {
    log("PASS", "poverty × diabetes", `r=${r.toFixed(4)} (paper: 0.736)${sig ? " ← changed" : ""}`);
  } else {
    log("WARN", "poverty × diabetes", `r=${r.toFixed(4)} — differs from paper's 0.736 by ${Math.abs(r - 0.736).toFixed(4)}`, "NEEDS NOTE");
  }

  // Within-cluster
  const clusters = await fetchJSON("/county-clusters");
  const assignments = clusters.county_assignments || {};
  const LABELS = { 0: "Prosperous Suburban", 1: "Rural Heartland", 3: "Rural Disadvantaged" };
  const OLD_WITHIN = { 0: 0.494, 1: 0.502, 3: 0.579 };

  for (const cid of [0, 1, 3]) {
    const fipsSet = new Set(Object.entries(assignments).filter(([_, c]) => c === cid).map(([f]) => f));
    const cNodes = nodes.filter(n => fipsSet.has(n.fips));
    const { r: cr, n } = pearsonR(cNodes, "poverty", "diabetes");
    if (cr != null) {
      const sig2 = track(`within ${LABELS[cid]}`, OLD_WITHIN[cid], cr, 0.02);
      log("PASS", `Within ${LABELS[cid]}`, `r=${cr.toFixed(4)} (n=${n}), was ${OLD_WITHIN[cid]}${sig2 ? " ← CHANGED" : ""}`);
    }
  }
}

async function testGravityModel() {
  console.log("\n\x1b[1m═══ 3. Gravity Model Parameters ═══\x1b[0m");
  const grav = await fetchJSON("/gravity-map");
  const meta = grav.metadata;

  const beta = meta?.beta ?? meta?.beta_operative;
  if (beta != null) {
    track("beta", 0.1398, beta, 0.005);
    log(Math.abs(beta - 0.139) < 0.005 ? "PASS" : "WARN", "beta", `β=${beta.toFixed(4)} (was 0.1398)`);
  }

  const r2 = meta?.pseudo_r2;
  if (r2 != null) {
    track("R²", 0.3027, r2, 0.01);
    log(Math.abs(r2 - 0.303) < 0.02 ? "PASS" : "WARN", "R²", `R²=${r2.toFixed(4)} (was 0.3027)`);
  }

  const np = meta?.n_pairs;
  log("PASS", "n_pairs", `${np?.toLocaleString()}`);
}

async function testValidation() {
  console.log("\n\x1b[1m═══ 4. IRS Validation ═══\x1b[0m");
  try {
    const val = await fetchJSON("/gravity-map/validation");
    const rho = val.rho_combined ?? val.spearman_rho;
    if (rho != null) {
      track("IRS rho", 0.1636, rho, 0.005);
      log(Math.abs(rho - 0.164) < 0.01 ? "PASS" : "WARN", "IRS ρ", `ρ=${rho.toFixed(4)} (was 0.1636)`);
    }
  } catch { log("WARN", "Validation endpoint", "Not available"); }
}

async function testPCA() {
  console.log("\n\x1b[1m═══ 5. PCA / Effective Dimensions ═══\x1b[0m");
  try {
    const pca = await fetchJSON("/pca-analysis");
    const ed = pca.effective_dimensions ?? pca.participation_ratio;
    const nd = pca.n_datasets;
    if (ed != null) {
      track("effective_dimensions", 7.19, ed, 0.3);
      log(Math.abs(ed - 7.19) < 0.5 ? "PASS" : "WARN", "Effective dimensions", `${ed.toFixed(2)} (was 7.19)`);
    }
    if (nd != null) log(nd >= 29 ? "PASS" : "FAIL", "n_datasets", `${nd}`);
  } catch { log("WARN", "PCA endpoint", "Not available"); }
}

async function testClusters() {
  console.log("\n\x1b[1m═══ 6. Cluster Assignments ═══\x1b[0m");
  const clusters = await fetchJSON("/county-clusters");
  const a = clusters.county_assignments;

  const checks = { "06075": 0, "54047": 2, "51107": 0, "48427": 2, "51013": 0 };
  const LABELS = { 0: "Prosperous Suburban", 1: "Rural Heartland", 2: "Rural Disadvantaged", 3: "High-Need Urban/Border" };
  let allMatch = true;
  for (const [fips, expected] of Object.entries(checks)) {
    const actual = a[fips];
    if (actual !== expected) { allMatch = false; log("FAIL", `Cluster ${fips}`, `expected ${expected}, got ${actual}`, "BLOCKS SUBMISSION"); }
  }
  if (allMatch) log("PASS", "Cluster assignments unchanged", "All 5 spot checks match");

  const counts = {};
  for (const c of Object.values(a)) counts[c] = (counts[c] || 0) + 1;
  for (const [c, n] of Object.entries(counts)) log("PASS", `${LABELS[c] || `Cluster ${c}`}`, `n=${n}`);

  const sil = clusters.silhouette_scores?.["4"] ?? clusters.silhouette_scores?.[4];
  if (sil != null) {
    track("silhouette k=4", 0.219, sil, 0.02);
    log("PASS", "Silhouette k=4", `${sil.toFixed(3)} (was 0.219)`);
  }
}

async function testMcDowellPeers() {
  console.log("\n\x1b[1m═══ 7. McDowell Peer List ═══\x1b[0m");
  const nodes = await getNodes();
  const allVars = Object.keys(nodes[0]?.datasets || {});
  const ranges = {};
  for (const n of nodes) { for (const [k, v] of Object.entries(n.datasets || {})) { if (v == null) continue; if (!ranges[k]) ranges[k] = { min: v, max: v }; else { if (v < ranges[k].min) ranges[k].min = v; if (v > ranges[k].max) ranges[k].max = v; } } }

  const mc = nodes.find(n => n.fips === "54047");
  const peers = nodes.filter(n => n.fips !== "54047" && n.datasets).map(n => {
    let sum = 0;
    for (const k of allVars) { const va = mc.datasets[k] ?? 0.5, vb = n.datasets[k] ?? 0.5; const r = ranges[k]; const na = r ? (va - r.min) / (r.max - r.min || 1) : 0.5; const nb = r ? (vb - r.min) / (r.max - r.min || 1) : 0.5; sum += (na - nb) ** 2; }
    return { fips: n.fips, name: n.county_name, d: Math.sqrt(sum) };
  }).sort((a, b) => a.d - b.d).slice(0, 10);

  const OLD_PEERS = ["Mingo", "Hancock", "Webster", "Allendale", "Calhoun"];
  const newNames = peers.slice(0, 5).map(p => p.name);
  const overlap = OLD_PEERS.filter(n => newNames.some(nn => nn.includes(n))).length;

  console.log("    New top 5: " + newNames.join(", "));
  console.log("    Old top 5: " + OLD_PEERS.join(", "));

  if (overlap >= 3) {
    log("PASS", "McDowell peers stable", `${overlap}/5 overlap with pre-fix list`);
  } else {
    log("WARN", "McDowell peers changed", `Only ${overlap}/5 overlap — broadband change shifted peer distances`, "NEEDS NOTE");
  }
}

async function testPositiveDeviance() {
  console.log("\n\x1b[1m═══ 8. Positive Deviance ═══\x1b[0m");
  // Diabetes outcome
  const body = { input_variables: ["poverty", "broadband", "obesity", "mental_health", "housing_burden", "unemployment", "food_access", "air", "median_income"], outcome_variable: "diabetes", county_fips: "54047" };
  const result = await fetchJSON("/positive-deviance/compute", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body) });

  const z = result.target_county?.residual_z;
  const r2 = result.r2;
  if (r2 != null) { track("PD R² diabetes", 0.7061, r2, 0.03); log("PASS", "PD R² diabetes", `R²=${r2.toFixed(4)} (was 0.7061)`); }
  if (z != null) { track("McDowell diabetes z", 1.076, z, 0.2); log("PASS", "McDowell diabetes z", `z=${z.toFixed(4)} (was 1.076)`); }

  // Residuals check
  const vals = Object.values(result.residuals_z || {}).filter(v => v != null && isFinite(v));
  const mean = vals.reduce((s, v) => s + v, 0) / vals.length;
  const std = Math.sqrt(vals.reduce((s, v) => s + (v - mean) ** 2, 0) / vals.length);
  log(Math.abs(mean) < 0.01 ? "PASS" : "FAIL", "Residuals mean ≈ 0", `mean=${mean.toFixed(6)}`);
  log(std > 0.9 && std < 1.1 ? "PASS" : "WARN", "Residuals std ≈ 1", `std=${std.toFixed(4)}`);
}

async function testGroundTruth() {
  console.log("\n\x1b[1m═══ 9. Broadband Ground Truth (B28002_007E) ═══\x1b[0m");
  const nodes = await getNodes();
  const nodeMap = new Map(nodes.map(n => [n.fips, n]));

  // Now expected ranges should match B28002_007E (fixed broadband)
  const checks = [
    ["54047", "McDowell WV", 60, 70],
    ["06075", "San Francisco", 80, 87],
    ["21189", "Owsley KY", 55, 72],
    ["36061", "New York County", 78, 88],
  ];

  for (const [fips, name, min, max] of checks) {
    const n = nodeMap.get(fips);
    const val = n?.datasets?.broadband;
    if (val == null) { log("WARN", `${name}`, "broadband null"); continue; }
    const pct = val * 100;
    if (pct >= min && pct <= max) {
      log("PASS", `${name} (${fips})`, `${pct.toFixed(1)}% — within [${min}, ${max}]`);
    } else {
      log("WARN", `${name} (${fips})`, `${pct.toFixed(1)}% — outside [${min}, ${max}]`, "NEEDS NOTE");
    }
  }
}

async function testMissingData() {
  console.log("\n\x1b[1m═══ 10. Missing Data & Coverage ═══\x1b[0m");
  const nodes = await getNodes();
  log("PASS", "County count", `${nodes.length}`);

  const allVars = new Set();
  for (const n of nodes) { for (const k of Object.keys(n.datasets || {})) allVars.add(k); }
  let total = 0, missing = 0;
  for (const v of allVars) { for (const n of nodes) { total++; if (n.datasets?.[v] == null) missing++; } }
  const pct = (missing / total * 100);
  log(pct < 5 ? "PASS" : "WARN", "Missing data", `${pct.toFixed(2)}% (paper: 3.7%)`);
}

async function testNationalMedians() {
  console.log("\n\x1b[1m═══ 11. National Medians ═══\x1b[0m");
  const nodes = await getNodes();
  function med(arr) { const s = [...arr].sort((a, b) => a - b); return s[Math.floor(s.length / 2)]; }

  const bb = med(nodes.map(n => n.datasets?.broadband).filter(v => v != null));
  const bbPct = bb * 100;
  log(bbPct >= 65 && bbPct <= 80 ? "PASS" : "WARN", "National median fixed broadband", `${bbPct.toFixed(1)}%`);

  const pov = med(nodes.map(n => n.datasets?.poverty).filter(v => v != null));
  log(pov >= 11 && pov <= 16 ? "PASS" : "WARN", "National median poverty", `${pov.toFixed(1)}%`);

  const le = med(nodes.map(n => n.datasets?.life_expectancy).filter(v => v != null));
  log(le >= 75 && le <= 80 ? "PASS" : "WARN", "National median life expectancy", `${le.toFixed(1)} yrs`);
}

async function testInternalConsistency() {
  console.log("\n\x1b[1m═══ 12. Internal Consistency ═══\x1b[0m");
  const nodes = await getNodes();
  const checks = [
    { a: "poverty", b: "median_income", sign: -1, label: "poverty vs income" },
    { a: "broadband", b: "median_income", sign: 1, label: "broadband vs income" },
    { a: "diabetes", b: "obesity", sign: 1, label: "diabetes vs obesity" },
    { a: "life_expectancy", b: "poverty", sign: -1, label: "life expectancy vs poverty" },
    { a: "broadband", b: "life_expectancy", sign: 1, label: "broadband vs life expectancy" },
  ];
  for (const c of checks) {
    const { r } = pearsonR(nodes, c.a, c.b);
    const correct = (c.sign > 0 && r > 0) || (c.sign < 0 && r < 0);
    log(correct ? "PASS" : "FAIL", c.label, `r=${r?.toFixed(4)} — ${correct ? "correct" : "WRONG"} direction`);
  }
}

// ═══════════════════════════════════════════════════════════════
async function main() {
  console.log("╔═══════════════════════════════════════════════════════════╗");
  console.log("║  Post-Broadband-Fix Validation (B28002_004E → B28002_007E)║");
  console.log("╚═══════════════════════════════════════════════════════════╝");

  const tests = [
    testBroadbandCorrelations, testPovertyDiabetes, testGravityModel,
    testValidation, testPCA, testClusters, testMcDowellPeers,
    testPositiveDeviance, testGroundTruth, testMissingData,
    testNationalMedians, testInternalConsistency,
  ];

  for (const fn of tests) {
    try { await fn(); } catch (e) { log("FAIL", `${fn.name} ERROR`, e.message); }
  }

  console.log("\n╔═══════════════════════════════════════════════════════════╗");
  console.log(`║  RESULTS: ${passed} passed, ${failed} failed, ${warnings} warnings`);
  console.log("╚═══════════════════════════════════════════════════════════╝");

  if (changes.length > 0) {
    console.log("\n\x1b[1m═══ SIGNIFICANT CHANGES FROM PRE-FIX VALUES ═══\x1b[0m");
    console.log("  These may need paper.md updates:");
    for (const c of changes) {
      console.log(`  △ ${c.label}: ${c.old.toFixed(4)} → ${c.new.toFixed(4)} (diff=${c.diff.toFixed(4)})`);
    }
  } else {
    console.log("\n\x1b[32mNo significant changes from pre-fix values\x1b[0m");
  }

  process.exit(failed > 0 ? 1 : 0);
}

main();
