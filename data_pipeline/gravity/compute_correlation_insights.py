"""Compute ranked correlation insights for the Discover tab."""
import json
import os
import sys
from pathlib import Path
from itertools import combinations

import numpy as np
import pandas as pd
from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parent.parent.parent / ".env", override=False)
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

DATA_DIR = Path(__file__).resolve().parent.parent.parent / "data"

DOMAIN_MAP = {
    "poverty": "economic", "eitc": "economic", "median_income": "economic",
    "bea_income": "economic", "unemployment": "economic",
    "obesity": "health", "diabetes": "health", "hypertension": "health", "mental_health": "health",
    "broadband": "infrastructure", "food_access": "infrastructure",
    "housing_burden": "infrastructure", "air": "infrastructure",
    "voter_turnout": "civic", "library": "civic", "rural_urban": "civic", "pop_density": "civic",
}

LABELS = {
    "poverty": "Poverty Rate", "eitc": "EITC Uptake", "median_income": "Median Income",
    "bea_income": "Per Capita Income", "unemployment": "Unemployment",
    "obesity": "Obesity", "diabetes": "Diabetes", "hypertension": "Hypertension",
    "mental_health": "Mental Health", "broadband": "Broadband Access",
    "food_access": "Low Food Access", "housing_burden": "Housing Burden",
    "air": "Air Quality", "voter_turnout": "Voter Turnout", "library": "Library Access",
    "rural_urban": "Rural-Urban Code", "pop_density": "Population Density",
}


def main():
    with open(DATA_DIR / "beta_calibration.json") as f:
        datasets = json.load(f)["datasets_used"]

    df = pd.read_csv(DATA_DIR / "county_data_matrix.csv", dtype={"fips": str})
    X = df[datasets].astype(float)
    corr = X.corr()

    pairs = []
    for a, b in combinations(datasets, 2):
        r = float(corr.loc[a, b])
        if np.isnan(r):
            continue
        da, db = DOMAIN_MAP.get(a, "?"), DOMAIN_MAP.get(b, "?")
        same = da == db
        abs_r = abs(r)
        effect = "large" if abs_r >= 0.50 else "medium" if abs_r >= 0.30 else "small" if abs_r >= 0.10 else "negligible"

        pairs.append({
            "var_a": a, "var_b": b,
            "label_a": LABELS.get(a, a), "label_b": LABELS.get(b, b),
            "r": round(r, 4), "abs_r": round(abs_r, 4),
            "domain_a": da, "domain_b": db, "same_domain": same,
            "effect_size": effect,
        })

    strongest = sorted(pairs, key=lambda x: -x["abs_r"])[:15]
    most_independent = sorted(pairs, key=lambda x: x["abs_r"])[:15]
    cross_strong = sorted([p for p in pairs if not p["same_domain"]], key=lambda x: -x["abs_r"])[:15]

    all_abs = [p["abs_r"] for p in pairs]

    results = {
        "n_pairs": len(pairs),
        "mean_abs_r": round(float(np.mean(all_abs)), 3),
        "median_abs_r": round(float(np.median(all_abs)), 3),
        "pct_large_effect": round(sum(1 for p in pairs if p["abs_r"] >= 0.50) / len(pairs) * 100, 1),
        "pct_negligible": round(sum(1 for p in pairs if p["abs_r"] < 0.10) / len(pairs) * 100, 1),
        "strongest_correlations": strongest,
        "most_independent": most_independent,
        "cross_domain_surprises": cross_strong,
    }

    print(f"Total pairs: {len(pairs)}")
    print(f"Mean |r|: {results['mean_abs_r']}")
    print(f"\nTop 5 strongest:")
    for p in strongest[:5]:
        print(f"  {p['label_a']} x {p['label_b']}: r={p['r']:.3f} ({p['domain_a']} x {p['domain_b']})")
    print(f"\nTop 5 most independent:")
    for p in most_independent[:5]:
        print(f"  {p['label_a']} x {p['label_b']}: r={p['r']:.3f}")
    print(f"\nTop 5 cross-domain surprises:")
    for p in cross_strong[:5]:
        print(f"  {p['label_a']} x {p['label_b']}: r={p['r']:.3f} ({p['domain_a']} x {p['domain_b']})")

    with open(DATA_DIR / "correlation_insights.json", "w") as f:
        json.dump(results, f, indent=2)
    print("\nSaved to data/correlation_insights.json")

    try:
        sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))
        from data_pipeline.utils.storage import upload_to_storage
        upload_to_storage(str(DATA_DIR / "correlation_insights.json"))
    except Exception as e:
        print(f"  WARNING: Storage upload FAILED: {e}")


if __name__ == "__main__":
    main()
