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

load_dotenv(Path(__file__).resolve().parent.parent / '.env')

logger = logging.getLogger("api.routes")

router = APIRouter()

DATA_DIR = Path(__file__).resolve().parent.parent / 'data'

# Dataset registry: dataset_id -> (value_column, description)
DATASET_REGISTRY = {
    'library':   ('library_spend_per_capita', 'Library spending per capita ($)'),
    'mobility':  ('mobility_rank_p25',        'Upward mobility rank (p25)'),
    'air':       ('air_quality_inv',          'Air quality index (inverted, higher=better)'),
    'broadband': ('broadband_rate',           'Broadband subscription rate'),
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


# ── GET /datasets ──────────────────────────────────────────────
@router.get('/datasets')
def list_datasets():
    results = []
    for ds_id, (col, desc) in DATASET_REGISTRY.items():
        path = DATA_DIR / f'{ds_id}.parquet'
        if path.exists():
            df = pd.read_parquet(path)
            results.append({
                'dataset_id': ds_id,
                'value_column': col,
                'description': desc,
                'county_count': int(df['fips'].nunique()),
                'row_count': len(df),
            })
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
        points.append({
            'fips': row['fips'],
            'name': '',
            'region': '',
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
