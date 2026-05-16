/**
 * DiscoveryLens — Replication Results Aggregator
 *
 * Runs the three published-findings replication test scripts, parses their
 * stdout, rolls sub-tests up to per-finding verdicts, and writes a structured
 * artifact at data/replication_results.json.
 *
 * Source test files (unmodified):
 *   - tests/known-effects-validation.mjs       (Tests E–H)
 *   - tests/extended-replication.mjs           (Tests I–P)
 *   - tests/research-domains-validation.mjs    (Tests Q–Z)
 *
 * Per-sub-test verdict rule (mirrors checkDir() in extended-replication.mjs
 * and chk() in research-domains-validation.mjs):
 *   - REPLICATES        : sign matches expected direction AND |r| > 0.3
 *   - REPLICATES (weak) : sign matches AND |r| in [0.05, 0.3]
 *   - INCONCLUSIVE      : sign mismatch BUT |r| < 0.05
 *   - CONTRADICTS       : sign mismatch AND |r| >= 0.05
 *   - ADDS NUANCE       : tests that produce a composite "ADDS NUANCE"
 *                         verdict in their detail strings (rare; testL only)
 *
 * known-effects-validation.mjs uses log() directly without "Verdict: X"
 * markers, so for sub-tests in that file we map PASS/WARN/FAIL + keywords
 * to a verdict using a hand-derived table (see KNOWN_EFFECTS_META and
 * inferKnownEffectsVerdict below).
 *
 * Per-finding rollup rule (combines sub-tests of one named test into one
 * finding-level verdict):
 *   1. If ANY sub-test = CONTRADICTS      -> CONTRADICTS
 *   2. Else if ALL sub-tests = INCONCLUSIVE -> INCONCLUSIVE
 *   3. Else if sub-tests mix REPLICATES (strong) with INCONCLUSIVE / weak
 *      and there is at least one strong signal           -> ADDS NUANCE
 *   4. Else if all directional sub-tests are REPLICATES  -> REPLICATES
 *   5. Else if all directional sub-tests are REPLICATES (weak) only
 *                                                        -> REPLICATES (weak)
 *
 * Finding-grouping rule:
 *   - known-effects:  E1, E2, E3 stay distinct; H and H2 roll up to H;
 *                     F and G are single-sub-test findings.
 *   - extended-replication, research-domains: sub-tests J1, J2, J3, ...
 *     all roll up to J (single alpha letter).
 *
 * Usage:
 *   node scripts/aggregate_replication.mjs
 *
 * Requires network access to https://web-production-a68ad.up.railway.app
 * (same as the underlying test files).
 */

import { spawnSync } from 'node:child_process';
import { writeFileSync } from 'node:fs';
import { resolve, dirname, join } from 'node:path';
import { fileURLToPath } from 'node:url';

const __dirname = dirname(fileURLToPath(import.meta.url));
const REPO_ROOT = resolve(__dirname, '..');

const TEST_FILES = [
  'tests/known-effects-validation.mjs',
  'tests/extended-replication.mjs',
  'tests/research-domains-validation.mjs',
];

// Test-ID -> metadata. Used (1) as a fallback for citation/direction when
// stdout doesn't carry an explicit "Verdict: X (citation)" structure, and
// (2) to provide curated finding-level domain descriptions for every test
// (so the output JSON / table aren't littered with raw stdout fragments
// like "bachelors_rate x life_expectancy:"). Hand-derived from the test
// function headers (e.g. "// TEST J: Education-Health Gradient (Cutler &
// Lleras-Muney 2006)") in the three test source files.
const TEST_META = {
  // known-effects-validation.mjs (E–H)
  E1: { citation: 'Barker et al. 2011',                domain: 'Diabetes Belt geography',                                expected_direction: '+' },
  E2: { citation: 'Case & Deaton 2020',                domain: 'Deaths of Despair geography',                            expected_direction: '+' },
  E3: { citation: 'Chetty et al. (related)',           domain: 'EITC peer clustering',                                   expected_direction: '+' },
  F:  { citation: 'Kline & Moretti 2014',              domain: 'TVA long-run infrastructure effect',                     expected_direction: '+' },
  G:  { citation: 'Markides & Coreil 1986; Ruiz 2013', domain: 'Hispanic Paradox via positive deviance',                 expected_direction: '+' },
  H:  { citation: 'ARC Distressed Counties (federal)', domain: 'Peer alignment with ARC distressed-county list',         expected_direction: '+' },
  // extended-replication.mjs (I–P)
  I:  { citation: 'RUPRI/HRSA',                        domain: 'Rural health penalty (poverty-matched LE gap)',          expected_direction: '+' },
  J:  { citation: 'Cutler & Lleras-Muney 2006',        domain: 'Education–health gradient',                              expected_direction: '+' },
  K:  { citation: 'Sommers et al. 2012',               domain: 'Uninsurance–health link (EITC proxy)',                   expected_direction: '+' },
  L:  { citation: 'Leung et al. 2017',                 domain: 'Food environment paradox (food access × diabetes)',      expected_direction: '-' },
  M:  { citation: 'Putnam 2000; Blakely et al. 2001',  domain: 'Social capital × health (voter turnout, libraries)',     expected_direction: '+' },
  N:  { citation: 'Meltzer & Schwartz 2016',           domain: 'Housing cost × health tradeoff',                         expected_direction: '+' },
  O:  { citation: 'Pierce & Schott 2016; Autor 2013',  domain: 'Manufacturing decline × mental health & diabetes',       expected_direction: '+' },
  P:  { citation: 'Whitacre et al. 2014',              domain: 'Broadband × economic opportunity',                       expected_direction: '+' },
  // research-domains-validation.mjs (Q–Z)
  Q:  { citation: 'Corak 2013',                        domain: 'Great Gatsby Curve (housing burden × poverty/EITC)',     expected_direction: '+' },
  R:  { citation: 'CDC/RWJF',                          domain: 'Obesity Belt (obesity × diabetes co-geography)',         expected_direction: '+' },
  S:  { citation: 'Acemoglu & Restrepo 2017',          domain: 'Aging × economic decline',                               expected_direction: '-' },
  T:  { citation: 'Peri 2012; Card 2009',              domain: 'Immigrant economic contribution',                        expected_direction: '+' },
  U:  { citation: 'DiPasquale & Glaeser 1999',         domain: 'Homeownership × civic/social stability',                 expected_direction: '+' },
  V:  { citation: 'McLanahan & Sandefur 1994',         domain: 'Single-parent households × child poverty',               expected_direction: '+' },
  W:  { citation: 'Krueger 2017',                      domain: 'Disability–opioid nexus (mental-health proxy)',          expected_direction: '+' },
  X:  { citation: 'Glaeser & Mare 2001; Moretti 2004', domain: 'Urban wage premium (pop density × income, broadband)',   expected_direction: '+' },
  Y:  { citation: 'Wilson 1987',                       domain: 'Concentrated poverty (child poverty × health)',          expected_direction: '+' },
  Z:  { citation: 'Novaco & Gonzalez 2009',            domain: 'Rural isolation × mental health',                        expected_direction: '+' },
};

// Reverse-lookup the "Verdict: X" tail string from a checkDir-emitted line
// into one of the five canonical verdict tokens.
const KEEP_TOKENS = ['REPLICATES (weak)', 'REPLICATES', 'CONTRADICTS', 'INCONCLUSIVE', 'ADDS NUANCE'];

function stripAnsi(s) {
  // eslint-disable-next-line no-control-regex
  return s.replace(/\x1b\[[0-9;]*m/g, '');
}

/**
 * Parse the stdout of a single test file into an array of sub-test records.
 */
function parseSubTests(rawStdout, sourceFile) {
  const text = stripAnsi(rawStdout);
  const lines = text.split(/\r?\n/);
  const subTests = [];
  const isKnownEffects = sourceFile.includes('known-effects');

  for (let i = 0; i < lines.length; i++) {
    const line = lines[i];
    // Status line: "  ✓ J1: bachelors_rate x life_expectancy: r=0.658 (n=3062), strong positive"
    const m = line.match(/^\s+([✓✗⚠])\s+([A-Z]\d*):\s*(.+?)$/);
    if (!m) continue;

    const [, icon, testId, restOfLine] = m;
    const status = icon === '✓' ? 'PASS' : icon === '✗' ? 'FAIL' : 'WARN';

    // r and n (optional)
    let r = null;
    let n = null;
    const rnMatch = restOfLine.match(/r=(-?\d+(?:\.\d+)?)\s*\(n=(\d+)\)/);
    if (rnMatch) {
      r = parseFloat(rnMatch[1]);
      n = parseInt(rnMatch[2], 10);
    }

    // Look at the next indented continuation line(s) for detail
    let detail = '';
    let j = i + 1;
    while (j < lines.length && /^\s{4,}/.test(lines[j]) && !/^\s+[✓✗⚠]/.test(lines[j])) {
      detail += (detail ? ' ' : '') + lines[j].trim();
      j++;
    }

    // Parse the detail for "Expected: <dir> (<citation>). Verdict: <X>"
    let verdict = null;
    let citation = null;
    let expectedDirection = null;

    // extended-replication.mjs uses "Expected: <dir> (<cite>). Verdict: <X>"
    // research-domains-validation.mjs uses "Expected: <dir> (<cite>). <X>"
    // Some citations have nested parens, e.g. "Krueger 2017 (proxy)" — so we
    // use a lazy `.+?` for the citation rather than `[^)]+?`. The trailing
    // ").\s*..." anchor forces the match to land at the *outer* close paren.
    const fullVerdictMatch = detail.match(
      /Expected:\s*(positive|negative)\s*\((.+?)\)\.\s*(?:Verdict:\s*)?(REPLICATES \(weak\)|REPLICATES|CONTRADICTS|INCONCLUSIVE|ADDS NUANCE)/,
    );
    if (fullVerdictMatch) {
      expectedDirection = fullVerdictMatch[1] === 'positive' ? '+' : '-';
      citation = fullVerdictMatch[2];
      verdict = fullVerdictMatch[3];
    } else {
      // Detail may carry only "Verdict: X" or "Verdict: X (citation)"
      // (e.g. testN's bare-verdict log() call, testL's composite line).
      const simpleVerdict = detail.match(
        /Verdict:\s*(REPLICATES \(weak\)|REPLICATES|CONTRADICTS|INCONCLUSIVE|ADDS NUANCE)(?:\s*\(([^)]+)\))?/,
      );
      if (simpleVerdict) {
        verdict = simpleVerdict[1];
        if (simpleVerdict[2]) citation = simpleVerdict[2];
      }
    }

    // Fallback when stdout doesn't carry an explicit verdict marker.
    // Applies to known-effects-validation.mjs (whose log() calls don't use
    // "Verdict: X" markers at all) and to a small allowlist of WARN-branch
    // log() calls in extended-replication (e.g. testI's "Gap smaller than
    // expected" path). Excluded by design: narrative-only sub-tests like
    // J3/M5/P4 — those describe exploratory within-cluster checks, not
    // primary replication, and shouldn't be counted as sub-tests.
    const FALLBACK_ALLOWLIST = new Set(['I']);
    if (verdict === null && (isKnownEffects || FALLBACK_ALLOWLIST.has(testId))) {
      verdict = inferVerdictFromStatus(status, restOfLine, detail);
      const meta = TEST_META[testId] || TEST_META[testId[0]];
      if (meta) {
        citation = meta.citation;
        expectedDirection = meta.expected_direction;
      }
    }

    if (verdict === null) continue; // narrative-only line, no verdict

    subTests.push({
      source_file: sourceFile,
      test_id: testId,
      status,
      label: restOfLine.replace(/\s*r=.+$/, '').trim(),
      r,
      n,
      detail,
      citation,
      expected_direction: expectedDirection,
      verdict,
    });
  }

  return subTests;
}

function inferVerdictFromStatus(status, restOfLine, detail) {
  if (status === 'PASS') return 'REPLICATES';
  if (status === 'FAIL') return 'CONTRADICTS';
  // WARN — disambiguate by keyword
  const blob = (restOfLine + ' ' + detail).toLowerCase();
  if (blob.includes('partial')) return 'REPLICATES (weak)';
  if (blob.includes('weak')) return 'REPLICATES (weak)';
  if (blob.includes('not detected') || blob.includes('not replicated') || blob.includes('low ')) {
    return 'INCONCLUSIVE';
  }
  return 'INCONCLUSIVE';
}

/**
 * Rollup rule, applied to the set of sub-test verdicts within a single
 * named test. Documented at the top of the file.
 */
function rollupVerdict(verdicts) {
  if (verdicts.includes('CONTRADICTS')) return 'CONTRADICTS';

  const hasStrong = verdicts.includes('REPLICATES');
  const hasWeak = verdicts.includes('REPLICATES (weak)');
  const hasNuance = verdicts.includes('ADDS NUANCE');
  const hasIncon = verdicts.includes('INCONCLUSIVE');

  if (!hasStrong && !hasWeak && !hasNuance && hasIncon) return 'INCONCLUSIVE';
  if (hasNuance) return 'ADDS NUANCE';
  if (hasStrong && (hasIncon || hasWeak)) return 'ADDS NUANCE';
  if (hasStrong) return 'REPLICATES';
  if (hasWeak) return 'REPLICATES (weak)';
  return 'INCONCLUSIVE';
}

/**
 * Group a sub-test under its parent finding ID.
 */
function findingIdFor(testId, sourceFile) {
  if (sourceFile.includes('known-effects')) {
    if (/^E\d/.test(testId)) return testId.slice(0, 2); // E1, E2, E3 distinct
    return testId[0]; // F, G, H, H2 -> F, G, H, H
  }
  return testId[0]; // single alpha letter
}

async function main() {
  console.log('DiscoveryLens - Replication Results Aggregator');
  console.log('='.repeat(60));
  console.log('');

  const allSubTests = [];

  for (const testFile of TEST_FILES) {
    const fullPath = join(REPO_ROOT, testFile);
    process.stdout.write(`Running ${testFile} ... `);

    const result = spawnSync('node', [fullPath], {
      cwd: REPO_ROOT,
      encoding: 'utf-8',
      maxBuffer: 16 * 1024 * 1024,
      timeout: 5 * 60 * 1000,
    });

    if (result.error) {
      console.log(`ERROR: ${result.error.message}`);
      continue;
    }
    if (result.status !== 0 && result.status !== 1) {
      // Note: extended-replication exits 1 if any sub-test FAILs, which is
      // normal for our purposes. We tolerate exit codes 0 and 1.
      console.log(`exited with status ${result.status}`);
    }

    const stdout = result.stdout || '';
    const subs = parseSubTests(stdout, testFile);
    console.log(`parsed ${subs.length} sub-test verdicts`);
    allSubTests.push(...subs);
  }

  console.log('');

  // Group by finding ID
  const findingsMap = new Map();
  for (const st of allSubTests) {
    const fid = findingIdFor(st.test_id, st.source_file);
    if (!findingsMap.has(fid)) findingsMap.set(fid, []);
    findingsMap.get(fid).push(st);
  }

  // Build findings array
  const findings = [];
  for (const [fid, subs] of findingsMap) {
    const verdicts = subs.map((s) => s.verdict);
    const rolled = rollupVerdict(verdicts);

    // Curated META wins over parsed stdout strings (the test code's chk()
    // calls sometimes pass slogan-style citations like "Food desert
    // hypothesis" rather than the actual paper citation in the test header;
    // META reflects the test header / function comment).
    const meta = TEST_META[fid] || {};
    const withCitation = subs.find((s) => s.citation) || subs[0];
    const citation = meta.citation || withCitation.citation || 'unknown';
    const expectedDir = meta.expected_direction || withCitation.expected_direction || null;

    // Representative r/n: first sub-test that has a numeric r
    const firstWithR = subs.find((s) => s.r !== null);
    const computedR = firstWithR ? firstWithR.r : null;
    const nVal = firstWithR ? firstWithR.n : null;

    // Domain: from META; only fall back to stdout label if META missing
    const domain =
      meta.domain ||
      (subs[0].label || '')
        .replace(/^[A-Z]\d*:\s*/, '')
        .replace(/:\s*$/, '')
        .replace(/,\s*\w+\s+(positive|negative)$/, '');

    findings.push({
      id: fid,
      citation,
      domain,
      expected_direction: expectedDir,
      computed_r: computedR,
      n: nVal,
      sub_test_count: subs.length,
      sub_test_verdicts: verdicts,
      sub_test_details: subs.map((s) => ({
        test_id: s.test_id,
        r: s.r,
        n: s.n,
        status: s.status,
        verdict: s.verdict,
      })),
      rolled_up_verdict: rolled,
    });
  }

  findings.sort((a, b) => a.id.localeCompare(b.id));

  const summary = {
    n_findings: findings.length,
    n_replicates: findings.filter((f) => f.rolled_up_verdict === 'REPLICATES').length,
    n_replicates_weak: findings.filter((f) => f.rolled_up_verdict === 'REPLICATES (weak)').length,
    n_adds_nuance: findings.filter((f) => f.rolled_up_verdict === 'ADDS NUANCE').length,
    n_inconclusive: findings.filter((f) => f.rolled_up_verdict === 'INCONCLUSIVE').length,
    n_contradicts: findings.filter((f) => f.rolled_up_verdict === 'CONTRADICTS').length,
  };

  const output = {
    generated_at: new Date().toISOString(),
    methodology: [
      'Per-sub-test verdict rule (mirrors checkDir() in tests/extended-replication.mjs',
      'and chk() in tests/research-domains-validation.mjs):',
      '  REPLICATES        : sign matches expected direction AND |r| > 0.3',
      '  REPLICATES (weak) : sign matches AND |r| in [0.05, 0.3]',
      '  INCONCLUSIVE      : sign mismatch BUT |r| < 0.05',
      '  CONTRADICTS       : sign mismatch AND |r| >= 0.05',
      'For known-effects-validation.mjs (whose stdout lacks "Verdict: X" markers),',
      'PASS -> REPLICATES, FAIL -> CONTRADICTS, WARN -> REPLICATES (weak) if the',
      'label/detail contains "partial"/"weak", else INCONCLUSIVE.',
      '',
      'Per-finding rollup rule (combines sub-tests of one named test):',
      '  1. ANY sub-test = CONTRADICTS                            -> CONTRADICTS',
      '  2. ALL sub-tests = INCONCLUSIVE                          -> INCONCLUSIVE',
      '  3. Mix of REPLICATES (strong) with INCONCLUSIVE or weak  -> ADDS NUANCE',
      '  4. All directional sub-tests = REPLICATES (strong)       -> REPLICATES',
      '  5. All directional sub-tests = REPLICATES (weak) only    -> REPLICATES (weak)',
      '',
      'Finding-grouping: in known-effects-validation.mjs, sub-tests E1/E2/E3 are',
      'distinct findings (different citations); H and H2 collapse to one finding H.',
      'In extended-replication.mjs and research-domains-validation.mjs, sub-tests',
      'within one named test (e.g. J1, J2, J3) all roll up to that finding (J).',
    ].join('\n'),
    findings,
    summary,
  };

  const outPath = join(REPO_ROOT, 'data', 'replication_results.json');
  writeFileSync(outPath, JSON.stringify(output, null, 2));
  console.log(`Wrote ${outPath}`);

  console.log('');
  console.log('=== SUMMARY ===');
  console.log(`Total findings:     ${summary.n_findings}`);
  console.log(`  REPLICATES:         ${summary.n_replicates}`);
  console.log(`  REPLICATES (weak):  ${summary.n_replicates_weak}`);
  console.log(`  ADDS NUANCE:        ${summary.n_adds_nuance}`);
  console.log(`  INCONCLUSIVE:       ${summary.n_inconclusive}`);
  console.log(`  CONTRADICTS:        ${summary.n_contradicts}`);
}

main().catch((e) => {
  console.error('FATAL:', e);
  process.exit(1);
});
