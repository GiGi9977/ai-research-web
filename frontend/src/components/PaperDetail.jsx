import { useState } from "react";
import { updatePaper } from "../api.js";
import ChatPanel from "./ChatPanel.jsx";
import SummaryPanel from "./SummaryPanel.jsx";

export default function PaperDetail({ paper, onUpdated, onDelete, onClose }) {
  const [editing, setEditing] = useState(false);
  const [form, setForm] = useState({});
  const [error, setError] = useState("");

  function startEdit() {
    setForm({
      title: paper.title,
      authors: paper.authors.join(", "),
      year: paper.year ?? "",
      abstract: paper.abstract ?? "",
    });
    setEditing(true);
  }

  async function onSave(e) {
    e.preventDefault();
    setError("");
    try {
      const updated = await updatePaper(paper.id, {
        title: form.title.trim(),
        authors: form.authors.split(",").map((a) => a.trim()).filter(Boolean),
        year: form.year === "" ? null : Number(form.year),
        abstract: form.abstract.trim() || null,
      });
      onUpdated({ ...paper, ...updated });
      setEditing(false);
    } catch (err) {
      setError(err.message);
    }
  }

  const set = (k) => (e) => setForm({ ...form, [k]: e.target.value });

  return (
    <div className="detail">
      <button className="link" onClick={onClose}>← Back to library</button>
      {editing ? (
        <form onSubmit={onSave} className="edit-form">
          <label>Title<input value={form.title} onChange={set("title")} required /></label>
          <label>Authors (comma separated)<input value={form.authors} onChange={set("authors")} /></label>
          <label>Year<input type="number" value={form.year} onChange={set("year")} /></label>
          <label>Abstract<textarea rows={8} value={form.abstract} onChange={set("abstract")} /></label>
          {error && <p className="error">{error}</p>}
          <div className="card-actions">
            <button type="submit">Save changes</button>
            <button type="button" className="secondary" onClick={() => setEditing(false)}>Cancel</button>
          </div>
        </form>
      ) : (
        <>
          <h2>{paper.title}</h2>
          <p className="meta">
            {paper.authors.length ? paper.authors.join(", ") : "Unknown authors"}
            {paper.year ? ` · ${paper.year}` : ""} · {paper.source}
            {paper.hasFullText ? " · full text stored" : " · abstract only"}
          </p>
          <p className="abstract">{paper.abstract || "No abstract available."}</p>
          <div className="card-actions">
            {paper.url && <a href={paper.url} target="_blank" rel="noreferrer">Open paper ↗</a>}
            <button className="secondary" onClick={startEdit}>Edit metadata</button>
            <button className="danger" onClick={() => onDelete(paper)}>Delete</button>
          </div>
        </>
      )}
      {!editing && (
        <>
          <SummaryPanel key={`s${paper.id}`} paper={paper} />
          <ChatPanel key={`c${paper.id}`} paper={paper} />
        </>
      )}
    </div>
  );
}
