import type { ScatterPoint } from "./api";
import { DOMAIN_LABELS, DOMAIN_UNITS } from "./constants";
import { percentileOf } from "./countyMath";

export interface InvestigationFlag {
  headline: string;
  description: string;
  action: string;
  /** "outlier" = orange border, "pattern" = blue border */
  kind: "outlier" | "pattern";
}

/**
 * Pure rules engine: generates investigation flags from statistical thresholds.
 * No LLM — every flag is a deterministic if/then on the data.
 */
export function generateFlags(
  county: ScatterPoint,
  allPoints: ScatterPoint[],
  xDs: string,
  yDs: string
): InvestigationFlag[] {
  const flags: InvestigationFlag[] = [];

  const rawXvals = allPoints.map((p) => p.raw_x);
  const rawYvals = allPoints.map((p) => p.raw_y);
  const pctX = percentileOf(county.raw_x, rawXvals);
  const pctY = percentileOf(county.raw_y, rawYvals);

  // Residual std across all points
  const residuals = allPoints.map((p) => p.residual);
  const resMean = residuals.reduce((a, b) => a + b, 0) / residuals.length;
  const residualStd = Math.sqrt(
    residuals.reduce((a, v) => a + (v - resMean) ** 2, 0) / residuals.length
  );

  const xLabel = DOMAIN_LABELS[xDs] ?? xDs;
  const yLabel = DOMAIN_LABELS[yDs] ?? yDs;
  const xUnit = DOMAIN_UNITS[xDs] ?? "";
  const yUnit = DOMAIN_UNITS[yDs] ?? "";
  const sigmaFromLine = residualStd > 0 ? county.residual / residualStd : 0;

  // ── Rule 1: Strong outlier ────────────────────────────────
  if (Math.abs(county.residual) > 2.0 * residualStd) {
    flags.push({
      kind: "outlier",
      headline: "Strong outlier \u2014 breaks the pattern",
      description: `This county is ${Math.abs(sigmaFromLine).toFixed(1)}\u03C3 from the regression line. Something unusual may be happening here.`,
      action: "Compare with the 5 most similar counties on all other dimensions",
    });
  }

  // ── Rule 2: High on both axes ─────────────────────────────
  if (pctX > 75 && pctY > 75) {
    flags.push({
      kind: "pattern",
      headline: "Above median on both dimensions",
      description: `Ranks in top 25% for both ${xLabel} and ${yLabel}`,
      action: "Filter to all counties in this quadrant to see the full pattern",
    });
  }

  // ── Rule 3: Low on both axes ──────────────────────────────
  if (pctX < 25 && pctY < 25) {
    flags.push({
      kind: "pattern",
      headline: "Below median on both dimensions",
      description: `Ranks in bottom 25% for both datasets \u2014 part of a cluster worth studying`,
      action: "Filter scatter to bottom-left quadrant",
    });
  }

  // ── Rule 4: High X, unexpectedly low Y ────────────────────
  if (pctX > 70 && county.residual < -1.5 * residualStd) {
    flags.push({
      kind: "outlier",
      headline: `${xLabel} is high but ${yLabel} is lower than expected`,
      description: `Despite ranking in the top 30% for ${xLabel}, this county underperforms on ${yLabel}`,
      action: "Check other dataset values \u2014 a confounding variable may explain this",
    });
  }

  // ── Rule 5: Low X, unexpectedly high Y ────────────────────
  if (pctX < 30 && county.residual > 1.5 * residualStd) {
    flags.push({
      kind: "outlier",
      headline: `Outperforms despite low ${xLabel}`,
      description: `This county achieves above-expected ${yLabel} despite low ${xLabel} \u2014 a potential positive outlier worth studying`,
      action: "Look for what other variables distinguish this county",
    });
  }

  // ── Rule 6: Extreme on any single dataset ─────────────────
  const extremes: { ds: string; pct: number; raw: number; unit: string }[] = [
    { ds: xDs, pct: pctX, raw: county.raw_x, unit: xUnit },
    { ds: yDs, pct: pctY, raw: county.raw_y, unit: yUnit },
  ];
  for (const { ds, pct, raw, unit } of extremes) {
    const label = DOMAIN_LABELS[ds] ?? ds;
    if (pct >= 95) {
      flags.push({
        kind: "pattern",
        headline: `Extreme value: ${label}`,
        description: `Ranks in the top 5% nationally for ${label} \u2014 ${raw.toFixed(3)} ${unit}`,
        action: `Filter scatter plot to show only counties with similar ${label} values`,
      });
    } else if (pct <= 5) {
      flags.push({
        kind: "pattern",
        headline: `Extreme value: ${label}`,
        description: `Ranks in the bottom 5% nationally for ${label} \u2014 ${raw.toFixed(3)} ${unit}`,
        action: `Filter scatter plot to show only counties with similar ${label} values`,
      });
    }
  }

  return flags;
}
