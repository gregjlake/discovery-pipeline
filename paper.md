---
title: 'DiscoSights: A Validated Spatial Interaction Model for US County Socioeconomic Similarity'
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

DiscoSights is a configurable county similarity and correlation explorer for US policy research. It enables researchers to identify structural peer counties --- places that share similar socioeconomic profiles despite geographic distance --- using Euclidean distance in a normalized 20-variable county data space. Peer discovery uses a modular approach: researchers choose a research lens (economic mobility, health equity, infrastructure, community vitality, or a custom variable subset) and the tool identifies peers specifically relevant to that lens. The same county can have different peer sets under different modules --- Appalachian economic peers, health-outcome peers, or civic-engagement peers --- enabling targeted policy transfer research. A gravity model framework [@tinbergen1962shaping] provides the visualization structure: counties with similar profiles exert higher gravitational attraction and cluster together in a dynamic terrain visualization whose axes adapt to the active module via client-side PCA. The gravity model is empirically calibrated ($\beta = 0.150$ from 249,922 county pairs) and validated against IRS migration flows ($\rho = 0.165$, 95% CI: 0.155--0.173, $n = 51{,}445$ pairs) [@irs_migration], providing external evidence that the similarity space captures real-world county affinity beyond population and geography. DiscoSights consists of a Python data pipeline (FastAPI on Railway) and a React frontend (Lovable) with terrain visualization, force-directed dot layout, county search with peer discovery, scatter plot correlation explorer with cluster filtering, and a Discover tab surfacing scientifically interesting variable relationships across 31 datasets including FEMA disaster risk [@fema_nri].

# Statement of Need

Policy researchers frequently need to identify peer counties --- places with similar structural conditions --- to inform policy transfer decisions, natural experiment design, and comparative analysis. Existing tools address this poorly: County Health Rankings [@remington2015county] confines comparisons within states; CDC PLACES compares only three counties at a time; the Distressed Communities Index provides a single composite score without peer identification. None enables researchers to define what "similar" means for their specific research question.

DiscoSights makes three contributions not found in existing tools. First, module-based peer discovery: researchers define similarity by selecting the variables relevant to their research question. A health equity researcher finds peers similar on disease burden and access; an economic mobility researcher finds peers similar on income, education, and employment. The same county yields genuinely different peer sets under different modules --- peer sets that cannot be obtained by filtering a general similarity score. Second, within-group correlation analysis: the cluster-filtered scatter plot reveals whether a correlation holds within structurally similar counties. We find that poverty and diabetes correlate strongly overall ($r = 0.705$) but the relationship weakens substantially within homogeneous county types ($r = 0.433$--$0.499$), demonstrating that aggregate county correlations are often driven by between-cluster variance rather than within-cluster conditions --- a consequential finding for policy intervention design. Third, complete coverage of small counties: all 3,135 US counties including small rural counties receive peer lists, unlike force-based tools where small counties lack sufficient gravitational mass to appear in pre-computed link caches.

# Mathematics

DiscoSights separates two analytical operations that use different methods. Peer discovery uses population-independent Euclidean distance in the module's variable subspace. For a target county $t$ and candidate county $c$ with normalized variable vectors $\mathbf{v}_t$ and $\mathbf{v}_c$ over the module's $k$ selected variables:

$$d(t,c) = \sqrt{\sum_{i=1}^{k} (v_{t,i} - v_{c,i})^2}$$

Missing values are imputed with 0.5 (the midpoint of the $[0,1]$ normalized scale). Peer counties are the $k$ nearest neighbors by this distance, equivalent to KNN in the module's variable subspace (Jaccard = 1.000 between the two methods). The terrain visualization uses client-side PCA on the module's variable matrix, projecting counties to 2D with kernel density as height. Terrain axes update dynamically when the module changes.

The gravity model provides the visualization framework and external validation. Following @tinbergen1962shaping, the gravitational force between county pairs is:

$$F_{ij} = \frac{P_i \cdot P_j}{d_{ij}^{\beta}}$$

where $d_{ij} = \max(\text{geo\_norm}_{ij} \cdot \text{data\_dissim}_{ij},\; 0.01)$ is the multiplicative combined distance of normalized geographic distance (Haversine / 5,251 miles) and normalized Euclidean data dissimilarity across all 20 variables. The distance decay $\beta$ is calibrated via two-pass OLS log-linear regression on 249,922 randomly sampled county pairs (seed = 42). Pass 1 estimates $\beta_{geo} = 0.054$ ($R^2 = 0.038$) using geographic distance only. Pass 2 estimates $\beta = 0.150$ ($R^2 = 0.299$) using combined distance. Cross-validation (80/20 holdout, seed = 42) confirms $\beta_{cv} = 0.150$ with $R^2_{holdout} = 0.300$, establishing stability. Population product explains 96.2% of raw force variance; gravity force values power the visualization and IRS validation but are not used for peer discovery, which uses population-independent Euclidean distance.

# Validation

The gravity model distance measure is validated against IRS county-to-county migration flows [@irs_migration] --- data never used in calibration. Migration provides an independent behavioral test: if the similarity space captures genuine county affinity, counties with high gravity force should show higher observed migration than population and geography alone predict.

Across 51,445 IRS county pairs (2019--2020 tax year), Spearman rank correlation improves from $\rho = 0.041$ (population only) to $\rho = 0.052$ (adding geography) to $\rho = 0.165$ (adding data similarity, 95% CI: 0.155--0.173, bootstrap $n = 1000$). The $+0.112$ improvement from Model B to C ($p < 0.001$) demonstrates that the normalized socioeconomic distance captures county affinity beyond what population and geography predict. The absolute $\rho = 0.165$ is intentionally modest --- IRS migration is driven primarily by economic opportunity, not socioeconomic similarity, so a weak but significant improvement is the appropriate expectation. The validation establishes construct validity of the distance measure, not predictive validity for migration.

Additionally, the within-group correlation analysis reveals that many strong aggregate county correlations are driven by between-cluster variance: poverty $\times$ diabetes $r = 0.705$ overall but $r = 0.433$--$0.499$ within homogeneous county archetypes (5 clusters, $k$-means, silhouette = 0.20). External validation against FEMA National Risk Index [@fema_nri] confirmed disaster risk is largely independent of socioeconomic disadvantage ($r = 0.151$). A benchmark comparison with @chetty2014land county-level poverty-mobility correlation ($r = -0.451$ vs. commuting zone $r \approx -0.60$) is consistent with ecological aggregation effects. The Opportunity Atlas data [@opportunity_atlas] was excluded from the gravity model due to temporal mismatch (1978--2015 outcomes vs. 2022 conditions) but remains available for scatter plot exploration.

# Acknowledgements

DiscoSights uses open data from the US Census Bureau (ACS, SAIPE), Centers for Disease Control and Prevention (PLACES/BRFSS), Environmental Protection Agency (AQS), US Department of Agriculture Economic Research Service (Food Access Atlas, Rural-Urban Codes), Internal Revenue Service (Statistics of Income), Federal Emergency Management Agency (National Risk Index), Institute of Museum and Library Services (Public Libraries Survey), Bureau of Labor Statistics (LAUS), and the MIT Election Data + Science Lab. The Opportunity Atlas data is from @chetty2014land and @opportunity_atlas.

# References
