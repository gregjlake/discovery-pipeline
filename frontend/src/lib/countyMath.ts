import type { ScatterPoint } from "./api";

/** Compute percentile rank (0–100) of value within an array */
export function percentileOf(value: number, values: number[]): number {
  const below = values.filter((v) => v < value).length;
  const equal = values.filter((v) => v === value).length;
  return ((below + equal * 0.5) / values.length) * 100;
}

/** Compute σ deviation from OLS regression line using residual and y std */
export function sigmaDeviation(
  residual: number,
  points: ScatterPoint[]
): { sigma: number; label: string } {
  const yVals = points.map((p) => p.y);
  const mean = yVals.reduce((a, b) => a + b, 0) / yVals.length;
  const std = Math.sqrt(
    yVals.reduce((a, v) => a + (v - mean) ** 2, 0) / yVals.length
  );
  const sigma = std > 0 ? residual / std : 0;
  let label: string;
  if (Math.abs(sigma) < 0.5) label = "near trend";
  else if (sigma > 0) label = "above trend";
  else label = "below trend";
  return { sigma, label };
}

/** Build percentile tier: ▲ top 25%, ▼ bottom 25%, – middle */
export function tierLabel(pct: number): string {
  if (pct >= 75) return "▲";
  if (pct <= 25) return "▼";
  return "–";
}

/** Build a plain-English summary from the tiers */
export function buildProfileSummary(
  tiers: Record<string, { pct: number; label: string }>
): string {
  const high: string[] = [];
  const low: string[] = [];
  for (const [, { pct, label }] of Object.entries(tiers)) {
    if (pct >= 75) high.push(label);
    else if (pct <= 25) low.push(label);
  }
  const parts: string[] = [];
  if (high.length) parts.push(`Ranks high on ${high.join(" and ")}`);
  if (low.length) parts.push(`low on ${low.join(" and ")}`);
  return parts.join(", ") || "Near national median across all measures";
}

/** Find k nearest counties by Euclidean distance on normalized values */
export function findSimilarCounties(
  target: ScatterPoint,
  allPoints: ScatterPoint[],
  k = 5
): { point: ScatterPoint; distance: number; similarity: number }[] {
  const others = allPoints.filter((p) => p.fips !== target.fips);
  const withDist = others.map((p) => {
    const dx = p.x - target.x;
    const dy = p.y - target.y;
    return { point: p, distance: Math.sqrt(dx * dx + dy * dy) };
  });
  withDist.sort((a, b) => a.distance - b.distance);
  const top = withDist.slice(0, k);
  const maxDist = top.length ? Math.max(...top.map((t) => t.distance), 0.001) : 1;
  return top.map((t) => ({
    ...t,
    similarity: Math.round(Math.max(0, (1 - t.distance / (maxDist * 1.5)) * 100)),
  }));
}
