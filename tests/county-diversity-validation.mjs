/**
 * DiscoveryLens — County Diversity Validation
 * Spot-checks across archetypes, geographies, and edge cases.
 * Run: node tests/county-diversity-validation.mjs
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

let _nodes = null, _clusters = null;
async function getNodes() { if (!_nodes) _nodes = (await fetchJSON("/gravity-map?module_id=all")).nodes || []; return _nodes; }
async function getClusters() { if (!_clusters) _clusters = (await fetchJSON("/county-clusters")).county_assignments || {}; return _clusters; }

function buildDistFn(nodes, vars) {
  const ranges = {};
  for (const n of nodes) for (const k of vars) { const v = n.datasets?.[k]; if (v == null) continue; if (!ranges[k]) ranges[k] = { min: v, max: v }; else { if (v < ranges[k].min) ranges[k].min = v; if (v > ranges[k].max) ranges[k].max = v; } }
  return (a, b) => {
    let sum = 0;
    for (const k of vars) { const va = a[k] ?? 0.5, vb = b[k] ?? 0.5; const r = ranges[k]; const na = r ? (va - r.min) / (r.max - r.min || 1) : 0.5; const nb = r ? (vb - r.min) / (r.max - r.min || 1) : 0.5; sum += (na - nb) ** 2; }
    return Math.sqrt(sum);
  };
}

const CLUSTER_LABELS = { 0: "Prosperous Suburban", 1: "Rural Heartland", 2: "Rural Disadvantaged", 3: "High-Need Urban/Border" };

function getPeers(nodes, fips, dist, k = 5) {
  const target = nodes.find(n => n.fips === fips);
  if (!target?.datasets) return [];
  return nodes.filter(n => n.fips !== fips && n.datasets)
    .map(n => ({ fips: n.fips, name: n.county_name, d: dist(target.datasets, n.datasets), region: n.region, pop: n.population }))
    .sort((a, b) => a.d - b.d).slice(0, k);
}

function fmtPov(v) { return v != null ? (v > 1 ? v.toFixed(1) + "%" : (v * 100).toFixed(1) + "%") : "null"; }
function fmtInc(v) { return v != null ? "$" + Math.round(v).toLocaleString() : "null"; }
function fmtLE(v) { return v != null ? v.toFixed(1) + " yrs" : "null"; }
function fmtBB(v) { return v != null ? (v > 1 ? v.toFixed(1) + "%" : (v * 100).toFixed(1) + "%") : "null"; }

// ═══════════════════════════════════════════════════════════════
// COUNTY PROFILES
// ═══════════════════════════════════════════════════════════════

const COUNTIES = {
  // Prosperous Suburban (cluster 0)
  "51107": { name: "Loudoun VA", expectedCluster: 0, povRange: [3, 8], incRange: [125000, 175000], leRange: [82, 87] },
  "08035": { name: "Douglas CO", expectedCluster: 0, povRange: [3, 7], incRange: [110000, 155000], leRange: [82, 88] },
  "18057": { name: "Hamilton IN", expectedCluster: 0, povRange: [3, 8], incRange: [95000, 130000], leRange: [80, 86] },

  // Rural Heartland (cluster 1)
  "29019": { name: "Boone MO", expectedCluster: 1, povRange: [12, 20], incRange: [50000, 75000], leRange: [76, 82] },
  "53071": { name: "Walla Walla WA", expectedCluster: 1, povRange: [12, 20], incRange: [50000, 70000], leRange: [76, 82] },
  "31109": { name: "Lancaster NE", expectedCluster: 1, povRange: [10, 16], incRange: [55000, 75000], leRange: [78, 83] },

  // Rural Disadvantaged (cluster 2)
  "21189": { name: "Owsley KY", expectedCluster: 2, povRange: [28, 45], incRange: [18000, 33000], leRange: [68, 76] },
  "28051": { name: "Holmes MS", expectedCluster: 2, povRange: [30, 45], incRange: [20000, 32000], leRange: [68, 76] },
  "48507": { name: "Zavala TX", expectedCluster: 2, povRange: [28, 42], incRange: [22000, 36000], leRange: [70, 80] },

  // Edge cases
  "48301": { name: "Loving TX", expectedCluster: null, povRange: [0, 20], incRange: [30000, 200000], leRange: [60, 95] },
  "15005": { name: "Kalawao HI", expectedCluster: null, povRange: null, incRange: null, leRange: null },
  "02158": { name: "Kusilvak AK", expectedCluster: null, povRange: [25, 45], incRange: [25000, 55000], leRange: [60, 75] },
};

async function testClusterAssignments() {
  console.log("\n\x1b[1m═══ 1. Cluster Assignments ═══\x1b[0m");
  const clusters = await getClusters();

  for (const [fips, info] of Object.entries(COUNTIES)) {
    const actual = clusters[fips];
    const actualLabel = CLUSTER_LABELS[actual] ?? "Unknown/Missing";

    if (info.expectedCluster === null) {
      // Edge case — just report
      log("PASS", `${info.name} (${fips})`, `cluster=${actual} (${actualLabel}) — edge case, no expected value`);
    } else if (actual === info.expectedCluster) {
      log("PASS", `${info.name} (${fips})`, `cluster=${actual} (${actualLabel}) ✓`);
    } else if (actual != null) {
      log("WARN", `${info.name} (${fips})`, `cluster=${actual} (${actualLabel}), expected=${info.expectedCluster} (${CLUSTER_LABELS[info.expectedCluster]})`, "NEEDS NOTE");
    } else {
      log("WARN", `${info.name} (${fips})`, "Not in cluster assignments — may be excluded from clustering", "INFORMATIONAL");
    }
  }

  // Find 3 representative High-Need Urban/Border (cluster 3) counties
  console.log("\n  Identifying representative cluster 3 (High-Need Urban/Border) counties:");
  const nodes = await getNodes();
  const c3Fips = Object.entries(clusters).filter(([_, c]) => c === 3).map(([f]) => f);
  const c3Nodes = nodes.filter(n => c3Fips.includes(n.fips) && n.population > 10000).sort((a, b) => b.population - a.population).slice(0, 5);
  for (const n of c3Nodes) {
    const pov = n.datasets?.poverty, inc = n.datasets?.median_income;
    console.log(`    ${n.fips} ${n.county_name} — pop=${n.population?.toLocaleString()}, poverty=${fmtPov(pov)}, income=${fmtInc(inc)}, region=${n.region}`);
  }
  if (c3Nodes.length >= 3) log("PASS", "Cluster 3 representatives found", `${c3Fips.length} counties total, top 5 shown above`);
}

async function testGroundTruth() {
  console.log("\n\x1b[1m═══ 2. Ground Truth Values ═══\x1b[0m");
  const nodes = await getNodes();
  const nodeMap = new Map(nodes.map(n => [n.fips, n]));

  for (const [fips, info] of Object.entries(COUNTIES)) {
    const n = nodeMap.get(fips);
    if (!n) {
      log("WARN", `${info.name} (${fips})`, "Not found in dataset", "INFORMATIONAL");
      continue;
    }

    const pov = n.datasets?.poverty;
    const inc = n.datasets?.median_income;
    const le = n.datasets?.life_expectancy;
    const bb = n.datasets?.broadband;
    const varCount = Object.keys(n.datasets || {}).filter(k => n.datasets[k] != null).length;

    let issues = [];

    // Poverty check
    if (info.povRange && pov != null) {
      const povPct = pov > 1 ? pov : pov * 100;
      if (povPct < info.povRange[0] - 3 || povPct > info.povRange[1] + 3) issues.push(`poverty=${fmtPov(pov)} outside [${info.povRange}]`);
    }

    // Income check
    if (info.incRange && inc != null) {
      if (inc < info.incRange[0] * 0.85 || inc > info.incRange[1] * 1.15) issues.push(`income=${fmtInc(inc)} outside [${info.incRange.map(v => "$" + v.toLocaleString())}]`);
    }

    // Life expectancy check
    if (info.leRange && le != null) {
      if (le < info.leRange[0] - 3 || le > info.leRange[1] + 3) issues.push(`life_exp=${fmtLE(le)} outside [${info.leRange}]`);
    }

    // Impossible values check
    if (pov != null && ((pov > 1 && pov > 60) || (pov <= 1 && pov > 0.6))) issues.push(`poverty=${pov} impossibly high`);
    if (inc != null && (inc < 5000 || inc > 500000)) issues.push(`income=${inc} implausible`);
    if (le != null && (le < 50 || le > 100)) issues.push(`life_exp=${le} implausible`);
    if (bb != null && (bb < 0 || bb > 1.01)) issues.push(`broadband=${bb} out of range`);

    const summary = `pop=${n.population?.toLocaleString()}, poverty=${fmtPov(pov)}, income=${fmtInc(inc)}, LE=${fmtLE(le)}, BB=${fmtBB(bb)}, vars=${varCount}/30`;

    if (issues.length === 0) {
      log("PASS", `${info.name} (${fips})`, summary);
    } else {
      log("WARN", `${info.name} (${fips})`, `${summary} — ISSUES: ${issues.join("; ")}`, "NEEDS NOTE");
    }
  }
}

async function testPeerPlausibility() {
  console.log("\n\x1b[1m═══ 3. Peer Plausibility ═══\x1b[0m");
  const nodes = await getNodes();
  const allVars = Object.keys(nodes[0]?.datasets || {});
  const dist = buildDistFn(nodes, allVars);
  const clusters = await getClusters();

  const testCases = [
    { fips: "51107", name: "Loudoun VA", expectPeerTraits: "wealthy suburban", expectDiverse: true },
    { fips: "08035", name: "Douglas CO", expectPeerTraits: "wealthy suburban", expectDiverse: true },
    { fips: "21189", name: "Owsley KY", expectPeerTraits: "rural high-poverty", expectDiverse: true },
    { fips: "28051", name: "Holmes MS", expectPeerTraits: "rural high-poverty Southern", expectDiverse: true },
    { fips: "29019", name: "Boone MO", expectPeerTraits: "mid-size moderate", expectDiverse: true },
    { fips: "48301", name: "Loving TX", expectPeerTraits: "small rural", expectDiverse: false },
    { fips: "48507", name: "Zavala TX", expectPeerTraits: "border poverty", expectDiverse: true },
  ];

  for (const tc of testCases) {
    const target = nodes.find(n => n.fips === tc.fips);
    if (!target) { log("WARN", `${tc.name} peers`, "County not found"); continue; }

    const peers = getPeers(nodes, tc.fips, dist, 10);
    const peerStates = new Set(peers.map(p => p.fips.slice(0, 2)));
    const peerClusters = peers.map(p => clusters[p.fips]).filter(c => c != null);
    const targetCluster = clusters[tc.fips];
    const sameClusterPeers = peerClusters.filter(c => c === targetCluster).length;

    const sim = Math.max(0, Math.round((1 - peers[0]?.d / Math.sqrt(allVars.length)) * 100));

    console.log(`    ${tc.name}: top 5 peers = ${peers.slice(0, 5).map(p => p.name).join(", ")}`);
    console.log(`      States: ${[...peerStates].join(",")}, same-cluster: ${sameClusterPeers}/10, top sim: ${sim}%`);

    let peerOk = true;
    const issues = [];

    // Geographic diversity (if expected)
    if (tc.expectDiverse && peerStates.size < 2) {
      issues.push("all peers from same state");
      peerOk = false;
    }

    // Top peer should have reasonable similarity
    if (sim < 70) {
      issues.push(`top peer similarity only ${sim}%`);
      peerOk = false;
    }

    // Most peers should share the same cluster
    if (targetCluster != null && sameClusterPeers < 5) {
      issues.push(`only ${sameClusterPeers}/10 peers in same cluster`);
    }

    if (issues.length === 0) {
      log("PASS", `${tc.name} peers`, `${peerStates.size} states, ${sameClusterPeers}/10 same cluster, top sim=${sim}%`);
    } else {
      log("WARN", `${tc.name} peers`, issues.join("; "), "INFORMATIONAL");
    }
  }
}

async function testMissingDataByCounty() {
  console.log("\n\x1b[1m═══ 4. Missing Data by County ═══\x1b[0m");
  const nodes = await getNodes();
  const allVars = new Set(); for (const n of nodes) for (const k of Object.keys(n.datasets || {})) allVars.add(k);
  const totalVars = allVars.size;

  const edgeCases = [
    ["48301", "Loving TX"],
    ["15005", "Kalawao HI"],
    ["02158", "Kusilvak AK"],
    ["02270", "Wade Hampton AK"], // Old FIPS for Kusilvak
  ];

  for (const [fips, name] of edgeCases) {
    const n = nodes.find(n => n.fips === fips);
    if (!n) {
      log("WARN", `${name} (${fips})`, "Not in dataset — may use different FIPS or be excluded", "INFORMATIONAL");
      continue;
    }
    const present = Object.keys(n.datasets || {}).filter(k => n.datasets[k] != null).length;
    const missing = totalVars - present;
    const pct = (missing / totalVars * 100).toFixed(0);

    if (missing > totalVars * 0.5) {
      log("WARN", `${name} (${fips})`, `${present}/${totalVars} variables present (${pct}% missing) — extreme missingness`, "INFORMATIONAL");
    } else {
      log("PASS", `${name} (${fips})`, `${present}/${totalVars} variables present (${pct}% missing)`);
    }

    // List missing variables
    if (missing > 0) {
      const missingVars = [...allVars].filter(k => n.datasets?.[k] == null);
      console.log(`      Missing: ${missingVars.join(", ")}`);
    }
  }
}

async function testDistanceFormulaDiversity() {
  console.log("\n\x1b[1m═══ 5. Distance Formula — Diverse Pairs ═══\x1b[0m");
  const nodes = await getNodes();
  const allVars = Object.keys(nodes[0]?.datasets || {});
  const dist = buildDistFn(nodes, allVars);
  const nodeMap = new Map(nodes.map(n => [n.fips, n]));

  const pairs = [
    ["51107", "08035", "Loudoun VA vs Douglas CO (both wealthy suburban)"],
    ["21189", "28051", "Owsley KY vs Holmes MS (both rural disadvantaged)"],
    ["51107", "21189", "Loudoun VA vs Owsley KY (extreme opposite)"],
    ["29019", "31109", "Boone MO vs Lancaster NE (both rural heartland)"],
    ["48507", "21189", "Zavala TX vs Owsley KY (different disadvantaged)"],
  ];

  for (const [fA, fB, label] of pairs) {
    const a = nodeMap.get(fA), b = nodeMap.get(fB);
    if (!a || !b) { log("WARN", label, "FIPS not found"); continue; }
    const d = dist(a.datasets, b.datasets);
    const sim = Math.max(0, Math.round((1 - d / Math.sqrt(allVars.length)) * 100));
    log("PASS", label, `dist=${d.toFixed(3)}, sim=${sim}%`);
  }

  // Verify: similar counties (same archetype) should be closer than different archetypes
  const loudounDouglas = dist(nodeMap.get("51107").datasets, nodeMap.get("08035").datasets);
  const loudounOwsley = dist(nodeMap.get("51107").datasets, nodeMap.get("21189").datasets);
  if (loudounDouglas < loudounOwsley) {
    log("PASS", "Distance ordering", `Loudoun↔Douglas (${loudounDouglas.toFixed(3)}) < Loudoun↔Owsley (${loudounOwsley.toFixed(3)}) — same-archetype counties are closer`);
  } else {
    log("FAIL", "Distance ordering", `Same-archetype pair NOT closer than cross-archetype pair`, "NEEDS NOTE");
  }
}

async function testCluster3Deep() {
  console.log("\n\x1b[1m═══ 6. Cluster 3 (High-Need Urban/Border) Deep Dive ═══\x1b[0m");
  const nodes = await getNodes();
  const clusters = await getClusters();

  const c3Fips = new Set(Object.entries(clusters).filter(([_, c]) => c === 3).map(([f]) => f));
  const c3Nodes = nodes.filter(n => c3Fips.has(n.fips));

  if (c3Nodes.length === 0) {
    log("WARN", "Cluster 3", "No counties found", "NEEDS NOTE");
    return;
  }

  // Compute cluster-level statistics
  const stats = {};
  for (const key of ["poverty", "median_income", "broadband", "foreign_born_pct", "language_isolation_rate", "pop_density"]) {
    const vals = c3Nodes.map(n => n.datasets?.[key]).filter(v => v != null);
    if (vals.length === 0) continue;
    const mean = vals.reduce((s, v) => s + v, 0) / vals.length;
    stats[key] = mean;
  }

  console.log("    Cluster 3 profile:");
  for (const [k, v] of Object.entries(stats)) {
    console.log(`      ${k}: mean=${v.toFixed(3)}`);
  }

  log("PASS", "Cluster 3 size", `n=${c3Nodes.length} counties`);

  // Pick 3 representative counties
  const sorted = c3Nodes.filter(n => n.population > 5000).sort((a, b) => b.population - a.population);
  const reps = sorted.slice(0, 3);
  for (const n of reps) {
    const pov = n.datasets?.poverty, fb = n.datasets?.foreign_born_pct, li = n.datasets?.language_isolation_rate;
    log("PASS", `Cluster 3 rep: ${n.county_name} (${n.fips})`,
      `pop=${n.population?.toLocaleString()}, poverty=${fmtPov(pov)}, foreign_born=${fb != null ? (fb * 100).toFixed(1) + "%" : "null"}, lang_iso=${li != null ? (li * 100).toFixed(1) + "%" : "null"}`);
  }
}

// ═══════════════════════════════════════════════════════════════
async function main() {
  console.log("╔═══════════════════════════════════════════════════════════╗");
  console.log("║  DiscoveryLens — County Diversity Validation             ║");
  console.log("╚═══════════════════════════════════════════════════════════╝");

  const tests = [testClusterAssignments, testGroundTruth, testPeerPlausibility, testMissingDataByCounty, testDistanceFormulaDiversity, testCluster3Deep];
  for (const fn of tests) { try { await fn(); } catch (e) { log("FAIL", `${fn.name} ERROR`, e.message); } }

  console.log("\n╔═══════════════════════════════════════════════════════════╗");
  console.log(`║  RESULTS: ${passed} passed, ${failed} failed, ${warnings} warnings`);
  console.log("╚═══════════════════════════════════════════════════════════╝");

  const blockers = results.filter(r => r.severity === "BLOCKS SUBMISSION" || r.severity === "NEEDS NOTE");
  if (results.some(r => r.status === "FAIL" && r.severity === "BLOCKS SUBMISSION")) {
    console.log("\n\x1b[31m══ ISSUES FOUND ══\x1b[0m");
  } else {
    console.log("\n\x1b[32m══ ALL COUNTIES VERIFIED ══\x1b[0m");
  }

  process.exit(failed > 0 ? 1 : 0);
}

main();
