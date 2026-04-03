"""Fetch housing_vacancy_rate, median_home_value, population_change_pct from Census."""
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


def fetch_acs(variables: str, label: str) -> pd.DataFrame:
    url = f"https://api.census.gov/data/2022/acs/acs5?get=NAME,{variables}&for=county:*{key_param}"
    print(f"  Fetching {label}...")
    r = requests.get(url, headers=headers, timeout=60)
    r.raise_for_status()
    data = r.json()
    df = pd.DataFrame(data[1:], columns=data[0])
    df["fips"] = df["state"].str.zfill(2) + df["county"].str.zfill(3)
    return df


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

    # 1. HOUSING VACANCY RATE
    print("\n=== HOUSING VACANCY RATE ===")
    df_hv = fetch_acs("B25002_003E,B25002_001E", "housing vacancy")
    for col in ["B25002_003E", "B25002_001E"]:
        df_hv[col] = pd.to_numeric(df_hv[col], errors="coerce")
    df_hv["housing_vacancy_rate"] = np.where(
        df_hv["B25002_001E"] > 0,
        df_hv["B25002_003E"] / df_hv["B25002_001E"],
        np.nan
    )
    df_hv["housing_vacancy_rate"] = df_hv["housing_vacancy_rate"].clip(0, 1)
    valid = df_hv.dropna(subset=["housing_vacancy_rate"])
    missing = len(df_hv) - len(valid)
    mn_fips = valid.loc[valid["housing_vacancy_rate"].idxmin(), "fips"]
    mx_fips = valid.loc[valid["housing_vacancy_rate"].idxmax(), "fips"]
    print(f"  Counties updated: {len(valid)}")
    print(f"  Mean value: {valid['housing_vacancy_rate'].mean():.4f}")
    print(f"  Min: {valid['housing_vacancy_rate'].min():.4f} ({names.get(mn_fips, mn_fips)})")
    print(f"  Max: {valid['housing_vacancy_rate'].max():.4f} ({names.get(mx_fips, mx_fips)})")
    print(f"  Missing/imputed: {missing}")
    n = upsert_to_supabase(c, "housing_vacancy_rate", "housing_vacancy_rate", valid, "housing_vacancy_rate")
    print(f"  Uploaded {n} rows")

    # 2. MEDIAN HOME VALUE
    print("\n=== MEDIAN HOME VALUE ===")
    df_mv = fetch_acs("B25077_001E", "median home value")
    df_mv["median_home_value"] = pd.to_numeric(df_mv["B25077_001E"], errors="coerce")
    # Census uses -666666666 as sentinel for suppressed data
    df_mv.loc[df_mv["median_home_value"] < 0, "median_home_value"] = np.nan
    valid = df_mv.dropna(subset=["median_home_value"])
    # Store raw value (will be min-max normalized by calibrate_beta)
    missing = len(df_mv) - len(valid)
    mn_fips = valid.loc[valid["median_home_value"].idxmin(), "fips"]
    mx_fips = valid.loc[valid["median_home_value"].idxmax(), "fips"]
    print(f"  Counties updated: {len(valid)}")
    print(f"  Mean value: ${valid['median_home_value'].mean():,.0f}")
    print(f"  Min: ${valid['median_home_value'].min():,.0f} ({names.get(mn_fips, mn_fips)})")
    print(f"  Max: ${valid['median_home_value'].max():,.0f} ({names.get(mx_fips, mx_fips)})")
    print(f"  Missing/imputed: {missing}")
    n = upsert_to_supabase(c, "median_home_value", "median_home_value", valid, "median_home_value")
    print(f"  Uploaded {n} rows")

    # 3. POPULATION CHANGE PCT (2020 to 2022)
    print("\n=== POPULATION CHANGE PCT ===")
    # Try Census PEP (Population Estimates Program)
    try:
        pep_url = (f"https://api.census.gov/data/2022/pep/population"
                   f"?get=NAME,POP_2022,POP_2020&for=county:*{key_param}")
        print(f"  Fetching from PEP 2022...")
        r = requests.get(pep_url, headers=headers, timeout=60)
        r.raise_for_status()
        data = r.json()
        df_pop = pd.DataFrame(data[1:], columns=data[0])
        df_pop["fips"] = df_pop["state"].str.zfill(2) + df_pop["county"].str.zfill(3)
        df_pop["pop22"] = pd.to_numeric(df_pop["POP_2022"], errors="coerce")
        df_pop["pop20"] = pd.to_numeric(df_pop["POP_2020"], errors="coerce")
        df_pop["population_change_pct"] = np.where(
            df_pop["pop20"] > 0,
            (df_pop["pop22"] - df_pop["pop20"]) / df_pop["pop20"],
            np.nan
        )
        print("  PEP source successful")
    except Exception as e:
        print(f"  PEP failed ({e}), falling back to ACS B01003 vs Decennial PL...")
        # Fallback: use ACS 2022 total pop and Census 2020 decennial PL 94-171
        df_acs = fetch_acs("B01003_001E", "ACS 2022 population")
        df_acs["pop22"] = pd.to_numeric(df_acs["B01003_001E"], errors="coerce")
        # Fetch 2020 Decennial
        dec_url = (f"https://api.census.gov/data/2020/dec/pl"
                   f"?get=NAME,P1_001N&for=county:*{key_param}")
        print("  Fetching 2020 Decennial population...")
        r2 = requests.get(dec_url, headers=headers, timeout=60)
        r2.raise_for_status()
        data2 = r2.json()
        df_dec = pd.DataFrame(data2[1:], columns=data2[0])
        df_dec["fips"] = df_dec["state"].str.zfill(2) + df_dec["county"].str.zfill(3)
        df_dec["pop20"] = pd.to_numeric(df_dec["P1_001N"], errors="coerce")
        df_pop = df_acs[["fips", "pop22"]].merge(df_dec[["fips", "pop20"]], on="fips", how="inner")
        df_pop["population_change_pct"] = np.where(
            df_pop["pop20"] > 0,
            (df_pop["pop22"] - df_pop["pop20"]) / df_pop["pop20"],
            np.nan
        )

    # Clamp extreme values
    df_pop["population_change_pct"] = df_pop["population_change_pct"].clip(-0.5, 0.5)
    valid = df_pop.dropna(subset=["population_change_pct"])
    missing = len(df_pop) - len(valid)
    mn_fips = valid.loc[valid["population_change_pct"].idxmin(), "fips"]
    mx_fips = valid.loc[valid["population_change_pct"].idxmax(), "fips"]
    print(f"  Counties updated: {len(valid)}")
    print(f"  Mean value: {valid['population_change_pct'].mean():.4f}")
    print(f"  Min: {valid['population_change_pct'].min():.4f} ({names.get(mn_fips, mn_fips)})")
    print(f"  Max: {valid['population_change_pct'].max():.4f} ({names.get(mx_fips, mx_fips)})")
    print(f"  Missing/imputed: {missing}")
    n = upsert_to_supabase(c, "population_change_pct", "population_change_pct", valid, "population_change_pct")
    print(f"  Uploaded {n} rows")

    print("\nWave 4 housing/vitality ingest complete.")


if __name__ == "__main__":
    main()
