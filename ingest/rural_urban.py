"""USDA Rural-Urban Continuum Codes 2023."""
import hashlib
from datetime import date

import pandas as pd
import requests

SOURCE_URL = "https://www.ers.usda.gov/media/5768/2023-rural-urban-continuum-codes.csv?v=21665"


def ingest() -> tuple[pd.DataFrame, dict]:
    resp = requests.get(SOURCE_URL)
    resp.raise_for_status()
    file_hash = hashlib.sha256(resp.content).hexdigest()

    df = pd.read_csv(pd.io.common.StringIO(resp.text), encoding='utf-8-sig')

    # Long-format CSV: filter to RUCC_2023 attribute rows
    rucc = df[df['Attribute'] == 'RUCC_2023'].copy()
    rucc['fips'] = rucc['FIPS'].astype(str).str.zfill(5)
    rucc['rural_urban_code'] = pd.to_numeric(rucc['Value'], errors='coerce')
    rucc = rucc.dropna(subset=['rural_urban_code'])
    rucc = rucc[rucc['fips'].str.match(r'^\d{5}$')]
    rucc = rucc[rucc['rural_urban_code'].between(1, 9)]
    rucc['year'] = 2023

    result = rucc[['fips', 'rural_urban_code', 'year']].copy()

    return result, {
        'dataset_id': 'rural_urban',
        'source_name': 'USDA Rural-Urban Continuum Codes 2023',
        'source_url': SOURCE_URL,
        'download_date': date.today().isoformat(),
        'file_hash': file_hash,
        'row_count': len(result),
        'counties_matched': result['fips'].nunique(),
        'notes': 'Rural-urban continuum code 1-9 (1=most urban, 9=most rural)',
    }
