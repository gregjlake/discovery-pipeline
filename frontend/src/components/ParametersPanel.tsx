import type { DatasetInfo } from "../lib/api";
import { NORM_METHODS, OUTLIER_METHODS, WEIGHT_METHODS, DOMAIN_LABELS } from "../lib/constants";

interface Props {
  datasets: DatasetInfo[];
  datasetX: string;
  datasetY: string;
  normMethod: string;
  outlierMethod: string;
  weightMethod: string;
  onDatasetX: (v: string) => void;
  onDatasetY: (v: string) => void;
  onNormMethod: (v: string) => void;
  onOutlierMethod: (v: string) => void;
  onWeightMethod: (v: string) => void;
}

export default function ParametersPanel({
  datasets, datasetX, datasetY,
  normMethod, outlierMethod, weightMethod,
  onDatasetX, onDatasetY, onNormMethod, onOutlierMethod, onWeightMethod,
}: Props) {
  return (
    <div className="panel-section">
      <h3>Parameters</h3>

      <label>X-axis dataset</label>
      <select value={datasetX} onChange={(e) => onDatasetX(e.target.value)}>
        {datasets.map((d) => (
          <option key={d.dataset_id} value={d.dataset_id}>
            {DOMAIN_LABELS[d.dataset_id] ?? d.dataset_id} ({d.county_count})
          </option>
        ))}
      </select>

      <label>Y-axis dataset</label>
      <select value={datasetY} onChange={(e) => onDatasetY(e.target.value)}>
        {datasets.map((d) => (
          <option key={d.dataset_id} value={d.dataset_id}>
            {DOMAIN_LABELS[d.dataset_id] ?? d.dataset_id} ({d.county_count})
          </option>
        ))}
      </select>

      <label>Normalization</label>
      <select value={normMethod} onChange={(e) => onNormMethod(e.target.value)}>
        {NORM_METHODS.map((m) => (
          <option key={m} value={m}>{m}</option>
        ))}
      </select>

      <label>Outlier treatment</label>
      <select value={outlierMethod} onChange={(e) => onOutlierMethod(e.target.value)}>
        {OUTLIER_METHODS.map((m) => (
          <option key={m} value={m}>{m}</option>
        ))}
      </select>

      <label>Weighting</label>
      <select value={weightMethod} onChange={(e) => onWeightMethod(e.target.value)}>
        {WEIGHT_METHODS.map((m) => (
          <option key={m} value={m}>{m}</option>
        ))}
      </select>
    </div>
  );
}
