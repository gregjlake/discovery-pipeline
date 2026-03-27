"""Housing cost burden from Census ACS table B25070 (gross rent as % of income)."""
import hashlib
from datetime import date

import pandas as pd
import requests

API_URL = "https://api.census.gov/data/2022/acs/acs5"


def ingest() -> tuple[pd.DataFrame, dict]:
    params = {
        'get': 'NAME,B25070_007E,B25070_008E,B25070_009E,B25070_010E,B25070_001E',
        'for': 'county:*',
    }
    resp = requests.get(API_URL, params=params)
    resp.raise_for_status()
    file_hash = hashlib.sha256(resp.content).hexdigest()

    data = resp.json()
    df = pd.DataFrame(data[1:], columns=data[0])
    df['fips'] = df['state'].str.zfill(2) + df['county'].str.zfill(3)

    for col in ['B25070_007E', 'B25070_008E', 'B25070_009E', 'B25070_010E', 'B25070_001E']:
        df[col] = pd.to_numeric(df[col], errors='coerce')

    df['cost_burdened'] = df['B25070_007E'] + df['B25070_008E'] + df['B25070_009E'] + df['B25070_010E']
    df = df.dropna(subset=['cost_burdened', 'B25070_001E'])
    df = df[df['B25070_001E'] > 0]
    df['housing_burden_rate'] = df['cost_burdened'] / df['B25070_001E']
    df = df[df['housing_burden_rate'].between(0, 1)]
    df['year'] = 2022

    result = df[['fips', 'housing_burden_rate', 'year']].copy()

    return result, {
        'dataset_id': 'housing_burden',
        'source_name': 'Census ACS 5-Year B25070 Gross Rent Burden',
        'source_url': API_URL,
        'download_date': date.today().isoformat(),
        'file_hash': file_hash,
        'row_count': len(result),
        'counties_matched': result['fips'].nunique(),
        'notes': 'Share of renters paying 30%+ of income on rent',
    }
