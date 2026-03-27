import { useState, useRef, useEffect } from "react";

interface Props {
  onSubmit: (question: string) => void;
  loading: boolean;
  history: string[];
  visible: boolean;
  onToggle: () => void;
}

export default function AskBar({ onSubmit, loading, history, visible, onToggle }: Props) {
  const [text, setText] = useState("");
  const inputRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    if (visible) inputRef.current?.focus();
  }, [visible]);

  const handleSubmit = () => {
    const q = text.trim();
    if (!q || loading) return;
    onSubmit(q);
    setText("");
  };

  return (
    <>
      {/* Toggle button — bottom-left of scatter */}
      {!visible && (
        <button className="ask-toggle" onClick={onToggle}>
          &#9000; Ask
        </button>
      )}

      {/* Input bar */}
      {visible && (
        <div className="ask-bar">
          {/* History chips */}
          {history.length > 0 && (
            <div className="ask-history">
              {history.map((q, i) => (
                <button
                  key={i}
                  className="ask-chip"
                  onClick={() => { setText(q); inputRef.current?.focus(); }}
                  title={q}
                >
                  {q.length > 40 ? q.slice(0, 37) + "..." : q}
                </button>
              ))}
            </div>
          )}
          <div className="ask-input-row">
            <input
              ref={inputRef}
              className="ask-input"
              type="text"
              placeholder="Ask a question about this data..."
              value={text}
              onChange={(e) => setText(e.target.value)}
              onKeyDown={(e) => { if (e.key === "Enter") handleSubmit(); }}
              disabled={loading}
            />
            <button
              className="ask-submit"
              onClick={handleSubmit}
              disabled={loading || !text.trim()}
            >
              {loading ? "..." : "Go"}
            </button>
            <button className="ask-close" onClick={onToggle}>✕</button>
          </div>
        </div>
      )}
    </>
  );
}
