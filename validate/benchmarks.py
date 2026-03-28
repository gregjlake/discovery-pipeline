"""Benchmark known published correlations against pipeline data."""
import numpy as np
import pandas as pd

BENCHMARKS = [
    {
        'name': 'Poverty × Mobility (Chetty 2014)',
        'dataset_x': 'poverty',
        'dataset_y': 'mobility',
        'expected_r': -0.60,
        'tolerance': 0.08,
        'citation': 'Chetty et al, Where is the Land of Opportunity, QJE 2014',
    },
    {
        'name': 'EITC × Poverty (IRS × SAIPE)',
        'dataset_x': 'eitc',
        'dataset_y': 'poverty',
        'expected_r': 0.80,
        'tolerance': 0.08,
        'citation': 'Expected strong positive — both measure poverty dimensions',
    },
    {
        'name': 'Median Income × Poverty',
        'dataset_x': 'median_income',
        'dataset_y': 'poverty',
        'expected_r': -0.75,
        'tolerance': 0.08,
        'citation': 'Expected strong negative by construction',
    },
    {
        'name': 'Unemployment × Poverty',
        'dataset_x': 'unemployment',
        'dataset_y': 'poverty',
        'expected_r': 0.65,
        'tolerance': 0.10,
        'citation': 'Well established labor economics relationship',
    },
    {
        'name': 'Obesity × Poverty',
        'dataset_x': 'obesity',
        'dataset_y': 'poverty',
        'expected_r': 0.50,
        'tolerance': 0.15,
        'citation': 'CDC health disparities — poverty associated with higher obesity',
    },
    {
        'name': 'Per Capita Income × Median Income',
        'dataset_x': 'bea_income',
        'dataset_y': 'median_income',
        'expected_r': 0.90,
        'tolerance': 0.08,
        'citation': 'Near-tautological — both measure income',
    },
]


def _zscore(s: pd.Series) -> pd.Series:
    return (s - s.mean()) / s.std()


def run_benchmarks(load_dataset_fn) -> list[dict]:
    """Run all benchmarks using the provided dataset loader.

    Args:
        load_dataset_fn: callable(dataset_id) -> pd.DataFrame with columns [fips, <value_col>, year]
            The value column name must match the dataset registry.

    Returns:
        List of result dicts with keys: name, dataset_x, dataset_y, expected_r, actual_r,
        tolerance, diff, status (PASS/WARN/FAIL), n, citation, error
    """
    # Dataset registry (duplicated here to keep module self-contained)
    registry = {
        'library':        'library_spend_per_capita',
        'mobility':       'mobility_rank_p25',
        'air':            'air_quality_inv',
        'broadband':      'broadband_rate',
        'eitc':           'eitc_rate',
        'poverty':        'poverty_rate',
        'median_income':  'median_hh_income',
        'bea_income':     'per_capita_income',
        'food_access':    'snap_rate',
        'obesity':        'obesity_rate',
        'diabetes':       'diabetes_rate',
        'mental_health':  'mental_health_rate',
        'hypertension':   'hypertension_rate',
        'unemployment':   'unemployment_rate',
        'rural_urban':    'rural_urban_code',
        'housing_burden': 'housing_burden_rate',
        'voter_turnout':  'total_votes_2020',
        'broadband_avail': 'internet_access_rate',
        'pop_density':    'pop_density',
    }

    results = []

    for bench in BENCHMARKS:
        result = {
            'name': bench['name'],
            'dataset_x': bench['dataset_x'],
            'dataset_y': bench['dataset_y'],
            'expected_r': bench['expected_r'],
            'tolerance': bench['tolerance'],
            'citation': bench['citation'],
            'actual_r': None,
            'diff': None,
            'status': 'SKIP',
            'n': 0,
            'error': None,
        }

        ds_x = bench['dataset_x']
        ds_y = bench['dataset_y']

        if ds_x not in registry or ds_y not in registry:
            result['error'] = f"Dataset not in registry: {ds_x if ds_x not in registry else ds_y}"
            results.append(result)
            continue

        col_x = registry[ds_x]
        col_y = registry[ds_y]

        try:
            df_x = load_dataset_fn(ds_x)
            df_y = load_dataset_fn(ds_y)
        except Exception as e:
            result['error'] = f"Failed to load data: {e}"
            results.append(result)
            continue

        # Merge on FIPS
        try:
            dx = df_x[['fips', col_x]].rename(columns={col_x: 'raw_x'})
            dy = df_y[['fips', col_y]].rename(columns={col_y: 'raw_y'})
            merged = dx.merge(dy, on='fips', how='inner').dropna(subset=['raw_x', 'raw_y'])

            if len(merged) < 10:
                result['error'] = f"Only {len(merged)} counties matched"
                results.append(result)
                continue

            # Zscore normalize
            merged['x'] = _zscore(merged['raw_x'])
            merged['y'] = _zscore(merged['raw_y'])
            merged = merged.replace([np.inf, -np.inf], np.nan).dropna(subset=['x', 'y'])

            actual_r = float(merged['x'].corr(merged['y']))
            diff = abs(actual_r - bench['expected_r'])

            result['actual_r'] = round(actual_r, 4)
            result['diff'] = round(diff, 4)
            result['n'] = len(merged)

            if diff <= bench['tolerance']:
                result['status'] = 'PASS'
            elif diff <= bench['tolerance'] * 2:
                result['status'] = 'WARN'
            else:
                result['status'] = 'FAIL'

        except Exception as e:
            result['error'] = str(e)

        results.append(result)

    return results


def print_benchmarks(results: list[dict]) -> None:
    """Pretty-print benchmark results to stdout."""
    print(f"\n{'='*70}")
    print("BENCHMARK RESULTS")
    print('='*70)
    print(f"{'Status':<6} {'Name':<40} {'Expected':>8} {'Actual':>8} {'Diff':>6} {'n':>6}")
    print('-'*70)
    for r in results:
        actual = f"{r['actual_r']:.3f}" if r['actual_r'] is not None else "—"
        diff = f"{r['diff']:.3f}" if r['diff'] is not None else "—"
        n = str(r['n']) if r['n'] else "—"
        print(f"{r['status']:<6} {r['name']:<40} {r['expected_r']:>8.3f} {actual:>8} {diff:>6} {n:>6}")
        if r['error']:
            print(f"       ERROR: {r['error']}")
    print('-'*70)
    statuses = [r['status'] for r in results]
    passed = statuses.count('PASS')
    warned = statuses.count('WARN')
    failed = statuses.count('FAIL')
    skipped = statuses.count('SKIP')
    print(f"Total: {len(results)} benchmarks — {passed} PASS, {warned} WARN, {failed} FAIL, {skipped} SKIP")
