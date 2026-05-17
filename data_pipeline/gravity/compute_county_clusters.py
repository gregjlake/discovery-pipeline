"""Compute county archetypes via k-means clustering on the active variable space."""
import json
import os
import sys
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.cluster import KMeans
from sklearn.metrics import silhouette_score
from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parent.parent.parent / ".env", override=False)
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

DATA_DIR = Path(__file__).resolve().parent.parent.parent / "data"

CANONICAL_K = 4  # Paper cites k=4 (silhouette=0.218 at 30 variables).
                 # Silhouette-optimal k can drift as datasets expand; pin
                 # to keep paper claims valid. Re-evaluate when adding
                 # variables. Silhouette scores for k=4..11 are still
                 # computed and emitted in the silhouette_scores field
                 # for exploratory comparison.

LABELS = {
    "poverty": "Poverty", "eitc": "EITC", "median_income": "Median Income",
    "bea_income": "Per Capita Income", "unemployment": "Unemployment",
    "obesity": "Obesity", "diabetes": "Diabetes", "hypertension": "Hypertension",
    "mental_health": "Mental Health", "broadband": "Broadband",
    "food_access": "Low Food Access", "housing_burden": "Housing Burden",
    "air": "Air Quality", "voter_turnout": "Voter Turnout", "library": "Library",
    "rural_urban": "Rural-Urban", "pop_density": "Pop Density",
}


def main():
    with open(DATA_DIR / "beta_calibration.json") as f:
        datasets = json.load(f)["datasets_used"]

    df = pd.read_csv(DATA_DIR / "county_data_matrix.csv", dtype={"fips": str})
    df["fips"] = df["fips"].str.zfill(5)
    X = df[datasets].fillna(0.5).values.astype(float)
    fips_list = df["fips"].tolist()

    # Load county names
    pop = pd.read_csv(DATA_DIR / "county_population.csv", dtype={"fips": str})
    pop["fips"] = pop["fips"].str.zfill(5)
    names = dict(zip(pop["fips"], pop["county_name"]))

    print(f"Counties: {len(fips_list)}, Variables: {len(datasets)}")

    # Compute silhouette scores for k=4..11 (exploratory).
    # NOTE: We do NOT pick k by max silhouette anymore — it can drift as
    # datasets expand and breaks the paper's k=4 / silhouette=0.218 claim.
    # CANONICAL_K is pinned above; the silhouette table is emitted in the
    # response for visibility.
    print("\nSilhouette scores (exploratory):")
    sil = {}
    for k in range(4, 12):
        km = KMeans(n_clusters=k, random_state=42, n_init=10)
        labels = km.fit_predict(X)
        s = silhouette_score(X, labels, sample_size=min(1000, len(X)), random_state=42)
        sil[k] = round(float(s), 4)
        print(f"  k={k}: {s:.4f}")

    silhouette_optimal_k = max(sil, key=sil.get)
    print(f"\nSilhouette-optimal k would be: {silhouette_optimal_k} (silhouette={sil[silhouette_optimal_k]:.4f})")
    print(f"Using CANONICAL_K = {CANONICAL_K} (silhouette={sil[CANONICAL_K]:.4f})")
    if silhouette_optimal_k != CANONICAL_K:
        print(f"  NOTE: silhouette-optimal k ({silhouette_optimal_k}) differs from CANONICAL_K ({CANONICAL_K}).")
        print(f"  Re-evaluate CANONICAL_K if dataset coverage has materially changed.")

    # Fit final model with canonical k
    km = KMeans(n_clusters=CANONICAL_K, random_state=42, n_init=10)
    labels = km.fit_predict(X)
    overall_mean = X.mean(axis=0)

    print(f"\n{'='*60}")
    print("CLUSTER PROFILES")
    print("=" * 60)

    clusters = {}
    for cid in range(CANONICAL_K):
        mask = labels == cid
        cluster_fips = [fips_list[i] for i in range(len(fips_list)) if mask[i]]
        cluster_X = X[mask]
        centroid = cluster_X.mean(axis=0)
        deviation = centroid - overall_mean

        high_idx = np.argsort(-deviation)[:4]
        low_idx = np.argsort(deviation)[:4]

        high_vars = [{"variable": datasets[i], "label": LABELS.get(datasets[i], datasets[i]),
                      "value": round(float(centroid[i]), 3), "dev": round(float(deviation[i]), 3)} for i in high_idx]
        low_vars = [{"variable": datasets[i], "label": LABELS.get(datasets[i], datasets[i]),
                     "value": round(float(centroid[i]), 3), "dev": round(float(deviation[i]), 3)} for i in low_idx]

        # Closest to centroid
        dists = np.linalg.norm(cluster_X - centroid, axis=1)
        closest = np.argsort(dists)[:5]
        examples = [{"fips": cluster_fips[i], "name": names.get(cluster_fips[i], cluster_fips[i])} for i in closest]

        clusters[str(cid)] = {
            "cluster_id": cid,
            "n_counties": int(mask.sum()),
            "pct": round(int(mask.sum()) / len(fips_list) * 100, 1),
            "high_variables": high_vars,
            "low_variables": low_vars,
            "examples": examples,
            "centroid": {datasets[i]: round(float(centroid[i]), 3) for i in range(len(datasets))},
        }

        print(f"\nCluster {cid} ({mask.sum()} counties, {clusters[str(cid)]['pct']}%):")
        high_str = ", ".join(v["label"] + "=" + f"{v['value']:.2f}(+{v['dev']:.2f})" for v in high_vars)
        low_str = ", ".join(v["label"] + "=" + f"{v['value']:.2f}({v['dev']:.2f})" for v in low_vars)
        ex_str = ", ".join(e["name"] for e in examples)
        print(f"  HIGH: {high_str}")
        print(f"  LOW:  {low_str}")
        print(f"  Examples: {ex_str}")

    results = {
        # "optimal_k" historically meant "silhouette-max k", but is now the
        # pinned canonical k. Kept under this key for downstream-consumer
        # backward compat. Use silhouette_optimal_k to see what silhouette
        # alone would have picked.
        "optimal_k": CANONICAL_K,
        "canonical_k": CANONICAL_K,
        "silhouette_optimal_k": silhouette_optimal_k,
        "silhouette_scores": {str(k): v for k, v in sil.items()},
        "clusters": clusters,
        "county_assignments": {fips_list[i]: int(labels[i]) for i in range(len(fips_list))},
    }

    with open(DATA_DIR / "county_clusters.json", "w") as f:
        json.dump(results, f, indent=2)
    print(f"\nSaved to data/county_clusters.json")

    try:
        sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))
        from data_pipeline.utils.storage import upload_to_storage
        upload_to_storage(str(DATA_DIR / "county_clusters.json"))
    except Exception as e:
        print(f"  WARNING: Storage upload FAILED: {e}")


if __name__ == "__main__":
    main()
