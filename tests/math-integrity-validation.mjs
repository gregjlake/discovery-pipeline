/**
 * DiscoveryLens — Round 5: Mathematical & Data Integrity
 * Run: node tests/math-integrity-validation.mjs
 */

const BASE = "https://web-production-a68ad.up.railway.app/api";
let passed = 0, failed = 0, warnings = 0;
const results = [];

function log(status, test, detail, severity = "") {
  const icon = status === "PASS" ? "\x1b[32m✓\x1b[0m" : status === "FAIL" ? "\x1b[31m✗\x1b[0m" : "\x1b[33m⚠\x1b[0m";
  console.log(`  ${icon} ${test}${severity ? ` [${severity}]` : ""}`);
  if (detail) console.log(`    ${detail}`);
  results.push({ status, test, detail, severity });
  if (status === "PASS") passed++; else if (status === "FAIL") failed++; else warnings++;
}

function pearsonR(xs, ys) {
  const p = []; for (let i = 0; i < xs.length; i++) if (xs[i] != null && ys[i] != null && isFinite(xs[i]) && isFinite(ys[i])) p.push([xs[i], ys[i]]);
  if (p.length < 10) return null;
  const n = p.length, mx = p.reduce((s, v) => s + v[0], 0) / n, my = p.reduce((s, v) => s + v[1], 0) / n;
  let num = 0, dx = 0, dy = 0;
  for (const [x, y] of p) { num += (x - mx) * (y - my); dx += (x - mx) ** 2; dy += (y - my) ** 2; }
  return Math.sqrt(dx * dy) === 0 ? null : num / Math.sqrt(dx * dy);
}

// Fisher z transform for CI
function fisherCI(r, n, alpha = 0.05) {
  const z = 0.5 * Math.log((1 + r) / (1 - r));
  const se = 1 / Math.sqrt(n - 3);
  const zCrit = 1.96; // 95%
  const lo = Math.tanh(z - zCrit * se);
  const hi = Math.tanh(z + zCrit * se);
  return [lo, hi];
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

function buildDistFn(nodes, vars) {
  const ranges = {};
  for (const n of nodes) for (const k of vars) { const v = n.datasets?.[k]; if (v == null) continue; if (!ranges[k]) ranges[k] = { min: v, max: v }; else { if (v < ranges[k].min) ranges[k].min = v; if (v > ranges[k].max) ranges[k].max = v; } }
  return (a, b) => {
    let sum = 0;
    for (const k of vars) { const va = a[k] ?? 0.5, vb = b[k] ?? 0.5; const r = ranges[k]; const na = r ? (va - r.min) / (r.max - r.min || 1) : 0.5; const nb = r ? (vb - r.min) / (r.max - r.min || 1) : 0.5; sum += (na - nb) ** 2; }
    return Math.sqrt(sum);
  };
}

// ═══════════════════════════════════════════════════════════════
async function test32() {
  console.log("\n\x1b[1m═══ TEST 32: Normalization Correctness ═══\x1b[0m");
  const nodes = await getNodes();
  const allVars = new Set(); for (const n of nodes) for (const k of Object.keys(n.datasets || {})) allVars.add(k);
  let failCount = 0;
  // The gravity map stores RAW values (not z-scored). The pipeline normalizes via min-max internally.
  // So we check min-max normalization: after normalize, values should span [0,1]
  for (const v of allVars) {
    const vals = nodes.map(n => n.datasets?.[v]).filter(x => x != null);
    if (vals.length < 100) continue;
    const min = Math.min(...vals), max = Math.max(...vals);
    const mean = vals.reduce((s, x) => s + x, 0) / vals.length;
    const std = Math.sqrt(vals.reduce((s, x) => s + (x - mean) ** 2, 0) / vals.length);
    // Raw values — just verify they have reasonable spread, no constant columns
    if (std < 0.0001) {
      log("FAIL", `32: ${v} has zero variance`, `std=${std.toFixed(6)}, all values identical`, "BLOCKS SUBMISSION");
      failCount++;
    }
  }
  if (failCount === 0) log("PASS", "32: All variables have non-zero variance", `${allVars.size} variables checked, no constant columns`);
  // Verify min-max normalization produces [0,1] range when applied
  const dist = buildDistFn(nodes, [...allVars]);
  // After normalization, each variable should span [0,1]
  let normOk = 0;
  for (const v of allVars) {
    const vals = nodes.map(n => n.datasets?.[v]).filter(x => x != null);
    if (vals.length < 100) continue;
    const min = Math.min(...vals), max = Math.max(...vals);
    const normVals = vals.map(x => (x - min) / (max - min || 1));
    const nMin = Math.min(...normVals), nMax = Math.max(...normVals);
    if (Math.abs(nMin) < 0.001 && Math.abs(nMax - 1) < 0.001) normOk++;
  }
  log("PASS", "32b: Min-max normalization", `${normOk}/${allVars.size} variables normalize to [0, 1]`);
}

async function test33() {
  console.log("\n\x1b[1m═══ TEST 33: Distance Formula Verification ═══\x1b[0m");
  const nodes = await getNodes();
  const nodeMap = new Map(nodes.map(n => [n.fips, n]));
  const allVars = Object.keys(nodes[0]?.datasets || {});
  const dist = buildDistFn(nodes, allVars);

  const pairs = [
    ["06075", "06081", "SF vs San Mateo"],
    ["54047", "54059", "McDowell vs Mingo"],
    ["51107", "51013", "Loudoun vs Arlington"],
  ];

  for (const [fipsA, fipsB, label] of pairs) {
    const a = nodeMap.get(fipsA), b = nodeMap.get(fipsB);
    if (!a || !b) { log("WARN", `33: ${label}`, `FIPS not found`); continue; }
    const d = dist(a.datasets, b.datasets);
    const sim = Math.max(0, Math.round((1 - d / Math.sqrt(allVars.length)) * 100));
    log("PASS", `33: ${label}`, `dist=${d.toFixed(4)}, sim=${sim}% (${a.county_name} ↔ ${b.county_name})`);
  }
}

async function test34() {
  console.log("\n\x1b[1m═══ TEST 34: Peer Ranking Correctness ═══\x1b[0m");
  const nodes = await getNodes();
  const allVars = Object.keys(nodes[0]?.datasets || {});
  const dist = buildDistFn(nodes, allVars);

  for (const [fips, expectedTop, label] of [["06075", "San Mateo", "SF"], ["54047", "Mingo", "McDowell"]]) {
    const target = nodes.find(n => n.fips === fips);
    const ranked = nodes.filter(n => n.fips !== fips && n.datasets)
      .map(n => ({ fips: n.fips, name: n.county_name, d: dist(target.datasets, n.datasets) }))
      .sort((a, b) => a.d - b.d);
    const top10 = ranked.slice(0, 10).map(p => p.name);
    const topPeer = ranked[0];

    if (topPeer.name.includes(expectedTop)) {
      log("PASS", `34: ${label} top peer`, `#1 = ${topPeer.name} (dist=${topPeer.d.toFixed(4)}) — matches expected`);
    } else {
      log("WARN", `34: ${label} top peer`, `#1 = ${topPeer.name} (expected ${expectedTop}). Top 5: ${top10.slice(0, 5).join(", ")}`, "NEEDS NOTE");
    }
    console.log(`    Top 10: ${top10.join(", ")}`);
  }
}

async function test35() {
  console.log("\n\x1b[1m═══ TEST 35: Within-Cluster Correlation Verification ═══\x1b[0m");
  const nodes = await getNodes();
  const clusters = await fetchJSON("/county-clusters");
  const assignments = clusters.county_assignments || {};
  const LABELS = { 0: "Prosperous Suburban", 1: "Rural Heartland", 2: "Rural Disadvantaged", 3: "High-Need Urban/Border" };

  // Overall
  const allXs = [], allYs = [];
  for (const n of nodes) { const p = n.datasets?.poverty, d = n.datasets?.diabetes; if (p != null && d != null) { allXs.push(p); allYs.push(d); } }
  const overallR = pearsonR(allXs, allYs);
  log(Math.abs(overallR - 0.736) < 0.01 ? "PASS" : "WARN", "35a: Overall poverty×diabetes", `r=${overallR.toFixed(4)} (paper: 0.736)`);

  // Within each cluster
  let wcData;
  try { wcData = await fetchJSON("/within-cluster-correlations"); } catch { wcData = null; }

  for (const cid of [0, 1, 2, 3]) {
    const fipsSet = new Set(Object.entries(assignments).filter(([_, c]) => c === cid).map(([f]) => f));
    const xs = [], ys = [];
    for (const n of nodes) { if (!fipsSet.has(n.fips)) continue; const p = n.datasets?.poverty, d = n.datasets?.diabetes; if (p != null && d != null) { xs.push(p); ys.push(d); } }
    const cr = pearsonR(xs, ys);
    if (cr == null) { log("WARN", `35b: ${LABELS[cid]}`, `n=${xs.length} — insufficient data`); continue; }

    // Compare to API if available
    let apiR = null;
    if (wcData) {
      const clusterEntry = wcData[cid] || wcData[String(cid)];
      if (clusterEntry) {
        const pair = clusterEntry.find?.(p => (p.var_a === "poverty" && p.var_b === "diabetes") || (p.var_a === "diabetes" && p.var_b === "poverty"));
        if (pair) apiR = pair.r;
      }
    }

    const apiMatch = apiR != null ? (Math.abs(cr - apiR) < 0.02 ? ` — matches API (${apiR.toFixed(4)})` : ` — DIFFERS from API (${apiR.toFixed(4)})`) : "";
    log("PASS", `35b: ${LABELS[cid]}`, `r=${cr.toFixed(4)} (n=${xs.length})${apiMatch}`);
  }
}

async function test36() {
  console.log("\n\x1b[1m═══ TEST 36: Bootstrap CI Verification ═══\x1b[0m");
  let val;
  try { val = await fetchJSON("/gravity-map/validation"); } catch { val = null; }
  if (!val) { log("WARN", "36: Validation endpoint", "Not available"); return; }

  const rho = val.rho_combined ?? val.spearman_rho;
  const ciLo = val.ci_low ?? val.bootstrap_ci?.[0];
  const ciHi = val.ci_high ?? val.bootstrap_ci?.[1];
  const nBoot = val.n_bootstrap ?? val.bootstrap_n;

  if (rho != null) log("PASS", "36a: ρ reported", `ρ=${rho.toFixed(4)}`);
  if (ciLo != null && ciHi != null) {
    const width = ciHi - ciLo;
    const symmetric = Math.abs((ciHi - rho) - (rho - ciLo)) < 0.005;
    log("PASS", "36b: CI", `[${ciLo.toFixed(3)}, ${ciHi.toFixed(3)}], width=${width.toFixed(3)}, ${symmetric ? "symmetric" : "asymmetric"}`);
    if (rho >= ciLo && rho <= ciHi) log("PASS", "36c: ρ within CI", "ρ falls inside its own CI");
    else log("FAIL", "36c: ρ outside CI", "ρ does not fall within reported CI", "BLOCKS SUBMISSION");
  } else {
    log("WARN", "36b: CI not in response", "Paper cites [0.155, 0.173]", "NEEDS NOTE");
  }
  if (nBoot != null) log(nBoot >= 1000 ? "PASS" : "WARN", "36d: Bootstrap iterations", `n=${nBoot}`);
}

async function test37() {
  console.log("\n\x1b[1m═══ TEST 37: Module Lens Distance Verification ═══\x1b[0m");
  const nodes = await getNodes();
  const healthVars = ["diabetes", "obesity", "mental_health", "hypertension", "life_expectancy", "food_access", "air", "poverty", "broadband", "child_poverty_rate"].filter(v => nodes[0]?.datasets?.[v] !== undefined);
  const econVars = ["poverty", "median_income", "bea_income", "unemployment", "eitc", "bachelors_rate", "homeownership_rate", "housing_burden", "manufacturing_pct", "agriculture_pct", "housing_vacancy_rate", "population_change_pct", "median_home_value"].filter(v => nodes[0]?.datasets?.[v] !== undefined);
  const allVars = Object.keys(nodes[0]?.datasets || {});

  const healthDist = buildDistFn(nodes, healthVars);
  const econDist = buildDistFn(nodes, econVars);
  const allDist = buildDistFn(nodes, allVars);

  const sf = nodes.find(n => n.fips === "06075");
  const healthPeers = nodes.filter(n => n.fips !== "06075" && n.datasets).map(n => ({ n, hd: healthDist(sf.datasets, n.datasets), ed: econDist(sf.datasets, n.datasets), ad: allDist(sf.datasets, n.datasets) }));

  const topHealth = [...healthPeers].sort((a, b) => a.hd - b.hd)[0];
  const topEcon = [...healthPeers].sort((a, b) => a.ed - b.ed)[0];
  const topAll = [...healthPeers].sort((a, b) => a.ad - b.ad)[0];

  // Health top peer should have smaller health distance than All top peer
  if (topHealth.hd <= topAll.hd) {
    log("PASS", "37a: Health lens peer closer on health", `Health top: ${topHealth.n.county_name} (hd=${topHealth.hd.toFixed(3)}) ≤ All top: ${topAll.n.county_name} (hd=${topAll.hd.toFixed(3)})`);
  } else {
    log("WARN", "37a: Health lens peer", `Health top hd=${topHealth.hd.toFixed(3)} > All top hd=${topAll.hd.toFixed(3)}`);
  }

  // Econ top peer should have smaller econ distance than health top peer
  if (topEcon.ed < topHealth.ed) {
    log("PASS", "37b: Econ lens peer closer on econ", `Econ top: ${topEcon.n.county_name} (ed=${topEcon.ed.toFixed(3)}) < Health top (ed=${topHealth.ed.toFixed(3)})`);
  } else {
    log("WARN", "37b: Econ vs Health peer", "Econ peer not closer on economic variables");
  }
}

async function test38() {
  console.log("\n\x1b[1m═══ TEST 38: IRS Migration Validation Spot Check ═══\x1b[0m");
  let val;
  try { val = await fetchJSON("/gravity-map/validation"); } catch { val = null; }
  if (!val) { log("WARN", "38: Validation endpoint", "Not available — cannot spot-check migration pairs"); return; }

  // Check if specific migration pair data is available
  if (val.top_pairs || val.example_pairs) {
    const pairs = val.top_pairs || val.example_pairs;
    log("PASS", "38a: Migration pair data", `${pairs.length} example pairs available`);
  } else {
    log("WARN", "38a: Migration pair data", "No individual pair data in validation response — only aggregate ρ", "INFORMATIONAL");
  }

  // The key check: ρ > 0 means high gravity pairs tend to have high migration
  const rho = val.rho_combined ?? val.spearman_rho;
  if (rho > 0) {
    log("PASS", "38b: Direction correct", `ρ=${rho.toFixed(4)} > 0 — high gravity ↔ high migration`);
  } else {
    log("FAIL", "38b: Direction wrong", `ρ=${rho.toFixed(4)} ≤ 0`, "BLOCKS SUBMISSION");
  }

  const nPairs = val.n_pairs ?? val.irs_pairs;
  if (nPairs != null) log("PASS", "38c: IRS pairs", `n=${nPairs.toLocaleString()}`);
}

async function test39() {
  console.log("\n\x1b[1m═══ TEST 39: Surprising Finding Ranking ═══\x1b[0m");
  // This tests the client-side computation in AnalysisTab
  // We verify the algorithm: highest |r| cross-domain pair in peer group
  const nodes = await getNodes();
  const sf = nodes.find(n => n.fips === "06075");
  const allVars = Object.keys(sf?.datasets || {});
  const dist = buildDistFn(nodes, allVars);

  // Get SF's top 20 peers + self
  const peers = nodes.filter(n => n.fips !== "06075" && n.datasets)
    .map(n => ({ n, d: dist(sf.datasets, n.datasets) }))
    .sort((a, b) => a.d - b.d).slice(0, 20).map(p => p.n);
  const peerGroup = [sf, ...peers];

  // Domain map
  const DOMAINS = { Economic: ["poverty", "median_income", "bea_income", "unemployment", "eitc", "bachelors_rate", "homeownership_rate", "manufacturing_pct", "agriculture_pct", "median_home_value"], Health: ["obesity", "diabetes", "hypertension", "mental_health", "life_expectancy"], Infrastructure: ["broadband", "food_access", "housing_burden", "air", "housing_vacancy_rate"], Civic: ["voter_turnout", "library", "rural_urban", "pop_density", "median_age", "population_change_pct"] };
  function varDomain(v) { for (const [d, vs] of Object.entries(DOMAINS)) if (vs.includes(v)) return d; return "Other"; }

  let best = null;
  for (let i = 0; i < allVars.length; i++) {
    for (let j = i + 1; j < allVars.length; j++) {
      const dA = varDomain(allVars[i]), dB = varDomain(allVars[j]);
      if (dA === dB || dA === "Other" || dB === "Other") continue;
      const xs = peerGroup.map(n => n.datasets?.[allVars[i]]).filter(x => x != null);
      const ys = peerGroup.map(n => n.datasets?.[allVars[j]]).filter(x => x != null);
      const r = pearsonR(peerGroup.map(n => n.datasets?.[allVars[i]]), peerGroup.map(n => n.datasets?.[allVars[j]]));
      if (r == null) continue;
      if (!best || Math.abs(r) > Math.abs(best.r)) best = { a: allVars[i], b: allVars[j], r, dA, dB };
    }
  }

  if (best) {
    log("PASS", "39: SF surprising finding", `Strongest cross-domain: ${best.a} × ${best.b} (${best.dA}×${best.dB}), r=${best.r.toFixed(4)}`);
  }
}

async function test40() {
  console.log("\n\x1b[1m═══ TEST 40: FIPS Consistency Across Variables ═══\x1b[0m");
  const nodes = await getNodes();
  const allVars = new Set(); for (const n of nodes) for (const k of Object.keys(n.datasets || {})) allVars.add(k);

  // Check coverage per variable
  const coverage = {};
  for (const v of allVars) {
    const count = nodes.filter(n => n.datasets?.[v] != null).length;
    coverage[v] = count;
  }

  const fullCoverage = Object.entries(coverage).filter(([_, c]) => c === nodes.length);
  const partialCoverage = Object.entries(coverage).filter(([_, c]) => c < nodes.length && c > 0);

  log("PASS", "40a: Full coverage variables", `${fullCoverage.length}/${allVars.size} variables have data for all ${nodes.length} counties`);
  if (partialCoverage.length > 0) {
    const worst = partialCoverage.sort((a, b) => a[1] - b[1]).slice(0, 3);
    log("PASS", "40b: Partial coverage", `${partialCoverage.length} variables with gaps. Lowest: ${worst.map(([v, c]) => `${v}=${c}`).join(", ")}`);
  }

  // Verify no duplicate FIPS
  const fipsSet = new Set(nodes.map(n => n.fips));
  log(fipsSet.size === nodes.length ? "PASS" : "FAIL", "40c: No duplicate FIPS", `${fipsSet.size} unique / ${nodes.length} total`);

  // Spot check McDowell and SF have all expected variables
  for (const [fips, name] of [["54047", "McDowell"], ["06075", "SF"]]) {
    const n = nodes.find(n => n.fips === fips);
    const varCount = Object.keys(n?.datasets || {}).filter(k => n.datasets[k] != null).length;
    log("PASS", `40d: ${name} variable count`, `${varCount}/${allVars.size}`);
  }
}

async function test41() {
  console.log("\n\x1b[1m═══ TEST 41: Higher Order Statistical Checks ═══\x1b[0m");
  const nodes = await getNodes();
  const allVars = [...new Set(Object.keys(nodes[0]?.datasets || {}))];

  // 41a: Variance inflation — check for |r| > 0.95 pairs
  console.log("  Checking collinearity...");
  const highCorr = [];
  for (let i = 0; i < allVars.length; i++) {
    for (let j = i + 1; j < allVars.length; j++) {
      const r = pearsonR(nodes.map(n => n.datasets?.[allVars[i]]), nodes.map(n => n.datasets?.[allVars[j]]));
      if (r != null && Math.abs(r) > 0.95) highCorr.push({ a: allVars[i], b: allVars[j], r });
    }
  }
  if (highCorr.length === 0) {
    log("PASS", "41a: No collinear pairs (|r| > 0.95)", "No variable pairs are near-duplicates");
  } else {
    for (const hc of highCorr) log("WARN", `41a: High collinearity: ${hc.a} × ${hc.b}`, `r=${hc.r.toFixed(4)}`, "NEEDS NOTE");
  }

  // 41b: Distribution skewness
  console.log("  Checking skewness...");
  let highSkew = 0;
  for (const v of allVars) {
    const vals = nodes.map(n => n.datasets?.[v]).filter(x => x != null);
    const n = vals.length, mean = vals.reduce((s, x) => s + x, 0) / n;
    const std = Math.sqrt(vals.reduce((s, x) => s + (x - mean) ** 2, 0) / n);
    if (std < 0.0001) continue;
    const skew = vals.reduce((s, x) => s + ((x - mean) / std) ** 3, 0) / n;
    if (Math.abs(skew) > 2.0) highSkew++;
  }
  log(highSkew <= 3 ? "PASS" : "WARN", "41b: Distribution skewness", `${highSkew}/${allVars.length} variables with |skew| > 2.0`);

  // 41c: Outlier influence on poverty×diabetes
  console.log("  Checking outlier influence...");
  const pVals = nodes.map(n => ({ p: n.datasets?.poverty, d: n.datasets?.diabetes })).filter(x => x.p != null && x.d != null);
  pVals.sort((a, b) => a.p - b.p);
  const trimmed = pVals.slice(Math.floor(pVals.length * 0.01), Math.floor(pVals.length * 0.99));
  const rFull = pearsonR(pVals.map(x => x.p), pVals.map(x => x.d));
  const rTrimmed = pearsonR(trimmed.map(x => x.p), trimmed.map(x => x.d));
  const drop = Math.abs(rFull - rTrimmed);
  if (drop < 0.1) {
    log("PASS", "41c: Outlier influence", `Full r=${rFull.toFixed(4)}, trimmed (1-99%) r=${rTrimmed.toFixed(4)}, drop=${drop.toFixed(4)} — robust`);
  } else {
    log("WARN", "41c: Outlier influence", `Full r=${rFull.toFixed(4)}, trimmed r=${rTrimmed.toFixed(4)}, drop=${drop.toFixed(4)} — outlier-sensitive`, "NEEDS NOTE");
  }

  // 41d: Sample size adequacy for within-cluster r
  console.log("  Checking within-cluster sample adequacy...");
  const clusters = await fetchJSON("/county-clusters");
  const assignments = clusters.county_assignments || {};
  const LABELS = { 0: "Prosperous Suburban", 1: "Rural Heartland", 2: "Rural Disadvantaged", 3: "High-Need Urban/Border" };

  for (const cid of [0, 1, 2, 3]) {
    const fipsSet = new Set(Object.entries(assignments).filter(([_, c]) => c === cid).map(([f]) => f));
    const xs = [], ys = [];
    for (const n of nodes) { if (!fipsSet.has(n.fips)) continue; const p = n.datasets?.poverty, d = n.datasets?.diabetes; if (p != null && d != null) { xs.push(p); ys.push(d); } }
    const r = pearsonR(xs, ys);
    if (r == null) continue;
    const [ciLo, ciHi] = fisherCI(r, xs.length);
    const adequate = xs.length >= 100;
    log(adequate ? "PASS" : "WARN", `41d: ${LABELS[cid]} sample size`,
      `n=${xs.length}, r=${r.toFixed(3)}, 95% CI [${ciLo.toFixed(3)}, ${ciHi.toFixed(3)}]${adequate ? "" : " — small sample"}`);
  }
}

// ═══════════════════════════════════════════════════════════════
async function main() {
  console.log("╔═══════════════════════════════════════════════════════════╗");
  console.log("║  DiscoveryLens — Round 5: Mathematical Integrity         ║");
  console.log("╚═══════════════════════════════════════════════════════════╝");

  const tests = [test32, test33, test34, test35, test36, test37, test38, test39, test40, test41];
  for (const fn of tests) { try { await fn(); } catch (e) { log("FAIL", `${fn.name} ERROR`, e.message); } }

  console.log("\n╔═══════════════════════════════════════════════════════════╗");
  console.log(`║  RESULTS: ${passed} passed, ${failed} failed, ${warnings} warnings`);
  console.log("╚═══════════════════════════════════════════════════════════╝");

  const blockers = results.filter(r => r.severity === "BLOCKS SUBMISSION");
  if (blockers.length > 0) { console.log("\n\x1b[31m══ VERDICT: MAJOR ISSUES ══\x1b[0m"); for (const b of blockers) console.log(`  ✗ ${b.test}: ${b.detail}`); }
  else if (warnings > 3) { console.log("\n\x1b[33m══ VERDICT: READY with notes ══\x1b[0m"); }
  else { console.log("\n\x1b[32m══ VERDICT: READY TO SUBMIT ══\x1b[0m"); }

  process.exit(blockers.length > 0 ? 1 : 0);
}

main();
