#!/usr/bin/env python3
"""
Positive Deviance Analysis — precompute OLS residuals for all county × outcome combinations.

For each variable as outcome, fits OLS using all OTHER variables as inputs,
then z-scores the residuals. Positive z = county outperforms predicted outcome.
"""
import numpy as np
import pandas as pd
import json
import os

from sklearn.linear_model import LinearRegression
from data_pipeline.utils.storage import upload_to_storage

# Load county data
df = pd.read_csv('data/county_data_matrix.csv')
df = df.set_index('fips')
df = df.drop(columns=['county_name'], errors='ignore')
df = df.fillna(0.5)

with open('data/beta_calibration.json') as f:
    beta = json.load(f)
all_datasets = beta['datasets_used']

print(f"Loaded {len(df)} counties × {len(all_datasets)} variables")

# For each variable as outcome, compute residuals using all OTHER variables as inputs
all_residuals = {}
all_r2 = {}
all_predicted = {}

for outcome_var in all_datasets:
    input_vars = [v for v in all_datasets if v != outcome_var]

    X = df[input_vars].values
    y = df[outcome_var].values

    # Fit OLS
    model = LinearRegression()
    model.fit(X, y)
    predicted = model.predict(X)
    residuals = y - predicted

    # Z-score residuals
    r_std = residuals.std()
    if r_std > 0:
        residual_z = (residuals - residuals.mean()) / r_std
    else:
        residual_z = np.zeros_like(residuals)

    r2 = model.score(X, y)

    all_residuals[outcome_var] = {
        str(fips): float(residual_z[i])
        for i, fips in enumerate(df.index)
    }
    all_r2[outcome_var] = float(r2)
    all_predicted[outcome_var] = {
        str(fips): float(predicted[i])
        for i, fips in enumerate(df.index)
    }

    print(f"  {outcome_var}: R²={r2:.3f}")

# Save full residual matrix
results = {
    'residuals_z': all_residuals,
    'r2_by_outcome': all_r2,
    'predicted_values': all_predicted,
    'n_counties': len(df),
    'n_outcomes': len(all_datasets),
    'method': ('OLS regression residuals, z-scored per outcome variable. '
               'Positive z = county outperforms its predicted outcome given all '
               'other variables as inputs.'),
    'note': ('These are full-model residuals (all 28 other vars as inputs). '
             'User-defined subset residuals are computed server-side at query time '
             'via POST /api/positive-deviance/compute.')
}

with open('data/positive_deviance.json', 'w') as f:
    json.dump(results, f)

print(f"\nSaved positive_deviance.json")
print(f"R² range: {min(all_r2.values()):.3f} - {max(all_r2.values()):.3f}")

# Print most interesting findings
sorted_r2 = sorted(all_r2.items(), key=lambda x: -x[1])
print("\nTop 5 most predictable outcomes:")
for var, r2 in sorted_r2[:5]:
    print(f"  {var}: R²={r2:.3f}")
print("\nLeast predictable (most independent):")
for var, r2 in sorted_r2[-5:]:
    print(f"  {var}: R²={r2:.3f}")

upload_to_storage('data/positive_deviance.json')
print("\nUploaded to Supabase Storage")
