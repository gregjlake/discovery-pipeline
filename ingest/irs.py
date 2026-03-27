"""Ingest IRS Statistics of Income — EITC rate by county via Census ZCTA-county crosswalk."""
import hashlib
from datetime import date

import pandas as pd
import requests

SOI_URL = "https://www.irs.gov/pub/irs-soi/22zpallnoagi.csv"
ZCTA_COUNTY_URL = "https://www2.census.gov/geo/docs/maps-data/data/rel2020/zcta520/tab20_zcta520_county20_natl.txt"


def _load_zcta_county_xwalk() -> pd.DataFrame:
    """Load Census ZCTA-to-county crosswalk based on land area overlap."""
    resp = requests.get(ZCTA_COUNTY_URL, timeout=60)
    resp.raise_for_status()
    df = pd.read_csv(pd.io.common.StringIO(resp.text), sep='|', dtype=str,
                     encoding='utf-8-sig')
    df = df[['GEOID_ZCTA5_20', 'GEOID_COUNTY_20', 'AREALAND_PART']].copy()
    df.columns = ['zcta', 'fips', 'area']
    df = df.dropna(subset=['zcta', 'fips'])
    df['zcta'] = df['zcta'].str.strip().str.zfill(5)
    df['fips'] = df['fips'].str.strip().str.zfill(5)
    df['area'] = pd.to_numeric(df['area'], errors='coerce').fillna(0)
    # Compute weight as fraction of ZCTA area in each county
    zcta_total = df.groupby('zcta')['area'].transform('sum')
    df['weight'] = df['area'] / zcta_total.replace(0, 1)
    return df[['zcta', 'fips', 'weight']]


def ingest() -> tuple[pd.DataFrame, dict]:
    resp = requests.get(SOI_URL)
    resp.raise_for_status()
    file_hash = hashlib.sha256(resp.content).hexdigest()

    soi = pd.read_csv(pd.io.common.StringIO(resp.text))

    # Find columns (case-insensitive)
    col_map = {}
    for c in soi.columns:
        cl = c.lower().strip()
        if cl in ('zipcode', 'zip_code', 'zip'):
            col_map['zip'] = c
        elif cl == 'n1':
            col_map['total_returns'] = c
        elif cl == 'n59660':
            col_map['eitc_returns'] = c

    if not all(k in col_map for k in ['zip', 'total_returns', 'eitc_returns']):
        raise ValueError(f"Missing required columns. Found: {list(soi.columns)}")

    soi = soi.rename(columns={col_map['zip']: 'zcta',
                               col_map['total_returns']: 'total_returns',
                               col_map['eitc_returns']: 'eitc_returns'})
    soi['zcta'] = soi['zcta'].astype(str).str.zfill(5)
    soi['total_returns'] = pd.to_numeric(soi['total_returns'], errors='coerce')
    soi['eitc_returns'] = pd.to_numeric(soi['eitc_returns'], errors='coerce')

    # Filter out aggregation rows
    soi = soi[soi['zcta'].str.match(r'^\d{5}$')]
    soi = soi[~soi['zcta'].isin(['00000', '99999'])]
    soi = soi.dropna(subset=['total_returns', 'eitc_returns'])

    # Load crosswalk and allocate ZIP returns to counties by area weight
    xwalk = _load_zcta_county_xwalk()
    merged = soi.merge(xwalk, on='zcta', how='inner')
    merged['w_total'] = merged['total_returns'] * merged['weight']
    merged['w_eitc'] = merged['eitc_returns'] * merged['weight']

    county = merged.groupby('fips').agg(
        total_returns=('w_total', 'sum'),
        eitc_returns=('w_eitc', 'sum'),
    ).reset_index()

    county['eitc_rate'] = county['eitc_returns'] / county['total_returns']
    county = county[county['eitc_rate'].between(0, 1)]
    county = county[county['fips'].str.match(r'^\d{5}$')]
    county['year'] = 2022

    result = county[['fips', 'eitc_rate', 'year']].copy()

    provenance = {
        'dataset_id': 'eitc',
        'source_name': 'IRS Statistics of Income — EITC Returns',
        'source_url': SOI_URL,
        'download_date': date.today().isoformat(),
        'file_hash': file_hash,
        'row_count': len(result),
        'counties_matched': result['fips'].nunique(),
        'notes': 'EITC filing rate as poverty proxy, ZIP-to-county via Census ZCTA crosswalk',
    }

    return result, provenance
