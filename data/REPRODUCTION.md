# Reproduction Guide

This document explains how to verify each quantitative claim in the DiscoSights paper.

## Quick Verification (no credentials needed)

```bash
python reproduce.py
```

This script reproduces beta calibration from flat files and prints stored validation results.

## Headline Claims

### beta = 0.139 (distance decay parameter)

| Method | Requirements |
|--------|-------------|
| `python reproduce.py` | None (uses `data/county_data_matrix.csv`) |
| Check `data/beta_calibration.json` | None |
| Live API: `curl .../api/gravity-map/metadata` | Internet |
| Full pipeline: `python data_pipeline/gravity/calibrate_beta.py` then `run_gravity_pipeline.py` | Supabase credentials |

**Source file:** `data/beta_calibration.json`
- `beta_operative`: 0.138702
- `r_squared_combined`: 0.302591
- `beta_cv`: 0.13883 (cross-validated, 80/20 holdout)
- `r2_cv_holdout`: 0.302131

### rho = 0.164 (IRS migration validation)

| Method | Requirements |
|--------|-------------|
| Check `data/validation_results.json` | None |
| Live API: `curl .../api/gravity-map/validation` | Internet |
| Full pipeline: `python data_pipeline/gravity/validate_against_migration.py` | `data/gravity_map_cache.json` (included) + IRS download |

**Source file:** `data/validation_results.json`
- `spearman_rho`: 0.1636
- `rho_ci_low`: 0.1542, `rho_ci_high`: 0.1723 (bootstrap 95% CI)
- `model_a_rho`: 0.0405 (population only)
- `model_b_rho`: 0.0534 (+ geography)
- `improvement_b_to_c`: 0.1102

**IRS data source:** https://www.irs.gov/statistics/soi-tax-stats-migration-data
- Download: County-to-County Migration Data, 2019-2020 (inflow file)

### Within-cluster r = 0.099--0.528 (poverty x diabetes)

| Method | Requirements |
|--------|-------------|
| Check `data/within_cluster_correlations.json` | None |
| Live API: `curl .../api/within-cluster-correlations` | Internet |

**Source file:** `data/within_cluster_correlations.json`
- Overall r = 0.705
- 5 cluster r-values computed from `data/county_data_matrix.csv` using k-means (k=5, seed=42)

### Silhouette = 0.17 (k=5 clustering)

| Method | Requirements |
|--------|-------------|
| Check `data/cluster_silhouette_scores.json` | None |
| Live API: `curl .../api/cluster-silhouette-scores` | Internet |

**Source file:** `data/cluster_silhouette_scores.json`

### KNN equivalence (Jaccard = 1.000 for peer discovery vs KNN)

The paper states peer discovery is "equivalent to KNN; Jaccard = 1.000." This means the peer discovery algorithm IS k-nearest-neighbors in the module's variable subspace -- it is definitionally identical, not an empirical comparison.

The separate gravity-vs-KNN comparison (Jaccard = 0.015) is in `data/knn_comparison.json` and shows that gravity model force rankings differ substantially from pure data-space KNN due to population weighting.

## Data Files

| File | Description |
|------|-------------|
| `data/county_data_matrix.csv` | 3,143 counties x 29 normalized variables (0-1 scale, NaN = missing) |
| `data/county_centroids.csv` | County lat/lon centroids |
| `data/county_population.csv` | County populations |
| `data/beta_calibration.json` | Calibrated beta and cross-validation results |
| `data/validation_results.json` | IRS migration validation results |
| `data/gravity_map_cache.json` | Pre-computed gravity nodes and top-10,000 links |
| `data/within_cluster_correlations.json` | Poverty x diabetes r by cluster |
| `data/cluster_silhouette_scores.json` | Silhouette scores for k=4..8 |
| `data/knn_comparison.json` | Gravity vs KNN peer list comparison |
| `data/pca_results.json` | PCA variance explained and loadings |
| `data/dataset_metadata.json` | Full provenance for all datasets |

## Full Pipeline Reproduction

Requires Supabase credentials (contains the raw county data):

```bash
cp .env.example .env
# Edit .env with SUPABASE_URL and SUPABASE_SERVICE_KEY

python data_pipeline/gravity/calibrate_beta.py
python data_pipeline/gravity/run_gravity_pipeline.py
python data_pipeline/gravity/validate_against_migration.py
```

Expected outputs match `data/beta_calibration.json` and `data/validation_results.json`.
