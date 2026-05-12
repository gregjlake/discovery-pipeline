"""Phase 6: Export consolidated JSON for the HistoryLens frontend (v2).

Output: data/processed/historylens_final.json

v2 schema additions per (country, decade):
  scores_absolute, score_a, score_b, score_c, peer_stability, regional_peers
v2 schema additions per variable cell:
  population entries carry "display_only": true (not used in scoring)
v2 metadata additions:
  weight_schemes, peer_stability_summary, sample_composition
  normalization is now an object describing relative + absolute
"""
import sys
import json
import datetime
from collections import Counter
from pathlib import Path
import pandas as pd

sys.path.insert(0, str(Path(__file__).parent))
from _common import (
    PROC, COUNTRY_MAP, DECADES, WEIGHT_SCHEMES, REGION_MAP,
    SCORING_VARS, DISPLAY_ONLY_VARS,
)

EXPORT_VARS = SCORING_VARS + DISPLAY_ONLY_VARS  # 5 vars total

KNOWN_GAPS = [
    {
        "country": "Russia",
        "decades": [1820, 1830, 1840, 1850, 1860, 1880, 1910],
        "note": "Pre-1860 GDP unavailable, 1880/1910 data missing",
    },
    {
        "country": "South Africa",
        "decades": [1820, 1830, 1840, 1850, 1860],
        "note": "Data starts 1870",
    },
    {
        "country": "South Korea",
        "decades": [1820, 1830, 1840, 1850, 1860],
        "note": "Sparse pre-1870 coverage",
    },
    {
        "country": "United States",
        "decades": [1820, 1830, 1840, 1850, 1860, 1900],
        "note": "Absolute index null pre-1870 and at 1900 (Maddison gap)",
    },
    {
        "country": "China",
        "decades": [1820, 1830, 1840],
        "note": "Data starts 1850; 1820-1840 all null",
    },
]


def quality_label(year_vars, has_score):
    """Decade-level data quality from per-variable null counts.

    Counts only SCORING_VARS (population is display-only and ignored).
    """
    if not has_score:
        return "null"
    n_present = sum(
        1 for var in SCORING_VARS
        if year_vars.get(var, {}).get("raw") is not None
    )
    if n_present >= 4:
        return "good"
    if n_present >= 2:
        return "partial"
    return "sparse"


def round_or_none(v, ndigits=1):
    if v is None or pd.isna(v):
        return None
    return round(float(v), ndigits)


def round_int_or_none(v):
    if v is None or pd.isna(v):
        return None
    return int(round(float(v)))


def main():
    print("[Phase 6] Export final JSON (v2)")

    scores      = pd.read_csv(PROC / "structural_scores.csv")
    peers       = pd.read_csv(PROC / "peers.csv")            # scheme A
    regional    = pd.read_csv(PROC / "regional_peers.csv")
    stability   = pd.read_csv(PROC / "peer_stability.csv")
    normalized  = pd.read_csv(PROC / "normalized.csv")

    # Indexes
    score_idx = scores.set_index(["country_name", "year"])
    norm_idx  = normalized.set_index(["country_name", "year", "variable"])[
        ["raw_value", "normalized_value", "normalized_value_abs"]
    ]
    stab_idx = stability.set_index(["country_name", "year"])["stability"]

    # Sample composition (region count)
    sample_comp = Counter(REGION_MAP.get(name, "Other") for name, _, _ in COUNTRY_MAP)

    # Peer stability summary
    n_total = len(stability)
    n_100 = int((stability["stability"] == 100).sum())
    n_at_least_67 = int((stability["stability"] >= 67).sum())
    n_unstable = int((stability["stability"] < 67).sum())
    stability_summary = {
        "n_country_decades":  n_total,
        "pct_full_stability": round(100 * n_100 / n_total, 1) if n_total else 0.0,
        "pct_at_least_67":    round(100 * n_at_least_67 / n_total, 1) if n_total else 0.0,
        "pct_unstable":       round(100 * n_unstable / n_total, 1) if n_total else 0.0,
    }

    output = {
        "metadata": {
            "countries":     len(COUNTRY_MAP),
            "decades":       DECADES,
            "variables":     EXPORT_VARS,
            "scoring_variables":     SCORING_VARS,
            "display_only_variables": DISPLAY_ONLY_VARS,
            "normalization": {
                "relative": "Per-decade min-max scaling — each variable is normalized 0-100 across countries within each decade. Captures relative position within the decade.",
                "absolute": "Cross-time min-max scaling — each variable is normalized 0-100 across the entire 1820-2000 panel. Allows meaningful cross-decade comparison.",
            },
            "weight_schemes": {
                k: {"label": v["label"], "weights": v["weights"]}
                for k, v in WEIGHT_SCHEMES.items()
            },
            "default_scheme": "A",
            "peer_stability_summary": stability_summary,
            "sample_composition": dict(sorted(sample_comp.items(), key=lambda kv: -kv[1])),
            "known_gaps":    KNOWN_GAPS,
            "generated":     datetime.date.today().isoformat(),
            "schema_version": "2.0",
        },
        "countries": [],
    }

    for canonical_name, iso3, tier in COUNTRY_MAP:
        region = REGION_MAP.get(canonical_name, "Other")

        scores_dict = {}
        scores_abs_dict = {}
        score_a_dict = {}
        score_b_dict = {}
        score_c_dict = {}
        peers_dict = {}
        regional_peers_dict = {}
        variables_dict = {}
        data_quality_dict = {}
        peer_stability_dict = {}

        for year in DECADES:
            ystr = str(year)
            key_cy = (canonical_name, year)

            # Scores (relative scheme A is "scores", plus all four explicit fields)
            if key_cy in score_idx.index:
                row = score_idx.loc[key_cy]
                scores_dict[ystr]      = round_or_none(row.get("structural_strength"), 1)
                scores_abs_dict[ystr]  = round_or_none(row.get("structural_strength_absolute"), 1)
                score_a_dict[ystr]     = round_or_none(row.get("score_a"), 1)
                score_b_dict[ystr]     = round_or_none(row.get("score_b"), 1)
                score_c_dict[ystr]     = round_or_none(row.get("score_c"), 1)
            else:
                scores_dict[ystr] = scores_abs_dict[ystr] = None
                score_a_dict[ystr] = score_b_dict[ystr] = score_c_dict[ystr] = None
            has_score = scores_dict[ystr] is not None

            # Global peers (top 3, scheme A)
            ppl = peers[
                (peers["country_name"] == canonical_name) &
                (peers["year"] == year)
            ].sort_values("peer_rank").head(3)
            peers_dict[ystr] = [
                {"name": p["peer_name"], "similarity": int(round(p["similarity_pct"]))}
                for _, p in ppl.iterrows()
            ]

            # Regional peers (top 3, scheme A)
            rpl = regional[
                (regional["country_name"] == canonical_name) &
                (regional["year"] == year)
            ].sort_values("peer_rank").head(3)
            regional_list = [
                {"name": p["peer_name"], "similarity": int(round(p["similarity_pct"]))}
                for _, p in rpl.iterrows()
            ]
            # If region has fewer than 3 neighbors with data, pad with explanatory entries
            while len(regional_list) < 3:
                regional_list.append({"name": None, "similarity": None,
                                      "note": "insufficient regional coverage"})
            regional_peers_dict[ystr] = regional_list

            # Variables (5 — gdp, life, edu, gini, population)
            year_vars = {}
            for var in EXPORT_VARS:
                key = (canonical_name, year, var)
                cell = {"raw": None, "normalized": None, "normalized_absolute": None}
                if var in DISPLAY_ONLY_VARS:
                    cell["display_only"] = True
                if key in norm_idx.index:
                    row = norm_idx.loc[key]
                    raw = row["raw_value"]
                    norm = row["normalized_value"]
                    norm_abs = row["normalized_value_abs"]
                    if var in ("population", "gdp_per_capita"):
                        cell["raw"] = round_int_or_none(raw)
                    else:
                        cell["raw"] = round_or_none(raw, 2)
                    cell["normalized"] = round_or_none(norm, 1)
                    cell["normalized_absolute"] = round_or_none(norm_abs, 1)
                year_vars[var] = cell
            variables_dict[ystr] = year_vars
            data_quality_dict[ystr] = quality_label(year_vars, has_score)

            # Peer stability
            if key_cy in stab_idx.index:
                peer_stability_dict[ystr] = int(stab_idx.loc[key_cy])
            else:
                peer_stability_dict[ystr] = None

        output["countries"].append({
            "name":            canonical_name,
            "iso3":            iso3,
            "region":          region,
            "tier":            tier,
            "scores":          scores_dict,
            "scores_absolute": scores_abs_dict,
            "score_a":         score_a_dict,
            "score_b":         score_b_dict,
            "score_c":         score_c_dict,
            "peer_stability":  peer_stability_dict,
            "data_quality":    data_quality_dict,
            "peers":           peers_dict,
            "regional_peers":  regional_peers_dict,
            "variables":       variables_dict,
        })

    out_path = PROC / "historylens_final.json"
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(output, f, indent=2, ensure_ascii=False)

    size_kb = out_path.stat().st_size / 1024
    print(f"  countries:      {len(output['countries'])}")
    print(f"  decades/country:{len(DECADES)}")
    print(f"  output size:    {size_kb:.1f} KB")
    print(f"  peer stability: {stability_summary}")
    print(f"  sample composition: {dict(sample_comp)}")

    blank = [c["name"] for c in output["countries"]
             if all(v is None for v in c["scores"].values())]
    if blank:
        print(f"  WARNING: countries with no scored decade: {blank}")

    print(f"\n  -> {out_path}")


if __name__ == "__main__":
    main()
