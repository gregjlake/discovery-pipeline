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

# Weights for structural strength score. Urbanization is intentionally excluded.
STRUCTURAL_WEIGHTS = {
    "gdp_per_capita":  0.30,
    "life_expectancy": 0.25,
    "education_years": 0.20,
    "gini":            0.15,   # inverted at normalize step (lower = better)
    "population":      0.10,
}

# Variables whose direction is "lower = better" — inverted at normalize step.
INVERT_AT_NORMALIZE = {"gini"}

SPARSE_MIN_DECADES = 6
MIN_VARS_FOR_SCORE = 3

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
