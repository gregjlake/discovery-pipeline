# HistoryLens Prototype

Interactive 3D visualization of structural strength across 40 nations from 1820 to 2000.

Part of the DiscoveryLens platform at discoverylens.org

## Data
- 40 countries across 6 regions
- 19 decades: 1820-2000
- 5 variables: GDP per capita, life expectancy, education, inequality, population
- Sources: CLIO-INFRA, Maddison Project Database, Our World in Data
- Normalization: per-year relative structural strength (0-100)

## Pipeline
Run pipeline/run_all.py to regenerate all data from raw sources.

## Visualization
Open index.html in a browser. No build step needed.

## Part of
- discoverylens.org — US county similarity explorer
- github.com/gregjlake/discovery-pipeline
