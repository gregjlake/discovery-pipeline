"""Phase 3: Normalize variables and compute composite scores.

v2 (population removed from composite):
  Two normalization schemes are computed.
    relative — per-decade (each year scaled across countries 0-100). Used for
               within-time peer discovery and the canonical structural_strength.
    absolute — global (each variable scaled across the entire 1820-2000 panel).
               Used for cross-time meaningful "structural_strength_absolute".

  Three weight schemes (A, B, C) over the four scoring variables produce
  score_a (== structural_strength), score_b, score_c — all from the relative
  per-decade normalized values. structural_strength_absolute uses Scheme A
  applied to the absolute-normalized values.

  Population is normalized for display only (relative + absolute) but excluded
  from every composite.

Outputs:
  data/processed/normalized.csv         long format with raw + both norms
  data/processed/structural_scores.csv  one row per (country, year) with all
                                        composite scores and norm columns
"""
import sys
from pathlib import Path
import pandas as pd
import numpy as np

sys.path.insert(0, str(Path(__file__).parent))
from _common import (
    PROC, VARIABLES, SCORING_VARS, DISPLAY_ONLY_VARS,
    WEIGHT_SCHEMES, INVERT_AT_NORMALIZE, MIN_VARS_FOR_SCORE,
    redistribute_weights,
)

# Variables that get normalized for export. SCORING_VARS + display-only vars.
EXPORT_VARS = SCORING_VARS + DISPLAY_ONLY_VARS


def normalize_per_year(h):
    """Per-decade min-max scaling (0-100) of value -> normalized_value."""
    h = h.copy()
    h["normalized_value"] = np.nan
    for (var, year), sub in h.groupby(["variable", "year"]):
        if sub.empty:
            continue
        vmin, vmax = sub["value"].min(), sub["value"].max()
        if vmax == vmin:
            norm = pd.Series(50.0, index=sub.index)
        else:
            norm = (sub["value"] - vmin) / (vmax - vmin) * 100.0
        if var in INVERT_AT_NORMALIZE:
            norm = 100.0 - norm
        h.loc[sub.index, "normalized_value"] = norm
    return h


def normalize_global(h):
    """Cross-time min-max scaling (0-100) -> normalized_value_abs.

    For each variable, find the min and max across the entire 1820-2000 panel
    of all 40 countries, then scale every observation against those bounds.
    """
    h = h.copy()
    h["normalized_value_abs"] = np.nan
    bounds = {}
    for var, sub in h.groupby("variable"):
        if sub["value"].notna().sum() == 0:
            continue
        vmin, vmax = sub["value"].min(), sub["value"].max()
        bounds[var] = (vmin, vmax)
        if vmax == vmin:
            norm = pd.Series(50.0, index=sub.index)
        else:
            norm = (sub["value"] - vmin) / (vmax - vmin) * 100.0
        if var in INVERT_AT_NORMALIZE:
            norm = 100.0 - norm
        h.loc[sub.index, "normalized_value_abs"] = norm
    return h, bounds


def composite_score(row, norm_cols, scheme_weights):
    """Weighted composite over scoring vars present in `row`.

    norm_cols: dict of {variable_name: column_name_in_row}
    Redistributes scheme weights proportionally over available vars.
    Returns NaN if fewer than MIN_VARS_FOR_SCORE present.
    """
    available = {var: row[col] for var, col in norm_cols.items() if pd.notna(row[col])}
    if len(available) < MIN_VARS_FOR_SCORE:
        return np.nan
    w = redistribute_weights(scheme_weights, available.keys())
    if not w:
        return np.nan
    return sum(available[v] * w[v] for v in available)


def main():
    print("[Phase 3] Normalize")
    h = pd.read_csv(PROC / "harmonized.csv")

    # ── Per-year (relative) normalization ──
    h = normalize_per_year(h)
    print("  Per-year normalization computed (each decade scaled 0-100 across countries).")

    # ── Cross-time (absolute) normalization ──
    h, abs_bounds = normalize_global(h)
    print("  Global normalization computed (each variable scaled 0-100 across all decades):")
    for var, (lo, hi) in abs_bounds.items():
        direction = " (inverted)" if var in INVERT_AT_NORMALIZE else ""
        print(f"    {var:18s}  global raw range {lo:>10.2f} .. {hi:>10.2f}{direction}")

    # ── Write long-format normalized.csv ──
    # is_interpolated is carried through from harmonize so the exporter (Phase 6)
    # can flag interpolated urbanization cells in the final JSON.
    if "is_interpolated" not in h.columns:
        h["is_interpolated"] = False
    norm_out = h.rename(columns={"value": "raw_value"})[
        ["country_name", "iso3", "year", "variable", "raw_value",
         "normalized_value", "normalized_value_abs",
         "source", "is_sparse", "is_interpolated"]
    ]
    norm_path = PROC / "normalized.csv"
    norm_out.to_csv(norm_path, index=False)
    print(f"  -> {norm_path}  ({len(norm_out):,} rows)")

    # ── Build wide table for scoring ──
    usable = h[~h["is_sparse"]].copy()

    rel_wide = usable.pivot_table(
        index=["country_name", "iso3", "year"],
        columns="variable", values="normalized_value", aggfunc="first",
    )
    abs_wide = usable.pivot_table(
        index=["country_name", "iso3", "year"],
        columns="variable", values="normalized_value_abs", aggfunc="first",
    )

    # Ensure all expected columns exist
    for var in EXPORT_VARS:
        if var not in rel_wide.columns:
            rel_wide[var] = np.nan
        if var not in abs_wide.columns:
            abs_wide[var] = np.nan

    # Friendly column names for the score CSV
    rename_map = {
        "gdp_per_capita":  "gdp_norm",
        "life_expectancy": "life_norm",
        "education_years": "edu_norm",
        "gini":            "gini_norm",
        "urbanization":    "urb_norm",
        "population":      "pop_norm",
    }
    rename_map_abs = {k: v + "_abs" for k, v in rename_map.items()}

    rel_renamed = rel_wide[EXPORT_VARS].rename(columns=rename_map).reset_index()
    abs_renamed = abs_wide[EXPORT_VARS].rename(columns=rename_map_abs).reset_index()

    wide = rel_renamed.merge(abs_renamed, on=["country_name", "iso3", "year"], how="left")

    # Map scoring variables to the relevant column names in `wide`.
    # Population is intentionally absent from these maps — it does not score.
    rel_cols = {v: rename_map[v] for v in SCORING_VARS}
    abs_cols = {v: rename_map_abs[v] for v in SCORING_VARS}

    # Compute composites
    wide["score_a"] = wide.apply(lambda r: composite_score(r, rel_cols, WEIGHT_SCHEMES["A"]["weights"]), axis=1)
    wide["score_b"] = wide.apply(lambda r: composite_score(r, rel_cols, WEIGHT_SCHEMES["B"]["weights"]), axis=1)
    wide["score_c"] = wide.apply(lambda r: composite_score(r, rel_cols, WEIGHT_SCHEMES["C"]["weights"]), axis=1)
    wide["structural_strength"] = wide["score_a"]
    wide["structural_strength_absolute"] = wide.apply(
        lambda r: composite_score(r, abs_cols, WEIGHT_SCHEMES["A"]["weights"]), axis=1
    )

    # Track variables_used for each row (relative side; identical set for abs).
    def vars_used(row):
        return ",".join(sorted(v for v, col in rel_cols.items() if pd.notna(row[col])))
    wide["variables_used"] = wide.apply(vars_used, axis=1)

    out_cols = (
        ["country_name", "iso3", "year",
         "structural_strength", "structural_strength_absolute",
         "score_a", "score_b", "score_c",
         "variables_used",
         "gdp_norm", "life_norm", "edu_norm", "gini_norm", "urb_norm", "pop_norm",
         "gdp_norm_abs", "life_norm_abs", "edu_norm_abs", "gini_norm_abs",
         "urb_norm_abs", "pop_norm_abs"]
    )
    out = wide[out_cols].sort_values(["country_name", "year"]).reset_index(drop=True)
    score_path = PROC / "structural_scores.csv"
    out.to_csv(score_path, index=False)

    n_scored = out["structural_strength"].notna().sum()
    print(f"  -> {score_path}  ({len(out):,} rows, {n_scored:,} scored)")
    if n_scored > 0:
        s = out["structural_strength"].dropna()
        sa = out["structural_strength_absolute"].dropna()
        print(f"  relative score   min={s.min():.1f}  median={s.median():.1f}  max={s.max():.1f}")
        print(f"  absolute score   min={sa.min():.1f}  median={sa.median():.1f}  max={sa.max():.1f}")

    # ── Norway / Sweden / Denmark debug (CHANGE 5) ──
    print("\n  AFTER (v2 weights, no population, scheme A):")
    for ctry in ["Norway", "Sweden", "Denmark"]:
        print(f"\n    {ctry}:")
        sub = out[out["country_name"] == ctry]
        for d in [1940, 1950, 1960]:
            row = sub[sub["year"] == d]
            if row.empty:
                print(f"      {d}: <missing>")
                continue
            r = row.iloc[0]
            ss = r["structural_strength"]
            ss_abs = r["structural_strength_absolute"]
            ss_str = f"{ss:.1f}" if pd.notna(ss) else "n/a"
            ssa_str = f"{ss_abs:.1f}" if pd.notna(ss_abs) else "n/a"
            def _fmt(v):
                return "nan" if pd.isna(v) else f"{v:.1f}"
            print(f"      {d}: composite_rel={ss_str}  composite_abs={ssa_str}  vars={r['variables_used']}")
            print(f"            gdp_norm={_fmt(r['gdp_norm'])}  life={_fmt(r['life_norm'])}  edu={_fmt(r['edu_norm'])}  gini={_fmt(r['gini_norm'])}  (pop={_fmt(r['pop_norm'])} display only)")

    # 1950 ranking
    y50 = out[(out["year"] == 1950) & out["structural_strength"].notna()].sort_values(
        "structural_strength", ascending=False
    ).reset_index(drop=True)
    print("\n  1950 ranking (Scheme A, relative, v2):")
    for i, r in y50.iterrows():
        marker = " <-- Nordic" if r["country_name"] in ("Norway", "Sweden", "Denmark", "Finland") else ""
        print(f"    {i+1:2d}. {r['country_name']:18s}  {r['structural_strength']:5.1f}{marker}")


if __name__ == "__main__":
    main()
