"""Phase 6: Export the consolidated JSON file the HistoryLens frontend will load.

Output: data/processed/historylens_final.json
"""
import sys
import json
import datetime
from collections import Counter
from pathlib import Path
import pandas as pd

sys.path.insert(0, str(Path(__file__).parent))
from _common import PROC, COUNTRY_MAP, DECADES

WEIGHTED_VARS = ["gdp_per_capita", "life_expectancy", "education_years", "gini", "population"]

# Per-user mapping. Hungary and Poland kept under "Western Europe" per the
# explicit specification (treats it as a European-core region, not strict geography).
REGION_MAP = {
    # Western Europe
    "Netherlands":    "Western Europe",
    "United Kingdom": "Western Europe",
    "France":         "Western Europe",
    "Sweden":         "Western Europe",
    "Norway":         "Western Europe",
    "Denmark":        "Western Europe",
    "Belgium":        "Western Europe",
    "Italy":          "Western Europe",
    "Spain":          "Western Europe",
    "Switzerland":    "Western Europe",
    "Germany":        "Western Europe",
    "Finland":        "Western Europe",
    "Portugal":       "Western Europe",
    "Greece":         "Western Europe",
    "Ireland":        "Western Europe",
    "Hungary":        "Western Europe",
    "Poland":         "Western Europe",
    # Anglo-Pacific
    "Australia":      "Anglo-Pacific",
    "Canada":         "Anglo-Pacific",
    # North America
    "United States":  "North America",
    "Mexico":         "North America",
    # Latin America
    "Chile":          "Latin America",
    "Argentina":      "Latin America",
    "Brazil":         "Latin America",
    "Colombia":       "Latin America",
    "Peru":           "Latin America",
    "Venezuela":      "Latin America",
    "Jamaica":        "Latin America",
    "Uruguay":        "Latin America",
    "Bolivia":        "Latin America",
    "Cuba":           "Latin America",
    # East Asia
    "Japan":          "East Asia",
    "China":          "East Asia",
    "South Korea":    "East Asia",
    "Indonesia":      "East Asia",
    "Philippines":    "East Asia",
    # South Asia
    "India":          "South Asia",
    # Eastern Europe
    "Russia":         "Eastern Europe",
    # Africa
    "South Africa":   "Africa",
    "Egypt":          "Africa",
}


def round_or_none(v, ndigits=1):
    if v is None or pd.isna(v):
        return None
    return round(float(v), ndigits)


def round_int_or_none(v):
    if v is None or pd.isna(v):
        return None
    return int(round(float(v)))


def main():
    print("[Phase 6] Export final JSON")

    scores     = pd.read_csv(PROC / "structural_scores.csv")
    peers      = pd.read_csv(PROC / "peers.csv")
    normalized = pd.read_csv(PROC / "normalized.csv")

    # Index for fast lookups
    score_idx = scores.set_index(["country_name", "year"])["structural_strength"]
    norm_idx  = normalized.set_index(["country_name", "year", "variable"])[
        ["raw_value", "normalized_value"]
    ]

    output = {
        "metadata": {
            "countries":     len(COUNTRY_MAP),
            "decades":       DECADES,
            "variables":     WEIGHTED_VARS,
            "normalization": "per-year",
            "generated":     datetime.date.today().isoformat(),
        },
        "countries": [],
    }

    for canonical_name, iso3, tier in COUNTRY_MAP:
        region = REGION_MAP.get(canonical_name, "Other")

        scores_dict    = {}
        peers_dict     = {}
        variables_dict = {}

        for year in DECADES:
            ystr = str(year)

            # Score
            s = score_idx.get((canonical_name, year), None)
            scores_dict[ystr] = round_or_none(s, 1)

            # Peers (top 3)
            ppl = peers[
                (peers["country_name"] == canonical_name) &
                (peers["year"] == year)
            ].sort_values("peer_rank").head(3)
            peers_dict[ystr] = [
                {"name": p["peer_name"], "similarity": int(round(p["similarity_pct"]))}
                for _, p in ppl.iterrows()
            ]

            # Variables (5 weighted vars; null where missing)
            year_vars = {}
            for var in WEIGHTED_VARS:
                key = (canonical_name, year, var)
                if key in norm_idx.index:
                    raw = norm_idx.loc[key, "raw_value"]
                    norm = norm_idx.loc[key, "normalized_value"]
                    if var in ("population", "gdp_per_capita"):
                        raw_out = round_int_or_none(raw)
                    else:
                        raw_out = round_or_none(raw, 2)
                    year_vars[var] = {
                        "raw":        raw_out,
                        "normalized": round_or_none(norm, 1),
                    }
                else:
                    year_vars[var] = {"raw": None, "normalized": None}
            variables_dict[ystr] = year_vars

        output["countries"].append({
            "name":      canonical_name,
            "iso3":      iso3,
            "region":    region,
            "tier":      tier,
            "scores":    scores_dict,
            "peers":     peers_dict,
            "variables": variables_dict,
        })

    out_path = PROC / "historylens_final.json"
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(output, f, indent=2, ensure_ascii=False)

    size_kb = out_path.stat().st_size / 1024
    print(f"  countries:      {len(output['countries'])}")
    print(f"  decades/country:{len(DECADES)}")
    print(f"  output size:    {size_kb:.1f} KB")

    regions = Counter(c["region"] for c in output["countries"])
    print(f"\n  Region distribution:")
    for region, count in sorted(regions.items(), key=lambda x: -x[1]):
        print(f"    {region:20s}  {count}")

    # Sanity: any country without any scored decade?
    blank = [c["name"] for c in output["countries"]
             if all(v is None for v in c["scores"].values())]
    if blank:
        print(f"\n  WARNING: countries with no scored decade: {blank}")

    print(f"\n  -> {out_path}")


if __name__ == "__main__":
    main()
