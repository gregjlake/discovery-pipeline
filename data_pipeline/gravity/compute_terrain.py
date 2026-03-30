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
    "library": "library_spend_per_capita", "mobility": "mobility_rank_p25",
    "air": "air_quality_inv", "broadband": "broadband_rate",
    "eitc": "eitc_rate", "poverty": "poverty_rate",
    "median_income": "median_hh_income", "bea_income": "per_capita_income",
    "food_access": "snap_rate", "obesity": "obesity_rate",
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
        "pc1_label": f"Economic Deprivation (PC1, {pca.explained_variance_ratio_[0]*100:.1f}%)",
        "pc2_label": f"Urbanization (PC2, {pca.explained_variance_ratio_[1]*100:.1f}%)",
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


if __name__ == "__main__":
    main()
