"""Pre-compute deterministic Fruchterman-Reingold layout for gravity map dots view."""
import json
import sys

import networkx as nx
import numpy as np

print("Loading cache...")
with open('data/gravity_map_cache.json') as f:
    cache = json.load(f)

nodes = cache['nodes']
links = cache['links']
fips_list = [n['fips'] for n in nodes]

# Skip if layout already computed and dataset count unchanged
n_datasets = len(cache.get('metadata', {}).get('calibration_source', '').split(','))
has_positions = nodes[0].get('x_computed') is not None if nodes else False
cached_n = cache.get('metadata', {}).get('layout_n_datasets')
current_n = len(nodes[0].get('datasets', {})) if nodes else 0

if has_positions and cached_n == current_n:
    print(f"Layout unchanged (n_datasets={current_n}) -- skipping")
    sys.exit(0)

# Build sparse graph: top 5,000 links by force_strength (not all 159K)
sorted_links = sorted(links, key=lambda l: l.get('force_strength', 0), reverse=True)
top_links = sorted_links[:5000]

G = nx.Graph()
for n in nodes:
    G.add_node(n['fips'], population=n['population'])
for l in top_links:
    fs = l.get('force_strength', 0)
    if fs > 0:
        G.add_edge(l['source'], l['target'], weight=fs)

print(f"Graph: {G.number_of_nodes()} nodes, {G.number_of_edges()} edges")

# Initial positions from geographic centroids
lats = np.array([n['initial_lat'] for n in nodes])
lons = np.array([n['initial_lon'] for n in nodes])
lon_n = (lons - lons.min()) / (lons.max() - lons.min())
lat_n = (lats - lats.min()) / (lats.max() - lats.min())
pos_init = {
    n['fips']: np.array([lon_n[i], 1 - lat_n[i]])
    for i, n in enumerate(nodes)
}

print("Computing Fruchterman-Reingold layout...")
print("(seed=42, 50 iterations, 5K links)")
pos = nx.spring_layout(
    G,
    pos=pos_init,
    k=0.15,
    weight='weight',
    iterations=50,
    seed=42
)
print("Done.")

W, H, PAD = 900, 700, 60
xs = np.array([pos[f][0] for f in fips_list])
ys = np.array([pos[f][1] for f in fips_list])
x_s = (xs - xs.min()) / (xs.max() - xs.min() + 1e-10)
y_s = (ys - ys.min()) / (ys.max() - ys.min() + 1e-10)
x_px = x_s * (W - 2 * PAD) + PAD
y_px = y_s * (H - 2 * PAD) + PAD

for i, n in enumerate(cache['nodes']):
    n['x_computed'] = round(float(x_px[i]), 2)
    n['y_computed'] = round(float(y_px[i]), 2)

cache['metadata']['layout_precomputed'] = True
cache['metadata']['layout_method'] = 'Fruchterman-Reingold (NetworkX spring_layout)'
cache['metadata']['layout_seed'] = 42
cache['metadata']['layout_iterations'] = 50
cache['metadata']['layout_note'] = 'Deterministic layout -- identical for all users'
cache['metadata']['layout_n_datasets'] = current_n

with open('data/gravity_map_cache.json', 'w') as f:
    json.dump(cache, f)

print("Positions saved.")
for fips, name in [('06037', 'LA'), ('17031', 'Cook'), ('48201', 'Harris TX'), ('54047', 'McDowell WV')]:
    if fips in pos:
        i = fips_list.index(fips)
        print(f"  {name}: x={x_px[i]:.1f}, y={y_px[i]:.1f}")
