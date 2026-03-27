import type { ScatterPoint } from "../lib/api";
import {
  DOMAIN_COLORS,
  DOMAIN_LABELS,
  DOMAIN_UNITS,
} from "../lib/constants";
import {
  percentileOf,
  sigmaDeviation,
  tierLabel,
  buildProfileSummary,
  findSimilarCounties,
} from "../lib/countyMath";
import { generateFlags } from "../lib/flagsEngine";

interface Props {
  point: ScatterPoint;
  allPoints: ScatterPoint[];
  datasetX: string;
  datasetY: string;
  onClose: () => void;
  onSelectCounty: (fips: string) => void;
}

/** Build a pseudo name from FIPS (real names need a lookup; use fips as fallback) */
function countyDisplay(p: ScatterPoint) {
  return p.name || `County ${p.fips}`;
}

function stateFromFips(fips: string) {
  return fips.slice(0, 2);
}

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

export default function CountyPanel({
  point, allPoints, datasetX, datasetY, onClose, onSelectCounty,
}: Props) {
  const stateFips = stateFromFips(point.fips);
  const region = point.region || REGION_MAP[stateFips] || "Unknown";

  // Percentiles for X and Y within current scatter
  const rawXvals = allPoints.map((p) => p.raw_x);
  const rawYvals = allPoints.map((p) => p.raw_y);
  const pctX = percentileOf(point.raw_x, rawXvals);
  const pctY = percentileOf(point.raw_y, rawYvals);

  // Sigma deviation
  const { sigma, label: trendLabel } = sigmaDeviation(point.residual, allPoints);
  const sigmaAbs = Math.abs(sigma).toFixed(1);
  const direction = sigma >= 0 ? "above" : "below";

  // Cross-dataset profile (only have X and Y in current scatter)
  const datasets = [datasetX, datasetY];
  const values: Record<string, { raw: number; pct: number; label: string }> = {
    [datasetX]: { raw: point.raw_x, pct: pctX, label: DOMAIN_LABELS[datasetX] },
    [datasetY]: { raw: point.raw_y, pct: pctY, label: DOMAIN_LABELS[datasetY] },
  };

  const tiers: Record<string, { pct: number; label: string }> = {};
  for (const ds of datasets) {
    tiers[ds] = { pct: values[ds].pct, label: values[ds].label };
  }
  const summary = buildProfileSummary(tiers);

  // Similar counties
  const similar = findSimilarCounties(point, allPoints, 5);

  // Investigation flags
  const flags = generateFlags(point, allPoints, datasetX, datasetY);

  return (
    <div className="county-panel">
      <button className="close-btn" onClick={onClose}>✕</button>

      {/* Section 1: County Facts */}
      <div className="panel-section">
        <h3>{countyDisplay(point)}</h3>
        <p className="county-meta">
          State FIPS {stateFips} · {region}
        </p>

        {datasets.map((ds) => {
          const v = values[ds];
          const color = DOMAIN_COLORS[ds] || "#888";
          const unit = DOMAIN_UNITS[ds] || "";
          return (
            <div key={ds} className="fact-row">
              <div className="fact-label" style={{ color }}>
                {v.label}
              </div>
              <div className="fact-value">
                {v.raw.toFixed(3)} {unit}
              </div>
              <div className="fact-pct">P{v.pct.toFixed(0)}</div>
              <div className="pct-bar-track">
                <div
                  className="pct-bar-fill"
                  style={{ width: `${v.pct}%`, backgroundColor: color }}
                />
                <div
                  className="pct-bar-marker"
                  style={{ left: `${v.pct}%` }}
                />
              </div>
            </div>
          );
        })}

        <div className="deviation-row">
          <span className={`trend-badge ${trendLabel.replace(" ", "-")}`}>
            {trendLabel}
          </span>
          <span className="deviation-text">
            {sigmaAbs}σ {direction} expected {DOMAIN_LABELS[datasetY]} given{" "}
            {DOMAIN_LABELS[datasetX]}
          </span>
        </div>
      </div>

      {/* Section 2: Cross-dataset profile */}
      <div className="panel-section">
        <h3>Cross-dataset Profile</h3>
        <div className="profile-bars">
          {datasets.map((ds) => {
            const v = values[ds];
            const color = DOMAIN_COLORS[ds] || "#888";
            const tier = tierLabel(v.pct);
            return (
              <div key={ds} className="profile-bar-row">
                <span className="profile-label">{v.label}</span>
                <span className="profile-tier">{tier}</span>
                <div className="profile-bar-track">
                  <div
                    className="profile-bar-fill"
                    style={{
                      width: `${v.pct}%`,
                      backgroundColor: color,
                    }}
                  />
                </div>
              </div>
            );
          })}
        </div>
        <p className="profile-summary">{summary}</p>
      </div>

      {/* Section 3: Similar counties */}
      <div className="panel-section">
        <h3>Similar Counties</h3>
        <ul className="similar-list">
          {similar.map((s) => (
            <li
              key={s.point.fips}
              className="similar-item"
              onClick={() => onSelectCounty(s.point.fips)}
            >
              <span className="similar-name">{countyDisplay(s.point)}</span>
              <span className="similar-score">{s.similarity}% similar</span>
            </li>
          ))}
        </ul>
      </div>

      {/* Section 4: Investigation flags */}
      {flags.length > 0 && (
        <div className="panel-section">
          <h3><span className="flag-icon">&#9879;</span> Investigate Further</h3>
          <div className="flag-list">
            {flags.map((flag, i) => (
              <div
                key={i}
                className={`flag-card flag-${flag.kind}`}
              >
                <div className="flag-headline">{flag.headline}</div>
                <div className="flag-description">{flag.description}</div>
                <button className="flag-action">{flag.action}</button>
                <div className="flag-source">Generated from data thresholds — not AI</div>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
