import { useEffect, useState } from "react";
import { fetchRobustness, type RobustnessResult } from "../lib/api";
import { NORM_METHODS, OUTLIER_METHODS } from "../lib/constants";

interface Props {
  datasetX: string;
  datasetY: string;
}

export default function RobustnessPanel({ datasetX, datasetY }: Props) {
  const [results, setResults] = useState<RobustnessResult[]>([]);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    setLoading(true);
    fetchRobustness(datasetX, datasetY)
      .then(setResults)
      .catch(() => setResults([]))
      .finally(() => setLoading(false));
  }, [datasetX, datasetY]);

  const grid = new Map<string, RobustnessResult>();
  for (const r of results) grid.set(`${r.nm}|${r.om}`, r);

  const rValues = results.map((r) => r.r).filter((r): r is number => r !== null);
  const minR = Math.min(...rValues);
  const maxR = Math.max(...rValues);

  function cellColor(r: number | null): string {
    if (r === null) return "#1e1e2e";
    const t = maxR > minR ? (r - minR) / (maxR - minR) : 0.5;
    const g = Math.round(60 + t * 140);
    const rb = Math.round(60 + (1 - t) * 60);
    return `rgb(${rb}, ${g}, ${rb})`;
  }

  if (loading) return <div className="panel-section"><h3>Robustness</h3><p>Computing…</p></div>;

  return (
    <div className="panel-section">
      <h3>Robustness Grid</h3>
      <p className="subtext">r across all norm × outlier combos</p>
      <table className="robustness-grid">
        <thead>
          <tr>
            <th></th>
            {OUTLIER_METHODS.map((om) => <th key={om}>{om}</th>)}
          </tr>
        </thead>
        <tbody>
          {NORM_METHODS.map((nm) => (
            <tr key={nm}>
              <td className="row-label">{nm}</td>
              {OUTLIER_METHODS.map((om) => {
                const cell = grid.get(`${nm}|${om}`);
                const r = cell?.r ?? null;
                return (
                  <td key={om} style={{ backgroundColor: cellColor(r) }}>
                    {r !== null ? r.toFixed(3) : "–"}
                  </td>
                );
              })}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
