"""Compare equal vs cluster vs PCA-7 weighting for gravity model validation."""
import numpy as np
import pandas as pd
import json
from scipy.stats import spearmanr
from sklearn.preprocessing import StandardScaler
from sklearn.decomposition import PCA

np.random.seed(42)

# --Load data --──────────────────────────────────────────────
with open('data/beta_calibration.json') as f:
    beta_data = json.load(f)
with open('data/gravity_map_cache.json') as f:
    cache = json.load(f)

beta = beta_data['beta_operative']
dataset_cols = beta_data['datasets_used']
print(f"Beta: {beta:.6f}")
print(f"Datasets: {len(dataset_cols)}")

nodes = cache['nodes']
centroids = pd.read_csv('data/county_centroids.csv', dtype={'fips': str})
centroids['fips'] = centroids['fips'].str.zfill(5)
cent = dict(zip(centroids['fips'], zip(centroids['lat'].astype(float), centroids['lon'].astype(float))))

pop_df = pd.read_csv('data/county_population.csv', dtype={'fips': str})
pop_df['fips'] = pop_df['fips'].str.zfill(5)
populations = dict(zip(pop_df['fips'], pop_df['population'].astype(float)))

irs = pd.read_csv('data/irs_migration_validation.csv', dtype={'origin_fips': str, 'dest_fips': str})
irs['origin_fips'] = irs['origin_fips'].str.zfill(5)
irs['dest_fips'] = irs['dest_fips'].str.zfill(5)
print(f"IRS migration pairs: {len(irs)}")

# --Step 1: Define cluster weights --────────────────────────
clusters = {
    'Economic deprivation': ['poverty', 'eitc', 'median_income', 'bea_income', 'unemployment', 'mobility'],
    'Health outcomes': ['obesity', 'diabetes', 'hypertension', 'mental_health'],
    'Infrastructure & environment': ['broadband', 'food_access', 'housing_burden', 'air'],
    'Civic & demographic': ['voter_turnout', 'library', 'rural_urban', 'pop_density'],
}

# Verify all datasets accounted for
all_cluster_vars = []
for vs in clusters.values():
    all_cluster_vars.extend(vs)
assert set(all_cluster_vars) == set(dataset_cols), f"Mismatch: {set(dataset_cols) - set(all_cluster_vars)}"

# Each cluster gets 25%, split equally within
weights_cluster = {}
for cluster_name, vars_list in clusters.items():
    w = 0.25 / len(vars_list)
    for v in vars_list:
        weights_cluster[v] = w

print("\n--Step 1: Cluster Weights --")
for cluster_name, vars_list in clusters.items():
    w = 0.25 / len(vars_list)
    print(f"  {cluster_name} ({len(vars_list)} vars, each = {w:.4f}):")
    for v in vars_list:
        print(f"    {v}: {w:.4f}")

# Weight array in dataset_cols order
w_cluster = np.array([weights_cluster[c] for c in dataset_cols])
# Equal weight array
w_equal = np.ones(len(dataset_cols)) / len(dataset_cols)

# PCA 7 columns
pca7_cols = ['poverty', 'mobility', 'median_income', 'unemployment', 'obesity', 'diabetes', 'rural_urban']
pca7_idx = [dataset_cols.index(c) for c in pca7_cols]

# --Build normalized vectors from cache --───────────────────
raw_vals = {col: [] for col in dataset_cols}
for n in nodes:
    ds = n.get('datasets', {})
    for col in dataset_cols:
        v = ds.get(col)
        if v is not None:
            raw_vals[col].append(v)

col_min = {col: min(raw_vals[col]) if raw_vals[col] else 0 for col in dataset_cols}
col_max = {col: max(raw_vals[col]) if raw_vals[col] else 1 for col in dataset_cols}

fips_to_vec = {}
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
    fips_to_vec[n['fips']] = np.array(v)

fips_list = [n['fips'] for n in nodes]
print(f"\nNodes with vectors: {len(fips_to_vec)}")

# --Haversine --─────────────────────────────────────────────
def haversine(f1, f2):
    R = 3958.8
    lat1, lon1 = cent.get(f1, (39.5, -98.35))
    lat2, lon2 = cent.get(f2, (39.5, -98.35))
    rl = np.radians
    dlat = rl(lat2 - lat1); dlon = rl(lon2 - lon1)
    a = np.sin(dlat/2)**2 + np.cos(rl(lat1)) * np.cos(rl(lat2)) * np.sin(dlon/2)**2
    return R * 2 * np.arcsin(np.sqrt(np.clip(a, 0, 1)))

# --Step 3: Sample 250k pairs and compute distances --───────
print("\n--Step 3: Sampling 250,000 pairs --")
n_pairs = 250000
pairs = set()
while len(pairs) < n_pairs:
    batch = np.random.choice(len(fips_list), size=(n_pairs * 2, 2))
    for i, j in batch:
        if i != j:
            a, b = min(i, j), max(i, j)
            pairs.add((a, b))
            if len(pairs) >= n_pairs:
                break

pairs = list(pairs)[:n_pairs]
print(f"Sampled {len(pairs)} unique pairs")

# Compute forces for all three variants
force_A = np.zeros(n_pairs)  # equal weight
force_B = np.zeros(n_pairs)  # cluster weight
force_C = np.zeros(n_pairs)  # PCA 7

sqrt_w_cluster = np.sqrt(w_cluster * len(dataset_cols))  # scale so total variance comparable
sqrt_w_equal = np.ones(len(dataset_cols))

pair_fips = []
for idx, (i, j) in enumerate(pairs):
    fi, fj = fips_list[i], fips_list[j]
    pair_fips.append((fi, fj))

    pop_i = populations.get(fi, 1000)
    pop_j = populations.get(fj, 1000)
    pop_prod = pop_i * pop_j

    geo = haversine(fi, fj)
    geo_norm = geo / 5251.0

    vi = fips_to_vec.get(fi, np.full(len(dataset_cols), 0.5))
    vj = fips_to_vec.get(fj, np.full(len(dataset_cols), 0.5))

    # Variant A: equal weight euclidean
    diff_a = vi - vj
    data_dissim_a = np.linalg.norm(diff_a)

    # Variant B: cluster weighted euclidean
    diff_b = (vi - vj) * sqrt_w_cluster
    data_dissim_b = np.linalg.norm(diff_b)

    # Variant C: PCA 7 cols only
    diff_c = vi[pca7_idx] - vj[pca7_idx]
    data_dissim_c = np.linalg.norm(diff_c)

    for variant_idx, data_dissim in enumerate([data_dissim_a, data_dissim_b, data_dissim_c]):
        data_norm = data_dissim / np.sqrt(len(dataset_cols) if variant_idx < 2 else 7)
        combined = max(geo_norm * data_norm, 0.01)
        force = pop_prod / (combined ** beta)
        if variant_idx == 0:
            force_A[idx] = force
        elif variant_idx == 1:
            force_B[idx] = force
        else:
            force_C[idx] = force

# Normalize forces to [0,1]
force_A = force_A / force_A.max()
force_B = force_B / force_B.max()
force_C = force_C / force_C.max()

print(f"Forces computed. Max raw values normalized.")

# --Step 4: Validate against IRS migration --────────────────
print("\n--Step 4: IRS Migration Validation --")

# Build lookup from pair → force
pair_lookup_A = {}
pair_lookup_B = {}
pair_lookup_C = {}
for idx, (fi, fj) in enumerate(pair_fips):
    key = (fi, fj)
    key_rev = (fj, fi)
    pair_lookup_A[key] = force_A[idx]
    pair_lookup_A[key_rev] = force_A[idx]
    pair_lookup_B[key] = force_B[idx]
    pair_lookup_B[key_rev] = force_B[idx]
    pair_lookup_C[key] = force_C[idx]
    pair_lookup_C[key_rev] = force_C[idx]

observed = []
pred_A = []
pred_B = []
pred_C = []
matched = 0

for _, row in irs.iterrows():
    o, d = row['origin_fips'], row['dest_fips']
    key = (o, d)
    fa = pair_lookup_A.get(key)
    fb = pair_lookup_B.get(key)
    fc = pair_lookup_C.get(key)
    if fa is not None:
        observed.append(float(row['flow']))
        pred_A.append(fa)
        pred_B.append(fb)
        pred_C.append(fc)
        matched += 1

print(f"IRS pairs matched to sampled pairs: {matched} / {len(irs)}")

rho_A, p_A = spearmanr(observed, pred_A)
rho_B, p_B = spearmanr(observed, pred_B)
rho_C, p_C = spearmanr(observed, pred_C)

print(f"  Variant A (Equal):   rho = {rho_A:.4f}  (p = {p_A:.2e})")
print(f"  Variant B (Cluster): rho = {rho_B:.4f}  (p = {p_B:.2e})")
print(f"  Variant C (PCA 7):   rho = {rho_C:.4f}  (p = {p_C:.2e})")

# --Effective dimensions for each variant --─────────────────
print("\n--Effective Dimensions --")

# Build data matrix from cache nodes (normalized)
data_matrix = np.array([fips_to_vec[f] for f in fips_list])

# A: equal weight
pca_a = PCA()
pca_a.fit(StandardScaler().fit_transform(data_matrix))
var_a = pca_a.explained_variance_ratio_
eff_a = float(1 / np.sum(var_a**2))

# B: cluster weighted
weighted_matrix = data_matrix * sqrt_w_cluster[np.newaxis, :]
pca_b = PCA()
pca_b.fit(StandardScaler().fit_transform(weighted_matrix))
var_b = pca_b.explained_variance_ratio_
eff_b = float(1 / np.sum(var_b**2))

# C: PCA 7 cols
pca7_matrix = data_matrix[:, pca7_idx]
pca_c = PCA()
pca_c.fit(StandardScaler().fit_transform(pca7_matrix))
var_c = pca_c.explained_variance_ratio_
eff_c = float(1 / np.sum(var_c**2))

# Economic domain share for each
econ_vars = ['poverty', 'eitc', 'median_income', 'bea_income', 'unemployment', 'mobility']
econ_share_a = len(econ_vars) / len(dataset_cols) * 100
econ_share_b = 25.0  # by construction
econ_pca7 = sum(1 for v in pca7_cols if v in econ_vars) / len(pca7_cols) * 100

print(f"  A (Equal):   eff_dims = {eff_a:.2f}  economic share = {econ_share_a:.0f}%")
print(f"  B (Cluster): eff_dims = {eff_b:.2f}  economic share = {econ_share_b:.0f}%")
print(f"  C (PCA 7):   eff_dims = {eff_c:.2f}  economic share = {econ_pca7:.0f}%")

# --Step 5: Print Results Table --───────────────────────────
print("\n" + "="*70)
print("COMPARISON TABLE")
print("="*70)
print(f"{'Weighting scheme':<22} {'IRS rho':>8} {'Eff dims':>10} {'Econ share':>12}")
print("-"*54)
print(f"{'A: Equal (current)':<22} {rho_A:>8.4f} {eff_a:>10.2f} {econ_share_a:>11.0f}%")
print(f"{'B: Cluster balanced':<22} {rho_B:>8.4f} {eff_b:>10.2f} {econ_share_b:>11.0f}%")
print(f"{'C: PCA 7 components':<22} {rho_C:>8.4f} {eff_c:>10.2f} {econ_pca7:>11.0f}%")
print("-"*54)

# Decision logic
print("\n--Decision Logic --")
diff_BA = rho_B - rho_A
diff_CA = rho_C - rho_A

if diff_BA > 0.005:
    print(f"B vs A: Cluster weighting IMPROVES migration prediction by +{diff_BA:.4f}.")
    print("  Strong case to make it the new default or at minimum a prominently recommended option.")
elif diff_BA < -0.005:
    print(f"B vs A: Cluster weighting REDUCES migration prediction by {-diff_BA:.4f}.")
    print("  Economic dominance in equal weighting is helping predict migration because migration")
    print("  IS economically driven. This is itself a finding.")
    print("  Recommend: keep equal weighting as default, offer cluster as research alternative.")
else:
    print(f"B vs A: Cluster weighting produces EQUIVALENT migration prediction (diff = {diff_BA:+.4f}).")
    print("  The choice between equal and cluster weighting is a philosophical one about construct")
    print("  validity, not an empirical one. Recommend: offer both, explain the tradeoff.")

print()
if diff_CA > 0.005:
    print(f"C vs A: PCA 7 IMPROVES migration prediction by +{diff_CA:.4f}.")
elif diff_CA < -0.005:
    print(f"C vs A: PCA 7 REDUCES migration prediction by {-diff_CA:.4f}.")
    print("  Dropping 11 datasets loses meaningful signal.")
else:
    print(f"C vs A: PCA 7 produces EQUIVALENT migration prediction (diff = {diff_CA:+.4f}).")

# --Step 6: Spot Check Peers --──────────────────────────────
print("\n--Step 6: Peer Spot Check --")

node_name = {n['fips']: n.get('county_name', n['fips']) for n in nodes}

def find_top_peers(target_fips, force_lookup, n=5):
    """Find top N peers by force for a given county."""
    scores = []
    for idx, (fi, fj) in enumerate(pair_fips):
        if fi == target_fips:
            scores.append((fj, force_lookup[idx]))
        elif fj == target_fips:
            scores.append((fi, force_lookup[idx]))
    scores.sort(key=lambda x: x[1], reverse=True)
    return [(node_name.get(f, f), round(s, 4)) for f, s in scores[:n]]

for target, label in [('54047', 'McDowell WV'), ('06085', 'Santa Clara CA')]:
    print(f"\n  {label} ({target}) peers:")
    for variant_name, forces in [('Equal', force_A), ('Cluster', force_B), ('PCA 7', force_C)]:
        peers = find_top_peers(target, forces)
        peer_str = ", ".join(f"{name}({s:.3f})" for name, s in peers)
        print(f"    {variant_name:>8}: {peer_str}")

# --Save results --──────────────────────────────────────────
results = {
    'variants': {
        'A_equal': {'rho': round(rho_A, 4), 'p': float(p_A), 'eff_dims': round(eff_a, 2), 'econ_share_pct': round(econ_share_a, 1)},
        'B_cluster': {'rho': round(rho_B, 4), 'p': float(p_B), 'eff_dims': round(eff_b, 2), 'econ_share_pct': round(econ_share_b, 1)},
        'C_pca7': {'rho': round(rho_C, 4), 'p': float(p_C), 'eff_dims': round(eff_c, 2), 'econ_share_pct': round(econ_pca7, 1)},
    },
    'cluster_weights': {k: round(v, 4) for k, v in weights_cluster.items()},
    'irs_pairs_matched': matched,
    'n_sampled_pairs': n_pairs,
    'beta_used': beta,
    'decision_B_vs_A': 'improves' if diff_BA > 0.005 else 'reduces' if diff_BA < -0.005 else 'equivalent',
    'decision_C_vs_A': 'improves' if diff_CA > 0.005 else 'reduces' if diff_CA < -0.005 else 'equivalent',
}

with open('data/weighting_comparison.json', 'w') as f:
    json.dump(results, f, indent=2)
print("\nResults saved to data/weighting_comparison.json")
