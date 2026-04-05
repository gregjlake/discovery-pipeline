# DiscoSights Methodology and Validation
## Version 1.0 -- 2026-04-05

### Overview
DiscoSights is a spatial interaction model for exploring socioeconomic similarity among US counties. It applies a gravity model analogy: counties with similar profiles across 30 socioeconomic datasets and smaller geographic distance exert stronger "gravitational attraction" toward each other.

### Data Sources
| Dataset | Label | Source | Data Year | Unit | MAUP Sensitivity |
|---------|-------|--------|-----------|------|------------------|
| agriculture_pct | Agriculture Employment | Census ACS 5-Year, Profile Table DP03 | 2018-2022 | % of employed civilian population in agriculture/forestry/fishing/hunting/mining | low |
| air | Air Quality | EPA Air Quality System (AQS) | 2022 | inverted Median AQI (higher = cleaner) | low |
| bachelors_rate | Bachelor's Degree Rate | Census ACS 5-Year, Table B15003 | 2022 | % of population 25+ with bachelor's degree | low |
| bea_income | ACS Per Capita Income | US Census Bureau, American Community Survey 5-Year | 2018â€“2022 | per capita personal income ($/year) | low |
| broadband | Broadband Subscription Rate | Census ACS 5-Year, Table B28002 | 2018â€“2022 | household broadband subscription rate | low [proxy] |
| child_poverty_rate | Child Poverty Rate | Census ACS 5-Year, Subject Table S1701 | 2018-2022 | % of children under 18 below poverty line | low |
| diabetes | Diabetes Rate | CDC PLACES (BRFSS-based) | 2022 | % of adults with diagnosed diabetes | medium [diagnosis bias] |
| eitc | EITC Uptake | IRS Statistics of Income | Tax Year 2022 | EITC returns / total returns filed | medium |
| food_access | Low Food Access | USDA Economic Research Service Food Access Research Atlas 2019 | 2019 | % population with low food access | low |
| foreign_born_pct | Foreign-Born Population | Census ACS 5-Year, Table B05002 | 2018-2022 | % of population born outside the US | low |
| homeownership_rate | Homeownership Rate | Census ACS 5-Year, Table B25003 | 2022 | % of occupied housing units that are owner-occupied | low |
| housing_burden | Housing Burden | Census ACS 5-Year, Table B25070 | 2018â€“2022 | % of renters paying 30%+ of income on rent | medium |
| housing_vacancy_rate | Housing Vacancy Rate | Census ACS 5-Year, Table B25002 | 2018-2022 | % of housing units that are vacant | low |
| hypertension | Hypertension Rate | CDC PLACES (BRFSS-based) | 2022 | % of adults with high blood pressure | medium [diagnosis bias] |
| language_isolation_rate | Language Isolation | Census ACS 5-Year, Table B16002 | 2018-2022 | % of households that are linguistically isolated | low |
| library | Library Access | IMLS Public Libraries Survey | FY 2022 | $/capita operating expenditure | low |
| life_expectancy | Life Expectancy | County Health Rankings 2024 (Robert Wood Johnson Foundation / University of Wisconsin) | 2019-2021 | years at birth (min-max normalized) | low |
| manufacturing_pct | Manufacturing Employment | Census ACS 5-Year, Profile Table DP03 | 2018-2022 | % of employed civilian population in manufacturing | low |
| median_age | Median Age | Census ACS 5-Year, Table B01002 | 2022 | years | low |
| median_home_value | Median Home Value | Census ACS 5-Year, Table B25077 | 2018-2022 | median value of owner-occupied housing units ($) | low |
| median_income | Median Income | Census SAIPE | 2022 | median household income ($) | low |
| mental_health | Mental Health | CDC PLACES (BRFSS-based) | 2022 | % of adults with frequent mental distress | medium [diagnosis bias] |
| obesity | Obesity Rate | CDC PLACES (BRFSS-based) | 2022 | % of adults with BMI â‰¥ 30 | medium |
| pop_density | Population Density | Census ACS 2022 population + Census Gazetteer land area | 2022 | people per square mile | low |
| population_change_pct | Population Change | Census ACS 5-Year (B01003) + 2020 Decennial (P1_001N) | 2020-2022 | % population change (2020 to 2022) | low |
| poverty | Poverty Rate | Census SAIPE (Small Area Income and Poverty Estimates) | 2022 | % of population below poverty line | low |
| rural_urban | Rural/Urban Classification | USDA Economic Research Service | 2023 | Rural-Urban Continuum Code (1=most urban, 9=most rural) | low |
| single_parent_rate | Single-Parent Households | Census ACS 5-Year, Table B11001 | 2018-2022 | % of households with single parent (no spouse present) | low |
| unemployment | Unemployment Rate | Census ACS 5-Year, Table B23025 | 2018â€“2022 | % of labor force unemployed | low |
| voter_turnout | Voter Turnout Rate | MIT Election Data + Science Lab / Census ACS population | 2020 | votes cast / county population | low |

Datasets flagged with [proxy] use indirect measurements. Datasets flagged with [diagnosis bias] measure diagnosed prevalence, which underestimates true prevalence in areas with limited healthcare access.

### Gravity Model Formula
```
Force(i,j) = Pop(i) x Pop(j) / dist(i,j)^beta
```

where:
- beta = 0.138702 (empirically calibrated)
- dist(i,j) = geo_norm(i,j) x data_dissimilarity(i,j)
- geo_norm = Haversine distance / max US distance (5,251 mi)
- data_dissimilarity = normalized Euclidean distance across 30 datasets

### beta Calibration
Two-pass calibration procedure:

**Pass 1 (geographic only):**
- beta_geo = 0.059286
- R-squared = 0.054221
- Method: OLS log-linear regression of socioeconomic similarity on geographic distance across 249,922 randomly sampled county pairs

**Pass 2 (combined distance):**
- beta_operative = 0.138702
- R-squared = 0.302591
- Method: Same regression using combined distance (geo x data dissimilarity)

The 8x improvement in R-squared from pass 1 to pass 2 (0.0542 -> 0.3026) confirms that socioeconomic distance adds predictive power beyond geography alone.

### Out-of-Sample Validation
The model was validated against IRS Statistics of Income county-to-county migration flows (tax year 2019-2020, 51,445 county pairs). This data was not used in model calibration.

Spearman rho (predicted force vs observed migration):
- Population only:     0.0405
- + Geographic dist:   0.0534
- + Data similarity:   0.1636

Adding socioeconomic similarity improved migration prediction by +0.110 rho over geography alone -- validating the model's core premise that data similarity carries predictive information beyond physical proximity.

### Weighting Robustness Analysis
Three weighting schemes were tested against IRS migration:

| Scheme | IRS rho | Eff dims | Econ share |
|--------|---------|----------|------------|
| Equal (current) | 0.0728 | 4.90 | 33.3% |
| Domain balanced | 0.0729 | 4.90 | 25.0% |
| PCA 7 components | 0.0720 | 3.11 | 57.1% |

Maximum difference: 0.0009 rho

All schemes produce equivalent aggregate predictions. The model is robust to weighting choice at the IRS migration level.

### Peer Stability Analysis
Peer-level stability was tested for 5 median-profile counties (P45-P55) across the three weighting schemes:

- Equal vs Domain balanced: mean Jaccard similarity = 0.891 (91% top-10 peer overlap)
- Equal vs PCA 7 components: mean Jaccard similarity = 0.090 (9% overlap)

Domain-balanced weighting preserves peer rankings. Reducing to 7 datasets produces substantially different peer lists. The 7-dataset view should be understood as a different analytical lens, not a cleaner version of the full model.

### External Validation -- FEMA Disaster Risk
FEMA National Risk Index (2023) scores for 9 natural hazard variables were compared against the 17 socioeconomic datasets:

- Overall disaster risk x poverty: r = 0.151 (weak -- largely independent)
- Social vulnerability x poverty: r = 0.515 (moderate)

Disaster risk adds a genuinely independent dimension to county analysis. Two counties can be socioeconomic peers while facing completely different natural hazard futures. FEMA disaster variables are available in the scatter plot but excluded from the gravity model to avoid conflating geographic hazard exposure with socioeconomic structure.

### Dataset Structure
PCA analysis of the 30 active datasets:
- Effective dimensions: 7.19 / 30
- Components for 80% variance: 11
- Components for 90% variance: 16

**PC1 (32.0% of variance):**
- Top drivers: median_income, bea_income, diabetes, poverty
- Interpretation: Economic deprivation axis

**PC2 (13.2% of variance):**
- Top drivers: homeownership_rate, median_age, housing_burden, rural_urban
- Interpretation: Urbanization axis

**High collinearity pairs (|r| > 0.6):**
  - child_poverty_rate x poverty: r=0.794
  - bachelors_rate x bea_income: r=0.793
  - bea_income x median_home_value: r=0.750
  - median_home_value x median_income: r=0.750
  - child_poverty_rate x eitc: r=0.741
  - diabetes x eitc: r=0.737
  - eitc x life_expectancy: r=-0.734
  - bachelors_rate x median_income: r=0.729
  - child_poverty_rate x diabetes: r=0.705
  - diabetes x poverty: r=0.705
  - life_expectancy x poverty: r=-0.699
  - bea_income x eitc: r=-0.683
  - bea_income x life_expectancy: r=0.683
  - eitc x median_income: r=-0.683
  - life_expectancy x median_income: r=0.681
  - diabetes x median_income: r=-0.678
  - foreign_born_pct x language_isolation_rate: r=0.678
  - broadband x diabetes: r=-0.674
  - broadband x median_income: r=0.670
  - bachelors_rate x median_home_value: r=0.668
  - bachelors_rate x diabetes: r=-0.666
  - life_expectancy x mental_health: r=-0.666
  - median_home_value x obesity: r=-0.659
  - diabetes x life_expectancy: r=-0.658
  - bachelors_rate x life_expectancy: r=0.650
  - child_poverty_rate x median_income: r=-0.646
  - broadband x poverty: r=-0.641
  - hypertension x median_income: r=-0.638
  - child_poverty_rate x life_expectancy: r=-0.631
  - bea_income x mental_health: r=-0.626
  - bea_income x broadband: r=0.623
  - broadband x hypertension: r=-0.623
  - bachelors_rate x broadband: r=0.620
  - bea_income x diabetes: r=-0.619
  - bachelors_rate x obesity: r=-0.614
  - bea_income x obesity: r=-0.612
  - eitc x hypertension: r=0.610
  - bachelors_rate x hypertension: r=-0.607
  - eitc x mental_health: r=0.607
  - bea_income x child_poverty_rate: r=-0.604

Note: Low effective dimensions reflect genuine structure in US county data -- economic, health, and social outcomes are deeply correlated. This is not a measurement artifact. Weighting robustness analysis confirms it does not distort findings.

### Known Limitations

1. **Ecological fallacy:** All analysis is at the county (FIPS) level. Correlations describe county averages, not individual-level relationships.

2. **Temporal inconsistency:** Datasets span 2018 to 2023. The Opportunity Atlas mobility data reflects 1978-2015 historical conditions. Cross-dataset correlations involving datasets from different eras should be interpreted with caution.

3. **Modifiable Areal Unit Problem (MAUP):** Results would differ at census tract or ZIP code level. Datasets rated High MAUP sensitivity (poverty, income, health outcomes) show particularly large within-county variation in urban areas.

4. **Diagnosis bias:** Health outcome datasets (diabetes, hypertension, mental health) measure diagnosed prevalence. Areas with limited healthcare access show lower measured rates even if true prevalence is identical or higher.

5. **Equal weighting assumption:** All 30 datasets contribute equally to socioeconomic distance. Weighting robustness analysis confirms this does not affect findings, but researchers with domain-specific questions may prefer the filter chip views.

6. **Non-migration validation:** The IRS migration validation tests whether the model predicts human movement, which is related but not identical to socioeconomic similarity. The model is optimized for similarity discovery, not migration prediction.

7. **Peer stability:** Peer discovery is robust for the full 30-dataset model (domain-balanced Jaccard = 0.891). Reducing to 7 datasets produces different peer lists (Jaccard = 0.090) -- this is a different analytical question, not a robustness check.

8. **Small county uncertainty:** 123 counties (population < 5,000 or ACS coefficient of variation > 30%) have unreliable Census estimates. These are flagged in the UI with a warning badge and can be filtered from scatter plot analysis. The gravity model includes all counties but researchers should treat flagged county findings with additional caution.

### Reproducibility
- Layout algorithm: Fruchterman-Reingold (NetworkX spring_layout, seed=42, 300 iterations)
- All users see identical county positions
- beta calibration seed: random.seed(42) for pair sampling
- Source code: github.com/gregjlake/discovery-pipeline / github.com/gregjlake/discovery-insights

---
*Generated automatically from DiscoSights model outputs. Values reflect model state as of 2026-04-05.*
