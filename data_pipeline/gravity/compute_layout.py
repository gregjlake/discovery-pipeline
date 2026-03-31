"""Pre-compute deterministic Fruchterman-Reingold layout for gravity map dots view."""
import networkx as nx
import numpy as np
import json

print("Loading cache...")
with open('data/gravity_map_cache.json') as f:
    cache = json.load(f)

nodes = cache['nodes']
links = cache['links']
fips_list = [n['fips'] for n in nodes]

G = nx.Graph()
for n in nodes:
    G.add_node(n['fips'], population=n['population'])
for l in links:
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
print("(seed=42, 300 iterations — takes 2-5 minutes)")
pos = nx.spring_layout(
    G,
    pos=pos_init,
    k=0.15,
    weight='weight',
    iterations=300,
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
cache['metadata']['layout_iterations'] = 300
cache['metadata']['layout_note'] = 'Deterministic layout — identical for all users'

with open('data/gravity_map_cache.json', 'w') as f:
    json.dump(cache, f)

print("Positions saved.")
for fips, name in [('06037', 'LA'), ('17031', 'Cook'), ('48201', 'Harris TX'), ('54047', 'McDowell WV')]:
    if fips in pos:
        i = fips_list.index(fips)
        print(f"  {name}: x={x_px[i]:.1f}, y={y_px[i]:.1f}")
