import hashlib
from datetime import date

import pandas as pd
import requests


SOURCE_URL = "https://opportunityinsights.org/wp-content/uploads/2018/10/county_outcomes_simple.csv"


def ingest() -> tuple[pd.DataFrame, dict]:
    resp = requests.get(SOURCE_URL)
    resp.raise_for_status()
    file_hash = hashlib.sha256(resp.content).hexdigest()

    df = pd.read_csv(pd.io.common.StringIO(resp.text))

    # Construct 5-digit FIPS from state (2-digit) + county (3-digit) columns
    df['fips'] = (
        df['state'].astype(str).str.zfill(2)
        + df['county'].astype(str).str.zfill(3)
    )

    cols = {'fips': 'fips', 'kfr_pooled_pooled_p25': 'mobility_rank_p25'}
    if 'college_pooled_pooled_p25' in df.columns:
        cols['college_pooled_pooled_p25'] = 'college_rate'

    df = df[list(cols.keys())].rename(columns=cols)
    df['year'] = 2015

    provenance = {
        'dataset_id': 'mobility',
        'source_name': 'Opportunity Atlas',
        'source_url': SOURCE_URL,
        'download_date': date.today().isoformat(),
        'file_hash': file_hash,
        'row_count': len(df),
        'counties_matched': df['fips'].nunique(),
        'notes': 'County-level upward mobility outcomes from Opportunity Insights',
    }

    return df, provenance
