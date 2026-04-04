"""Fetch county-level life expectancy from County Health Rankings 2024."""
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


def upsert_to_supabase(client, dataset_id, column_name, df, value_col):
    rows = [{"fips": r["fips"], "dataset_id": dataset_id, "year": 2024,
             "value": float(r[value_col]), "column_name": column_name}
            for _, r in df.iterrows() if pd.notna(r[value_col])]
    client.table("raw_values").delete().eq("dataset_id", dataset_id).execute()
    for i in range(0, len(rows), 500):
        client.table("raw_values").insert(rows[i:i + 500]).execute()
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

    # Download County Health Rankings 2024 analytic data
    print("=== LIFE EXPECTANCY ===")
    print("Source: County Health Rankings 2024 (Robert Wood Johnson Foundation / UW)")
    url = "https://www.countyhealthrankings.org/sites/default/files/media/document/analytic_data2024.csv"
    print(f"  Fetching {url}...")
    r = requests.get(url, timeout=120, headers={"User-Agent": "Mozilla/5.0 (research data download)"})
    r.raise_for_status()

    lines = r.text.split("\n")
    # Row 0 = human-readable headers, Row 1 = variable codes, Row 2+ = data
    header_codes = lines[1].split(",")
    data_lines = lines[2:]

    # Parse into DataFrame using code headers
    import io
    csv_text = lines[1] + "\n" + "\n".join(data_lines)
    df = pd.read_csv(io.StringIO(csv_text), dtype={"fipscode": str}, low_memory=False)

    # Extract life expectancy (v147_rawvalue) and FIPS
    df["fips"] = df["fipscode"].astype(str).str.zfill(5)
    df["life_expectancy_raw"] = pd.to_numeric(df["v147_rawvalue"], errors="coerce")

    # Filter to counties only (countycode != "000" which is state-level)
    df = df[df["countycode"].astype(str) != "000"].copy()
    df = df[df["fips"].str.len() == 5].copy()

    # Drop missing
    valid = df.dropna(subset=["life_expectancy_raw"]).copy()
    missing_count = len(df) - len(valid)

    # Print raw stats
    mn_val = valid["life_expectancy_raw"].min()
    mx_val = valid["life_expectancy_raw"].max()
    mean_val = valid["life_expectancy_raw"].mean()
    mn_fips = valid.loc[valid["life_expectancy_raw"].idxmin(), "fips"]
    mx_fips = valid.loc[valid["life_expectancy_raw"].idxmax(), "fips"]

    print(f"  Counties with data: {len(valid)}")
    print(f"  Counties missing data: {missing_count}")
    print(f"  Min life expectancy: {mn_val:.1f} years ({names.get(mn_fips, mn_fips)})")
    print(f"  Max life expectancy: {mx_val:.1f} years ({names.get(mx_fips, mx_fips)})")
    print(f"  Mean life expectancy: {mean_val:.1f} years")

    # Upsert raw values to Supabase
    n = upsert_to_supabase(c, "life_expectancy", "life_expectancy", valid, "life_expectancy_raw")
    print(f"  Uploaded {n} rows to raw_values (dataset_id=life_expectancy)")


if __name__ == "__main__":
    main()
