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

    # Find optimal k
    print("\nSilhouette scores:")
    sil = {}
    for k in range(4, 12):
        km = KMeans(n_clusters=k, random_state=42, n_init=10)
        labels = km.fit_predict(X)
        s = silhouette_score(X, labels, sample_size=min(1000, len(X)), random_state=42)
        sil[k] = round(float(s), 4)
        print(f"  k={k}: {s:.4f}")

    optimal_k = max(sil, key=sil.get)
    print(f"\nOptimal k: {optimal_k} (silhouette={sil[optimal_k]:.4f})")

    # Fit final model
    km = KMeans(n_clusters=optimal_k, random_state=42, n_init=10)
    labels = km.fit_predict(X)
    overall_mean = X.mean(axis=0)

    print(f"\n{'='*60}")
    print("CLUSTER PROFILES")
    print("=" * 60)

    clusters = {}
    for cid in range(optimal_k):
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
        "optimal_k": optimal_k,
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
        print(f"  Storage upload skipped: {e}")


if __name__ == "__main__":
    main()
