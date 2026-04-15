/**
 * DiscoveryLens — Ground Truth Verification (Round 4)
 * Spot-checks raw data values against published government sources.
 * Run: node tests/ground-truth-validation.mjs
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
  if (status === "PASS") passed++; else if (status === "FAIL") failed++; else warnings++;
}

function pearsonR(xs, ys) {
  const pairs = [];
  for (let i = 0; i < xs.length; i++) {
    if (xs[i] != null && ys[i] != null && isFinite(xs[i]) && isFinite(ys[i])) pairs.push([xs[i], ys[i]]);
  }
  if (pairs.length < 10) return null;
  const n = pairs.length, mx = pairs.reduce((s, p) => s + p[0], 0) / n, my = pairs.reduce((s, p) => s + p[1], 0) / n;
  let num = 0, dx = 0, dy = 0;
  for (const [x, y] of pairs) { num += (x - mx) * (y - my); dx += (x - mx) ** 2; dy += (y - my) ** 2; }
  return Math.sqrt(dx * dy) === 0 ? null : num / Math.sqrt(dx * dy);
}

async function fetchJSON(path, opts) {
  const res = await fetch(`${BASE}${path}`, opts);
  if (!res.ok) throw new Error(`HTTP ${res.status} for ${path}`);
  return res.json();
}

let _nodes = null;
async function getNodes() {
  if (!_nodes) { const d = await fetchJSON("/gravity-map?module_id=all"); _nodes = d.nodes || []; }
  return _nodes;
}

function getVal(node, key) {
  if (!node?.datasets) return null;
  return node.datasets[key] ?? null;
}

/** Check a value falls within a range. Handles both 0-1 proportions and already-percentage values. */
function checkRange(testName, fips, countyName, varKey, rawVal, minExpected, maxExpected, unit, tolerance = 0) {
  if (rawVal == null) {
    log("WARN", `${testName}: ${countyName}`, `${varKey} is null/missing`, "NEEDS NOTE");
    return;
  }
  // Normalize: if value is 0-1 and expected is 0-100, multiply
  let displayVal = rawVal;
  let val = rawVal;
  if (unit === "%" && rawVal > 0 && rawVal < 1) { val = rawVal * 100; displayVal = `${(rawVal * 100).toFixed(1)}% (raw: ${rawVal.toFixed(4)})`; }
  else if (unit === "%") { displayVal = `${rawVal.toFixed(1)}%`; }
  else if (unit === "$") { displayVal = `$${Math.round(rawVal).toLocaleString()}`; }
  else if (unit === "yrs") { displayVal = `${rawVal.toFixed(1)} yrs`; }
  else { displayVal = `${rawVal.toFixed(4)}`; }

  const min = minExpected - tolerance;
  const max = maxExpected + tolerance;
  if (val >= min && val <= max) {
    log("PASS", `${testName}: ${countyName} (${fips})`, `${varKey}=${displayVal} — within [${minExpected}, ${maxExpected}]${unit}`);
  } else if (val >= minExpected - tolerance * 2 && val <= maxExpected + tolerance * 2) {
    log("WARN", `${testName}: ${countyName} (${fips})`, `${varKey}=${displayVal} — outside [${minExpected}, ${maxExpected}] but within extended tolerance`, "NEEDS NOTE");
  } else {
    log("FAIL", `${testName}: ${countyName} (${fips})`, `${varKey}=${displayVal} — OUTSIDE expected [${minExpected}, ${maxExpected}]${unit}`, "BLOCKS SUBMISSION");
  }
}

// ═══════════════════════════════════════════════════════════════
// TEST 23 — POVERTY RATE GROUND TRUTH
// ═══════════════════════════════════════════════════════════════
async function test23() {
  console.log("\n\x1b[1m═══ TEST 23: Poverty Rate Ground Truth (Census SAIPE 2022) ═══\x1b[0m");
  const nodes = await getNodes();
  const nodeMap = new Map(nodes.map(n => [n.fips, n]));

  const checks = [
    ["06075", "San Francisco CA", 10, 12],
    ["17031", "Cook County IL", 13, 15],
    ["54047", "McDowell WV", 35, 40],
    ["48301", "Loving County TX", 5, 15],
    ["36061", "New York County NY", 14, 17],
    ["06041", "Marin County CA", 6, 9],
    ["21189", "Owsley County KY", 35, 42],
    ["48427", "Starr County TX", 32, 38],
    ["51107", "Loudoun County VA", 4, 7],
  ];

  for (const [fips, name, min, max] of checks) {
    const node = nodeMap.get(fips);
    const val = getVal(node, "poverty");
    checkRange("23", fips, name, "poverty", val, min, max, "%", 3);
  }
}

// ═══════════════════════════════════════════════════════════════
// TEST 24 — BROADBAND GROUND TRUTH
// ═══════════════════════════════════════════════════════════════
async function test24() {
  console.log("\n\x1b[1m═══ TEST 24: Broadband Ground Truth (ACS 2022) ═══\x1b[0m");
  const nodes = await getNodes();
  const nodeMap = new Map(nodes.map(n => [n.fips, n]));

  // Expected ranges for B28002_007E (fixed broadband: cable/fiber/DSL)
  const checks = [
    ["06075", "San Francisco CA", 78, 87],
    ["54047", "McDowell WV", 60, 72],
    ["48301", "Loving County TX", 50, 70],
    ["36061", "New York County NY", 74, 84],
    ["21189", "Owsley County KY", 55, 68],
  ];

  for (const [fips, name, min, max] of checks) {
    const node = nodeMap.get(fips);
    const val = getVal(node, "broadband");
    checkRange("24", fips, name, "broadband", val, min, max, "%", 5);
  }
}

// ═══════════════════════════════════════════════════════════════
// TEST 25 — LIFE EXPECTANCY GROUND TRUTH
// ═══════════════════════════════════════════════════════════════
async function test25() {
  console.log("\n\x1b[1m═══ TEST 25: Life Expectancy Ground Truth (CDC USALEEP) ═══\x1b[0m");
  const nodes = await getNodes();
  const nodeMap = new Map(nodes.map(n => [n.fips, n]));

  const checks = [
    ["06075", "San Francisco CA", 82, 85],
    ["54047", "McDowell WV", 64, 68],
    ["06041", "Marin County CA", 84, 88],
    ["46102", "Oglala Lakota SD", 64, 72],
    ["51107", "Loudoun County VA", 82, 86],
  ];

  for (const [fips, name, min, max] of checks) {
    const node = nodeMap.get(fips);
    const val = getVal(node, "life_expectancy");
    if (val == null) {
      log("WARN", `25: ${name} (${fips})`, "life_expectancy is null — county may not have USALEEP data", "INFORMATIONAL");
    } else {
      checkRange("25", fips, name, "life_expectancy", val, min, max, "yrs", 2);
    }
  }
}

// ═══════════════════════════════════════════════════════════════
// TEST 26 — DIABETES RATE GROUND TRUTH
// ═══════════════════════════════════════════════════════════════
async function test26() {
  console.log("\n\x1b[1m═══ TEST 26: Diabetes Rate Ground Truth (CDC PLACES) ═══\x1b[0m");
  const nodes = await getNodes();
  const nodeMap = new Map(nodes.map(n => [n.fips, n]));

  const checks = [
    ["06075", "San Francisco CA", 7, 11],
    ["54047", "McDowell WV", 18, 25],
    ["06041", "Marin County CA", 6, 10],
  ];

  for (const [fips, name, min, max] of checks) {
    const node = nodeMap.get(fips);
    const val = getVal(node, "diabetes");
    checkRange("26", fips, name, "diabetes", val, min, max, "%", 3);
  }

  // Check a Mississippi Delta county (high diabetes belt)
  // Holmes County MS (28051) — known high diabetes
  const holmes = nodeMap.get("28051");
  const hVal = getVal(holmes, "diabetes");
  if (hVal != null) {
    checkRange("26", "28051", "Holmes MS (Delta)", "diabetes", hVal, 16, 25, "%", 3);
  }

  // Check a Minnesota county (typically low diabetes)
  // Hennepin MN (27053)
  const henn = nodeMap.get("27053");
  const hennVal = getVal(henn, "diabetes");
  if (hennVal != null) {
    checkRange("26", "27053", "Hennepin MN", "diabetes", hennVal, 7, 12, "%", 3);
  }
}

// ═══════════════════════════════════════════════════════════════
// TEST 27 — MEDIAN INCOME GROUND TRUTH
// ═══════════════════════════════════════════════════════════════
async function test27() {
  console.log("\n\x1b[1m═══ TEST 27: Median Income Ground Truth (ACS 2022) ═══\x1b[0m");
  const nodes = await getNodes();
  const nodeMap = new Map(nodes.map(n => [n.fips, n]));

  const checks = [
    ["06075", "San Francisco CA", 120000, 145000],
    ["54047", "McDowell WV", 25000, 33000],
    ["06041", "Marin County CA", 120000, 150000],
    ["21189", "Owsley County KY", 20000, 30000],
    ["51107", "Loudoun County VA", 130000, 160000],
    ["48427", "Starr County TX", 26000, 36000],
  ];

  for (const [fips, name, min, max] of checks) {
    const node = nodeMap.get(fips);
    const val = getVal(node, "median_income");
    if (val == null) {
      log("WARN", `27: ${name} (${fips})`, "median_income is null", "NEEDS NOTE");
    } else {
      checkRange("27", fips, name, "median_income", val, min, max, "$", 5000);
    }
  }
}

// ═══════════════════════════════════════════════════════════════
// TEST 28 — INTERNAL CONSISTENCY CHECK
// ═══════════════════════════════════════════════════════════════
async function test28() {
  console.log("\n\x1b[1m═══ TEST 28: Internal Consistency (Directional Checks) ═══\x1b[0m");
  const nodes = await getNodes();

  const checks = [
    { a: "poverty", b: "median_income", expectSign: -1, label: "poverty vs income (should be negative)" },
    { a: "broadband", b: "median_income", expectSign: 1, label: "broadband vs income (should be positive)" },
    { a: "diabetes", b: "obesity", expectSign: 1, label: "diabetes vs obesity (should be positive)" },
    { a: "life_expectancy", b: "poverty", expectSign: -1, label: "life expectancy vs poverty (should be negative)" },
  ];

  for (const chk of checks) {
    const xs = [], ys = [];
    for (const n of nodes) {
      const a = getVal(n, chk.a), b = getVal(n, chk.b);
      if (a != null && b != null) { xs.push(a); ys.push(b); }
    }
    const r = pearsonR(xs, ys);
    if (r == null) {
      log("WARN", `28: ${chk.label}`, "Insufficient data", "NEEDS NOTE");
      continue;
    }
    const correctSign = (chk.expectSign > 0 && r > 0) || (chk.expectSign < 0 && r < 0);
    if (correctSign) {
      log("PASS", `28: ${chk.label}`, `r=${r.toFixed(4)} — correct direction`);
    } else {
      log("FAIL", `28: ${chk.label}`, `r=${r.toFixed(4)} — WRONG DIRECTION (expected ${chk.expectSign > 0 ? "positive" : "negative"})`, "BLOCKS SUBMISSION");
    }
  }
}

// ═══════════════════════════════════════════════════════════════
// TEST 29 — OUTLIER SANITY CHECK
// ═══════════════════════════════════════════════════════════════
async function test29() {
  console.log("\n\x1b[1m═══ TEST 29: Outlier Sanity Check (Physically Plausible Ranges) ═══\x1b[0m");
  const nodes = await getNodes();

  // Define plausible ranges for each variable
  // Note: poverty might be stored as either 0-1 or 0-100; detect from data
  const firstPoverty = nodes.find(n => getVal(n, "poverty") != null)?.datasets?.poverty;
  const povertyIsPct = firstPoverty > 1; // If > 1, it's percentage form

  const checks = [
    { key: "poverty", min: povertyIsPct ? 0 : 0, max: povertyIsPct ? 60 : 0.6, label: "Poverty Rate" },
    { key: "life_expectancy", min: 55, max: 100, label: "Life Expectancy" },
    { key: "broadband", min: 0, max: 1.01, label: "Broadband" },
    { key: "diabetes", min: 0, max: povertyIsPct ? 35 : 0.35, label: "Diabetes" },
    { key: "median_income", min: 10000, max: 500000, label: "Median Income" },
    { key: "unemployment", min: 0, max: povertyIsPct ? 40 : 0.4, label: "Unemployment" },
  ];

  for (const chk of checks) {
    let violations = 0;
    const violationList = [];
    let totalWithData = 0;

    for (const n of nodes) {
      const v = getVal(n, chk.key);
      if (v == null) continue;
      totalWithData++;
      if (v < chk.min || v > chk.max) {
        violations++;
        if (violationList.length < 3) {
          violationList.push(`${n.county_name} (${n.fips}): ${v}`);
        }
      }
    }

    if (violations === 0) {
      log("PASS", `29: ${chk.label}`, `All ${totalWithData} values within [${chk.min}, ${chk.max}]`);
    } else {
      const detail = `${violations}/${totalWithData} violations. Examples: ${violationList.join("; ")}`;
      if (violations <= 3) {
        log("WARN", `29: ${chk.label}`, detail, "NEEDS NOTE");
      } else {
        log("FAIL", `29: ${chk.label}`, detail, "BLOCKS SUBMISSION");
      }
    }
  }
}

// ═══════════════════════════════════════════════════════════════
// TEST 30 — YEAR-OVER-YEAR PLAUSIBILITY (National Medians)
// ═══════════════════════════════════════════════════════════════
async function test30() {
  console.log("\n\x1b[1m═══ TEST 30: National Medians Plausibility ═══\x1b[0m");
  const nodes = await getNodes();

  function median(arr) {
    const s = [...arr].sort((a, b) => a - b);
    const mid = Math.floor(s.length / 2);
    return s.length % 2 === 0 ? (s[mid - 1] + s[mid]) / 2 : s[mid];
  }

  const povertyVals = nodes.map(n => getVal(n, "poverty")).filter(v => v != null);
  const broadbandVals = nodes.map(n => getVal(n, "broadband")).filter(v => v != null);
  const leVals = nodes.map(n => getVal(n, "life_expectancy")).filter(v => v != null);
  const diabetesVals = nodes.map(n => getVal(n, "diabetes")).filter(v => v != null);

  const medPoverty = median(povertyVals);
  const medBroadband = median(broadbandVals);
  const medLE = median(leVals);
  const medDiabetes = median(diabetesVals);

  // Poverty: normalize to percentage
  const pov = medPoverty > 1 ? medPoverty : medPoverty * 100;
  if (pov >= 11 && pov <= 16) {
    log("PASS", "30a. National median poverty", `${pov.toFixed(1)}% — plausible for 2022`);
  } else {
    log("WARN", "30a. National median poverty", `${pov.toFixed(1)}% — outside expected 11-16%`, "NEEDS NOTE");
  }

  // Broadband: normalize to percentage
  const bb = medBroadband > 1 ? medBroadband : medBroadband * 100;
  if (bb >= 55 && bb <= 72) {
    log("PASS", "30b. National median fixed broadband", `${bb.toFixed(1)}% — plausible for B28002_007E (cable/fiber/DSL)`);
  } else {
    log("WARN", "30b. National median fixed broadband", `${bb.toFixed(1)}% — outside expected 55-72% for fixed broadband`, "NEEDS NOTE");
  }

  // Life expectancy
  if (medLE >= 75 && medLE <= 80) {
    log("PASS", "30c. National median life expectancy", `${medLE.toFixed(1)} yrs — plausible`);
  } else {
    log("WARN", "30c. National median life expectancy", `${medLE.toFixed(1)} yrs — outside expected 75-80`, "NEEDS NOTE");
  }

  // Diabetes: normalize
  const dia = medDiabetes > 1 ? medDiabetes : medDiabetes * 100;
  if (dia >= 9 && dia <= 14) {
    log("PASS", "30d. National median diabetes", `${dia.toFixed(1)}% — plausible for 2022`);
  } else {
    log("WARN", "30d. National median diabetes", `${dia.toFixed(1)}% — outside expected 9-14%`, "NEEDS NOTE");
  }
}

// ═══════════════════════════════════════════════════════════════
// TEST 31 — CROSS-VARIABLE RANK CONSISTENCY (McDowell WV)
// ═══════════════════════════════════════════════════════════════
async function test31() {
  console.log("\n\x1b[1m═══ TEST 31: McDowell WV Cross-Variable Rank Consistency ═══\x1b[0m");
  const nodes = await getNodes();
  const mc = nodes.find(n => n.fips === "54047");
  if (!mc) { log("FAIL", "31: McDowell lookup", "FIPS 54047 not found", "BLOCKS SUBMISSION"); return; }

  function percentileRank(nodes, key, fips) {
    const vals = nodes.map(n => ({ fips: n.fips, v: getVal(n, key) })).filter(x => x.v != null);
    vals.sort((a, b) => a.v - b.v);
    const idx = vals.findIndex(x => x.fips === fips);
    if (idx === -1) return null;
    return Math.round((idx / vals.length) * 100);
  }

  const checks = [
    { key: "poverty", label: "Poverty", expectHigh: true, expectPctMin: 95, expectPctMax: 100 },
    { key: "life_expectancy", label: "Life Expectancy", expectHigh: false, expectPctMin: 0, expectPctMax: 5 },
    { key: "broadband", label: "Broadband", expectHigh: false, expectPctMin: 40, expectPctMax: 75 },
    { key: "median_income", label: "Median Income", expectHigh: false, expectPctMin: 0, expectPctMax: 5 },
    { key: "diabetes", label: "Diabetes", expectHigh: true, expectPctMin: 90, expectPctMax: 100 },
  ];

  for (const chk of checks) {
    const pct = percentileRank(nodes, chk.key, "54047");
    if (pct == null) {
      log("WARN", `31: McDowell ${chk.label}`, "Value missing", "NEEDS NOTE");
      continue;
    }

    const inRange = pct >= chk.expectPctMin && pct <= chk.expectPctMax;
    const detail = `${pct}th percentile (expected ${chk.expectPctMin}-${chk.expectPctMax}th)`;

    if (inRange) {
      log("PASS", `31: McDowell ${chk.label}`, detail);
    } else if (Math.abs(pct - (chk.expectHigh ? 97 : 3)) < 15) {
      log("WARN", `31: McDowell ${chk.label}`, `${detail} — outside expected but close`, "INFORMATIONAL");
    } else {
      log("FAIL", `31: McDowell ${chk.label}`, `${detail} — UNEXPECTED RANK for a severely disadvantaged county`, "BLOCKS SUBMISSION");
    }
  }
}

// ═══════════════════════════════════════════════════════════════
// RUN ALL
// ═══════════════════════════════════════════════════════════════
async function main() {
  console.log("╔═══════════════════════════════════════════════════════════╗");
  console.log("║  DiscoveryLens — Ground Truth Verification (Round 4)     ║");
  console.log("║  Spot-checking against published government data         ║");
  console.log("╚═══════════════════════════════════════════════════════════╝");

  const tests = [
    ["23", test23], ["24", test24], ["25", test25], ["26", test26],
    ["27", test27], ["28", test28], ["29", test29], ["30", test30], ["31", test31],
  ];

  for (const [name, fn] of tests) {
    try { await fn(); } catch (e) { log("FAIL", `TEST ${name} ERROR`, e.message, "BLOCKS SUBMISSION"); }
  }

  console.log("\n╔═══════════════════════════════════════════════════════════╗");
  console.log(`║  RESULTS: ${passed} passed, ${failed} failed, ${warnings} warnings`);
  console.log("╚═══════════════════════════════════════════════════════════╝");

  const blockers = results.filter(r => r.severity === "BLOCKS SUBMISSION");
  const needsNote = results.filter(r => r.severity === "NEEDS NOTE");

  if (blockers.length > 0) {
    console.log("\n\x1b[31m══ VERDICT: MAJOR ISSUES — NEEDS REVISION ══\x1b[0m");
    for (const b of blockers) console.log(`  ✗ ${b.test}: ${b.detail}`);
  } else if (needsNote.length > 5) {
    console.log("\n\x1b[33m══ VERDICT: NEEDS REVISION — too many notes ══\x1b[0m");
    for (const n of needsNote) console.log(`  ⚠ ${n.test}: ${n.detail}`);
  } else if (needsNote.length > 0) {
    console.log("\n\x1b[33m══ VERDICT: READY TO SUBMIT with minor notes ══\x1b[0m");
    for (const n of needsNote) console.log(`  ⚠ ${n.test}: ${n.detail}`);
  } else {
    console.log("\n\x1b[32m══ VERDICT: READY TO SUBMIT ══\x1b[0m");
  }

  process.exit(blockers.length > 0 ? 1 : 0);
}

main();
