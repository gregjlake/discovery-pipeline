"""Shared constants and helpers for the HistoryLens pipeline."""
from pathlib import Path

PIPELINE_DIR = Path(__file__).parent
ROOT = PIPELINE_DIR.parent
RAW = ROOT / "data" / "raw"
PROC = ROOT / "data" / "processed"
PROC.mkdir(parents=True, exist_ok=True)

DECADES = list(range(1820, 2001, 10))   # 1820, 1830, ..., 2000  (19 decades)

VARIABLES = [
    "gdp_per_capita",
    "life_expectancy",
    "population",
    "urbanization",
    "gini",
    "education_years",
]

# Source priority per variable. First source wins; later sources fill gaps.
SOURCE_PRIORITY = {
    "gdp_per_capita":   ["Maddison",   "CLIO-INFRA"],
    "life_expectancy":  ["CLIO-INFRA", "OWID"],
    "population":       ["Maddison",   "CLIO-INFRA"],
    "urbanization":     ["CLIO-INFRA"],
    "gini":             ["CLIO-INFRA"],
    "education_years":  ["CLIO-INFRA"],
}

# Variables that enter the structural strength composite (population excluded
# as of v2 — it is a scale variable, not a development indicator).
# v2.1: urbanization added (interpolated between 1850/1900/1950/2000 benchmarks,
# see 02_harmonize.py for the interpolation rule).
SCORING_VARS = [
    "gdp_per_capita", "life_expectancy", "education_years", "gini", "urbanization",
]

# Variables collected and exported but NOT scored (display-only in the JSON).
DISPLAY_ONLY_VARS = ["population"]

# Three weight schemes. Each must sum to 1.0 over SCORING_VARS.
# A = balanced (default); B = GDP-heavy classical; C = capability/Sen-HDI.
# v2.1: urbanization added at 8% in Scheme A (per project spec); schemes B and
# C take 8% off their other weights proportionally so all three schemes share a
# single five-variable basis.
WEIGHT_SCHEMES = {
    "A": {
        "label": "Balanced (default)",
        "weights": {
            "gdp_per_capita":  0.37,
            "life_expectancy": 0.28,
            "education_years": 0.18,
            "gini":            0.09,
            "urbanization":    0.08,
        },
    },
    "B": {
        "label": "GDP-heavy (classical economics)",
        "weights": {
            "gdp_per_capita":  0.50,
            "life_expectancy": 0.18,
            "education_years": 0.14,
            "gini":            0.10,
            "urbanization":    0.08,
        },
    },
    "C": {
        "label": "Capability approach (Sen / HDI)",
        "weights": {
            "gdp_per_capita":  0.23,
            "life_expectancy": 0.33,
            "education_years": 0.27,
            "gini":            0.09,
            "urbanization":    0.08,
        },
    },
}

# Default scheme for the canonical structural_strength field.
DEFAULT_SCHEME = "A"
STRUCTURAL_WEIGHTS = WEIGHT_SCHEMES[DEFAULT_SCHEME]["weights"]

# Variables whose direction is "lower = better" — inverted at normalize step.
INVERT_AT_NORMALIZE = {"gini"}

SPARSE_MIN_DECADES = 6
MIN_VARS_FOR_SCORE = 3

# Region map used by 04_peers.py (regional peers) and 06_export.py.
# Hungary and Poland kept under "Western Europe" per project convention.
REGION_MAP = {
    # Western Europe
    "Netherlands":    "Western Europe", "United Kingdom": "Western Europe",
    "France":         "Western Europe", "Sweden":         "Western Europe",
    "Norway":         "Western Europe", "Denmark":        "Western Europe",
    "Belgium":        "Western Europe", "Italy":          "Western Europe",
    "Spain":          "Western Europe", "Switzerland":    "Western Europe",
    "Germany":        "Western Europe", "Finland":        "Western Europe",
    "Portugal":       "Western Europe", "Greece":         "Western Europe",
    "Ireland":        "Western Europe", "Hungary":        "Western Europe",
    "Poland":         "Western Europe",
    # Anglo-Pacific
    "Australia":      "Anglo-Pacific",  "Canada":         "Anglo-Pacific",
    # North America
    "United States":  "North America",  "Mexico":         "North America",
    # Latin America
    "Chile":     "Latin America", "Argentina":  "Latin America",
    "Brazil":    "Latin America", "Colombia":   "Latin America",
    "Peru":      "Latin America", "Venezuela":  "Latin America",
    "Jamaica":   "Latin America", "Uruguay":    "Latin America",
    "Bolivia":   "Latin America", "Cuba":       "Latin America",
    # East Asia
    "Japan":         "East Asia", "China":       "East Asia",
    "South Korea":   "East Asia", "Indonesia":   "East Asia",
    "Philippines":   "East Asia",
    # South Asia
    "India":         "South Asia",
    # Eastern Europe
    "Russia":        "Eastern Europe",
    # Africa
    "South Africa":  "Africa", "Egypt":         "Africa",
}


def redistribute_weights(scheme_weights, available_vars):
    """Return weights renormalized over the subset of vars actually present."""
    avail = {v: scheme_weights[v] for v in available_vars if v in scheme_weights}
    total = sum(avail.values())
    if total == 0:
        return {}
    return {v: w / total for v, w in avail.items()}

# 40-country target list with canonical names + ISO3 codes + tier
COUNTRY_MAP = [
    # Tier A
    ("Netherlands",    "NLD", "A"),
    ("United Kingdom", "GBR", "A"),
    ("France",         "FRA", "A"),
    ("Sweden",         "SWE", "A"),
    ("Norway",         "NOR", "A"),
    ("Denmark",        "DNK", "A"),
    ("Belgium",        "BEL", "A"),
    ("Italy",          "ITA", "A"),
    ("United States",  "USA", "A"),
    ("Chile",          "CHL", "A"),
    ("Argentina",      "ARG", "A"),
    ("Spain",          "ESP", "A"),
    ("Switzerland",    "CHE", "A"),
    ("Japan",          "JPN", "A"),
    ("Mexico",         "MEX", "A"),
    ("Brazil",         "BRA", "A"),
    ("Germany",        "DEU", "A"),
    ("Russia",         "RUS", "A"),
    # Tier B
    ("Australia",      "AUS", "B"),
    ("Canada",         "CAN", "B"),
    ("Finland",        "FIN", "B"),
    ("Colombia",       "COL", "B"),
    ("Peru",           "PER", "B"),
    ("Portugal",       "PRT", "B"),
    ("Venezuela",      "VEN", "B"),
    ("China",          "CHN", "B"),
    ("India",          "IND", "B"),
    ("Jamaica",        "JAM", "B"),
    ("Uruguay",        "URY", "B"),
    ("Hungary",        "HUN", "B"),
    ("Ireland",        "IRL", "B"),
    ("Philippines",    "PHL", "B"),
    ("Bolivia",        "BOL", "B"),
    ("Cuba",           "CUB", "B"),
    ("Indonesia",      "IDN", "B"),
    ("South Korea",    "KOR", "B"),
    ("South Africa",   "ZAF", "B"),
    ("Egypt",          "EGY", "B"),
    ("Poland",         "POL", "B"),
    ("Greece",         "GRC", "B"),
]

CANONICAL_TO_ISO = {name: iso for name, iso, _ in COUNTRY_MAP}
CANONICAL_NAMES = [name for name, _, _ in COUNTRY_MAP]
ISO_TO_CANONICAL = {iso: name for name, iso, _ in COUNTRY_MAP}

# Per-source aliases. When the source uses a different name, list it here.
# Default alias = canonical name itself.
SOURCE_ALIASES = {
    "Russia": {
        "Maddison":   ["Former USSR"],         # historical thread for GDP/Pop
        "OWID":       ["Russia"],              # life expectancy
        "CLIO-INFRA": ["Russian Federation", "Russia"],
    },
    "South Korea": {
        "Maddison":   ["Republic of Korea"],
        "OWID":       ["South Korea"],
        "CLIO-INFRA": ["South Korea", "Korea, South", "Korea (South)", "Korea"],
    },
    "United States": {
        "Maddison":   ["United States"],
        "OWID":       ["United States"],
        "CLIO-INFRA": ["United States", "United States of America"],
    },
    "Egypt": {
        "CLIO-INFRA": ["Egypt", "Egypt, Arab Rep."],
    },
}


def aliases_for(canonical_name, source):
    """Return list of source-specific aliases for a canonical country name."""
    overrides = SOURCE_ALIASES.get(canonical_name, {})
    if source in overrides:
        return overrides[source]
    return [canonical_name]


# CLIO-INFRA file → variable mapping
CLIO_FILES = {
    "GDPperCapita_Compact.xlsx":              "gdp_per_capita",
    "LifeExpectancyatBirth_Compact.xlsx":     "life_expectancy",
    "TotalPopulation_Compact.xlsx":           "population",
    "UrbanizationRatio_Compact.xlsx":         "urbanization",
    "IncomeInequality_Compact.xlsx":          "gini",
    "AverageYearsofEducation_Compact.xlsx":   "education_years",
}

MADDISON_FILE = "maddison_project_database_2023.xlsx"
OWID_LIFE_FILE = "owid_life_expectancy.csv"
