"""Phase 4: Peer discovery with weight-scheme sensitivity and regional peers.

For each (country, year) compute top-5 nearest peers under three weight
schemes (A, B, C) using weighted-Euclidean distance over the four scoring
variables (population is excluded from peer matching). Then compute
peer_stability — the share of top-3 peers identical across all three
schemes — and a regional-peers list (top-3 within the same region).

Outputs:
  data/processed/peers.csv             (scheme A — kept as canonical "peers")
  data/processed/peers_b.csv           (Scheme B)
  data/processed/peers_c.csv           (Scheme C)
  data/processed/peer_stability.csv    (one row per country-year)
  data/processed/regional_peers.csv    (top-3 within each country's region)
"""
import sys
from pathlib import Path
import pandas as pd
import numpy as np

sys.path.insert(0, str(Path(__file__).parent))
from _common import PROC, WEIGHT_SCHEMES, REGION_MAP, SCORING_VARS

# Map scoring vars -> column names in structural_scores.csv
NORM_COLS_BY_VAR = {
    "gdp_per_capita":  "gdp_norm",
    "life_expectancy": "life_norm",
    "education_years": "edu_norm",
    "gini":            "gini_norm",
}
NORM_COLS = [NORM_COLS_BY_VAR[v] for v in SCORING_VARS]
TOP_N = 5
MIN_SHARED_VARS = 2


def weighted_distance(a, b, weights):
    """Weighted-mean-squared Euclidean over shared (non-NaN) dimensions.

    a, b: 1D arrays, same shape
    weights: 1D array, same shape, weight per dimension
    Returns (dist, n_shared). dist is on the 0-100 scale per dim.
    """
    shared = ~(np.isnan(a) | np.isnan(b))
    n_shared = int(shared.sum())
    if n_shared < MIN_SHARED_VARS:
        return None, n_shared
    diff = a[shared] - b[shared]
    w = weights[shared]
    if w.sum() == 0:
        return None, n_shared
    w_norm = w / w.sum()
    dist = float(np.sqrt(np.sum(w_norm * diff ** 2)))
    return dist, n_shared


def compute_scheme_peers(scores, weights_dict, scheme_label):
    """Return DataFrame of top-5 peers per (country, year) under one scheme."""
    weight_array = np.array([weights_dict[v] for v in SCORING_VARS], dtype=float)
    rows = []
    for year, group in scores.groupby("year"):
        countries = group[["country_name", "iso3"] + NORM_COLS].copy()
        countries = countries.set_index(["country_name", "iso3"])
        valid = countries.notna()
        countries = countries[valid.any(axis=1)]
        if len(countries) < 2:
            continue

        for (cn_a, iso_a), row_a in countries.iterrows():
            distances = []
            a = row_a.values.astype(float)
            for (cn_b, iso_b), row_b in countries.iterrows():
                if cn_a == cn_b:
                    continue
                b = row_b.values.astype(float)
                dist, n_shared = weighted_distance(a, b, weight_array)
                if dist is None:
                    continue
                distances.append((dist, cn_b, iso_b, n_shared))
            distances.sort(key=lambda x: x[0])
            for rank, (dist, peer_name, peer_iso, n_shared) in enumerate(distances[:TOP_N], start=1):
                rows.append({
                    "country_name":   cn_a,
                    "iso3":           iso_a,
                    "year":           int(year),
                    "scheme":         scheme_label,
                    "peer_rank":      rank,
                    "peer_name":      peer_name,
                    "peer_iso3":      peer_iso,
                    "distance":       round(dist, 3),
                    "similarity_pct": round(max(0.0, 100.0 - dist), 1),
                    "shared_vars":    n_shared,
                })
    return pd.DataFrame(rows).sort_values(
        ["country_name", "year", "peer_rank"]
    ).reset_index(drop=True)


def compute_regional_peers(scores):
    """Top-3 peers within each country's region, scheme A weights."""
    weights = WEIGHT_SCHEMES["A"]["weights"]
    weight_array = np.array([weights[v] for v in SCORING_VARS], dtype=float)
    rows = []
    for year, group in scores.groupby("year"):
        countries = group[["country_name", "iso3"] + NORM_COLS].copy()
        countries = countries.set_index(["country_name", "iso3"])
        valid = countries.notna()
        countries = countries[valid.any(axis=1)]
        if len(countries) < 2:
            continue

        for (cn_a, iso_a), row_a in countries.iterrows():
            region_a = REGION_MAP.get(cn_a, "Other")
            distances = []
            a = row_a.values.astype(float)
            for (cn_b, iso_b), row_b in countries.iterrows():
                if cn_a == cn_b:
                    continue
                if REGION_MAP.get(cn_b, "Other") != region_a:
                    continue
                b = row_b.values.astype(float)
                dist, n_shared = weighted_distance(a, b, weight_array)
                if dist is None:
                    continue
                distances.append((dist, cn_b, iso_b, n_shared))
            distances.sort(key=lambda x: x[0])
            top = distances[:3]
            for rank, (dist, peer_name, peer_iso, n_shared) in enumerate(top, start=1):
                rows.append({
                    "country_name":   cn_a,
                    "iso3":           iso_a,
                    "year":           int(year),
                    "region":         region_a,
                    "peer_rank":      rank,
                    "peer_name":      peer_name,
                    "peer_iso3":      peer_iso,
                    "distance":       round(dist, 3),
                    "similarity_pct": round(max(0.0, 100.0 - dist), 1),
                    "shared_vars":    n_shared,
                })
    return pd.DataFrame(rows).sort_values(
        ["country_name", "year", "peer_rank"]
    ).reset_index(drop=True)


def compute_stability(peers_a, peers_b, peers_c):
    """For each (country, year), share of top-3 peer NAMES identical across A/B/C."""
    rows = []

    def top3(df, country, year):
        sub = df[(df["country_name"] == country) &
                 (df["year"] == year) &
                 (df["peer_rank"] <= 3)]
        return list(sub["peer_name"])

    keys = peers_a[["country_name", "year"]].drop_duplicates().itertuples(index=False)
    for cn, yr in keys:
        ta = set(top3(peers_a, cn, yr))
        tb = set(top3(peers_b, cn, yr))
        tc = set(top3(peers_c, cn, yr))
        if not (ta and tb and tc):
            continue
        common = ta & tb & tc
        # 100 if 3 in common, 67 if 2, 33 if 1, 0 if none
        n = len(common)
        if n == 3:
            stability = 100
        elif n == 2:
            stability = 67
        elif n == 1:
            stability = 33
        else:
            stability = 0
        rows.append({
            "country_name":  cn,
            "year":          int(yr),
            "stability":     stability,
            "common_count":  n,
            "common_peers":  ",".join(sorted(common)),
        })
    return pd.DataFrame(rows).sort_values(["country_name", "year"]).reset_index(drop=True)


def main():
    print("[Phase 4] Peer discovery (3 schemes + regional + stability)")
    scores = pd.read_csv(PROC / "structural_scores.csv")

    peers_by_scheme = {}
    for scheme_id, scheme in WEIGHT_SCHEMES.items():
        df = compute_scheme_peers(scores, scheme["weights"], scheme_id)
        peers_by_scheme[scheme_id] = df
        suffix = "" if scheme_id == "A" else f"_{scheme_id.lower()}"
        out_path = PROC / f"peers{suffix}.csv"
        df.to_csv(out_path, index=False)
        print(f"  scheme {scheme_id} ({scheme['label']}): {len(df):,} rows -> {out_path}")

    # Regional peers
    regional = compute_regional_peers(scores)
    reg_path = PROC / "regional_peers.csv"
    regional.to_csv(reg_path, index=False)
    print(f"  regional peers: {len(regional):,} rows -> {reg_path}")

    # Stability
    stab = compute_stability(peers_by_scheme["A"], peers_by_scheme["B"], peers_by_scheme["C"])
    stab_path = PROC / "peer_stability.csv"
    stab.to_csv(stab_path, index=False)
    n_total = len(stab)
    n_100 = int((stab["stability"] == 100).sum())
    n_at_least_67 = int((stab["stability"] >= 67).sum())
    n_unstable = int((stab["stability"] < 67).sum())
    pct_100 = round(100 * n_100 / n_total, 1) if n_total else 0
    pct_67 = round(100 * n_at_least_67 / n_total, 1) if n_total else 0
    pct_unstable = round(100 * n_unstable / n_total, 1) if n_total else 0
    print(f"  peer stability over {n_total} (country,year) pairs:")
    print(f"    100% (all 3 same): {n_100}  ({pct_100}%)")
    print(f"    >=67% (>=2 same):  {n_at_least_67}  ({pct_67}%)")
    print(f"    <67% (unstable):   {n_unstable}  ({pct_unstable}%)")

    # Top stable / unstable pairs
    print("\n  Top 5 most stable country-decades (100% stability — sample):")
    head = stab[stab["stability"] == 100].head(5)
    for _, r in head.iterrows():
        print(f"    {r['country_name']:18s} {int(r['year'])}  peers={r['common_peers']}")

    print("\n  Top 5 most unstable country-decades (lowest stability):")
    tail = stab.sort_values(["stability", "country_name", "year"]).head(5)
    for _, r in tail.iterrows():
        print(f"    {r['country_name']:18s} {int(r['year'])}  stability={r['stability']}%  common={r['common_peers']}")


if __name__ == "__main__":
    main()
