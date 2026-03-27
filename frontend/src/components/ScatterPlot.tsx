import {
  ScatterChart,
  Scatter,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
  ReferenceLine,
  Cell,
} from "recharts";
import type { ScatterPoint } from "../lib/api";
import { DOMAIN_LABELS } from "../lib/constants";

interface Props {
  points: ScatterPoint[];
  datasetX: string;
  datasetY: string;
  r: number;
  n: number;
  selectedFips: string | null;
  highlightedFips: string | null;
  highlightFipsList: Set<string>;
  onClickPoint: (point: ScatterPoint) => void;
}

export default function ScatterPlot({
  points, datasetX, datasetY, r, n,
  selectedFips, highlightedFips, highlightFipsList, onClickPoint,
}: Props) {
  const hasListHighlight = highlightFipsList.size > 0;

  return (
    <div className="scatter-container">
      <div className="scatter-header">
        <h2>
          {DOMAIN_LABELS[datasetX]} vs {DOMAIN_LABELS[datasetY]}
        </h2>
        <span className="scatter-stats">
          r = {r.toFixed(3)} · r² = {(r * r).toFixed(3)} · n = {n}
        </span>
      </div>
      <ResponsiveContainer width="100%" height={500}>
        <ScatterChart margin={{ top: 10, right: 20, bottom: 40, left: 40 }}>
          <CartesianGrid strokeDasharray="3 3" stroke="#2a2a3e" />
          <XAxis
            dataKey="x"
            type="number"
            name={DOMAIN_LABELS[datasetX]}
            label={{ value: DOMAIN_LABELS[datasetX], position: "bottom", fill: "#94a3b8", offset: 20 }}
            tick={{ fill: "#64748b", fontSize: 11 }}
            stroke="#334155"
          />
          <YAxis
            dataKey="y"
            type="number"
            name={DOMAIN_LABELS[datasetY]}
            label={{ value: DOMAIN_LABELS[datasetY], angle: -90, position: "left", fill: "#94a3b8", offset: 20 }}
            tick={{ fill: "#64748b", fontSize: 11 }}
            stroke="#334155"
          />
          <ReferenceLine y={0} stroke="#475569" strokeDasharray="2 2" />
          <ReferenceLine x={0} stroke="#475569" strokeDasharray="2 2" />
          <Tooltip
            cursor={{ strokeDasharray: "3 3" }}
            content={({ payload }) => {
              if (!payload?.length) return null;
              const p = payload[0].payload as ScatterPoint;
              return (
                <div className="scatter-tooltip">
                  <strong>{p.name || `FIPS ${p.fips}`}</strong>
                  <div>x: {p.raw_x.toFixed(3)} → {p.x.toFixed(3)}</div>
                  <div>y: {p.raw_y.toFixed(3)} → {p.y.toFixed(3)}</div>
                  <div>residual: {p.residual.toFixed(3)}</div>
                </div>
              );
            }}
          />
          <Scatter
            data={points}
            onClick={(data) => {
              if (data && data.payload) onClickPoint(data.payload as ScatterPoint);
            }}
            style={{ cursor: "pointer" }}
          >
            {points.map((p) => {
              const isSelected = p.fips === selectedFips;
              const isHighlighted = p.fips === highlightedFips;
              const isInList = hasListHighlight && highlightFipsList.has(p.fips);
              const isDimmed = hasListHighlight && !isInList && !isSelected;

              let fill: string;
              let stroke = "none";
              let strokeW = 0;
              let radius = 3;

              if (isSelected) {
                fill = "#f97316"; stroke = "#fff"; strokeW = 2; radius = 6;
              } else if (isHighlighted) {
                fill = "#facc15"; stroke = "#fff"; strokeW = 1.5; radius = 5;
              } else if (isInList) {
                fill = "#22d3ee"; radius = 4;
              } else if (isDimmed) {
                fill = "rgba(99, 102, 241, 0.15)";
              } else {
                fill = "rgba(99, 102, 241, 0.5)";
              }

              return (
                <Cell
                  key={p.fips}
                  fill={fill}
                  stroke={stroke}
                  strokeWidth={strokeW}
                  r={radius}
                />
              );
            })}
          </Scatter>
        </ScatterChart>
      </ResponsiveContainer>
    </div>
  );
}
