"""Compare gravity model peers vs KNN baseline in 17-dimensional data space."""
import json
import os
import sys
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.neighbors import NearestNeighbors
from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parent.parent.parent / ".env", override=False)
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

DATA_DIR = Path(__file__).resolve().parent.parent.parent / "data"


def main():
    with open(DATA_DIR / "beta_calibration.json") as f:
        beta_data = json.load(f)
    datasets = beta_data["datasets_used"]

    # Load normalized county vectors
    matrix_path = DATA_DIR / "county_data_matrix.csv"
    if matrix_path.exists():
        df = pd.read_csv(matrix_path, dtype={"fips": str})
        df["fips"] = df["fips"].str.zfill(5)
        print(f"Loaded {len(df)} counties from CSV")
    else:
        raise FileNotFoundError("county_data_matrix.csv not found. Run export first.")

    X = df[datasets].fillna(0.5).values.astype(float)
    fips_list = df["fips"].tolist()
    print(f"Feature matrix: {X.shape}")

    # Fit KNN (k=21: self + 20 neighbors)
    knn = NearestNeighbors(n_neighbors=21, metric="euclidean", algorithm="auto")
    knn.fit(X)
    distances, indices = knn.kneighbors(X)
    print("KNN fitted.")

    # Load gravity model peers from cache
    with open(DATA_DIR / "gravity_map_cache.json") as f:
        cache = json.load(f)
    nodes = {n["fips"]: n for n in cache["nodes"]}
    links = cache.get("links", [])

    # Build gravity peer lists (top 20 by force_strength)
    gravity_peers = {}
    for fips in fips_list:
        county_links = [l for l in links if l["source"] == fips or l["target"] == fips]
        county_links.sort(key=lambda x: x.get("force_strength", 0), reverse=True)
        peers = []
        for link in county_links[:20]:
            peer = link["target"] if link["source"] == fips else link["source"]
            if peer not in peers:
                peers.append(peer)
        gravity_peers[fips] = set(peers[:20])

    # Build KNN peer lists
    knn_peers = {}
    for i, fips in enumerate(fips_list):
        peer_indices = indices[i, 1:21]
        knn_peers[fips] = set(fips_list[j] for j in peer_indices)

    # Compute Jaccard similarity
    print("\nComputing Jaccard similarity...")
    jaccards = []
    fips_with_j = []
    for fips in fips_list:
        grav = gravity_peers.get(fips, set())
        knn_p = knn_peers.get(fips, set())
        if not grav:
            continue
        union = len(grav | knn_p)
        j = len(grav & knn_p) / union if union > 0 else 0
        jaccards.append(j)
        fips_with_j.append(fips)

    jaccards = np.array(jaccards)
    mean_j = float(np.mean(jaccards))
    median_j = float(np.median(jaccards))
    pct_above_50 = float(np.mean(jaccards > 0.5) * 100)
    pct_above_75 = float(np.mean(jaccards > 0.75) * 100)

    print(f"\nKNN vs Gravity Peer Overlap (Jaccard, k=20):")
    print(f"  Mean Jaccard:          {mean_j:.3f}")
    print(f"  Median Jaccard:        {median_j:.3f}")
    print(f"  Counties J > 0.50:     {pct_above_50:.1f}%")
    print(f"  Counties J > 0.75:     {pct_above_75:.1f}%")

    # Top agreeing
    sorted_j = sorted(zip(fips_with_j, jaccards), key=lambda x: -x[1])
    print("\nTop 5 counties where KNN ~ gravity:")
    for fips, j in sorted_j[:5]:
        name = nodes.get(fips, {}).get("county_name", fips)
        print(f"  {name}: J={j:.3f}")

    # Top diverging
    bot = sorted(zip(fips_with_j, jaccards), key=lambda x: x[1])[:10]
    print("\nTop 10 counties where gravity != KNN:")
    for fips, j in bot:
        name = nodes.get(fips, {}).get("county_name", fips)
        grav_only = gravity_peers.get(fips, set()) - knn_peers.get(fips, set())
        grav_names = [nodes.get(f, {}).get("county_name", f) for f in list(grav_only)[:3]]
        print(f"  {name}: J={j:.3f}  gravity finds: {grav_names}")

    # Interpretation
    if mean_j > 0.70:
        interpretation = "HIGH OVERLAP: Gravity peers largely equivalent to KNN. Peer-finding robust to method choice."
    elif mean_j > 0.50:
        interpretation = "MODERATE OVERLAP: Majority of peers agree. Differences from population weighting in gravity."
    else:
        interpretation = "LOW OVERLAP: Population weighting drives gravity divergence from pure data-space KNN."

    print(f"\nInterpretation: {interpretation}")

    results = {
        "mean_jaccard_gravity_vs_knn": round(mean_j, 3),
        "median_jaccard_gravity_vs_knn": round(median_j, 3),
        "pct_counties_j_above_50": round(pct_above_50, 1),
        "pct_counties_j_above_75": round(pct_above_75, 1),
        "n_counties_compared": len(jaccards),
        "k_neighbors": 20,
        "distance_metric": "euclidean",
        "interpretation": interpretation,
        "top_diverging_counties": [
            {"fips": fips, "name": nodes.get(fips, {}).get("county_name", fips),
             "jaccard": round(float(j), 3)}
            for fips, j in bot[:10]
        ],
    }

    with open(DATA_DIR / "knn_comparison.json", "w") as f:
        json.dump(results, f, indent=2)
    print("\nSaved to data/knn_comparison.json")

    try:
        from data_pipeline.utils.storage import upload_to_storage
        upload_to_storage(str(DATA_DIR / "knn_comparison.json"))
    except Exception as e:
        print(f"  Storage upload skipped: {e}")


if __name__ == "__main__":
    main()
