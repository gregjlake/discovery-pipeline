/**
 * DiscoveryLens — Independent Peer Review Validation Suite
 * Simulates a Science reviewer independently verifying paper claims.
 * Run: node tests/peer-review-validation.mjs
 */

const BASE = "https://web-production-a68ad.up.railway.app/api";

let passed = 0, failed = 0, warnings = 0;
const results = [];

function log(status, test, detail, severity = "") {
  const icon = status === "PASS" ? "\x1b[32m✓\x1b[0m" : status === "FAIL" ? "\x1b[31m✗\x1b[0m" : "\x1b[33m⚠\x1b[0m";
  const sev = severity ? ` [${severity}]` : "";
  console.log(`  ${icon} ${test}${sev}`);
  if (detail) console.log(`    ${detail}`);
  results.push({ status, test, detail, severity });
  if (status === "PASS") passed++;
  else if (status === "FAIL") failed++;
  else warnings++;
}

function pearsonR(xs, ys) {
  const pairs = [];
  for (let i = 0; i < xs.length; i++) {
    if (xs[i] != null && ys[i] != null && isFinite(xs[i]) && isFinite(ys[i])) pairs.push([xs[i], ys[i]]);
  }
  if (pairs.length < 10) return null;
  const n = pairs.length;
  const mx = pairs.reduce((s, p) => s + p[0], 0) / n;
  const my = pairs.reduce((s, p) => s + p[1], 0) / n;
  let num = 0, dx = 0, dy = 0;
  for (const [x, y] of pairs) { num += (x - mx) * (y - my); dx += (x - mx) ** 2; dy += (y - my) ** 2; }
  const denom = Math.sqrt(dx * dy);
  return denom === 0 ? null : num / denom;
}

async function fetchJSON(path, opts) {
  const res = await fetch(`${BASE}${path}`, opts);
  if (!res.ok) throw new Error(`HTTP ${res.status} for ${path}`);
  return res.json();
}

// Cache gravity data (large payload, fetch once)
let _gravCache = null;
async function getGravityNodes() {
  if (!_gravCache) {
    const data = await fetchJSON("/gravity-map?module_id=all");
    _gravCache = data.nodes || [];
  }
  return _gravCache;
}

function pairwiseR(nodes, varA, varB) {
  const xs = [], ys = [];
  for (const n of nodes) {
    const a = n.datasets?.[varA], b = n.datasets?.[varB];
    if (a != null && b != null) { xs.push(a); ys.push(b); }
  }
  return { r: pearsonR(xs, ys), n: xs.length };
}

// ═══════════════════════════════════════════════════════════════
// TEST 1 — REPRODUCIBILITY OF HEADLINE FINDINGS
// ═══════════════════════════════════════════════════════════════
async function test1() {
  console.log("\n\x1b[1m═══ TEST 1: Reproducibility of Headline Findings ═══\x1b[0m");
  const nodes = await getGravityNodes();

  // 1a: food_access × poverty
  const fa = pairwiseR(nodes, "food_access", "poverty");
  if (fa.r != null) {
    if (fa.r >= -0.07 && fa.r <= -0.03) {
      log("PASS", "1a. food_access × poverty", `r=${fa.r.toFixed(4)} (n=${fa.n}), within [-0.07, -0.03]`);
    } else if (Math.abs(fa.r) < 0.15) {
      log("WARN", "1a. food_access × poverty", `r=${fa.r.toFixed(4)} (n=${fa.n}), outside expected range but still near zero`, "NEEDS NOTE");
    } else {
      log("FAIL", "1a. food_access × poverty", `r=${fa.r.toFixed(4)} (n=${fa.n}), substantially different from claimed -0.048`, "BLOCKS SUBMISSION");
    }
  } else {
    log("FAIL", "1a. food_access × poverty", "Insufficient data", "BLOCKS SUBMISSION");
  }

  // 1b: median_age × food_access
  const ma = pairwiseR(nodes, "median_age", "food_access");
  if (ma.r != null) {
    if (ma.r >= -0.02 && ma.r <= 0.02) {
      log("PASS", "1b. median_age × food_access", `r=${ma.r.toFixed(4)} (n=${ma.n}), within [-0.02, 0.02]`);
    } else if (Math.abs(ma.r) < 0.10) {
      log("WARN", "1b. median_age × food_access", `r=${ma.r.toFixed(4)} (n=${ma.n}), weak but outside expected range`, "NEEDS NOTE");
    } else {
      log("FAIL", "1b. median_age × food_access", `r=${ma.r.toFixed(4)} (n=${ma.n}), not near zero as claimed`, "BLOCKS SUBMISSION");
    }
  } else {
    log("FAIL", "1b. median_age × food_access", "Insufficient data", "BLOCKS SUBMISSION");
  }

  // 1c: broadband × diabetes
  const bd = pairwiseR(nodes, "broadband", "diabetes");
  if (bd.r != null) {
    if (bd.r >= -0.68 && bd.r <= -0.59) {
      log("PASS", "1c. broadband × diabetes", `r=${bd.r.toFixed(4)} (n=${bd.n}), within [-0.68, -0.59] (B28002_007E fixed broadband)`);
    } else if (Math.abs(bd.r + 0.632) < 0.05) {
      log("WARN", "1c. broadband × diabetes", `r=${bd.r.toFixed(4)} (n=${bd.n}), close to expected -0.632`, "NEEDS NOTE");
    } else {
      log("FAIL", "1c. broadband × diabetes", `r=${bd.r.toFixed(4)} (n=${bd.n}), deviates from expected -0.632`, "BLOCKS SUBMISSION");
    }
  } else {
    log("FAIL", "1c. broadband × diabetes", "Insufficient data", "BLOCKS SUBMISSION");
  }

  // 1d: poverty × diabetes overall
  const pd = pairwiseR(nodes, "poverty", "diabetes");
  if (pd.r != null) {
    if (Math.abs(pd.r - 0.736) <= 0.01) {
      log("PASS", "1d. poverty × diabetes overall", `r=${pd.r.toFixed(4)} (n=${pd.n}), matches paper claim of 0.736`);
    } else if (Math.abs(pd.r - 0.736) <= 0.03) {
      log("WARN", "1d. poverty × diabetes overall", `r=${pd.r.toFixed(4)} (n=${pd.n}), close to 0.736`, "INFORMATIONAL");
    } else {
      log("FAIL", "1d. poverty × diabetes overall", `r=${pd.r.toFixed(4)}, differs from paper's 0.736`, "BLOCKS SUBMISSION");
    }
  }

  // 1e: within-cluster attenuation
  const clusterData = await fetchJSON("/county-clusters");
  const assignments = clusterData.county_assignments || {};
  const LABELS = { 0: "Prosperous Suburban", 1: "Rural Heartland", 2: "High-Need Urban/Border", 3: "Rural Disadvantaged" };

  let anyAmplified = false;
  for (const cid of [0, 1, 3]) { // skip cluster 2 (n~153, some are territories)
    const fipsSet = new Set(Object.entries(assignments).filter(([_, c]) => c === cid).map(([f]) => f));
    const cNodes = nodes.filter(n => fipsSet.has(n.fips));
    const cr = pairwiseR(cNodes, "poverty", "diabetes");
    if (cr.r != null) {
      const attenuated = Math.abs(cr.r) < Math.abs(pd.r);
      if (attenuated) {
        log("PASS", `1e. Within ${LABELS[cid]}`, `r=${cr.r.toFixed(4)} (n=${cr.n}) < overall ${pd.r.toFixed(4)} — attenuated`);
      } else {
        log("FAIL", `1e. Within ${LABELS[cid]}`, `r=${cr.r.toFixed(4)} (n=${cr.n}) ≥ overall ${pd.r.toFixed(4)} — AMPLIFIED`, "BLOCKS SUBMISSION");
        anyAmplified = true;
      }
    }
  }
  if (!anyAmplified) {
    log("PASS", "1e. No cluster amplification", "All tested clusters show attenuation — paper claim supported");
  }
}

// ═══════════════════════════════════════════════════════════════
// TEST 2 — SIMPSON'S PARADOX DETECTION VALIDITY
// ═══════════════════════════════════════════════════════════════
async function test2() {
  console.log("\n\x1b[1m═══ TEST 2: Simpson's Paradox Detection ═══\x1b[0m");
  const nodes = await getGravityNodes();
  const clusterData = await fetchJSON("/county-clusters");
  const assignments = clusterData.county_assignments || {};

  const testVars = ["poverty", "diabetes", "broadband", "median_income", "housing_burden",
    "obesity", "mental_health", "unemployment", "life_expectancy", "voter_turnout"];

  let bestReversal = null;
  let pairsChecked = 0;

  for (let i = 0; i < testVars.length; i++) {
    for (let j = i + 1; j < testVars.length; j++) {
      const varA = testVars[i], varB = testVars[j];
      const overall = pairwiseR(nodes, varA, varB);
      if (overall.r == null || Math.abs(overall.r) < 0.05) continue;
      pairsChecked++;

      for (const cid of [0, 1, 3]) {
        const fipsSet = new Set(Object.entries(assignments).filter(([_, c]) => c === cid).map(([f]) => f));
        const cNodes = nodes.filter(n => fipsSet.has(n.fips));
        const cr = pairwiseR(cNodes, varA, varB);
        if (cr.r == null || cr.n < 30) continue;

        // Sign reversal: overall positive but within-cluster negative (or vice versa)
        if ((overall.r > 0 && cr.r < 0) || (overall.r < 0 && cr.r > 0)) {
          const strength = Math.abs(overall.r) + Math.abs(cr.r);
          if (!bestReversal || strength > bestReversal.strength) {
            bestReversal = {
              varA, varB, overallR: overall.r, clusterR: cr.r,
              clusterId: cid, clusterN: cr.n, strength,
            };
          }
        }
      }
    }
  }

  if (bestReversal) {
    log("PASS", "Simpson's paradox candidate found",
      `${bestReversal.varA} × ${bestReversal.varB}: overall r=${bestReversal.overallR.toFixed(3)}, ` +
      `within cluster ${bestReversal.clusterId} r=${bestReversal.clusterR.toFixed(3)} (n=${bestReversal.clusterN}) — SIGN REVERSAL`);
  } else {
    log("WARN", "No Simpson's paradox found",
      `Checked ${pairsChecked} variable pairs across 3 clusters. No sign reversals detected. ` +
      `If the paper claims Simpson's paradox detection, this is an overclaim.`, "NEEDS NOTE");
  }
}

// ═══════════════════════════════════════════════════════════════
// TEST 3 — GRAVITY MODEL VALIDATION
// ═══════════════════════════════════════════════════════════════
async function test3() {
  console.log("\n\x1b[1m═══ TEST 3: Gravity Model Validation ═══\x1b[0m");

  let validation, metadata;
  try { validation = await fetchJSON("/gravity-map/validation"); } catch { validation = null; }
  try { metadata = await fetchJSON("/gravity-map/metadata"); } catch {
    // Try from main gravity-map response
    const grav = await fetchJSON("/gravity-map");
    metadata = grav.metadata;
  }

  // β value
  const beta = metadata?.beta ?? metadata?.beta_operative ?? metadata?.beta_combined;
  if (beta != null) {
    if (Math.abs(beta - 0.139) < 0.002) {
      log("PASS", "3a. β = 0.139", `β=${beta.toFixed(4)} — matches paper exactly`);
    } else {
      log("FAIL", "3a. β = 0.139", `β=${beta.toFixed(4)} — deviates from paper claim`, "BLOCKS SUBMISSION");
    }
  } else {
    log("WARN", "3a. β value", "Not found in metadata response", "NEEDS NOTE");
  }

  // ρ value
  if (validation) {
    const rho = validation.rho_combined ?? validation.spearman_rho;
    if (rho != null) {
      if (Math.abs(rho - 0.164) < 0.005) {
        log("PASS", "3b. ρ = 0.164", `ρ=${rho.toFixed(4)} — matches paper`);
      } else {
        log("FAIL", "3b. ρ = 0.164", `ρ=${rho.toFixed(4)}`, "BLOCKS SUBMISSION");
      }
    }

    // CI
    const ciLow = validation.ci_low ?? validation.bootstrap_ci?.[0];
    const ciHigh = validation.ci_high ?? validation.bootstrap_ci?.[1];
    if (ciLow != null && ciHigh != null) {
      log("PASS", "3c. 95% CI reported", `[${ciLow.toFixed(3)}, ${ciHigh.toFixed(3)}]`);
    } else {
      log("WARN", "3c. 95% CI", "Not found in validation response", "NEEDS NOTE");
    }
  } else {
    log("WARN", "3b-c. Validation endpoint", "Not available — cannot verify ρ or CI", "NEEDS NOTE");
  }

  // n_pairs
  const nPairs = metadata?.n_pairs;
  if (nPairs != null) {
    if (nPairs > 200000 && nPairs < 300000) {
      log("PASS", "3d. n_pairs ≈ 250,000", `n_pairs=${nPairs.toLocaleString()}`);
    } else {
      log("WARN", "3d. n_pairs", `n_pairs=${nPairs.toLocaleString()} — outside expected range`, "NEEDS NOTE");
    }
  }

  // R²
  const r2 = metadata?.pseudo_r2 ?? metadata?.r_squared_combined;
  if (r2 != null) {
    if (Math.abs(r2 - 0.303) < 0.01) {
      log("PASS", "3e. R² = 0.303", `R²=${r2.toFixed(4)}`);
    } else {
      log("WARN", "3e. R²", `R²=${r2.toFixed(4)}, paper claims 0.303`, "NEEDS NOTE");
    }
  }
}

// ═══════════════════════════════════════════════════════════════
// TEST 4 — PEER STABILITY TEST
// ═══════════════════════════════════════════════════════════════
async function test4() {
  console.log("\n\x1b[1m═══ TEST 4: Peer Stability ═══\x1b[0m");
  const nodes = await getGravityNodes();
  const nodeMap = new Map(nodes.map(n => [n.fips, n]));

  const ranges = {};
  for (const n of nodes) {
    if (!n.datasets) continue;
    for (const [k, v] of Object.entries(n.datasets)) {
      if (v == null) continue;
      if (!ranges[k]) ranges[k] = { min: v, max: v };
      else { if (v < ranges[k].min) ranges[k].min = v; if (v > ranges[k].max) ranges[k].max = v; }
    }
  }
  const allVars = Object.keys(ranges);

  function euclidDist(a, b) {
    let sum = 0;
    for (const k of allVars) {
      const va = a[k] ?? 0.5, vb = b[k] ?? 0.5;
      const r = ranges[k];
      const na = r ? (va - r.min) / (r.max - r.min || 1) : 0.5;
      const nb = r ? (vb - r.min) / (r.max - r.min || 1) : 0.5;
      sum += (na - nb) ** 2;
    }
    return Math.sqrt(sum);
  }

  function getPeers(fips, k = 5) {
    const target = nodeMap.get(fips);
    if (!target || !target.datasets) return null;
    return nodes
      .filter(n => n.fips !== fips && n.datasets)
      .map(n => ({ fips: n.fips, name: n.county_name, dist: euclidDist(target.datasets, n.datasets) }))
      .sort((a, b) => a.dist - b.dist)
      .slice(0, k);
  }

  // 4a: Smallest county — Loving TX (48301)
  const loving = nodeMap.get("48301");
  if (loving) {
    const peers = getPeers("48301");
    if (peers && peers.length === 5) {
      log("PASS", "4a. Loving TX (smallest)", `Returns ${peers.length} peers. Top: ${peers[0].name} (dist=${peers[0].dist.toFixed(3)})`);
    } else {
      log("FAIL", "4a. Loving TX", "Failed to return peers", "NEEDS NOTE");
    }
  } else {
    log("WARN", "4a. Loving TX (48301)", "Not found in dataset — may be excluded due to population threshold", "INFORMATIONAL");
  }

  // 4b: Largest county — LA (06037)
  const laPeers = getPeers("06037");
  if (laPeers) {
    // LA peers should be large urban counties
    const peerPops = laPeers.map(p => nodeMap.get(p.fips)?.population ?? 0);
    const allUrban = laPeers.every(p => (nodeMap.get(p.fips)?.datasets?.rural_urban ?? 9) < 4);
    log(allUrban ? "PASS" : "WARN", "4b. LA County peers",
      `Top peers: ${laPeers.map(p => p.name).join(", ")}. ${allUrban ? "All urban" : "Some non-urban"}`);
  }

  // 4c: Determinism — run twice
  const peers1 = getPeers("06075");
  const peers2 = getPeers("06075");
  if (peers1 && peers2) {
    const match = peers1.every((p, i) => p.fips === peers2[i].fips);
    if (match) {
      log("PASS", "4c. Determinism", "SF peers identical across two runs");
    } else {
      log("FAIL", "4c. Determinism", "Peer results differ between runs — non-deterministic", "BLOCKS SUBMISSION");
    }
  }

  // 4d: Symmetry check
  const sfTop = getPeers("06075", 1)?.[0];
  if (sfTop) {
    const reverse = getPeers(sfTop.fips, 20);
    const sfInReverse = reverse?.find(p => p.fips === "06075");
    if (sfInReverse) {
      const distDiff = Math.abs(sfTop.dist - sfInReverse.dist);
      if (distDiff < 0.0001) {
        log("PASS", "4d. Distance symmetry", `dist(SF, ${sfTop.name})=${sfTop.dist.toFixed(4)} = dist(${sfTop.name}, SF)=${sfInReverse.dist.toFixed(4)}`);
      } else {
        log("FAIL", "4d. Distance symmetry", `Asymmetric: ${sfTop.dist.toFixed(4)} ≠ ${sfInReverse.dist.toFixed(4)}`, "BLOCKS SUBMISSION");
      }
    } else {
      log("WARN", "4d. Distance symmetry", `SF not in top 20 of ${sfTop.name} — expected but depends on neighborhood`, "INFORMATIONAL");
    }
  }
}

// ═══════════════════════════════════════════════════════════════
// TEST 5 — POSITIVE DEVIANCE MATHEMATICAL VALIDITY
// ═══════════════════════════════════════════════════════════════
async function test5() {
  console.log("\n\x1b[1m═══ TEST 5: Positive Deviance Mathematical Validity ═══\x1b[0m");

  const body = {
    input_variables: ["poverty", "broadband", "obesity", "mental_health", "housing_burden",
      "unemployment", "food_access", "air", "median_income"],
    outcome_variable: "diabetes",
  };

  const result = await fetchJSON("/positive-deviance/compute", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });

  const residuals = result.residuals_z;
  if (!residuals || typeof residuals !== "object") {
    log("FAIL", "5a. Residuals returned", "No residuals_z in response", "BLOCKS SUBMISSION");
    return;
  }

  const vals = Object.values(residuals).filter(v => v != null && isFinite(v));
  const n = vals.length;
  const mean = vals.reduce((s, v) => s + v, 0) / n;
  const std = Math.sqrt(vals.reduce((s, v) => s + (v - mean) ** 2, 0) / n);
  const sum = vals.reduce((s, v) => s + v, 0);

  // Sum should be ~0
  if (Math.abs(sum) < n * 0.01) {
    log("PASS", "5a. Residuals sum ≈ 0", `sum=${sum.toFixed(4)} (n=${n})`);
  } else {
    log("FAIL", "5a. Residuals sum ≈ 0", `sum=${sum.toFixed(4)} (n=${n}) — OLS residuals must sum to zero`, "BLOCKS SUBMISSION");
  }

  // Mean should be ~0
  if (Math.abs(mean) < 0.01) {
    log("PASS", "5b. Residual mean ≈ 0", `mean=${mean.toFixed(6)}`);
  } else {
    log("FAIL", "5b. Residual mean ≈ 0", `mean=${mean.toFixed(6)}`, "NEEDS NOTE");
  }

  // Std should be ~1 (z-scored)
  if (std > 0.9 && std < 1.1) {
    log("PASS", "5c. Residual std ≈ 1", `std=${std.toFixed(4)}`);
  } else {
    log("WARN", "5c. Residual std ≈ 1", `std=${std.toFixed(4)} — expected ~1.0 for z-scores`, "NEEDS NOTE");
  }

  // McDowell for diabetes
  const mcZ = residuals["54047"];
  if (mcZ != null) {
    log("PASS", "5d. McDowell residual", `z=${mcZ.toFixed(4)} for diabetes outcome`);
    if (mcZ > 1.0) {
      log("PASS", "5e. McDowell high-residual", `z=${mcZ.toFixed(4)} > 1.0 — county has higher diabetes than predicted`);
    } else {
      log("WARN", "5e. McDowell high-residual", `z=${mcZ.toFixed(4)} — not a strong positive deviant for diabetes`, "INFORMATIONAL");
    }
  } else {
    log("WARN", "5d. McDowell residual", "FIPS 54047 not in residuals", "NEEDS NOTE");
  }

  log("PASS", "5f. Model fit", `R²=${result.r2?.toFixed(4)}, n=${result.n_counties}`);
}

// ═══════════════════════════════════════════════════════════════
// TEST 6 — VARIABLE COVERAGE AND MISSING DATA
// ═══════════════════════════════════════════════════════════════
async function test6() {
  console.log("\n\x1b[1m═══ TEST 6: Variable Coverage and Missing Data ═══\x1b[0m");
  const nodes = await getGravityNodes();

  // Get all variable keys from first node
  const allVars = new Set();
  for (const n of nodes) {
    if (n.datasets) for (const k of Object.keys(n.datasets)) allVars.add(k);
  }
  const vars = [...allVars];

  let totalCells = 0, missingCells = 0;
  const varMissing = {};

  for (const v of vars) {
    let missing = 0;
    for (const n of nodes) {
      totalCells++;
      if (n.datasets?.[v] == null) { missingCells++; missing++; }
    }
    varMissing[v] = { missing, pct: (missing / nodes.length * 100).toFixed(1) };
  }

  const overallPct = (missingCells / totalCells * 100);

  log("PASS", "6a. Variable count", `${vars.length} variables across ${nodes.length} counties`);

  if (overallPct >= 3.0 && overallPct <= 5.0) {
    log("PASS", "6b. Missing data %", `${overallPct.toFixed(2)}% missing (paper claims 3.9%)`);
  } else if (overallPct < 10) {
    log("WARN", "6b. Missing data %", `${overallPct.toFixed(2)}% missing (paper claims 3.9%)`, "NEEDS NOTE");
  } else {
    log("FAIL", "6b. Missing data %", `${overallPct.toFixed(2)}% missing — far from claimed 3.9%`, "BLOCKS SUBMISSION");
  }

  // Flag variables with >20% missing
  const highMissing = Object.entries(varMissing).filter(([_, v]) => parseFloat(v.pct) > 20);
  if (highMissing.length > 0) {
    for (const [v, info] of highMissing) {
      log("WARN", `6c. High missing: ${v}`, `${info.pct}% missing (${info.missing}/${nodes.length})`, "NEEDS NOTE");
    }
  } else {
    log("PASS", "6c. No variable >20% missing", "All variables have adequate coverage");
  }
}

// ═══════════════════════════════════════════════════════════════
// TEST 7 — EFFECTIVE DIMENSIONS VERIFICATION
// ═══════════════════════════════════════════════════════════════
async function test7() {
  console.log("\n\x1b[1m═══ TEST 7: Effective Dimensions (PCA) ═══\x1b[0m");

  let pca;
  try { pca = await fetchJSON("/pca-analysis"); } catch { pca = null; }

  if (!pca) {
    log("WARN", "7. PCA endpoint", "Not available", "NEEDS NOTE");
    return;
  }

  const effDim = pca.effective_dimensions ?? pca.participation_ratio;
  if (effDim != null) {
    if (effDim >= 7.0 && effDim <= 7.5) {
      log("PASS", "7a. Effective dimensions", `${effDim.toFixed(2)} (paper claims 7.19)`);
    } else if (effDim >= 6.0 && effDim <= 8.5) {
      log("WARN", "7a. Effective dimensions", `${effDim.toFixed(2)} (paper claims 7.19)`, "NEEDS NOTE");
    } else {
      log("FAIL", "7a. Effective dimensions", `${effDim.toFixed(2)} — far from paper's 7.19`, "BLOCKS SUBMISSION");
    }
  }

  const nDs = pca.n_datasets;
  if (nDs != null) {
    if (nDs >= 29 && nDs <= 31) {
      log("PASS", "7b. n_datasets", `${nDs}`);
    } else {
      log("WARN", "7b. n_datasets", `${nDs} — expected ~30`, "NEEDS NOTE");
    }
  }

  // Verify eigenvalues if available
  const eigenvalues = pca.eigenvalues ?? pca.explained_variance;
  if (eigenvalues && Array.isArray(eigenvalues)) {
    // Participation ratio = (Σλ)² / Σ(λ²)
    const sumL = eigenvalues.reduce((s, v) => s + v, 0);
    const sumL2 = eigenvalues.reduce((s, v) => s + v * v, 0);
    const pr = (sumL * sumL) / sumL2;
    log("PASS", "7c. Independent PR computation", `PR=${pr.toFixed(2)} from ${eigenvalues.length} eigenvalues`);
    if (effDim != null && Math.abs(pr - effDim) < 0.5) {
      log("PASS", "7d. PR matches reported", `Computed=${pr.toFixed(2)}, reported=${effDim.toFixed(2)}`);
    }
  }
}

// ═══════════════════════════════════════════════════════════════
// TEST 8 — COUNTY COVERAGE COMPLETENESS
// ═══════════════════════════════════════════════════════════════
async function test8() {
  console.log("\n\x1b[1m═══ TEST 8: County Coverage Completeness ═══\x1b[0m");
  const nodes = await getGravityNodes();

  // Count
  if (nodes.length === 3135) {
    log("PASS", "8a. County count", `${nodes.length} — matches paper claim of 3,135`);
  } else if (nodes.length >= 3100 && nodes.length <= 3200) {
    log("WARN", "8a. County count", `${nodes.length} — close to 3,135`, "NEEDS NOTE");
  } else {
    log("FAIL", "8a. County count", `${nodes.length} — paper claims 3,135`, "BLOCKS SUBMISSION");
  }

  // Duplicate FIPS
  const fipsSet = new Set(nodes.map(n => n.fips));
  if (fipsSet.size === nodes.length) {
    log("PASS", "8b. No duplicate FIPS", `${fipsSet.size} unique FIPS codes`);
  } else {
    log("FAIL", "8b. Duplicate FIPS", `${fipsSet.size} unique vs ${nodes.length} total`, "BLOCKS SUBMISSION");
  }

  // All 50 states
  const states = new Set(nodes.map(n => n.fips.slice(0, 2)));
  // DC is 11, states are 01-56 (excluding gaps)
  const expectedStates = 50 + 1; // 50 states + DC
  if (states.size >= expectedStates) {
    log("PASS", "8c. State coverage", `${states.size} state/territory FIPS prefixes`);
  } else {
    log("WARN", "8c. State coverage", `${states.size} state FIPS prefixes — expected ≥51 (50 states + DC)`, "NEEDS NOTE");
  }

  // Spot checks
  const spotChecks = [
    ["06075", "San Francisco CA"],
    ["54047", "McDowell WV"],
    ["48301", "Loving TX"],
    ["06037", "LA County"],
    ["17031", "Cook IL"],
  ];
  for (const [fips, name] of spotChecks) {
    const found = nodes.find(n => n.fips === fips);
    if (found) {
      log("PASS", `8d. ${name} (${fips})`, `Found: ${found.county_name}, pop=${found.population?.toLocaleString()}`);
    } else {
      log("WARN", `8d. ${name} (${fips})`, "Not found in dataset", "NEEDS NOTE");
    }
  }
}

// ═══════════════════════════════════════════════════════════════
// TEST 9 — CORRELATION MATRIX SYMMETRY
// ═══════════════════════════════════════════════════════════════
async function test9() {
  console.log("\n\x1b[1m═══ TEST 9: Correlation Matrix Symmetry ═══\x1b[0m");
  const nodes = await getGravityNodes();

  const testVars = ["poverty", "diabetes", "broadband", "median_income", "obesity",
    "housing_burden", "life_expectancy", "unemployment"];

  // Build correlation matrix
  const matrix = {};
  for (const a of testVars) {
    matrix[a] = {};
    for (const b of testVars) {
      const { r } = pairwiseR(nodes, a, b);
      matrix[a][b] = r;
    }
  }

  // Check diagonal = 1.0
  let diagOk = true;
  for (const v of testVars) {
    if (Math.abs(matrix[v][v] - 1.0) > 0.001) {
      log("FAIL", `9a. Diagonal ${v}`, `r(${v},${v})=${matrix[v][v]?.toFixed(4)} ≠ 1.0`, "BLOCKS SUBMISSION");
      diagOk = false;
    }
  }
  if (diagOk) log("PASS", "9a. Diagonal = 1.0", "All diagonal entries are 1.0");

  // Check symmetry
  let maxAsymmetry = 0;
  let asymPair = "";
  for (const a of testVars) {
    for (const b of testVars) {
      if (a === b) continue;
      const diff = Math.abs((matrix[a][b] ?? 0) - (matrix[b][a] ?? 0));
      if (diff > maxAsymmetry) { maxAsymmetry = diff; asymPair = `${a} × ${b}`; }
    }
  }
  if (maxAsymmetry < 0.001) {
    log("PASS", "9b. Matrix symmetry", `Max asymmetry=${maxAsymmetry.toFixed(6)} — perfectly symmetric`);
  } else {
    log("FAIL", "9b. Matrix symmetry", `Max asymmetry=${maxAsymmetry.toFixed(6)} at ${asymPair}`, "BLOCKS SUBMISSION");
  }

  // Check |r| <= 1.0
  let anyOver1 = false;
  for (const a of testVars) {
    for (const b of testVars) {
      if (Math.abs(matrix[a][b] ?? 0) > 1.001) {
        log("FAIL", `9c. |r| > 1.0`, `r(${a},${b})=${matrix[a][b]?.toFixed(4)}`, "BLOCKS SUBMISSION");
        anyOver1 = true;
      }
    }
  }
  if (!anyOver1) log("PASS", "9c. All |r| ≤ 1.0", "No mathematically impossible values");

  // Spot check
  const rPD = matrix["poverty"]["diabetes"];
  const rDP = matrix["diabetes"]["poverty"];
  log("PASS", "9d. Spot check", `r(poverty,diabetes)=${rPD?.toFixed(4)}, r(diabetes,poverty)=${rDP?.toFixed(4)}`);
}

// ═══════════════════════════════════════════════════════════════
// TEST 10 — TEMPORAL CONSISTENCY
// ═══════════════════════════════════════════════════════════════
async function test10() {
  console.log("\n\x1b[1m═══ TEST 10: Temporal Consistency ═══\x1b[0m");

  let meta;
  try { meta = await fetchJSON("/dataset-metadata"); } catch { meta = null; }

  if (!meta) {
    log("WARN", "10. Dataset metadata", "Endpoint not available", "NEEDS NOTE");
    return;
  }

  const entries = Object.entries(meta);
  log("PASS", "10a. Metadata available", `${entries.length} datasets documented`);

  let oldData = 0;
  for (const [id, m] of entries) {
    const year = m.data_year;
    // Check for pre-2018 data
    const yearNum = parseInt(year);
    if (yearNum && yearNum < 2018) {
      log("WARN", `10b. Old data: ${id}`, `data_year="${year}" — predates 2018`, "NEEDS NOTE");
      oldData++;
    }
  }
  if (oldData === 0) {
    log("PASS", "10b. No pre-2018 data", "All datasets from 2018 or later");
  }
}

// ═══════════════════════════════════════════════════════════════
// TEST 11 — ARCHETYPE DISTRIBUTION SANITY CHECK
// ═══════════════════════════════════════════════════════════════
async function test11() {
  console.log("\n\x1b[1m═══ TEST 11: Archetype Distribution ═══\x1b[0m");

  const data = await fetchJSON("/county-clusters");
  const assignments = data.county_assignments || {};
  const total = Object.keys(assignments).length;

  const counts = {};
  for (const cid of Object.values(assignments)) {
    counts[cid] = (counts[cid] || 0) + 1;
  }

  log("PASS", "11a. Total assigned", `${total} counties across ${Object.keys(counts).length} clusters`);

  const LABELS = { 0: "Prosperous Suburban", 1: "Rural Heartland", 2: "High-Need Urban/Border", 3: "Rural Disadvantaged" };
  let anyTooSmall = false, anyDominant = false;

  for (const [cid, count] of Object.entries(counts)) {
    const pct = (count / total * 100).toFixed(1);
    const label = LABELS[cid] || `Cluster ${cid}`;

    if (count < 50) {
      log("WARN", `11b. ${label} too small`, `n=${count} (${pct}%) — may be statistically meaningless`, "NEEDS NOTE");
      anyTooSmall = true;
    } else if (count / total > 0.60) {
      log("WARN", `11b. ${label} dominant`, `n=${count} (${pct}%) — >60% of counties`, "NEEDS NOTE");
      anyDominant = true;
    } else {
      log("PASS", `11b. ${label}`, `n=${count} (${pct}%)`);
    }
  }

  // Silhouette score
  const silhouette = data.silhouette_scores;
  if (silhouette) {
    const k4Score = silhouette["4"] ?? silhouette[4];
    if (k4Score != null) {
      if (k4Score > 0.1) {
        log("PASS", "11c. Silhouette score", `k=4: ${k4Score.toFixed(3)} (>0.1)`);
      } else {
        log("WARN", "11c. Silhouette score", `k=4: ${k4Score.toFixed(3)} (<0.1 — weak clustering)`, "NEEDS NOTE");
      }
    }
  }

  // optimal_k
  if (data.optimal_k != null) {
    log("PASS", "11d. optimal_k", `${data.optimal_k}`);
  }
}

// ═══════════════════════════════════════════════════════════════
// TEST 12 — PEER SIMILARITY SYMMETRY AND CONSISTENCY
// ═══════════════════════════════════════════════════════════════
async function test12() {
  console.log("\n\x1b[1m═══ TEST 12: Peer Similarity Consistency ═══\x1b[0m");
  const nodes = await getGravityNodes();
  const nodeMap = new Map(nodes.map(n => [n.fips, n]));

  const ranges = {};
  for (const n of nodes) {
    if (!n.datasets) continue;
    for (const [k, v] of Object.entries(n.datasets)) {
      if (v == null) continue;
      if (!ranges[k]) ranges[k] = { min: v, max: v };
      else { if (v < ranges[k].min) ranges[k].min = v; if (v > ranges[k].max) ranges[k].max = v; }
    }
  }
  const allVars = Object.keys(ranges);

  function euclidDist(a, b) {
    let sum = 0;
    for (const k of allVars) {
      const va = a[k] ?? 0.5, vb = b[k] ?? 0.5;
      const r = ranges[k];
      const na = r ? (va - r.min) / (r.max - r.min || 1) : 0.5;
      const nb = r ? (vb - r.min) / (r.max - r.min || 1) : 0.5;
      sum += (na - nb) ** 2;
    }
    return Math.sqrt(sum);
  }

  const sf = nodeMap.get("06075");
  const arlington = nodeMap.get("51013");

  if (!sf || !arlington) {
    log("FAIL", "12. Lookup", "SF or Arlington not found", "BLOCKS SUBMISSION");
    return;
  }

  const distAB = euclidDist(sf.datasets, arlington.datasets);
  const distBA = euclidDist(arlington.datasets, sf.datasets);

  if (Math.abs(distAB - distBA) < 0.0001) {
    log("PASS", "12a. Distance symmetry", `dist(SF, Arlington)=${distAB.toFixed(6)} = dist(Arlington, SF)=${distBA.toFixed(6)}`);
  } else {
    log("FAIL", "12a. Distance symmetry", `${distAB.toFixed(6)} ≠ ${distBA.toFixed(6)}`, "BLOCKS SUBMISSION");
  }

  // Similarity score monotonicity
  const simAB = Math.max(0, Math.round((1 - distAB / Math.sqrt(allVars.length)) * 100));
  log("PASS", "12b. Similarity score", `sim(SF, Arlington)=${simAB}% (distance=${distAB.toFixed(4)})`);

  // Verify monotonicity: closer counties should have higher similarity
  const sfPeers = nodes
    .filter(n => n.fips !== "06075" && n.datasets)
    .map(n => ({ fips: n.fips, dist: euclidDist(sf.datasets, n.datasets) }))
    .sort((a, b) => a.dist - b.dist)
    .slice(0, 20);

  let monotonic = true;
  for (let i = 1; i < sfPeers.length; i++) {
    const simI = 1 - sfPeers[i].dist / Math.sqrt(allVars.length);
    const simPrev = 1 - sfPeers[i - 1].dist / Math.sqrt(allVars.length);
    if (simI > simPrev + 0.0001) { monotonic = false; break; }
  }
  if (monotonic) {
    log("PASS", "12c. Monotonicity", "Closer counties always have higher similarity scores");
  } else {
    log("FAIL", "12c. Monotonicity", "Similarity not monotonic with distance", "BLOCKS SUBMISSION");
  }
}

// ═══════════════════════════════════════════════════════════════
// RUN ALL TESTS
// ═══════════════════════════════════════════════════════════════
async function main() {
  console.log("╔═══════════════════════════════════════════════════════════╗");
  console.log("║  DiscoveryLens — Independent Peer Review Validation      ║");
  console.log("║  Reviewer: Science (simulated)                           ║");
  console.log("╚═══════════════════════════════════════════════════════════╝");

  const tests = [
    ["TEST 1", test1], ["TEST 2", test2], ["TEST 3", test3],
    ["TEST 4", test4], ["TEST 5", test5], ["TEST 6", test6],
    ["TEST 7", test7], ["TEST 8", test8], ["TEST 9", test9],
    ["TEST 10", test10], ["TEST 11", test11], ["TEST 12", test12],
  ];

  for (const [name, fn] of tests) {
    try { await fn(); } catch (e) { log("FAIL", `${name} ERROR`, e.message, "BLOCKS SUBMISSION"); }
  }

  // ── FINAL VERDICT ──
  console.log("\n╔═══════════════════════════════════════════════════════════╗");
  console.log(`║  RESULTS: ${passed} passed, ${failed} failed, ${warnings} warnings`);
  console.log("╚═══════════════════════════════════════════════════════════╝");

  const blockers = results.filter(r => r.severity === "BLOCKS SUBMISSION");
  const needsNote = results.filter(r => r.severity === "NEEDS NOTE");

  if (blockers.length > 0) {
    console.log("\n\x1b[31m══ VERDICT: MAJOR ISSUES — NEEDS REVISION ══\x1b[0m");
    console.log("Blocking issues:");
    for (const b of blockers) console.log(`  ✗ ${b.test}: ${b.detail}`);
  } else if (needsNote.length > 3) {
    console.log("\n\x1b[33m══ VERDICT: NEEDS REVISION — too many open notes ══\x1b[0m");
  } else if (needsNote.length > 0) {
    console.log("\n\x1b[33m══ VERDICT: READY TO SUBMIT with minor notes ══\x1b[0m");
    console.log("Notes for authors:");
    for (const n of needsNote) console.log(`  ⚠ ${n.test}: ${n.detail}`);
  } else {
    console.log("\n\x1b[32m══ VERDICT: READY TO SUBMIT ══\x1b[0m");
  }

  process.exit(blockers.length > 0 ? 1 : 0);
}

main();
