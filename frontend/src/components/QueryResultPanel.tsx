import { useState } from "react";
import type { QueryResult } from "../lib/queryEngine";

interface Props {
  result: QueryResult;
  rawJson?: string | null;
  onSuggestionClick: (question: string) => void;
  onClose: () => void;
}

export default function QueryResultPanel({ result, rawJson, onSuggestionClick, onClose }: Props) {
  const [showQuery, setShowQuery] = useState(false);

  return (
    <div className="qr-panel">
      <div className="qr-header">
        <h3>{result.title}</h3>
        <button className="qr-close" onClick={onClose}>✕</button>
      </div>

      <div className="qr-sample-size">
        {result.type === "filter"
          ? `Filtered from ${result.sampleSize} counties — ${result.highlightFips.length} match`
          : `Computed across ${result.sampleSize} counties`}
      </div>

      {/* Bar chart for aggregate results */}
      {result.bars && result.bars.length > 0 && (
        <div className="qr-bars">
          {result.bars.map((bar) => {
            const maxVal = Math.max(...result.bars!.map((b) => Math.abs(b.value)));
            const pct = maxVal > 0 ? (Math.abs(bar.value) / maxVal) * 100 : 0;
            return (
              <div key={bar.label} className="qr-bar-row">
                <span className="qr-bar-label">{bar.label}</span>
                <div className="qr-bar-track">
                  <div
                    className="qr-bar-fill"
                    style={{ width: `${pct}%` }}
                  />
                </div>
                <span className="qr-bar-value">{bar.value.toFixed(3)}</span>
              </div>
            );
          })}
        </div>
      )}

      {/* Table rows */}
      {result.rows.length > 0 && (
        <div className="qr-table">
          {result.rows.map((row, i) => (
            <div key={i} className="qr-row">
              <span className="qr-row-label">{row.label}</span>
              <span className="qr-row-value">{row.value}</span>
            </div>
          ))}
          {result.type === "filter" && result.highlightFips.length > 20 && (
            <div className="qr-row qr-more">
              ...and {result.highlightFips.length - 20} more counties highlighted on plot
            </div>
          )}
        </div>
      )}

      {/* Conceptual fallback: suggestions */}
      {result.suggestions && result.suggestions.length > 0 && (
        <div className="qr-suggestions">
          <div className="qr-suggestions-label">
            {result.type === "conceptual"
              ? "This question goes beyond the current dataset. Try these instead:"
              : "Try a different query:"}
          </div>
          {result.suggestions.map((s, i) => (
            <button
              key={i}
              className="qr-suggestion-btn"
              onClick={() => onSuggestionClick(s)}
            >
              {s}
            </button>
          ))}
        </div>
      )}

      {/* Footer */}
      <div className="qr-footer">
        <span>Computed from dataset values &middot; not AI-generated &middot;</span>
        <button className="qr-show-query" onClick={() => setShowQuery(!showQuery)}>
          {showQuery ? "hide query" : "show query"}
        </button>
      </div>

      {showQuery && rawJson && (
        <pre className="qr-raw-json">{rawJson}</pre>
      )}
    </div>
  );
}
