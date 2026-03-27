import { useEffect, useState, useCallback, useMemo } from "react";
import {
  fetchDatasets,
  fetchScatter,
  askQuestion,
  type DatasetInfo,
  type ScatterPoint,
  type ScatterResponse,
} from "./lib/api";
import { executeQuery, type QueryResult, type QueryType } from "./lib/queryEngine";
import ScatterPlot from "./components/ScatterPlot";
import ParametersPanel from "./components/ParametersPanel";
import ProvenancePanel from "./components/ProvenancePanel";
import RobustnessPanel from "./components/RobustnessPanel";
import CountyPanel from "./components/CountyPanel";
import AskBar from "./components/AskBar";
import QueryResultPanel from "./components/QueryResultPanel";
import "./App.css";

type Tab = "params" | "provenance" | "robustness";

const FALLBACK_QUESTIONS = [
  "Show me Southern counties with high mobility",
  "Which region has the strongest correlation?",
  "Show the top 10 counties for library spending",
  "What do the outlier counties have in common?",
];

export default function App() {
  const [datasets, setDatasets] = useState<DatasetInfo[]>([]);
  const [datasetX, setDatasetX] = useState("library");
  const [datasetY, setDatasetY] = useState("mobility");
  const [normMethod, setNormMethod] = useState("zscore");
  const [outlierMethod, setOutlierMethod] = useState("keep");
  const [weightMethod, setWeightMethod] = useState("equal");
  const [scatter, setScatter] = useState<ScatterResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [tab, setTab] = useState<Tab>("params");
  const [selectedCounty, setSelectedCounty] = useState<ScatterPoint | null>(null);
  const [highlightedFips, setHighlightedFips] = useState<string | null>(null);

  // Ask feature state
  const [askOpen, setAskOpen] = useState(false);
  const [askLoading, setAskLoading] = useState(false);
  const [askHistory, setAskHistory] = useState<string[]>([]);
  const [queryResult, setQueryResult] = useState<QueryResult | null>(null);
  const [rawLlmJson, setRawLlmJson] = useState<string | null>(null);

  // Set of FIPS to highlight from query results
  const highlightFipsList = useMemo(
    () => new Set(queryResult?.highlightFips ?? []),
    [queryResult],
  );

  // Load dataset list
  useEffect(() => {
    fetchDatasets().then(setDatasets).catch(console.error);
  }, []);

  // Load scatter data
  const loadScatter = useCallback(() => {
    setLoading(true);
    setSelectedCounty(null);
    setHighlightedFips(null);
    setQueryResult(null);
    fetchScatter(datasetX, datasetY, normMethod, outlierMethod, weightMethod)
      .then(setScatter)
      .catch(console.error)
      .finally(() => setLoading(false));
  }, [datasetX, datasetY, normMethod, outlierMethod, weightMethod]);

  useEffect(() => {
    if (datasets.length > 0) loadScatter();
  }, [loadScatter, datasets]);

  const handleClickPoint = (point: ScatterPoint) => {
    setSelectedCounty(point);
    setHighlightedFips(null);
  };

  const handleCloseCounty = () => {
    setSelectedCounty(null);
    setHighlightedFips(null);
  };

  const handleSelectSimilar = (fips: string) => {
    setHighlightedFips(fips);
    const found = scatter?.points.find((p) => p.fips === fips);
    if (found) setSelectedCounty(found);
  };

  // ── Ask handler ──────────────────────────────
  const handleAsk = async (question: string) => {
    if (!scatter) return;
    setAskLoading(true);
    setQueryResult(null);
    setRawLlmJson(null);

    // Update history (keep last 3)
    setAskHistory((prev) => {
      const next = [question, ...prev.filter((q) => q !== question)];
      return next.slice(0, 3);
    });

    try {
      const resp = await askQuestion(question, datasetX, datasetY);

      if (resp.error) {
        // LLM call failed — show fallback buttons
        setQueryResult({
          type: "conceptual",
          title: resp.error,
          sampleSize: scatter.points.length,
          highlightFips: [],
          rows: [],
          suggestions: FALLBACK_QUESTIONS,
        });
        setRawLlmJson(null);
      } else {
        const qType = resp.query_type as QueryType;
        const result = executeQuery(
          qType,
          resp.params,
          scatter.points,
          datasetX,
          datasetY,
        );
        setQueryResult(result);
        setRawLlmJson(resp.raw_llm_json ?? null);
      }
    } catch {
      // Network failure — show fallback
      setQueryResult({
        type: "conceptual",
        title: "Could not reach the query service",
        sampleSize: scatter?.points.length ?? 0,
        highlightFips: [],
        rows: [],
        suggestions: FALLBACK_QUESTIONS,
      });
    } finally {
      setAskLoading(false);
    }
  };

  const handleSuggestionClick = (question: string) => {
    handleAsk(question);
  };

  const handleClearResult = () => {
    setQueryResult(null);
    setRawLlmJson(null);
  };

  return (
    <div className="app">
      <header className="app-header">
        <h1>Discovery Surface</h1>
        <span className="app-subtitle">County-level correlation explorer</span>
      </header>

      <div className="app-body">
        <main className="main-area">
          {loading && <div className="loading-overlay">Loading...</div>}
          {scatter && (
            <>
              <div className="scatter-wrap">
                <ScatterPlot
                  points={scatter.points}
                  datasetX={datasetX}
                  datasetY={datasetY}
                  r={scatter.r}
                  n={scatter.n}
                  selectedFips={selectedCounty?.fips ?? null}
                  highlightedFips={highlightedFips}
                  highlightFipsList={highlightFipsList}
                  onClickPoint={handleClickPoint}
                />
                <AskBar
                  onSubmit={handleAsk}
                  loading={askLoading}
                  history={askHistory}
                  visible={askOpen}
                  onToggle={() => { setAskOpen(!askOpen); if (askOpen) handleClearResult(); }}
                />
              </div>

              {queryResult && (
                <QueryResultPanel
                  result={queryResult}
                  rawJson={rawLlmJson}
                  onSuggestionClick={handleSuggestionClick}
                  onClose={handleClearResult}
                />
              )}
            </>
          )}
        </main>

        <aside className={`side-panel ${selectedCounty ? "county-active" : ""}`}>
          {selectedCounty ? (
            <div className="panel-slide-in" key={`county-${selectedCounty.fips}`}>
              <CountyPanel
                point={selectedCounty}
                allPoints={scatter?.points ?? []}
                datasetX={datasetX}
                datasetY={datasetY}
                onClose={handleCloseCounty}
                onSelectCounty={handleSelectSimilar}
              />
            </div>
          ) : (
            <div className="panel-slide-in" key="controls">
              <div className="tab-bar">
                <button className={tab === "params" ? "active" : ""} onClick={() => setTab("params")}>
                  Parameters
                </button>
                <button className={tab === "provenance" ? "active" : ""} onClick={() => setTab("provenance")}>
                  Provenance
                </button>
                <button className={tab === "robustness" ? "active" : ""} onClick={() => setTab("robustness")}>
                  Robustness
                </button>
              </div>

              {tab === "params" && (
                <ParametersPanel
                  datasets={datasets}
                  datasetX={datasetX}
                  datasetY={datasetY}
                  normMethod={normMethod}
                  outlierMethod={outlierMethod}
                  weightMethod={weightMethod}
                  onDatasetX={setDatasetX}
                  onDatasetY={setDatasetY}
                  onNormMethod={setNormMethod}
                  onOutlierMethod={setOutlierMethod}
                  onWeightMethod={setWeightMethod}
                />
              )}
              {tab === "provenance" && (
                <ProvenancePanel datasetX={datasetX} datasetY={datasetY} />
              )}
              {tab === "robustness" && (
                <RobustnessPanel datasetX={datasetX} datasetY={datasetY} />
              )}
            </div>
          )}
        </aside>
      </div>
    </div>
  );
}
