import hashlib
from datetime import date

import pandas as pd
import requests


API_URL = "https://api.census.gov/data/2022/acs/acs5"


def ingest() -> tuple[pd.DataFrame, dict]:
    params = {
        'get': 'NAME,B28002_001E,B28002_004E',
        'for': 'county:*',
    }
    resp = requests.get(API_URL, params=params)
    resp.raise_for_status()
    file_hash = hashlib.sha256(resp.content).hexdigest()

    data = resp.json()
    df = pd.DataFrame(data[1:], columns=data[0])

    df['fips'] = df['state'].str.zfill(2) + df['county'].str.zfill(3)
    df['B28002_001E'] = df['B28002_001E'].astype(float)
    df['B28002_004E'] = df['B28002_004E'].astype(float)
    df['broadband_rate'] = df['B28002_004E'] / df['B28002_001E']

    df = df[(df['broadband_rate'] >= 0.05) & (df['broadband_rate'] <= 1.0)]
    df = df[['fips', 'broadband_rate']].copy()
    df['year'] = 2022

    provenance = {
        'dataset_id': 'broadband',
        'source_name': 'Census ACS 5-Year (B28002)',
        'source_url': API_URL,
        'download_date': date.today().isoformat(),
        'file_hash': file_hash,
        'row_count': len(df),
        'counties_matched': df['fips'].nunique(),
        'notes': 'Broadband subscription rate from ACS table B28002',
    }

    return df, provenance
