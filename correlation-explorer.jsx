import React, { useEffect, useState, useCallback, useMemo } from "react";
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

// ── Configuration ────────────────────────────────────────────
const API_BASE = "https://discovery-pipeline-production.up.railway.app/api";
// For local dev: const API_BASE = "http://localhost:8000/api";

const DOMAIN_COLORS = {
  library: "#6366f1", mobility: "#f59e0b", air: "#10b981", broadband: "#3b82f6",
  eitc: "#ec4899", poverty: "#ef4444", median_income: "#8b5cf6",
  bea_income: "#a855f7", food_access: "#f97316", obesity: "#dc2626",
  diabetes: "#e11d48", mental_health: "#0891b2", hypertension: "#be123c",
  unemployment: "#ca8a04", rural_urban: "#65a30d", housing_burden: "#7c3aed",
  voter_turnout: "#0284c7",
};

const DOMAIN_LABELS = {
  library: "Library Spending", mobility: "Upward Mobility", air: "Air Quality",
  broadband: "Broadband Access", eitc: "EITC Rate", poverty: "Poverty Rate",
  median_income: "Median Income", bea_income: "Per Capita Income",
  food_access: "SNAP Rate", obesity: "Obesity Rate", diabetes: "Diabetes Rate",
  mental_health: "Mental Health", hypertension: "Hypertension Rate",
  unemployment: "Unemployment Rate", rural_urban: "Rural-Urban Code",
  housing_burden: "Housing Burden", voter_turnout: "Votes Cast 2020",
};

const DOMAIN_UNITS = {
  library: "$/capita", mobility: "rank (0-1)", air: "AQI inv.", broadband: "rate (0-1)",
  eitc: "rate (0-1)", poverty: "%", median_income: "$", bea_income: "$/person/yr",
  food_access: "% households", obesity: "% adults", diabetes: "% adults",
  mental_health: "% adults", hypertension: "% adults", unemployment: "% unemployed",
  rural_urban: "code 1-9", housing_burden: "% cost-burdened", voter_turnout: "total votes",
};

// Full metadata for all 20 datasets: icon, label, unit, color, category
const DATASET_META = {
  library:        { icon: "\uD83D\uDCDA", label: "Library Spending",   unit: "$/capita/yr",    color: "#6366f1", category: "civic" },
  mobility:       { icon: "\uD83D\uDCC8", label: "Upward Mobility",    unit: "rank (0-1)",     color: "#f59e0b", category: "economic" },
  air:            { icon: "\uD83C\uDF2C\uFE0F", label: "Air Quality",        unit: "AQI inv.",       color: "#10b981", category: "environment" },
  broadband:      { icon: "\uD83D\uDCF6", label: "Broadband Access",   unit: "rate (0-1)",     color: "#3b82f6", category: "infrastructure" },
  eitc:           { icon: "\uD83D\uDCB3", label: "EITC Rate",          unit: "rate (0-1)",     color: "#ec4899", category: "economic" },
  poverty:        { icon: "\uD83D\uDCC9", label: "Poverty Rate",       unit: "%",              color: "#ef4444", category: "economic" },
  median_income:  { icon: "\uD83D\uDCB0", label: "Median Income",      unit: "$",              color: "#8b5cf6", category: "economic" },
  bea_income:     { icon: "\uD83D\uDCB5", label: "Per Capita Income",  unit: "$/person/yr",    color: "#a855f7", category: "economic" },
  food_access:    { icon: "\uD83C\uDF7D\uFE0F", label: "SNAP Rate",          unit: "% households",   color: "#f97316", category: "welfare" },
  obesity:        { icon: "\u2764\uFE0F",  label: "Obesity Rate",       unit: "% adults",       color: "#dc2626", category: "health" },
  diabetes:       { icon: "\uD83E\uDE78", label: "Diabetes Rate",      unit: "% adults",       color: "#e11d48", category: "health" },
  mental_health:  { icon: "\uD83E\uDDE0", label: "Mental Health",      unit: "% adults",       color: "#0891b2", category: "health" },
  hypertension:   { icon: "\uD83E\uDE7A", label: "Hypertension Rate",  unit: "% adults",       color: "#be123c", category: "health" },
  unemployment:   { icon: "\uD83D\uDCBC", label: "Unemployment Rate",  unit: "% unemployed",   color: "#ca8a04", category: "economic" },
  rural_urban:    { icon: "\uD83C\uDFE1", label: "Rural-Urban Code",   unit: "code 1-9",       color: "#65a30d", category: "geography" },
  housing_burden: { icon: "\uD83C\uDFE0", label: "Housing Burden",     unit: "% cost-burdened", color: "#7c3aed", category: "housing" },
  voter_turnout:  { icon: "\uD83D\uDDF3\uFE0F", label: "Votes Cast 2020",   unit: "total votes",    color: "#0284c7", category: "civic" },
};

const NORM_METHODS = ["zscore", "minmax", "rank", "log", "robust"];
const OUTLIER_METHODS = ["keep", "winsor5", "winsor1", "remove3"];

const REGION_COLORS = {
  South: "#ef4444", Northeast: "#3b82f6", Midwest: "#f59e0b", West: "#10b981",
};

// ── API helpers ──────────────────────────────────────────────
async function apiFetch(path) {
  const res = await fetch(`${API_BASE}${path}`);
  if (!res.ok) throw new Error(`API ${res.status}: ${path}`);
  return res.json();
}

async function apiPost(path, body) {
  const res = await fetch(`${API_BASE}${path}`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  if (!res.ok) throw new Error(`API ${res.status}: ${path}`);
  return res.json();
}

// ── OLS helpers ──────────────────────────────────────────────
function computeOLS(points) {
  if (!points || points.length < 3) return { slope: 0, intercept: 0, resStd: 1 };
  const n = points.length;
  const mx = points.reduce((a, p) => a + p.x, 0) / n;
  const my = points.reduce((a, p) => a + p.y, 0) / n;
  let cov = 0, varX = 0;
  for (const p of points) { cov += (p.x - mx) * (p.y - my); varX += (p.x - mx) ** 2; }
  const slope = varX > 0 ? cov / varX : 0;
  const intercept = my - slope * mx;
  const residuals = points.map((p) => p.y - (slope * p.x + intercept));
  const resMean = residuals.reduce((a, b) => a + b, 0) / n;
  const resStd = Math.sqrt(residuals.reduce((a, r) => a + (r - resMean) ** 2, 0) / n);
  return { slope, intercept, resStd: resStd || 1 };
}

// ── Percentile color helper ──────────────────────────────────
function pctColor(p) {
  if (p > 66) return "#4ade80";
  if (p > 33) return "#fbbf24";
  return "#f87171";
}

function zColor(z) {
  if (z > 0.5) return "#4ade80";
  if (z < -0.5) return "#f87171";
  return "#94a3b8";
}

// ── Flag border color ────────────────────────────────────────
function flagBorderColor(type) {
  if (type === "outlier") return "#f97316";
  if (type === "pattern") return "#3b82f6";
  if (type === "extreme") return "#8b5cf6";
  return "#475569";
}

// ══════════════════════════════════════════════════════════════
// MAIN COMPONENT
// ══════════════════════════════════════════════════════════════
export default function CorrelationExplorer() {
  // ── Datasets & params state ────────────────────────────────
  const [datasets, setDatasets] = useState([]);
  const [xDs, setXDs] = useState("poverty");
  const [yDs, setYDs] = useState("mobility");
  const [normMethod, setNormMethod] = useState("zscore");
  const [outlierMethod, setOutlierMethod] = useState("keep");

  // ── Scatter data state ─────────────────────────────────────
  const [scatter, setScatter] = useState(null);
  const [loading, setLoading] = useState(false);
  const [tab, setTab] = useState("params"); // params | source | robust

  // ── County detail state ────────────────────────────────────
  const [selectedCounty, setSelectedCounty] = useState(null);
  const [countyDetail, setCountyDetail] = useState(null);
  const [countyFlags, setCountyFlags] = useState(null);
  const [countyLoading, setCountyLoading] = useState(false);

  // ── OLS computed from scatter points ───────────────────────
  const ols = useMemo(() => computeOLS(scatter?.points), [scatter]);

  // ── Load dataset list ──────────────────────────────────────
  useEffect(() => {
    apiFetch("/datasets").then(setDatasets).catch(console.error);
  }, []);

  // ── Load scatter data ──────────────────────────────────────
  const loadScatter = useCallback(() => {
    setLoading(true);
    setSelectedCounty(null);
    setCountyDetail(null);
    setCountyFlags(null);
    apiPost("/scatter", {
      dataset_x: xDs, dataset_y: yDs,
      norm_method: normMethod, outlier_method: outlierMethod,
      weight_method: "equal",
    })
      .then(setScatter)
      .catch(console.error)
      .finally(() => setLoading(false));
  }, [xDs, yDs, normMethod, outlierMethod]);

  useEffect(() => {
    if (datasets.length > 0) loadScatter();
  }, [loadScatter, datasets]);

  // ── Dot click handler ──────────────────────────────────────
  const handleDotClick = async (point) => {
    if (selectedCounty?.fips === point.fips) {
      setSelectedCounty(null);
      setCountyDetail(null);
      setCountyFlags(null);
      return;
    }
    setSelectedCounty(point);
    setCountyLoading(true);
    try {
      const flagParams = new URLSearchParams({
        x: xDs, y: yDs,
        slope: String(ols.slope),
        intercept: String(ols.intercept),
        residual_std: String(ols.resStd),
        residual: String(point.residual),
      });
      const [detail, flags] = await Promise.all([
        apiFetch(`/county/${point.fips}`),
        apiFetch(`/county/${point.fips}/flags?${flagParams}`),
      ]);
      setCountyDetail(detail);
      setCountyFlags(flags);
    } catch (e) {
      console.error("County detail error:", e);
      setCountyDetail(null);
      setCountyFlags(null);
    } finally {
      setCountyLoading(false);
    }
  };

  const handleCloseCounty = () => {
    setSelectedCounty(null);
    setCountyDetail(null);
    setCountyFlags(null);
  };

  const handleSimilarClick = (fips) => {
    const found = scatter?.points.find((p) => p.fips === fips);
    if (found) handleDotClick(found);
  };

  // ── Render ─────────────────────────────────────────────────
  const xMeta = DATASET_META[xDs] || {};
  const yMeta = DATASET_META[yDs] || {};
  const xLabel = xMeta.label || DOMAIN_LABELS[xDs] || xDs;
  const yLabel = yMeta.label || DOMAIN_LABELS[yDs] || yDs;
  const xIcon = xMeta.icon || "";
  const yIcon = yMeta.icon || "";

  return (
    <div style={styles.app}>
      {/* Header */}
      <header style={styles.header}>
        <h1 style={styles.h1}>Discovery Surface</h1>
        <span style={styles.subtitle}>County-level correlation explorer · {datasets.length} datasets</span>
      </header>

      <div style={styles.body}>
        {/* ── Main scatter area ──────────────────────────── */}
        <main style={styles.main}>
          {loading && <div style={styles.loadingOverlay}>Loading...</div>}
          {scatter && (
            <div>
              {/* Scatter header */}
              <div style={styles.scatterHeader}>
                <h2 style={styles.h2}>{xIcon} {xLabel} vs {yIcon} {yLabel}</h2>
                <span style={styles.stats}>
                  r = {scatter.r.toFixed(3)} · r² = {(scatter.r ** 2).toFixed(3)} · n = {scatter.n}
                </span>
              </div>

              {/* Scatter chart */}
              <ResponsiveContainer width="100%" height={500}>
                <ScatterChart margin={{ top: 10, right: 20, bottom: 40, left: 40 }}>
                  <CartesianGrid strokeDasharray="3 3" stroke="#2a2a3e" />
                  <XAxis
                    dataKey="x" type="number" name={xLabel}
                    label={{ value: xLabel, position: "bottom", fill: "#94a3b8", offset: 20 }}
                    tick={{ fill: "#64748b", fontSize: 11 }} stroke="#334155"
                  />
                  <YAxis
                    dataKey="y" type="number" name={yLabel}
                    label={{ value: yLabel, angle: -90, position: "left", fill: "#94a3b8", offset: 20 }}
                    tick={{ fill: "#64748b", fontSize: 11 }} stroke="#334155"
                  />
                  <ReferenceLine y={0} stroke="#475569" strokeDasharray="2 2" />
                  <ReferenceLine x={0} stroke="#475569" strokeDasharray="2 2" />
                  <Tooltip content={({ payload }) => {
                    if (!payload?.length) return null;
                    const p = payload[0].payload;
                    return (
                      <div style={styles.tooltip}>
                        <strong style={{ color: "#f1f5f9" }}>{p.name || `FIPS ${p.fips}`}</strong>
                        <div>{p.region}</div>
                        <div>x: {p.raw_x.toFixed(3)} → {p.x.toFixed(3)}</div>
                        <div>y: {p.raw_y.toFixed(3)} → {p.y.toFixed(3)}</div>
                      </div>
                    );
                  }} />
                  <Scatter
                    data={scatter.points}
                    onClick={(data) => { if (data?.payload) handleDotClick(data.payload); }}
                    style={{ cursor: "pointer" }}
                  >
                    {scatter.points.map((p) => {
                      const isSelected = selectedCounty && p.fips === selectedCounty.fips;
                      const hasSel = !!selectedCounty;
                      return (
                        <Cell
                          key={p.fips}
                          fill={isSelected ? "#f97316" : (REGION_COLORS[p.region] || "rgba(99,102,241,0.5)")}
                          fillOpacity={hasSel && !isSelected ? 0.2 : (isSelected ? 1 : 0.6)}
                          stroke={isSelected ? "#fff" : "none"}
                          strokeWidth={isSelected ? 2.5 : 0}
                          r={isSelected ? 8 : 3}
                        />
                      );
                    })}
                  </Scatter>
                </ScatterChart>
              </ResponsiveContainer>
            </div>
          )}
        </main>

        {/* ── Side panel ─────────────────────────────────── */}
        <aside style={styles.sidePanel}>
          {selectedCounty && countyDetail ? (
            /* ── County detail panel ───────────────────── */
            <div style={styles.panelSlide} key={`county-${selectedCounty.fips}`}>
              {/* Close button */}
              <button style={styles.closeBtn} onClick={handleCloseCounty}>✕</button>

              {/* Header */}
              <div style={styles.section}>
                <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
                  <div style={{
                    width: 10, height: 10, borderRadius: "50%",
                    background: REGION_COLORS[countyDetail.region] || "#64748b",
                  }} />
                  <h3 style={{ ...styles.sectionTitle, fontSize: 16, textTransform: "none", letterSpacing: 0 }}>
                    {countyDetail.name || `County ${countyDetail.fips}`}
                  </h3>
                </div>
                <p style={styles.mutedText}>
                  State {countyDetail.state} · {countyDetail.region} · FIPS {countyDetail.fips}
                </p>
              </div>

              {countyLoading ? (
                <div style={{ ...styles.section, color: "#64748b" }}>Loading county data...</div>
              ) : (
                <>
                  {/* Dataset values */}
                  <div style={styles.section}>
                    <h3 style={styles.sectionTitle}>Dataset Values</h3>
                    {Object.entries(countyDetail.datasets).map(([dsId, ds]) => {
                      const meta = DATASET_META[dsId];
                      return (
                      <div key={dsId} style={styles.dsRow}>
                        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "baseline" }}>
                          <span style={{ fontSize: 12, fontWeight: 500, color: meta?.color || DOMAIN_COLORS[dsId] || "#94a3b8" }}>
                            {meta?.icon ? `${meta.icon} ` : ""}{meta?.label || DOMAIN_LABELS[dsId] || dsId}
                          </span>
                          <span style={{ fontSize: 12, fontFamily: "monospace", color: "#e2e8f0" }}>
                            {ds.raw_value} <span style={{ color: "#64748b", fontSize: 10 }}>{ds.unit}</span>
                          </span>
                        </div>
                        <div style={styles.barTrack}>
                          <div style={{
                            ...styles.barFill,
                            width: `${ds.national_percentile}%`,
                            background: DOMAIN_COLORS[dsId] || "#6366f1",
                          }} />
                        </div>
                        <div style={{ display: "flex", justifyContent: "space-between", marginTop: 2 }}>
                          <span style={{ fontSize: 10, color: pctColor(ds.national_percentile) }}>
                            P{ds.national_percentile.toFixed(0)}
                          </span>
                          <span style={{ fontSize: 10, fontFamily: "monospace", color: zColor(ds.z_score) }}>
                            {ds.z_score > 0 ? "+" : ""}{ds.z_score.toFixed(2)}σ
                          </span>
                        </div>
                      </div>
                      );
                    })}
                  </div>

                  {/* Regression position */}
                  <div style={styles.section}>
                    <h3 style={styles.sectionTitle}>Regression Position</h3>
                    {(() => {
                      const sigma = ols.resStd > 0 ? selectedCounty.residual / ols.resStd : 0;
                      const dir = sigma >= 0 ? "above" : "below";
                      const badge = Math.abs(sigma) < 0.5 ? "near trend" : dir === "above" ? "above trend" : "below trend";
                      const badgeColor = Math.abs(sigma) < 0.5 ? "#1e3a5f" : sigma > 0 ? "#166534" : "#7f1d1d";
                      const badgeText = Math.abs(sigma) < 0.5 ? "#60a5fa" : sigma > 0 ? "#4ade80" : "#f87171";
                      return (
                        <div style={{ background: "#1a1a2e", borderRadius: 6, padding: "8px 10px", display: "flex", alignItems: "center", gap: 8 }}>
                          <span style={{ fontSize: 11, fontWeight: 600, padding: "2px 8px", borderRadius: 10, background: badgeColor, color: badgeText, whiteSpace: "nowrap" }}>
                            {badge}
                          </span>
                          <span style={{ fontSize: 11, color: "#94a3b8" }}>
                            {Math.abs(sigma).toFixed(1)}σ {dir} expected {yLabel} given {xLabel}
                          </span>
                        </div>
                      );
                    })()}
                  </div>

                  {/* Similar counties */}
                  <div style={styles.section}>
                    <h3 style={styles.sectionTitle}>5 Most Similar Counties</h3>
                    {countyDetail.similar_counties?.map((s) => (
                      <div
                        key={s.fips}
                        style={styles.similarRow}
                        onClick={() => handleSimilarClick(s.fips)}
                      >
                        <div style={{ display: "flex", alignItems: "center", gap: 6, flex: 1 }}>
                          <div style={{
                            width: 8, height: 8, borderRadius: "50%",
                            background: REGION_COLORS[s.region] || "#64748b",
                          }} />
                          <span style={{ fontSize: 12, color: "#e2e8f0" }}>
                            {s.name || `FIPS ${s.fips}`}
                          </span>
                        </div>
                        <div style={{ display: "flex", alignItems: "center", gap: 6, minWidth: 80 }}>
                          <div style={{ flex: 1, height: 4, background: "#1e1e2e", borderRadius: 2, overflow: "hidden" }}>
                            <div style={{ height: "100%", width: `${s.similarity_score}%`, background: "#6366f1", borderRadius: 2 }} />
                          </div>
                          <span style={{ fontSize: 10, fontFamily: "monospace", color: "#64748b", minWidth: 28 }}>
                            {s.similarity_score}%
                          </span>
                        </div>
                      </div>
                    ))}
                  </div>

                  {/* Flags */}
                  <div style={styles.section}>
                    <h3 style={styles.sectionTitle}>
                      <span style={{ marginRight: 4 }}>&#9879;</span> Investigate Further
                    </h3>
                    <p style={{ fontSize: 9, color: "#475569", fontStyle: "italic", marginBottom: 10 }}>
                      Generated from statistical thresholds — not AI
                    </p>
                    {countyFlags && countyFlags.flags && countyFlags.flags.length > 0 ? (
                      countyFlags.flags.map((f, i) => (
                        <div key={i} style={{ ...styles.flagCard, borderLeftColor: flagBorderColor(f.type) }}>
                          <div style={{ fontSize: 12, fontWeight: 600, color: "#e2e8f0", marginBottom: 4, lineHeight: 1.3 }}>
                            {f.headline}
                          </div>
                          <div style={{ fontSize: 11, color: "#94a3b8", lineHeight: 1.4, marginBottom: 4 }}>
                            {f.description}
                          </div>
                          <div style={{ fontSize: 9, color: "#475569", textAlign: "right" }}>rules engine</div>
                        </div>
                      ))
                    ) : (
                      <p style={{ fontSize: 12, color: "#64748b", fontStyle: "italic" }}>
                        No unusual patterns detected for this county in the current view
                      </p>
                    )}
                  </div>
                </>
              )}
            </div>
          ) : (
            /* ── Parameters / Source / Robustness panel ─── */
            <div style={styles.panelSlide} key="controls">
              {/* Tab bar */}
              <div style={styles.tabBar}>
                {["params", "source", "robust"].map((t) => (
                  <button
                    key={t}
                    style={{ ...styles.tabBtn, ...(tab === t ? styles.tabBtnActive : {}) }}
                    onClick={() => setTab(t)}
                  >
                    {t === "params" ? "Parameters" : t === "source" ? "Source" : "Robustness"}
                  </button>
                ))}
              </div>

              {tab === "params" && (
                <div style={styles.section}>
                  <h3 style={styles.sectionTitle}>Parameters</h3>

                  <label style={styles.label}>X-axis dataset</label>
                  <select style={styles.select} value={xDs} onChange={(e) => setXDs(e.target.value)}>
                    {datasets.map((d) => {
                      const meta = DATASET_META[d.dataset_id];
                      return (
                        <option key={d.dataset_id} value={d.dataset_id}>
                          {meta ? `${meta.icon} ` : ""}{meta?.label || d.dataset_id} ({d.county_count})
                        </option>
                      );
                    })}
                  </select>

                  <label style={styles.label}>Y-axis dataset</label>
                  <select style={styles.select} value={yDs} onChange={(e) => setYDs(e.target.value)}>
                    {datasets.map((d) => {
                      const meta = DATASET_META[d.dataset_id];
                      return (
                        <option key={d.dataset_id} value={d.dataset_id}>
                          {meta ? `${meta.icon} ` : ""}{meta?.label || d.dataset_id} ({d.county_count})
                        </option>
                      );
                    })}
                  </select>

                  <label style={styles.label}>Normalization</label>
                  <select style={styles.select} value={normMethod} onChange={(e) => setNormMethod(e.target.value)}>
                    {NORM_METHODS.map((m) => <option key={m} value={m}>{m}</option>)}
                  </select>

                  <label style={styles.label}>Outlier treatment</label>
                  <select style={styles.select} value={outlierMethod} onChange={(e) => setOutlierMethod(e.target.value)}>
                    {OUTLIER_METHODS.map((m) => <option key={m} value={m}>{m}</option>)}
                  </select>
                </div>
              )}

              {tab === "source" && (
                <div style={styles.section}>
                  <h3 style={styles.sectionTitle}>Data Sources</h3>
                  <p style={styles.mutedText}>
                    {scatter?.n || 0} counties in current scatter from {xLabel} × {yLabel}
                  </p>
                </div>
              )}

              {tab === "robust" && (
                <div style={styles.section}>
                  <h3 style={styles.sectionTitle}>Robustness</h3>
                  <p style={styles.mutedText}>
                    Current: r = {scatter?.r.toFixed(3)} with {normMethod} + {outlierMethod}
                  </p>
                </div>
              )}
            </div>
          )}
        </aside>
      </div>
    </div>
  );
}

// ══════════════════════════════════════════════════════════════
// STYLES (inline for Lovable compatibility)
// ══════════════════════════════════════════════════════════════
const styles = {
  app: { minHeight: "100vh", display: "flex", flexDirection: "column", background: "#0f0f1a", color: "#e2e8f0", fontFamily: "'Inter', -apple-system, sans-serif" },
  header: { display: "flex", alignItems: "baseline", gap: 16, padding: "16px 24px", borderBottom: "1px solid #1e1e2e", background: "#13131f" },
  h1: { fontSize: 20, fontWeight: 600, margin: 0 },
  subtitle: { fontSize: 13, color: "#64748b" },
  body: { display: "flex", flex: 1, overflow: "hidden" },
  main: { flex: 1, position: "relative", padding: 24, overflowY: "auto" },
  loadingOverlay: { position: "absolute", inset: 0, display: "flex", alignItems: "center", justifyContent: "center", background: "rgba(15,15,26,0.7)", zIndex: 10, fontSize: 18, color: "#94a3b8" },
  scatterHeader: { display: "flex", alignItems: "baseline", gap: 16, marginBottom: 8 },
  h2: { fontSize: 16, fontWeight: 500, margin: 0 },
  stats: { fontSize: 13, color: "#94a3b8", fontFamily: "monospace" },
  tooltip: { background: "#1e1e2e", border: "1px solid #334155", borderRadius: 6, padding: "8px 12px", fontSize: 12, lineHeight: 1.5 },

  sidePanel: { width: 360, minWidth: 360, borderLeft: "1px solid #1e1e2e", background: "#13131f", overflowY: "auto", position: "relative" },
  panelSlide: { animation: "slideIn 200ms ease-out" },

  closeBtn: { position: "absolute", top: 12, right: 12, width: 28, height: 28, background: "#1e1e2e", border: "1px solid #334155", borderRadius: "50%", color: "#94a3b8", fontSize: 14, cursor: "pointer", display: "flex", alignItems: "center", justifyContent: "center", zIndex: 5 },

  section: { padding: 16, borderBottom: "1px solid #1e1e2e" },
  sectionTitle: { fontSize: 13, fontWeight: 600, textTransform: "uppercase", letterSpacing: 0.5, color: "#94a3b8", marginBottom: 12, marginTop: 0 },
  mutedText: { fontSize: 12, color: "#64748b", margin: "4px 0" },
  label: { display: "block", fontSize: 12, color: "#64748b", margin: "10px 0 4px" },
  select: { width: "100%", padding: "6px 8px", background: "#1e1e2e", border: "1px solid #334155", borderRadius: 4, color: "#e2e8f0", fontSize: 13 },

  tabBar: { display: "flex", borderBottom: "1px solid #1e1e2e" },
  tabBtn: { flex: 1, padding: "10px 4px", background: "none", border: "none", borderBottom: "2px solid transparent", color: "#64748b", fontSize: 12, cursor: "pointer" },
  tabBtnActive: { color: "#e2e8f0", borderBottomColor: "#6366f1" },

  dsRow: { marginBottom: 10 },
  barTrack: { height: 4, background: "#1e1e2e", borderRadius: 2, marginTop: 4, overflow: "hidden" },
  barFill: { height: "100%", borderRadius: 2, transition: "width 300ms ease" },

  similarRow: { display: "flex", alignItems: "center", justifyContent: "space-between", padding: "6px 8px", borderRadius: 4, cursor: "pointer", fontSize: 12, transition: "background 150ms" },

  flagCard: { padding: "10px 12px", borderRadius: 6, background: "#1a1a2e", borderLeft: "3px solid #475569", marginBottom: 8 },
};
