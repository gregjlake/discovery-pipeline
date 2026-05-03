"""Phase 3: Normalize variables to 0-100 and compute structural strength scores.

Outputs:
  data/processed/normalized.csv         long format with raw + normalized values
  data/processed/structural_scores.csv  one row per (country, year) with composite score
"""
import sys
from pathlib import Path
import pandas as pd
import numpy as np

sys.path.insert(0, str(Path(__file__).parent))
from _common import (
    PROC, VARIABLES, STRUCTURAL_WEIGHTS, INVERT_AT_NORMALIZE, MIN_VARS_FOR_SCORE,
)


def main():
    print("[Phase 3] Normalize")
    h = pd.read_csv(PROC / "harmonized.csv")

    # ── Per-year normalization to 0-100 (direction-corrected) ──
    # For each (variable, year), scale across countries available in that decade.
    # Score 80 means "top 20% of countries in this specific decade".
    h["normalized_value"] = np.nan
    overall_bounds = {}
    for (var, year), sub in h.groupby(["variable", "year"]):
        if sub.empty:
            continue
        vmin = sub["value"].min()
        vmax = sub["value"].max()
        if vmax == vmin:
            norm = pd.Series(50.0, index=sub.index)
        else:
            norm = (sub["value"] - vmin) / (vmax - vmin) * 100.0
        if var in INVERT_AT_NORMALIZE:
            norm = 100.0 - norm
        h.loc[sub.index, "normalized_value"] = norm

    # Track overall raw range per variable (for reporting only — not used for scaling)
    for var in VARIABLES:
        sub = h[h["variable"] == var]
        if not sub.empty:
            overall_bounds[var] = (sub["value"].min(), sub["value"].max())

    print("  Per-year normalization (each decade scaled independently)")
    print("  Overall raw value ranges (for reference only):")
    for var, (lo, hi) in overall_bounds.items():
        direction = " (inverted)" if var in INVERT_AT_NORMALIZE else ""
        print(f"    {var:18s}  raw range {lo:>10.2f} .. {hi:>10.2f}{direction}")

    # rename + reorder columns for normalized.csv
    norm_out = h.rename(columns={"value": "raw_value"})[
        ["country_name", "iso3", "year", "variable", "raw_value",
         "normalized_value", "source", "is_sparse"]
    ]
    norm_path = PROC / "normalized.csv"
    norm_out.to_csv(norm_path, index=False)
    print(f"  -> {norm_path}  ({len(norm_out):,} rows)")

    # ── Build wide table for structural scoring ──
    # Use only non-sparse rows. Keep raw country-year-variable -> normalized_value.
    usable = h[~h["is_sparse"]].copy()
    wide = usable.pivot_table(
        index=["country_name", "iso3", "year"],
        columns="variable",
        values="normalized_value",
        aggfunc="first",
    ).reset_index()

    # Ensure all weighted variables exist as columns (even if empty)
    for var in STRUCTURAL_WEIGHTS:
        if var not in wide.columns:
            wide[var] = np.nan

    # Compute structural strength
    weighted_vars = list(STRUCTURAL_WEIGHTS.keys())
    weights = pd.Series(STRUCTURAL_WEIGHTS)

    def row_score(row):
        avail = {v: row[v] for v in weighted_vars if pd.notna(row[v])}
        if len(avail) < MIN_VARS_FOR_SCORE:
            return pd.Series({"structural_strength": np.nan,
                              "variables_used": ",".join(sorted(avail.keys()))})
        w = weights[list(avail.keys())]
        w_norm = w / w.sum()
        score = sum(avail[v] * w_norm[v] for v in avail)
        return pd.Series({"structural_strength": score,
                          "variables_used": ",".join(sorted(avail.keys()))})

    scored = wide.apply(row_score, axis=1)
    wide = pd.concat([wide, scored], axis=1)

    # Build the output: country, iso3, year, structural_strength, variables_used,
    #                  gdp_norm, life_norm, edu_norm, gini_norm, pop_norm
    rename_map = {
        "gdp_per_capita":  "gdp_norm",
        "life_expectancy": "life_norm",
        "education_years": "edu_norm",
        "gini":            "gini_norm",
        "population":      "pop_norm",
    }
    for src, dst in rename_map.items():
        wide[dst] = wide.get(src, np.nan)

    out = wide[
        ["country_name", "iso3", "year",
         "structural_strength", "variables_used",
         "gdp_norm", "life_norm", "edu_norm", "gini_norm", "pop_norm"]
    ].sort_values(["country_name", "year"]).reset_index(drop=True)

    score_path = PROC / "structural_scores.csv"
    out.to_csv(score_path, index=False)

    n_scored = out["structural_strength"].notna().sum()
    print(f"  -> {score_path}  ({len(out):,} rows, {n_scored:,} with score)")

    # Quick distribution
    if n_scored > 0:
        s = out["structural_strength"].dropna()
        print(f"  score distribution: min={s.min():.1f}  median={s.median():.1f}  max={s.max():.1f}")


if __name__ == "__main__":
    main()
