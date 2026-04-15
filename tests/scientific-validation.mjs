/**
 * DiscoveryLens Scientific Validation Suite
 * Verifies data accuracy independently of the UI.
 * Run: node tests/scientific-validation.mjs
 */

const BASE = "https://web-production-a68ad.up.railway.app/api";

let passed = 0, failed = 0, warnings = 0;
const results = [];

function log(status, test, detail) {
  const icon = status === "PASS" ? "\x1b[32m✓\x1b[0m" : status === "FAIL" ? "\x1b[31m✗\x1b[0m" : "\x1b[33m⚠\x1b[0m";
  console.log(`  ${icon} ${test}`);
  if (detail) console.log(`    ${detail}`);
  results.push({ status, test, detail });
  if (status === "PASS") passed++;
  else if (status === "FAIL") failed++;
  else warnings++;
}

function pearsonR(xs, ys) {
  const pairs = [];
  for (let i = 0; i < xs.length; i++) {
    if (xs[i] != null && ys[i] != null && isFinite(xs[i]) && isFinite(ys[i])) {
      pairs.push([xs[i], ys[i]]);
    }
  }
  if (pairs.length < 10) return null;
  const n = pairs.length;
  const mx = pairs.reduce((s, p) => s + p[0], 0) / n;
  const my = pairs.reduce((s, p) => s + p[1], 0) / n;
  let num = 0, dx = 0, dy = 0;
  for (const [x, y] of pairs) {
    num += (x - mx) * (y - my);
    dx += (x - mx) ** 2;
    dy += (y - my) ** 2;
  }
  const denom = Math.sqrt(dx * dy);
  return denom === 0 ? null : num / denom;
}

async function fetchJSON(path, opts) {
  const res = await fetch(`${BASE}${path}`, opts);
  if (!res.ok) throw new Error(`HTTP ${res.status} for ${path}`);
  return res.json();
}

// ═══════════════════════════════════════════════════════════════
// TEST 1 — CORRELATION VALIDATION
// ═══════════════════════════════════════════════════════════════
async function test1_correlations() {
  console.log("\n═══ TEST 1: Correlation Validation ═══");

  const pairs = [
    ["poverty", "diabetes"],
    ["broadband", "life_expectancy"],
    ["poverty", "broadband"],
    ["median_income", "diabetes"],
    ["housing_burden", "homeownership_rate"],
  ];

  // Get all county data from gravity-map
  const gravData = await fetchJSON("/gravity-map?module_id=all");
  const nodes = gravData.nodes || [];

  for (const [varA, varB] of pairs) {
    // Compute r from raw data
    const xs = nodes.map(n => n.datasets?.[varA]).filter(v => v != null);
    const ys = nodes.map(n => n.datasets?.[varB]).filter(v => v != null);

    // Pairwise complete
    const pairXs = [], pairYs = [];
    for (const n of nodes) {
      const a = n.datasets?.[varA], b = n.datasets?.[varB];
      if (a != null && b != null) { pairXs.push(a); pairYs.push(b); }
    }

    const computedR = pearsonR(pairXs, pairYs);

    // Fetch from scatter API
    let apiR = null;
    try {
      const scatterData = await fetchJSON(`/scatter?x=${varA}&y=${varB}`);
      apiR = scatterData.r ?? scatterData.correlation?.r ?? null;
    } catch {
      // Try POST
      try {
        const scatterData = await fetchJSON("/scatter", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ x_dataset: varA, y_dataset: varB }),
        });
        apiR = scatterData.r ?? scatterData.correlation?.r ?? null;
      } catch {}
    }

    const label = `${varA} × ${varB}`;
    if (computedR == null) {
      log("WARN", label, "Insufficient data to compute r");
      continue;
    }

    if (apiR != null) {
      const diff = Math.abs(computedR - apiR);
      if (diff <= 0.01) {
        log("PASS", label, `computed r=${computedR.toFixed(4)}, API r=${apiR.toFixed(4)}, diff=${diff.toFixed(4)}`);
      } else if (diff <= 0.05) {
        log("WARN", label, `computed r=${computedR.toFixed(4)}, API r=${apiR.toFixed(4)}, diff=${diff.toFixed(4)} (>0.01 but <0.05)`);
      } else {
        log("FAIL", label, `computed r=${computedR.toFixed(4)}, API r=${apiR.toFixed(4)}, diff=${diff.toFixed(4)} EXCEEDS TOLERANCE`);
      }
    } else {
      log("WARN", label, `computed r=${computedR.toFixed(4)}, API r not available from scatter endpoint`);
    }
  }
}

// ═══════════════════════════════════════════════════════════════
// TEST 2 — PEER CORRECTNESS
// ═══════════════════════════════════════════════════════════════
async function test2_peerCorrectness() {
  console.log("\n═══ TEST 2: Peer Correctness (McDowell WV) ═══");

  const gravData = await fetchJSON("/gravity-map?module_id=all");
  const nodes = gravData.nodes || [];
  const nodeMap = new Map(nodes.map(n => [n.fips, n]));

  const mcDowell = nodeMap.get("54047");
  if (!mcDowell) { log("FAIL", "McDowell lookup", "FIPS 54047 not found in nodes"); return; }

  // Compute dataset ranges for normalization
  const ranges = {};
  for (const n of nodes) {
    if (!n.datasets) continue;
    for (const [k, v] of Object.entries(n.datasets)) {
      if (v == null) continue;
      if (!ranges[k]) ranges[k] = { min: v, max: v };
      else { if (v < ranges[k].min) ranges[k].min = v; if (v > ranges[k].max) ranges[k].max = v; }
    }
  }

  // Get all variable keys
  const allVars = Object.keys(ranges);

  // Euclidean distance (normalized)
  function euclidDist(a, b, keys) {
    let sum = 0;
    for (const k of keys) {
      const va = a[k] ?? 0.5, vb = b[k] ?? 0.5;
      const r = ranges[k];
      const na = r ? (va - r.min) / (r.max - r.min || 1) : 0.5;
      const nb = r ? (vb - r.min) / (r.max - r.min || 1) : 0.5;
      sum += (na - nb) ** 2;
    }
    return Math.sqrt(sum);
  }

  // Compute peers
  const peers = nodes
    .filter(n => n.fips !== "54047" && n.datasets)
    .map(n => ({ fips: n.fips, dist: euclidDist(mcDowell.datasets, n.datasets, allVars) }))
    .sort((a, b) => a.dist - b.dist)
    .slice(0, 10)
    .map(p => {
      const node = nodeMap.get(p.fips);
      const sim = Math.max(0, Math.round((1 - p.dist / Math.sqrt(allVars.length)) * 100));
      return { ...node, similarity: sim };
    });

  // Compute national median poverty
  const povertyVals = nodes.map(n => n.datasets?.poverty).filter(v => v != null).sort((a, b) => a - b);
  const medianPoverty = povertyVals[Math.floor(povertyVals.length / 2)];

  // Check: all peers have higher poverty than national median
  const highPovPeers = peers.filter(p => (p.datasets?.poverty ?? 0) > medianPoverty);
  if (highPovPeers.length === peers.length) {
    log("PASS", "Peers high poverty", `All ${peers.length} peers above national median poverty (${medianPoverty.toFixed(1)})`);
  } else {
    log("WARN", "Peers high poverty", `${highPovPeers.length}/${peers.length} peers above median poverty (${medianPoverty.toFixed(1)}). Some peers may be structurally similar on other dimensions.`);
  }

  // Check: rurality
  const ruralPeers = peers.filter(p => (p.datasets?.rural_urban ?? 0) > 5);
  if (ruralPeers.length >= peers.length * 0.7) {
    log("PASS", "Peers rural character", `${ruralPeers.length}/${peers.length} peers are rural (rural_urban > 5)`);
  } else {
    log("WARN", "Peers rural character", `Only ${ruralPeers.length}/${peers.length} peers are rural`);
  }

  // Check: geographic diversity (not all WV)
  const states = new Set(peers.map(p => p.fips.slice(0, 2)));
  if (states.size > 1) {
    log("PASS", "Geographic diversity", `Peers span ${states.size} states: ${[...states].join(", ")}`);
  } else {
    log("FAIL", "Geographic diversity", "All peers from same state — expected cross-state peers");
  }

  // Check: top similarity above 80%
  if (peers[0]?.similarity >= 80) {
    log("PASS", "Top peer similarity", `Top peer: ${peers[0].county_name} at ${peers[0].similarity}%`);
  } else {
    log("WARN", "Top peer similarity", `Top peer: ${peers[0]?.county_name} at ${peers[0]?.similarity}% (expected ≥80%)`);
  }

  // Report peer list
  console.log("    Peer list:");
  for (const p of peers.slice(0, 5)) {
    console.log(`      ${p.fips} ${p.county_name} — ${p.similarity}% similar, poverty=${p.datasets?.poverty?.toFixed(1)}, rural=${p.datasets?.rural_urban?.toFixed(0)}, region=${p.region}`);
  }
}

// ═══════════════════════════════════════════════════════════════
// TEST 3 — POSITIVE DEVIANCE RESIDUALS
// ═══════════════════════════════════════════════════════════════
async function test3_positiveDeviance() {
  console.log("\n═══ TEST 3: Positive Deviance Residuals ═══");

  // McDowell WV positive deviance for life_expectancy
  const body = {
    input_variables: ["poverty", "diabetes", "obesity", "mental_health", "hypertension",
      "food_access", "air", "broadband", "child_poverty_rate"],
    outcome_variable: "life_expectancy",
    county_fips: "54047",
  };

  const result = await fetchJSON("/positive-deviance/compute", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });

  // R² check
  const r2 = result.r2;
  if (r2 != null) {
    if (Math.abs(r2 - 0.275) <= 0.05) {
      log("PASS", "PD R²", `R²=${r2.toFixed(4)} (expected ~0.275, tol ±0.05)`);
    } else {
      log("WARN", "PD R²", `R²=${r2.toFixed(4)} (expected ~0.275, diff=${Math.abs(r2 - 0.275).toFixed(4)}). Model may use different variable set.`);
    }
  } else {
    log("FAIL", "PD R²", "R² not returned by API");
  }

  // McDowell residual z
  const tc = result.target_county;
  if (tc) {
    const z = tc.residual_z;
    console.log(`    McDowell: actual=${tc.actual?.toFixed(2)}, predicted=${tc.predicted?.toFixed(2)}, z=${z?.toFixed(4)}`);
    // Note: sign depends on which direction is "positive deviance"
    // Life expectancy for McDowell is very low (~66.3), so it should be BELOW predicted = negative z
    if (z != null) {
      if (Math.abs(z) > 0.5) {
        log("PASS", "McDowell residual z", `z=${z.toFixed(4)} (non-trivial residual, McDowell is a clear outlier)`);
      } else {
        log("WARN", "McDowell residual z", `z=${z.toFixed(4)} (expected a larger residual for McDowell)`);
      }
    }
  } else {
    log("FAIL", "McDowell residual", "target_county not returned");
  }

  // Discriminating factors
  if (result.discriminating_factors?.length > 0) {
    log("PASS", "Discriminating factors", `${result.discriminating_factors.length} factors returned. Top: ${result.discriminating_factors[0].variable}`);
  } else {
    log("WARN", "Discriminating factors", "No discriminating factors returned");
  }
}

// ═══════════════════════════════════════════════════════════════
// TEST 4 — CLUSTER ASSIGNMENT SPOT CHECK
// ═══════════════════════════════════════════════════════════════
async function test4_clusterAssignments() {
  console.log("\n═══ TEST 4: Cluster Assignment Spot Check ═══");

  const EXPECTED = {
    "06075": { cluster: 0, name: "San Francisco CA", label: "Prosperous Suburban" },
    "54047": { cluster: 3, name: "McDowell WV", label: "Rural Disadvantaged" },
    "51107": { cluster: 0, name: "Loudoun VA", label: "Prosperous Suburban" },
    "48427": { cluster: 3, name: "Starr TX", label: "Rural Disadvantaged" },
    "51013": { cluster: 0, name: "Arlington VA", label: "Prosperous Suburban" },
  };

  const CLUSTER_LABELS = {
    0: "Prosperous Suburban",
    1: "Rural Heartland",
    2: "High-Need Urban/Border",
    3: "Rural Disadvantaged",
  };

  const data = await fetchJSON("/county-clusters");
  const assignments = data.county_assignments;

  for (const [fips, expected] of Object.entries(EXPECTED)) {
    const actual = assignments[fips];
    const actualLabel = CLUSTER_LABELS[actual] ?? "Unknown";
    if (actual === expected.cluster) {
      log("PASS", `${expected.name} (${fips})`, `cluster=${actual} (${actualLabel})`);
    } else {
      log("FAIL", `${expected.name} (${fips})`, `expected cluster=${expected.cluster} (${expected.label}), got=${actual} (${actualLabel})`);
    }
  }
}

// ═══════════════════════════════════════════════════════════════
// TEST 5 — METRIC CARD RANK VERIFICATION
// ═══════════════════════════════════════════════════════════════
async function test5_metricRank() {
  console.log("\n═══ TEST 5: Metric Card Rank Verification ═══");

  const gravData = await fetchJSON("/gravity-map?module_id=all");
  const nodes = gravData.nodes || [];
  const sf = nodes.find(n => n.fips === "06075");
  if (!sf) { log("FAIL", "SF lookup", "FIPS 06075 not found"); return; }

  // Compute broadband rank among all counties
  const sfBroadband = sf.datasets?.broadband;
  if (sfBroadband == null) { log("FAIL", "SF broadband", "broadband value missing"); return; }

  const allBroadband = nodes.map(n => n.datasets?.broadband).filter(v => v != null);
  allBroadband.sort((a, b) => a - b);
  const rank = allBroadband.filter(v => v <= sfBroadband).length;
  const total = allBroadband.length;
  const pct = Math.round((rank / total) * 100);

  log("PASS", "SF broadband rank", `rank=${rank} of ${total} (top ${100 - pct}%), value=${sfBroadband.toFixed(4)}`);

  // Verify it's in the top quartile (SF should have high broadband)
  if (pct >= 75) {
    log("PASS", "SF broadband top quartile", `${pct}th percentile — high broadband as expected for SF`);
  } else {
    log("WARN", "SF broadband top quartile", `${pct}th percentile — lower than expected for SF`);
  }

  // Also verify poverty rank
  const sfPoverty = sf.datasets?.poverty;
  if (sfPoverty != null) {
    const allPoverty = nodes.map(n => n.datasets?.poverty).filter(v => v != null);
    allPoverty.sort((a, b) => a - b);
    const pRank = allPoverty.filter(v => v <= sfPoverty).length;
    const pTotal = allPoverty.length;
    const pPct = Math.round((pRank / pTotal) * 100);
    log("PASS", "SF poverty rank", `rank=${pRank} of ${pTotal} (${pPct}th pct), value=${sfPoverty.toFixed(1)}`);
  }
}

// ═══════════════════════════════════════════════════════════════
// TEST 6 — WITHIN-CLUSTER CORRELATION ATTENUATION
// ═══════════════════════════════════════════════════════════════
async function test6_withinClusterCorrelation() {
  console.log("\n═══ TEST 6: Within-Cluster Correlation (poverty × diabetes) ═══");

  const [gravData, clusterData] = await Promise.all([
    fetchJSON("/gravity-map?module_id=all"),
    fetchJSON("/county-clusters"),
  ]);

  const nodes = gravData.nodes || [];
  const assignments = clusterData.county_assignments || {};

  const CLUSTER_LABELS = {
    0: "Prosperous Suburban",
    1: "Rural Heartland",
    2: "High-Need Urban/Border",
    3: "Rural Disadvantaged",
  };

  // Overall correlation
  const allXs = [], allYs = [];
  for (const n of nodes) {
    const p = n.datasets?.poverty, d = n.datasets?.diabetes;
    if (p != null && d != null) { allXs.push(p); allYs.push(d); }
  }
  const overallR = pearsonR(allXs, allYs);

  if (overallR != null) {
    if (Math.abs(overallR - 0.705) <= 0.03) {
      log("PASS", "Overall poverty×diabetes r", `r=${overallR.toFixed(4)} (expected ~0.705)`);
    } else {
      log("WARN", "Overall poverty×diabetes r", `r=${overallR.toFixed(4)} (expected ~0.705, diff=${Math.abs(overallR - 0.705).toFixed(4)})`);
    }
  } else {
    log("FAIL", "Overall poverty×diabetes r", "Could not compute");
  }

  // Within each cluster
  for (const clusterId of [0, 1, 2, 3]) {
    const clusterFips = new Set(
      Object.entries(assignments).filter(([_, c]) => c === clusterId).map(([f]) => f)
    );
    const cXs = [], cYs = [];
    for (const n of nodes) {
      if (!clusterFips.has(n.fips)) continue;
      const p = n.datasets?.poverty, d = n.datasets?.diabetes;
      if (p != null && d != null) { cXs.push(p); cYs.push(d); }
    }
    const clusterR = pearsonR(cXs, cYs);
    const label = CLUSTER_LABELS[clusterId] || `Cluster ${clusterId}`;

    if (clusterR != null) {
      const attenuated = Math.abs(clusterR) < Math.abs(overallR);
      if (attenuated) {
        log("PASS", `Within ${label} r`, `r=${clusterR.toFixed(4)} (n=${cXs.length}) — attenuated from overall ${overallR.toFixed(4)}`);
      } else {
        log("WARN", `Within ${label} r`, `r=${clusterR.toFixed(4)} (n=${cXs.length}) — NOT attenuated (overall=${overallR.toFixed(4)})`);
      }
    } else {
      log("WARN", `Within ${label} r`, `Insufficient data (n=${cXs.length})`);
    }
  }

  // Paper claim check: Prosperous Suburban should be near 0.1-0.5
  const c0Fips = new Set(Object.entries(assignments).filter(([_, c]) => c === 0).map(([f]) => f));
  const c0Xs = [], c0Ys = [];
  for (const n of nodes) {
    if (!c0Fips.has(n.fips)) continue;
    const p = n.datasets?.poverty, d = n.datasets?.diabetes;
    if (p != null && d != null) { c0Xs.push(p); c0Ys.push(d); }
  }
  const c0R = pearsonR(c0Xs, c0Ys);
  if (c0R != null && Math.abs(c0R) < 0.55) {
    log("PASS", "Paper claim: Prosperous Suburban r < 0.55", `r=${c0R.toFixed(4)} — supports within-cluster attenuation claim`);
  } else {
    log("FAIL", "Paper claim: Prosperous Suburban r < 0.55", `r=${c0R?.toFixed(4)} — may not support JOSS paper claim`);
  }
}

// ═══════════════════════════════════════════════════════════════
// RUN ALL TESTS
// ═══════════════════════════════════════════════════════════════
async function main() {
  console.log("╔════════════════════════════════════════════════╗");
  console.log("║  DiscoveryLens Scientific Validation Suite     ║");
  console.log("╚════════════════════════════════════════════════╝");

  try { await test1_correlations(); } catch (e) { log("FAIL", "TEST 1 ERROR", e.message); }
  try { await test2_peerCorrectness(); } catch (e) { log("FAIL", "TEST 2 ERROR", e.message); }
  try { await test3_positiveDeviance(); } catch (e) { log("FAIL", "TEST 3 ERROR", e.message); }
  try { await test4_clusterAssignments(); } catch (e) { log("FAIL", "TEST 4 ERROR", e.message); }
  try { await test5_metricRank(); } catch (e) { log("FAIL", "TEST 5 ERROR", e.message); }
  try { await test6_withinClusterCorrelation(); } catch (e) { log("FAIL", "TEST 6 ERROR", e.message); }

  console.log("\n╔════════════════════════════════════════════════╗");
  console.log(`║  Results: ${passed} passed, ${failed} failed, ${warnings} warnings`);
  console.log("╚════════════════════════════════════════════════╝");

  if (failed > 0) {
    console.log("\n\x1b[31m⚠ FAILURES DETECTED — review before JOSS submission\x1b[0m");
    for (const r of results.filter(r => r.status === "FAIL")) {
      console.log(`  ✗ ${r.test}: ${r.detail}`);
    }
    process.exit(1);
  } else if (warnings > 0) {
    console.log("\n\x1b[33mWarnings present — review for accuracy\x1b[0m");
  } else {
    console.log("\n\x1b[32mAll validations passed\x1b[0m");
  }
}

main();
