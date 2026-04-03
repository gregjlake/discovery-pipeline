"""Fetch manufacturing_pct and agriculture_pct from Census ACS 5-Year 2022 DP03."""
import os
import sys
import requests
import pandas as pd
import numpy as np
from pathlib import Path
from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parent.parent.parent / ".env", override=False)
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

CENSUS_KEY = os.environ.get("CENSUS_API_KEY", "")
key_param = f"&key={CENSUS_KEY}" if CENSUS_KEY else ""
headers = {"User-Agent": "Mozilla/5.0 (research data download)"}


def upsert_to_supabase(client, dataset_id, column_name, df, value_col):
    rows = [{"fips": r["fips"], "dataset_id": dataset_id, "year": 2022,
             "value": float(r[value_col]), "column_name": column_name}
            for _, r in df.iterrows() if pd.notna(r[value_col])]
    client.table("raw_values").delete().eq("dataset_id", dataset_id).execute()
    for i in range(0, len(rows), 500):
        client.table("raw_values").insert(rows[i:i+500]).execute()
    return len(rows)


def main():
    from supabase import create_client
    c = create_client(os.environ["SUPABASE_URL"], os.environ["SUPABASE_SERVICE_KEY"])

    centroids = pd.read_csv(
        Path(__file__).resolve().parent.parent.parent / "data" / "county_centroids.csv",
        dtype={"fips": str}
    )
    centroids["fips"] = centroids["fips"].str.zfill(5)
    names = dict(zip(centroids["fips"], centroids["county_name"]))

    # Fetch DP03 profile table: manufacturing % and agriculture %
    print("\n=== INDUSTRY DATA (ACS DP03) ===")
    url = (f"https://api.census.gov/data/2022/acs/acs5/profile"
           f"?get=NAME,DP03_0033PE,DP03_0028PE&for=county:*{key_param}")
    print(f"  Fetching DP03 industry percentages...")
    r = requests.get(url, headers=headers, timeout=60)
    r.raise_for_status()
    data = r.json()
    df = pd.DataFrame(data[1:], columns=data[0])
    df["fips"] = df["state"].str.zfill(2) + df["county"].str.zfill(3)

    # 1. MANUFACTURING PCT
    print("\n=== MANUFACTURING PCT ===")
    df["manufacturing_pct"] = pd.to_numeric(df["DP03_0033PE"], errors="coerce") / 100.0
    df["manufacturing_pct"] = df["manufacturing_pct"].clip(0, 1)
    valid = df.dropna(subset=["manufacturing_pct"])
    missing = len(df) - len(valid)
    mn_fips = valid.loc[valid["manufacturing_pct"].idxmin(), "fips"]
    mx_fips = valid.loc[valid["manufacturing_pct"].idxmax(), "fips"]
    print(f"  Counties updated: {len(valid)}")
    print(f"  Mean value: {valid['manufacturing_pct'].mean():.4f}")
    print(f"  Min: {valid['manufacturing_pct'].min():.4f} ({names.get(mn_fips, mn_fips)})")
    print(f"  Max: {valid['manufacturing_pct'].max():.4f} ({names.get(mx_fips, mx_fips)})")
    print(f"  Missing/imputed: {missing}")
    n = upsert_to_supabase(c, "manufacturing_pct", "manufacturing_pct", valid, "manufacturing_pct")
    print(f"  Uploaded {n} rows")

    # 2. AGRICULTURE PCT
    print("\n=== AGRICULTURE PCT ===")
    df["agriculture_pct"] = pd.to_numeric(df["DP03_0028PE"], errors="coerce") / 100.0
    df["agriculture_pct"] = df["agriculture_pct"].clip(0, 1)
    valid = df.dropna(subset=["agriculture_pct"])
    missing = len(df) - len(valid)
    mn_fips = valid.loc[valid["agriculture_pct"].idxmin(), "fips"]
    mx_fips = valid.loc[valid["agriculture_pct"].idxmax(), "fips"]
    print(f"  Counties updated: {len(valid)}")
    print(f"  Mean value: {valid['agriculture_pct'].mean():.4f}")
    print(f"  Min: {valid['agriculture_pct'].min():.4f} ({names.get(mn_fips, mn_fips)})")
    print(f"  Max: {valid['agriculture_pct'].max():.4f} ({names.get(mx_fips, mx_fips)})")
    print(f"  Missing/imputed: {missing}")
    n = upsert_to_supabase(c, "agriculture_pct", "agriculture_pct", valid, "agriculture_pct")
    print(f"  Uploaded {n} rows")

    print("\nWave 3 industry ingest complete.")


if __name__ == "__main__":
    main()
