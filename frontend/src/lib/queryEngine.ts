import type { ScatterPoint } from "./api";
import { DOMAIN_LABELS } from "./constants";
import { percentileOf } from "./countyMath";

// ── Types ────────────────────────────────────────────────────

export type QueryType = "filter" | "aggregate" | "compare_cohort" | "rank" | "conceptual" | "error";

export interface QueryResult {
  type: QueryType;
  title: string;
  sampleSize: number;
  /** For filter/rank: FIPS codes to highlight on scatter */
  highlightFips: string[];
  /** Rendered data rows */
  rows: ResultRow[];
  /** For conceptual fallback: suggested clickable questions */
  suggestions?: string[];
  /** For aggregate: bar chart data */
  bars?: { label: string; value: number; color?: string }[];
  error?: string;
}

export interface ResultRow {
  label: string;
  value: string;
  fips?: string;
}

// ── Region lookup ────────────────────────────────────────────

const REGION_MAP: Record<string, string> = {
  "01": "South", "02": "West", "04": "West", "05": "South", "06": "West",
  "08": "West", "09": "Northeast", "10": "South", "11": "South", "12": "South",
  "13": "South", "15": "West", "16": "West", "17": "Midwest", "18": "Midwest",
  "19": "Midwest", "20": "Midwest", "21": "South", "22": "South", "23": "Northeast",
  "24": "South", "25": "Northeast", "26": "Midwest", "27": "Midwest", "28": "South",
  "29": "Midwest", "30": "West", "31": "Midwest", "32": "West", "33": "Northeast",
  "34": "Northeast", "35": "West", "36": "Northeast", "37": "South", "38": "Midwest",
  "39": "Midwest", "40": "South", "41": "West", "42": "Northeast", "44": "Northeast",
  "45": "South", "46": "Midwest", "47": "South", "48": "South", "49": "West",
  "50": "Northeast", "51": "South", "53": "West", "54": "South", "55": "Midwest",
  "56": "West",
};

function regionOf(fips: string): string {
  return REGION_MAP[fips.slice(0, 2)] || "Unknown";
}

function stateOf(fips: string): string {
  return fips.slice(0, 2);
}

// ── Pearson r helper ─────────────────────────────────────────

function pearsonR(xs: number[], ys: number[]): number {
  const n = xs.length;
  if (n < 3) return 0;
  const mx = xs.reduce((a, b) => a + b, 0) / n;
  const my = ys.reduce((a, b) => a + b, 0) / n;
  let num = 0, dx2 = 0, dy2 = 0;
  for (let i = 0; i < n; i++) {
    const dx = xs[i] - mx;
    const dy = ys[i] - my;
    num += dx * dy;
    dx2 += dx * dx;
    dy2 += dy * dy;
  }
  const denom = Math.sqrt(dx2 * dy2);
  return denom > 0 ? num / denom : 0;
}

// ── Query executors ──────────────────────────────────────────

export function executeFilter(
  points: ScatterPoint[],
  params: Record<string, unknown>,
  xDs: string,
  yDs: string,
): QueryResult {
  const allRawX = points.map((p) => p.raw_x);
  const allRawY = points.map((p) => p.raw_y);

  let filtered = points;

  const region = params.region as string | null;
  if (region) {
    filtered = filtered.filter((p) => regionOf(p.fips).toLowerCase() === region.toLowerCase());
  }

  const xPctMin = params.x_percentile_min as number | null;
  const xPctMax = params.x_percentile_max as number | null;
  const yPctMin = params.y_percentile_min as number | null;
  const yPctMax = params.y_percentile_max as number | null;

  if (xPctMin != null || xPctMax != null || yPctMin != null || yPctMax != null) {
    filtered = filtered.filter((p) => {
      const px = percentileOf(p.raw_x, allRawX);
      const py = percentileOf(p.raw_y, allRawY);
      if (xPctMin != null && px < xPctMin) return false;
      if (xPctMax != null && px > xPctMax) return false;
      if (yPctMin != null && py < yPctMin) return false;
      if (yPctMax != null && py > yPctMax) return false;
      return true;
    });
  }

  if (filtered.length === 0) {
    return {
      type: "filter",
      title: "No counties match these criteria",
      sampleSize: 0,
      highlightFips: [],
      rows: [],
      suggestions: [
        `Show all ${region || "Southern"} counties`,
        `Show counties in the top 50% for ${DOMAIN_LABELS[xDs]}`,
        `Show the top 10 counties for ${DOMAIN_LABELS[yDs]}`,
      ],
    };
  }

  const desc: string[] = [];
  if (region) desc.push(region);
  if (xPctMin != null || xPctMax != null) desc.push(`X P${xPctMin ?? 0}-${xPctMax ?? 100}`);
  if (yPctMin != null || yPctMax != null) desc.push(`Y P${yPctMin ?? 0}-${yPctMax ?? 100}`);

  return {
    type: "filter",
    title: `Filtered from ${points.length} counties` + (desc.length ? ` (${desc.join(", ")})` : ""),
    sampleSize: filtered.length,
    highlightFips: filtered.map((p) => p.fips),
    rows: filtered.slice(0, 20).map((p) => ({
      label: p.name || `FIPS ${p.fips}`,
      value: `x: ${p.raw_x.toFixed(3)}, y: ${p.raw_y.toFixed(3)}`,
      fips: p.fips,
    })),
  };
}

export function executeAggregate(
  points: ScatterPoint[],
  params: Record<string, unknown>,
  xDs: string,
  yDs: string,
): QueryResult {
  const groupBy = (params.group_by as string) || "region";
  const metric = (params.metric as string) || "mean";
  const dataset = (params.dataset as string) || "both";

  // Group points
  const groups = new Map<string, ScatterPoint[]>();
  for (const p of points) {
    const key = groupBy === "state" ? stateOf(p.fips) : regionOf(p.fips);
    if (!groups.has(key)) groups.set(key, []);
    groups.get(key)!.push(p);
  }

  const rows: ResultRow[] = [];
  const bars: { label: string; value: number; color?: string }[] = [];

  const sortedKeys = [...groups.keys()].sort();
  for (const key of sortedKeys) {
    const pts = groups.get(key)!;
    if (pts.length < 3 && metric === "pearson_r") continue;

    let val: number;
    let label: string;

    if (metric === "pearson_r") {
      val = pearsonR(pts.map((p) => p.x), pts.map((p) => p.y));
      label = `r = ${val.toFixed(3)} (n=${pts.length})`;
    } else if (metric === "median") {
      const sorted = dataset === "y"
        ? pts.map((p) => p.raw_y).sort((a, b) => a - b)
        : pts.map((p) => p.raw_x).sort((a, b) => a - b);
      val = sorted[Math.floor(sorted.length / 2)];
      label = `median = ${val.toFixed(3)} (n=${pts.length})`;
    } else {
      // mean
      if (dataset === "y") {
        val = pts.reduce((a, p) => a + p.raw_y, 0) / pts.length;
      } else {
        val = pts.reduce((a, p) => a + p.raw_x, 0) / pts.length;
      }
      label = `mean = ${val.toFixed(3)} (n=${pts.length})`;
    }

    rows.push({ label: key, value: label });
    bars.push({ label: key, value: val });
  }

  // Sort bars by value descending
  bars.sort((a, b) => b.value - a.value);

  const metricLabel = metric === "pearson_r" ? "correlation" : metric;
  const dsLabel = dataset === "y" ? DOMAIN_LABELS[yDs] : dataset === "x" ? DOMAIN_LABELS[xDs] : "both";

  return {
    type: "aggregate",
    title: `${metricLabel} of ${dsLabel} by ${groupBy}`,
    sampleSize: points.length,
    highlightFips: [],
    rows,
    bars,
  };
}

export function executeCompareCohort(
  points: ScatterPoint[],
  params: Record<string, unknown>,
  xDs: string,
  yDs: string,
): QueryResult {
  const cohort = (params.cohort as string) || "outliers";
  const allRawX = points.map((p) => p.raw_x);
  const allRawY = points.map((p) => p.raw_y);

  let selected: ScatterPoint[];
  let cohortLabel: string;

  if (cohort === "outliers") {
    const residuals = points.map((p) => p.residual);
    const resMean = residuals.reduce((a, b) => a + b, 0) / residuals.length;
    const resStd = Math.sqrt(residuals.reduce((a, v) => a + (v - resMean) ** 2, 0) / residuals.length);
    selected = points.filter((p) => Math.abs(p.residual) > 2 * resStd);
    cohortLabel = "Outlier counties (>2σ from regression)";
  } else if (cohort === "top_quartile") {
    selected = points.filter((p) => {
      const px = percentileOf(p.raw_x, allRawX);
      const py = percentileOf(p.raw_y, allRawY);
      return px >= 75 && py >= 75;
    });
    cohortLabel = "Top quartile on both dimensions";
  } else if (cohort === "bottom_quartile") {
    selected = points.filter((p) => {
      const px = percentileOf(p.raw_x, allRawX);
      const py = percentileOf(p.raw_y, allRawY);
      return px <= 25 && py <= 25;
    });
    cohortLabel = "Bottom quartile on both dimensions";
  } else {
    selected = [];
    cohortLabel = "Selected counties";
  }

  if (selected.length === 0) {
    return {
      type: "compare_cohort",
      title: `No counties in cohort: ${cohortLabel}`,
      sampleSize: 0,
      highlightFips: [],
      rows: [],
    };
  }

  // Compute cohort means vs national
  const cohortMeanX = selected.reduce((a, p) => a + p.raw_x, 0) / selected.length;
  const cohortMeanY = selected.reduce((a, p) => a + p.raw_y, 0) / selected.length;
  const natMeanX = points.reduce((a, p) => a + p.raw_x, 0) / points.length;
  const natMeanY = points.reduce((a, p) => a + p.raw_y, 0) / points.length;

  // Region breakdown
  const regionCounts = new Map<string, number>();
  for (const p of selected) {
    const r = regionOf(p.fips);
    regionCounts.set(r, (regionCounts.get(r) || 0) + 1);
  }

  const rows: ResultRow[] = [
    { label: `Cohort ${DOMAIN_LABELS[xDs]}`, value: `${cohortMeanX.toFixed(3)} vs national ${natMeanX.toFixed(3)}` },
    { label: `Cohort ${DOMAIN_LABELS[yDs]}`, value: `${cohortMeanY.toFixed(3)} vs national ${natMeanY.toFixed(3)}` },
    { label: "Region breakdown", value: [...regionCounts.entries()].map(([r, c]) => `${r}: ${c}`).join(", ") },
  ];

  return {
    type: "compare_cohort",
    title: `${cohortLabel}`,
    sampleSize: selected.length,
    highlightFips: selected.map((p) => p.fips),
    rows,
  };
}

export function executeRank(
  points: ScatterPoint[],
  params: Record<string, unknown>,
  xDs: string,
  yDs: string,
): QueryResult {
  const dataset = (params.dataset as string) || "x";
  const direction = (params.direction as string) || "top";
  const n = Math.min((params.n as number) || 10, 50);

  const sorted = [...points].sort((a, b) => {
    const va = dataset === "y" ? a.raw_y : a.raw_x;
    const vb = dataset === "y" ? b.raw_y : b.raw_x;
    return direction === "top" ? vb - va : va - vb;
  });

  const top = sorted.slice(0, n);
  const dsLabel = dataset === "y" ? DOMAIN_LABELS[yDs] : DOMAIN_LABELS[xDs];

  return {
    type: "rank",
    title: `${direction === "top" ? "Top" : "Bottom"} ${n} counties for ${dsLabel}`,
    sampleSize: points.length,
    highlightFips: top.map((p) => p.fips),
    rows: top.map((p, i) => ({
      label: `#${i + 1} ${p.name || `FIPS ${p.fips}`}`,
      value: `${(dataset === "y" ? p.raw_y : p.raw_x).toFixed(3)}`,
      fips: p.fips,
    })),
  };
}

export function executeConceptual(
  params: Record<string, unknown>,
  points: ScatterPoint[],
  xDs: string,
  yDs: string,
): QueryResult {
  const reason = (params.reason as string) || "This question goes beyond the current dataset";
  const related = (params.related_questions as string[]) || [];

  // Compute what we CAN say
  const natMeanX = points.reduce((a, p) => a + p.raw_x, 0) / points.length;
  const natMeanY = points.reduce((a, p) => a + p.raw_y, 0) / points.length;
  const r = pearsonR(points.map((p) => p.x), points.map((p) => p.y));

  const rows: ResultRow[] = [
    { label: "Current correlation (r)", value: r.toFixed(3) },
    { label: `National mean ${DOMAIN_LABELS[xDs]}`, value: natMeanX.toFixed(3) },
    { label: `National mean ${DOMAIN_LABELS[yDs]}`, value: natMeanY.toFixed(3) },
    { label: "Counties in view", value: String(points.length) },
  ];

  const suggestions = related.length > 0 ? related : [
    `Which region has the highest ${DOMAIN_LABELS[xDs]}?`,
    `Show the top 10 counties for ${DOMAIN_LABELS[yDs]}`,
    `What do the outlier counties have in common?`,
  ];

  return {
    type: "conceptual",
    title: reason,
    sampleSize: points.length,
    highlightFips: [],
    rows,
    suggestions,
  };
}

// ── Router ───────────────────────────────────────────────────

export function executeQuery(
  queryType: QueryType,
  params: Record<string, unknown>,
  points: ScatterPoint[],
  xDs: string,
  yDs: string,
): QueryResult {
  switch (queryType) {
    case "filter":
      return executeFilter(points, params, xDs, yDs);
    case "aggregate":
      return executeAggregate(points, params, xDs, yDs);
    case "compare_cohort":
      return executeCompareCohort(points, params, xDs, yDs);
    case "rank":
      return executeRank(points, params, xDs, yDs);
    case "conceptual":
      return executeConceptual(params, points, xDs, yDs);
    default:
      return executeConceptual({ reason: "Unknown query type" }, points, xDs, yDs);
  }
}
