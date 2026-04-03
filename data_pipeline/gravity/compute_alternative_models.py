"""Compute alternative gravity models for dataset selection feature."""
import json
import os
import sys
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.spatial.distance import cdist
from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parent.parent.parent / ".env", override=False)
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

DATA_DIR = Path(__file__).resolve().parent.parent.parent / "data"

# All 29 active datasets
ALL_DATASETS = {
    "library": "library_spend_per_capita",
    "air": "air_quality_inv", "broadband": "broadband_rate",
    "eitc": "eitc_rate", "poverty": "poverty_rate",
    "median_income": "median_hh_income", "bea_income": "per_capita_income",
    "food_access": "pct_low_food_access", "obesity": "obesity_rate",
    "diabetes": "diabetes_rate", "mental_health": "mental_health_rate",
    "hypertension": "hypertension_rate", "unemployment": "unemployment_rate",
    "rural_urban": "rural_urban_code", "housing_burden": "housing_burden_rate",
    "voter_turnout": "voter_turnout_rate", "pop_density": "pop_density",
    "bachelors_rate": "bachelors_rate", "median_age": "median_age",
    "homeownership_rate": "homeownership_rate",
    "child_poverty_rate": "child_poverty_rate", "single_parent_rate": "single_parent_rate",
    "foreign_born_pct": "foreign_born_pct", "language_isolation_rate": "language_isolation_rate",
    "manufacturing_pct": "manufacturing_pct", "agriculture_pct": "agriculture_pct",
    "housing_vacancy_rate": "housing_vacancy_rate", "median_home_value": "median_home_value",
    "population_change_pct": "population_change_pct",
}

COMBINATIONS = [
    {
        "id": "economic",
        "label": "Economic conditions",
        "description": "Clusters by poverty, income, economic mobility, and labor market. Isolates the dominant axis of American inequality (PC1 = 41.8% of variance).",
        "datasets": ["poverty", "eitc", "median_income", "bea_income", "unemployment", "mobility"],
    },
    {
        "id": "health",
        "label": "Health outcomes",
        "description": "Clusters by chronic disease burden independent of economic conditions. Reveals the geography of the American health crisis.",
        "datasets": ["obesity", "diabetes", "hypertension", "mental_health"],
    },
    {
        "id": "infrastructure",
        "label": "Infrastructure & environment",
        "description": "Clusters by access to services and environmental quality. Shows infrastructure character beyond economic conditions.",
        "datasets": ["broadband", "library", "air", "food_access"],
    },
    {
        "id": "civic",
        "label": "Civic & demographic",
        "description": "Clusters by political participation, urban character, and housing stress. Reveals geographic patterns in civic life.",
        "datasets": ["voter_turnout", "rural_urban", "pop_density", "housing_burden"],
    },
]


def load_shared():
    """Load data shared across all combinations."""
    with open(DATA_DIR / "beta_calibration.json") as f:
        cal = json.load(f)
    beta = cal["beta_operative"]

    # Load raw values from Supabase
    from supabase import create_client
    sb = create_client(os.environ["SUPABASE_URL"], os.environ["SUPABASE_SERVICE_KEY"])

    all_rows = []
    offset = 0
    while True:
        r = sb.table("raw_values").select("fips,dataset_id,column_name,value").range(offset, offset + 999).execute()
        if not r.data:
            break
        all_rows.extend(r.data)
        if len(r.data) < 1000:
            break
        offset += 1000

    rv = pd.DataFrame(all_rows)
    rv = rv[rv["dataset_id"].isin(ALL_DATASETS.keys())]
    pivot = rv.pivot_table(index="fips", columns="dataset_id", values="value", aggfunc="first").reset_index()
    pivot["fips"] = pivot["fips"].astype(str).str.zfill(5)

    # Min-max normalize all columns
    ds_cols = [c for c in pivot.columns if c in ALL_DATASETS]
    for c in ds_cols:
        s = pivot[c].astype(float)
        mn, mx = s.min(), s.max()
        pivot[c] = (s - mn) / (mx - mn) if mx > mn else 0.5

    # Load populations
    pop = pd.read_csv(DATA_DIR / "county_population.csv", dtype={"fips": str})
    pop["fips"] = pop["fips"].str.zfill(5)

    # Load centroids
    cent = pd.read_csv(DATA_DIR / "county_centroids.csv", dtype={"fips": str})
    cent["fips"] = cent["fips"].str.zfill(5)

    # Merge
    merged = cent.merge(pop[["fips", "population"]], on="fips", how="inner")
    merged = merged.merge(pivot, on="fips", how="inner")

    fips_list = merged["fips"].values
    populations = merged["population"].values.astype(float)
    print(f"Counties: {len(fips_list)}")

    # Geo distance matrix
    lats = np.radians(merged["lat"].values)
    lons = np.radians(merged["lon"].values)
    dlat = lats[:, None] - lats[None, :]
    dlon = lons[:, None] - lons[None, :]
    a = np.sin(dlat / 2) ** 2 + np.cos(lats[:, None]) * np.cos(lats[None, :]) * np.sin(dlon / 2) ** 2
    geo_dist = 3958.8 * 2 * np.arcsin(np.sqrt(np.clip(a, 0, 1)))
    geo_norm = geo_dist / geo_dist.max()
    print(f"Geo matrix: {geo_norm.shape}")

    # Load main cache for nodes
    with open(DATA_DIR / "gravity_map_cache.json") as f:
        main_cache = json.load(f)

    return merged, fips_list, populations, geo_norm, beta, main_cache, ds_cols


def compute_combination(combo, merged, fips_list, populations, geo_norm, beta, main_cache):
    print(f"\n=== Computing: {combo['label']} ===")
    ds_names = combo["datasets"]
    actual_cols = [d for d in ds_names if d in merged.columns]
    print(f"  Datasets: {actual_cols} ({len(actual_cols)}/{len(ds_names)})")

    if len(actual_cols) < 2:
        print("  ERROR: Insufficient columns")
        return None

    vectors = merged[actual_cols].fillna(0.5).values.astype(float)
    n = len(fips_list)

    # Data dissimilarity
    dissim = cdist(vectors, vectors, metric="euclidean")
    dmax = dissim.max()
    dissim_norm = dissim / dmax if dmax > 0 else dissim

    # Combined distance
    combined = geo_norm * dissim_norm
    combined = np.maximum(combined, 0.01)
    np.fill_diagonal(combined, combined.max() * 10)

    # Top-50 neighbors per county
    print(f"  Computing forces for {n} counties...")
    all_links = []
    for i in range(n):
        forces = populations[i] * populations / (combined[i] ** beta)
        forces[i] = 0
        top_idx = np.argpartition(forces, -50)[-50:]
        top_idx = top_idx[np.argsort(forces[top_idx])[::-1]]
        for j in top_idx:
            all_links.append({
                "source": fips_list[i],
                "target": fips_list[j],
                "raw_force": float(forces[j]),
            })
        if (i + 1) % 1000 == 0:
            print(f"    {i+1}/{n}...")

    # Normalize and take top 10K
    max_f = max(l["raw_force"] for l in all_links) if all_links else 1
    for l in all_links:
        l["force_strength"] = round(l["raw_force"] / max_f, 6)
        del l["raw_force"]
    all_links.sort(key=lambda x: -x["force_strength"])
    top_links = all_links[:10000]

    # Print top 5
    nodes_by_fips = {n["fips"]: n for n in main_cache["nodes"]}
    print(f"  Top 5 links:")
    for l in top_links[:5]:
        src = nodes_by_fips.get(l["source"], {}).get("county_name", "?")
        tgt = nodes_by_fips.get(l["target"], {}).get("county_name", "?")
        print(f"    {src} <-> {tgt}: {l['force_strength']:.3f}")

    # Build cache — EXCLUDE nodes to save space (reference main cache)
    cache = {
        "combination_id": combo["id"],
        "combination_label": combo["label"],
        "combination_description": combo["description"],
        "datasets_used": ds_names,
        "n_datasets": len(actual_cols),
        "links": top_links,
    }

    fname = DATA_DIR / f"gravity_cache_{combo['id']}.json"
    with open(fname, "w") as f:
        json.dump(cache, f)
    sz = fname.stat().st_size / 1024
    print(f"  Saved: {fname.name} ({sz:.0f} KB, {len(top_links)} links)")
    return cache


def main():
    merged, fips_list, populations, geo_norm, beta, main_cache, ds_cols = load_shared()

    for combo in COMBINATIONS:
        compute_combination(combo, merged, fips_list, populations, geo_norm, beta, main_cache)

    # Top-link comparison
    print("\n=== TOP LINK COMPARISON ACROSS COMBINATIONS ===")
    nodes_by_fips = {n["fips"]: n for n in main_cache["nodes"]}
    top_pairs = set()
    for combo in COMBINATIONS:
        fname = DATA_DIR / f"gravity_cache_{combo['id']}.json"
        if fname.exists():
            with open(fname) as f:
                c = json.load(f)
            if c["links"]:
                top = c["links"][0]
                src = nodes_by_fips.get(top["source"], {}).get("county_name", "?")[:25]
                tgt = nodes_by_fips.get(top["target"], {}).get("county_name", "?")[:25]
                print(f"  {combo['id']:15s}: {src} <-> {tgt} ({top['force_strength']:.3f})")
                top_pairs.add((top["source"], top["target"]))

    if len(top_pairs) == 1:
        print("\n  WARNING: All combinations have same top link.")
        print("  Population mass overrides distance (beta=0.14).")
        print("  Check links 2-20 for diversity.")
    else:
        print(f"\n  Different top links across combinations.")


if __name__ == "__main__":
    main()
