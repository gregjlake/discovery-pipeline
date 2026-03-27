import hashlib
import io
import zipfile
from datetime import date

import pandas as pd
import requests

SOURCE_URL = "https://aqs.epa.gov/aqsweb/airdata/annual_aqi_by_county_2022.zip"
CENSUS_FIPS_URL = "https://www2.census.gov/geo/docs/reference/codes2020/national_county2020.txt"


def _load_fips_lookup() -> pd.DataFrame:
    """Load Census county FIPS crosswalk: state name + county name -> 5-digit FIPS."""
    resp = requests.get(CENSUS_FIPS_URL)
    resp.raise_for_status()
    fips_df = pd.read_csv(pd.io.common.StringIO(resp.text), sep='|', dtype=str)
    fips_df['fips'] = fips_df['STATEFP'] + fips_df['COUNTYFP']
    # Strip " County", " Parish", etc. for matching and lowercase
    fips_df['county_clean'] = (
        fips_df['COUNTYNAME']
        .str.replace(r'\s+(County|Parish|Borough|Census Area|Municipality|city|City and Borough)$',
                      '', regex=True)
        .str.strip()
        .str.lower()
    )
    from ingest.fips import STATE_FIPS_MAP
    inv_map = {v: k for k, v in STATE_FIPS_MAP.items()}
    fips_df['state_abbr'] = fips_df['STATEFP'].map(inv_map)
    return fips_df[['state_abbr', 'county_clean', 'fips']].dropna()


# Map full state names to abbreviations
_STATE_NAME_TO_ABBR = {
    'Alabama': 'AL', 'Alaska': 'AK', 'Arizona': 'AZ', 'Arkansas': 'AR',
    'California': 'CA', 'Colorado': 'CO', 'Connecticut': 'CT', 'Delaware': 'DE',
    'District of Columbia': 'DC', 'Florida': 'FL', 'Georgia': 'GA', 'Hawaii': 'HI',
    'Idaho': 'ID', 'Illinois': 'IL', 'Indiana': 'IN', 'Iowa': 'IA', 'Kansas': 'KS',
    'Kentucky': 'KY', 'Louisiana': 'LA', 'Maine': 'ME', 'Maryland': 'MD',
    'Massachusetts': 'MA', 'Michigan': 'MI', 'Minnesota': 'MN', 'Mississippi': 'MS',
    'Missouri': 'MO', 'Montana': 'MT', 'Nebraska': 'NE', 'Nevada': 'NV',
    'New Hampshire': 'NH', 'New Jersey': 'NJ', 'New Mexico': 'NM', 'New York': 'NY',
    'North Carolina': 'NC', 'North Dakota': 'ND', 'Ohio': 'OH', 'Oklahoma': 'OK',
    'Oregon': 'OR', 'Pennsylvania': 'PA', 'Rhode Island': 'RI', 'South Carolina': 'SC',
    'South Dakota': 'SD', 'Tennessee': 'TN', 'Texas': 'TX', 'Utah': 'UT',
    'Vermont': 'VT', 'Virginia': 'VA', 'Washington': 'WA', 'West Virginia': 'WV',
    'Wisconsin': 'WI', 'Wyoming': 'WY',
}


def ingest() -> tuple[pd.DataFrame, dict]:
    resp = requests.get(SOURCE_URL)
    resp.raise_for_status()
    file_hash = hashlib.sha256(resp.content).hexdigest()

    with zipfile.ZipFile(io.BytesIO(resp.content)) as zf:
        csv_file = [n for n in zf.namelist() if n.endswith('.csv')][0]
        with zf.open(csv_file) as f:
            df = pd.read_csv(f)

    # Build FIPS by joining EPA state+county names to Census FIPS crosswalk
    fips_lookup = _load_fips_lookup()

    df['state_abbr'] = df['State'].map(_STATE_NAME_TO_ABBR)
    df['county_clean'] = df['County'].str.strip().str.lower()

    df = df.merge(fips_lookup, on=['state_abbr', 'county_clean'], how='left')
    df = df.dropna(subset=['fips'])

    for col in ['Days with AQI', 'Good Days', 'Moderate Days', 'Median AQI']:
        df[col] = pd.to_numeric(df[col], errors='coerce')

    df = df[df['Days with AQI'] >= 50].copy()

    df['air_clean_score'] = (
        (df['Good Days'] + 0.5 * df['Moderate Days']) / df['Days with AQI']
    )
    df['air_quality_inv'] = 200 - df['Median AQI'].clip(0, 200)

    df['year'] = 2022

    result = df[['fips', 'air_clean_score', 'air_quality_inv', 'year']].copy()

    provenance = {
        'dataset_id': 'air',
        'source_name': 'EPA Air Quality Index Annual Summary',
        'source_url': SOURCE_URL,
        'download_date': date.today().isoformat(),
        'file_hash': file_hash,
        'row_count': len(result),
        'counties_matched': result['fips'].nunique(),
        'notes': 'County-level air quality metrics from EPA AQS annual AQI data',
    }

    return result, provenance
