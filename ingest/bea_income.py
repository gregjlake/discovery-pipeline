"""Per capita personal income from Census ACS table B19301."""
import hashlib
from datetime import date

import pandas as pd
import requests

API_URL = "https://api.census.gov/data/2022/acs/acs5"


def ingest() -> tuple[pd.DataFrame, dict]:
    params = {'get': 'NAME,B19301_001E', 'for': 'county:*'}
    resp = requests.get(API_URL, params=params)
    resp.raise_for_status()
    file_hash = hashlib.sha256(resp.content).hexdigest()

    data = resp.json()
    df = pd.DataFrame(data[1:], columns=data[0])
    df['fips'] = df['state'].str.zfill(2) + df['county'].str.zfill(3)
    df['per_capita_income'] = pd.to_numeric(df['B19301_001E'], errors='coerce')
    df = df.dropna(subset=['per_capita_income'])
    df = df[df['per_capita_income'] > 0]
    df['year'] = 2022

    result = df[['fips', 'per_capita_income', 'year']].copy()

    return result, {
        'dataset_id': 'bea_income',
        'source_name': 'Census ACS 5-Year B19301 Per Capita Income',
        'source_url': API_URL,
        'download_date': date.today().isoformat(),
        'file_hash': file_hash,
        'row_count': len(result),
        'counties_matched': result['fips'].nunique(),
        'notes': 'Per capita personal income from ACS table B19301',
    }
