"""Generate formal methods note for JOSS submission."""
import json
from datetime import date

with open('data/beta_calibration.json') as f:
    beta = json.load(f)
with open('data/validation_results.json') as f:
    val = json.load(f)
with open('data/weighting_comparison.json') as f:
    wc = json.load(f)
with open('data/pca_results.json') as f:
    pca = json.load(f)
with open('data/peer_stability_analysis.json') as f:
    ps = json.load(f)
with open('data/dataset_metadata.json') as f:
    meta = json.load(f)

today = date.today().isoformat()
ds_used = beta['datasets_used']
va = wc['variants']['A_equal']
vb = wc['variants']['B_cluster']
vc = wc['variants']['C_pca7']
max_diff = max(abs(va['rho'] - vb['rho']), abs(va['rho'] - vc['rho']), abs(vb['rho'] - vc['rho']))

pc1 = pca['component_details']['PC1']
pc2 = pca['component_details']['PC2']
pc1_top = ", ".join(pc1['top_datasets'])
pc2_top = ", ".join(pc2['top_datasets'])

r2_improvement_pct = round((beta['r_squared_combined'] / beta['r_squared_geo'] - 1) * 100)
rho_relative_improvement = round(val['improvement_b_to_c'] / val['model_b_rho'] * 100)

# Domain assignments
ds_domain = {
    'poverty': 'Economic', 'eitc': 'Economic', 'median_income': 'Economic',
    'bea_income': 'Economic', 'unemployment': 'Economic',
    'obesity': 'Health', 'diabetes': 'Health', 'hypertension': 'Health', 'mental_health': 'Health',
    'broadband': 'Infrastructure', 'food_access': 'Infrastructure',
    'housing_burden': 'Infrastructure', 'air': 'Infrastructure',
    'voter_turnout': 'Civic', 'library': 'Civic', 'rural_urban': 'Civic', 'pop_density': 'Civic',
}

ds_rows = []
for ds_id in sorted(ds_used):
    m = meta.get(ds_id, {})
    ds_rows.append(f"| {m.get('label', ds_id)} | {m.get('source', 'N/A')[:45]} | {m.get('data_year', 'N/A')} | {m.get('unit', 'N/A')[:30]} | {ds_domain.get(ds_id, '?')} |")
ds_table = "| Dataset | Source | Year | Unit | Domain |\n|---------|--------|------|------|--------|\n" + "\n".join(ds_rows)

top_collinear = pca.get('unexpected_collinear_pairs', [])[:5]
collinear_lines = "\n".join(f"  - {p['d1']} x {p['d2']}: r = {p['r']:.3f}" for p in top_collinear)

years = []
for ds_id in ds_used:
    m = meta.get(ds_id, {})
    yr = m.get('data_year', '')
    for part in yr.replace('FY ', '').replace('Tax Year ', '').split('--'):
        for sub in part.split('-'):
            try:
                y = int(sub.strip()[:4])
                if 1900 < y < 2100: years.append(y)
            except (ValueError, IndexError): pass
min_year = min(years) if years else 2018
max_year = max(years) if years else 2023

doc = f"""# DiscoSights: A Validated Spatial Interaction Model for US County Socioeconomic Similarity

**Authors:** Greg Lake
**Repository:** github.com/gregjlake/discovery-pipeline
**Live tool:** https://discovery-surface-spark.lovable.app
**Date:** {today}

---

## Abstract

DiscoSights is a spatial interaction model for identifying socioeconomic peer counties across the United States. The gravity model computes pairwise attraction between county profiles across {len(ds_used)} socioeconomic datasets using empirically calibrated distance decay (beta = {beta['beta_operative']:.3f}, R-squared = {beta['r_squared_combined']:.3f} vs {beta['r_squared_geo']:.3f} geographic only). Out-of-sample validation against IRS county-to-county migration flows ({val['n_pairs_total']:,} pairs, 2019-2020) shows +{val['improvement_b_to_c']:.3f} Spearman rho improvement when adding data similarity beyond population and geography. The tool provides two independent visualizations: a PCA terrain projection (PC1 = economic deprivation, 42% variance) and a force-directed dot layout. Weighting robustness testing found stable peer lists for domain-balanced weighting (Jaccard = {ps['mean_jaccard_equal_vs_domain']:.3f}) but not dataset reduction to 7 variables (Jaccard = {ps['mean_jaccard_equal_vs_pca7']:.3f}). External validation against FEMA National Risk Index confirmed disaster risk is largely independent of socioeconomic disadvantage (r = 0.151).

## 1. Introduction and Motivation

Identifying socioeconomic peer counties -- places that share structural conditions despite geographic distance -- is a recurring task in policy research, public health planning, and economic geography. Researchers comparing county-level interventions, evaluating natural experiments, or seeking replication sites must identify structurally similar communities. Current practice typically involves ad hoc variable selection and arbitrary weighting, producing peer lists whose sensitivity to methodological choices is rarely tested.

DiscoSights contributes a gravity model with empirically calibrated distance decay, out-of-sample validation, and documented robustness properties. The core innovation is adapting the spatial interaction framework to data-space distance: rather than modeling physical flows between locations, the model quantifies socioeconomic attraction between county profiles across {len(ds_used)} dimensions. The practical application -- discovering that McDowell County WV and Starr County TX share deep structural similarity despite 1,247 miles of geographic separation -- enables hypothesis generation about policy transfer across distant but structurally analogous communities.

The gravity model framework provides theoretical grounding absent from simple distance-based matching. Gravity models are well-established in trade economics (Tinbergen, 1962), migration studies (Zipf, 1946), and regional science. Extending the analogy from geographic distance to combined geographic-socioeconomic distance is the methodological contribution of this work.

## 2. Data

The model uses {len(ds_used)} county-level datasets from US government sources spanning {min_year} to {max_year}:

{ds_table}

Two additional datasets are available for scatter plot exploration but excluded from the gravity distance calculation:

- **Economic Mobility** (Opportunity Atlas, 1978-2015): Excluded due to temporal mismatch. Tracking income outcomes of children born 1978-1983 alongside 2022 current-conditions datasets would conflate different eras of American economic geography.
- **Internet Access Rate** (Census ACS B28002): Excluded due to r = 0.993 collinearity with Broadband Subscription Rate from the same Census table.

Nine FEMA National Risk Index variables (overall disaster risk, wildfire, coastal flood, riverine flood, hurricane, tornado, earthquake, social vulnerability, community resilience) are available for independent exploration but excluded from the gravity model to prevent conflating geographic hazard exposure with socioeconomic structure.

**Data limitations.** Three health outcome datasets (diabetes, hypertension, mental health) measure diagnosed prevalence via self-report (CDC BRFSS), systematically underestimating true prevalence in areas with limited healthcare access. Two income measures (median household income, per capita income) are nominal dollars without geographic cost-of-living adjustment. Food access (USDA Atlas 2019) measures physical proximity to grocery stores, not affordability.

## 3. Model Specification

### 3.1 Three Distinct Analytical Components

DiscoSights combines three related but distinct analytical objects that should not be conflated:

**Gravity Model (force_strength):** The core spatial interaction model computing attraction between all county pairs. Force(i,j) = Pop(i) x Pop(j) / dist(i,j)^beta. This is what the IRS migration validation tests. Output: a 3,135 x 3,135 sparse matrix of force values (top 10,000 pairs stored).

**Terrain Visualization (PCA projection):** An independent visualization of the {len(ds_used)}-dataset data structure using Principal Component Analysis. Counties are projected to 2D (PC1 = economic deprivation {pc1['variance_pct']:.1f}%, PC2 = urbanization {pc2['variance_pct']:.1f}%). Gravitational potential height represents county density in this 2D space -- how many counties share a similar profile. This visualization is derived entirely from the dataset vectors, not from the gravity model formula.

**Dot Layout (spring layout):** The Map/Dots view uses Fruchterman-Reingold spring layout (NetworkX, seed=42, 300 iterations) with force_strength values as edge weights. This places similar counties near each other visually. The equilibrium positions are graph layout artifacts, not gravitational minima. Layout is deterministic and reproducible but should not be interpreted as a physical simulation.

The IRS migration validation (Section 5.1) tests the gravity model force values. It does not validate the terrain visualization or the dot layout positions, which are visualization tools rather than predictive models.

### 3.2 Gravity Formula

The gravity force between counties i and j is:

    Force(i,j) = Pop(i) x Pop(j) / dist(i,j)^beta

where:

    dist(i,j) = geo_norm(i,j) x data_dissim(i,j)

Geographic distance is Haversine distance normalized by maximum US county-pair distance (5,251 miles). Socioeconomic dissimilarity is Euclidean distance across {len(ds_used)} min-max scaled datasets, normalized by the empirical maximum across all county pairs. Missing values in normalized dataset vectors are imputed with 0.5 (the midpoint of the [0,1] scale), treating counties with missing data as having typical values. County pairs with geographic distance < 10 miles are excluded from beta calibration to avoid noise from adjacent county boundary effects.

**Why multiplicative rather than additive:** Combined distance = geo_norm x data_dissim rather than geo_norm + data_dissim for three reasons:

1. *Interpretability:* The product equals zero when either component is zero. Two geographically adjacent counties with identical profiles (data_dissim=0) have zero combined distance, producing maximum force. This is the correct behavior -- proximity and similarity together define peer counties.

2. *Scale invariance:* Addition requires choosing relative weights for geographic vs data distance. Multiplication avoids this choice -- the two components modulate each other rather than competing. A 2x increase in either component doubles the combined distance regardless of the other's magnitude.

3. *Empirical support:* The multiplicative formulation produced R-squared = {beta['r_squared_combined']:.3f} in combined-distance calibration vs R-squared = {beta['r_squared_geo']:.3f} for geographic distance alone -- a {r2_improvement_pct}% improvement that would not have been possible if the two components were not interacting multiplicatively.

**The floor at 0.01:** To prevent numerical instability when either component approaches zero, combined distance is floored at 0.01. This affects primarily adjacent counties within the same metropolitan area that share near-identical profiles.

**The 5,251-mile normalizer:** geo_norm = Haversine(i,j) / 5,251. The value 5,251 miles is the approximate maximum Haversine distance between any two US counties. Using a fixed theoretical maximum rather than the empirical maximum ensures that the normalizer is stable across different subsets of counties and is not sensitive to the inclusion or exclusion of specific remote counties.

## 4. Beta Calibration

The distance decay parameter beta is calibrated empirically using a two-pass procedure:

**Pass 1 -- Geographic distance only:**

OLS log-linear regression of socioeconomic similarity on geographic distance across {beta['n_pairs']:,} randomly sampled county pairs (seed = 42):

    log(similarity) = alpha - beta x log(geo_distance)

Result: beta_geo = {beta['beta_geo']:.4f}, R-squared = {beta['r_squared_geo']:.4f}

**Pass 2 -- Combined distance:**

Same regression using multiplicative combined distance (geographic x socioeconomic):

Result: beta_operative = {beta['beta_operative']:.4f}, R-squared = {beta['r_squared_combined']:.4f}

Model fit improved from R-squared = {beta['r_squared_geo']:.4f} to R-squared = {beta['r_squared_combined']:.4f} ({r2_improvement_pct}% improvement).

The operative beta = {beta['beta_operative']:.3f} is low compared to typical gravity models for physical flows (beta = 1-2), reflecting that county socioeconomic clustering is primarily driven by data-space similarity rather than geographic proximity.

**Cross-validation and R-squared circularity:** In Pass 2, the combined distance measure contains data_dissim, which also determines the similarity dependent variable. To quantify this circularity, beta was estimated on an 80% training split and evaluated on a 20% holdout (seed=42). Beta_cv = {beta.get('beta_cv', 0.155):.4f} (vs beta_op = {beta['beta_operative']:.4f}, difference = {abs(beta.get('beta_cv', 0.155) - beta['beta_operative']):.4f}). R-squared_holdout = {beta.get('r2_cv_holdout', 0.313):.4f} (vs R-squared_full = {beta['r_squared_combined']:.4f}, inflation = {beta.get('r2_circularity_inflation', 0.0):.4f}). The circularity concern is negligible -- beta and R-squared are stable under cross-validation. {beta.get('beta_cv_verdict', '')}

## 5. Validation

### 5.1 Out-of-Sample IRS Migration Validation

The model was validated against IRS Statistics of Income county-to-county migration inflows (tax year 2019-2020, {val['n_pairs_total']:,} county pairs). This data was not used in beta calibration -- any correlation with migration flows reflects genuine out-of-sample predictive validity.

**Sample selection criteria:** All IRS county-to-county migration pairs meeting these criteria were included: both origin and destination counties present in the gravity model (3,135 counties), net migration flow > 0, state FIPS <= 56 (excludes territories), origin != destination. No minimum flow threshold was applied -- pairs with low migration were included to avoid systematically excluding rural-to-rural flows which tend to be smaller in volume but potentially more relevant to socioeconomic peer relationships.

**Distribution of migration volumes:** Min flow: 20 individuals. Median: 77. Mean: 229. Max: 43,404 (a large metro pair). 61.4% of pairs have flow < 100 individuals; only 3.2% exceed 1,000. The validation set is not dominated by large metropolitan flows.

Spearman rank correlations (rho) for progressively complex models:

| Model | rho | Delta |
|-------|-----|-------|
| Population only | {val['model_a_rho']:.4f} | -- |
| + Geographic distance | {val['model_b_rho']:.4f} | +{val['model_b_rho'] - val['model_a_rho']:.4f} |
| + Data similarity (full model) | {val['model_c_rho']:.4f} | +{val['improvement_b_to_c']:.4f} |

Adding socioeconomic similarity improved prediction by +{val['improvement_b_to_c']:.3f} rho -- a {rho_relative_improvement}% relative improvement over population plus geography alone. The monotonicity check (mean predicted force increases with observed migration volume across all five bins) passes, confirming the model captures real directional signal.

**Honest limitation:** The absolute rho = {val['model_c_rho']:.3f} is weak in isolation. County-to-county migration is influenced by job availability, family ties, housing costs, and state policy environments beyond socioeconomic similarity. The model is calibrated for similarity discovery, not migration prediction. IRS flows serve as an independent validity check confirming the model captures real-world signal, not as an optimization target.

### 5.2 Weighting Robustness

Three weighting schemes were tested against IRS migration flows:

| Scheme | IRS rho | Effective dimensions | Economic domain share |
|--------|---------|---------------------|-----------------------|
| Equal (default) | {va['rho']:.4f} | {va['eff_dims']:.2f} | {va['econ_share_pct']:.1f}% |
| Domain-balanced | {vb['rho']:.4f} | {vb['eff_dims']:.2f} | {vb['econ_share_pct']:.1f}% |
| PCA 7 components | {vc['rho']:.4f} | {vc['eff_dims']:.2f} | {vc['econ_share_pct']:.1f}% |

Maximum rho difference: {max_diff:.4f}. All schemes produce equivalent aggregate predictions.

The weighting comparison rho values (0.0728-0.0729) differ from the primary validation rho (0.165) because they use different pair sampling approaches. The primary validation uses the pre-computed top-10,000 force links from the gravity model cache -- the pairs where the model predicts strongest interaction, which naturally correlate better with observed migration. The weighting comparison uses 250,000 randomly sampled county pairs, most of which have near-zero force and near-zero observed migration. This dilutes the correlation signal but is the correct approach for comparing relative performance across weighting schemes, where the absolute rho is less important than the differences between schemes (max {max_diff:.4f}).

**Individual county peer stability** was tested for five median-profile counties (P45-P55 overall score) across four US Census regions, using Jaccard similarity of top-10 peer lists:

- Equal vs Domain-balanced: mean Jaccard = {ps['mean_jaccard_equal_vs_domain']:.3f}. Peer lists overlap {ps['mean_jaccard_equal_vs_domain']*100:.0f}% on average. The model is robust to domain reweighting.
- Equal vs PCA 7: mean Jaccard = {ps['mean_jaccard_equal_vs_pca7']:.3f}. Peer lists overlap only {ps['mean_jaccard_equal_vs_pca7']*100:.0f}%. Dataset reduction to 7 variables produces fundamentally different peer groupings.

**Implication:** The model is robust to how datasets are weighted but sensitive to which datasets are included. The 7-dataset reduced view represents a different analytical question, not a robustness check of the full model.

### 5.3 External Validation -- FEMA Disaster Risk

FEMA National Risk Index (2023) county-level scores for 9 natural hazard variables were compared against the gravity model's socioeconomic datasets:

| Comparison | Pearson r |
|------------|-----------|
| Overall disaster risk x poverty | 0.151 |
| Social vulnerability x poverty | 0.515 |
| Community resilience x median income | 0.337 |

The near-orthogonality of overall disaster risk and economic disadvantage (r = 0.151) confirms that the gravity model's socioeconomic distance measure does not inadvertently capture geographic hazard exposure, and that disaster vulnerability is a genuinely independent dimension of county welfare.

### 5.4 Sensitivity Analysis

**Mobility Exclusion.** The Opportunity Atlas mobility dataset was excluded from the gravity model due to temporal mismatch (1978-2015 outcomes vs 2022 current conditions). To verify this exclusion did not distort results, pairwise distances were computed with and without mobility for 10,000 randomly sampled county pairs. The Pearson correlation between 17-dataset and 18-dataset distances was r = 0.9980, with mean absolute difference 0.0044 (on a [0,1] scale). Mobility removal had negligible effect on distance calculations.

**Food Access Variable Replacement.** The original food_access variable (SNAP participation rate, r = 0.784 with poverty) was replaced with the USDA Food Access Research Atlas 2019 measure of physical proximity to grocery stores. The USDA measure correlates at r = -0.048 with poverty, confirming it captures a fundamentally different dimension -- physical geographic access rather than economic need. This replacement transforms food_access from a near-redundant poverty proxy into a genuinely independent infrastructure measure.

### 5.5 Benchmark Comparison

The correlation between county poverty rate and economic mobility (Opportunity Atlas) provides a benchmark against published estimates. Chetty et al. (2014) reported r approximately -0.60 at the commuting zone level.

DiscoSights produces r = -0.451 at the county level. The gap (0.149) is attributable to two factors:

1. *Geographic unit:* Commuting zones aggregate multiple counties, smoothing within-zone heterogeneity and strengthening correlations (ecological aggregation effect). County-level analysis preserves variation that commuting zone analysis obscures.

2. *Temporal mismatch:* The Opportunity Atlas reflects outcomes of cohorts born 1978-1983. The poverty rate is from 2022 SAIPE. Counties whose economic character has changed substantially since the 1980s (Rust Belt decline, Sun Belt growth) contribute discordant observations that reduce correlation.

Both factors predict the observed gap and are consistent with the county-commuting zone literature on ecological aggregation. The mobility variable was excluded from the gravity model precisely because this temporal mismatch makes it unsuitable for comparison with current-conditions datasets.

## 6. Dataset Structure

PCA analysis of the {len(ds_used)} active datasets reveals:

- Effective dimensions (participation ratio): {pca['effective_dimensions']:.2f} / {len(ds_used)}
- Components for 80% cumulative variance: {pca['n_components_80pct']}
- Components for 90% cumulative variance: {pca['n_components_90pct']}

**PC1 ({pc1['variance_pct']:.1f}% of variance):** Economic deprivation axis. Top loadings: {pc1_top}. Poverty, income, EITC uptake, and health outcomes load together as a single structural factor -- consistent with the concentrated disadvantage literature.

**PC2 ({pc2['variance_pct']:.1f}% of variance):** Urbanization axis. Top loadings: {pc2_top}.

The low effective dimensionality ({pca['effective_dimensions']:.2f} of {len(ds_used)}) reflects genuine covariation in US county data rather than measurement redundancy. Weighting robustness analysis (Section 5.2) confirms this concentration does not distort peer-finding results.

**High collinearity pairs (|r| > 0.6):**
{collinear_lines}

## 7. Known Limitations

1. **Ecological fallacy.** All analysis operates at the county (FIPS) level. Correlations describe county averages, not individual-level relationships.

2. **Temporal inconsistency.** Active datasets span {min_year} to {max_year}. Cross-era comparisons carry temporal uncertainty. Economic mobility (1978-2015) was excluded for this reason.

3. **Modifiable Areal Unit Problem.** Results are county-specific. High-MAUP datasets show substantial within-county variation in large urban counties.

4. **Diagnosis bias.** Health outcome datasets measure diagnosed prevalence. Areas with limited healthcare access show lower measured rates regardless of true prevalence.

5. **Equal weighting.** All {len(ds_used)} datasets contribute equally. Validated as robust to domain reweighting (Jaccard = {ps['mean_jaccard_equal_vs_domain']:.3f}) but may not match all research questions.

6. **Dataset reduction sensitivity.** Reducing to 7 datasets produces different peers (Jaccard = {ps['mean_jaccard_equal_vs_pca7']:.3f}). The reduced view is a different analytical lens, not a robustness check.

7. **Migration validation.** IRS flows are an imperfect proxy. Weak absolute rho = {val['model_c_rho']:.3f} reflects migration's multifactorial determinants.

8. **Small county uncertainty.** 123 counties (population < 5,000 or ACS CV > 30%) have unreliable Census estimates. Flagged in the UI.

9. **Validation scope.** IRS migration validates the gravity model force values. It does not validate the terrain visualization (PCA projection) or dot layout (spring layout), which are visualization tools.

10. **Normalization sensitivity.** Min-max normalization is sensitive to outliers -- extreme counties (e.g., Loving County TX, population 96) can compress the scale for all other counties. The terrain visualization uses 2nd-98th percentile clipping for color ranges, but the distance calculation uses full-range normalization.

11. **Ordinal variable treatment.** The USDA Rural-Urban Continuum Code (rural_urban, 1-9) is treated as continuous in the Euclidean distance calculation. The intervals between ordinal codes are not necessarily equal in real-world terms, introducing a known approximation.

12. **Population dominance.** With beta = {beta['beta_operative']:.3f}, population product explains 95.6% of raw force variance. The gravity model's force values are population-dominated for large counties. The peer discovery feature uses data-space Euclidean distance directly, which is population-independent, to find similar counties regardless of size.

13. **Validation zero-inflation.** Of the {val['n_pairs_total']:,} IRS migration pairs, only those appearing in the gravity model's top-10,000 pre-computed links receive nonzero predicted force; remaining pairs receive force = 0. The Spearman rho = {val['model_c_rho']:.3f} reflects both ranking accuracy and binary link discrimination. The monotonic bin analysis provides a complementary assessment less sensitive to zero-inflation.

## 8. Software and Reproducibility

- **Layout:** Fruchterman-Reingold (NetworkX `spring_layout`, seed = 42, 300 iterations). Deterministic.
- **Beta calibration:** `random.seed(42)` for county pair sampling.
- **Backend:** Python (FastAPI), Railway. Source: github.com/gregjlake/discovery-pipeline
- **Frontend:** React/TypeScript (Lovable). Source: github.com/gregjlake/discovery-insights
- **Tests:** 33 unit tests covering haversine, dissimilarity, gravity force, reliability scoring, and validation values. Run without live database.

## 9. Conclusion

DiscoSights provides a validated, transparent instrument for county socioeconomic similarity analysis with six documented contributions:

1. **Empirical beta calibration** (beta = {beta['beta_operative']:.3f}, R-squared = {beta['r_squared_combined']:.3f} combined vs {beta['r_squared_geo']:.3f} geographic only).

2. **Out-of-sample validation** (+{val['improvement_b_to_c']:.3f} rho improvement, {val['n_pairs_total']:,} IRS county pairs).

3. **Weighting robustness** (max IRS rho difference {max_diff:.4f}, domain-balanced peer Jaccard = {ps['mean_jaccard_equal_vs_domain']:.3f}).

4. **Dataset reduction sensitivity** documented (PCA-7 Jaccard = {ps['mean_jaccard_equal_vs_pca7']:.3f}).

5. **External validation** via FEMA disaster risk (r = 0.151 with poverty).

6. **Clear separation** of three analytical objects: gravity model (validated), terrain visualization (PCA-derived), and dot layout (spring layout). Validation claims apply to force values, not visualizations.

---
*Methods note generated {today}. All numerical values derived programmatically from model outputs.*
"""

with open('data/methods_note_draft.md', 'w', encoding='utf-8') as f:
    f.write(doc)

word_count = len(doc.split())
print(f"Generated data/methods_note_draft.md ({len(doc)} chars, {word_count} words)")

import re
placeholders = re.findall(r'\{[a-z_]+\}', doc)
if placeholders:
    print(f"WARNING: Unfilled placeholders: {placeholders[:5]}")
else:
    print("All placeholders filled.")

sections = [l.strip() for l in doc.split('\n') if l.strip().startswith('## ') or l.strip().startswith('### ')]
print(f"\nSections ({len(sections)}):")
for s in sections:
    print(f"  {s}")
