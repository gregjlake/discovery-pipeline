"""PCA analysis of gravity model datasets to diagnose collinearity."""
import json
import os
import sys
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.preprocessing import StandardScaler
from sklearn.decomposition import PCA
from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parent.parent.parent / ".env", override=False)
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

DATA_DIR = Path(__file__).resolve().parent.parent.parent / "data"

# The 17 active gravity model datasets
# mobility excluded: temporal mismatch (1978-2015 vs 2022)
# broadband_avail excluded: r=0.993 collinearity with broadband
DATASETS = {
    "library": "library_spend_per_capita",
    "air": "air_quality_inv", "broadband": "broadband_rate",
    "eitc": "eitc_rate", "poverty": "poverty_rate",
    "median_income": "median_hh_income", "bea_income": "per_capita_income",
    "food_access": "pct_low_food_access", "obesity": "obesity_rate",
    "diabetes": "diabetes_rate", "mental_health": "mental_health_rate",
    "hypertension": "hypertension_rate", "unemployment": "unemployment_rate",
    "rural_urban": "rural_urban_code", "housing_burden": "housing_burden_rate",
    "voter_turnout": "voter_turnout_rate", "pop_density": "pop_density",
}

KNOWN_TAUTOLOGICAL = {
    frozenset(["poverty", "eitc"]),
    frozenset(["poverty", "median_income"]),
    frozenset(["poverty", "bea_income"]),
    frozenset(["median_income", "bea_income"]),
    frozenset(["obesity", "diabetes"]),
    frozenset(["obesity", "hypertension"]),
    frozenset(["diabetes", "hypertension"]),
    frozenset(["rural_urban", "pop_density"]),
}


def main():
    from supabase import create_client
    sb = create_client(os.environ["SUPABASE_URL"], os.environ["SUPABASE_SERVICE_KEY"])

    dataset_cols = sorted(DATASETS.keys())
    print(f"Datasets in gravity model: {len(dataset_cols)}")
    print(dataset_cols)

    # Load from raw_values
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
    target = set(DATASETS.items())
    rv = rv[rv.apply(lambda r: (r["dataset_id"], r["column_name"]) in target, axis=1)]
    pivot = rv.pivot_table(index="fips", columns="dataset_id", values="value", aggfunc="first").reset_index()

    # Filter to gravity model counties (same as calibrate_beta: inner join with centroids)
    centroids = pd.read_csv(DATA_DIR / "county_centroids.csv", dtype={"fips": str})
    centroids["fips"] = centroids["fips"].str.zfill(5)
    pop = pd.read_csv(DATA_DIR / "county_population.csv", dtype={"fips": str})
    pop["fips"] = pop["fips"].str.zfill(5)
    gravity_fips = set(centroids["fips"]) & set(pop["fips"])

    available = [c for c in dataset_cols if c in pivot.columns]
    df = pivot[["fips"] + available].copy()
    df = df[df["fips"].isin(gravity_fips)]
    print(f"Counties (matching gravity model): {len(df)}")
    print(f"Available datasets: {len(available)}")

    # Min-max normalize then fill NaN with 0.5 (matches gravity model)
    for c in available:
        df[c] = pd.to_numeric(df[c], errors="coerce")
        cmin, cmax = df[c].min(), df[c].max()
        if cmax > cmin:
            df[c] = (df[c] - cmin) / (cmax - cmin)
        else:
            df[c] = 0.5
        missing = df[c].isna().sum()
        if missing > 0:
            print(f"  Imputing {missing} missing values in {c} with 0.5")
            df[c] = df[c].fillna(0.5)

    vectors = df[available].values.astype(float)

    # Standardize
    scaler = StandardScaler()
    vectors_scaled = scaler.fit_transform(vectors)

    # PCA
    pca = PCA()
    scores = pca.fit_transform(vectors_scaled)
    var_explained = pca.explained_variance_ratio_
    cumvar = np.cumsum(var_explained)

    print("\n=== VARIANCE EXPLAINED BY COMPONENT ===")
    for i in range(min(12, len(var_explained))):
        bar = "#" * int(var_explained[i] * 100)
        print(f"  PC{i+1:2d}: {var_explained[i]*100:5.1f}%  {bar}  (cumulative: {cumvar[i]*100:.1f}%)")

    n80 = int(np.argmax(cumvar >= 0.80)) + 1
    n90 = int(np.argmax(cumvar >= 0.90)) + 1
    n95 = int(np.argmax(cumvar >= 0.95)) + 1
    print(f"\n  80% variance: {n80} components")
    print(f"  90% variance: {n90} components")
    print(f"  95% variance: {n95} components")

    eff_dim = 1.0 / np.sum(var_explained ** 2)
    print(f"\n  Effective dimensions: {eff_dim:.1f} (out of {len(available)})")

    if eff_dim < 8:
        print("  WARNING: Several datasets are highly redundant.")
    elif eff_dim < 12:
        print("  NOTE: Moderate collinearity. Equal weighting is a simplification.")
    else:
        print("  OK: Low collinearity. Equal weighting is reasonable.")

    # Loadings
    n_pcs = min(8, len(var_explained))
    loadings = pd.DataFrame(
        pca.components_[:n_pcs].T,
        index=available,
        columns=[f"PC{i+1}" for i in range(n_pcs)],
    )

    print("\n=== COMPONENT LOADINGS (top 4 datasets per PC) ===")
    component_names = {}
    for pc_idx in range(min(6, n_pcs)):
        pc = f"PC{pc_idx+1}"
        pct = var_explained[pc_idx] * 100
        top4 = loadings[pc].abs().nlargest(4)
        print(f"\n  {pc} ({pct:.1f}% of variance):")
        ds_in_pc = []
        for dataset, loading in top4.items():
            direction = "+" if loadings.loc[dataset, pc] > 0 else "-"
            print(f"    {direction}{abs(loading):.3f}  {dataset}")
            ds_in_pc.append(dataset)
        component_names[pc] = {
            "variance_pct": round(pct, 1),
            "top_datasets": ds_in_pc[:4],
            "loadings": {d: round(float(loadings.loc[d, pc]), 3) for d in ds_in_pc},
        }

    # Unexpected collinearity
    corr = pd.DataFrame(vectors, columns=available).corr()
    unexpected = []
    for i in range(len(available)):
        for j in range(i + 1, len(available)):
            r = corr.iloc[i, j]
            if abs(r) > 0.6:
                pair = frozenset([available[i], available[j]])
                if pair not in KNOWN_TAUTOLOGICAL:
                    unexpected.append({"d1": available[i], "d2": available[j], "r": round(float(r), 3)})

    unexpected.sort(key=lambda x: abs(x["r"]), reverse=True)
    print("\n=== UNEXPECTED HIGH COLLINEARITY (|r|>0.6, not tautological) ===")
    for p in unexpected:
        print(f"  {p['d1']} x {p['d2']}: r={p['r']:.3f}")
    if not unexpected:
        print("  (none found)")

    assessment = "problematic" if eff_dim < 8 else "moderate" if eff_dim < 12 else "reasonable"
    note = (
        f"With {eff_dim:.1f} effective dimensions out of {len(available)}, "
        + (
            "equal weighting is problematic -- variance is concentrated in a few dimensions."
            if eff_dim < 8
            else "equal weighting is a moderate simplification."
            if eff_dim < 12
            else "equal weighting is a reasonable approximation."
        )
    )

    results = {
        "n_datasets": len(available),
        "n_counties": len(df),
        "datasets": available,
        "variance_explained": [round(float(v), 4) for v in var_explained],
        "cumulative_variance": [round(float(v), 4) for v in cumvar],
        "n_components_80pct": n80,
        "n_components_90pct": n90,
        "n_components_95pct": n95,
        "effective_dimensions": round(float(eff_dim), 2),
        "component_details": component_names,
        "unexpected_collinear_pairs": unexpected,
        "equal_weighting_assessment": assessment,
        "equal_weighting_note": note,
    }

    with open(DATA_DIR / "pca_results.json", "w") as f:
        json.dump(results, f, indent=2)

    print(f"\nSaved to data/pca_results.json")
    print(f"\nEqual weighting assessment: {assessment.upper()}")
    print(note)

    try:
        from data_pipeline.utils.storage import upload_to_storage
        upload_to_storage(str(DATA_DIR / "pca_results.json"))
    except Exception as e:
        print(f"  Storage upload skipped: {e}")


if __name__ == "__main__":
    main()
