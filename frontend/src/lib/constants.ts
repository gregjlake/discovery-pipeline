export const DOMAIN_COLORS: Record<string, string> = {
  library:       "#6366f1",  // indigo
  mobility:      "#f59e0b",  // amber
  air:           "#10b981",  // emerald
  broadband:     "#3b82f6",  // blue
  eitc:          "#ec4899",  // pink
  poverty:       "#ef4444",  // red
  median_income: "#8b5cf6",  // violet
};

export const DOMAIN_LABELS: Record<string, string> = {
  library:       "Library Spending",
  mobility:      "Upward Mobility",
  air:           "Air Quality",
  broadband:     "Broadband Access",
  eitc:          "EITC Rate",
  poverty:       "Poverty Rate",
  median_income: "Median Income",
};

export const DOMAIN_UNITS: Record<string, string> = {
  library:       "$/capita",
  mobility:      "rank (0–1)",
  air:           "AQI inv.",
  broadband:     "rate (0–1)",
  eitc:          "rate (0–1)",
  poverty:       "%",
  median_income: "$",
};

export const NORM_METHODS = ["zscore", "minmax", "rank", "log", "robust"] as const;
export const OUTLIER_METHODS = ["keep", "winsor5", "winsor1", "remove3"] as const;
export const WEIGHT_METHODS = ["equal", "popweight"] as const;
