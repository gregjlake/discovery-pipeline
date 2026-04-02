"""Calibrate distance-decay β from socioeconomic similarity vs geographic distance."""
import json
import os
from pathlib import Path

import numpy as np
import pandas as pd
import scipy.stats
from scipy.spatial.distance import cdist
from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parent.parent.parent / ".env", override=False)
DATA_DIR = Path(__file__).resolve().parent.parent.parent / "data"

# The 20 active gravity model datasets and their primary value columns
DATASETS = {
    "library":        "library_spend_per_capita",
    # mobility excluded: temporal mismatch (1978-2015 vs 2022 datasets)
    "air":            "air_quality_inv",
    "broadband":      "broadband_rate",
    "eitc":           "eitc_rate",
    "poverty":        "poverty_rate",
    "median_income":  "median_hh_income",
    "bea_income":     "per_capita_income",
    "food_access":    "pct_low_food_access",
    "obesity":        "obesity_rate",
    "diabetes":       "diabetes_rate",
    "mental_health":  "mental_health_rate",
    "hypertension":   "hypertension_rate",
    "unemployment":   "unemployment_rate",
    "rural_urban":    "rural_urban_code",
    "housing_burden": "housing_burden_rate",
    "voter_turnout":  "voter_turnout_rate",
    # broadband_avail excluded: r=0.993 with broadband (same ACS B28002 table)
    "pop_density":    "pop_density",
    "bachelors_rate": "bachelors_rate",
    "median_age":     "median_age",
    "homeownership_rate": "homeownership_rate",
}


# ── STEP 1: LOAD DATA ────────────────────────────────────────
def load_data():
    print("=" * 60)
    print("STEP 1: LOAD DATA")
    print("=" * 60)

    # Load centroids
    centroids = pd.read_csv(DATA_DIR / "county_centroids.csv", dtype={"fips": str})
    centroids["fips"] = centroids["fips"].str.zfill(5)
    print(f"Centroids: {len(centroids)} counties")

    # Load raw values from Supabase
    url = os.environ.get("SUPABASE_URL")
    key = os.environ.get("SUPABASE_SERVICE_KEY")
    from supabase import create_client
    sb = create_client(url, key)

    print("Loading raw values from Supabase...")
    print("  No pre-normalized columns found (no county_data table).")
    print("  Using raw values from raw_values table with min-max normalization (fallback).")
    print("  All 17 datasets use fallback min-max normalization.")

    # Paginate all raw_values
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
    print(f"  Loaded {len(all_rows)} raw_values rows")

    rv = pd.DataFrame(all_rows)

    # Filter to our 20 primary columns
    target_pairs = set(DATASETS.items())
    rv = rv[rv.apply(lambda r: (r["dataset_id"], r["column_name"]) in target_pairs, axis=1)]
    print(f"  Filtered to 17 primary columns: {len(rv)} rows")

    # Pivot: fips × dataset_id -> value
    pivot = rv.pivot_table(index="fips", columns="dataset_id", values="value", aggfunc="first")
    pivot = pivot.reset_index()
    pivot["fips"] = pivot["fips"].astype(str).str.zfill(5)

    # Min-max normalize each column
    ds_cols = [c for c in pivot.columns if c in DATASETS]
    for c in ds_cols:
        col = pivot[c].astype(float)
        cmin, cmax = col.min(), col.max()
        if cmax > cmin:
            pivot[c] = (col - cmin) / (cmax - cmin)
        else:
            pivot[c] = 0.5

    # Merge with centroids
    merged = centroids.merge(pivot, on="fips", how="inner")
    available = [c for c in ds_cols if c in merged.columns]
    print(f"\n  Counties in intersection: {len(merged)}")
    print(f"  Datasets available: {len(available)}/17")
    missing = [d for d in DATASETS if d not in available]
    if missing:
        print(f"  Missing datasets: {missing}")
    print(f"  Normalization: min-max (fallback for all 17)")

    return merged, available


# ── STEP 2: GEO DISTANCE MATRIX ──────────────────────────────
def compute_geo_dist(merged):
    print("\n" + "=" * 60)
    print("STEP 2: GEO DISTANCE MATRIX")
    print("=" * 60)

    lats = merged["lat"].values
    lons = merged["lon"].values
    R = 3958.8  # miles

    lats_r = np.radians(lats)
    lons_r = np.radians(lons)
    dlat = lats_r[:, None] - lats_r[None, :]
    dlon = lons_r[:, None] - lons_r[None, :]
    a = np.sin(dlat / 2) ** 2 + np.cos(lats_r[:, None]) * np.cos(lats_r[None, :]) * np.sin(dlon / 2) ** 2
    geo_dist = R * 2 * np.arcsin(np.sqrt(np.clip(a, 0, 1)))

    print(f"  Shape: {geo_dist.shape}")
    print(f"  Max distance: {geo_dist.max():.1f} miles")
    print(f"  Mean distance: {geo_dist.mean():.1f} miles")

    return geo_dist


# ── STEP 3: DATA SIMILARITY MATRIX ───────────────────────────
def compute_similarity(merged, ds_cols):
    print("\n" + "=" * 60)
    print("STEP 3: DATA SIMILARITY MATRIX")
    print("=" * 60)

    vectors = merged[ds_cols].values.astype(float)
    # Fill NaN with 0.5 (median substitute)
    nan_count = np.isnan(vectors).sum()
    vectors = np.nan_to_num(vectors, nan=0.5)
    print(f"  Feature matrix: {vectors.shape} (counties x datasets)")
    print(f"  NaN values filled with 0.5: {nan_count}")

    dissim = cdist(vectors, vectors, metric="euclidean")
    dmax = dissim.max()
    dissim_norm = dissim / dmax if dmax > 0 else dissim
    similarity = 1 - dissim_norm

    # Set diagonal to NaN
    np.fill_diagonal(similarity, np.nan)

    mean_sim = np.nanmean(similarity)
    print(f"  Similarity shape: {similarity.shape}")
    print(f"  Mean similarity: {mean_sim:.4f}")
    print(f"  Max dissimilarity (pre-norm): {dmax:.4f}")

    return similarity


# ── STEP 4: SAMPLE COUNTY PAIRS ──────────────────────────────
def sample_pairs(geo_dist, similarity, n_sample=250_000):
    print("\n" + "=" * 60)
    print("STEP 4: SAMPLE COUNTY PAIRS")
    print("=" * 60)

    n = geo_dist.shape[0]
    total_pairs = n * (n - 1)
    print(f"  Total possible pairs: {total_pairs:,}")
    print(f"  Sampling {n_sample:,} random pairs...")

    rng = np.random.default_rng(42)
    idx_i = rng.integers(0, n, size=n_sample)
    idx_j = rng.integers(0, n, size=n_sample)
    # Remove self-pairs
    mask = idx_i != idx_j
    idx_i = idx_i[mask]
    idx_j = idx_j[mask]

    geo_miles = geo_dist[idx_i, idx_j]
    sim = similarity[idx_i, idx_j]

    # Filter
    valid = (geo_miles >= 10) & (sim > 0) & (~np.isnan(sim)) & (~np.isnan(geo_miles))
    geo_miles = geo_miles[valid]
    sim = sim[valid]

    print(f"  After filtering (geo>=10mi, sim>0): {len(geo_miles):,} pairs")

    return geo_miles, sim


# ── STEP 5: FIT LOG-LINEAR REGRESSION ────────────────────────
def fit_regression(geo_miles, sim):
    print("\n" + "=" * 60)
    print("STEP 5: FIT LOG-LINEAR REGRESSION")
    print("=" * 60)
    print("  log(similarity) = alpha - beta * log(geo_miles)")

    log_geo = np.log(geo_miles)
    log_sim = np.log(sim)

    slope, intercept, r_value, p_value, std_err = scipy.stats.linregress(log_geo, log_sim)
    beta_geo = -slope
    r2 = r_value ** 2

    print(f"\n  beta (geo-only, first pass) = {beta_geo:.4f}")
    print(f"  R-squared                   = {r2:.4f}")
    print(f"  std_err                     = {std_err:.6f}")
    print(f"  intercept                   = {intercept:.4f}")
    print(f"  p_value                     = {p_value:.2e}")

    # Interpretation
    print("\n  Interpretation:")
    if beta_geo < 0.2:
        print("    beta: WARNING - Very weak decay - check normalization")
    elif beta_geo < 0.3:
        print("    beta: Weak decay - datasets may be geographically diffuse")
    elif beta_geo < 0.8:
        print("    beta: Moderate decay - expected for diverse datasets")
    elif beta_geo < 1.5:
        print("    beta: Strong decay - datasets are geographically clustered")
    else:
        print("    beta: WARNING - Very strong decay - check for outliers")

    if r2 < 0.05:
        print("    R2: Distance explains little variance - gravity visualization")
        print("        will show mostly data-space clustering")
    elif r2 < 0.15:
        print("    R2: Moderate geographic signal")
    else:
        print("    R2: Distance is a meaningful predictor of similarity")

    return beta_geo, r2, std_err, intercept, p_value


# (Moran's I cross-validation removed — spatial autocorrelation
#  analysis noted as future work in methods note limitation 14)


# ── STEP 7: SPOT CHECKS ──────────────────────────────────────
def spot_checks(geo_miles, sim):
    print("\n" + "=" * 60)
    print("STEP 7: SPOT CHECKS")
    print("=" * 60)

    close = sim[geo_miles < 100]
    mid = sim[(geo_miles >= 100) & (geo_miles <= 500)]
    far = sim[geo_miles > 1000]

    m_close = np.mean(close) if len(close) > 0 else float("nan")
    m_mid = np.mean(mid) if len(mid) > 0 else float("nan")
    m_far = np.mean(far) if len(far) > 0 else float("nan")

    print(f"  < 100 miles:    mean similarity = {m_close:.4f}  (n={len(close):,})")
    print(f"  100-500 miles:  mean similarity = {m_mid:.4f}  (n={len(mid):,})")
    print(f"  > 1000 miles:   mean similarity = {m_far:.4f}  (n={len(far):,})")

    if m_close > m_mid > m_far:
        print("  Monotonically decreasing - GOOD")
    else:
        print("  WARNING: Not monotonically decreasing - check data")


# ── STEP 8: STORE RESULT ─────────────────────────────────────
def store_result(beta_geo, r2, std_err, intercept, p_value, n_pairs, ds_cols):
    print("\n" + "=" * 60)
    print("STEP 8: STORE RESULT")
    print("=" * 60)

    # Upsert to Supabase
    url = os.environ.get("SUPABASE_URL")
    key = os.environ.get("SUPABASE_SERVICE_KEY")
    if url and key:
        from supabase import create_client
        sb = create_client(url, key)
        sb.table("gravity_model_metadata").upsert({
            "id": "default",
            "beta": float(beta_geo),
            "pseudo_r2": float(r2),
            "n_pairs": int(n_pairs),
            "calibration_year": "N/A",
            "calibration_source": (
                "Internal: socioeconomic similarity decay vs geographic distance, "
                "DiscoSights 17 datasets, first-pass geo-only"
            ),
            "model_type": "OLS log-linear: log(similarity) ~ log(geo_miles)",
            "distance_type": (
                "Multiplicative: geo_miles_normalized x data_dissimilarity_normalized"
            ),
        }, on_conflict="id").execute()
        print("  Upserted to Supabase gravity_model_metadata")
    else:
        print("  Supabase not configured - skipped")

    # Save JSON
    result = {
        "beta_geo": round(float(beta_geo), 6),
        "beta_combined": None,
        "beta_operative": None,
        "r_squared_geo": round(float(r2), 6),
        "n_pairs": int(n_pairs),
        "std_err": round(float(std_err), 6),
        "intercept": round(float(intercept), 6),
        "p_value": float(p_value),
        "normalization_type": "min-max (fallback, no pre-normalized columns in Supabase)",
        "datasets_used": sorted(ds_cols),
        "note": (
            "beta_combined will be filled by run_gravity_pipeline.py "
            "after combined distance matrix is computed"
        ),
    }
    out = DATA_DIR / "beta_calibration.json"
    with open(out, "w") as f:
        json.dump(result, f, indent=2)
    print(f"  Saved {out}")


# ── MAIN ──────────────────────────────────────────────────────
def main():
    merged, ds_cols = load_data()
    geo_dist = compute_geo_dist(merged)
    similarity = compute_similarity(merged, ds_cols)
    geo_miles, sim = sample_pairs(geo_dist, similarity)
    beta_geo, r2, std_err, intercept, p_value = fit_regression(geo_miles, sim)
    spot_checks(geo_miles, sim)
    store_result(beta_geo, r2, std_err, intercept, p_value, len(geo_miles), ds_cols)

    print("\n" + "=" * 60)
    print("DONE")
    print("=" * 60)


if __name__ == "__main__":
    main()
