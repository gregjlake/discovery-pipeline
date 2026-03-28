"""Apply all 11 scientific provenance fixes to dataset_metadata.json."""
import json
from pathlib import Path

META = Path(__file__).resolve().parent.parent / "data" / "dataset_metadata.json"

with open(META, encoding="utf-8") as f:
    d = json.load(f)

# ── GLOBAL: higher_is_better + data_type for ALL 17 datasets ──
HIB = {
    "library": True, "mobility": True, "air": True, "broadband": True,
    "eitc": None, "poverty": False, "median_income": True, "bea_income": True,
    "food_access": None, "obesity": False, "diabetes": False,
    "mental_health": False, "hypertension": False, "unemployment": False,
    "rural_urban": None, "housing_burden": False, "voter_turnout": True,
}
DT = {k: "continuous" for k in HIB}
DT["rural_urban"] = "ordinal"

DN = {
    "air": "Inverted Median AQI: higher value = cleaner air (200 - Median AQI)",
    "broadband": "Higher subscription = more connected",
    "eitc": "Ambiguous: higher rate may indicate more poverty OR better program access.",
    "food_access": "Ambiguous: higher SNAP rate = more food assistance enrollment, correlates with food insecurity but also program access.",
    "rural_urban": "Ordinal 1-9. Higher code = more rural. Whether rural is 'better' depends on the outcome being studied.",
    "voter_turnout": "Raw vote count (not a rate). Strongly confounded by county population size.",
    "median_income": "Nominal dollars, not cost-of-living adjusted",
    "bea_income": "Nominal dollars, not cost-of-living adjusted",
}

for ds_id in HIB:
    if ds_id in d:
        d[ds_id]["higher_is_better"] = HIB[ds_id]
        d[ds_id]["data_type"] = DT[ds_id]
        if ds_id in DN:
            d[ds_id]["direction_note"] = DN[ds_id]

# ── FIX 1: BROADBAND ──
d["broadband"]["label"] = "Broadband Subscription Rate"
d["broadband"]["notes"] = (
    "Measures household broadband subscription rate from ACS (table B28002), "
    "NOT physical infrastructure availability. Low subscription rates may reflect "
    "unaffordability or lack of infrastructure \u2014 this data cannot distinguish between them. "
    "FCC availability maps would be needed to separate these causes. "
    "ACS 5-year estimate (2018\u20132022 average)."
)
d["broadband"]["proxy_warning"] = "Subscription rate, not infrastructure availability"

# ── FIX 2: AIR QUALITY (already inverted — clarify) ──
d["air"]["notes"] = (
    "Inverted Median AQI: computed as 200 \u2212 Median AQI, so higher value = cleaner air. "
    "Annual county AQI summary from EPA monitoring stations. Only 973 counties (~31%) "
    "have direct measurements with 50+ monitoring days. Counties without monitors are "
    "absent (not modeled/interpolated). Monitor placement is non-random. "
    "Air quality is spatially smooth, making county-level aggregation appropriate (low MAUP)."
)

# ── FIX 3: RURAL_URBAN ordinal ──
d["rural_urban"]["notes"] = (
    "USDA ordinal codes 1\u20139 where 1=large metro core, 9=completely rural (<2,500 pop, "
    "not adjacent to metro). Treated as continuous for correlation and distance calculations. "
    "This is a simplification \u2014 intervals between codes are not equal in real-world terms. "
    "Interpret correlations involving rural_urban as indicating direction (urban vs rural) "
    "rather than precise magnitude. Population density would be a truly continuous alternative. "
    "Based on 2020 Census population and OMB metro definitions."
)

# ── FIX 4: DIAGNOSIS BIAS ──
d["diabetes"]["notes"] = (
    "Crude prevalence of DIAGNOSED diabetes from CDC PLACES (BRFSS-based). "
    "Areas with limited healthcare access show lower measured rates even if true prevalence "
    "is identical or higher. Poverty correlations likely understate the true relationship "
    "due to diagnosis bias. Small-area estimates from BRFSS telephone survey."
)
d["diabetes"]["diagnosis_bias"] = True

d["hypertension"]["notes"] = (
    "Crude prevalence of DIAGNOSED high blood pressure from CDC PLACES (BRFSS-based). "
    "Areas with limited healthcare access show lower measured rates even if true prevalence "
    "is identical or higher. Poverty correlations likely understate the true relationship "
    "due to diagnosis bias. Small-area estimates from BRFSS telephone survey."
)
d["hypertension"]["diagnosis_bias"] = True

d["mental_health"]["notes"] = (
    "Self-reported frequent mental distress (\u226514 poor mental health days/month) from "
    "CDC PLACES (BRFSS). Systematically underreported in communities with higher mental "
    "health stigma. Geographic patterns may partly reflect stigma rather than actual prevalence. "
    "Diagnosis bias: areas with less mental healthcare access have lower reported rates."
)
d["mental_health"]["diagnosis_bias"] = True

# ── FIX 5: EITC NON-TAKE-UP ──
d["eitc"]["notes"] = (
    "EITC filing rate as share of total tax filers. ~20% of eligible households nationally "
    "do not claim EITC. Non-take-up is systematically higher in immigrant communities and "
    "areas with tax filing barriers. Low EITC rates may indicate: lower poverty, OR filing "
    "barriers, OR higher undocumented population \u2014 this data cannot distinguish between "
    "these causes. ZIP-to-county aggregation via Census ZCTA area-weighted crosswalk."
)

# ── FIX 6: UNEMPLOYMENT COVID + U-3 ──
d["unemployment"]["notes"] = (
    "ACS 5-year estimate (2018\u20132022) of U-3 unemployment rate. Includes 2020 pandemic spike "
    "(national peak 14.7% in April 2020) and recovery, which inflates the average for volatile "
    "counties. U-3 counts only those actively seeking work. Does not include discouraged workers, "
    "underemployed, or informal economy. In distressed counties, U-3 may understate true "
    "hardship because many have left the labor force."
)

# ── FIX 7: POVERTY/INCOME COST-OF-LIVING ──
d["poverty"]["notes"] = (
    "Census Official Poverty Measure (OPM) from SAIPE with fixed national thresholds, "
    "NOT adjusted for geographic cost of living. $30K income means very different conditions "
    "in rural Mississippi vs urban California. The Supplemental Poverty Measure (SPM) adjusts "
    "for this but is only available at state level. Model-based estimates combining ACS, IRS, "
    "and SNAP administrative records."
)

d["median_income"]["notes"] = (
    "Nominal dollar income without geographic cost-of-living adjustment. "
    "$50K in rural Alabama = substantially higher purchasing power than $50K in coastal suburbs. "
    "Model-based county estimates from Census SAIPE program."
)

d["bea_income"]["notes"] = (
    "Per capita income from Census ACS 5-Year (table B19301). Nominal dollars without "
    "cost-of-living adjustment. Previously mislabeled as BEA data. ACS measures household "
    "survey income; BEA personal income (includes transfer payments) would differ."
)

# ── FIX 8: VOTER TURNOUT 2020 ──
d["voter_turnout"]["notes"] = (
    "Raw vote count (total votes cast) in 2020 presidential election, NOT a turnout rate. "
    "No denominator (eligible voter population unavailable at county level). "
    "Confounded by county population \u2014 large counties show higher values regardless of "
    "civic engagement. 2020 had highest national turnout since 1900 (66.9%), driven by "
    "pandemic mail-in voting. Patterns may not reflect structural engagement."
)

# ── FIX 9: OBESITY SELF-REPORT ──
d["obesity"]["notes"] = (
    "Crude prevalence from CDC PLACES, based on self-reported height/weight (BRFSS). "
    "Self-reporting systematically underestimates BMI \u2014 people underreport weight and "
    "overreport height. Bias varies by region, education, gender. Model-based small area "
    "estimates partially smooth this but underlying survey bias propagates."
)

# ── FIX 10: LIBRARY COUNT VS QUALITY ──
d["library"]["notes"] = (
    "Library operating expenditure per capita from IMLS FY2022. Does not capture library "
    "quality, hours, collection size, or digital services. County totals aggregated from "
    "library-level data using Census tract FIPS mapping."
)

# ── FIX 11: HOUSING BURDEN SELECTION BIAS ──
d["housing_burden"]["notes"] = (
    "Share of renters paying 30%+ of income on rent (HUD threshold). Excludes homeowners. "
    "Selection bias: when housing becomes unaffordable, price-sensitive households leave, "
    "so remaining renters can afford current prices. Housing_burden may appear LOWER in "
    "the most expensive markets because the poorest residents have been displaced. "
    "ACS 5-year estimate (2018\u20132022)."
)

with open(META, "w", encoding="utf-8") as f:
    json.dump(d, f, indent=2, ensure_ascii=False)

print("All 11 fixes applied.")
print()

# Summary table
print(f"{'Dataset':<18} {'Label':<26} {'HIB':>5} {'Type':<10} {'Year Type':<12} {'MAUP':<7} Key Caveat")
print("-" * 130)
for ds_id, m in d.items():
    hib = m.get("higher_is_better")
    hib_str = "T" if hib is True else "F" if hib is False else "?"
    caveat = m.get("notes", "")[:60] + "..."
    print(f"{ds_id:<18} {m['label']:<26} {hib_str:>5} {m.get('data_type','?'):<10} {m.get('year_type','?'):<12} {m.get('maup_sensitivity','?'):<7} {caveat}")
