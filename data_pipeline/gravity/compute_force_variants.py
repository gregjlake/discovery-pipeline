"""Compute force variant fields (dist affinity, pop residual) for gravity cache."""
import numpy as np, json, pandas as pd
from scipy.stats import linregress

with open('data/gravity_map_cache.json') as f:
    cache = json.load(f)
with open('data/beta_calibration.json') as f:
    beta_data = json.load(f)

beta = beta_data['beta_operative']
dataset_cols = beta_data['datasets_used']
nodes = cache['nodes']
links = cache['links']

populations = {n['fips']: float(n['population']) for n in nodes}

# Load centroids for geo distance
centroids = pd.read_csv('data/county_centroids.csv', dtype={'fips': str})
centroids['fips'] = centroids['fips'].str.zfill(5)
cent = dict(zip(centroids['fips'], zip(centroids['lat'], centroids['lon'])))

def haversine(f1, f2):
    R = 3958.8
    lat1, lon1 = cent.get(f1, (39.5, -98.35))
    lat2, lon2 = cent.get(f2, (39.5, -98.35))
    rl = np.radians
    dlat = rl(lat2 - lat1); dlon = rl(lon2 - lon1)
    a = (np.sin(dlat/2)**2 +
         np.cos(rl(lat1)) * np.cos(rl(lat2)) * np.sin(dlon/2)**2)
    return R * 2 * np.arcsin(np.sqrt(np.clip(a, 0, 1)))

# Build normalized vectors from cache node datasets
# First compute min/max for each dataset across all nodes
raw_vals = {col: [] for col in dataset_cols}
for n in nodes:
    ds = n.get('datasets', {})
    for col in dataset_cols:
        v = ds.get(col)
        if v is not None:
            raw_vals[col].append(v)

col_min = {col: min(raw_vals[col]) if raw_vals[col] else 0 for col in dataset_cols}
col_max = {col: max(raw_vals[col]) if raw_vals[col] else 1 for col in dataset_cols}

# Build normalized vectors per county
vec = {}
for n in nodes:
    ds = n.get('datasets', {})
    v = []
    for col in dataset_cols:
        raw = ds.get(col)
        if raw is None:
            v.append(0.5)  # fallback for missing
        else:
            rng = col_max[col] - col_min[col]
            v.append((raw - col_min[col]) / rng if rng > 0 else 0.5)
    vec[n['fips']] = np.array(v)

print(f"Computing variants for {len(links)} links, beta={beta:.4f}...")

raw_forces, dist_forces, pop_products = [], [], []
link_pairs = []

for l in links:
    s, t = l['source'], l['target']
    pop_i = populations.get(s, 1)
    pop_j = populations.get(t, 1)
    pop_prod = pop_i * pop_j

    geo = haversine(s, t)
    geo_norm = geo / 5251.0

    vi = vec.get(s, np.full(len(dataset_cols), 0.5))
    vj = vec.get(t, np.full(len(dataset_cols), 0.5))
    data_d = np.linalg.norm(vi - vj)
    data_norm = data_d / np.sqrt(len(dataset_cols))

    combined = max(geo_norm * data_norm, 0.01)

    raw_forces.append(l['force_strength'])
    dist_forces.append(1.0 / (combined ** beta))
    pop_products.append(pop_prod)
    link_pairs.append((s, t))

# Normalize distance affinity
dist_arr = np.array(dist_forces)
dist_norm = dist_arr / dist_arr.max()

# Population residual via OLS on log scale
log_raw = np.log(np.array(raw_forces) + 1e-10)
log_pop = np.log(np.array(pop_products) + 1e-10)
slope, intercept, r, p, se = linregress(log_pop, log_raw)
predicted = slope * log_pop + intercept
residuals = log_raw - predicted
res_min, res_max = residuals.min(), residuals.max()
res_norm = (residuals - res_min) / (res_max - res_min + 1e-10)

pop_r2 = round(float(r**2) * 100, 1)
print(f"Population explains {pop_r2}% of force variance")
print(f"Residual view isolates the remaining {round(100 - pop_r2, 1)}%")

# Print top 5 for each view
def top5(values, pairs):
    idx = np.argsort(values)[-5:][::-1]
    return [(pairs[i][0], pairs[i][1], float(values[i])) for i in idx]

node_name = {n['fips']: n.get('county_name', n['fips']) for n in nodes}

print("\nTop 5 Raw (population dominated):")
for s, t, v in top5(np.array(raw_forces), link_pairs):
    print(f"  {node_name.get(s,s)} <-> {node_name.get(t,t)}: {v:.3f}")

print("\nTop 5 Distance Affinity (population removed):")
for s, t, v in top5(dist_norm, link_pairs):
    print(f"  {node_name.get(s,s)} <-> {node_name.get(t,t)}: {v:.3f}")

print("\nTop 5 Population Residual (unexpected attraction):")
for s, t, v in top5(res_norm, link_pairs):
    print(f"  {node_name.get(s,s)} <-> {node_name.get(t,t)}: {v:.3f}")

# Update cache
for i, l in enumerate(cache['links']):
    l['force_raw'] = raw_forces[i]
    l['force_dist'] = float(dist_norm[i])
    l['force_residual'] = float(res_norm[i])

cache['metadata']['force_variants'] = {
    'raw': 'Pop(i)*Pop(j)/dist^beta - absolute interaction',
    'dist_affinity': '1/dist^beta - socioeconomic affinity only',
    'pop_residual': 'Excess attraction beyond population prediction'
}
cache['metadata']['pop_explains_force_pct'] = pop_r2

with open('data/gravity_map_cache.json', 'w') as f:
    json.dump(cache, f)
print("\nCache updated with force variants.")
