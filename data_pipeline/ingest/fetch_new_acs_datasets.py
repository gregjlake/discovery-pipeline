"""Fetch bachelors_rate, median_age, homeownership_rate from Census ACS 5-Year 2022."""
import os
import sys
import json
import requests
import pandas as pd
import numpy as np
from pathlib import Path
from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parent.parent.parent / ".env", override=False)
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

CENSUS_KEY = os.environ.get("CENSUS_API_KEY", "")
BASE = "https://api.census.gov/data/2022/acs/acs5"
key_param = f"&key={CENSUS_KEY}" if CENSUS_KEY else ""
headers = {"User-Agent": "Mozilla/5.0 (research data download)"}


def fetch_acs(variables: str, label: str) -> pd.DataFrame:
    url = f"{BASE}?get=NAME,{variables}&for=county:*{key_param}"
    print(f"  Fetching {label}...")
    r = requests.get(url, headers=headers, timeout=30)
    r.raise_for_status()
    data = r.json()
    df = pd.DataFrame(data[1:], columns=data[0])
    df["fips"] = df["state"].str.zfill(2) + df["county"].str.zfill(3)
    return df


def main():
    from supabase import create_client
    c = create_client(os.environ["SUPABASE_URL"], os.environ["SUPABASE_SERVICE_KEY"])

    # 1. BACHELOR'S DEGREE RATE
    print("\n=== BACHELOR'S DEGREE RATE ===")
    df = fetch_acs("B15003_022E,B15003_001E", "education")
    df["bach"] = pd.to_numeric(df["B15003_022E"], errors="coerce")
    df["total"] = pd.to_numeric(df["B15003_001E"], errors="coerce")
    df["bachelors_rate"] = np.where(df["total"] > 0, df["bach"] / df["total"], np.nan)
    df["bachelors_rate"] = df["bachelors_rate"].clip(0, 1)
    valid = df.dropna(subset=["bachelors_rate"])
    print(f"  Counties: {len(valid)}, Mean: {valid['bachelors_rate'].mean():.3f}")
    print(f"  Top 5: {valid.nlargest(5, 'bachelors_rate')[['fips','NAME','bachelors_rate']].to_string(index=False)}")

    rows = [{"fips": r["fips"], "dataset_id": "bachelors_rate", "year": 2022,
             "value": float(r["bachelors_rate"]), "column_name": "bachelors_rate"} for _, r in valid.iterrows()]
    c.table("raw_values").delete().eq("dataset_id", "bachelors_rate").execute()
    for i in range(0, len(rows), 500):
        c.table("raw_values").insert(rows[i:i+500]).execute()
    print(f"  Uploaded {len(rows)} rows")

    # 2. MEDIAN AGE
    print("\n=== MEDIAN AGE ===")
    df2 = fetch_acs("B01002_001E", "median age")
    df2["median_age"] = pd.to_numeric(df2["B01002_001E"], errors="coerce")
    valid2 = df2.dropna(subset=["median_age"])
    mn, mx = valid2["median_age"].min(), valid2["median_age"].max()
    print(f"  Counties: {len(valid2)}, Min: {mn:.1f}, Max: {mx:.1f}, Mean: {valid2['median_age'].mean():.1f}")

    rows2 = [{"fips": r["fips"], "dataset_id": "median_age", "year": 2022,
              "value": float(r["median_age"]), "column_name": "median_age"} for _, r in valid2.iterrows()]
    c.table("raw_values").delete().eq("dataset_id", "median_age").execute()
    for i in range(0, len(rows2), 500):
        c.table("raw_values").insert(rows2[i:i+500]).execute()
    print(f"  Uploaded {len(rows2)} rows")

    # 3. HOMEOWNERSHIP RATE
    print("\n=== HOMEOWNERSHIP RATE ===")
    df3 = fetch_acs("B25003_002E,B25003_001E", "homeownership")
    df3["owner"] = pd.to_numeric(df3["B25003_002E"], errors="coerce")
    df3["total"] = pd.to_numeric(df3["B25003_001E"], errors="coerce")
    df3["homeownership_rate"] = np.where(df3["total"] > 0, df3["owner"] / df3["total"], np.nan)
    df3["homeownership_rate"] = df3["homeownership_rate"].clip(0, 1)
    valid3 = df3.dropna(subset=["homeownership_rate"])
    print(f"  Counties: {len(valid3)}, Mean: {valid3['homeownership_rate'].mean():.3f}")

    rows3 = [{"fips": r["fips"], "dataset_id": "homeownership_rate", "year": 2022,
              "value": float(r["homeownership_rate"]), "column_name": "homeownership_rate"} for _, r in valid3.iterrows()]
    c.table("raw_values").delete().eq("dataset_id", "homeownership_rate").execute()
    for i in range(0, len(rows3), 500):
        c.table("raw_values").insert(rows3[i:i+500]).execute()
    print(f"  Uploaded {len(rows3)} rows")

    print("\nAll three datasets ingested.")


if __name__ == "__main__":
    main()
