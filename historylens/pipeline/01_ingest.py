"""Phase 1: Ingest all raw sources into a single long-format CSV.

Outputs: data/processed/raw_long.csv
Columns: country_name, iso3, year, variable, value, source
"""
import sys
import warnings
from pathlib import Path
import pandas as pd

sys.path.insert(0, str(Path(__file__).parent))
from _common import RAW, PROC, DECADES, CLIO_FILES, MADDISON_FILE, OWID_LIFE_FILE

warnings.filterwarnings("ignore")


def ingest_clio(path, variable):
    """CLIO-INFRA wide-format XLSX -> long format restricted to decade columns."""
    df = pd.read_excel(path, sheet_name="Data Clio Infra Format")
    # year columns may be int or str — build a lookup
    cols_by_year = {}
    for c in df.columns:
        try:
            cols_by_year[int(float(c))] = c
        except (ValueError, TypeError):
            continue
    decade_cols = [cols_by_year[d] for d in DECADES if d in cols_by_year]
    sub = df[["ccode", "country name"] + decade_cols].copy()
    sub.columns = ["iso3", "country_name"] + DECADES[:len(decade_cols)]
    long = sub.melt(
        id_vars=["iso3", "country_name"],
        var_name="year",
        value_name="value",
    )
    long["year"] = long["year"].astype(int)
    long["variable"] = variable
    long["source"] = "CLIO-INFRA"
    long = long.dropna(subset=["value"])
    return long[["country_name", "iso3", "year", "variable", "value", "source"]]


def ingest_maddison(path):
    """Maddison Project 'Full data' sheet -> long format for gdp_per_capita and population."""
    df = pd.read_excel(path, sheet_name="Full data")
    df = df[df["year"].isin(DECADES)].copy()

    gdp = df[["country", "countrycode", "year", "gdppc"]].rename(
        columns={"country": "country_name", "countrycode": "iso3", "gdppc": "value"}
    )
    gdp["variable"] = "gdp_per_capita"
    gdp["source"] = "Maddison"

    pop = df[["country", "countrycode", "year", "pop"]].rename(
        columns={"country": "country_name", "countrycode": "iso3", "pop": "value"}
    )
    pop["variable"] = "population"
    pop["source"] = "Maddison"

    out = pd.concat([gdp, pop], ignore_index=True)
    out = out.dropna(subset=["value"])
    return out[["country_name", "iso3", "year", "variable", "value", "source"]]


def ingest_owid_life(path):
    """OWID life expectancy CSV -> long format restricted to decade years."""
    df = pd.read_csv(path)
    df = df[df["Year"].isin(DECADES)].copy()
    df = df.rename(columns={
        "Entity": "country_name",
        "Code": "iso3",
        "Year": "year",
        "Life expectancy": "value",
    })
    df["variable"] = "life_expectancy"
    df["source"] = "OWID"
    df = df.dropna(subset=["value"])
    return df[["country_name", "iso3", "year", "variable", "value", "source"]]


def main():
    print("[Phase 1] Ingest")
    parts = []

    for fname, var in CLIO_FILES.items():
        path = RAW / fname
        if not path.exists():
            print(f"  MISSING: {fname}")
            continue
        d = ingest_clio(path, var)
        print(f"  CLIO-INFRA {var:18s}  {len(d):>5} rows  ({path.name})")
        parts.append(d)

    mad_path = RAW / MADDISON_FILE
    if mad_path.exists():
        d = ingest_maddison(mad_path)
        print(f"  Maddison    gdp+pop             {len(d):>5} rows  ({mad_path.name})")
        parts.append(d)
    else:
        print(f"  MISSING: {MADDISON_FILE}")

    owid_path = RAW / OWID_LIFE_FILE
    if owid_path.exists():
        d = ingest_owid_life(owid_path)
        print(f"  OWID        life_expectancy     {len(d):>5} rows  ({owid_path.name})")
        parts.append(d)
    else:
        print(f"  MISSING: {OWID_LIFE_FILE}")

    raw_long = pd.concat(parts, ignore_index=True)
    raw_long = raw_long.sort_values(["variable", "country_name", "year", "source"]).reset_index(drop=True)

    out_path = PROC / "raw_long.csv"
    raw_long.to_csv(out_path, index=False)
    print(f"\n  TOTAL: {len(raw_long):,} rows  ->  {out_path}")
    print(f"  variables: {sorted(raw_long['variable'].unique())}")
    print(f"  sources:   {sorted(raw_long['source'].unique())}")
    print(f"  countries: {raw_long['country_name'].nunique()} unique")


if __name__ == "__main__":
    main()
