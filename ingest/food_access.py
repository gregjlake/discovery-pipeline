"""SNAP/food stamp receipt rate as food access proxy from Census ACS B22010."""
import hashlib
from datetime import date

import pandas as pd
import requests

API_URL = "https://api.census.gov/data/2022/acs/acs5"


def ingest() -> tuple[pd.DataFrame, dict]:
    params = {'get': 'NAME,B22010_001E,B22010_002E', 'for': 'county:*'}
    resp = requests.get(API_URL, params=params)
    resp.raise_for_status()
    file_hash = hashlib.sha256(resp.content).hexdigest()

    data = resp.json()
    df = pd.DataFrame(data[1:], columns=data[0])
    df['fips'] = df['state'].str.zfill(2) + df['county'].str.zfill(3)
    df['total_hh'] = pd.to_numeric(df['B22010_001E'], errors='coerce')
    df['snap_hh'] = pd.to_numeric(df['B22010_002E'], errors='coerce')
    df = df.dropna(subset=['total_hh', 'snap_hh'])
    df = df[df['total_hh'] > 0]
    df['snap_rate'] = df['snap_hh'] / df['total_hh']
    df = df[df['snap_rate'].between(0, 1)]
    df['year'] = 2022

    result = df[['fips', 'snap_rate', 'year']].copy()

    return result, {
        'dataset_id': 'food_access',
        'source_name': 'Census ACS 5-Year B22010 SNAP Receipt',
        'source_url': API_URL,
        'download_date': date.today().isoformat(),
        'file_hash': file_hash,
        'row_count': len(result),
        'counties_matched': result['fips'].nunique(),
        'notes': 'SNAP/food stamp household rate as food access proxy (USDA atlas unavailable)',
    }
