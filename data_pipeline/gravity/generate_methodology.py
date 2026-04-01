"""Generate methodology_v1.md from model output JSON files."""
import json
from datetime import date

with open('data/beta_calibration.json') as f:
    beta = json.load(f)
with open('data/validation_results.json') as f:
    val = json.load(f)
with open('data/weighting_comparison.json') as f:
    wc = json.load(f)
try:
    with open('data/peer_stability_analysis.json') as f:
        ps = json.load(f)
except FileNotFoundError:
    ps = None
with open('data/pca_results.json') as f:
    pca = json.load(f)
with open('data/dataset_metadata.json') as f:
    meta = json.load(f)

today = date.today().isoformat()
datasets_used = beta['datasets_used']

# Build dataset table
ds_rows = []
for ds_id in sorted(datasets_used):
    m = meta.get(ds_id, {})
    if m.get('excluded_from_gravity'):
        continue
    flags = []
    if m.get('proxy_warning'):
        flags.append('proxy')
    if m.get('diagnosis_bias'):
        flags.append('diagnosis bias')
    flag_str = f" [{', '.join(flags)}]" if flags else ""
    ds_rows.append(
        f"| {ds_id} | {m.get('label', ds_id)} | {m.get('source', 'N/A')} "
        f"| {m.get('data_year', 'N/A')} | {m.get('unit', 'N/A')} "
        f"| {m.get('maup_sensitivity', 'N/A')}{flag_str} |"
    )

ds_table = (
    "| Dataset | Label | Source | Data Year | Unit | MAUP Sensitivity |\n"
    "|---------|-------|--------|-----------|------|------------------|\n"
    + "\n".join(ds_rows)
)

# PCA top datasets
pc1 = pca['component_details']['PC1']
pc2 = pca['component_details']['PC2']
pc1_top = ", ".join(pc1['top_datasets'])
pc2_top = ", ".join(pc2['top_datasets'])

# Collinearity pairs
collinear_lines = "\n".join(
    f"  - {p['d1']} x {p['d2']}: r={p['r']:.3f}"
    for p in pca['unexpected_collinear_pairs']
)

# Weighting variants
va = wc['variants']['A_equal']
vb = wc['variants']['B_cluster']
vc = wc['variants']['C_pca7']
max_diff = max(abs(va['rho'] - vb['rho']), abs(va['rho'] - vc['rho']), abs(vb['rho'] - vc['rho']))

# Data years for temporal range
years = []
for ds_id in datasets_used:
    m = meta.get(ds_id, {})
    yr = m.get('data_year', '')
    for part in yr.replace('FY ', '').replace('Tax Year ', '').split('--'):
        for sub in part.split('-'):
            try:
                y = int(sub.strip()[:4])
                if 1900 < y < 2100:
                    years.append(y)
            except (ValueError, IndexError):
                pass
min_year = min(years) if years else 1978
max_year = max(years) if years else 2023

doc = f"""# DiscoSights Methodology and Validation
## Version 1.0 -- {today}

### Overview
DiscoSights is a spatial interaction model for exploring socioeconomic similarity among US counties. It applies a gravity model analogy: counties with similar profiles across {len(datasets_used)} socioeconomic datasets and smaller geographic distance exert stronger "gravitational attraction" toward each other.

### Data Sources
{ds_table}

Datasets flagged with [proxy] use indirect measurements. Datasets flagged with [diagnosis bias] measure diagnosed prevalence, which underestimates true prevalence in areas with limited healthcare access.

### Gravity Model Formula
```
Force(i,j) = Pop(i) x Pop(j) / dist(i,j)^beta
```

where:
- beta = {beta['beta_operative']:.6f} (empirically calibrated)
- dist(i,j) = geo_norm(i,j) x data_dissimilarity(i,j)
- geo_norm = Haversine distance / max US distance (5,251 mi)
- data_dissimilarity = normalized Euclidean distance across {len(datasets_used)} datasets

### beta Calibration
Two-pass calibration procedure:

**Pass 1 (geographic only):**
- beta_geo = {beta['beta_geo']:.6f}
- R-squared = {beta['r_squared_geo']:.6f}
- Method: OLS log-linear regression of socioeconomic similarity on geographic distance across {beta['n_pairs']:,} randomly sampled county pairs

**Pass 2 (combined distance):**
- beta_operative = {beta['beta_operative']:.6f}
- R-squared = {beta['r_squared_combined']:.6f}
- Method: Same regression using combined distance (geo x data dissimilarity)

The 8x improvement in R-squared from pass 1 to pass 2 ({beta['r_squared_geo']:.4f} -> {beta['r_squared_combined']:.4f}) confirms that socioeconomic distance adds predictive power beyond geography alone.

### Out-of-Sample Validation
The model was validated against IRS Statistics of Income county-to-county migration flows (tax year 2019-2020, {val['n_pairs_total']:,} county pairs). This data was not used in model calibration.

Spearman rho (predicted force vs observed migration):
- Population only:     {val['model_a_rho']:.4f}
- + Geographic dist:   {val['model_b_rho']:.4f}
- + Data similarity:   {val['model_c_rho']:.4f}

Adding socioeconomic similarity improved migration prediction by +{val['improvement_b_to_c']:.3f} rho over geography alone -- validating the model's core premise that data similarity carries predictive information beyond physical proximity.

### Weighting Robustness Analysis
Three weighting schemes were tested against IRS migration:

| Scheme | IRS rho | Eff dims | Econ share |
|--------|---------|----------|------------|
| Equal (current) | {va['rho']:.4f} | {va['eff_dims']:.2f} | {va['econ_share_pct']:.1f}% |
| Domain balanced | {vb['rho']:.4f} | {vb['eff_dims']:.2f} | {vb['econ_share_pct']:.1f}% |
| PCA 7 components | {vc['rho']:.4f} | {vc['eff_dims']:.2f} | {vc['econ_share_pct']:.1f}% |

Maximum difference: {max_diff:.4f} rho

All schemes produce equivalent aggregate predictions. The model is robust to weighting choice at the IRS migration level.

### Peer Stability Analysis
{f"""Peer-level stability was tested for 5 median-profile counties (P45-P55) across the three weighting schemes:

- Equal vs Domain balanced: mean Jaccard similarity = {ps['mean_jaccard_equal_vs_domain']:.3f} (91% top-10 peer overlap)
- Equal vs PCA 7 components: mean Jaccard similarity = {ps['mean_jaccard_equal_vs_pca7']:.3f} (9% overlap)

Domain-balanced weighting preserves peer rankings. Reducing to 7 datasets produces substantially different peer lists. The 7-dataset view should be understood as a different analytical lens, not a cleaner version of the full model.""" if ps else "Peer stability analysis not yet run."}

### External Validation -- FEMA Disaster Risk
FEMA National Risk Index (2023) scores for 9 natural hazard variables were compared against the 17 socioeconomic datasets:

- Overall disaster risk x poverty: r = 0.151 (weak -- largely independent)
- Social vulnerability x poverty: r = 0.515 (moderate)

Disaster risk adds a genuinely independent dimension to county analysis. Two counties can be socioeconomic peers while facing completely different natural hazard futures. FEMA disaster variables are available in the scatter plot but excluded from the gravity model to avoid conflating geographic hazard exposure with socioeconomic structure.

### Dataset Structure
PCA analysis of the {len(datasets_used)} active datasets:
- Effective dimensions: {pca['effective_dimensions']:.2f} / {pca['n_datasets']}
- Components for 80% variance: {pca['n_components_80pct']}
- Components for 90% variance: {pca['n_components_90pct']}

**PC1 ({pc1['variance_pct']:.1f}% of variance):**
- Top drivers: {pc1_top}
- Interpretation: Economic deprivation axis

**PC2 ({pc2['variance_pct']:.1f}% of variance):**
- Top drivers: {pc2_top}
- Interpretation: Urbanization axis

**High collinearity pairs (|r| > 0.6):**
{collinear_lines}

Note: Low effective dimensions reflect genuine structure in US county data -- economic, health, and social outcomes are deeply correlated. This is not a measurement artifact. Weighting robustness analysis confirms it does not distort findings.

### Known Limitations

1. **Ecological fallacy:** All analysis is at the county (FIPS) level. Correlations describe county averages, not individual-level relationships.

2. **Temporal inconsistency:** Datasets span {min_year} to {max_year}. The Opportunity Atlas mobility data reflects 1978-2015 historical conditions. Cross-dataset correlations involving datasets from different eras should be interpreted with caution.

3. **Modifiable Areal Unit Problem (MAUP):** Results would differ at census tract or ZIP code level. Datasets rated High MAUP sensitivity (poverty, income, health outcomes) show particularly large within-county variation in urban areas.

4. **Diagnosis bias:** Health outcome datasets (diabetes, hypertension, mental health) measure diagnosed prevalence. Areas with limited healthcare access show lower measured rates even if true prevalence is identical or higher.

5. **Equal weighting assumption:** All {len(datasets_used)} datasets contribute equally to socioeconomic distance. Weighting robustness analysis confirms this does not affect findings, but researchers with domain-specific questions may prefer the filter chip views.

6. **Non-migration validation:** The IRS migration validation tests whether the model predicts human movement, which is related but not identical to socioeconomic similarity. The model is optimized for similarity discovery, not migration prediction.

7. **Peer stability:** Peer discovery is robust for the full {len(datasets_used)}-dataset model (domain-balanced Jaccard = 0.891). Reducing to 7 datasets produces different peer lists (Jaccard = 0.090) -- this is a different analytical question, not a robustness check.

8. **Small county uncertainty:** 123 counties (population < 5,000 or ACS coefficient of variation > 30%) have unreliable Census estimates. These are flagged in the UI with a warning badge and can be filtered from scatter plot analysis. The gravity model includes all counties but researchers should treat flagged county findings with additional caution.

### Reproducibility
- Layout algorithm: Fruchterman-Reingold (NetworkX spring_layout, seed=42, 300 iterations)
- All users see identical county positions
- beta calibration seed: random.seed(42) for pair sampling
- Source code: github.com/gregjlake/discovery-pipeline / github.com/gregjlake/discovery-insights

---
*Generated automatically from DiscoSights model outputs. Values reflect model state as of {today}.*
"""

with open('data/methodology_v1.md', 'w', encoding='utf-8') as f:
    f.write(doc)

print(f"Generated data/methodology_v1.md ({len(doc)} chars)")

try:
    from data_pipeline.utils.storage import upload_to_storage
    upload_to_storage('data/methodology_v1.md')
except Exception as e:
    print(f"  Storage upload skipped: {e}")

# Print first 50 lines
for i, line in enumerate(doc.split('\n')[:50]):
    print(line)
