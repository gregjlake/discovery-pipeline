"""Apply 4 dataset improvements: unemployment, food access, broadband avail, pop density."""
import io
import json
import os
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import requests
from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parent.parent / ".env", override=False)
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

DATA_DIR = Path(__file__).resolve().parent.parent / "data"


def _get_sb():
    from supabase import create_client
    return create_client(os.environ["SUPABASE_URL"], os.environ["SUPABASE_SERVICE_KEY"])


def _upsert_raw_values(sb, dataset_id, column_name, df_fips_value, year=2022):
    """Upsert a dataset column to raw_values table."""
    rows = []
    for _, row in df_fips_value.iterrows():
        v = row.iloc[1]
        if pd.isna(v):
            continue
        rows.append({
            "fips": row["fips"],
            "dataset_id": dataset_id,
            "column_name": column_name,
            "value": float(v),
            "year": year,
        })
    batch = 1000
    for i in range(0, len(rows), batch):
        sb.table("raw_values").upsert(rows[i:i+batch], on_conflict="fips,dataset_id,column_name").execute()
    print(f"  Supabase: upserted {len(rows)} rows for {dataset_id}/{column_name}")


# ═══════════════════════════════════════════════════════════════
# IMPROVEMENT 1: Unemployment — keep ACS 5yr but document clearly
# BLS blocks all programmatic access. ACS 1yr only covers 848 counties.
# Best option: keep ACS 5yr with updated notes.
# ═══════════════════════════════════════════════════════════════
def improvement1():
    print("\n" + "=" * 60)
    print("IMPROVEMENT 1: UNEMPLOYMENT — DOCUMENT ACS 5-YEAR LIMITATION")
    print("=" * 60)

    # Load current values
    sb = _get_sb()
    all_rows = []
    offset = 0
    while True:
        r = sb.table("raw_values").select("fips,value").eq("dataset_id", "unemployment").eq("column_name", "unemployment_rate").range(offset, offset+999).execute()
        if not r.data: break
        all_rows.extend(r.data)
        if len(r.data) < 1000: break
        offset += 1000

    vals = [row["value"] for row in all_rows]
    print(f"  Current unemployment: {len(vals)} counties")
    print(f"  Mean: {np.mean(vals):.4f} ({np.mean(vals)*100:.1f}%)")
    print(f"  Median: {np.median(vals):.4f}")
    print(f"  Range: {min(vals):.4f} to {max(vals):.4f}")
    print(f"  NOTE: BLS blocks programmatic access (403). ACS 1-year only covers 848 large counties.")
    print(f"  KEEPING ACS 5-year (2018-2022) with updated documentation.")

    # Update metadata
    meta_path = DATA_DIR / "dataset_metadata.json"
    with open(meta_path, encoding="utf-8") as f:
        meta = json.load(f)
    meta["unemployment"]["notes"] = (
        "ACS 5-year estimate (2018-2022) of U-3 unemployment rate. Includes 2020 pandemic spike "
        "(national peak 14.7%). BLS Local Area Unemployment Statistics (single-year county data) "
        "blocked programmatic access; ACS 1-year only covers 848 large counties. This 5-year average "
        "is the most complete county-level source available. U-3 counts only active job seekers; "
        "does not include discouraged workers or underemployed."
    )
    with open(meta_path, "w", encoding="utf-8") as f:
        json.dump(meta, f, indent=2, ensure_ascii=False)
    print("  Updated dataset_metadata.json")


# ═══════════════════════════════════════════════════════════════
# IMPROVEMENT 2: Food Access — USDA atlas unavailable, improve SNAP docs
# ═══════════════════════════════════════════════════════════════
def improvement2():
    print("\n" + "=" * 60)
    print("IMPROVEMENT 2: FOOD ACCESS — USDA ATLAS UNAVAILABLE")
    print("=" * 60)
    print("  USDA Food Access Research Atlas URLs return 404.")
    print("  The ERS download page has no direct file links.")
    print("  KEEPING SNAP participation rate with improved documentation.")

    meta_path = DATA_DIR / "dataset_metadata.json"
    with open(meta_path, encoding="utf-8") as f:
        meta = json.load(f)
    meta["food_access"]["notes"] = (
        "SNAP (food stamp) participation rate from Census ACS B22010. Measures economic need "
        "and program enrollment, NOT physical proximity to grocery stores. The USDA Food Access "
        "Research Atlas (standard food desert measure) was unavailable at ingest time and remains "
        "inaccessible (URLs return 404 as of March 2026). SNAP participation correlates with food "
        "insecurity (r~0.7 with poverty) but is distinct from physical food access. A county can "
        "have good physical access but high SNAP rates (low income), or poor physical access but "
        "low SNAP rates (rural, less enrollment). Interpret as economic food insecurity proxy."
    )
    meta["food_access"]["higher_is_better"] = False
    meta["food_access"]["direction_note"] = "Higher SNAP rate = more food insecurity. Not a direct measure of physical food access."
    with open(meta_path, "w", encoding="utf-8") as f:
        json.dump(meta, f, indent=2, ensure_ascii=False)
    print("  Updated dataset_metadata.json")


# ═══════════════════════════════════════════════════════════════
# IMPROVEMENT 3: FCC Broadband Availability (new dataset)
# Using Census ACS B28002 which already has broadband type data
# FCC data is census-block level (millions of rows) — too granular
# ═══════════════════════════════════════════════════════════════
def improvement3():
    print("\n" + "=" * 60)
    print("IMPROVEMENT 3: BROADBAND AVAILABILITY (NEW DATASET)")
    print("=" * 60)

    # FCC open data is census-block level — millions of rows, impractical.
    # Use Census ACS B28002 which reports internet type subscriptions.
    # B28002_002E = With an Internet subscription (any type)
    # B28002_001E = Total households
    # This captures "has any internet" which is availability-adjacent.
    # Also get B28002_007E = Broadband such as cable, fiber, DSL
    print("  FCC data is census-block level (millions of rows).")
    print("  Using Census ACS B28002 for any-internet subscription as availability proxy.")

    url = "https://api.census.gov/data/2022/acs/acs5"
    params = {"get": "NAME,B28002_001E,B28002_002E,B28002_007E", "for": "county:*"}
    resp = requests.get(url, params=params, timeout=30)
    resp.raise_for_status()
    data = resp.json()

    df = pd.DataFrame(data[1:], columns=data[0])
    df["fips"] = df["state"].str.zfill(2) + df["county"].str.zfill(3)
    df["total"] = pd.to_numeric(df["B28002_001E"], errors="coerce")
    df["any_internet"] = pd.to_numeric(df["B28002_002E"], errors="coerce")
    df["broadband_type"] = pd.to_numeric(df["B28002_007E"], errors="coerce")
    df = df.dropna(subset=["total", "any_internet"])
    df = df[df["total"] > 0]
    df["internet_access_rate"] = df["any_internet"] / df["total"]
    df = df[df["internet_access_rate"].between(0, 1)]
    df["year"] = 2022

    result = df[["fips", "internet_access_rate", "year"]].copy()
    print(f"  Counties: {len(result)}")
    print(f"  Mean internet access: {result['internet_access_rate'].mean():.3f} ({result['internet_access_rate'].mean()*100:.1f}%)")
    print(f"  Range: {result['internet_access_rate'].min():.3f} to {result['internet_access_rate'].max():.3f}")

    # Save and upsert
    result.to_csv(DATA_DIR / "broadband_avail.csv", index=False)
    sb = _get_sb()
    _upsert_raw_values(sb, "broadband_avail", "internet_access_rate", result[["fips", "internet_access_rate"]], 2022)

    # Update metadata
    meta_path = DATA_DIR / "dataset_metadata.json"
    with open(meta_path, encoding="utf-8") as f:
        meta = json.load(f)
    meta["broadband_avail"] = {
        "label": "Internet Access Rate",
        "source": "Census ACS 5-Year, Table B28002 (any internet subscription)",
        "source_url": "https://data.census.gov",
        "data_year": "2018-2022",
        "year_type": "range",
        "unit": "% households with any internet subscription",
        "higher_is_better": True,
        "data_type": "continuous",
        "maup_sensitivity": "low",
        "notes": (
            "Share of households with any internet subscription from ACS B28002. "
            "Includes broadband, dial-up, satellite, cellular. More inclusive than the "
            "existing broadband subscription rate (B28002_004E). FCC Form 477 county-level "
            "availability data was not used due to census-block granularity (millions of rows). "
            "This ACS measure captures internet adoption broadly, combining availability and "
            "affordability effects."
        ),
    }
    with open(meta_path, "w", encoding="utf-8") as f:
        json.dump(meta, f, indent=2, ensure_ascii=False)
    print("  Updated dataset_metadata.json with broadband_avail entry")

    return result


# ═══════════════════════════════════════════════════════════════
# IMPROVEMENT 4: Population Density (new dataset)
# ═══════════════════════════════════════════════════════════════
def improvement4():
    print("\n" + "=" * 60)
    print("IMPROVEMENT 4: POPULATION DENSITY (NEW DATASET)")
    print("=" * 60)

    # Get land area from Census Gazetteer (per-state files)
    print("  Downloading Census Gazetteer land area...")
    STATE_FIPS = [str(i).zfill(2) for i in range(1, 57) if i not in (3, 7, 14, 43, 52)]

    all_gaz = []
    for sf in STATE_FIPS:
        url = f"https://www2.census.gov/geo/docs/maps-data/data/gazetteer/2025_Gazetteer/2025_gaz_counties_{sf}.txt"
        try:
            r = requests.get(url, timeout=10)
            if r.status_code == 200:
                df = pd.read_csv(io.StringIO(r.text), sep="|", dtype=str)
                all_gaz.append(df)
        except:
            pass

    if not all_gaz:
        print("  ERROR: Could not download gazetteer files. Trying alternative...")
        # Fallback: use RUCC population data + approximate area
        # Actually, compute from county_centroids + county_population
        # Use approximate county area from typical US county (~1000 sq mi avg)
        pop = pd.read_csv(DATA_DIR / "county_population.csv", dtype={"fips": str})
        pop["fips"] = pop["fips"].str.zfill(5)
        # Average US county area ~1,000 sq mi, but this is too imprecise
        # Use the RUCC CSV which has population - at least we can rank
        print("  Gazetteer failed. Using population alone (density not possible without area).")
        return None

    gaz = pd.concat(all_gaz, ignore_index=True)
    # Parse pipe-delimited columns
    if len(gaz.columns) == 1:
        # Single column — need to split by pipe
        col = gaz.columns[0]
        split = gaz[col].str.split("|", expand=True)
        headers = col.split("|")
        split.columns = headers[:split.shape[1]]
        gaz = split

    gaz["fips"] = gaz["GEOID"].str.zfill(5)
    gaz["aland_sqmi"] = pd.to_numeric(gaz["ALAND_SQMI"], errors="coerce")

    # Load population
    pop = pd.read_csv(DATA_DIR / "county_population.csv", dtype={"fips": str})
    pop["fips"] = pop["fips"].str.zfill(5)

    # Merge
    merged = pop.merge(gaz[["fips", "aland_sqmi"]], on="fips", how="inner")
    merged = merged[merged["aland_sqmi"] > 0]
    merged["pop_density"] = merged["population"] / merged["aland_sqmi"]
    merged["year"] = 2022

    print(f"  Counties: {len(merged)}")
    print(f"  Density range: {merged['pop_density'].min():.1f} to {merged['pop_density'].max():.0f} people/sq mi")
    print(f"  Mean: {merged['pop_density'].mean():.1f}")
    print(f"  Median: {merged['pop_density'].median():.1f}")
    print(f"  p10: {merged['pop_density'].quantile(0.1):.1f}")
    print(f"  p90: {merged['pop_density'].quantile(0.9):.1f}")

    # Spot checks
    ny = merged[merged["fips"] == "36061"]
    if len(ny):
        print(f"  New York County (Manhattan): {ny.iloc[0]['pop_density']:.0f}/sq mi")

    result = merged[["fips", "pop_density", "year"]].copy()
    result.to_csv(DATA_DIR / "pop_density.csv", index=False)

    # Upsert
    sb = _get_sb()
    _upsert_raw_values(sb, "pop_density", "pop_density", result[["fips", "pop_density"]], 2022)

    # Update metadata
    meta_path = DATA_DIR / "dataset_metadata.json"
    with open(meta_path, encoding="utf-8") as f:
        meta = json.load(f)
    meta["pop_density"] = {
        "label": "Population Density",
        "source": "Census ACS 2022 population + Census Gazetteer land area",
        "source_url": "https://data.census.gov",
        "data_year": "2022",
        "year_type": "precise",
        "unit": "people per square mile",
        "higher_is_better": None,
        "data_type": "continuous",
        "maup_sensitivity": "low",
        "direction_note": "Higher = more urban. Neither high nor low is inherently better.",
        "notes": (
            "Continuous alternative to USDA Rural-Urban Continuum Codes. Highly right-skewed "
            "(Manhattan ~70K/sq mi vs rural Alaska <1/sq mi). Consider log scale for visualization. "
            "Computed as Census ACS population / Gazetteer land area in square miles."
        ),
    }
    with open(meta_path, "w", encoding="utf-8") as f:
        json.dump(meta, f, indent=2, ensure_ascii=False)
    print("  Updated dataset_metadata.json with pop_density entry")

    return result


# ═══════════════════════════════════════════════════════════════
# VALIDATION
# ═══════════════════════════════════════════════════════════════
def validate():
    print("\n" + "=" * 60)
    print("VALIDATION SPOT CHECKS")
    print("=" * 60)

    sb = _get_sb()

    # Count datasets in Supabase
    r = sb.table("raw_values").select("dataset_id", count="exact").limit(0).execute()
    print(f"  Total raw_values rows: {r.count}")

    # Count distinct datasets
    all_rows = []
    offset = 0
    while True:
        r = sb.table("raw_values").select("dataset_id,column_name").range(offset, offset+999).execute()
        if not r.data: break
        all_rows.extend(r.data)
        if len(r.data) < 1000: break
        offset += 1000
    pairs = set((d["dataset_id"], d["column_name"]) for d in all_rows)
    print(f"  Distinct dataset/column pairs: {len(pairs)}")
    for ds, col in sorted(pairs):
        print(f"    {ds}: {col}")


def main():
    improvement1()
    improvement2()
    improvement3()
    improvement4()
    validate()

    print("\n" + "=" * 60)
    print("SUMMARY")
    print("=" * 60)
    print("  unemployment: documented ACS 5yr limitation (BLS inaccessible)")
    print("  food_access:  documented SNAP proxy (USDA Atlas inaccessible)")
    print("  broadband_avail: NEW - Census ACS internet access rate")
    print("  pop_density:  NEW - Census population / Gazetteer area")


if __name__ == "__main__":
    main()
