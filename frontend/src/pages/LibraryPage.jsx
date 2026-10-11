import { useEffect, useState } from "react";
import { deletePaper, getPaper, listPapers } from "../api.js";
import PaperCard from "../components/PaperCard.jsx";
import PaperDetail from "../components/PaperDetail.jsx";
import UploadDropzone from "../components/UploadDropzone.jsx";

export default function LibraryPage() {
  const [papers, setPapers] = useState(null);
  const [selected, setSelected] = useState(null);
  const [error, setError] = useState("");

  useEffect(() => {
    listPapers().then(setPapers).catch((e) => setError(e.message));
  }, []);

  async function open(id) {
    setError("");
    try {
      setSelected(await getPaper(id));
    } catch (e) {
      setError(e.message);
    }
  }

  async function remove(paper) {
    if (!window.confirm(`Delete "${paper.title}" from your library?`)) return;
    try {
      await deletePaper(paper.id);
      setPapers((ps) => ps.filter((p) => p.id !== paper.id));
      setSelected(null);
    } catch (e) {
      setError(e.message);
    }
  }

  function onUpdated(updated) {
    setSelected(updated);
    setPapers((ps) => ps.map((p) => (p.id === updated.id ? { ...p, ...updated } : p)));
  }

  if (selected) {
    return (
      <PaperDetail
        paper={selected}
        onUpdated={onUpdated}
        onDelete={remove}
        onClose={() => setSelected(null)}
      />
    );
  }

  return (
    <section>
      <UploadDropzone
        onUploaded={(paper) => {
          setPapers((ps) => [paper, ...(ps ?? [])]);
          open(paper.id);
        }}
      />
      {error && <p className="error">{error}</p>}
      {papers === null && !error && <p>Loading…</p>}
      {papers?.length === 0 && <p>Your library is empty. Search for papers and save them here.</p>}
      {papers?.map((p) => (
        <PaperCard
          key={p.id}
          paper={p}
          actions={<button onClick={() => open(p.id)}>Open</button>}
        />
      ))}
    </section>
  );
}
