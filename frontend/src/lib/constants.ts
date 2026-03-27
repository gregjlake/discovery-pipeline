export const DOMAIN_COLORS: Record<string, string> = {
  library:        "#6366f1",  // indigo
  mobility:       "#f59e0b",  // amber
  air:            "#10b981",  // emerald
  broadband:      "#3b82f6",  // blue
  eitc:           "#ec4899",  // pink
  poverty:        "#ef4444",  // red
  median_income:  "#8b5cf6",  // violet
  bea_income:     "#a855f7",  // purple
  food_access:    "#f97316",  // orange
  obesity:        "#dc2626",  // red-600
  diabetes:       "#e11d48",  // rose-600
  mental_health:  "#0891b2",  // cyan-600
  hypertension:   "#be123c",  // rose-700
  unemployment:   "#ca8a04",  // yellow-600
  rural_urban:    "#65a30d",  // lime-600
  housing_burden: "#7c3aed",  // violet-600
  voter_turnout:  "#0284c7",  // sky-600
};

export const DOMAIN_LABELS: Record<string, string> = {
  library:        "Library Spending",
  mobility:       "Upward Mobility",
  air:            "Air Quality",
  broadband:      "Broadband Access",
  eitc:           "EITC Rate",
  poverty:        "Poverty Rate",
  median_income:  "Median Income",
  bea_income:     "Per Capita Income",
  food_access:    "SNAP Rate",
  obesity:        "Obesity Rate",
  diabetes:       "Diabetes Rate",
  mental_health:  "Mental Health",
  hypertension:   "Hypertension Rate",
  unemployment:   "Unemployment Rate",
  rural_urban:    "Rural-Urban Code",
  housing_burden: "Housing Burden",
  voter_turnout:  "Votes Cast 2020",
};

export const DOMAIN_UNITS: Record<string, string> = {
  library:        "$/capita",
  mobility:       "rank (0–1)",
  air:            "AQI inv.",
  broadband:      "rate (0–1)",
  eitc:           "rate (0–1)",
  poverty:        "%",
  median_income:  "$",
  bea_income:     "$/person/year",
  food_access:    "% households",
  obesity:        "% adults",
  diabetes:       "% adults",
  mental_health:  "% adults",
  hypertension:   "% adults",
  unemployment:   "% unemployed",
  rural_urban:    "code 1-9",
  housing_burden: "% cost-burdened",
  voter_turnout:  "total votes",
};

export const NORM_METHODS = ["zscore", "minmax", "rank", "log", "robust"] as const;
export const OUTLIER_METHODS = ["keep", "winsor5", "winsor1", "remove3"] as const;
export const WEIGHT_METHODS = ["equal", "popweight"] as const;
