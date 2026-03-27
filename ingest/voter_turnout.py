"""County-level presidential election turnout from MIT Election Lab."""
import hashlib
from datetime import date

import pandas as pd
import requests

SOURCE_URL = "https://dataverse.harvard.edu/api/access/datafile/4819117"


def ingest() -> tuple[pd.DataFrame, dict]:
    resp = requests.get(SOURCE_URL)
    resp.raise_for_status()
    file_hash = hashlib.sha256(resp.content).hexdigest()

    df = pd.read_csv(pd.io.common.StringIO(resp.text), sep='\t')

    # Filter to 2020 presidential race
    df = df[df['year'] == 2020]
    df = df[df['office'].isin(['PRESIDENT', 'US PRESIDENT'])]

    df = df.dropna(subset=['county_fips'])
    df['fips'] = df['county_fips'].astype(float).astype('Int64').astype(str).str.zfill(5)
    df['totalvotes'] = pd.to_numeric(df['totalvotes'], errors='coerce')

    # Get total votes per county (totalvotes is the same for all candidates in a county)
    county_votes = df.groupby('fips').agg(
        totalvotes=('totalvotes', 'max'),
    ).reset_index()

    county_votes = county_votes[county_votes['fips'].str.match(r'^\d{5}$')]
    county_votes = county_votes[county_votes['totalvotes'] > 0]
    county_votes = county_votes.dropna(subset=['totalvotes'])

    county_votes['total_votes_2020'] = county_votes['totalvotes'].astype(float)
    county_votes['year'] = 2020

    result = county_votes[['fips', 'total_votes_2020', 'year']].copy()

    return result, {
        'dataset_id': 'voter_turnout',
        'source_name': 'MIT Election Lab County Presidential Returns',
        'source_url': SOURCE_URL,
        'download_date': date.today().isoformat(),
        'file_hash': file_hash,
        'row_count': len(result),
        'counties_matched': result['fips'].nunique(),
        'notes': 'Total votes cast in 2020 presidential election by county',
    }
