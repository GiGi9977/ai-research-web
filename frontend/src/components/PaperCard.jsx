import { useState } from "react";

const ABSTRACT_PREVIEW = 300;

export default function PaperCard({ paper, actions }) {
  const [expanded, setExpanded] = useState(false);
  const abstract = paper.abstract || "";
  const long = abstract.length > ABSTRACT_PREVIEW;
  const shown = expanded || !long ? abstract : abstract.slice(0, ABSTRACT_PREVIEW) + "…";

  return (
    <article className="card">
      <h3>{paper.title}</h3>
      <p className="meta">
        {paper.authors?.length ? paper.authors.join(", ") : "Unknown authors"}
        {paper.year ? ` · ${paper.year}` : ""}
      </p>
      <p className="abstract">{shown || "No abstract available."}</p>
      <div className="card-actions">
        {long && (
          <button className="link" onClick={() => setExpanded(!expanded)}>
            {expanded ? "Show less" : "Show more"}
          </button>
        )}
        {paper.url && (
          <a href={paper.url} target="_blank" rel="noreferrer">
            Open paper ↗
          </a>
        )}
        {actions}
      </div>
    </article>
  );
}
