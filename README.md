# DiscoSights — Backend Pipeline

## Overview

DiscoSights is a spatial interaction model for US county socioeconomic similarity. This repository contains the data ingestion pipeline, gravity model calibration, validation scripts, and FastAPI backend serving the live tool at https://discovery-surface-spark.lovable.app.

The frontend repository is at [github.com/gregjlake/discovery-insights](https://github.com/gregjlake/discovery-insights).

## Statement of Need

Identifying socioeconomic peer counties — places that share structural conditions despite geographic distance — is a common but methodologically inconsistent task in policy research, public health, and economic geography. Researchers typically select variables ad hoc and weight them arbitrarily.

DiscoSights provides a gravity model with empirically calibrated distance decay (beta = 0.155), out-of-sample IRS migration validation (+0.112 rho improvement over geography alone), and documented weighting robustness (Jaccard = 0.891 across schemes). Example: McDowell County WV and Starr County TX share economic profiles across 17 datasets despite being 1,247 miles apart.

## Installation

### Requirements

- Python 3.10+
- PostgreSQL (via Supabase) or local PostgreSQL
- Census API key (optional but recommended)

### Setup

```bash
git clone https://github.com/gregjlake/discovery-pipeline
cd discovery-pipeline
pip install -r requirements.txt
cp .env.example .env
# Edit .env with your credentials
```

### Environment Variables

See `.env.example` for all required variables:

| Variable | Required | Description |
|----------|----------|-------------|
| `SUPABASE_URL` | Yes | Supabase project URL |
| `SUPABASE_SERVICE_KEY` | Yes | Supabase service role key |
| `CENSUS_API_KEY` | No | Census Bureau API key (keyless works at low rate) |
| `DATABASE_URL` | No | Direct PostgreSQL URL (Railway deployment) |

## Database Setup

Run `schema.sql` to create all required tables:

```bash
psql $DATABASE_URL < schema.sql
```

Or create tables via Supabase dashboard using `schema.sql` as reference.

## Data Pipeline

### Running the full pipeline

```bash
# 1. Calibrate beta (geographic + combined distance)
python data_pipeline/gravity/calibrate_beta.py

# 2. Run gravity model (force computation + cache)
python data_pipeline/gravity/run_gravity_pipeline.py

# 3. Validate against IRS migration flows
python data_pipeline/gravity/validate_against_migration.py

# 4. Compute force variants (raw, affinity, residual)
python data_pipeline/gravity/compute_force_variants.py

# 5. Compute pre-computed layout positions
python data_pipeline/gravity/compute_layout.py

# 6. Compute PCA analysis
python data_pipeline/gravity/pca_analysis.py

# 7. Compute terrain potential field
python data_pipeline/gravity/compute_terrain.py

# 8. Add reliability scores from Census MOE
python data_pipeline/gravity/fetch_margins_of_error.py

# 9. Generate methodology document
python data_pipeline/gravity/generate_methodology.py
```

### Key outputs

| File | Description |
|------|-------------|
| `data/beta_calibration.json` | Calibrated beta and R-squared values |
| `data/gravity_map_cache.json` | Pre-computed nodes, links, and force variants |
| `data/validation_results.json` | IRS migration validation results |
| `data/pca_results.json` | PCA analysis of dataset structure |
| `data/county_reliability.json` | Census MOE-based reliability scores |
| `data/methodology_v1.md` | Auto-generated methodology document |
| `data/dataset_metadata.json` | Full provenance for all datasets |

## Running the API locally

```bash
uvicorn api.main:app --reload --port 8000
```

API documentation available at http://localhost:8000/docs

Key endpoints:

| Endpoint | Description |
|----------|-------------|
| `GET /api/gravity-map` | Gravity nodes, links, and metadata |
| `GET /api/gravity-terrain` | 80x80 potential field for terrain view |
| `GET /api/pca-analysis` | PCA results and component loadings |
| `GET /api/datasets` | Available dataset list |
| `POST /api/scatter` | Scatter plot data for any dataset pair |
| `GET /api/methodology` | Full methodology document (markdown) |

## Testing

```bash
pytest tests/ -v
```

Unit tests cover core scientific functions (haversine, dissimilarity, gravity force, reliability scoring) using synthetic data — no live Supabase connection required.

## Model Summary

- **17 active datasets** from Census, CDC, EPA, USDA, IRS, FEMA
- **beta = 0.155** (empirically calibrated, R-squared = 0.313)
- **IRS validation**: +0.112 rho improvement over geography alone
- **Weighting robustness**: domain-balanced Jaccard = 0.891
- **3,135 counties** with pre-computed equilibrium positions
- **9 FEMA disaster datasets** available for scatter exploration

## Data Sources

See `data/dataset_metadata.json` for full provenance. Key sources:

- Census Bureau ACS 5-Year (2018-2022)
- Census SAIPE (2022)
- USDA Food Access Research Atlas (2019)
- FEMA National Risk Index (2020)
- IRS Statistics of Income migration data (2019-2020)
- CDC PLACES / BRFSS (2022)
- EPA Air Quality System (2022)
- IMLS Public Libraries Survey (FY 2022)
- MIT Election Data + Science Lab (2020)

## Citation

If you use DiscoSights in research, please cite:

> Lake, G. (2026). DiscoSights: A Validated Spatial Interaction Model for US County Socioeconomic Similarity. *Journal of Open Source Software* (submitted).

## Authors

**Greg Lake** — Independent Researcher
GitHub: [@gregjlake](https://github.com/gregjlake)

## License

MIT — see [LICENSE](LICENSE)
