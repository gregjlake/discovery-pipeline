"""Fetch Census ACS margins of error and compute county reliability scores."""
import requests
import pandas as pd
import numpy as np
import json
import os

BASE = "https://api.census.gov/data/2022/acs/acs5"
KEY = os.environ.get("CENSUS_API_KEY", "")
key_param = f"&key={KEY}" if KEY else ""

# ACS variables: (estimate, MOE, denominator, label)
ACS_VARS = {
    "broadband": {
        "get": "B28002_004E,B28002_004M,B28002_001E",
        "est": "B28002_004E", "moe": "B28002_004M", "denom": "B28002_001E",
    },
    "housing_burden": {
        "get": "B25070_010E,B25070_010M,B25070_001E",
        "est": "B25070_010E", "moe": "B25070_010M", "denom": "B25070_001E",
    },
    "unemployment": {
        "get": "B23025_005E,B23025_005M,B23025_002E",
        "est": "B23025_005E", "moe": "B23025_005M", "denom": "B23025_002E",
    },
    "bea_income": {
        "get": "B19301_001E,B19301_001M",
        "est": "B19301_001E", "moe": "B19301_001M", "denom": None,
    },
}

all_cv = {}

for var_name, spec in ACS_VARS.items():
    url = f"{BASE}?get=NAME,{spec['get']}&for=county:*{key_param}"
    print(f"Fetching {var_name}...")
    try:
        r = requests.get(url, timeout=30)
        if r.status_code != 200:
            print(f"  HTTP {r.status_code} - skipping")
            continue
        data = r.json()
        header = data[0]
        rows = data[1:]
        df = pd.DataFrame(rows, columns=header)
        df["fips"] = df["state"].str.zfill(2) + df["county"].str.zfill(3)

        est_col = spec["est"]
        moe_col = spec["moe"]
        df[est_col] = pd.to_numeric(df[est_col], errors="coerce")
        df[moe_col] = pd.to_numeric(df[moe_col], errors="coerce")

        # CV = MOE / (1.645 * estimate)
        df["se"] = df[moe_col].abs() / 1.645
        df["cv"] = np.where(df[est_col] > 0, df["se"] / df[est_col], np.nan)
        df["cv"] = df["cv"].clip(0, 5)  # cap extreme values

        for _, row in df.iterrows():
            fips = row["fips"]
            if fips not in all_cv:
                all_cv[fips] = {}
            all_cv[fips][var_name] = float(row["cv"]) if pd.notna(row["cv"]) else np.nan

        valid = df["cv"].dropna()
        print(f"  Counties: {len(df)}, CV available: {len(valid)}")
        print(f"  CV median: {valid.median():.3f}, mean: {valid.mean():.3f}")
        print(f"  CV < 0.15: {(valid < 0.15).sum()}, CV > 0.30: {(valid > 0.30).sum()}")
    except Exception as e:
        print(f"  ERROR: {e}")

# Load population data
pop_df = pd.read_csv("data/county_population.csv", dtype={"fips": str})
pop_df["fips"] = pop_df["fips"].str.zfill(5)
pop_lookup = dict(zip(pop_df["fips"], pop_df["population"].astype(float)))

# Compute composite reliability
results = []
for fips in sorted(all_cv.keys()):
    pop = pop_lookup.get(fips, 0)

    # Population reliability
    if pop < 1000:
        pop_rel = 0.2
    elif pop < 5000:
        pop_rel = 0.5
    elif pop < 10000:
        pop_rel = 0.7
    elif pop < 25000:
        pop_rel = 0.85
    else:
        pop_rel = 1.0

    # ACS variable reliabilities
    var_rels = []
    cvs = all_cv[fips]
    for var_name in ACS_VARS:
        cv = cvs.get(var_name)
        if cv is not None and not np.isnan(cv):
            if cv < 0.15:
                rel = 1.0
            elif cv < 0.30:
                rel = 1.0 - (cv - 0.15) / 0.15
            else:
                rel = 0.0
            var_rels.append(rel)

    acs_rel = np.mean(var_rels) if var_rels else 0.5
    composite = min(np.mean([acs_rel, pop_rel]), pop_rel)

    results.append({
        "fips": fips,
        "population": pop,
        "county_reliability": round(composite, 3),
        "broadband_cv": round(cvs.get("broadband", np.nan), 4) if not np.isnan(cvs.get("broadband", np.nan)) else None,
        "housing_cv": round(cvs.get("housing_burden", np.nan), 4) if not np.isnan(cvs.get("housing_burden", np.nan)) else None,
        "low_population_flag": pop < 5000,
        "very_low_population_flag": pop < 1000,
    })

df_out = pd.DataFrame(results)
df_out.to_csv("data/county_reliability.csv", index=False)
print(f"\nSaved data/county_reliability.csv: {len(df_out)} counties")

# Distribution
high = (df_out["county_reliability"] >= 0.8).sum()
mod = ((df_out["county_reliability"] >= 0.5) & (df_out["county_reliability"] < 0.8)).sum()
low = (df_out["county_reliability"] < 0.5).sum()
pop_lt5k = df_out["low_population_flag"].sum()
pop_lt1k = df_out["very_low_population_flag"].sum()

print(f"\nRELIABILITY DISTRIBUTION:")
print(f"  High (>= 0.8):     {high} ({high/len(df_out)*100:.1f}%)")
print(f"  Moderate (0.5-0.8): {mod} ({mod/len(df_out)*100:.1f}%)")
print(f"  Low (< 0.5):        {low} ({low/len(df_out)*100:.1f}%)")
print(f"  Population < 5,000: {pop_lt5k}")
print(f"  Population < 1,000: {pop_lt1k}")

# Sample low-reliability counties
print(f"\nSample low-reliability counties:")
low_sample = df_out[df_out["county_reliability"] < 0.5].sort_values("county_reliability").head(5)
for _, row in low_sample.iterrows():
    print(f"  {row['fips']}: pop={int(row['population'])}, reliability={row['county_reliability']:.3f}, bb_cv={row['broadband_cv']}, hb_cv={row['housing_cv']}")
