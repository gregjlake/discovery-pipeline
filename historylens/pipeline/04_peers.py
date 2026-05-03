"""Phase 4: For each (country, year) find the 5 nearest structural peers.

Distance is mean-squared Euclidean over the normalized variable scores
that both countries share. similarity_pct = max(0, 100 - distance).

Output: data/processed/peers.csv
Columns: country_name, iso3, year, peer_rank, peer_name, peer_iso3, distance, similarity_pct
"""
import sys
from pathlib import Path
import pandas as pd
import numpy as np

sys.path.insert(0, str(Path(__file__).parent))
from _common import PROC

NORM_COLS = ["gdp_norm", "life_norm", "edu_norm", "gini_norm", "pop_norm"]
TOP_N = 5
MIN_SHARED_VARS = 2   # require at least 2 shared variables to call something a peer


def main():
    print("[Phase 4] Peer discovery")
    scores = pd.read_csv(PROC / "structural_scores.csv")

    rows = []
    for year, group in scores.groupby("year"):
        # Build matrix of normalized scores for this year
        countries = group[["country_name", "iso3"] + NORM_COLS].copy()
        countries = countries.set_index(["country_name", "iso3"])
        # mask of "has data"
        valid = countries.notna()
        # only consider countries with at least 1 normalized variable
        countries = countries[valid.any(axis=1)]
        if len(countries) < 2:
            continue

        for (cn_a, iso_a), row_a in countries.iterrows():
            distances = []
            for (cn_b, iso_b), row_b in countries.iterrows():
                if cn_a == cn_b:
                    continue
                a = row_a.values.astype(float)
                b = row_b.values.astype(float)
                shared_mask = ~(np.isnan(a) | np.isnan(b))
                n_shared = int(shared_mask.sum())
                if n_shared < MIN_SHARED_VARS:
                    continue
                diff = a[shared_mask] - b[shared_mask]
                # Mean squared Euclidean -> distance is on same 0-100 scale per dim
                dist = float(np.sqrt(np.mean(diff ** 2)))
                distances.append((dist, cn_b, iso_b, n_shared))

            distances.sort(key=lambda x: x[0])
            for rank, (dist, peer_name, peer_iso, n_shared) in enumerate(distances[:TOP_N], start=1):
                rows.append({
                    "country_name":  cn_a,
                    "iso3":          iso_a,
                    "year":          int(year),
                    "peer_rank":     rank,
                    "peer_name":     peer_name,
                    "peer_iso3":     peer_iso,
                    "distance":      round(dist, 3),
                    "similarity_pct": round(max(0.0, 100.0 - dist), 1),
                    "shared_vars":   n_shared,
                })

    out = pd.DataFrame(rows).sort_values(
        ["country_name", "year", "peer_rank"]
    ).reset_index(drop=True)

    out_path = PROC / "peers.csv"
    out.to_csv(out_path, index=False)
    print(f"  -> {out_path}  ({len(out):,} rows)")

    if len(out):
        print(f"  countries with peers: {out['country_name'].nunique()}")
        print(f"  years covered:        {out['year'].min()}-{out['year'].max()}")


if __name__ == "__main__":
    main()
