---
title: 'DiscoveryLens: A Configurable County Similarity and Correlation Explorer for US Policy Research'
tags:
  - Python
  - spatial analysis
  - gravity model
  - socioeconomic data
  - county health
  - policy research
  - United States
authors:
  - name: Greg Lake
    orcid: 0009-0004-4071-4099
    affiliation: 1
affiliations:
  - name: Independent Researcher
    index: 1
date: 2026-04-01
bibliography: paper.bib
---

# Summary

DiscoveryLens is a configurable county similarity and correlation explorer for US policy research. It identifies structural peer counties --- places sharing similar socioeconomic profiles despite geographic distance --- using Euclidean distance in a normalized 30-variable space spanning economic, health, infrastructure, civic, child welfare, immigration, industry, and housing domains. Researchers choose a research lens (economic mobility, health equity, child welfare, immigration, infrastructure, community vitality, or a custom subset) and the tool identifies peers relevant to that lens. The same county can have different peer sets under different modules --- Appalachian economic peers, health-outcome peers, or civic-engagement peers --- enabling targeted policy transfer research. A gravity model framework [@tinbergen1962shaping] provides visualization: counties with similar profiles cluster together in a dynamic terrain whose axes adapt via client-side PCA. The model is calibrated via two-pass OLS regression ($\beta = 0.139$ from 249,922 county pairs) and validated against IRS migration flows ($\rho = 0.164$, 95% CI: 0.154--0.172, $n = 51{,}445$ pairs) [@irs_migration]. DiscoveryLens consists of a Python data pipeline (FastAPI on Railway) and a React frontend with terrain visualization, force-directed dot layout, county search with peer discovery, scatter plot correlation explorer with cluster filtering, and a Discover tab surfacing variable relationships across 30 gravity model variables plus 11 additional variables (9 FEMA disaster risk [@fema_nri] and 2 excluded) for scatter exploration.

# Statement of Need

Policy researchers frequently need to identify peer counties --- places with similar structural conditions --- for policy transfer, natural experiments, and comparative analysis. Peer similarity is structural and correlational --- DiscoveryLens identifies counties with similar observed profiles, not counties with equivalent causal mechanisms, and findings should be treated as hypothesis-generating rather than causal evidence [@robinson1950ecological]. Existing tools address this poorly: County Health Rankings [@remington2015county] confines comparisons within states; CDC PLACES compares only three counties at a time; the Distressed Communities Index provides a single composite score without peer identification. None lets researchers define what "similar" means for their research question.

DiscoveryLens makes three contributions. First, module-based peer discovery: researchers select variables relevant to their question. A health equity researcher finds peers similar on disease burden and access; an economic mobility researcher finds peers similar on income, employment, and industry mix; a child welfare researcher finds peers similar on child poverty and family structure. The same county yields genuinely different peer sets under different modules --- peer sets that cannot be obtained by filtering a general similarity score. Second, within-group correlation analysis: the cluster-filtered scatter plot reveals whether correlations hold within structurally similar counties. Poverty and diabetes correlate strongly overall ($r = 0.736$) but the relationship varies within county archetypes --- from moderate ($r = 0.477$, 95% CI: 0.432--0.519) in prosperous suburban counties to $r = 0.596$ (95% CI: 0.549--0.639) in rural disadvantaged counties --- suggesting that county archetype attenuates the poverty--diabetes relationship. This demonstrates that aggregate county correlations are often driven by between-cluster variance rather than within-cluster conditions [@robinson1950ecological] --- a phenomenon DiscoveryLens makes interactively explorable. Third, complete coverage: all 3,135 US counties including small rural counties receive peer lists, unlike force-based tools where small counties lack sufficient gravitational mass to appear in link caches.

# Mathematics

DiscoveryLens separates two analytical operations. Peer discovery uses population-independent Euclidean distance in the module's variable subspace. For target county $t$ and candidate $c$ with normalized vectors $\mathbf{v}_t$ and $\mathbf{v}_c$ over $k$ selected variables:

$$d(t,c) = \sqrt{\sum_{i=1}^{k} (v_{t,i} - v_{c,i})^2}$$

Missing values (3.7% of county-variable cells, concentrated in air quality at 69% missing) are imputed with 0.5 (midpoint of $[0,1]$). Peers are the $k$ nearest neighbors by this distance (equivalent to KNN; Jaccard = 1.000). The terrain visualization uses client-side PCA, projecting counties to 2D with kernel density as height; axes update when the module changes.

The gravity model [@tinbergen1962shaping] provides the visualization framework and external validation:

$$F_{ij} = \frac{P_i \cdot P_j}{d_{ij}^{\beta}}$$

where $d_{ij} = \max(\text{geo\_norm}_{ij} \cdot \text{data\_dissim}_{ij},\; 0.01)$ combines normalized geographic distance (Haversine / 5,251 miles) and Euclidean data dissimilarity across 30 variables. $\beta$ is calibrated via two-pass OLS log-linear regression on 249,922 county pairs (seed = 42). Pass 1: $\beta_{geo} = 0.059$ ($R^2 = 0.054$, geographic only). Pass 2: $\beta = 0.139$ ($R^2 = 0.303$, combined distance). Cross-validation (80/20 holdout) confirms $\beta_{cv} = 0.139$, $R^2_{holdout} = 0.302$. Population product explains 96.7% of raw force variance; peer discovery uses population-independent Euclidean distance instead.

# Validation

The gravity model is validated against IRS county-to-county migration flows [@irs_migration] --- data never used in calibration. Across 51,445 IRS county pairs (2019--2020 tax year), Spearman rank correlation improves from $\rho = 0.041$ (population only) to $\rho = 0.053$ (adding geography) to $\rho = 0.164$ (adding data similarity, 95% CI: 0.154--0.172, bootstrap $n = 1000$). The $+0.110$ improvement (bootstrap 95% CI on $\rho_C$: 0.154--0.172, $n = 1{,}000$ resamples, seed = 42) demonstrates that socioeconomic distance captures county affinity beyond population and geography. The modest absolute $\rho = 0.164$ is expected --- IRS migration is driven primarily by economic opportunity, not socioeconomic similarity, so a weak but significant improvement establishes construct validity of the distance measure rather than predictive accuracy for migration. Of the 51,445 pairs, approximately 24% appear in the top-10,000 gravity link cache with non-zero predicted force; the remaining 76% receive zero. The $\rho$ therefore reflects both ranking accuracy and binary link discrimination.

To validate that peer identification captures genuine structural similarity rather than surface correlations, we conducted a holdout prediction test. Using Health Equity lens peers (defined by health variables) to predict median household income --- a variable not included in the peer-defining set --- peer prediction achieved 79% lower mean absolute error than the national mean and 31% lower error than the five nearest geographic neighbors across five test counties (San Francisco, McDowell WV, Cook IL, Marin CA, Starr TX). At scale across 200 randomly selected counties, peer-based prediction outperformed both geographic proximity and the national mean 60% of the time ($\text{MAE}_{peer} = \$4{,}178$ vs. $\text{MAE}_{geo} = \$6{,}971$ vs. $\text{MAE}_{national} = \$11{,}680$). This cross-domain predictive validity suggests the similarity space captures latent structural conditions that generalize beyond the variables used to define peers.

As a further external validity check, DiscoveryLens independently reproduces several established findings in health geography. The tool's positive deviance analysis --- without being prompted --- identifies counties with large immigrant populations as the strongest positive deviants on life expectancy relative to economic predictions, with top positive deviant counties showing 2.8$\times$ the national foreign-born rate. This independently detects the Hispanic/Immigrant Paradox [@markides1986health; @ruiz2013hispanic]. Additionally, 78% of the 50 highest-diabetes counties fall within the CDC-identified Diabetes Belt [@barker2011diabetes], and 100% of high-EITC county peers show above-average EITC clustering consistent with @chetty2014land.

Within-group correlation analysis reveals that many aggregate county correlations are driven by between-cluster variance [@robinson1950ecological]: poverty $\times$ diabetes $r = 0.736$ overall but $r = 0.477$--$0.596$ within three of four county archetypes ($k$-means, $k = 4$, silhouette $= 0.218$; clusters overlap and should be treated as archetypes rather than hard categories). The High-Need Urban/Border cluster ($n = 153$ counties) is too small to compute reliable within-cluster correlations and is excluded from within-cluster analyses. FEMA National Risk Index validation [@fema_nri] confirmed disaster risk is largely independent of socioeconomic disadvantage ($r = 0.151$). A benchmark against @chetty2014land county-level poverty-mobility correlation ($r = -0.451$ vs. commuting zone $r \approx -0.60$) is consistent with ecological aggregation effects. Opportunity Atlas data [@opportunity_atlas] was excluded due to temporal mismatch (1978--2015 outcomes vs. 2022 conditions) but remains available for scatter exploration.

# Acknowledgements

DiscoveryLens uses open data from the US Census Bureau (ACS, SAIPE), Centers for Disease Control and Prevention (PLACES/BRFSS), Environmental Protection Agency (AQS), US Department of Agriculture Economic Research Service (Food Access Atlas, Rural-Urban Codes), Internal Revenue Service (Statistics of Income), Federal Emergency Management Agency (National Risk Index), Institute of Museum and Library Services (Public Libraries Survey), Bureau of Labor Statistics (LAUS), and the MIT Election Data + Science Lab. The Opportunity Atlas data is from @chetty2014land and @opportunity_atlas.

# References
