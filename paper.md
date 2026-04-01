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
    orcid: 0000-0000-0000-0000
    affiliation: 1
affiliations:
  - name: Independent Researcher
    index: 1
date: 1 April 2026
bibliography: paper.bib
---

# Summary

DiscoSights is a spatial interaction model for identifying socioeconomic peer counties across the United States. The model computes pairwise attraction between 3,135 county profiles across 17 government datasets using the gravity formula Force(i,j) = Pop(i) x Pop(j) / dist(i,j)^beta, where distance combines geographic proximity and socioeconomic dissimilarity. The distance decay parameter beta = 0.155 is empirically calibrated from 249,922 county pairs, yielding R-squared = 0.313 for combined distance versus 0.038 for geography alone. Out-of-sample validation against IRS county-to-county migration flows [@irs_migration] shows +0.113 Spearman rho improvement when adding data similarity beyond population and geography. The tool enables researchers to find structurally similar communities regardless of geographic proximity --- for example, McDowell County WV and Starr County TX share economic profiles despite 1,247 miles of separation. DiscoSights provides an interactive web interface with terrain visualization, force-directed dot layout, county search with peer discovery, and a scatter plot for exploring correlations across 28 datasets including FEMA disaster risk [@fema_nri].

# Statement of Need

Identifying socioeconomic peer counties is a recurring need in policy research, public health planning, and economic geography. Researchers evaluating county-level interventions, seeking replication sites, or studying natural experiments must find structurally similar communities. Existing tools like the County Health Rankings [@remington2015county] provide single-dimension comparisons but lack multidimensional peer discovery with validated distance metrics. The CDC PLACES platform offers county health estimates but no similarity model.

DiscoSights addresses this gap with three contributions absent from existing tools: (1) an empirically calibrated distance decay parameter rather than an assumed value, (2) out-of-sample validation against IRS migration flows confirming the model captures real-world interaction signal, and (3) documented weighting robustness --- three weighting schemes produce equivalent predictions (maximum rho difference 0.0009) and 89% peer overlap for domain-balanced weighting. The model is validated, transparent, and immediately usable by researchers who need peer county identification grounded in multidimensional socioeconomic data rather than ad hoc variable selection.

# Mathematics

The gravity force between counties $i$ and $j$ is:

$$F_{ij} = \frac{P_i \cdot P_j}{d_{ij}^{\beta}}$$

where $P_i$ and $P_j$ are county populations and $d_{ij}$ is the combined distance:

$$d_{ij} = \max\left(\frac{h_{ij}}{5251} \cdot \frac{\|\mathbf{v}_i - \mathbf{v}_j\|}{\sqrt{k}}, \; 0.01\right)$$

Here $h_{ij}$ is the Haversine geographic distance in miles, $\mathbf{v}_i$ and $\mathbf{v}_j$ are min-max normalized vectors across $k = 17$ socioeconomic datasets, and the floor of 0.01 prevents numerical instability for adjacent identical-profile counties.

The distance decay $\beta = 0.155$ is calibrated via OLS log-linear regression on 249,922 randomly sampled county pairs (seed = 42). A two-pass procedure first estimates $\beta_{geo} = 0.055$ ($R^2 = 0.038$) using geographic distance only, then $\beta_{combined} = 0.155$ ($R^2 = 0.313$) using the multiplicative combined distance. The 720% R-squared improvement confirms that socioeconomic dissimilarity adds substantial explanatory power beyond geography alone [@tinbergen1962shaping].

# Validation

The model was validated against IRS Statistics of Income county-to-county migration flows (2019--2020, 51,445 pairs) [@irs_migration]. Spearman rank correlation improves from $\rho = 0.041$ (population only) to $\rho = 0.053$ (adding geography) to $\rho = 0.165$ (adding data similarity), a +0.113 improvement over geography alone. Weighting robustness testing across three schemes (equal, domain-balanced, PCA-reduced) found maximum rho difference of 0.0009 and peer-level Jaccard similarity of 0.891 for domain-balanced weighting. External validation against FEMA National Risk Index [@fema_nri] confirmed disaster risk is largely independent of socioeconomic disadvantage ($r = 0.151$), establishing that the model captures a distinct welfare dimension. A benchmark comparison with @chetty2014land county-level poverty-mobility correlation ($r = -0.451$ vs. commuting zone $r \approx -0.60$) is consistent with known ecological aggregation effects. The Opportunity Atlas data [@opportunity_atlas] was excluded from the gravity model due to temporal mismatch (1978--2015 outcomes vs. 2022 conditions) but remains available for scatter plot exploration.

# Acknowledgements

DiscoSights uses open data from the US Census Bureau (ACS, SAIPE), Centers for Disease Control and Prevention (PLACES/BRFSS), Environmental Protection Agency (AQS), US Department of Agriculture Economic Research Service (Food Access Atlas, Rural-Urban Codes), Internal Revenue Service (Statistics of Income), Federal Emergency Management Agency (National Risk Index), Institute of Museum and Library Services (Public Libraries Survey), Bureau of Labor Statistics (LAUS), and the MIT Election Data + Science Lab. The Opportunity Atlas data is from @chetty2014land and @opportunity_atlas.

# References
