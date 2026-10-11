import { useRef, useState } from "react";
import { uploadPaper } from "../api.js";

export default function UploadDropzone({ onUploaded }) {
  const inputRef = useRef(null);
  const [busy, setBusy] = useState(false);
  const [dragging, setDragging] = useState(false);
  const [error, setError] = useState("");

  async function handleFiles(files) {
    const file = files?.[0];
    if (!file) return;
    setBusy(true);
    setError("");
    try {
      onUploaded(await uploadPaper(file));
    } catch (err) {
      setError(`${file.name}: ${err.message}`);
    } finally {
      setBusy(false);
      if (inputRef.current) inputRef.current.value = "";
    }
  }

  return (
    <div
      className={`dropzone${dragging ? " dragging" : ""}`}
      onDragOver={(e) => {
        e.preventDefault();
        setDragging(true);
      }}
      onDragLeave={() => setDragging(false)}
      onDrop={(e) => {
        e.preventDefault();
        setDragging(false);
        handleFiles(e.dataTransfer.files);
      }}
    >
      <input
        ref={inputRef}
        type="file"
        accept="application/pdf,.pdf"
        hidden
        onChange={(e) => handleFiles(e.target.files)}
      />
      {busy ? (
        <p>Extracting text and metadata…</p>
      ) : (
        <p>
          Drop a PDF here or{" "}
          <button className="link" onClick={() => inputRef.current.click()}>
            choose a file
          </button>
        </p>
      )}
      {error && <p className="error">{error}</p>}
    </div>
  );
}
