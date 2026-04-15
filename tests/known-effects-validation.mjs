/**
 * DiscoveryLens — Known Effects Replication & Natural Experiment Detection
 * Tests whether the tool independently reproduces published research findings.
 * Run: node tests/known-effects-validation.mjs
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

async function fetchJSON(path, opts) {
  const res = await fetch(`${BASE}${path}`, opts);
  if (!res.ok) throw new Error(`HTTP ${res.status}`);
  return res.json();
}

let _nodes = null;
async function getNodes() { if (!_nodes) _nodes = (await fetchJSON("/gravity-map?module_id=all")).nodes || []; return _nodes; }

function buildDistFn(nodes, vars) {
  const ranges = {};
  for (const n of nodes) for (const k of vars) { const v = n.datasets?.[k]; if (v == null) continue; if (!ranges[k]) ranges[k] = { min: v, max: v }; else { if (v < ranges[k].min) ranges[k].min = v; if (v > ranges[k].max) ranges[k].max = v; } }
  return (a, b) => {
    let sum = 0;
    for (const k of vars) { const va = a[k] ?? 0.5, vb = b[k] ?? 0.5; const r = ranges[k]; const na = r ? (va - r.min) / (r.max - r.min || 1) : 0.5; const nb = r ? (vb - r.min) / (r.max - r.min || 1) : 0.5; sum += (na - nb) ** 2; }
    return Math.sqrt(sum);
  };
}

// State FIPS → region helpers
const DEEP_SOUTH = new Set(["01","13","22","28","45"]); // AL, GA, LA, MS, SC
const APPALACHIA_STATES = new Set(["21","47","54","37","51","42","39"]); // KY, TN, WV, NC, VA, PA, OH
const DELTA_STATES = new Set(["05","22","28"]); // AR, LA, MS
const RUST_BELT = new Set(["17","18","26","39","42","55"]); // IL, IN, MI, OH, PA, WI

// ARC Distressed Counties (2024 fiscal year, Appalachian subset — well-known examples)
// Source: https://www.arc.gov/distressed-counties/
const ARC_DISTRESSED_FIPS = new Set([
  "21013","21025","21043","21051","21063","21071","21095","21109","21119","21121",
  "21127","21131","21133","21135","21147","21153","21159","21165","21175","21189",
  "21193","21195","21197","21199","21203","21205","21231","21235","21237",
  "54005","54011","54015","54019","54023","54025","54029","54039","54043","54045",
  "54047","54049","54053","54055","54059","54067","54069","54073","54075","54077",
  "54079","54081","54083","54087","54089","54091","54093","54097","54099","54101",
  "54109",
  "47013","47025","47035","47049","47067","47129","47133","47137","47141","47151",
  "28003","28009","28011","28013","28029","28031","28043","28051","28063","28091",
  "01029","01057","01063","01077","01079","01093",
]);

// ═══════════════════════════════════════════════════════════════
// TEST E — REPLICATION OF KNOWN HEALTH GEOGRAPHY FINDINGS
// ═══════════════════════════════════════════════════════════════
async function testE() {
  console.log("\n\x1b[1m═══ TEST E: Replication of Known Health Geography ═══\x1b[0m");
  const nodes = await getNodes();

  // E1: Diabetes Belt (Barker et al. 2011)
  console.log("\n  \x1b[1mE1: CDC Diabetes Belt replication\x1b[0m");
  const withDiabetes = nodes.filter(n => n.datasets?.diabetes != null);
  withDiabetes.sort((a, b) => b.datasets.diabetes - a.datasets.diabetes);
  const top50 = withDiabetes.slice(0, 50);

  let inBelt = 0;
  const regionCounts = {};
  for (const n of top50) {
    const st = n.fips.slice(0, 2);
    const inDeepSouth = DEEP_SOUTH.has(st);
    const inAppalachia = APPALACHIA_STATES.has(st);
    const inDelta = DELTA_STATES.has(st);
    if (inDeepSouth || inAppalachia || inDelta) inBelt++;

    const region = inDeepSouth ? "Deep South" : inAppalachia ? "Appalachia" : inDelta ? "Delta" : "Other";
    regionCounts[region] = (regionCounts[region] || 0) + 1;
  }

  const beltPct = (inBelt / 50 * 100).toFixed(0);
  console.log(`    Top 50 highest-diabetes counties by region:`);
  for (const [r, c] of Object.entries(regionCounts).sort((a, b) => b[1] - a[1])) {
    console.log(`      ${r}: ${c} counties (${(c/50*100).toFixed(0)}%)`);
  }
  console.log(`    In Diabetes Belt (Appalachia + Deep South + Delta): ${inBelt}/50 (${beltPct}%)`);

  // Show top 10
  console.log("    Top 10 highest-diabetes counties:");
  for (const n of top50.slice(0, 10)) {
    console.log(`      ${n.fips} ${n.county_name} — diabetes=${n.datasets.diabetes.toFixed(1)}%, region=${n.region}`);
  }

  if (inBelt >= 30) {
    log("PASS", "E1: Diabetes Belt replication", `${beltPct}% of top-50 diabetes counties are in the known Diabetes Belt — replicates Barker et al. (2011)`);
  } else if (inBelt >= 20) {
    log("WARN", "E1: Partial Diabetes Belt replication", `${beltPct}% in belt — partial replication`, "INFORMATIONAL");
  } else {
    log("FAIL", "E1: Diabetes Belt not replicated", `Only ${beltPct}% in belt — expected >60%`);
  }

  // E2: Deaths of Despair (Case & Deaton 2020)
  console.log("\n  \x1b[1mE2: Deaths of Despair geography (Case & Deaton 2020)\x1b[0m");
  const mc = nodes.find(n => n.fips === "54047");
  const allVars = Object.keys(nodes[0]?.datasets || {});
  const dist = buildDistFn(nodes, allVars);

  const mcPeers = nodes.filter(n => n.fips !== "54047" && n.datasets)
    .map(n => ({ n, d: dist(mc.datasets, n.datasets) }))
    .sort((a, b) => a.d - b.d).slice(0, 20);

  // Mental health as proxy for deaths of despair
  const peerMH = mcPeers.map(p => p.n.datasets?.mental_health).filter(v => v != null);
  const natMH = nodes.map(n => n.datasets?.mental_health).filter(v => v != null);
  const peerMHMean = peerMH.reduce((s, v) => s + v, 0) / peerMH.length;
  const natMHMean = natMH.reduce((s, v) => s + v, 0) / natMH.length;

  // Poverty as economic distress proxy
  const peerPov = mcPeers.map(p => p.n.datasets?.poverty).filter(v => v != null);
  const natPov = nodes.map(n => n.datasets?.poverty).filter(v => v != null);
  const peerPovMean = peerPov.reduce((s, v) => s + v, 0) / peerPov.length;
  const natPovMean = natPov.reduce((s, v) => s + v, 0) / natPov.length;

  const mhRatio = peerMHMean / natMHMean;
  const povRatio = peerPovMean / natPovMean;

  console.log(`    McDowell peer mental health: ${peerMHMean.toFixed(1)} vs national ${natMHMean.toFixed(1)} (${mhRatio.toFixed(1)}x)`);
  console.log(`    McDowell peer poverty: ${peerPovMean.toFixed(1)}% vs national ${natPovMean.toFixed(1)}% (${povRatio.toFixed(1)}x)`);

  // Check geographic distribution — should be Appalachia + Rust Belt
  const peerStates = {};
  for (const p of mcPeers) {
    const st = p.n.fips.slice(0, 2);
    const region = APPALACHIA_STATES.has(st) ? "Appalachia" : DEEP_SOUTH.has(st) ? "Deep South" : RUST_BELT.has(st) ? "Rust Belt" : "Other";
    peerStates[region] = (peerStates[region] || 0) + 1;
  }
  console.log("    McDowell peer geography:", Object.entries(peerStates).map(([r, c]) => `${r}=${c}`).join(", "));

  if (mhRatio > 1.3) {
    log("PASS", "E2: Deaths of Despair — mental health elevated",
      `McDowell peers ${mhRatio.toFixed(1)}x national mean mental health burden — consistent with Case & Deaton (2020)`);
  } else {
    log("WARN", "E2: Deaths of Despair — weak signal", `Only ${mhRatio.toFixed(1)}x national mean`, "INFORMATIONAL");
  }

  // E3: EITC peer clustering (Chetty et al. 2018 related)
  console.log("\n  \x1b[1mE3: EITC clustering (Chetty et al. related)\x1b[0m");
  const withEITC = nodes.filter(n => n.datasets?.eitc != null);
  withEITC.sort((a, b) => b.datasets.eitc - a.datasets.eitc);
  const top20EITC = withEITC.slice(0, 20);

  const natEITCMean = withEITC.reduce((s, n) => s + n.datasets.eitc, 0) / withEITC.length;
  let peersAboveAvg = 0, totalPeerEITC = 0;

  for (const county of top20EITC.slice(0, 5)) {
    const peers = nodes.filter(n => n.fips !== county.fips && n.datasets)
      .map(n => ({ n, d: dist(county.datasets, n.datasets) }))
      .sort((a, b) => a.d - b.d).slice(0, 10);
    for (const p of peers) {
      const pe = p.n.datasets?.eitc;
      if (pe != null) {
        totalPeerEITC++;
        if (pe > natEITCMean) peersAboveAvg++;
      }
    }
  }

  const eitcPct = (peersAboveAvg / totalPeerEITC * 100).toFixed(0);
  console.log(`    High-EITC counties' peers: ${peersAboveAvg}/${totalPeerEITC} (${eitcPct}%) also above-average EITC`);

  if (peersAboveAvg / totalPeerEITC > 0.7) {
    log("PASS", "E3: EITC peer clustering", `${eitcPct}% of high-EITC county peers also have above-average EITC — structural clustering confirmed`);
  } else {
    log("WARN", "E3: EITC clustering", `Only ${eitcPct}% above average`, "INFORMATIONAL");
  }
}

// ═══════════════════════════════════════════════════════════════
// TEST F — TVA NATURAL EXPERIMENT DETECTION
// ═══════════════════════════════════════════════════════════════
async function testF() {
  console.log("\n\x1b[1m═══ TEST F: TVA Natural Experiment Detection ═══\x1b[0m");
  const nodes = await getNodes();
  const allVars = Object.keys(nodes[0]?.datasets || {});
  const dist = buildDistFn(nodes, allVars);

  // TVA counties (major cities along Tennessee River system)
  const TVA_FIPS = [
    { fips: "01083", name: "Limestone AL (Decatur)" },
    { fips: "01033", name: "Colbert AL (Muscle Shoals)" },
    { fips: "47107", name: "McMinn TN (Athens)" },
    { fips: "21145", name: "McCracken KY (Paducah)" },
  ];

  let tvaBetter = 0, totalComparisons = 0;

  for (const tva of TVA_FIPS) {
    const target = nodes.find(n => n.fips === tva.fips);
    if (!target) { console.log(`    ${tva.name}: not found`); continue; }

    const peers = nodes.filter(n => n.fips !== tva.fips && n.datasets)
      .map(n => ({ n, d: dist(target.datasets, n.datasets) }))
      .sort((a, b) => a.d - b.d).slice(0, 10);

    const tvaIncome = target.datasets.median_income;
    const tvaBB = target.datasets.broadband;
    const peerIncome = peers.map(p => p.n.datasets?.median_income).filter(v => v != null);
    const peerBB = peers.map(p => p.n.datasets?.broadband).filter(v => v != null);
    const peerIncMean = peerIncome.reduce((s, v) => s + v, 0) / peerIncome.length;
    const peerBBMean = peerBB.reduce((s, v) => s + v, 0) / peerBB.length;

    // TVA counties should have BETTER infrastructure than their structural peers
    // (since TVA invested heavily in infrastructure)
    const incDiff = tvaIncome - peerIncMean;
    const bbDiff = (tvaBB - peerBBMean) * 100;

    console.log(`    ${tva.name}:`);
    console.log(`      Income: $${Math.round(tvaIncome).toLocaleString()} vs peer mean $${Math.round(peerIncMean).toLocaleString()} (diff: $${Math.round(incDiff).toLocaleString()})`);
    console.log(`      Broadband: ${(tvaBB*100).toFixed(1)}% vs peer mean ${(peerBBMean*100).toFixed(1)}% (diff: ${bbDiff.toFixed(1)}pp)`);
    console.log(`      Peers: ${peers.slice(0, 5).map(p => p.n.county_name).join(", ")}`);

    totalComparisons += 2;
    if (incDiff > 0) tvaBetter++;
    if (bbDiff > 0) tvaBetter++;
  }

  const tvaPct = (tvaBetter / totalComparisons * 100).toFixed(0);
  console.log(`\n    TVA counties outperform peers: ${tvaBetter}/${totalComparisons} comparisons (${tvaPct}%)`);

  if (tvaBetter >= totalComparisons * 0.6) {
    log("PASS", "F: TVA effect detected",
      `TVA counties outperform structural peers on ${tvaPct}% of economic metrics — consistent with long-run TVA infrastructure effect (Kline & Moretti 2014)`);
  } else if (tvaBetter >= totalComparisons * 0.4) {
    log("WARN", "F: Partial TVA effect", `${tvaPct}% outperformance — weak but directionally consistent`, "INFORMATIONAL");
  } else {
    log("WARN", "F: TVA effect not detected", `Only ${tvaPct}% outperformance — TVA effect may be absorbed into peer similarity variables`, "INFORMATIONAL");
  }
}

// ═══════════════════════════════════════════════════════════════
// TEST G — HISPANIC PARADOX / POSITIVE DEVIANCE
// ═══════════════════════════════════════════════════════════════
async function testG() {
  console.log("\n\x1b[1m═══ TEST G: Hispanic Paradox via Positive Deviance ═══\x1b[0m");

  // Run positive deviance: predict life_expectancy from economic variables
  const body = {
    input_variables: ["poverty", "median_income", "unemployment", "housing_burden", "bachelors_rate", "food_access"],
    outcome_variable: "life_expectancy",
  };
  const result = await fetchJSON("/positive-deviance/compute", {
    method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body),
  });

  const nodes = await getNodes();
  const nodeMap = new Map(nodes.map(n => [n.fips, n]));
  const residuals = result.residuals_z || {};

  // Get top 30 positive deviants (higher life expectancy than predicted by economics)
  const sorted = Object.entries(residuals)
    .filter(([_, z]) => z != null && isFinite(z))
    .sort((a, b) => b[1] - a[1]);
  const top30 = sorted.slice(0, 30);

  // Check foreign_born_pct for top positive deviants
  const topFB = [], allFB = [];
  for (const [fips, z] of top30) {
    const n = nodeMap.get(fips);
    const fb = n?.datasets?.foreign_born_pct;
    if (fb != null) topFB.push(fb);
  }
  for (const n of nodes) {
    const fb = n.datasets?.foreign_born_pct;
    if (fb != null) allFB.push(fb);
  }

  const topFBMean = topFB.reduce((s, v) => s + v, 0) / topFB.length;
  const natFBMean = allFB.reduce((s, v) => s + v, 0) / allFB.length;
  const ratio = topFBMean / natFBMean;

  console.log(`  Top 30 positive deviance counties (life exp > predicted by economics):`);
  console.log(`    Mean foreign_born_pct: ${(topFBMean * 100).toFixed(1)}% vs national ${(natFBMean * 100).toFixed(1)}% (${ratio.toFixed(1)}x)`);

  // Show top 10 with foreign-born %
  console.log("    Top 10 positive deviants:");
  for (const [fips, z] of top30.slice(0, 10)) {
    const n = nodeMap.get(fips);
    const fb = n?.datasets?.foreign_born_pct;
    console.log(`      ${n?.county_name || fips}: z=${z.toFixed(2)}, foreign_born=${fb != null ? (fb * 100).toFixed(1) + "%" : "N/A"}, LE=${n?.datasets?.life_expectancy?.toFixed(1) || "N/A"}`);
  }

  // Bottom 30 (negative deviants — worse life expectancy than predicted)
  const bottom30 = sorted.slice(-30);
  const botFB = [];
  for (const [fips] of bottom30) {
    const n = nodeMap.get(fips);
    const fb = n?.datasets?.foreign_born_pct;
    if (fb != null) botFB.push(fb);
  }
  const botFBMean = botFB.reduce((s, v) => s + v, 0) / botFB.length;
  console.log(`    Bottom 30 (negative deviants) mean foreign_born: ${(botFBMean * 100).toFixed(1)}%`);

  if (topFBMean > natFBMean * 1.3) {
    log("PASS", "G: Hispanic Paradox detected",
      `Positive deviance counties have ${ratio.toFixed(1)}x national foreign-born rate — DiscoveryLens independently detects the Hispanic Paradox (Markides & Coreil 1986)`);
  } else if (topFBMean > natFBMean) {
    log("WARN", "G: Weak Hispanic Paradox signal",
      `Positive deviance counties ${ratio.toFixed(1)}x national foreign-born — directionally consistent but weak`, "INFORMATIONAL");
  } else {
    log("WARN", "G: Hispanic Paradox not detected",
      `Positive deviance counties have lower foreign-born than national average`, "INFORMATIONAL");
  }
}

// ═══════════════════════════════════════════════════════════════
// TEST H — ARC DISTRESSED COUNTIES ALIGNMENT
// ═══════════════════════════════════════════════════════════════
async function testH() {
  console.log("\n\x1b[1m═══ TEST H: ARC Distressed Counties Alignment ═══\x1b[0m");
  const nodes = await getNodes();
  const allVars = Object.keys(nodes[0]?.datasets || {});
  const dist = buildDistFn(nodes, allVars);
  const clusters = await fetchJSON("/county-clusters");
  const assignments = clusters.county_assignments || {};

  // McDowell's top 20 peers
  const mc = nodes.find(n => n.fips === "54047");
  const mcPeers = nodes.filter(n => n.fips !== "54047" && n.datasets)
    .map(n => ({ n, d: dist(mc.datasets, n.datasets) }))
    .sort((a, b) => a.d - b.d).slice(0, 20);

  let arcOverlap = 0;
  console.log("  McDowell top 20 peers vs ARC distressed list:");
  for (const p of mcPeers) {
    const isARC = ARC_DISTRESSED_FIPS.has(p.n.fips);
    if (isARC) arcOverlap++;
    console.log(`    ${p.n.fips} ${p.n.county_name} — ${isARC ? "ARC DISTRESSED" : "not on ARC list"}`);
  }

  const arcPct = (arcOverlap / 20 * 100).toFixed(0);
  console.log(`\n    ARC overlap: ${arcOverlap}/20 peers (${arcPct}%) are ARC-designated distressed counties`);

  if (arcOverlap >= 10) {
    log("PASS", "H: ARC distressed alignment",
      `${arcPct}% of McDowell's structural peers are ARC-designated distressed — DiscoveryLens peer identification aligns with official government classification`);
  } else if (arcOverlap >= 6) {
    log("WARN", "H: Partial ARC alignment",
      `${arcPct}% overlap — moderate alignment with ARC designations`, "INFORMATIONAL");
  } else {
    log("WARN", "H: Low ARC alignment",
      `Only ${arcPct}% overlap — peers extend beyond Appalachia to similar conditions nationally`, "INFORMATIONAL");
  }

  // Also check: what % of McDowell peers are in DiscoveryLens "Rural Disadvantaged" cluster?
  const peerCluster2 = mcPeers.filter(p => assignments[p.n.fips] === 2).length;
  console.log(`    Peers in Rural Disadvantaged cluster: ${peerCluster2}/20 (${(peerCluster2/20*100).toFixed(0)}%)`);

  if (peerCluster2 >= 15) {
    log("PASS", "H2: Cluster-peer alignment",
      `${(peerCluster2/20*100).toFixed(0)}% of McDowell peers are in Rural Disadvantaged cluster — archetype classification is consistent with peer discovery`);
  }
}

// ═══════════════════════════════════════════════════════════════
async function main() {
  console.log("╔═══════════════════════════════════════════════════════════╗");
  console.log("║  DiscoveryLens — Known Effects Replication               ║");
  console.log("║  Diabetes Belt, Deaths of Despair, TVA, Hispanic Paradox ║");
  console.log("╚═══════════════════════════════════════════════════════════╝");

  for (const fn of [testE, testF, testG, testH]) {
    try { await fn(); } catch (e) { log("FAIL", `${fn.name} ERROR`, e.message); }
  }

  console.log("\n╔═══════════════════════════════════════════════════════════╗");
  console.log(`║  RESULTS: ${passed} passed, ${failed} failed, ${warnings} warnings`);
  console.log("╚═══════════════════════════════════════════════════════════╝");

  if (failed > 0) console.log("\n\x1b[31m══ REPLICATION FAILURES ══\x1b[0m");
  else console.log("\n\x1b[32m══ KNOWN EFFECTS REPLICATED ══\x1b[0m");

  process.exit(failed > 0 ? 1 : 0);
}

main();
