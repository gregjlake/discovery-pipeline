const BASE = "http://localhost:8000/api";

export async function fetchDatasets() {
  const res = await fetch(`${BASE}/datasets`);
  return res.json();
}

export async function fetchScatter(datasetX, datasetY, normMethod="zscore", outlierMethod="keep", weightMethod="equal") {
  const res = await fetch(`${BASE}/scatter`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      dataset_x: datasetX,
      dataset_y: datasetY,
      norm_method: normMethod,
      outlier_method: outlierMethod,
      weight_method: weightMethod,
    })
  });
  return res.json();
}

export async function fetchRobustness(datasetX, datasetY) {
  const res = await fetch(`${BASE}/robustness`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ dataset_x: datasetX, dataset_y: datasetY })
  });
  return res.json();
}

export async function fetchProvenance(datasetId) {
  const res = await fetch(`${BASE}/provenance/${datasetId}`);
  return res.json();
}
