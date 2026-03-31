import json
import logging
import os
import uuid
from pathlib import Path

import numpy as np
import pandas as pd
from dotenv import load_dotenv
from fastapi import APIRouter, HTTPException

from api.schemas import ScatterRequest, ScatterResponse, AskRequest, AskResponse
from normalize.methods import NORM_FUNCTIONS
from normalize.outliers import OUTLIER_FUNCTIONS

load_dotenv(Path(__file__).resolve().parent.parent / '.env', override=False)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("api.routes")

router = APIRouter()

DATA_DIR = Path(__file__).resolve().parent.parent / 'data'

# State FIPS -> region lookup
_REGION_BY_STATE_FIPS = {}
for _fips_list, _region in [
    ('09,23,25,33,34,36,42,44,50', 'Northeast'),
    ('01,05,10,11,12,13,21,22,24,28,37,40,45,47,48,51,54', 'South'),
    ('17,18,19,20,26,27,29,31,38,39,46,55', 'Midwest'),
    ('02,04,06,08,15,16,30,32,35,41,49,53,56', 'West'),
]:
    for _f in _fips_list.split(','):
        _REGION_BY_STATE_FIPS[_f] = _region


def _region_from_fips(fips: str) -> str:
    return _REGION_BY_STATE_FIPS.get(fips[:2], '')


# Dataset registry: dataset_id -> (value_column, description)
DATASET_REGISTRY = {
    'library':        ('library_spend_per_capita', 'Library spending per capita ($)'),
    'mobility':       ('mobility_rank_p25',        'Upward mobility rank (p25)'),
    'air':            ('air_quality_inv',          'Air quality index (inverted, higher=better)'),
    'broadband':      ('broadband_rate',           'Broadband subscription rate'),
    'eitc':           ('eitc_rate',                'EITC filing rate (poverty proxy)'),
    'poverty':        ('poverty_rate',             'Poverty rate (%)'),
    'median_income':  ('median_hh_income',         'Median household income ($)'),
    'bea_income':     ('per_capita_income',        'ACS per capita income ($/year)'),
    'food_access':    ('snap_rate',                'SNAP participation rate (proxy)'),
    'obesity':        ('obesity_rate',             'Adult obesity prevalence (%)'),
    'diabetes':       ('diabetes_rate',            'Adult diabetes prevalence (%)'),
    'mental_health':  ('mental_health_rate',       'Poor mental health days (%)'),
    'hypertension':   ('hypertension_rate',        'High blood pressure prevalence (%)'),
    'unemployment':   ('unemployment_rate',        'Unemployment rate'),
    'rural_urban':    ('rural_urban_code',         'Rural-urban continuum code (1-9)'),
    'housing_burden': ('housing_burden_rate',      'Cost-burdened renters (30%+ income)'),
    'voter_turnout':  ('total_votes_2020',         'Total votes cast 2020 presidential'),
    'broadband_avail': ('internet_access_rate',     'Internet access rate (any type)'),
    'pop_density':    ('pop_density',               'Population density (people/sq mi)'),
}


def _get_supabase():
    """Return Supabase client or None."""
    url = os.environ.get('SUPABASE_URL')
    key = os.environ.get('SUPABASE_SERVICE_KEY')
    if not url or not key:
        return None
    try:
        from supabase import create_client
        return create_client(url, key)
    except Exception as e:
        logger.warning(f"Could not create Supabase client: {e}")
        return None


def _load_dataset_from_supabase(dataset_id: str) -> pd.DataFrame | None:
    """Load dataset from Supabase raw_values table. Returns None on failure."""
    sb = _get_supabase()
    if sb is None:
        return None
    try:
        col = DATASET_REGISTRY[dataset_id][0]
        # Paginate to get all rows (Supabase default limit is 1000)
        all_rows = []
        page_size = 1000
        offset = 0
        while True:
            resp = sb.table('raw_values') \
                .select('fips,value,year,column_name') \
                .eq('dataset_id', dataset_id) \
                .eq('column_name', col) \
                .range(offset, offset + page_size - 1) \
                .execute()
            if not resp.data:
                break
            all_rows.extend(resp.data)
            if len(resp.data) < page_size:
                break
            offset += page_size

        if not all_rows:
            return None
        df = pd.DataFrame(all_rows)
        df = df.rename(columns={'value': col})
        df = df[['fips', col, 'year']]
        logger.info(f"Loaded {dataset_id} from Supabase: {len(df)} rows")
        return df
    except Exception as e:
        logger.warning(f"Supabase read failed for {dataset_id}: {e}")
        return None


def _load_dataset_from_parquet(dataset_id: str) -> pd.DataFrame:
    """Load dataset from local parquet fallback."""
    path = DATA_DIR / f'{dataset_id}.parquet'
    if not path.exists():
        raise HTTPException(404, f"Dataset '{dataset_id}' not found (no Supabase, no parquet)")
    logger.info(f"Falling back to parquet for {dataset_id}")
    return pd.read_parquet(path)


def _load_dataset(dataset_id: str) -> pd.DataFrame:
    """Load dataset: try Supabase first, fall back to parquet."""
    df = _load_dataset_from_supabase(dataset_id)
    if df is not None and len(df) > 0:
        return df
    return _load_dataset_from_parquet(dataset_id)


def _load_provenance_from_supabase(dataset_id: str) -> dict | None:
    """Load latest provenance record from Supabase."""
    sb = _get_supabase()
    if sb is None:
        return None
    try:
        resp = sb.table('provenance') \
            .select('*') \
            .eq('dataset_id', dataset_id) \
            .order('created_at', desc=True) \
            .limit(1) \
            .execute()
        if resp.data:
            return resp.data[0]
        return None
    except Exception as e:
        logger.warning(f"Supabase provenance read failed for {dataset_id}: {e}")
        return None


def _load_provenance(dataset_id: str) -> dict:
    """Load provenance: try Supabase first, fall back to local JSON."""
    prov = _load_provenance_from_supabase(dataset_id)
    if prov is not None:
        return prov
    path = DATA_DIR / f'{dataset_id}_provenance.json'
    if not path.exists():
        raise HTTPException(404, f"Provenance for '{dataset_id}' not found")
    logger.info(f"Falling back to local provenance JSON for {dataset_id}")
    with open(path) as f:
        return json.load(f)


# ── GET /health ───────────────────────────────────────────────
@router.get('/health')
def health():
    supabase_url = os.environ.get('SUPABASE_URL', '')
    supabase_key = os.environ.get('SUPABASE_SERVICE_KEY', '')
    masked_url = supabase_url[:20] + '...' if len(supabase_url) > 20 else supabase_url or '(not set)'
    masked_key = supabase_key[:20] + '...' if len(supabase_key) > 20 else ('(not set)' if not supabase_key else '(short)')

    result = {
        'status': 'ok',
        'supabase_url': masked_url,
        'supabase_url_length': len(supabase_url),
        'supabase_key_preview': masked_key,
        'supabase_key_length': len(supabase_key),
        'supabase_client': False,
        'raw_values_count': None,
        'parquet_fallback_available': {},
        'dotenv_path': str(Path(__file__).resolve().parent.parent / '.env'),
        'dotenv_exists': (Path(__file__).resolve().parent.parent / '.env').exists(),
        'data_dir': str(DATA_DIR),
        'data_dir_exists': DATA_DIR.exists(),
        'errors': [],
    }

    # Check parquet files
    for ds_id in DATASET_REGISTRY:
        path = DATA_DIR / f'{ds_id}.parquet'
        result['parquet_fallback_available'][ds_id] = path.exists()

    # Try Supabase connection
    try:
        sb = _get_supabase()
        if sb is None:
            result['errors'].append(f'Supabase client returned None (url_set={bool(supabase_url)}, key_set={bool(supabase_key)})')
        else:
            result['supabase_client'] = True
            try:
                resp = sb.table('raw_values').select('id', count='exact').limit(1).execute()
                result['raw_values_count'] = resp.count
            except Exception as e:
                result['errors'].append(f'raw_values query failed: {e}')
    except Exception as e:
        result['errors'].append(f'Supabase init error: {e}')

    return result


# ── GET /benchmarks ────────────────────────────────────────────
@router.get('/benchmarks')
def benchmarks():
    from validate.benchmarks import run_benchmarks
    return run_benchmarks(_load_dataset)


# ── Unit labels per dataset ───────────────────────────────────
_DATASET_UNITS = {
    'library':        '$/capita/yr',
    'mobility':       'rank (0–1)',
    'air':            'AQI inv.',
    'broadband':      'rate (0–1)',
    'eitc':           'rate (0–1)',
    'poverty':        '%',
    'median_income':  '$',
    'bea_income':     '$/person/yr',
    'food_access':    '% households',
    'obesity':        '% adults',
    'diabetes':       '% adults',
    'mental_health':  '% adults',
    'hypertension':   '% adults',
    'unemployment':   '% unemployed',
    'rural_urban':    'code 1–9',
    'housing_burden': '% cost-burdened',
    'voter_turnout':  'total votes',
    'broadband_avail': '% with internet',
    'pop_density':    'people/sq mi',
}


def _load_all_datasets_cached() -> dict[str, pd.DataFrame]:
    """Load every registered dataset. Returns {dataset_id: DataFrame}."""
    cache: dict[str, pd.DataFrame] = {}
    for ds_id in DATASET_REGISTRY:
        try:
            cache[ds_id] = _load_dataset(ds_id)
        except Exception:
            pass
    return cache


# ── GET /county/{fips} ────────────────────────────────────────
@router.get('/county/{fips}')
def county_detail(fips: str):
    if not fips or len(fips) != 5 or not fips.isdigit():
        raise HTTPException(400, "FIPS must be a 5-digit string")

    all_data = _load_all_datasets_cached()
    region = _region_from_fips(fips)

    # Build per-dataset stats for this county
    datasets_out: dict[str, dict] = {}
    county_zscores: dict[str, float] = {}  # for similarity calc

    for ds_id, (col, _desc) in DATASET_REGISTRY.items():
        df = all_data.get(ds_id)
        if df is None or col not in df.columns:
            continue

        vals = df[col].dropna()
        row = df[df['fips'] == fips]
        if row.empty:
            continue

        raw_value = float(row.iloc[0][col])
        mean = float(vals.mean())
        std = float(vals.std())
        z = (raw_value - mean) / std if std > 0 else 0.0
        pct = float((vals < raw_value).sum() + (vals == raw_value).sum() * 0.5) / len(vals) * 100

        datasets_out[ds_id] = {
            'raw_value': round(raw_value, 4),
            'unit': _DATASET_UNITS.get(ds_id, ''),
            'national_percentile': round(pct, 1),
            'national_mean': round(mean, 4),
            'national_std': round(std, 4),
            'z_score': round(z, 4),
        }
        county_zscores[ds_id] = z

    if not datasets_out:
        raise HTTPException(404, f"No data found for FIPS {fips}")

    # ── Similar counties ──────────────────────────────────────
    # Build z-score matrix for all counties across shared datasets
    shared_ds = list(county_zscores.keys())
    min_shared = min(4, len(shared_ds))

    # Pivot: fips -> {ds_id: z_score}
    county_vectors: dict[str, dict[str, float]] = {}
    for ds_id in shared_ds:
        df = all_data.get(ds_id)
        if df is None:
            continue
        col = DATASET_REGISTRY[ds_id][0]
        vals = df[col].dropna()
        mean = float(vals.mean())
        std = float(vals.std())
        if std == 0:
            continue
        for _, r in df[['fips', col]].dropna().iterrows():
            f = r['fips']
            if f == fips:
                continue
            if f not in county_vectors:
                county_vectors[f] = {}
            county_vectors[f][ds_id] = (float(r[col]) - mean) / std

    # Filter to counties with enough shared datasets, compute distance
    distances: list[tuple[str, float]] = []
    for other_fips, other_z in county_vectors.items():
        common = [d for d in shared_ds if d in other_z]
        if len(common) < min_shared:
            continue
        dist_sq = sum((county_zscores[d] - other_z[d]) ** 2 for d in common)
        distances.append((other_fips, dist_sq ** 0.5))

    distances.sort(key=lambda x: x[1])
    top5 = distances[:5]
    max_dist = max(d for _, d in top5) if top5 else 1.0
    max_dist = max(max_dist, 0.001)

    similar_counties = []
    for other_fips, dist in top5:
        score = round(max(0, 100 - (dist / (max_dist * 1.2) * 100)))
        similar_counties.append({
            'fips': other_fips,
            'name': '',
            'state': other_fips[:2],
            'similarity_score': score,
            'region': _region_from_fips(other_fips),
        })

    return {
        'fips': fips,
        'name': '',
        'state': fips[:2],
        'region': region,
        'datasets': datasets_out,
        'similar_counties': similar_counties,
    }


# ── GET /county/{fips}/flags ──────────────────────────────────
@router.get('/county/{fips}/flags')
def county_flags(
    fips: str,
    x: str,
    y: str,
    slope: float,
    intercept: float,
    residual_std: float,
    residual: float,
):
    # Load county detail (reuse the endpoint logic)
    county_data = county_detail(fips)

    flags = []
    px = county_data['datasets'].get(x, {}).get('national_percentile', 50)
    py = county_data['datasets'].get(y, {}).get('national_percentile', 50)

    x_label = DATASET_REGISTRY.get(x, (x, x))[1]
    y_label = DATASET_REGISTRY.get(y, (y, y))[1]

    # Rule 1 — Strong outlier
    if residual_std > 0 and abs(residual) > 2.0 * residual_std:
        sigma = round(abs(residual) / residual_std, 1)
        direction = 'above' if residual > 0 else 'below'
        flags.append({
            'headline': f'Strong outlier — {sigma}σ {direction} trend',
            'description': f'This county breaks the {x_label} vs {y_label} pattern more than 95% of counties. Something unusual is happening here.',
            'type': 'outlier',
            'datasets_involved': [x, y],
            'generated_by': 'rules_engine',
        })

    # Rule 2 — High on both
    if px > 75 and py > 75:
        flags.append({
            'headline': 'Top quartile on both dimensions',
            'description': f'Ranks above 75th percentile for both {x_label} and {y_label} — part of a high-performing cluster.',
            'type': 'pattern',
            'datasets_involved': [x, y],
            'generated_by': 'rules_engine',
        })

    # Rule 3 — Low on both
    if px < 25 and py < 25:
        flags.append({
            'headline': 'Bottom quartile on both dimensions',
            'description': f'Ranks below 25th percentile for both {x_label} and {y_label} — part of a cluster worth studying.',
            'type': 'pattern',
            'datasets_involved': [x, y],
            'generated_by': 'rules_engine',
        })

    # Rule 4 — High X but unexpectedly low Y
    if px > 70 and residual_std > 0 and residual < -1.5 * residual_std:
        flags.append({
            'headline': f'High {x_label} but lower {y_label} than expected',
            'description': f'Despite ranking in the top 30% for {x_label}, this county underperforms on {y_label}. A confounding variable may explain this gap.',
            'type': 'pattern',
            'datasets_involved': [x, y],
            'generated_by': 'rules_engine',
        })

    # Rule 5 — Low X but high Y
    if px < 30 and residual_std > 0 and residual > 1.5 * residual_std:
        flags.append({
            'headline': f'Outperforms despite low {x_label}',
            'description': f'Achieves above-expected {y_label} despite low {x_label}. What distinguishes this county from similar ones?',
            'type': 'outlier',
            'datasets_involved': [x, y],
            'generated_by': 'rules_engine',
        })

    # Rule 6 — Extreme values across any dataset
    for ds_id, ds_data in county_data['datasets'].items():
        p = ds_data.get('national_percentile', 50)
        if p > 95:
            flags.append({
                'headline': f'Extreme value: top 5% for {ds_id}',
                'description': f'Ranks in the top 5% nationally for {ds_id} — raw value: {ds_data["raw_value"]} {ds_data["unit"]}',
                'type': 'extreme',
                'datasets_involved': [ds_id],
                'generated_by': 'rules_engine',
            })
        elif p < 5:
            flags.append({
                'headline': f'Extreme value: bottom 5% for {ds_id}',
                'description': f'Ranks in the bottom 5% nationally for {ds_id} — raw value: {ds_data["raw_value"]} {ds_data["unit"]}',
                'type': 'extreme',
                'datasets_involved': [ds_id],
                'generated_by': 'rules_engine',
            })

    return {
        'fips': fips,
        'flags': flags,
        'flag_count': len(flags),
        'generated_by': 'rules_engine',
        'note': 'All flags generated from statistical thresholds — no AI involved',
    }


# ── GET /datasets ──────────────────────────────────────────────
@router.get('/datasets')
def list_datasets():
    results = []
    errors = []
    for ds_id, (col, desc) in DATASET_REGISTRY.items():
        try:
            df = _load_dataset(ds_id)
            results.append({
                'dataset_id': ds_id,
                'value_column': col,
                'description': desc,
                'county_count': int(df['fips'].nunique()),
                'row_count': len(df),
            })
        except Exception as e:
            logger.error(f"Failed to load dataset {ds_id}: {e}")
            errors.append(f"{ds_id}: {e}")
    if not results and errors:
        logger.error(f"All datasets failed: {errors}")
    return results


# ── POST /scatter ──────────────────────────────────────────────
@router.post('/scatter', response_model=ScatterResponse)
def scatter(req: ScatterRequest):
    if req.dataset_x not in DATASET_REGISTRY:
        raise HTTPException(400, f"Unknown dataset_x: {req.dataset_x}")
    if req.dataset_y not in DATASET_REGISTRY:
        raise HTTPException(400, f"Unknown dataset_y: {req.dataset_y}")
    if req.norm_method not in NORM_FUNCTIONS:
        raise HTTPException(400, f"Unknown norm_method: {req.norm_method}")
    if req.outlier_method not in OUTLIER_FUNCTIONS:
        raise HTTPException(400, f"Unknown outlier_method: {req.outlier_method}")

    col_x = DATASET_REGISTRY[req.dataset_x][0]
    col_y = DATASET_REGISTRY[req.dataset_y][0]

    df_x = _load_dataset(req.dataset_x)[['fips', col_x]].rename(columns={col_x: 'raw_x'})
    df_y = _load_dataset(req.dataset_y)[['fips', col_y]].rename(columns={col_y: 'raw_y'})

    merged = df_x.merge(df_y, on='fips', how='inner').dropna(subset=['raw_x', 'raw_y'])

    # Normalize
    norm_fn = NORM_FUNCTIONS[req.norm_method]
    merged['x'] = norm_fn(merged['raw_x'])
    merged['y'] = norm_fn(merged['raw_y'])

    # Drop any NaN/inf produced by normalization
    merged = merged.replace([np.inf, -np.inf], np.nan).dropna(subset=['x', 'y'])

    # Outlier treatment
    outlier_fn = OUTLIER_FUNCTIONS[req.outlier_method]
    merged = outlier_fn(merged)

    if len(merged) < 3:
        raise HTTPException(400, "Too few data points after filtering")

    # Population weight (use broadband total_hh as proxy if available)
    weights = None
    if req.weight_method == 'popweight':
        try:
            pop_df = _load_dataset('broadband')[['fips']].copy()
            # broadband doesn't have total_hh, use count as equal proxy
            # For real pop weighting we'd need a population dataset
            pop_df['pop'] = 1.0
            merged = merged.merge(pop_df, on='fips', how='left')
            merged['pop'] = merged['pop'].fillna(1.0)
            weights = merged['pop'].values
        except Exception:
            weights = None

    # Pearson r
    if weights is not None:
        # Weighted correlation
        w = weights / weights.sum()
        mx = np.average(merged['x'], weights=w)
        my = np.average(merged['y'], weights=w)
        cov = np.sum(w * (merged['x'] - mx) * (merged['y'] - my))
        sx = np.sqrt(np.sum(w * (merged['x'] - mx) ** 2))
        sy = np.sqrt(np.sum(w * (merged['y'] - my) ** 2))
        r = float(cov / (sx * sy)) if sx > 0 and sy > 0 else 0.0
    else:
        r = float(merged['x'].corr(merged['y']))

    # Residuals from OLS: y = a + b*x
    b = merged['x'].cov(merged['y']) / merged['x'].var() if merged['x'].var() > 0 else 0
    a = merged['y'].mean() - b * merged['x'].mean()
    merged['residual'] = merged['y'] - (a + b * merged['x'])

    # Build points
    points = []
    for _, row in merged.iterrows():
        fips = row['fips']
        points.append({
            'fips': fips,
            'name': '',
            'region': _region_from_fips(fips),
            'x': round(float(row['x']), 6),
            'y': round(float(row['y']), 6),
            'raw_x': round(float(row['raw_x']), 6),
            'raw_y': round(float(row['raw_y']), 6),
            'pop': float(row['pop']) if 'pop' in row.index else None,
            'residual': round(float(row['residual']), 6),
        })

    return ScatterResponse(
        query_id=str(uuid.uuid4()),
        r=round(r, 6),
        n=len(merged),
        r_squared=round(r ** 2, 6),
        points=points,
        config=req,
    )


# ── POST /robustness ──────────────────────────────────────────
@router.post('/robustness')
def robustness(req: ScatterRequest):
    if req.dataset_x not in DATASET_REGISTRY:
        raise HTTPException(400, f"Unknown dataset_x: {req.dataset_x}")
    if req.dataset_y not in DATASET_REGISTRY:
        raise HTTPException(400, f"Unknown dataset_y: {req.dataset_y}")

    col_x = DATASET_REGISTRY[req.dataset_x][0]
    col_y = DATASET_REGISTRY[req.dataset_y][0]

    df_x = _load_dataset(req.dataset_x)[['fips', col_x]].rename(columns={col_x: 'raw_x'})
    df_y = _load_dataset(req.dataset_y)[['fips', col_y]].rename(columns={col_y: 'raw_y'})
    base = df_x.merge(df_y, on='fips', how='inner').dropna(subset=['raw_x', 'raw_y'])

    results = []
    for nm_name, norm_fn in NORM_FUNCTIONS.items():
        for om_name, outlier_fn in OUTLIER_FUNCTIONS.items():
            df = base.copy()
            df['x'] = norm_fn(df['raw_x'])
            df['y'] = norm_fn(df['raw_y'])
            df = df.replace([np.inf, -np.inf], np.nan).dropna(subset=['x', 'y'])
            df = outlier_fn(df)
            if len(df) >= 3:
                r = float(df['x'].corr(df['y']))
            else:
                r = None
            results.append({
                'nm': nm_name,
                'om': om_name,
                'r': round(r, 6) if r is not None else None,
                'n': len(df),
            })

    return results


# ── GET /provenance/{dataset_id} ──────────────────────────────
@router.get('/provenance/{dataset_id}')
def provenance(dataset_id: str):
    if dataset_id not in DATASET_REGISTRY:
        raise HTTPException(404, f"Unknown dataset: {dataset_id}")

    prov = _load_provenance(dataset_id)
    df = _load_dataset(dataset_id)
    col = DATASET_REGISTRY[dataset_id][0]

    val_col = df[col] if col in df.columns else pd.Series(dtype=float)

    return {
        **prov,
        'value_column': col,
        'raw_min': round(float(val_col.min()), 4) if len(val_col) > 0 else None,
        'raw_max': round(float(val_col.max()), 4) if len(val_col) > 0 else None,
        'raw_mean': round(float(val_col.mean()), 4) if len(val_col) > 0 else None,
        'missing_values': int(val_col.isna().sum()),
    }


# ── POST /ask ─────────────────────────────────────────────────
SYSTEM_PROMPT = """You are a query parser for a scientific data tool. The user is looking at a scatter plot of US county data. Your only job is to classify their question and extract parameters. Return only valid JSON matching one of these query types. Never answer the question yourself. Never generate data. Only parse the intent and return structured parameters. If uncertain, return type: conceptual.

Query types:

1. filter — Filter counties by criteria
   {"type": "filter", "params": {"region": "South"|"Northeast"|"Midwest"|"West"|null, "x_percentile_min": 0-100|null, "x_percentile_max": 0-100|null, "y_percentile_min": 0-100|null, "y_percentile_max": 0-100|null}}
   Use this when: user wants to see a subset of counties (by region, by value range, by quadrant)

2. aggregate — Group statistics
   {"type": "aggregate", "params": {"group_by": "region"|"state", "metric": "mean"|"median"|"pearson_r", "dataset": "x"|"y"|"both"}}
   Use this when: user asks about averages, comparisons between groups, which group is highest/strongest

3. compare_cohort — Compare specific counties
   {"type": "compare_cohort", "params": {"cohort": "outliers"|"top_quartile"|"bottom_quartile"|"selected"}}
   Use this when: user asks what outliers/top/bottom counties have in common

4. rank — Show top/bottom counties
   {"type": "rank", "params": {"dataset": "x"|"y", "direction": "top"|"bottom", "n": 10}}
   Use this when: user asks for top/bottom N, best/worst, highest/lowest

5. conceptual — Cannot answer from current data
   {"type": "conceptual", "params": {"reason": "brief explanation", "related_questions": ["question 1 that CAN be answered", "question 2", "question 3"]}}
   Use this when: question requires data not in the scatter, asks about causation, or needs external info

Return ONLY the JSON object, no other text."""


@router.post('/ask', response_model=AskResponse)
async def ask(req: AskRequest):
    ds_labels = {k: v[1] for k, v in DATASET_REGISTRY.items()}
    x_label = ds_labels.get(req.dataset_x, req.dataset_x)
    y_label = ds_labels.get(req.dataset_y, req.dataset_y)

    user_msg = f"""Current scatter plot: X = {req.dataset_x} ({x_label}), Y = {req.dataset_y} ({y_label})
Available datasets: {', '.join(req.available_datasets)}
Regions available: South, Northeast, Midwest, West

User question: {req.question}"""

    api_key = os.environ.get('ANTHROPIC_API_KEY', '')
    if not api_key:
        return AskResponse(
            query_type='error',
            params={},
            error='ANTHROPIC_API_KEY not set'
        )

    try:
        import anthropic
        client = anthropic.Anthropic(api_key=api_key)
        message = client.messages.create(
            model='claude-haiku-4-5-20251001',
            max_tokens=300,
            system=SYSTEM_PROMPT,
            messages=[{'role': 'user', 'content': user_msg}],
        )
        raw_text = message.content[0].text.strip()

        # Parse JSON from response (handle markdown fences)
        json_str = raw_text
        if '```' in json_str:
            json_str = json_str.split('```')[1]
            if json_str.startswith('json'):
                json_str = json_str[4:]
            json_str = json_str.strip()

        parsed = json.loads(json_str)
        query_type = parsed.get('type', 'conceptual')
        params = parsed.get('params', {})

        return AskResponse(
            query_type=query_type,
            params=params,
            raw_llm_json=raw_text,
        )
    except json.JSONDecodeError:
        return AskResponse(
            query_type='error',
            params={},
            raw_llm_json=raw_text if 'raw_text' in dir() else None,
            error='Could not parse question — try rephrasing',
        )
    except Exception as e:
        return AskResponse(
            query_type='error',
            params={},
            error=str(e),
        )


# ── GET /dataset-metadata ──────────────────────────────────────
DATASET_META_PATH = DATA_DIR / 'dataset_metadata.json'


@router.get('/dataset-metadata')
def dataset_metadata():
    from fastapi.responses import JSONResponse
    if not DATASET_META_PATH.exists():
        return JSONResponse(status_code=503, content={"error": "dataset_metadata.json not found"})
    with open(DATASET_META_PATH) as f:
        data = json.load(f)
    return JSONResponse(content=data, headers={"Cache-Control": "max-age=86400"})


# ── GET /correlation-matrix ───────────────────────────────────
TAUTOLOGICAL_PAIRS = {
    frozenset(('poverty', 'eitc')): "Both measure economic hardship. EITC filing rate and poverty rate are alternative measures of the same low-income population.",
    frozenset(('poverty', 'median_income')): "Income and poverty are inverse measures of the same economic construct.",
    frozenset(('poverty', 'bea_income')): "Both measure county-level economic conditions — poverty rate and per-capita income are different expressions of the same phenomenon.",
    frozenset(('median_income', 'bea_income')): "Two income measures from different surveys (SAIPE and ACS) measuring the same underlying construct.",
    frozenset(('obesity', 'diabetes')): "Clinical comorbidity — obesity is the primary risk factor for Type 2 diabetes. ~85% of Type 2 diabetics are overweight or obese.",
    frozenset(('obesity', 'hypertension')): "Clinical comorbidity — obesity is a primary risk factor for hypertension.",
    frozenset(('diabetes', 'hypertension')): "Clinical comorbidity — both are components of metabolic syndrome and share common risk factors.",
    frozenset(('broadband', 'broadband_avail')): "Two measures of the same phenomenon (internet access) from different sources — subscription rate vs any-internet adoption.",
    frozenset(('rural_urban', 'pop_density')): "Two measures of the same urbanization construct — ordinal USDA codes vs continuous population density.",
}

_corr_cache = None


@router.get('/correlation-matrix')
def correlation_matrix():
    from fastapi.responses import JSONResponse
    global _corr_cache
    if _corr_cache is not None:
        return JSONResponse(content=_corr_cache, headers={"Cache-Control": "max-age=3600"})

    # Load all datasets
    frames = {}
    for ds_id, (col, _) in DATASET_REGISTRY.items():
        try:
            df = _load_dataset(ds_id)
            if col in df.columns:
                series = df[['fips', col]].dropna().rename(columns={col: ds_id})
                frames[ds_id] = series
        except Exception:
            pass

    if len(frames) < 2:
        return JSONResponse(status_code=503, content={"error": "Not enough datasets loaded"})

    # Merge all on FIPS
    merged = None
    for ds_id, df in frames.items():
        if merged is None:
            merged = df
        else:
            merged = merged.merge(df, on='fips', how='outer')

    ds_cols = [c for c in merged.columns if c != 'fips']

    # Min-max normalize
    for c in ds_cols:
        s = merged[c].astype(float)
        mn, mx = s.min(), s.max()
        merged[c] = (s - mn) / (mx - mn) if mx > mn else 0.5

    # Correlation matrix
    corr = merged[ds_cols].corr()
    matrix = {}
    for d1 in ds_cols:
        matrix[d1] = {}
        for d2 in ds_cols:
            v = corr.loc[d1, d2]
            matrix[d1][d2] = round(float(v), 4) if not pd.isna(v) else None

    # Find high pairs
    high_pairs = []
    seen = set()
    for d1 in ds_cols:
        for d2 in ds_cols:
            if d1 >= d2:
                continue
            pair = frozenset((d1, d2))
            if pair in seen:
                continue
            seen.add(pair)
            r_val = matrix[d1].get(d2)
            if r_val is None:
                continue
            if abs(r_val) < 0.6:
                continue

            severity = "very_high" if abs(r_val) > 0.85 else "high" if abs(r_val) > 0.70 else "moderate"

            if pair in TAUTOLOGICAL_PAIRS:
                high_pairs.append({
                    "d1": d1, "d2": d2, "r": r_val,
                    "type": "tautological",
                    "reason": TAUTOLOGICAL_PAIRS[pair],
                    "interpretation": "High correlation here is expected by construction, not a discovery.",
                    "severity": severity,
                })
            else:
                high_pairs.append({
                    "d1": d1, "d2": d2, "r": r_val,
                    "type": "collinear",
                    "reason": f"Empirically correlated (r={r_val:.3f}). These datasets tend to move together across counties, possibly due to shared underlying drivers.",
                    "interpretation": "This correlation may reflect genuine co-occurrence or shared confounders.",
                    "severity": severity,
                })

    high_pairs.sort(key=lambda x: -abs(x["r"]))

    taut_count = sum(1 for p in high_pairs if p["type"] == "tautological")
    coll_count = sum(1 for p in high_pairs if p["type"] == "collinear")
    logger.info(f"Correlation matrix: {len(high_pairs)} high pairs ({taut_count} tautological, {coll_count} collinear)")

    # Mark which datasets are in gravity model (18 active, broadband_avail excluded)
    GRAVITY_EXCLUDED = {"broadband_avail"}
    datasets_info = {ds: {"in_gravity_model": ds not in GRAVITY_EXCLUDED} for ds in ds_cols}

    result = {"matrix": matrix, "high_pairs": high_pairs, "datasets": datasets_info}
    _corr_cache = result
    return JSONResponse(content=result, headers={"Cache-Control": "max-age=3600"})


# ── GET /methodology ──────────────────────────────────────────
METHODOLOGY_PATH = DATA_DIR / 'methodology_v1.md'


@router.get('/methodology')
def methodology():
    from fastapi.responses import PlainTextResponse
    if not METHODOLOGY_PATH.exists():
        return PlainTextResponse(status_code=503, content="methodology_v1.md not found. Run generate_methodology.py first.")
    with open(METHODOLOGY_PATH, encoding='utf-8') as f:
        content = f.read()
    return PlainTextResponse(content=content, media_type="text/markdown", headers={"Cache-Control": "max-age=3600"})


# ── GET /pca-analysis ─────────────────────────────────────────
PCA_PATH = DATA_DIR / 'pca_results.json'


@router.get('/pca-analysis')
def pca_analysis():
    from fastapi.responses import JSONResponse
    if not PCA_PATH.exists():
        return JSONResponse(status_code=503, content={"error": "pca_results.json not found"})
    with open(PCA_PATH) as f:
        data = json.load(f)
    return JSONResponse(content=data, headers={"Cache-Control": "max-age=86400"})


# ── GET /gravity-terrain ──────────────────────────────────────
TERRAIN_PATH = DATA_DIR / 'gravity_terrain.json'


@router.get('/gravity-terrain')
def gravity_terrain():
    from fastapi.responses import JSONResponse
    if not TERRAIN_PATH.exists():
        return JSONResponse(status_code=503, content={"error": "Terrain data not built."})
    with open(TERRAIN_PATH) as f:
        data = json.load(f)
    return JSONResponse(content=data, headers={"Cache-Control": "max-age=86400"})


# ── GET /correlation-stats ─────────────────────────────────────
@router.get('/correlation-stats')
def correlation_stats(x: str, y: str):
    from fastapi.responses import JSONResponse
    from scipy import stats as sp_stats

    if x not in DATASET_REGISTRY or y not in DATASET_REGISTRY:
        raise HTTPException(400, f"Unknown dataset: {x if x not in DATASET_REGISTRY else y}")
    if x == y:
        raise HTTPException(400, "X and Y must be different datasets")

    col_x = DATASET_REGISTRY[x][0]
    col_y = DATASET_REGISTRY[y][0]

    try:
        df_x = _load_dataset(x)[['fips', col_x]].rename(columns={col_x: 'xv'})
        df_y = _load_dataset(y)[['fips', col_y]].rename(columns={col_y: 'yv'})
    except Exception as e:
        raise HTTPException(503, str(e))

    merged = df_x.merge(df_y, on='fips', how='inner').dropna(subset=['xv', 'yv'])
    x_vals = merged['xv'].values.astype(float)
    y_vals = merged['yv'].values.astype(float)
    n = len(x_vals)

    if n < 3:
        raise HTTPException(400, "Too few data points")

    r, p = sp_stats.pearsonr(x_vals, y_vals)
    r_squared = r ** 2
    variance_pct = round(r_squared * 100, 1)
    t_stat = r * np.sqrt(n - 2) / np.sqrt(max(1 - r ** 2, 1e-10))

    abs_r = abs(r)
    if abs_r >= 0.5:
        effect = "Strong"
    elif abs_r >= 0.3:
        effect = "Moderate"
    elif abs_r >= 0.1:
        effect = "Weak"
    else:
        effect = "Negligible"

    if variance_pct >= 25:
        practical = "Large — explains substantial county variance"
    elif variance_pct >= 9:
        practical = "Moderate — meaningful county-level pattern"
    elif variance_pct >= 1:
        practical = "Small — real but limited explanatory value"
    else:
        practical = "Negligible — statistically real but trivial"

    bonf = 0.05 / 171
    bonf_sig = bool(p < bonf)
    # Bonferroni r threshold
    t_thresh = sp_stats.t.ppf(1 - bonf / 2, df=n - 2)
    r_bonf_threshold = float(t_thresh / np.sqrt(t_thresh ** 2 + n - 2))

    # Effect color
    effect_color = "gray" if abs_r < 0.1 else "yellow" if abs_r < 0.3 else "blue" if abs_r < 0.5 else "green"

    if p < 0.001:
        p_disp = "p<0.001"
    elif p < 0.01:
        p_disp = "p<0.01"
    elif p < 0.05:
        p_disp = "p<0.05"
    else:
        p_disp = f"p={p:.3f}"

    direction = "positive" if r > 0 else "negative"
    interpretation = (
        f"{effect} {direction} correlation explaining "
        f"{variance_pct}% of county-level variance. {practical}."
    )

    return JSONResponse(content={
        "x": x, "y": y, "n": n,
        "r": round(float(r), 4),
        "r_squared": round(float(r_squared), 4),
        "variance_explained_pct": variance_pct,
        "t_stat": round(float(t_stat), 4),
        "p_value": float(p),
        "p_display": p_disp,
        "effect_size": effect,
        "practical_significance": practical,
        "effect_color": effect_color,
        "bonferroni_significant": bonf_sig,
        "bonferroni_threshold": bonf,
        "bonferroni_threshold_r": round(r_bonf_threshold, 4),
        "n_comparisons": 171,
        "interpretation": interpretation,
        "direction": direction,
    }, headers={"Cache-Control": "max-age=3600"})


# ── GET /gravity-map/validation ────────────────────────────────
VALIDATION_PATH = DATA_DIR / 'validation_results.json'


@router.get('/gravity-map/validation')
def gravity_validation():
    from fastapi.responses import JSONResponse
    if not VALIDATION_PATH.exists():
        return JSONResponse(status_code=503, content={"error": "validation_results.json not found"})
    with open(VALIDATION_PATH) as f:
        data = json.load(f)
    return JSONResponse(content=data, headers={"Cache-Control": "max-age=86400"})


# ── Gravity combinations ──────────────────────────────────────
GRAVITY_COMBINATIONS = [
    {"id": "all", "label": "All datasets (18)", "n_datasets": 18,
     "description": "All 18 active datasets weighted equally. Primarily clusters by economic deprivation (PC1=41.8%). Best for: overall socioeconomic similarity.",
     "datasets": list(DATASET_REGISTRY.keys()),
     "cache_file": str(DATA_DIR / "gravity_map_cache.json")},
    {"id": "economic", "label": "Economic conditions", "n_datasets": 6,
     "description": "Clusters by poverty, income, economic mobility, and labor market. Isolates the dominant axis of American inequality.",
     "datasets": ["poverty", "eitc", "median_income", "bea_income", "unemployment", "mobility"],
     "cache_file": str(DATA_DIR / "gravity_cache_economic.json")},
    {"id": "health", "label": "Health outcomes", "n_datasets": 4,
     "description": "Clusters by chronic disease burden independent of economic conditions.",
     "datasets": ["obesity", "diabetes", "hypertension", "mental_health"],
     "cache_file": str(DATA_DIR / "gravity_cache_health.json")},
    {"id": "infrastructure", "label": "Infrastructure & environment", "n_datasets": 4,
     "description": "Clusters by access to services and environmental quality.",
     "datasets": ["broadband", "library", "air", "food_access"],
     "cache_file": str(DATA_DIR / "gravity_cache_infrastructure.json")},
    {"id": "civic", "label": "Civic & demographic", "n_datasets": 4,
     "description": "Clusters by political participation, urban character, and housing stress.",
     "datasets": ["voter_turnout", "rural_urban", "pop_density", "housing_burden"],
     "cache_file": str(DATA_DIR / "gravity_cache_civic.json")},
    {"id": "pca", "label": "PCA balanced (7 axes)", "n_datasets": 7,
     "description": "Equal weight to each independent axis of county variation (7 PCA components, 80% of variance). Economic deprivation drops from 41.8% to 14.3% influence. Best for: finding counties similar across ALL dimensions equally.",
     "datasets": list(DATASET_REGISTRY.keys()),
     "cache_file": str(DATA_DIR / "gravity_cache_pca.json")},
]


@router.get('/gravity-combinations')
def gravity_combinations():
    from fastapi.responses import JSONResponse
    result = []
    for c in GRAVITY_COMBINATIONS:
        result.append({
            "id": c["id"], "label": c["label"], "description": c["description"],
            "n_datasets": c["n_datasets"], "datasets": c["datasets"],
            "available": Path(c["cache_file"]).exists(),
        })
    return JSONResponse(content=result)


# ── GET /gravity-map ──────────────────────────────────────────
_gravity_caches = {}


def _load_gravity_cache(combo_id="all"):
    cache_file = None
    for c in GRAVITY_COMBINATIONS:
        if c["id"] == combo_id:
            cache_file = c["cache_file"]
            break
    if cache_file is None or not Path(cache_file).exists():
        return None
    # Check if cached in memory
    mtime = Path(cache_file).stat().st_mtime
    if combo_id in _gravity_caches and _gravity_caches[combo_id][1] == mtime:
        return _gravity_caches[combo_id][0]
    with open(cache_file) as f:
        data = json.load(f)
    # For non-all caches, merge nodes from main cache
    if combo_id != "all" and "nodes" not in data:
        main = _load_gravity_cache("all")
        if main:
            data["nodes"] = main["nodes"]
            data["metadata"] = main.get("metadata", {})
    _gravity_caches[combo_id] = (data, mtime)
    return data


@router.get('/gravity-map')
def gravity_map(combination: str = "all"):
    from fastapi.responses import JSONResponse
    data = _load_gravity_cache(combination)
    if data is None:
        available = [c["id"] for c in GRAVITY_COMBINATIONS if Path(c["cache_file"]).exists()]
        return JSONResponse(
            status_code=404 if combination != "all" else 503,
            content={"error": f"Combination '{combination}' not found", "available": available},
        )
    return JSONResponse(
        content=data,
        headers={"Cache-Control": "max-age=3600"},
    )


@router.get('/gravity-map/metadata')
def gravity_map_metadata():
    from fastapi.responses import JSONResponse
    data = _load_gravity_cache()
    if data is None:
        return JSONResponse(
            status_code=503,
            content={"error": "Gravity map cache not built. Run data_pipeline/gravity/run_gravity_pipeline.py first."},
        )
    return JSONResponse(
        content=data.get("metadata", {}),
        headers={"Cache-Control": "max-age=3600"},
    )
