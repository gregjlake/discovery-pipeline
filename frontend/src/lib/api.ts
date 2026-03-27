const BASE = "http://localhost:8000/api";

export interface DatasetInfo {
  dataset_id: string;
  value_column: string;
  description: string;
  county_count: number;
  row_count: number;
}

export interface ScatterPoint {
  fips: string;
  name: string;
  region: string;
  x: number;
  y: number;
  raw_x: number;
  raw_y: number;
  pop: number | null;
  residual: number;
}

export interface ScatterResponse {
  query_id: string;
  r: number;
  n: number;
  r_squared: number;
  points: ScatterPoint[];
  config: {
    dataset_x: string;
    dataset_y: string;
    norm_method: string;
    outlier_method: string;
    weight_method: string;
  };
}

export interface RobustnessResult {
  nm: string;
  om: string;
  r: number | null;
  n: number;
}

export interface ProvenanceInfo {
  dataset_id: string;
  source_name: string;
  source_url: string;
  download_date: string;
  file_hash: string;
  row_count: number;
  counties_matched: number;
  notes: string;
  value_column: string;
  raw_min: number;
  raw_max: number;
  raw_mean: number;
  missing_values: number;
}

export async function fetchDatasets(): Promise<DatasetInfo[]> {
  const res = await fetch(`${BASE}/datasets`);
  return res.json();
}

export async function fetchScatter(
  datasetX: string,
  datasetY: string,
  normMethod = "zscore",
  outlierMethod = "keep",
  weightMethod = "equal"
): Promise<ScatterResponse> {
  const res = await fetch(`${BASE}/scatter`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      dataset_x: datasetX,
      dataset_y: datasetY,
      norm_method: normMethod,
      outlier_method: outlierMethod,
      weight_method: weightMethod,
    }),
  });
  return res.json();
}

export async function fetchRobustness(
  datasetX: string,
  datasetY: string
): Promise<RobustnessResult[]> {
  const res = await fetch(`${BASE}/robustness`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ dataset_x: datasetX, dataset_y: datasetY }),
  });
  return res.json();
}

export async function fetchProvenance(
  datasetId: string
): Promise<ProvenanceInfo> {
  const res = await fetch(`${BASE}/provenance/${datasetId}`);
  return res.json();
}

export interface AskResponse {
  query_type: string;
  params: Record<string, unknown>;
  raw_llm_json?: string | null;
  error?: string | null;
}

export async function askQuestion(
  question: string,
  datasetX: string,
  datasetY: string,
): Promise<AskResponse> {
  const res = await fetch(`${BASE}/ask`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      question,
      dataset_x: datasetX,
      dataset_y: datasetY,
    }),
  });
  return res.json();
}
