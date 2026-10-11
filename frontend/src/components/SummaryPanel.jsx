import { useState } from "react";
import { summarizePaper } from "../api.js";
import RichText from "./RichText.jsx";

export default function SummaryPanel({ paper }) {
  const [summary, setSummary] = useState(paper.summary || "");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  async function generate(refresh) {
    setLoading(true);
    setError("");
    try {
      setSummary((await summarizePaper(paper.id, refresh)).summary);
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  }

  return (
    <section className="panel">
      <div className="panel-head">
        <h3>Summary</h3>
        <button onClick={() => generate(Boolean(summary))} disabled={loading}>
          {loading ? "Summarizing…" : summary ? "Regenerate" : "Generate summary"}
        </button>
      </div>
      {!paper.hasFullText && (
        <p className="meta">Full text isn't stored for this paper, so the summary uses the abstract only.</p>
      )}
      {error && <p className="error">{error}</p>}
      {summary && <div className="summary"><RichText text={summary} /></div>}
    </section>
  );
}
