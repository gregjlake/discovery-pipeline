"""Phase 2: Harmonize raw_long across sources using priority rules.

For each (canonical_country, year, variable) triple, walk the priority list
of sources; within each source try every alias name; first non-null value wins.

Outputs: data/processed/harmonized.csv
Columns: country_name, iso3, year, variable, value, source, is_sparse, is_interpolated
"""
import sys
from pathlib import Path
import pandas as pd

sys.path.insert(0, str(Path(__file__).parent))
from _common import (
    PROC, DECADES, VARIABLES, SOURCE_PRIORITY,
    CANONICAL_NAMES, CANONICAL_TO_ISO, SPARSE_MIN_DECADES,
    aliases_for,
)


def main():
    print("[Phase 2] Harmonize")
    raw = pd.read_csv(PROC / "raw_long.csv")

    # Build a lookup index: (source, country_name, variable, year) -> value (first row's value)
    # Using groupby for speed.
    raw_idx = raw.set_index(["source", "country_name", "variable", "year"])["value"]
    raw_idx = raw_idx[~raw_idx.index.duplicated(keep="first")]

    rows = []
    unmatched = {}  # canonical_country -> set of variables with no source coverage at all

    for canonical in CANONICAL_NAMES:
        iso3 = CANONICAL_TO_ISO[canonical]
        for variable in VARIABLES:
            priority = SOURCE_PRIORITY[variable]
            for year in DECADES:
                value = None
                source_used = None
                for source in priority:
                    for alias in aliases_for(canonical, source):
                        key = (source, alias, variable, year)
                        if key in raw_idx.index:
                            v = raw_idx.loc[key]
                            if pd.notna(v):
                                value = float(v)
                                source_used = source
                                break
                    if value is not None:
                        break
                if value is not None:
                    rows.append({
                        "country_name":    canonical,
                        "iso3":            iso3,
                        "year":            year,
                        "variable":        variable,
                        "value":           value,
                        "source":          source_used,
                        "is_sparse":       False,    # filled below
                        "is_interpolated": False,    # never interpolated at this phase
                    })

            # Track variables a country has zero coverage on
            if not any(r for r in rows if r["country_name"] == canonical and r["variable"] == variable):
                unmatched.setdefault(canonical, set()).add(variable)

    harmonized = pd.DataFrame(rows)

    # Compute is_sparse: per (country, variable), if fewer than SPARSE_MIN_DECADES decade points -> sparse
    counts = (
        harmonized.groupby(["country_name", "variable"])["year"]
        .count()
        .rename("n_decades")
        .reset_index()
    )
    sparse_pairs = set(
        zip(
            counts.loc[counts["n_decades"] < SPARSE_MIN_DECADES, "country_name"],
            counts.loc[counts["n_decades"] < SPARSE_MIN_DECADES, "variable"],
        )
    )
    harmonized["is_sparse"] = list(
        (cn, var) in sparse_pairs
        for cn, var in zip(harmonized["country_name"], harmonized["variable"])
    )

    harmonized = harmonized.sort_values(
        ["country_name", "variable", "year"]
    ).reset_index(drop=True)

    out_path = PROC / "harmonized.csv"
    harmonized.to_csv(out_path, index=False)

    # Summary
    print(f"  rows:        {len(harmonized):,}")
    print(f"  countries:   {harmonized['country_name'].nunique()} of {len(CANONICAL_NAMES)}")
    print(f"  variables:   {harmonized['variable'].nunique()} of {len(VARIABLES)}")
    print(f"  sparse pairs (<{SPARSE_MIN_DECADES} decades): {len(sparse_pairs)}")

    # Source distribution per variable
    print("\n  Source distribution:")
    src_dist = (
        harmonized.groupby(["variable", "source"]).size().unstack(fill_value=0)
    )
    print(src_dist.to_string())

    # Sparse pairs detail
    if sparse_pairs:
        print("\n  Sparse (country, variable) pairs:")
        for cn, var in sorted(sparse_pairs):
            n = counts.loc[
                (counts["country_name"] == cn) & (counts["variable"] == var), "n_decades"
            ].values[0]
            print(f"    {cn:18s}  {var:18s}  ({n} decades)")

    # Countries with zero coverage on any variable (entirely missing)
    expected_pairs = {(c, v) for c in CANONICAL_NAMES for v in VARIABLES}
    present_pairs = set(zip(harmonized["country_name"], harmonized["variable"]))
    missing_pairs = expected_pairs - present_pairs
    if missing_pairs:
        print("\n  Country-variable pairs with NO data anywhere:")
        for cn, var in sorted(missing_pairs):
            print(f"    {cn:18s}  {var}")

    print(f"\n  -> {out_path}")


if __name__ == "__main__":
    main()
