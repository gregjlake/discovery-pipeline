"""Fetch child_poverty_rate, single_parent_rate, foreign_born_pct, language_isolation_rate from Census ACS 5-Year 2022."""
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
BASE = "https://api.census.gov/data/2022/acs/acs5"
key_param = f"&key={CENSUS_KEY}" if CENSUS_KEY else ""
headers = {"User-Agent": "Mozilla/5.0 (research data download)"}


def fetch_acs(variables: str, label: str) -> pd.DataFrame:
    url = f"{BASE}?get=NAME,{variables}&for=county:*{key_param}"
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

    # Load county names for reporting
    centroids = pd.read_csv(
        Path(__file__).resolve().parent.parent.parent / "data" / "county_centroids.csv",
        dtype={"fips": str}
    )
    centroids["fips"] = centroids["fips"].str.zfill(5)
    names = dict(zip(centroids["fips"], centroids["county_name"]))

    # 1. CHILD POVERTY RATE (children under 18 in poverty / total children under 18)
    # Use Subject Table S1701_C03_002E (% below poverty, under 18 years)
    print("\n=== CHILD POVERTY RATE ===")
    try:
        url_subj = f"https://api.census.gov/data/2022/acs/acs5/subject?get=NAME,S1701_C03_002E&for=county:*{key_param}"
        print(f"  Fetching child poverty from Subject Table S1701...")
        r = requests.get(url_subj, headers=headers, timeout=60)
        r.raise_for_status()
        data = r.json()
        df_cp = pd.DataFrame(data[1:], columns=data[0])
        df_cp["fips"] = df_cp["state"].str.zfill(2) + df_cp["county"].str.zfill(3)
        df_cp["child_poverty_rate"] = pd.to_numeric(df_cp["S1701_C03_002E"], errors="coerce") / 100.0
        df_cp["child_poverty_rate"] = df_cp["child_poverty_rate"].clip(0, 1)
        valid = df_cp.dropna(subset=["child_poverty_rate"])
        missing = len(df_cp) - len(valid)
        mn_fips = valid.loc[valid["child_poverty_rate"].idxmin(), "fips"]
        mx_fips = valid.loc[valid["child_poverty_rate"].idxmax(), "fips"]
        print(f"  Counties updated: {len(valid)}")
        print(f"  Mean value: {valid['child_poverty_rate'].mean():.4f}")
        print(f"  Min: {valid['child_poverty_rate'].min():.4f} ({names.get(mn_fips, mn_fips)})")
        print(f"  Max: {valid['child_poverty_rate'].max():.4f} ({names.get(mx_fips, mx_fips)})")
        print(f"  Missing/imputed: {missing}")
        n = upsert_to_supabase(c, "child_poverty_rate", "child_poverty_rate", valid, "child_poverty_rate")
        print(f"  Uploaded {n} rows")
    except Exception as e:
        print(f"  Subject table failed: {e}")
        print("  Falling back to B17001 detailed table...")
        # Fallback: B17001 detailed poverty by age
        male_vars = "B17001_004E,B17001_005E,B17001_006E,B17001_007E,B17001_008E,B17001_009E"
        female_vars = "B17001_018E,B17001_019E,B17001_020E,B17001_021E,B17001_022E,B17001_023E"
        denom_vars = "B17001_003E,B17001_017E"
        all_vars = f"{male_vars},{female_vars},{denom_vars}"
        df_cp = fetch_acs(all_vars, "child poverty B17001")
        male_cols = ["B17001_004E","B17001_005E","B17001_006E","B17001_007E","B17001_008E","B17001_009E"]
        female_cols = ["B17001_018E","B17001_019E","B17001_020E","B17001_021E","B17001_022E","B17001_023E"]
        for col in male_cols + female_cols + ["B17001_003E","B17001_017E"]:
            df_cp[col] = pd.to_numeric(df_cp[col], errors="coerce")
        numerator = df_cp[male_cols + female_cols].sum(axis=1)
        denominator = df_cp["B17001_003E"] + df_cp["B17001_017E"]
        df_cp["child_poverty_rate"] = np.where(denominator > 0, numerator / denominator, np.nan)
        df_cp["child_poverty_rate"] = df_cp["child_poverty_rate"].clip(0, 1)
        valid = df_cp.dropna(subset=["child_poverty_rate"])
        missing = len(df_cp) - len(valid)
        mn_fips = valid.loc[valid["child_poverty_rate"].idxmin(), "fips"]
        mx_fips = valid.loc[valid["child_poverty_rate"].idxmax(), "fips"]
        print(f"  Counties updated: {len(valid)}")
        print(f"  Mean value: {valid['child_poverty_rate'].mean():.4f}")
        print(f"  Min: {valid['child_poverty_rate'].min():.4f} ({names.get(mn_fips, mn_fips)})")
        print(f"  Max: {valid['child_poverty_rate'].max():.4f} ({names.get(mx_fips, mx_fips)})")
        print(f"  Missing/imputed: {missing}")
        n = upsert_to_supabase(c, "child_poverty_rate", "child_poverty_rate", valid, "child_poverty_rate")
        print(f"  Uploaded {n} rows")

    # 2. SINGLE PARENT RATE
    print("\n=== SINGLE PARENT RATE ===")
    df_sp = fetch_acs("B11001_005E,B11001_008E,B11001_001E", "single parent households")
    for col in ["B11001_005E", "B11001_008E", "B11001_001E"]:
        df_sp[col] = pd.to_numeric(df_sp[col], errors="coerce")
    df_sp["single_parent_rate"] = np.where(
        df_sp["B11001_001E"] > 0,
        (df_sp["B11001_005E"] + df_sp["B11001_008E"]) / df_sp["B11001_001E"],
        np.nan
    )
    df_sp["single_parent_rate"] = df_sp["single_parent_rate"].clip(0, 1)
    valid = df_sp.dropna(subset=["single_parent_rate"])
    missing = len(df_sp) - len(valid)
    mn_fips = valid.loc[valid["single_parent_rate"].idxmin(), "fips"]
    mx_fips = valid.loc[valid["single_parent_rate"].idxmax(), "fips"]
    print(f"  Counties updated: {len(valid)}")
    print(f"  Mean value: {valid['single_parent_rate'].mean():.4f}")
    print(f"  Min: {valid['single_parent_rate'].min():.4f} ({names.get(mn_fips, mn_fips)})")
    print(f"  Max: {valid['single_parent_rate'].max():.4f} ({names.get(mx_fips, mx_fips)})")
    print(f"  Missing/imputed: {missing}")
    n = upsert_to_supabase(c, "single_parent_rate", "single_parent_rate", valid, "single_parent_rate")
    print(f"  Uploaded {n} rows")

    # 3. FOREIGN BORN PCT
    print("\n=== FOREIGN BORN PCT ===")
    df_fb = fetch_acs("B05002_013E,B05002_001E", "foreign born")
    for col in ["B05002_013E", "B05002_001E"]:
        df_fb[col] = pd.to_numeric(df_fb[col], errors="coerce")
    df_fb["foreign_born_pct"] = np.where(
        df_fb["B05002_001E"] > 0,
        df_fb["B05002_013E"] / df_fb["B05002_001E"],
        np.nan
    )
    df_fb["foreign_born_pct"] = df_fb["foreign_born_pct"].clip(0, 1)
    valid = df_fb.dropna(subset=["foreign_born_pct"])
    missing = len(df_fb) - len(valid)
    mn_fips = valid.loc[valid["foreign_born_pct"].idxmin(), "fips"]
    mx_fips = valid.loc[valid["foreign_born_pct"].idxmax(), "fips"]
    print(f"  Counties updated: {len(valid)}")
    print(f"  Mean value: {valid['foreign_born_pct'].mean():.4f}")
    print(f"  Min: {valid['foreign_born_pct'].min():.4f} ({names.get(mn_fips, mn_fips)})")
    print(f"  Max: {valid['foreign_born_pct'].max():.4f} ({names.get(mx_fips, mx_fips)})")
    print(f"  Missing/imputed: {missing}")
    n = upsert_to_supabase(c, "foreign_born_pct", "foreign_born_pct", valid, "foreign_born_pct")
    print(f"  Uploaded {n} rows")

    # 4. LANGUAGE ISOLATION RATE
    print("\n=== LANGUAGE ISOLATION RATE ===")
    lang_vars = "B16002_004E,B16002_007E,B16002_010E,B16002_013E,B16002_001E"
    df_li = fetch_acs(lang_vars, "language isolation")
    iso_cols = ["B16002_004E", "B16002_007E", "B16002_010E", "B16002_013E"]
    for col in iso_cols + ["B16002_001E"]:
        df_li[col] = pd.to_numeric(df_li[col], errors="coerce")
    df_li["language_isolation_rate"] = np.where(
        df_li["B16002_001E"] > 0,
        df_li[iso_cols].sum(axis=1) / df_li["B16002_001E"],
        np.nan
    )
    df_li["language_isolation_rate"] = df_li["language_isolation_rate"].clip(0, 1)
    valid = df_li.dropna(subset=["language_isolation_rate"])
    missing = len(df_li) - len(valid)
    mn_fips = valid.loc[valid["language_isolation_rate"].idxmin(), "fips"]
    mx_fips = valid.loc[valid["language_isolation_rate"].idxmax(), "fips"]
    print(f"  Counties updated: {len(valid)}")
    print(f"  Mean value: {valid['language_isolation_rate'].mean():.4f}")
    print(f"  Min: {valid['language_isolation_rate'].min():.4f} ({names.get(mn_fips, mn_fips)})")
    print(f"  Max: {valid['language_isolation_rate'].max():.4f} ({names.get(mx_fips, mx_fips)})")
    print(f"  Missing/imputed: {missing}")
    n = upsert_to_supabase(c, "language_isolation_rate", "language_isolation_rate", valid, "language_isolation_rate")
    print(f"  Uploaded {n} rows")

    # 5. TEEN BIRTH RATE check
    print("\n=== TEEN BIRTH RATE ===")
    print("  Checking if teen_birth_rate exists in county_data...")
    try:
        r = c.table("raw_values").select("fips").eq("dataset_id", "teen_birth_rate").limit(1).execute()
        if r.data:
            print(f"  teen_birth_rate already exists in Supabase ({len(r.data)} rows found)")
        else:
            print("  teen_birth_rate NOT found. Skipped -- CDC WONDER requires data use agreement.")
    except Exception as e:
        print(f"  Check failed: {e}. Skipped -- CDC WONDER requires data use agreement.")

    print("\nWave 2 child/family/immigration ingest complete.")


if __name__ == "__main__":
    main()
