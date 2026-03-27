"""Ingest Census SAIPE poverty estimates — poverty rate and median household income."""
import hashlib
from datetime import date

import pandas as pd
import requests

API_URL = "https://api.census.gov/data/timeseries/poverty/saipe"


def ingest() -> tuple[pd.DataFrame, dict]:
    params = {
        'get': 'NAME,SAEPOVRTALL_PT,SAEMHI_PT',
        'for': 'county:*',
        'in': 'state:*',
        'time': '2022',
    }
    resp = requests.get(API_URL, params=params)
    resp.raise_for_status()
    file_hash = hashlib.sha256(resp.content).hexdigest()

    data = resp.json()
    df = pd.DataFrame(data[1:], columns=data[0])

    df['fips'] = df['state'].str.zfill(2) + df['county'].str.zfill(3)

    df['poverty_rate'] = pd.to_numeric(df['SAEPOVRTALL_PT'], errors='coerce')
    df['median_hh_income'] = pd.to_numeric(df['SAEMHI_PT'], errors='coerce')

    # Filter out nulls and obvious bad values
    df = df.dropna(subset=['poverty_rate', 'median_hh_income'])
    df = df[df['poverty_rate'].between(0, 100)]
    df = df[df['median_hh_income'] > 0]
    df = df[df['fips'].str.match(r'^\d{5}$')]

    df['year'] = 2022

    result = df[['fips', 'poverty_rate', 'median_hh_income', 'year']].copy()

    provenance = {
        'dataset_id': 'saipe',
        'source_name': 'Census SAIPE Poverty Estimates',
        'source_url': API_URL,
        'download_date': date.today().isoformat(),
        'file_hash': file_hash,
        'row_count': len(result),
        'counties_matched': result['fips'].nunique(),
        'notes': 'County-level poverty rate and median household income from Census SAIPE 2022',
    }

    return result, provenance
