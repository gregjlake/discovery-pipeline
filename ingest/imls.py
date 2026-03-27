import hashlib
import io
import zipfile
from datetime import date

import pandas as pd
import requests

SOURCE_URL = "https://www.imls.gov/sites/default/files/2024-06/pls_fy2022_csv.zip"


def ingest() -> tuple[pd.DataFrame, dict]:
    resp = requests.get(SOURCE_URL)
    resp.raise_for_status()
    file_hash = hashlib.sha256(resp.content).hexdigest()

    with zipfile.ZipFile(io.BytesIO(resp.content)) as zf:
        ae_file = [n for n in zf.namelist() if 'ae' in n.lower() and n.endswith('.csv')][0]
        with zf.open(ae_file) as f:
            df = pd.read_csv(f, encoding='latin-1')

    # Extract 5-digit county FIPS from CENTRACT (Census tract code: first 5 digits = county FIPS)
    df['fips'] = df['CENTRACT'].astype(str).str.zfill(11).str[:5]
    df = df[df['fips'].str.match(r'^\d{5}$')]

    for col in ['TOTOPEXP', 'POPU_UND']:
        df[col] = pd.to_numeric(df[col], errors='coerce')
        df.loc[df[col] < 0, col] = None

    county = df.groupby('fips').agg(
        TOTOPEXP=('TOTOPEXP', 'sum'),
        POPU_UND=('POPU_UND', 'sum'),
        n_libraries=('FSCSKEY', 'count'),
    ).reset_index()

    county['library_spend_per_capita'] = county['TOTOPEXP'] / county['POPU_UND']
    county['year'] = 2022

    result = county[['fips', 'library_spend_per_capita', 'n_libraries', 'year']].copy()

    provenance = {
        'dataset_id': 'library',
        'source_name': 'IMLS Public Libraries Survey FY2022',
        'source_url': SOURCE_URL,
        'download_date': date.today().isoformat(),
        'file_hash': file_hash,
        'row_count': len(result),
        'counties_matched': result['fips'].nunique(),
        'notes': 'County-level library spending per capita from PLS AE file',
    }

    return result, provenance
