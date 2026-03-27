import pandas as pd

def validate_dataset(df: pd.DataFrame, dataset_id: str) -> list:
    issues = []
    MIN_COUNTIES = {'library': 2500, 'mobility': 3000, 'air': 900, 'broadband': 3000}
    if df['fips'].nunique() < MIN_COUNTIES.get(dataset_id, 2000):
        issues.append(f"Low county coverage: {df['fips'].nunique()}")
    bad_fips = df[~df['fips'].str.match(r'^\d{5}$')]
    if len(bad_fips) > 0:
        issues.append(f"{len(bad_fips)} rows with malformed FIPS codes")
    EXPECTED_RANGES = {
        'library':   ('library_spend_per_capita',  0, 500),
        'mobility':  ('mobility_rank_p25',          0, 1),
        'air':       ('air_quality_inv',            0, 200),
        'broadband': ('broadband_rate',             0, 1),
    }
    if dataset_id in EXPECTED_RANGES:
        col, lo, hi = EXPECTED_RANGES[dataset_id]
        if col in df.columns:
            out_of_range = df[(df[col] < lo) | (df[col] > hi)]
            if len(out_of_range) > 0:
                issues.append(f"{len(out_of_range)} rows outside expected range [{lo},{hi}] for {col}")
    miss_rate = df.drop(columns=['fips','year'], errors='ignore').isna().mean()
    for col, rate in miss_rate.items():
        if rate > 0.40:
            issues.append(f"High missing rate: {col} is {rate:.0%} missing")
    dups = df['fips'].duplicated().sum()
    if dups > 0:
        issues.append(f"{dups} duplicate FIPS codes")
    return issues
