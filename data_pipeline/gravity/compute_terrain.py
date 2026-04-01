"""Compute gravitational potential terrain for 3D visualization."""
import json
import os
import sys
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.preprocessing import StandardScaler
from sklearn.decomposition import PCA
from scipy.ndimage import maximum_filter
from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parent.parent.parent / ".env", override=False)
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

DATA_DIR = Path(__file__).resolve().parent.parent.parent / "data"

ALL_DATASETS = {
    "library": "library_spend_per_capita",
    # mobility excluded: temporal mismatch (1978-2015 vs 2022)
    "air": "air_quality_inv", "broadband": "broadband_rate",
    "eitc": "eitc_rate", "poverty": "poverty_rate",
    "median_income": "median_hh_income", "bea_income": "per_capita_income",
    "food_access": "pct_low_food_access", "obesity": "obesity_rate",
    "diabetes": "diabetes_rate", "mental_health": "mental_health_rate",
    "hypertension": "hypertension_rate", "unemployment": "unemployment_rate",
    "rural_urban": "rural_urban_code", "housing_burden": "housing_burden_rate",
    "voter_turnout": "total_votes_2020", "pop_density": "pop_density",
}

REGION_MAP = {
    "Northeast": {"09","23","25","33","44","50","34","36","42"},
    "South": {"10","11","12","13","24","37","45","51","54","01","21","28","47","05","22","40","48"},
    "Midwest": {"17","18","26","39","55","19","20","27","29","31","38","46"},
    "West": {"04","08","16","30","32","35","49","56","02","06","15","41","53"},
}

def get_region(fips):
    st = str(fips).zfill(5)[:2]
    for r, states in REGION_MAP.items():
        if st in states: return r
    return "Unknown"


def main():
    with open(DATA_DIR / "beta_calibration.json") as f:
        cal = json.load(f)
    beta = cal["beta_operative"]

    # Load from Supabase
    from supabase import create_client
    sb = create_client(os.environ["SUPABASE_URL"], os.environ["SUPABASE_SERVICE_KEY"])
    all_rows = []
    offset = 0
    while True:
        r = sb.table("raw_values").select("fips,dataset_id,column_name,value").range(offset, offset+999).execute()
        if not r.data: break
        all_rows.extend(r.data)
        if len(r.data) < 1000: break
        offset += 1000

    rv = pd.DataFrame(all_rows)
    target = set(ALL_DATASETS.items())
    rv = rv[rv.apply(lambda r: (r["dataset_id"], r["column_name"]) in target, axis=1)]
    pivot = rv.pivot_table(index="fips", columns="dataset_id", values="value", aggfunc="first").reset_index()
    pivot["fips"] = pivot["fips"].astype(str).str.zfill(5)

    ds_cols = sorted([c for c in pivot.columns if c in ALL_DATASETS])
    for c in ds_cols:
        s = pivot[c].astype(float)
        mn, mx = s.min(), s.max()
        pivot[c] = (s - mn) / (mx - mn) if mx > mn else 0.5

    pop = pd.read_csv(DATA_DIR / "county_population.csv", dtype={"fips": str})
    pop["fips"] = pop["fips"].str.zfill(5)

    merged = pop[["fips", "population"]].merge(pivot, on="fips", how="inner")
    merged = merged.dropna(subset=ds_cols, thresh=len(ds_cols)-2)
    for c in ds_cols:
        merged[c] = merged[c].astype(float).fillna(merged[c].median())

    fips_list = merged["fips"].values
    populations = merged["population"].values.astype(float)
    pop_norm = populations / populations.max()
    vectors = merged[ds_cols].values.astype(float)

    # PCA to 2D
    scaler = StandardScaler()
    vectors_scaled = scaler.fit_transform(vectors)
    pca = PCA(n_components=2, random_state=42)
    coords_2d = pca.fit_transform(vectors_scaled)

    print(f"Counties: {len(fips_list)}")
    print(f"PC1: {pca.explained_variance_ratio_[0]*100:.1f}%")
    print(f"PC2: {pca.explained_variance_ratio_[1]*100:.1f}%")

    # Check PC1 sign: poverty should load POSITIVE (disadvantaged = positive PC1)
    # Find poverty column index and check its loading
    if "poverty" in ds_cols:
        pov_idx = ds_cols.index("poverty")
        pov_loading = pca.components_[0, pov_idx]
        if pov_loading < 0:
            print(f"  Flipping PC1 (poverty loading = {pov_loading:.3f}, need positive)")
            coords_2d[:, 0] = -coords_2d[:, 0]
        else:
            print(f"  PC1 orientation correct (poverty loading = {pov_loading:.3f})")

    # Clip PC1/PC2 color ranges to 2nd-98th percentile for contrast
    pc1_vals = coords_2d[:, 0]
    pc2_vals = coords_2d[:, 1]
    pc1_color_min = float(np.percentile(pc1_vals, 2))
    pc1_color_max = float(np.percentile(pc1_vals, 98))
    pc2_color_min = float(np.percentile(pc2_vals, 2))
    pc2_color_max = float(np.percentile(pc2_vals, 98))
    print(f"  PC1 color range (p2-p98): [{pc1_color_min:.2f}, {pc1_color_max:.2f}]")
    print(f"  PC2 color range (p2-p98): [{pc2_color_min:.2f}, {pc2_color_max:.2f}]")

    county_positions = [
        {"fips": fips_list[i], "pc1": float(coords_2d[i,0]), "pc2": float(coords_2d[i,1]),
         "population": int(populations[i]), "pop_norm": float(pop_norm[i]),
         "region": get_region(fips_list[i])}
        for i in range(len(fips_list))
    ]

    # Compute potential field
    GRID = 80
    x_min, x_max = coords_2d[:,0].min(), coords_2d[:,0].max()
    y_min, y_max = coords_2d[:,1].min(), coords_2d[:,1].max()
    x_pad = (x_max-x_min)*0.1; y_pad = (y_max-y_min)*0.1
    x_min -= x_pad; x_max += x_pad; y_min -= y_pad; y_max += y_pad

    x_grid = np.linspace(x_min, x_max, GRID)
    y_grid = np.linspace(y_min, y_max, GRID)
    xx, yy = np.meshgrid(x_grid, y_grid)
    grid_points = np.column_stack([xx.ravel(), yy.ravel()])

    print(f"\nComputing potential on {GRID}x{GRID} grid...")
    potential = np.zeros(len(grid_points))
    BATCH = 500
    for bs in range(0, len(grid_points), BATCH):
        be = min(bs+BATCH, len(grid_points))
        batch = grid_points[bs:be]
        diff = batch[:, np.newaxis, :] - coords_2d[np.newaxis, :, :]
        dist = np.sqrt((diff**2).sum(axis=2))
        dist = np.maximum(dist, 0.01)
        contrib = pop_norm[np.newaxis, :] / (dist ** beta)
        potential[bs:be] = contrib.sum(axis=1)

    potential_grid = potential.reshape(GRID, GRID)
    print(f"Potential range: [{potential_grid.min():.2f}, {potential_grid.max():.2f}]")

    p_min, p_max = potential_grid.min(), potential_grid.max()
    potential_norm = (potential_grid - p_min) / (p_max - p_min)
    potential_log = np.log1p(potential_norm * 10) / np.log1p(10)
    print(f"Log range: [{potential_log.min():.4f}, {potential_log.max():.4f}]")

    # Compute mean PC1 and PC2 per grid cell for representational color
    pc1_grid = np.zeros((GRID, GRID))
    pc2_grid = np.zeros((GRID, GRID))
    pc1_vals = coords_2d[:, 0]
    pc2_vals = coords_2d[:, 1]

    # Map each county to its grid cell
    col_idx = np.clip(((pc1_vals - x_min) / (x_max - x_min) * (GRID - 1)).astype(int), 0, GRID - 1)
    row_idx = np.clip(((pc2_vals - y_min) / (y_max - y_min) * (GRID - 1)).astype(int), 0, GRID - 1)

    cell_pc1_sum = np.zeros((GRID, GRID))
    cell_pc2_sum = np.zeros((GRID, GRID))
    cell_count = np.zeros((GRID, GRID))
    for k in range(len(fips_list)):
        r, c = row_idx[k], col_idx[k]
        cell_pc1_sum[r, c] += pc1_vals[k]
        cell_pc2_sum[r, c] += pc2_vals[k]
        cell_count[r, c] += 1

    # For cells with counties: use mean
    mask = cell_count > 0
    pc1_grid[mask] = cell_pc1_sum[mask] / cell_count[mask]
    pc2_grid[mask] = cell_pc2_sum[mask] / cell_count[mask]
    # For empty cells: use implied PC value from grid position
    for ri in range(GRID):
        for ci in range(GRID):
            if cell_count[ri, ci] == 0:
                pc1_grid[ri, ci] = x_min + (ci / (GRID - 1)) * (x_max - x_min)
                pc2_grid[ri, ci] = y_min + (ri / (GRID - 1)) * (y_max - y_min)

    pc1_range = [float(pc1_vals.min()), float(pc1_vals.max())]
    pc2_range = [float(pc2_vals.min()), float(pc2_vals.max())]
    print(f"PC1 full range: [{pc1_range[0]:.2f}, {pc1_range[1]:.2f}]")
    print(f"PC2 full range: [{pc2_range[0]:.2f}, {pc2_range[1]:.2f}]")
    print(f"Sample cell (40,40): potential={potential_log[40,40]:.4f}, pc1={pc1_grid[40,40]:.3f}, pc2={pc2_grid[40,40]:.3f}")

    # Find wells
    local_max = (potential_log == maximum_filter(potential_log, size=8))
    maxima = sorted(
        [(i, j, float(potential_log[i,j])) for i, j in np.argwhere(local_max)],
        key=lambda x: -x[2]
    )[:10]

    print(f"\nTop 10 gravitational wells:")
    for rank, (i, j, val) in enumerate(maxima):
        print(f"  {rank+1}. PC1={x_grid[j]:.2f}, PC2={y_grid[i]:.2f}, depth={val:.4f}")

    terrain = {
        "grid_size": GRID,
        "x_range": [float(x_min), float(x_max)],
        "y_range": [float(y_min), float(y_max)],
        "x_grid": x_grid.tolist(),
        "y_grid": y_grid.tolist(),
        "potential": potential_log.tolist(),
        "pc1_grid": pc1_grid.tolist(),
        "pc2_grid": pc2_grid.tolist(),
        "pc1_range": pc1_range,
        "pc2_range": pc2_range,
        "pc1_color_range": [pc1_color_min, pc1_color_max],
        "pc2_color_range": [pc2_color_min, pc2_color_max],
        "pc1_label": f"Economic Deprivation (PC1, {pca.explained_variance_ratio_[0]*100:.1f}%)",
        "pc2_label": f"Urbanization (PC2, {pca.explained_variance_ratio_[1]*100:.1f}%)",
        "color_encoding": {
            "hue": "PC1 economic character - blue=prosperous, amber=disadvantaged",
            "brightness": "PC2 urbanization - bright=urban, dim=rural",
            "height": "County density - tall=many similar counties"
        },
        "beta": float(beta),
        "n_counties": len(fips_list),
        "county_positions": county_positions,
        "top_wells": [
            {"rank": rank+1, "pc1": float(x_grid[j]), "pc2": float(y_grid[i]), "depth": float(val)}
            for rank, (i, j, val) in enumerate(maxima)
        ],
    }

    out = DATA_DIR / "gravity_terrain.json"
    with open(out, "w") as f:
        json.dump(terrain, f)
    print(f"\nSaved: {out.name} ({out.stat().st_size/1024:.0f} KB)")

    deepest_pc1 = x_grid[maxima[0][1]]
    print(f"\nDeepest well at PC1={deepest_pc1:.2f}")
    if deepest_pc1 > 0:
        print("Positive PC1 = economic deprivation side. Poor counties cluster most densely.")
    else:
        print("Negative PC1 = prosperous side. Wealthy counties cluster more tightly.")

    try:
        from data_pipeline.utils.storage import upload_to_storage
        upload_to_storage(str(out))
    except Exception as e:
        print(f"  Storage upload skipped: {e}")


if __name__ == "__main__":
    main()
