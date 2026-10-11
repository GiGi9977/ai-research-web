import { useEffect, useState } from "react";
import { listPapers, savePaper, searchPapers } from "../api.js";
import PaperCard from "../components/PaperCard.jsx";

export default function SearchPage() {
  const [query, setQuery] = useState("");
  const [results, setResults] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [savedIds, setSavedIds] = useState(new Set());
  const [saving, setSaving] = useState(null);

  useEffect(() => {
    listPapers()
      .then((papers) => setSavedIds(new Set(papers.map((p) => p.externalId))))
      .catch(() => {});
  }, []);

  async function onSubmit(e) {
    e.preventDefault();
    if (!query.trim()) return;
    setLoading(true);
    setError("");
    try {
      setResults(await searchPapers(query.trim()));
    } catch (err) {
      setError(err.message);
      setResults(null);
    } finally {
      setLoading(false);
    }
  }

  async function onSave(paper) {
    setSaving(paper.externalId);
    setError("");
    try {
      await savePaper(paper);
      setSavedIds((ids) => new Set(ids).add(paper.externalId));
    } catch (err) {
      setError(`Could not save "${paper.title}": ${err.message}`);
    } finally {
      setSaving(null);
    }
  }

  return (
    <section>
      <form className="search-bar" onSubmit={onSubmit}>
        <input
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          placeholder="Search papers by keyword or topic…"
        />
        <button type="submit" disabled={loading}>
          {loading ? "Searching…" : "Search"}
        </button>
      </form>
      {error && <p className="error">{error}</p>}
      {results && results.length === 0 && <p>No papers found.</p>}
      {results?.map((p) => {
        const saved = savedIds.has(p.externalId);
        return (
          <PaperCard
            key={p.externalId}
            paper={p}
            actions={
              <button
                onClick={() => onSave(p)}
                disabled={saved || saving === p.externalId}
              >
                {saved ? "Saved ✓" : saving === p.externalId ? "Saving…" : "Save to library"}
              </button>
            }
          />
        );
      })}
    </section>
  );
}
