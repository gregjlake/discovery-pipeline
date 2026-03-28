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
    'bea_income':     ('per_capita_income',        'Per capita personal income ($/year)'),
    'food_access':    ('snap_rate',                'SNAP/food stamp receipt rate'),
    'obesity':        ('obesity_rate',             'Adult obesity prevalence (%)'),
    'diabetes':       ('diabetes_rate',            'Adult diabetes prevalence (%)'),
    'mental_health':  ('mental_health_rate',       'Poor mental health days (%)'),
    'hypertension':   ('hypertension_rate',        'High blood pressure prevalence (%)'),
    'unemployment':   ('unemployment_rate',        'Unemployment rate'),
    'rural_urban':    ('rural_urban_code',         'Rural-urban continuum code (1-9)'),
    'housing_burden': ('housing_burden_rate',      'Cost-burdened renters (30%+ income)'),
    'voter_turnout':  ('total_votes_2020',         'Total votes cast 2020 presidential'),
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


# ── GET /gravity-map ──────────────────────────────────────────
GRAVITY_CACHE = DATA_DIR / 'gravity_map_cache.json'
_gravity_cache_data = None
_gravity_cache_mtime = 0


def _load_gravity_cache():
    global _gravity_cache_data, _gravity_cache_mtime
    if not GRAVITY_CACHE.exists():
        return None
    mtime = GRAVITY_CACHE.stat().st_mtime
    if _gravity_cache_data is None or mtime != _gravity_cache_mtime:
        with open(GRAVITY_CACHE) as f:
            _gravity_cache_data = json.load(f)
        _gravity_cache_mtime = mtime
    return _gravity_cache_data


@router.get('/gravity-map')
def gravity_map():
    from fastapi.responses import JSONResponse
    data = _load_gravity_cache()
    if data is None:
        return JSONResponse(
            status_code=503,
            content={"error": "Gravity map cache not built. Run data_pipeline/gravity/run_gravity_pipeline.py first."},
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
