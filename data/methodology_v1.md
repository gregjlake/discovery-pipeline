# DiscoSights Methodology and Validation
## Version 1.0 -- 2026-03-31

### Overview
DiscoSights is a spatial interaction model for exploring socioeconomic similarity among US counties. It applies a gravity model analogy: counties with similar profiles across 18 socioeconomic datasets and smaller geographic distance exert stronger "gravitational attraction" toward each other.

### Data Sources
| Dataset | Label | Source | Data Year | Unit | MAUP Sensitivity |
|---------|-------|--------|-----------|------|------------------|
| air | Air Quality | EPA Air Quality System (AQS) | 2022 | inverted Median AQI (higher = cleaner) | low |
| bea_income | ACS Per Capita Income | US Census Bureau, American Community Survey 5-Year | 2018â€“2022 | per capita personal income ($/year) | low |
| broadband | Broadband Subscription Rate | Census ACS 5-Year, Table B28002 | 2018â€“2022 | household broadband subscription rate | low [proxy] |
| diabetes | Diabetes Rate | CDC PLACES (BRFSS-based) | 2022 | % of adults with diagnosed diabetes | medium [diagnosis bias] |
| eitc | EITC Uptake | IRS Statistics of Income | Tax Year 2022 | EITC returns / total returns filed | medium |
| food_access | SNAP Participation Rate | Census ACS 5-Year, Table B22010 (SNAP proxy â€” not USDA Food Access Atlas) | 2018â€“2022 | % of households receiving SNAP/food stamps | low [proxy] |
| housing_burden | Housing Burden | Census ACS 5-Year, Table B25070 | 2018â€“2022 | % of renters paying 30%+ of income on rent | medium |
| hypertension | Hypertension Rate | CDC PLACES (BRFSS-based) | 2022 | % of adults with high blood pressure | medium [diagnosis bias] |
| library | Library Access | IMLS Public Libraries Survey | FY 2022 | $/capita operating expenditure | low |
| median_income | Median Income | Census SAIPE | 2022 | median household income ($) | low |
| mental_health | Mental Health | CDC PLACES (BRFSS-based) | 2022 | % of adults with frequent mental distress | medium [diagnosis bias] |
| mobility | Economic Mobility | Opportunity Atlas (Chetty et al.) | 1978â€“2015 | mean household income rank at age 35 (percentile) | medium |
| obesity | Obesity Rate | CDC PLACES (BRFSS-based) | 2022 | % of adults with BMI â‰¥ 30 | medium |
| pop_density | Population Density | Census ACS 2022 population + Census Gazetteer land area | 2022 | people per square mile | low |
| poverty | Poverty Rate | Census SAIPE (Small Area Income and Poverty Estimates) | 2022 | % of population below poverty line | low |
| rural_urban | Rural/Urban Classification | USDA Economic Research Service | 2023 | Rural-Urban Continuum Code (1=most urban, 9=most rural) | low |
| unemployment | Unemployment Rate | Census ACS 5-Year, Table B23025 | 2018â€“2022 | % of labor force unemployed | low |
| voter_turnout | Voter Turnout | MIT Election Data + Science Lab | 2020 | total votes cast (presidential election) | low |

Datasets flagged with [proxy] use indirect measurements. Datasets flagged with [diagnosis bias] measure diagnosed prevalence, which underestimates true prevalence in areas with limited healthcare access.

### Gravity Model Formula
```
Force(i,j) = Pop(i) x Pop(j) / dist(i,j)^beta
```

where:
- beta = 0.142157 (empirically calibrated)
- dist(i,j) = geo_norm(i,j) x data_dissimilarity(i,j)
- geo_norm = Haversine distance / max US distance (5,251 mi)
- data_dissimilarity = normalized Euclidean distance across 18 datasets

### beta Calibration
Two-pass calibration procedure:

**Pass 1 (geographic only):**
- beta_geo = 0.050423
- R-squared = 0.039063
- Method: OLS log-linear regression of socioeconomic similarity on geographic distance across 249,922 randomly sampled county pairs

**Pass 2 (combined distance):**
- beta_operative = 0.142157
- R-squared = 0.313088
- Method: Same regression using combined distance (geo x data dissimilarity)

The 8x improvement in R-squared from pass 1 to pass 2 (0.0391 -> 0.3131) confirms that socioeconomic distance adds predictive power beyond geography alone.

### Out-of-Sample Validation
The model was validated against IRS Statistics of Income county-to-county migration flows (tax year 2019-2020, 51,445 county pairs). This data was not used in model calibration.

Spearman rho (predicted force vs observed migration):
- Population only:     0.0405
- + Geographic dist:   0.0515
- + Data similarity:   0.1630

Adding socioeconomic similarity improved migration prediction by +0.112 rho over geography alone -- validating the model's core premise that data similarity carries predictive information beyond physical proximity.

### Weighting Robustness Analysis
Three weighting schemes were tested against IRS migration:

| Scheme | IRS rho | Eff dims | Econ share |
|--------|---------|----------|------------|
| Equal (current) | 0.0728 | 4.90 | 33.3% |
| Domain balanced | 0.0729 | 4.90 | 25.0% |
| PCA 7 components | 0.0720 | 3.11 | 57.1% |

Maximum difference: 0.0009 rho

All schemes produce equivalent predictions and identical county peer-finding results. The model is robust to weighting choice.

### Dataset Structure
PCA analysis of the 18 active datasets:
- Effective dimensions: 4.65 / 18
- Components for 80% variance: 7
- Components for 90% variance: 10

**PC1 (41.8% of variance):**
- Top drivers: diabetes, poverty, eitc, median_income
- Interpretation: Economic deprivation axis

**PC2 (15.0% of variance):**
- Top drivers: housing_burden, rural_urban, mobility, voter_turnout
- Interpretation: Urbanization axis

**High collinearity pairs (|r| > 0.6):**
  - food_access x poverty: r=0.780
  - diabetes x eitc: r=0.765
  - eitc x food_access: r=0.753
  - diabetes x poverty: r=0.737
  - broadband x diabetes: r=-0.701
  - diabetes x median_income: r=-0.700
  - bea_income x eitc: r=-0.684
  - eitc x median_income: r=-0.683
  - diabetes x food_access: r=0.673
  - broadband x median_income: r=0.671
  - hypertension x median_income: r=-0.659
  - broadband x poverty: r=-0.650
  - bea_income x obesity: r=-0.646
  - bea_income x diabetes: r=-0.638
  - bea_income x mental_health: r=-0.638
  - broadband x hypertension: r=-0.635
  - food_access x mental_health: r=0.631
  - eitc x hypertension: r=0.629
  - eitc x mental_health: r=0.629
  - mental_health x poverty: r=0.622
  - bea_income x broadband: r=0.619
  - food_access x unemployment: r=0.614
  - food_access x median_income: r=-0.609

Note: Low effective dimensions reflect genuine structure in US county data -- economic, health, and social outcomes are deeply correlated. This is not a measurement artifact. Weighting robustness analysis confirms it does not distort findings.

### Known Limitations

1. **Ecological fallacy:** All analysis is at the county (FIPS) level. Correlations describe county averages, not individual-level relationships.

2. **Temporal inconsistency:** Datasets span 1978 to 2023. The Opportunity Atlas mobility data reflects 1978-2015 historical conditions. Cross-dataset correlations involving datasets from different eras should be interpreted with caution.

3. **Modifiable Areal Unit Problem (MAUP):** Results would differ at census tract or ZIP code level. Datasets rated High MAUP sensitivity (poverty, income, health outcomes) show particularly large within-county variation in urban areas.

4. **Diagnosis bias:** Health outcome datasets (diabetes, hypertension, mental health) measure diagnosed prevalence. Areas with limited healthcare access show lower measured rates even if true prevalence is identical or higher.

5. **Equal weighting assumption:** All 18 datasets contribute equally to socioeconomic distance. Weighting robustness analysis confirms this does not affect findings, but researchers with domain-specific questions may prefer the filter chip views.

6. **Non-migration validation:** The IRS migration validation tests whether the model predicts human movement, which is related but not identical to socioeconomic similarity. The model is optimized for similarity discovery, not migration prediction.

### Reproducibility
- Layout algorithm: Fruchterman-Reingold (NetworkX spring_layout, seed=42, 300 iterations)
- All users see identical county positions
- beta calibration seed: random.seed(42) for pair sampling
- Source code: github.com/gregjlake/discovery-pipeline / github.com/gregjlake/discovery-insights

---
*Generated automatically from DiscoSights model outputs. Values reflect model state as of 2026-03-31.*
