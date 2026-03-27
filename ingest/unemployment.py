"""Unemployment rate from Census ACS table B23025 (employment status)."""
import hashlib
from datetime import date

import pandas as pd
import requests

API_URL = "https://api.census.gov/data/2022/acs/acs5"


def ingest() -> tuple[pd.DataFrame, dict]:
    params = {'get': 'NAME,B23025_003E,B23025_005E', 'for': 'county:*'}
    resp = requests.get(API_URL, params=params)
    resp.raise_for_status()
    file_hash = hashlib.sha256(resp.content).hexdigest()

    data = resp.json()
    df = pd.DataFrame(data[1:], columns=data[0])
    df['fips'] = df['state'].str.zfill(2) + df['county'].str.zfill(3)
    df['labor_force'] = pd.to_numeric(df['B23025_003E'], errors='coerce')
    df['unemployed'] = pd.to_numeric(df['B23025_005E'], errors='coerce')
    df = df.dropna(subset=['labor_force', 'unemployed'])
    df = df[df['labor_force'] > 0]
    df['unemployment_rate'] = df['unemployed'] / df['labor_force']
    df = df[df['unemployment_rate'].between(0, 1)]
    df['year'] = 2022

    result = df[['fips', 'unemployment_rate', 'year']].copy()

    return result, {
        'dataset_id': 'unemployment',
        'source_name': 'Census ACS 5-Year B23025 Employment Status',
        'source_url': API_URL,
        'download_date': date.today().isoformat(),
        'file_hash': file_hash,
        'row_count': len(result),
        'counties_matched': result['fips'].nunique(),
        'notes': 'Unemployment rate from ACS B23025 (BLS direct download blocked)',
    }
