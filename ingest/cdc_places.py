"""CDC PLACES health outcomes — obesity, diabetes, mental health, hypertension."""
import hashlib
from datetime import date

import pandas as pd
import requests

API_URL = "https://data.cdc.gov/resource/swc5-untb.json"

MEASURES = {
    'OBESITY': ('obesity_rate', 'obesity'),
    'DIABETES': ('diabetes_rate', 'diabetes'),
    'MHLTH': ('mental_health_rate', 'mental_health'),
    'BPHIGH': ('hypertension_rate', 'hypertension'),
}


def _fetch_measure(measure_id: str, col_name: str) -> pd.DataFrame:
    """Fetch one CDC PLACES measure, paginating through all results."""
    all_rows = []
    offset = 0
    page_size = 50000
    while True:
        params = {
            '$limit': page_size,
            '$offset': offset,
            'measureid': measure_id,
            'datavaluetypeid': 'CrdPrv',
        }
        resp = requests.get(API_URL, params=params)
        resp.raise_for_status()
        data = resp.json()
        if not data:
            break
        all_rows.extend(data)
        if len(data) < page_size:
            break
        offset += page_size

    df = pd.DataFrame(all_rows)
    df['fips'] = df['locationid'].astype(str).str.zfill(5)
    df[col_name] = pd.to_numeric(df['data_value'], errors='coerce')
    df = df[df['fips'].str.match(r'^\d{5}$')]
    df = df.dropna(subset=[col_name])
    # Filter to county-level (5-digit FIPS, not state-level 2-digit)
    df = df[df['fips'].str.len() == 5]
    return df[['fips', col_name]].drop_duplicates(subset='fips')


def ingest() -> tuple[pd.DataFrame, dict]:
    """Fetch all four CDC PLACES measures and return combined dataframe."""
    combined = None
    content_for_hash = b''

    for measure_id, (col_name, _) in MEASURES.items():
        resp = requests.get(API_URL, params={
            '$limit': 1, 'measureid': measure_id, 'datavaluetypeid': 'CrdPrv'
        })
        content_for_hash += resp.content

        df = _fetch_measure(measure_id, col_name)
        if combined is None:
            combined = df
        else:
            combined = combined.merge(df, on='fips', how='outer')

    file_hash = hashlib.sha256(content_for_hash).hexdigest()
    combined['year'] = 2022

    return combined, {
        'dataset_id': 'cdc_places',
        'source_name': 'CDC PLACES Health Outcomes',
        'source_url': API_URL,
        'download_date': date.today().isoformat(),
        'file_hash': file_hash,
        'row_count': len(combined),
        'counties_matched': combined['fips'].nunique(),
        'notes': 'Obesity, diabetes, mental health, hypertension prevalence from CDC PLACES',
    }
