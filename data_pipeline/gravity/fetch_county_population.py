"""Fetch US county populations from Census ACS 5-Year 2022 and store in Supabase."""
import os
from pathlib import Path

import pandas as pd
import requests
from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parent.parent.parent / ".env", override=False)

ACS_URL = "https://api.census.gov/data/2022/acs/acs5"
# Free key: https://api.census.gov/data/key_signup.html
CENSUS_KEY = os.environ.get("CENSUS_API_KEY", "")

VALID_STATES = {str(i).zfill(2) for i in range(1, 57)}  # 01-56, skip gaps


def fetch():
    params = {"get": "NAME,B01003_001E", "for": "county:*"}
    if CENSUS_KEY:
        params["key"] = CENSUS_KEY

    print("Fetching county population from Census ACS 2022...")
    if not CENSUS_KEY:
        print("  (no CENSUS_API_KEY — using unauthenticated access)")

    resp = requests.get(ACS_URL, params=params, timeout=30)
    resp.raise_for_status()
    data = resp.json()

    df = pd.DataFrame(data[1:], columns=data[0])
    df["fips"] = df["state"].str.zfill(2) + df["county"].str.zfill(3)
    df["population"] = pd.to_numeric(df["B01003_001E"], errors="coerce")
    df = df.rename(columns={"NAME": "county_name"})
    df = df[df["state"].isin(VALID_STATES)]
    df = df.dropna(subset=["population"])
    df["population"] = df["population"].astype(int)
    df = df[["fips", "county_name", "population"]]

    return df


def save_csv(df):
    out = Path(__file__).resolve().parent.parent.parent / "data" / "county_population.csv"
    out.parent.mkdir(exist_ok=True)
    df.to_csv(out, index=False)
    print(f"Saved {out} ({len(df)} rows)")


def upsert_supabase(df):
    url = os.environ.get("SUPABASE_URL")
    key = os.environ.get("SUPABASE_SERVICE_KEY")
    if not url or not key:
        print("SUPABASE_URL/SUPABASE_SERVICE_KEY not set — skipping upload")
        return

    from supabase import create_client
    sb = create_client(url, key)

    rows = df.to_dict(orient="records")
    batch = 500
    total = 0
    for i in range(0, len(rows), batch):
        sb.table("county_population").upsert(rows[i : i + batch], on_conflict="fips").execute()
        total += len(rows[i : i + batch])
    print(f"Supabase: upserted {total} rows to county_population")


def main():
    df = fetch()
    print(f"\nTotal counties: {len(df)}")
    print(df.head().to_string(index=False))
    save_csv(df)
    upsert_supabase(df)


if __name__ == "__main__":
    main()
