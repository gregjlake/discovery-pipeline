"""Peer stability analysis: are peer results stable for typical (median) counties?"""
import json, os
import numpy as np
import pandas as pd
from dotenv import load_dotenv

load_dotenv()

# ── Step 1: Load data ────────────────────────────────────────
with open('data/gravity_map_cache.json') as f:
    cache = json.load(f)
with open('data/beta_calibration.json') as f:
    cal = json.load(f)

nodes = cache['nodes']
dataset_cols = cal['datasets_used']
print(f"Datasets: {len(dataset_cols)}")
print(f"Nodes: {len(nodes)}")

# Build normalized vectors from cache node datasets
raw_vals = {col: [] for col in dataset_cols}
for n in nodes:
    ds = n.get('datasets', {})
    for col in dataset_cols:
        v = ds.get(col)
        if v is not None:
            raw_vals[col].append(v)

col_min = {col: min(raw_vals[col]) if raw_vals[col] else 0 for col in dataset_cols}
col_max = {col: max(raw_vals[col]) if raw_vals[col] else 1 for col in dataset_cols}

fips_list = [n['fips'] for n in nodes]
node_lookup = {n['fips']: n for n in nodes}
vec_lookup = {}
for n in nodes:
    ds = n.get('datasets', {})
    v = []
    for col in dataset_cols:
        raw = ds.get(col)
        if raw is None:
            v.append(0.5)
        else:
            rng = col_max[col] - col_min[col]
            v.append((raw - col_min[col]) / rng if rng > 0 else 0.5)
    vec_lookup[n['fips']] = np.array(v)

# ── Step 2: Find 5 boundary counties ─────────────────────────
print("\n" + "=" * 60)
print("STEP 2: BOUNDARY COUNTY SELECTION")
print("=" * 60)

overall_scores = {}
for fips, vec in vec_lookup.items():
    overall_scores[fips] = float(np.mean(vec))

scores_arr = np.array(list(overall_scores.values()))
p45 = np.percentile(scores_arr, 45)
p50 = np.percentile(scores_arr, 50)
p55 = np.percentile(scores_arr, 55)
print(f"P45={p45:.4f}  P50={p50:.4f}  P55={p55:.4f}")

# Counties in median band
band = {f: s for f, s in overall_scores.items() if p45 <= s <= p55}
print(f"Counties in P45-P55 band: {len(band)}")

# Select one per region closest to P50
regions = ['Midwest', 'South', 'Northeast', 'West']
selected = []
used_fips = set()

for region in regions:
    candidates = [(f, s) for f, s in band.items()
                  if node_lookup[f].get('region') == region]
    if candidates:
        best = min(candidates, key=lambda x: abs(x[1] - p50))
        selected.append(best[0])
        used_fips.add(best[0])

# One additional from any region
remaining = [(f, s) for f, s in band.items() if f not in used_fips]
if remaining:
    best = min(remaining, key=lambda x: abs(x[1] - p50))
    selected.append(best[0])

# Compute percentiles for display
all_scores_sorted = np.sort(scores_arr)
def get_percentile(score):
    return float(np.searchsorted(all_scores_sorted, score) / len(all_scores_sorted) * 100)

print(f"\nSelected {len(selected)} boundary counties:")
print(f"{'FIPS':<8} {'Name':<30} {'Region':<12} {'Score':<8} {'Pctl':<6}")
print("-" * 66)
for f in selected:
    n = node_lookup[f]
    s = overall_scores[f]
    pctl = get_percentile(s)
    print(f"{f:<8} {n.get('county_name', f):<30} {n.get('region', '?'):<12} {s:.4f}  P{pctl:.0f}")

# ── Step 3: Define three weighting schemes ────────────────────
print("\n" + "=" * 60)
print("STEP 3: WEIGHTING SCHEMES")
print("=" * 60)

# Domain clusters (mobility removed)
clusters = {
    'Economic': ['poverty', 'eitc', 'median_income', 'bea_income', 'unemployment'],
    'Health': ['obesity', 'diabetes', 'hypertension', 'mental_health'],
    'Infrastructure': ['broadband', 'food_access', 'housing_burden', 'air'],
    'Civic & demographic': ['voter_turnout', 'library', 'rural_urban', 'pop_density'],
}

# Verify all datasets accounted for
all_cluster_vars = []
for vs in clusters.values():
    all_cluster_vars.extend(vs)
assert set(all_cluster_vars) == set(dataset_cols), f"Mismatch: {set(dataset_cols) - set(all_cluster_vars)}"

# Scheme A: equal
w_equal = np.ones(len(dataset_cols))

# Scheme B: domain balanced
w_domain = np.zeros(len(dataset_cols))
for cluster_name, vars_list in clusters.items():
    w = 0.25 / len(vars_list)
    for v in vars_list:
        idx = dataset_cols.index(v)
        w_domain[idx] = w
sqrt_w_domain = np.sqrt(w_domain * len(dataset_cols))  # scale for euclidean

# Scheme C: PCA 7
pca7_cols = ['poverty', 'median_income', 'unemployment', 'obesity', 'diabetes', 'rural_urban', 'broadband']
pca7_cols = [c for c in pca7_cols if c in dataset_cols]
pca7_idx = [dataset_cols.index(c) for c in pca7_cols]

print(f"Scheme A: Equal (17 datasets, each 1/17)")
print(f"Scheme B: Domain balanced (4 domains x 25%)")
for cname, cvars in clusters.items():
    w = 0.25 / len(cvars)
    print(f"  {cname}: {len(cvars)} vars, each {w:.4f}")
print(f"Scheme C: PCA 7 ({len(pca7_cols)} datasets): {pca7_cols}")

# ── Step 4 & 5: Compute peers and stability ──────────────────
print("\n" + "=" * 60)
print("STEPS 4-5: PEER COMPUTATION AND STABILITY")
print("=" * 60)

def compute_top_peers(target_fips, scheme, n=10):
    """Compute top N socioeconomic peers using given weighting scheme."""
    vi = vec_lookup[target_fips]
    dists = []
    for other_fips in fips_list:
        if other_fips == target_fips:
            continue
        vj = vec_lookup[other_fips]
        if scheme == 'equal':
            d = np.linalg.norm(vi - vj)
        elif scheme == 'domain':
            d = np.linalg.norm((vi - vj) * sqrt_w_domain)
        elif scheme == 'pca7':
            d = np.linalg.norm(vi[pca7_idx] - vj[pca7_idx])
        dists.append((other_fips, d))
    dists.sort(key=lambda x: x[1])
    return [f for f, _ in dists[:n]]

def jaccard(set_a, set_b):
    a, b = set(set_a), set(set_b)
    return len(a & b) / len(a | b) if (a | b) else 0.0

all_results = []
# Include both boundary + extreme counties
extreme_fips = [('54047', 'Extreme'), ('06085', 'Extreme')]
all_targets = [(f, 'Typical') for f in selected] + extreme_fips

for target_fips, county_type in all_targets:
    n = node_lookup.get(target_fips)
    if not n:
        print(f"  {target_fips}: NOT FOUND in cache")
        continue

    peers_a = compute_top_peers(target_fips, 'equal')
    peers_b = compute_top_peers(target_fips, 'domain')
    peers_c = compute_top_peers(target_fips, 'pca7')

    j_ab = jaccard(peers_a, peers_b)
    j_ac = jaccard(peers_a, peers_c)

    top3_stable = set(peers_a[:3]) == set(peers_b[:3]) == set(peers_c[:3])
    top1_stable = peers_a[0] == peers_b[0] == peers_c[0]

    s = overall_scores.get(target_fips, 0)
    pctl = get_percentile(s)

    print(f"\n{'=' * 50}")
    print(f"{n.get('county_name', target_fips)} ({target_fips}) -- {n.get('region', '?')} [{county_type}]")
    print(f"Overall score: {s:.4f} (P{pctl:.0f})")
    print(f"{'=' * 50}")

    for label, peers in [('Equal', peers_a), ('Domain balanced', peers_b), ('PCA 7', peers_c)]:
        print(f"\n  Top 10 peers -- {label}:")
        for i, pf in enumerate(peers):
            pn = node_lookup.get(pf, {})
            print(f"    {i+1}. {pn.get('county_name', pf)} ({pf})")

    print(f"\n  Stability:")
    print(f"    Jaccard (Equal vs Domain):  {j_ab:.3f}")
    print(f"    Jaccard (Equal vs PCA 7):   {j_ac:.3f}")
    print(f"    Top-3 identical:            {'Yes' if top3_stable else 'No'}")
    print(f"    Top-1 identical:            {'Yes' if top1_stable else 'No'}")

    all_results.append({
        'fips': target_fips,
        'name': n.get('county_name', target_fips),
        'region': n.get('region', '?'),
        'type': county_type,
        'percentile': round(pctl, 1),
        'jaccard_equal_vs_domain': round(j_ab, 3),
        'jaccard_equal_vs_pca7': round(j_ac, 3),
        'top1_stable': top1_stable,
        'top3_stable': top3_stable,
    })

# ── Step 6: Overall verdict ──────────────────────────────────
print("\n" + "=" * 60)
print("STEP 6: OVERALL STABILITY RESULTS")
print("=" * 60)

boundary_results = [r for r in all_results if r['type'] == 'Typical']
extreme_results = [r for r in all_results if r['type'] == 'Extreme']

mean_j_ab = np.mean([r['jaccard_equal_vs_domain'] for r in boundary_results])
mean_j_ac = np.mean([r['jaccard_equal_vs_pca7'] for r in boundary_results])
top1_count = sum(1 for r in boundary_results if r['top1_stable'])

print(f"Mean Jaccard (Equal vs Domain): {mean_j_ab:.3f}")
print(f"Mean Jaccard (Equal vs PCA 7):  {mean_j_ac:.3f}")
print(f"Top-1 stable: {top1_count}/{len(boundary_results)} counties")

if mean_j_ab > 0.7 and mean_j_ac > 0.7:
    verdict = "stable"
    verdict_text = ("STABLE: Peer discovery is robust for typical counties. "
                    "The robustness claim is fully supported for both extreme and typical county profiles.")
elif min(mean_j_ab, mean_j_ac) >= 0.5:
    verdict = "moderate"
    verdict_text = ("MODERATELY STABLE: Core peers consistent, full top-10 shows some sensitivity. "
                    "Disclose that peer rankings for median-profile counties are indicative rather than definitive.")
else:
    verdict = "unstable"
    verdict_text = ("WEIGHTING SENSITIVE: Peer discovery for typical counties depends meaningfully on weighting choice. "
                    "This must be disclosed prominently. The robustness claim should be qualified to extreme counties only.")

print(f"\nVerdict: {verdict_text}")

# ── Step 7: Comparison table ─────────────────────────────────
print("\n" + "=" * 60)
print("STEP 7: COMPARISON TABLE")
print("=" * 60)
print(f"{'County':<28} {'Type':<9} {'J(A,B)':<10} {'J(A,C)':<10}")
print("-" * 57)
for r in all_results:
    print(f"{r['name']:<28} {r['type']:<9} {r['jaccard_equal_vs_domain']:<10.3f} {r['jaccard_equal_vs_pca7']:<10.3f}")

# ── Step 8: Save ─────────────────────────────────────────────
output = {
    'boundary_counties': boundary_results,
    'extreme_counties': extreme_results,
    'mean_jaccard_equal_vs_domain': round(mean_j_ab, 3),
    'mean_jaccard_equal_vs_pca7': round(mean_j_ac, 3),
    'top1_stable_count': top1_count,
    'verdict': verdict,
    'verdict_text': verdict_text,
}

with open('data/peer_stability_analysis.json', 'w') as f:
    json.dump(output, f, indent=2)
print("\nSaved to data/peer_stability_analysis.json")
