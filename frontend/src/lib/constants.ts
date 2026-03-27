export const DOMAIN_COLORS: Record<string, string> = {
  library:   "#6366f1",  // indigo
  mobility:  "#f59e0b",  // amber
  air:       "#10b981",  // emerald
  broadband: "#3b82f6",  // blue
};

export const DOMAIN_LABELS: Record<string, string> = {
  library:   "Library Spending",
  mobility:  "Upward Mobility",
  air:       "Air Quality",
  broadband: "Broadband Access",
};

export const DOMAIN_UNITS: Record<string, string> = {
  library:   "$/capita",
  mobility:  "rank (0–1)",
  air:       "AQI inv.",
  broadband: "rate (0–1)",
};

export const NORM_METHODS = ["zscore", "minmax", "rank", "log", "robust"] as const;
export const OUTLIER_METHODS = ["keep", "winsor5", "winsor1", "remove3"] as const;
export const WEIGHT_METHODS = ["equal", "popweight"] as const;
