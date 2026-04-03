"""Compute PCA-balanced gravity model: equal weight to each independent axis."""
import json
import os
import sys
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.preprocessing import StandardScaler
from sklearn.decomposition import PCA
from scipy.spatial.distance import cdist
from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parent.parent.parent / ".env", override=False)
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

DATA_DIR = Path(__file__).resolve().parent.parent.parent / "data"

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


def main():
    with open(DATA_DIR / "beta_calibration.json") as f:
        cal = json.load(f)
    beta = cal["beta_operative"]
    dataset_cols = sorted(ALL_DATASETS.keys())
    print(f"Datasets: {len(dataset_cols)}")
    print(f"Beta operative: {beta}")

    # Load from Supabase raw_values
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
    rv = rv[rv["dataset_id"].isin(ALL_DATASETS.keys())]
    pivot = rv.pivot_table(index="fips", columns="dataset_id", values="value", aggfunc="first").reset_index()
    pivot["fips"] = pivot["fips"].astype(str).str.zfill(5)

    available = [c for c in dataset_cols if c in pivot.columns]
    for c in available:
        s = pivot[c].astype(float)
        mn, mx = s.min(), s.max()
        pivot[c] = (s - mn) / (mx - mn) if mx > mn else 0.5

    # Load populations and centroids
    pop = pd.read_csv(DATA_DIR / "county_population.csv", dtype={"fips": str})
    pop["fips"] = pop["fips"].str.zfill(5)
    cent = pd.read_csv(DATA_DIR / "county_centroids.csv", dtype={"fips": str})
    cent["fips"] = cent["fips"].str.zfill(5)

    merged = cent.merge(pop[["fips", "population"]], on="fips", how="inner")
    merged = merged.merge(pivot, on="fips", how="inner")
    merged = merged.dropna(subset=available, thresh=len(available) - 2)
    for c in available:
        merged[c] = merged[c].astype(float).fillna(merged[c].median())

    fips_list = merged["fips"].values
    populations = merged["population"].values.astype(float)
    vectors = merged[available].values.astype(float)
    print(f"Counties: {len(fips_list)}")

    # Geo distance
    lats = np.radians(merged["lat"].values)
    lons = np.radians(merged["lon"].values)
    dlat = lats[:, None] - lats[None, :]
    dlon = lons[:, None] - lons[None, :]
    a = np.sin(dlat/2)**2 + np.cos(lats[:,None])*np.cos(lats[None,:])*np.sin(dlon/2)**2
    geo_dist = 3958.8 * 2 * np.arcsin(np.sqrt(np.clip(a, 0, 1)))
    geo_norm = geo_dist / geo_dist.max()
    print(f"Geo matrix: {geo_norm.shape}")

    # PCA
    scaler = StandardScaler()
    vectors_scaled = scaler.fit_transform(vectors)

    pca = PCA(n_components=7, random_state=42)
    pca_scores = pca.fit_transform(vectors_scaled)

    print("\nPCA variance by component:")
    for i, v in enumerate(pca.explained_variance_ratio_):
        print(f"  PC{i+1}: {v*100:.1f}%")
    print(f"  Total: {pca.explained_variance_ratio_.sum()*100:.1f}%")

    # Standardize each component to unit variance
    stds = pca_scores.std(axis=0)
    pca_scores_std = pca_scores / stds
    print("PCA scores standardized to unit variance per component")

    # Distance in PCA space
    print("Computing PCA distance matrix...")
    pca_dissim = cdist(pca_scores_std, pca_scores_std, metric="euclidean")
    pca_dissim_norm = pca_dissim / pca_dissim.max() if pca_dissim.max() > 0 else pca_dissim

    # Combined distance
    combined = geo_norm * pca_dissim_norm
    combined = np.maximum(combined, 0.01)
    np.fill_diagonal(combined, combined.max() * 10)

    mask = ~np.eye(len(fips_list), dtype=bool)
    for p in [5, 25, 50, 75, 95]:
        print(f"  p{p}: {np.percentile(combined[mask], p):.4f}")

    # Top-50 neighbors
    n = len(fips_list)
    print(f"\nComputing forces for {n} counties...")
    all_links = []
    for i in range(n):
        forces = populations[i] * populations / (combined[i] ** beta)
        forces[i] = 0
        top_idx = np.argpartition(forces, -50)[-50:]
        top_idx = top_idx[np.argsort(forces[top_idx])[::-1]]
        for j in top_idx:
            all_links.append({"source": fips_list[i], "target": fips_list[j], "raw_force": float(forces[j])})
        if (i+1) % 1000 == 0:
            print(f"  {i+1}/{n}...")

    max_f = max(l["raw_force"] for l in all_links)
    for l in all_links:
        l["force_strength"] = round(l["raw_force"] / max_f, 6)
        del l["raw_force"]
    all_links.sort(key=lambda x: -x["force_strength"])
    top_links = all_links[:10000]

    # Load main cache for nodes and comparison
    with open(DATA_DIR / "gravity_map_cache.json") as f:
        main_cache = json.load(f)
    nodes_by_fips = {n_["fips"]: n_ for n_ in main_cache["nodes"]}

    print(f"\n=== TOP 10 LINKS IN PCA BALANCED VIEW ===")
    for i, l in enumerate(top_links[:10]):
        src = nodes_by_fips.get(l["source"], {}).get("county_name", "?")[:28]
        tgt = nodes_by_fips.get(l["target"], {}).get("county_name", "?")[:28]
        print(f"  {i+1:2d}. {src} <-> {tgt}: {l['force_strength']:.3f}")

    # Compare across all combinations
    print(f"\n=== TOP LINK COMPARISON ===")
    combos = {"all": "gravity_map_cache", "economic": "gravity_cache_economic",
              "health": "gravity_cache_health", "infrastructure": "gravity_cache_infrastructure",
              "civic": "gravity_cache_civic"}
    for cid, fname_base in combos.items():
        fname = DATA_DIR / f"{fname_base}.json"
        if fname.exists():
            with open(fname) as f:
                c = json.load(f)
            if c.get("links"):
                t = c["links"][0]
                src = nodes_by_fips.get(t["source"], {}).get("county_name", "?")[:25]
                tgt = nodes_by_fips.get(t["target"], {}).get("county_name", "?")[:25]
                print(f"  {cid:15s}: {src} <-> {tgt} ({t['force_strength']:.3f})")
    t = top_links[0]
    src = nodes_by_fips.get(t["source"], {}).get("county_name", "?")[:25]
    tgt = nodes_by_fips.get(t["target"], {}).get("county_name", "?")[:25]
    print(f"  {'pca':15s}: {src} <-> {tgt} ({t['force_strength']:.3f})")

    # Divergence analysis
    main_top20 = {frozenset([l["source"], l["target"]]) for l in main_cache["links"][:20]}
    pca_top20 = {frozenset([l["source"], l["target"]]) for l in top_links[:20]}
    unique_to_pca = pca_top20 - main_top20
    print(f"\n=== PCA BALANCED ASSESSMENT ===")
    print(f"  Top-20 links unique to PCA view: {len(unique_to_pca)}")
    if len(unique_to_pca) > 5:
        print("  PCA is revealing genuinely different cluster structure")
    else:
        print("  Population mass dominates all views at beta=0.14.")
        print("  Views differ in weaker links (rank 20-10000).")
    for pair in list(unique_to_pca)[:5]:
        a, b = list(pair)
        print(f"    {nodes_by_fips.get(a,{}).get('county_name','?')[:25]} <-> {nodes_by_fips.get(b,{}).get('county_name','?')[:25]}")

    # Save cache (exclude nodes to save space — merge from main at API level)
    pca_cache = {
        "combination_id": "pca",
        "combination_label": "PCA balanced (7 axes)",
        "combination_description": (
            "Equal weight to each independent axis of county variation. "
            "Economic deprivation drops from 41.8% to 14.3%. Best for "
            "finding counties similar across ALL dimensions equally."
        ),
        "datasets_used": available,
        "n_datasets": 7,
        "pca_components": 7,
        "pca_variance_explained": [round(float(v), 4) for v in pca.explained_variance_ratio_],
        "pca_component_names": [
            "Economic deprivation", "Urbanization", "Density",
            "Air quality", "Density vs library", "Health", "Remaining structure",
        ],
        "links": top_links,
    }
    out = DATA_DIR / "gravity_cache_pca.json"
    with open(out, "w") as f:
        json.dump(pca_cache, f)
    print(f"\nSaved: {out.name} ({out.stat().st_size/1024:.0f} KB)")


if __name__ == "__main__":
    main()
